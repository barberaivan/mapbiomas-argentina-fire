# 06 — Inspecting the object calls in QGIS

The whole scored object set can be reviewed on a map **without uploading anything to GEE**:
`scripts/objects_inspect_export.R` joins the step-06 predictions, the step-05 metrics and the
collection-00 verdict onto the geometry already on disk, one GeoPackage per fire-year. It is a
**diagnostic tool, not a pipeline step** — nothing downstream consumes it, and
`data/objects-inspect-cache/` is regenerable from the CSVs at any time. Read
[`06-object_model.md`](06-object_model.md) first; this file only says how to look at its output.

## Inputs → Outputs

step-06 `objects_<fy>_pred.csv` + step-05 metrics + `objects_<fy>.gpkg` →
**`scripts/objects_inspect_export.R`** → `<fy>_objects_pred.gpkg` (+ `inspect_objects.qgz`)

| | What it is | Where |
|---|---|---|
| **out** | one QGIS layer per fire-year, every object of the year, **34 curated fields** | `data/objects-inspect-cache/<fy>_objects_pred.gpkg` |
| **out** | a QGIS project over all 28 layers | `data/objects-inspect-cache/inspect_objects.qgz` |
| **out** | *(`--sample N`)* a decile-stratified GeoJSON for `geemap` | `data/objects-inspect-cache/<fy>_objects_sample.geojson` |

## Run

```bash
collection-01/scripts/run_06_inspect.sh -j 6      # all 28 years, resumable, biggest first
```

~1 min on 6 workers, 6.3 GB, feature counts summing to exactly 1 689 419. Unlike prediction this is
I/O- and memory-bound — a worker holds a whole year's geometry, up to 386 MB / 93 k multipolygons —
hence `-j 6` rather than the 8 used for scoring.

## The field set

The 23 raw `frac_c*` columns are not predictors and 28 years of them is dead weight in a table read
by eye, so the field set is curated and ordered the way a row is read — what it is, what we decided,
why, then the evidence (`--fields all` restores everything for one year):

| group | fields |
|---|---|
| identity & size | `oid`, `fire_year`, `area_ha`, `n_pixels`, `size_class` |
| the verdicts | `fire`, `fire_model`, `fire_tag`, `c00_pass`, `verdict` |
| why the model said it | `p_mean`, `p_width`, `p_thresh`, `p_margin`, `th_band`, `c00_case` |
| burn evidence & timing | `seed_mean`, `burned_around_{1,2,3}`, `doy_median`, `date_span`, `date_median_date` |
| aggregated vegetation | the 5 `frac_*` groups |
| shape | `perimeter_m`, `convexity`, `mbr_fill`, `mbr_elongation`, `circularity`, `shape_index` |

Four fields are not from step 05, and they are why this is a script and not a join.
**`p_thresh` / `p_margin` / `th_band`** carry the cut that applied to *this* object's band and the
signed distance to it — a verdict is unreadable without its threshold when the threshold varies by
size — and `apply_thresholds()` recomputes them and **cross-checks the stored `fire_model`**, so a
thresholds-file edit after a prediction run is reported instead of silently making the map lie.
**`verdict`** is one categorical (`both` / `model only` / `c00 only` / `neither` / `unscored`), so
the model-vs-filter disagreement is a single symbology. `size_class` (6 display classes) is
deliberately finer than `th_band` (4 threshold bands).

`--sample N` also writes a decile-stratified `<fy>_objects_sample.geojson` for `geemap`:
`Map.add_geojson()` puts a local vector on an ipyleaflet map as a **client-side** layer while GEE
imagery renders as server-side tiles beside it, nothing uploaded. Keep it in the low thousands of
features. Default `0`, since QGIS is what actually gets used.

## Where to look first

The model and the collection-00 filter **disagree on 26.6 % of the object area**, cleanly split:
`c00 only` (filter keeps, model rejects) is 83 k *large* objects / 11.1 Mha, `model only` is 977 k
*small* ones / 11.6 Mha ([`notes/06-c00_baseline.md`](notes/06-c00_baseline.md)). **Start with
`"verdict" = 'c00 only' AND "area_ha" >= 300`** — 5872 objects holding 6397 kha, **7.5 % of all
object area**, where the old filter auto-accepts under its ≥300 ha rule and the model rejects
*without confidence* (mean `p_width` 0.46). It is the highest-area-stakes set in the collection and
small enough to walk object by object. By contrast `model only` below 1 ha is 31 933 objects for
22 kha — 0.03 % of area.

| expression | what it shows |
|---|---|
| `"verdict" = 'c00 only' AND "area_ha" >= 300` | **the set to review first** (above) |
| `"verdict" != 'both'` | every disagreement with the collection-00 filter |
| `abs("p_margin") < 0.05` | borderline calls — objects that would flip under a small threshold change |
| `"p_width" > 0.5` | where the model has no idea; also the round-2 collection targets |
| `"fire_tag" >= 0 AND "fire_tag" != "fire_model"` | labels the model disagrees with |
| `"size_class" IN ('<0.5 ha','0.5-1 ha')` | the minimum-size decision |
| `"th_band" = '1-50 ha' AND "fire" = 1` | the weakest band's positives (83 % of all objects) |
| `"seed_mean" < 0.1 AND "fire" = 1` | fire calls with little seed support — the most suspicious positives |

Categorise the fill on `verdict`, add an XYZ satellite basemap, and sort by `p_margin` to walk from
the most borderline call outwards.

## Gotchas

- **The layer name starts with a digit** (`2020_objects_pred`), so any SQL context — DB Manager,
  virtual layers, `ogrinfo -sql` — needs it **double-quoted**. Symbology and attribute-table filters
  are unaffected.
- **`p_thresh` / `p_margin` / `th_band` are recomputed at export time**, not read from the
  prediction CSV, and cross-checked against the stored `fire_model`. Edit
  `config/object_model_thresholds.csv` after a prediction run and the export reports the mismatch
  rather than drawing a map that disagrees with the deployed call.
- **A whole-country raster overview is not an option**: rasterizing `p_mean` at 30 m country-wide is
  9.16 B cells (`05` "Foundations"), so it would have to be coarsened to ~300 m, which erases
  exactly the small objects that are in doubt.

## Files

| File | Role |
|---|---|
| `scripts/objects_inspect_export.R` | build one year's QGIS layer (`--fields all`, `--sample N`) |
| `scripts/run_06_inspect.sh` | all 28 years, parallel, resumable |
| `scripts/objects_data_functions.R` | the shared module — `apply_thresholds()`, the c-00 filter, the readers |

## Related

- [`06-object_model.md`](06-object_model.md) — the model whose calls this displays, the three call
  columns and the per-size-band cuts.
- [`notes/06-c00_baseline.md`](notes/06-c00_baseline.md) — the full model-vs-filter disagreement
  table, and why a Shiny review app was not built.
