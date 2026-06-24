# 02 — Vegetation (fire-class) remap

The burn-probability model is fit **per region × vegetation type**, so the MapBiomas
Argentina land-cover legend is remapped into a small set of per-region **fire-classes**
(`veg_fire`). This note covers the remap and the files that carry it into production; the
area/feasibility analysis lives in the notebook.

## Why

- A separate logistic regression is fit for each `veg_fire` class — burn signatures differ
  by vegetation (forest vs grassland vs shrubland …) and by region.
- The class is read from the **previous-year** (`y−1`) LULC, never the focal year, to avoid
  contamination by the very fire we want to detect.
- Classes are region-scoped but a class may span regions (e.g. `agriculture_cuyo-pat`
  covers CUYO+PAT).

## Source of truth and production lookup

The remap is authored in a **Google Sheet** (the `remap_by_region` tab) and regenerated into
a language-agnostic CSV — **never hand-edit the CSV**:

```bash
Rscript collection-01/scripts/veg-fire_remap_clean-google-sheet.R
```

| File | Role |
|---|---|
| `config/veg_fire_remap.csv` | **production lookup**: `mb_class_raw` × region → `veg_fire` code + name. Read by `workflow/02-model_fitting.R` and the GEE prediction pipeline. |
| `config/veg_fire_remap_metadata.txt` | what the CSV is, how it was generated, column meanings |
| `scripts/veg-fire_remap_clean-google-sheet.R` | regenerates the CSV from the Sheet |
| [Google Sheet](https://docs.google.com/spreadsheets/d/17ZShb8D0JaJw4nLvBDzt19xF6Fdg8lGHYs4Jogh0X1A/edit?gid=1376068841#gid=1376068841) | upstream editable source |

## Current state

**Remap v2 (resolved 2026-06-17):** 23 fittable `veg_fire` classes, 0 unmapped observations.
The former unfittable `agriculture_cuyo` (K=2) was merged with `agriculture_pat` into
**`agriculture_cuyo-pat`** (CUYO+PAT, K=10), which also absorbed the previously-unmapped CUYO
class 19. Low-K (<10 fires) classes are accepted as fittable.

## Related notebook

- `notebooks/land_cover_remap.qmd` — validates `config/veg_fire_remap.csv` against the full
  observations: raw-class × region areas, obs/burned counts, fires-with-positives, and a
  per-`veg_fire` summary cross-checked against the CV-feasibility table. Run it after any
  remap change.
