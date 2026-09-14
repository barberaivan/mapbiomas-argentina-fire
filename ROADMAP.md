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

## Now — finish the v2 re-export (3 of 4 branches are DONE)

> **Goal for Monday 14 Sep: the ONLY thing blocking this pipeline should be Iván ingesting the
> 27 scar packages by hand.** Everything else finishes unattended overnight.

**Read this first, then `$PYTHON collection-01/scripts/run_07_v2_driver.py --status`.** A cron
supervisor (`run_07_v2_driver.py`, every 15 min, state in `collection-01/logs/v2-driver/`) runs
every step below on its own. Its board is `STATUS.md`; its log is `tick.log`. If the board's
timestamp is >20 min old the supervisor is NOT running — check `crontab -l` then `cron.log`.

Everything is **`_v2`, replaced in place**. There is no `_v3`; the asset paths and
`C.PRODUCT_VERSION = 2` do not change. (Why v2 was rebuilt at all: the first run shipped an
unconfined rule A that deleted two thirds of the Delta del Paraná. Fixed in 8032aa2 — rule A now
also requires `area_ha < 150` and intersection with `config/rule_a_aoi.geojson`. Full story in
`git log` and docs/07 §1.1; it is settled and needs no further action.)

### State — 14 Sep 00:25

| What | Where | State |
|---|---|---|
| **Fire-object polygon layer** (07e) | `FINAL_PRODUCTS/burned_area_polygons_v2` | ✅ **DONE** — exported, `--verify` green on all 28 fire-years, `--set-props` written. **1,012,648 rows / 63,328,585 ha** |
| **Calendar scar packages** (07b, local) | `collection-01/data/scars-upload-cache/` | ✅ **DONE** — 27 zips, 630 MB, gate green |
| **Month-of-burn rasters** (07a) | `collection1_fire_mask_v2/…_<year>` | ✅ **DONE** — **27/27**, all carrying the current rule A. 2002 landed 14 Sep 00:16 |
| **The nine subproducts** (07d) | `FINAL_PRODUCTS/` | ⏳ **launched 14 Sep 00:21** — 9/9 `arg07d_*` tasks in flight, verified on the server (not just `rc=0`) |
| **The three scar rasters** (07c) | `FINAL_PRODUCTS/` | ⏳ gated on Iván's ingest **and** on 27/27 |

**The fix is confirmed, twice, independently — do not re-derive this.** The local scar build
(pure R, never touches Earth Engine) totals **63.24 Mha**; 07e's `--verify` on the landed asset
reports `area per OBJECT` = **63.33 Mha**. The roadmap predicted 63.33. The small gap between the
two is fire-year vs calendar-year partitioning, as expected.

### A wedged GEE task no longer needs a human

**Settled — do not re-derive.** One 2002 export ran **37 h** stuck at 73.7 % (`progress` frozen at
`14/18` work units, `attempt: 1`) while the other 26 years each finished in 42–54 min. It was a
server-side stall: nothing in our code caused it and nothing in our code can prevent it. Cancelled
and resubmitted by hand; the retry landed in 78 min.

The supervisor now breaks such a stall itself (`stall_survey` / `cancel_wedged_mob`, tested by
`scripts/test-07-v2_driver_stall.py`; full rationale in those docstrings). Four things about it
are worth knowing before you touch it:

- **GEE serves a task's current progress but no history**, so last tick's reading lives on disk in
  `logs/v2-driver/mob-progress.json`. That file is the watchdog's only memory.
- **`updateTime` is not the signal** — the server refreshes it on a stalled task too; the wedged op
  carried a fresh `updateTime` for all 37 h. Only the work-unit count is real.
- A `mob_` task flat for **2.5 h** is cancelled and re-topped-up, `MAX_STALL_KILLS = 3` times, then
  it stops and says so on the board. **07d/07c tasks are shown but never auto-cancelled** — 27
  measured healthy `mob_` runs calibrate that threshold and nothing calibrates theirs.
- Four guards run before any cancel, because the compute project is shared with the whole network
  and cancelling another country's export is unrecoverable for them.

**Never relaunch with `--all` to fix one year.** The supervisor tops up only the missing
years (`month_years_current()` → `missing`), because `--all --overwrite` re-exports the good
assets too: ~24 h to repair ~50 min of work, tearing them down on the way.

### What is running right now — no human needed

The nine subproduct tasks (07d) went out at **00:21 on 14 Sep** and are on the server. When they
land, the supervisor runs the **audit automatically** and leaves `A3-check.out` and `A3-props.out`
in `collection-01/logs/v2-driver/` — **read them, they are not self-checking.**

Encodings there are copied verbatim from the network's reference; **do not innovate** (docs/07 §12).
If the board still shows `0/9` hours from now with nothing in flight, read `A2.out`.

**The morning check is one command:**

```bash
$PYTHON collection-01/scripts/run_07_v2_driver.py --status
```

Read the **A2** row. `9/9` → the night went fine; go read `A3-*.out`, then do the ingest below.
Still short with tasks in flight → look at each task's `flat N min` on that row: small means merely
slow, large means it has stopped moving. **07d tasks are not auto-cancelled** (above), so a wedged
one is yours to cancel and resubmit — the same drill the 2002 note describes.

The ingest below does **not** wait on 07d. It is gated only on 27/27 month assets, which landed at
00:16, so you can do it the moment you sit down.

### What Iván has to do — the only human gate

**Ingest the 27 scar packages by hand**, then the last product builds itself:

1. Upload `collection-01/data/scars-upload-cache/scars_<Y>.zip` (27 of them) as
   `…/FINAL_PRODUCTS/annual_burned_vectors_v2/scars_<Y>`.
   **Copy the destination from the gate's own closing line** (`validate_scar_zips.py` prints it,
   interpolated from `C.PRODUCT_VERSION`) — never type the path, v2 scars in the v1 folder is
   exactly what the versioning exists to prevent.
2. Set `exclusion_rule_a` / `exclusion_rule_b` on each FeatureCollection.
3. `$PYTHON collection-01/scripts/validate_scar_zips.py --ingested`
4. The next 15-min tick launches **07c** (the three scar rasters) on its own, then its check
   (`C4-check.out`).

Nothing was ingested from the broken run, so **there is nothing to delete in GEE here**.

### Still owed to people

`burned_area_polygons_v2` was replaced in place on 12 Sep 17:46, so the link early users already
hold still works — but the layer under it moved from **908,346 rows / 58.05 Mha** to
**1,012,648 rows / 63.33 Mha**. **Tell them the numbers changed**, not merely that v1 is
superseded: anyone who already quoted a total from that layer quoted one ~8 % low.

**When reading 07e's `--verify` output, do not quote the ROW sum** (68,447,098 ha). Vertex-split
parts are one row each — object `2000_57529` alone over-counts by 5.1 Mha. The figure to quote is
`area per OBJECT`.

### Operating notes for whoever picks this up

- **The compute project is shared with the whole MapBiomas Fuego network.** `listOperations()`
  returns every country's tasks. Never cancel or reason about a task you did not launch; match
  only on our namespaced prefixes (`mob_`, `arg07d_`, `arg07e_`, `arg07c_`).
- **The driver's logs are append-only across runs.** A bare `grep '\[C2\] rc='` matches *last
  night's* line. Anchor every check on today's timestamp or on the live process — this produced
  two false "it finished" readings on 12 Sep.
- **A marker is not evidence.** Three bugs this weekend were all the same shape: a `.done` file or
  a gate asserting a success that was not real (stale `B.done`; the zip gate exiting 1 *after*
  passing all 27; `stage_B` gating the stamping step on its own stamp). All three are fixed — see
  `git log` — but the pattern is worth distrusting. When a run is invalidated, its markers are as
  stale as its assets: clear **every** `*.done` and `*.tries`, not the ones you remember.

## Next — the summary statistics

All of [docs/09](collection-01/docs/09-statistics.md). Starts only after the products land.

- [ ] **Add the grid and the product ids to the GEE-side constants.** *(edit)* `SNIC_CRS`,
      `SNIC_TRANSFORM`, `PRODUCT_LULC`, the `FINAL_PRODUCTS` prefix and `MONTH_OF_BURN_COL` into
      `mapbiomas-arg-fire-gee/collection-01/utils/constants.js`, exported and required — never
      pasted into an app. Carry the same SYNC WARNING the `veg_fire` arrays already have.
- [ ] **Fork the toolkit's `core/` into our repo and patch it.** *(edit)*
      `fuego:collection-01/statistics/core/` — `calculate.js` swaps `scale` for `crs` +
      `crsTransform`; that is the only logic change, and it must be annotated so it can be offered
      back to Brazil. **Never push to `mapbiomas-latam-fire-gee`.**
- [ ] **Write `argentina/`.** *(edit)* `_shared/products.js` (asset ids, mirroring
      `constants.py::product_name()`), `territories/index.js` (paint `Stats-Arg_ecorregions` and
      `Stats-Arg_political_level_3_v`, pack as `ecoregion16·100000 + GEOCODE`, decode to ecorregión
      16 **and** 13, provincia and departamento), `datasets/fuego_col1.js` (D1 + the six D2),
      `apps/fuego_col1.js` (config + UI). LULC legends already exist in their `00_Tools/Legends.js`;
      territory names come off the FCs — **except the 16 ecoregion names, which must be hand-written
      because the asset's are mis-encoded** ([docs/09 §4.2](collection-01/docs/09-statistics.md)).
- [ ] **Export D1 × ecoregion first, and run verification gates 1, 2, 4 and 5** before anything
      else. It answers the whole factsheet and it is the cheapest thing to be wrong about.
- [ ] **Export D1 × ecoregion_departamento and the six D2 tables.** The platform deliverable.

## Then — the factsheet (data due ~16 Sep)

- [ ] **Regenerate the local fire-count tables under the final filters.** *(run)* The object
      selection changed, so `factsheet_region_summary_min10ha.csv` and
      `factsheet_counts_by_month_min10ha.csv` are stale. Local `sf`/R only, no Earth Engine, minutes.
- [ ] **Build the three analyses** from the D1 CSVs + the count tables —
      [docs/09 §9](collection-01/docs/09-statistics.md), content plan in
      `collection-01/presentations/factsheet-notes.md`.
- [ ] **Decide what the factsheet says about the Pampa.** Still open. The Pampa is largely cropland;
      after the filters its total is still built partly on residual cropland pixels (1.37 Mha
      nationally at `T_AGRI = 0.4`). Candidate framings: report it on non-agricultural land only
      (restricting the denominator the same way); report both numbers and make the gap the story;
      call it an upper bound; or drop the panel and keep it for the December Bariloche launch. It is
      legitimate to show something that is not a straight read of the platform — but it has to be
      said out loud. **Needs a call before the 16th.**

## Later — hand-off and cleanup

- [ ] **Tell Brazil the assets are ready, and work the question list** in
      [docs/09 §16](collection-01/docs/09-statistics.md) — GCS bucket access, where
      `argentina/` lives, the `crsTransform` patch, whether the public asset ids stay the same, the
      real deadline, and the coarse-read over-reporting warning that affects every country.
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
