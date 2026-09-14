# ROADMAP

**What to do next, in order.** This file is the *when*; `collection-01/docs/NN-*.md` are the *how*.
Read it at the start of every session, before planning anything.

**How to use it**

- Work top-down. `Now` is in flight, `Next` is ordered and its blockers are named, `Later` is
  scheduled but not yet startable.
- Each item says whether it is **run** (execute what exists) or **edit → run** (code must change
  first). That distinction is the whole point of the file — several things below look like a re-run
  and are not.
- **Update this file as you go**: tick an item when it lands, and delete it on the next pass. Git
  history is the archive; a long done-list costs every future session context it could spend on the
  work.
- [`BACKLOG.md`](BACKLOG.md) is the *unscheduled* pile, per topic, with the post-mortems. An item
  moves BACKLOG → ROADMAP when it is scheduled, never the other way.

**Dates.** MapBiomas Argentina col-3 (with fire col-1) launches **24 Sep 2026**. The factsheet is
drawn by graphic designers, so its **data is due ~Wed 16 Sep**. Ideally, assets sould be ready 
at **15 Sep 2026** for Brazil to copy them to `mapbiomas-public`.

---

## Now — the statistics toolkit, in Python, and the one big table

> **Goal: have real numbers to analyse for the factsheet tomorrow (Wed 16 Sep).** Everything in
> this section is local Python + one GEE export. Nothing here waits on a product asset.

**The decision that reorders the whole file (14 Sep 13:00).** The nine subproducts (07d) were
launched at 00:21 and **cancelled at 13:05** with one task 12 h in at 36 %. They are not on the
path to any number we report:

- **D1 — the master table, and the only one the `%` metric may use — reads the month-of-burn
  collection directly** (`month·100 + lulc_col3(year−1)`, `unmask(0)`), crossed with col-3 LULC.
  Month-of-burn is **27/27, done**. docs/09 §5.1.
- **Every factsheet number is a `group_by` on D1**, except the fire counts, which come from the
  **local** object database (`objects-pred/`, `objects-raw/*_raster_metrics.csv`, the `.gpkg`) and
  never touch Earth Engine at all. docs/09 §9.
- The nine feed **D2**, the network's six platform CSVs — and only **five** of them do
  (`*_coverage` ×4 + `year_last_fire`). That is critical-path item 6, **publication**, not analysis.

So 07d blocks Brazil copying assets; it does not block us. It is now the **"After"** section below.
`A2` is paused in the supervisor (`logs/v2-driver/A2.pause` — delete that file to resume; the board
shows ⏸ and prints the reason). The nine were cancelled cleanly: 9/9 confirmed `CANCELLED`, nothing
else left PENDING or RUNNING in `mapbiomas-argentina`.

### What exists already — 14 Sep 13:10

| What | Where | State |
|---|---|---|
| **Month-of-burn rasters** (07a) | `collection1_fire_mask_v2/…_<year>` | ✅ **27/27**, all carrying the current rule A. 2002 landed 00:16. **This is D1's only input besides LULC.** |
| **Fire-object polygon layer** (07e) | `FINAL_PRODUCTS/burned_area_polygons_v2` | ✅ exported, `--verify` green on all 28 fire-years, `--set-props` written. **1,012,648 rows / 63,328,585 ha** |
| **Calendar scar packages** (07b, local) | `data/scars-upload-cache/` | ✅ 27 zips, 739 MB, gate green — **awaiting the manual ingest ("After")** |
| **The nine subproducts** (07d) | `FINAL_PRODUCTS/` | ⛔ **cancelled 14 Sep 13:05**, 0/9. Paused, see "After" |
| **The three scar rasters** (07c) | `FINAL_PRODUCTS/` | ⛔ gated on the ingest — "After" |

Everything is **`_v2`, replaced in place**. There is no `_v3`; the asset paths and
`C.PRODUCT_VERSION = 2` do not change. (Why v2 was rebuilt at all: the first run shipped an
unconfined rule A that deleted two thirds of the Delta del Paraná. Fixed in 8032aa2 — rule A now
also requires `area_ha < 150` and intersection with `config/rule_a_aoi.geojson`. Settled; docs/07
§1.1 and `git log`.)

