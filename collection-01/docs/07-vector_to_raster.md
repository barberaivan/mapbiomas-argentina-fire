# 07 — From classified objects to the calendar-year pixels

Step 07 is the hand-off from *our* mapping method to the network's calendar-year products. It turns
the step-06 fire-year objects into burned **pixels** on a calendar year: which objects contribute at
all, which year and month each of their pixels belongs to, and the three sub-steps that write that
out — 07a the month-of-burn collection, 07b the local scar build, 07c the scar rasters.

**What is packaged from those pixels is the other half**:
[`07-published_products.md`](07-published_products.md) holds the shape every published asset takes,
**07d**'s nine derived subproducts and **07e**'s merged fire-object polygon layer. The order of
operations below spans both files, because the step runs as one sequence.

`docs/08` is a third thing again — Argentina's route through the network's post-processing spec,
written for a reader comparing us with the other countries.

## Order of operations

Run in this order: 07a → 07b → 07c → 07d, each needing the one before it. **07e is independent** —
it reads the step-06 objects directly and can be rebuilt at any time.

| # | Sub-step | Script | Documented in |
|---|---|---|---|
| **07a** | **Month of burn** per calendar year → `CLASSIFICATION_COLLECTIONS/collection1_fire_mask_v<N>` (ImageCollection, one 1-band uint8 image per year, 1–12, masked elsewhere). The pivot everything else reads. | `workflow/07-month_of_burn.py` (GEE) | this file, "07a — the GEE month-of-burn build" |
| **07b** | **Calendar-year scars**, 8-connected, labelled locally → `data/scars-upload-cache/scars_<Y>.zip`, then ingested by hand as `FINAL_PRODUCTS/annual_burned_vectors_v<N>/scars_<Y>` | `workflow/07-calendar_scars.R` + `scripts/run_07_scars.sh` (local, two passes) | this file, "07b — the local scar build" |
| **07c** | **Scar rasters** — `annual_burned_id`, `annual_burned_area_ha`, `annual_burned_scar_size_range`, painted from the ingested scars and masked to 07a | `workflow/07-scar_rasters.py` (GEE) | this file, "07c — the scar rasters, and the mask invariant" |
| **07d** | **The nine derived subproducts** — `monthly_burned`, `annual_burned`, both `*_coverage`, `frequency_burned` (+`_coverage`), `accumulated_burned` (+`_coverage`), `year_last_fire` | `workflow/07-subproducts.py` (GEE) | [`07-published_products.md`](07-published_products.md) |
| **07e** | **The fire-object polygon layer** — every mapped fire, all 28 fire-years, merged into one FC with ten properties, for early users → `FINAL_PRODUCTS/burned_area_polygons_v<N>` | `workflow/07-burned_area_polygons.py` (GEE) | [`07-published_products.md`](07-published_products.md) |

> **Version, not build.** Everything was first built as `_v1` and re-built as `_v2` after two things
> changed underneath: the object selection gained the two exclusion rules
> (**"Object exclusion ruleset"**), and the land cover the `*_coverage` products cross against moved
> from a preliminary col-3 to the published `mapbiomas_argentina_collection3_pb`
> (**"The `_v2` re-export"**). Asset ids carry `v<N>` from `C.PRODUCT_VERSION`; which ones have
> landed at any moment is **`logs/v2-driver/STATUS.md`**, written every 15 minutes, not a table in a
> doc.

Commands, in order:

```bash
# 07a  (re-runnable, skips existing assets).  The exclusion rules of "Object exclusion ruleset" are ON BY DEFAULT and
# v2 is a NEW collection ("The `_v2` re-export"), so no flags and no --overwrite are needed.
$PYTHON collection-01/workflow/07-month_of_burn.py --all --launch

# 07b  — pass 1 must finish before pass 2: a calendar year needs BOTH its fire-years
tmux new-session -d -s s07pix  '/abs/path/collection-01/scripts/run_07_scars.sh pixels -j 5'
tmux new-session -d -s s07scar 'OBJ_CORES=6 /abs/path/collection-01/scripts/run_07_scars.sh scars -j 2'
$PYTHON collection-01/scripts/validate_scar_zips.py              # gate the zips  -> 27/27
$PYTHON collection-01/scripts/validate_scar_zips.py --ingested   # gate the upload -> 27/27

# 07c  (re-runnable, skips existing assets)
$PYTHON collection-01/workflow/07-scar_rasters.py --check --years 2003,2020 --roi=-61.6,-25.6,-61.1,-25.1
$PYTHON collection-01/workflow/07-scar_rasters.py --launch

# 07d and 07e  — see 07-published_products.md
```

`scripts/run_07_scars.sh` is the launcher for 07b (two modes, resumable, biggest-year first, one
process per year — same pattern as `run_05_years.sh` / `run_06_predict.sh`).

**The whole sequence runs unattended** under `scripts/run_07_v2_driver.py`, one cron tick every
15 min (`scripts/v2_driver_tick.sh`), writing `logs/v2-driver/STATUS.md`. It exists because the
gates are hours apart — 07d waits for all 27 month assets, 07c for a manual ingest — and a "sleep,
then launch the next thing" script dies with the session, while cron comes back at boot without a
login. **So it never sleeps**: each tick surveys the world (asset counts in both compute projects,
`.done_fy*` markers, zips on disk, `pgrep`), runs whatever is unblocked, and exits. Everything it
invokes is idempotent, so a repeated tick is a no-op and an interrupted one is retried by the next.

Two traps it had to be taught, both live rules:

* **`listOperations()` is project-scoped** (CLAUDE.md), and this step submits from two accounts —
  07a/07d as comahue on `mapbiomas-argentina`, 07e/07c as gmail on `mapbiomas-fire-485203`. The
  driver polls **both** and maps each task prefix to the project it lives in; a one-project watcher
  reports the other account's task as missing, which is indistinguishable from never having
  submitted it.
* **A resumable launcher reads v1 output as "done".** `run_07_scars.sh` skips a year whose
  `.done_fy*` marker or `.zip` exists, and those were still on disk from v1, so the first survey
  read the scar stages as complete with nothing rebuilt. **Anything gated on a file must be gated
  on a file that v1 cannot have written** — the same argument "The `_v2` re-export" makes for
  versioning assets rather than overwriting them. The v1 local build is archived as
  `data/objects-scars_v1/` and `data/scars-upload-cache_v1/`.

---

## The decisions this step rests on

**The fire layer is the object-level classification.** Only objects with **`fire == 1` and
`area_ha >= 1`**, and which survive the two exclusion rules of "Object exclusion ruleset"**, contribute a pixel. `fire` is the deployed call — the collected label where there
is one, else the model (docs/06 "The three call columns"); `fire_tag == -1` means *unlabelled*, never *not fire*. The
filter is a **positive** selection, not "everything not rejected": 36 objects in the collection are
entirely `candseed==3` dieback, so they have a null `date_median` and a null `fire`, and
"not rejected" would admit them.

**The whole object set is what was uploaded** in step 06 (`objects_raw_<fy>`, 28 FCs, every object
with all 20 predictors), because a fire-only layer can show commission error but never omission,
and the rejected objects are what aims the next label campaign (docs/06 "Upload to GEE"). Step 07 filters at
read time; nothing about the upload changes.

**Calendar year and month are assigned PER PIXEL, from `abs_date`** — not per object from
`year_calendar`. The object-level `year_cal` remains a property of the object database and is not
used by any raster product. Per-pixel is what makes `annual_burned`, `monthly_burned` and
`scar_size` agree pixel-for-pixel (docs/08 "How Argentina's route differs"). The consequence is deliberate: **a fire that
straddles 31 December is split into two calendar years**, and therefore into two scars.

**A `candseed==3` dieback pixel takes its parent object's median date**, not its own `abs_date`
("`candseed == 3`").

**Minimum mapped fire: 1 ha**, applied to the *object* before the calendar split — so a
calendar-year part of a qualifying object may itself be smaller.

### Object exclusion ruleset

The selection is **positive and complete**: an object contributes pixels only if

```
fire == 1  &  area_ha >= 1  &  not(rule A)  &  not(rule B)
```

The rules exist because the per-observation spectral model cannot separate two kinds of
agricultural signal from fire. Harvest, tillage and stubble burning all look like a burn scar, and
the `veg_fire` remap keeps agriculture *burnable*, so cropland pixels were never excluded from the
SNIC candidate set. Fixing it at the **object** level — rather than masking the rasters — is what
keeps the vector layer and every raster identical by construction: it is a statement about *fires we
do not map*, which is the only thing our method is defined in terms of. Masking the rasters instead
would leave area that is in one product and not another.

Each rule names a *set of objects*. The selection above is what excludes them.

#### Rule A — Pampa grassland burning in the winter–spring window, confined

Objects that are almost entirely `grassland_pampa`, **and** burned in the winter–spring window,
**and** are small, **and** lie in the agricultural Pampa.

```
frac_c15 > T_GRASS   AND   T_DATE_FROM <= date_med <= T_DATE_TO
                     AND   area_ha < RULE_A_MAX_HA
                     AND   the object INTERSECTS the rule-A AOI
```

`T_GRASS = 0.70`, window **1 Jul → 15 Nov**, `RULE_A_MAX_HA = 150`, AOI =
`config/rule_a_aoi.geojson`.

##### Why rule A is confined, and not a bare composition threshold

Two confinements were added on 2026-09-12, after an unconfined rule A was found to be deleting real
fire at scale.

**`veg_fire` 15 is not only Pampa pasture.** It is the remap of MapBiomas 11 Herbáceas Inundables +
12 Herbáceas + 15 Pasturas *in the PAMPA region* (`config/veg_fire_remap.csv`), so the marshes of
the **Delta del Paraná** carry class 15 exactly as a Pampa pasture does — and the Delta burns inside
1 Jul → 15 Nov. Unconfined, the rule deleted **two thirds of the Delta's burned area**, including
the 121 kha Islas del Paraná fire of 2020, and it bit hardest in the big Delta fire years, so it
distorted the interannual series and not merely the level. **The AOI** — a hand-drawn 25-vertex
polygon over the agricultural Pampa, `config/rule_a_aoi.geojson` — excludes the Delta and Campos y
Malezales entirely. **The size cut** (`RULE_A_MAX_HA = 150`) exists because rule A's drop was
bimodal: harvest, tillage and stubble burning happen on fields, and a 121 kha scar is not a field.
Measurements: [`notes/07-exclusion_rules_choice.md`](notes/07-exclusion_rules_choice.md).

Three things about the AOI that are load-bearing:

- **Re-run `scripts/rule_a_aoi_extract.py` whenever the polygon is redrawn.** It pulls `aoiA` out of
  the pushed GEE explorer, and the GeoJSON in the repo is the only copy production reads.
- **INTERSECTS, not centroid.** An object that merely touches the AOI is inside it — the rule is a
  statement about a region, and a scar straddling the edge is half in the agricultural Pampa. The
  local side uses `terra::is.related(v, aoi, "intersects")`, the predicate, not `terra::intersect()`,
  which would build 78 k clipped geometries a year to throw them away.
