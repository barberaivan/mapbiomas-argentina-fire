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

## Now — the burnable denominator, and the factsheet off the toolkit's numbers

> **Goal: have real numbers to analyse for the factsheet on Tue 15 Sep.** What is left on our side
> is **one small GEE export** plus local R. Nothing here waits on a product asset.
> **Scope: ecoregion only** — departamento and provincia are December (docs/09 §1.2).

**The strategy changed again on 14 Sep, and it shrinks this section.** We are **not** computing the
burned-area cross-tab. The split is now (docs/09 §4):

- **The numerator — burned area by month × year × ecoregión × LULC — comes from the network's
  toolkit**, run with **our 13-class ecoregion vector** registered in it:
  `…/ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_2-13Ecorregiones_3857`. **Hand them the vector,
  never the `_r` raster** — the raster numbers the regions alphabetically and the vector does not, so
  six of thirteen ids disagree and Monte's 47 Mha decodes as Pampa (docs/09 §5.1, measured 14 Sep).
- **The denominator — burnable area per ecoregión — is ours**: one constant layer, the **mode of the
  col-3 burnable classes over 1998–2024**, reduced as `eco13·10 + burnable`. 26 rows, one task,
  minutes. Same programming strategy as their app (docs/09 §4.2–§4.3).
- **The fire counts stay local**, off the object database, and never touch Earth Engine (docs/09 §8.2).