**The area total is confirmed twice, independently — do not re-derive it.** The local scar build
(pure R, never touches Earth Engine) totals **63.24 Mha**; 07e's `--verify` on the landed asset
reports `area per OBJECT` = **63.33 Mha**. The gap is fire-year vs calendar-year partitioning, as
expected. **When reading 07e's `--verify`, never quote the ROW sum** (68,447,098 ha) — vertex-split
parts are one row each, and object `2000_57529` alone over-counts by 5.1 Mha.

### The route changed: Python, not a fork of their JavaScript

**[docs/09 §3](collection-01/docs/09-statistics.md) is superseded and must be rewritten as the
first task below.** It specifies forking the network's `2-Statistics/toolkit/v03/core/` into the
`fuego` Code Editor repo and patching `scale` → `crs` + `crsTransform` in JavaScript. We are
instead writing **a Python translation of that toolkit** in this repo. Reasons, on record:

- The analysis is ours and already lives here, in Python and R (docs/09 §9 — **we do not use Looker
  Studio**). A JS toolkit in a separate repo puts the one artefact the factsheet depends on behind a
  Code Editor round-trip, at the point in the calendar where that costs the most.
- Everything it needs is already a Python constant — `MONTH_OF_BURN_COL`, `PRODUCT_LULC`,
  `SNIC_CRS`/`SNIC_TRANSFORM`, `product_name()` — in `collection-01/utils/constants.py`. The JS
  route's first task was *copying those into a second source of truth* and keeping them in sync.
- It is a translation, not a redesign. **The method is still theirs** and the shape that makes it
  fast is not ours to change (docs/09 §2): the cross-tab lives in the pixel value, territory is one
  painted raster and never an intersected vector, the reduction geometry is a `bounds()` rectangle,
  no `tileScale`, all years in one task.

Keep the annotation discipline the JS plan had: mark every place the translation **diverges** from
their `core/`, because the `crs` + `crsTransform` change is one we owe back to Brazil.

### The work

- [ ] **Rewrite [docs/09 §3](collection-01/docs/09-statistics.md) for the Python route.** *(edit)*
      Replace the fork-their-`core/` plan with the module layout below, and delete the JS path
      rather than leaving both — a losing alternative left in the docs is the next person's trap.
      Keep §3.2 (**pin `crs` + `crsTransform`, never `scale: 30`**) verbatim; it is the one piece of
      §3 that survives unchanged, and it is the whole reason the fork existed.
- [ ] **Build `collection-01/statistics/` (Python).** *(edit)* A translation of their `core/`:
      `datasets.py` (D1 first: one band per calendar year, `month·100 + lulc_col3(year−1)`,
      `unmask(0)`, uint16 — docs/09 §5.1), `territories.py` (paint the `Stats-Arg_*` vectors and
      **pack** as `ecoregion16·100000 + GEOCODE`; packing instead of intersecting is what removes
      the sliver problem — docs/09 §4.3, and the 16 ecoregion names are **hand-written**, the
      asset's are Latin-1 damaged — §4.2), `calculate.py` (the grouped area reduction, on the pinned
      grid), `legends.py` (col-3 `nivel0/1/2` + the burnable class list — docs/09 §6).
- [ ] **Export D1 × ecoregión first, and run verification gates 1, 2, 4 and 5**
      ([docs/09 §8](collection-01/docs/09-statistics.md)) before anything else is exported. It
      answers the whole factsheet and it is the cheapest thing to be wrong about.
      **`unmask(0)` is load-bearing** — it is what makes one table carry numerator *and*
      denominator; a D1 without it silently cannot answer "% of grassland that burned".
- [ ] **Download the big CSV.** That is the deliverable of this section: the table the next two
      sections read. If the reduction is slow — it should not be, it is two stored byte reads, a
      multiply and an add on one lattice — the escape hatch in docs/09 §5.1 is to materialise D1 as
      **one 27-band uint16 asset** with a pixel-wise `Export.image.toAsset` and reduce that.
      **Do not go back to a hand-written reducer.**
- [ ] **Then export D1 × ecoregión_departamento.** The finer cut, same table shape, once the coarse
      one is verified.

## Next — the factsheet datasets

From the big table and the local vectors. No Earth Engine.

- [ ] **Regenerate the local fire-count tables under the final filters.** *(run)* The object
      selection changed, so `factsheet_region_summary_min10ha.csv` and
      `factsheet_counts_by_month_min10ha.csv` are stale. Local `sf`/R only, minutes.
