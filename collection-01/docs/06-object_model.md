# 06 — Object model: which fire objects are real fire

Step 06 takes the step-05 fire **objects** and their metrics and decides, per object, whether it is
a burned scar or noise. The classifier is a **probit BART fitted locally in R on ~5 k collected
labels**; it replaces collection-00's empirical threshold filter. It then scores **all 28
fire-years / 1.69 M objects**, and the whole scored object set — geometry plus every predictor plus
the call — is uploaded to GEE as one FeatureCollection per fire-year.

"Object" (not "polygon") is the deliberate name: a fire *is* an object, and the metrics are
object-level, even though the layer is sparse rather than a wall-to-wall OBIA partition. Many
objects are multipolygons (the step-05 dilation-bridge case, 05 §2.3). The globally-unique key is
**`oid = "<fire_year>_<pid>"`** (05 §3); every join — labels ↔ objects, predictions ↔ geometry — is
on `oid`.

**Geometry and metrics are split (05 §4):** the per-year GPKG holds `oid` + geometry only; the
metrics live in `objects_<fy>_raster_metrics.csv` and `objects_<fy>_shape_metrics.csv`, both keyed
by `oid`. Fitting and prediction run **from the CSVs alone** — geometry is read only when a QGIS
layer or an upload package is built.

---

## Files, directories and scripts

Everything step 06 produces is in the Insync store under `collection-01/data/` (gitignored
symlink), except the tracked threshold config. A **`-cache` suffix means regenerable**: those
directories can be deleted and rebuilt from the CSVs at any time.

| directory | contents | written by |
|---|---|---|
| `data/objects-labels/` | `polygons_data_<author>.gpkg` (one per collaborator asset — the file prefix mirrors the GEE asset name on purpose) + `polygons_data_merged.csv` (one row per label↔object pair) | `scripts/objects_labels_prep.R` |
| `models-store/object_model/` | `bart_object_model.json` (the serialized fit, 92.7 MB) + `_meta.rds` | `06-object_model.R fit` |
| `data/objects-pred/` | `objects_<fy>_pred.csv` (`oid`, `p_*`, `fire_model`, `fire_tag`, `fire`), `objects_<fy>_derived.csv` (the 8 derived predictors, for the upload), `oof_grid_5.csv` | `06-object_model.R predict` / `cv` |
| `config/object_model_thresholds.csv` | **tracked** — the per-size-band fire-call cut | `scripts/objects_threshold.R` |
| `data/objects-analysis/` | every reported table/plot: threshold sweep, importance + ALE curves, size distribution, c-00 comparison, upload validation | `objects_threshold.R`, `objects_importance_ale.R`, `objects_data_explore.R`, `validate_upload_zips.py`, the notebook |
| `data/objects-inspect-cache/` | 28 `<fy>_objects_pred.gpkg` QGIS layers (6.3 GB) + `inspect_objects.qgz` | `scripts/objects_inspect_export.R` |
| `data/objects-upload-cache/` | 28 `objects_raw_<fy>.zip` — the GEE upload packages (1.3 GB) and their loose Shapefile components | `scripts/objects_upload.py` |

| script | role |
|---|---|
| `workflow/06-object_model.R` | the pipeline step: `fit` \| `predict [years\|all]` \| `cv [region\|grid K\|random K]` |
| `scripts/objects_data_functions.R` | **the shared module** — readers, derived predictors, veg groups, `clean_tagged()`, the tag lookup, thresholds, regions, the c-00 filter, `auc_fast`. Everything below sources it, so "the clean labelled table" means the same rows everywhere |
| `scripts/objects_labels_prep.R` | download the per-collaborator label assets, intersect them with the objects, join metrics |
| `scripts/objects_threshold.R` | sweep the out-of-fold probabilities → `config/object_model_thresholds.csv` |
| `scripts/objects_importance_ale.R` | 4 importance measures + 1-D ALE curves → `objects-analysis/` |
| `scripts/objects_data_explore.R` | population size distribution + how the c-00 filter splits it |
| `scripts/objects_inspect_export.R` | join predictions onto geometry → a QGIS GPKG per year |
| `scripts/objects_upload.py` | build one year's zipped Shapefile (geometry + all predictors + the calls) for GEE |
| `scripts/validate_upload_zips.py` | pre-upload gate over the 28 zips (schema, codes, counts, geometry) |
| `scripts/run_06_predict.sh` / `run_06_inspect.sh` / `run_07_upload_zips.sh` | the three parallel, resumable all-years launchers |
| `notebooks/objects-analysis.qmd` | the standing analysis: size, uncertainty, the cuts, the per-year leak diagnostic, importance/ALE |

---

## 1. Label collection

**We do NOT upload objects to GEE for label collection.** Labels are collected **directly on the
step-04 SNIC `candseed` layer**, which already exists as a GEE asset per fire-year and shows, per
pixel, candidate vs. seed on exactly the clusters SNIC kept. **Shape and seed density — the most
informative signal for fire vs. noise — are fully visible there without any polygons.** This also
unblocked collection while step-05 vectorization was still running: the object a collected point
falls in does not change when the pixels are later polygonized, so points map cleanly onto objects
afterwards by point-in-polygon against the GPKG.

### The interactive collection code (GEE)

A script per collaborator (few enough to coordinate by hand), showing the SNIC `candseed` band plus
some reference layers from `explore_snic_IB-02`.

- **Year range.** The code exposes `(y_lwr, y_upr)` and draws the `candseed` image for each
  fire-year in it, **coloured differently per year**. Collect over small ranges in fire-active
  regions, wider ranges in quiet ones.
- **The drawing-layer NAME is the metadata.** Each user keeps several drawing layers split by class
  × year, so they can place many points fast; section 8 of each `training_polygons_*` script parses
  the layer name:

  | layer name | class | fire-year(s) |
  |---|---|---|
  | `fire_YYYY` | 1 | `YYYY` |
  | `nonfire_YYYY` | 0 | `YYYY` |
  | `fire_YYYY_poly` / `nonfire_YYYY_poly` | as above | as above — `_poly` just records that polygons were drawn |
  | `fire_YYYY_YYYY` (range) | 1 | **both ends inclusive** — written **once per year** in the range, so every row carries one concrete `fire_year` |

  Anything not named `fire_*` / `nonfire_*` is ignored on purpose (ROIs, bare `geometry*`, the
  doubtful layers `dudas2014` / `dudoso_2015` / `dudoso_2017`, `ejemplo_*`, imported vis params). To
  promote a doubtful layer to training data, **rename** it to the convention. An unparseable
  `fire_*`-style name **throws** rather than being silently dropped.
