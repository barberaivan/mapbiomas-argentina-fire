# 11 — Planning the analysis and the remap (factsheet + product update)

**Window: 10 Sep → 24 Sep 2026.** Launch of MapBiomas Argentina col-3 (with our fire col-1) is
**24 September**; the factsheet is drawn by graphic designers, so **the data behind the plots has to
be delivered around Wed 16 September**, not on the 23rd.

This file is the plan for two things that turned out to be one thing:

1. **A product update.** Some assets have to be re-exported no matter what (§1), and we may also
   want to change the map itself to stop over-mapping fire on cropland (§2).
2. **The factsheet analysis** (`presentations/factsheet-notes.md` holds the *content* plan — which
   plots, which message; this file holds the *production* plan — which asset, which export, what it
   costs, in what order).

They are one thing because every factsheet number has to come from the same layer the platform
publishes, or we have to say out loud that it doesn't.

> **Scope note.** docs/07 is still the reference for *how* each sub-step works. This file only
> records what we re-run in September 2026, why, and in what order. If the two disagree about
> mechanics, docs/07 wins; if they disagree about what was run, this file wins.

**Status, 10 Sep 2026.** All three filter points are wired and verified (§2.3); the threshold
explorers are in the Earth Engine repo (§6); the territory tags and every fire-count table are
built (§8); the burnable and burned-area scripts are written and checked (§5.1). What is left is
one decision — the threshold — and then the exports.

**Status, 11 Sep 2026, 04:30 UTC — read this first if you are the next session.** Overnight the
three burnable benchmarks all **failed on a null-geometry export** (§4.3); the bug is fixed in both
step-11 scripts and everything is relaunched. Four tasks are in flight, all in `TESTS/`, nothing
production:

| task | account | submitted (UTC) | what to do with it |
|---|---|---|---|
| `arg11_burnable_ecoregions13_2020_benchmark` (k=1, 30 m) | gmail | 11 Sep 04:20:21, **RUNNING from 04:23:53** | read `startTime → endTime`, fill the §4.3 table |
| `…_benchmark_k3` (90 m) | comahue | 11 Sep 04:20:51 | ✅ landed in 37 s — **a compute-cache hit, not a timing** |
| `…_benchmark_k4` (120 m) | comahue | 11 Sep 04:21:24 | ✅ landed in 41 s — same caveat |
| `arg11_burned_ecoregions13_2020_benchmark` (burned area by region, 2020) | **comahue** | 11 Sep 04:27:49, **RUNNING from 04:27:54** | **the open question** — is the masked numerator actually cheap? |

**The next session's job, in order:**

1. **Poll the four tasks and record the durations in §4.3** — `ee.data.listOperations()` is
   project-scoped, so poll **both** `mapbiomas-fire-485203` (gmail) and `mapbiomas-argentina`
   (comahue), and do it before the operations age out (a few weeks). Earth Engine stores when an
   asset *landed*, never how long its task ran.
2. **Answer the burned-area question.** If `arg11_burned_…` comes back in minutes, the §5.1
   assumption holds and the numerator is free. If it comes back in hours, that is a real problem:
   the burned half **cannot** be decimated (§5.1), so there is no lever — say so loudly and rethink
   the numerator's route (`--from-objects` in one pass is the fallback).
3. **Decide on the fixed burnable layer** (§4.3, "the idea that makes this benchmark moot") — the
   mode of `veg_fire` across years as a single frozen denominator. That is the structural fix; the
   benchmark only tells us how much pain we avoid.
4. Then the threshold decision and the exports, as before.

Do **not** re-run an identical benchmark expression to get a timing — Earth Engine will serve it
from cache and hand you a fake number (§4.3).

---

## 1. Some products must be re-exported anyway — the land cover was preliminary

`C.PRODUCT_LULC` was pinned on 2026-07-29 to

```
LAND-COVER/COLLECTION-3/INTEGRATION/mapbiomas_argentina_collection3_integration_v1_buffer
```

but the collection that actually publishes is **`mapbiomas_argentina_collection3_pb`**, and there
are `v4`, `v7`, `v8_buffer` in between. So the four `*_coverage` subproducts
(`monthly_burned_coverage`, `annual_burned_coverage`, `frequency_burned_coverage`,
`accumulated_burned_coverage`) currently encode a **preliminary land cover**. This is the risk
already flagged in `presentations/factsheet-notes.md` ("hay que correrlas de nuevo"), and it is
independent of everything else in this document.

**Verified 2026-09-10 — `_pb` is safe to swap in.** Same 41 bands `classification_1985..2025` (so
2025 is native, no forward duplication), same pixel size, and the same lattice as our SNIC grid:

```
SNIC origin  -73.58468801489491, -21.764113209062533   step 0.000269494585236
_pb  origin  -73.566631877684,   -21.780821873347
Δlon = +67 px exactly,  Δlat = −62 px exactly     → integer offset, docs/07 §12.4 carries over
```

(`v1_buffer` had a *different* footprint, origin −76.267 / −14.999, 89361×155938; `_pb` matches
`v8_buffer`, 144332×123501.)

So: **change one line in `utils/constants.py` and re-export.** Which products that touches depends
on the second decision, so the full dependency table is in §3.

> **Only the four `*_coverage` products read land cover.** `07-subproducts.py:360` already stamps
> `lulc_asset` on those four and `"lulc": "not used"` on the other five. If the agriculture filter
> is declined, the mandatory re-export is **4 tasks**, not 9.

---

## 2. The agriculture problem, measured

