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

## Now — RELAUNCH the v2 re-export, overwriting what is already there

> ### ⚠ THE FIRST v2 RUN WENT OUT WITH A BROKEN RULE A. IT IS ALL BEING REDONE, IN PLACE.
>
> **The one thing to know: we are launching `_v2` again, with `--overwrite`, over both the GEE
> assets and the local files.** There is no `_v3`. The asset paths, `C.PRODUCT_VERSION = 2` and
> every name stay exactly as they are; what changes is the object selection underneath them.
>
> **What was wrong.** Rule A dropped any object that was >70 % `veg_fire` 15 `grassland_pampa` and
> burned 1 Jul–15 Nov, anywhere in the country. But class 15 is the remap of MapBiomas 11
> *Herbáceas Inundables* + 12 + 15 **in the PAMPA region**, so the marshes of the **Delta del
> Paraná** carry it like a Pampa pasture does. The rule was deleting **65.7 % of the Delta's FY2020
> burned area** — 433 kha, including one 121,058 ha object that burned on 11 Aug 2020 — and 80.1 %
> of FY2008, 77.6 % of FY2022. Those are the Islas del Paraná fires. It bit hardest in exactly the
> big Delta fire years, so it distorted the time series as well as the level.
>
> **The fix, already committed** (docs/07 §1.1): rule A gains two conjuncts — `area_ha < 150` and
> *the object INTERSECTS* a hand-drawn agricultural-Pampa polygon (`config/rule_a_aoi.geojson`).
> Rule B is unchanged. All 28 fire-years: the published map goes from 58.05 Mha to **63.33 Mha**
> (the ruleset removes 8.4 % of the accepted area instead of 16.0 %), and the Delta's rule-A loss
> from 1.455 Mha to 23 ha. All three application points — 07a, 07b, 07e — were re-verified to agree
> **to the object** on FY2008/2020/2022.
>
> **The supervisor was RELAUNCHED on 12 Sep 08:05**, after the checklist below was worked
> through: the broken run's local files are gone, every stage marker is cleared and `A1.tries`
> is back to 0, so the next cron tick starts A1 (`--overwrite`) and C1 together. Watch it with
> `$PYTHON collection-01/scripts/run_07_v2_driver.py --status`; **nothing below needs a human
> until the manual ingest in branch C.**

**How the driver now knows the difference.** The old gate was "does the asset exist". That is
useless when the wrong version exists, so `run_07_v2_driver.py` counts only assets whose
`exclusion_rule_a` property equals the **current** `C.exclusion_rules()` text — one
`ImageCollection.filter().size()` per tick for 07a, one `getAsset` for 07e. As of 12 Sep that reads
**mob 0/27, poly False**, which is correct: 19 month assets and the polygon layer exist and are all
from the broken run. A1 and B now pass `--overwrite`. This is the same lesson docs/07 already
records about the v1 markers, one level up: *anything gated on a thing the previous run could also
have written is not a gate*.

**But the asset gate is only half of it — and the other half nearly ate branch B.** Every stage
also short-circuits on its own `<stage>.done` file *before* it ever looks at an asset
(`stage_B` opens with `if done("B"): return`). `B.done` was written at 01:31 on 12 Sep, eight
hours **before** the rule-A fix landed at 07:49, so it certified the BROKEN polygon layer. The
original checklist cleared `C1.done` and `C2.done` and not `B.done`: branch B would have
returned at its first line on every tick for the rest of the weekend, the board would have shown
`B ✅ verified=True`, and the layer early users hold would still be the 58.05 Mha one. **When a
run is invalidated, the markers are as stale as the assets — clear every `*.done` and `*.tries`,
not the ones you happen to remember.**

### The relaunch checklist — in this order

