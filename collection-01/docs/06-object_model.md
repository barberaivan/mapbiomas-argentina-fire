# 06 — Polygons classification using an object-based model

From the vectorized snic objects (step 05) plus their metrics table, we classify which objects
are actually fire, fit/deploy the classifier locally, and upload **only the classified fire
subset** back to GEE.

In this doc "polygon" means a step-05 fire object (often a *multi*polygon — the dilation-bridge
case, 05 §2.3). Its globally-unique key is **`oid = "<fire_year>_<pid>"`** (05 §3); every join —
collected labels ↔ objects, classified fire ids ↔ geometry — is on `oid`.

**Geometry and metrics are split (05 §4):** the per-year GPKG holds `oid` + geometry only; the
metrics live in two CSVs — `objects_<fy>_raster_metrics.csv` and `objects_<fy>_shape_metrics.csv`,
both keyed by `oid`. The model classifies **from the CSVs alone** — no geometry needed until the
final fire-subset upload.

## Data collection

**We do NOT upload the polygons to GEE for data collection.** They are many, heavy, and carry
metrics the collector never looks at (docs/07). Instead, **collect points directly on the step-04
SNIC `candseed` layer** — the SNIC asset per fire-year already exists in GEE and shows, per pixel,
candidate vs. seed on exactly the clusters SNIC kept. **Shape and seed density — the most
informative signal for fire vs. not — are fully visible there without the polygons.** This also
unblocked collection while step-05 vectorization was still running: the objects a collected point
falls in do not change when the pixels are later polygonized, so points taken on the SNIC layer map
cleanly onto objects afterwards (by `oid`, via a local point-in-polygon against the GPKG).

Consequence: **the only geometry ever ingested into GEE is the classified fire subset** (below),
not the full per-year object set.

### Interactive data-collection GEE code

The data collection needs a GEE script replicated across a few users (few enough to coordinate
by hand). It shows the SNIC **`candseed`** band (candidate vs. seed) plus a few of the reference
layers from `explore_snic_IB-02`. **No polygons are loaded** — the collector reads the SNIC
clusters directly (their shape and seed density are what discriminates fire from noise).

- **Year range.** The code exposes a range `(y_lwr, y_upr)` and shows the SNIC `candseed` image for
  each fire-year in it, **coloured differently per year**. In fire-active regions collect over small
  ranges (even one year at a time); in quiet regions a wider range is fine.
- **Points, not polygon metadata.** The user drops geometry points on the SNIC clusters and tags
  each point with the year range. There is **no clicked-polygon metadata panel** at collection time
  (there are no polygons yet) — the panel idea is dropped; per-object metrics are joined **locally,
  afterwards**, by intersecting the collected points with the step-05 GPKG to attach each point's
  `oid`, then joining the metrics CSV on `oid`.
- **Exports (settled 2026-07-27): one asset per collaborator, all their years and both classes.**
  Each user keeps several drawing layers split by **class × year/year-range** — metadata lives at the
  layer level, not per point, so they place many points fast over same-class/-year clusters. The
  **name of the drawing layer IS the metadata**, and section 8 of each `training_polygons_*` script
  parses it:

  | layer name | class | fire-year(s) |
  |---|---|---|
  | `fire_YYYY` | 1 | `YYYY` |
  | `nonfire_YYYY` | 0 | `YYYY` |
  | `fire_YYYY_poly` / `nonfire_YYYY_poly` | as above | as above — `_poly` just records that polygons were drawn instead of points |
  | `fire_YYYY_YYYY` (range) | 1 | **both ends inclusive** — the feature is written **once per year** in the range, so every row carries one concrete `fire_year` |

  Anything **not** named `fire_*` / `nonfire_*` is ignored on purpose: the ROIs, bare `geometry*`,
  the doubtful layers (`dudas2014`, `dudoso_2015`, `dudoso_2017`), `ejemplo_*`, and imported vis
  params. To promote a doubtful layer to training data, **rename** it to the convention.

  One `Export.table.toAsset` per script writes
  `…/TRAINING-DATA/POLYGONS-DATA/polygons_data_<author>` (author lowercase), which is then
  **downloaded straight from the asset page** — no per-year merge step. Schema: `class` (1/0),
  `fire_year`, `y_lwr`/`y_upr` (the declared range), `geom_type` (`Point`/`Polygon`, read off the
  geometry, not the name), `author`, `src` (the drawing layer it came from, so a suspect feature
  traces back). **Points and polygons share one table**; both are intersected against the
  fire-year's objects downstream. Geometry-flavour drawing layers (all items fused into one
  `MultiPoint`/`MultiPolygon`) are exploded with `geometries()` into one feature per drawn item, so
  both Code-Editor import flavours behave identically. An unparseable name **throws** rather than
  being silently dropped. Registry upkeep: adding a drawing layer = adding one
  `[fire_2021, 'fire_2021']` line.

### Why the SNIC layer, not the polygons (record)