- **The AOI must be PLANAR on the GEE side.** `C.rule_a_aoi_ee()` builds it with `geodesic=False`:
  the ring has edges spanning several degrees and a geodesic edge bows away from the straight
  lon/lat line `terra` tests against. Planar, the two implementations agree **to the object**.

`frac_c15` is one single `veg_fire` class — 15, `grassland_pampa`. It deliberately does **not** use
the `frac_gr_tp` predictor, which lumps `grassland_ba + grassland_chaco + grassland_pampa`: the rule
is about the Pampa alone.

**The date test is what makes this rule.** It is a composition threshold *and* a season: an object
that is almost entirely Pampa grassland is excluded if it burned inside the window and mapped if it
burned outside it. Without the season it would delete real Pampa fire.

#### Rule B — agriculture, anywhere in the country

Objects with a high agriculture fraction.

```
frac_agri > T_AGRI
```

`T_AGRI = 0.40`, and `frac_agri = frac_c1 + frac_c2 + frac_c3` — the `veg_fire` agriculture classes
`agriculture_{chaco, cuyo-pat, pampa}`, **excluding** class 4 `agriculture-per` (perennials and
orchards, which burn for different reasons and are not the confusion this rule addresses).

Unlike rule A this is unconditional on season and applies everywhere.

#### The thresholds

`T_GRASS = 0.70`, window 1 Jul → 15 Nov, `RULE_A_MAX_HA = 150`, the AOI, `T_AGRI = 0.40`.
Confirmed with the team 2026-09-11; **rule A's two confinements added 2026-09-12** after the Delta
problem above was found — and that revision is what `_v2` is built with. Changing any of them means
re-running 07a, 07b, 07c, 07d and 07e and then every statistic, so treat a proposal to change them
as a new collection, not a tweak.

**Rule B was left alone.** Adding a `frac_woody` condition, a `shape_idx` compactness condition and
an area cap to it was explored on 2026-09-12 and rejected: `shape_idx` correlates 0.685 with
log₁₀(area) on raster-derived polygons, so one global threshold acts mostly as a size filter, and
the agri/non-agri distributions overlap heavily below ~25 ha. The knobs survive in the explorer,
off by default.

They live in `utils/constants.py` as `C.T_GRASS`, `C.GRASS_WINDOW` and `C.T_AGRI`, and they are the
**default**: a run with no flags produces the published selection. Every script keeps an override
(`--t-grass` / `--t-agri`, or the `T_GRASS` / `T_AGRI` env vars in R) for the explorers and `TESTS/`
exports, and a `--no-exclusions` / `RULES=0` escape for reproducing the pre-rule numbers — and both
are recorded in the asset properties, so an unfiltered run can never be mistaken for a published one.

#### What they remove

| | rule | measured, FY2020, whole country |
|---|---|---|
| **A** | Pampa grassland in the window, **confined** | 8,227 obj / 136,993 ha — **3.2 %** of the year's burned area |
| **B** | agriculture | 2,389 obj / 162,168 ha — **3.8 %** |
| | **A or B** | 10,616 obj / 299,162 ha — **7.0 %** |

Over all 28 fire-years: before the rules **69.12 Mha**, after them **63.33 Mha (−8.4 %)**. An
unconfined rule A would have published 58.05 Mha instead, and that **5.27 Mha** difference is almost
all real fire — the Delta's rule-A loss alone goes from 1.455 Mha to 23 ha. Rule A's **window is the
single biggest lever in the ruleset**; rule B alone drops 2.36 Mha over 28 years with **no trend
across years**, so the national series and its slope are essentially unaffected by that threshold,
and it is not a small-object filter in disguise (median dropped object 14.2 ha, max 10,704 ha).
Per-year and per-ecoregion figures: [`notes/07-exclusion_rules_choice.md`](notes/07-exclusion_rules_choice.md).

**At these thresholds the two rules cannot both fire**, and that is arithmetic, not luck:
`frac_c15 > 0.70` leaves under 0.30 for every other class, so `frac_agri` cannot reach 0.40.
Measured on FY2020 the overlap is **empty**. They can overlap only if the thresholds are moved far
apart.

> **What an object rule cannot fix.** Pixel-weighted, burned area falling on annual cropland is
> 2.95 Mha (4.3 % of the total). Rule B at 0.4 leaves **1.37 Mha of cropland pixels still in the
> map**, inside mixed objects. So the rules fix *what the map looks like* — whole spurious
> crop-field "fires" disappear — but do not make a per-land-cover-class pixel statistic clean.
> That is a caption problem for the factsheet, not something a threshold can solve.

#### Implementation — three application points, one definition

The rules are applied at read time, in the three places that read the object set. They must be given
**identical** thresholds or the products stop describing the same map.

| file | where | mechanism |
|---|---|---|
| `utils/constants.py` | `T_GRASS`, `GRASS_WINDOW`, `RULE_A_MAX_HA`, `RULE_A_AOI_GEOJSON`, `T_AGRI`, `rule_a_aoi_ee()`, `exclusion_rules()` | the single source of truth for the Python side |
| `workflow/07-month_of_burn.py` | `accepted_objects(fire_year, rules=True, …)` | `ee.Filter` on the FC properties + `ee.Filter.bounds(C.rule_a_aoi_ee())` |
| `workflow/07-calendar_scars.R` | `accepted_oids(fy)` | `data.table` predicate on the local metrics CSV + the `in_aoi` tag |
| `workflow/07-burned_area_polygons.py` | `fire_filter(fire_year)` | `ee.Filter`, identical to 07a's |
| `scripts/rule_a_aoi_extract.py` | — | pulls `aoiA` out of the pushed GEE explorer into `config/rule_a_aoi.geojson` |
| `scripts/rule_a_aoi_tag.R` | — | writes `objects-analysis/aoi_rule_a_<fy>.csv`, the `in_aoi` column 07b reads |
| `scripts/rule_a_cap_diagnostic.py` | `settled()` | the diagnostic, same predicate, for measuring |

