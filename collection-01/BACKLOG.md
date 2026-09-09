# Backlog — collection-01

Pending work items not yet scheduled. Add new items at the top of each section.

---

## Validation (step 10)

The point-drawing recipe in `docs/10-validation.md` Appendix B (`stratifiedSample` per stratum)
does not scale — OOMs at country scale in every variant (direct, tuned, by-carta partitioned,
even plain `reduceRegion`). Root cause found 2026-08-31: not `stratum`, not the algorithm — the
**region geometry** (`ARG-Political_Level_1-Pais`, 2M+ edges) makes any op that receives it as
`region=` pay to evaluate containment against it. Fixed by swapping it for a plain
`ee.Geometry.Rectangle` bounding box everywhere it's used as a sampling/reduction region (5/5
failures → 3/3 successes in a controlled test). Full post-mortem in `docs/10-validation.md` §0
and `collection-01/validation/02_sample_pool.py`'s module docstring.

Working implementation pivoted to an **unstratified pool** (`Image.sample()`, no `classBand`,
split by stratum locally in pandas) instead of Appendix B's per-stratum `stratifiedSample` — see
`02_sample_pool.py`. Two-stage: "pool 1" sized only for the initial 100/stratum/year, cheap
(~100-150k pts/year); "pool 2" (below) extends to the 5,000/stratum reserve later.

- [ ] **CEO Geo-Dash: add an NBR chart + a delta-NBR image, for 2003/2013/2022.** Goal: let the
  validator resolve obvious burn/no-burn calls fast without leaving the point-review UI. Needs an
  NBR time-series chart (pre-/post-fire window per point) and a delta-NBR image panel, wired for
  the three sampled fire-years only. Lives in Geo-Dash / `ceo_val_00_template` config (repo
  `fuego`), not this repo — scope and exact config approach not yet worked out.
- [x] **Pool 1 + frozen lists for all 3 fire-years** (2026-08-31). 2003/2013/2022, 9 lists total
  in `outputs/frozen/`, all comfortably above the initial-100 floor (worst case S1/fy2022: 506).
- [x] **`03_ceo_export.py --export --all-years`** run, 3 `ceo_upload_fy<FY>.csv` (300 rows each,
  100/stratum, shuffled) produced and manually uploaded as GEE table assets (no automated
  path — `osgeo`/GDAL isn't installed in this repo's venv, and CSV-direct upload via the Code
  Editor's Assets → NEW → CSV file worked fine, no need for the shapefile-zip route
  `objects_upload.py` uses elsewhere): `projects/mapbiomas-argentina/assets/FIRE/VALIDATION/
  ceo_points/ceo_points_fy<2003|2013|2022>`.
- [ ] **Update `ceo_val_00_template`** (repo `fuego`, not this repo) — `POINTS_ASSET_PREFIX`
  still points at the `ceo_points_demo_sierras_cordoba_fy` demo asset from testing. Needs to
  point at `ceo_points_fy` before real interpretation starts. Iván's side (GEE JS repo).
- [ ] **Pool 2 — extend to the 5,000/stratum reserve.** Mechanism decided, not built: reuse
  `draw_pool()` with a bigger N (sized the same way as pool 1, via `size_full_draw()` against
  each year's own pilot counts), de-duplicate against pool 1's frozen `(col, row)` (collision
  rate negligible at these scales, ~0.03% — no need for an exclusion mask), append ranked after
  pool 1's existing rows. Pool 1's frozen rows/ranks must never be touched (design §5 rule 6).
- [ ] **Exact-`Nh` pixel census (docs §4.4).** `01_strata_export.py --weights-launch` (country-wide
  `reduceRegion`) was never re-tested with the geometry fix — don't assume it's still broken,
  verify first; it very plausibly works now given the same fix applied cleanly to `sample()` and
  `reduceRegions`-by-carta both use the same region-geometry mechanism. If it still fails, the
  pool's own realized per-stratum proportions are already a usable `Wh` estimate (tight — see
  `docs/10-validation.md` §0/§7) as a fallback, pending the team's sign-off on using an estimate
  vs. an exact census as the frozen fingerprint.

