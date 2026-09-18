# 05 — Fire-object vectorization & metrics (R)

Step 05 turns the step-04 burned **pixels** into fire-scar **objects** and attaches the
per-object metrics that the step-06 classifier reads. It runs **one fire-year at a time**,
whole-country and untiled, so an object is global within its year — nearby fragments of one scar
share an id. First R stage of the prediction pipeline; it consumes step 04's SNIC product, so
read [`04-snic.md`](04-snic.md) first.

## Foundations

**This step materializes the fire patch so that step 06 can judge it.** A patch has properties no
pixel has — shape, size, vegetation composition, a spread of burn dates — variables that help
separate a real scar from a field of spectrally similar noise.

**Every stage is sized by burned cells, never by the grid.** Argentina's 30 m lattice is 9.16 B
cells; a heavy fire year has ~116 M burned ones, three orders of magnitude fewer. The pipeline is
built around that ratio — a per-tile extract, union-find over a parent array, one small raster
per object — because the obvious dense formulations (a country-wide object-id grid, an explicit
edge list, a materialized dilation halo) each need tens of GB and OOM'd a 31 GB box. The measured
walls are in [`notes/05-whole_country_redesign.md`](notes/05-whole_country_redesign.md).

**Objects jargon: `pid` and `oid`.** `pid` is the label the step assigns to an object, 
unique **within a fire-year only**, because
labelling restarts each year. The globally unique key is **`oid = "<fire_year>_<pid>"`** (e.g.
`2015_4213`) — every output below is keyed by it, and it is the join key everything downstream
uses. Since it embeds the fire-year, **no separate `fire_year` column is written**.

## Inputs → Outputs

step-04 SNIC rasters → **`workflow/05-objects_metrics.R`** → one GPKG of geometry + two metric CSVs

| | What it is | Where |
|---|---|---|
| **in** | SNIC GeoTIFFs, **7 bands**, one per *carta* — the 248-sheet MapBiomas grid Argentina is tiled on (`04-snic.py --to-asset` + `download_snic.py`) | `data/snic-rasters/<fy>/` |
| **out** | one polygon per object + **`oid` only**, no metrics | `data/objects-raw/objects_<fy>.gpkg` |
| **out** | raster metrics (`aggregate_metrics`), keyed by `oid` | `data/objects-raw/objects_<fy>_raster_metrics.csv` |
| **out** | geometry/shape metrics (`add_shape_metrics`), keyed by `oid` | `data/objects-raw/objects_<fy>_shape_metrics.csv` |

The seven bands are `candseed` (1 candidate, 2 seed, 3 Patagonia next-year dieback), `abs_date`
(per-pixel burn mid-date, days since 1970-01-01), `veg_fire` (the burnable class), `n` (Landsat
observation count) and `burned_around_{1,2,3}` precomputed in GEE as cell counts. All are masked
to `candseed > 0`, so the files are sparse and terra reads the mask off the **NoData tag** — no
COG structure is involved.

**Geometry and metrics are split with no redundancy**, each phase writing its own CSV keyed by
`oid`, so there is no join-onto-geometry step and step 06 never opens the geometry. The GPKG is a
*local* intermediate — labels, QGIS layers, the upload package — hence GPKG and not GeoJSON
(~12× larger, measured).

## How it works

### Extract — one carta tile at a time

Read one carta (each under 2³¹ cells), keep the burned cells, map local `(row, col)` onto the
global lattice via the tile's offset, `rbindlist`. The result is one `data.table` of burned cells
carrying every band plus global `row`/`col`/`cell`.

**The Patagonia steppe dieback cut** is applied here, before labelling, so dropped cells neither
form nor join objects. SNIC adds `candseed == 3` dieback padding west of −70.3°, but the
steppe-edge strip east of `DIEBACK_LON_CUT` is mostly false positives and is dropped — tightening
the padding's western limit rather than re-running SNIC.

### Label — union-find, with dilation as a wider window

