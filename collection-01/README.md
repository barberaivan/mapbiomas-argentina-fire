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
│                           # object_model_thresholds.csv — step-06 fire-call cut per size band (docs/06 §6)
├── models/                 # Tracked: *_coefficients.csv (the GEE deliverable) + README; see models/README.md
├── models-store/           # symlink → Insync store (gitignored): heavy fits, CV metrics, tuning, OOF preds
├── workflow/               # Numbered pipeline steps (mixed Python + R)
│   ├── 01-training_data_export.py   # Export training data (one GEE task per fire)
│   ├── 02-model_fitting.R           # Fit LR per veg_fire class (R, glmnet)
│   ├── 03–06-*.{py,R}      # Prediction pipeline (bp ts → SNIC → objects → object model)
│   ├── 07-month_of_burn.py          # Month of burn per CALENDAR year, in GEE (docs/07 §7)
│   ├── 07-calendar_scars.R          # 8-connected calendar-year scars, locally, two passes (docs/07 §8)
│   ├── 07-scar_rasters.py           # Scar id / area / size-range rasters from the ingested scar FCs
│   └── 07-subproducts.py            # The 9 derived subproducts, from the month collection (docs/07 §12)
│                           # step 08 (network post-processing) has no script yet — docs/08-postprocessing.md
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
│   ├── ts_plot_by_fire.R                  # Driver: one panel per fire (pooled across classes) -> models-store/prediction_plots/{region}/region_fireNN.png
│   ├── objects_data_functions.R           # step 06: THE SHARED MODULE — readers, derived predictors, veg groups, clean_tagged(), tag lookup, thresholds, regions, c-00 filter
│   ├── objects_labels_prep.R               # step 06: download the per-collaborator label assets, join them to objects -> polygons_data_merged.csv
│   ├── objects_data_explore.R             # step 06: size distribution of the full table + how the c-00 empirical filter splits it
│   ├── objects_threshold.R                # step 06: per-size-band fire-call threshold from out-of-fold preds -> config/object_model_thresholds.csv
│   ├── objects_importance_ale.R           # step 06: 4 importance measures + 1-D ALE curves for the 20 predictors -> data/objects-analysis/
│   ├── objects_inspect_export.R           # step 06: GPKG (QGIS, 32 curated fields) of predictions, to inspect without a GEE upload (--sample N adds a GeoJSON)
│   ├── objects_upload.py                  # step 06/07: package one fire-year (geometry + all 20 predictors + the calls) as a zipped Shapefile for GEE
│   ├── validate_upload_zips.py            # step 06/07: pre-upload gate over the 28 zips (schema, code fields, counts, geometry) -> upload_zip_validation.csv
│   ├── run_06_predict.sh                  # step 06: parallel scoring — one Rscript per fire-year, 8 at a time, resumable (prediction is single-threaded)
│   ├── run_06_inspect.sh                  # step 06: parallel QGIS-layer build — one Rscript per fire-year, 6 at a time (I/O + memory bound), resumable
│   ├── run_07_upload_zips.sh              # step 07: parallel upload-package build — one process per fire-year, 4 at a time, resumable
│   ├── run_07_scars.sh                    # step 07: calendar-year scar build in two passes — `pixels` per fire-year (-j 5), `scars` per calendar year (-j 2), resumable
│   ├── validate_scar_zips.py              # step 07: pre-ingest gate over the 27 scar zips (fields/types, gapless scar_id, area vs summary, CRS, geometry)
│   ├── run_05_years.sh                    # Overnight all-years step-05 launcher — one Rscript/year, resumable, OOM-flagging (docs/05 §4.1)
│   └── mem_monitor.sh                     # Lightweight RAM peak / near-OOM-warn monitor (used by run_05_years.sh; standalone too)
├── notebooks/              # Quarto-R (.qmd) exploratory analyses and decisions
├── samples/                # ARCHIVE — JS templates from interactive point collection
└── data/                   # symlink → Insync store (gitignored): downloads, training inputs, steps 04–06 outputs
```

### Where the step-04→06 data lives (`data/`, in the store — not git)

| directory | contents | size |
|---|---|---|
| `snic-rasters/<fy>/` | step-04 per-carta SNIC GeoTIFFs — the step-05 input | 11 GB |
| `objects-raw/` | step-05 output: `objects_<fy>.gpkg` (geometry + `oid`) + the two metrics CSVs | 6.8 GB |
| `objects-labels/` | the collected labels: one GPKG per collaborator + `polygons_data_merged.csv` | 4 MB |
| `objects-pred/` | step-06 output: `objects_<fy>_pred.csv` (`p_*`, `fire_model`, `fire_tag`, `fire`), `_derived.csv`, `oof_grid_5.csv` | 317 MB |
| `objects-analysis/` | every reported table/plot from the scripts and the notebook | 2 MB |
| `objects-inspect-cache/` | 28 QGIS layers + a `.qgz` project — **regenerable** | 6.3 GB |
| `objects-upload-cache/` | the 28 GEE upload zips + loose Shapefile components — **regenerable** | 8.4 GB |

A fire is an **object** (the layer is sparse, not an OBIA partition), and a **`-cache` suffix means
regenerable**: delete it and re-run its launcher. Details: `docs/05-object_metrics.md` §4 and
`docs/06-object_model.md` "Files, directories and scripts".

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
tmux new-session -d -s obj05 '/abs/path/to/collection-01/scripts/run_05_years.sh 2001 2025'
tmux attach -t obj05            # watch; Ctrl-B D to detach
grep -E 'OOM|WARN|FAILED|done rc=0' collection-01/logs/05_{run,mem}_*.log   # morning triage
```

