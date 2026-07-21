# 05 — Fire-object vectorization & metrics (R)

Step 05 turns the step-04 burned **pixels** into fire-scar **objects** and attaches the
per-object metrics that the step-06 filter uses to separate real scars from noise. It is the
first R stage of the prediction pipeline; it runs **one fire-year at a time**, whole-country,
with objects global within the year (no tiling — nearby fragments of one scar share an id).

**Read `docs/04-snic.md` first** — step 05 consumes its Drive COG. Production:
`workflow/05-objects_metrics.R`.

---

## 1. Input — the step-04 Drive COG

`04-snic.py --to-drive` writes one cloud-optimized GeoTIFF per fire-year to the
`snic-polygons` Drive folder (`C.SNIC_DRIVE_FOLDER`), which Insync syncs to
`collection-01/data/snic-polygons/` (a symlink into the store). Bands:

| band | meaning |
|---|---|
| `candseed` | 1 = candidate, 2 = seed, 3 = Patagonia next-year dieback candidate (04 §4.3) |
| `abs_date` | per-pixel K=2 burn mid-date, **whole days since 1970-01-01** (int16) |
| `veg_fire` | veg_fire class `MB(Y1−1)`, 1–23 burnable (04 §4) |
| `n` | Landsat observation count (from `bpts`) of the same winning image as `abs_date` |

All bands are masked to `burned = candseed > 0`, so the file is sparse (tens of MB/yr) even
though the grid is country-wide.

> **COG usage:** nothing special is needed. terra/GDAL read a COG transparently; the
> cloud-optimized layout (internal tiling + overviews) only helps *partial/remote* reads, and
> these files are **local**. A plain `terra::rast()` (or `terra::vrt()` when GEE auto-splits a
> big export into sub-tifs) is enough — no `vsicurl` / GDAL COG options.

---

## 2. Object ids — the 1-px dilation connectivity hack (`[2]`)

A real scar often breaks into pixel fragments a pixel or two apart (unburned gaps, threshold
noise). Plain `terra::patches()` on `burned` would call each fragment its own object. To knit
them back together:

1. **Dilate** the burned mask by one **8-neighbour** ring (3×3 square kernel).
2. **Suppress dilation out of agriculture/grassland** — veg_fire ∈ **{1, 2, 3, 13, 17}**
   (`agriculture_chaco/cuyo-pat/pampa`, `grassland_chaco`, `grassland-inund_chaco`). There
   burned fields sit close together and bridging distinct fields inflates **commission error**,
   so those pixels never grow outward.
3. Run `terra::patches(directions = 8)` on the **grown** mask → fragments now ≤1 px apart land
   in one connected component and share an id.
4. **Drop the halo**: keep ids **only on the original burned pixels** (`mask()` back to
   `burned`). The dilation was pure connectivity glue — two fragments bridged by the halo keep
   the shared id even though the bridge pixels are removed.

**The suppression is decided at the halo pixel, by its neighbours.** A halo pixel is masked when
its **only** burned neighbours are the avoided ag/grassland classes, and kept when it has at
least one burned neighbour **outside** the avoided set. (This needs no veg reading on the
unburned halo target — only on the burned neighbours, which the COG carries. It is exactly
equivalent to "grow only the non-avoided burned pixels", the same result pixel-for-pixel.)

To keep the country-wide grid out of RAM, the dilation never densifies: `focal(fun="max",
na.rm=TRUE)` over the 1/NA masks returns 1 in the halo and NA far away.

---

## 3. Per-object raster metrics (`[3]`)

Computed **raster-native**, extracting only the burned cells into a `data.table`
(`terra::as.data.frame(..., na.rm = TRUE)` drops the empty grid) and aggregating by object id.
Doing the numeric work here — not on polygons — is both faster and exact for area.

- **veg_fire abundance** — per-class **fractions** for all 23 burnable classes
  (`frac_c1 … frac_c23`, absent classes = 0) **and** the ranked **top-5**
  (`veg_top1…5` codes + `veg_top1_frac…5_frac`).
