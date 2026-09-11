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

---

## 1. Some products must be re-exported anyway — the LULC was preliminary

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

> **Only the four `*_coverage` products read LULC.** `07-subproducts.py:360` already stamps
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
disappear) but does **not** make a per-LULC-class pixel statistic clean. That is the tension §5.3
and §8 have to resolve, not something the threshold can fix.

**(b) It is mostly Chaco, not Pampa.** Of the ~1.58 Mha of cropland pixels inside the objects a
0.4 filter would drop:

| | area |
|---|---|
| `agriculture_chaco` | **1,337 kha** |
| `agriculture_pampa` | 216 kha |
| `agriculture_cuyo-pat` | 26 kha |

This matters. In Chaco, **fire on recently converted land is often real** — post-deforestation
burning of cleared plots is a genuine, reportable phenomenon, and deleting it is a scientific
choice, not a QC fix. In Pampa the same filter is much closer to pure commission-error removal.
That asymmetry is the argument for (i) a permissive threshold and (ii) trying a **region-specific**
filter (§6).

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
property of the uploaded `objects_raw_<fy>` FeatureCollections in GEE (verified on FY2020) and a
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
      ├──────────────► 07a  month_of_burn   (27 GEE tasks)  ── the pivot
      │                        │
      │                        ├── 07d  9 subproducts   (4 of them × PRODUCT_LULC)
      │                        └── 07c  3 scar rasters  (masked to 07a)
      │
      ├──────────────► 07b  local calendar scars (28 + 27 local passes, 27 manual ingests)
      │                        └── feeds 07c
      └──────────────► 07e  burned_area_polygons_v1  (1 GEE task, 3.27 h measured)