`07-scar_rasters.py`, `07-subproducts.py` and `scripts/audit_product_properties.py` need no edit:
they stamp and audit `C.exclusion_rules()`, which now words the confined rule A.

**The AOI membership is evaluated ONCE**, by `rule_a_aoi_tag.R`, and 07b reads a column. A spatial
predicate evaluated separately in two languages is exactly the thing that drifts; `accepted_oids()`
**hard-errors** when the tag file is missing or stale rather than silently treating every object as
outside the AOI, which would disable half of rule A and still look plausible.

**All three application points agree to the object**, verified on FY2008, FY2020 and FY2022
against each other and against the GEE explorer — the same counts from `accepted_objects()`,
`fire_filter()` and `accepted_oids()`
([`notes/07-exclusion_rules_choice.md`](notes/07-exclusion_rules_choice.md)). That agreement is the
thing to re-check after any change, because the three are separate implementations of one rule.

⚠️ **07c cannot be brought up to date on its own.** It paints the *ingested* scar FCs and masks them
to 07a, so re-running it against scars built from an unfiltered object set does not just leave an
attribute stale — it paints the **wrong** one. A scar's `area_ha` would still count the cropland
pixels that 07a no longer contains, and a scar that was 8-connected *through* an excluded object
keeps its merged identity instead of splitting in two. Both `annual_burned_id` and
`annual_burned_area_ha` would then disagree with the extent they are painted on. **07b must be
re-run whenever the thresholds change, and 07c after it.**

Details that have already cost time:

- **Column names differ by side.** The GEE FeatureCollection property is **`date_med`**; the local
  metrics CSV column is **`date_median`**. `frac_c15` and `frac_c1..c3` carry the same name on both.
- **`date_med` is a NUMBER of days since 1970-01-01** (18,383 = 2020-05-01) — `objects_upload.py`
  maps `date_median` → `date_med`, and the ISO string is the separate `date_medd`. So the window is
  resolved to day numbers client-side (`C.grass_window_days`), never with an `ee.Date` per feature.
- **The window is anchored inside the fire year.** The fire year runs 1 May *fy* → 30 Apr *fy+1*, so
  a window month ≥ 5 belongs to *fy* and Jan–Apr to *fy+1*. Both bounds inclusive.
- **Both rules exclude on `>`, so the *keep* predicate is `<=`**, not `<`. This is why the FY2020
  count is 2,389 and not the 2,407 an `>=` rule gives.