### Scripts (R utilities)

```bash
# Build fires_table_stats.csv (needed by data_collection_stats.qmd)
# Re-run whenever training observation CSVs are updated.
Rscript collection-01/scripts/make_fires_table_stats.R
```

### Step 06 — object model (R, stochtree BART)

Fits one probit-BART on the clean labelled objects (5255 objects, prevalence 0.53) and scores a
fire-year's objects with a posterior probability of being fire
(`p_mean`/`p_sd`/`p_q05`/`p_q95`/`p_width`). Needs `stochtree` (CRAN). Measured timings, the CV
result and every decision: `docs/06-object_model.md`.

**20 predictors**: 15 non-vegetation metrics + 5 aggregated vegetation fractions (the 23 raw class
fractions summed by group, which measured better than using them raw). **No predictor identifies the
year, and none proxies for it** — `fire_year` and `year_calendar` were removed after they were found
to be reading the per-year label prevalence rather than the fire regime, `n_mean` after it was found
to track the growth of the Landsat record, and day-of-year enters circularly as `doy_sin`/`doy_cos`.
Read `docs/06-object_model.md` §4 before touching the predictor set.

**Three call columns** come out of `predict`: `fire_model` (the model at its size-band cut),
`fire_tag` (the collected label, `-1` where there is none) and **`fire`** — the deployed call, which
is the tag where there is one and the model otherwise.

```bash
Rscript collection-01/workflow/06-object_model.R              # fit, then time one year (FY2020)
Rscript collection-01/workflow/06-object_model.R fit
Rscript collection-01/workflow/06-object_model.R predict 2020 2014
Rscript collection-01/workflow/06-object_model.R cv grid 5     # 0.5 deg blocks -> 5 folds — THE DEPLOYED DESIGN (AUC 0.891)
Rscript collection-01/workflow/06-object_model.R cv           # leave-one-region-out (harsher than deployment; not maintained)
Rscript collection-01/workflow/06-object_model.R cv random 5    # random folds, leak-inflated, for contrast
# every year: use the PARALLEL launcher — stochtree prediction is single-threaded, so one
# process per fire-year (8 at a time) is 4.5 min instead of ~37. Resumable.
tmux new-session -d -s obj06 '/abs/path/to/collection-01/scripts/run_06_predict.sh -j 8'
```

`OBJ_THREADS` (8) `MCMC_ITER` (2000) `POST_DRAWS` (500) `NUM_GFR` (10) `PRED_CHUNK` (20000).

The fire call uses a **per-size-band cut** (0.250 / 0.202 / 0.436 / 0.690 — the cut *rises* with
object size), re-derivable from the out-of-fold predictions, plus the importance/ALE analysis that
says which predictors carry the model:

```bash
Rscript collection-01/scripts/objects_threshold.R        # -> config/object_model_thresholds.csv (tracked)
Rscript collection-01/scripts/objects_importance_ale.R   # -> data/objects-analysis/{importance,ale_curves}_objects.csv
```

Map inspection with **no GEE upload** — joins the predictions onto the step-05 geometry
already on disk: a full GPKG for QGIS, plus a small decile-stratified GeoJSON light enough
to drop into geemap/leafmap as a client-side layer next to GEE imagery tiles
(`docs/06-object_model.md` "Looking at it on a map without uploading to GEE"):

```bash
Rscript collection-01/scripts/objects_inspect_export.R 2020            # both products
Rscript collection-01/scripts/objects_inspect_export.R 2020 --sample 40 --no-full
Rscript collection-01/scripts/objects_inspect_export.R 2020 --fields all  # keep the 23 raw frac_c*

# ALL years: the parallel launcher (28 layers, 6.3 GB, ~1 min on 6 workers). Resumable.
tmux new-session -d -s obj06i '/abs/path/to/collection-01/scripts/run_06_inspect.sh -j 6'
```

