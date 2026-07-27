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
- **Exports (open).** As with the training-locations collection, each user keeps several
  point-feature collections split by **class × year/year-range** — so metadata lives at the FC
  level, not per point, letting them place many points fast over same-class/-year clusters. With few
  users, Claude can later edit all the scripts, tag points, merge the FCs, and hand off one export
  (the user runs it in GEE).

### Why the SNIC layer, not the polygons (record)

El snic-vectorización-métricas y tal está tomando mucho más de lo que esperaba, no llego a tener los polígonos con métricas para mañana. PEEERO ya están exportadas a asset las imágens por año con el resultado del SNIC, en donde dice si cada pixel fue candidato o seed, sólo sobre clusters que el snic mantuvo. Entonces podemos empezar a tomar datos sobre esa capa. Más lento quizás, sin poder ver las métricas a nivel de polígono, pero igual la forma y la densidad de semillas es lo más informativo. Así que podemos largar la toma de datos aunque aún no tengamos los polígonos con metadata. Porque al poligonizar, no va a cambiar con qué polígonos intersectan esos puntos. Así que estamos atrasados pero quizás no sea tan grave.
Ya le pedí a algunos que destinen jueves-viernes a tomar datos, por eso era un moco el atraso.

*(This started as a stop-gap for the vectorization delay; it is now the chosen approach — docs/07.)*

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