- **One asset per collaborator**, all their years and both classes:
  `…/TRAINING-DATA/POLYGONS-DATA/polygons_data_<author>`, downloaded from the asset page — no
  per-year merge. Schema: `class` (1/0), `fire_year`, `y_lwr`/`y_upr`, `geom_type`
  (`Point`/`Polygon`, read off the geometry rather than the name), `author`, `src` (the drawing
  layer, so a suspect feature traces back). Points and polygons share one table. Geometry-flavour
  drawing layers (all items fused into one `MultiPoint`/`MultiPolygon`) are exploded with
  `geometries()`, so both Code-Editor import flavours behave identically.

### Label prep — `scripts/objects_labels_prep.R`

`Rscript collection-01/scripts/objects_labels_prep.R [all|download|merge] [--force] [author…]`

**Download** — one asset → one GeoPackage per author (rgee `getDownloadURL("GeoJSON")`; existing
files skipped unless `--force`), so a collaborator who adds points costs one re-download, not
seven. **GPKG, not shapefile**: the labels mix points and polygons in one table, and field names
survive intact. **Merge** always reads *every* file present, so the merged table stays complete
after a single-author refresh.

**Merge** matches each label to the objects **of its own fire-year** and attaches their metrics →
`polygons_data_merged.csv`, one row per (label, object) pair.

*Why it is shaped this way.* A year is ~78 k objects / ~330 MB and only a handful are ever hit, so a
year is never read whole: labels are grouped into 1° blocks, each block read back through the
**GeoPackage R-tree** (`terra::vect(extent=)`), and the exact predicate run on that subset. Two
measured findings worth keeping:

- **`terra::relate(…, "intersects")`, not `sf::st_intersects`.** The 1-px dilation can weld a whole
  fire season into one object — `1999_24193` is **13 053 parts / 643 742 vertices**. `st_intersects`
  degrades pathologically there: **one point against that object costs ~55 s** (identical with
  `prepared = TRUE/FALSE` and with the arguments swapped). `terra::relate` answers the same block in
  1.6 s and returns **pair-for-pair identical** results — verified against sf on every FY1999 block.
  Whole merge: **27 s**.
- **Never `st_cast` the labels to POINT** to satisfy terra's one-geometry-type-per-SpatVector rule.
  A polygon label collapses to its first vertex and silently loses its objects (a 1999 polygon label
  went from 131 objects to 4). The script splits POINT vs POLYGON per block instead.

*Nothing is dropped; problems are flagged* — `n_objects` (0 = the label hit no object, >1 = a drawn
polygon), `oid_n_labels`, `oid_class_conflict` (object labelled both fire and non-fire). The model
step decides what to do with them. First full run (2026-07-27, 4643 labels, 7 collaborators, 21
fire-years): **6597 pairs over 5266 objects**, **234 labels (5 %) hit no object** (drawn where SNIC
kept no cluster — there is nothing to classify), **10 objects carry both classes**, and labels are
very unevenly spread (up to 40 on one object). One matched object (`2011_57456`, 1 px) has NA
`seed_mean`/`date_median` in step 05 itself — all-dieback objects have no seed/date stats by design
(05 §3), not a join failure.

## 2. The fitting set

`clean_tagged()` turns the label↔object pairs into one row per OBJECT, reporting every cut: −234
rows whose label hit no object, −10 objects labelled both classes, −1315 duplicate labels on an
already-labelled object, −1 object with an NA predictor → **5255 objects, 2788 fire / 2467
non-fire** (prevalence 0.531), 20 predictors.

Uneven label density per object is deliberately **not** corrected — a label is a label, and
reweighting by it would invent information.

## 3. The model — probit BART

**`stochtree` 0.4.5, `OutcomeModel(outcome = "binary", link = "probit")`**, fitted locally. Why BART
rather than a boosted ensemble, in one line each: with ~5 k labels there is **no honest way to tune
hyperparameters**, and BART's defaults are calibrated regularization priors rather than
placeholders; and the posterior yields a **per-object interval**, which is both an uncertainty
statement we can publish and the targeting signal for a round-2 collection. `stochtree` specifically
because `num_threads` parallelises the GFR sampler and the MCMC *within* a chain.

`num_gfr = 10`, `num_mcmc = 500` with `keep_every = 4` — i.e. **2000 MCMC iterations thinned to 500
retained draws** (`num_mcmc` is the *retained* count; stochtree runs `num_mcmc * keep_every`).
`num_threads = 8` = **physical** cores: tree sampling is memory-bandwidth-bound, so the extra
hyperthreads mostly add contention. If `num_threads` ever falls back to 1 on Linux/gcc, the build
has no OpenMP.

Thinning is what makes prediction affordable — cost is linear in draws, and 500 draws still put ~25
order statistics below `p_q05`, so 2000 retained draws would cost 4× the prediction time and memory
for no gain in a 5th percentile.

| step | measured |
|---|---|
| fit (5255 × 20, 2000 iter → 500 draws, 8 threads) | **~90 s** |
| serialized fit (JSON) | 92.7 MB, reloads in ~4 s |
| predict one large year (78 k objects × 500 draws) | ~100 s ≈ 2.6 µs/obj/draw |
| **all 28 fire-years / 1 689 419 objects** | **4m33s** on 8 parallel workers (~37 min in one process) |
| grid-blocked out-of-fold AUC | **0.8907** |

**Scoring every object across posterior draws is not a problem — but only in the right shape.**
Never pass the full object set as `X_test` to `bart()`: 1.69 M × 500 doubles ≈ **6.8 GB**. Instead
**fit → serialize to JSON → `predict()` per fire-year in `PRED_CHUNK` blocks → reduce each block to
its summaries and discard the draws**, so peak memory is one block (20 k × 500 ≈ 80 MB) regardless
of how many objects exist.

