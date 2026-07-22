# 05 — Fire-object vectorization & metrics (R)

Step 05 turns the step-04 burned **pixels** into fire-scar **objects** and attaches the
per-object metrics that the step-06 filter uses to separate real scars from noise. First R
stage of the prediction pipeline; runs **one fire-year at a time**, whole-country, with objects
global within the year (no tiling — nearby fragments of one scar share an id).

Production: `workflow/05-objects_metrics.R` + `utils/label_uf.cpp`. **Read `docs/04-snic.md`
first** — step 05 consumes its SNIC product.

The pipeline was rebuilt to **run whole-country on 31 GB RAM**. The three steps that broke at
9.16 B cells each got replaced; §7 has the FY2000 profile that forced each change, §8 the roads
abandoned. The old dense route survives as a ROI-scale `terra` fallback.

---

## 1. Input — the step-04 SNIC product (two layouts)

`snic_tifs`/`load_snic` read **either** layout, preferring the first:

**A. Direct-download per-carta tiles (preferred; 04 §5b).** `04-snic.py --to-asset` +
`download_snic.py` land **248 per-carta GeoTIFFs** in `collection-01/data/snic-direct/<fy>/`.
**7 bands** — the four below **plus `burned_around_{1,2,3}` pre-computed in GEE** as **cell
counts** (R divides by (2r+1)²). This is the layout that scales: the extract reads one carta at
a time (§2.1).

**B. Legacy Drive COG.** `04-snic.py --to-drive` writes one GeoTIFF per fire-year to
`snic-polygons/`. **4 bands** (no `burned_around`; computed locally). **ROI-scale only** — one
big COG is a single "tile", so it re-hits the whole-mosaic extract limit at country scale.

| band | meaning |
|---|---|
| `candseed` | 1 = candidate, 2 = seed, 3 = Patagonia next-year dieback (04 §4.3) |
| `abs_date` | per-pixel K=2 burn mid-date, **days since 1970-01-01** (int16) |
| `veg_fire` | veg_fire class `MB(Y1−1)`, 1–23 burnable (04 §4) |
| `n` | Landsat observation count of the winning `abs_date` image |

All bands are masked to `burned = candseed > 0`, so files are sparse (tens of MB/yr). terra/GDAL
read the mask via the **NoData tag**; no COG structure is needed (those overviews only help
partial/remote reads — these files are local).

---

## 2. The whole-country algorithm

Four steps, all sized by **burned cells (O(burned))**, never the dense 9.16 B-cell grid.

### 2.1 Extract — per-carta tile (`extract_burned`)

Read **one carta tile at a time** (each < 2³¹ cells), keep the burned cells, map local
`(row,col)` to the **global lattice** via the tile's offset, `rbindlist`. Never calls
`as.data.frame()` on the whole mosaic — that builds `1:ncell` (9.16 B) and R's `cbind` throws
*"long vectors not supported"* (§7). The result is one `data.table` of burned cells carrying all
bands + global `row`/`col`/`cell`.

### 2.2 Label — union-find, with dilation as a wider window (`label_uf` + `utils/label_uf.cpp`)

Objects = connected components of burned cells. **Union-find** (disjoint-set, Tarjan; path
halving) does this with **only an `N`-int parent array** (~0.5 GB at 116 M cells): candidate
edges are streamed one window-offset at a time and discarded — no edge list, no graph object.
The C++ (`utils/label_uf.cpp`) is three tiny primitives (`uf_new` / `uf_union` / `uf_labels`)
and is **labelling-agnostic**; the R caller decides which pairs to union.

**The 1-px dilation without a halo.** A real scar breaks into fragments a pixel or two apart.
The original glued them by *dilating* the mask (a 1-px halo), labelling the grown mask, then
dropping the halo — but materializing that halo (8× the non-ag burned cells) is what OOM'd the
country run (§7). It is **exactly equivalent** — and halo-free — to instead union two burned
cells directly when they fall within a **wider window**, with a veg-class distance threshold.
Working out the geometry (a non-ag/grass burned pixel "occupies" its 3×3 dilation; an ag/grass
one, whose dilation is suppressed, occupies just 1×1; two occupied regions 8-touch at exactly
these distances):

| the two burned cells | union if Chebyshev distance ≤ |
|---|---|
| both **non**-ag/grass | **3** |
| exactly one non-ag/grass | **2** |
| both ag/grass | **1** (plain 8-connectivity) |

