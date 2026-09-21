# 01 — Training data

How the labelled training set for the burn-probability model is built: expert-collected points
are sampled against the Landsat time series and the previous year's MapBiomas mosaic, exported
as one GEE asset per fire, and downloaded as pooled CSVs for the local fit in step 02. Each row
is one **observation** — a point on a date — carrying its spectral values and a burned label.

## Foundations

**The unit of judgement here is the observation, not the year.** The model asks, for a single
pixel on a single date, how likely it is that this pixel is burned — using spectral information
only. Every usable Landsat observation is evaluated, so a fire is detected as a *change in the
series* rather than as a signature in a summary image. The approach follows Long et al. (2019),
where all Landsat observations are scored.

This is the opposite end from MapBiomas Fire Brazil, which classifies an **annual mosaic** — the
same way land cover is mapped everywhere in the network. Classifying a mosaic is cheaper and
reuses the land-cover machinery, but it collapses the time axis exactly where the information
is: the date of the burn, the pre-fire baseline of that specific pixel, and the distinction
between a scar and a spectrally similar surface that was always dark. Keeping the observation as
the unit is what makes the time-series metrics of step 03 possible at all.

The consequence for training data is direct: a training **point** is not a label. The label is
per observation, assigned from where that observation's date falls relative to the fire.

## Inputs → Outputs

Landsat C2 SR + MapBiomas mosaic (`y−1`) + expert-collected points
→ **`workflow/01-training_data_export.py`** → one GEE asset per fire
→ **`scripts/download_observations.py`** → one pooled CSV per region

| | What it is | Where |
|---|---|---|
| **in** | Landsat C2 SR (L5 TM, L7 ETM+, L8 OLI, L9 OLI-2), 1999–2025, all scenes intersecting the territory | GEE |
| **in** | MapBiomas Argentina annual mosaic of the **previous** year, 40 selected bands | GEE (`C.MAPBIOMAS_MOSAIC`) |
| **in** | burned / unburned points collected interactively per fire by domain experts | GEE assets — collection procedure and layout in [`../samples/README.md`](../samples/README.md) |
| **out** | observations, one asset per fire | `COLLECTION-1/TRAINING-DATA/{region}/training_observations-fire_NN_v{version}` |
| **out** | per-run reproducibility log | `workflow/01-training_data_export/run_{region}_v{version}.json` |
| **out** | pooled observations for the local fit (6,177,098 obs over 5 regions, of which 5,923,062 pass the step-02 `fit` gate; git-ignored) | `data/training_observations_{region}_v{version}.csv` |

Landsat is QA_PIXEL-masked (cloud, cloud shadow, snow, water); L5/L7 reflectance is harmonized
to the OLI domain (Roy et al. 2016) and OLI/OLI-2 left as-is. There is **no temporal
interpolation and no spatial gap-filling** — a missing observation stays missing, which is what
lets step 03 read real dates.

## How it works

The export samples the Landsat series and the `y−1` mosaic at every training point and writes
one GEE task per fire, described `training_obs_{region}_{fire_id}_v{version}` — region included
because `fire_id`s repeat across regions.

The previous-year mosaic is attached as context to every observation; [`02-model_fitting.md`](02-model_fitting.md)
covers which 40 bands and why `y−1`. In the export code the bands are `.select()`-ed *before*
`.mosaic()`, so only the 40 are ever processed, and the loop variable is `mb_year` (the actual
MapBiomas data year) with `obs_year = mb_year + 1` — an observation in year `Y` gets the `Y−1`
mosaic.

### The observation-level burned label

- `burned = 0` — every observation from an unburned point, **and** observations from burned
  points in the **pre-fire** window.
- `burned = 1` — observations from burned points in the **post-fire** window
  (`post_lwr → post_upr_long`).
- `post_upr_short` is preserved in `training_fires` for filtering at training time but is **not**
  used to assign labels.
- `pre_lwr` is often null in the assets, and is computed as `pre_upr` minus one year.

These windows are the collectors' judgement about when each fire happened, which is why they are
revisited — and sometimes overridden per fire — by the `fit` gate in
[`02-data_cleaning.md`](02-data_cleaning.md).

## Run

```bash
$PYTHON collection-01/workflow/01-training_data_export.py --region <R> --version <V>
$PYTHON collection-01/scripts/status.py                       # export status across regions
$PYTHON collection-01/scripts/download_observations.py --region <R> --version <V>
```

## Key decisions

- **`fire_id` is a verbatim string.** Only the `"fire_"` prefix is guaranteed — the body need not
  be numeric or two digits (`"fire_sde10"` sits beside `"fire_07"`). Build asset tokens with
  `C.fire_token(fire_id)` and never zero-pad, parse a numeric part, or reconstruct it.
- **Fires with no burned points are exported unburned-only, not skipped.** The drought and ash
  negatives (e.g. PAT `fire_46`, `fire_47`) exist precisely to teach the model what a false
  positive looks like; dropping them would remove the hardest negatives from training.
- **Every run writes a JSON sidecar** with input paths, task ids, versions and parameters, so a
  set of assets can be traced back to the run that made it.

## Gotchas

- PAT fires 01–30 fall back to `COLLECTION-0/TRAINING-DATA/` for their `training_locations`.
- Bare `fire_id`s repeat across regions — key fires region-uniquely
  (`region_fire_id = paste(region, fire_id)`) in any analysis.
- The pooled CSVs are large and git-ignored; they are downloaded, never committed.

## Files

| File | Role |
|---|---|
| `workflow/01-training_data_export.py` | the export step |
| `workflow/01-training_data_export/run_*.json` | per-run logs |
| `scripts/status.py` | check export status across regions |
| `scripts/download_observations.py` | download assets → local CSV |
| `samples/` | archival templates documenting the interactive point collection |
| `data/training_observations_*_v1.csv` | downloaded training set (git-ignored) |

## Related

- [`../samples/README.md`](../samples/README.md) — how the points were collected.
- [`02-data_cleaning.md`](02-data_cleaning.md) — the `fit` gate applied to these observations.
- `notebooks/data_collection_stats.qmd` — collection effort (time, authors, points/obs per fire).