---

## Data preparation

This is probably for collection 2.

- [ ] **Reconcile CHACO `id_local` gaps in the `areas_regiones` sheet vs the remap.** The remap's
  `local_class` "ID=NN" ids are missing from the sheet for some Chaco classes, so the long-run
  area crosswalk drops/undercounts them: **grassland_chaco (veg_fire 13)** ids 42/43 → 0 km²,
  **shrubland-open_chaco (veg_fire 23)** ids 44/45 → undercounted. This biases the area weights in
  `notebooks/lr_term_pruning.qmd` (worked around by imputing the **median** area to zero-area
  classes) and `land_cover_remap.qmd`'s `area_frac`. Fix the sheet ids (or the remap
  `local_class`), then drop the median workaround.
- [ ] Sample training points for the 3 missing fires in BA (check `training_locations_status.txt`). The fires are commented in the script that creates the training_fires asset. They must be included in that asset and then, points must be sampled.
- [ ] Add a column to the `toma_de_muestras` Drive table to flag whether the exported GEE asset exists and is validated. A lot of `training_locations` files were not exported, and doing that takes time.

---

## Burn probability model (obs)

- [ ] Refine models. In Collection 1 the set was hardly decreased so that glmnet converged, but maybe that was not so necessary; maybe we can prune highly correlated variables by veg_fire class, not globally. Anyway, keeping a smaller set is good for reducing the prediction compute.

---

## Diagnostics / notebooks

- [x] **Per-fire NBR / NBR2 / burn-probability time-series plot (for Lican).** Add a per-fire
  diagnostic to `notebooks/model_fit_diagnostics.qmd` (or a sibling) to spot fires whose
  pre-/post-fire date windows are mis-defined. A 3-facet "spaghetti" time series per fire —
  rows: **NBR**, **NBR2**, **OOF-predicted burn probability**; x-axis: observation date; one
  line per training point (`point_id`); colour by burned vs unburned. Reading: if burned
  points' predicted probability stays low across the post-fire window, the post-fire date was
  likely set too generously.
  - Use the **OOF** probability (`p_oof` from `models/class_NN_oof_predictions.csv`), not an
    in-sample refit.
  - Auto-flag fires: plot only those whose **median `p_oof` over burned obs** is below a
    threshold (notebook param, default 0.6); allow an optional manual `fire_id` override.
  - Data (both git-ignored — download separately): `data/training_observations_{region}_v1.csv`
    (`NBR`, `NBR2`, `date`, `point_id`, `fire_id`, `region`, `burned`) joined to
    `models/class_NN_oof_predictions.csv` on `(region, fire_id, point_id, date)`. Key fires
    region-uniquely (`region_fire_id = paste(region, fire_id)`).
  - Lican has reference code from collection-00 that produced this plot (not in this repo) — adapt it.

---

## Prediction pipeline (step 03 — bp-ts export)

- [ ] **Handle write-permission failures on the output collection.** Several users hit
  `Error: Insufficient permissions to create asset
  'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/WORKFLOW-EXPORTS/bp_ts_metrics/bpts_YYYY_<carta>'`
  (Error code 3). It's a **write-ACL** problem on the destination collection (separate from the
  Celda 2 compute project): the authenticated account lacks Writer on `.../bp_ts_metrics`, or they
  authenticated with an email not in the permissions table. Two things to build:
  - A **pre-flight check** in the notebook that, right after auth, verifies the account can write
    to the output collection and fails loudly with a clear message — instead of failing tile by tile.
  - An admin **batch-grant script/checklist**: give Writer on `.../WORKFLOW-EXPORTS/bp_ts_metrics`
    (or a parent folder) to every email in the permissions table.
- [ ] **Make the compute project selectable in the Colab export notebook
  (`scripts/colab_bpts_export.ipynb`).** Celda 2 now hardcodes `GEE_PROJECT = 'mapbiomas-argentina'`
  (switched from `mapbiomas-fire-485203`, which kept failing for several accounts). If the fire
  project gets fixed, let users choose between `mapbiomas-argentina` and `mapbiomas-fire` as the
  compute project (e.g. a variable at the top of Celda 2 with the alternative commented). Confirm
  which project each account can actually initialize/export with before making it the default.

