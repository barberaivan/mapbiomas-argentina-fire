# 02 — Model fitting (obs-level burn probability)

One elastic-net logistic regression per `veg_fire` class, fit locally in R with `glmnet` on the
cleaned training observations from step 01. Its output is a table of coefficients per class —
the small, portable artifact that the GEE prediction pipeline (steps 03+) evaluates at every
Landsat pixel-date in Argentina.

## Foundations

**The model has to be deployable inside GEE, and that constraint chose it.** A fitted logistic
regression is a set of coefficients plus a simple equation: trivial to store, to version, to
ship as a CSV, and cheap to evaluate over billions of pixel-dates. The richer classifiers GEE
offers natively — random forest, boosted trees — fail on both ends here: it's likely they could not be
fitted on this many training observations, and a fitted one cannot be saved as an asset, which
is what deploying over the whole Landsat archive requires. External ML/DL models on Vertex AI
would lift both limits, at a large step up in complexity, but that implies an economic cost to
MapBiomas.

**Every class shares one predictor set**, chosen globally rather than per class: only the
coefficients differ between vegetation types. That keeps deployment cheap in the same way the
model itself does — the prediction pipeline builds one band set once and reuses it for all 23
classes, instead of assembling a different design per vegetation type and paying for it at every
pixel-date.

**We also wanted a natively probabilistic model**, because everything downstream consumes a
probability rather than a hard class — the time-series metrics of step 03 read the shape of
`p` through time. GEE's constraint bites again: a probability-mode random forest is not
exportable to an asset. Only a regression-mode forest on binary data would return something
probability-like, and getting calibrated probabilities out of it means tuning minimum node size
against `N` — a dependency that would have to be re-tuned per class. Logistic regression gives
the probability by construction, with nothing to tune for it.

Fitting happens **locally in R**, not in GEE. The training set is a few million observations,
which `glmnet` handles well, and only the coefficients need to cross into GEE.

## Inputs → Outputs

`training_observations_{region}_v{V}.csv` (with the `fit` gate) + `config/veg_fire_remap.csv`
→ **`workflow/02-model_fitting.R`** → one coefficient table per class

| | What it is | Where |
|---|---|---|
| **in** | cleaned training observations, one CSV per region | `data/training_observations_{region}_v{V}.csv` — see [`01-training_data.md`](01-training_data.md), [`02-data_cleaning.md`](02-data_cleaning.md) |
| **in** | which `veg_fire` classes exist and which regions each spans | `config/veg_fire_remap.csv` — see [`02-vegetation_remap.md`](02-vegetation_remap.md) |
| **out** | coefficients, one folder per model variant, tracked | `models/P<NNN>/class_NN_coefficients.csv` |
| **out** | heavy per-class artifacts (`cv_metrics`, `tuning`, `fit.rds`, `oof_predictions`) | `models-store/` (git-ignored, Insync store) |

**`models/P050/` is what production reads.** `C.DEPLOYED_MODEL` in `utils/constants.py` selects
the variant and `C.COEF_DIR` points at it, so redeploying a different one is that single
constant. `COEF_TAG` chooses the destination folder at write time (default `P129`).
[`../models/README.md`](../models/README.md) has the output schema and the coefficient
fold-back / GEE-export details.

## How it works

The fitting unit is the **`veg_fire` class**, not the region: a class may span regions, so the
driver reads each class's regions from `config/veg_fire_remap.csv`, loads only those region
CSVs, and skips classes whose regions are not all downloaded yet. `workflow/02-model_fitting.R`
is the source of truth for the design — term lists, block sizes, α grid and CV are defined
there.

### Predictors

**The deployed model carries 51 terms + intercept** (52 coefficient rows): 10 focal mains, 14
previous-year mosaic mains, 10 focal×focal, 4 same-band, 6 prev×fire-index, 7 prev×fire-band —
the same terms in every class, as Foundations says. It is the top-P=50 cut of the 129-term set
the fit works in; see the Key decisions below.

Interactions are fit on mean-centered factors and folded back to raw-product scale at export, so
GEE evaluates raw products directly.

### Tuning and cross-validation

