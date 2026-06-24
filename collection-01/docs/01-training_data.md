# 01 — Training data

How the labeled training set for the burn-probability model is built. This is a
short operational note, **not** the ATBD (see `collection-00/docs/` for the pilot
ATBD that this draws from).

## Inputs

- **Landsat C2 SR** (L5 TM, L7 ETM+, L8 OLI, L9 OLI-2), 1999–2025, all scenes
  intersecting the territory. QA_PIXEL masking (cloud, cloud-shadow, snow, water).
  L5/L7 reflectance harmonized to the OLI domain (Roy et al. 2016); OLI/OLI-2 left
  as-is. No temporal interpolation or spatial gap-filling.
- **MapBiomas Argentina annual mosaic** of the **previous** year (`y−1`) — attached to
  each observation as previous-year context (40 selected bands; see
  [`02-model_fitting.md`](02-model_fitting.md) for which bands and why `y−1`). Export-code
  notes: bands are `.select()`-ed *before* `.mosaic()` (only the 40 are processed); the loop
  variable is `mb_year` (the actual MB data year) with `obs_year = mb_year + 1`, so an
  observation in year `Y` gets the `Y−1` mosaic.
- **Training points**: burned / unburned points collected interactively per fire in the
  GEE Code Editor by domain experts. The collection procedure and the GEE asset layout
  are documented in [`../samples/README.md`](../samples/README.md).

## Step 01 — export (`workflow/01-training_data_export.py`)

Samples the Landsat time-series + the `y−1` MapBiomas mosaic at every training point and
exports **one GEE asset per fire**:
`COLLECTION-1/TRAINING-DATA/{region}/training_observations-fire_NN_v{version}`.

Conventions (the durable ones are also in `CLAUDE.md`):

- One GEE task per fire; task description `training_obs_{region}_{fire_id}_v{version}`
  (region included because `fire_id`s repeat across regions).
- `fire_id` is verbatim and only the `"fire_"` prefix is guaranteed — the body need
  not be numeric or two digits (e.g. `"fire_sde10"`). Build asset tokens with
  `C.fire_token(fire_id)` (`utils/constants.py`); never zero-pad or reconstruct it.
- PAT fires 01–30 fall back to `COLLECTION-0/TRAINING-DATA/` for their training_locations.
- Fires with no burned points (drought/ash negatives, e.g. PAT fire_46/47) export
  unburned-only rather than being skipped.
- Each run writes a JSON sidecar to `workflow/01-training_data_export/run_{region}_v{version}.json`
  (input paths, task ids, versions, parameters) for reproducibility.

## Observation-level burned label

- `burned = 0`: all observations from unburned points, **and** observations from burned
  points in the **pre-fire** window.
- `burned = 1`: observations from burned points in the **post-fire** window
  (`post_lwr → post_upr_long`).
- `post_upr_short` is preserved in `training_fires` for filtering at training time, but is
  **not** used to assign labels.
- `pre_lwr` is often null in assets → computed as `pre_upr` minus one year.

## Download for local fitting

`scripts/download_observations.py --region <R> --version <V>` pulls the completed assets to
`collection-01/data/training_observations_{region}_v{version}.csv` (git-ignored, large).
These pooled CSVs (~5.7M obs across 5 regions) are the input to step 02 and the notebooks.

## Production / reference files

| File | Role |
|---|---|
| `workflow/01-training_data_export.py` | the export step |
| `workflow/01-training_data_export/run_*.json` | per-run logs |
| `scripts/status.py` | check export status across regions |
| `scripts/download_observations.py` | download assets → local CSV |
| `samples/` | archival templates documenting the interactive point collection |
| `data/training_observations_*_v1.csv` | downloaded training set (git-ignored) |

## Related notebooks

- `notebooks/data_collection_stats.qmd` — effort stats (time, authors, points/obs per fire).
