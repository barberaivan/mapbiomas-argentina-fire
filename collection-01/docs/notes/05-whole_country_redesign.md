# 05 — Making step 05 run whole-country: what broke, and every road not taken

> **Extracted from** `collection-01/docs/05-object_metrics.md` §6 (Status), §7 (Whole-country
> FY2000 profile) and §8 (Roads taken and abandoned)
> @ `7bf09ae` (2026-09-18) — those sections no longer exist; the doc was restructured to
> `docs/TEMPLATE.md` and its headings are now named, not numbered.
> Lab notebook — the record of building the step, not documentation of it.

The doc keeps only the outcome: every stage is sized by burned cells and objects stay global
(untiled). This is the route, and the measured walls that forced it. Memory and wall-clock of the
resulting pipeline are in [`05-memory_profile.md`](05-memory_profile.md).

> **Everything below is an abandoned road — none of it is in the code any more.** Two of these
> alternatives outlived the decision as fallbacks and were both **deleted on 2026-09-18**:
>
> - the **legacy Drive COG** input layout (`04-snic.py --to-drive` → `objects-raw/`), together with
>   step 05's fallback that read it — no `snic_*.tif` existed anywhere on disk, all 28 fire-years
>   came from the per-carta tiles, and the fallback could only reach its own `stop()`;
> - the dense **`terra`** labelling mode (`object_ids()` + `raster_metrics()`, invoked as
>   `Rscript 05-objects_metrics.R terra <fy>`), which had served as the independent oracle for the
>   ROI equivalence check recorded in §6 and was never run again after it.
>
> Read the list below as history, not as routes on offer.

---

## 6. Status (2026-07-22)

**Done & validated (ROI 1998, sparse vs terra):** per-tile extract, union-find labelling,
**dilation-as-window** (veg-threshold 3/2/1), parallel per-object vectorize, and all metrics —
**115 objects, sorted per-object pixel counts identical, area rel-diff 0**. All in production.

**Proven at country scale (FY2000 benchmark, `scripts/objects-benchmarks/`):** extract 499 s /
8.4 GB; union-find label 82 s / 8.6 GB (82,025 objects, matches GDAL's CC count); vectorize
Path B 163 s (13 cores) — identical objects to Path A.

**Full production script run whole-country (FY2000) — the metrics-aggregation memory is now
measured (§9).** It fits 31 GB but with only ~2 GB headroom; the run also surfaced a fix
(fork-unwrapped-SpatVector merge) that had been killing the whole run at the final step. Step-06
filter cuts are still open (04 §7).

> **Fire-active years may not fit whole-country.** Everything here scales with burned cells.
> **FY2000 turns out to be a near-worst-case year** — the arid-diagonal megafires make it one of
> the most-burned years in the record (116 M burned cells), so §9's whole-country run is the
> stress test, not a mild baseline. It fits, but with only ~2 GB free (§9), so a year with
> materially more burned cells could still push the metrics group-by or the vectorize past 31 GB
> and OOM. Fallback: **process by REGION** — a few large groups of cartas, run independently, then
> concatenated. Deliberately *coarse* (not per-carta) so very few scars cross a region seam; cut
> the boundaries along low-fire gaps to minimise splits. Caveat: this reintroduces the
> **seam-merge** for objects straddling a region boundary — the exact thing tiling was rejected
> for (§8) — so keep regions few and large, and only reach for it when a year actually OOMs
> whole-country.

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

## 8. Roads taken and abandoned

Chronological, so a future reader sees why the current design is what it is:

- **GEE `connectedComponents`** — native scar labelling in GEE. Dead end: `maxSize` caps a
  component at ~1024 px (real scars silently split). Labelling stays local.
- **`terra::patches()` dense labelling** (the original) — correct and simple, but O(all cells)
  and needs a 34 GB int32 `pid` grid at 9 B cells. Kept only as the ROI `terra` fallback.
  *(2026-09-18: deleted — never run again after the equivalence check above.)*
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