El snic-vectorización-métricas y tal está tomando mucho más de lo que esperaba, no llego a tener los polígonos con métricas para mañana. PEEERO ya están exportadas a asset las imágens por año con el resultado del SNIC, en donde dice si cada pixel fue candidato o seed, sólo sobre clusters que el snic mantuvo. Entonces podemos empezar a tomar datos sobre esa capa. Más lento quizás, sin poder ver las métricas a nivel de polígono, pero igual la forma y la densidad de semillas es lo más informativo. Así que podemos largar la toma de datos aunque aún no tengamos los polígonos con metadata. Porque al poligonizar, no va a cambiar con qué polígonos intersectan esos puntos. Así que estamos atrasados pero quizás no sea tan grave.
Ya le pedí a algunos que destinen jueves-viernes a tomar datos, por eso era un moco el atraso.

*(This started as a stop-gap for the vectorization delay; it is now the chosen approach — docs/07.)*

### Label prep — `scripts/polygons_data_prep.R` (download + intersect + join)

One script, two stages, either runnable alone:
`Rscript collection-01/scripts/polygons_data_prep.R [all|download|merge] [--force] [author…]`

**Download** — one asset → **one GeoPackage** in `data/polygons_data/polygons_data_<author>.gpkg`
(rgee, `getDownloadURL("GeoJSON")`; existing files skipped unless `--force`). A file per asset so a
collaborator who adds points and re-exports costs one re-download, not seven. **GPKG, not
shapefile**: the labels mix points and polygons in one table (a shapefile cannot), field names
survive intact, and step 05 already writes GPKG. `merge` always reads *every* file present, so the
merged table stays complete after a single-author refresh.

**Merge** — each label is matched to the step-05 objects **of its own fire-year** and the object's
metrics are attached → `data/polygons_data/polygons_data_merged.csv`, one row per (label, object)
pair. Both files live under `collection-01/data/`, i.e. in the Insync store, not git.

*Matching, and why it is shaped this way.* A year is ~78 k objects / ~330 MB and only a handful are
ever hit, so a year is never read whole: labels are grouped into 1° blocks, each block is read back
through the **GeoPackage R-tree** (`terra::vect(extent=)`), and the exact predicate runs on that
small subset. Two measured findings worth keeping:

- **`terra::relate(…, "intersects")`, not `sf::st_intersects`.** The 1-px dilation can weld a whole
  fire season into one object — `1999_24193` is **13 053 parts / 643 742 vertices**. `st_intersects`
  degrades pathologically there: **one point against that object costs ~55 s** (identical with
  `prepared = TRUE/FALSE` and with the arguments swapped), which alone made FY 1999 take 176 s and
  the full run > 30 min. `terra::relate` answers the same block in 1.6 s (0.04 s for that object)
  and returns **pair-for-pair identical** results — verified against sf on every FY 1999 block.
  Whole merge: **27 s**.
- **Never `st_cast` the labels to POINT** to satisfy terra's one-geometry-type-per-SpatVector rule.
  A polygon label collapses to its first vertex and silently loses its objects (a 1999 polygon label
  went from 131 objects to 4). The script splits POINT vs POLYGON per block instead.