So the labeller sweeps a **7×7 forward-offset window** (24 offsets, each undirected pair once)
and, per candidate pair, unions only within that veg-dependent threshold. Ag/grass = veg_fire ∈
**{1, 2, 3, 13, 17}** (`agriculture_*`, `grassland_chaco`, `grassland-inund_chaco`), where
bridging distinct burned fields would inflate commission error. This reproduces the terra
dilate→label→drop-halo result **pixel-for-pixel** (verified: ROI 1998 → 115 objects, sorted
per-object pixel counts identical to the terra path, area rel-diff 0).

### 2.3 Vectorize — parallel per-object (`vectorize_sparse`, Path B)

Per pid: build a **tiny local-bbox raster** holding all of that pid's cells and
`as.polygons(dissolve=TRUE)` → one (multi)polygon. Disconnected fragments of one pid (the
dilation-bridge case) dissolve into a single multipolygon, so the bridge is preserved
**natively**. Objects are independent → `mclapply` across `OBJ_CORES`; workers return
`terra::wrap`ped chunks (fork-serializable), master merges. Never builds the country-wide 34 GB
`pid` raster. (Alternative "Path A" — write `pid` to a disk GeoTIFF + streaming
`gdal_polygonize` — is ~2× slower and needs an extra dissolve-by-pid for the disconnected case;
see §7/§8.)

### 2.4 Metrics — raster + geometry (`aggregate_metrics`, `add_shape_metrics`)

Computed **raster-native** over the burned-cell `data.table`, grouped by pid — faster and exact
for area:

- **veg abundance** — per-class fractions `frac_c1…c23` (absent = 0) + ranked top-5
  (`veg_top1…5` + `_frac`).
- **area** — `area_m2` = Σ per-cell `cellSize` (for a lon/lat grid computed on a 1-column strip
  by latitude, O(nrow)) and `n_pixels`.
- **`abs_date` / `n` summaries** — `{median, mean, p2.5, p97.5, min, max}` (`n_*` skipped if no
  `n` band; a human `date_median_date` is added at write).
- **neighbourhood sparseness** `burned_around_{1,2,3}` — mean over the object's pixels of the
  burned fraction in the (2r+1)² window. Direct tiles carry it pre-computed in GEE (cell counts
  → ÷(2r+1)²); the legacy COG computes it here.

**Geometry shape/sparsity** (ported from collection-00 `addShapeMetrics`): `perimeter_m`,
`convexity` (area/hull), `mbr_fill` (area/bbox), `mbr_elongation`, `circularity` (4πA/P²),
`shape_index` (P/2√πA). Bbox = axis-aligned envelope; on the lon/lat grid its spans are
converted degrees→metres.

---

## 3. Object ids — pid / oid

`pid` = object id, unique **within a year only** (labelling restarts each year). Each polygon
also carries the globally-unique **`oid = "<fire_year>_<pid>"`** (e.g. `2015_4213`), plus
`fire_year`.

---

## 4. Outputs & run

Written to `collection-01/data/snic-polygons/`:

| file | contents |
|---|---|
| `objects_<fy>.gpkg` | one polygon per object + all §2.4 metrics + `fire_year` + `oid` |
| `objects_<fy>_metrics.csv` | the metrics table alone (no geometry) |

```
OBJ_CORES=13 Rscript collection-01/workflow/05-objects_metrics.R 2000   # union-find (default)
Rscript collection-01/workflow/05-objects_metrics.R test 1998           # small-ROI → objects_test_*
Rscript collection-01/workflow/05-objects_metrics.R terra 2000          # dense fallback (ROI only)
```

`OBJ_CORES` (default ~half the cores; 1 = serial) sets the per-object vectorize fan-out.

