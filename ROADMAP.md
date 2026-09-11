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

## Now

Nothing is blocked on a decision. The two that were here are settled and recorded:

- **The exclusion rules and their thresholds are FINAL** — `T_GRASS = 0.70`, 1 Jul → 15 Nov,
  `T_AGRI = 0.40`, as specified in [docs/07 §1.1](collection-01/docs/07-vector_to_raster.md).
  Confirmed with the team, 2026-09-11. **Do not reopen this**: changing one value re-runs 07a–07e
  and every statistic below. If someone asks for a different number, that is a new collection.
- **Col-3 classes 22 and 26 are non-burnable** ([docs/09 §6](collection-01/docs/09-statistics.md)).

Start at the next section.

## Next — edit, then run: code changes before any re-export

- [x] ~~**Wire rule A into the three application points, with the final thresholds.**~~ **Done
      2026-09-11.** `C.T_GRASS = 0.70`, `C.GRASS_WINDOW = ((7,1),(11,15))`, `C.T_AGRI = 0.40` and
      `C.grass_window_days()` / `C.exclusion_rules()` in `utils/constants.py`; both rules wired in
      `07-month_of_burn.py::accepted_objects()`, `07-calendar_scars.R::accepted_oids()` and
      `07-burned_area_polygons.py::fire_filter()`. **The rules are ON by default** — `--no-exclusions`
      / `RULES=0` and `--t-grass` / `--t-agri` are overrides for the explorers and `TESTS/` only, and
      are recorded in the properties. **Both implementations verified against the explorer**: FY2020
      rule A 15,092, rule B 2,389, union 17,481 obj / 908,771 ha, overlap 0 — identical from GEE and
      from R. [docs/07 §1.1](collection-01/docs/07-vector_to_raster.md).
- [x] ~~**Make every asset record the rules it is based on.**~~ **Done 2026-09-11.** One
      `C.exclusion_rules()` builds the `exclusion_rule_a` / `exclusion_rule_b` property pair, stamped
      by 07a (the month images), 07c (the three scar rasters), 07d (the nine subproducts) and 07e
      (the polygon layer), and checked by `scripts/audit_product_properties.py`. The old
      `agriculture_filter` property is gone. ⚠️ **The scar FCs are hand-ingested, so their properties
      must be set at ingest** — the rasters painted from them carry the rules, the vectors do not yet.
- [x] ~~**Repoint `C.PRODUCT_LULC` to the published land cover.**~~ **Done 2026-09-11.** Now
      `…/COLLECTION-3/INTEGRATION/mapbiomas_argentina_collection3_pb`; the old value was the
      *preliminary* `…_integration_v1_buffer`. Re-verified against the asset: 41 bands
      `classification_1985..2025` (2025 native), same pixel step as `SNIC_TRANSFORM`, and an offset
      of exactly **+67 columns / −62 rows** from our lattice — integer, so nothing resamples.
- [x] ~~**Find out whether a department layer exists.**~~ **It does, and so does everything else.**
      Verified in the asset browser 2026-09-11: the `Stats-Arg_*` family in `ANCILLARY_DATA/` has
      departments (528, INDEC `GEOCODE`, carrying the province name), provinces (24) and ecoregions
      (16), each as vector **and** raster. 16 → 13 ecoregions measured as an exact aggregation, so
      one export serves both. Details, the crosswalk and the name-encoding problem:
      [docs/09 §4.2](collection-01/docs/09-statistics.md).
- [x] ~~**Decide the asset naming for the re-export.**~~ **`_v2`, driven by one constant.**
      `C.PRODUCT_VERSION = 2` now defaults `C.product_name()` and interpolates into
      `MONTH_OF_BURN_COL` and `ANNUAL_BURNED_VECTORS`, so 07a/07c/07d/07e all write v2 and v1 stays
      readable. Brazil copies v2 over the public asset, so no public id changes.
      [docs/07 §1.2](collection-01/docs/07-vector_to_raster.md).

## Next — run: re-export the products

Three independent branches. 
- A blocks the factsheet and the platform; 
- B is parallel, just for completeness; 
- C is the scar-size path, blocks the platform.

Everything reads the filtered object set, so nothing here starts before the
thresholds are fixed and wired.

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
      `--set-props`. Needed for the
      fire-count analyses and it is the layer early users already have a link to.
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

## Next — run + a little code: the summary statistics

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

## Next — the factsheet (data due ~16 Sep)

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
- [ ] **Fix the stale doc pointers in code comments.** `docs/11-*.md` no longer exists. Scripts
      still cite it: `07-month_of_burn.py`, `07-calendar_scars.R` and `07-burned_area_polygons.py`
      say "docs/11 §2/§2.3" for the agriculture filter — that spec is now
      [docs/07 §1.1](collection-01/docs/07-vector_to_raster.md); `factsheet_object_stats.R` and
      `objects_region_tag.R` say "docs/11 §5.2/§6" for the fire-count family — now
      [docs/09 §9](collection-01/docs/09-statistics.md).
- [ ] **Delete the `FIRE/COLLECTION-1/TESTS/` asset folder** when the September work is done. It
      holds only benchmark assets. Deletions are Iván's to run.

## Not on the critical path

Running in parallel, nothing above depends on them: validation
([docs/10](collection-01/docs/10-validation.md), and the open items in
[`BACKLOG.md`](BACKLOG.md)), the ATBD and methodology page, and the December Bariloche launch
materials.
