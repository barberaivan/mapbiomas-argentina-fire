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

## 2. Object ids = pid — the 1-px dilation connectivity hack (`[2]`)

pid = polygon id.

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
  scales with **total cells**, so the country (**9.16 B cells**, measured) would be hours/year. The
  `sparse` path replaces `patches()` + dense extraction with an index-based connected-components +
  aggregation over **burned cells only** (O(burned)); the remaining non-sparse steps (the whole-grid
  extract and the `pid` densification) are exactly what break at country scale — see §7/§8.
- **[CONFIRMED on FY2000] the whole-country wall is LABELLING memory, not vectorization.** A full
  FY2000 profile (116.1 M burned cells, 9.16 B-cell grid, 82,025 objects) settled the open risks:
  - **`terra::as.data.frame(vrt, cells = TRUE)` crashes at country scale** — it builds `1:ncell`
    (9.16 B) and R's `cbind` throws *"long vectors not supported"*. So the burned-cell extract must
    run **per-carta tile** (each < 2³¹ cells) and map local→global row/col. `objects_sparse` (which
    calls `as.data.frame(r, cells=TRUE)` on the whole mosaic) needs this fix before it can run 2000.
  - **`igraph` labelling OOM-killed at > 31 GB** — the R-side edge list + graph object (plus the
    dilation halo's 8× materialization) don't fit. **A small Rcpp UNION-FIND — parent array only,
    no stored edges, no graph, unions streamed one offset at a time — replaces it: 8.6 GB, 82 s**
    for the whole country (`n_pids = 82,025`, matching gdal's independent CC count). This is the
    key change; igraph does not scale here. (The union-find still needs extending to absorb the
    dilation halo without materializing it — the remaining production to-do, §8.)
- **Shape/sparseness feature set & cuts** for the step-06 filter are still open (04 §7).

### 7b. Vectorization — the three options, benchmarked on FY2000

Label build and vectorize both start from the same `cell→pid` table. Once labelling is fixed
(§7, union-find), vectorizing the whole FY2000 country grid (82,025 objects) was measured
head-to-head — **A and B produced identical objects** (82,025 each; total-area rel-diff 3.7e-14;
per-pid area max rel-diff 7.8e-11):

| Path | how | wall time | peak RAM | notes |
|---|---|---|---|---|
| **A — disk `pid` raster + `gdal_polygonize`** | write `pid` to a tiled/nodata GeoTIFF **block-aware** (touch only populated 512² blocks), `osgeo.gdal.Polygonize -8`, then **dissolve-by-pid** | **337 s** (write 48 + polygonize 270 + dissolve 20) | ~8.5 GB | simplest code — one polygonize call. |
| **B — per-object loop, parallel** | per pid: tiny local-bbox raster → `as.polygons(dissolve)`; N workers write GPKG shards; merge | **163 s** (13 cores) | ~4 GB | ~2× faster; **native-correct** for the dilation case (below). |
| **C — raster-free edge tracing** (future) | numpy boundary-edge cancellation: 4 unit edges/cell, cancel shared, stitch rings per pid — **no array anywhere**, O(burned) | not built | tiny | fastest in principle (no per-call overhead, no grid); **bespoke code** (ring/hole/multipolygon assembly), no turnkey library does "sparse labelled cells → dissolved polygons". |

**"COG" is a misnomer here.** The disk route's win is **not** the cloud-optimized overviews (those
help only partial/zoomed reads; step 05 reads full-res, full-coverage). It is: (a) the `pid` grid
lives **on disk, written out-of-core**, never the 34 GB in-RAM `values(pr)<-` fill; and (b)
`gdal_polygonize` **streams** it scanline-by-scanline, flushing polygons straight to the GPKG →
bounded RAM. A plain tiled + nodata GeoTIFF suffices. The **block-aware** writer (populated blocks
only) makes the write cheap — **48 s vs terra's naïve full-grid 522 s**; polygonize (270 s) then
dominates A.

**gdal splits disconnected same-pid cells → Path A needs a dissolve.** `gdal.Polygonize` emits one
polygon per *connected* run of equal value; `-8` merges diagonal touches, but cells that share a
pid yet are **physically disconnected** — the dilation-hack case (§2: fragments bridged by a 1-px
halo that is then dropped) — come out as **separate features with the same pid value**. So Path A
must **group-by-pid + union** afterwards (`terra::aggregate(by="pid")`, or `ST_Union … GROUP BY
pid`) to match `terra::as.polygons(dissolve=TRUE)`. **Path B has no such issue**: it burns all of a
pid's cells into one local raster and dissolves there → one multipolygon per pid natively. (The
FY2000 benchmark ran plain 8-conn labelling, so `raw = dissolved = 82,025` and the split didn't
fire; it **will** fire under the production dilation partition.)

