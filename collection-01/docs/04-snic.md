# 04 — SNIC 3D approximation (spatio-temporal burned-area segmentation)

Step 04 grows the per-pixel burn-probability metrics from step 03 (`bpts`) into **spatial
objects** (fire scars), approximating a full space × space × time clustering with per-year 2D
SNIC plus temporal safeguards (§1). Downstream metrics, manual review, and the final products
then operate on segments rather than pixels.

**Status: design in progress.** This is the living design record for step 04, matured from
Iván's notes (`misc/SNIC 3D notes.odt`). Code stubs: `workflow/04-snic.py` (segmentation), with
the object-based follow-on in `workflow/05-objects_metrics.py` and
`workflow/06-object_filtering.py`. **Read `docs/03-bpts.md` first** — step 04 consumes the
burn-probability time-series metrics produced there (see also `03-bpts.md §10`: fire-regions as
unions of cartas, no edge buffer needed, watch SNIC's internal ~256-px tile seams).

> This doc captures decisions **and open questions**. Items marked **[OPEN]** still need Iván's
> call before implementation; **[DECIDED]** items reflect the current agreed direction and can
> still be revisited.

---

## 1. The ideal, and why we approximate it

The **ideal** algorithm would cluster the full Landsat archive in 3D (space × space × time),
directly deciding *which pixels and dates* are burned and grouping them into **fire events**.
That is out of reach here: it needs custom clustering code and the full Landsat stack exported
*out* of GEE — too expensive to run at country scale.

So step 04 is an **approximation** built from the annual step-03 metrics:

- step 03 already reduces each pixel's Landsat probability series to **annual** change/magnitude
  metrics, from which seeds and candidates are derived (see "Getting started" below and §2 —
  treated as a solved upstream step);
- step 04 runs **SNIC in 2D space, per year**, and approximates the temporal (3rd) dimension
  with a **neighbour-year window** plus **date-based firebreaks**.

Two structural problems the approximation must handle:

1. **Cross-year fires.** A fire straddling the New Year is bisected by the annual images. SNIC
   run on year `y` alone cannot exploit the spatial continuity of a scar whose other half lives
   in year `y−1` (or `y+1`).
2. **Recurring fire.** A single pixel can burn in more than one year; the representation must
   not confuse two fires a year apart for one.

**Key reframing (resolves several of the notes' doubts).** Step-03 padding already *attributes*
every pixel to the correct year: the delta argmax is restricted to focal-year observations and
`date_post` is guaranteed to fall inside the focal year. So cross-year fires are **not an
attribution problem** — each pixel is already dated to the right year. What's missing is purely
**spatial**: SNIC on year `y` won't connect the Dec-`y−1` portion of a scar to its Jan-`y`
portion. Therefore the neighbour-year window exists to lend year `y`'s segmentation the
neighbour-year **seeds/pixels** of a boundary-crossing scar — not to re-date anything.

---

## Getting started — delineate regions, tune seeds & candidates (do this first)

Before any of the algorithm design below, two hands-on GEE tools set up its inputs: the
**fire-regions** SNIC runs over (§7.3), and the **seed/candidate thresholds** it grows from (the
`candseed` surface §2 treats as given). Both live in the **fuego** GEE repo (not this one), under
`collection-01/visualization-misc/`; see CLAUDE.md → "GEE Code Editor scripts" for the repo
location and the pull/edit/push workflow. Their reusable pieces live in the fuego repo's
`collection-01/utils/` (below).

### Delineate fire-regions — `snic_regions_definition`

Paints every pixel that was **ever a seed (red) or candidate (orange) in any year**
(`bpts.map(...).max()`), other pixels masked, with the carta grid drawn as borders-only on top.
Used by eye to trace the fire-region footprints (unions of cartas) that SNIC then runs over.
Deliberately **no `reproject`** (pan-the-country overview) — unlike `explore_snic_IB`, which pins
to 30 m for exact segmentation on a small ROI.

Use case: a **fast, country-wide, deliberately coarse (non-30 m)** look at where fire happened,
so you can scan the whole country and pick candidate **test ROIs** — which then go into
`explore_snic_IB` for the exact 30 m, scale-stable tuning. Thresholds here are a starting point;
finalise them in `explore_snic_IB`.

### Tune seeds & candidates — `explore_snic_IB`

Tunes the SNIC **seed** and **candidate** thresholds *on the fly* (no export), while avoiding
SNIC's scale-dependence. For a chosen year it: merges the two bpts collections (Argentina + the
mapbiomas-chaco 1999–2009 overflow), filters to the year, mosaics the tiles over a ROI, **decodes
the 7 probability bands to probability scale** (÷10000; the day / DOY / count bands are left
as-is), then thresholds seeds + candidates and runs SNIC. This is a **simplified single-year
SNIC for threshold tuning** — the full production per-year algorithm (gap-fill + firebreaks +
supervised SNIC) is §3–§6.

Key design points:

- **Scale-independence.** SNIC and `connectedPixelCount` are neighborhood ops, so the
  interactive map would otherwise evaluate them at the zoom-pyramid scale (result changes as you
  zoom). The decoded mosaic is `reproject()`-ed to the assets' native 30 m grid **before** any
  neighborhood op, and the SNIC output is reprojected too — pinning the whole computation to 30 m
  at any zoom. (Keep the ROI modest; a 30 m-pinned neighborhood over a whole carta can hit
  interactive memory/timeout limits.)
- **Seeds (strict) vs candidates (loose)**, adapted from the col-0 method
  (`collection-00/misc/snic_visualization` in the GEE repo). Seeds use high magnitude (`pmax3`) +
  change (`delta3_peak`) + persistence (`minfore3_peak`); candidates use the loose versions and
  define the footprint SNIC may grow into. A `connectedPixelCount` filter **drops seed components
  of ≤ P pixels (P = 5)** — so a fire-cluster must be seeded by ≥ 6 connected pixels — which
  removes a lot of speckle noise. `burned` = SNIC clusters that contain a seed. All thresholds
  are tunable variables at the top of the script.
- **Previous-year land cover.** Displays the `y−1` raw MapBiomas classes and the `veg_fire`
  classes (the exact land-cover context step 03 used), with a compact legend of the 25 `veg_fire`
  classes.
- **NBR + NBR2 series.** A cheap NBR/NBR2-only Landsat collection (`y−1 … y+1`) added at opacity
  0 — invisible on the map, but the Inspector charts it as a time series on click.

The thresholds settled here produce the `candseed ∈ {0,1,2}` surface that the algorithm design
(§2 onward) takes as its input.

### Ground seeds & candidates in the burned/unburned data — [DECIDED: local period-based; thresholds OPEN]

`explore_snic_IB` tunes the thresholds *by eye*. To **ground them in data** — and answer whether a
**second (annual) model** is needed (col-0 had one) — we compare the `bpts` metrics of burned vs
unburned **training points**. col-0 decisions rested mostly on highest 5-med prob and highest 5-med
delta (a simple empirical tree could suffice); this study tests that directly.

**The deciding question.** If a **shallow tree (depth ≤3) on 3–4 `bpts` metrics** reaches
near-ceiling burned/unburned separation, the empirical-tree route is justified and **no second
model is needed**. A clear plateau is the evidence *for* a model. A GEE random forest stays a
**fallback**, not the plan — it would reintroduce the extra deployed model we're avoiding (a
resolved point table is a one-liner to upload as a training FC asset if RF ever graduates).

