# models/

Fitted model outputs from `workflow/02-model_fitting.R` (one elastic-net logistic
regression per **veg_fire class**, pooling regions where a class spans regions).
Inputs/reference data live in `data/`; this directory is outputs only.

**This file is the reference for the artifacts** — the folder layout, the file schema and how to
predict from them. *Why* the model is like this is [`docs/02-model_fitting.md`](../docs/02-model_fitting.md);
how it is deployed in GEE is [`docs/02-burn_probability.md`](../docs/02-burn_probability.md).

## Per-model folders (`P<NNN>/`)

Coefficient CSVs live **one folder per model variant**, named `P<NNN>` (3-digit, leading
zeros). Every variant is fit by the same CV — grouped K-fold on region-unique fire ids, K
adaptive at `min(10, n_fires_with_positives)` — so the fold count is not in the name:

| Folder | Model | Rows (incl. intercept) |
|--------|-------|------------------------|
| `P129/` | full fit (all terms) | 130 |
| `P080/` | term-pruning, top-P=80 | 81 |
| `P060/` | top-P=60 | 62 |
| `P050/` | top-P=50 — **DEPLOYED** (see `utils/constants.py` `DEPLOYED_MODEL`) | 52 |
| `P040/` | top-P=40 | 42 |
| `P030/` | top-P=30 | 33 |

`P` is the top-P percentile cut on the global term ranking, **not** the term count (e.g. `P050`
has 52 rows). The reduced folders hold only `intercept + kept terms` (trimmed at write time) so GEE
prediction builds only the deployed bands — see `docs/02-burn_probability.md`
"From CSV rows to coefficient bands". Each folder is
(re)produced by `02-model_fitting.R` writing to `models/<COEF_TAG>/` (`COEF_TAG` defaults to
`P129`; `scripts/refit_pruning_sweep.R` sets `P030`…`P080`). Only `*_coefficients.csv` are tracked
(see `.gitignore`); heavy artifacts stay in `models-store/`.

> The `K3` in the sweep's artifact paths (`models-store/pruning/K3_P<P>/`, `keep_K3_P<P>.csv`)
> is **not a fold count**. It is the area weighting used to rank terms globally — scheme
> `area_cbrt_K3`, i.e. `area^(1/3)`, chosen in `notebooks/lr_term_pruning.qmd` and carried in
> `config/pruning_terms.csv`.

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
| `cv_feasibility_v{ver}.csv` | pre-flight gate (all regions; `_{region}_` variant for a single region) | yes |
| `cv_metrics_v{ver}.csv`     | summary of all fitted classes (rbind of `class_*_cv_metrics.csv`) | yes |

`NN` is the `veg_fire` code from `config/veg_fire_remap.csv` — note codes shift if the
remap changes (e.g. a class is added/dropped), so reconcile filenames against the current
remap rather than assuming a fixed mapping.

The OOF predictions sidecar is keyed `(fire_id, point_id, date)` so it joins back to
`data/training_observations_{region}_v{ver}.csv` for plotting `p_i` by fire/class.

## Getting the veg_fire class from (region, mb_class_raw)

The fitting unit (`class_NN`) is a **veg_fire class**, defined by `config/veg_fire_remap.csv`.
The mapping is keyed on **`(region, mb_class_raw)`** — `mb_class_raw` (the previous-year
MapBiomas Argentina LULC code) maps to a *different* veg_fire class in different regions, so
you must join on both. `mb_class_raw` is a column in `data/training_observations_{region}_v1.csv`.

```r
library(data.table)
remap <- fread("collection-01/config/veg_fire_remap.csv")          # mb_class_raw, region, veg_fire, veg_fire_name, fittable
obs   <- fread("collection-01/data/training_observations_PAT_v1.csv")
obs   <- merge(obs, remap[region == "PAT", .(mb_class_raw, veg_fire, veg_fire_name)],
               by = "mb_class_raw", all.x = TRUE)
# obs$veg_fire is now the NN in class_NN_*; rows with veg_fire = NA are unmapped (excluded from fits).
```

This is exactly what `02-model_fitting.R::load_region()` does (filter remap to the region,
merge on `mb_class_raw`). So `class_NN` ↔ `veg_fire_name` comes straight from the remap:
`unique(remap[, .(veg_fire, veg_fire_name)])`.

## Predicting burn probability