---

## Calendar-year products (step 07)

Built 2026-07-29/30 (`docs/07-vector_to_raster.md`). **All 12 product images and the 27 scar FCs are
landed and verified on the exported assets** — docs/08 §7 is the delivery checklist.

**Next actions, in order** (everything else in this section is history, kept for the reasoning):

1. **Share `burned_area_polygons_v1` with early users** — it is done and verified (2026-07-31).
   1,263,079 rows / 1,263,076 objects / **69.12 Mha per object**, `--verify` clean on all 28
   fire-years, 19 asset properties set, dates ISO `YYYY-MM-DD`, `filterDate()` working. Point users at
   docs/07 §13.3 (`calendar_year` is the object's *modal* year and will not cross-tabulate exactly
   against the rasters) and §13.7 (`oid` identifies an object, not a row — one FY2000 fire is 4 rows,
   so a row-sum of `area_ha` overstates the layer by 5.1 Mha).
   - [ ] **Run the prepared deletion** of the two per-fire-year test assets and their folder:
     `$PYTHON collection-01/scripts/delete_07e_by_year_assets.py --apply` (dry run by default; it
     guards on the merged layer existing with 1,263,079 features, asserts type and path per asset,
     and refuses a non-empty folder). The `--per-year` / `--year` code is already gone.
   - [ ] **Re-ingest `objects_raw_2021` (step 06) — the root cause.** The `distinct('oid')` guard in
     `fires()` protects this one layer; the stored duplication is still there for anything else that
     reads that asset. Note the audit method: any count over a *plain filtered stored* collection is
     answered from metadata, so insert a `.map()` before trusting a feature count.
   - [ ] **Look at `2000_57529` in QGIS.** A single fire object of **1,706,171 ha** is extraordinary —
     it may be genuine for FY2000 or a segmentation artifact merging many fires. It is 22 % of FY2000's
     mapped area and the reason the layer's area figure needed a 5.1 Mha correction, so it is worth an
     eye before the ATBD quotes anything about the largest mapped fires.
2. **Regenerate `scars_<Y>_months.csv`** (`07-calendar_scars.R` pass 2, from `scars-pixels-cache`),
   then `07-month_of_burn.py --all --stats-read` — the last unrun verification of the month product.
3. **The network's visual validation gate** (docs/08 §2): `1-Toolkit_Collection1/Visualize-Collections-Fire`
   over a few years by eye, before IPAM copies anything to `mapbiomas-public`.
4. **Ask IPAM the three open questions** (docs/08 §8): #9 `frequency_burned`'s band name — the only one
   that changes an asset — plus #1 the `COLLECTION-1` spelling and #8 whether we may publish the
   fire-year vectors.
5. **Then the statistics stage** (docs/09), which cannot start before the territorial-layer decision —
   deferred to ~20 Aug 2026, see below.

What remains, in detail:

- [x] **27 calendar-year scar FeatureCollections ingested and verified** (2026-07-29).
  `annual_burned_vectors/scars_<Y>`, 1999-2025. Both gates pass: `validate_scar_zips.py` 27/27 on the
  packages, and `--ingested` 27/27 on what landed — every year's feature count and `area_ha` total
  matching the local build, and `scar_id` surviving the DBF round trip as an integer (a string would
  have failed `ee.Image().paint` only at raster time). Mask agreement checked on 2003/2020/2025:
  `month px == scar px`, `month-only = scar-only = 0`.