- **An impossible date must fail loudly.** `Date.UTC` (and R's `as.Date`) would quietly roll `02-30`
  into 2 March; `C.grass_window_days` builds a `datetime.date` and raises instead.
- `07-calendar_scars.R` takes its thresholds from **environment variables**, not arguments, because
  both passes and the launcher call the same function and an env var reaches all of them identically.
  A run cannot end up with one pass filtered and the other not.
- **Every asset records both rules in its properties** — `exclusion_rule_a` and `exclusion_rule_b`,
  built once by `C.exclusion_rules()` so all four products word them identically. An asset that does
  not state its own selection cannot be told apart from one built before the rules existed.

#### The thresholds are settled, and changing one is a new collection

`T_GRASS`, `GRASS_WINDOW`, `RULE_A_MAX_HA`, `RULE_A_AOI_GEOJSON` and `T_AGRI` live in
`utils/constants.py` and are the **default**: a run with no flags produces the published selection.
Confirmed with the team 2026-09-11, rule A's two confinements added 2026-09-12. Changing any of them
means re-running 07a, 07b, 07c, 07d and 07e and then every statistic, so treat a proposal to change
them as a new collection, not a tweak.

They were chosen by eye, with Camilo, from the Earth Engine explorers in the `fuego` repo
(`collection-01/visualization-misc/`). **Pasture is deliberately not in the ruleset** — adding it
would drop 5.78 Mha instead of 2.36 Mha, and pasture fire is largely genuine management burning —
and **rule B was left alone**: a compactness condition was explored and rejected, because
`shape_idx` correlates 0.685 with log₁₀(area) so one global threshold acts mostly as a size filter.
Both survive as options in the explorer, off by default
([`notes/07-exclusion_rules_choice.md`](notes/07-exclusion_rules_choice.md)).

Every script keeps an override (`--t-grass` / `--t-agri`, or the `T_GRASS` / `T_AGRI` env vars in R)
for the explorers and `TESTS/` exports, and a `--no-exclusions` / `RULES=0` escape for reproducing
the pre-rule numbers — and both are recorded in the asset properties, so an unfiltered run can never
be mistaken for a published one.

### The `_v2` re-export

Two things changed under the products after the first launch: the exclusion rules above, and the
land cover the four `*_coverage` products cross against (`C.PRODUCT_LULC` moves from the
preliminary `…_integration_v1_buffer` to the published `mapbiomas_argentina_collection3_pb`). So
**everything step 07 exports is rebuilt, and it is rebuilt as version 2**:

| | v1 | v2 |
|---|---|---|
| month of burn (07a) | `CLASSIFICATION_COLLECTIONS/collection1_fire_mask_v1` | `…_fire_mask_v2` |
| the nine subproducts (07d) | `FINAL_PRODUCTS/mapbiomas_argentina_fire_collection1_<sub>_v1` | `…_<sub>_v2` |
| the three scar rasters (07c) | idem | idem |
| the scar vectors (07b, hand-ingested) | `FINAL_PRODUCTS/annual_burned_vectors` | `…_annual_burned_vectors_v2` |
| the polygon layer (07e) | `FINAL_PRODUCTS/burned_area_polygons_v1` (1,263,076 obj, pre-rule) | `…_v2` (1,012,645 obj) |

One constant drives all of it: **`C.PRODUCT_VERSION = 2`**, which `C.product_name()` defaults to and
which `MONTH_OF_BURN_COL` and `ANNUAL_BURNED_VECTORS` interpolate. Pass `version=1` explicitly to
address an old product deliberately (a v1-vs-v2 comparison).

**Why version rather than overwrite in place.** Agreed with the Brazil team: we write `_v2` on our
side and **they copy it over the public asset**, so the public id — and therefore the Workspace
registration, the `band_format` lookup and every download link — does not change
([`../statistics/docs/statistics.md`](../statistics/docs/statistics.md) §11 "Publication and
launch").
Versioning on our side then buys three things overwriting would not:

1. the v1 products stay readable while v2 is built, so a number can be traced to the layer it came
   from;
2. nothing is ever half-replaced — a failed re-export leaves a complete v1, not a mixture;
3. **the gate on 07d becomes meaningful.** 07d must not start until all 27 month assets exist
   (`docs/07-published_products` "Namespace the task descriptions"); against an overwritten
   collection that count is already 27 before anything has run.

The scar vectors are versioned for the same reason and one more: they are ingested by hand, and a
folder holding a mix of v1 and v2 scars would silently produce a scar raster from the wrong
selection.

---

## The verified calendar-year partition

```
calendar year Y  =  Jan–Apr Y  from fire-year (Y−1)   ⊎   May–Dec Y  from fire-year Y
```

Checked over all 28 fire-years: **no object's `date_min`/`date_max` leaves its own fire-year
window** (1 May *fy* → 30 Apr *fy*+1), 0 exceptions. So the two contributions are disjoint in month
by construction and merging them is a **union**, not an arbitration. `max` only ever decides
genuine **reburn** — a pixel burning Feb *Y* and again Sep *Y* — where the later date wins, which
is what the pixel looks like at year end.

The series is **1999–2025**. FY1998 exists only as its Jan–Apr 1999 part plus a Nov–Dec 1998
remainder; that remainder falls in calendar 1998, which is not published, and the pixels pass
reports it as dropped rather than silently discarding it.

**The pixel accounting closes exactly.** Summing each fire-year's two calendar halves against its
accepted pixel count, **27 of 28 fire-years match to the pixel** (0 difference). The only exception
is FY1998, by construction: **1,058,206 px (~76 kha)** of genuinely mapped Nov–Dec 1998 burned area
sit in calendar 1998 and therefore appear in **no published product**. Totals reconcile —
911,617,919 accepted px, 910,559,713 in the published series, difference exactly 1,058,206. This is
inherent to the series starting at 1999, not a defect, but it should be **stated in the ATBD**:
Argentina's collection maps a fire-year that the calendar-year products cannot fully express at the
lower edge.

One exception to the window rule matters in the code: **dieback pixels genuinely do leave their
fire-year window** (their raw date is Jun–Nov of *fy*+1), so each fire-year's contribution is
filtered with the general test `date ∈ [Y, Y+1)` and is never shortcut to "Jan–Apr for the older
fire-year".

---

## One grid, pinned everywhere

All **56** SNIC assets (28 `snic_<fy>` + 28 `snic_metrics_<fy>`) share one identical projection:

```
EPSG:4326, transform [0.000269494585236, 0, -73.58468801489491,
                      0, -0.000269494585236, -21.764113209062533]
```

and the 248 per-carta tiles in `data/snic-rasters/<fy>/` sit on the same lattice (offset exactly
22578 columns, 0 rows). All 28 fire-years have byte-identical tile footprints. Recorded as
`C.SNIC_CRS` / `C.SNIC_TRANSFORM`.

**Every export pins `crs` + `crsTransform`, never `scale=30`.** `scale: 30` in EPSG:4326 — which
every reference script uses — is a *different* grid: different origin, and 30 m is not that degree
step. A half-pixel shift there would misalign the GEE month raster from the scar rasters painted
from locally-built vectors, which is precisely the thing this step has to get right.

The local side derives the lattice from those constants rather than from a `vrt` of whatever tiles
are on disk, because `cell = (row−1)·NC + col` is the labelling key: if `NC` differed between the
two fire-years feeding a calendar year, unrelated scars would silently merge. The origin is shifted
**one pixel west** of the transform origin, because the westernmost carta starts exactly there —
without the shift `col` would run 0…74085, 74086 distinct values against `NC = 74085`, and
`(row−1)·NC + NC` would collide with `row·NC + 0`.

Lattice: `NC = 74086`, `NR = 123601` (9.16 B cells, matching docs/05).

---

## `candseed == 3`: dieback pixels take the parent object's date

A `candseed==3` pixel is Patagonian slow-dieback padding (docs/04 "Patagonia dieback
padding"): it was a candidate in the *next* year's image with a mid-date in Jun–Nov of *fy*+1. That date is when the **dieback was
detected**, a different physical event from the burn — the pixel has no burn date of its own.

Measured across the 28 fire-years: **881 k such pixels (~79 kha) survive** the step-05 longitude
cut — **4.0 %** of all candidate pixels west of the cut, and **14–18 % in FY2014, 2015, 2021 and
2024**. Their raw dates fall in Jun–Nov (plus ~10 k in April).

Left raw they would do two things:

1. report Andean Patagonia burning in **austral winter** in the monthly product; and
2. whenever the parent fire burned **May–Dec**, fall into the *next* calendar year — splitting the
   scar and minting a **phantom scar** with its own id and size class.

So each dieback pixel takes its **parent object's `date_median`** (`C.DIEBACK_USE_PARENT_DATE`,
`DIEBACK_USE_PARENT_DATE` in the R script). No pixel that has a real measured date is touched, and
`date_med` was already a property on the uploaded FCs, so it costs nothing. The 36 all-dieback
objects have no parent date at all and are filtered out.

**FY2025 has no dieback padding**, because that needs the FY2026 image. The last year of the series
is asymmetric in this one respect — worth a line in the ATBD.

Two step-05 behaviours are replayed rather than re-derived:

- **The longitude cut.** Step 05 dropped `candseed==3` east of **−70.6** *before* labelling, so the
  objects never contained them — but `snic_<fy>` still carries them (65,752 px over 28 fire-years).
  GEE replays the cut with `pixelLonLat`; the local pass gets it for free (the objects are already
  post-cut) and keeps the test as a guard.
- **Objects, not calendar dates, own the `candseed==3` assignment.** Their date being in the "wrong"
  fire-year is not a problem to fix; the substitution removes the question entirely.

---

## The LULC mask and the solitary-pixel filter are embedded upstream

The network's stage 3 applies a LULC mask (water 26 at minimum) and deletes 4-connected components
of ≤ 4 px. **Argentina applies neither at this stage, because both are already in the pipeline —
and more strictly:**

- `veg_fire` is derived from the **previous-year MapBiomas LULC**, and every non-burnable class has
  no `VEG_TABLE` entry, so `THR_DEF = 9` makes it unreachable as a SNIC candidate. Verified on
  FY2000/2014/2023 over ~3.6 M candidate pixels: **zero `candseed>0` pixels on `veg_fire` 24
  (non-burnable) or 25 (non-observed)**. The reference rule drops water only; ours drops every
  non-burnable class.
- The `>= 1 ha` object cut (≈ 11 px, before the calendar split) is stricter than `<= 4 px`.

The collection is still named `collection1_fire_mask_v1`, because that is the asset every
downstream reference script reads, and the images carry `lulc_mask` and `solitary_pixel_filter`
properties recording that it was applied upstream rather than skipped.

---

## Why the object polygons can be trusted as the pixel set

Both sides of this step recover a pixel set from the step-06 polygons, so that had to be exact
rather than approximately right. docs/notes/08-corrections_and_delivery.md warned that "painting a polygon fills its
interior". **It does not**, and this was verified two independent ways:

- **Locally**: `terra::cells(country template, accepted polygons)` for FY2020 returned
  **55,008,255** cells against `sum(n_pixels) = 55,008,255` over the same objects — exact over
  55 M pixels. Every fire-year processed since reports the same `EXACT`.
- **In GEE**: on the audited ROIs, `paint(fc,1)` and the `candseed`-derived burned mask agree with
  **0 painted-but-not-burned** pixels.

The reason is that step 05 vectorized the *accepted pixel set* with `as.polygons(dissolve=TRUE)`,
so holes are true interior rings and the boundary follows pixel edges. Both `terra::cells` and
GEE's `paint` use pixel-centre-in-polygon, so they recover the same set.

The `candseed > 0` intersection is therefore a **guard, not a correction**. It is kept on both
sides, and the residual is logged per year rather than assumed to be zero.

---

## 07a — the GEE month-of-burn build

`07-month_of_burn.py`, per calendar year `Y`, for `fy ∈ {Y−1, Y}`:

1. `fc = objects_raw_<fy>` filtered to `fire == 1 & area_ha >= 1 & date_med` not null.
2. `footprint = ee.Image().paint(fc, 1).gt(0)` — `paint` on an empty image is **masked outside** the
   features, so this is the footprint and nothing else.
3. `burned = candseed > 0 & (candseed != 3 | lon <= −70.6)`.
4. `date = abs_date.where(candseed == 3, paint(fc, 'date_med'))`.
5. `keep = footprint & burned & date ∈ [Y, Y+1)`.
6. `month = Σ_{k=1..12} (date >= first day of month k of Y)` — exact on that interval.

then `ee.ImageCollection([contribution(Y−1), contribution(Y)]).max()`.

GEE has **no per-pixel date decomposition**: `abs_date` is whole days since 1970-01-01 and there is
no per-pixel `ee.Date`, hence the threshold sum. Only 12 comparisons per fire-year, so it is cheap.

Two GEE gotchas are baked into that code, both found the hard way:

- **`paint` the FC once, not twice.** `date_med` is notNull for every feature in `fc`, so the painted
  date band is non-null exactly on the object footprint — its `.mask()` *is* the footprint. The
  earlier version rasterized the same FC twice per fire-year (four times per calendar year) to get
  the footprint and the date separately; rasterizing 20–70 k polygons is the dominant cost of this
  export, so that was double work for nothing.
- **Do NOT replace `ee.Image.pixelLonLat()` with a clipped constant** for the longitude cut, however
  tempting (pixelLonLat materializes two float bands over 9.16 B cells to answer one threshold).
  `clip` sets the image's **footprint** and `unmask(0)` does not reset it, so the subsequent
  `.And()`/`.Or()` intersect footprints and confine the *entire result* to west of the cut. Measured:
  the Chaco audit box, east of the cut, went from 32,546 burned px to **0** — it would have silently
  emptied most of the country while still producing a valid-looking asset.

`--check` audits a **small** ROI: the per-month pixel histogram plus the painted-vs-burned
residual. It exists precisely for the two traps above — both were caught by re-running it against
recorded numbers, not by reading the code. Two ROIs are used, and they check different things:
the **San Ramón** patch, calendar 1999 (a single Feb 1999 fire, `docs/04` "The San Ramón
exception" — and therefore **useless on any other year**, where it correctly reads 0), and a
**Chaco 0.5° box**, where a calendar year draws from both its fire-years and the two land in
disjoint month ranges that sum exactly. Recorded results, graph and landed asset alike:
[`notes/07-verification_log.md`](notes/07-verification_log.md).

The **whole-country** histogram cannot be taken interactively — `reduceRegion(...).getInfo()` over
the 74085 × 123601 grid times out — so `--stats` submits it as a batch task and `--stats-read`
prints it beside `scars_<Y>_months.csv`. That pair is the standing local↔GEE check, and **it has
never completed** ("What is still open"). Two rules came out of getting it to submit at all:

- **A table asset's properties are scalars.** There is no dictionary column, so a
  `frequencyHistogram` dict cannot be a property — flatten it to `m01`…`m12` + `n_px`. And
  `ee.Feature(None, …)` cannot be written to a table *asset* at all (toDrive can, but then
  `--stats-read` cannot read it back), so it needs a placeholder geometry.
- **Count with `sum().unweighted()`, never a bare `reduceRegion`.** The default weights partial
  pixels at the region boundary, which would leave this check permanently a few pixels off the
  local build — the same artefact "07c — the scar rasters" records. `img.eq(m)` keeps the image's
  mask, so it counts burned pixels only and needs no dense `unmask(0)` over 9.16 B cells.

---

## 07b — the local scar build

GEE cannot do the labelling — `connectedPixelCount` caps at 1024 px (≈ 92 ha), far below a real
scar — which is why the reference chain round-trips through Drive and Colab. We label locally from
the carta tiles and object polygons already on disk: no Drive, no download.

The scars are a **separate labelling pass**, not a re-use of the step-05 objects:

- **calendar** year, not fire-year;
- **plain 8-connectivity**, intentionally *not* step 05's 1-px-dilation connectivity, so two
  distinct fires that touch become one scar — which is what the network's definition says;
- a fire straddling 31 December becomes two scars, one per year.

**Two passes**, because each fire-year feeds two calendar years and reading the 248 tiles is the
dominant cost — once per fire-year rather than once per (calendar year, fire-year) halves it:

| Pass | Unit | Does |
|---|---|---|
| `pixels` | fire-year (28) | one sparse `terra::cells()` per fire-year for the accepted-object pixel set → per-tile read of `candseed`+`abs_date` → join on the global cell number → dieback substitution → split into the two calendar halves → `data/scars-pixels-cache/cy<Y>_fy<fy>.rds` (`row`, `col`, `month`) |
| `scars` | calendar year (27) | read the two halves → merge, later month wins on reburn → 8-connected union-find → `area_ha` from the per-row cell area → per-scar vectorize → GPKG + summary CSVs + zipped Shapefile |

Three implementation choices that decide whether this finishes in hours or days:

- **`terra::cells()`, not `rasterize`.** It is sparse — cost and memory scale with the polygons'
  area, not with the template — so one call against the full 9.16 B-cell country template returns
  in ~1 min. `rasterize` would allocate the grid, and per-tile rasterization measured 4–11 h.
- **The cell lookup is keyed the tile's way round.** `d[, obj_date := ct[.(d$cell), on="cell", …]]`
  probes the tile's ~100 k pixels into the keyed object-cell table; `d[ct, on="cell"]` would walk
  all ~55 M object cells once per tile, 248 times per fire-year.
- **`values()` + `which()`, not `as.data.frame(cells=TRUE, na.rm=TRUE)`** — measured 2.3–2.5×
  faster on the tile read, which is the pass's bottleneck, and byte-identical output.

Two smaller ones: the pixel cache carries the object's **integer date**, never its `oid` string
(55 M character entries would cost ~440 MB of pointers and a slow string join); and the reburn
dedup uses `unique(..., by=)` over the sorted table rather than `.SD[1L]` by group, which at ~100 M
rows is orders of magnitude slower.

A handful of pixels carry `candseed > 0` with a **NA `abs_date`**. Step 05 dropped them (its
`na.rm` extract spanned every band), so they belong to no object and both sides exclude them: the
local pass filters them explicitly, and GEE excludes them because they are outside the footprint.

**`scar_id`** is a fresh integer, 1..n within the calendar year, assigned in order of the scar's
first cell — deterministic and stable across re-runs (docs/08 open #5). `oid` cannot be used:
`ee.Image().paint` needs a number.

### The pixel accounting closes exactly

Every accepted object pixel is accounted for across the fire-year → calendar-year transformation,
with three sinks that sum to the input: the 27 published years, the one unpublishable edge year
(FY1998's Nov–Dec 1998 tail, 1,058,206 px) and intra-year reburn (269,043 px, later month kept).
911,617,919 accepted px in, 910,290,670 out, **difference 0**. Nothing is silently lost or
double-counted. Reproduce it from the per-year `scars_<Y>_summary.csv` files plus the `reburn:`
lines in `logs/07_scars_<Y>.log`; the v1 run's own numbers are in
[`notes/07-verification_log.md`](notes/07-verification_log.md).

**No size class is written into the vectors.** It is derived in GEE from `area_ha`
(`C.SCAR_SIZE_LOWER_HA`), so the ranges are a one-line, one-task change rather than 27 re-uploads.
That mattered: the reference script's ranges turned out **not** to match the published legend, and
the classes were switched to the legend's after the vectors were already built
(`docs/external/mapbiomas-fuego-reference.md` "Stage 4, scripts 4–6 — the scar-size chain").

## 07c — the scar rasters, and the mask invariant

`07-scar_rasters.py` paints the ingested `scars_<Y>` FCs into the three subproducts. Two departures
from the reference `5-export_annual_burned_id_and_size_by_year`:

- **Our `area_ha` is painted, not recomputed.** The reference maps
  `area_ha = feat.geometry().area()/10000`. For a pixel-edge polygon with interior rings, GEE's
  geodesic polygon area is not the pixel-count area that every other figure we publish derives
  from, and the statistics stage is checked to ~1 % (statistics/docs/statistics.md).
- **Size classes are applied server-side** from `C.SCAR_SIZE_LOWER_HA`, for the reason in "07b — the local scar build". The
  values are the **published legend's**, not the reference script's: `< 10 / 10–250 / 250–500 /
  500–5 000 / 5 000–10 000 / 10 000–50 000 / 50 000–100 000 / ≥ 100 000 ha`, confirmed from the
  Coleção 5 legend-code PDF and the live col-5 platform legend (docs/external/mapbiomas-fuego-reference.md "Stage 4, scripts 4–6 — the scar-size chain"). We write **level 2
  only** (1–8); the platform derives its level-1 aggregation. Argentina populates all 8 classes —
  24 scars ≥ 100 000 ha, largest 219 410 ha in calendar 2003.

**The scar mask is forced to equal the month-of-burn mask** — both products are painted with
`.updateMask(month.mask())`, so the requirement holds by construction, and `--check` reports
`month-only` and `scar-only` pixel counts per year so the residual is a number, not an assumption.

Verified on the landed assets, not on the graph: `month px == scar px == size px` in every audited
year, `month-only = scar-only = 0`, and 0 pixels where the stored size class disagrees with
recomputing it from the painted `area_ha`. Argentina populates all 8 classes — 24 scars ≥ 100 000 ha,
largest 219 410 ha in calendar 2003 ([`notes/07-verification_log.md`](notes/07-verification_log.md)).

**The monolith held** — one task painting 27 FeatureCollections simply worked — so the `--per-year`
+ `--merge` fallback and the `--roi` smoke test were deleted rather than left as a second path to
maintain. The empty `FINAL_PRODUCTS/scar_year_parts` collection that a dry run once created is left
for Iván to delete.

## What is still open

Every asset 07a–07e produces is built and verified on the landed exports
([`notes/07-verification_log.md`](notes/07-verification_log.md)); `docs/08` "What Argentina
delivers" is the delivery checklist. Three loose ends survive, none of them a product:

- **The whole-country month-histogram cross-check has never completed.** The GEE half is on its
  third submission; the **local half is missing from disk** — `07-calendar_scars.R`'s pass 2 has to
  be re-run from `scars-pixels-cache` before `--stats-read` can report `MATCH`. This is the last
  unrun verification of the month product.
- **`regiones_fuego_argentina_v1` does not exist** *under that name*. Every reference script uses it
  for the export geometry and the `region` property; step 07 uses `ARG_BUFFER_FC` instead and sets
  `region = 'argentina'`, which is fine because our products have no region dimension at all. A
  5-feature region vector **does** exist — `ANCILLARY_DATA/VECTOR/ARG/regiones_arg_col1_simplificada_num`,
  carrying `Region` and an integer `Zona` 1–5 — but it is `simplificada` and its `Zona` numbering is
  **not** verified against `REGION_RASTER.region_id`, so it is a candidate for the statistics
  stage's territorial layer, not a drop-in for it.
- **Asset-name cosmetics**: the month images are
  `mapbiomas_argentina_fire_collection1_fire_mask_v<N>_<year>`, which carries the version mid-name.
  Only the `year` property is read downstream, so this is cosmetic — but if it is to be renamed, do
  it before the publish copy.


## Files

| File | Role |
|---|---|
| `workflow/07-month_of_burn.py` | 07a — the month-of-burn ImageCollection (GEE) |
| `workflow/07-calendar_scars.R` + `scripts/run_07_scars.sh` | 07b — the 8-connected calendar-year scars (local, two passes) |
| `scripts/validate_scar_zips.py` | the gate on 07b's packages and on what landed |
| `workflow/07-scar_rasters.py` | 07c — the three scar subproducts |
| `scripts/rule_a_aoi_extract.py` / `rule_a_aoi_tag.R` | rule A's AOI: pull it from the explorer, tag the objects once |
| `scripts/run_07_v2_driver.py` + `scripts/v2_driver_tick.sh` | the unattended cron driver; board at `logs/v2-driver/STATUS.md` |
| `utils/constants.py` | the pinned grid, `PRODUCT_VERSION`, the exclusion-rule thresholds, `SCAR_SIZE_LOWER_HA` |

## Related

- [`07-published_products.md`](07-published_products.md) — the other half of step 07: the shape the
  published assets take, 07d's nine derived subproducts and 07e's polygon layer.
- [`06-object_model.md`](06-object_model.md) — the `fire` call and the object set this step reads.
  Its `Gotchas` carry the two storage defects of that upload; the guards are in
  [`07-published_products.md`](07-published_products.md), which is what exports features.
- [`08-postprocessing.md`](08-postprocessing.md) — Argentina's route through the network's spec, and
  [`external/mapbiomas-fuego-reference.md`](external/mapbiomas-fuego-reference.md) — the spec itself.
- [`../statistics/docs/statistics.md`](../statistics/docs/statistics.md) — what is computed *from*
  these products.
- `notes/`: [`07-exclusion_rules_choice.md`](notes/07-exclusion_rules_choice.md) (how the two rules
  were arrived at) and [`07-verification_log.md`](notes/07-verification_log.md) (the dated audits of
  every sub-step).
