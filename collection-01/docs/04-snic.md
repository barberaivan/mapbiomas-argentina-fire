# 04 — SNIC spatial segmentation

Step 04 grows the per-pixel burn-probability metrics from step 03 (`bpts`) into **spatial
objects** (fire scars) with SNIC region-growing, so downstream metrics and manual review
operate on segments rather than pixels. **Status: in development** — the Python driver
`workflow/04-snic.py` is still a stub. The design work so far lives in an interactive GEE
exploration tool (below); the productionised Python export will follow the step-03 pattern
(export one asset per *carta*).

See also the downstream design notes in `03-bpts.md §10` (fire-regions as unions of cartas,
no edge buffer needed, watch SNIC's internal ~256-px tile seams).

## Delineating fire-regions (visual, prerequisite)

`snic_regions_definition` — fuego repo, `collection-01/visualization-misc/`. Paints every
pixel that was **ever a seed (red) or candidate (orange) in any year** (`bpts.map(...).max()`),
other pixels masked, with the carta grid drawn as borders-only on top. Used by eye to trace the
fire-region footprints (unions of cartas) that SNIC then runs over. Deliberately no `reproject`
(pan-the-country overview) — unlike `explore_snic_IB`, which pins to 30 m for exact
segmentation on a small ROI. Thresholds here are a starting point; finalise them in
`explore_snic_IB`.

Use case: a **fast, country-wide, deliberately coarse (non-30 m)** look at where fire happened,
so you can scan the whole country and pick candidate **test ROIs** — which then go into
`explore_snic_IB` for the exact 30 m, scale-stable tuning.

## Output is the SNIC *mask*, not `cluster_id`

Downstream we use **only the binary SNIC `burned` mask** (clusters that contain a seed) — the
`cluster_id` label band is never exported or consumed. Two consequences:

- **No label-consistency concern across the export split.** Cluster IDs are only unique within
  one SNIC run; if we exported them, tiling would need care. Since we drop the labels, the
  export tiling below is a pure transport split.
- The exported layer is a sparse binary mask → compresses to almost nothing as a COG.

## Export (operationalisation)

SNIC must see the whole contiguous footprint, so run it over a **region mosaic (union of
cartas), one asset per region + year**:

1. **`toAsset`, per region + year.** No per-dimension cap (only `maxPixels`, raise to ~1e13);
   assets are internally-tiled pyramids, so a region-wide mosaic is fine. This asset also
   materialises the heavy neighborhood computation once.
2. **`toDrive` as tiled Cloud-Optimized GeoTIFFs**, off `ee.Image(region_year_asset)` (fast
   copy, no recompute). **No Cloud Storage bucket needed** — `cloudOptimized: true` *is*
   supported on `toDrive` (contrary to a common belief that COG is CS-only); a COG is
   DEFLATE/LZW-compressed + tiled, so the sparse mask stays tiny, same as the asset. Use
   `fileDimensions` (multiple of 256, e.g. 8192) to control the split and `skipEmptyTiles=True`
   to drop all-masked tiles. The 10k-px file cap applies here (Drive/CS files), **not** to the
   asset.
   - **Tile inside the single `toDrive()` call (via `fileDimensions`), do *not* loop over the
     cartas grid.** SNIC already ran at region level → the asset; `toDrive` is pure transport,
     so transport tiles need not honor the cartas grid (which governs *computation* tiling
     elsewhere). One task per region+year beats hundreds of per-carta tasks, and terra
     reassembles by geolocation regardless of how the split aligns.
3. **Reassemble in R with terra:** `terra::vrt(tiles)` (virtual mosaic, no copy) or
   `merge()`/`mosaic()`. Tiles are exact non-overlapping subsets and carry only the mask, so
   reassembly is a plain stitch — no relabeling.

## Interactive exploration tool (GEE repo)

`explore_snic_IB` — in the **fuego** GEE repo (not this one), at
`collection-01/visualization-misc/explore_snic_IB`. See CLAUDE.md → "GEE Code Editor scripts"
for the repo location and the pull/edit/push workflow.

Purpose: tune the SNIC **seed** and **candidate** thresholds *on the fly* (no export), while
avoiding SNIC's scale-dependence. For a chosen year it: merges the two bpts collections
(Argentina + the mapbiomas-chaco 1999–2009 overflow), filters to the year, mosaics the tiles
over a ROI, **decodes the 7 probability bands to probability scale** (÷10000; the day / DOY /
count bands are left as-is), then thresholds seeds + candidates and runs SNIC.

Key design points:

- **Scale-independence.** SNIC and `connectedPixelCount` are neighborhood ops, so the
  interactive map would otherwise evaluate them at the zoom-pyramid scale (result changes as
  you zoom). The decoded mosaic is `reproject()`-ed to the assets' native 30 m grid **before**
  any neighborhood op, and the SNIC output is reprojected too — pinning the whole computation
  to 30 m at any zoom. (Keep the ROI modest; a 30 m-pinned neighborhood over a whole carta can
  hit interactive memory/timeout limits.)
- **Seeds (strict) vs candidates (loose)**, adapted from the col-0 method
  (`collection-00/misc/snic_visualization` in the GEE repo). Seeds use high magnitude
  (`pmax3`) + change (`delta3_peak`) + persistence (`minfore3_peak`); candidates use the loose
  versions and define the footprint SNIC may grow into. A `connectedPixelCount` filter **drops
  seed components of ≤ P pixels (P = 5)** — so a fire-cluster must be seeded by ≥ 6 connected
  pixels — which removes a lot of speckle noise. `burned` = SNIC clusters that contain a seed.
  All thresholds are tunable variables at the top of the script.
- **Previous-year land cover.** Displays the `y−1` raw MapBiomas classes and the `veg_fire`
  classes (the exact land-cover context step 03 used), with a compact legend of the 25
  `veg_fire` classes.
- **NBR + NBR2 series.** A cheap NBR/NBR2-only Landsat collection (`y−1 … y+1`) added at
  opacity 0 — invisible on the map, but the Inspector charts it as a time series on click.

## Shared helpers added to the GEE utils

To keep the script small, the reusable pieces live in the fuego repo's `collection-01/utils/`:

- `functions.js`: `vegFireImage(year)` / `mbClassImage(year)` — a faithful JS port of Python
  `functions.py:veg_fire_image` (`region_id·100 + mb_class → veg_fire`, prev-year, unmapped →
  25); `vegFireLegend(nCols)` — the compact class legend; `addNBR_NBR2` — NBR/NBR2-only index.
- `constants.js`: the LULC/region asset ids, the canonical `REGION_CLASS_FROM` / `VEG_FIRE_TO`
  remap, `VEG_FIRE_NAMES`, `VEG_FIRE_PALETTE`, `MB_LULC_PALETTE`.

> **Sync caveat.** Those `constants.js` remap arrays are a **hand copy** of this repo's
> `config/veg_fire_remap.csv` (the single source of truth) — there is no automatic sync
> between the two repos. If that CSV is regenerated with class changes, update the fuego
> `constants.js` arrays to match. The coupling is flagged in both places
> (`config/veg_fire_remap_metadata.txt` → "MANUAL DOWNSTREAM COPY" and a SYNC WARNING comment
> in `constants.js`).