*Nothing is dropped; problems are flagged* — `n_objects` (0 = the label hit no object, >1 = a drawn
polygon), `oid_n_labels`, `oid_class_conflict` (object labelled both fire and non-fire). The model
step decides. First full run (2026-07-27, 4643 labels from 7 collaborators, 21 fire-years):
**6597 pairs over 5266 objects** (2788 fire / 2468 non-fire after dropping conflicts), **234 labels
(5 %) hit no object** — a point drawn where SNIC kept no cluster, so there is nothing to classify —
**10 objects carry both classes**, and labels are **very unevenly spread over objects** (up to 40
labels on one object; jime's 340 labels land on 21 objects). Expect to dedupe/weight by `oid`
before fitting. One matched object (`2011_57456`, 1 px) has NA `seed_mean`/`date_median` in step
05 itself — all-dieback objects have no seed/date stats by design (docs/05 §3), not a join failure.

## The fitting set

`clean_tagged()` in `scripts/objects_data_functions.R` turns the 6831 label↔object pairs into one
row per OBJECT, reporting every cut: −234 rows whose label hit no object, −10 objects labelled both
classes, −1315 duplicate labels on an already-labelled object, −1 object with an NA predictor
(`2011_57456`) → **5255 objects, 2788 fire / 2467 non-fire**, 22 predictors.

Uneven label density per object is deliberately **not** corrected — a label is a label, and
reweighting by it would invent information.
## The model

**Probit BART, fitted with [`stochtree`](https://cran.r-project.org/package=stochtree) 0.4.5 in R**,
on the 22 predictors, locally — no geometry is needed to classify (the two per-year CSVs joined on
`oid` are enough), and no GEE round-trip. `workflow/06-object_model.R`, modes `fit`,
`predict [years|all]`, `cv [region|grid K|random K]`.

Why BART rather than a boosted ensemble, in one line each: with ~5 k labels there is **no honest way
to tune hyperparameters**, and BART's defaults are calibrated regularization priors rather than
placeholders; and the posterior yields a **per-object interval**, which is both an uncertainty
statement we can publish and the targeting signal for a round-2 collection. `stochtree` specifically
because its `num_threads` parallelises the GFR sampler and the MCMC *within* a chain, which is real
wall-clock scaling of the fit.

### As fitted (2026-07-27)

`OutcomeModel(outcome = "binary", link = "probit")`, `num_gfr = 10`, `num_mcmc = 500` with
`keep_every = 4` — i.e. **2000 MCMC iterations thinned to 500 retained draws** (`num_mcmc` is the
*retained* count; stochtree runs `num_mcmc * keep_every`). `num_threads = 8` = **physical** cores:
tree sampling is memory-bandwidth-bound, so the 8 extra hyperthreads mostly add contention. If you
ever see `num_threads` fall back to 1 on Linux/gcc, the build has no OpenMP.

Thinning is what makes prediction affordable — cost is linear in draws, and 500 draws still put ~25
order statistics below `p_q05`, so 2000 retained draws would have cost 4× the prediction time and 4×
the memory for no gain in a 5th percentile.

| step | measured |
|---|---|
| fit (5255 × 22, 2000 iter → 500 draws, 8 threads) | **94 s** |
| serialized fit (JSON) | 92.7 MB, reloads in ~4 s |
| predict FY 2020 — 78 211 objects × 500 draws | **102 s** = 769 obj/s = 2.6 µs/obj/draw |
| **all 28 fire-years / 1 689 383 objects** | **4m33s** on 8 parallel workers (~37 min in one process) |
| out-of-fold AUC | **0.92** grid-blocked (0.98 random, 0.74 leave-one-region-out) |

**Scoring every object across posterior draws is not a problem** — but only in the right shape.
Never pass the full object set as `X_test` to `bart()`: 1.69 M × 500 doubles ≈ **6.8 GB**. Instead
**fit → serialize to JSON → `predict()` per fire-year in `PRED_CHUNK` blocks → reduce each block to
its summaries and discard the draws**, so peak memory is one block (20 k × 500 ≈ 80 MB) regardless
of how many objects exist.

**Prediction is single-threaded** (measured): `num_threads` is a *sampler* setting, and
`predict.bartmodel` takes no thread argument — nor do the C++ predict entry points
(`predict_forest_cpp` and friends). One process pegs one core with its OpenMP threads idle. The
years are independent, so the parallelism goes at the **process** level: `scripts/run_06_predict.sh`
runs one `Rscript` per fire-year, 8 at a time, biggest years first, resumable. Each worker
deserializes the 92.7 MB JSON itself (~1.4 GB RSS), so budget ~1.4 GB × workers.

### The 22 predictors

17 non-vegetation metrics — `n_pixels`, `area_ha`, `burned_around_{1,2,3}`, `seed_mean`, `n_mean`,
`doy_median`, `date_span`, `year_calendar`, `fire_year`, `perimeter_m`, `convexity`, `mbr_fill`,
`mbr_elongation`, `circularity`, `shape_index` — plus **five aggregated vegetation fractions**:

| column | veg_fire classes |
|---|---|
| `frac_agri` | 1 agriculture_chaco, 2 agriculture_cuyo-pat, 3 agriculture_pampa — **not** 4 agriculture-per |
| `frac_grass_inund` | 17 grassland-inund_chaco |
| `frac_pasture` | 18 pasture_ba, 19 pasture_chaco |
| `frac_grass_temp` | 12 grassland_ba, 13 grassland_chaco, 15 grassland_pampa — **not** cuyo/patagonia |
| `frac_woody` | 5,6,7,8,9,11 forests + 20,21,22,23 shrublands — **not** 10 forest-inund |
| *(no group)* | 4 agriculture-per, 10 forest-inund, 14 grassland_cuyo, 16 grassland_pat |

Membership is derived from `config/veg_fire_remap.csv` **by name**
(`objects_data_functions.R::veg_groups`), not from typed-in codes, so a remap change follows through
— and a code landing in two groups is an error, not a silent reshuffle. The groups are deliberately
**not** region-separated and **not a partition**: the five sum to 0.70 on average, never above 1.

These five replaced the 23 raw `frac_c1..frac_c23` fractions after a direct comparison on the same
5255 objects and the same folds: **the aggregated version won on every grid-blocked metric** (AUC
0.902 → 0.921, accuracy 0.786 → 0.812), with the gain landing where the error was — the 1–50 ha band
(61 % of all objects) went 0.872 → 0.903 AUC. The reason is **split budget**: 23 sparse columns were
58 % of the design matrix and BART draws split variables uniformly over what is available, so merging
them concentrates the same signal into 5 dense columns. (Leave-one-region-out was a wash, 0.750 →
0.741 — the gain is not about region-agnosticism.) The raw fractions are kept in the step-05 metrics
and summed at load time; only the 5 sums enter the model.

### What comes out per object

`p_mean`, `p_sd`, `p_q05`, `p_q95` and **`p_width = p_q95 − p_q05`** precomputed, plus the `fire`
call from the size-band threshold. The semantics matter: these bound the **probability** — epistemic
uncertainty about the fitted function — *not* the class label. A predictive interval for a Bernoulli
draw would be 0/1 and useless. Wide `p_width` = the model does not know = where a round-2 collection
should go.

The classified objects yield the set of fire `oid`s, and **only that subset is uploaded** — we do
not upload a full-year asset and filter it in GEE.

### Threshold: 0.5 is wrong, and the right cut RISES with object size

`scripts/objects_threshold.R` sweeps every cut on the **out-of-fold** probabilities
(`oof_grid_5.csv` — never in-sample, or the cut would be chosen against answers the model
already saw) and reports four criteria. **Youden's J (sens + spec − 1) is the headline** because it
is the only one here that does not move with prevalence, and our labelled set is not a random sample
of objects. F1 and accuracy are reported but drift with that same sampling bias; `J_area` weights
each object by `area_ha` (the deliverable is an area product) but a handful of huge objects dominate
its weights.

| stratum | n | Youden cut | sens | spec | J | J at 0.5 | bootstrap 5–95 % |
|---|---|---|---|---|---|---|---|
| < 1 ha | 114 | 0.233 | 1.000 | 0.953 | 0.953 | 0.609 | 0.233–0.340 |
| **1–50 ha** | 3217 | **0.180** | 0.855 | 0.791 | 0.646 | 0.530 | 0.111–0.236 |
| **50–300 ha** | 1192 | **0.405** | 0.878 | 0.834 | 0.712 | 0.695 | 0.336–0.476 |
| 300–1000 ha | 399 | 0.562 | 0.893 | 0.850 | 0.743 | 0.710 | 0.496–0.851 |
| ≥ 1000 ha | 333 | 0.579 | 0.948 | 0.909 | 0.857 | 0.834 | 0.500–0.772 |
| **≥ 300 ha** (pooled, deployed) | 732 | **0.598** | 0.910 | 0.880 | 0.789 | 0.763 | 0.520–0.657 |
| ≥ 1 ha (pooled) | 5141 | 0.274 | 0.860 | 0.815 | 0.675 | 0.633 | 0.232–0.326 |
| all (pooled) | 5255 | 0.274 | 0.861 | 0.820 | 0.681 | 0.635 | 0.231–0.298 |

**The cut rises with size — 0.18 → 0.41 → 0.60 — and it flattens above 300 ha.** For 1–50 vs
50–300 vs ≥300 the bootstrap intervals are near-disjoint, so those differences are signal, not
resampling noise: the model is far more confident on big objects, and a single threshold would be
simultaneously too high for small objects and too low for large ones. The gain is concentrated where
the error was — in 1–50 ha, J 0.530 → 0.646 and sensitivity 0.610 → 0.855. Above 300 ha the 0.5
default was already nearly right (0.763 vs 0.789).

**Splitting ≥300 ha in two buys nothing**, which is why it is *reported* above but **deployed
pooled**: 300–1000 gives 0.562 and ≥1000 gives 0.579, with bootstrap intervals that almost coincide
(0.496–0.851 and 0.500–0.772). Same evidence standard that justified the other bands says these two
are one band; deploying them separately would add a knob that can only overfit. Hence
`DEPLOY_BANDS` ≠ `SIZE_BANDS` in the script, and the config carries four rows. `band_lower()`
(`objects_data_functions.R`) parses each band's lower bound out of its own label, so the config can
gain or lose bands without any code knowing their names.

Picks are written to **`config/object_model_thresholds.csv`** (tracked) and applied by
`06-object_model.R predict`, which adds a `fire` 0/1 column and logs the rule it used; with the file
absent it falls back to 0.5 and says so. The `< 1 ha` row is recorded for completeness but should
not be leaned on — 114 objects, 29 of them fire, and that whole stratum is 3.4 % of objects for
0.044 % of area, so the **hard size cut, not a threshold, is the right tool there**.

**The threshold governs object COUNTS, not the area headline.** Against the labelled objects' own
burned area (2387.6 kha), `p > 0.5` gives 2350.8 kha, the global Youden cut 2437.8 kha and the
per-band cuts 2330.8 kha — all within ±2.5 %, while the object count moves 2266 → 2895. Same story
on the full FY 2020: the band cuts call 69 049 objects fire (4350 kha) where 0.5 called 53 654
(4326 kha) — **+15 395 objects for +24 kha**. Area is dominated by large objects the model is
confident about, so lowering the cut is cheap in area and expensive only in small-object commission.

**The caveat that limits all of this.** Youden's J is prevalence-invariant *as a measure*, but the
threshold it selects is optimal for the prevalence of the set it was chosen on — and our labels are
not a random sample. In the 1–50 ha band labelled prevalence is 0.47, whereas most of the 1.4 M real
objects in that band are presumably noise. Applied to FY 2020 the band cuts call **83–90 % of
objects fire in every band**, which is implausible as a population rate; note that even at 0.5 the
model calls 67 % of 1–50 ha objects fire, so this is the *label sampling*, not the threshold. What
would settle it is a **randomly sampled** set of small-object labels — a collection task, not a
modelling one (BACKLOG). Until then, treat 0.18 as the lower bound of a defensible range for the
1–50 ha cut and expect to raise it once a random sample exists.

### Cross-validation: the fold design decides the answer

Three designs, same model, same 5255 objects. `Rscript …/06-object_model.R cv [region|grid K|random K]`;
out-of-fold predictions land in `data/objects-predictions/oof_<spec>.csv`.

| fold design | AUC | accuracy | sens | spec | what it measures |
|---|---|---|---|---|---|
| random 5-fold | 0.976 | 0.922 | 0.934 | 0.909 | **leak-inflated** — adjacent objects from one drawn polygon straddle folds |
| **0.5° blocks → 5 folds** (349 blocks) | **0.902** | 0.786 | 0.687 | 0.899 | **the deployment number** — no adjacency leak, every region still in every fold |
| leave-one-region-out (5 MapBiomas regions, 2 km buffered) | 0.750 | 0.671 | 0.716 | 0.621 | transfer to an **unseen ecoregion** — a condition production never faces |

Read the middle row. Leave-one-region-out is the harshest possible test and not the deployment
condition: every region *does* have labels in production, and held-out prevalence swings 0.10
(Patagonia) to 0.83 (Pampas), so a fold's model is trained on a different class mix than it is
scored on. Per region: Puna 0.970 (n = 79), Bosque Atlántico 0.839, Chaco 0.773, Patagonia 0.773,
Pampas 0.700.

**Where the error lives** — out-of-fold, by size (grid-blocked / leave-one-region-out AUC):

| stratum | share of all objects | AUC grid | AUC region | sens@0.5 grid |
|---|---|---|---|---|
| < 1 ha (n = 114 labels) | 3.4 % | 0.974 | 0.568 | 0.62 |
| 1–50 ha (n = 3217) | 61 % | **0.872** | **0.695** | **0.53** |
| 50–300 ha (n = 1192) | 11 % | 0.921 | 0.807 | 0.82 |
| ≥ 300 ha (n = 732) | 1.8 % | 0.956 | 0.831 | 0.94 |

So the weak band is **1–50 ha**, which is also where 61 % of the objects are: grid-blocked AUC 0.87
and only **0.53 sensitivity at the 0.5 cut** — it misses about half the real fires there. Above
300 ha the model is nearly clean. The `< 1 ha` row differs wildly between designs for a data reason,
not a model reason: 86 of its 114 labels are in Patagonia, so leave-one-region-out leaves that
stratum with no comparable training data at all.

Two consequences, both in the BACKLOG: the 0.5 threshold is in the wrong place for a burned-area
product (specificity 0.90 vs sensitivity 0.69 — pick the cut on the OOF file), and round-2 label
collection should target 1–50 ha objects with wide `p_width`.

**And one caveat that no fold design fixes.**
**The labelled sample is not a random sample of objects**, and per-year prevalence swings from
   0.00 (2009, 2016) to 1.00 (1998) — 2020 alone contributes 1647 labels at 88 % fire. Treat the
   *ranking* and the *uncertainty* as the product; do not read `p_mean` as a calibrated absolute
   probability. On FY 2020 the model calls 67.7 % of objects fire (4401 of 4841 kha) where the
   collection-00 filter keeps 22.9 % (4045 kha) — the two agree on almost all of the *area* and
   disagree almost entirely on small objects (38 246 objects the filter rejects and the model keeps
   are 558 kha in total).

### Looking at it on a map without uploading to GEE

A full-year GEE ingest is ~8 h by hand (no GCS bucket — see "Uploading the classified fire subset"),
which is not a price worth paying to *inspect* a model. `scripts/objects_inspect_export.R` joins the
predictions + the object metrics + the c-00 verdict onto the step-05 geometry already on disk:

- **`<fy>_objects_pred.gpkg`** — every object of the year, **33 curated fields** (see below). Open
  in QGIS, graduate the fill on `p_mean` (or `p_width`), add an XYZ imagery basemap, and use the
  attribute table and filter expressions to walk cases. FY 2020: **353 MB written in 6 s**, and
  QGIS pans it smoothly off the GPKG spatial index. This is the fastest route to eyes-on and needs
  nothing new built.
- **`<fy>_objects_sample.geojson`** — a stratified sample (default 20 objects per `p_mean` decile,
  geometry simplified to ~30 m; FY 2020 → 200 objects, 1.6 MB). This is the answer to "is there a
  geemap midpoint": **yes.** geemap/leafmap is an ipyleaflet map — `Map.add_geojson(path)` /
  `add_gdf()` puts local vectors on it as **client-side** layers while GEE imagery (candseed,
  Landsat min-NBR, the bpts composite) renders as server-side tiles beside them. Nothing is
  uploaded to Earth Engine. The binding constraint is the **browser**, not GEE: keep client-side
  features in the low thousands, which is exactly what a decile-stratified sample gives you.

**All 28 years are built** by `scripts/run_06_inspect.sh` (parallel, one `Rscript` per year,
resumable, biggest-first, RAM monitor alongside): **1m4s on 6 workers, 6.3 GB, peak 16.2 GB RSS**,
28 GPKGs + 28 GeoJSON samples, feature counts summing to exactly 1 689 419. Unlike prediction this
is I/O- and memory-bound (a worker holds a whole year's geometry — up to 386 MB / 93 k
multipolygons), hence `-j 6` rather than 8.

> **QGIS gotcha:** the layer name starts with a digit (`2020_objects_pred`), so any SQL
> context — DB Manager, virtual layers, `ogrinfo -sql` — needs it **double-quoted**. Symbology and
> attribute-table filters are unaffected.

#### The inspection field set (33 fields)

The 23 raw `frac_c*` columns are **not** model predictors (they are summed into the 5 groups) and 28
years of them is dead weight in a table read by eye, so the GPKG carries a curated set ordered the way
a row is read — what it is, what we decided, why, then the evidence. `--fields all` restores
everything for one year.

| group | fields |
|---|---|
| identity & size | `oid`, `fire_year`, `area_ha`, `n_pixels`, `size_class` |
| the two verdicts | `fire` (model), `c00_pass` (collection-00 filter), `verdict` |
| why the model said it | `p_mean`, `p_width`, `p_thresh`, `p_margin`, `th_band`, `c00_case` |
| burn evidence & timing | `seed_mean`, `n_mean`, `burned_around_{1,2,3}`, `doy_median`, `date_span`, `date_median_date` |
| aggregated vegetation | `frac_agri`, `frac_grass_inund`, `frac_pasture`, `frac_grass_temp`, `frac_woody` |
| shape | `perimeter_m`, `convexity`, `mbr_fill`, `mbr_elongation`, `circularity`, `shape_index` |

Four fields do not come from step 05 and are the reason this is worth a script rather than a join:

- **`p_thresh` / `p_margin` / `th_band`** — the cut that applied to *this* object's size band and the
  signed distance to it. A verdict without its threshold is unreadable when the threshold varies by
  size; `abs("p_margin") < 0.05` is the filter that finds the calls actually worth eyeballing.
  `apply_thresholds()` (shared) recomputes them and **cross-checks against the stored `fire`**, so a
  thresholds-file edit after a prediction run is reported instead of silently making the map lie.
- **`verdict`** — one categorical (`both` / `model only` / `c00 only` / `neither` / `unscored`) so
  "where do the model and the old empirical filter part ways" is a single symbology. On FY 2020 they
  disagree on **69.7 %** of objects (model 88.3 % fire vs filter 22.9 %), so this is the main map.

Note `size_class` (6 display classes) is deliberately finer than `th_band` (4 threshold bands): a row
can be display class `>=1000 ha` while its call came from band `>=300 ha`. The display breaks split
1 ha into `<0.5` / `0.5-1` because that is where the minimum-size decision lives.

#### How to actually inspect it — where to look first

Across all 28 fire-years the model and the collection-00 filter **disagree on 27 % of the object
area**, and the disagreement is cleanly structured — `c00 only` is *large* objects, `model only` is
*small* ones:

| verdict | objects | area (kha) | mean ha | mean `p_width` | % of area |
|---|---|---|---|---|---|
| both | 292 869 | 55 892 | 191 | 0.427 | 65.8 |
| **c00 only** (filter keeps, model rejects) | 108 818 | 12 621 | 116 | 0.320 | 14.8 |
| **model only** (model keeps, filter rejects) | 860 018 | 10 304 | 12 | 0.511 | 12.1 |
| neither | 427 678 | 6 174 | 14 | 0.237 | 7.3 |

**Start with `"verdict" = 'c00 only' AND "area_ha" >= 300`.** That is **6477 objects holding 6785 kha
— 8 % of all object area** — where the old filter auto-accepts under its `>= 300 ha` rule and the
model rejects *without confidence* (mean `p_mean` 0.30, mean `p_width` 0.56). It is the
highest-area-stakes set in the collection and small enough to walk object by object, and at `>= 300 ha`
each one is unmistakable against imagery. Whatever is decided there moves the headline number more
than anything else in step 06.

By contrast `model only` below 1 ha is **29 421 objects for 21 kha** — 0.02 % of area. Worth a glance
to see *what* they are, but not worth arguing about.

The filters this field set exists for:

| expression | what it shows |
|---|---|
| `"verdict" != 'both'` | every disagreement with the collection-00 filter |
| `"verdict" = 'c00 only' AND "area_ha" >= 300` | **the set to review first** (see above) |
| `abs("p_margin") < 0.05` | borderline calls — objects that would flip under a small threshold change |
| `"p_width" > 0.5` | where the model has no idea; also the round-2 collection targets |
| `"size_class" IN ('<0.5 ha','0.5-1 ha')` | the minimum-size decision |
| `"th_band" = '1-50 ha' AND "fire" = 1` | the weakest band's positives (61 % of all objects) |
| `"seed_mean" < 0.1 AND "fire" = 1` | fire calls with little seed support — the most suspicious positives |

Suggested setup: categorise the fill on `verdict` (4 colours), add an XYZ satellite basemap, and keep
`p_mean`, `p_width`, `p_margin`, `area_ha` and `seed_mean` visible in the attribute form. Then sort the
attribute table by `p_margin` to walk from the most borderline call outwards. The companion
`<fy>_objects_sample.geojson` (200 objects, decile-stratified) is the same thing for a geemap/leafmap
notebook when you want GEE imagery — `candseed`, min-NBR — under the polygons instead of a basemap.

That covers Lican's suggestion without a Shiny app: the sampling-by-predictor-range panel is a QGIS
filter expression or a geemap cell. Build the Shiny app only if a *shared* review tool is wanted —
for one analyst it adds a UI to maintain and no capability QGIS lacks. A whole-country raster
overview is the other option not taken: rasterizing `p_mean` at 30 m country-wide is 9.16 B cells
(docs/05 §7), so it would have to be coarsened to ~300 m, which erases the small objects that are
precisely the ones in doubt.

## Whole-population uncertainty — and why it does not decide the minimum size

`notebooks/object_size_distribution.qmd` scores all **1 689 383** objects (28 fire-years; 36 unscored,
NA predictors) and asks the question the minimum-size decision was supposed to rest on: *is the model
measurably less able to classify small objects?* `% undecided` = the `p_q05`-`p_q95` interval straddles
the cut that applies to that object, i.e. the posterior cannot place it on either side.

| display class | objects | area (kha) | cut | median `p_mean` | mean `p_width` | % called fire | % undecided |
|---|---|---|---|---|---|---|---|
| < 0.5 ha | 15 070 | 4.0 | 0.233 | 0.092 | 0.395 | 26.3 | 58.8 |
| 0.5–1 ha | 42 514 | 33.5 | 0.233 | 0.352 | 0.476 | 59.9 | 58.3 |
| 1–50 ha | 1 409 244 | 16 787 | 0.180 | 0.415 | 0.418 | 69.4 | 46.6 |
| 50–300 ha | 192 380 | 20 465 | 0.405 | 0.613 | 0.399 | 63.1 | 42.5 |
| 300–1000 ha | 22 791 | 11 534 | 0.598 | 0.894 | 0.329 | 75.5 | 36.8 |
| ≥ 1000 ha | 7 384 | 36 167 | 0.598 | 0.968 | 0.235 | 88.1 | 24.0 |
| **all** | **1 689 383** | **84 991** | — | 0.438 | **0.415** | 68.2 | **46.3** |

**The answer is no — or rather, not distinctively.** Uncertainty does fall monotonically with size
(width 0.476 → 0.235, undecided 58 % → 24 %), which is the expected direction, but the model is
**unsure everywhere**: a mean `p_width` of 0.415 means the average 5–95 % interval spans 41 points of
probability, and even the ≥1000 ha class cannot place a quarter of its objects on one side of its cut.
A minimum-size cut therefore removes objects that are *somewhat* worse than average, not objects that
are qualitatively unclassifiable:

| cut | objects dropped | area dropped | dropped: width / undecided | kept: width / undecided |
|---|---|---|---|---|
| 0.5 ha | 0.89 % | 0.005 % | 0.395 / 58.8 % | 0.415 / 46.2 % |
| 1 ha | 3.41 % | **0.044 %** | 0.455 / 58.4 % | 0.413 / 45.8 % |
| 2 ha | 12.6 % | 0.321 % | 0.454 / 54.0 % | 0.409 / 45.1 % |
| 5 ha | 34.0 % | 1.749 % | 0.435 / 50.6 % | 0.405 / 44.1 % |

So **the honest argument for a 1 ha minimum is cost/benefit, not uncertainty**: 3.4 % of objects for
0.044 % of area, i.e. a large reduction in count and noise for a rounding error in the headline
number. Do not claim the model "cannot classify" sub-hectare objects — it classifies them the same way
it classifies everything, only with slightly wider intervals, and it does push them toward non-fire
(median `p_mean` 0.092 in `<0.5 ha` vs 0.968 in `>=1000 ha`, so the discrimination is real).

**What the width actually indicates is covariate shift.** 5255 labels against 1.69 M objects, collected
where fires were known rather than sampled from the object population — BART widens its posterior
exactly where it has no data, and 46 % undecided is that message. This reinforces, from the population
side, the caveat the threshold work reached from the label side: the binding limitation is the
labelled sample, not the model or the cut. Combined with 68.2 % of objects / 66.2 of 85.0 Mha called
fire, the deployed thresholds should be treated as a lower bound on the cuts, not as calibrated.

### Also measured: the pixel scale is latitude-dependent

`area_ha` is **not** `n_pixels * 0.09`. Objects carry lat/lon pixel coordinates (~30 m *at the equator*)
and area is measured on the ellipsoid, so one pixel is `900*cos(lat)` m² — **831 m² at 22° S down to
517 m² at 55° S** (median 778). Harmless, but two consequences: a size class is a pixel-count *range*
(1 ha = 12 px in Formosa, 19 px in Santa Cruz), and the same 15-px object changes class between the
north and Patagonia. Also visible there: the `n_pixels` count **dips** from 3796 one-pixel objects to
778 at five, then climbs monotonically (6 px → 3081 … 20 px → 12 474). A segmentation floor would give
a hard cut, not a dip-then-rise, so something is producing isolated 1–2 px objects that 3–5 px does not
get — the step-05 1-px dilation connectivity hack is the suspect. Small in area either way; worth a
QGIS look.

## What the data says about size limits and the collection-00 filter

From `scripts/objects_data_explore.R` (both tables, 2026-07-27). **FULL = 1 689 419 objects over 28
fire-years, 84.99 Mha**; median object 9 ha, p99 494 ha, largest 1.71 Mha (`2000_57529`).

**A small-object cut is nearly free.** Objects below a cut, as a share of count vs of area:

| cut | objects dropped | area dropped |
|---|---|---|
| < 1 ha | 3.4 % (57 619) | **0.044 %** |
| < 2 ha | 12.6 % | 0.32 % |
| < 5 ha | 34.0 % | 1.75 % |
| < 10 ha | 52.8 % | 4.45 % |

So the `< 1 ha` cut of docs/06 costs essentially nothing and removes 58 k objects from the ingest;
even 5 ha stays under 2 % of area. Size alone, though, does **not** separate the classes: in the
labelled data P(fire) is 0.44–0.50 flat across 1–100 ha, rising only to 0.75/0.80 above 300/1000 ha,
and `area_ha >= 1` on its own has specificity 0.03 (it keeps everything).

**The collection-00 filter transfers badly to collection 1.** Reproduced verbatim in
`objects_data_functions.R::c00_pass`; against the 5255 labels: **accuracy 0.62, sensitivity 0.50,
specificity 0.77, precision 0.70** (vs 0.92 / 0.93 / 0.91 for BART out-of-fold). Where it breaks:

- **Case 1 (1–50 ha) has sensitivity 0.19** — it discards 81 % of the real fires in the band that
  holds 61 % of all objects. One threshold does nearly all of that damage: `burned_around_3 > 0.7`
  cuts **81 % of the FIRE objects** there (and 90 % of the non-fire) — in collection 1 that band's
  fire objects sit at a median `burned_around_3` of 0.58, well below the cut.
- **Case 3 (≥ 300 ha auto-accept) has precision 0.77** — 166 of 732 labelled objects above 300 ha
  are non-fire, so "very large is rarely non-fire" does not hold here. Those 30 175 objects supply
  **69.6 % of all the area the filter keeps**, so the assumption is load-bearing.
- `circularity > 0.01` is **inert** (cuts 0.0 % of fire, 0.4 % of non-fire); `shape_index < 7` is the
  one term working as intended (cuts 20 % of fire vs 48 % of non-fire in case 2).
- On the full table it keeps **23.8 % of objects / 80.6 % of the area**, stable across years
  (18–27 % of objects).

Conclusion: keep the filter only as a **baseline to compare against**, and as the source of the two
ideas worth keeping — the hard small-object cut, and size-stratified reasoning. The model replaces
the thresholds.

## Uploading the classified fire subset

This is the **only geometry ingest** into GEE. Take the fire `oid`s from the local classification,
subset the per-year step-05 GPKG(s) to those objects, attach whatever metadata we want the
unofficial vector database (FC) to carry, and upload — per fire-year, into an `.../objects/` folder.

- **Format — convert, don't upload the GPKG.** GEE table ingestion does not read GeoPackage; it
  accepts zipped **Shapefile**, **CSV** (geometry as a WKT column), **GeoJSON/NDJSON**, TFRecord.
  **Prefer GeoJSON** (preserves field names + types, one-line write from the `sf` object:
  `sf::st_write(fire_polys, "fire_<fy>.geojson")`) or CSV-with-WKT. Avoid Shapefile — it truncates
  field names to 10 chars (`burned_around_1`, `date_median_date`, … collide) and caps at 2 GB / 255
  fields. CRS is already **EPSG:4326** (GEE-native) — do not reproject.
- **Transport + ingest — the CLI cannot take a local file.** `earthengine upload table` rejects any
  source without a `gs://` prefix (`ee/cli/commands.py:_check_valid_files`), and the client library
  exposes **no** upload-URL helper (the legacy `getTableUploadUrl()` is gone from `ee.data`; the
  Code Editor stages through a browser-internal endpoint with no public equivalent). So a scripted
  ingest needs a **GCS bucket**, and as of 2026-07 we have none:
  `mapbiomas-fire-485203` has **no billing account** (bucket creation → `403 … billing account …
  disabled in state absent`) and neither GEE account has `storage.buckets.list` on
  `mapbiomas-argentina`. Until one of those is fixed, ingest **by hand**: Code Editor → Assets →
  NEW → Table upload → Shapefile. Watch with `earthengine task list`. Assets live under
  **`projects/mapbiomas-argentina`**. Keep `oid` as a property — the join key for the month-of-burn
  build (rasterization, below).
- **Very large geometries.** Set **max vertices = 1000000** on ingest. Objects routinely exceed it
  (2000 has one of 2,178,607 vertices); GEE subdivides the geometry *inside* the feature, so `oid`
  and the properties survive. Without it the feature can be rejected.

### Inspection upload — the full (unclassified) object set

Separately from the fire-subset upload above, `collection-01/scripts/polygons_upload.py` packages **one whole
fire-year — every object, all 42 predictors** — for on-map comparison of candidate filters (see
docs/07 for why this is exploration-only and not the production route). Geometry is the entire
cost, since the step-05 GPKGs carry no attributes, so **zipped Shapefile, not GeoJSON**: measured
on 2000, 373 MB GPKG → **73 MB zip in ~30 s** (the same year is ~880 MB as GeoJSON). Field names
are renamed by hand to ≤10 chars in the script's `RENAME` map — never let OGR auto-truncate, since
`date_median`/`date_median_date` and `burned_around_{1,2,3}` collide. Whole-country estimate for
all 28 years: **~1 GB zipped**. Ingest is the slow part, not packaging — minutes per year.

Assets go to `.../WORKFLOW-EXPORTS/polygons_raw/polygons_raw_<fy>`.

## Rasterization

Step 07 (see docs/07). The official MapBiomas layer is a raster of **month-of-burn per calendar
year**, built server-side by combining the **uploaded fire polygons** with the **SNIC metrics
images**. Objects are placed into a calendar year by their `year_calendar` metric (05 §2.4);
`candseed==3` dieback pixels take the parent object's date, never their own next-year date (04
§4.3). In parallel we keep the **unofficial vector FC** — the uploaded fire polygons with metadata.