**The observation (Iván).** The algorithm badly over-maps burned area on cropland. We should have
masked agriculture; we trusted the training data instead, and that was wrong.

**Why it happens.** Harvest, tillage and stubble burning all look like a burn scar to a
per-observation spectral model, and the `veg_fire` remap keeps agriculture *burnable*, so cropland
pixels were never excluded from the SNIC candidate set.

### 2.1 What a polygon-level filter would actually remove

Measured on the local object tables, all 28 fire-years, deployed selection
`fire == 1 & area_ha >= 1` — **1,263,076 objects / 69.12 Mha**. `frac_agri` is the object's
abundance of `veg_fire` classes 1–3 (`agriculture_{chaco, cuyo-pat, pampa}`), **excluding**
class 4 `agriculture-per` (perennials/orchards).

| filter (drop objects with…) | objects dropped | area dropped |
|---|---|---|
| `frac_agri ≥ 0.2` | 109,605 (8.7 %) | 4.67 Mha (6.8 %) |
| `frac_agri ≥ 0.3` | 77,153 (6.1 %) | 3.34 Mha (4.8 %) |
| **`frac_agri ≥ 0.4`** | 54,114 (4.3 %) | **2.36 Mha (3.4 %)** |
| `frac_agri ≥ 0.5` | 36,938 (2.9 %) | 1.67 Mha (2.4 %) |
| `frac_agri ≥ 0.6` | 26,395 (2.1 %) | 1.23 Mha (1.8 %) |
| `frac_agri ≥ 0.8` | 16,408 (1.3 %) | 0.75 Mha (1.1 %) |

Per fire-year the loss is 2–6 % with **no trend**, so analysis 2 (the time series and its slope) is
essentially unaffected by the choice. The national headline moves 69.1 → 66.8 Mha at 0.4.

### 2.2 Three facts that shape the decision

**(a) A polygon filter removes only about half the agricultural burning.** Pixel-weighted, burned
area falling on annual cropland is **2.95 Mha (4.3 % of the total)**. Filtering objects at 0.4
leaves **1.37 Mha of cropland pixels still in the map**, inside mixed objects:

| keep objects with | burned area kept | residual cropland pixels |
|---|---|---|
| `frac_agri < 0.2` | 64.45 Mha | 0.70 Mha |
| `frac_agri < 0.3` | 65.78 Mha | 1.03 Mha |
| `frac_agri < 0.4` | 66.76 Mha | 1.37 Mha |
| `frac_agri < 0.5` | 67.45 Mha | 1.68 Mha |

So the object filter fixes **what the map looks like** (whole spurious crop-field "fires"
disappear) but does **not** make a per-land-cover-class pixel statistic clean. That is the tension §5.3
and §9 have to resolve, not something the threshold can fix.

**(b) It is mostly Chaco — and, in proportion, Yungas.** Now measured against the **Burkart
ecoregions** rather than the `veg_fire` class suffix (which is regionalised by the 5 MapBiomas
regions, so `agriculture_chaco` spans more than the Chaco ecoregion — an earlier note here said
"85 % Chaco" on that basis; **the right figure is 70 %**):

| ecoregion | burned | cropland px | % of its burned area | dropped at 0.4 |
|---|---|---|---|---|
| **Chaco** | 29.21 Mha | **2,056 kha** | 7.0 % | 5.9 % |
| **Pampa** | 6.36 Mha | 420 kha | 6.6 % | 5.0 % |
| Espinal | 16.31 Mha | 216 kha | **1.3 %** | 0.7 % |
| **Yungas** | 1.17 Mha | 176 kha | **15.0 %** | 14.2 % |
| Monte | 9.19 Mha | 54 kha | 0.6 % | 0.2 % |
| Delta e Islas del Paraná | 2.69 Mha | 13 kha | 0.5 % | 0.4 % |

Three things follow.

**Chaco carries 70 % of it**, and there **fire on recently converted land is often real** —
post-deforestation burning of cleared plots is a genuine, reportable phenomenon, so deleting it is
a scientific choice, not a QC fix.

**Yungas is the worst in proportion — 15 % of its burned area on cropland**, more than double
Chaco's rate, and a 0.4 filter takes out 14.2 % of it. It is small in absolute terms (1.17 Mha over
28 years) so it never showed up in the national numbers, but any Yungas panel in the factsheet is
materially affected. This was not on the radar before tonight.

**Espinal and Monte are clean** — 16.31 and 9.19 Mha burned, the 2nd and 3rd largest, at 1.3 % and
0.6 % cropland. So the filter costs almost nothing over most of the burned area of the country.

Together this is the argument for (i) a permissive threshold and (ii) a **region-specific** filter
(§6) — the right threshold in Espinal and in Yungas are plainly not the same number.

*(22 objects / 227 ha fall outside every ecoregion — coastal centroids, negligible.)*

**(c) The dropped objects are small but not tiny.** Median 14.2 ha, p90 87 ha, max 10,704 ha —
i.e. this is not a "small-object" filter in disguise, and a size threshold would not substitute
for it.

### 2.3 The three ways to fix it, and why one is right

| option | what it is | verdict |
|---|---|---|
| **Filter the objects** | one more predicate next to `fire == 1 & area_ha >= 1`; every raster re-derives from it | ✅ **the clean one.** Vector and raster stay identical by construction; it is a statement about *fires we do not map*, which is what our method is defined in terms of |
| Mask the raster products | apply an agriculture mask to the published rasters | ❌ splits the vector layer from the raster layers — a user cross-tabulating the two finds area that is in one and not the other |
| Mask only for the factsheet | leave the products alone, analyse a masked version | ⚠️ fallback only. Valid if we say so explicitly, but it means the factsheet doesn't describe the published map |

