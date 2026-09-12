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

## Now — re-export the products as v2

> ### ⚠️ THIS SECTION IS ALREADY RUNNING, UNATTENDED — DO NOT RE-LAUNCH ANY OF IT BY HAND
>
> Started **Fri 11 Sep 2026, 21:27** (Iván away for the weekend). Every item below was submitted
> or started by `collection-01/scripts/run_07_v2_driver.py`, which cron ticks **every 15 min**.
> **Before you touch anything in this section, look at the board:**
>
> ```bash
> $PYTHON collection-01/scripts/run_07_v2_driver.py --status   # the board (no server calls)
> tail -40 collection-01/logs/v2-driver/tick.log               # what it has been doing
> crontab -l                                                   # is it still armed?
> ```
>
> A stage that shows ⏳ is either in flight or waiting on its gate — running its command yourself
> duplicates work at best. If `STATUS.md`'s "last tick" stamp is more than ~20 min old, the
> supervisor is not ticking: check `crontab -l` and `collection-01/logs/v2-driver/cron.log`.
> **When the board is all ✅, delete the two crontab lines** (the `v2_driver_tick.sh` entries) —
> that is the only manual cleanup it needs.

**Why a supervisor and not a sequence of commands.** The gates here are hours apart — 07d waits for
all 27 month assets, 07c for a manual ingest — and the obvious "wait, then launch the next thing"
shape dies with the session: a power cut takes the terminal, tmux and any sleeping process with it.
So the driver never sleeps. Each tick reads the state of the *world* — asset counts in both compute
projects, `.done_fy*` markers, zips on disk, `pgrep` — does whatever is now unblocked, writes
`logs/v2-driver/STATUS.md`, and exits. cron comes back at boot without a login (there is an
`@reboot` entry), so an outage costs only the hours the box is off; submitted Earth Engine tasks are
unaffected either way. Everything it invokes is already idempotent, so a repeated tick is a no-op
and an interrupted one is retried by the next. Per-stage state is in `logs/v2-driver/`: `<stage>.out`
is the command output, `<stage>.done` the marker (delete one to force that stage to run again),
`<stage>.tries` the retry counter — a stage that burns its budget stops and says so on the board
rather than looping. Design notes and the two traps it had to be taught:
[docs/07 "Order of operations"](collection-01/docs/07-vector_to_raster.md).

**What it is waiting on you for:** the 27 scar zips in `collection-01/data/scars-upload-cache/` must
be ingested **by hand** as `annual_burned_vectors_v2/scars_<Y>` (the folder already exists) with
`exclusion_rule_a` / `exclusion_rule_b` set on each FC. The next tick after that launches 07c on its
own. Nothing else needs a human.

The exclusion rules are wired and ON by default, `C.PRODUCT_VERSION = 2` sends every output to a new
asset path, and `C.PRODUCT_LULC` points at the published col-3 — so the commands in
[docs/07](collection-01/docs/07-vector_to_raster.md)'s "Order of operations" produce the published
selection with no flags.

Three branches.
- A blocks the factsheet and the platform;
- B is fully independent, just for completeness;
- C is the calendar-year scars, blocks the platform. Its local half is independent, but its last
  step (07c, the rasterization) needs **A1 finished** as well as the manual ingest.

- [ ] **A1 — 07a, month of burn.** *(run)* 27 Earth Engine tasks into the **new v2 collection** —
      no flags, no `--overwrite`: the rules are the default and v2 is a different asset path.
      ~58 min per calendar year; at ~4 concurrent across the two accounts, ~6.5 h. Submit **all 27
      up front** and as the second account (`ivanbarbera@comahue-conicet.gob.ar`, project
      `mapbiomas-argentina`) — the queue is per user and the shared project is the congested lane.
      Once submitted, nothing local has to survive; a power cut does not affect them.
- [ ] **A2 — 07d, the nine subproducts.** *(run)* **Must not start until all 27 month assets
      exist**, or it silently builds a partial product. That is an asset-existence test, not a
      judgement, so a cron entry can do it unattended: every 30 min, count assets in
      `C.MONTH_OF_BURN_COL`; at 27, run `07-subproducts.py --launch` once, drop a marker file, log
      to disk. **Count assets, not tasks** — the task list is project-scoped and shows the whole
      network's work. This gate only works because v2 is a new collection (docs/07 §1.2): against an
      overwritten one the count starts at 27.
- [x] **B — 07e, the fire-object polygon layer.** ✅ **done 12 Sep 2026, 01:31** — one submission,
      ~4 h, `--verify` clean on all 28 fire-years, 19 properties set.
      `FINAL_PRODUCTS/burned_area_polygons_v2`: **908,346 rows / 908,343 objects / 58.05 Mha**
      (per-object area; the 3-row gap is `2000_57529` split into 4 parts at the vertex limit, which
      is why a row-sum over-counts by 5.1 Mha). Against v1 — 1,263,079 rows / 69.12 Mha — the
      exclusion rules remove **28 % of the objects and 16 % of the area**. None of v1's duplicate
      FY2021 rows (docs/07 §13.6) recurred. **Tell the early users the v1 link is superseded.**
- [ ] **C — the calendar-year scars (07b local → ingest → 07c).** *(run — not optional)* The scars
      are built **locally, from the same filtered fire-year object set as 07a** (rules A and B on,
      which is the whole reason this is being re-run): `run_07_scars.sh pixels` turns each of the 28
      fire-years into its accepted burned pixels, `run_07_scars.sh scars` merges the two fire-year
      halves of each of the 27 calendar years, labels them 8-connected and vectorizes → 27 zipped
      Shapefiles. GEE cannot do this labelling (`connectedPixelCount` caps at 1024 px), so **the
      scars exist only as vectors until they are ingested by hand** into `annual_burned_vectors_v2`
      — set `exclusion_rule_a` / `exclusion_rule_b` on each ingested FC yourself; only the rasters
      painted from them get the properties automatically. Then 07c is just the rasterization: 3
      cheap tasks painting `annual_burned_id`, `annual_burned_area_ha` and
      `annual_burned_scar_size_range` from the ingested FCs, masked to the v2 month of burn — **so
      07c needs A1 finished as well as the ingest**. Because the filters change which objects exist,
      they change the scars themselves: one that was 8-connected *through* a dropped object now
      splits in two, and every `area_ha` shrinks — which is why the local build is re-run and not
      just the painting. `annual_burned_scar_size_range` is a published subproduct, so this blocks
      the platform. [docs/07 §1.1](collection-01/docs/07-vector_to_raster.md).
      **Local half done 11 Sep 23:51** — 28/28 pixel passes (41 min), 27/27 calendar years (77 min),
      no failures; `validate_scar_zips.py` passes **27/27**, 678 MB in `data/scars-upload-cache/`.
      Measured: **2,217,621 scars / 57.96 Mha**, against v1's 2,734,416 / 69.02 Mha — −18.9 % of
      scars, −16.0 % of area. Now waiting only on the manual ingest, then 07c fires itself.

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