**Prediction is single-threaded** (measured): `num_threads` is a *sampler* setting, and
`predict.bartmodel` takes no thread argument — nor do the C++ predict entry points. One process pegs
one core with its OpenMP threads idle. The years are independent, so the parallelism goes at the
**process** level: `scripts/run_06_predict.sh` runs one `Rscript` per fire-year, 8 at a time,
biggest first, resumable. Each worker deserializes the 92.7 MB JSON itself (~1.4 GB RSS), so budget
~1.4 GB × workers.

## 4. The 20 predictors

15 non-vegetation metrics — `n_pixels`, `area_ha`, `burned_around_{1,2,3}`, `seed_mean`, `doy_sin`,
`doy_cos`, `date_span`, `perimeter_m`, `convexity`, `mbr_fill`, `mbr_elongation`, `circularity`,
`shape_index` — plus **five aggregated vegetation fractions**:

| column | veg_fire classes |
|---|---|
| `frac_agri` | 1 agriculture_chaco, 2 agriculture_cuyo-pat, 3 agriculture_pampa — **not** 4 agriculture-per |
| `frac_grass_inund` | 17 grassland-inund_chaco |
| `frac_pasture` | 18 pasture_ba, 19 pasture_chaco |
| `frac_grass_temp` | 12 grassland_ba, 13 grassland_chaco, 15 grassland_pampa — **not** cuyo/patagonia |
| `frac_woody` | 5,6,7,8,9,11 forests + 20,21,22,23 shrublands — **not** 10 forest-inund |
| *(no group)* | 4 agriculture-per, 10 forest-inund, 14 grassland_cuyo, 16 grassland_pat |

Membership is derived from `config/veg_fire_remap.csv` **by name**
(`objects_data_functions.R::veg_groups`), not from typed-in codes, so a remap change follows
through — and a code landing in two groups is an error, not a silent reshuffle. The groups are
deliberately **not** region-separated and **not a partition**: the five sum to 0.70 on average,
never above 1.

The 8 predictors that do not exist on disk — `doy_sin`, `doy_cos`, `date_span` and the 5 veg
groups — are built at load time by `add_derived()`. `predict` also writes them to
`objects_<fy>_derived.csv` so the upload can carry them without Python reimplementing the by-name
veg grouping (which would drift).

> *Historical record.* The 5 aggregated fractions replaced the 23 raw `frac_c1..frac_c23` columns
> (2026-07-27): on the same objects and folds the aggregated set won on every grid-blocked metric
> (then-current AUC 0.902 → 0.921), with the gain landing in the weak 1–50 ha band. The reason is
> **split budget** — 23 sparse columns were 58 % of the design matrix and BART draws split variables
> uniformly over what is available. The raw fractions are kept in the step-05 metrics and summed at
> load time; only the 5 sums enter the model. Those AUC figures were measured before the leak fix
> below and are not comparable to the current ones.

### No predictor may identify the year — or proxy for it

This is the rule the predictor set is built around, and it cost two predictors. It is recorded
because the failure is easy to reintroduce and hard to see.

Per-year label prevalence in the fitting set is an artifact of **where people drew**, not of the
fire regime: it runs from 0.00 (2001, 2009, 2016) to 1.00 (1998), and seven fire-years have no
labels at all. Give the model the year and it learns that sampling pattern, then applies it to every
object of that year.

**`fire_year` and `year_calendar` were predictors, and they were leaking the labels.** Removed
2026-07-28. What was measured on the then-deployed fit: those two columns took **18.4 % of all
splits** in the forest (9.9 % + 8.5 %) — the **top two of 22**, ahead of `seed_mean` (6.7 %);
Spearman(per-year label prevalence, per-year predicted fire %) was **0.83** on deployed predictions
and **0.96** out of fold — out of fold, the prediction for a year *was* its label prevalence. The
symptom that exposed it was three implausible fire-years (**1998 called 100.0 % fire**, 2012 96.6 %,
2013 93.3 % — and 2013 has no labels at all, so that figure was interpolated between 2012 and 2014),
but every year was affected. Removing them cost pooled OOF AUC (0.9211 → 0.8948) and **gained**
n-weighted **within-year** OOF AUC (0.8400 → 0.8467): the pooled gap had been pure between-year
prevalence. That signature — pooled falls, within-year holds — is what removing leakage looks like.

**Grid-blocked CV structurally could not detect it.** Each of the 5 grid folds contains 17–20 of the
21 labelled years, so the year lookup sits on both sides of every split and reads as skill. The fold
design blocks *space*, not *time* (§7). A per-year diagnostic therefore exists as a standing check:
`notebooks/objects-analysis.qmd` §8.

**`n_mean` was dropped for the same class of reason** (same day). The mean Landsat observation count
per object was carried as a **proxy for polygon quality** — how well-observed, and so how
well-constrained, each object's probability is. But it is a **soft era proxy**: observation density
rises across the record as sensors come online (L5, +L7 1999, +L8 2013, +L9 2021), giving
Spearman(fire_year, mean `n_mean`) = **0.81**, and with it in the model the per-year fire rate
inherited a **0.79** time trend. In a 28-year collection built for trend analysis, that lets an
improving satellite archive masquerade as a rising fire regime. Dropping it is cheap because
**`seed_mean` already carries observation quality density-normalised**: the step-04 seed threshold K
is chosen per pixel by `(veg_fire, n)` (04 §4.1). Measured, the two are near-orthogonal per object
(Spearman **+0.014**) and `seed_mean`'s own era trend is far weaker (+0.45 vs +0.81) — so removing
`n_mean` strips the raw density that normalisation was designed to neutralise, and nothing else. The
manufactured trend roughly halved (Spearman 0.789 → **0.407**) for **0.0014** of within-year AUC.

What replaced them:

- **`fire_year`, `year_calendar` — dropped as predictors**, but they keep their product roles:
  `year_calendar` places an object in a calendar year for the step-08 monthly products (08 §6), and
  the fire-year is embedded in `oid`. Both remain in the step-05 metrics and in the upload.
- **`doy_median` → `doy_sin` + `doy_cos`** (period 365.25). Day-of-year carries season, not year, so
  it is legitimate — but it must be **circular**. The fire season straddles Dec/Jan (the entire
  reason a fire-year exists, 04 §2), so an axis-aligned tree cannot express "December through
  February" as one region in raw DOY. A threshold on `sin` or `cos` selects a single arc, so the pair
  represents wrap-around intervals in two splits. (A linear day-of-*fire*-year coordinate would fix
  the wrap in one column, but would hard-code the fire-year start convention.)
