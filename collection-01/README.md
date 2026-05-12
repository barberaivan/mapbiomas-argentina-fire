# MapBiomas Argentina Fire — Collection 01

*In development. See [`collection-00/README_00.md`](../collection-00/README_00.md) for the complete pilot.*

---

## What changed from collection 0

| Aspect | Collection 0 | Collection 1 |
|--------|-------------|-------------|
| Coverage | Patagonia only | BA, CHACO, PAMPA, CUYO, PAT |
| Model | Logistic regression (2 levels) | Random Forest |
| Language | GEE JavaScript + R | GEE Python API |
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
│   ├── constants.py        # All paths, feature lists, MB reclass table, RF params
│   └── functions.py        # GEE helpers: Landsat preprocessing, indices, MB sampling
├── workflow/
│   ├── 00-status.py        # Check export status across all regions
│   ├── 01-training_data_export.py   # Export training data (one GEE task per fire)
│   └── 02–08-*.py          # Stubs — in development
├── notebooks/              # Quarto-R (.qmd) exploratory analyses
├── samples/                # ARCHIVE — JS templates from interactive point collection
└── data/                   # gitignored — local downloads and scratch files
```

---

## Running the pipeline

Run all scripts from the **repo root**.

### Step 00 — Check status

```bash
/home/ivan/.venvs/gee/bin/python collection-01/workflow/00-status.py
/home/ivan/.venvs/gee/bin/python collection-01/workflow/00-status.py --region PAT
```

Reports DONE / RUNNING / PENDING / FAILED / MISSING for each fire in each region.

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

### Steps 02–08

In development. See script stubs in `collection-01/workflow/`.

### Notebooks (Quarto-R, run in order)

| Notebook | When to run | Output |
|----------|-------------|--------|
| `01-landcover_reclassification.qmd` | Before step 01 | `MB_RECLASS_FROM/TO` in `constants.py` |
| `02-training_sample_audit.qmd` | After step 01 | Class balance checks per region |
| `03-rf_hyperparameter_tuning.qmd` | After step 01 | `RF_PARAMS` in `constants.py` |

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
| 02 — RF model fitting | Stub |
| 03–08 — prediction pipeline | Stubs |