**For the per-fire diagnostic plot (Lican's task): you do NOT predict — use `p_oof`.**
`class_NN_oof_predictions.csv` already holds the honest cross-validated probability per
observation (`p_oof`), keyed `(region, fire_id, point_id, date)`. Join it to the spectral
time series and plot `p_oof` directly — no `.rds`, no design rebuild. Re-predicting with the
full-data fit would be *in-sample* and over-optimistic, which is the opposite of what the
plot needs.

```r
oof <- fread("collection-01/models-store/class_16_oof_predictions.csv")   # grassland_pat
ts  <- merge(obs, oof[, .(region, fire_id, point_id, date, p_oof)],
             by = c("region", "fire_id", "point_id", "date"), all.x = TRUE)
# plot ts$NBR, ts$NBR2, ts$p_oof vs date, one line per point_id, coloured by burned.
```

**To predict on new observations (general case):** every model exports RAW-scale
coefficients, so prediction is a plain linear predictor + logistic — no glmnet object
needed. `class_NN_coefficients.csv` (`term`, `coefficient`) and the `coef_raw` vector inside
`class_NN_fit.rds` are identical. The terms are products on the **raw** band scale (the
mean-centering used during fitting is already folded into the intercept + main slopes), so
you just rebuild the 129 columns and dot them with the coefficients:

```r
fit <- readRDS("collection-01/models-store/class_16_fit.rds")   # coef_raw, specs, all_terms, alpha, lambda
FOCAL <- c("BLUE","GREEN","RED","NIR","SWIR1","SWIR2","NBR","NBR2","NDVI","NDMI","NDSI")
PREV  <- c("green","nir","swir1","swir2","ndvi","ndwi","npv","ndfi")
SUMM  <- c(med="median", wet="median_wet", dry="median_dry", sd="stdDev")
num   <- function(d, nm) { x <- as.numeric(d[[nm]]); x[is.na(x)] <- 0; x }

design_raw <- function(d) {
  Fm <- sapply(FOCAL, function(f) num(d, f)); colnames(Fm) <- paste0(FOCAL, "_t")
  pg <- expand.grid(s = names(SUMM), v = PREV, stringsAsFactors = FALSE)
  Pm <- sapply(seq_len(nrow(pg)), function(i) num(d, sprintf("mb_mos_%s_%s", pg$v[i], SUMM[[pg$s[i]]])))
  colnames(Pm) <- paste0(toupper(pg$v), "_", pg$s)
  MM <- cbind(Fm, Pm)
  Pr <- sapply(fit$specs, function(z) MM[, z$fa] * MM[, z$fb])   # RAW products (no centering)
  colnames(Pr) <- sapply(fit$specs, `[[`, "name")
  cbind(MM, Pr)[, fit$all_terms, drop = FALSE]
}
X   <- design_raw(obs)
eta <- fit$coef_raw[["(Intercept)"]] + as.numeric(X %*% fit$coef_raw[fit$all_terms])
p   <- plogis(eta)                                              # burn probability
```

Verified: this raw recipe reproduces glmnet's own `predict(..., s = lambda)` on the centered
design to machine precision (max |Δp| ≈ 1.6e-14). This is the same band-multiply-then-dot the
GEE prediction step performs, so it doubles as a local check of the deployed model. (Note the
training CSVs carry MIRBI etc.; the design uses only the 11 FOCAL + 32 PREV columns above.)

## What produced these files

The design and the tuning are [`docs/02-model_fitting.md`](../docs/02-model_fitting.md)
"Predictors" and "Tuning and cross-validation"; only what you need to *read* a file is repeated
here.

- **Grouped K-fold**, group = `(region, fire_id)` → "leave-several-fires-out", so a
  `class_NN_oof_predictions.csv` row is a prediction from folds that never saw that fire. `K` is
  adaptive, `min(10, n_fires_with_positives)`, which is why it is not in any filename — run
  `scripts/cv_feasibility_report.py` first.
- **Elastic net over `alpha ∈ {0.25, 0.5, 0.75}`**, same `foldid` across alphas, selected at
  `lambda.min` on binomial deviance. Ridge (0) and lasso (1) are **not** in the grid: neither was
  ever best in CV, and the interior keeps the ridge component that conditions this collinear
  design. `class_NN_tuning.csv` is that α/λ surface.
- The **129-term design** is 11 focal mains + 32 prev-year mains + 22 focal×focal + 64 prev×focal.
  Interactions are fit on mean-centered factors and the centering is folded back at export, which
  is what makes the recipe above a plain dot product on raw bands.
- All region/class sample exceptions live in one `SAMPLE_RULES` table in `02-model_fitting.R`; the
  generic fold/CV/fit code never branches on region.