The GPKG carries **32 curated fields**: identity/size, the verdicts (`fire`, `fire_model`,
`fire_tag`, `c00_pass`, and `verdict` = model-vs-c00 agreement), why the model called it (`p_mean`,
`p_width`, `p_thresh`, `p_margin`, `th_band`), burn evidence + timing, the 5 aggregated veg
fractions and the 6 shape metrics. Useful QGIS filters: `"verdict" != 'both'` (disagreement),
`abs("p_margin") < 0.05` (borderline calls), `"p_width" > 0.5` (model has no idea), `"fire_tag" >= 0`
(the collected labels). Note the layer name starts with a digit, so SQL contexts need it
double-quoted. **Where to start:** `"verdict" = 'c00 only' AND "area_ha" >= 300` — 5872 objects /
6397 kha (7.5 % of all object area) that the old filter keeps and the model rejects without
confidence. Full guidance: docs/06 §11.

Data exploration behind the size cuts and the collection-00 filter comparison — reads the
full 1.69 M-object table and the clean labelled table, writes CSVs + PNGs to
`data/objects-analysis/`:

```bash
Rscript collection-01/scripts/objects_data_explore.R          # ~1 min, ~1 GB
```

Both share `scripts/objects_data_functions.R` (loaders, `clean_tagged()`, the c-00 filter),
so "the clean labelled table" means the same rows in both.

### Step 06b — the GEE upload packages (the object FeatureCollections)

**Every object of every fire-year goes up**, not only the ones called fire: a fire-only layer can
only show commission error, and a reviewer needs the rejected objects to find the fires the model
*missed*. One FeatureCollection per fire-year, carrying `oid`, all **20 predictors**, the three call
columns, `p_mean`/`p_width`, `year_cal` and `date_medd`:

```
projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/WORKFLOW-EXPORTS/objects_raw/objects_raw_YYYY
```

`YYYY` is the **fire-year**. Ingest is **by hand** (Code Editor → Assets → NEW → Table upload →
Shapefile) because `earthengine upload table` only accepts `gs://` sources and no GCS bucket is
reachable — **set max vertices = 1000000** in the dialog for every year (two years hold a single
feature above 1 M vertices). A single all-years table is impossible on ingest: `.shp` caps at 2 GB.
Merge server-side afterwards if one FC is wanted.

```bash
# build all 28 packages (biggest first, resumable) — 1.3 GB total
tmux new-session -d -s zip07 '/abs/path/to/collection-01/scripts/run_07_upload_zips.sh -j 4'

# then GATE them before uploading: schema, code fields, counts, geometry
tmux new-session -d -s validate '$PYTHON collection-01/scripts/validate_upload_zips.py -j 8'
```

The validator exists because a hand upload has no failing pipeline to catch a bad zip — it would
surface weeks later as a wrong map. Its sharpest check is that `fire`/`fire_model`/`fire_tag` are
never NULL: OGR writes an unset DBF integer as null and GEE reads it as `0`, indistinguishable from
"a human said NOT fire", hence the `-1` sentinel. Full detail: docs/06 §12.

### Step 07 — the calendar-year products

Two deliverables, and they must agree pixel-for-pixel: the **month-of-burn raster** per calendar
year, and the **calendar-year scars** the size products are painted from. Design and the
verification numbers are in `docs/07-vector_to_raster.md`.

```
calendar year Y  =  Jan-Apr Y  from fire-year (Y-1)   |+|   May-Dec Y  from fire-year Y
```

Only objects with `fire == 1 & area_ha >= 1` contribute, and calendar year + month are taken
**per pixel** from `abs_date` — never per object from `year_calendar`.

**7a — month of burn, in GEE.** Nothing to upload: it paints the step-06 object FCs against the
SNIC assets already in GEE.

```bash
# audit a SMALL roi first — never the whole country (reduceRegion at 30 m is not cheap)
$PYTHON collection-01/workflow/07-month_of_burn.py --year 2020 --check --roi=-61.6,-25.6,-61.1,-25.1

$PYTHON collection-01/workflow/07-month_of_burn.py --all --launch    # 27 tasks — inside tmux
```

**7b — calendar-year scars, locally.** GEE cannot label these: `connectedPixelCount` caps at
1024 px (~92 ha), far below a real scar. Two passes, because each fire-year feeds two calendar
years and reading the 248 carta tiles is the dominant cost. **Run `pixels` to completion first** —
a calendar year needs both of its fire-years.