- **area** — `area_m2` = Σ per-cell area from `terra::cellSize(unit="m")` (CRS-correct;
  the canonical area, reused by the §6 shape ratios' *reported* value) and `n_pixels`.
- **`abs_date` summaries** — `date_{median, mean, p2.5, p97.5, min, max}` (days since epoch;
  a human `date_median_date` is added at write time).
- **`n` summaries** — `n_{median, mean, p2.5, p97.5, min, max}` (skipped with a warning if the
  `n` band is absent, e.g. a COG exported before `n` was added — 04 §5).
- **neighbourhood sparseness** — `burned_around_{1,2,3}` = mean, over the object's pixels, of
  the burned fraction in the (2r+1)² window (r = 1,2,3 px). A solid scar → near 1; speckly
  noise → low. Ported from collection-00 (fuego `07-objects_metrics` `burned_around_*`).
  Computed sparsely as `focal(fun="sum", na.rm=TRUE)/window` so it never densifies the grid.

---

## 4. Vectorize + join (`[4] [5]`)

`terra::as.polygons(pid, dissolve = TRUE)` yields **one (multi)polygon per object id** — the
dissolve *is* the per-id merge (no manual per-id loop needed). The §3 metrics table is then
joined on `pid` as polygon attributes.

`patches()` restarts numbering at 1 every year, so the within-year `pid` **collides across
fire-years**. Each polygon therefore also carries a globally-unique **`oid = "<fire_year>_<pid>"`**
(e.g. `2015_4213`); `pid` and `fire_year` are kept too.

---

## 5. Geometry shape / sparsity metrics (`[6]`)

Ported verbatim from collection-00 `addShapeMetrics` (fuego
`collection-00/utils/functions.js`). Area denominators use the **geometry** area
(self-consistent with the geometry-derived perimeter/hull/bbox); the **reported `area_m2`
stays the raster pixel area** from §3.

| metric | definition |
|---|---|
| `perimeter_m` | polygon perimeter |
| `convexity` | area / convex-hull area (compactness; ↓ = sparse/ragged) |
| `mbr_fill` | area / axis-aligned bounding-box area |
| `mbr_elongation` | bbox long side / short side |
| `circularity` | 4π·area / perimeter² (1 = disk) |
| `shape_index` | perimeter / (2√(π·area)) (1 = disk; ↑ = complex boundary) |

The bounding box is the **axis-aligned envelope** (matching EE `geom.bounds()`), computed
vectorized from the vertex table (`terra::geom()`), not a per-feature loop.

---

## 6. Outputs

Written to `collection-01/data/snic-polygons/`:

| file | contents |
|---|---|
| `objects_<fire_year>.gpkg` | one polygon per object + all §3/§5 metrics + `fire_year` |
| `objects_<fire_year>_metrics.csv` | the metrics table alone (no geometry) |

Run from the repo root:

```
Rscript collection-01/workflow/05-objects_metrics.R [fire_year ...]   # default: all present
Rscript collection-01/workflow/05-objects_metrics.R test 1998 1999    # small-ROI snic_test_* → objects_test_*
Rscript collection-01/workflow/05-objects_metrics.R terra 2000        # dense fallback (see §7)
```

**Two labelling methods** (same result; `pid` numbers may differ, the *partition* is identical):
- **`sparse` (default, needs `igraph`)** — the object ids come from a connected-components
  labelling that runs over the **burned cell indices only** (`§2`/§7). O(burned), not O(all
  cells).
- **`terra`** — the original `terra::patches()` over the dense grid, kept as a fallback.

Downstream: **step 06** filters these objects (`docs/06` when written) — real scars are
compact and seeded throughout (`seed`/`candseed` share + high `burned_around_*` + high
`convexity`/`circularity`); noise is sparse and unseeded. The final deliverables (filtered
polygons + the mandatory per-pixel **month-of-burn** raster, where `candseed==3` dieback pixels
inherit the parent object's date) are built there, followed by the manual ash/drought masking
pass.

---

## 7. Performance & open questions

- **Why the `sparse` default exists.** Profiling the `terra` path on the ROI (52 M cells, ~528 k
  burned) showed the cost is dominated by full-grid ops — `patches()` (~51 s) and the dense
  `focal`/`as.data.frame` extraction (~55 s) — while `as.polygons()` was cheap (~3 s). All of it
  scales with **total cells**, so the country (~3 B cells) would be ~2 h/year. The `sparse` path
  replaces `patches()` + dense extraction with an index-based connected-components + aggregation
  over **burned cells only** (O(burned)); the one remaining dense step is building the `pid`
  raster for `as.polygons()`.
- **`sparse` scaling risk to watch.** `igraph` labelling is C-fast, but the R-side edge list
  (~4 edges × burned cells) and the graph object are the memory cost at country scale; if it's
  too heavy, swap the labelling for a union-find (same 4-neighbour logic, no stored edges) via
  Rcpp or the C++ CA. Measure on a real full-country year before committing.
- **Shape/sparseness feature set & cuts** for the step-06 filter are still open (04 §7).

---

## 8. Status & handoff (WIP — 2026-07-21)

Active refactor: make step 05 scale from the ROI to the whole country. Where things stand,
so another session can pick up:

**Done & verified (on the 1998/1999 ROI):**
- **Sparse `igraph` labelling is the DEFAULT** (§3b): connected components over burned CELL
  INDICES, replacing `terra::patches()` over the dense grid. Verified **identical partition** to
  the terra path (115 objects, identical sorted sizes, **0.000000 % area diff**) and **~8.4×
  faster** overall on the 52 M-cell ROI — the labelling alone dropped **70 s → 1.7 s**. The terra
  path stays as the `terra` fallback.
  - On 8-connectivity: the graph is fully 8-connected; edges are emitted in only the 4 "forward"
    directions (E, S, SE, SW) per cell so each **undirected** edge is listed **once**, not twice —
    hence "≈4 unique edges per burned cell", not a connectivity reduction.
- **`04-snic.py --to-drive` writes sparse NoData COGs** (`skipEmptyTiles=True`,
  `formatOptions.noData=0`): masked background → NA, burned pixels preserved. Runs under the
  **comahue** account / `mapbiomas-argentina` (see CLAUDE.md → GEE accounts). Older dense-0 COGs
  still work — the burned mask uses `ifel(candseed>0,…)`.

**PENDING — whole-country profile (the real test).** The ROI is only 52 M cells; the country is
**~3 B**. A full-country `snic_2000` drive export is running (GEE task `5FR3V6…`) and **a monitor
is watching for `collection-01/data/snic-polygons/snic_2000.tif`**; when it lands + Insync-syncs,
the monitor runs the whole-country profile:

```
Rscript collection-01/workflow/05-objects_metrics.R 2000        # sparse (default)
# terra path may OOM / take hours at 3 B cells — run only deliberately
```

Watch these three, in expected order of cost at country scale:
1. **burned-cell extract** (`as.data.frame`, the one O(all-cells) step left) — the sparse NoData
   COG should let terra skip empty tiles on read; measure the real speedup.
2. **`igraph` edge list + graph** memory (~4 edges × burned cells). If too heavy → union-find
   (no stored edges) via Rcpp or the C++ CA labeller.
3. **`pid`-raster build** (`values<-NA` densifies the full grid) — remaining dense step; use
   `trim()` to the burned bbox and/or a disk-backed block write.

**Open op gotcha — duplicate Drive files.** GEE `toDrive` does NOT overwrite: a re-export lands
as `snic_<y> (2).tif` (Insync), which `load_snic`'s glob would `vrt()` together. Clear the Drive
folder before re-exporting a year, and/or make `load_snic` pick the newest. **[TODO]**
