# MapBiomas Argentina Fire — Collection 01

*In development. See [`collection-00/README_00.md`](../collection-00/README_00.md) for the complete pilot.*

---

## What changed from collection 0

| Aspect | Collection 0 | Collection 1 |
|--------|-------------|-------------|
| Coverage | Patagonia only | BA, CHACO, PAMPA, CUYO, PAT |
| Model | Logistic regression (2 levels) | Regularized logistic regression (`glmnet`) |
| Language | GEE JavaScript + R | Python (GEE processing) + R (model fitting) |
| Previous-year features | Custom index summaries | MapBiomas mosaic (21 bands) |
| Spectral features | NBR/NBR2/MIRBI/NDVI | 17 features (see below) |

---

## Spectral features (17 per Landsat observation)

| Group | Features |
|-------|---------|
| Optical | BLUE, GREEN, RED, NIR, SWIR1, SWIR2 |
| Fire indices | NBR, NBR2, MIRBI (raw), NDVI |
| Tasseled-cap (Baig 2014 OLI) | TCB, TCG, TCW |
| Auxiliary | NDMI (vegetation moisture), NDSI (snow), SAVI (sparse veg), NDWI (open water) |

Previous-year MapBiomas features (21 mosaic bands + raw/reclassified LULC class) are attached to each observation using the year prior to the observation date.

---

## Repository structure

```
collection-01/
├── utils/
│   ├── constants.py        # All paths, feature lists, MB reclass table, LR terms
│   └── functions.py        # GEE helpers: Landsat preprocessing, indices, MB sampling
├── workflow/               # Numbered pipeline steps (mixed Python + R)
│   ├── 01-training_data_export.py   # Export training data (one GEE task per fire)
│   ├── 02-model_fitting.R           # Fit LR per veg_fire class (R, glmnet)
│   └── 03–08-*.py          # Stubs — in development (Python/GEE)
├── scripts/                # Ad-hoc utilities — not mandatory pipeline steps
│   ├── status.py                    # Check GEE export status across all regions
│   ├── download_observations.py     # Download training observations to local CSV
│   ├── export_region_raster.py      # Export region-ID raster to GEE asset
│   └── make_fires_table_stats.R     # Build fires_table_stats.csv from xlsx + obs CSVs
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

Fitted locally in R with `glmnet`. Run with `Rscript`, or interactively in any R IDE (e.g. RStudio / Positron).

```bash
Rscript collection-01/workflow/02-model_fitting.R
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
| `algo-fuego.qmd` | Algorithm flowchart (Mermaid/DOT) | — |
| `vegetation_remap_and_class_imbalance.qmd` | Validate MB → fire-class remap; class balance per region | training obs CSVs, Google Sheets |
| `data_collection_stats.qmd` | Field collection stats (time, authors, points, obs per fire) | `fires_table_stats.csv` → run `make_fires_table_stats.R` first |
| `logistic_regression_terms.qmd` | LR model term design for obs-level burn probability | — |
| `logistic_regression_feature_engineering_ideas.qmd` | Feature engineering ideas for the LR model | — |
| `burn_prob_ts_metrics.qmd` | Exploration of burn-probability time-series summary metrics | — |

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

Current training_locations coverage: see `training_locations_status.txt`.

---

## Status

| Step | Status |
|------|--------|
| 01 — training data export | PAT: complete. Other regions: pending training_locations. |
| 02 — model fitting (R, glmnet) | Stub |
| 03–08 — prediction pipeline | Stubs |
