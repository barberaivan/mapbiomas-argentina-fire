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

**Patagonia steppe dieback cut.** SNIC adds `candseed==3` dieback padding only **west of −70.3°**
(04 §4.3), but the −70.6…−70.3 steppe-edge strip is mostly false positives in the steppe. The
extract therefore **drops `candseed==3` cells with longitude > −70.6** — effectively tightening the
padding's western limit from −70.3 to −70.6. Clumsy-but-cheap vs. re-running SNIC. Applied here
(before labelling), so dropped cells neither form nor join objects. (The GEE-precomputed
`burned_around` counts still include them in neighbours' windows — negligible.)

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
cells directly when they fall within a **wider window**, with a distance threshold that depends on
whether each endpoint gets **enlarged context**. Working out the geometry (a burned pixel with
enlarged context "occupies" its 3×3 dilation; one without — see below — occupies just 1×1; two
occupied regions 8-touch at exactly these distances):

| the two burned cells | union if Chebyshev distance ≤ |
|---|---|
| both **with** enlarged context | **3** |
| exactly one with enlarged context | **2** |
| both **without** enlarged context | **1** (plain 8-connectivity) |

So the labeller sweeps a **7×7 forward-offset window** (24 offsets, each undirected pair once)
and, per candidate pair, unions only within that distance threshold. A burned cell gets **no
enlarged context** (8-connectivity only) when it is either:

- **ag/grass/pasture** — veg_fire ∈ **{1, 2, 3, 12, 13, 15, 17, 18, 19}** (`agriculture_*`,
  `grassland_ba/chaco/pampa`, `grassland-inund_chaco`, `pasture_ba/chaco`), where bridging distinct
  burned fields/paddocks would inflate commission error; **or**
- a **`candseed==3` dieback pixel** — Patagonia slow-dieback padding may only *extend* a real scar,
  never bridge across gaps, so it is connected to its 8-neighbours only.

Everything else (forests, shrublands, `grassland_cuyo` (14), `grassland_pat`/steppe (16), and
perennial ag `agriculture-per_chaco-ba` (4)) **keeps** enlarged context — in sparse/fragmented
fuels bridging recovers one real scar. (Keep the no-enlarged-context set in sync with the R
`NO_DILATE_VEG` constant.) The original ROI validation (ag/grass = {1,2,3,13,17}, no dieback rule)
reproduced the terra dilate→label→drop-halo result **pixel-for-pixel** (ROI 1998 → 115 objects,
sorted per-object pixel counts identical, area rel-diff 0); the expanded set follows the same
geometry.

### 2.3 Vectorize — parallel per-object (`vectorize_sparse`, Path B)

Per polygon-id (pid): build a **tiny local-bbox raster** holding all of that pid's cells and
`as.polygons(dissolve=TRUE)` → one (multi)polygon. Disconnected fragments of one pid (the
dilation-bridge case) dissolve into a single multipolygon, so the bridge is preserved
**natively**. Objects are independent → `mclapply` across `OBJ_CORES`; workers return
`terra::wrap`ped chunks (fork-serializable), master merges. Never builds the country-wide 34 GB
`pid` raster. (Alternative "Path A" — write `pid` to a disk GeoTIFF + streaming
`gdal_polygonize` — is ~2× slower and needs an extra dissolve-by-pid for the disconnected case;
see §7/§8.)

### 2.4 Metrics — raster + geometry (`aggregate_metrics`, `add_shape_metrics`)

Computed **raster-native** over the burned-cell `data.table`, grouped by pid — faster and exact
for area. The set was **trimmed** (2026-07-23) to the metrics the step-06 model actually uses; the
cut replaces the six-stat `qstats` (per-group `quantile()` at R-callback speed — §9's wall-clock
sink) with GForce-optimizable `{median, min, max, mean}`, buying back both time and the transient
memory that drove the peak (§9.3):

- **seed share** — `seed_mean` = fraction of the object's focal pixels that are SNIC **seeds**
  (`candseed == 2`). **The single most discriminating metric** for fire vs. noise (real scars are
  densely seeded, noise is unseeded) — 05 §4 / the step-06 filter lean on it. Computed over focal
  pixels (`candseed != 3`), consistent with the date exclusion below.
- **veg abundance** — per-class fractions `frac_c1…c23` (absent = 0). **No ranked top-5** (dropped;
  fully derivable from the fractions, incl. the "agriculture proportion" = Σ ag fractions).
- **area** — `area_ha` = Σ per-cell `cellSize` ÷ 10⁴ (for a lon/lat grid the `cellSize` is computed
  on a 1-column strip by latitude, O(nrow)) and `n_pixels`.
- **`abs_date` summary** — `{median, min, max}` only (a human `date_median_date` is added at write).
- **`year_calendar`** — per pixel's `abs_date` → calendar year, then the **mode** across the
  object's pixels (assigns the object to the calendar year most of it burned in — the join key into
  the official calendar-year month-of-burn raster, step 07). *(No `year_fire`: it is redundant with
  the fire-year already encoded in `oid`.)*
