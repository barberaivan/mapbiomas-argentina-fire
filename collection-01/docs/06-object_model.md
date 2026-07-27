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

## Measured: the first stochtree run (`workflow/06-object_model.R`, 2026-07-27)

`Rscript collection-01/workflow/06-object_model.R` = fit + a one-year prediction probe.
stochtree **0.4.5**, 8 threads, `OutcomeModel(outcome = "binary", link = "probit")`,
`num_gfr = 10`, `num_mcmc = 500` with `keep_every = 4` — i.e. **2000 MCMC iterations thinned to
500 retained draws** (`num_mcmc` is the *retained* count; stochtree runs `num_mcmc * keep_every`).

**The fitting set** — `clean_tagged()` in `scripts/objects_data_functions.R`, from the 6831 pairs:
−234 rows whose label hit no object, −10 objects labelled both classes, −1315 duplicate labels on
an already-labelled object, −1 object with an NA predictor → **5255 objects, 2788 fire / 2467
non-fire**, 40 predictors. Uneven label density per object is *not* corrected — reweighting by it
would invent information.

| step | measured |
|---|---|
| fit (5255 × 40, 2000 iter → 500 draws, 8 threads) | **95 s** |
| serialized fit (JSON) | 89 MB, reloads in 5.6 s |
| predict FY 2020 — 78 211 objects × 500 draws | **103 s** = 762 obj/s = 2.6 µs/obj/draw |
| ↳ of which the per-object quantile reduction | ~6 s (1.6 s per 20 k-row chunk) |
| **extrapolated to all 1 689 419 objects** | **≈ 37 min**, peak RAM one chunk (20 k × 500 ≈ 80 MB) |
| out-of-fold AUC — see the CV section below | **0.90** grid-blocked (0.976 random, 0.75 leave-one-region-out) |

**So no — scoring every polygon across posterior draws is not a problem.** 37 min once, at flat
memory. What *would* be a problem is the naive route the docs warn about above: passing the full
object set as `X_test` to `bart()` materializes 1.69 M × 500 doubles ≈ **6.8 GB**. Fit → serialize →
`predict()` per year in chunks → reduce to `p_mean/p_sd/p_q05/p_q95/p_width` → discard the draws.
Thinning is the other half of the answer: cost is linear in draws, so 2000 retained draws would
have been 4× the prediction time and 4× the memory for no gain in a 5th percentile.

### Predictor variant: grouped vegetation fractions beat the 23 raw ones — USE `grouped`

`--grouped` (default) replaces the 23 raw `frac_c1..frac_c23` with **five summed fractions**, taking
the design matrix from 40 to 22 columns. Membership is derived from `config/veg_fire_remap.csv`
**by name** (`objects_data_functions.R::veg_groups`), not from typed-in codes, and any code landing
in two groups is an error rather than a silent reshuffle:

| column | veg_fire classes |
|---|---|
| `frac_agri` | 1 agriculture_chaco, 2 agriculture_cuyo-pat, 3 agriculture_pampa — **not** 4 agriculture-per |
| `frac_grass_inund` | 17 grassland-inund_chaco |
| `frac_pasture` | 18 pasture_ba, 19 pasture_chaco |
| `frac_grass_temp` | 12 grassland_ba, 13 grassland_chaco, 15 grassland_pampa — **not** cuyo/patagonia |
| `frac_woody` | 5,6,7,8,9,11 forests + 20,21,22,23 shrublands — **not** 10 forest-inund |
| *(no group)* | 4 agriculture-per, 10 forest-inund, 14 grassland_cuyo, 16 grassland_pat |

Not region-separated and **not a partition** — the five sum to 0.70 on average, never more than 1.

Same 5255 objects, same folds, same MCMC budget. Grid-blocked (the deployment number):

| | full (40 cols) | **grouped (22 cols)** |
|---|---|---|
| AUC | 0.9017 | **0.9211** |
| accuracy | 0.786 | **0.812** |
| sensitivity | 0.687 | **0.729** |
| specificity | 0.899 | **0.906** |
| precision | 0.885 | **0.897** |

Grouped wins on every pooled metric, and **the gain lands where the error was**: the 1–50 ha band
(61 % of all objects) goes 0.872 → **0.903** AUC, and the one hard fold — the high-prevalence
fold 5 — goes 0.816 → **0.864**. Above 300 ha the two are equal (0.956 / 0.953).