**Decision: filter at the polygon level** (Iván). One predicate, applied once, at the only place
where "what we mapped" is defined.

The filter is genuinely three lines, and `frac_agri` is already present on **both** sides — it is a
property of the uploaded `objects_raw_<fy>` FeatureCollections in Earth Engine (verified on FY2020) and a
column of the local `objects_<fy>_derived.csv`:

| file | line | what to change |
|---|---|---|
| `workflow/07-month_of_burn.py` | `accepted_objects()`, ~133 | add `ee.Filter.lt("frac_agri", T)` |
| `workflow/07-calendar_scars.R` | 159 | add `& frac_agri < T` to the `merge(...)[...]` |
| `workflow/07-burned_area_polygons.py` | the same positive selection | idem |

…plus the threshold itself in `utils/constants.py`, and it must be stamped into every asset's
properties so the layer says what it excluded.

---

## 3. What re-runs, under which decision

```
objects_raw_<fy>  (step 06, unchanged — the WHOLE object set stays uploaded)
      │  filter: fire==1 & area_ha>=1  [ & frac_agri < T ]
      ├──────────────► 07a  month_of_burn   (27 Earth Engine tasks)  ── the pivot
      │                        │
      │                        ├── 07d  9 subproducts   (4 of them × PRODUCT_LULC)
      │                        └── 07c  3 scar rasters  (masked to 07a)
      │
      ├──────────────► 07b  local calendar scars (28 + 27 local passes, 27 manual ingests)
      │                        └── feeds 07c
      └──────────────► 07e  burned_area_polygons_v1  (1 Earth Engine task, 3.27 h measured)
```

| decision | must re-run | tasks |
|---|---|---|
| **land cover only** (mandatory, §1) | the four `*_coverage` products | 4 Earth Engine |
| **+ agriculture filter** | 07a, then all 9 of 07d, then 07e | 27 + 9 + 1 Earth Engine |
| **+ keep the size chain exact** | 07b (local + ingest) then 07c | 55 local + 3 Earth Engine |

**The size chain is optional and it is the one to defer** (Iván: not mandatory). Nothing in the
reduced factsheet uses scar size. And because **07c masks the scar rasters to 07a**, re-running
just 07c (3 cheap tasks) after the new 07a already keeps scar **extent** consistent with every
other product; only the `area_ha` / `scar_size_range` *attributes* would be stale — a scar keeps
the size class it had before its cropland part was removed. That is a documentable minor
inconsistency, not a broken product.

Order of priority:

- **A (blocks the factsheet and the platform):** 07a → 07d.
- **B (independent, run in parallel):** 07e. Needed for the fire-count analyses (§5.2) and it is
  the layer early users already have a link to.
- **C (defer, do if the week allows):** 07b → 07c. If it doesn't fit, re-run 07c alone and record
  the attribute caveat in the asset properties.

---

## 4. Feasibility and the critical path

### 4.2 The parallelism ceiling — this is the real constraint

**Earth Engine runs ~2 export tasks at a time per user.** We have two accounts
(`ivanbarbera93@gmail.com`, `ivanbarbera@comahue-conicet.gob.ar`); at the very most we could
borrow a third. So the realistic ceiling is **~4–6 concurrent exports, not 9+**.

27 tasks at 2-per-account therefore means roughly `27 / (2 × accounts)` × per-task-time in serial
rounds. At 4 concurrent: 7 rounds.

**Measured (2026-09-10): a year takes ~58 min** (§4.3), so **7 rounds ≈ 6.5 h at 4 concurrent**,
~13 h at 2. **07a fits comfortably** — launch it in the morning and it lands the same day. The
agriculture filter is therefore affordable, and §2.3's "mask only for the factsheet" fallback is
not needed.

Observed caveat: with one export already running per account, a second submission sat **PENDING**
rather than starting, so treat 2-per-account as an upper bound and the comahue /
`mapbiomas-argentina` project as the less congested lane.

The queue is **per user**, so submitting under the second account starts immediately instead of
queueing behind the first — see CLAUDE.md on passing `--credentials` explicitly rather than
swapping `~/.config/earthengine/credentials`. And `ee.data.listOperations()` is **project-scoped**,
so a watcher must poll both projects or it will report the other account's task as missing.

### 4.3 Timings — all measured

| step | per unit | total |
|---|---|---|
| **07a month of burn** | **~58 min per calendar year** | 27 years ≈ 26 h serial, **~6.5 h at four concurrent** |
| 07e polygon layer | 3.27 h, one task | 3.27 h |
| 07b scars, pass 1 (pixels) | 28 fire-years, 5 workers | 41 min |
| 07b scars, pass 2 | 27 calendar years, 2 workers | 96 min |
| 07b manual upload of the 27 scar files | — | ≤ 30 min |
| territory tagging (local) | ~10 ms per object, 6 cores | ~50 min |

#### Burnable-area benchmark — measured, and the null-geometry bug that ate the first round

Launched 10 Sep to time the denominator (whole country, 13 ecoregions × `veg_fire`, calendar
2020), into `TESTS/burnable_benchmark`.