- **`n_mean`** — mean Landsat observation count over the object's pixels (skipped if no `n` band).
- **neighbourhood sparseness** `burned_around_{1,2,3}` — mean over the object's pixels of the
  burned fraction in the (2r+1)² window. Direct tiles carry it pre-computed in GEE (cell counts
  → ÷(2r+1)²); the legacy COG computes it here.

**Dieback pixels excluded from all date computations.** `candseed==3` cells carry *next*-fire-year
dates (04 §4.3) and downstream inherit the parent object's date, never their own — so they are
**dropped before computing** `abs_date` `{median,min,max}` and the `year_calendar` mode, otherwise
they would drag the object toward the following year.

**Geometry shape/sparsity** (ported from collection-00 `addShapeMetrics`): `perimeter_m`,
`convexity` (area/hull), `mbr_fill` (area/bbox), `mbr_elongation`, `circularity` (4πA/P²),
`shape_index` (P/2√πA). Bbox = axis-aligned envelope; on the lon/lat grid its spans are
converted degrees→metres.

---

## 3. Object ids — pid / oid

`pid` = object id, unique **within a year only** (labelling restarts each year). The
globally-unique key is **`oid = "<fire_year>_<pid>"`** (e.g. `2015_4213`) — it is the join key
everything downstream uses, and since it embeds the fire-year, no separate `fire_year` column is
written.

---

## 4. Outputs & run

Written to `collection-01/data/snic-polygons/`. **Geometry and metrics are split with no
redundancy**, and the metrics themselves are split by their compute phase — each of the two metric
phases (§2.4) writes its own CSV directly, keyed by `oid`, so there is **no join-onto-geometry
step** (minimal code):

| file | contents |
|---|---|
| `objects_<fy>.gpkg` | one polygon per object + **`oid` only** (no metrics) — lightweight local intermediate |
| `objects_<fy>_raster_metrics.csv` | the §2.4 **raster** metrics (`aggregate_metrics`), keyed by `oid` |
| `objects_<fy>_shape_metrics.csv` | the §2.4 **geometry/shape** metrics (`add_shape_metrics`), keyed by `oid` |

Why GPKG and not GeoJSON: the per-year file is a **local intermediate** (used to turn collected
points into per-object labels, and to subset the fire objects) — GPKG is lighter, faster, and
coordinate-lossless. **GeoJSON is produced only later, for the classified fire subset** that gets
uploaded to GEE (step 06), never for the full year. The step-06 model reads the two CSVs (join on
`oid`) — no geometry needed — so all three files stay independent through classification.

```
OBJ_CORES=13 Rscript collection-01/workflow/05-objects_metrics.R 2000   # union-find (default)
Rscript collection-01/workflow/05-objects_metrics.R test 1998           # small-ROI → objects_test_*
Rscript collection-01/workflow/05-objects_metrics.R terra 2000          # dense fallback (ROI only)
```

`OBJ_CORES` (default ~half the cores; 1 = serial) sets the per-object vectorize fan-out.

### 4.1 Overnight all-years batch — `run_05_years.sh` + `mem_monitor.sh`

Because a fire-active year can push the metrics/vectorize peak past 31 GB and OOM (§6, §9), the
full 2001–2025 run is driven by a wrapper that **runs one `Rscript` per year** rather than passing
every year to a single R process. That isolation is the point: if one year is OOM-killed, only that
year dies — the loop continues and the remaining years still finish overnight (a single process
would lose everything after the failing year). Both scripts are plain bash, no deps, in
`collection-01/workflow/`:

