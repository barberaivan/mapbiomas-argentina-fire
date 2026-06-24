# 02 — Model fitting (obs-level burn probability)

One elastic-net logistic regression per `veg_fire` class, fit locally in R with `glmnet`.
Output coefficients feed the GEE prediction pipeline (steps 03+). The **design rationale**
lives in the notebook; this note is the operational map.

## Approach (summary)

- **Model**: regularized logistic regression (`glmnet`, elastic net). Cheap to evaluate in
  GEE over billions of pixel-dates, which is why LR over RF/NN.
- **Design**: a reduced **129-term** predictor set (11 focal mains + 32 prev-year mosaic
  mains + 22 focal×focal + 10 same-band + 22 prev×fire-index + 32 prev×fire-band). Reduced
  from a 427-term "canonical-team" design that was too collinear to fit quickly — the full
  story (correlation pruning, exact-linear-combo cut, VIF/eigenvalue analysis) is in
  `notebooks/logistic_regression_design.qmd`.
- **Tuning**: α grid `{0.25, 0.5, 0.75}` (ridge & lasso dropped), `lambda.min`,
  `nlambda=50`, `thresh=1e-4` (the real convergence-speed lever). Interactions fit on
  mean-centered factors, folded back to raw-product scale at export.
- **CV**: grouped K-fold (K=10), grouped by **region-unique fire id** (whole fires held
  out), stratified packing. Out-of-fold `p_i` saved per observation.
- The fitting unit is the **`veg_fire` class** (may span regions); the driver loads whichever
  region CSVs a class needs, from `config/veg_fire_remap.csv`.

## Run

```bash
# pre-flight: confirm each class has enough positive-bearing fires for grouped CV
$PYTHON collection-01/scripts/cv_feasibility_report.py --version 1

# fit all fittable classes whose region data is downloaded ...
Rscript collection-01/workflow/02-model_fitting.R 1
# ... or named classes (memory-heavy ones: FIT_CORES=2 or 1)
Rscript collection-01/workflow/02-model_fitting.R 1 grassland_pampa
```

`workflow/02-model_fitting.R` is the **source of truth** for the design (the term lists,
block sizes, α grid and CV are defined there). Memory is auto-sized per class to a RAM budget;
`FIT_CORES` overrides.

## Outputs (`models/` + `models-store/`)

Per class `class_NN_*`: `coefficients.csv` (tracked, in `models/` — the small GEE deliverable)
and `cv_metrics.csv`, `tuning.csv`, `fit.rds`, `oof_predictions.csv` (git-ignored, large —
live in `models-store/`, the Insync-synced store symlinked in by `setup.sh`).
`cv_metrics_v1.csv` is the cross-class summary, also in `models-store/`. The `class_NN` ↔
`veg_fire_name` mapping follows `config/veg_fire_remap.csv`. See
[`../models/README.md`](../models/README.md) for the output schema and the coefficient
fold-back / GEE-export details.

## Production / reference files

| File | Role |
|---|---|
| `workflow/02-model_fitting.R` | the fit (source of truth for the design) |
| `config/veg_fire_remap.csv` | defines the classes to fit (see [`02-vegetation_remap.md`](02-vegetation_remap.md)) |
| `scripts/cv_feasibility_report.py` | pre-flight CV feasibility per class |
| `models/class_*_coefficients.csv` | tracked fitted outputs (GEE deliverable) |
| `models-store/class_*`, `models-store/cv_metrics_v1.csv` | heavy fitted outputs (gitignored) |
| `models/README.md` | output schema + coefficient export details |

## Related notebooks

- `notebooks/logistic_regression_design.qmd` — the full design story (renders on full data).
- `notebooks/model_fit_diagnostics.qmd` — per-class diagnostics (tuning, coefficients,
  calibration, OOF, omission/commission, by-fire OOF breakdown); auto-discovers every fitted
  `class_*`. The per-fire time-series panels are **not** in this notebook — they are produced
  only as standalone PNGs by `scripts/ts_plot_by_fire.R` (see below).

## Per-fire time-series diagnostic plots

For each fitted class, a 4-row panel (NBR / NBR2 / raw predicted burn probability /
smoothed predicted burn probability) per fire, Burned points stacked above Unburned, one
line per training point — useful for
spotting fires whose pre/post-fire date window is mis-defined. Predicts **in-sample**
(`class_NN_fit.rds`, not OOF) over the full training observations — see
[`../models/README.md`](../models/README.md) ("Predicting burn probability") for why that
tradeoff is accepted here.

Script set (`collection-01/scripts/`):
- `ts_predict_functions.R` — `design_raw()` / `predict_class()`, RAW-scale prediction from a
  `class_NN_fit.rds` without loading glmnet.
- `ts_plot_cache.R` — builds `models-store/ts_plot_cache_v1.rds`: predicts `p_pred` for every
  fitted class's full observation set, adds `burn_class` (point-level Burned/Unburned factor)
  and `p_pred_smooth` (n5 rolling median of `p_pred` per point, via `slider::slide_dbl`).
- `ts_plot_functions.R` — shared `plot_fire_panel()`. Aesthetic (hex colors, thin-spaghetti +
  bold-median-line geoms, `theme_classic`-based theme) mirrors the top two panels of
  `collection-00/data_viz_Lican/functions.R::plot_tempseg()`, by explicit request.
- `ts_plot_by_fire.R` — the **canonical** (and only) driver: one PNG per fire (pooled across
  every veg_fire class a fire's points belong to, since a point's class depends on its
  previous-year land cover) → `models-store/prediction_plots/{region}/{region_fire_id}.png`.

The median marker on each per-fire panel is a solid burn-class–colored point for dates whose
observations were used in fitting (`fit == TRUE`), and a **red asterisk** for held-out dates
(`fit == FALSE`) — a quick visual flag for which obs the fit actually saw.

Re-run `ts_plot_cache.R` after any `class_NN_fit.rds` changes, then `ts_plot_by_fire.R` to
refresh the standalone PNGs.
