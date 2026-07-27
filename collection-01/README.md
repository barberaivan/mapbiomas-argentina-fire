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
├── docs/                   # Per-workflow-step development notes (NN-*.md) — start here for design
├── utils/
│   ├── constants.py        # All paths, feature lists, MB reclass table, LR terms
│   └── functions.py        # Shared cross-step GEE helpers ONLY (Landsat, indices, MB sampling, veg_fire); step-specific code lives with its step
├── config/                 # veg_fire_remap.csv — canonical MB→fire-class remap (source of truth)
├── models/                 # Tracked: *_coefficients.csv (the GEE deliverable) + README; see models/README.md
├── models-store/           # symlink → Insync store (gitignored): heavy fits, CV metrics, tuning, OOF preds
├── workflow/               # Numbered pipeline steps (mixed Python + R)
│   ├── 01-training_data_export.py   # Export training data (one GEE task per fire)
│   ├── 02-model_fitting.R           # Fit LR per veg_fire class (R, glmnet)
│   ├── 03–07-*.{py,R}      # Prediction pipeline (bp ts → SNIC → objects → filter → raster) — in development
│   │                       # step 08 (network post-processing) has no script yet — docs/08-postprocessing.md
│   ├── run_05_years.sh              # Overnight all-years step-05 launcher — one Rscript/year, resumable, OOM-flagging (docs/05 §4.1)
│   └── mem_monitor.sh               # Lightweight RAM peak / near-OOM-warn monitor (used by run_05_years.sh; standalone too)
├── scripts/                # Ad-hoc utilities — not mandatory pipeline steps
│   ├── status.py                          # Check GEE export status across all regions
│   ├── download_observations.py           # Download training observations to local CSV
│   ├── download_snic.py                   # Direct tiled download of step-04 SNIC products (per-carta GeoTIFFs) — feeds step 05 (docs/04 §5b)
│   ├── data_cleaning.R                     # Add the `fit` gate column (base window filter + per-fire edits) — REQUIRED before step 02; see docs/02-data_cleaning.md
│   ├── export_region_raster.py            # Export region-ID raster to GEE asset
│   ├── veg-fire_remap_clean-google-sheet.R # Regenerate config/veg_fire_remap.csv from the Google Sheet
│   ├── cv_feasibility_report.py           # Pre-flight CV feasibility per veg_fire class (run before fitting)
│   ├── make_fires_table_stats.R           # Build fires_table_stats.csv from xlsx + obs CSVs
│   ├── ts_predict_functions.R             # design_raw() + predict_class(): RAW-scale prediction from a class_NN_fit.rds
│   ├── ts_plot_cache.R                    # Build models-store/ts_plot_cache_v1.rds (in-sample p_pred + n5-smoothed prob, every fitted class)
│   ├── ts_plot_functions.R                # Shared plot_fire_panel() (NBR/NBR2/raw p/smoothed p, Burned-over-Unburned); sourced below and by the notebook
│   └── ts_plot_by_fire.R                  # Driver: one panel per fire (pooled across classes) -> models-store/prediction_plots/{region}/region_fireNN.png
├── notebooks/              # Quarto-R (.qmd) exploratory analyses and decisions
├── samples/                # ARCHIVE — JS templates from interactive point collection
└── data/                   # symlink → Insync store (gitignored): local downloads and training inputs
```

---

## First-time setup (heavy data lives outside git)

Training inputs (`data/`) and heavy model outputs (`models-store/`) are **not** in git — they
live in the Insync/Drive-synced `mapbiomas-arg-fire-store` folder, symlinked into the repo by
`setup.sh`. **See the repo-root [README — "Getting started"](../README.md#getting-started-first-time-setup)
for the full setup.** Once linked, everything below works against the symlinked paths transparently.

---

## Running the pipeline

Run all scripts from the **repo root**. Commands below invoke Python as **`$PYTHON`** — the
project's GEE venv, configured per-machine by `setup.sh` (see the repo-root README). To use it
in your own terminal, `source .local-paths` first (or run `./setup.sh` once).

### Step 01 — Export training data

```bash
# Test on one fire first, review the asset schema in the GEE Code Editor
$PYTHON collection-01/workflow/01-training_data_export.py \
  --region PAT --version 1 --test-fire fire_32