⚠️ **The open dependency: which asset their dataset reads.** The toolkit's datasets normally read the
**published `*_coverage` subproducts** — which are exactly the nine that are not exported yet. If
that is how it is configured, the numerator waits on 07d (Brazil's help, "After"), and Tue 15 Sep is
tight. If instead the dataset is defined against the **month-of-burn collection + col-3 LULC**
(27/27, landed, what our own table was going to read), it can run today. **Settle this in the same
message as the territorial layer** — it is the one thing that decides whether the factsheet's
numerator exists this week.

The nine subproducts (07d) were launched 00:21 and **cancelled 13:05**; they are not on the path to
any factsheet number, and **Brazil is now helping export them** — see "After". `A2` is paused in the
supervisor (`logs/v2-driver/A2.pause` — delete that file to resume; the board shows ⏸ and prints the
reason). The nine were cancelled cleanly: 9/9 confirmed `CANCELLED`, nothing else left PENDING or
RUNNING in `mapbiomas-argentina`.

### What exists already — 14 Sep 13:10

| What | Where | State |
|---|---|---|
| **Month-of-burn rasters** (07a) | `collection1_fire_mask_v2/…_<year>` | ✅ **27/27**, all carrying the current rule A. 2002 landed 00:16. **This is what the toolkit's numerator reads.** |
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

### What is left to write, and what it must copy

**[docs/09](collection-01/docs/09-statistics.md) is the build spec — read it before writing a
line.** Our one export is small, but it copies the app's shape exactly (docs/09 §2): the crossing
packed into the pixel value, territory painted and never intersected, a `bounds()` rectangle as the
reduction geometry, no `tileScale`, one task. The three divergences are deliberate and listed in
§2: the pinned grid (`crs` + `crsTransform`, never `scale: 30`), Python instead of JavaScript, and
`Export.table.toDrive` instead of their GCS bucket.

Two things about the join, because they are what a wrong number will come from:

- **Both sides must key on the same 13 ids** — theirs and ours (docs/09 gate 2). Check the *names*,
  not the count.
- **The denominator no longer varies by year** (docs/09 §4.4). `%` now means "of the area that is
  burnable most of the time", which makes the series a pure fire signal — and makes a `%` over 100
  arithmetically possible. Say it in the footnote; check it in gate 4.

### The work

- [ ] **Hand Brazil the territorial layer and agree the dataset — first, and blocking.** *(Iván)*
      Three questions in one message: the territorial layer (below), **which asset the dataset reads**
      (month-of-burn collection vs the not-yet-exported `*_coverage` subproducts — see above), and
      which LULC year it crosses. The asset is
      `projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_2-13Ecorregiones_3857`
      (13 features, unique id `GEOCODE` 1..13, names in `LEVEL_2`, clean UTF-8). **Not the `_r`
      raster** — docs/09 §5.1 trap 1. One thing to settle in the same message: **which LULC year
      their dataset crosses** — we want the **previous** year (docs/09 §4.1); if their definition
      only does same-year, take it and say so in the footnote.
- [ ] **Build `collection-01/statistics/`** *(edit)* — module layout in
      [docs/09 §1.1](collection-01/docs/09-statistics.md), spec in §4–§6. Much smaller than
      yesterday's plan: `burnable_export.py`, `decode.py`, `legends.py`, and the R side. Add
      `ECOREGIONS13` to `utils/constants.py` rather than retyping the asset id.
- [ ] **Test on a small rectangle inside Argentina first.** Seconds, and it catches every structural
      error the national run reveals slowly (docs/09 §4.5). A flag on `burnable_export.py`, not a
      commented-out block.
- [ ] **Export the burnable denominator** — `eco13·10 + burnable`, the **mode of the col-3 burnable
      classes over 1998–2024**, on the pinned grid, **to Drive as the comahue account** so it lands
      in `data/statistics/` via Insync (docs/09 §4.2–§4.3, §4.6). 26 rows. Watch the two things that
      are easy to get wrong: **no observado must stay masked** (it belongs to neither list, so the
      mode never sees it) and the **ecoregions must be the single mask driver**.
- [ ] **Decode both tables and run the verification gates**
      ([docs/09 §7](collection-01/docs/09-statistics.md)). Gates 2 (both sides key the same), 4
      (denominator ≥ numerator) and 5 (total area closes) first — they are cheap and they catch what
      is invisible in the numbers. `data/statistics/burnable_eco13.csv` plus the toolkit's CSVs are
      what the next two sections read.

## Next — the factsheet datasets

From the toolkit's table, our burnable table and the local vectors. No Earth Engine.

- [ ] **Regenerate the fire-count tables: final filters, each fire ONCE, by CALENDAR year.**
      *(edit → run)* Three changes at once ([docs/09 §8.2](collection-01/docs/09-statistics.md)):
      the object selection changed, so the existing CSVs are stale; a fire is now counted in the
      single region containing its **centroid**, not in every region it touches; and a fire is filed
      under the **calendar year and month of `date_median`**, not under its fire-year — everything
      the factsheet reports is calendar-year. The centroid tags already exist
      (`regions_<fy>_one.csv`), so the work is to switch the consumer to them and **drop the
      `_multi` path from both script and doc**, not to leave both. ⚠️ **A calendar year needs both
      of its fire-years**, so read all 28 files first and aggregate after — never per file. Move
      `scripts/factsheet_object_stats.R` in as `statistics/fire_counts.R`, writing
      `data/statistics/fire_counts_by_month.csv` + `fire_region_summary.csv`. Local R, minutes.
- [ ] **Build the four analyses** from the toolkit's table + `burnable_eco13.csv` + the counts —
      [docs/09 §8.1](collection-01/docs/09-statistics.md), content plan in
      [docs/10](collection-01/docs/10-factsheet_design.md): mean annual burned proportion; the time
      series and its GAM trend; the pirogram (area half from the toolkit, **count half from the
      objects**); the intra-annual shape normalised per region. **Analysis 1's per-LULC-class
      variant is not computable** from these tables (docs/09 §4.4) — decide whether to drop it or to
      pay for one more small export, before it is promised to the designers.
- [ ] **State the three divergences in the footnote.** Everything reported is **calendar-year** —
      the fire-year is how the mapping is organised, not how anything is published. What differs is
      how each side files a fire: (i) rasters assign year and month **per pixel** from `abs_date`,
      the count side **per object** from `date_median`, so a fire straddling 31 December is split in
      one and filed whole in the other; (ii) "area burned in month M" is a pixel sum on one side and
      a whole-object assignment on the other; (iii) the denominator is a **27-year modal burnable
      area**, not that year's. Acceptable — say all three out loud.

## Then — the factsheet plots

- [ ] **Draw the plots** off those datasets, in `statistics/factsheet_plots.R`. There is no
      plotting script yet: the pair pushed in ccc0f08 was written against the old object selection
      and has been deleted (3f494b4). What survives from that commit is the content plan in
      [docs/10](collection-01/docs/10-factsheet_design.md) — the multi-region conventions (colour
      per region, the little map as the legend, `all_regions` vs focal variants), §4's intra-annual
      distribution normalised per region, and §2's interannual series in "veces el año típico".
      Figures land in `data/statistics/figures/`. Data is due to the designers **~Wed 16 Sep**.
- [ ] **Decide what the factsheet says about the Pampa.** Still open, and it needs a call before the
      16th. The Pampa is largely cropland; after the filters its total is still built partly on
      residual cropland pixels (1.37 Mha nationally at `T_AGRI = 0.4`). Candidate framings: report
      it on non-agricultural land only (restricting the denominator the same way); report both and
      make the gap the story; call it an upper bound; or drop the panel and keep it for the December
      Bariloche launch. It is legitimate to show something that is not a straight read of the
      platform — but it has to be said out loud.

## After — finish the v2 product exports

Publication, not analysis. Picks up exactly where 14 Sep 13:05 left it.

**Brazil is helping with this half (14 Sep).** They are exporting the remaining fire subproducts
from our `FINAL_PRODUCTS` — the same reference code, run on their side, which is what takes 07d off
our critical path. **The exception is everything on the scar-size side**: `annual_burned_scar_id`,
`annual_burned_scar_area` and `annual_burned_scar_size_range` (07c) are gated on **the manual ingest
of the 27 calendar-scar packages, which only Iván can do** — nobody can unblock those for us. So the
first item below is still the one that matters, and it is still ours.

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
- [ ] **Settle with Brazil which of the nine they export, then resume the rest.** *(run)* They are
      helping with 07d, so the first move is to agree the split explicitly — then
      `rm collection-01/logs/v2-driver/A2.pause` and the next tick resubmits **whatever is left to
      us**. Encodings are copied verbatim from the network's reference — **do not innovate there**
      (docs/07 §12). The audit then runs automatically and leaves `A3-check.out` and `A3-props.out`
      — **read them, they are not self-checking.** ⚠️ **Do not let both sides export the same
      subproduct**: the in-flight check is project-scoped and would not see their task, which is the
      same failure mode as the two-account split below.
- [ ] **Watch the throughput, and split across accounts if it repeats.** On 14 Sep only **one** of
      the nine ever started: 12 h at 36 %, eight stuck `PENDING` behind it, with the project
      otherwise idle (one soy task and a table ingest all day) — so it was a concurrency cap, not
      contention. The queue is **per user**, and `mapbiomas-fire-485203` had **0 running**, so the
      lever is to submit some of the nine as **gmail** on the fire project alongside comahue's; the
      destination asset path is unaffected (CLAUDE.md). **The trap:** the in-flight check is
      project-scoped, so a naive relaunch on the other project does not see the first project's
      tasks and would run duplicates into the same asset. Split the list explicitly, do not
      relaunch the same list twice.
- [ ] **Run the five remaining network tables** once the four `*_coverage` + `year_last_fire`
      products exist, and `toDrive-area-scar-size` **after** the scar ingest above. They **cannot
      agree with the factsheet's numbers by construction** (same-year LULC, burned-only rows, and a
      per-year denominator vs our 27-year modal one); say so in the CSV hand-off. docs/09 §9.

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
      [docs/09 §13](collection-01/docs/09-statistics.md) — whether the public asset ids stay the
      same, the real deadline, whether they need our CSVs at all now that we export to Drive, and the
      coarse-read over-reporting warning that affects every country. The `crsTransform` patch is now
      a Python implementation of `core/`, so offering it back means handing them a diff against their
      JS, not a branch. Say so plainly; the grid fix still matters to them.