Leave-one-region-out is a **wash**: AUC 0.750 → 0.741, accuracy 0.671 → 0.684. Worth noting because
the stated hope was that region-agnostic groups would transfer better across ecoregions — they do
not. The gain is not about region-agnosticism, it is about **split budget**: 23 sparse columns were
58 % of the design matrix and BART draws split variables uniformly over what is available, so
merging them concentrates the same signal into 5 dense columns. Per region the changes cancel
(Pampas 0.700 → 0.789, Bosque Atlántico 0.839 → 0.764, Patagonia 0.773 → 0.721, Chaco ≈, Puna ≈).

Fitted grouped model: 94 s, JSON 92.7 MB; FY 2020 prediction 100.5 s (778 obj/s), 68.6 % of objects
above 0.5 covering 4326 of 4841 kha, mean `p_width` 0.333 (vs 0.370 for the full variant — the
posterior is also a little tighter). All artifacts are variant-suffixed
(`bart_object_model_<variant>.json`, `objects_<fy>_pred_<variant>.csv`, `oof_<variant>_<spec>.csv`),
so refitting one never overwrites the other.

Still open (BACKLOG): the 0.5 cut is not the right threshold — sensitivity 0.73 against specificity
0.91 under grid blocking. Pick it on `data/objects-predictions/oof_grouped_grid_5.csv`.

### Threshold: 0.5 is wrong, and the right cut RISES with object size

`scripts/objects_threshold.R` sweeps every cut on the **out-of-fold** probabilities
(`oof_grouped_grid_5.csv` — never in-sample, or the cut would be chosen against answers the model
already saw) and reports four criteria. **Youden's J (sens + spec − 1) is the headline** because it
is the only one here that does not move with prevalence, and our labelled set is not a random sample
of objects. F1 and accuracy are reported but drift with that same sampling bias; `J_area` weights
each object by `area_ha` (the deliverable is an area product) but a handful of huge objects dominate
its weights.

| stratum | n | Youden cut | sens | spec | J | J at 0.5 | bootstrap 5–95 % |
|---|---|---|---|---|---|---|---|
| **1–50 ha** | 3217 | **0.180** | 0.855 | 0.791 | 0.646 | 0.530 | 0.111–0.236 |
| **50–300 ha** | 1192 | **0.405** | 0.878 | 0.834 | 0.712 | 0.695 | 0.336–0.476 |
| **≥ 300 ha** | 732 | **0.598** | 0.910 | 0.880 | 0.789 | 0.763 | 0.520–0.657 |
| < 1 ha | 114 | 0.233 | 1.000 | 0.953 | 0.953 | 0.609 | 0.233–0.340 |
| all | 5255 | 0.274 | 0.861 | 0.820 | 0.681 | 0.635 | — |

**The cut rises monotonically with size — 0.18 → 0.41 → 0.60 — and the bootstrap intervals barely
overlap**, so the per-band difference is signal, not resampling noise. That is the justification for
per-band cuts over one global 0.274: the model is far more confident on big objects, so a single
threshold is simultaneously too high for small ones and too low for large ones. The gain is
concentrated where the error was: in 1–50 ha, J goes 0.530 → 0.646 and sensitivity 0.610 → 0.855.
Above 300 ha the 0.5 default was already nearly right (0.763 vs 0.789).

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
predictions + all 40 predictors + the c-00 verdict onto the step-05 geometry already on disk:

- **`<fy>_objects_pred.gpkg`** — every object of the year, 50 fields. Open in QGIS, graduate the
  fill on `p_mean` (or `p_width`), add an XYZ imagery basemap, and use the attribute table and
  filter expressions to walk cases. FY 2020: **354 MB written in 6 s**, and QGIS pans it smoothly
  off the GPKG spatial index. This is the fastest route to eyes-on and needs nothing new built.
- **`<fy>_objects_sample.geojson`** — a stratified sample (default 20 objects per `p_mean` decile,
  geometry simplified to ~30 m; FY 2020 → 200 objects, 1.6 MB). This is the answer to "is there a
  geemap midpoint": **yes.** geemap/leafmap is an ipyleaflet map — `Map.add_geojson(path)` /
  `add_gdf()` puts local vectors on it as **client-side** layers while GEE imagery (candseed,
  Landsat min-NBR, the bpts composite) renders as server-side tiles beside them. Nothing is
  uploaded to Earth Engine. The binding constraint is the **browser**, not GEE: keep client-side
  features in the low thousands, which is exactly what a decile-stratified sample gives you.

