# CLAUDE.md

Guidance for Claude Code (and any contributor) working in this repo. Durable operating
rules only — for **what to do next, in order, see [`ROADMAP.md`](ROADMAP.md)** (and the rule
below); for design detail see the per-step notes in `collection-01/docs/` (below).

## The roadmap comes first

**[`ROADMAP.md`](ROADMAP.md) at the repo root is the ordered list of what to do next.** It is the
*when*; `collection-01/docs/NN-*.md` are the *how*. Four rules:

- **Read it before planning any task.** When Iván hands you a task, check whether it is on the
  roadmap. If it is, work from the roadmap's ordering and its "run" / "edit → run" note — several
  items look like a re-run and are not.
- **Update it when work advances.** Tick an item when it lands and delete it on the next pass; git
  history is the archive. Never let the roadmap and reality disagree.
- **For a large task that is not on it, ask Iván whether to add it** before starting. Small,
  self-contained work does not belong there.
- **Do not read [`BACKLOG.md`](BACKLOG.md) unless asked.** It is the unscheduled pile for the whole
  repo (all collections) — long, unordered, and none of it is next. Open it only when Iván points
  at it, or when moving an item from it onto the roadmap.

## Primary focus

**Active development is almost always in `collection-01/`, running scripts from
`collection-01/workflow/`.** Default to `collection-01/` context unless told otherwise.
Collection 0 (`collection-00/`) is the completed Patagonia pilot — reference, not active work.

## How this repo is documented — read the right file

Documentation is modular. **Most development notes live in `collection-01/docs/`, one file
per workflow step**, numbered to match the step (numbers repeat when several topics belong to
one step, e.g. the remap and the fit are both inputs to step 02):

