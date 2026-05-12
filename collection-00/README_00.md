# MapBiomas Argentina Fire

**MapBiomas Argentina – Fire Mapping Algorithm**  
*Pilot: Collection 0*

---

## Documentation (read first)

Before using or reproducing the workflow, please read the [documentation](https://github.com/barberaivan/mapbiomas-argentina-fire/blob/main/collection-00/docs/documentation_pilot_latex/build/mapbiomas_fire_argentina_atbd_pilot_2025.pdf); the README focuses exclusively on how to reproduce and deploy the algorithm.

---

## Repository scope

This repository contains the complete Fire mapping workflow for MapBiomas Argentina, including:

- Google Earth Engine (GEE) scripts for:
  - Training data extraction
  - Burn probability estimation
  - Temporal and spatial segmentation
  - Object-based filtering and final products
- R scripts for:
  - Fitting burn probability models
  - Exporting model coefficients to GEE-compatible format

Most processing occurs in GEE; R is only required to fit the burn probability models.

---

## High-level workflow overview

The pipeline is modular and asset-based. Intermediate products are exported at each step to avoid GEE memory limits.

There are two valid entry points, depending on whether you use the provided models or fit your own:

#### Option A — Use pre-fitted models (not recommended)
You only need:

- `/utils`
- `/workflow`

#### Option B — Fit your own models (recommended)
You must run the full pipeline:

1. `/samples`
2. `/models_fit` (R)
3. `/utils` (update `constants.js`)
4. `/workflow`

---

## Google Earth Engine repository structure

The GEE-side code mirrors the following structure:

```text
users/mapbiomas-arg/fuego/collection-00
├── samples/ # Training data collection
│ ├── training_data_export
│ ├── training_fires
│ ├── training_locations-fire_00_template # Replicated for fire_01 … fire_30
│
├── utils/ # Core dependencies (required)
│ ├── constants.js # Logistic regression coefficients (from R) and more
│ └── functions.js # Core functions used by the workflow
│
├── workflow/ # Main production pipeline
│ ├── 01-burn_prob_obs-burn_indices_summaries
│ ├── 01-filters-ancillary_indices_summaries
│ ├── 02-temporal_segmentation-time_series_metrics
│ ├── 03-temporal_segmentation-annual_burn_prob
│ ├── 04-spatial_segmentation-snic
│ ├── 05-spatial_segmentation-mask_handmade
│ ├── 06-spatial_segmentation-objects
│ ├── 07-spatial_segmentation-objects_metrics
│ └── 08-object_based_filtering
```

---

## Workflow logic (GEE)

Each script in `/workflow`:

- Operates year by year
- Exports an image or vector asset
- Uses those assets as inputs for the next step

This design is intentional and required to:

- Avoid GEE memory and execution limits
- Allow partial reruns and inspection of intermediate products

### Workflow steps

1. **Annual summaries of burn indices and ancillary ones**  
   Annual layers of burn-related spectral indices and ancillary indices for brightness.

2. **Temporal segmentation**  
   Computes the time-series of burn probability at the observation level using a fitted logistic regression, based on spectral indices. Then, computes the annual time-series metrics, producing an annual multi-band image.

3. **Annual burn probability**  
   Applies a second logistic regression model to produce burn probability layers at the annual level.

4. **Region growing algorithm (SNIC)**  
   Generates annual clusters of burned area.

5. **Manual masking**  
   Masks ash and drought artifacts based on annual burn probability layers.

7. **Object vectorization**  
   Converts SNIC clusters into polygons.
   
6. **Objects metrics**  
   Computes polygon-level metrics, for filtering.

8. **Filtering and final products**  
   Applies object-level filters, and produces:
   - Final annual burned area layers
   - Derived products (e.g. fire frequency)

---

## R-side: model fitting (`/models_fit`)

Burn probability models are fitted locally in R.

### Requirements

- R (≥4.5.1)
- Working directory set to: `../models_fit`

### Data

To reproduce model fitting with our data, download the required inputs from [Google Drive](https://drive.google.com/drive/folders/11sIlmlSFVWNgOGPPOlhgEaiRvdDM4S-Q).

You need:

- `models_fit/data/`
- `.rds` files from `models_fit/exports/`

### Outputs

The R workflow exports the logistic regression coefficients as GEE-ready constants (.js files). Their content must be copied in the into `/utils/constants.js`.

Only after updating `constants.js` can the GEE workflow be executed with the new models.

---

## Running the full pipeline with custom models

1. Run `/samples` in GEE to collect training data
2. Export samples to Google Drive
3. Fit models in `/models_fit` (R)
4. Update `/utils/constants.js`
5. Run `/workflow` sequentially (Steps 01 → 08)

---

## Running the pipeline with provided models

If you use the models we fitted for the pilot:

1. Ensure `/utils` and `/workflow` are available
2. Do not run `/samples` or `/models_fit`
3. Execute `/workflow` sequentially in GEE

This is not recommended, as the relationship between spectral/time-series metrics and burn probability varies in space. It is only suggested for experimental usage.

---

## Status

This repository corresponds to Collection 0 (pilot) of MapBiomas Argentina Fire.  
Structure and logic may evolve in future collections.