# Full region — submits one GEE task per fire in parallel
$PYTHON collection-01/workflow/01-training_data_export.py \
  --region PAT --version 1
```

Output per fire: `COLLECTION-1/TRAINING-DATA/{region}/training_observations-fire_NN_v1`

A JSON run log is written to `workflow/01-training_data_export/run_{region}_v{version}.json`.

### Scripts (ad-hoc utilities)

```bash
# Check GEE export status across all regions (or one)
$PYTHON collection-01/scripts/status.py
$PYTHON collection-01/scripts/status.py --region PAT

# Download completed training observations to collection-01/data/ as a local CSV
$PYTHON collection-01/scripts/download_observations.py --region PAT --version 1
```

### Observation cleaning — the `fit` gate (R, REQUIRED before step 02)

Adds a boolean `fit` column to each `data/training_observations_{region}_v1.csv`: a base
window filter plus the per-fire manual edits transcribed from `data/data_cleaning.xlsx`.
`02-model_fitting.R` errors out if the column is missing and fits only `fit == TRUE` rows.
Idempotent — re-run after editing the rule table. See `docs/02-data_cleaning.md` (it documents
the date-ordering semantics, which are easy to get wrong).

```bash
Rscript collection-01/scripts/data_cleaning.R 1                       # all regions, version 1
CLEAN_REGIONS=CHACO Rscript collection-01/scripts/data_cleaning.R 1   # one region (debugging)
```

### Step 02 — Model fitting (R)

Fitted locally in R with `glmnet` — one elastic-net logistic regression per **veg_fire
class** (a class may span regions, e.g. `agriculture_cuyo-pat`). The fitting unit is the
class, read from `config/veg_fire_remap.csv`. Run a CV feasibility check first, then fit
all available classes or a named subset. Outputs land in `models/` (see `models/README.md`).

```bash
# Pre-flight: confirm each class has enough positive-bearing fires for grouped CV
$PYTHON collection-01/scripts/cv_feasibility_report.py --version 1