Downstream **step 06** filters these objects (real scars are compact & seeded — high
`seed`/`candseed` share, `burned_around_*`, `convexity`/`circularity`; noise is sparse &
unseeded), then builds the filtered polygons + the per-pixel month-of-burn raster (dieback
`candseed==3` inherits the parent object's date), followed by the manual ash/drought mask.

---

## 5. Two labelling methods

- **`sparse` (default)** — union-find (`utils/label_uf.cpp`) over burned cells, dilation as a
  wider-window union (§2.2). O(burned); scales to the whole country.
- **`terra`** — the original `terra::patches()` over the dense grid + `as.polygons` on a densified
  `pid`. Identical partition, but O(all cells) and needs a 34 GB `pid` raster at 9 B cells → **ROI
  fallback only**.

---

## 6. Status (2026-07-22)

**Done & validated (ROI 1998, sparse vs terra):** per-tile extract, union-find labelling,
**dilation-as-window** (veg-threshold 3/2/1), parallel per-object vectorize, and all metrics —
**115 objects, sorted per-object pixel counts identical, area rel-diff 0**. All in production.

**Proven at country scale (FY2000 benchmark, `scripts/objects-benchmarks/`):** extract 499 s /
8.4 GB; union-find label 82 s / 8.6 GB (82,025 objects, matches GDAL's CC count); vectorize
Path B 163 s (13 cores) — identical objects to Path A.

**Remaining:** run the **full production script whole-country** (e.g. FY2000) end-to-end to
confirm the one untested-at-scale piece — the **metrics aggregation memory** over 116 M rows
(the benchmark labelled+vectorized but computed no metrics). It is O(burned), so it should fit,
but the direct-tile extract must carry all 7 bands, so `dt` is ~10–15 GB; measure it. If tight,
compute the metrics from the on-disk tiles in a second streaming pass. Step-06 filter cuts are
still open (04 §7).

---

## 7. Whole-country FY2000 profile — what forced the redesign

Running the ROI-tuned pipeline on the whole country (116.1 M burned cells, 9.16 B-cell grid) hit
three walls. Each is now fixed (§2); the numbers live in `scripts/objects-benchmarks/`.

| step | ROI-tuned approach | broke because | fix |
|---|---|---|---|
| extract | `as.data.frame(vrt, cells=TRUE)` | builds `1:ncell` (9.16 B) → *"long vectors not supported"* | **per-carta tile** extract (§2.1) |
| label | `igraph` connected components | edge list + graph object OOM > 31 GB | **union-find**, 82 s / 8.6 GB (§2.2) |
| dilation | materialize the 1-px halo | halo = 8× non-ag burned cells → part of the OOM | **wider-window union**, no halo (§2.2) |
| vectorize | densify `pid` + one `as.polygons` | 34 GB in-RAM int32 grid | **per-object** local rasters (§2.3) |

**Vectorize A vs B (both give identical objects).** *Path A* — write `pid` to a tiled/nodata
GeoTIFF (block-aware: only populated blocks → 48 s vs terra's naïve 522 s) + streaming
`osgeo.gdal.Polygonize` (270 s) + **dissolve-by-pid** (gdal splits a pid's disconnected
fragments into separate same-value features, undoing the dilation bridge, so a `GROUP BY pid`
union is required). *Path B* (§2.3) — 163 s, and native-correct for the dilation case with no
dissolve. **B chosen.** (On "COG": the win was never the cloud-optimized overviews — step 05
reads full-res/full-coverage — but the on-disk out-of-core write + streaming read.)

---

## 8. Roads taken and abandoned

Chronological, so a future reader sees why the current design is what it is:

- **GEE `connectedComponents`** — native scar labelling in GEE. Dead end: `maxSize` caps a
  component at ~1024 px (real scars silently split). Labelling stays local.
- **`terra::patches()` dense labelling** (the original) — correct and simple, but O(all cells)
  and needs a 34 GB int32 `pid` grid at 9 B cells. Kept only as the ROI `terra` fallback.
- **Whole-mosaic `as.data.frame(cells=TRUE)`** — the burned-cell extract. Crashes on the
  `1:ncell` long vector at country scale. Replaced by the per-tile extract.
- **`igraph` sparse labelling** — was the default; ~8.4× faster than terra on the ROI. But the
  explicit edge list (~4/cell) + graph object OOM > 31 GB whole-country. Replaced by union-find,
  which stores only the parent array.
- **Materializing the dilation halo** — the literal dilate→label→drop. The halo (8× the non-ag
  burned cells) is a big transient that fed the OOM. Replaced by the exact wider-window union.
- **In-RAM `pid` densification for `as.polygons`** — `values(pr)<-` on the country grid = 34 GB.
  Replaced by per-object local rasters (Path B), or an out-of-core disk write (Path A).
- **Tiling by carta + seam-merge** — would parallelize and bound RAM, and the input is already
  248 tiles. Rejected: a scar crossing a carta seam splits, and merging forces re-aggregating
  *every* polygon-level metric across the pieces — fiddly and error-prone. The untiled run is
  feasible (~12–16 min/yr), so objects stay global, no seams.
- **Path A (disk `gdal_polygonize`)** — works, but ~2× slower than Path B and needs the extra
  dissolve-by-pid for disconnected same-pid fragments. Kept documented, not used.
- **`cc3d` / `scipy.ndimage` labellers** — C-fast, but both need a **dense in-RAM label array**
  (int32 ≈ 34 GB at 9 B cells) → viable only tiled, and we run untiled. `rasterio.features.shapes`
  is the same GDAL engine as `gdal.Polygonize` but in-memory only. None adopted.
- **Raster-free numpy edge-tracing** (union cell edges, cancel shared, stitch rings) — fastest in
  principle (no per-call overhead, no array), but bespoke ring/hole/multipolygon code with no
  turnkey library. Noted as a future option; not built.