- [x] **Unused scar-raster export path deleted** (2026-07-29). All three monolithic tasks succeeded,
  so `--per-year` / `--merge`, `export_per_year` / `merge_per_year`, `SCAR_PARTS_COL`,
  `ensure_container` and the `--roi` smoke test are gone from `07-scar_rasters.py`, along with their
  paragraphs here and in docs/07. No GEE limit was ever measured against the monolith — it simply
  worked, and that one line is all the record it needs. `--roi` survives as the `--check` extent only.
  Two fixes went in with it: the export now **skips an asset that already exists** (a re-`--launch`
  would otherwise grind through the whole country and die on "cannot overwrite"), and task
  descriptions are namespaced `arg07c_<subproduct>` for the shared-project reason in docs/07 §12.7.
  - [x] **`FINAL_PRODUCTS/scar_year_parts` deleted** (2026-07-29) — an empty IMAGE_COLLECTION left by
    an early `--per-year` dry run (that dry-run-creates-assets bug is itself already fixed). Iván
    authorised this one deletion explicitly as an exception to the "user runs deletions" rule; the
    script asserted type, path and 0 children before deleting, and re-listed afterwards (3 products +
    27 scar FCs intact). The `*_roitest` assets were already gone.
- [ ] **Cross-check the local and GEE masks per year.** `objects-scars/scars_<Y>_months.csv` holds
  the per-month pixel histogram from the local build; `07-month_of_burn.py --check` gives the same
  histogram from the raster. They should match exactly — both derive from the same object pixel set,
  which was verified exact — so any divergence is a real bug, not tolerance.
  **The whole-country half has failed twice at export time and is on its third submission** — both
  failures in how the result is WRITTEN, never in the reduce (docs/07 §7):
  1. `ee.Feature(None, …)` cannot go into a table **asset** — *"Unable to export features with null
     geometry"*. Fixed 2026-07-29 with a placeholder point.
  2. all 27 then FAILED with *"invalid type `Dictionary<Long>`"* — a table asset's properties are
     **scalars**, so a `frequencyHistogram` dict cannot be one. Fixed 2026-07-30: flattened to
     `m01`…`m12` + `n_px`, counted with `img.eq(m)` and **`sum().unweighted()`** (the default weights
     partial pixels at the region edge and would leave the check permanently a few pixels off).
     Validated on the Chaco box first — integer scalars, `n_px = 32,559` for 2020, matching §9.1.
     **27 tasks relaunched 2026-07-30 21:23.**
  ⚠️ **The local half is missing from disk**: `data/objects-scars` is currently a 6.3 MB serialized
  data.table, not the directory holding `scars_<Y>_months.csv`, and `data/scars-upload-cache` is empty
  (the store was mid-Insync-sync on 2026-07-30). Regenerate the months CSVs — pass 2 only, from
  `scars-pixels-cache` — before `--stats-read` can report anything but `no local months csv`.
- [x] **Sub-step 07e — the merged fire-object polygon layer** (2026-07-30/31).
  `FINAL_PRODUCTS/burned_area_polygons_v1`: all 28 fire-years of `objects_raw` filtered to
  `fire == 1 & area_ha >= 1`, stripped to ten properties (`oid`, `fire_year`, `calendar_year`,
  `area_ha`, `date_med/min/max`, `p_mean`, `p_width`, `seed_mean`), merged and flattened —
  **1,263,079 rows for 1,263,076 objects, 69.12 Mha** (a row-sum says 74.23 Mha — one FY2000 object is
  4 rows, docs/07 §13.7). Dates are ISO `YYYY-MM-DD` and `system:time_start` is stamped from
  `date_med`, so the layer answers `filterDate()` (§13.2.1). Verified: `--verify` clean on all 28
  fire-years, 19 asset properties set, `filterDate` and the ISO string filter returning the same
  71,754 features for 2020. `workflow/07-burned_area_polygons.py`, docs/07 §13.
  - **It took three exports**, and the two failures are the lesson (§13.6): both landed COMPLETE with
    1,249 duplicate FY2021 rows because **`objects_raw_2021` is duplicated in storage and no
    metadata-level count reveals it** — `size()`, `aggregate_count('oid')` and `aggregate_array('oid')`
    all report 53,263 on the filtered source, while ITERATING it (put a `.map()` in the chain) returns
    54,514. Fixed with `distinct('oid')` in `fires()`, skipped for FY2000 whose 4 rows are a real
    vertex split. The first diagnosis — a random shard retry in the writer — was wrong, and the
    re-export reproducing the *same* 1,249 oids is what disproved it.
  - **`--per-year` / `--year` deleted** (2026-07-31). Kept as insurance against a 1.26 M-feature task
    landing wrong, it protected nothing: FY2021 exported *alone* duplicated identically, so export size
    was never the variable. Three merged tasks have now completed (2.6-3.7 h each) and
    `User memory limit exceeded` never appeared. It did earn its keep as a test vehicle — `--year 2012`
    proved ISO dates and `system:time_start` survive a table export, `--year 2021` located the bug.
  - ⚠️ This **overrides docs/08 open #8**, which parked the fire-year vectors outside `FINAL_PRODUCTS`
    until IPAM rules on publishing them. If the ruling is no, the asset moves and the shared link dies.
