# models/

Fitted model outputs from `workflow/02-model_fitting.R` (one elastic-net logistic
regression per **veg_fire class**, pooling regions where a class spans regions).
Inputs/reference data live in `data/`; this directory is outputs only.

The fitting unit is the **class**, not the region: the driver reads each class's
regions from `config/veg_fire_remap.csv`, loads only those `data/training_observations_{region}_v{ver}.csv`
tables, and **skips** classes whose regions aren't all exported yet (logged). So a
partial export (e.g. only PAT today) fits exactly the classes it can.

## Naming

`class_NN_<description>` where `NN` is the `veg_fire` code (see `config/veg_fire_remap.csv`),
e.g. `class_07_coefficients.csv`. Classes cross regions, so files are flat (no region subfolders).

| File | Consumer | Tracked in git |
|------|----------|----------------|
| `class_NN_coefficients.csv` | GEE/Python prediction | yes (small) |
| `class_NN_cv_metrics.csv`   | notebooks | yes |
| `class_NN_tuning.csv`       | notebooks (α/λ surface) | yes |
| `class_NN_oof_predictions.csv` | notebooks (per-obs OOF `p_i`) | **no** (large) |
| `class_NN_fit.rds`          | R refit cache | **no** (large) |
| `cv_feasibility_{region}_v{ver}.csv` | pre-flight gate | yes |

The OOF predictions sidecar is keyed `(fire_id, point_id, date)` so it joins back to
`data/training_observations_{region}_v{ver}.csv` for plotting `p_i` by fire/class.

## CV design (summary; full rationale in CLAUDE.md)

- **Grouped K-fold, K=10**, group = `(region, fire_id)` → "leave-several-fires-out".
- Folds built **per class** by stratified greedy packing (balance obs + positive count).
- **Pure-negative fires** (ash/drought, crops) are distributed across folds at the
  point level, not held out as a group — keeps every fold supplied with positives.
- Adaptive `K = min(10, n_fires_with_positives)`; run `cv_feasibility_report.py` first.
- Elastic net: `alpha ∈ {0, .25, .5, .75, 1}`, **same foldid across all alphas**.
- Tune on binomial **deviance** (log-loss); report deviance + Brier + reliability + AUC.

## Predictors & region exceptions (in `02-model_fitting.R`)

- `build_design()` builds the **canonical-team 427-term** design (6 blocks; see
  `notebooks/logistic_regression_terms.qmd §"Canonical team"`).
- All region/class sample exceptions live in one `SAMPLE_RULES` table; the generic
  fold/CV/fit code never branches on region. Current PAT rules:
  `forest_pat`/`shrubland_pat` train on the **merged forest+shrubland ash** negatives;
  `grassland_pat` **downsamples ash to 10%** of its unburned.
