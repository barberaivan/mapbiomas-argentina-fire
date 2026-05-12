# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MapBiomas Argentina Fire is a geospatial pipeline for detecting and mapping burned areas in Argentina using Landsat satellite imagery. The algorithm produces annual burned area products across two collections:

- **Collection 0** (`collection-00/`): Pilot — complete and operational. Covers Patagonia only.
- **Collection 1** (`collection-01/`): In development. Covers all five regions (BA, CHACO, PAMPA, CUYO, PAT).

## Technology Stack

| Component | Collection 0 | Collection 1 |
|-----------|-------------|-------------|
| GEE processing | JavaScript API | Python API (`earthengine-api`) |
| Model fitting | R (logistic regression) | GEE Python API (Random Forest) |
| Source imagery | Landsat C2 SR — L5, L7, L8, L9 | same |
| Land cover reference | MapBiomas Argentina LULC | same + MapBiomas annual mosaic |
| Spatial segmentation | SNIC (GEE native) | same (steps 04+) |

## Development Environment

- **Python venv**: `/home/ivan/.venvs/gee` — always use `/home/ivan/.venvs/gee/bin/python` to run collection-01 workflow scripts. Never create a new venv for this repo.
- **GEE project**: `mapbiomas-fire-485203` (hardcoded in `collection-01/utils/constants.py`).
- **Run scripts from the repo root**, not from inside `collection-01/`. The scripts add `collection-01/` to `sys.path` at startup.

## Collection 0 — Architecture

1. **Training data** (`samples/`): GEE JS scripts extract Landsat time-series for 30 labeled fires (PAT only), export to Google Drive as CSVs.
2. **Model fitting** (`models_fit/`, R): Two-level logistic regression. Coefficients exported as JS constants into `utils/constants.js`.
3. **GEE workflow** (`workflow/`, 8 steps): burn index summaries → obs-level probability → annual probability → SNIC → manual masking → vectorization → polygon metrics → object filtering.

Key files:
- `collection-00/utils/constants.js` — model coefficients (63 obs-level + 47 annual-level), paths, ROI geometry
- `collection-00/utils/functions.js` — Landsat preprocessing, index computation, summary statistics
- `collection-00/README_00.md` — full reproduction instructions and GCS asset paths

## Collection 1 — Architecture

1. **Training data export** (`workflow/01-training_data_export.py`): samples Landsat + MapBiomas mosaic at training points, exports one GEE asset per fire.
2. **RF model fitting** (`workflow/02-model_fitting.py`, stub): fit Random Forest per region × fire-class in GEE.
3. **Prediction pipeline** (`workflow/03–08`, stubs): same burn-probability → SNIC → masking → filtering structure as collection 0.

Key files:
- `collection-01/utils/constants.py` — single source of truth: paths, year range, spectral features, MB reclass table, RF params, MB mosaic band list
- `collection-01/utils/functions.py` — Landsat preprocessing, index computation, MB class and mosaic helpers
- `collection-01/workflow/00-status.py` — check training_observations export status across all regions
- `collection-01/workflow/01-training_data_export.py` — export training data (one GEE task per fire)
- `collection-01/BACKLOG.md` — pending work items

## Collection 1 — Design Decisions

**Training data export**
- One GEE task per fire. Output asset: `training_observations-fire_NN_v{version}` under `COLLECTION-1/TRAINING-DATA/{region}/`.
- Task description format: `training_obs_{region}_fire_{NN}_v{version}` — region included because fire_ids repeat across regions.
- PAT fires 01–30 fall back to `COLLECTION-0/TRAINING-DATA/` for training_locations. Fires without locations are skipped with a warning.
- Fires with no burned points (fire_46, fire_47 — drought/ash negatives) export unburned-only without being skipped.
- `fire_id` is stored as a string `"fire_NN"` in GEE assets. Use `str(fire_id).removeprefix("fire_").zfill(2)` to get the zero-padded numeric part.

**Spectral features (17 focal-date)**
- Optical: BLUE, GREEN, RED, NIR, SWIR1, SWIR2
- Fire indices: NBR, NBR2, MIRBI (raw — not sign-flipped as in col0), NDVI
- Tasseled-cap (Baig 2014 OLI coefficients): TCB, TCG, TCW
- Auxiliary: NDMI (vegetation moisture = NIR−SWIR1/NIR+SWIR1, same formula as col0's `ndwi_gao`), NDSI (snow), SAVI (sparse veg), NDWI (open water, McFeeters 1996 — new in col1)

**MapBiomas mosaic**
- 21 bands selected from 111: visible + NIR + SWIR1/2 + NDVI, median/dry/wet aggregates only.
- Selection (`.select()`) happens before `.mosaic()` so only the 21 bands are processed.
- Previous-year mosaic: for observations in year Y, the mosaic for year Y−1 is attached.
- The loop variable is `mb_year` (the actual MB data year). `obs_year = mb_year + 1`. Range: `mb_start_year = obs_start_year − 1` to `mb_end_year = obs_end_year − 1`.

**Burned label at observation level**
- `burned=0`: all observations from unburned points, and observations from burned points in the pre-fire window.
- `burned=1`: observations from burned points in the post-fire window (post_lwr → post_upr_long).
- `post_upr_short` is preserved in `training_fires` for filtering at training time but not used to assign labels.
- `pre_lwr` is often null in assets → computed as `pre_upr` minus one year.

**RF fitting (steps 02+)**
- RF fitted via Python GEE API, not locally in R.
- One RF per region × fire-class. Fire-class split (forest / shrubland / grassland-agri) may vary by region.
- The exported training asset is the canonical training set; CSV download is for inspection only.

## General Design Decisions

- **Asset-based processing**: each workflow step exports intermediate GEE assets, avoiding memory/computation limits and allowing inspection at each stage.
- **Manual masking step** (step 05): removes false positives from ash/drought; requires domain expert review before vectorization.
- **Run logs**: each `01-training_data_export.py` run writes a JSON sidecar with input paths, task IDs, versions, and parameters for reproducibility.
