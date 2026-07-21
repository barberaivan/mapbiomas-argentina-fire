# 05 — Fire-object vectorization & metrics (R)

Step 05 turns the step-04 burned **pixels** into fire-scar **objects** and attaches the
per-object metrics that the step-06 filter uses to separate real scars from noise. It is the
first R stage of the prediction pipeline; it runs **one fire-year at a time**, whole-country,
with objects global within the year (no tiling — nearby fragments of one scar share an id).

**Read `docs/04-snic.md` first** — step 05 consumes its Drive COG. Production:
`workflow/05-objects_metrics.R`.

---

## 1. Input — the step-04 SNIC product (two layouts)

`load_snic` reads **either** layout, preferring the first:

**A. Direct-download per-carta tiles (preferred; 04 §5b).** `04-snic.py --to-asset` +
`download_snic.py` land **248 per-carta GeoTIFFs** in `collection-01/data/snic-direct/<fy>/`
(bypassing Drive + Insync). `load_snic` `vrt()`s them into one whole-country mosaic **before**
labelling (cross-carta scars rejoin). **7 bands** — the four below **plus `burned_around_{1,2,3}`
pre-computed in GEE** (05 §3). `burned_around_*` are **cell COUNTS** (not fractions); R divides
by (2r+1)².

**B. Legacy Drive COG.** `04-snic.py --to-drive` writes one cloud-optimized GeoTIFF per fire-year
to the `snic-polygons` Drive folder (`C.SNIC_DRIVE_FOLDER`), Insync-synced to
`collection-01/data/snic-polygons/` (a symlink into the store). **4 bands** (no `burned_around`);
R computes the sparseness locally (05 §3).

Bands common to both:

| band | meaning |
|---|---|
| `candseed` | 1 = candidate, 2 = seed, 3 = Patagonia next-year dieback candidate (04 §4.3) |
| `abs_date` | per-pixel K=2 burn mid-date, **whole days since 1970-01-01** (int16) |
| `veg_fire` | veg_fire class `MB(Y1−1)`, 1–23 burnable (04 §4) |
| `n` | Landsat observation count (from `bpts`) of the same winning image as `abs_date` |

All bands are masked to `burned = candseed > 0`, so the file is sparse (tens of MB/yr) even
though the grid is country-wide.

> **No COG needed** (either layout). terra/GDAL read the mask via the **NoData tag** and skip
> empty tiles regardless of the cloud-optimized layout — those overviews only help *partial/remote*
> reads, and these files are **local**. A plain `terra::rast()`/`terra::vrt()` is enough; the direct
> tiles are plain (non-COG) GeoTIFFs by design (04 §5b).

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
  **Two sources** (`load_snic` picks by band presence): the **direct-download tiles carry it
  pre-computed in GEE** (`reduceNeighborhood` sum → per-pixel **cell count**; R ÷ (2r+1)² → the
  fraction, then means per object) — a local focal that GEE does without densifying, so it belongs
  upstream (04 §5b, §7b); the **legacy COG has no such band**, so R computes it sparsely as
  `focal(fun="sum", na.rm=TRUE)/window` (never densifying the grid).

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

### 7b. Faster-than-terra alternatives (to benchmark on the country run)

Researched while waiting for the `snic_2000` whole-country export. Conclusion up front: **the
sparse igraph path is already O(burned) and C-fast — Python won't beat it on the numeric
metrics unless you tile.** The one clean win is **vectorization**: the leftover dense step
(§8.3, the `pid`-raster → `as.polygons`) is where a disk-streaming GDAL polygonizer beats terra.
Map each candidate to the §8 bottleneck it addresses:

| §8 bottleneck | Candidate | Notes |
|---|---|---|
| **3 — `pid`-raster → `as.polygons`** (densifies the full grid in R) | **`gdal_polygonize` on a disk-backed pid COG** | Write the sparse `pid` to a temp COG, then `gdal_polygonize -8` **streams from disk** (no full grid in RAM) — the concrete form of the "disk-backed block write" §8.3 anticipates. `rasterio.features.shapes` is the *same GDAL engine but in-memory only* (rasterio #630), so use `osgeo.gdal.Polygonize` / the CLI for the larger-than-memory read. terra's `as.polygons` is GDAL too, but needs the dense R grid built first. **Highest-value change; keeps everything else in R.** |
| **2 — igraph edge-list memory** (~4 edges × burned cells) | **`cc3d`** (seung-lab/connected-components-3d) | C++ two-pass **union-find, no stored edge list** — exactly the fallback §8.2 names. `cc3d.statistics()` gives per-label voxel counts / bboxes / centroids for free (→ area, bbox metrics). ~2.6× faster than `scipy.ndimage.label` on binary, one-shot multilabel. **Caveat: needs a dense in-RAM array** (uint8 mask ≈3 GB at 3 B cells; int32 labels ≈12 GB) → a *tiled* option, not free. The index-based igraph is actually **more memory-frugal** (never densifies), so only reach for `cc3d` if igraph memory is the measured wall. |
| **1 — burned-cell extract** (`as.data.frame`, O(all-cells)) | **`scipy.ndimage.sum_labels` / `mean` / `find_objects`** on the label array | Per-object area / date / `n` summaries straight from labels, no dataframe. Dense-array bound → tile it. First just measure whether the **sparse NoData COG** already lets terra skip empty tiles on read (§8.1) — that may make this moot. |

**How Brazil gets "~20 min/whole-country-year":** their `mapbiomas/brazil-fire` post-processing
(`mapbiomas_fire_collections/collection_0{4,5}`, ~74 % Python) builds the "fire scar size range"
sub-product; the fast local route is **`gdal_polygonize`** (C, one streaming pass that labels +
vectorizes contiguous same-value pixels — `-8` for 8-conn) reading the annual burned raster from
disk. It can't reproduce our **1-px dilation + ag/grassland suppression** hack (§2) — that shapes
the *partition* before labelling — so we keep the sparse label build in R and swap only the final
vectorize to disk-streaming GDAL.

**Ruled out — GEE `connectedComponents`.** Native GEE scar labelling is a dead end: `maxSize`
caps a connected component at ~1024 px, absurdly small for real fire scars (they silently split).
So labelling can't move to GEE; it stays local (R/Python).

**Benchmark plan when `snic_2000` lands** — cheap A/B, no rewrite:
1. Run the current sparse path; record time + peak RAM for the three §8 steps.
2. Step 3 only: write `pid` to a temp COG, `gdal_polygonize -8` it, compare wall-time + peak RAM
   vs `as.polygons`.
3. Only if the burned-cell extract or igraph memory is the measured wall, prototype the tiled
   `cc3d` / `scipy.ndimage` route — otherwise skip it.

### 7c. Whole-country, untiled — [DECIDED]

Tiling by carta was considered — it would parallelize the label/extract across cores and cut
per-tile RAM to MBs (each carta ~20 M cells), and the production input is **already 248 per-carta
tiles** (`snic-direct/<fy>/`, 04 §5b). **Rejected**, for one decisive reason: a scar straddling a
carta boundary splits into two objects, so tiling needs a **seam-merge** — and merging isn't just
geometry, it forces **re-aggregating every polygon-level metric** (area, veg fractions, date/`n`
summaries, `burned_around`, the shape/sparsity metrics) across the joined pieces. That
re-aggregation is fiddly and error-prone, and the payoff isn't needed: the **whole-country untiled
run is feasible within ~1 h/year**, which is acceptable. So step 05 stays **one raster per
fire-year**, objects global, no seams (§1).

To keep the untiled run feasible **without** the 34 GB `pid` densification (§8.3, the real
whole-country blocker at 9 B cells):

- **Label** with the sparse igraph over burned cells — O(burned), never the dense grid (§3b).
- **Build the `pid` raster on DISK, out-of-core** (block write / rasterize the sparse burned cells) —
  *not* the in-RAM `values(pr) <- NA` fill, which needs 34 GB at 9 B cells.
- **Vectorize** by streaming `gdal_polygonize` over that disk `pid`: **bounded RAM** (the benchmark
  polygonized the whole `snic_2000` at ~2.8 GB in ~3.5 min), no tiling, no seam-merge.

So the memory ceiling is set by the sparse label + the out-of-core `pid` write, not by any dense
grid — and the whole thing runs untiled. (Head-to-head timing/memory — legacy terra `as.polygons`
vs streaming `gdal_polygonize` on the whole `snic_2000` — in `docs/04 §5c`.)

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
