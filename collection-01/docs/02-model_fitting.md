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

## Outputs (`models/`)

Per class `class_NN_*`: `coefficients.csv`, `cv_metrics.csv`, `tuning.csv`, `fit.rds`, and
`oof_predictions.csv` (git-ignored — large). `cv_metrics_v1.csv` is the cross-class summary.
The `class_NN` ↔ `veg_fire_name` mapping follows `config/veg_fire_remap.csv`. See
[`../models/README.md`](../models/README.md) for the output schema and the coefficient
fold-back / GEE-export details.

## Production / reference files

| File | Role |
|---|---|
| `workflow/02-model_fitting.R` | the fit (source of truth for the design) |
| `config/veg_fire_remap.csv` | defines the classes to fit (see [`02-vegetation_remap.md`](02-vegetation_remap.md)) |
| `scripts/cv_feasibility_report.py` | pre-flight CV feasibility per class |
| `models/class_*`, `models/cv_metrics_v1.csv` | fitted outputs |
| `models/README.md` | output schema + coefficient export details |

## Related notebooks

- `notebooks/logistic_regression_design.qmd` — the full design story (renders on full data).
- `notebooks/model_fit_diagnostics.qmd` — per-class diagnostics (tuning, coefficients,
  calibration, OOF, omission/commission, by-fire); auto-discovers every fitted `class_*`.
