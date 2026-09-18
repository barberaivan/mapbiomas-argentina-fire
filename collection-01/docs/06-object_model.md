# 06 — Object model: which fire objects are real fire

Step 06 takes the step-05 fire **objects** and their metrics and decides, per object, whether it is
a burned scar or noise. The classifier is a **probit BART fitted locally in R on ~5 k collected
labels**; it replaces collection-00's empirical threshold filter. It scores **all 28 fire-years /
1.69 M objects**, and the whole scored object set — geometry plus every predictor plus the call —
goes back up to GEE as one FeatureCollection per fire-year, which is what step 07 paints.

Step 06 is three files: the labels come from [`06-object_labels.md`](06-object_labels.md), this one
is the model and the upload, and [`06-object_inspection.md`](06-object_inspection.md) is the QGIS
layer for looking at the result.

## Foundations

**A classifier, not a threshold filter.** Collection 00 decided fire with a hand-built rule over
size, shape and neighbourhood (`objects_data_functions.R::c00_pass`). Reproduced verbatim against
our labels it scores **accuracy 0.62 / sensitivity 0.50**, versus 0.81 / 0.85 for the model at the
deployed cuts, and it fails worst exactly where the objects are: it discards 81 % of the real fires
in the 1–50 ha band, which holds 83 % of all objects. Two of its ideas survive — a hard small-object
cut, and reasoning stratified by size ([`notes/06-c00_baseline.md`](notes/06-c00_baseline.md)).

**Probit BART, because of what ~5 k labels allow.** There is no honest way to tune a boosted
ensemble's hyperparameters on a set this small, and BART's defaults are calibrated regularization
priors rather than placeholders. More importantly the posterior yields a **per-object interval** on
the probability — both an uncertainty statement we can publish and the targeting signal for a
round-2 collection. `stochtree` because `num_threads` parallelises the GFR sampler and the MCMC
within a chain.

**The labelled sample, not the model, is the binding limitation — a caveat on everything below.**
The 5255 labels were collected where fires were known, not sampled from the object population
([`06-object_labels.md`](06-object_labels.md)), so per-year prevalence runs 0.00 to 1.00 and small
objects are under-sampled. The model's *ranking* and its *uncertainty* are therefore the product,
not a calibrated probability; the deployed cuts are a **lower bound**; and the fold design has to
be chosen with that sampling in mind.

## Inputs → Outputs

step-05 metric CSVs + collected labels → **`workflow/06-object_model.R`** → `fire` per object →
`objects_upload.py` → one FeatureCollection per fire-year in GEE

| | What it is | Where |
|---|---|---|
| **in** | per-year raster + shape metrics, one row per object, keyed by `oid` | `data/objects-raw/objects_<fy>_{raster,shape}_metrics.csv` |
| **in** | per-year geometry, `oid` only (read for QGIS and the upload, never for fitting) | `data/objects-raw/objects_<fy>.gpkg` |
| **in** | the clean fitting set — 5255 labelled objects ([`06-object_labels.md`](06-object_labels.md)) | `data/objects-labels/polygons_data_merged.csv` |
| **out** | the serialized fit (92.7 MB JSON) + its metadata | `models-store/object_model/` |
| **out** | per-object probabilities and the three call columns | `data/objects-pred/objects_<fy>_pred.csv` |
| **out** | the per-size-band fire-call cut — **tracked in git** | `config/object_model_thresholds.csv` |
| **out** | the whole scored object set, 28 FeatureCollections | `C.OBJECTS_RAW_COL` / `objects_raw_<fy>` |

**`oid = "<fire_year>_<pid>"`** (`05` "Object ids") is the key of every join — labels ↔ objects,
predictions ↔ geometry, upload ↔ raster. "Object" and not "polygon" is the deliberate name: a fire
*is* an object and the metrics are object-level, even though the layer is sparse rather than a
wall-to-wall OBIA partition, and many objects are multipolygons (`05` "Vectorize"). **Geometry and
metrics are split** (`05` "Inputs → Outputs"), so fitting and prediction run from the CSVs alone.

## How it works

### The model