- **`date_span` — kept.** A duration names neither a year nor a season, so it carries no sampling
  signal.
- **No absolute time coordinate is a predictor**, including the raw `date_{median,min,max}` columns,
  which never were — the reason is restated at `objects_data_functions.R::add_derived`.

The residual time trend in the deployed product is **Spearman 0.407 / Pearson 0.325** over a range
of 71.0–83.7 % fire (sd 3.0). Some interannual structure is real. It is **unattributed**, not proven
clean: do not publish it as a fire-regime finding without checking against an independent record.

> Removing the leak does **not** make prevalence calibrated. The labels are still not a random
> sample of objects, so the *level* of the fire rate remains uncertain (§6, §9). What the fix removes
> is the model reading the year off the sampling.

### Collection 2: two metrics to stop computing

- **`n_mean` — do not compute it at all** in the object summaries. It is not a predictor, and
  carrying it invites exactly the mistake above. The observation count still belongs where it is
  already used and normalised: inside the step-04 seed definition.
- **`n_pixels` — drop it too; `area_ha` is the meaningful one.** The pixel scale is
  latitude-dependent (§9), so a pixel count is not a size, and the model confirms it carries nothing
  the area does not: `n_pixels` is **last of 20** on every importance measure (permutation |Δp|
  **0.0006**, permutation AUC drop **0.0000**, ALE range 0.0076 — §8). It is kept in collection 1
  only because it answers "how many pixels is this really" when reading a QGIS row.

## 5. What comes out per object — and the deployed fire call

`p_mean`, `p_sd`, `p_q05`, `p_q95` and **`p_width = p_q95 − p_q05`** precomputed. The semantics
matter: these bound the **probability** — epistemic uncertainty about the fitted function — *not*
the class label. A predictive interval for a Bernoulli draw would be 0/1 and useless. Wide
`p_width` = the model does not know = where a round-2 collection should go.

Three call columns, because a collected label must override a model guess:

| column | meaning |
|---|---|
| `fire_model` | the model's call: `p_mean` vs the cut for that object's size band (§6) |
| `fire_tag` | the collected label for that object, if any — `1` fire, `0` non-fire, **`-1` = nobody labelled it** |
| `fire` | **THE DEPLOYED CALL** = `fire_tag` where there is one, else `fire_model` |

`resolve_fire()` in the shared module is the single definition, and `tag_lookup()` builds the tag
column from `polygons_data_merged.csv` with the same cuts as the fitting set (objects with
conflicting classes are dropped, so a tag is never ambiguous). Reporting inside `predict` uses
`fire_model`, so the model's own rate is never silently improved by the tags.

**Why `-1` and not `NA`:** the upload is a Shapefile, and OGR writes an unset DBF integer as null,
which GEE reads back as **`0`** — indistinguishable from "a human said NOT fire". The sentinel is
explicit for that reason, and it covers a second kind of missingness: `fire_model = fire = -1` marks
the **36 objects that could not be scored at all** (an NA predictor — all-dieback objects, 05 §3).
The CSVs keep R-native `NA`; the sentinel exists only because DBF cannot express it.

## 6. The classification threshold — 0.5 is wrong, and the right cut rises with size

`scripts/objects_threshold.R` sweeps every cut on the **out-of-fold** probabilities (`oof_grid_5.csv`
— never in-sample, or the cut would be chosen against answers the model already saw) and reports
four criteria. **Youden's J (sens + spec − 1) is the headline** because it is the only one here that
does not move with prevalence, and our labelled set is not a random sample of objects. F1 and
accuracy are reported but drift with that sampling bias; `J_area` weights each object by `area_ha`
(the deliverable is an area product) but a handful of huge objects dominate its weights.

Deployed — `config/object_model_thresholds.csv` (tracked):

| stratum | n | prevalence | **cut** | sens | spec | J | J at 0.5 | bootstrap 5–95 % |
|---|---|---|---|---|---|---|---|---|
| < 1 ha | 114 | 0.254 | 0.250 | 0.897 | 0.929 | 0.826 | 0.643 | 0.211–0.380 |
| **1–50 ha** | 3217 | 0.468 | **0.202** | 0.837 | 0.763 | 0.600 | 0.492 | 0.183–0.283 |
| **50–300 ha** | 1192 | 0.576 | **0.436** | 0.854 | 0.791 | 0.645 | 0.631 | 0.326–0.565 |
| **≥ 300 ha** (pooled) | 732 | 0.773 | **0.690** | 0.857 | 0.849 | 0.706 | 0.662 | 0.601–0.792 |

**The cut rises with size — 0.20 → 0.44 → 0.69**, and for 1–50 vs 50–300 vs ≥300 the bootstrap
intervals are near-disjoint, so those differences are signal, not resampling noise: the model is far
more confident on big objects, and a single threshold would be simultaneously too high for small
objects and too low for large ones. The gain is concentrated where the error was — in 1–50 ha,
sensitivity 0.596 → 0.837.

**Splitting ≥300 ha in two buys nothing**, which is why it is swept but **deployed pooled**: the two
halves' J values sit inside each other's bootstrap intervals. The same evidence standard that
justified the other bands says these two are one band; deploying them separately would add a knob
that can only overfit. Hence `DEPLOY_BANDS` ≠ `SIZE_BANDS` in the script, and the config carries
four rows. `band_lower()` parses each band's lower bound out of its own label, so the config can
gain or lose bands without any code knowing their names.

`06-object_model.R predict` applies the file and logs the rule it used; with the file absent it
falls back to 0.5 and says so. The `< 1 ha` row is recorded for completeness but should not be
leaned on — 114 objects, 29 of them fire, and that whole stratum is 3.4 % of objects for 0.044 % of
area, so the **hard size cut, not a threshold, is the right tool there**.

**The threshold governs object COUNTS, not the area headline.** Against the labelled objects' own
burned area (2387.6 kha), `p > 0.5` gives 2327.7 kha over 2314 objects and the per-band cuts give
2270.6 kha over 2898 objects — ±5 % of area for +25 % of objects. Same story on the full FY2020: the
band cuts call **63 923** objects fire (4257 kha) where 0.5 called **50 519** (4189 kha) — **+13 404
objects for +68 kha** out of 4841 kha in the year. Area is dominated by large objects the model is
confident about, so lowering the cut is cheap in area and expensive only in small-object commission.