- [x] **1. Clear the local artefacts of the broken run.** *(done 12 Sep 08:03)* The launchers skip
      a year whose marker or zip exists, and all of them were on disk from the broken build.
      **Deleted outright, not archived** (Iván's call, 12 Sep): they are a known-wrong build,
      fully regenerable from step 05, and archiving 4.4 GB into the Insync store to sit beside
      the v1 archives buys nothing.
      ```bash
      cd collection-01/data
      rm -rf objects-scars scars-upload-cache                    # 3.7 GB + 678 MB
      rm -f scars-pixels-cache/.done_fy* scars-pixels-cache/*.rds   # 28 markers + 54 files, 15 GB
      cd ../logs/v2-driver && rm -f *.done *.tries               # ALL of them — see above
      ```
      The 54 `.rds` went too, beyond what this list first said: the pixels pass rewrites all of
      them anyway, and a stale one is only invisible while all 28 markers are present. A wrong
      file that survives a failed rerun is worse than a missing one.
      (`data/objects-scars_v1/` and `scars-upload-cache_v1/` are the ORIGINAL v1 archives — left
      alone.)
- [x] **2. Build the rule-A AOI tag.** *(run)* ~2 min for all 28 fire-years; 07b **hard-errors**
      without it rather than silently disabling half of rule A.
      ```bash
      Rscript collection-01/scripts/rule_a_aoi_tag.R          # -> objects-analysis/aoi_rule_a_<fy>.csv
      ```
      *(done 12 Sep — all 28 CSVs present.)* Re-run with `FORCE=1` only if the polygon is
      redrawn, and then `$PYTHON collection-01/scripts/rule_a_aoi_extract.py` **first**. Only 07b
      reads these; 07a and 07e test the AOI server-side with `ee.Filter.bounds(C.rule_a_aoi_ee())`,
      so **no step-06 re-upload was needed** — the AOI is not a property on the object FCs.
- [x] **3. Un-pause the supervisor.** *(done 12 Sep 08:05)*
      `echo 0 > collection-01/logs/v2-driver/A1.tries` — 0, not 1, so the relaunch gets the full
      `MAX_TRIES` budget like every other stage (whose counters are now absent, i.e. 0).
      Cron is untouched and ticks every 15 min. Watch
      `$PYTHON collection-01/scripts/run_07_v2_driver.py --status`.

### What each branch has to redo

- [ ] **A1 — 07a, month of burn.** *(running since 12 Sep 08:15; 27/27 submitted, rc=0)* All **27**
      calendar years again, over the 19 assets that are already there plus the 8 that never landed.
      **Measured 12 Sep: GEE gives this account ~2 concurrent, not 4**, and a year takes 42–54 min
      (mob_2000 54, mob_2003 52, mob_2001 42) — so A1 is **~11 h, landing ~19:30**, not the ~6.5 h
      estimated here. Nothing is wrong; the estimate was optimistic about concurrency. Budget from
      11 h when planning a relaunch. As comahue (`ivanbarbera@comahue-conicet.gob.ar`, project
      `mapbiomas-argentina`) — the queue is per user. `Export.image.toAsset(overwrite=True)`
      replaces an asset only when the **new task completes**, so a failed year leaves the old
      (wrong) image in place rather than a hole — which is why the `exclusion_rule_a` asset filter,
      not existence, is what the driver counts.
- [ ] **A2 — 07d, the nine subproducts.** *(run)* Nothing landed from the broken run, so this is a
      clean first build — but it is **gated on A1 reaching 27/27 assets carrying the current rule
      text**, which is the check the driver now makes. Count assets, not tasks: the task list is
      project-scoped and shows the whole network's work.
- [ ] **B — 07e, the fire-object polygon layer.** *(run, `--overwrite`)* The landed
      `burned_area_polygons_v2` is from the broken run and must be replaced **in place**, keeping
      the link the early users already have. Expect ~4 h, then `--verify` on all 28 fire-years and
      `--set-props`. The row/area counts will be **larger** than the 908,346 rows / 58.05 Mha now
      published — the confined rule A gives 5.27 Mha back. **Tell the early users the numbers
      changed**, not just that v1 is superseded.
- [x] **C1/C2 — the local scar build and its gate.** *(done 12 Sep 11:06)* `pixels` 28/28 then
      `scars` 27/27 in **2 h 23 min** (08:22 → 10:45); gate green at 11:06. The 27 packages sit in
      `collection-01/data/scars-upload-cache/`, 630 MB, waiting for the ingest.
      **This is where the fix was independently confirmed.** Summing the 27
      `scars_<Y>_summary.csv` gives **63.24 Mha** against the 63.33 Mha predicted above, and the
      ruleset now removes **8.38 %** of the accepted area against the 8.4 % predicted — while the
      broken run's 16.0 % reproduces the 58.05 Mha that went out (69.02 × 0.840 = 57.98). Both
      numbers come out of a branch that never touches Earth Engine, so they check the selection
      rather than restate it.
- [ ] **C3 — the manual ingest, then 07c.** *(Monday 14 Sep — the only human gate left)* Ingest the
      27 zips as `annual_burned_vectors_v2/scars_<Y>` with `exclusion_rule_a` / `exclusion_rule_b`
      set on each FC — **nothing was ingested from the broken run, so there is nothing to delete in
      GEE here**. Copy the destination from the gate's own closing line, which interpolates
      `C.PRODUCT_VERSION`; then `$PYTHON collection-01/scripts/validate_scar_zips.py --ingested`.
      07c then paints the three scar rasters from the ingested FCs, masked to the v2 month of
      burn, so it needs **A1 finished as well as the ingest**. Changing the selection changes the scars themselves — one that was
      8-connected *through* a dropped object splits in two — which is why the local build is redone
      and not just the painting.

**What is still waiting on a human:** only the **manual ingest in C** — Iván ingests the 27 zips on
Monday 14 Sep, and the next tick then launches 07c on its own. Steps 1–3 are done. Everything else
the supervisor does by itself over the weekend: A1 → A2 → A3, B (launch → `--verify` → `--set-props`)
and C1 → C2.

**Still owed to people, once B lands:** `burned_area_polygons_v2` is replaced in place, so the link
early users already hold keeps working but its numbers change — 908,346 rows / 58.05 Mha becomes
something larger, the confined rule A giving 5.27 Mha back. **Tell them the numbers moved**, not
merely that v1 is superseded.

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