**`stochtree` 0.4.5, `OutcomeModel(outcome = "binary", link = "probit")`.** `num_gfr = 10`,
`num_mcmc = 500` with `keep_every = 4` — i.e. 2000 MCMC iterations thinned to 500 retained draws
(`num_mcmc` is the *retained* count). Thinning is what makes prediction affordable: cost is linear
in draws, and 500 draws still put ~25 order statistics below `p_q05`. `num_threads = 8` =
**physical** cores; tree sampling is memory-bandwidth-bound, so hyperthreads mostly add contention,
and `num_threads` falling back to 1 on Linux/gcc means the build has no OpenMP.

The fit takes ~90 s and serializes to a 92.7 MB JSON that reloads in ~4 s. **Prediction, not the
fit, is the memory risk**: never pass the full object set as `X_test` (1.69 M × 500 doubles ≈
6.8 GB). The shape that works is **fit → serialize → `predict()` per fire-year in `PRED_CHUNK`
blocks → reduce each block to its summaries and discard the draws**, so peak memory is one block
however many objects exist.

**Prediction is single-threaded** — `num_threads` is a *sampler* setting, and neither
`predict.bartmodel` nor the C++ entry points take a thread argument — so the parallelism goes at the
**process** level: `run_06_predict.sh` runs one `Rscript` per fire-year, 8 at a time (4m33s for all
28). Each worker deserializes the JSON itself, ~1.4 GB RSS, so budget ~1.4 GB × workers.

### The 20 predictors

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
(`objects_data_functions.R::veg_groups`), never from typed-in codes, so a remap change follows
through — and a code landing in two groups is an error, not a silent reshuffle. The groups are
deliberately **not** region-separated and **not a partition**: the five sum to 0.70 on average,
never above 1. They replaced the 23 raw `frac_c*` columns, which were 58 % of the design matrix and
so ate BART's split budget ([`notes/06-predictor_selection.md`](notes/06-predictor_selection.md)).

The 8 predictors that do not exist on disk — `doy_sin`, `doy_cos`, `date_span` and the 5 veg groups
— are built at load time by `add_derived()`. `predict` also writes them to
`objects_<fy>_derived.csv` so the upload can carry them without Python reimplementing the by-name
veg grouping (which would drift).

#### Why no predictor may identify the year

**This is the rule the predictor set is built around, it has cost two predictors, and it is easy to
reintroduce.** Per-year label prevalence in the fitting set is an artifact of *where people drew*,
not of the fire regime: it runs 0.00 to 1.00 and seven fire-years have no labels at all. Give the
model the year and it learns that sampling pattern, then applies it to every object of that year.

- **`fire_year` and `year_calendar` were predictors and were leaking the labels.** Removed
  2026-07-28: out of fold, the prediction for a year *was* its label prevalence. Pooled OOF AUC fell
  0.9211 → 0.8948 and **within-year** OOF AUC rose 0.8400 → 0.8467 — pooled falls, within-year
  holds, which is what removing leakage looks like. They keep their **product** roles (`oid` carries
  the fire-year; `year_calendar` places an object in a calendar year for step 07), and they stay in
  the step-05 metrics and in the upload.
- **`n_mean` was dropped for the same class of reason** — a **soft era proxy**. Observation density
  rises across the record as sensors come online, so carrying it let an improving satellite archive
  masquerade as a rising fire regime in a collection built for trend analysis. It is cheap to drop
  because `seed_mean` already carries observation quality density-normalised (the step-04 seed
  threshold K is chosen per pixel by `(veg_fire, n)`, `04` "Seeds and candidates") and the two are
  near-orthogonal per object.