```

| decision | must re-run | tasks |
|---|---|---|
| **LULC only** (mandatory, §1) | the four `*_coverage` products | 4 GEE |
| **+ agriculture filter** | 07a, then all 9 of 07d, then 07e | 27 + 9 + 1 GEE |
| **+ keep the size chain exact** | 07b (local + ingest) then 07c | 55 local + 3 GEE |

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

### 4.1 The unknown that gates everything

**07a's per-year runtime is recorded nowhere.** It is the dominant cost (painting up to ~72 k
polygons over the whole country at 30 m, twice per calendar year) and it is 27 of them. Until it is
measured, every schedule below is a guess.

**Benchmark, launched 2026-09-10:** two calendar years spanning the range, exported to a **TESTS
folder** so nothing production is touched:

```
FIRE/COLLECTION-1/TESTS/month_of_burn_benchmark/…_{2012,2020}_benchmark
```

| benchmark year | objects painted (approx., both contributing fire-years) | burned area |
|---|---|---|
| **2012** — low | 26,930 | 0.92 Mha |
| **2020** — high | 71,753 | 4.68 Mha |

2.7× in object count, 5× in area — enough to tell whether the cost scales with objects or is
dominated by the fixed country-wide sweep. Run **unfiltered**, deliberately: we do not have a
threshold yet, and an unfiltered run is the conservative upper bound on cost.

### 4.2 The parallelism ceiling — this is the real constraint

**GEE runs ~2 export tasks at a time per user.** We have two accounts
(`ivanbarbera93@gmail.com`, `ivanbarbera@comahue-conicet.gob.ar`); at the very most we could
borrow a third. So the realistic ceiling is **~4–6 concurrent exports, not 9+**.

27 tasks at 2-per-account therefore means roughly `27 / (2 × accounts)` × per-task-time in serial
rounds. At 4 concurrent: 7 rounds. If a year takes 1 h → 7 h (fine). If a year takes 4 h → over a
day (tight, but survivable if launched Friday). If a year takes 8 h+ → the agriculture filter does
not fit before the 16th and we fall back to §2.3's third option for the factsheet.

The queue is **per user**, so submitting under the second account starts immediately instead of
queueing behind the first — see CLAUDE.md on passing `--credentials` explicitly rather than
swapping `~/.config/earthengine/credentials`. And `ee.data.listOperations()` is **project-scoped**,
so a watcher must poll both projects or it will report the other account's task as missing.

### 4.3 Timings we do know

| step | measured | source |
|---|---|---|
| 07e merged polygon export | **3.27 h** | docs/07 §13, 2026-07-31 |
| 07b pass 1 (pixels, 28 fire-years, `-j 5`) | **41 min** | docs/07, run 2026-07-29 |
| 07b pass 2 (scars, 27 calendar years, `-j 2`) | **96 min** | idem |
| 07b manual ingest of the 27 scar zips | **≤ 30 min** (Iván) | — |
| 07a per year | **unknown — being measured** | §4.1 |
| burnable-area reduction per year (§5.1) | **unknown — being measured** | §5.1 |

So the whole size chain is ~2.5 h of compute plus half an hour of clicking. It is not the expensive
part; 07a is.

### 4.4 Test exports go to `TESTS/`

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

**Numerator** — burned area per calendar year × territory (and × LULC class, from
`annual_burned_coverage` / `monthly_burned_coverage`). One export gives analyses 1, 2 *and* the
LULC panel at once.

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

Cost is unmeasured — a timing test on one year is running alongside the 07a benchmark. If it is
too slow at 27 years × 13 ecoregions, the fallbacks in order are: (i) reduce over the ecoregion
raster in one pass instead of per-feature, (ii) accept a 2-3 year subsample for the *map* panel
while keeping the national number at full resolution, (iii) compute burnable once per 5 years and
interpolate (it changes slowly) — **flagging it**, since the user asked for native resolution.

### 5.2 Family B — fire counts (n fires ≥ 10 ha by month and region)

**This needs no GEE and no re-export at all.** It is the local object CSVs
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

### 5.3 The one place the two families collide

Analysis 1's **per-LULC-class** panel is Family A (pixels) but the agriculture problem is
object-level (§2.2a). After a 0.4 filter, ~1.37 Mha of cropland pixels remain in the map, so a
class table will still show agriculture burning. Options in §8.

---

## 6. Choosing the threshold — the GEE explorer

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
| 2 | **`_coverage` re-export is mandatory** regardless (new LULC, §1) | 2026-09-10 |
| 3 | The **size chain (07b/07c) is not mandatory** for the factsheet; defer it (§3) | Iván, 2026-09-10 |
| 4 | Threshold chosen **visually**, with Camilo, from a GEE explorer; region-specific and multi-year options included (§6) | Iván, 2026-09-10 |
| 5 | **Burnable = col-2 v8 (`MAPBIOMAS_LULC`) reclassed to `veg_fire`, previous year** (§5.1) | Iván, 2026-09-10 |
| 6 | Benchmarks and timing tests go to a **`TESTS/` asset folder** (§4.4) | Iván, 2026-09-10 |
| 7 | Manual ingest of the 27 annual scar assets costs **≤ 30 min**, not half a day | Iván, 2026-09-10 |

---

## 8. Open — the Pampa problem

The easy move for analysis 1's LULC panel is **simply not to show agriculture**. But that leaves a
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

## 9. What to ask the Brazil / platform team — tomorrow

### 9.1 How the asset → platform route actually works, and why they must copy

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
copy: the Workspace subtheme form's key field is a **`GEE Asset ID` pointing at
`projects/mapbiomas-public/...`**, and the `data_type` / `band_format` / `version` properties tell
it how to interpret the bands (docs/09 §4).

Consequences:

- **Re-exporting `FINAL_PRODUCTS` changes nothing the public sees** until Brazil re-copies.
- There is a **second destination**, the Cloud-Storage COGs
  (`ToPublish/1-toBucket-subproducts` → `gs://shared-development-storage/…/COLLECTION1/temp/…`),
  which appear to serve the **downloads page**, not the map. Those would need regenerating too.
- Workspace registration points at an asset **ID**. If the ID changes, the registration has to
  change with it.

### 9.2 The questions

1. **What is the last date we can hand you updated assets** and still have them on the platform for
   24 September? (This, not the 24th, is our real deadline — §4 hangs off it.)
2. **If we re-export in place (same asset IDs), does the copy just have to be re-run**, or does
   anything in Workspace / the legends / the subtheme registration have to be redone?
3. **Should we bump the version — `…_v2` instead of `…_v1` — from now on?** A new ID is cleaner
   (the old one stays readable, nothing is overwritten mid-flight, and the `version` asset property
   stops lying), but it changes the `GEE Asset ID` registered in Workspace and every download link.
   Ask which they prefer; **do not decide this unilaterally**, because `C.product_name()`'s
   `version=1` default and the platform's `band_format` lookup both encode it.
