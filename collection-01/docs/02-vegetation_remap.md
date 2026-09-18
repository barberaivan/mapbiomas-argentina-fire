# 02 — Vegetation (fire-class) remap

The MapBiomas Argentina land-cover legend is remapped into a small set of **fire-classes**
(`veg_fire`), built by crossing MapBiomas regions with MapBiomas LULC classes. The result is one
lookup table, `config/veg_fire_remap.csv`, which decides how many burn-probability models get
fit and which observations each one sees. It is a configuration artifact, not a computation —
but it is upstream of everything in step 02.

## Foundations

**A separate logistic regression is fit per `veg_fire` class**, because burn signatures differ by
vegetation: what a burn scar does to the spectral series in closed forest is not what it does in
grassland or open shrubland, and one pooled model would fit the average of surfaces that do not
behave alike.

The class is read from the **previous-year (`y−1`) LULC**, never the focal year. Reading the
focal year would let the fire we are trying to detect decide which model judges it — the land
cover of a burned pixel changes *because* it burned.

**The grouping is not purely ecological — data availability was a hard constraint.** Initially a
remap strictly within regions was considered, but many classes are better off crossing them.
Partly that is spectral and land-use similarity; partly it is that separate models simply could
not be informed, because data collection was organised by region and that did not guarantee
coverage of every class in every region. So a class may span regions
(`agriculture_cuyo-pat` covers CUYO and PAT). **The remap is an open path to improve** — with
more collected fires, groups currently merged for want of data could be split on their own
merits.

## Inputs → Outputs

Google Sheet (`remap_by_region` tab) → **`scripts/veg-fire_remap_clean-google-sheet.R`**
→ `config/veg_fire_remap.csv`

| | What it is | Where |
|---|---|---|
| **in** | the editable authored remap, one row per raw class × region | [Google Sheet](https://docs.google.com/spreadsheets/d/17ZShb8D0JaJw4nLvBDzt19xF6Fdg8lGHYs4Jogh0X1A/edit?gid=1376068841#gid=1376068841), tab `remap_by_region` |
| **out** | the production lookup: `mb_class_raw` × region → `veg_fire` code + name | `config/veg_fire_remap.csv` |
| **out** | what the CSV is, how it was generated, column meanings | `config/veg_fire_remap_metadata.txt` |

The CSV is read by `workflow/02-model_fitting.R` — which takes from it both the list of classes
to fit and the regions each class needs — and by the GEE prediction pipeline, which uses it to
route each pixel to its class's coefficients.

## How it works

The Sheet is the source of truth and the CSV is generated from it, so the CSV is
**language-agnostic and must never be hand-edited** — an edit there is silently lost on the next
regeneration.

Current state, **remap v2 (resolved 2026-06-17)**: 23 fittable `veg_fire` classes out of 25, and
0 unmapped observations. The former unfittable `agriculture_cuyo` (K=2) was merged with
`agriculture_pat` into `agriculture_cuyo-pat` (CUYO+PAT, K=10), which also absorbed the
previously unmapped CUYO class 19.

## Run

```bash
Rscript collection-01/scripts/veg-fire_remap_clean-google-sheet.R
```

Re-run `notebooks/land_cover_remap.qmd` after any remap change.

## Key decisions

- **Low-K classes are accepted as fittable.** A class backed by fewer than 10 fires is fit
  anyway rather than dropped or merged further; the alternative loses a vegetation type from the
  map entirely. The cost is visible downstream — CV folds are capped by the number of fires with
  positives, so those classes fit at K < 10 (see [`02-model_fitting.md`](02-model_fitting.md)).
- **Classes are allowed to span regions.** Region-scoped naming is kept for readability, but the
  fitting unit is the class, so a merged class pools every region it names.

## Gotchas

- Never hand-edit `config/veg_fire_remap.csv`; edit the Sheet and regenerate.
- The count that matters is **distinct `veg_fire` values**, not rows: the CSV has one row per raw
  class × region (74 rows → 25 classes → 23 fittable).

## Files

| File | Role |
|---|---|
| `config/veg_fire_remap.csv` | production lookup; read by the fit and by the GEE prediction pipeline |
| `config/veg_fire_remap_metadata.txt` | what the CSV is, how it was generated, column meanings |
| `scripts/veg-fire_remap_clean-google-sheet.R` | regenerates the CSV from the Sheet |
| [Google Sheet](https://docs.google.com/spreadsheets/d/17ZShb8D0JaJw4nLvBDzt19xF6Fdg8lGHYs4Jogh0X1A/edit?gid=1376068841#gid=1376068841) | upstream editable source |

## Related

- [`02-model_fitting.md`](02-model_fitting.md) — the fit this table configures.
- `notebooks/land_cover_remap.qmd` — validates the CSV against the full observations: raw-class ×
  region areas, obs/burned counts, fires-with-positives, and a per-`veg_fire` summary
  cross-checked against the CV-feasibility table.
