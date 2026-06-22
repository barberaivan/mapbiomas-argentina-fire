# MapBiomas Argentina Fire — Collection 01

*In development. See [`collection-00/README_00.md`](../collection-00/README_00.md) for the complete pilot.*

---

## What changed from collection 0

| Aspect | Collection 0 | Collection 1 |
|--------|-------------|-------------|
| Coverage | Patagonia only | BA, CHACO, PAMPA, CUYO, PAT |
| Model | Logistic regression (2 levels) | Regularized logistic regression (`glmnet`) |
| Language | GEE JavaScript + R | Python (GEE processing) + R (model fitting) |
| Previous-year features | Custom index summaries | MapBiomas mosaic (40 bands) |
| Spectral features | NBR/NBR2/MIRBI/NDVI | 21 features (see below) |

---

## Spectral features (21 per Landsat observation)

| Group | Features |
|-------|---------|
| Optical | BLUE, GREEN, RED, NIR, SWIR1, SWIR2 |
| Fire indices | NBR, NBR2, MIRBI (raw), NDVI |
| Tasseled-cap (Baig 2014 OLI) | TCB, TCG, TCW |
| Auxiliary | NDMI (vegetation moisture), NDSI (snow), SAVI (sparse veg), NDWI (open water) |
| Canonical-team additions | AFRI, kNDVI, EVI2, NIRv |

(Source of truth: `ALL_FOCAL_FEATURES` in `utils/constants.py`.)

Previous-year MapBiomas features (40 mosaic bands — optical + NDVI/NDWI/NPV/NDFI, each as median/dry/wet/stdDev — plus the raw/reclassified LULC class) are attached to each observation using the year prior to the observation date.

---

## Repository structure

```
collection-01/
├── utils/
│   ├── constants.py        # All paths, feature lists, MB reclass table, LR terms
│   └── functions.py        # GEE helpers: Landsat preprocessing, indices, MB sampling
├── config/                 # veg_fire_remap.csv — canonical MB→fire-class remap (source of truth)
├── models/                 # Fitted model outputs (coefficients, CV metrics, tuning); see models/README.md
├── workflow/               # Numbered pipeline steps (mixed Python + R)
│   ├── 01-training_data_export.py   # Export training data (one GEE task per fire)
│   ├── 02-model_fitting.R           # Fit LR per veg_fire class (R, glmnet)
│   └── 03–08-*.py          # Stubs — in development (Python/GEE)
├── scripts/                # Ad-hoc utilities — not mandatory pipeline steps
│   ├── status.py                          # Check GEE export status across all regions
│   ├── download_observations.py           # Download training observations to local CSV
│   ├── export_region_raster.py            # Export region-ID raster to GEE asset
│   ├── veg-fire_remap_clean-google-sheet.R # Regenerate config/veg_fire_remap.csv from the Google Sheet
│   ├── cv_feasibility_report.py           # Pre-flight CV feasibility per veg_fire class (run before fitting)
│   └── make_fires_table_stats.R           # Build fires_table_stats.csv from xlsx + obs CSVs
├── notebooks/              # Quarto-R (.qmd) exploratory analyses and decisions
├── samples/                # ARCHIVE — JS templates from interactive point collection
└── data/                   # gitignored — local downloads and scratch files
```

---

## Running the pipeline

Run all scripts from the **repo root**.

### Step 01 — Export training data

```bash
# Test on one fire first, review the asset schema in the GEE Code Editor
/home/ivan/.venvs/gee/bin/python collection-01/workflow/01-training_data_export.py \
  --region PAT --version 1 --test-fire fire_32

# Full region — submits one GEE task per fire in parallel
/home/ivan/.venvs/gee/bin/python collection-01/workflow/01-training_data_export.py \
  --region PAT --version 1
```

Output per fire: `COLLECTION-1/TRAINING-DATA/{region}/training_observations-fire_NN_v1`

A JSON run log is written to `workflow/01-training_data_export/run_{region}_v{version}.json`.

### Scripts (ad-hoc utilities)

