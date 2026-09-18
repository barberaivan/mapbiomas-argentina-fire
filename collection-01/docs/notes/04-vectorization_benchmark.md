# 04 — Whole-country vectorization benchmark (FY2000)

> **Extracted from** `collection-01/docs/04-snic.md` §5c ("Whole-country vectorization benchmark
> (FY2000)")
> @ `c949f6b` (2026-09-18) — that section no longer exists; the doc was restructured to
> `docs/TEMPLATE.md` and its headings are now named, not numbered.
> Lab notebook — the record of building the step, not documentation of it.

It sat in the step-04 doc because it was measured while the step-04 → step-05 handoff was being
designed, but it benchmarks the **step-05** vectorize primitive. The decision it fed — untiled,
whole-country, out-of-core — and the rest of that redesign are in
[`05-whole_country_redesign.md`](05-whole_country_redesign.md).

---

## 5c. Whole-country vectorization benchmark (FY2000)

> **Input:** one whole-country `snic_2000` image (16 sub-tifs, **9,156,980,085 cells** =
> 123601 × 74085), not the per-carta tiles of §5b. It measures the vectorize primitive at real
> whole-country scale; numbers on the tiled input will differ. Machine: 31 GB RAM + 8 GB swap; GDAL 3.8.4.

Steps share a burned-mask prep (terra writes a sparse `candseed>0` uint8 tif), then the mask is
vectorized three ways. Wall time / peak RSS from `/usr/bin/time -v`:

| step | wall | peak RSS | output |
|---|---|---|---|
| **prep** — build sparse burned-mask tif (terra, out-of-core, 9.16 B-cell scan) | 18:48 | 8.7 GB | 18 MB sparse mask |
| **OLD** — `terra::as.polygons(dissolve=TRUE)` | 7:48 | 8.5 GB | **1** dissolved feature |
| **NEW-compute** — `rasterio.features.shapes` (streaming Band, count-only) | 3:33 | 2.8 GB | 82,025 polygons |
| **NEW-native** — `osgeo gdal.Polygonize` → GPKG (polygonize **+ write**) | 4:20 | 2.4 GB | 82,025 scars, 365 MB GPKG |

Reading:

- **Streaming `gdal_polygonize` vectorizes the whole country at ~2.4 GB in ~4.3 min** and yields
  the **82,025 per-scar polygons directly** (one per 8-connected burned blob), writing straight to
  GPKG. Native (osgeo, C→OGR) even beats the rasterio count on RAM (2.4 vs 2.8 GB) because geometries
  never round-trip through Python — same GDAL engine, better output path.
- **terra `as.polygons` on the same sparse mask is ~2× slower and ~3.5× heavier (7:48 / 8.5 GB), and
  returns a single dissolved feature** — it has no per-object ids without a `pid` raster. Which is
  the real blocker: building that `pid` raster in RAM is the **34 GB densification** at 9.16 B cells
  (`values(pr) <- NA_integer_` → 9.16e9 × 4 B) — **> the 31 GB RAM**, so the in-memory terra path
  **cannot complete** at country scale (§8.3).
- **The prep scan (18:48 / 8.7 GB) is the real cost, and it's a monolithic-COG artifact** — reading
  9.16 B cells single-threaded. From the per-carta direct-download tiles it is far cheaper and
  parallelizable (though we run **untiled** by choice — [`05-whole_country_redesign.md`](05-whole_country_redesign.md)).

**Caveat:** the benchmark polygonized the **raw** burned mask (no 1-px dilation / ag-suppression,
§2), so it times the vectorize *primitive*; production polygonizes the `pid` raster (same cost
order). **Conclusion:** streaming `gdal_polygonize` over a **disk-backed** `pid` (built out-of-core,
not the 34 GB in-RAM fill) makes the whole-country, **untiled** run feasible at bounded RAM within
~1 h/year (decision + architecture in [`05-whole_country_redesign.md`](05-whole_country_redesign.md)).