- [ ] **The departamento / provincia cut — December, not September.** The finer cut for the
      Bariloche launch, on both sides of the ratio: the packed `ecoregion16·100000 + GEOCODE`
      territory id and the masking rule that comes with it are written down in
      [docs/09 §5.4](collection-01/docs/09-statistics.md) so nothing is re-derived, and the 16 → 13
      ecoregion crosswalk (exact, measured) is in §5.2. Province falls out of the department layer;
      no second asset. Note the `Stats-Arg_political_level_*` names are Latin-1 damaged and the
      16-class `GEOCODE` is a string — both bite here, not in September (docs/09 §5.1).
- [ ] **Delete the dead step-11 code** once the toolkit route is verified end to end:
      `workflow/11-burnable_area.py`, `workflow/11-burned_area_stats.py`. Both are superseded —
      [docs/09](collection-01/docs/09-statistics.md)'s opening note.
- [ ] **Fix the stale doc pointers in code comments.** Two generations of drift now. (a) The
      **validation doc moved 10 → 11** on 14 Sep (`docs/10` is now the factsheet design), so every
      `docs/10 §…` in `collection-01/validation/*.py` and `scripts/10_burned_area_by_fire_year.py`
      means **docs/11**. (b) The older one: `docs/11-*.md` as cited by 24 `docs/11 §…` references in
      five files no longer exists at all. `07-month_of_burn.py` (6) →
      [docs/07 §1.1](collection-01/docs/07-vector_to_raster.md) for the rules and
      [docs/09](collection-01/docs/09-statistics.md) for the TESTS/ notes;
      `factsheet_object_stats.R` (4) and `objects_region_tag.R` (3) → docs/07 §1.1 for the filter,
      [docs/09 §8.2](collection-01/docs/09-statistics.md) for the fire-count family. The 11 in
      `workflow/11-*.py` need no fixing — those two scripts are deleted by the item above.
- [ ] **Delete the `FIRE/COLLECTION-1/TESTS/` asset folder** when the September work is done. It
      holds only benchmark assets. Deletions are Iván's to run.

## Not on the critical path

Running in parallel, nothing above depends on them: validation
([docs/11](collection-01/docs/11-validation.md), and the open items in
[`BACKLOG.md`](BACKLOG.md)), the ATBD and methodology page, and the December Bariloche launch
materials.