- [ ] **Build the three analyses** from the D1 CSV + the count tables —
      [docs/09 §9](collection-01/docs/09-statistics.md), content plan in
      `collection-01/presentations/factsheet-notes.md`: mean annual burned proportion; the time
      series and its GAM trend; the pirogram (area half from D1, **count half from the objects**).
- [ ] **State the two divergences in the footnote.** Rasters assign calendar year and month **per
      pixel** from `abs_date`; the count side assigns **per object** from `date_median`. So a fire
      straddling 31 December is split in one and not the other, and "area burned in month M" is a
      pixel sum in D1 and a whole-object assignment in the counts. Acceptable — say it out loud.

## Then — the factsheet plots

- [ ] **Draw the plots** off those datasets (`scripts/factsheet_plots.R`,
      `factsheet_plot_functions.R`; the temporal-shape panels are already comparable across regions,
      ccc0f08). Data is due to the designers **~Wed 16 Sep**.
- [ ] **Decide what the factsheet says about the Pampa.** Still open, and it needs a call before the
      16th. The Pampa is largely cropland; after the filters its total is still built partly on
      residual cropland pixels (1.37 Mha nationally at `T_AGRI = 0.4`). Candidate framings: report
      it on non-agricultural land only (restricting the denominator the same way); report both and
      make the gap the story; call it an upper bound; or drop the panel and keep it for the December
      Bariloche launch. It is legitimate to show something that is not a straight read of the
      platform — but it has to be said out loud.

## After — finish the v2 product exports

Publication, not analysis. Picks up exactly where 14 Sep 13:05 left it.

- [ ] **Ingest the 27 calendar-scar packages by hand.** *(Iván)* They are built and gated, in
      `collection-01/data/scars-upload-cache/` — which is a symlink into the Insync store, so the
      real path is
      `/home/ivan/Insync/MapBiomas/mapbiomas-arg-fire-store/collection-01/data/scars-upload-cache/`.
      27 files, `scars_1999.zip` … `scars_2025.zip`, 739 MB.
      1. Upload each as `…/FINAL_PRODUCTS/annual_burned_vectors_v2/scars_<Y>`. **Copy the
         destination from the gate's own closing line** (`validate_scar_zips.py` prints it,
         interpolated from `C.PRODUCT_VERSION`) — never type it. v2 scars in the v1 folder is
         exactly what the versioning exists to prevent.
      2. Set `exclusion_rule_a` / `exclusion_rule_b` on each FeatureCollection.
      3. `$PYTHON collection-01/scripts/validate_scar_zips.py --ingested`
      4. The next 15-min tick launches **07c** (the three scar rasters) on its own, then `C4-check.out`.

      Nothing was ingested from the broken run, so **there is nothing to delete in GEE here**.
- [ ] **Resume 07d — the nine subproducts.** *(run)* `rm collection-01/logs/v2-driver/A2.pause`;
      the next tick resubmits all nine. Encodings are copied verbatim from the network's reference —
      **do not innovate there** (docs/07 §12). Then the audit runs automatically and leaves
      `A3-check.out` and `A3-props.out` — **read them, they are not self-checking.**
- [ ] **Watch the throughput, and split across accounts if it repeats.** On 14 Sep only **one** of
      the nine ever started: 12 h at 36 %, eight stuck `PENDING` behind it, with the project
      otherwise idle (one soy task and a table ingest all day) — so it was a concurrency cap, not
      contention. The queue is **per user**, and `mapbiomas-fire-485203` had **0 running**, so the
      lever is to submit some of the nine as **gmail** on the fire project alongside comahue's; the
      destination asset path is unaffected (CLAUDE.md). **The trap:** the in-flight check is
      project-scoped, so a naive relaunch on the other project does not see the first project's
      tasks and would run duplicates into the same asset. Split the list explicitly, do not
      relaunch the same list twice.
- [ ] **Run D2 — the six network-spec tables** once the five `*_coverage` + `year_last_fire`
      products and the scar-size raster exist. D1 and D2 **cannot agree by construction** (previous
      vs same-year LULC); say so in the CSV hand-off. docs/09 §5.2.

## Still owed to people

