# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MapBiomas Argentina Fire is a geospatial pipeline for detecting and mapping burned areas in Argentina using Landsat satellite imagery. The algorithm produces annual burned area products and is implemented across two collections:

- **Collection 0** (`collection-00/`): Pilot collection — complete and operational
- **Collection 1** (`collection-01/`): Next iteration — in development

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Remote sensing processing | Google Earth Engine (GEE), JavaScript API |
| Statistical modeling | R (≥ 4.5.1) |
| Source imagery | Landsat Collection 2 Surface Reflectance (L5, L7, L8, L9) |
| Spatial segmentation | SNIC (GEE native) |
| Land cover reference | MapBiomas Argentina annual mosaics |

## Running the Pipeline

There is no traditional build system. Execution is manual.

**GEE scripts** (JavaScript in `workflow/` and `samples/`): Copy/paste into the [GEE Code Editor](https://code.earthengine.google.com/). Scripts run against GEE cloud assets; outputs export to Google Cloud Storage. Requires `.env` with `GOOGLE_CLOUD_PROJECT`.

**R model fitting** (`models_fit/`): Run scripts sequentially in a local R environment:

```r
source("01-data_preparation_obs.R")      # Prepare observation-level training data
source("02-model_obs_fit.R")             # Fit observation-level logistic regression
source("03-model_obs_cross_validation.R")
source("05-data_preparation_annual.R")   # Prepare annual-level training data
source("07-model_annual_fit.R")          # Fit annual-level logistic regression
```

Training data (CSV) must be downloaded from Google Drive to `models_fit/data/raw/` before running R scripts. Model outputs go to `models_fit/exports/`.

## Architecture

The pipeline has three main stages:

### 1. Training Data Collection (`samples/`)
GEE scripts extract Landsat time-series for 30 labeled training fires across Argentina and export the data to Google Drive as CSVs.

### 2. Statistical Model Fitting (R, `models_fit/`)
Two-level logistic regression approach:
- **Observation-level**: Predicts burn probability at individual Landsat observations (pixel × date)
- **Annual-level**: Aggregates observation probabilities to an annual burn probability per pixel

Model coefficients are exported as JavaScript constants and embedded in `utils/constants.js` for use in GEE.

### 3. GEE Workflow Pipeline (`workflow/`, 8 sequential steps)

```
01 → Annual burn index summaries (NBR, NBR2, MIRBI, NDVI, brightness, NDSI)
02 → Temporal segmentation: observation-level burn probability
03 → Annual burn probability aggregation
04 → Spatial segmentation (SNIC region-growing)
05 → Manual masking (remove ash/drought artifacts)
06 → Vectorize clusters to polygons
07 → Compute polygon-level metrics
08 → Object-based filtering → final burned area product
```

Each step exports intermediate raster/vector assets to GCS to work within GEE memory limits.

## Key Files

- **`collection-00/utils/constants.js`** — Core configuration: year ranges, spectral index names, ROI geometry, and all model coefficients (63 observation-level + 47 annual-level logistic regression parameters)
- **`collection-00/utils/functions.js`** — Shared GEE utilities: Landsat preprocessing, spectral index computation, summary statistics
- **`collection-00/models_fit/functions.R`** — Shared R utilities: data preparation, cross-validation, visualization
- **`collection-00/README_00.md`** — Detailed workflow documentation and GCS data paths for full pipeline reproduction
- **`collection-00/docs/documentation_pilot_latex/build/mapbiomas_fire_argentina_atbd_pilot_2025.pdf`** — ATBD (Algorithm Technical Basis Document): primary methodology reference
- **`.env.example`** — Required environment variables template

## Design Decisions

- **Asset-based, year-by-year processing**: Each workflow step processes one year at a time and exports intermediate assets, avoiding GEE memory/computation limits and allowing inspection of intermediate products.
- **Two-level modeling**: The observation level captures temporal burn signatures; the annual level improves robustness by aggregating across multiple Landsat passes per year.
- **Spectral index summaries as features**: Low/high value summaries of spectral indices (not raw bands) reduce input dimensionality for the model.
- **Manual masking step**: Workflow step 05 removes false positives from ash or drought before vectorization; this step requires domain expert review.
- **Collection 1 redesign**: Moving from logistic regression to Random Forest models and expanding the predictor set, with Python/GEE implementation replacing the R model fitting workflow.