That covers Lican's suggestion without a Shiny app: the sampling-by-predictor-range panel is a QGIS
filter expression or a geemap cell. Build the Shiny app only if a *shared* review tool is wanted —
for one analyst it adds a UI to maintain and no capability QGIS lacks. A whole-country raster
overview is the other option not taken: rasterizing `p_mean` at 30 m country-wide is 9.16 B cells
(docs/05 §7), so it would have to be coarsened to ~300 m, which erases the small objects that are
precisely the ones in doubt.

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

## Model fitting and classification

Feed all the metric variables to **XGB additive trees**, fit and classify **locally** (python
or R), tuning hyperparams with CV. **No geometry is needed for the model** — it reads the two
per-year CSVs (`_raster_metrics` + `_shape_metrics`) joined on `oid`. The most important predictor
is **`seed_mean`** (seed share). Include the **fire-year** (recoverable from `oid`) and
**`year_calendar`**; year mostly operates through `n_mean` (e.g. in 1999 many real fires had few
seeds). No independent validation — the CV is only for hyperparam tuning.

### Sign-constrained XGB (option, given thin labels)

The label set is small relative to 42 predictors, so the ensemble is free to invent a
**reversal** in sparse interior regions of predictor space — a gap between observed clusters
where nothing pins the fit down. XGBoost's `monotone_constraints` (per-feature `{-1,0,1}`,
`hist`/`approx`/`exact`) removes that freedom by rejecting any split whose child weights run
against the declared sign and propagating the resulting bounds down the subtree.

Two things to be clear about before using it:

- What it enforces is **conditional (ceteris-paribus) monotonicity** — monotone in `x_j` with
  every other feature held fixed. That is *stronger* than marginal monotonicity, not weaker;
  a monotone PDP does not imply it (a PDP averages monotone slices, so it is monotone
  automatically and cannot be used to check the property).
- It therefore **forbids sign-flipping interactions** on the constrained feature. Magnitude
  can still vary freely across regions; direction cannot. That is a real modelling assumption
  and it costs fit, since the bound propagation also blocks some splits that never violated
  anything.

So constrain only signs defensible under cross-examination — realistically **`seed_mean`**
(more seed share → more fire), possibly `n_mean`. **Not** `area_ha` (very large objects are
either real fire complexes or dilation-bridging artifacts — see the 1.71 Mha `2000_57529`),
not the shape metrics, and not `burned_around_*` (a region-wide ash/drought false-positive
patch pushes it up for the wrong reason).

It does **not** help outside the training range: trees are constant there, constrained or not.
The gain is strictly in sparse interior regions.

Related: `interaction_constraints` (whitelist which features may appear together in a tree) is
the companion knob if the fitted surface turns out to be implausibly interactive.

### BART (option, and arguably the better fit here)

**Same function class as XGB** — a sum of trees, piecewise constant on axis-aligned partitions —
but fitted by MCMC (Bayesian backfitting) rather than greedy stagewise descent, so every tree
keeps being revisited conditional on the others instead of being frozen once added. For
fire/non-fire use **probit BART** (Albert–Chib latent-variable augmentation).

Why it suits *this* step specifically:

- **No CV tuning.** With a small label set we cannot tune honestly anyway; BART's defaults are
  calibrated regularization priors, not placeholders (below).
- **The posterior gives a per-object SD**, which is a direct map of *where the model is unsure* —
  exactly the targeting signal for a second round of point collection. Upload posterior **mean
  and SD** as FC properties and the collection round-2 targets can be picked on the map.
- We have no independent validation set, so a point estimate with no uncertainty is a weak
  deliverable; a posterior is not.

Cost: far slower than XGB (MCMC), though trivial at a few thousand labelled objects.

**Default priors** (Chipman, George & McCulloch 2010) — studied, not arbitrary, and already
partly data-calibrated:

| component | prior | default |
|---|---|---|
| tree depth | `P(node at depth d splits) = α(1+d)^(−β)` | `α=0.95, β=2` → ~55 % of trees have 2 terminal nodes, ~3 % have ≥5 |
| leaf values | `N(0, σ_μ²)`, `σ_μ = 3/(k√m)` on the probit scale | `k=2` (main shrinkage knob; sensible range 1–3) |
| split variable / cut point | uniform over available | see DART below |
| number of trees | — | `m=200`; results robust to it |

Tuning is legitimate and was proposed in the original paper (CV over `k`, `m`, and the σ prior;
`bartMachineCV` grid-searches it). With few labels, prefer **defaults + a sensitivity check on
`k`** over a noisy CV.

