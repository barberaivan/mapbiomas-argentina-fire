# objects-benchmarks — step-05 whole-country vectorization benchmarks

One-off benchmark harness that profiled step 05 (`workflow/05-objects_metrics.R`) on the
whole-country **FY2000** grid and compared the two vectorization strategies. Findings and the
resulting decisions live in **`docs/05-object_metrics.md` §7–§8**; these scripts are kept so the
numbers are reproducible. They are **not** part of the production pipeline.

Input: the FY2000 direct-download tiles in `collection-01/data/snic-direct/2000/` (04 §5b).
Interpreter: the project GEE venv (`$PYTHON`) for the `.py` files; system `Rscript` for the `.R`.

## Headline result (FY2000: 116.1 M burned cells, 9.16 B-cell grid, 82,025 objects)

The whole-country wall is **labelling memory**, not vectorization:

| stage | result |
|---|---|
| extract (per-carta tile) | 499 s, 8.4 GB — a whole-mosaic `as.data.frame(cells=TRUE)` instead **crashes** (`1:ncell` long vector) |
| label — **igraph** | **OOM > 31 GB** ❌ |
| label — **union-find (Rcpp)** | **82 s, 8.6 GB** ✅ (`n_pids = 82,025`, matches gdal's CC count) |
| vectorize **A** (disk pid + `gdal_polygonize` + dissolve) | **337 s** (write 48 + polygonize 270 + dissolve 20) |
| vectorize **B** (per-object loop, 13 cores) | **163 s** |
| A vs B agreement | **identical** — 82,025 objects each, total-area rel-diff 3.7e-14 |

## Whole-country A-vs-B harness

Orchestrated by **`run_all.sh`** (needs `F2000_DIR` = a scratch dir for the intermediate
binaries/GeoTIFF/GPKGs). Extract is split out so labelling can be re-tried without re-scanning tiles:

```bash
export F2000_DIR=/some/scratch/full2000
Rscript collection-01/scripts/objects-benchmarks/stage0_extract.R   # once → row/col.i32 + meta_grid.json
bash    collection-01/scripts/objects-benchmarks/run_all.sh         # label → A → B → compare
```

| script | role |
|---|---|
| `stage0_extract.R` | per-carta burned-cell extract → `row/col.i32` + `meta_grid.json` (dodges the `as.data.frame` long-vector crash) |
| `stage0_label_uf.R` | memory-bounded **union-find** 8-conn labelling (Rcpp parent array, no edge list/graph) → `pid.i32` + `meta.json` |
| `stageA.py` | Path A: block-aware out-of-core `pid` GeoTIFF write + `osgeo.gdal.Polygonize -8` → raw GPKG |
| `stageA_dissolve.R` | Path A: `terra::aggregate(by="pid")` (required to merge gdal's disconnected same-pid fragments — docs/05 §7b) |
| `stageB.R` | Path B: per-object local-raster `as.polygons`, parallel (`F2000_CORES`, default 13), shard + merge |
| `compare.R` | A-vs-B agreement: feature counts, total area, per-pid area |

> `stage0_label_uf.R` runs **plain 8-connected** labelling (no dilation halo) — the dilation is what
> OOM'd the original. Fine for A-vs-B (both consume the same pids); production must extend the
> union-find to carry the halo. Everything is parameterised by `F2000_DIR`, so relocatable.

## Supporting micro-benchmarks

Produced numbers cited in docs/05 §7b (kept for record; some carry session-specific scratch paths).

| script | role |
|---|---|
| `bbox_dist.py` | per-object bbox / area distribution from a polygon GPKG (Path B cost driver) |
| `costcurve.R` | `terra::as.polygons` cost vs bbox size (the 6.6 ms fixed per-call overhead) |
| `bench_2000.sh` | legacy `snic_2000` mask build + streaming `gdal_polygonize` vs terra `as.polygons` |
| `bench_native_2000.py` | native `osgeo.gdal.Polygonize` of the legacy mask → GPKG |