`burned_area_polygons_v2` was replaced in place on 12 Sep 17:46, so the link early users already
hold still works — but the layer under it moved from **908,346 rows / 58.05 Mha** to
**1,012,648 rows / 63.33 Mha**. **Tell them the numbers changed**, not merely that v1 is
superseded: anyone who already quoted a total from that layer quoted one ~8 % low.

## Operating notes for whoever picks this up

- **The compute project is shared with the whole MapBiomas Fuego network.** `listOperations()`
  returns every country's tasks. Never cancel or reason about a task you did not launch; match only
  on our namespaced prefixes (`mob_`, `arg07d_`, `arg07e_`, `arg07c_`).
- **A wedged GEE task is a real failure mode, and the supervisor now breaks it by itself.** One
  2002 export ran **37 h** frozen at `14/18` work units while every other year finished in 42–54
  min. Settled, do not re-derive. Two things about the fix are worth knowing before touching it:
  **GEE serves a task's current progress but no history**, so last tick's reading lives on disk in
  `logs/v2-driver/mob-progress.json`; and **`updateTime` is not the signal** — the server refreshes
  it on a stalled task too. Only the work-unit count is real. `mob_` tasks flat for 2.5 h are
  cancelled and resubmitted (3 kills max); **07d/07c tasks are shown on the board but never
  auto-cancelled**, because 27 measured healthy `mob_` runs calibrate that threshold and nothing
  calibrates theirs. Tested by `scripts/test-07-v2_driver_stall.py`.
- **A paused stage is not a finished one.** `<stage>.pause` in `logs/v2-driver/` skips a stage and
  shows ⏸ on the board with its reason. It is deliberately **not** a `.done` file — a marker that
  claims a success which never happened is the bug this repo hit three times in Sep 2026.
- **The driver's logs are append-only across runs.** A bare `grep '\[C2\] rc='` matches *last
  night's* line; a `grep '23:3[0-9]'` matches a previous day's tick. Anchor every check on today's
  timestamp, on a line count taken before you start, or on the live process.
- **A marker is not evidence.** Three bugs in Sep 2026 were the same shape: a `.done` file or a gate
  asserting a success that was not real. All fixed — but distrust the pattern. When a run is
  invalidated, its markers are as stale as its assets: clear **every** `*.done` and `*.tries`.
- **Verify a launch on the server, not from `rc=0`.** The 00:21 subproduct launch was confirmed by
  listing nine `arg07d_*` operations, not by the launcher's exit code.

## Later — hand-off and cleanup

- [ ] **Tell Brazil the assets are ready, and work the question list** in
      [docs/09 §16](collection-01/docs/09-statistics.md) — GCS bucket access, whether the public
      asset ids stay the same, the real deadline, and the coarse-read over-reporting warning that
      affects every country. **Two items on that list changed today:** "where `argentina/` lives"
      is moot — we are not adding a country folder to their toolkit — and the `crsTransform` patch
      is now a Python translation of `core/`, so offering it back means handing them a diff against
      their JS, not a branch. Say so plainly; the grid fix still matters to them.
- [ ] **Delete the dead step-11 code** once the toolkit route is verified end to end:
      `workflow/11-burnable_area.py`, `workflow/11-burned_area_stats.py`. Both are superseded —
      [docs/09](collection-01/docs/09-statistics.md)'s opening note.
- [ ] **Fix the stale doc pointers in code comments.** `docs/11-*.md` no longer exists; 24 `docs/11
      §…` references survive in five files. `07-month_of_burn.py` (6) →
      [docs/07 §1.1](collection-01/docs/07-vector_to_raster.md) for the rules and
      [docs/09](collection-01/docs/09-statistics.md) for the TESTS/ notes;
      `factsheet_object_stats.R` (4) and `objects_region_tag.R` (3) → docs/07 §1.1 for the filter,
      [docs/09 §9](collection-01/docs/09-statistics.md) for the fire-count family. The 11 in
      `workflow/11-*.py` need no fixing — those two scripts are deleted by the item above.
- [ ] **Delete the `FIRE/COLLECTION-1/TESTS/` asset folder** when the September work is done. It
      holds only benchmark assets. Deletions are Iván's to run.

## Not on the critical path

Running in parallel, nothing above depends on them: validation
([docs/10](collection-01/docs/10-validation.md), and the open items in
[`BACKLOG.md`](BACKLOG.md)), the ATBD and methodology page, and the December Bariloche launch
materials.
