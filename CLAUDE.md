# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Primary Focus

**Active development is almost always in `collection-01/`, running `.py` scripts from `collection-01/workflow/`.** Default to that context unless the user says otherwise.

## Project Overview

MapBiomas Argentina Fire is a geospatial pipeline for detecting and mapping burned areas in Argentina using Landsat satellite imagery. The algorithm produces annual burned area products across two collections:

- **Collection 0** (`collection-00/`): Pilot — complete and operational. Covers Patagonia only.
- **Collection 1** (`collection-01/`): In development. Covers all five regions (BA, CHACO, PAMPA, CUYO, PAT).

## Technology Stack

| Component | Collection 0 | Collection 1 |
|-----------|-------------|-------------|
| GEE processing | JavaScript API | Python API (`earthengine-api`) |
| Model fitting | R (logistic regression -LR-) | same |
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
2. **LR model fitting** (`workflow/02-model_fitting.py`, stub): fit Random Forest per region × fire-class in GEE.
3. **Prediction pipeline** (`workflow/03–08`, stubs): same burn-probability → SNIC → masking → filtering structure as collection 0.

Key files:
- `collection-01/utils/constants.py` — single source of truth: paths, year range, spectral features, MB reclass table, LR terms, MB mosaic band list
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
- 40 bands selected from 111: optical (6) + NDVI + NDWI + NPV + NDFI, each with median/dry/wet/stdDev aggregates.
- Selection (`.select()`) happens before `.mosaic()` so only the 40 bands are processed.
- Previous-year mosaic: for observations in year Y, the mosaic for year Y−1 is attached.
- The loop variable is `mb_year` (the actual MB data year). `obs_year = mb_year + 1`. Range: `mb_start_year = obs_start_year − 1` to `mb_end_year = obs_end_year − 1`.

**MapBiomas land cover remap**
- The previous-year land cover is used to fit separate models, but with a remap of the argentina-level legend to have only a few classes by region (fire-class).
- Fire-class remap info is in the following [Google Sheets table](https://docs.google.com/spreadsheets/d/17ZShb8D0JaJw4nLvBDzt19xF6Fdg8lGHYs4Jogh0X1A/edit?gid=1376068841#gid=1376068841).
- `remap_by_region` sheet has `id` as argentina-wide classes, with `veg_fire_name_1` and `veg_fire_name_2` being to remap proposals. 
- Area analysis for the remaps are in `collection-01/notebooks/land_cover_remap.qmd`.
- The remap is still being decided, so there are no reliable constants, but the most updated source is the Google Sheets.

**Burned label at observation level**
- `burned=0`: all observations from unburned points, and observations from burned points in the pre-fire window.
- `burned=1`: observations from burned points in the post-fire window (post_lwr → post_upr_long).
- `post_upr_short` is preserved in `training_fires` for filtering at training time but not used to assign labels.
- `pre_lwr` is often null in assets → computed as `pre_upr` minus one year.

**LR fitting (steps 02+)**
- LR fitted via locally in R using glmnet for regularization. ~300 predictor variables, described in `collection-01/notebooks/burn_probability_terms.qmd`.
- One LR per region × fire-class. 
- The exported training asset is the canonical training set; but there is a large CSV download (all fires together) to fit locally.

## Collection 1 — Notebooks

All notebooks are Quarto-R (`.qmd`) in `collection-01/notebooks/`. Render with `quarto render` or run chunks interactively in RStudio.

| Notebook | What's in it |
|----------|-------------|
| `algo-fuego.qmd` | Flowchart of the full fire-mapping algorithm (Mermaid/DOT). No analysis code. |
| `land_cover_remap.qmd` | Validates the MB Argentina → fire-class remap proposals 1 and 2 by region. Shows burned/unburned counts per class, area fractions, and per-fire robustness. Source of the reclassification and downsampling decisions. |
| `data_collection_stats.qmd` | Stats on the field data collection effort: time, authors, points and observations per fire. Requires `fires_table_stats.csv` — if obs CSVs changed, run `scripts/make_fires_table_stats.R` first. |
| `logistic_regression_terms.qmd` | Design of the LR term structure for the obs-level burn-probability model. Covers which features and interactions to include. |
| `logistic_regression_feature_engineering_ideas.qmd` | Exploratory ideas for feature engineering (non-linearities, interactions) for the LR model. Conceptual, not production code. |
| `burn_prob_ts_metrics.qmd` | Explores summary metrics derived from the intra-annual burn-probability time series. Compares rolling means, forward differences, and other statistics on synthetic signals. |

## GEE Code Editor Scripts

GEE JavaScript scripts live in a separate git repo cloned from Google's hosting:

- **Local path**: `/home/ivan/Insync/MapBiomas/mapbiomas-argentina-fire-gee/`
- **Remote**: `https://earthengine.googlesource.com/users/mapbiomas-arg/fuego` (repo name: `mapbiomas-arg/fuego`)
- **Credentials**: set up in `~/.gitcookies` (Google-issued token)

The user does **not** regularly pull this repo, so it may be behind. **Always `git pull` before editing any file in it**, then edit, then `git push`. The Code Editor reflects the push immediately on next refresh.

```bash
cd /home/ivan/Insync/MapBiomas/mapbiomas-argentina-fire-gee && git pull
# … edit files …
git add <file> && git commit -m "message" && git push
```

The `fuego` repo is the sole source of truth for all GEE JS code — do not keep `.js` copies in this repo.

## Running Long Scripts

For local processing estimated to take more than ~15 minutes, use `tmux` so the run survives session closure. GEE task-submission scripts are short enough to run normally.

```bash
tmux new-session -d -s <name> \
  '/home/ivan/.venvs/gee/bin/python -u <script> [args] 2>&1 | tee <logfile>'
```

Reattach with `tmux attach -t <name>`; detach without killing with `Ctrl+B D`. If unsure whether a run is heavy enough, ask the user before launching.

## General Design Decisions

- **Asset-based processing**: each workflow step exports intermediate GEE assets, avoiding memory/computation limits and allowing inspection at each stage.
- **Manual masking step** (step 05): removes false positives from ash/drought; requires domain expert review before vectorization.
- **Run logs**: each `01-training_data_export.py` run writes a JSON sidecar with input paths, task IDs, versions, and parameters for reproducibility.