Objects are the connected components of the burned cells. **Union-find** (`utils/label_uf.cpp` —
three primitives, labelling-agnostic; the R caller chooses the pairs) needs only an `N`-int parent
array, so candidate edges are streamed one window-offset at a time and discarded.

A real scar breaks into fragments a pixel or two apart. Gluing them by dilating the mask 1 px,
labelling, then dropping the halo is **exactly equivalent** — and halo-free — to unioning two
burned cells directly when they fall within a wider window, with the threshold depending on
whether each endpoint gets **enlarged context**. A cell with enlarged context occupies its 3×3
dilation, one without occupies 1×1, and two occupied regions 8-touch at exactly these distances:

| the two burned cells | union if Chebyshev distance ≤ |
|---|---|
| both **with** enlarged context | **3** |
| exactly one with enlarged context | **2** |
| both **without** enlarged context | **1** (plain 8-connectivity) |

So the labeller sweeps a 7×7 forward-offset window (24 offsets, each undirected pair once) and
unions only within the pair's threshold. A cell gets **no** enlarged context when it is either
**ag/grass/pasture** (`NO_DILATE_VEG` in the R script), where bridging distinct burned
fields would inflate commission error, or a **`candseed == 3` dieback pixel**, which may only
*extend* a real scar and never bridge a gap. Everything else — forests, shrublands, the Cuyo and
Patagonian grasslands, perennial agriculture — keeps enlarged context, because in sparse fuels
bridging recovers one real scar. The equivalence was verified against the dense
dilate→label→drop-halo route pixel-for-pixel on an ROI.

### Vectorize — one small raster per object

Per `pid`: build a tiny local-bbox raster holding that `pid`'s cells and `as.polygons(dissolve =
TRUE)` → one (multi)polygon. Disconnected fragments of one `pid` — the dilation-bridge case —
dissolve into a single multipolygon, so the bridge is preserved **natively**. Objects are
independent, so this is an `mclapply` fan-out across `OBJ_CORES` workers (default ~half the
cores; 1 = serial); they return `terra::wrap`ped chunks and the master concatenates with
`terra::vect()`. The country-wide `pid` raster is never built.

### Metrics — raster-native, then geometry

Computed over the burned-cell `data.table` grouped by `pid`, which is both faster and exact for
area. The set is deliberately narrow: only what step 06 actually uses, with every summary chosen
to be GForce-optimizable in `data.table`.

- **`seed_mean`** — fraction of the object's focal pixels that are SNIC seeds (`candseed == 2`).
  **The single most discriminating metric** for fire vs. noise: real scars are densely seeded,
  noise is unseeded.
- **veg abundance** — per-class fractions `frac_c1…c23` (absent = 0). No ranked top-5; it is
  fully derivable from the fractions, including the agriculture proportion.
- **area** — `area_ha` from per-cell `cellSize`, and `n_pixels`.
- **`abs_date` summary** — `{median, min, max}`, plus a human-readable `date_median_date` at write.
- **`year_calendar`** — the **mode** across the object's pixels of each pixel's calendar year; the
  join key into the calendar-year products of step 07.
- **`burned_around_{1,2,3}`** — neighbourhood sparseness: mean over the object's pixels of the
  burned fraction in the (2r+1)² window.
- **`n_mean`** — mean Landsat observation count. Computed here but **not a model predictor, and
  collection 2 should not compute it at all**: it is an era proxy and reintroduced a spurious time
  trend in the fire rate. See [`06-object_model.md`](06-object_model.md) §4.

**Dieback pixels are excluded from every date computation.** `candseed == 3` cells carry *next*
fire-year dates and inherit the parent object's date downstream, so they are dropped before the
`abs_date` summaries and the `year_calendar` mode, which they would otherwise drag into the
following year. An all-dieback object therefore has no seed or date statistics by design, and
carries NA predictors through step 06.

**Geometry/shape metrics** (ported from collection-00's `addShapeMetrics`): `perimeter_m`,
`convexity` (area/hull), `mbr_fill` (area/bbox), `mbr_elongation`, `circularity` (4πA/P²),
`shape_index` (P/2√πA), the bbox being the axis-aligned envelope with spans converted to metres.

## Run

```bash
OBJ_CORES=13 Rscript collection-01/workflow/05-objects_metrics.R 2000   # union-find (default)
Rscript collection-01/workflow/05-objects_metrics.R test 1998           # small ROI → objects_test_*
Rscript collection-01/workflow/05-objects_metrics.R terra 2000          # dense fallback, ROI only