α grid `{0.25, 0.5, 0.75}` (ridge and lasso dropped — never best in CV), selected at
`lambda.min`, `nlambda=50`, `lambda.min.ratio=1e-4`. The convergence tolerance `thresh` is the
real speed lever on this ill-conditioned design: it starts at `1e-4` and is **adaptive** — each
α gets a wall-clock budget (`FIT_TIMEOUT_SEC`, 600 s) and is refit looser if it blows it, so no
slow-class list is hardcoded. `THRESH_START` pre-seeds classes already known to crawl.

CV is **grouped K-fold on region-unique fire id** — whole fires held out, with stratified
packing so folds carry comparable positive counts. K is adaptive, `min(10, n_fires_with_positives)`:
21 of the 23 fittable classes fit at K=10, two at 7 and 6. Out-of-fold `p_i` is saved per
observation.

## Run

```bash
# pre-flight: confirm each class has enough positive-bearing fires for grouped CV
$PYTHON collection-01/scripts/cv_feasibility_report.py --version 1

# fit all fittable classes whose region data is downloaded ...
Rscript collection-01/workflow/02-model_fitting.R 1
# ... or named classes (memory-heavy ones: FIT_CORES=2 or 1)
Rscript collection-01/workflow/02-model_fitting.R 1 grassland_pampa
```

Memory is auto-sized per class to a RAM budget; `FIT_CORES` overrides.

## Key decisions

- **P=50 is the deployed predictor set, not the 129 it was fit with.** Term count dominates
  per-tile prediction cost in step 03, so the 129 terms were ranked globally and cut to a top-P
  subset; predictive skill is flat from the full fit down to P≈50 and drops below it. `P` is a
  **percentile cut on that ranking, not a term count** — P=50 keeps 51 terms. The route
  — two separate reductions, from 427 terms and then from 129 — is in
  [`notes/02-lr_term_reduction.md`](notes/02-lr_term_reduction.md); the decision record is
  [`03-bpts.md`](03-bpts.md) "Key decisions".
- **Every variant keeps its own tracked folder** rather than the chosen one being promoted into
  a single `models/`. The deployed coefficients then travel with the repo, which is what the
  Colab multi-account export of step 03 needs.
- **Whole fires are held out in CV, keyed region-uniquely.** Observations from one fire are
  strongly correlated; splitting them across folds would report a skill the model does not have
  on a new fire. Bare `fire_id`s repeat across regions, so the grouping key is `region_fire_id`.

## Gotchas

- A class's CV folds are built from **fires with positives**, so a class with few such fires
  silently fits at K < 10. Check `K` in its `cv_metrics.csv` before comparing classes.
- `scripts/cv_feasibility_report.py` is a pre-flight, not a gate — the fit will still start on a
  class the report flags.

## Files

| File | Role |
|---|---|
| `workflow/02-model_fitting.R` | the fit (source of truth for the design) |
| `config/veg_fire_remap.csv` | defines the classes to fit (see [`02-vegetation_remap.md`](02-vegetation_remap.md)) |
| `scripts/cv_feasibility_report.py` | pre-flight CV feasibility per class |
| `scripts/refit_pruning_sweep.R` | refits every top-P variant through the fit's `KEEP_TERMS_CSV` / `COEF_TAG` hooks |
| `models/P<NNN>/class_*_coefficients.csv` | tracked fitted outputs; `P050/` is the GEE deliverable |
| `utils/constants.py` (`DEPLOYED_MODEL`, `COEF_DIR`) | which variant production reads |
| `models-store/class_*`, `models-store/cv_metrics_v1.csv` | heavy fitted outputs (gitignored) |
| `models/README.md` | output schema + coefficient export details |

## Related

- [`notes/02-lr_term_reduction.md`](notes/02-lr_term_reduction.md) — how the predictor set got
  from 427 terms to 50, and what `K3` in the sweep's paths actually means.
- `notebooks/logistic_regression_design.qmd` — evidence for the 427 → 129 reduction.
- `notebooks/lr_term_pruning.qmd` — evidence for the 129 → top-P reduction.
- `notebooks/model_fit_diagnostics.qmd` — per-class diagnostics (tuning, coefficients,
  calibration, OOF, omission/commission, by-fire OOF breakdown); auto-discovers every fitted
  `class_*`.
- [`02-diagnostic_plots.md`](02-diagnostic_plots.md) — the per-fire time-series panels, which
  are **not** in the diagnostics notebook.