**How Brazil gets "~20 min/whole-country-year":** their `mapbiomas/brazil-fire` post-processing
(~74 % Python) builds the "fire scar size range" sub-product via **`gdal_polygonize`** (C, one
streaming pass). It can't reproduce our **1-px dilation + ag/grassland suppression** hack (§2) —
that shapes the *partition* before labelling — so labelling stays local (now union-find) and only
the vectorize is the A/B choice above.

**Ruled out.** *GEE `connectedComponents`* — `maxSize` caps a component at ~1024 px (real scars
silently split); labelling can't move to GEE. *`cc3d` / `scipy.ndimage`* — both need a **dense
in-RAM label array** (int32 labels ≈ 34 GB at 9 B cells) → viable only *tiled*, and we run untiled
(§7c); the sparse union-find never densifies, so neither is needed. *`rasterio.features.shapes`* is
the same GDAL engine as `gdal.Polygonize` but **in-memory only** (rasterio #630) — no advantage
over the streaming `osgeo.gdal.Polygonize` used in Path A.

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

The untiled run is feasible on 31 GB — **[CONFIRMED on FY2000]** — with these three changes to the
current sparse path (each replaces a step that breaks or OOMs at 9 B cells):

1. **Extract per-carta tile**, not `as.data.frame` on the whole mosaic (which crashes on the
   `1:ncell` long vector) → global row/col. ~8 min (cache it), ~8 GB.
2. **Label with union-find** (Rcpp parent array, unions streamed one forward-offset at a time), not
   igraph (which OOMs > 31 GB) → **82 s, 8.6 GB**, `n_pids = 82,025`.
3. **Vectorize** via Path A (out-of-core `pid` write + streaming `gdal_polygonize` + dissolve-by-pid)
   **or** Path B (per-object parallel loop), §7b — **337 s / 163 s**, both ~4–8 GB, both producing
   identical objects.

End-to-end FY2000 (extract → label → vectorize) is ~12–16 min, well inside the ~1 h/year budget,
untiled, no seam-merge. The memory ceiling is the tiled extract + the union-find parent array —
never a dense 9 B-cell grid. **Still to do for production faithfulness:** extend the union-find to
absorb the 1-px dilation halo (§2) without materializing it (the halo's 8× blow-up is what OOM'd
the original `label_sparse` — §8).

---

## 8. Status & handoff (WIP — 2026-07-22)

Active refactor: make step 05 scale from the ROI to the whole country. Where things stand,
so another session can pick up:

**Done & verified (on the 1998/1999 ROI):**
- **Sparse `igraph` labelling is the current DEFAULT** (§3b) — but **ROI-scale only: it OOMs at
  country scale** (§7, §8 below); union-find replaces it. Connected components over burned CELL
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

**[DONE 2026-07-22] whole-country FY2000 profile (the real test).** Ran the full pipeline on the
FY2000 `snic-direct` tiles (116.1 M burned cells, 9.16 B-cell grid, 82,025 objects). Three findings,
each with a production TODO (detail in §7 / §7b):

1. **`terra::as.data.frame(vrt, cells=TRUE)` crashes** at 9 B cells (`1:ncell` long vector).
   **[TODO: extract per-carta tile → global row/col in `objects_sparse`.]**
2. **`igraph` labelling OOM-killed > 31 GB** (edge list + graph + the dilation halo's 8×). Replaced
   with an **Rcpp union-find** (parent array only, no edges/graph, unions streamed one offset at a
   time): **82 s, 8.6 GB**, `n_pids = 82,025` (matches gdal's independent CC count).
   **[TODO: make union-find the default `label_sparse`, and extend it to carry the 1-px dilation
   halo without materializing it.]**
3. **Vectorization was never the wall.** Path A (disk `pid` + `gdal_polygonize` + dissolve) = 337 s;
   Path B (per-object, 13 cores) = 163 s; **identical objects**. Choose B for speed / native dilation
   correctness, or A for simpler code (§7b). **[TODO: wire the chosen path into `vectorize_join`,
   replacing the in-RAM `values(pr)<-` fill + `as.polygons`.]**

Bench scripts (extract, `stage0_label_uf.R`, `stageA.py`, `stageB.R`, `compare.R`) are in the
session scratchpad `full2000/`; move into `collection-01/scripts/` if kept for reproducibility.

**Open op gotcha — duplicate Drive files.** GEE `toDrive` does NOT overwrite: a re-export lands
as `snic_<y> (2).tif` (Insync), which `load_snic`'s glob would `vrt()` together. Clear the Drive
folder before re-exporting a year, and/or make `load_snic` pick the newest. **[TODO]**