# all years overnight, one Rscript per year, resumable — launch with an ABSOLUTE path
tmux new-session -d -s obj05 '/abs/path/to/collection-01/scripts/run_05_years.sh 2001 2025'
grep -E 'OOM|WARN|FAILED|done rc=0' collection-01/logs/05_{run,mem}_*.log   # morning triage
```

`run_05_years.sh` runs **one `Rscript` per year** so an OOM kills only that year, skips any year
whose `_shape_metrics.csv` already exists, flags `rc=137` as a likely OOM, and starts
`mem_monitor.sh` alongside. Budget **~26 GB of RAM** and ~17 h for a 25-year batch; measurements
in [`notes/05-memory_profile.md`](notes/05-memory_profile.md).

## Key decisions

All five were forced by whole-country memory; the benchmarks behind them are in
[`notes/05-whole_country_redesign.md`](notes/05-whole_country_redesign.md).

- **Objects stay global — the country is never tiled.** A scar crossing a seam splits, and
  re-merging forces every polygon metric to be re-aggregated across the pieces. The untiled run is
  feasible, so the seam problem is never created; the fallback for a year that does not fit is a
  few deliberately coarse regions, not per-carta tiling.
- **Union-find, not a graph library.** `igraph` is faster on a ROI but its explicit edge list
  OOM'd whole-country; union-find stores only the parent array.
- **Dilation as a wider union window, not a materialized halo.** Exactly equivalent, verified
  pixel-for-pixel, and without the transient that fed the OOM.
- **Per-object local rasters to vectorize**, over a disk `gdal_polygonize` route ~2× slower that
  also needs a dissolve-by-pid to undo gdal's splitting of disconnected fragments.
- **Metrics stay serial, and run before vectorize.** Parallelizing the group-by duplicates the
  heavy columns and several megafires in one worker would OOM; running it first frees the band
  table before the fork instead of carrying it through.

## Gotchas

- **Never read this step's memory off summed process RSS.** Forked workers share the master's
  pages copy-on-write, so summed RSS balloons to 90–120 GB while the true footprint is ~28 GB.
  Track `MemTotal − MemAvailable`.
- **`_shape_metrics.csv` is written last**, so it is the completion marker: a year with a GPKG but
  no shape CSV did not finish.
- Keep `NO_DILATE_VEG` and the enlarged-context rule above in sync; one decision written twice.

## Files

| File | Role |
|---|---|
| `workflow/05-objects_metrics.R` | the step |
| `utils/label_uf.cpp` | union-find primitives (`uf_new` / `uf_union` / `uf_labels`) |
| `scripts/run_05_years.sh` | one `Rscript` per year, resumable, OOM-flagging |
| `scripts/mem_monitor.sh` | RAM sampler; logs peaks and a `WARN` near OOM |
| `scripts/download_snic.py` | fetch the step-04 per-carta tiles |
| `scripts/objects-benchmarks/` | the benchmark scripts behind the notes below |

## Related

- [`04-snic.md`](04-snic.md) — the SNIC product this step consumes.
- [`06-object_model.md`](06-object_model.md) — the classifier these metrics feed, and §4 on why no
  predictor may proxy for the year.
- [`notes/05-whole_country_redesign.md`](notes/05-whole_country_redesign.md) — what broke at
  9.16 B cells and every road not taken.
- [`notes/05-memory_profile.md`](notes/05-memory_profile.md) — the FY2000 profile, the
  fork-unwrapped-SpatVector merge bug, and the 25-year batch.
- `notebooks/objects-analysis.qmd` — exploration of the resulting object set.
