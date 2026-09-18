# 05 — What step 05 costs: the FY2000 memory profile, the merge bug, and the 25-year run

> **Extracted from** `collection-01/docs/05-object_metrics.md` §9 (Full-pipeline whole-country
> run) and the measured-run block at the end of §4.1
> @ `7bf09ae` (2026-09-18) — those sections no longer exist; the doc was restructured to
> `docs/TEMPLATE.md` and its headings are now named, not numbered.
> Lab notebook — the record of building the step, not documentation of it.

The doc keeps only the outcomes: **plan for ~26 GB of RAM and budget ~17 h for a 25-year batch**,
the serial metrics aggregation is the peak, and the per-year `Rscript` isolation in
`run_05_years.sh` exists because a heavy year can still OOM. This is the measurement behind all
three, plus the one bug that killed the first end-to-end run. The redesign that produced this
pipeline is in [`05-whole_country_redesign.md`](05-whole_country_redesign.md).

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

---

## The 25-year production batch (from §4.1)

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