```bash
# Check GEE export status across all regions (or one)
/home/ivan/.venvs/gee/bin/python collection-01/scripts/status.py
/home/ivan/.venvs/gee/bin/python collection-01/scripts/status.py --region PAT

# Download completed training observations to collection-01/data/ as a local CSV
/home/ivan/.venvs/gee/bin/python collection-01/scripts/download_observations.py --region PAT --version 1
```

### Step 02 — Model fitting (R)

Fitted locally in R with `glmnet` — one elastic-net logistic regression per **veg_fire
class** (a class may span regions, e.g. `agriculture_cuyo-pat`). The fitting unit is the
class, read from `config/veg_fire_remap.csv`. Run a CV feasibility check first, then fit
all available classes or a named subset. Outputs land in `models/` (see `models/README.md`).

```bash
# Pre-flight: confirm each class has enough positive-bearing fires for grouped CV
/home/ivan/.venvs/gee/bin/python collection-01/scripts/cv_feasibility_report.py --version 1

# Fit all fittable classes whose region data is available...
Rscript collection-01/workflow/02-model_fitting.R 1
# ...or restrict to named classes (memory-heavy ones: FIT_CORES=2 or 1)
Rscript collection-01/workflow/02-model_fitting.R 1 agriculture_cuyo-pat forest_pat
```

Regenerate the canonical remap from the Google Sheet whenever it changes (do not hand-edit the CSV):

```bash
Rscript collection-01/scripts/veg-fire_remap_clean-google-sheet.R
```

### Steps 03–08

In development (Python/GEE). See script stubs in `collection-01/workflow/`.

### Scripts (R utilities)

```bash
# Build fires_table_stats.csv (needed by data_collection_stats.qmd)
# Re-run whenever training observation CSVs are updated.
Rscript collection-01/scripts/make_fires_table_stats.R
```

### Notebooks (Quarto-R)

| Notebook | Purpose | Dependencies |
|----------|---------|--------------|
| `land_cover_remap.qmd` | Validate the canonical MB → fire-class remap against full obs; CV feasibility per class | training obs CSVs, `config/veg_fire_remap.csv`, Google Sheets |
| `model_fit_diagnostics.qmd` | Per-class fit diagnostics (tuning, coefficients, calibration, OOF, omission/commission, by-fire) | `models/class_*` outputs (+ `_model_fit_diagnostics_child.qmd` template) |
| `data_collection_stats.qmd` | Field collection stats (time, authors, points, obs per fire) | `fires_table_stats.csv` → run `make_fires_table_stats.R` first |
| `logistic_regression_design.qmd` | Obs-level burn-probability LR design: canonical-team 427-term set → reduction protocol → final 129-term elastic-net design + fitting config | full `data/training_observations_*_v1.csv` |
| `logistic_regression_feature_engineering_ideas.qmd` | Feature engineering ideas for the LR model | — |
| `burn_prob_ts_metrics.qmd` | Exploration of burn-probability time-series summary metrics | — |
| `categorical_vs_bernoulli.qmd` | Categorical vs Bernoulli formulation notes | — |

Rendered `.html` versions are tracked alongside the `.qmd` so they can be read without a Quarto/R toolchain.

---

## GEE asset paths

```
projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/TRAINING-DATA/
├── {region}/training_fires                        # fire event metadata
├── {region}/training_locations-fire_NN            # burned/unburned training points
└── {region}/training_observations-fire_NN_v1      # output of step 01
```

PAT also draws training_locations from collection 0:
`FIRE/COLLECTION-0/TRAINING-DATA/training_locations-fire_NN` (fires 01–30)

Export status across regions: `python collection-01/scripts/status.py`.

---

## Status

| Step | Status |
|------|--------|
| 01 — training data export | Complete for all 5 regions (BA, CHACO, PAMPA, CUYO, PAT), v1. |
| 02 — model fitting (R, glmnet) | Implemented. PAT classes fitted; remaining classes pending (see CLAUDE.md work order). |
| 03–08 — prediction pipeline | Stubs |