- [x] **Sub-step 07d built and launched** (2026-07-29) — `workflow/07-subproducts.py`, 9 export tasks.
  All nine derive from 07a's month collection plus the LULC; encodings copied verbatim from the
  reference (docs/07 §12), the `accumulate1` filename typo not copied. Verified before launch: band
  counts 27/27/27/27/53/53/53/53/27, every coverage code decoding exactly (`mc//100 == month`,
  `mc mod 100 == L`, `fc//100 == freq`, `acc_cov == L`), `freq_2025_2025 == annual_2025` to the pixel,
  and `frequency`/`accumulated`/`accumulated_coverage`/`year_last_fire` agreeing on 241,281 px in the
  audit box. See docs/07 §12.5-§12.6.
- [x] **LULC to 2025 — closed, and moot** (2026-07-29). The four `*_coverage` products now cross
  against **LULC collection 3 v1** (`C.PRODUCT_LULC`, Iván's call), which carries
  `classification_2025` natively — nothing is duplicated forward. `C.PRODUCT_LULC` is a **separate
  constant from `C.MAPBIOMAS_LULC`** on purpose: the latter is the model-side input `veg_fire` (and
  hence the whole SNIC candidate set) was built from at col-2 v8 and must stay frozen there, while
  the published products track whatever LULC Argentina publishes. Verified col-3 v1 has a
  byte-identical grid to col-2 v8 (so the lattice proof and decode audit transferred untouched), a
  footprint containing the 2 km buffer, and the same class codes with **max 77 < 100** — which is
  what makes `M*100 + L` decodable and `mod 100` exact. docs/07 §12.1/§12.4.
  - If a **col-3 v2** lands, this is a one-line change to `C.PRODUCT_LULC` plus a re-export of the
    four coverage products (they will need deleting first, or `--overwrite` adding to the script).
- [x] **`LEGACY_DESCRIPTIONS` dropped from `07-subproducts.py`** (2026-07-30), all nine tasks having
  finished. The first batch used the BARE subproduct name as the task description; the namespaced
  `arg07d_<subproduct>` (`TASK_PREFIX`) replaced it because `listOperations()` is **project-scoped and
  cross-user** — the shared `mapbiomas-fire` project had 226 tasks from other countries' teams, and a
  bare `annual_burned` colliding with one of theirs would make the in-flight check silently skip one
  of our products. docs/07 §12.7. `07-scar_rasters.py` was checked at the same time and already
  namespaces its descriptions `arg07c_` — nothing to do there.
- [x] **The nine subproducts' property blocks repaired in place** (2026-07-30, docs/07 §12.8) —
  `ee.data.updateAsset`, metadata only, no re-export; bands/dtypes/pyramiding re-read afterwards and
  untouched. The five non-coverage products were advertising a `lulc_asset` they never cross in (and a
  pre-col-3 one, since only the coverage products were re-exported against col-3), and
  `monthly_burned` had inherited the **1999** month image's own `year` / `fire_years` / `name` /
  `pixel_unit` / … through `ee.Image.cat`. Both fixed at the source too: the script now stamps
  `lulc_asset` only on the four coverage products, and inserts an `.add(0)` — a band-wise op, which
  drops input properties — before renaming `monthly_burned`, so a re-export comes out clean.
  **`scripts/audit_product_properties.py`** is the standing drift check (dry run by default,
  `--apply` to write); run it after any re-export or any move of `C.PRODUCT_LULC`.
- [ ] **The territorial layer — NOT before ~20 August 2026** (Iván, 2026-07-29). Not needed for the
  31 July assets, and **which territories to cut by is undecided** — possibly a **vegetation-units
  map** rather than the 5 fire regions. That decision comes first; the layer is mechanical after it.
  docs/08 §8.10. What follows applies only if the 5 fire regions win:
- [ ] **Build `regiones_fuego_argentina_v1` as a FeatureCollection.** ⚠️ **The premise was wrong**: a
  5-feature region VECTOR does exist — `ANCILLARY_DATA/VECTOR/ARG/regiones_arg_col1_simplificada_num`,
  with `Region` (`Pampas`, `Bosque Atlantico`, `Puna,Monte y Altos Andes`, `Patagonia`, `Chaco`) and an
  integer `Zona` 1-5 (found 2026-07-29). So this is a rename/reproperty job, not a build from the
  raster. Two things to check before relying on it:
  - **`Zona` numbering vs `REGION_RASTER`'s `region_id`** — NOT verified to agree. Zona is
    Puna/Monte=1, Patagonia=2, Pampas=3, Chaco=4, BA=5, which is not `C.REGIONS` order.
  - **It is `simplificada`** — simplified geometry. Fine as an export geometry or a `region` property
    source; do NOT assume it is adequate for the area statistics, which are checked to ~1 % (docs/09)
    and whose authoritative regions are the raster.
- [x] **Scar-size ranges settled — the published legend's, not the reference script's** (2026-07-29).
  Confirmed from the Coleção 5 legend-code PDF and the live Fogo col-5 platform legend, so no IPAM
  ruling was needed. `C.SCAR_SIZE_LOWER_HA = [10, 250, 500, 5000, 10000, 50000, 100000]`; we write
  level 2 (1-8) only and the platform derives level 1. Measured check: all 8 classes are populated
  for Argentina (24 scars >= 100,000 ha), so docs/08's guess that the reference's smaller ranges
  suited us was wrong. Do NOT copy `6-export_scar_size_range_by_year`.
- [ ] **ATBD note: FY2025 has no Patagonian dieback padding** (it needs the FY2026 image), so the
  last year of the series is asymmetric in that one respect.
- [ ] **ATBD note: ~76 kha of mapped Nov–Dec 1998 burned area is in no published product.** The
  calendar series starts 1999, so FY1998's Nov–Dec 1998 part (1,058,206 px) has nowhere to go. Both
  edges of the series are therefore asymmetric: 1998 loses its Nov–Dec tail, 2025 loses its dieback
  padding. Verified: every other fire-year's pixels are accounted for exactly (docs/07 §2).
- [ ] Cosmetic: the month images are named
  `mapbiomas_argentina_fire_collection1_fire_mask_v1_<year>`, carrying `v1` mid-name. Only the `year`
  property is read downstream, so this is harmless — but rename before the publish copy if at all.

---

## Object model (step 06)

- [x] **`fire_year` / `year_calendar` were leaking the labels — removed, model refitted**
  (2026-07-28). Symptom: fire-year 1998 called **100.0 %** fire, 2012 96.6 %, 2013 93.3 %. Cause:
  per-year label prevalence is an artifact of where collaborators drew (0.00 to 1.00 across years,
  seven years unlabelled), and with the year available the model read it as a lookup — those two
  columns took **18.4 % of all splits** in the forest, the top two of 22. Grid-blocked CV could not
  see it: every fold holds 17–20 of the 21 labelled years. Fix: no absolute time
  coordinate; `doy_median` replaced by circular `doy_sin`/`doy_cos` (the fire season straddles
  Dec/Jan, so an axis-aligned tree cannot express it in raw DOY); `date_span` kept as a duration.
  `year_calendar` and `fire_year` keep their product/key roles. Result, on the same grid-5 folds:

  | | leaky (22) | fixed (21) |
  |---|---|---|
  | pooled OOF AUC | 0.9211 | 0.8948 |
  | n-weighted **within-year** OOF AUC | 0.8400 | **0.8467** |
  | Spearman(label prevalence, % called fire) over all objects | **0.829** | **−0.082** |
  | per-year fire rate, range / sd | 20.1–100.0 % / 20.7 | 62.6–83.6 % / 5.1 |

  The pooled AUC fell because the leak is gone; **within-year discrimination held**, which is the
  signature of removing leakage without losing real skill. Thresholds re-derived (all four cuts
  moved) and all 28 years re-scored. Old outputs kept under
  `data/objects-pred/stale-leaky-model/`. Full record: docs/06 §4; the standing diagnostic is
  `notebooks/objects-analysis.qmd` §8.
- [x] **`n_mean` dropped — deployed model is 20 predictors** (2026-07-28). `n_mean` was carried as a
  **proxy for polygon quality** (how well-observed each object is) but is a **soft era proxy**: Landsat
  observation density rises across the record (L5, +L7 1999, +L8 2013, +L9 2021), Spearman(fire_year,
  mean `n_mean`) = **0.81**, and with it in the model the per-year fire rate inherited a **0.79** time
  trend — an improving archive masquerading as a rising fire regime, in a collection built for trend
  analysis. Dropping it is cheap because `seed_mean` already carries observation quality
  **density-normalised**: the step-04 seed threshold K is chosen per pixel by `(veg_fire, n)`
  (docs/04 §4.1), which is why the two are near-orthogonal per object (Spearman **+0.014**) and
  seed_mean's own era trend is much weaker (+0.45 vs +0.81). Identical grid-5 folds:

  | | with `n_mean` (21) | **deployed, without (20)** |
  |---|---|---|
  | pooled OOF AUC | 0.8948 | 0.8907 |
  | within-year OOF AUC | 0.8467 | 0.8453 |
  | mean Youden J across bands | 0.713 | 0.694 |
  | **residual time trend** Spearman / Pearson | **0.789 / 0.760** | **0.407 / 0.325** |
  | observation density vs fire rate, Spearman / Pearson | 0.906 / 0.889 | 0.381 / 0.348 |
  | per-year fire rate: range / sd | 62.6–83.6 % / 5.0 | 71.0–83.7 % / 3.0 |

  Trend roughly halved for **0.0014** of within-year AUC. The 21-predictor variant and all the
  variant-selection machinery have been removed — a single model, no `OBJ_VARIANT`. Deployed cuts:
  0.250 / 0.202 / 0.436 / 0.690. The residual 0.407 trend is **unattributed**, not proven clean:
  don't publish it as a fire-regime finding without an independent record. Record: docs/06 §4;
  standing diagnostic `notebooks/objects-analysis.qmd` §8.1.
- [x] **docs/06 rewritten and its stale statistics refreshed** (2026-07-28). Every figure in the doc
  is now measured on the deployed 20-predictor model: the whole-population uncertainty table (mean
  `p_width` **0.317**, **31.3 %** undecided), the size-stratified out-of-fold metrics (AUC 0.871 in
  1–50 ha up to 0.923 above 300 ha, recomputed from `oof_grid_5.csv`), the model-vs-collection-00
  cross-tab (**26.6 %** of area in disagreement; `c00 only ≥300 ha` = 5872 objects / 6397 kha), and
  the threshold area-cost figures. The 22→21→20-predictor turns are compressed to one record each
  rather than restated as comparisons, and the veg-aggregation AUCs are marked historical. Two
  corrections worth noting: 1–50 ha is **61 % of the labels but 83 % of the population** (the doc had
  been quoting the label share as if it were the population share), and the upload section now
  documents the actual route — **the whole object set, not the fire subset**.
- [ ] **Collection 2: stop computing `n_mean` and `n_pixels`** in the step-05 object summaries.
  `n_mean` is an era proxy (see the closed item above). `n_pixels` is not a size — the pixel scale is
  latitude-dependent — and the importance analysis puts it **last of 20** on every measure
  (permutation |Δp| 0.0006, AUC drop 0.0000, ALE range 0.008), so `area_ha` carries everything it
  does. Recorded at docs/05 §2.4 and docs/06 §4.
- [x] **Aggregated vegetation fractions in the object model** (2026-07-27). Five summed fractions
  (`frac_agri`, `frac_grass_inund`, `frac_pasture`, `frac_grass_temp`, `frac_woody`, derived from
  `config/veg_fire_remap.csv` by name) replaced the 23 raw class fractions: 22 predictors instead of
  40. Better on every grid-blocked metric (AUC 0.902 → 0.921, accuracy 0.786 → 0.812), gain
  concentrated in the weak 1–50 ha band (0.872 → 0.903). The 40-column alternative has been removed
  from the code. See docs/06 §4.
- [x] **Classification threshold chosen on out-of-fold predictions** (2026-07-27,
  `scripts/objects_threshold.R`). Youden's J per size band, on `oof_grid_5.csv`: the cut
  RISES with size — then 1–50 ha 0.180, 50–300 ha 0.405, ≥300 ha 0.598 — with barely
  overlapping bootstrap intervals, so the per-band difference is real. Written to
  `config/object_model_thresholds.csv` and applied by `06-object_model.R predict`. *(Those cuts were
  measured on the pre-leak-fix model; the deployed set is **0.250 / 0.202 / 0.436 / 0.690** — the
  rises-with-size finding survived the refit. Current figures: docs/06 §6.)*
- [x] **All 28 fire-years scored + whole-population size/uncertainty exploration** (2026-07-27).
  `scripts/run_06_predict.sh` (parallel, one process per year — stochtree prediction is
  single-threaded) scored 1 689 383 objects in **4m33s**. `notebooks/objects-analysis.qmd`
  holds the result: uncertainty falls with size but the model is unsure **everywhere**, so the
  minimum-size case is cost/benefit — 1 ha drops 3.4 % of objects for 0.044 % of area — not "the model
  can't classify them". *(On the deployed model: mean `p_width` 0.412 → 0.129 across size classes,
  global 0.317, 31.3 % of intervals straddling their cut. docs/06 §9.)*