**The caveat that limits all of this.** Youden's J is prevalence-invariant *as a measure*, but the
threshold it selects is optimal for the prevalence of the set it was chosen on — and our labels are
not a random sample. In the 1–50 ha band labelled prevalence is 0.47, whereas most of the 1.4 M real
objects in that band are presumably noise. Applied to the whole population the band cuts call
**79 % of 1–50 ha objects fire**, which is implausible as a population rate — and even at 0.5 the
model calls a large majority of them fire, so this is the *label sampling*, not the cut. What would
settle it is a **randomly sampled** set of small-object labels — a collection task, not a modelling
one (BACKLOG). Until then, treat 0.20 as the **lower bound** of a defensible range for the 1–50 ha
cut.

## 7. Cross-validation: the fold design decides the answer

`Rscript …/06-object_model.R cv [region|grid K|random K]`; out-of-fold predictions land in
`data/objects-pred/oof_<spec>.csv`. **Only `grid 5` is deployed**: 0.5° blocks (349 of them)
assigned to 5 folds.

| | at 0.5 | at the deployed per-band cuts |
|---|---|---|
| AUC | **0.8907** | — |
| accuracy | 0.790 | 0.814 |
| sensitivity | 0.717 | **0.845** |
| specificity | 0.872 | 0.780 |
| precision | — | 0.813 |

The cuts trade specificity for the sensitivity a burned-area product needs. Per fold, AUC runs
**0.845–0.950** (the lowest is fold 5, which holds 1755 labels at prevalence 0.85). The n-weighted
**within-year** AUC is **0.8453** over the 18 years with both classes — that is the number to watch
for leakage, not the pooled one.

Why grid blocks and not regions: leave-one-region-out is the harshest possible test and not the
deployment condition — every region *does* have labels in production, and held-out prevalence swings
0.10 (Patagonia) to 0.83 (Pampas), so a fold's model would be trained on a different class mix than
it is scored on. Grid blocks remove the adjacency leak (objects from one drawn polygon are
neighbours) while keeping every region represented in every fold. `cv region` and `cv random K`
still run if the comparison is wanted; their figures are not maintained here.

**A fold design blocks only what it is built to block.** This one blocks space, not time — which is
exactly why it could not see the `fire_year` leak (§4), and why the per-year diagnostic exists
separately.

**Where the error lives** — the same out-of-fold predictions, by size band:

| band | labels | share of labels | share of population | AUC | sens @ 0.5 | sens @ cut | spec @ cut |
|---|---|---|---|---|---|---|---|
| < 1 ha | 114 | 2 % | 3.4 % | 0.957 | 0.655 | 0.862 | 0.929 |
| **1–50 ha** | 3217 | **61 %** | **83.4 %** | **0.871** | **0.596** | 0.837 | 0.763 |
| 50–300 ha | 1192 | 23 % | 11.4 % | 0.899 | 0.821 | 0.853 | 0.791 |
| ≥ 300 ha | 732 | 14 % | 1.8 % | 0.923 | 0.915 | 0.855 | 0.849 |

So the weak band is **1–50 ha**, which is also where 83 % of the objects are: AUC 0.871 and only
**0.60 sensitivity at 0.5** — it would miss two fires in five there, which is what the 0.202 cut
exists to fix. Above 300 ha the model is nearly clean. (Note the two share columns: 1–50 ha is 61 %
of the *labels* but 83 % of the *population* — small objects are under-sampled relative to how many
there are, which is the same covariate-shift story as §9.)

**And one caveat no fold design fixes.** The labelled sample is not a random sample of objects, and
per-year prevalence swings 0.00 to 1.00. Treat the *ranking* and the *uncertainty* as the product;
do not read `p_mean` as a calibrated absolute probability.

## 8. What the model leans on — importance and ALE

`scripts/objects_importance_ale.R` → `importance_objects.csv` + `ale_curves_objects.csv`, rendered
in `notebooks/objects-analysis.qmd` §9. Four measures, because none is trustworthy alone: the
predictors are strongly correlated (`area_ha`/`n_pixels`/`perimeter_m` near-collinear,
`burned_around_{1,2,3}` nested windows) and every importance measure mishandles correlation its own
way.

| measure | what it is | how it misleads |
|---|---|---|
| `split_share` / `root_share` | fraction of all (root) forest splits taken by the column, parsed from the saved forest JSON | biased toward high-cardinality continuous columns; credit splits arbitrarily between correlated columns |
| `perm_dp` | mean \|Δ predicted probability\| when the column is shuffled | the measure that matches the upload question — but a correlated pair can both look small |
| `perm_auc_drop` | AUC lost on the labelled set when the column is shuffled | in-sample, so "what separates the classes it was shown", not validation |
| `ale_range` | max − min of the 1-D **ALE** curve (Apley & Zhu), in probability units | ALE not PDP *because* of the correlation — a PDP averages over combinations that do not exist (a 1-pixel object with a 10 km perimeter) and invents effects there |

Ordered by `perm_dp` (full table in the notebook):

| predictor | split share | perm \|Δp\| | perm AUC drop | ALE range |
|---|---|---|---|---|
| `frac_grass_temp` | 0.083 | **0.243** | 0.217 | 0.488 |
| `seed_mean` | 0.070 | **0.206** | 0.081 | **0.587** |
| `frac_woody` | 0.049 | 0.073 | 0.010 | 0.171 |
| `burned_around_1` | 0.062 | 0.072 | 0.008 | 0.222 |
| `frac_grass_inund` | 0.064 | 0.068 | 0.028 | 0.415 |
| `frac_agri` | 0.064 | 0.061 | 0.010 | 0.263 |
| `doy_cos` | 0.068 | 0.061 | 0.011 | 0.140 |
| … | | | | |
| `perimeter_m` | 0.025 | 0.006 | 0.001 | 0.028 |
| `shape_index` | 0.034 | 0.003 | 0.000 | 0.005 |
| `n_pixels` | 0.021 | **0.0006** | **0.0000** | 0.008 |

Two things this settles:

- **Two predictors carry the model**: the temperate-grassland fraction and the seed share. That is
  the intended story — real scars are densely seeded (04 §4.1), and the fuel type decides how a
  burned patch looks. `seed_mean` has the largest *effect size* (ALE 0.587) even though
  `frac_grass_temp` moves the output most on average.
- **The size/shape block is nearly inert**, and `n_pixels` is inert outright — hence the collection-2
  note in §4. `area_ha` still earns its place (ALE 0.160) because it selects the threshold band.

No predictor shows the signature that caught `fire_year`: a large split share concentrated at the
root with an effect that tracks the calendar. `doy_sin`/`doy_cos` sit mid-table with small ALE
ranges, which is what a genuine seasonal signal looks like.

## 9. The whole population — size and uncertainty

`notebooks/objects-analysis.qmd` scores all **1 689 419** objects (28 fire-years; 36 unscored) and
asks the question the minimum-size decision was supposed to rest on: *is the model measurably less
able to classify small objects?* `% undecided` = the `p_q05`–`p_q95` interval straddles the cut that
applies to that object.

| display class | objects | area (kha) | cut | median `p` | mean `p_width` | % called fire | % undecided |
|---|---|---|---|---|---|---|---|
| < 0.5 ha | 15 070 | 4 | 0.250 | 0.187 | 0.412 | 44.5 | 49.6 |
| 0.5–1 ha | 42 514 | 34 | 0.250 | 0.366 | 0.322 | 59.3 | 40.5 |
| 1–50 ha | 1 409 244 | 16 787 | 0.202 | 0.649 | 0.319 | 78.6 | 31.0 |
| 50–300 ha | 192 380 | 20 465 | 0.436 | 0.736 | 0.310 | 68.3 | 31.5 |
| 300–1000 ha | 22 791 | 11 534 | 0.690 | 0.950 | 0.217 | 77.4 | 24.9 |
| ≥ 1000 ha | 7 384 | 36 167 | 0.690 | 0.989 | 0.129 | 90.3 | 13.2 |
| **all** | **1 689 383** | **84 991** | — | — | **0.317** | ~77 | **31.3** |

**The answer is no — or rather, not distinctively.** Uncertainty falls monotonically with size
(width 0.412 → 0.129, undecided 50 % → 13 %), the expected direction, but the model is **unsure
everywhere**: a mean `p_width` of 0.317 means the average 5–95 % interval spans 32 points of
probability, and even the ≥1000 ha class cannot place 13 % of its objects on one side of its cut. So
a minimum-size cut removes objects that are *somewhat* worse than average, not objects that are
qualitatively unclassifiable:

| cut | objects dropped | area dropped | fire-area dropped | dropped: width / undecided | kept: width / undecided |
|---|---|---|---|---|---|
| 0.5 ha | 0.89 % | 0.005 % | 0.002 % | 0.412 / 49.6 % | 0.316 / 31.1 % |
| 1 ha | 3.41 % | **0.044 %** | 0.032 % | 0.346 / 42.9 % | 0.316 / 30.9 % |
| 2 ha | 12.60 % | 0.321 % | 0.296 % | 0.332 / 40.8 % | 0.315 / 29.9 % |
| 5 ha | 33.99 % | 1.749 % | 1.665 % | 0.317 / 34.9 % | 0.317 / 29.4 % |

So **the honest argument for a 1 ha minimum is cost/benefit, not uncertainty**: 3.4 % of objects for
0.044 % of area — a large reduction in count and noise for a rounding error in the headline number.
Do not claim the model "cannot classify" sub-hectare objects; it classifies them the same way it
classifies everything, only with wider intervals, and it does push them toward non-fire (median
`p_mean` 0.187 in `<0.5 ha` vs 0.989 in `>=1000 ha`, so the discrimination is real).

**What the width actually indicates is covariate shift.** 5255 labels against 1.69 M objects,
collected where fires were known rather than sampled from the object population — BART widens its
posterior exactly where it has no data, and 31 % undecided is that message. This reinforces, from
the population side, the caveat §6 reached from the label side: the binding limitation is the
labelled sample, not the model or the cut. The deployed cuts should be treated as a lower bound.

### Also measured: the pixel scale is latitude-dependent

`area_ha` is **not** `n_pixels * 0.09`. Objects carry lat/lon pixel coordinates (~30 m *at the
equator*) and area is measured on the ellipsoid, so one pixel is `900*cos(lat)` m² — **831 m² at
22° S down to 517 m² at 55° S** (median 778). Harmless, but two consequences: a size class is a
pixel-count *range* (1 ha = 12 px in Formosa, 19 px in Santa Cruz), and the same 15-px object
changes class between the north and Patagonia. This is the first reason `n_pixels` is not a size
(§4); the importance analysis is the second. Also visible there: the `n_pixels` count **dips** from
3796 one-pixel objects to 778 at five, then climbs monotonically (6 px → 3081 … 20 px → 12 474). A
segmentation floor would give a hard cut, not a dip-then-rise, so something is producing isolated
1–2 px objects that 3–5 px does not get — the step-05 1-px dilation connectivity hack is the
suspect (BACKLOG).

## 10. The collection-00 empirical filter, as a baseline

Reproduced verbatim in `objects_data_functions.R::c00_pass`. Against the 5255 labels: **accuracy
0.62, sensitivity 0.50, specificity 0.77, precision 0.70** — versus 0.79 / 0.72 / 0.87 for BART
out-of-fold at 0.5, or 0.81 / 0.85 / 0.78 at the deployed cuts. Where it breaks (from
`scripts/objects_data_explore.R`):

- **Case 1 (1–50 ha) has sensitivity 0.19** — it discards 81 % of the real fires in the band holding
  83 % of all objects. One threshold does nearly all the damage: `burned_around_3 > 0.7` cuts **81 %
  of the FIRE objects** there (and 90 % of the non-fire) — in collection 1 that band's fire objects
  sit at a median `burned_around_3` of 0.58, well below the cut.
- **Case 3 (≥ 300 ha auto-accept) has precision 0.77** — 166 of the 732 labelled objects above
  300 ha are non-fire, so "very large is rarely non-fire" does not hold here. Those objects supply
  **69.6 % of all the area the filter keeps**, so the assumption is load-bearing.
- `circularity > 0.01` is **inert** (cuts 0.0 % of fire, 0.4 % of non-fire); `shape_index < 7` is the
  one term working as intended (cuts 20 % of fire vs 48 % of non-fire in case 2).
