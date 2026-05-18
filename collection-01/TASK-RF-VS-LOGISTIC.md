# TASK: RF regression vs. elastic-net logistic — PAT grassland comparison

**Output file:** `collection-01/scripts/rf_vs_logistic.R`  
**Run from:** repo root  
**Interpreter:** R (base, no Rscript wrapper needed — user runs it interactively)

---

## Goal

Compare Random Forest regression vs. elastic-net logistic regression on PAT
grassland training observations using **Brier score** as the primary metric.
Brier = mean((p̂ − y)²), lower is better.  If the elastic net is competitive,
the project will use logistic regression for its simpler GEE deployment path.

---

## Data

```
collection-01/data/training_observations_PAT_v1.csv
```

Columns of interest:

| Name | Role |
|---|---|
| `burned` | Response (0/1) |
| `fire_id` | Grouping variable for CV |
| `mb_class_raw` | Used for fire-class filter (see below) |
| `BLUE` … `NDWI` | 17 focal spectral features (Landsat-scale floats) |
| `mb_mos_blue_median` … `mb_mos_ndvi_median_wet` | 21 previous-year MapBiomas mosaic bands (**large integers** — must be standardised before any regression) |

### Fire-class filter (proposal 2)

Read the remap sheet from Google Sheets:

```
https://docs.google.com/spreadsheets/d/17ZShb8D0JaJw4nLvBDzt19xF6Fdg8lGHYs4Jogh0X1A/export?format=csv&sheet=remap_by_region
```

Filter to `region_fire == "PAT"`, use column `veg_fire_name_2`. Join on
`mb_class_raw`. Keep only rows where the joined fire class is **"grassland"**.

### Special fires

`fire_46` and `fire_47` are unburned-only controls (drought/ash false
positives). They are **always included in every training fold** but **never
assigned to a test fold**.

---

## Features

### Focal features (17) — no scaling needed for RF; scaled for elastic net

```r
FOCAL <- c("BLUE","GREEN","RED","NIR","SWIR1","SWIR2",
           "NBR","NBR2","MIRBI","NDVI","TCB","TCG","TCW",
           "NDMI","NDSI","SAVI","NDWI")
```

### Previous-year mosaic features (21) — large integers, must be scaled

```r
MOSAIC <- c(
  "mb_mos_blue_median",  "mb_mos_blue_median_dry",  "mb_mos_blue_median_wet",
  "mb_mos_green_median", "mb_mos_green_median_dry", "mb_mos_green_median_wet",
  "mb_mos_red_median",   "mb_mos_red_median_dry",   "mb_mos_red_median_wet",
  "mb_mos_nir_median",   "mb_mos_nir_median_dry",   "mb_mos_nir_median_wet",
  "mb_mos_swir1_median", "mb_mos_swir1_median_dry", "mb_mos_swir1_median_wet",
  "mb_mos_swir2_median", "mb_mos_swir2_median_dry", "mb_mos_swir2_median_wet",
  "mb_mos_ndvi_median",  "mb_mos_ndvi_median_dry",  "mb_mos_ndvi_median_wet"
)
```

---

## Models

### 1. Random Forest regression (`ranger`)

- **Packages:** `ranger`
- **Mode:** regression (response is numeric 0/1, objective = MSE)
- **Features:** all 38 raw features (FOCAL + MOSAIC), **no scaling needed**
- **Fixed params:** `num.trees = 300`, `replace = TRUE`, `sample.fraction = 0.5`
  (matches GEE SMILE default `bagFraction = 0.5`), `seed = 42`