- **`run_05_years.sh [start_year] [end_year]`** (default `2001 2025`) — loops the years, one
  `Rscript 05-objects_metrics.R <fy>` each. **Resumable/idempotent:** skips any year whose
  `objects_<fy>_shape_metrics.csv` (written *last*, so a true completion marker) already exists —
  relaunch after a crash and done years are skipped. Records per-year exit code + wall time and
  flags **`rc=137` (SIGKILL — the kernel OOM-killer's signature) as a likely OOM**. `tee`s the R
  step messages to the tmux window *and* the run log (`PIPESTATUS[0]` preserves R's real exit code
  so the OOM flag survives the pipe). Auto-starts the monitor and kills it on exit.
- **`mem_monitor.sh [logfile] [interval_s] [warn_avail_mb]`** (defaults `mem_monitor.log 15 2048`) —
  lightweight whole-system RAM sampler: tracks peak used/swap, logs a `PEAK` line only on a new high
  (file stays tiny), and appends a **`WARN … NEAR OOM`** line the moment `MemAvailable` drops below
  the threshold (re-arms after recovery). Writes a final `STOP` line with the peaks. Standalone-usable
  around any heavy run.

```
tmux new-session -d -s obj05 '/abs/path/to/collection-01/workflow/run_05_years.sh 2001 2025'
tmux attach -t obj05                 # watch live; Ctrl-B D to detach
tail -f collection-01/logs/05_run_*.log
# morning triage:
grep -E 'OOM|WARN|FAILED|done rc=0' collection-01/logs/05_{run,mem}_*.log
```

Two logs land in `collection-01/logs/`: `05_run_<range>_<stamp>.log` (steps + per-year
done/OOM/failed) and `05_mem_<range>_<stamp>.log` (peak RAM + any WARN). Launch from tmux with an
**absolute path** (the wrapper `cd`s to the repo root itself, but a detached tmux shell may not
start there). If a year OOMs, buy headroom via the §9.3 trims or fall back to the per-REGION split
(§6), then relaunch the same command.

**Measured whole-country 2001–2025 run (2026-07-24, 31 GB / 16-core box, `OBJ_CORES`=13, all
years post-§9.3-trim).** All 25 years finished `rc=0`, no OOM, no memory `WARN`.

- **RAM:** peak **24.9 GB** resident + ~1 GB swap — comfortably under 31 GB (~6 GB headroom), and
  below the FY2000 pre-trim profile (§9, 28.7 GB) thanks to the §9.3 metric trims and these years
  being lighter than the FY2000 near-worst case. **Plan for ≥ ~26 GB RAM for this step; 32 GB is a
  safe target.** A materially heavier future year is still the per-REGION-split trigger (§6).
- **Time per fire-year:** **24 of 25 years took ~34–48 min** (median ~37 min). The lone outlier is
  **FY2023 at 138 min** — the heaviest fire year in the 2001–2025 record; it still fit in RAM, but
  is the current worst case to watch.
- **Total:** the 25 years ran back-to-back in **~17.3 h** wall-clock (one `Rscript`/year, serial).

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

---

## 9. Full-pipeline whole-country run (FY2000) — memory profile, the merge bug, and where to trim

The first end-to-end production run on the whole country (FY2000, 116.1 M burned cells, 31 GB
RAM box, `OBJ_CORES=13`) closed the §6 "Remaining" item — it **measured the metrics-aggregation
memory** the benchmark had skipped — and turned up one hard bug. **FY2000 is a near-worst-case
year** (the arid-diagonal megafires; one of the most-burned years on record), so these numbers
are the stress test, not a mild baseline.

### 9.1 It fits — but only just (~2.5 GB headroom)

**Result:** 71,024 objects → `objects_2000.gpkg` (390 MB) + `_metrics.csv` (28 MB), **wall-clock
1 h 39 m**, `OBJ_CORES=13`. (71,024 vs the §6 benchmark's 82,025 is expected — the benchmark
labelled plain 8-connected, production's **dilation-as-window** merges fragments into fewer, larger
objects.) The long wall-clock is the serial metrics phase, not the parallel parts: avg CPU was only
~125 % (mostly one core), because per-pid `qstats` and `add_shape_metrics` dominate (§9.3).

Peak **system memory used 28.7 GB / min available 2.6 GB** (of 31 GB), max single-process
RSS 26.2 GB, swap barely touched (~0.6 GB), no OOM-kill. Track **available RAM
(`MemTotal−MemAvailable`)**, never summed process
RSS — during the parallel vectorize the forked workers share the master's pages copy-on-write, so
summed RSS balloons to ~90–120 GB while the true committed footprint stays ~28 GB. Two phases sit
at the ~2–3 GB-available floor:

- **Serial metrics aggregation — the real peak (parent RSS ≈ 25 GB).** This is the piece §6
  flagged as untested. It peaks not because any one structure is huge but because the **full
  7-band `dt` (~10 GB) is still alive while `aggregate_metrics` builds its `dcast` wide tables +
  `qstats` intermediates** — the two coexist. It's a single R process, **CPU-bound on one core**
  (`vmstat`: 1 core pinned, si/so≈0, wa=0), and it **dominates wall-clock** — far longer than the
  §6 "12–16 min/yr" note (which timed label+vectorize only, no metrics). The per-pid `qstats`
  (median/mean/p2.5/p97.5/min/max, computed for **both** `abs_date` and `n` → 12 quantile-family
  calls per pid over ~82 k pids) is not data.table-GForce-optimized, so it runs at R-callback speed.
- **Vectorize fan-out (13 workers).** Once metrics returns, the heavy `dt` goes out of scope and
  is GC'd — **only `geom = dt[,.(row,col,pid)]` survives** — so parent RSS drops to ~15 GB before
  the fork. Available RAM still dips to ~2.6 GB here, but that is COW-shared master pages, not
  runaway worker growth.

The design's "drop the heavy object, carry only pid+coords into vectorize" (`objects_sparse`
returning `geom` + finished `mets`) **already works** — RSS visibly falls at the metrics→vectorize
boundary. The remaining pressure is entirely *inside* the serial metrics phase.