# Fit all fittable classes whose region data is available...
Rscript collection-01/workflow/02-model_fitting.R 1
# ...or restrict to named classes (memory-heavy ones: FIT_CORES=2 or 1)
Rscript collection-01/workflow/02-model_fitting.R 1 agriculture_cuyo-pat forest_pat
```

Regenerate the canonical remap from the Google Sheet whenever it changes (do not hand-edit the CSV):

```bash
Rscript collection-01/scripts/veg-fire_remap_clean-google-sheet.R
```

### Steps 03–09

In development. See the per-step notes in `collection-01/docs/` (03 bp-ts metrics, 04 SNIC,
05 object metrics, 06 object model, 07 vector→raster, 08 post-processing, 09 statistics/launch) and the
scripts in `collection-01/workflow/`.

**Steps 01–07 are our own mapping method; step 08 is not.** Once step 07 delivers the month-of-burn
raster, the remaining work is the **MapBiomas Fuego network-wide post-processing, publication and
launch process** — the same six stages every country runs (consolidated collection → LULC-masked
final version → subproducts → statistics → public assets + Workspace catastro → launch), each with a
country-team validation gate, so that all countries' products are identical in name, band format,
encoding and legend despite mapping with a different method (Alencar et al. 2022). Reproduce it from
the network's reference code, don't redesign it:

- `docs/08-postprocessing.md` — stages 1–4: the GEE assets (what each reference script does, **§6
  Argentina's route**, what we owe, open decisions).
- `docs/09-statistics.md` — stages 5–6 + launch: statistics, territorial layer, Workspace, materials.
- [*Guía del Proceso de Lanzamiento — MapBiomas Fuego*](https://docs.google.com/presentation/d/1Y5SUeS_405k5zZkBX4z6BDaC_umI8Saiguk7coITB1Q/edit) — the network's own guide (public; `docs/08` §1 shows how to read it as a PDF).
- Read-only reference repo at `/home/ivan/dev/MapBiomas/mapbiomas-latam-fire-gee/` (see CLAUDE.md → *GEE Code Editor scripts*).

**Argentina is expected to deliver all six subproducts** (annual, monthly, accumulated, frequency,
year of last fire, scar size). Dates: assets to MapBiomas Argentina **31 Jul 2026**, public launch
**24 Sep 2026**.

Step 05 (object vectorization & metrics, R) runs **one fire-year at a time**. For the full
2001–2025 run, use the overnight launcher — one `Rscript` per year (resumable; OOM-killed years
are flagged and don't stop the batch) with a lightweight RAM monitor alongside (**docs/05 §4.1**):

```bash
# launch detached; use an ABSOLUTE path (see docs/05 §4.1)
tmux new-session -d -s obj05 '/abs/path/to/collection-01/workflow/run_05_years.sh 2001 2025'
tmux attach -t obj05            # watch; Ctrl-B D to detach
grep -E 'OOM|WARN|FAILED|done rc=0' collection-01/logs/05_{run,mem}_*.log   # morning triage
```

### Scripts (R utilities)

```bash
# Build fires_table_stats.csv (needed by data_collection_stats.qmd)
# Re-run whenever training observation CSVs are updated.
Rscript collection-01/scripts/make_fires_table_stats.R
```

### Scripts (R utilities) — step-06 label prep

Downloads the per-collaborator fire/non-fire collections exported by the GEE
`training_polygons_*` scripts (one GeoPackage per asset, individually
re-downloadable) and matches every label to the step-05 objects of its own
fire-year, attaching their metrics → `data/polygons_data/polygons_data_merged.csv`,
the table the object model is fitted on. Details + measured timings:
`docs/06-object_model.md` "Label prep".

```bash
Rscript collection-01/scripts/polygons_data_prep.R              # download missing, then merge
Rscript collection-01/scripts/polygons_data_prep.R download camilo --force   # one author again
Rscript collection-01/scripts/polygons_data_prep.R merge        # re-merge everything present
```

### Scripts (R utilities) — time-series diagnostics

Per-fire diagnostic: a 4-row (NBR / NBR2 / raw predicted burn probability /
smoothed predicted burn probability) time series, Burned stacked above Unburned,
one line per training point — for
spotting fires whose pre/post-fire date window is mis-defined. Predicts
**in-sample** (`class_NN_fit.rds`, not OOF) over the full training
observations; see `models/README.md` for the caveat. Aesthetic (colors, line
geoms, n5 rolling-median smoothing) mirrors
`collection-00/data_viz_Lican/functions.R::plot_tempseg()`.

```bash
# 1. Build the prediction cache (re-run after syncing new/updated class_NN_fit.rds)
Rscript collection-01/scripts/ts_plot_cache.R

# 2. One PNG per fire (pooled across classes) -> models-store/prediction_plots/{region}/region_fireNN.png
Rscript collection-01/scripts/ts_plot_by_fire.R
```

The median marker is a solid burn-class–colored point for dates whose observations
were used in fitting (`fit == TRUE`) and a red asterisk for held-out dates
(`fit == FALSE`). These PNGs are standalone — they are not embedded in any notebook.

### Notebooks (Quarto-R)

| Notebook | Purpose | Dependencies |
|----------|---------|--------------|
| `land_cover_remap.qmd` | Validate the canonical MB → fire-class remap against full obs; CV feasibility per class | training obs CSVs, `config/veg_fire_remap.csv`, Google Sheets |
| `model_fit_diagnostics.qmd` | Per-class fit diagnostics (tuning, coefficients, calibration, OOF, omission/commission, by-fire OOF breakdown) | `models/class_*_coefficients.csv`, `models-store/class_*` outputs (+ `_model_fit_diagnostics_child.qmd` template) |
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
| 02 — model fitting (R, glmnet) | All 23 `veg_fire` classes fitted (v1); see `models/cv_metrics_v1.csv`. |
| 03–07 — prediction pipeline | Stubs |
| 08 — network post-processing & published subproducts | Not started; design notes only (`docs/08-postprocessing.md`). Assets due **31 Jul 2026** |
| 09 — statistics, publication, launch | Not started; design notes only (`docs/09-statistics.md`). Launch **24 Sep 2026** |