| Doc | Covers |
|---|---|
| `collection-01/docs/00-overview.md` | **read first** — the method in one page: spectral → temporal → spatial, and which step is which |
| `collection-01/docs/01-training_data.md` | step 01 — training-data export, labels, inputs |
| `collection-01/docs/02-vegetation_remap.md` | the `veg_fire` fire-class remap (input to step 02) |
| `collection-01/docs/02-data_cleaning.md` | the `fit`-column cleaning gate (input to step 02) |
| `collection-01/docs/02-model_fitting.md` | step 02 — elastic-net LR fitting |
| `collection-01/docs/02-burn_probability.md` | the fitted model **deployed in GEE** — the spectral stage's product. How `veg_fire` picks the model, how the per-class coefficient CSVs become **one band per term via `veg_fire.remap`** (so 23 models are one branchless expression), the raw-scale dot product and the rename-before-multiply band alignment, and why the probability is **never materialized**. The code runs inside `workflow/03-bp_ts_metrics.py`; the per-year precomputation that makes it affordable is documented in `docs/03-bpts.md` "What is precomputed per year" |
| `collection-01/docs/02-diagnostic_plots.md` | the per-fire burn-probability time-series panels (a diagnostic tool, not a step) |
| `collection-01/docs/TEMPLATE.md` | the shape a step doc follows — read before writing or rewriting one |
| `collection-01/docs/03-bpts.md` | step 03 — burn-probability time-series metrics, the **temporal** stage (the model it consumes is `02-burn_probability.md`, computed in the same graph — **"What is precomputed per year" is the join**, and it is required, not cosmetic): the delta = `minfore` − `maxback` design, the asymmetric 3+2 padding and the two guaranteed-structure arrays, the 16 int16 bands and their decode, the idempotent cross-account launcher and the **two destination collections** (1999–2009 overflow to `mapbiomas-chaco`), plus the GEE array gotchas that are still load-bearing. History is in `docs/notes/03-performance_profile.md` (where the per-tile compute goes — the array machinery is <1 % — and the EECU A/B test behind P=50), `docs/notes/03-tile_merge_test.md` (merging cartas: rejected), `docs/notes/03-validation_2015.md` (the Cholila tile check, ~7e-9 against a hand-computed logit) and `docs/notes/03-dropped_timediff_bands.md` (18 → 16 bands) |
| `collection-01/docs/03-colab_multi_export.md` | step 03 — distributed multi-account export via Colab (admin notes) |
| `collection-01/docs/04-snic.md` | step 04 — burned-area segmentation: the whole-country **non-calendar fire-year** SNIC. Why the 1 May boundary and the two partial edge years; the per-veg, per-pixel-K seed/candidate cuts; the window-filter-and-combine that turns two calendar `bpts` images into one fire-year; the Patagonia dieback padding (`candseed = 3`) and the San Ramón exception; supervised SNIC at `neighborhoodSize = 512`; and the two-stage handoff to R (`--to-asset` bakes `abs_date`/`veg_fire`/`n`/`burned_around_*`, `download_snic.py` pulls the 7-band stack one *carta* at a time). History is in `docs/notes/04-snic3d_firebreaks.md` (the shelved firebreak + gap-fill route the fire-year replaced) and `docs/notes/04-vectorization_benchmark.md` (the FY2000 whole-country vectorize benchmark) |
| `collection-01/docs/05-object_metrics.md` | step 05 — fire-object vectorization & metrics (R): burned pixels → objects, one fire-year at a time, whole-country and **untiled**. The dilation-as-a-wider-union-window connectivity rule (and the `NO_DILATE_VEG` classes exempt from it), union-find labelling (`utils/label_uf.cpp`), per-object raster metrics (`seed_mean`, veg fractions, area, `abs_date` summaries, sparseness) + geometry shape metrics ported from collection-00, the `pid`/`oid` keys, the outputs (`data/snic-rasters/` → `data/objects-raw/`, geometry/metrics split) and the overnight all-years launcher (`scripts/run_05_years.sh` + `scripts/mem_monitor.sh`). History is in `docs/notes/05-whole_country_redesign.md` (what broke at 9.16 B cells, every road not taken) and `docs/notes/05-memory_profile.md` (the FY2000 profile, the merge bug, the 25-year batch) |
| `collection-01/docs/06-object_model.md` | step 06 — object-based fire/non-fire classification. Opens with **"Files, directories and scripts"** — the step-06 data layout (`objects-labels/`, `objects-pred/`, `objects-analysis/`, the regenerable `*-cache/`) and what each script is for; then label collection in GEE (drawing layers → one asset per collaborator) and their join to objects; the **probit BART** fit (`stochtree`) with posterior probability bounds; the 20 predictors (incl. 5 aggregated vegetation fractions) and **§4 why no predictor may identify the year or proxy for it** (the `fire_year`/`year_calendar` label-prevalence leak, the `n_mean` era proxy, and the two metrics collection 2 should stop computing); **§5 the three call columns** (`fire_model` / `fire_tag` / deployed `fire`, and why `-1` not `NA`); the per-size-band **classification threshold** (Youden's J out-of-fold); **grid-blocked CV** and why the fold design decides the answer; **§8 importance + ALE**; **§11 QGIS inspection** without a GEE upload; **§12 the upload** — all 28 fire-years, whole object set, zipped Shapefiles + the validation gate |
| `collection-01/docs/07-vector_to_raster.md` | step 07 — **everything Argentina builds**, in five sub-steps **07a–07e** with an explicit order-of-operations table and run commands at the top. **§1.1 is the object exclusion ruleset** — the positive selection is `fire == 1 & area_ha >= 1 & not(A) & not(B)`, where **B** drops `frac_agri > T` (agriculture, everywhere) and **A** drops `frac_c15 > T` *within a 1 Jul–15 Nov window* (the Pampa grassland/cropland problem; a composition threshold **and** a season, 17.5 % of FY2020 on its own); why the fix is at the object level and not a raster mask, the three application points that must carry identical thresholds, and the `date_med`/`date_median` split; **§1.2 the `_v2` re-export** — one constant (`C.PRODUCT_VERSION = 2`) renames the month collection, the nine subproducts, the scar rasters, the scar vectors and the polygon layer, and why versioning beats overwriting (v1 stays readable, nothing half-replaced, and the "all 27 month assets exist" gate on 07d actually means something) (07a month of burn ✅, 07b local scars ✅, 07c scar rasters ✅, 07d **the nine derived subproducts** ✅ — §12: the encodings copied from the reference, the four settled answers, the four traps, the LULC-on-our-lattice verification, the pre-launch decode audit and **§12.8 the re-verification on the landed assets**; 07e **the merged fire-object polygon layer for early users** — §13: 1.26 M polygons, the ten properties, why `polygons` not `vectors`, and the measured feasibility of one 1.26 M-feature table export). Also covers the ONE pinned grid (`crsTransform`, never `scale=30`) and the col-0 lattice collision; the verified calendar-year partition; the **`candseed==3` parent-date substitution** (881 k px / ~79 kha, and why it protects the scar product); why the LULC mask + solitary-pixel filter are **already embedded upstream** (verified: zero candidates on non-burnable `veg_fire`); the proof that polygon paint/rasterize reproduces the object pixel set **exactly**; and why `terra::cells()` is the right membership tool |
| `collection-01/docs/08-postprocessing.md` | step 08 — the **MapBiomas Fuego network-wide post-processing** (stages 1–4: the GEE assets), identical in every country and summarised from the network's [*Guía del Proceso de Lanzamiento*](https://docs.google.com/presentation/d/1Y5SUeS_405k5zZkBX4z6BDaC_umI8Saiguk7coITB1Q/edit) (§1 gives the `curl …/export/pdf` recipe to read the slides as a PDF): LULC masking + month coding, the `FINAL_PRODUCTS` subproducts (annual/monthly burned, burned coverage, frequency, accumulated, year-last-fire, scar id/area/size-range). Also: their mapping method (Alencar et al. 2022) vs ours, and **§6 Argentina's route — vectors-only upload, calendar-year products from fire-year objects** |
| `collection-01/statistics/docs/statistics.md` | step 09 — **every factsheet number and figure**. **Three sources** (§intro): the **numerator** is the network's toolkit, run on our 13-class ecorregión vector as a repointed copy in the `fuego` repo, exported to GCS and downloaded into `data/statistics/` (§2 — including **§2.2 why our copy crosses the PREVIOUS year's LULC** and the three-way discrepancy that creates); the **denominator** is ours and constant — the **mode over 1998–2024** of the col-3 burnable classes, `eco13·10 + status`, 4 statuses so nothing shrinks it silently (§3, with §3.1 the measured table, **§3.2 why Islas del Atlántico Sur is NOT reported** — outside the processing grid, so its zero is a mapping gap — and §3.3 what a constant denominator changes); the **fire counts** are local, off the polygons (§4). **§5 is the code**, and **§5.0 says which of the four `factsheet_*` notebooks is THE DELIVERABLE**: **`factsheet_sep2026.qmd`** is what the designer gets (**§5.10** — the September deck slide by slide, 16 clean images with no title/subtitle/caption inside plus one `figNN_datos.csv` each, written to `data/statistics/factsheet_sep2026_figures_and_tables/`, and the four decisions it carries: Mha not `%` with the GAM rescaled not re-fitted, Y-axis decimals from the tick step, a wider nivel-2 ramp for the pie, and `relabel_fill()` because a scale's own `name` silently beats `labs(fill=)`); `factsheet.qmd` (análisis 1–5, every regional variant, with titles and captions) is **the bank it selects from**; `factsheet_veg.qmd` and `factsheet_veg_short.qmd` are **exploratory** — not published in September, kept and documented because they are the material for the December fire launch and the paper. Note what September did NOT take: análisis 5 and 6 are not in the deck. **§5.10.1 is a bug in the NETWORK's legend, found and fixed 17 Sep 2026**: `lulc_argentina_nivel2` in `00_Tools/Legends.js` had the names of codes 11, 12 and 63 rotated one place against their keys (11 is Herbaceas Inundables, 12 is Herbaceas, 63 is Mosaicos de arbustos y herbaceas; the Delta is 75 % code 11 and the Pampa 62 % code 12, and Chile's legend in that same file uses the global convention). **The fix is on BOTH sides and they go together**: `legends.py` for the denominator, which is ours and decodes by code, and `factsheet_tables.R::fix_n2()` on read for the toolkit's `annual_burned_coverage_*.csv`, which arrive with the name already decoded. The numerator↔denominator join is BY NAME, so fixing one side alone pairs different classes with no orphan and no gate firing. **No GEE re-export was needed** (the `_raw` files re-decode with `--check`), no number moved, and nivel 0/1 are untouched because all three are one family. **The network still has to be told.** Read §5.10.1 before touching any nivel-2 class name. Also: `fire_counts.R` (the vector pass), `factsheet_tables.R` (the plot-ready tables, the trend GAMs), `factsheet_style.R`, `notebooks/factsheet.qmd` and **`notebooks/factsheet_veg.qmd`** (análisis 6, split out so it renders in seconds; same `fig06_` prefix, one producer per figure) — and **the two land-cover questions, which are NOT the same and have different denominators**: **§5.2 análisis 4**, the *composition* of what burned (no new export — the toolkit's `annual_burned_coverage` already is it), and **§5.3 análisis 5**, *what % of each class burned*, which needed the second export `lulc_area_export.py` (the toolkit cannot give it: every dataset there is masked to burned pixels). §5.3 also carries the two rules that define that number — the **Y ↔ Y−1 offset** and **the mean taken LAST** (Jensen + reburn double-counting). **§5.5–5.7 are the three things added on 17 Sep 2026**: §5.5.1 the frequency raster re-read in *times burned* (and why the integer version needs `--reducer max`, a second file and a different claim); **§5.6 the year-of-last-fire raster** — `year_last_fire_v2` band `year_last_fire_2026`, `mean` not `max` (max saturates), and the measured finding that **the nine v2 subproducts do not share a lattice** (frequency/annual are EPSG:3857, year-last-fire and the col-3 LULC are the 4326 SNIC one, integer-offset from each other), so this raster aggregates on its own asset's lattice and the two factsheet rasters cannot be crossed cell-by-cell — the gate crosses national numbers; **§5.7 análisis 6**, `lulc_change_export.py`: the **whole country** crossed by fire state × cover of Y−1 × cover of Y+offset, packed `state*1e6 + eco*1e4 + prev*100 + post` (**int32, not uint16**), reduced on the LULC lattice so the categorical layer is never resampled, gated year-by-year against the toolkit's annual burned area (0.00 % every year). The design is **Ferro et al. 2026** (this group's Dry Chaco paper) redone at 30 m nationally: **§5.7.1 the CONTROL** — the reduction is not masked to fire because "15 % of what burned changed cover" is unreadable without the 3.9 % that changes without fire; four states so the exclusion rule (no fire elsewhere in the window) applies to treatment *and* control with the two contaminated groups kept visible; `q = P(changed|burned)/P(changed|not)` = **3.74** nationally, conditioned on the origin class per transition (bosque → agropecuario **q = 10.9**), and why the control reorders the regions (Pampa's 33.9 % drops to third; Campos y Malezales and Altos Andes come out **below 1**); **§5.7.2 the Y+3 window** as the scar-artifact test — the burned rate rises 14.5 → 17.6 % instead of falling back, so the transitions are persistent; **§5.7.3 the two flags the general analysis does not use** — `--lat-split` (split a non-homogeneous ecoregion without inventing one: north of −44 holds 87 % of Bosques Patagónicos' burned area and behaves differently) and `--window` (separate the fire-free exclusion window from the post-fire lag; without it each lag carries its own range of focal years and Y+1…Y+5 is four populations, not a trajectory — and `--offset 5 --window 5` IS the plain `--offset 5` file). The measured result: burned Patagonian forest leaving forest goes **49 % at Y+1 → 78 % at Y+5** on a fixed cohort, converging near 80 % and not the ~95 % the severity literature reports, with `Matorrales y arbustales abiertos` rising 36 → 57 % — **the arbustalización reaches the map about three years late**. Consequence beyond Patagonia: **Y+1 is calibrated on the Chaco, where fire clears**, so it structurally understates systems where fire kills but does not clear — read woody vegetation at Y+3 minimum, forest at Y+4–5; **§5.8 `factsheet_veg_short.qmd`** — the same análisis 6 cut to three national sentences and two figures for the slide (nothing recomputed, prefix `fig06c_`, ~10 s): **every percentage carries its area**, and the two units are not interchangeable (what burned is a **series total in hectare-years**, 61.4 Mha with reburns counted twice and NOT the accumulated area that ever burned; what is country surface is **per year**, 252 Mha). The three claims: 12.5 Mha / 20 % of what burned changed class at nivel 2 (9.1 Mha / 14.8 % at nivel 1 — **each Sankey must carry its own level's number**), the country changes 10.4 Mha·yr / 4.1 %, and 3.4 % of that change burned against a 0.9 % area share = **3.6×**, which is `q` = 3.74 by another route. §5.8 also carries **the thresholded-Sankey trap**, which applies to the long notebook's Sankeys too: the cut is **per transition**, so a destination fed by many small flows is drawn far thinner than it is — 0.891 Mha arrive at forest in BOTH levels (identical, asserted at render), but in 2 bands at nivel 1 and 37 at nivel 2, so a 1.5 % cut drew one of them. **Never read arrival area off a thresholded Sankey** (that is análisis 4), and `sankey_change(keep_unchanged = TRUE)` draws the complete one with the diagonal — flat on purpose, since 85 % of what burns stays what it was. **§5.9 forest only** (`factsheet_bosques{,_destinos}.csv`): **Y+4 and Y+5 ARE national** — `--lat-split` adds a north/south bit, it does not clip the reduction, so the `_n44` files are the whole country and all four lags are already exported; and there are **four different forest q's** that a slide can confuse — family leaves forest **6.4**, *bosque cerrado* leaves forest **14.0**, forest → agropecuario **10.9**, cerrado leaves its own class 11.7. The family average describes none of its classes (**bosque inundable q = 1.0**), so a forest number on a slide must be a class. **§6** everything is calendar-year + the three divergences; **§7** the territorial layer and its three measured traps (the `_r` rasters are numbered differently from their own vectors); **§8** burnable as a col-3 legend decision; **§9 the verification gates, with what each one measured**; §11 publication + launch; §12 decisions on record |
| `collection-01/statistics/docs/factsheet-sep2026-spec.md` | the **factsheet's content** (in Spanish) — what each slide says and why. **Its header box is the status table**: `factsheet_sep2026.qmd` is the deliverable, `factsheet.qmd` is the bank it selects from, and the two vegetation notebooks are exploratory (December + the paper). Then: the multi-region graphic conventions (stable colour per region, the little map as the legend, `all_regions` vs focal variants, palette ordered by latitude) and the **six** analyses (mean annual burned proportion; the time series + GAM trend, and its "veces el año típico" normalisation; **§3 the whole intra-annual pattern in one analysis** — 3.1 the peak month on a **cyclic** palette (December next to January, because a month is not a magnitude), 3.2 the pirogram, 3.3 the per-region normalised shape, 3.4 the normalised pirogram that puts both PMFs on one axis and writes the series totals into the panel; **§4 the composition of what burned by LULC class**; **§5 what % of each class burns** — those two are different questions with different denominators and §5 says why they get confused; and **§6 how land cover changes around fire** — with **§6.5 the slide version** (three sentences, two figures, `factsheet_veg_short.qmd`): every percentage with its area, the two units named, and the trap that the Sankey and the percentage must come from the same legend level. In the full §6 the control is the figure, not the percentage: a dumbbell of burned vs unburned change rates per region, `q` on a log axis, the q-per-transition matrix and the Sankey, plus the box that says it stays observational because pixels that burn are not a random sample). **§0.1 is the convention of every pixel map**: zero is white and a class of its own, magma for the frequency pair and plasma for the years; §0.2 the same frequency map read in *times burned*; **§2.1 the year-of-last-fire map**, which is the figure that opens análisis 2. Figure prefixes follow these numbers (`fig03_*` is all of the intra-annual work). Pairs with collection-01/statistics/docs/statistics.md, which says where every number comes from || `collection-01/validation/docs/design.md` | step 11 — **validation design**: stratified random sample of pixels, Olofsson (2014)/Stehman (2014) design-based estimators, error-adjusted burned area with CIs. Everything is **fire-year** (1 May → 30 Apr), so our layer is rebuilt from the calendar month-of-burn collection and every external product is `filterDate`d to the same window. **§4 is the exact strata-raster recipe** — the S2 union of our map + MCD64A1 + **VNP64A1 (VIIRS burned area, in GEE from Mar 2012)** + FireCCI51 + FIRMS, aggregated with `max` (never `mode`) onto a coarse grid that is **our 30 m grid decimated ×16 (~480 m), not an independent 500 m grid**, dilated with a 3×3 square kernel, reprojected back and minus S1; population = whole country (`ARG-Political_Level_1-Pais`, 279.27 Mha). Strata land in the existing IC **`FIRE/VALIDATION/sampling_strata`**, one 2-band image per fire year (`stratum` 1/2/3 + `burned` = our map's own call, so the drawn points carry the map class and the confusion matrix comes straight out of the sample CSV), keyed by the mandatory `year` (= FIRE year) + `collection` (= 1) properties. Also §5 the frozen 30 k-per-stratum ordered sample lists, §6 what 100/stratum/year buys and how to extend, §7 response design + QC, §9 why `stehman2014()` not `olofsson()`. |

> **When a workflow step is in play, read the matching `collection-01/docs/NN-*.md` first.**
> Those notes point onward to the production files (`config/`, `models/`, `workflow/`) and to
> the notebooks that hold the deeper analysis. Add a new `docs/NN-*.md` when you start a new
> step; keep CLAUDE.md as the index, not the encyclopedia.

Other documentation:

- `collection-01/README.md` — human orientation: repo structure, how to run each step, the
  pipeline overview, status, and the **notebooks table** (what each `.qmd` contains).
- `collection-01/models/README.md` — model output schema + coefficient export details.
- `BACKLOG.md` (repo root) — unscheduled work items, all collections. Read only when asked (above).
- `collection-00/README_00.md` and `collection-00/docs/` — pilot reproduction + ATBD.

## Development environment

- **Python interpreter**: run collection-01 scripts with `$PYTHON` (e.g. `$PYTHON
  collection-01/workflow/01-training_data_export.py …`). `$PYTHON` is machine-local — set by
  `./setup.sh /path/to/store /path/to/venv/bin/python`, which records it in `.local-paths`
  (your shell) and `.claude/settings.local.json` (Claude Code's Bash). Use the project's GEE
  venv; never create a new venv for this repo.
- **GEE project**: `mapbiomas-fire-485203` (hardcoded in `collection-01/utils/constants.py`).
- **GEE accounts — two of them.** Most work runs under the primary personal account
  (`ivanbarbera93@gmail.com`). A few steps run under a **second account,
  `ivanbarbera@comahue-conicet.gob.ar`** — it **owns the Google Drive that Insync syncs into
  `STORE_ROOT`** (`.local-paths`), and it has its own task queue. GEE credentials live in a single file
  (`~/.config/earthengine/credentials`), so switching accounts means swapping that file — keep
  per-account backups (`credentials.gmail`, `credentials.comahue`) and `cp` the one you need
  into place before running. Note the comahue account is registered under the shared
  `mapbiomas-argentina` compute project, **not** `mapbiomas-fire-485203`, so a script that
  hardcodes `C.GEE_PROJECT` may need a project override when run under it.
  - **Prefer passing the credentials file explicitly over swapping it.** `ee.Initialize()` accepts a
    `google.oauth2.credentials.Credentials` built from any file, so both accounts can be used in one
    session, nothing is clobbered, and a half-finished `cp` cannot leave the wrong token resident.
    `workflow/07-burned_area_polygons.py::initialize()` is the pattern (`--credentials` +
    `--project`); copy it rather than re-inventing the swap. Reason to bother: **the GEE task queue
    is per user**, so submitting a long export as the second account starts it immediately instead of
    behind the first account's tasks — the destination asset path is unaffected.
  - **`ee.data.listOperations()` is scoped to the compute project it was initialized against** (and
    is cross-user within it), so anything that tracks tasks submitted by both accounts must poll both
    projects. A one-project watcher reports the other account's task as missing, which is
    indistinguishable from never having submitted it.
- **Run scripts from the repo root**, not from inside `collection-01/` — scripts add
  `collection-01/` to `sys.path` at startup.
- `collection-01/utils/constants.py` is the single source of truth for paths, year range,
  spectral features, the MB reclass table, LR terms, and the MB mosaic band list.

## Technology stack

| Component | Collection 0 | Collection 1 |
|-----------|-------------|-------------|
| GEE processing | JavaScript API | Python API (`earthengine-api`) |
| Model fitting | R (logistic regression) | same (`glmnet`, elastic net) |
| Source imagery | Landsat C2 SR — L5/L7/L8/L9 | same |
| Land cover reference | MapBiomas Argentina LULC | same + MapBiomas annual mosaic |
| Spatial segmentation | SNIC (GEE native) | same (steps 04+) |

## Collection 1 — pipeline at a glance

Numbered steps in `collection-01/workflow/`, each **exporting a GEE asset** so intermediate
stages can be inspected and limits avoided:

1. `01-training_data_export.py` — sample Landsat + prev-year MB mosaic at training points → one asset per fire.
2. `02-model_fitting.R` — fit one elastic-net LR per `veg_fire` class (locally, R), export coefficients for GEE.
3. **Prediction pipeline:** obs-level burn probability → time-series / annual summary (`03-bp_ts_metrics.py`) → SNIC segmentation (`04-snic.py`) → object vectorization & metrics (`05-objects_metrics.R`), plus a manual ash/drought masking pass still to be built.
4. `06-object_model.R` — **object-level fire/non-fire classification, replacing collection-00's
   empirical filter** (which scores accuracy 0.62 / sensitivity 0.50 on our labels). A probit BART
   (`stochtree`) on 20 object metrics, fitted locally in R and applied per fire-year; the fire call
   uses a **per-size-band threshold** from `config/object_model_thresholds.csv`, overridden by a
   collected label where one exists (`fire = fire_tag` if tagged, else `fire_model`). Modes: `fit`,
   `predict [years|all]`, `cv [region|grid K|random K]`. All of it runs **locally on CSVs from step
   05** — no GEE round-trip — and then the **whole scored object set** (all 28 fire-years, every
   object, all 20 predictors) goes back up as one FeatureCollection per fire-year, so a reviewer can
   also find the fires the model missed (docs/06 §12). Labels are prepared by
   `scripts/objects_labels_prep.R`; the threshold by `scripts/objects_threshold.R`; the upload by
   `scripts/objects_upload.py` + `scripts/validate_upload_zips.py`.
   **Never give the model a predictor that names the year or proxies for it** — that leak has been
   found and fixed twice here; docs/06 §4 before touching `PREDICTORS`.
5. **Step 07 — fire-year objects → calendar-year products** (docs/07). Four scripts:
   `07-month_of_burn.py` builds the **month-of-burn ImageCollection** in GEE (one 1-band uint8 image
   per calendar year, 1–12, masked elsewhere) by painting the step-06 objects filtered to
   `fire == 1 & area_ha >= 1` against the SNIC assets; `07-calendar_scars.R` builds the
   **8-connected calendar-year scars** locally (GEE cannot label them — `connectedPixelCount` caps
   at 1024 px); `07-scar_rasters.py` paints the ingested scar FCs into the three size subproducts;
   `07-subproducts.py` derives the **nine remaining subproducts** (monthly/annual burned, both
   `*_coverage`, frequency, accumulated, year-last-fire) from the month collection plus the
   MapBiomas LULC — encodings copied verbatim from the network's reference, do not innovate there.
   The published products cross against **`C.PRODUCT_LULC`** (LULC col-3), which is a *separate*
   constant from **`C.MAPBIOMAS_LULC`** (col-2 v8) on purpose: the latter is the model-side layer
   `veg_fire` — and hence the whole SNIC candidate set — was built from, and must stay frozen.
   Calendar year and month are assigned **per pixel** from `abs_date`, never per object from
   `year_calendar` — that is what makes annual/monthly/scar agree pixel-for-pixel, at the cost of
   splitting a fire that straddles 31 December. **Pin `crs` + `crsTransform` on every export**;
   `scale=30` in EPSG:4326 is a *different* grid.
6. **Step 08 — post-processing to the network's common products.** After step 07 the work stops being
   ours: every MapBiomas Fuego country runs the *same* post-processing to publish the *same* subproducts,
   even though their mapping method differs from ours. **Do not innovate there** — reproduce the
   reference code (see `docs/08-postprocessing.md` and the reference repo below). **But read
   docs/08's header box first:** its §§1–5 describe what *Brazil* does, and several of those stages
   (the LULC mask, the solitary-pixel filter) are already embedded upstream in our pipeline — running
   them again is a no-op at best. docs/07 wins where the two disagree.

See `collection-01/README.md` for the full structure and run commands, and the `docs/` notes
above for per-step design.

## Conventions & gotchas

- **`fire_id`** is a verbatim string whose **only guaranteed structure is the `"fire_"`
  prefix** — the body need not be numeric or two digits (e.g. `"fire_sde10"` alongside
  `"fire_07"`). **Never zero-pad, parse a numeric part, or reconstruct it**; build asset
  tokens with `C.fire_token(fire_id)` (`collection-01/utils/constants.py`) and use the id
  as-is otherwise. Bare `fire_id`s also **repeat across regions** — always key fires
  region-uniquely (`region_fire_id = paste(region, fire_id)`) in any analysis.
- **Asset-based processing**: every workflow step exports an intermediate GEE asset; don't
  collapse steps into one in-memory computation.
- **`oid` is the object key** from step 05 onward: `"<fire_year>_<pid>"`, unique across the whole
  collection, and every join (labels ↔ objects, predictions ↔ geometry, upload ↔ raster) is on it.
  Since the fire-year is embedded, no separate `fire_year` column is written to geometry files.
- **`data/` directory naming** (steps 04–06, all in the Insync store): `snic-rasters/` →
  `objects-raw/` → `objects-labels/`, `objects-pred/`, `objects-analysis/`, plus
  `objects-inspect-cache/` and `objects-upload-cache/`; **`statistics/` (step 09) holds every
  factsheet input and output** — the raw GEE export, the decoded table, the fire counts, the figures
  (collection-01/statistics/docs/statistics.md §1.1). Two rules: it is an **object** (a fire is an
  object; the sparse layer is not an OBIA partition, so "polygons" was retired), and a **`-cache`
  suffix means regenerable** — safe to delete, rebuilt from the CSVs by its launcher. Layout tables:
  docs/05 "Inputs → Outputs" and docs/06 "Files, directories and scripts".
- **Prediction tiling**: all image-based GEE predictions run over the MapBiomas *cartas* grid
  (`projects/mapbiomas-chaco/BASE/cartas-argentina`), not Landsat WRS-2 path/row.
- **Manual masking step**: a hand-made masking pass removes ash/drought false positives and
  needs domain-expert review before vectorization (exact step number is in flux).
- **GEE asset deletions**: the user runs deletions themselves — prepare the script and a
  dry-run, then hand off. Don't delete assets directly.
- **The GEE compute project is SHARED with the whole network — never touch a task you did not
  launch.** `mapbiomas-fire-485203` is used by many people across MapBiomas Fuego, and
  `ee.data.listOperations()` is **project-scoped, not per-account**: it returns *every* user's
  tasks (226 of them in July 2026 — Peru's `MONITOR_01_*`, Bolivia's `GT_Fuego-…`, …). Two rules
  follow. **(1)** Never cancel, restart or reason about an unfamiliar task as if it were ours —
  other countries' teams are mid-run in there. **(2)** **Namespace every task `description`**
  (`bpts_…`, `mob_…`, `arg07d_…`) and never match one by a generic name: an in-flight check that
  matches a bare `annual_burned` can collide with another country's export and silently skip one of
  ours, which is indistinguishable from the resumable-skip working. `destinationUris` would
  disambiguate by asset path but exists only on FINISHED operations. See docs/07 §12.7.

## GEE Code Editor scripts (separate repos)

All GEE JavaScript lives outside this repo. Two Code Editor repos matter — **ours** (writable) and
the **network's reference** (read-only). Files in both have **no extension**.

### Ours — `fuego` (write here)

- **Local**: `/home/ivan/dev/MapBiomas/mapbiomas-arg-fire-gee/`
- **Remote**: `https://earthengine.googlesource.com/users/mapbiomas-arg/fuego` (`mapbiomas-arg/fuego`); pushes to branch `master`

The user does not regularly pull it, so it may be behind. **Always `git pull` before editing,
then edit, then `git push`** — the Code Editor reflects the push on next refresh. The `fuego`
repo is the sole source of truth for GEE JS code; do not keep `.js` copies here.

### The network's reference — `mapbiomas-fire` (READ ONLY, never push)

The MapBiomas Fuego network's own Code Editor repo: the canonical implementation of the **step-08
post-processing and published subproducts** that every country shares, plus their mapping-side
scripts (annual quality mosaics) which we do *not* use.

- **Local**: `/home/ivan/dev/MapBiomas/mapbiomas-latam-fire-gee/`
- **Remote**: `https://earthengine.googlesource.com/users/mapbiomasworkspace1/mapbiomas-fire` (branch `master`)
- **Start at** `4-Collection_anual_final_products/Reference/` — the country folders are adaptations of it.
- **`2-Statistics/`** is the other half people forget: **`toolkit/v03/` is the stage-5 method**
  (collection-01/statistics/docs/statistics.md §2 — we re-implement its shape in Python, in `collection-01/statistics/`; we do **not**
  fork its JavaScript), the six `toDrive-area-*` scripts are the spec of what each network number is
  (collection-01/statistics/docs/statistics.md §9), and `1-Burned_area_products/` holds the comparison series against
  MCD64A1/FireCCI/GABAM.

It is **not ours**: pull to stay current, never commit or push. See
`collection-01/docs/08-postprocessing.md` for a map of the repo and what each script does.

**It is not always cloned** — it was missing on this machine on 11 Sep 2026, and the path above then
looks like any other stale reference. Clone it before reading:

```bash
git clone https://earthengine.googlesource.com/users/mapbiomasworkspace1/mapbiomas-fire \
  /home/ivan/dev/MapBiomas/mapbiomas-latam-fire-gee
```

## Running long scripts

**Always launch anything that runs more than a couple of minutes inside `tmux`** (or another
detached, long-surviving mechanism) so it survives session/terminal closure. This includes not
only local processing but **GEE task-submission scripts that fan out over many tiles** — e.g. a
full-year step-03 launch (`03-bp_ts_metrics.py --year YYYY`) submits one export task per *carta*
(hundreds of `task.start()` round-trips) and takes well over the few-minutes a foreground call
tolerates. Only a single-tile / handful-of-tasks submission is safe to run in the foreground.

```bash
tmux new-session -d -s <name> \
  '$PYTHON -u <script> [args] 2>&1 | tee <logfile>'
```

Reattach with `tmux attach -t <name>`; detach with `Ctrl+B D`. If unsure whether a run is
heavy enough, default to `tmux`.

> Make bulk launchers **idempotent / resumable**: skip tiles that already have a completed asset
> *or* an in-flight (PENDING/RUNNING) task, so a killed-and-rerun launch never duplicates work.

Long local runs that iterate over years follow the same rule via `scripts/run_05_years.sh` (step
05): **one `Rscript` per year** so an OOM kills only that year (flagged `rc=137`), not the whole
batch; skips years whose completion CSV exists; `scripts/mem_monitor.sh` samples RAM alongside and
logs a `WARN` when free memory nears the OOM limit. See `docs/05-object_metrics.md` "Run". Launch
from tmux with an **absolute path** — a detached tmux shell may not start in the repo root.

The same one-process-per-fire-year pattern covers step 06: `run_06_predict.sh` (scoring — stochtree
prediction is single-threaded, so `-j 8`), `run_06_inspect.sh` (QGIS layers — I/O- and memory-bound,
`-j 6`), `run_07_upload_zips.sh` (upload packages, `-j 4`). All three are resumable, biggest-year
first, and log per year to `collection-01/logs/`.

Step 07's local scar build uses the same launcher shape in **two passes**
(`scripts/run_07_scars.sh pixels|scars`): `pixels` is one process per **fire-year** (28, `-j 5`,
tile-read bound, ~6-9 min each), `scars` is one process per **calendar year** (27, `-j 2` with
`OBJ_CORES=6`, dominated by the per-scar vectorize). Run `pixels` to completion first — a calendar
year needs **both** its fire-years. Memory, not CPU, is the binding constraint on `scars`: it holds
a whole calendar year's pixel set (up to ~100 M px) through the union-find, so prefer fewer
concurrent years with more `OBJ_CORES` each — `mclapply` forks share the parent's table
copy-on-write, which separate year processes do not. Gate the packages with
`scripts/validate_scar_zips.py` before any manual ingest.