With 42 predictors, most of them probably irrelevant, consider the **DART sparsity prior**
(Linero 2018) — a Dirichlet prior on splitting proportions in place of the uniform, which does
variable selection. Exposed as a `sparse=TRUE`-style argument in the `BART` package; verify the
exact interface for the probit routine before relying on it.

#### Which implementation (as of 2026-07)

**Use [`stochtree`](https://cran.r-project.org/package=stochtree)** — the successor package from
the BART/XBART authors ([arXiv:2512.12051](https://arxiv.org/abs/2512.12051)), C++ core with both
R and Python bindings, CRAN 0.3.1 since Feb 2026.

The deciding factor is *what kind* of parallelism each package offers, given our 8 physical cores:

| package | how it uses cores | verdict |
|---|---|---|
| `BART` | `mc.pbart(mc.cores=8)` forks concurrent **chains**; OpenMP only in `predict` | 8× draws, not 8× speed; 8× memory |
| `dbarts` | `bart2`'s `n.threads` defaults to `min(guessNumCores(), n.chains)` — threading is essentially *across* chains | same limitation |
| `bartMachine` | Java/rJava backend | rJava setup friction; skip |
| **`stochtree`** | **`num_threads` covers the GFR sampler, the MCMC *and* prediction** | genuine within-chain scaling — real wall-clock reduction |

Relevant `stochtree::bart()` arguments (the last four live inside `general_params`):

- `num_gfr = 5` — grow-from-root warm start; converges to high-probability regions far faster
  than cold MCMC, so fewer MCMC iterations are needed. Also warm-starts each chain when
  `num_chains > 1`.
- `num_mcmc = 100` — **raise this to 1000–2000.** A 5th percentile from 100 draws is the 5th
  order statistic, far too noisy for the `p_q05` we intend to map. GFR is what makes it affordable.
- `num_threads` — set to **8 (physical), not 16.** Tree sampling is memory-bandwidth-bound, so
  hyperthreaded logical cores mostly add contention. Defaults to 1 if OpenMP was not compiled
  in — if you see 1 on Linux/gcc, something is wrong with the build.
- `outcome_model` — the probit/binary switch. Note `probit_outcome_model` is **deprecated** in
  favour of it, so check `?bart` for the accepted value rather than copying older examples.
- **JSON serialization** — fit once, serialize, predict per year in a separate process. Drops
  straight into the one-`Rscript`-per-year pattern of `workflow/run_05_years.sh` (docs/05 §4.1).

**The tradeoff to be aware of:** stochtree's `variable_weights` is a *fixed* vector of relative
split probabilities, **not** a learned Dirichlet — so it does not give you DART's automatic
variable selection. `BART::pbart(..., sparse=TRUE)` remains the only one of these with the learned
sparsity prior. Fit stochtree first (fast enough to iterate) and fall back only if variable
selection turns out to be the binding problem; a middle route is to derive `variable_weights` from
a first pass.

**Prediction is the memory risk, not the fit.** We fit on the labelled objects only (a few
thousand) but predict on **all 1.69 M**. At 1000 draws that is ~1.7e9 doubles ≈ 13.5 GB if the
draw matrix is materialized. So: never pass the full object set as `X_test` to the fit; `predict()`
in chunks (one fire-year ≈ 75 k objects × 1000 draws ≈ 600 MB) and reduce to the summaries inside
the loop, discarding the draws.

Upload four DBF-safe properties per object: **`p_mean`, `p_q05`, `p_q95`**, plus
**`p_width = p_q95 − p_q05`** precomputed so uncertainty can be thresholded in GEE without
arithmetic across two properties. Note the semantics: these bound the **probability** (epistemic
uncertainty about the fitted function), *not* the class label — a predictive interval for a
Bernoulli draw would be 0/1 and useless. Wide `p_width` = the model does not know = where round-2
point collection should go.

**Caveat:** a monotone variant (mBART) exists in the literature but a maintained R implementation
is uncertain — check before assuming you can have the sign constraint *and* the posterior.

Optional **hard size constraints**: drop objects `< 1 ha`, and possibly apply the model only to
`1 ha ≤ area < 2000 ha` (very large objects are rarely non-fire) — the upper cut is riskier. If the
`< 1 ha` cut is adopted, apply it **before** the fire-subset upload (it removes the long tail of
tiny noise objects, shrinking the FC that gets ingested); it could also be applied at data
collection so users don't spend time on objects that won't be used.

The classified objects yield the set of fire `oid`s. **Then upload only the fire subset** (below) —
we do not upload, then filter, a full-year asset.

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