- **Parallel:** `num.threads = 8` (ranger's built-in threading)
- **Tuning grid** (9 combinations):

| Parameter | Values |
|---|---|
| `mtry` | 3, 6, 12  ← floor(√38/2), floor(√38), floor(√38×2) |
| `min.node.size` | 50, 100, 150 |

Predictions are ranger's regression output (continuous, effectively in [0,1]).
No clamping needed.

### 2. Elastic-net logistic regression (`glmnet`)

- **Packages:** `glmnet`, `Matrix`
- **Family:** `"binomial"` (log-likelihood objective, output = probability)
- **Standardise inputs:** z-score ALL 38 features (mean=0, sd=1) using
  **training-fold statistics only** (never leaking test-fold moments).
  Compute interactions **after** z-scoring the main effects so all columns
  enter glmnet on comparable scales.
- **Call glmnet with `standardize = FALSE`** (we already standardised manually).
- **Lambda selection:** inner `cv.glmnet` on the training fold, pick `lambda.min`.
- **Tuning grid** (3 values):

| Parameter | Values |
|---|---|
| `alpha` | 0.1, 0.5, 0.9 |

#### Design matrix (52 columns)

Build in this order (all on z-scored scale):

1. 38 main effects: FOCAL (17) + MOSAIC (21)
2. Focal raw-band pairwise interactions (6):  
   RED×NIR, RED×SWIR1, RED×SWIR2, NIR×SWIR1, NIR×SWIR2, SWIR1×SWIR2
3. Previous-year NDVI × focal fire indices (2):  
   `mb_mos_ndvi_median` × NBR, `mb_mos_ndvi_median` × NBR2
4. Matched previous-year × focal raw-band pairs (6):  
   `mb_mos_blue_median`×BLUE, `mb_mos_green_median`×GREEN,  
   `mb_mos_red_median`×RED, `mb_mos_nir_median`×NIR,  
   `mb_mos_swir1_median`×SWIR1, `mb_mos_swir2_median`×SWIR2

Use `Matrix::sparse.model.matrix()` or just `cbind()` for the design matrix.

#### Note on production deployment

To back-transform elastic-net coefficients to the original (unscaled) feature
space: for each main-effect predictor j, β_j_orig = β_j / sd_j. For an
interaction term k = i×j (both z-scored), β_k_orig = β_k / (sd_i × sd_j).
Adjust the intercept accordingly. Document this in a comment block in the
script so it is available for later GEE deployment.

---

## Cross-validation design

**5-fold, fire-grouped.** All observations from the same fire stay in the same
fold (no leakage across observations within a fire).

```r
library(rsample)

# Fires 46/47 are held out of the CV structure
dat_cv    <- filter(dat, !fire_id %in% c("fire_46", "fire_47"))
dat_fixed <- filter(dat, fire_id %in% c("fire_46", "fire_47"))

folds <- group_vfold_cv(dat_cv, group = "fire_id", v = 5)
```

For each fold:
- **Training set** = `training(split)` rows **plus all rows from `dat_fixed`**
- **Test set** = `testing(split)` rows (never includes fire_46/47)

---

## Outer CV loop

Use `foreach` + `doParallel` for the outer fold loop (5 iterations).
Inside each fold, ranger uses its own threading (`num.threads = 8`), so set
`registerDoParallel(cores = 5)` for the outer loop — total CPU usage stays
within 8 threads since the 5 folds run sequentially by default with ranger
absorbing the parallelism. **Alternatively**, if the dataset fits comfortably
in memory, run the outer loop sequentially and rely entirely on ranger's
`num.threads = 8` and glmnet's parallel lambda paths.

For each fold, collect:

```
model   | hyperparam_1 | hyperparam_2 | fold | brier
RF      | mtry         | min.node.size| 1..5 | <dbl>
ElasNet | alpha        | lambda_min   | 1..5 | <dbl>
```

---

## Outputs

### 1. Full results table (printed to console)

All hyperparameter combinations × folds, grouped by model. Columns:
`model`, `mtry`/`alpha`, `min_node_size`/`lambda_min`, `fold`, `brier`.
Print with `print(full_tbl, n = Inf)`.

### 2. Summary table (mean ± SD across folds)

Aggregate by model + hyperparams. Add a `cv_sd` column (SD of Brier across
folds — higher SD = less stable). Sort by `mean_brier` ascending.
Print both the full summary and a 2-row sub-table showing the single best RF
vs. the single best elastic net.

```
# Example output shape:
# model     alpha  mtry  min_node  mean_brier  cv_sd
# ElasNet   0.5    —     —         0.0312      0.003
# RF        —      6     100       0.0318      0.007
```

### 3. Calibration plot (ggplot2, saved to console via `print()`)

Use **out-of-fold predictions** accumulated across all 5 folds (each
observation is predicted exactly once). For the best RF and best elastic net:

- Bin predicted probabilities into 10 equal-width bins [0, 0.1), …, [0.9, 1]
- Plot mean predicted probability (x) vs. observed fraction burned (y) per bin
- Add a diagonal reference line (perfect calibration)
- One line/colour per model
- Save to `collection-01/scripts/rf_vs_logistic_calibration.png` using
  `ggsave()` in addition to printing

---

## Test mode (run this FIRST before the full grid)

At the top of the script, include a `TEST_MODE <- TRUE` flag. When `TRUE`:

- Subsample the grassland data to **2 000 rows** (set seed before sampling)
- Use **2 folds** instead of 5
- RF grid reduced to **1 combination**: mtry = 6, min.node.size = 100,
  `num.trees = 20`
- Elastic net grid reduced to **1 alpha**: 0.5
- Target: completes in < 60 seconds and prints non-NaN Brier scores

Only switch `TEST_MODE <- FALSE` once the test run produces sensible output
(Brier scores roughly in the 0.01–0.20 range for burned-area data).

---

## Packages required

```r
library(tidyverse)   # data wrangling + ggplot2
library(rsample)     # group_vfold_cv
library(ranger)      # RF regression
library(glmnet)      # elastic net logistic
library(Matrix)      # sparse matrix (optional, for glmnet design matrix)
library(foreach)     # parallel outer loop (optional)
library(doParallel)  # parallel backend (optional)
```

Install any missing packages with `install.packages()` before running.

---

## File location and run command

```
collection-01/scripts/rf_vs_logistic.R
```

Run from the repo root (or set working directory accordingly):

```r
source("collection-01/scripts/rf_vs_logistic.R")
```

---

## Implementation notes for Sonnet

- Do not use tidymodels/parsnip — call `ranger()` and `glmnet()`/`cv.glmnet()`
  directly for clarity and speed.
- The remap join with the Google Sheet must handle the `id` column arriving as
  mixed-type (some rows have non-numeric values); coerce with
  `as.integer(suppressWarnings(...))` and drop NAs, then deduplicate on
  `mb_class_raw` within `region_fire == "PAT"`.
- ranger's `predictions` slot for regression mode is a numeric vector, not a
  data frame.
- `cv.glmnet` returns `lambda.min` directly; use `predict(..., s = "lambda.min",
  type = "response")` to get probabilities.
- Accumulate out-of-fold predictions in a list and `bind_rows()` at the end
  for the calibration plot.
- The script should be self-contained: no sourced helpers, no external `.R`
  files.