- **`doy_median` → `doy_sin` + `doy_cos`** (period 365.25). Day-of-year carries season, not year, so
  it is legitimate — but it must be **circular**: the fire season straddles Dec/Jan (`04` "The
  fire-year"), so an axis-aligned tree cannot express "December through February" as one region in
  raw DOY, whereas a threshold on `sin` or `cos` selects an arc.
- **`date_span` is kept** — a duration names neither a year nor a season — and **no absolute time
  coordinate is a predictor**, including the raw `date_{median,min,max}` columns, which never were
  (restated at `objects_data_functions.R::add_derived`).

**Grid-blocked CV structurally could not detect the leak**: each fold contains 17–20 of the 21
labelled years, so the year lookup sits on both sides of every split and reads as skill. The fold
design blocks *space*, not *time*, so a per-year diagnostic exists as a standing check in
`notebooks/objects-analysis.qmd`.

**What remains after the fix.** The residual time trend in the deployed product is **Spearman 0.407
/ Pearson 0.325** over a range of 71.0–83.7 % fire. Some interannual structure is real, but this is
**unattributed, not proven clean**: do not publish it as a fire-regime finding without an
independent record. Measurements, including the symptom that exposed the leak — 1998 called 100.0 %
fire — are in [`notes/06-predictor_selection.md`](notes/06-predictor_selection.md).

#### Collection 2: two metrics to stop computing

- **`n_mean` — do not compute it at all** in the object summaries. It is not a predictor, and
  carrying it invites exactly the mistake above. The observation count still belongs where it is
  already used and normalised: inside the step-04 seed definition.
- **`n_pixels` — drop it too; `area_ha` is the meaningful one.** The pixel scale is
  latitude-dependent (`Gotchas`), so a pixel count is not a size, and the model confirms it carries
  nothing the area does not: `n_pixels` is **last of 20** on every importance measure. It is kept in
  collection 1 only because it answers "how many pixels is this really" when reading a QGIS row.

### The three call columns

`p_mean`, `p_sd`, `p_q05`, `p_q95` and **`p_width = p_q95 − p_q05`** are precomputed per object.
These bound the **probability** — epistemic uncertainty about the fitted function — *not* the class
label; a predictive interval for a Bernoulli draw would be 0/1 and useless. Wide `p_width` = the
model does not know = where a round-2 collection should go.

Then three call columns, because a collected label must override a model guess:

| column | meaning |
|---|---|
| `fire_model` | the model's call: `p_mean` vs the cut for that object's size band |
| `fire_tag` | the collected label for that object, if any — `1` fire, `0` non-fire, **`-1` = nobody labelled it** |
| `fire` | **THE DEPLOYED CALL** = `fire_tag` where there is one, else `fire_model` |

`resolve_fire()` is the single definition, and `tag_lookup()` builds the tag column with the same
cuts as the fitting set, so a tag is never ambiguous. Reporting inside `predict` uses `fire_model`,
so the model's own rate is never silently improved by the tags.

**Why `-1` and not `NA`:** the upload is a Shapefile, and OGR writes an unset DBF integer as null,
which GEE reads back as **`0`** — indistinguishable from "a human said NOT fire". The sentinel also
covers a second missingness: `fire_model = fire = -1` marks the **36 objects that could not be
scored at all** (an NA predictor — all-dieback objects have no seed/date stats by design, `05`
"Metrics"). The CSVs keep R-native `NA`; the sentinel exists only because DBF cannot express it.

### The classification threshold

0.5 is wrong, and **the right cut rises with size**. `scripts/objects_threshold.R` sweeps every cut
on the **out-of-fold** probabilities (`oof_grid_5.csv` — never in-sample, or the cut would be chosen
against answers the model already saw). **Youden's J is the headline**, being the only criterion
here that does not move with prevalence; F1 and accuracy are reported but drift with the sampling
bias.

Deployed cuts live in **`config/object_model_thresholds.csv`** (tracked), four rows:

| stratum | n | prevalence | **cut** | J | J at 0.5 |
|---|---|---|---|---|---|
| < 1 ha | 114 | 0.254 | 0.250 | 0.826 | 0.643 |
| **1–50 ha** | 3217 | 0.468 | **0.202** | 0.600 | 0.492 |
| **50–300 ha** | 1192 | 0.576 | **0.436** | 0.645 | 0.631 |
| **≥ 300 ha** (pooled) | 732 | 0.773 | **0.690** | 0.706 | 0.662 |

For 1–50 / 50–300 / ≥300 the bootstrap intervals on the cut are near-disjoint, so those differences
are signal: the model is far more confident on big objects, and one threshold would be
simultaneously too high for small objects and too low for large ones. The gain lands where the error
was — 1–50 ha sensitivity 0.596 → 0.837. **Splitting ≥300 ha in two buys nothing**, so it is swept
but deployed pooled (`DEPLOY_BANDS` ≠ `SIZE_BANDS`); `band_lower()` parses each band's lower bound
out of its own label, so the config can gain or lose bands without any code knowing their names.
`predict` applies the file and logs the rule used; absent it falls back to 0.5 and says so. Full
sweep and all four criteria: [`notes/06-threshold_sweep.md`](notes/06-threshold_sweep.md).

Two things to hold onto. **The threshold governs object COUNTS, not the area headline** — on FY2020
the band cuts call 63 923 objects fire against 0.5's 50 519, for +68 kha out of 4841 kha, because
area is dominated by large objects the model is confident about. And **the cuts are a lower bound**:
J is prevalence-invariant as a *measure*, but the cut it selects is optimal for the prevalence of
the set it was chosen on, and applied to the population the band cuts call 79 % of 1–50 ha objects
fire — implausible as a population rate, and a property of the label sampling rather than of the
cut. The `< 1 ha` row should not be leaned on at all (114 objects, 29 of them fire): there the
**hard size cut, not a threshold, is the right tool**, and step 07 applies it at 1 ha
(`docs/07` "Object exclusion ruleset").

### Cross-validation

`06-object_model.R cv [region|grid K|random K]`; out-of-fold predictions land in
`data/objects-pred/oof_<spec>.csv`. **Only `grid 5` is deployed**: 0.5° blocks (349 of them)
assigned to 5 folds.

| | at 0.5 | at the deployed per-band cuts |
|---|---|---|
| AUC | **0.8907** | — |
| accuracy | 0.790 | 0.814 |
| sensitivity | 0.717 | **0.845** |
| specificity | 0.872 | 0.780 |

The cuts trade specificity for the sensitivity a burned-area product needs. Per fold AUC runs
0.845–0.950, and the n-weighted **within-year** AUC is **0.8453** over the 18 years with both
classes — **that is the number to watch for leakage**, not the pooled one.

**The fold design decides the answer.** Leave-one-region-out is the harshest possible test and not
the deployment condition: every region *does* have labels in production, and held-out prevalence
swings 0.10 (Patagonia) to 0.83 (Pampas), so a fold's model would be trained on a different class
mix than it is scored on. Grid blocks remove the adjacency leak — objects from one drawn polygon
are neighbours — while keeping every region in every fold. `cv region` and `cv random K` still run
for comparison; their figures are not maintained here.

**Where the error lives** — the same out-of-fold predictions, by size band:

| band | labels | share of labels | share of population | AUC | sens @ 0.5 | sens @ cut |
|---|---|---|---|---|---|---|
| < 1 ha | 114 | 2 % | 3.4 % | 0.957 | 0.655 | 0.862 |
| **1–50 ha** | 3217 | **61 %** | **83.4 %** | **0.871** | **0.596** | 0.837 |
| 50–300 ha | 1192 | 23 % | 11.4 % | 0.899 | 0.821 | 0.853 |
| ≥ 300 ha | 732 | 14 % | 1.8 % | 0.923 | 0.915 | 0.855 |

The weak band is **1–50 ha**, which is also where 83 % of the objects are: at 0.5 it would miss two
fires in five there, which is what the 0.202 cut exists to fix. Above 300 ha the model is nearly
clean. Note the two share columns — 1–50 ha is 61 % of the *labels* but 83 % of the *population*,
the same under-sampling the cuts and the posterior width both report.

### What the model leans on

`scripts/objects_importance_ale.R` → `importance_objects.csv` + `ale_curves_objects.csv`, rendered
in `notebooks/objects-analysis.qmd`. **Four measures, because none is trustworthy alone**: the
predictors are strongly correlated (`area_ha`/`n_pixels`/`perimeter_m`; the nested
`burned_around_{1,2,3}` windows) and each measure mishandles correlation its own way. The curves
are **ALE** (Apley & Zhu) and not PDP for the same reason — a PDP averages over combinations that
do not exist, such as a 1-pixel object with a 10 km perimeter, and invents effects there.

| predictor | split share | perm \|Δp\| | ALE range |
|---|---|---|---|
| `frac_grass_temp` | 0.083 | **0.243** | 0.488 |
| `seed_mean` | 0.070 | **0.206** | **0.587** |
| `frac_woody` | 0.049 | 0.073 | 0.171 |
| `burned_around_1` | 0.062 | 0.072 | 0.222 |
| … | | | |
| `n_pixels` | 0.021 | **0.0006** | 0.008 |

**Two predictors carry the model** — the temperate-grassland fraction and the seed share — which is
the intended story: real scars are densely seeded (`04` "Seeds and candidates") and the fuel type
decides how a burned patch looks. **The size/shape block is nearly inert**, `n_pixels` outright so
(hence the collection-2 note above), while `area_ha` earns its place by selecting the threshold
band. And no predictor shows the signature that caught `fire_year`: a large split share concentrated
at the root with an effect that tracks the calendar. Full tables:
[`notes/06-importance_ale.md`](notes/06-importance_ale.md).

### The population and the labelled sample

Scoring all **1 689 419** objects (28 fire-years; 36 unscored) answers the question the
minimum-size decision was supposed to rest on — *is the model measurably less able to classify
small objects?* — and **the answer is no, not distinctively**. Uncertainty does fall monotonically
with size (mean `p_width` 0.412 in `<0.5 ha` → 0.129 in `≥1000 ha`), but the model is **unsure
everywhere**: the global mean `p_width` is 0.317, and 31.3 % of objects have an interval straddling
their own cut.

Two consequences. **The honest argument for a 1 ha minimum is cost/benefit, not uncertainty** — it
drops 3.4 % of objects for 0.044 % of area. Do not claim the model "cannot classify" sub-hectare
objects; it classifies them like everything else, with wider intervals, and does push them toward
non-fire. And **the width is reporting covariate shift**: BART widens its posterior where it has no
data, and 31 % undecided is that message about 5255 labels against 1.69 M objects. Tables:
[`notes/06-population_and_size.md`](notes/06-population_and_size.md).

## Run

```bash
Rscript collection-01/scripts/objects_labels_prep.R all      # the labels (docs/06-object_labels.md)
Rscript collection-01/workflow/06-object_model.R fit         # ~90 s -> models-store/object_model/
Rscript collection-01/workflow/06-object_model.R cv grid 5   # -> oof_grid_5.csv
Rscript collection-01/scripts/objects_threshold.R            # -> config/object_model_thresholds.csv
collection-01/scripts/run_06_predict.sh -j 8                 # all 28 fire-years, resumable
```

`fit` must be re-run before `predict` whenever the predictor set or the fitting set changes; `cv`
and `objects_threshold.R` must be re-run before the cuts are trusted again. Launch the all-years
scripts from `tmux` with an absolute path. To look at the result on a map, see
[`06-object_inspection.md`](06-object_inspection.md).

## Upload to GEE

**Every object is uploaded, not just the classified fire subset**, so that an expert user can find
the fires the model *missed* and so the rejected objects can aim the next label campaign
([`notes/06-upload_decisions.md`](notes/06-upload_decisions.md)). Each fire-year becomes one
FeatureCollection named for the **fire-year** (`C.OBJECTS_RAW_COL` / `objects_raw_1998 …
objects_raw_2025`), carrying **28 fields**: `oid`, the 20 predictors,
`fire`/`fire_model`/`fire_tag`, `p_mean`, `p_width`, `year_cal`, `date_medd`. All 20 predictors are
there deliberately — the layer exists so a call can be *re-judged*, which is impossible without the
inputs it was made from. `n_mean` is the one metric explicitly withheld, via `DROP_COLS`, so its
absence reads as a decision rather than an oversight.

**Zipped Shapefile, not GeoJSON**: geometry is the whole cost — 373 MB GPKG → ~880 MB GeoJSON →
73 MB zipped SHP for one year, 1.3 GB for 28. Field names are renamed by hand to ≤10 chars in
`objects_upload.py::RENAME`; never let OGR auto-truncate, since `date_median`/`date_median_date` and
`burned_around_{1,2,3}` collide. CRS is already EPSG:4326; do not reproject. **One all-years
FeatureCollection is not possible on ingest** — `.shp` caps at 2 GB — so it is 28 uploads; merge
server-side afterwards if one FC is wanted, since `oid` carries the fire-year.

**The ingest is by hand**, because a scripted one needs a GCS bucket and we have none (no billing
account on `mapbiomas-fire-485203`; no `storage.buckets.list` on `mapbiomas-argentina`).
`objects_upload.py` detects the missing bucket and prints the exact dialog values instead of
failing. So: **Code Editor → Assets → NEW → Table upload → Shapefile**, 28 times, watched with
`earthengine task list`.

> **Set max vertices = 1000000 in the dialog, for every year.** Objects routinely exceed it (FY2000
> has one of 2 178 607 vertices, FY2023 one of 1 895 434), and without it the feature can be
> rejected. What GEE does instead is **split the geometry across several features that share one
> `oid`** — see `Gotchas`.

```bash
# build all 28 zips (biggest first, 4 workers, resumable; skips years already built)
tmux new-session -d -s zip07 '/abs/path/to/collection-01/scripts/run_07_upload_zips.sh -j 4'

# pre-upload gate over the 28 zips
tmux new-session -d -s validate '$PYTHON collection-01/scripts/validate_upload_zips.py -j 8'
```

`validate_upload_zips.py` exists because **the upload is by hand, so a bad zip is not caught by a
failing pipeline — it is caught weeks later as a wrong map.** It imports `RENAME` and
`PREDICTOR_NAMES` from `objects_upload.py`, so it validates against what the writer believes it
wrote: flat zip with all components, EPSG:4326, the 28 fields present and `n_mean` absent,
integer-typed code fields, feature count against the prediction CSV, `oid` unique, **the three code
columns never NULL and only ever −1/0/1**, `fire == (fire_tag if fire_tag >= 0 else fire_model)`
feature by feature, no null geometries, max vertices per feature. It exits non-zero on any failure.
The NULL-code check is the one that matters most: it caught a real bug, which is why the −1
sentinel exists in all three columns.

## Key decisions

- **Per-size-band cuts, not 0.5.** The model's confidence rises with object size, and the
  out-of-fold Youden's J cut rises with it — 0.20 / 0.44 / 0.69 — with near-disjoint bootstrap
  intervals between bands. ≥300 ha is swept in two halves but **deployed pooled**, because their J
  values sit inside each other's intervals. Sweep: `notes/06-threshold_sweep.md`.
- **Grid blocks for CV, not regions.** Blocking 0.5° blocks removes the adjacency leak while keeping
  every region in every fold, which is the deployment condition; leave-one-region-out scores a class
  mix that never occurs in production.
- **Five aggregated vegetation fractions, derived by name from the remap.** The 23 raw columns were
  58 % of the design matrix and ate BART's split budget; the aggregation won on every grid-blocked
  metric, with the gain in the weak 1–50 ha band. `notes/06-predictor_selection.md`.
- **Upload the whole object set, all 28 fire-years.** A fire-only layer can only ever show
  commission error; the rejected objects are how a reviewer finds the misses and how the next label
  campaign is aimed. Fire-only would have saved ~33 % of the geometry — not enough.
- **The labelled sample is the binding limitation**, and the fix is a collection task, not a
  modelling one: a **randomly sampled** set of small-object labels (BACKLOG). Until it exists, treat
  the deployed cuts as a lower bound and `p_mean` as a ranking, not a calibrated probability.

## Gotchas

- **`objects_raw_2021` carries 1 249 duplicated features in storage** — byte-identical geometry and
  properties — and **no metadata count reveals them**: `size()` over the plain stored collection is
  answered from metadata, while anything that iterates (an export, a `.map()` in the chain) returns
  them. It came in through the hand ingest. Every consumer must guard; `docs/07` does, with
  `distinct('oid')` in `fires()`. Re-ingesting the year is a BACKLOG item, and until it happens that
  guard is what stands between the asset and every derived product (`docs/07` "`objects_raw_2021` is
  duplicated in storage").
- **`oid` is unique per OBJECT, not per row, in the uploaded FeatureCollections.** The max-vertices
  setting does not subdivide inside one feature: it writes **several features sharing one `oid`**,
  each repeating the whole object's attributes. FY2000's `2000_57529` is 4 rows, the only case in 28
  years — and a naive `aggregate_sum('area_ha')` therefore over-counts by 5.1 Mha. Dissolve by `oid`
  or subtract the split before quoting an area, and **never** repair a duplicate with a blind
  `distinct('oid')` on FY2000 (`docs/07` "`oid` is unique per OBJECT, not per row").
- **`area_ha` is not `n_pixels × 0.09`.** Objects carry lat/lon pixel coordinates (~30 m *at the
  equator*) and area is measured on the ellipsoid, so one pixel is `900·cos(lat)` m² — **831 m² at
  22° S down to 517 m² at 55° S**. A size class is therefore a pixel-count *range* (1 ha = 12 px in
  Formosa, 19 px in Santa Cruz), and the same 15-px object changes class between the north and
  Patagonia.

## Files, directories and scripts

Everything step 06 produces is in the Insync store under `collection-01/data/` (gitignored symlink),
except the tracked threshold config. A **`-cache` suffix means regenerable**: those directories can
be deleted and rebuilt from the CSVs at any time.

| directory | contents | written by |
|---|---|---|
| `data/objects-labels/` | the collected labels ([`06-object_labels.md`](06-object_labels.md)) | `objects_labels_prep.R` |
| `models-store/object_model/` | `bart_object_model.json` (the serialized fit, 92.7 MB) + `_meta.rds` | `06-object_model.R fit` |
| `data/objects-pred/` | `objects_<fy>_pred.csv` (`oid`, `p_*`, `fire_model`, `fire_tag`, `fire`), `objects_<fy>_derived.csv` (the 8 derived predictors, for the upload), `oof_grid_5.csv` | `06-object_model.R predict` / `cv` |
| `config/object_model_thresholds.csv` | **tracked** — the per-size-band fire-call cut | `objects_threshold.R` |
| `data/objects-analysis/` | every reported table/plot: threshold sweep, importance + ALE curves, size distribution, c-00 comparison, upload validation | `objects_threshold.R`, `objects_importance_ale.R`, `objects_data_explore.R`, `validate_upload_zips.py`, the notebook |
| `data/objects-inspect-cache/` | 28 `<fy>_objects_pred.gpkg` QGIS layers (6.3 GB) + `inspect_objects.qgz` | `objects_inspect_export.R` |
| `data/objects-upload-cache/` | 28 `objects_raw_<fy>.zip` — the GEE upload packages (1.3 GB) and their loose Shapefile components | `objects_upload.py` |

| script | role |
|---|---|
| `workflow/06-object_model.R` | the pipeline step: `fit` \| `predict [years\|all]` \| `cv [region\|grid K\|random K]` |
| `scripts/objects_data_functions.R` | **the shared module** — readers, derived predictors, veg groups, `clean_tagged()`, the tag lookup, thresholds, regions, the c-00 filter, `auc_fast`. Everything below sources it, so "the clean labelled table" means the same rows everywhere |
| `scripts/objects_threshold.R` | sweep the out-of-fold probabilities → `config/object_model_thresholds.csv` |
| `scripts/objects_importance_ale.R` | 4 importance measures + 1-D ALE curves → `objects-analysis/` |
| `scripts/objects_data_explore.R` | population size distribution + how the c-00 filter splits it |
| `scripts/objects_inspect_export.R` | join predictions onto geometry → a QGIS GPKG per year ([`06-object_inspection.md`](06-object_inspection.md)) |
| `scripts/objects_upload.py` | build one year's zipped Shapefile (geometry + all predictors + the calls) for GEE |
| `scripts/validate_upload_zips.py` | pre-upload gate over the 28 zips (schema, codes, counts, geometry) |
| `scripts/run_06_predict.sh` / `run_06_inspect.sh` / `run_07_upload_zips.sh` | the three parallel, resumable all-years launchers |

## Related

- [`05-object_metrics.md`](05-object_metrics.md) — the objects and metrics this step consumes.
- [`06-object_labels.md`](06-object_labels.md) — where the ~5 k labels come from and how the
  fitting set is cut.
- [`06-object_inspection.md`](06-object_inspection.md) — reviewing the calls in QGIS (a diagnostic
  tool, not a step): the curated field set, the model-vs-c00 `verdict`, and where to look first.
- [`07-vector_to_raster.md`](07-vector_to_raster.md) — what step 07 does with the `fire` call: the
  month-of-burn raster per **calendar** year, objects placed by their `year_calendar` metric
  (`05` "Metrics"), `candseed == 3` dieback pixels taking the parent object's date
  (`04` "Patagonia dieback padding"), and the object exclusion ruleset that adds the 1 ha minimum.
- `notebooks/objects-analysis.qmd` — the standing analysis: size, uncertainty, the cuts, the
  per-year leak diagnostic, importance/ALE.
- `notes/`: [`06-predictor_selection.md`](notes/06-predictor_selection.md),
  [`06-threshold_sweep.md`](notes/06-threshold_sweep.md),
  [`06-importance_ale.md`](notes/06-importance_ale.md),
  [`06-population_and_size.md`](notes/06-population_and_size.md),
  [`06-c00_baseline.md`](notes/06-c00_baseline.md),
  [`06-upload_decisions.md`](notes/06-upload_decisions.md).