**Chosen approach — recompute the metrics LOCALLY from the training observations (col-0 style),
period-based** (revised 2026-07-06, superseding an earlier "sample the exported annual `bpts` at the
points" plan). Rather than sample the GEE `bpts` images, we recompute the burn-probability
time-series metrics directly from the already-downloaded `training_observations_<region>_v1.csv`.
Why this is cleaner:

- **Runs now, on all data.** No wait for the still-exporting `bpts`, no per-fire export-completeness
  gate — every training fire in every downloaded region is usable immediately.
- **Dissolves the two hard problems.** Because the metric window is the fire's **observation period**
  (not a calendar year), **cross-year attribution disappears** (the series just spans Dec→Jan on
  cross-year-safe day-numbers) and **the annual-vs-window contamination disappears** (an unburned
  point's series only covers its validated window, so a different-season fire elsewhere in the year
  simply isn't in it — no `date_post` gate needed). Both the straddle-year handling and the
  contamination gate an earlier draft designed are **no longer required**.
- **Reuses validated code.** `scripts/ts_predict_functions.R:predict_class()` already computes
  per-obs burn probability from raw-scale coefficients (verified to reproduce glmnet to ~1e-14); we
  point it at the **deployed P050** coefficients (reconstructed from the git-tracked
  `models/P050/*.csv`, so probabilities match production).
- **`veg_fire` stratification is free** (from `mb_class_raw` + region via `config/veg_fire_remap.csv`).

Decisions taken this session (2026-07-06):

- **Recover trimmed obs (don't just use `fit == TRUE`).** `data_cleaning.R`'s `fit == FALSE` mostly
  trims post-fire obs for *label* quality, but those are valid observations and dropping them starves
  the K=3 `minfore` window (a scar's high-prob obs sit at the series end → `pmax3`/`delta3` wrongly
  collapse to ~0). So the metric series uses **all obs of "usable" points** — points with ≥ 1
  `fit == TRUE` obs, which still honours whole exclusions (`drop_fire`, fully-dropped unburned points).
  The label is the point-level `class`. *(Verified on BA fire_12: recovery lifts burned points reaching
  ≥ 3 post-fire obs from 94 % → 100 %.)*
- **One `veg_fire` per point = production's focal-year rule (`03-bpts §2.1, §3.4`).** Production applies
  a *single* `veg_fire = MapBiomas(fire_year−1)` to the whole focal-year series (incl. padding obs),
  **not** each obs's own prev-year class. So we assign the class from the point's obs in
  `fire_year = year(post_lwr)` (its `mb_class_raw` = MB(fire_year−1)) and apply that one class model to
  the whole series. *(This was the decisive fix: without it, points whose prev-year MB class changed
  between the pre- and post-fire years get the wrong model on half the series and their `delta3`
  diverges wildly — bidirectionally — from production.)*
- **Two-part min-obs gate.** (a) The step-03 padded-array rule (`03-bpts §3.5`): ≥ 6 obs for the K=3
  family, ≥ 4 for K=2. (b) **K=3 also needs ≥ 3 *post-fire* obs** (`date ≥ post_lwr`) to see sustained
  burn; burned points below that are genuinely fast-recovery veg → **NA the K=3 family** (K=2 is the
  right metric there) so they don't pollute the seed-metric distribution with false lows.
- **Annualised density `n`.** No calendar year to count over, so annualise the point's obs rate:
  `n = round(n_obs / days_elapsed × 365)` (`days_elapsed` = last−first obs day). Extrapolates a
  short period up and normalises a long one down to a per-year density comparable to production `n`.
- **What to look at.** (1) per-metric ECDF/violin, burned vs unburned, for the seed trio
  (`pmax3`,`delta3_peak`,`minfore3_peak`) and the loose K=2 candidate metrics; (2) commission/omission
  vs threshold, **read from two ends** — **seeds optimise precision** (few unburned above the cut;
  seeds only need part of a scar, SNIC grows the rest), **candidates optimise recall** (few burned
  below the cut; candidates are the footprint SNIC grows into); (3) 2D scatter + the shallow CART;
  (4) **stratify by region / veg_fire / `n`** — separability drifts (grassland recovers fast, forest
  slow; sparse series overlap more), so check whether one global set holds.
- **Transfer validation — a single-fire hard-check (DONE, PASS).** The metrics are period-based;
  production applies the cuts to **year-based** `bpts`. Hard-check ONE fire that burns **mid-year in an
  already-exported year** (`scripts/test-bp_ts_metrics_local.R`; find candidates with
  `bp_ts_metrics_local_train.R --midyear`): compute locally, sample the exported image at the same
  points, compare. **Result on BA fire_12 (Sept 2016, 337 burned pts):** `date_post` agrees to a median
  of **1 day** (100 % within 30 d → *same event detected*), `delta3`/`pmax3` median |Δ| ≈ **0.011**,
  **r ≈ 0.88**, ~88 % within 0.15. The residual per-point scatter is **bidirectional and unbiased** —
  the inherent effect of the truncated/sparser training window feeding `minfore3`/`maxback3` different
  neighbour obs than production's full-year+padding series (not removable from training data alone).
  Since thresholds are calibrated on the **distribution** (not per-point values), this is acceptable;
  final cuts are still confirmed against production (`explore_snic_IB` / the export).

**Tooling (calibration, so `scripts/` + a notebook + `config/`, NOT `workflow/`** — produces
hand-editable *numbers*, not a consumed pipeline asset; mirrors the term-pruning scripts+notebook→
`config/`/`models/` shape):

- `scripts/bp_ts_metrics_local_train.R` — the local recompute: recover usable-point obs → focal-year
  P050 `predict_class` → per-point period metrics + K-family gates + annualised `n` + `veg_fire` →
  `data/annual_data_resolved.csv` (145 k points). Named to mirror `workflow/03-bp_ts_metrics.py`; has
  a `--midyear` helper listing hard-check candidate fires.
- `scripts/test-bp_ts_metrics_local.R` — the single mid-year-fire hard-check against the exported
  image.
- `scripts/annual_data_download.py` — **retained as the validation sampler** (pulls exported
  year-based `bpts` at a fire's points for the hard-check); no longer the primary path.
- `notebooks/snic_candidates_seeds_definition.qmd` — distributions, commission/omission curves,
  shallow CART, region/veg/`n` stratification.
- `config/snic_seed_candidate_thresholds.csv` — the hand-editable seed/candidate cuts the step-04
  SNIC reads; starts as col-0-adapted PLACEHOLDERs, finalised from the notebook. **Manual override is
  first-class**: if data-based thresholds fail out-of-sample, edit this file, no code change.

> **[OPEN]** the threshold *values* (await the notebook), whether one global set holds or region/veg
> stratification is needed, and the outcome of the single-fire hard-check (magnitude agreement
> confirms period→year transfer).

### [2026-07-07] Notebook results, the K decision, and how to follow up

`notebooks/snic_candidates_seeds_definition.qmd` now implements the full study (rendered HTML
alongside it); it added the **n-breakpoint sweep** (`§sec-nbreak`) and the **initial 5-value
table** (`§sec-initial`). What we learned and decided:

- **The candseed design is `deltaK_peak` thresholds with K chosen *per pixel* by `(veg_fire, n)`.**
  Since `deltaK_peak = minforeK − maxbackK` and `minforeK = min` over **K consecutive** obs, the
  metric *already bakes K-persistence in* — so choosing K = choosing how much persistence to
  demand, which is exactly what recovery-speed (`veg_fire`) and sampling density (`n`) should
  govern. `pmax`/`minfore` are **subsumed** → dropped. Only `deltaK_peak` remains.
- **The NA artifact — read this before re-running any comparison.** On the training points K=2
  (`delta2`) out-ranks K=3 (`delta3`) on essentially every axis (overall AUC, per-`n`-bin, 22/23
  veg, and the precision end) — **but only when K=3's missing values are scored as misses**
  (`NA-as-worst`: `delta3 = NA` for a burned pixel with <3 post-fire obs = a missed detection).
  Dropping them (`na.omit`) makes K=3 look *better* — that was an evaluation artifact that fooled
  an earlier pass. Under `na.omit` K=3 ties/beats K=2 at high `n`; the whole "K=2 wins" is the NA
  penalty. **So K=3's cost is recall (the NA holes); its benefit is commission-at-scale**
  (persistence rejecting the `~0.5` background noise Iván saw on the maps), which a **44 %-burned,
  hard-negative point set structurally cannot measure.** The AUC therefore only bounds the *safe
  K=3 envelope* (how much K=3 recall tolerates); **whether to actually use K=3 for noise rejection
  is a maps call** (`explore_snic_IB`).
- **n-breakpoint sweep.** Per veg, route `n ≥ break → K3`, `n < break → K2`; score with the
  **weighted per-subgroup AUC** (`AUC(delta2)` on the low-`n` group + `AUC(delta3)` on the high-`n`
  group, weighted by N — scale-free, `NA-as-worst`). `interior_gain ≤ 0.02` for **all** veg → no
  recall crossover; read the curve as the **max-K3 envelope**, not proof K=3 wins. `n_break` = the
  knee (lowest break within 0.01 AUC of all-K=2). **Low-`n` is only ~0.5 % of training data**, so
  the breakpoint is principle-set at the low edge of the trainable range; the only adaptive move
  with support below that is **K=2→K=1** for the sparse early years (1999–2001).
- **Initial thresholds — base-rate-invariant so they transfer to ~1 %-burned deployment.**
  `candidate` = highest threshold with **omission ≤ 5 %** (within-burned recall bar); `seed` =
  lowest with **FPR ≤ 2 %** (within-unburned specificity — the transfer-safe replacement for a raw
  commission bar, which is base-rate-dependent). Order them `cand = min`, `seed = max` so seed ⊂
  candidate (separable veg meet both bars over a wide band and would otherwise invert). Calibrated
  on **full per-veg data** → **`n_break`-independent**: slide the breakpoint on the maps, keep the
  same delta cuts. Output written to **`data/snic_thresholds_initial_by_veg.csv`**.

**Follow-up — resume here (all [OPEN]):**

1. **5-value vs 4-value structure — decide first.** `K3_cand` is **NA for ~15/23 veg** (K=3 can't
   meet the 95 %-recall candidate bar), while `K3_seed` exists for all. The data leans **4-value**:
   *candidate always K=2* (broadest footprint, no persistence hole) and *seed pixel-wise K*
   (`K3_seed` for `n ≥ break`, `K2_seed` below — the persistent precision core). The 5-value form
   still works (K3_cand falls back to K2_cand where NA); pick one.
2. **Merge veg into 2–3 recovery groups by the sweep, not by name** — the behaviour cuts across
   prefixes (`forest_pampa` steep/K2-only vs `forest_pat`/`forest_ba` flat/K3-safe; `grassland_pat`
   = arid steppe = slow). The `k3na` rate per veg is a clean recovery-speed proxy here.
3. **`pasture_chaco`** is barely separable (AUC ≈ 0.69) even at best — special handling / manual
   review, or accept weak cuts.
4. **Write the chosen thresholds to config + validate on maps.** Transcribe into
   `config/snic_seed_candidate_thresholds.csv` (schema change → per-veg) and the fuego JS, then use
   **`explore_snic_IB`** to answer the one thing the points can't: does K=3 actually reject the
   `~0.5` background commission, and nudge `n_break` by eye. Remember `connected_min_px ≥ 6` +
   supervised SNIC seed-growing are the real scale noise suppressors, not the delta cut alone.

### [2026-07-07 pm → 2026-07-08 plan] Map-based pivot, tooling built, next session

**The data route is shelved.** The per-veg thresholds calibrated from the training points
(`data/snic_thresholds_initial_by_veg.csv`) **failed out of sample** — on unseen ground they gave
tiny scars, bad behaviour, and speckle "burned" patches all over **non-vegetated** areas. So we stop
calibrating cuts from the points and **move to map-based (by-eye) thresholds**; follow-up items 1–4
above are parked (the CSV stays only as a starting reference, not the plan).

**Tooling built & pushed** (fuego repo, `visualization-misc/explore_snic_IB-02`; `-01` keeps the old
notebook-optima version for reference):

- **Global hand-set delta cuts** (`G_K2/K3_CAND/SEED`) that move all veg at once; `n_break` stays
  per-veg (K2-vs-K3 selector only); each `VEG_TABLE` delta cell is an **override** (`null` = global,
  a number = just that veg). Per-pixel `K = n ≥ n_break ? 3 : 2`.
- **Seed jumpgap filter** — reject seeds where `min(jumpgap2, jumpgap3) > S_GAP` (adaptive: 60 d if
  `n ≥ 20`, else 90 d); plus the `connected_min_px` speck drop and supervised SNIC.
- **Country-wide context layers** (per-pixel → unprojected, pan everywhere): delta2/delta3/n scan,
  bpts inspector, veg_fire, MapBiomas classes. **ROI + 30 m only** for the neighborhood/segmentation
  layers (candidate/seed/SNIC/burned) and the Landsat NBR series.
- **Independent "did it actually burn?" references (OFF by default):** MODIS `MCD64A1` + VIIRS
  `VNP64A1` focal-year burned masks (orange; ~500 m, corroborate not delineate), and the **min-NBR
  false-color mosaic** (`swir2/nir/red`, `qualityMosaic('-nbr')` — the training-point composite),
  built from the same ROI-filtered Landsat collection as the time-series; heavy → turn on when
  zoomed in.

**Tomorrow (2026-07-08) — do both [OPEN]:**

1. **Review the SNIC output on the fly** in `explore_snic_IB-02`: tune the global (and per-veg
   override) delta cuts **by eye**, cross-checking each scar against the **min-NBR false-color**
   mosaic and the **MODIS/VIIRS** masks to separate real burns from commission. This is the call the
   points can't make — whether K=3 actually rejects the ~0.5 background, and where a global cut holds
   vs needs a per-veg override.
2. **Define the SNIC processing regions** (§7.3) — trace the contiguous carta groups that don't
   split high-fire areas, using `snic_regions_definition` (ever-seed/candidate paint) alongside the
   new reference layers. Feeds the §7.3 [OPEN] region definition + the tile-boundary diff test.

### Shared GEE utils

To keep the scripts small, the reusable pieces live in the fuego repo's `collection-01/utils/`:

- `functions.js`: `vegFireImage(year)` / `mbClassImage(year)` — a faithful JS port of Python
  `functions.py:veg_fire_image` (`region_id·100 + mb_class → veg_fire`, prev-year, unmapped →
  25); `vegFireLegend(nCols)` — the compact class legend; `addNBR_NBR2` — NBR/NBR2-only index.
- `constants.js`: the LULC/region asset ids, the canonical `REGION_CLASS_FROM` / `VEG_FIRE_TO`
  remap, `VEG_FIRE_NAMES`, `VEG_FIRE_PALETTE`, `MB_LULC_PALETTE`.

> **Sync caveat.** Those `constants.js` remap arrays are a **hand copy** of this repo's
> `config/veg_fire_remap.csv` (the single source of truth) — there is no automatic sync between
> the two repos. If that CSV is regenerated with class changes, update the fuego `constants.js`
> arrays to match. The coupling is flagged in both places
> (`config/veg_fire_remap_metadata.txt` → "MANUAL DOWNSTREAM COPY" and a SYNC WARNING comment in
> `constants.js`).

---

## 2. Inputs, outputs, terminology

**Input** — an annual `ImageCollection`, **one image per year**, each carrying:

- `candseed ∈ {0, 1, 2}` — `0` = no fire, `1` = candidate, `2` = seed. In practice `0` can be
  masked; we keep it unmasked in the notation. **Seeds/candidates are derived upstream** from the
  step-03 bands (`delta{2,3}_peak`, `minfore/pmax`, `n`, …) — the thresholds tuned in
  `explore_snic_IB` and **grounded in the burned/unburned training-point distributions** (see
  "Getting started" → *Ground seeds & candidates in the data*, and
  `config/snic_seed_candidate_thresholds.csv`); *that derivation is out of scope for the algorithm
  sections* — step 04 takes `candseed` as given.
- a **burn date** per pixel (from step-03 `date_post{2,3}`), and
- the observation density `n` (step-03 quality channel), used to make `D` adaptive (§5).

**Output** — an **annual burned-area mask** (one per year). The SNIC *cluster ids themselves are
discarded*: we only need burned / not-burned. The mask is vectorized in step 05.

### 2.1 Dates MUST be absolute, not DOY — [DECIDED]

Step-03 `date_post` is **day-of-year (1–366) within the focal year**. Any cross-year date
arithmetic on raw DOY is wrong: a Dec-`y−1` pixel (DOY ≈ 355) and a Jan-`y` pixel (DOY ≈ 10) are
~20 days apart in reality but ~345 apart in DOY. Before any Δdate comparison (mosaic tiebreaks,
firebreaks, overlap-merge), convert to an **absolute integer day count** — days since a fixed
epoch — using each annual image's `year` property:

```
abs_date = days_since_epoch(year, date_post)     # exact whole-day counts, cross-year safe
```

This mirrors step-03's own "day-number" philosophy (§3.2 of `03-bpts.md`), where all
persistence/width metrics are exact whole-day differences that stay correct across the year
boundary. Keep `abs_date` as an int band alongside `candseed` throughout step 04.

---

## 3. Per-year algorithm (overview)

For each focal year `y` — **backward-only** window (§4 explains why we look at `y−1` only):

1. **Gap-fill** the focal `candseed` (+ `abs_date`) surface from the *previous* year's
   near-boundary pixels (§4).
2. **Firebreaks** — mask every pixel whose `abs_date` differs from a neighbour by > `D`, so
   8-connected SNIC physically cannot grow across a temporal discontinuity (§5).
3. **Supervised SNIC** — region-growing **from seeds** through connected candidates over the
   masked candseed surface; seedless candidate islands are dropped, and the burned mask is the
   union of the seed-grown regions (§6). Post-SNIC gap-closing and object metrics follow in
   steps 05–06.

---

## 4. Backward-only gap-fill of the previous year — [DECIDED]

**Goal, stated precisely.** Give year `y`'s segmentation the neighbour-year pixels of a
boundary-crossing scar, so a focal-year fragment (often mostly *candidates*) is spatially joined
to the previous year's seeds and survives the seed filter — **without** importing separate
neighbour-year fires. The **firebreak (§5)** enforces the "same fire vs different fire" split, so
this step just needs to *supply* the pixels.

### 4.1 Look **backward only** (previous year), not both neighbours

Rather than a symmetric `y−1 … y+1` mosaic (which raises "what if both neighbours have
`candseed > 0` here?"), each focal year looks **only at `y−1`**, and only its **near-boundary
(late-year) pixels** — Iván's "half year" back. Rationale:

- **The failure case is negligible.** Backward-only mis-handles a fire only if it *starts* in the
  first half of `y−1` and is still burning past Jan 1 of `y` — a fire duration of >6 months,
  which does not occur.
- **It matches Argentine fire seasonality.** Summer seasons are dominated by **Jan–March** fires;
  burned area from October onward is smaller. Spring seasons (after a dry winter) **end in
  January**. So the meaningful cross-year spill is *late `y−1` → early `y`*, which the later year
  reaching back captures exactly.
- **It removes the collision tiebreak entirely** — with a single neighbour there is never a
  both-neighbours-burned pixel to arbitrate.

### 4.2 The gap-fill rule — [DECIDED]

- At every pixel where **focal `candseed > 0`**: keep the **focal** `candseed` and focal
  `abs_date` (focal wins — that pixel belongs to year `y`).
- Where **focal `candseed = 0`**: **fill** from `y−1` where `candseed > 0` **and** `abs_date` is
  within ~`D` of the year boundary (late `y−1`), carrying `y−1`'s `candseed` and `abs_date`.

Result: one `candseed` band + one `abs_date` band. The late-`y−1` seeds land at locations where
focal was 0, adjacent to the focal candidates; the firebreak (§5) then keeps them together (dates
within `D`) or separates them (a genuinely older `y−1` fire, Δ > `D`), and SNIC joins what
survives.

### 4.3 Duplication is unavoidable — deferred to the overlap-merge

A scar crossing `y−1 → y` is processed in **both** annual runs: year `y` pulls in the late-`y−1`
half via gap-fill; year `y−1`'s own run already produced (at least) that half as focal. There is
**no way to avoid this duplication** inside an annual-segmentation approximation — only true 3D
clustering would. It is reconciled once, in the **cross-year overlap-merge (§7)**, after each
polygon's year is re-assigned from its `date_mode`. Do not try to prevent it earlier.

---

## 5. Dating firebreaks — [DECIDED: hard mask]

Before SNIC, **mask every pixel whose `abs_date` differs from any of its 8 neighbours (that are
themselves `candseed > 0`) by more than `D`.** The masked pixels are no longer candidate/seed, so
they form a ≥1-px seam that **8-connected SNIC cannot cross** — a hard firebreak between two
temporally distinct fires that merely touch in space. This replaces any soft "date as a SNIC
feature band" idea: the point is a barrier, not a nudge.

- **Two-sided seam.** Masking a pixel when *any* neighbour exceeds `D` erodes the boundary on
  **both** sides of a jump, guaranteeing a gap wide enough to block 8-connectivity. It costs a
  thin rind of real candidate pixels at genuine event boundaries — acceptable.
- **Within one fire it never fires.** Adjacent pixels of a single spreading fire differ by a few
  days; only a per-pixel-step date jump > `D` (an abrupt discontinuity = different event) trips
  it. So `D` must exceed the plausible within-fire adjacent-pixel date gradient (easily true for
  `D ~ 60 d`).
- **Implementation — [DECIDED]:** **shift `abs_date` by one pixel in each of the 8 neighbour
  directions**, take the absolute diff against the focal pixel → an **8-band diff image**, reduce
  to its **per-pixel max**, and **mask where max > `D`**. This masks *both* pixels of every
  offending adjacency (each is the other's neighbour), giving the two-sided ≥2 px seam. Compute
  over the `candseed > 0` domain only, so no-fire/masked neighbours contribute no spurious date.
  (In GEE the shift is `abs_date` displaced by the 8 offsets; the same seam can be recomputed
  identically in R — see §6.1's `fb`.)

**`D` is adaptive on density `n`** — [DECIDED intent, form OPEN]. Dense images (`n` high) resolve
transitions well → `D` can be **small** (tighter separation, less downstream redundancy); sparse
→ widen `D`. The concrete `D = f(n)` is **[OPEN]** and is reused by the overlap-merge (§7).

---

## 6. Supervised SNIC — seed-grown region growing — [DECIDED]

SNIC here is a **supervised region-growing** step ("supervised SNIC", Iván's term) — **not** mere
connectedness and **not** a feature clusterer. It runs on the firebreak-masked candseed surface
with the **seed pixels supplied as SNIC seeds**, and grows clusters **from seeds through
spatially connected candidates**:

- **Isolated candidates are dropped by SNIC itself.** A candidate blob not reachable from any
  seed gets no cluster and falls out of the mask. So SNIC *is* the seed/candidate classifier
  (burned = candidate connected to a seed) — this is **not** deferred to a downstream `seed_mean`
  filter (`seed_mean` in §7 is only a secondary object-quality metric, not what removes seedless
  islands).
- We **discard the cluster ids** and keep the **burned mask** = union of the seed-grown regions.
- Because the firebreak seam (§5) is already masked out of the input, a seed **cannot grow across
  a temporal discontinuity** — growth is confined within firebreak-bounded regions.

**No cross-tile / cross-split label concern.** Since the cluster ids are discarded and R
relabels the mask globally with `patches()` (§6.1, §7.3), it does not matter that SNIC ids are
only unique within one run/tile — the export can be split and re-mosaicked freely (§7.3–§7.5).

**Why not GEE connected-components (and why SNIC stays in GEE).** Native object labeling
(`connectedComponents` / `connectedPixelCount`) caps objects at **≤1024 pixels** — useless for
real fire scars, which are far larger — and it is **unsupervised**, so it would keep seedless
candidate islands that supervised SNIC correctly discards. Both reasons keep SNIC in GEE; it is
not replaceable by connected-components.

**The SNIC mask is also what makes the download sparse** — only seed-grown (burned) pixels
survive; everything else is masked and, with a compressed export (§7.2), never materializes.

Workflow split: **04** = firebreak + SNIC → objects mask; **05** = vectorize + per-polygon
metrics (`seed_mean`, `date_mode`); **06** = filtering + de-dup.

### 6.1 Grouping nearby patches (gap-closing) — the terra replacement for Col-0's double vectorization

Connected SNIC patches still **fragment a single fire** wherever a cloud/no-data gap, a thin
unburned strip, or the firebreak erosion itself leaves a 1–2 px break. These must be **grouped
into one object** — *unless a firebreak lies between them* (that gap is a deliberate temporal
separation, not a fragmentation).

**What Col-0 did** (`collection-00/workflow/06-spatial_segmentation-objects.js`): a
raster→vector→raster→vector "closing": `focalMax(radius=1)` to a **wider** context mask →
vectorize it for group ids → stamp the id onto the **strict** SNIC pixels via
`reduceRegions(max)` → re-vectorize → dissolve. It worked but was awkward (no native
connected-component labeler in GEE), and it had **no firebreak awareness** — merging was
unconditional.

**Col-1, in terra** — the clean raster-native version, done **once**, respecting firebreaks. The
key correction to a plain "dilate → clump → mask back": use a **barrier-constrained (geodesic)
dilation**, or a naive `focalMax` will **jump the ~2 px firebreak seam** and re-merge two
temporally distinct fires. Block the dilation *at* firebreak pixels each step:

```r
# per tile: burn (0/1), abs_date, fb (firebreak seam, 1/0 — recomputed in R, see below)
d <- burn
for (i in 1:r) {                       # r = 1 or 2 px gap tolerance
  d <- focal(d, w = 3, fun = max, na.policy = "omit")
  d <- d * (fb == 0)                    # firebreak = impassable wall
}
grp <- patches(d, directions = 8, zeroAsNA = TRUE)   # connected components (raster::clump → terra::patches)
id  <- mask(grp, burn, maskvalue = 0)                # stamp group id back onto strict burn
# then vectorize ONCE and dissolve by id
```

Because the 8-shift firebreak masks pixels on **both** sides of a date jump, the wall is ≥2 px
and topologically closed, so the geodesic dilation flows through genuine gaps but **cannot cross
a firebreak** — exactly "merge patches 1–2 px apart unless a firebreak is between them."

**Tooling — [DECIDED]:** terra. C++ is overkill (terra's `focal`/`patches` are already compiled;
per-tile burned data is sparse). Python (`scipy.ndimage.label`, `skimage.morphology`) is equally
capable but R keeps one language for the vector de-dup (§7) and matches the repo's existing R
step.

**Export requirement:** R must know the firebreak locations. Cleanest is to export `abs_date` on
**all** candseed pixels (pre-firebreak) so R **recomputes** the 8-shift firebreak itself —
single source of truth, and R then both applies it (mask) and reuses it as the dilation wall.

### 6.2 [RESOLVED] terra does *post-SNIC grouping*, it does not replace SNIC

An earlier draft floated replacing SNIC with `terra::patches()`. **Rejected** — the two do
different jobs. Supervised SNIC (§6) *grows regions from seeds and drops seedless candidates*;
`patches()` / `connectedComponents` are *unsupervised* connected-components that would keep those
islands and (in GEE) cap objects at ≤1024 px. terra's role is strictly the **post-SNIC
gap-closing** of §6.1 — merging seed-grown regions that a small gap fragmented — operating on the
SNIC burned mask, **downstream** of the seed-growing, never in place of it.

---

## 7. Object-based processing (steps 05–06) — vector post-processing likely in R

From the notes; tightly coupled to the SNIC design (it's where cross-year fires are finally
reunited).

1. **Vectorize** each annual objects mask to polygons.
2. **Per-object metrics** — `seed_mean` (seed proportion — the real fake-fire discriminator),
   `date_mode` (modal burn date), size, and shape/sparseness. **Computed raster-native with
   `terra::zonal()` on the patch-id raster, *before* vectorizing — not with vector
   `reduceRegions`/`extract` (§7.6).**
3. **Filter objects** — remove fake fires — via an **empirical decision tree** (as in Col-0) or
   an **object-level model**. **[OPEN]** which. A **permissive SNIC is deliberate** — recall is
   protected at segmentation and precision is recovered here (§7.6).
4. **Re-assign year** = `year(date_mode)` (a polygon's true year is its modal burn date's year,
   which can differ from the annual run it came from — this is what makes the backward gap-fill
   of §4 consistent).
5. **De-duplicate** (using updated years):
   - **Same-year overlaps:** among intersecting polygons in the same year, if Δ`date_mode` < `D`
     **and** IoU > **0.2** → **merge**; else keep the **larger**. **[OPEN]** confirm 0.2.
   - **Backward (previous-year) overlaps:** same rule against `y−1`. **Optimization:** compare
     only near-boundary polygons — late-`y` vs early-`y−1` — not all pairs.

### 7.1 Duplication cost and the case for R (`sf`/`terra`) — [OPEN, leaning to R]

Duplication is unavoidable (§4.3), so a de-dup pass is mandatory. But **vector–vector topology in
GEE is its weak spot**: spatial joins and per-feature `intersection()/area()` (needed for IoU)
are slow and routinely hit *"computation timed out" / "user memory exceeded"* at scale, and
**fires also cross carta tiles**, so de-dup is an inherently *global* vector operation that GEE
tiling fights against.

Recommended division of labour:

- **GEE (raster):** through step 04 — the annual **objects masks** (+ `abs_date`, `candseed`
  bands), **one image per region per year** (see §7.3 for why regions, not single cartas).
- **R (`terra`/`sf`):** vectorize (or ingest GEE polygons), compute `seed_mean`/`date_mode`,
  filter, re-assign year, and run the cross-tile + cross-year de-dup. `terra` is very efficient
  and `sf`'s spatial predicates are mature; this also fits the repo's existing R step (model
  fitting). Mitigations still apply: true overlap is **sparse**, near-boundary pruning cuts most
  pairs, and smaller `D` in dense areas reduces redundancy at the source.

Validate on a real multi-tile year before committing the GEE-vs-R boundary.

### 7.2 Download weight — masked pixels are cheap only after compression

Downloading the whole country is **not** too heavy, but for a reason worth stating precisely:
**masking is a flag, not a space saving.** A masked pixel costs the same as a real one in GEE
compute and in a *dense/uncompressed* GeoTIFF (written as `noData` at full dtype width). It is
**compression** (LZW/DEFLATE, or a COG with empty tiles dropped) that makes a mostly-masked
raster tiny, because the near-constant background collapses to almost nothing.

Order-of-magnitude for Argentina (~2.78 M km² → **~3.1 billion 30 m pixels/band/year**):

| export form | size |
|---|---|
| dense/uncompressed, ~2–3 bands | ~10–15 GB/yr → **~300–400 GB** for 1999–2025 (the "too heavy" case) |
| **compressed** sparse mask (burned ≈ 0.3–1 % of area) | ~tens of MB/yr → **~0.3–1.5 GB** total |
| `reduceToVectors` polygons per tile | ~MB/yr → **~100–300 MB** total (lightest) |

So the download is dominated by the small **burned** fraction, not the grid — provided we (a)
export **per region** (§7.3), (b) **skip region-years with zero burned pixels**
(`skipEmptyTiles`), and (c) keep **compression + tiling on** (`cloudOptimized`). Note this
cheapness is **download-only**: it does not reduce GEE *processing* memory, which still works the
full dense grid per tile.

**Does the download exploit the maskedness? Only if you ask for it.** The EE **asset** is stored
internally tiled + compressed, but you never pull that blob directly — "download" **re-renders**
the image to GeoTIFF (`Export.image.toDrive` / `toCloudStorage`, or `getDownloadURL`). To exploit
the mask you must request a **compressed** GeoTIFF: `formatOptions: {cloudOptimized: true}`
(DEFLATE + internal tiling). Then the masked/constant background collapses to almost nothing and
the file size tracks the seed-grown fire pixels. A **plain uncompressed** export writes every
`noData` pixel at full dtype width → dense and large, mask notwithstanding. Practical notes:
`getDownloadURL` has a **~32 MB request cap**, so for region-year images use **Export to
Drive/GCS**, not the direct URL; masked pixels export as `noData` (keep a `noData` value set).

### 7.3 Processing unit: regions (contiguous tile groups), not single cartas — [DECIDED intent]

Unlike step 03 (which runs **per carta** — `CLAUDE.md` prediction-tiling convention), step 04
runs SNIC over **regions = groups of contiguous cartas**, with region boundaries chosen to **not
split high-fire-activity areas** (delineate them with `snic_regions_definition`, see "Getting
started"). Rationale: supervised SNIC and the §6.1 grouping are spatial — a scar straddling a
processing boundary would be **bisected**, fragmenting the object and forcing cross-boundary
stitching. Bigger contiguous regions push most scars fully inside one unit, shrinking the
cross-boundary de-dup (§7) to the few genuine region-edge cases. Output is **one highly-masked
image per region per year**, exported to asset then downloaded (§7.2, §7.5).

> **[OPEN / verify — the deciding test for extent]** GEE SNIC is computed on internal processing
> tiles (~256 px + `neighborhoodSize` buffer) and can show **tile-boundary artifacts**. A
> country-wide *export region* does **not** make SNIC compute globally — you cannot make it "see"
> all of ARG at once; a bigger region just adds more internal seams. **Test:** SNIC one region,
> then SNIC the same area split in two, and diff the masks along the seam. *Identical* → internal
> tiling is transparent for the mask (full-ARG export is then safe, choose extent by export
> limits); *seams/drops* → **raise `neighborhoodSize`** (primary lever, below), overlapping
> regions only as fallback. Document the finding here in the spirit of the §5 gotchas in
> `03-bpts.md`.

**The primary lever: `neighborhoodSize`.** SNIC's `neighborhoodSize` (px; default `2 × size`) is
the internal-tile buffer *designed* to avoid tile-boundary artifacts — each processing tile is
expanded by it before segmenting, so objects within that reach are not cut at the seam. **Raise
it** to keep fires intact across internal seams. Caveats: (i) it is **not free** — a bigger
buffer is recomputed per internal tile → more memory (may need `tileScale`), with a practical
ceiling that can't cover the very largest scars (thousands of px) cheaply; (ii) **you don't need
to cover the whole fire** — because we keep only the **mask** and **relabel in R** (§6.1
`patches()`), cross-tile *label* inconsistency is irrelevant and the only residual risk is
**completeness** (a seed-connected candidate near a seam dropped when its seed is beyond reach).
So `neighborhoodSize` only has to exceed the **max seed-to-candidate reach across a seam**, not
the scar's extent — and since real scars carry seeds throughout, a generous-but-sane value
suffices. The §7.3 diff test picks the value.

**Extent recommendation.** With `neighborhoodSize` set adequately + R global relabeling, internal
seams and region-to-region joins are both handled, so the extent choice (full-ARG vs regions) is
driven by **export robustness/resumability**, not by "seeing the whole country" (SNIC never
does). Prefer **per-region** exports over one monolithic country task per year (far more
resumable — the `CLAUDE.md` idempotency rule). **Manual overlapping regions** become a *fallback*
only if memory caps `neighborhoodSize` below what completeness needs. Compute is not the
constraint (supervised single-band SNIC is cheap); export robustness and completeness are.

**Two boundaries, different roles — [DECIDED].** SNIC runs per **region**, but the **export can
be sharded** freely: whether you tile a region's single `toDrive` with `fileDimensions` (§7.5) or
export per carta, R re-mosaics all tiles (up to all of ARG) and runs the §6.1 `patches()`
gap-closing on the full mosaic, so objects span tile seams for free — no cluster-id matching, and
export-tile boundaries are **harmless**. What still matters is the **SNIC-region** boundary: a
scar straddling two regions is grown separately in each, so if a fragment's seeds all sit on one
side, the other region grows nothing there (seedless → dropped) and that fragment is **never
exported** — R cannot recover it. Hence region boundaries must still avoid splitting high-fire
areas; export boundaries need not.

### 7.4 Export mechanics for the R (raster) path — [DECIDED]

The chosen handoff is **download rasters, do all object work in R** (simpler than vectorizing in
GEE, which hits the flaky reduce-regions/vector path). Per region-year:

- **Bands: `candseed` (0/1/2) + `abs_date`** — two bands, cast to a **single int16** dtype so the
  export is one clean GeoTIFF (GeoTIFF bands share a type). `candseed` carries everything: burned
  = `candseed > 0` (already the SNIC-grown mask, seedless islands gone), and the polygon
  `seed_mean` = `mean(candseed == 2)` — no separate seed band needed. Encode `abs_date` as **days
  since 1970-01-01** (≈10 600–20 500 for 1999–2025 → fits int16, matching step-03's all-int16
  convention, `03-bpts §3.7`). *(The SNIC cluster ids are **not** exported — R relabels; §6.)*
- **Export call:** `Export.image.toDrive` with **`formatOptions={'cloudOptimized': True}`** (see
  §7.5 for why Drive) — that flag (a `formatOptions` key) is what turns on DEFLATE + internal
  tiling and makes the masked background nearly free (§7.2). COG preserves the mask →
  `terra::rast()` reads masked pixels as `NA`; if they arrive as `0`, `unmask(-9999)` before
  export and `NAflag(r) <- -9999` in R.
- **In R:** mosaic tiles → §6.1 barrier-constrained `patches()` for objects → per-object
  `seed_mean`, `date_mode`, size → filter → cross-region/cross-year de-dup (§7).

### 7.5 Getting the rasters to the local machine — [DECIDED: Drive + COG]

> **Revised 2026-07-06, superseding an earlier `[DECIDED: GCS]` lean.** Three facts flipped the
> destination from Cloud Storage to **Drive with a Cloud-Optimized GeoTIFF**: (1)
> **`mapbiomas-argentina` has no Cloud-Storage budget** — GCS costs money the project can't
> spend, and borrowing the fire-latam team's bucket adds permissions/coupling we'd rather avoid;
> (2) **`cloudOptimized: true` works on `Export.image.toDrive`** (it is *not* Cloud-Storage-only,
> contrary to common belief) — so Drive gets the *same* DEFLATE + internal-tiling compression
> that makes the masked background nearly free (§7.2), and the only technical reason to prefer
> GCS evaporates; (3) Drive needs no bucket, no billing, no auth setup.

Export destinations are **three independent systems** — neither Drive nor GCS consumes the
`mapbiomas-argentina` **EE asset** quota:

| Destination | Call | Storage / cost | Downloadable? |
|---|---|---|---|
| EE asset | `Export.image.toAsset` | EE project asset quota | **No** — an asset is not a file; re-export needed |
| Cloud Storage | `Export.image.toCloudStorage` | GCP billing (~$0.02/GB·mo storage, ~$0.12/GB egress) | Yes — `gcloud storage cp` |
| **Drive** | `Export.image.toDrive` | Drive quota (15 GB free) | Yes — browser / `rclone` |

**Operational recipe (per region-year):**

1. *(optional but recommended)* `Export.image.toAsset`, one asset per region+year. Not
   downloadable, so it isn't the deliverable — but it **materialises the SNIC computation once**
   (the Drive export then runs off `ee.Image(asset)` as a fast copy, no recompute) and lets you
   inspect the result in GEE. The `CLAUDE.md` "asset per step" convention otherwise doesn't
   strictly apply here, since an asset can't be downloaded as a GeoTIFF.
2. `Export.image.toDrive(image, formatOptions={'cloudOptimized': True}, …)` — the COG **is** the
   step-04 artifact. Tile the file **inside this single call** with `fileDimensions` (multiple of
   256, e.g. 8192) and `skipEmptyTiles=True`; do **not** loop per carta (transport tiles need not
   honor the carta grid — R re-mosaics by geolocation regardless, §7.3). The ~10k-px-per-file cap
   applies to Drive/CS **files**, **not** to the asset (assets are internally-tiled pyramids,
   only bounded by `maxPixels`, raise to ~1e13). Keep a `noData` value set (§7.4).
3. **Download & mosaic in R:** pull the tiles (browser, or `rclone` for scripted bulk), then
   `terra::vrt(tiles)` (virtual mosaic, no copy) or `merge()`/`mosaic()` → §6.1 gap-closing.

*(If a CS bucket ever becomes available, the GCS mechanics are a drop-in alternative and are
nicer for scripted bulk pulls of hundreds of tiles: one-time `gcloud auth login` (interactive —
`! gcloud auth login`), `gcloud config set project mapbiomas-argentina`,
`gcloud storage buckets create gs://<bucket> --location=us`; export with
`toCloudStorage(bucket='<bucket>', fileNamePrefix='snic/<region>/<year>', …)`; download with
`gcloud storage cp -r gs://<bucket>/snic ./data/snic/`; spot-check without downloading via GDAL
virtual paths — `terra::rast("/vsigs/<bucket>/snic/<region>/<year>.tif")`. Absent budget,
Drive+COG is the decision.)*

### 7.6 A permissive SNIC + raster-native object metrics (`zonal`) — [DECIDED]

**Tune SNIC permissive on purpose.** The seed/candidate cuts are set *loose*: it is better to let
many false-positive objects through than to lose real scars, because false positives are **cheaply
removed downstream** — by (a) **low seed density** (`seed_mean` — a real scar is seeded throughout,
a spurious blob is not) and (b) **shape features** (real scars are compact/contiguous; noise is
sparse/porous). So **recall is protected at segmentation, precision is recovered at filtering
(§7 step 3)** — the two jobs are deliberately separated. This is why the seedless-candidate drop
(§6) and the `seed_mean`/shape filter carry the precision burden, not the delta cut alone.

**Compute per-object metrics raster-native, with `terra::zonal()` on the patch-id raster — not
with vector `reduceRegions`/`extract`.** After §6.1's `patches()` you already hold an object-id
raster pixel-aligned with `candseed`, so the **zones are free**; `zonal` is a single compiled pass
(`O(n_pixels)`, no geometry). Compute the metrics keyed by id **before** vectorizing, then
vectorize **once** and left-join the metrics by id:

```r
seed_mean <- zonal(candseed == 2, patchId, fun = "mean", na.rm = TRUE)  # fake-fire discriminator
date_mode <- zonal(abs_date,      patchId, fun = "modal", na.rm = TRUE)  # modal burn date
size      <- freq(patchId)                                              # pixel count per object
```

- **Why not the vector route.** In GEE, `reduceRegions` at 30 m over many polygons is exactly the
  timeout / user-memory path that pushed object work to R (§7.1) — avoid it. In R,
  `terra::extract`/`exactextractr::exact_extract` *work* and are C++-fast, but are strictly more
  work (they rasterize/intersect each polygon); `zonal` skips all of it because the id raster **is**
  the zones. Only reach for `exact_extract` when a metric needs **sub-pixel polygon-coverage
  weighting** — `seed_mean` does not.
- **Caveats.** `zonal` needs both rasters on the **exact same grid** (they are — both come off the
  SNIC output), and `na.rm = TRUE` so masked background never dilutes a proportion.

**Shape metrics are only *partly* polygon-based.** Genuinely geometric ones (perimeter-vs-area
compactness, elongation, bounding-box fill) do need the vector polygon. But a **sparseness /
porosity** signal is a **pixel-level neighborhood op**, so it stays raster-native: `focal(burn,
fun = sum)` = count of burned pixels in each pixel's window, then `zonal(focalSum, patchId,
fun = "mean")` averages it over the object → a sparseness score with no geometry at all. So
**exploit rasterness for sparsity too**; keep the vector polygon only for the truly geometric
shape features. **[OPEN]** the exact shape/sparseness feature set and their filter cuts.

---

## 8. Open questions to resolve before implementation

- **[§5]** Concrete `D = f(n)` (also governs the §7 merge tolerance).
- **[§6]** SNIC parameters: how seeds are supplied, `size`, `compactness`, `neighborhoodSize`,
  connectivity 8.
- **[Getting started]** Seed/candidate threshold *values* in `config/snic_seed_candidate_thresholds.csv`
  (await the fuller `bpts` export + the `snic_candidates_seeds_definition.qmd` study), and whether one
  global set holds or region/veg stratification is needed. Same study also decides empirical-tree vs
  second (annual) model for `candseed`.
- **[§7]** Polygon filter: empirical decision tree vs polygon-level model; IoU merge threshold
  (0.2?) and whether the `date_mode` merge tolerance equals `D`.
- **[§7.3]** Region definition (which contiguous carta groups) and **verify SNIC tile-boundary
  artifacts** on a real region-year.
- **[§9]** Final month-of-burn raster: pixel-level (month, year-band) rule when polygon vs pixel
  dates disagree; ensure de-dup preserves per-pixel dates and no pixel lands in two year-bands.

**Resolved:** supervised SNIC (seed-grown region growing, drops seedless candidates), kept in
GEE, ids discarded, mask retained (§6); terra does *post-SNIC* gap-closing, not a replacement
(§6.2); hard masked firebreak via 8-direction shift-diff, max > `D` (§5); backward-only gap-fill
from late `y−1`, no collision tiebreak (§4); cross-year duplication is inherent and deferred to
the overlap-merge (§4.3); download is sparse only with a compressed (`cloudOptimized`) export
(§7.2); step 04 SNIC runs per region while the export shards freely and R re-mosaics (§7.3);
raster handoff to **Drive + COG**, not GCS (§7.5); all object work in R on downloaded
`candseed`+`abs_date` int16 rasters (§7.4); permissive SNIC by design (recall at segmentation,
precision at filtering) with per-object metrics computed raster-native via `terra::zonal()` on the
patch-id raster — incl. pixel-level sparseness — not vector `reduceRegions`/`extract` (§7.6).

---

## 9. Final product: polygons **and** a per-pixel month-of-burn raster — [NEW, to develop]

> Parked mid-discussion (2026-07-03) — flesh out next session.

The deliverable is **two coupled products**:

1. **Polygons with metadata** (fire objects: id, year, area, `date_mode`, `seed_mean`, …) — the
   working product from §7.
2. **The MapBiomas-required raster:** a **multi-band image, one band per year, pixel value =
   month of burn** (1–12). This is *mandatory* for the MapBiomas deliverable.

**The load-bearing consequence: per-pixel date must be preserved end-to-end.** We cannot collapse
a fire to a single polygon-level `date_mode` and lose the pixel dates — the month-of-burn raster
needs each pixel's own month. So the pipeline must carry per-pixel `abs_date` all the way to a
final rasterization step: **polygons → rasterize back → month = month(pixel `abs_date`)**, binned
into the correct **year band** = `year(pixel abs_date)`.

Implications to work through (flagged now, resolved later):

- **§4 gap-fill (reinforced, now load-bearing).** When we import `candseed > 0` from `y−1` before
  SNIC, we must keep each imported pixel's **real previous-year date** (its `abs_date`), not just
  the mask — already the design, but now it's what makes the month/year band correct. An imported
  Dec-`y−1` pixel has month = December and belongs to the **`y−1` band**, even though it was
  pulled into year `y`'s segmentation.
- **§7 de-dup (needs care).** Merging polygons must **not** overwrite per-pixel dates with one
  polygon date — a merged scar spans pixels of different months, and a gap-filled pixel exists in
  both `y−1`'s own output and via `y`'s run. The de-dup has to resolve **at the pixel level for
  the month/year raster** (which single month/year does each pixel get?), not only at the polygon
  level. Guard against a pixel being written into two year-bands.
- **Open:** exact rule for a pixel's final (month, year-band) when polygon-level and pixel-level
  dates disagree; how month-of-burn interacts with the manual ash/drought masking pass; whether
  the raster is derived from the *filtered/merged* polygons (so fake-fire pixels are excluded).