- [ ] **Decide and record the collection's minimum mapped fire size.** The evidence is now in
  (docs/06 table); 1 ha is the defensible default, 0.5 ha if we want to keep everything that costs
  nothing (0.005 % of area). Needs to be stated in the ATBD and applied consistently in step 07.
- [ ] **Explain the `n_pixels` dip at 3–5 px** (3796 objects at 1 px, 778 at 5 px, then a monotone
  climb to 12 474 at 20 px). Not a segmentation floor — a floor cuts, it does not dip. Prime suspect
  is the step-05 1-px dilation connectivity hack (docs/05). Negligible area; check in QGIS.
- [ ] **A RANDOMLY SAMPLED set of small-object labels, to calibrate the threshold level.** This is
  now the binding limitation, and it is a collection task, not a modelling one. Youden's J is
  prevalence-invariant as a *measure*, but the cut it selects is optimal for the prevalence of the
  set it was chosen on, and our labels are not a random sample of objects: labelled prevalence in
  1–50 ha is 0.47, while most of the 1.4 M real objects in that band are presumably noise. Applied
  to the population the band cuts call **78.6 %** of 1–50 ha objects fire, which is not a plausible
  population rate — and the rate stays high at 0.5, so it is the sampling, not the cut. Reassuringly
  the area cost is small either way (on FY2020, +13 404 objects for +68 kha of 4841), so this bounds
  object-count commission, not the headline area. Until a random sample exists, treat **0.202** as the
  LOWER bound of the defensible range for the 1–50 ha cut.
- [ ] **More labels in the 1–50 ha band**, which holds **83 % of all objects** (but only 61 % of the
  labels — it is under-sampled relative to how many there are) and is where the model is weakest
  (grid-blocked OOF AUC 0.871 vs 0.923 above 300 ha). Aim round-2 collection with `p_width` from the
  `predict all` output.

---

*Format: `- [ ]` open, `- [x]` done.*