- On the full population it keeps **23.8 % of objects / 80.6 % of the area**, stable across years
  (18.5–27.5 %).

Keep the filter only as a **baseline to compare against**, and as the source of the two ideas worth
keeping — the hard small-object cut, and size-stratified reasoning. The model replaces the
thresholds.

## 11. Inspecting it in QGIS, without uploading to GEE

`scripts/objects_inspect_export.R` joins the predictions + metrics + the c-00 verdict onto the
step-05 geometry already on disk, writing **`<fy>_objects_pred.gpkg`** — every object of the year,
**32 curated fields**. Graduate the fill on `p_mean` (or `p_width`), add an XYZ imagery basemap, and
walk cases with the attribute table and filter expressions. **All 28 years** are built by
`scripts/run_06_inspect.sh` (parallel, one `Rscript` per year, resumable, biggest-first): **~1 min
on 6 workers, 6.3 GB**, feature counts summing to exactly 1 689 419. Unlike prediction this is I/O-
and memory-bound (a worker holds a whole year's geometry — up to 386 MB / 93 k multipolygons), hence
`-j 6` rather than 8. A `qgz` project over the 28 layers lives beside them in the cache.

`--sample N` additionally writes a decile-stratified `<fy>_objects_sample.geojson` (geometry
simplified to ~30 m), which is the answer to "is there a geemap midpoint": **yes** —
`Map.add_geojson(path)` puts a local vector on an ipyleaflet map as a **client-side** layer while
GEE imagery (candseed, min-NBR, the bpts composite) renders as server-side tiles beside it, with
nothing uploaded. The binding constraint is the browser, so keep it in the low thousands of
features. Default is `0` (GPKG only) since QGIS is what actually gets used.

> **QGIS gotcha:** the layer name starts with a digit (`2020_objects_pred`), so any SQL context — DB
> Manager, virtual layers, `ogrinfo -sql` — needs it **double-quoted**. Symbology and
> attribute-table filters are unaffected.

### The inspection field set (32 fields)

The 23 raw `frac_c*` columns are not model predictors (they are summed into the 5 groups) and 28
years of them is dead weight in a table read by eye, so the GPKG carries a curated set ordered the
way a row is read — what it is, what we decided, why, then the evidence. `--fields all` restores
everything for one year.

| group | fields |
|---|---|
| identity & size | `oid`, `fire_year`, `area_ha`, `n_pixels`, `size_class` |
| the verdicts | `fire`, `fire_model`, `fire_tag`, `c00_pass` (collection-00 filter), `verdict` |
| why the model said it | `p_mean`, `p_width`, `p_thresh`, `p_margin`, `th_band`, `c00_case` |
| burn evidence & timing | `seed_mean`, `burned_around_{1,2,3}`, `doy_median`, `date_span`, `date_median_date` |
| aggregated vegetation | `frac_agri`, `frac_grass_inund`, `frac_pasture`, `frac_grass_temp`, `frac_woody` |
| shape | `perimeter_m`, `convexity`, `mbr_fill`, `mbr_elongation`, `circularity`, `shape_index` |

Four fields do not come from step 05 and are the reason this is a script rather than a join:

- **`p_thresh` / `p_margin` / `th_band`** — the cut that applied to *this* object's size band and the
  signed distance to it. A verdict without its threshold is unreadable when the threshold varies by
  size; `abs("p_margin") < 0.05` finds the calls actually worth eyeballing. `apply_thresholds()`
  recomputes them and **cross-checks against the stored `fire_model`**, so a thresholds-file edit
  after a prediction run is reported instead of silently making the map lie.
- **`verdict`** — one categorical (`both` / `model only` / `c00 only` / `neither` / `unscored`) so
  "where do the model and the old empirical filter part ways" is a single symbology.

Note `size_class` (6 display classes) is deliberately finer than `th_band` (4 threshold bands): a
row can be display class `>=1000 ha` while its call came from band `>=300 ha`. The display breaks
split 1 ha into `<0.5` / `0.5-1` because that is where the minimum-size decision lives.

### Where to look first

Across all 28 fire-years the model and the collection-00 filter **disagree on 26.6 % of the object
area** (58–70 % of objects, year by year), and the disagreement is cleanly structured — `c00 only`
is *large* objects, `model only` is *small* ones:

| verdict | objects | area (kha) | mean ha | mean `p_mean` | mean `p_width` | % of area |
|---|---|---|---|---|---|---|
| both | 318 565 | 57 462 | 180 | 0.785 | 0.302 | 67.6 |
| **c00 only** (filter keeps, model rejects) | 83 122 | 11 051 | 133 | 0.161 | 0.316 | 13.0 |
| **model only** (model keeps, filter rejects) | 976 781 | 11 597 | 12 | 0.719 | 0.353 | 13.6 |
| neither | 310 915 | 4 880 | 16 | 0.088 | 0.220 | 5.7 |

**Start with `"verdict" = 'c00 only' AND "area_ha" >= 300`.** That is **5872 objects holding 6397 kha
— 7.5 % of all object area** — where the old filter auto-accepts under its `>= 300 ha` rule and the
model rejects *without confidence* (mean `p_mean` 0.35, mean `p_width` 0.46). It is the
highest-area-stakes set in the collection, small enough to walk object by object, and at `>= 300 ha`
each one is unmistakable against imagery. Whatever is decided there moves the headline number more
than anything else in step 06.

By contrast `model only` below 1 ha is **31 933 objects for 22 kha** — 0.03 % of area. Worth a
glance to see *what* they are, not worth arguing about.

| expression | what it shows |
|---|---|
| `"verdict" = 'c00 only' AND "area_ha" >= 300` | **the set to review first** (above) |
| `"verdict" != 'both'` | every disagreement with the collection-00 filter |
| `abs("p_margin") < 0.05` | borderline calls — objects that would flip under a small threshold change |
| `"p_width" > 0.5` | where the model has no idea; also the round-2 collection targets |
| `"fire_tag" >= 0` | the collected labels — check the model against them by eye |
| `"fire_tag" >= 0 AND "fire_tag" != "fire_model"` | labels the model disagrees with |
| `"size_class" IN ('<0.5 ha','0.5-1 ha')` | the minimum-size decision |
| `"th_band" = '1-50 ha' AND "fire" = 1` | the weakest band's positives (83 % of all objects) |
| `"seed_mean" < 0.1 AND "fire" = 1` | fire calls with little seed support — the most suspicious positives |

Suggested setup: categorise the fill on `verdict`, add an XYZ satellite basemap, keep `p_mean`,
`p_width`, `p_margin`, `area_ha` and `seed_mean` visible in the attribute form, then sort by
`p_margin` to walk from the most borderline call outwards.

That covers Lican's suggestion without a Shiny app: the sampling-by-predictor-range panel is a QGIS
filter expression or a geemap cell. Build the app only if a *shared* review tool is wanted — for one
analyst it adds a UI to maintain and no capability QGIS lacks. A whole-country raster overview is
the other option not taken: rasterizing `p_mean` at 30 m country-wide is 9.16 B cells (05 §7), so it
would have to be coarsened to ~300 m, which erases the small objects that are precisely the ones in
doubt.

## 12. Uploading to GEE — the whole object set, per fire-year

**Decision (2026-07-28): upload every object, not just the classified fire subset.** The earlier
plan was fire-only, to save space. Two reasons overrode it: an expert user needs the rejected
objects to find **fires the model missed** (a fire-only layer can only ever show commission error),
and the rejected objects with their predictors are the raw material for aiming the next
collection's label campaign. Measured, fire-only would have saved ~33 % of the geometry with extreme
per-year variance — not enough to justify a one-sided product.

Each fire-year becomes one FeatureCollection asset, named for the **fire-year** (not the calendar
year — `oid` and the asset name agree, and `year_calendar` is a column):

```
projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/WORKFLOW-EXPORTS/objects_raw/objects_raw_YYYY
```

`objects_raw_1998 … objects_raw_2025`, 28 of them, from `objects_raw_<fy>.zip` of the same name.
Each carries **28 fields**: `oid`, the
**20 predictors**, `fire` / `fire_model` / `fire_tag`, `p_mean`, `p_width`, `year_cal`, `date_medd`.
All 20 predictors are there deliberately: the layer exists so a call can be *re-judged*, which is
impossible without the inputs it was made from. `n_mean` is the one metric explicitly withheld
(§4), via `DROP_COLS`, so its absence reads as a decision rather than an oversight.

**Format — zipped Shapefile, not GeoJSON.** Geometry is the whole cost (the step-05 GPKGs carry no
attributes): one year measured 373 MB GPKG → ~880 MB GeoJSON → **73 MB zipped SHP**. The 28 zips
total **1.3 GB**. Field names are renamed by hand to ≤10 chars in `objects_upload.py::RENAME` —
never let OGR auto-truncate, since `date_median`/`date_median_date` and `burned_around_{1,2,3}`
collide. CRS is already **EPSG:4326** (GEE-native); do not reproject.

**A single all-years FeatureCollection is not possible on ingest.** A Shapefile `.shp` caps at
**2 GB** and the full 28-year geometry is far past that, so it is 28 uploads. Merge them
server-side afterwards if one FC is wanted (`ee.FeatureCollection(ids).flatten()` over the 28
assets, exported to a new asset) — `oid` already carries the fire-year, so nothing is lost.

**The ingest is manual.** `earthengine upload table` rejects any source without a `gs://` prefix
(`ee/cli/commands.py:_check_valid_files`) and the client library exposes no upload-URL helper (the
legacy `getTableUploadUrl()` is gone; the Code Editor stages through a browser-internal endpoint
with no public equivalent). A scripted ingest therefore needs a GCS bucket, and as of 2026-07 we
have none: `mapbiomas-fire-485203` has **no billing account** (bucket creation → `403 … billing
account … disabled in state absent`) and neither GEE account has `storage.buckets.list` on
`mapbiomas-argentina`. So: **Code Editor → Assets → NEW → Table upload → Shapefile**, 28 times,
watching with `earthengine task list`. `objects_upload.py` detects the missing bucket and prints the
exact dialog values instead of failing.

> **Set max vertices = 1000000 in the dialog, for every year.** Objects routinely exceed it (FY2000
> has one of 2 178 607 vertices, FY2023 one of 1 895 434). GEE then subdivides the geometry *inside*
> the feature, so `oid` and the properties survive; without it the feature can be rejected.

Build and check the packages:

```bash
# build all 28 zips (biggest first, 4 workers, resumable; skips years already built)
tmux new-session -d -s zip07 '/abs/path/to/collection-01/scripts/run_07_upload_zips.sh -j 4'

# pre-upload gate over the 28 zips
tmux new-session -d -s validate '$PYTHON collection-01/scripts/validate_upload_zips.py -j 8'
```

`validate_upload_zips.py` exists because **the upload is by hand, so a bad zip is not caught by a
failing pipeline — it is caught weeks later as a wrong map.** It imports `RENAME` and
`PREDICTOR_NAMES` from `objects_upload.py`, so it validates against what the writer believes it
wrote, and checks per year: flat zip with all components, EPSG:4326, the 28 required fields present
and `n_mean` absent, integer-typed code fields, feature count against the prediction CSV, `oid`
unique, **the three code columns never NULL and only ever −1/0/1**, `fire == (fire_tag if fire_tag
>= 0 else fire_model)` feature by feature, no null geometries, and max vertices per feature. It
writes `objects-analysis/upload_zip_validation.csv` and exits non-zero on any failure.

The NULL-code check is the one that matters most, and it caught a real bug: unscored objects were
leaving `fire_model`/`fire` unset in the DBF, which GEE would have read as `0` — a silent "not
fire" for objects that were never classified at all. Hence the −1 sentinel in all three columns
(§5).

**Run of record (2026-07-28):** 28 zips, 1.3 GB, **ALL PASS** — 1 689 419 features, 5256 tagged
objects, 1 295 006 called fire, 36 unscored.

## 13. Onward — step 07

The month-of-burn raster per **calendar** year is built server-side by combining the uploaded
objects with the SNIC metrics images; objects are placed into a calendar year by their
`year_calendar` metric (05 §2.4), and `candseed==3` dieback pixels take the parent object's date,
never their own next-year date (04 §4.3). See `docs/07-vector_to_raster.md`, then `docs/08` for the
network-wide post-processing.
