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

Three independent branches. 
- A blocks the factsheet and the platform; 
- B is parallel, just for completeness; 
- C is the scar-size path, blocks the platform.

Nothing blocks these. The exclusion rules are wired and ON by default, `C.PRODUCT_VERSION = 2`
sends every output to a new asset path, and `C.PRODUCT_LULC` points at the published col-3 — so the
commands in [docs/07](collection-01/docs/07-vector_to_raster.md)'s "Order of operations" produce the
published selection with no flags.

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
- [ ] **B — 07e, the fire-object polygon layer.** *(run)* One task, 3.27 h measured, independent of
      A. `--launch` (v2 is a new path, so no `--overwrite`), then `--verify` (the gate), then
      `--set-props`. Needed for the fire-count analyses, and it is the layer early users already
      have a link to — tell them the v1 link is superseded.
- [ ] **C — the scar-size chain (07b → 07c).** *(run — not optional)* 28 + 27 local passes (no env
      vars: the rules are the default), 27 manual ingests into `annual_burned_vectors_v2`, then 3
      cheap Earth Engine tasks. **Set `exclusion_rule_a` / `exclusion_rule_b` on the ingested FCs by
      hand** — only the rasters painted from them get the properties automatically.
      **07b reads the object set directly, so the filters change the scars themselves** — not only
      which pixels survive, but how they are labelled: a scar that was 8-connected *through* a
      dropped object now splits in two, and every `area_ha` shrinks. **Re-running 07c alone is
      wrong**, not merely stale: it would paint old scars (old ids, old areas) masked to the new
      07a, so `annual_burned_id` and `annual_burned_area_ha` would disagree with the extent they sit
      on. `annual_burned_scar_size_range` is a published subproduct, so this blocks the platform.
      [docs/07 §1.1](collection-01/docs/07-vector_to_raster.md).

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
