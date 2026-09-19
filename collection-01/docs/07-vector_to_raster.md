# 07 — From classified objects to the calendar-year products

Step 07 is the hand-off from *our* mapping method to the network's calendar-year products. It turns
the step-06 fire-year objects into every published raster: month of burn, the calendar-year scars,
and the derived subproducts.

**Everything Argentina builds lives in step 07** (this file), in the sub-steps below.
**docs/08 is the network's reference** — what Brazil and the other countries do, who owns what, and
the delivery dates. Read docs/08 for the *shape* of a product; read this file for what we actually
run. Where they disagree, this file wins.

## Order of operations

Run in this order; each sub-step needs the one before it.

| # | Sub-step | Script | State |
|---|---|---|---|
| **07a** | **Month of burn** per calendar year → `CLASSIFICATION_COLLECTIONS/collection1_fire_mask_v1` (ImageCollection, one 1-band uint8 image per year, 1–12, masked elsewhere). The pivot everything else reads. | `workflow/07-month_of_burn.py` (GEE) | ✅ **done** — 27/27 exported |
| **07b** | **Calendar-year scars**, 8-connected, labelled locally → `data/scars-upload-cache/scars_<Y>.zip`, then ingested by hand as `FINAL_PRODUCTS/annual_burned_vectors/scars_<Y>` | `workflow/07-calendar_scars.R` + `scripts/run_07_scars.sh` (local, two passes) | ✅ **done** — 27/27 built, gated and ingested, all verified against the local build |
| **07c** | **Scar rasters** — `annual_burned_id`, `annual_burned_area_ha`, `annual_burned_scar_size_range`, painted from the ingested scars and masked to 07a | `workflow/07-scar_rasters.py` (GEE) | ✅ **done** — 3/3 exported and verified on the landed assets (`notes/07-verification_log.md`) |
| **07d** | **The nine derived subproducts** — `monthly_burned`, `annual_burned`, both `*_coverage`, `frequency_burned` (+`_coverage`), `accumulated_burned` (+`_coverage`), `year_last_fire` | `workflow/07-subproducts.py` (GEE) | ✅ **done** — 9/9 landed and verified on the exported assets (`notes/07-verification_log.md`) |
| **07e** | **The fire-object polygon layer** — every mapped fire, all 28 fire-years, merged into one FC with ten properties, for early users → `FINAL_PRODUCTS/burned_area_polygons_v2` | `workflow/07-burned_area_polygons.py` (GEE) | ✅ **done** — **`_v2`: 1,012,648 rows / 1,012,645 objects / 63.33 Mha** (counted on the asset, 2026-09-15; the local object tables reproduce it to the object — statistics/docs/statistics.md §4). `_v1` (2026-07-31, third submission, 3.27 h) was **1,263,079 rows / 1,263,076 objects / 69.12 Mha** — that is the **pre-rule** layer, and the 250,431-object difference is exactly what exclusion rules A and B remove ("Object exclusion ruleset"). v1 took three goes: the first two carried 1,249 duplicate FY2021 rows because `objects_raw_2021` is duplicated *in storage* where no metadata count reveals it ("`objects_raw_2021` is duplicated in storage") |

> ⚠️ **The `State` column above describes the build, not the version.** Everything was first built
> as `_v1` and re-built as `_v2` in September 2026, after two things changed underneath: the object
> selection gained the two exclusion rules (**"Object exclusion ruleset"**), and the land cover the
> `*_coverage` products cross against moved from a preliminary col-3 to the published
> `mapbiomas_argentina_collection3_pb` (**"The `_v2` re-export"**). **The live state of that re-run
> is `logs/v2-driver/STATUS.md`, not this table** — as of 2026-09-18 it reports 07a, 07b, 07c and
> 07e complete and **07d paused** (deprioritised 14 Sep: the statistics come first and do not need
> it). Check the board before assuming a subproduct is on v2.

Commands, in order:

```bash
# 07a  (re-runnable, skips existing assets).  The exclusion rules of "Object exclusion ruleset" are ON BY DEFAULT and
# v2 is a NEW collection ("The `_v2` re-export"), so no flags and no --overwrite are needed.
$PYTHON collection-01/workflow/07-month_of_burn.py --all --launch

# 07b  (done) — pass 1 must finish before pass 2: a calendar year needs BOTH its fire-years
tmux new-session -d -s s07pix  '/abs/path/collection-01/scripts/run_07_scars.sh pixels -j 5'
tmux new-session -d -s s07scar 'OBJ_CORES=6 /abs/path/collection-01/scripts/run_07_scars.sh scars -j 2'
$PYTHON collection-01/scripts/validate_scar_zips.py              # gate the zips  -> 27/27
$PYTHON collection-01/scripts/validate_scar_zips.py --ingested   # gate the upload -> 27/27

# 07c  (done; re-runnable, skips existing assets)
$PYTHON collection-01/workflow/07-scar_rasters.py --check --years 2003,2020 --roi=-61.6,-25.6,-61.1,-25.1
$PYTHON collection-01/workflow/07-scar_rasters.py --launch

# 07d  (done; re-runnable, skips existing assets) — all nine derive from 07a, NOT from 07c
$PYTHON collection-01/workflow/07-subproducts.py --check     # band bookkeeping + ROI counts
$PYTHON collection-01/workflow/07-subproducts.py --launch     # 9 tasks
#   one product only:  --only frequency_burned

# 07e  — the polygon layer for early users ("07e — the fire-object polygon layer"). Independent of 07b-07d; needs only step 06.
$PYTHON collection-01/workflow/07-burned_area_polygons.py --check
$PYTHON collection-01/workflow/07-burned_area_polygons.py --launch              # the merged FC
$PYTHON collection-01/workflow/07-burned_area_polygons.py --launch --overwrite  # re-export in place
$PYTHON collection-01/workflow/07-burned_area_polygons.py --verify              # THE gate ("`objects_raw_2021` is duplicated in storage")
$PYTHON collection-01/workflow/07-burned_area_polygons.py --set-props           # after it lands
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
problem above was found — that revision is what the `_v2` re-export is being relaunched with
([`ROADMAP.md`](../../ROADMAP.md)). Changing any of them means re-running 07a, 07b, 07c, 07d and
07e and then every statistic, so treat a proposal to change them as a new collection, not a tweak.

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
registration, the `band_format` lookup and every download link — does not change (statistics/docs/statistics.md "What is still open").
Versioning on our side then buys three things overwriting would not:

1. the v1 products stay readable while v2 is built, so a number can be traced to the layer it came
   from;
2. nothing is ever half-replaced — a failed re-export leaves a complete v1, not a mixture;
3. **the gate on 07d becomes meaningful.** 07d must not start until all 27 month assets exist
   ("Namespace the task descriptions"); against an overwritten collection that count is already 27 before anything has run.

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

## Products, and the shape they take

The subproducts are **single multiband images, one band per calendar year** — not ImageCollections
of per-year images. Confirmed in the launch guide ("Imagen multibanda con el ID de cada cicatriz")
and in `ToPublish/2-toAsset-Public`, whose `band_format` property (`burned_monthly_{year}`,
`scar_area_ha_{year}`, …) only means anything for a multiband image.

The **one** ImageCollection in the chain is the stage-3 pivot,
`collection1_fire_mask_v1` — one single-band image per year — which is what step 07 produces and
what every stage-4 script reads.

**One asset per subproduct, with one BAND per year — not one asset per year.** The scar chain is
three images of 27 bands, never 27 images of 3 bands. Reference script 5 builds them that way
(`ee.Image().select()` then `addBands` per year, one export each), script 6 reclassifies every band
of the area image in a single expression, and `ToPublish/2-toAsset-Public` attaches a `band_format`
property per subproduct (`scar_id_{year}`, `scar_area_ha_{year}`) — a `{year}` token that only means
anything if each band *is* a year.

| Asset | Shape | Bands | dtype / pyramiding | Built by |
|---|---|---|---|---|
| `CLASSIFICATION_COLLECTIONS/collection1_fire_mask_v1` | **ImageCollection**, one 1-band image per year | `burned_monthly` (1–12) | uint8 / `mode` | `07-month_of_burn.py` |
| `FINAL_PRODUCTS/annual_burned_vectors/scars_<Y>` | FeatureCollection per year | `scar_id`, `area_ha`, `n_px`, `year` | — | manual ingest of `scars_<Y>.zip` |
| `FINAL_PRODUCTS/…_annual_burned_id_v1` | single multiband image | `scar_id_1999` … `scar_id_2025` | int / `mode` | `07-scar_rasters.py` |
| `FINAL_PRODUCTS/…_annual_burned_area_ha_v1` | single multiband image | `scar_area_ha_1999` … | float / `median` | idem |
| `FINAL_PRODUCTS/…_annual_burned_scar_size_range_v1` | single multiband image | `scar_area_ha_1999` … (see below) | uint8 / `mode` | idem |

⚠️ **The size-range bands are named `scar_area_ha_<year>`, NOT `scar_size_range_<year>`.** That is
not a copy-paste slip: the reference inherits the band names from the area product, and the publish
map lists `annual_burned_scar_size_range: 'scar_area_ha_{year}'`. Renaming them to something more
sensible would break the platform's band lookup.

Naming keeps **our** `COLLECTION-1` spelling (docs/08 open #1) while the asset *names* inside follow
the network exactly; the `mapbiomas-public` copy is renamed at publish time.

**`annual_burned_vectors` uses underscores, unlike the reference's `annual-burned-vectors`.** That is
deliberate, not a typo: everything else under `FINAL_PRODUCTS` is underscored (`FINAL_PRODUCTS`
itself, `..._annual_burned_v1`, `..._annual_burned_area_ha_v1`), so the hyphenated folder is an
oddity in the reference tree. Nothing external reads the path — the only consumer is
`07-scar_rasters.py` via `C.ANNUAL_BURNED_VECTORS`, because we **replaced** reference script
`5-export_annual_burned_id_and_size_by_year` rather than adapting it ("07c — the scar rasters": we paint our own
pixel-count `area_ha` instead of letting it recompute `geometry().area()`, and we classify sizes
server-side). That script would not run against our tree anyway: it expects per-year assets named
`mbfogo-col1-<year>-v1`, and ours are `scars_<Y>`. If IPAM ever needs to run their version, both the
folder and the per-year names have to be aligned — not just the folder.

---

## What is still open

Nothing in **07a–07e** is outstanding: all 12 images, the 27 scar FCs and the polygon layer are
landed and verified on the exported assets ([`notes/07-verification_log.md`](notes/07-verification_log.md)),
and `docs/08` "What Argentina delivers" is the delivery checklist. Three things are:

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

## 07d — the nine derived subproducts

Everything here derives from **07a's month-of-burn collection** plus the **MapBiomas LULC**. No new
vectors, no local work, no re-labelling. Script: `workflow/07-subproducts.py`, **9 export tasks
launched 2026-07-29**.

Reference: `Reference/2-Collection_Fire_Subproducts/1_burned_area_products_monthly_annual_coverage`
(products 1–4), `2_burned_area_frequency_accumulated_coverage` (5–8), `3_year_last_fire` (9).
**Do not innovate here** — copy the encodings exactly; they are what the platform decodes.

### The four settled answers

**1. Which LULC layer?** `C.PRODUCT_LULC` — the **published MapBiomas Argentina land-cover
integration**, bands `classification_<year>`. **NOT `veg_fire`.** `veg_fire` is our internal
25-class fire-modelling remap (region-specific, built for the burn-probability model); it is not the
published LULC legend and no other country has it. Using it would make our `*_coverage` products
undecodable by the platform and incomparable across the network. `veg_fire`'s only role in step 07 is
the argument that the LULC *mask* is already embedded upstream (docs/08 "Foundations") — it never enters a
product.

⚠️ **`C.PRODUCT_LULC` is deliberately a SECOND constant, not a repoint of `C.MAPBIOMAS_LULC`.**
`MAPBIOMAS_LULC` is the **model-side** input: `utils/functions.py::get_mb_class_band` derives
`veg_fire` from it, which drives the step-01 training export and the step-03/04 candidate mask, so
the entire collection's SNIC candidate set was built against that exact asset (LULC col-2 v8) and it
must stay frozen there. The coverage products answer a different question — "which *published* land
cover burned in year Y" — so they track whatever LULC Argentina publishes. **The two pointing at
different collections is not an inconsistency to fix.**

`PRODUCT_LULC` is **LULC collection 3, published** —
`…/COLLECTION-3/INTEGRATION/mapbiomas_argentina_collection3_pb`. It has moved twice: col-2 v8 → the
preliminary col-3 (`…_integration_v1_buffer`, 2026-07-29, which is what the **v1** coverage
products on the asset store were built against) → the published col-3, which the `_v2` re-export
crosses.

Each move cost nothing, because **all three share one byte-identical grid**, offset from the SNIC
lattice by exactly **9953 columns / −25102 rows — integers**. So combining LULC with the month
raster involves no resampling and no half-pixel shift, which for a *categorical* band is the
difference between a class code and its neighbour's. Their footprints all contain the 2 km buffer,
so no burned pixel can fall outside the LULC and silently drop out of a coverage product (`add`
propagates the mask).

**Max class code 77 < 100 is what makes the encodings work** — it is why `M*100 + L` and
`freq*100 + L` are decodable and `mod 100` exact. Re-check it whenever `PRODUCT_LULC` moves, along
with the lattice offset and the footprint; the measured audits are in
[`notes/07-verification_log.md`](notes/07-verification_log.md). The available band list is read
from the **asset**, never hardcoded, so extending or repointing the source self-corrects — which is
why duplicating a missing last year forward (the network's own answer) was never a blocker, and is
moot now that col-3 carries `classification_2025` natively.

**2. Same year or previous year?** **The same calendar year.** The reference selects
`lulc.select('classification_' + year)` for the burning year itself. Note this differs from
`veg_fire`, which is built from the **previous** year's LULC (the classifier must not see the burn it
is predicting). The coverage products have no such constraint — they answer "which land cover burned
in year Y", as classified in year Y — so the two layers are genuinely different and differently
aligned in time. Do not "fix" one to match the other.

For the **frequency** products the LULC year is the **moving end of the window**: the forward pass
(`fire_frequency_<y_first>_<y>`) uses `classification_<y>`, the backward pass
(`fire_frequency_<y>_<y_last>`) also uses `classification_<y>`. In both cases it is the end that
varies, not the fixed anchor.

**3. Do they split by region?** **No.** Scripts 1, 2, 3, 5 and 6 all export **one multiband image per
subproduct** over `regions.union().geometry()` — the whole country. The only per-region assets in the
network's chain are the stage-2/3 classification collections (one image per region-year), and ours has
no region dimension at all: 07a wrote one whole-country image per calendar year. So there is nothing
to reconcile. (Not to be confused with the **statistics** exports, statistics/docs/statistics.md, which *are* cut by
territory — that is a different stage and a different layer.)

**4. Shape.** One asset per subproduct, one **band** per year — never one asset per year ("Products, and the shape they take").

### The nine products

`M` = the month-of-burn band (1–12, masked elsewhere); `L` = `classification_<year>`.

| Subproduct | Band | Encoding | dtype | Pyramiding |
|---|---|---|---|---|
| `monthly_burned` | `burned_monthly_<year>` | `M` | uint8 | mode |
| `annual_burned` | `burned_area_<year>` | `M > 0` → 1 | uint8 | mode |
| `monthly_burned_coverage` | `burned_coverage_<year>` | `M * 100 + L` | uint16 | mode |
| `annual_burned_coverage` | `burned_coverage_<year>` | `(M >= 1) * L` | uint8 | mode |
| `frequency_burned` | `fire_frequency_<y1>_<y2>` | count of years burned in the window, `selfMask()`ed | int16 | mode |
| `frequency_burned_coverage` | `fire_frequency_<y1>_<y2>` | `freq * 100 + L` | int16 | mode |
| `accumulated_burned` | `fire_accumulated_<y1>_<y2>` | `freq >= 1` → 1 | uint8 | mode |
| `accumulated_burned_coverage` | `fire_accumulated_<y1>_<y2>` | `freq_coverage mod 100` (recovers `L`) | uint8 | mode |
| `year_last_fire` | `classification_<year+1>` | calendar year of the most recent fire up to that band | uint16 | mode |

Export with `crs=C.SNIC_CRS` + `crsTransform=C.SNIC_TRANSFORM` (never `scale=30`, "One grid, pinned everywhere"),
`region = ARG_BUFFER_FC`, `maxPixels=1e13`, `pyramidingPolicy` `mode` throughout.

Band counts as built: **27** for the four annual/monthly products and for `year_last_fire`, **53**
for each of the four window products (frequency / accumulated, with and without coverage).

**Frequency windows are two-sided.** A forward pass accumulates `y_first…y` and a backward pass
`y…y_last`; both band sets are concatenated and sorted, and the duplicated join band — the full
`1999_2025` window, which both passes produce — is kept from the forward pass only (the reference
drops the backward copy with `freqPost.slice(0,-1)`). 27 + 27 − 1 = **53**. Never-burned pixels are
`selfMask`ed out, so frequency is `1..N`-or-absent, never 0. The coverage variant encodes the LULC of
the window's **moving end** — `y` in both passes, i.e. the window's end going forward and its start
going backward.

### Four traps in the reference code

1. **`year_last_fire` bands are `classification_<year+1>`** — an off-by-one the platform expects.
   Preserve it; it looks like a bug and is not.
2. **The `accumulated_burned` filename typo.** Script 2 builds
   `'..._accumulate' + coll_n + '_burned_v1'` → `..._accumulate1_burned_v1`, while the publish list
   expects `..._accumulated_burned_v1`. Use the correct spelling.
3. **`frequency_burned`'s band name is unresolved.** Script 2 writes `fire_frequency_<y1>_<y2>`, but
   `ToPublish/2-toAsset-Public`'s `band_format` map says `frequency_burned_{year1}_{year2}`. The
   `accumulated_*` pair is consistent (`fire_accumulated_*` both places); only frequency disagrees.
   **Confirm with IPAM which the platform reads** — docs/08 open #9.
4. **The `*_coverage` products are the easiest to forget** and are exactly what the statistics stage
   reads (statistics/docs/statistics.md §2). Four of the nine are coverage products.

### The LULC is the only place land cover enters our chain

The stage-3 LULC *mask* does not apply to us (`docs/08` "Foundations"), so the four `*_coverage`
products are the **only** point at which land cover touches the published rasters. Everything that
makes that safe — the shared lattice, the integer offset, the footprint, the `< 100` class codes —
is above, under "The four settled answers".

### What was verified

`--check` prints the band bookkeeping for all nine products plus per-year ROI counts, and a
value-level decode of **every encoding** was run on a Chaco 0.5° box before submitting and again
against the landed assets. Both passes agree to the pixel: every decode residual 0, single-year
window = annual, and the five window-scoped products sharing one mask exactly
([`notes/07-verification_log.md`](notes/07-verification_log.md)).

> **ROI histograms taken with `frequencyHistogram` come out a few pixels below the
> `sum().unweighted()` counts.** That is `reduceRegion`'s **edge weighting** of partial pixels at
> the box boundary, not a disagreement between products — the same artefact the scar check records.
> Use `sum().unweighted()` whenever a count has to match a local build.

`scripts/audit_product_properties.py` is the standing property-drift check (dry run by default,
`--apply` to write). Run it after any re-export and after any move of `C.PRODUCT_LULC`: a silent
drift there is how a published asset ends up advertising the wrong land-cover collection.

### Three departures from the reference, all plumbing

The encodings are copied verbatim; what differs is how the graph is fed.

1. **The grid is pinned** (`crs` + `crsTransform`), never `scale=30` — "One grid, pinned everywhere", the same rule as 07a/07c.
2. **`region = ARG_BUFFER_FC`** instead of `regions.union().geometry()`, because
   `regiones_fuego_argentina_v1` does not exist as a FeatureCollection ("What is still open").
3. **All nine products read the 07a month collection**, whereas the reference exports `annual_burned`
   first and has scripts 2 and 3 read *that asset*. `annual_burned` is *defined* as `month > 0`, so a
   frequency built from the month images is bit-identical to one built from the exported annual
   product — and deriving everything from the single pivot makes the nine consistent **by
   construction** rather than by sequencing. The operational win is that the nine tasks are
   independent: nothing waits for a 27-band export to land, and any one product can be re-run alone
   (`--only`). Confirmed by the two exact cross-product agreements in "What was verified".

The reference's `accumulated_burned` filename typo is not copied ("Four traps in the reference code").

---

### Namespace the task descriptions

`mapbiomas-fire-485203` is used by **many people across the network**, and
`ee.data.listOperations()` is **project-scoped, not per-account**: it returns every user's tasks (226
of them when 07d was launched — Peru's `MONITOR_01_*`, Bolivia's
`GT_Fuego-mapbiomas_bolivia_fire_collection1_burned_area_*`, …). Step 03 already documents that
scoping for `bpts_` (`03-bp_ts_metrics.py::_inflight_bpts_names`).

07d was first written matching in-flight tasks on the **bare** subproduct name (`annual_burned`,
`monthly_burned`, `year_last_fire`) — which is exactly what another country's adaptation of these same
reference scripts would call its exports. A collision would print
`[skip] … has a PENDING/RUNNING task` and **silently not submit one of our products**, which is the
worst kind of failure here: it looks like the resumable-skip working. Descriptions are therefore
namespaced **`arg07d_<subproduct>`** (`TASK_PREFIX`).

`destinationUris` — which would identify the task by *our* asset path and settle it exactly — is
populated **only on FINISHED operations**, so it cannot serve the in-flight test. The prefix is the
fix, not a workaround for a nicer one.

⚠️ **Never cancel or touch a task you did not launch**, and never match one by a generic description:
in this project the other tasks belong to other countries' teams.

The first batch went out under the bare descriptions, so a `LEGACY_DESCRIPTIONS` fallback kept them
accepted by the in-flight test — otherwise a re-run before they landed would have double-submitted.
✅ **Deleted 2026-07-30**, once all nine had finished: it was the collision-prone form the prefix
exists to retire, and keeping it any longer would have meant one of our products could be silently
skipped because another country happened to be exporting an `annual_burned`. The in-flight test now
matches the namespaced description only.

---

## 07e — the fire-object polygon layer, for early users

```
FINAL_PRODUCTS/burned_area_polygons_v2
```

Every mapped fire, all 28 fire-years, in **one** FeatureCollection. Script:
`workflow/07-burned_area_polygons.py`. Nothing is computed and no geometry is touched — it is the
step-06 object set under the full positive selection 07a paints (`fire == 1 & area_ha >= 1 &
not(A) & not(B)`, "Object exclusion ruleset"), stripped to ten properties, merged and flattened.

**`_v2`: 1,012,648 rows for 1,012,645 objects, 63.33 Mha** (counted on the asset 2026-09-15).

⚠️ **The `_v1` figures quoted in this section — 1,263,079 rows / 1,263,076 objects / 69.12 Mha —
are the PRE-RULE layer**, exported 31 July, before exclusion rules A and B were finalised
(2026-09-11/12). The 250,431-object gap between the two is the rules: −196,804 to rule A and
−53,627 to rule B, measured per fire-year by `statistics/fire_counts.R`, whose local object tables
reproduce the v2 count **to the object** (statistics/docs/statistics.md §4). Do not quote a v1 number as the size of the
published layer. (A naive row-sum of `area_ha` overstates the area in either version — "`oid` is unique per OBJECT, not per row".)

It depends only on step 06, not on 07a–07d, so it can be rebuilt at any time and in any order.

### The name, and the folder

**A plain `burned_area_polygons_v1`, NOT `C.product_name()`.** Every raster subproduct is
`mapbiomas_argentina_fire_collection1_<subproduct>_v1` because the platform's `band_format` lookup
and the publish copy require that exact form. This layer is not one of those: it is ours, it is for
people, and it is a name a user has to read out and type (Iván, 2026-07-30 — the first launch used
the long form and was cancelled and re-run for this).

**`polygons`, not `vectors`.** `FINAL_PRODUCTS/annual_burned_vectors/` is already taken by the
**calendar-year scars** (07b/07c) — plain 8-connectivity, calendar-clipped, one scar per connected
burn, a genuinely different layer from these fire-year objects. Reusing the network's word would put
two unrelated layers one line apart under near-identical names. "polygons" also tells a user what
they are getting, where a "vector" could be points or lines.

⚠️ **Being in `FINAL_PRODUCTS` overrides docs/08 open #8**, which parked the fire-year vector
database *outside* that folder until IPAM rules whether Argentina may publish it. Iván's call
(2026-07-30): early users get a link that survives a yes, and Brazil's own col-5
`annual_burned_vectors` is the precedent that the door is open. `ToPublish/2-toAsset-Public` copies
an **explicit** subproduct list rather than the folder, so it cannot be swept into a published
collection by accident — but if the ruling is no, the asset moves and the shared link dies.

### The ten properties

| property | source | meaning |
|---|---|---|
| `oid` | `oid` | stable object id `<fy>_<n>` — the key that joins user feedback back to the object database and its 20 metrics |
| `fire_year` | **the asset name** | the non-calendar mapping year, 1 May *fy* → 30 Apr *fy*+1 |
| `calendar_year` | `year_cal` | the **mode** of the object's per-pixel calendar years |
| `area_ha` | `area_ha` | pixel-count area — *not* a geodesic polygon area |
| `date_med` / `date_min` / `date_max` | idem | burn dates, ISO 8601 `YYYY-MM-DD` ("Dates readable, and the layer `filterDate`-able") |
| `p_mean` | `p_mean` | posterior mean fire probability (probit BART, docs/06) |
| `p_width` | `p_width` | width of its credible interval, `p_q95 − p_q05` |
| `seed_mean` | `seed_mean` | mean SNIC seed burn probability over the object |

`fire_year` is **not** a property of the source FCs — it exists only in the asset name, so the
script sets it per source collection. `year_cal` → `calendar_year` is the one rename; everything
else keeps the object database's vocabulary. The classification **threshold is deliberately not
included** (Iván, 2026-07-30) — it is a per-size-band constant from
`config/object_model_thresholds.csv`, not a property of a fire, and `p_mean` is what a user actually
wants to filter on.

#### Dates readable, and the layer `filterDate`-able

The object database stores the three dates as **whole days since 1970-01-01** — an integer `19018`
that nobody can read in the Inspector or a QGIS attribute table. In this layer they are
**`YYYY-MM-DD` strings** instead (Iván, 2026-07-30). Nothing is lost: the integers stay in the object
database, `oid` joins back to them, and ISO-8601 still range-filters correctly because it sorts
lexicographically — `ee.Filter.gte('date_med', '2021-01-01')` does what it looks like.

Each feature also carries **`system:time_start`, stamped from `date_med`**, so the collection answers
`filterDate()`. Two decisions inside that:

- **`date_med`, not `date_min`** — one fire, one instant, matching what `calendar_year` already does
  (the modal year, "Two things users must be told").
- **`system:time_end` deliberately NOT set.** With both timestamps the date filter passes on interval
  *intersection*, so a fire burning 28 Dec → 4 Jan would come back from a December query *and* a
  January one, and summing `area_ha` per month would double-count it. One timestamp keeps one fire in
  one bucket, so `filterDate` results stay summable. The true span is still right there and readable:
  `date_min`…`date_max`.

Implementation trap: **`Feature.select()` drops `system:time_*`** along with every other unlisted
property, so the timestamp is set *after* the select. Set it before and it vanishes — and a
`filterDate` that silently matches nothing is indistinguishable from a window with no fires in it.

### Two things users must be told

1. **`calendar_year` is the object's majority year, and the rasters do not agree with it.** It is
   `mode_int(cyear)` over the object's pixels (`05-objects_metrics.R:239`), while every published
   raster assigns year and month **per pixel** ("The decisions this step rests on"). A fire straddling 31 December is split across
   two years in the rasters and lands whole in one year here. Neither is wrong — but a user who
   cross-tabulates the two without knowing this finds "missing" area.
2. **Fire-year 1998 is here and in no published raster.** 3,845 polygons, `calendar_year` 1998 or
   1999; the calendar series starts at 1999, so FY1998's Nov–Dec 1998 tail (~76 kha) exists in this
   layer only ("The verified calendar-year partition").

And a third for us: **the layer's area must be summed per OBJECT, not per row**, because one FY2000
object is stored as 4 rows each carrying the whole object's area ("`oid` is unique per OBJECT, not
per row"). Summed per row, v1 read 74.23 Mha instead of 69.12 — an overstatement of **5,118,513 ha**
from one fire counted four times. Done correctly, the layer and the scars agree to **0.14 %**
(69.12 vs 69.02 Mha on v1), where the naive arithmetic made them look 5.2 Mha apart. The residual
differences are real and should **not** be forced to zero: fire-year vs calendar partition, calendar
1998 included here and dropped there, intra-year reburn deduplicated there but not here, and a
different minimum unit.


### Which ACCOUNT submits it

**The GEE task queue is per user**, so the merged export runs as the **second account**
(`ivanbarbera@comahue-conicet.gob.ar`) on the **`mapbiomas-argentina`** compute project, whose queue
was empty, rather than waiting behind the primary account's tasks. Only the *compute* project
changes — the destination asset is the same either way, so the link shared with early users does not
depend on who submitted it.

```bash
$PYTHON collection-01/workflow/07-burned_area_polygons.py --launch \
    --project mapbiomas-argentina \
    --credentials ~/.config/earthengine/credentials.comahue