### 9.2 The bug that killed the run at the finish line (fixed)

After ~42 min of correct compute (extract → label → metrics → per-object vectorize all fine), the
run died at the **final master merge** in `vectorize_sparse`:

```
error … selecting a method for function 'merge': argument "x" is missing
Calls: … vectorize_sparse -> do.call -> rbind -> …
```

`do.call(rbind, lapply(res, terra::unwrap))` mis-dispatches terra's S4 `rbind` to `merge` **only
for fork-unwrapped SpatVectors** — freshly-built SpatVectors `rbind` fine via `do.call`, so the
per-worker combine (fresh objects) never tripped it; only the master's combine of `unwrap()`ed
worker results did. **Fix:** use `terra::vect(<list of SpatVectors>)` (the idiom for concatenating
a list; `Reduce(rbind, .)` also works) for **both** the worker and master combines. Verified: the
per-object `pid` attribute survives and counts match. *This is why a whole-country run needs an
end-to-end test — the benchmark's `stageB.R` used its own combine and never exercised this path.*
(Minor, not yet fixed: a constant-1 `lyr.1` column from `as.polygons` leaks into the metrics CSV —
harmless, droppable.)

### 9.3 Where to cut the metrics peak & time (some resolved 2026-07-23)

The serial metrics phase is both the memory peak and the wall-clock sink, so it's the target:

- **Fewer summaries — ADOPTED (§2.4).** `qstats` emitted 6 stats × 2 vars per object via per-group
  `quantile()` at R-callback speed. The trimmed set — `abs_date` `{median,min,max}`, `n_mean`, and
  dropping the veg top-5 — is GForce-optimizable, cutting R-callback CPU *and* the intermediate
  footprint that drove the peak. (User: "computing lots of summaries for the same variable, I can
  easily decrease that.")
- **Ordering — keep raster-metrics BEFORE vectorize (reorder rejected).** A proposed
  polygonize-first order (vectorize → shape metrics → free → raster metrics) does **not** help:
  vectorize needs only the slim `geom`, raster metrics need the full 7-band `dt`, so whatever runs
  last should be the cheap one. The current order already consumes the heavy bands first, frees
  `dt`, and carries only `geom` into the fork — reordering would instead keep the 10 GB `dt` alive
  through the fork. Raster metrics and polygon (shape) metrics are already computed in separate
  phases (`aggregate_metrics` pre-vectorize, `add_shape_metrics` post-vectorize on small `polys`).
- **Free/slim `dt` before the wide `dcast`s.** Drop columns no longer needed once their summary is
  computed, so the 7-band `dt` and the `dcast` outputs don't both sit at full width — this is what
  pushes the parent to ~25 GB.
- **Decouple the two peaks via disk (user's idea).** Aggregate metrics → write the per-pid metrics
  CSV → drop the heavy object → keep only `pid`+coords for vectorize. Then RAM is never occupied by
  "everything at once"; metrics and vectorize peak separately, not together.
- **Do NOT parallelize the metrics group-by (as-is).** Splitting `dt` by pid across workers
  duplicates the heavy columns, and several arid-diagonal **megafires landing in one worker**
  would OOM — the exact failure the user cautioned about. Serial group-by is the memory-cheapest
  form and already fits; only revisit if the whole year is first split by REGION (§6).
- **Latent vectorize risk — megafire bbox.** `.one_object` allocates a **dense** `rep(NA, h·w)`
  array over each object's bounding box. A long diagonal megafire has a huge, mostly-empty bbox, so
  one worker can transiently allocate GBs for a single scar. It did **not** OOM at FY2000, but the
  risk grows with more/larger fires (and would compound if metrics were also parallelized). A
  sparse local raster or per-fragment polygonize would remove it.

**Bottom line for the two open questions.** [1] Loading all 7 bands per burned cell and computing
every metric whole-country **does not OOM** at FY2000 — peak 28.7 GB used, 2.6 GB free. [2] Because
FY2000 is already a near-worst-case fire year, most years should fit too — but the ~2 GB headroom
is thin, so a materially heavier year remains a REGION-split candidate (§6), and the §9.3 trims buy
back headroom cheaply before that's needed.