```bash
tmux new-session -d -s s07pix '/abs/path/to/collection-01/scripts/run_07_scars.sh pixels -j 5'
# then, one process per calendar year; memory-bound, so few years x more cores each
tmux new-session -d -s s07scar 'OBJ_CORES=6 /abs/path/to/collection-01/scripts/run_07_scars.sh scars -j 2'

# GATE the 27 packages before any manual ingest
$PYTHON collection-01/scripts/validate_scar_zips.py
```

`pixels` writes a regenerable cache (`data/scars-pixels-cache/`, ~24 GB — safe to delete);
`scars` writes `data/objects-scars/scars_<Y>.gpkg` + summary CSVs and the upload package
`data/scars-upload-cache/scars_<Y>.zip`.

**7c — scar rasters, in GEE**, once the 27 scar FCs are ingested by hand into
`.../COLLECTION-1/FINAL_PRODUCTS/annual_burned_vectors/scars_<Y>`:

```bash
# mask agreement; pass a --roi box, a whole-country interactive reduce is slow
$PYTHON collection-01/workflow/07-scar_rasters.py --check --years 2003,2020 --roi=-61.6,-25.6,-61.1,-25.1
$PYTHON collection-01/workflow/07-scar_rasters.py --launch     # skips assets that already exist
```

**7d — the nine derived subproducts, in GEE.** `monthly_burned`, `annual_burned`, both
`*_coverage`, `frequency_burned` (+`_coverage`), `accumulated_burned` (+`_coverage`),
`year_last_fire`. All nine derive from 7a's month collection plus the MapBiomas LULC, so they do
**not** wait for 7c, and the encodings are copied verbatim from the network's reference scripts —
do not innovate there (`docs/07-vector_to_raster.md` §12).

```bash
$PYTHON collection-01/workflow/07-subproducts.py --check      # band bookkeeping + ROI counts
$PYTHON collection-01/workflow/07-subproducts.py --launch      # 9 tasks
$PYTHON collection-01/workflow/07-subproducts.py --launch --only frequency_burned   # just one
```

### Scripts (R utilities) — step-06 label prep

Downloads the per-collaborator fire/non-fire collections exported by the GEE
`training_polygons_*` scripts (one GeoPackage per asset, individually
re-downloadable) and matches every label to the step-05 objects of its own
fire-year, attaching their metrics → `data/objects-labels/polygons_data_merged.csv`,
the table the object model is fitted on. Details + measured timings:
`docs/06-object_model.md` "Label prep".

```bash
Rscript collection-01/scripts/objects_labels_prep.R              # download missing, then merge
Rscript collection-01/scripts/objects_labels_prep.R download camilo --force   # one author again
Rscript collection-01/scripts/objects_labels_prep.R merge        # re-merge everything present
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
| `objects-analysis.qmd` | Step 06, the standing analysis: size distribution of all 1.69 M objects (6 display classes), the latitude-dependent pixel scale, labels vs population by size, `p_mean`/`p_width`/`% undecided` per class → the **minimum-fire-size** decision; the **per-size-band classification cuts** (Youden J, sens/spec, bootstrap intervals, ROC); the **per-year leak diagnostic** (§8 — the check that caught `fire_year`, plus §8.1 the residual time trend); and **§9 predictor importance + ALE curves** | step-05 metrics + `run_06_predict.sh` + `objects_threshold.R` + `objects_importance_ale.R` |

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
| 03 — burn-probability time series | Running (per-carta export; `docs/03-bpts.md`). |
| 04 — SNIC segmentation | Whole-country fire-year SNIC settled; Drive-COG handoff to R (`docs/04-snic.md`). |
| 05 — object metrics (R/terra) | 2001–2025 measured and run; 1.69 M objects (`docs/05-object_metrics.md`). |
| 06 — object model (R, BART) | **Done.** 20 predictors, fitted on 5255 labels, grid-blocked OOF AUC 0.891 (within-year 0.845); per-size-band cuts deployed; all 28 fire-years scored (1 689 419 objects, 36 unscored); 28 QGIS layers built and inspected (`docs/06-object_model.md`). |
| 07 — calendar-year products | Object FCs ingested (28). **07a month-of-burn ImageCollection** done (27/27); **07b calendar-year scars** built locally, gated and ingested (27/27); **07c scar rasters** done (3/3, verified on the landed assets); **07d the nine derived subproducts** exporting (9 tasks) — `docs/07-vector_to_raster.md`. |
| 08 — network post-processing & published subproducts | Not started; design notes only (`docs/08-postprocessing.md`). Assets due **31 Jul 2026** |
| 09 — statistics, publication, launch | Not started; design notes only (`docs/09-statistics.md`). Launch **24 Sep 2026** |