4. **The statistics CSVs / tables** (docs/09 §2.1, the six `toDrive-area-*` exports): have any been
   produced or loaded into Looker Studio yet for Argentina? If yes, **they were computed on the
   preliminary LULC and on the unfiltered map and must be recomputed** — who runs them, and by
   when? Is there anything else already generated downstream of our assets that a re-export
   silently invalidates?
5. **The COGs / downloads page** — do they need regenerating alongside the asset copy, and who does
   that?
6. **The territorial layer** (docs/09 §2.2, still ours to build and listed as blocking everything):
   confirm the format they need and whether the 13 Burkart ecoregions can be one of the cuts.

---

## 10. Log

| date | what |
|---|---|
| 2026-09-10 | Doc created. Measured the agriculture numbers (§2); verified the `_pb` LULC lattice (§1). |
| 2026-09-10 | **Built and committed** — see the table below. Benchmarks launched to `TESTS/`; territory tagging launched locally. |

### 10.1 What exists now

| what | where | state |
|---|---|---|
| Threshold explorers (single-year + multi-year) | `fuego` repo, `collection-01/visualization-misc/explore_agri_filter_*` | ✅ pushed — **this is the thing to open with Camilo** |
| The agriculture filter itself | `07-month_of_burn.py --agri-max T` | ✅ wired, default OFF, stamped into the asset's `agriculture_filter` property. Still to add at the other two filter points (§2.3) once the threshold is fixed |
| Benchmark plumbing | `07-month_of_burn.py --out-collection/--suffix/--credentials` | ✅ — timing runs land in `TESTS/`, never next to a product |
| **Burnable area** (the denominator) | `workflow/11-burnable_area.py` | ✅ written, ROI-checked. Whole-country timing pending |
| **Burned area** (the numerator) | `workflow/11-burned_area_stats.py` | ✅ written, ROI-checked (Chaco 2020: 22,228 ha, Aug–Sep peak). Reduces the **month-of-burn collection**, so it is indifferent to which subproducts have been re-exported |
| Object → territory tags | `scripts/objects_region_tag.R` | 🔄 running, ~1–1.5 h for 28 fire-years on 6 cores |
| **Family B tables** (fires × territory × month) | `scripts/factsheet_object_stats.R` | ✅ written, smoke-tested; blocked only on the tags |

### 10.2 Measurements taken today

| thing | result |
|---|---|
| `--decimate` on the burnable denominator | On a fragmented Chaco box, total burnable moves **+0.003 % at K=3 (90 m)**, **+0.015 % at K=4 (120 m)** — but small fragmented classes break at K=4 (`forest-inund` −36 %, `grassland-inund` −26 %; at K=3, −5 % and −1 %). **K=3 is a usable fallback for aggregates; K=4 is not safe per class.** |
| Territory tagging cost | ~10–15 ms per object, ~1–1.5 h for all 1.69 M on 6 cores. `st_intersects`, **not** `st_within`, on the centroids: identical answer for a point, 2.4 s vs 23.4 s per 2,000 objects (34 min vs 5.5 h over the collection) |
| GEE concurrency, observed | With one export running per account, a second submission sat **PENDING**. The shared `mapbiomas-fire-485203` project is congested with the rest of the network, so the comahue / `mapbiomas-argentina` project is the better lane for our batch — §4.2's ceiling is real |
| 07a per-year runtime | **still unmeasured.** GEE's `progress` field sat at 0.33–0.35 between minute 17 and minute 36; it is not linear and must not be extrapolated. Take `startTime → endTime` off the finished task |

### 10.3 Two traps caught (both would have been silent)

1. **GEE's geojson export writes some territories as `GEOMETRYCOLLECTION`**, and casting them to polygons **splits the feature into one row per polygon** — ecoregion 9 (Pampa) came back as 2 rows. Every Pampa fire would have been listed twice in the `_multi` tags and every per-region count inflated, with nothing in the output saying so. `objects_region_tag.R` now dissolves back and asserts one row per `region_id`.
2. **A partial tag set silently rescales every regional number.** `merge()` just drops the untagged fire-years, so running the Family B tables while tagging is still going returns numbers scaled down by the fraction of years present. `factsheet_object_stats.R` now refuses to write instead.