**All three tasks of the first round failed** — `code 3, "Unable to export features with null
geometry"`. `year_table()` built `ee.Feature(None, …)` and a table ASSET cannot hold a
null-geometry feature. This is the *same* trap already written up in
`07-month_of_burn.py::stats_year()` (trap #1, from the 29 Jul failures) and already worked around
in `validation/01_strata_export.py` — both step-11 scripts reintroduced it. Fixed 11 Sep in
`11-burnable_area.py` **and** `11-burned_area_stats.py` (which had it too, unlaunched) with the
same placeholder point `[-64, -34]` those two use; it carries no meaning.

**The error fires at WRITE time, i.e. after the entire reduction has run.** So the failed tasks
still measured the compute, and the first round is the only clean timing we will ever get:

| task | account | started (UTC) | ran | EECU·s | outcome |
|---|---|---|---|---|---|
| `arg11_burnable_ecoregions13_2020_benchmark` (k=1, 30 m) | gmail | 2026-09-11 00:40:13 (attempt 1) | ~141 min, then GEE retried | — | killed by us at 03:01 → attempt 2, cancelled 04:20 |
| `…_benchmark_k3` (90 m) | comahue | 2026-09-11 00:41:55 | **98.4 min** | 9 292 | FAILED (null geometry) |
| `…_benchmark_k4` (120 m) | comahue | 2026-09-11 02:20:24 | **49.7 min** | 5 183 | FAILED (null geometry) |

> ⚠️ **The re-run is NOT a timing.** Relaunched at 04:20 on 11 Sep, k=3 landed in **37 s** and k=4
> in **41 s** — Earth Engine served the reduction from its **compute cache**, since the identical
> computation had already been evaluated hours earlier and only the write had failed. Any rerun of
> an identical expression within the cache window measures the cache, not the work. To time this
> honestly again you must perturb the expression (a different year, a different territory).
> The cache hit is itself the proof that the first round's failure was purely at write.

**So the earlier "k=3 is not running faster than k=1" note was wrong** — it was read ~55 min in,
before either finished. k=3 (98 min) beat k=1 (≥141 min), and k=4 halved k=3 again. Decimation
*does* buy time on the denominator. Note also that the comahue account ran k=3 and k=4 strictly
serially (k=4 started 5 s after k=3 ended), i.e. **one concurrent slot, not the two §4.2 assumes.**

The k=3 asset reads back sensibly: 184 rows, **250,377,516 ha burnable** for 2020 against a
279.27 Mha country.

#### The idea that makes this whole benchmark moot: ONE fixed burnable layer

*Iván, 11 Sep.* The denominator is expensive because it is recomputed for all 27 years, and the
`veg_fire` layer moves year to year (it is built from the previous year's LULC). But **the number
we report is a percentage, and the burned fraction is small** — single-digit percent nationally.
Perturbing a denominator of that size by the small interannual drift in what counts as burnable
changes the reported `%` in a digit nobody reads.

So: **decide burnable/non-burnable ONCE per pixel, as fixed data — the mode of `veg_fire` across
years** — compute the burnable area on that single frozen layer, and use it as the denominator for
every year. One heavy compute instead of 27, and the series gains a property it does not have now:
year-to-year changes in `%` burned are changes in *fire*, not in the denominator.

Consequences to think through before adopting it (**next session**):

- Which classes the mode collapses, and whether an ecoregion that genuinely converted (Chaco
  clearing) ends up on the wrong side of burnable for half the series. The mode is a *majority over
  28 years*, so a pixel cleared in 2010 stays "burnable" — that is arguably the right call for a
  denominator, but it must be a stated decision, not a side effect.
- It changes only the DENOMINATOR. The numerator (burned area) stays per-year and per-month.
- The per-`veg_fire`-class breakdown still needs a class per pixel; the mode gives one, but
  "burnable area of class 5" then means "of pixels whose modal class is 5".
- Publishability: docs/09's stage-5 CSVs specify burnable = col-2 v8 `veg_fire`, **previous year**
  (§5). A fixed layer is a *deviation from the network spec* and is fine for the factsheet, but
  the platform CSVs may still need the per-year version. Check before replacing, not after.

**For the test, keep it simple: the benchmark stays the single year it was already running (2020).**
The fixed-layer idea is a design change, not a benchmark variant.

#### Burned-area-by-region benchmark — launched 11 Sep 04:23 UTC, result pending

*Iván, 11 Sep:* the assumption baked into this file's header (§ "the half that cannot be decimated
— burned, masked — is the cheap one, because its mask already restricts the sweep") **has never
been measured.** If it is wrong, it is a large problem: the burned numerator is the half that
*cannot* be decimated (`--decimate` is refused without `--from-objects`, because the exported asset
is read off a pyramid level and dilates — §5.1), so there is no lever to pull if it turns out to be
slow.

| task | account | started (UTC) | duration |
|---|---|---|---|
| `arg11_burned_ecoregions13_2020_benchmark` (k=1, 30 m, from the published 07a asset) | comahue | started **2026-09-11 04:27:54** | *fill in* |

First submitted on gmail at 04:23:33 and **cancelled and re-submitted on comahue at 04:27:49**: the gmail queue was already serving the k=1 burnable task and, as §4.2 records, each account gets very few concurrent slots — it would have sat PENDING all night instead of answering the question by morning. Lands in `TESTS/burned_benchmark/`. Read the duration off `startTime → endTime` in
`ee.data.listOperations()` **before it ages out** (a few weeks), and write it into the row above.

**07a does not depend on fire load.** Calendar 2012 (26,930 objects, 0.92 Mha) took 57.8 min;
calendar 2020 (71,753 objects, 4.68 Mha) took 58.8 min — 2.7× the objects for 1.7 % more time.
The cost is the whole-country sweep at 30 m, not the painting, so the big years will not blow up.

**So the remap fits.** Launch 07a in the morning and it lands the same day.

> Earth Engine's `progress` field sat at 0.33–0.37 for most of an hour and then finished. It is
> not linear; never extrapolate from it. Take `startTime → endTime` off the finished task.

### 4.4 Running it unattended over a weekend

The failure mode to design for is **the power going off**, not a disconnection. That kills a tmux
session and this assistant equally, so neither can be part of the plan.

**Earth Engine tasks are not affected.** Once submitted they run on Google's servers and queue
there — observed 10 Sep: tasks sat `PENDING` for 40 minutes while others ran, then started on
their own. So **submit all 27 of 07a up front** and nothing local needs to survive.

**Submit the bulk as the second account.** Measured the same evening:

```
mapbiomas-fire-485203 (shared with the network)   RUNNING 1   PENDING 9
mapbiomas-argentina   (the comahue account)       RUNNING 2   PENDING 1
```

Those 9 pending are mostly other countries'. The shared project is the congested lane. At ~2–3
concurrent overall, 27 years at ~58 min each is **10–13 h** — launched in the morning, 07a lands
that night or early the next day.

**The one real dependency: 07d must not start until all 27 month-of-burn assets exist**, or it
silently builds a partial product from an incomplete collection.

That dependency is a test for an asset's existence, not a judgement, so **cron can do it** — no
assistant, no tmux:

- an entry every 30 min that counts the assets in `C.MONTH_OF_BURN_COL`;
- when the count reaches 27, run `07-subproducts.py --launch` **once**, then remove its own
  trigger (a marker file next to the log is enough);
- log to a file so the outcome is readable on return.

**Why cron and not something else:** it is restarted by the machine at boot, so it survives the
power cut that ends every other option here. It needs only the machine to come back up, the
network, and the credentials file already on disk.

Two things to get right when it is written:

- **Count assets, not tasks.** A task list is per-project and shows the whole network's work
  (docs/07 §12.7); an asset count is unambiguous, and it is also the thing 07d actually depends on.
- **Make it fire once.** The launcher already skips existing and in-flight products, so a double
  trigger is harmless — but a marker file makes that a guarantee rather than a reliance.

07e is independent of 07a and can go in the same first submission. 07b/07c are priority C (§3) and
need a person for the manual upload anyway, so they are not part of the unattended path.

### 4.5 Test exports go to `TESTS/`

A new folder `FIRE/COLLECTION-1/TESTS/` holds every timing/benchmark asset, so nothing lands next
to a published product and nothing can be mistaken for one. Delete it wholesale when the September
work is done. (Deletions are Iván's to run — CLAUDE.md.)

Every benchmark task keeps the namespaced description convention (`mob_…`, `arg07d_…`) with a
`_bench` suffix. The compute project is shared with the whole network; never match a task by a
generic name and never touch one we did not launch.

---

## 5. The factsheet analysis plan

The three analyses in `presentations/factsheet-notes.md` split into **two families with completely
different costs**. Recognising the split is what makes the schedule work.

### 5.1 Family A — area and proportion (analyses 1, 2, and the "% burned per month" half of 3)

Pixel-based. Needs the re-exported rasters, and it is a grouped `pixelArea()` reduction over
year × class × territory.

**These are the same six statistics CSVs docs/09 §2.1 already owes the network.** Do not build a
parallel factsheet pipeline — build the stage-5 exports with the ecoregion layer as one of the
territorial cuts and read the factsheet off them. That also unblocks docs/09 open item #1
(the territorial layer), which is listed as blocking everything.

**Numerator** — burned area per calendar year × territory (and × land-cover class, from
`annual_burned_coverage` / `monthly_burned_coverage`). One export gives analyses 1, 2 *and* the
land-cover panel at once.

> **`workflow/11-burned_area_stats.py --from-objects` takes 07a off the factsheet's critical
> path.** Instead of reading the exported month-of-burn asset, it calls 07a's *own*
> `month_of_burn()` to paint the objects on the fly — applying `--agri-max` itself — and reduces
> in the same task. So the factsheet's numbers can come from a **filtered** map in one pass while
> the products are re-exported on their own schedule, instead of waiting for 27 exports to land.
> It is the same function 07a exports, not a re-implementation, so the two cannot drift.
>
> **Verified 2026-09-10**: with no filter it reproduces the published asset *month for month*
> over a Chaco box in 2020 — 22,228.3 ha both ways, every month identical. With `--agri-max 0.4`
> the same box falls to **15,524.1 ha, −30 %** — against 3.4 % nationally (§2.1), which is the
> §2.2b concentration made concrete.
>
> The honest trade: every year repaints, so there is no reusable intermediate and this does not
> make 07a cheaper — it removes an ordering constraint, not work. And a number produced this way
> is **of a map that is not yet published**; label it (§9).

**Denominator — burnable area, per year, per territory.** This is the expensive one: a full-country
30 m reduction × 27 years, and it has no burned-pixel mask to shrink it.

> **Decision (Iván): burnable is defined by `MAPBIOMAS_LULC` = col-2 v8, reclassed through
> `config/veg_fire_remap.csv`, and it is the PREVIOUS year's land cover.** That is what our method
> actually treats as burnable — it is the layer `veg_fire` and therefore the whole SNIC candidate
> set was built from — so it is the only denominator for which "burned / burnable" is internally
> coherent. Do not use col-3 here just because the published `*_coverage` products do; those answer
> a different question ("which *published* land cover burned"). **`veg_fire ∈ 1..23` is burnable;
> 24 `non-burnable` and 25 `non-observed` are excluded, and `non-observed` does NOT count toward
> the burnable denominator.**

Note the consequence and state it in the factsheet footnote: **the numerator is calendar-year and
the denominator is previous-year land cover**, matching how the map itself was built.

> ⚠️ **Decimation is safe on the denominator and WRONG on the numerator — and wrong silently.**
> The symmetry is tempting and it does not hold. Measured over a Chaco box, calendar 2020:
>
> | | k=1 (truth) | k=3 (~90 m) | k=4 (~120 m) |
> |---|---|---|---|
> | burned, reading the **exported asset** | 22,228.3 ha | 25,353.5 ha **(+14.1 %)** | **(+36.2 %)** |
> | burned, **painted on the fly** (`--from-objects`) | 22,228.3 ha | 22,185.2 ha (−0.19 %) | (−0.37 %) |
> | burnable (space-filling land cover) | — | +0.003 % | +0.015 % |
>
> The month-of-burn asset is stored with `pyramidingPolicy={burned_monthly: "mode"}` (07a), and
> **mode ignores masked pixels** — so at a coarse pyramid level a block containing a single
> burned pixel comes back burned and the sparse burn mask **dilates**. Land cover does not
> suffer it because every pixel has a class, so mode is a real majority.
>
> **The rule: decimation is safe on a SPACE-FILLING layer, unsafe on a SPARSE MASKED one.** That
> falls the right way — the expensive half (burnable) can be decimated, and the half that cannot
> (burned) is the cheap one, because its mask already restricts the sweep.
>
> The caution generalises: **any** coarse read of our published burned-area rasters over-reports
> — a quick whole-country `reduceRegion` at 500 m as a sanity check, a Looker cross-check, or
> anything else that lands on a pyramid level. Worth raising with the network (§10.2), and worth
> checking what the platform's own displayed statistics do. `11-burned_area_stats.py` now
> **refuses** `--decimate > 1` without `--from-objects`.

Cost is unmeasured — a timing test on one year is running alongside the 07a benchmark. If it is
too slow at 27 years × 13 ecoregions, the fallbacks in order are: (i) reduce over the ecoregion
raster in one pass instead of per-feature, (ii) accept a 2-3 year subsample for the *map* panel
while keeping the national number at full resolution, (iii) compute burnable once per 5 years and
interpolate (it changes slowly) — **flagging it**, since the user asked for native resolution.

### 5.2 Family B — fire counts (n fires ≥ 10 ha by month and region)

**This needs no Earth Engine and no re-export at all.** It is the local object CSVs
(`objects-pred/` + `objects-raw/*_raster_metrics.csv`) plus the `objects-raw/*.gpkg` geometries,
spatially joined **once** to the ecoregion layer in R/`sf`.

- 607,164 objects at `area_ha ≥ 10` (574,493 after a 0.4 agriculture filter).
- An `sf` join of that against 13 polygons is minutes, not hours.
- Re-tagging under a different threshold is then a `filter()` call — **so this family is
  threshold-agnostic and can be built today**, before any export finishes.
- Per `factsheet-notes.md`: the count is on the **fire-year** object database, month = month of
  `date_median`, and an object is counted in **every** region it intersects (double counting is
  accepted and intended).

That is the schedule's slack: the expensive half is work we owe the network anyway, and the cheap
half is available immediately.

## 6. Choosing the threshold — the Earth Engine explorer

**Decision (Iván): the threshold is chosen by eye, with Camilo, from a Code Editor script.** Built
in the `fuego` repo (`mapbiomas-arg-fire-gee`, `collection-01/visualization-misc/`), pushed to
`master`. Requirements:

1. **Both regionalisations, side by side**, so we can see whether the filter behaves differently by
   region: **Burkart 13 ecoregions**
   (`ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_2-13Ecorregiones_3857`, `LEVEL_2` = name,
   `GEOCODE` = 1..13) and the **MapBiomas Argentina regions**
   (`ANCILLARY_DATA/VECTOR/ARG/ARG-Regiones-MapBiomas-buffer2km`, 5 features:
   Pampas / Bosque Atlantico / Puna,Monte y Altos Andes / Patagonia / Chaco).
2. **A region-specific filter option** — one threshold per region rather than one national
   threshold. §2.2b is the reason: Chaco carries 85 % of the affected cropland area and its
   land-clearing fire is partly real.
3. **Single-year *and* multi-year views.** A single year shows whether an individual scar is
   plausible; all years together often make the cropland pattern obvious (regular rectangles,
   field boundaries, annual repetition) in a way one year does not.
4. **Alternatives selectable in the explorer**, not hard-coded: at least `frac_agri` alone vs
   `frac_agri + frac_past`, and the threshold itself.

> If one script becomes a blob, split it in two — `…_single_year` and `…_multi_year`. Prefer two
> readable scripts over one with a mode switch nobody remembers.

Note for the reading: **pasture is a separate question.** `frac_agri + frac_past ≥ 0.4` would drop
5.78 Mha (8.4 %) instead of 2.36 Mha, and pasture fire is largely genuine management burning. It is
in the explorer as an option, but the prior is agriculture only.

---

## 7. Decisions on record

| # | decision | who / when |
|---|---|---|
| 1 | Fix agriculture by **filtering objects**, not by masking rasters (§2.3) | Iván, 2026-09-10 |
| 2 | **`_coverage` re-export is mandatory** regardless (new land cover, §1) | 2026-09-10 |
| 3 | The **size chain (07b/07c) is not mandatory** for the factsheet; defer it (§3) | Iván, 2026-09-10 |
| 4 | Threshold chosen **visually**, with Camilo, from a Earth Engine explorer; region-specific and multi-year options included (§6) | Iván, 2026-09-10 |
| 5 | **Burnable = col-2 v8 (`MAPBIOMAS_LULC`) reclassed to `veg_fire`, previous year** (§5.1) | Iván, 2026-09-10 |
| 6 | Benchmarks and timing tests go to a **`TESTS/` asset folder** (§4.4) | Iván, 2026-09-10 |
| 7 | Manual ingest of the 27 annual scar assets costs **≤ 30 min**, not half a day | Iván, 2026-09-10 |

---

## 8. What is already computed

### The national series and the month curve — no compute needed

`CLASSIFICATION_COLLECTIONS/mob_month_stats` already holds **27 assets** — the whole-country
per-month burned **pixel count** for 1999–2025, exported as 07b's cross-check. So the national
time series (analysis 2) and the national pirogram (analysis 3) exist *today*:

```bash
$PYTHON collection-01/workflow/07-month_of_burn.py --all --stats-read     --csv collection-01/data/objects-analysis/national_month_pixels.csv
```

All 27 years still report `MATCH` against the local month counts.

**National series, relative to the series mean (=100):** 2001 is the biggest year at **213 %**,
2012 the smallest at **35 %** — a **6.2×** range. 2020 (177 %) and 2022 (162 %) are the recent
peaks; 2010, 2012, 2014, 2015 the quiet years.

**National pirogram, share of all burned pixels by month:** **bimodal** — a late-winter/spring
peak in **Aug (18.2 %) / Sep (16.4 %) / Oct (9.6 %)** and a second summer peak in
**Jan (14.6 %) / Dec (10.1 %) / Feb (7.7 %)**, with a March–June trough (1.6–3.6 %). That is two
different fire regimes showing up in one national curve — Chaco late winter, Patagonia/Pampa
summer — which is an argument for the per-region panels the factsheet already plans, and for
plotting the x-axis May→April so neither peak is cut.

### ⚠️ Two things these numbers are not

1. **They are pixel counts, and × 0.09 ha is wrong by 18.5 %.** The lattice step is
   0.000269494585236 **degrees**, so a pixel is ~30 m north–south everywhere but ~30·cos(lat) m
   east–west. Naive conversion gives **81.93 Mha where the object database says 69.12** — a mean
   effective pixel of **0.0759 ha** (lat ≈ 32°). Worse, the bias is not uniform by month:
   Patagonian fires (≈0.064 ha/px) peak in summer and Chaco fires (≈0.082 ha/px) in late winter,
   so the **pirogram's shape is skewed toward the summer months**. Use these for *relative*
   structure only; hectares come from `11-burned_area_stats.py`, which sums `pixelArea()`.
2. **They describe the current, unfiltered map** — no agriculture filter.

### A pixel count that looked wrong, and was not

Summing the 27 histograms gives **910,290,670 px**, where docs/07 **§2** says **910,559,713**.
I flagged that as an open discrepancy. **It is not one, and the mistake was mine**: §2's figure
is an *intermediate* line — accepted pixels minus calendar 1998 — and docs/07 **§8** already
carries the full reconciliation, including the step I thought was missing:

```
  accepted object px (28 fire-years)     911,617,919
  − calendar 1998, not published           1,058,206
  = inside the published series          910,559,713     <- §2 quotes THIS line
  − intra-year reburn, deduped               269,043
  = expected calendar px                 910,290,670     <- what the asset contains
```

Re-derived independently tonight from the local pixel cache, as the overlap between the two
fire-year contributions to each calendar year: **269,043 px — exact to the pixel.** Big fire
years dominate it (calendar 2000 alone contributes 40,300); quiet years give a few hundred.

Two useful by-products of having checked:

- **Per-year, the local union equals the published raster's count exactly** — calendar 1999,
  33,456,607 px; calendar 2020, 59,759,246 px; both identical to `mob_month_stats`. The local
  pixel set and the Earth Engine product agree year by year, not just in total.
- The right national pixel total for anything quoted from the products is **910,290,670**, and
  the reason a pixel can be "mapped twice but published once" — reburn across two fire-years
  inside one calendar year, where `max` keeps the later month — is worth one sentence in the
  methods document.

### Fire counts per region

`factsheet_region_summary_min10ha.csv`, fires ≥ 10 ha, 28 fire-years, `_multi` tags:

| ecoregion | fires/yr | ha/yr | fires/yr per 10,000 km² | median fire |
|---|---|---|---|---|
| Chaco | 8,556 | 1,049,323 | 131.7 | 30.3 ha |
| Espinal | 3,877 | 676,975 | 129.8 | 25.7 ha |
| Pampa | 5,768 | 207,882 | **145.6** | 21.6 ha |
| Monte | 562 | 415,620 | 12.0 | 26.5 ha |
| Campos y Malezales | 1,429 | 98,925 | **533.1** | 25.7 ha |
| Delta e Islas del Paraná | 871 | 110,967 | 155.2 | 25.7 ha |
| Yungas | 403 | 48,079 | 84.6 | 26.0 ha |
| Estepa Patagónica | 96 | 51,209 | 1.8 | 28.9 ha |

Two things worth a panel. **Campos y Malezales has by far the highest fire *density*** — 533
fires/yr per 10,000 km², four times Pampa's — while contributing under 100 kha/yr: many small
fires, a completely different regime from Monte, which burns four times the area with a
fifteenth of the density. And **Monte is the clearest "few but large" case** (12 fires/yr per
10,000 km², 415 kha/yr). That contrast — density vs area — is a better regional story than
either variable alone, and it is exactly what factsheet-notes.md's "relativizar por área"
question was reaching for.

`factsheet_counts_by_month_min10ha.csv` (5,377 rows: layer × region × fire-year × month) is the
pirogram's count axis, ready to plot.

## 9. Open — the Pampa problem

The easy move for analysis 1's land-cover panel is **simply not to show agriculture**. But that leaves a
worse question unanswered: **what do we say about burned area in the Pampa?**

The Pampa is largely cropland. If we do not correct it, the honest caption is close to *"here is our
number, but don't believe it, it's overestimated"* — which is not a thing to put on a factsheet. If
we do correct it (object filter + not showing the class), the Pampa's total is still built partly on
residual cropland pixels (§2.2a).

Candidate framings, none settled:

- **Report the Pampa on non-agricultural land only** — burned area over natural and semi-natural
  classes, with the denominator restricted the same way. Coherent, defensible, and it makes the
  ratio meaningful; the cost is that the absolute number stops being "burned area in the Pampa".
- **Report both numbers** — total mapped, and the natural/semi-natural subset — and let the gap be
  the story ("most of what burns in the Pampa is cropland residue, which our method cannot separate
  from stubble management").
- **Say it is an upper bound** and give the validation-based error-adjusted estimate instead
  (docs/10) — the right answer scientifically, but the validation is not finished and cannot be by
  the 16th.
- **Drop the Pampa panel** from the reduced factsheet and keep it for the December Bariloche
  launch, where there is room to explain it.

It is legitimate for the factsheet to show something that is not a straight read of the platform
(e.g. *"we removed fires occurring predominantly on cropland, which nevertheless appear in the
maps"*) — we just have to be explicit. **This needs a decision before the 16th.**

---

## 10. What to ask the Brazil / platform team — tomorrow

### 10.1 How the asset → platform route actually works, and why they must copy

Updating our assets **does not update the platform.** There are two distinct asset trees:

```
ours (we write)                                     public (Brazil writes)
projects/mapbiomas-argentina/assets/FIRE/           projects/mapbiomas-public/assets/
  COLLECTION-1/FINAL_PRODUCTS/…              ──►      argentina/fire/collection1/…
                                     copyAsset
                                     setAssetAcl({all_users_can_read: true})
                                     setAssetProperties({data_type, band_format, version})
```

The copy is `ToPublish/2-toAsset-Public` in the network's reference repo, and **Brazil owns that
step** ("para garantizar parámetros necesarios", docs/09 §3). The platform then reads the *public*
copy: the Workspace subtheme form's key field is a **`Earth Engine Asset ID` pointing at
`projects/mapbiomas-public/...`**, and the `data_type` / `band_format` / `version` properties tell
it how to interpret the bands (docs/09 §4).

Consequences:

- **Re-exporting `FINAL_PRODUCTS` changes nothing the public sees** until Brazil re-copies.
- There is a **second destination**, the Cloud-Storage COGs
  (`ToPublish/1-toBucket-subproducts` → `gs://shared-development-storage/…/COLLECTION1/temp/…`),
  which appear to serve the **downloads page**, not the map. Those would need regenerating too.
- Workspace registration points at an asset **ID**. If the ID changes, the registration has to
  change with it.

### 10.2 The questions

1. **What is the last date we can hand you updated assets** and still have them on the platform for
   24 September? (This, not the 24th, is our real deadline — §4 hangs off it.)
2. **If we re-export in place (same asset IDs), does the copy just have to be re-run**, or does
   anything in Workspace / the legends / the subtheme registration have to be redone?
3. **Should we bump the version — `…_v2` instead of `…_v1` — from now on?** A new ID is cleaner
   (the old one stays readable, nothing is overwritten mid-flight, and the `version` asset property
   stops lying), but it changes the `Earth Engine Asset ID` registered in Workspace and every download link.
   Ask which they prefer; **do not decide this unilaterally**, because `C.product_name()`'s
   `version=1` default and the platform's `band_format` lookup both encode it.
4. **The statistics CSVs / tables** (docs/09 §2.1, the six `toDrive-area-*` exports): have any been
   produced or loaded into Looker Studio yet for Argentina? If yes, **they were computed on the
   preliminary land cover and on the unfiltered map and must be recomputed** — who runs them, and by
   when? Is there anything else already generated downstream of our assets that a re-export
   silently invalidates?
5. **The COGs / downloads page** — do they need regenerating alongside the asset copy, and who does
   that?
6. **The territorial layer** (docs/09 §2.2, still ours to build and listed as blocking everything):
   confirm the format they need and whether the 13 Burkart ecoregions can be one of the cuts.
7. **Do any platform-side or Looker statistics read our burned-area rasters at a coarser scale
   than 30 m?** If so they are over-reporting — the `mode` pyramid dilates a sparse burn mask,
   measured at **+14 % at 90 m and +36 % at 120 m** (§5.1). This affects every country whose
   burned-area products are sparse masked rasters, not just ours, so it is worth raising with
   the network rather than only fixing on our side.

---