```

**`--credentials`, never swapping the resident file.** `ee.oauth.get_credentials_path()` hardcodes
`~/.config/earthengine/credentials` with no env override, so the obvious route is to `cp` the
account you want into place; passing the file explicitly is strictly better — nothing is clobbered,
both accounts are usable in one session, and a half-finished swap cannot leave the wrong token
resident. This function is the pattern CLAUDE.md points other scripts at.

**Monitoring has to ask twice.** `ee.data.listOperations()` is project-scoped *and* cross-user, so
the resident account can see the comahue task — but only when initialized against
`mapbiomas-argentina`. A watcher that polls only `C.GEE_PROJECT` reports the 07e task as `MISSING`,
which looks exactly like a task that was never submitted. The same asymmetry applies to a re-export:
`--overwrite` on an asset the comahue account created is submitted by that account too.

Write permission **cannot be pre-flighted** — `getAssetAcl` on `FINAL_PRODUCTS` returns empty
`writers`/`owners` because access comes from the cloud project's IAM, not a per-asset ACL — so a
missing write permission surfaces as an immediate task failure, not hours in. Launching is the
cheaper test. Feasibility measurements and the EECU trap:
[`notes/07-export_post_mortems.md`](notes/07-export_post_mortems.md).


### ⚠️ `objects_raw_2021` is duplicated in storage, and no count reveals it

**`objects_raw_2021` holds 1,249 FY2021 features twice**, byte-identical in geometry and in every
property. It came in through step 06's hand ingest, it is deterministic, and it is in the stored
source — but **no metadata count shows it**: `size()`, `aggregate_count('oid')` and
`len(aggregate_array('oid'))` all agree on the wrong number, because an aggregation over a plain
filtered *stored* collection is answered from the asset's metadata. Put a `.map()` in the chain and
GEE has to **iterate**, which returns the extra features. An export iterates, so it writes them.

Two rules outlast the bug:

1. **A count that agrees with itself is not a clean bill of health.** Three numbers, one pushed-down
   answer, all three wrong about what a read returns. The honest check materialises: put a `.map()`
   in front, or count on the **landed asset**.
2. **A COMPLETED task is not evidence that each feature was written once.** The original `--verify`
   — size, schema, one feature — passed the bad asset without a murmur.

**The fix** is `distinct('oid')` inside `fires()` — one row per object, the invariant actually
wanted — applied per fire-year and **skipped for FY2000**, whose 4 rows are a legitimate vertex
split (below). `distinct(['oid', '.geo'])` needs no exception but hashes ~4 GB of serialised
multipolygon to buy a distinction that matters in one year. **The root cause belongs upstream**:
`objects_raw_2021` should be re-ingested by step 06 (BACKLOG, `docs/06` "Gotchas"). Until it is,
that guard is what stands between the asset and every product derived from it. Full post-mortem:
[`notes/07-export_post_mortems.md`](notes/07-export_post_mortems.md).

### `oid` is unique per OBJECT, not per row

`objects_raw_2000` stores `2000_57529`, a **1,706,171 ha** object, as **4 features** with disjoint
geometry parts, each repeating the whole object's `area_ha`, dates and probabilities. It is a vertex
split — `Export.table.toAsset(maxVertices=…)` cuts a geometry that exceeds the limit into pieces —
and it happened **upstream, in the step-06 upload**, not here: audited across all 28 sources, the
totals are **1,263,079 rows / 1,263,076 distinct `oid`** and FY2000 is the only year affected. This
layer carries all 4 rows faithfully, which is why the expected row count is 3 above the object count.

Two consequences, both in the asset's `oid_uniqueness` property:

- **a naive `aggregate_sum('area_ha')` over-counts the layer by 5,118,513 ha** — 3 extra copies of
  1,706,171 ha. This is not a footnote: it is what made the layer look like 74.23 Mha instead of
  69.12 Mha ("Two things users must be told"), and it is why `--verify` now prints both totals. Dissolve by `oid`, or subtract
  the split, before quoting an area.
- **never repair a duplicate with a blind `distinct('oid')` on this fire-year.** It would keep one
  part and silently drop ~1.3 Mha of that fire — measured: `distinct(['oid', '.geo'])` leaves the 4
  rows intact, `distinct('oid')` returns 1. That is exactly why the guard in `fires()` skips FY2000
  and why `--verify` carries `KNOWN_VERTEX_SPLITS = {2000: 3}` rather than tolerating any surplus.

Why the split cannot simply be undone: the 4 parts exist *because* the whole geometry exceeds the
exporter's vertex limit, so re-merging them would only be split again on write. Four rows is the
storable form; the caveat is the price.

---

## Files

| File | Role |
|---|---|
| `workflow/07-month_of_burn.py` | 07a — the month-of-burn ImageCollection (GEE) |
| `workflow/07-calendar_scars.R` + `scripts/run_07_scars.sh` | 07b — the 8-connected calendar-year scars (local, two passes) |
| `scripts/validate_scar_zips.py` | the gate on 07b's packages and on what landed |
| `workflow/07-scar_rasters.py` | 07c — the three scar subproducts |
| `workflow/07-subproducts.py` | 07d — the nine derived subproducts |
| `workflow/07-burned_area_polygons.py` | 07e — the merged fire-object polygon layer |
| `scripts/rule_a_aoi_extract.py` / `rule_a_aoi_tag.R` | rule A's AOI: pull it from the explorer, tag the objects once |
| `scripts/audit_product_properties.py` | the standing property-drift check over the published assets |
| `scripts/run_07_v2_driver.py` + `scripts/v2_driver_tick.sh` | the unattended cron driver; board at `logs/v2-driver/STATUS.md` |
| `utils/constants.py` | the pinned grid, `PRODUCT_VERSION`, `PRODUCT_LULC`, the exclusion-rule thresholds, `SCAR_SIZE_LOWER_HA` |

## Related

- [`06-object_model.md`](06-object_model.md) — the `fire` call and the object set this step reads,
  and the two storage defects of that upload which every consumer here must guard against.
- [`08-postprocessing.md`](08-postprocessing.md) — Argentina's route through the network's spec, and
  [`external/mapbiomas-fuego-reference.md`](external/mapbiomas-fuego-reference.md) — the spec itself.
- [`../statistics/docs/statistics.md`](../statistics/docs/statistics.md) — what is computed *from*
  these products.
- `notes/`: [`07-exclusion_rules_choice.md`](notes/07-exclusion_rules_choice.md) (how the two rules
  were arrived at), [`07-verification_log.md`](notes/07-verification_log.md) (the four dated audits),
  [`07-export_post_mortems.md`](notes/07-export_post_mortems.md) (the merged-export feasibility, the
  EECU trap, the FY2021 duplication).
