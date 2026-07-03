# 03 — Burn-probability time-series metrics (`bpts`)

Full design + implementation record for step 03. This is the single reference: what the
step does, **why each decision was taken**, and — importantly — the **GEE array-handling
problems we hit and how they were solved**, so a future change doesn't re-discover them.

Code: `utils/functions.py` (building blocks + `bpts` driver), `workflow/03-bp_ts_metrics.py`
(CLI), `scripts/test-03-bp_ts.py` (interactive/headless checks). Distributed multi-account
export is documented separately in `03-colab_multi_export.md`. Related exploration notebook:
`notebooks/burn_prob_ts_metrics.qmd` (candidate metrics on synthetic signals; the ideas here
are the matured version).

---

## 1. What this step does

For every **year × MapBiomas carta tile**:

1. compute the **observation-level burn probability** for every Landsat image (the step-02
   logistic regression applied per pixel-date),
2. reduce that per-pixel time series to **annual summary metrics** (magnitude, persistence,
   change, plus quality bands),
3. export a 16-band image to the target collection.

- **Output collection:** `projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/WORKFLOW-EXPORTS/bp_ts_metrics`
  (`C.BP_TS_METRICS_COL`).
- **Asset name pattern:** `bpts_YYYY_<tile-id>` (e.g. `bpts_2015_SK-19-Y-A`).
- **Properties set:** `year`, `tile_id`, and `system:time_start` = `YYYY-07-01` (mid-year, for
  inspector visualization).
- **Years:** 1999–2025 (`C.YEARS`).
- **Tiles:** all cartas intersecting the buffered-Argentina FC
  (`C.ARG_BUFFER_FC`) — **248 tiles**. Grid: `C.CARTAS_FC`
  (`projects/mapbiomas-chaco/BASE/cartas-argentina`), tile id in property `grid_name`
  (`C.CARTAS_ID_PROPERTY`).

Place in the pipeline: this is the prediction step that feeds SNIC segmentation (step 04) and
the object metrics / manual ash-drought masking downstream.

---

## 2. The burn-probability model, deployed in GEE

### 2.1 Predictors and the previous-year context

The step-02 model is **one elastic-net logistic regression per `veg_fire` class** (23 fittable
classes). It predicts the probability that a pixel-date is *burned*, from:

- **focal** spectral features of the Landsat observation (11 terms), and
- **previous-year** MapBiomas mosaic summaries + interactions.

`veg_fire` is the previous-year land cover crossed with the region:

```
mb_year      = min(year - 1, C.MB_LIMIT_YEAR)            # LULC asset stops at MB_LIMIT_YEAR
region_class = region_id * 100 + mb_class_raw            # region 1..5, MB class
veg_fire     = remap(region_class, REGION_CLASS_FROM, VEG_FIRE_TO, default=25)
```

The region raster `C.REGION_RASTER` (`…/ARG-Regiones-MapBiomas-buffer2km`, band `region_id`,
codes 1–5 with a 2 km buffer beyond the border, 0 outside) is painted once
(`scripts/export_region_raster.py`). Pixels outside any region or with an unmapped class fall
through to the **non-observed sentinel 25**; non-burnable land covers are **24**.

### 2.2 The linear predictor on the RAW band scale

Every model exports **raw-scale coefficients** (the mean-centering used while fitting is folded
into the intercept + main slopes — see `models/README.md`). So prediction is a plain dot
product, no glmnet object, no centering before products:

```
eta  = intercept
     + Σ prev_coef  · mb_mosaic_band                  (prev main effects)
     + Σ focal_coef · landsat_band                    (focal main effects)
     + Σ pairs_coef · focal_f1 · focal_f2             (focal × focal)
     + Σ cross_coef · mb_mosaic_f1 · landsat_f2       (prev × focal)
prob = 1 / (1 + exp(-eta))
```

This was one of Iván's explicit worries (use predictors on their raw scale, no centering
before products). **Verified:** GEE `prob` reproduces a hand-computed raw-scale logit to
**~7e-9** (float32) for a real pixel/class — see §6.

### 2.3 The 130-term structure (what `load_all_coefficients` parses)

The reduced design is **130 terms across 7 blocks**, identical order in all 23 class CSVs:

| block | count | term form | factor1 | factor2 |
|---|---|---|---|---|
| `(intercept)` | 1 | `(Intercept)` | — | — |
| `focal` | 11 | `BLUE_t` | focal `BLUE` | — |
| `prev` | 32 | `GREEN_med` | prev `mb_mos_green_median` | — |
| `pairs` | 22 | `BLUE_t__NBR_t` | focal `BLUE` | focal `NBR` |
| `sameband` | 10 | `GREEN_med__GREEN_t` | prev `mb_mos_green_median` | focal `GREEN` |
| `cross_idx` | 22 | `NDVI_med__NBR_t` | prev `mb_mos_ndvi_median` | focal `NBR` |
| `cross_band` | 32 | `NDVI_med__RED_t` | prev `mb_mos_ndvi_median` | focal `RED` |

Term-name parsing rules (`_parse_feature` / `_parse_term`):
- `_t` suffix → **focal** factor, raw index name (`BLUE_t` → `BLUE`, matches `add_indices`).
- summary suffix → **prev** factor, MapBiomas mosaic band via `C.PREV_SUFFIX_MAP`
  (`med→median`, `wet→median_wet`, `dry→median_dry`, `sd→stdDev`): `GREEN_med` →
  `mb_mos_green_median`.
- `A__B` → product; for cross blocks factor1 is prev, factor2 is focal.
- `(Intercept)` → GEE-safe band name `intercept_term` (parentheses are illegal band chars).

### 2.4 Turning per-class coefficients into pixel-wise images

`build_coeff_image(veg_fire, terms)` makes a **130-band image**: each band is one term's
coefficient, assigned per pixel by `veg_fire.remap(FITTABLE_VEG_FIRE, [coef_c1..c23], 0.0)`.
Non-fittable classes get coefficient 0 (and are masked out of prediction anyway).

The prev-only part of `eta` and the prev factor of every cross term are **time-invariant
within a year**, so we precompute them once per tile-year and reuse for every Landsat image:
- `build_prev_scalar` → intercept + Σ(prev_coef · mosaic_band): single band `prev_scalar`.
- `build_cross_factor1_coef` → for each cross term, the multi-band image `prev_factor · coef`
  (only the focal factor is multiplied in per image at runtime).

**Band-alignment safeguard (Iván's worry #3, coefficient/band ordering).** Rather than rely on
GEE's band-matching rules, every multiply renames the selected feature bands to the coefficient
band names first (`_select_renamed`), so the two operands have **identical names in identical
order** — correct under any GEE matching rule. `compute_burn_prob_img` then assembles the four
contribution groups, applies the logistic, and (critically) **carries `system:time_start`**
(see §5, gotcha 3).

---

## 3. From observation series to annual metrics

### 3.1 Main ideas (why these metrics)

- Burn probability must be **smoothed before detection**. Col-0 used a median of K=5 obs; here
  some veg types recover fast and image density varies, so we also use a **smaller K=3** window.
  Median (not mean) keeps values on the original probability scale.
- Detection rests on **magnitude** (high prob), **persistence**, and **change** — measured in
  number of consecutive *valid* obs, not elapsed time, because the Landsat series is irregular
  and density varies by pixel and year.
- Col-0 used `diff(median5)` centred at the middle obs: a fire just before an observation shows
  the minimum of the first burned obs, and the diff spikes there. We soften to K=3.
- Claude's Col-1 proposal — a **delta = minfore − maxback** (jump in prob followed by
  persistence): `minforeK` is the post-jump *floor* (min of the next K), `maxbackK` the
  pre-jump *baseline* (max of the previous K). Using `max` of the back window smooths low-prob
  noisy observations inside a stable burn scar, avoiding false detections that a no-smoothing
  delta would create.

Everything is on the **probability scale** (neither logit nor log).

### 3.2 Per-observation quantities

For valid obs `t` with prob `p[t]` at date `d[t]` — the **day-number** (integer days
relative to focal-year Jan 1; `_day_num`, computed with EE's exact calendar-aware `'day'`
unit). Focal obs get 0–365 (so DOY = `d[t]+1`); prev-year padding obs are negative, next-year
obs are >365, so all date differences below are exact whole-day counts that stay correct across
the year boundary:

- forward persistence: `minfore3[t]=min(p[t],p[t+1],p[t+2])`, `minfore2[t]=min(p[t],p[t+1])`
- pre-jump baseline: `maxback3[t]=max(p[t-3..t-1])` (conservative), `maxback2[t]=max(p[t-2..t-1])` (permissive)
- change: `delta3 = minfore3 − maxback3`, `delta2 = minfore2 − maxback2`
- widths (days): `prevwidth3=d[t-1]-d[t-3]`, `prevwidth2=d[t-1]-d[t-2]`,
  `jumpgap=d[t]-d[t-1]`, `postwidth3=d[t+2]-d[t]`, `postwidth2=d[t+1]-d[t]`

`jumpgap` is strong fire evidence when **short**; if long it may be slow change (not fire) or
fire under low image density.

### 3.3 Collapsing to annual scalars

Each delta is treated **independently**: find *its own* argmax `t*` over the focal year and
extract *its own* bundle at that `t*`. Tying K=3 and K=2 to one peak would mis-anchor the
other (the optimal transition obs differs by window). At each delta's `t*` we store the delta
value, `minforeK` (post level; `maxback = minforeK − deltaK` so it isn't stored separately),
`jumpgap`, the relevant `prevwidth`/`postwidth`, and `date_post = d[t*]+1` — the **day-of-year**
(1–366) of the post-jump obs (`date_post − jumpgap/2` ≈ a good candidate burn date). Because
`t*` is always a focal obs, `date_post` is guaranteed to fall within the focal year.

Whole-series (not tied to a delta peak): `pmax1`=max raw prob, `pmax2`=max(minfore2),
`pmax3`=max(minfore3). Quality: `n` (obs count) — the sole density/quality channel. All bands
are always exported; which to trust is decided later by image density.

> The per-pixel inter-obs gap bands `timediff_med`/`timediff_max` were **dropped** (2026-06):
> largely redundant with `n` as a density signal, and removing them saves storage. The code no
> longer computes the `diffs` array — see §3.7.

### 3.4 The padding strategy (the subtle part)

Window metrics lose obs at the series extremes: `maxback3` needs 3 obs *behind*, `minfore3`
needs 2 *ahead*. To give the focal year enough context we borrow from neighbours: **3 obs
before** and **2 obs after** the focal year — **asymmetric** padding.

Why asymmetric: `maxback3` at the first focal obs looks back 3 steps; `minfore3` at the last
looks forward only 2. Symmetric padding of 2 would under-supply `maxback3` at `t=1`. The argmax
search is always restricted to focal indices `1:T`, so padded obs only ever serve as
*background context* for the first/last focal obs — a burn can never be "detected" twice across
adjacent years.

Padded obs can't be taken as the literal nearest neighbour images (those may be cloud-masked at
this pixel), so we compute burn probability for **M months** on each side (`C.pad_months(year)`),
build the per-pixel array, and take the **3 latest** prev and **2 earliest** next obs
(`C.PAD_OBS_LEFT`/`RIGHT`). All padded obs use the **focal year's** previous-year LULC/mosaic
(strictly they'd use their own; but for only 3+2 obs the focal year's context is the better
approximation — except under very low image density, which we can't fully solve).

**M is year-dependent** (`C.pad_months`): **2 months for 2001+**, but **4 for 1999** and **3 for
2000** — the early Landsat era is sparse (L7 launched mid-1999), so those years pad wider to still
gather the 3+2 obs. A narrower pad is also much cheaper (fewer scenes → less per-image cost; §8).

Landsat window for focal year `y` (default 2-month pad): **Nov 1 (y−1) → Mar 1 (y+1)** exclusive
(`filterDate` end is exclusive). Split into prev `[(13−M)…Dec y−1]`, focal `[y]`, next
`[Jan…M y+1]` — e.g. for 2001+ prev = `[Nov–Dec y−1]`, next = `[Jan–Feb y+1]`.

### 3.5 Two guaranteed-structure padded arrays (instead of one)

We build **two** padded arrays rather than one with variable left-padding, so that
**fixed-offset array slices are always correct** for unmasked pixels:

- **K=3 array** `[≤3 prev | T focal | ≤2 next]`, kept only where length ≥ 6 (min T=1).
- **K=2 array** `[≤2 prev | T focal | ≤1 next]`, kept only where length ≥ 4.

`arraySlice` clamps when a side has fewer obs; the `length ≥ 6` (resp. ≥4) mask then keeps only
pixels wide enough that, after dropping the leading 3 (resp. 2) and trailing 2 (resp. 1)
positions, **at least one focal obs has full back/fore context**. Elegantly, the fixed offsets
*automatically drop* boundary focal obs that genuinely lack context (e.g. with only 2 prev
obs, the first focal obs — which can't have a real `maxback3` — is excluded), regardless of how
many prev/next obs actually arrived. Pixels failing a window's length test get *that window's*
bands masked — a quality flag, not an error.

Fixed-offset slices for K=3 (column 0 = prob, 1 = date), with `L` = padded length:

```
p[t-3]=slice(0,0,-5)  p[t-2]=slice(0,1,-4)  p[t-1]=slice(0,2,-3)
p[t]  =slice(0,3,-2)  p[t+1]=slice(0,4,-1)  p[t+2]=slice(0,5)
```

All six are length `L-5`, so they `arrayCat` along axis 1 and reduce cleanly. K=2 uses offsets
2 / −1 (lengths `L-3`).

### 3.6 Finding `t*` (argmax via sort)

Bundle everything needed at `t*` into one `[T,6]` array `[delta, minfore, d_t, d_{t-1},
d_{t-3}, d_{t+2}]`, sort rows **descending by delta**, take the top row, read the six scalars
with `arrayGet`. Widths/gaps are exact whole-day differences (the date column is already in
integer days), and `date_post` is `d[t*]+1`.

### 3.7 Output bands (16) and integer encoding

All bands are **int16-encoded for export** (≈half the float32 asset size). The encoding is
applied in `bpts_image`; the `decode` column below is how to recover each band. The band groups
and `PROB_SCALE` live in `utils/functions.py` (`PROB_BANDS`/`DAY_BANDS`/`DOY_BANDS`). Everything
is a single signed dtype (int16, −32768…32767) on purpose — see the note below the table.

| band | definition | decode | masked when |
|---|---|---|---|
| `delta3_peak` | max(delta3) over focal year | ÷10000 | K=3 array short |
| `minfore3_peak` | minfore3 at delta3 argmax | ÷10000 | K=3 array short |
| `jumpgap3` | d[t*]−d[t*−1], days | as-is | K=3 array short |
| `prevwidth3` | d[t*−1]−d[t*−3], days | as-is | K=3 array short |
| `postwidth3` | d[t*+2]−d[t*], days | as-is | K=3 array short |
| `date_post3` | d[t*]+1, day-of-year (1–366) | as-is | K=3 array short |
| `delta2_peak` | max(delta2) | ÷10000 | K=2 array short |
| `minfore2_peak` | minfore2 at delta2 argmax | ÷10000 | K=2 array short |
| `jumpgap2` | d[t*]−d[t*−1], days | as-is | K=2 array short |
| `prevwidth2` | d[t*−1]−d[t*−2], days | as-is | K=2 array short |
| `postwidth2` | d[t*+1]−d[t*], days | as-is | K=2 array short |
| `date_post2` | d[t*]+1, day-of-year (1–366) | as-is | K=2 array short |
| `pmax3` | max(minfore3) whole series | ÷10000 | K=3 array short |
| `pmax2` | max(minfore2) whole series | ÷10000 | K=2 array short |
| `pmax1` | max raw prob whole series | ÷10000 | n = 0 |
| `n` | focal obs count; **−1** non-burnable, **−2** non-observed | as-is | **never masked** |

> **Dropped (2026-06):** `timediff_med` / `timediff_max` (median/max inter-obs gap, days). They
> were largely redundant with `n` as a density signal, so they were removed to save storage — the
> output went from 18 → **16 bands** and `compute_bp_ts_metrics` no longer builds the `diffs`
> array. The §5 gotcha #4 (the `n>=2` mask that guarded those reducers) is now moot.

**Why all int16 (signed), not uint16 for the day bands.** Every encoded value fits well inside
±32767: probabilities ×10000 span 0…10000, `delta*` are **signed** (−10000…10000), day-gaps are
≲250, DOY is 1–366, and `n` carries −1/−2. The day-gaps are mathematically ≥0 (the array is
sorted ascending by date, so within the argmax row `d[t−3] ≤ d[t−1] ≤ d[t] ≤ d[t+2]`), but we
keep them **signed** anyway: a stray negative then stays visibly negative instead of wrapping to
a huge unsigned value. A single signed dtype also makes downstream reads uniform.

Missing data is never given a probability — masked pixels simply don't contribute to the
array, so no-obs fittable pixels get `n = 0`. The `n` band is the quality/sentinel channel: it
is the only band never masked, and carries −1/−2 for non-burnable/non-observed `veg_fire`.

---

## 4. The `bpts` driver and how to run it

```python
bpts(year=None, tile_id=None, export=True, overwrite=False)
```

| call | effect |
|---|---|
| `bpts(2015, 'SK-19-Y-A', export=False)` | returns the `ee.Image` for inspection |
| `bpts(2015, 'SK-19-Y-A')` | exports that one tile-year |
| `bpts(2015)` | exports all 248 tiles for 2015 |
| `bpts(tile_id='SK-19-Y-A')` | exports all years for that tile |
| `bpts()` | exports everything (all years × tiles) |

- `export=False` requires both `year` and `tile_id`.
- **Skip-if-done-or-in-flight:** before submitting, `bpts` **skips any tile-year that is
  already exported OR already has a PENDING/RUNNING task** — so re-running a year is idempotent
  and resubmits only genuinely-missing tiles. Both checks are **cross-account and
  cross-project**: completed comes from the shared output collection; in-flight comes from
  `listOperations`, which is *project-scoped* (returns every user's tasks in the project), run
  over every project in `C.BPTS_TASK_PROJECTS` (`mapbiomas-argentina`, `mapbiomas-fire-485203`)
  plus the active `GEE_PROJECT`. So no contributor re-launches something already running,
  regardless of who launched it or which project it was billed to. If the running account
  can't read one of those projects, a `UserWarning` names which projects *were* evaluated (that
  gap still relies on the per-year Excel sign-out). `overwrite=True` forces resubmission (but
  GEE won't overwrite — delete the asset first).
- `bpts_status(year)` classifies each tile-year as **done / in flight / to launch** (same three
  states the launcher skips on) — prints one line per year and returns
  `{year: {"done": [...], "in_flight": [...], "to_launch": [...]}}`. No GEE compute — just
  `listAssets` + `listOperations`.

Per-tile-year flow (see `bpts_image` / `burn_prob_collection`): build `veg_fire`, mosaic, the
static LR components and `is_fittable`; `get_landsat` over the padded window; `mosaic_by_date`
to dedupe same-day scenes; map the LR to a 2-band `[prob, day_num]` collection masked to
fittable (`day_num` = integer days from focal-year Jan 1, see §3.2); split by `filterDate` into
prev/focal/next arrays via `safe_to_array`; reduce with `compute_bp_ts_metrics`; apply the `n`
sentinels; int16-encode (§3.7); export at scale 30, `EPSG:4326`, `maxPixels=1e10`.

CLI (also good from Positron): `workflow/03-bp_ts_metrics.py --year 2003 [--tile … |
--status | --overwrite | --project …]`. Distributed multi-account runs: see
`03-colab_multi_export.md`.

---

## 5. GEE array-handling problems we hit (and why the fixes look like they do)

Array ops in GEE are the brittle part of this step. All of the following were hit during
implementation and fixed; **read this before touching the array code.**

**The governing rule (learned from col-0, which shipped this pattern):** an empty array only
*throws* on (a) **unmasked** pixels and (b) **constant** array images (which GEE evaluates
eagerly). **Masked raster pixels short-circuit cleanly** — the engine skips them and returns
masked. So the discipline is: every `arrayReduce`/`arrayGet`/`arraySlice(axis≥1)` site must
reach either a *non-empty* array or a *masked* pixel. Two consequences bit us:

1. **`arraySort(keys)` needs keys of the same rank as the array** — multiple elements only along
   the sort axis. Passing an `arrayProject([0])`'d 1-D key against a 2-D `[T,6]` bundle throws
   *"Image and keys must have same dimensions."* Fix: sort with the `[T,1]` delta column
   (negated for descending), not a projected 1-D key.

2. **An empty `ee.Array` cannot stay 2-D.** Slicing any array down to zero rows collapses it to
   1-D, so an empty `[0,2]` stub is actually 1-D and breaks the downstream `arraySlice(1, …)`
   *(symptom: "Image.arraySlice: Axis must be ... less than the dimension")* whenever a
   prev/focal/next sub-collection is globally empty. Fix: `safe_to_array` never returns an empty
   stub — it **prepends a fully-masked 2-band sentinel image** so the collection is never empty
   and `toArray()` is always statically 2-D. The masked sentinel contributes no per-pixel
   elements (no-obs pixels still come back masked, `n = 0`).

3. **`compute_burn_prob_img` must carry `system:time_start`.** It builds a fresh
   `prob.addBands(day_num)` image; without copying the timestamp, the downstream
   `filterDate` split into prev/focal/next returns **empty** and every pixel gets `n = 0`
   (the product looked structurally fine but was all-empty — a silent, expensive failure that
   only showed after a full export).

4. **Whole-series reducers over `focal_arr` aren't covered by the padded-array masks.** *(Now
   historical — the `timediff_*` bands this guarded were dropped, §3.7. Kept here because the
   same trap will reappear if any future whole-series reducer over a length-`n−1` array is
   added.)* A fittable pixel with exactly **1 focal obs** has a non-empty `focal_arr` (so it
   isn't masked) but an **empty `diffs` array** (length `n−1 = 0`); reducing it throws an
   out-of-bounds `arrayGet`. This is common (sparse Landsat) and crashed a 22-minute export. Fix
   that was used: `diffs.updateMask(n.gte(2))` before the reducers, so n<2 pixels short-circuit.
   (`pmax1` is safe: n=1 reduces fine, n=0 is already masked.)

**Other array notes:**
- `updateMask(cond.gte(threshold))` leaves UNMASKED where the condition holds.
- `ImageCollection.toArray()` stacks images on axis 0, bands on axis 1 → `[N, bands]`; select
  `['prob','day_num']` first so column 0 = prob, column 1 = date.
- `n = focal_arr.arrayLength(0).unmask(0)` — `arrayLength` is the one array op that's safe on an
  empty array; `unmask(0)` guarantees `n` is never masked, then the −1/−2 sentinels are applied
  by `veg_fire.eq(24/25)`.

**Compute-limit note (not a bug):** interactive `getInfo`/`reduceRegion` on the full 130-band ×
full-Landsat-series graph hits the *user memory limit* — even `bandNames()`, because
`safe_to_array` forces building the collection. The batch `Export.image.toAsset` tiles the
computation and is the intended run path; for interactive debugging, feed
`compute_bp_ts_metrics` small synthetic arrays or sample a single Landsat image.

---

## 6. Validation (against `bpts_2015_SK-19-Y-A`)

Done with the non-buffered `…/ARG-Regiones-MapBiomas` as a temporary stand-in for the
not-yet-exported buffered raster:

- **Coefficients:** all 130 terms parse; every focal/prev factor maps to a real
  `add_indices` / mosaic band name (7 blocks: 1/11/32/22/10/22/32).
- **Burn probability:** GEE `prob` reproduces the hand-computed raw-scale logit to **~7e-9**
  for a real pixel (`veg_fire = 21`) — confirms coefficient ordering, band alignment, raw
  products, the `veg_fire→coef` remap, and the sigmoid.
- **Metrics:** all bands verified by hand on a synthetic series (delta/minfore peaks, jumpgap
  / widths, pmax1/2/3, K=2 family). *(Validation predates the §3.7 drop of `timediff_*`; the
  remaining 16 bands are unchanged.)*
- **Masking:** insufficient-padding and no-obs pixels mask cleanly (no errors), `n = 0`.
- **Realism:** over the exported tile `n` averages 25 (max 54), with `−2` sentinels present;
  ~**29,300 ha** of strong persistent detections (`delta3>0.5 & pmax3>0.5`) centred at
  −71.71, −42.40 — the 2015 Cholila forest burn (~40,000 ha).

---

## 7. Open items / future changes

- **Prerequisite:** export the buffered `C.REGION_RASTER`
  (`scripts/export_region_raster.py`) before a production run; until then border-buffer pixels
  read as non-observed (`n = −2`). (That export is slow not from compute but from re-rasterizing
  lazily-computed buffer/difference geometries over ~3 B pixels — materialize the buffered FC
  first if speed matters.)
- **`date_post` timing:** over the Cholila scar mean `date_post3` ≈ DOY 220 (early August 2015),
  later than the Feb–Mar fire — likely the delta-argmax favouring a post-winter persistence jump.
  Worth a domain look; it's exactly what the manual masking/review step exists to catch.
- **Cost lever:** profiled in §8. The cost is the 130-term LR + cloud-masking + graph plumbing,
  evaluated over ~150 mosaicked scenes; the time-series array metrics are < 1%. So the levers are
  **predictor pruning** (BACKLOG: prune correlated terms per class) and a **shorter padded
  window**, not the array code or the orchestration. Coarser export tiling (region-year) would cut
  task count but risks per-task limits — the carta grid exists to avoid them.
- **Not stored:** the previous-year `veg_fire` (cheap to recompute; not worth the memory).

---

## 8. Performance profile — where the per-tile time goes

A real export is **compute-bound, not I/O-bound**, and the cost is dominated by per-image
processing repeated over the ~150 date-mosaicked Landsat scenes — **not** by the time-series
array work. Two measurements pin this down.

**Wall-clock vs. burnable area** (real export tasks, scale 30):

| tile | fittable area | run time |
|---|---|---|
| `SK-19-Y-A` (Cholila, dense) | 11,287 km² | 52 min |
| `SF-19-X-D` (near-empty) | 451 km² | 19 min |

Two points → runtime ≈ **~17 min fixed floor + ~0.003 min/km²**. The floor is per-tile overhead
(building the ~294-scene series, the LR graph, export setup) paid regardless of how much land is
burnable — so even empty tiles cost ~the floor as a full export, and the per-tile **mean is
~20–25 min** (a tail of dense tiles pulls it up). At 2 tasks/account in parallel that's
**~2–3 days/year on one account**.

> Measure burnable area with `ee.Image.pixelArea().updateMask(is_fittable).reduceRegion(sum)` —
> **not** a `frequencyHistogram` of the class band, which `bestEffort` resampling distorts badly
> (it reported `SF-19-X-D` as 74% fittable when the area integral says 2.6%).

**True EECU breakdown** (genuine GEE profiler via `ee.profilePrinting()`, full bpts graph over a
6 km box @30m; the array machinery is exercised but cheap):

| group | EECU·s | operations |
|---|---|---|
| 130-term LR arithmetic | **~610** | `Image.reduce` (per-term sum), `select` (2.1M band selects), `multiply`+`add`, `updateMask`/`float`/`addBands` |
| graph plumbing | **~490** | infrastructure for a **5.6M-node** graph (scales with images × terms) |
| cloud masking | **~219** | `bitwiseAnd`/`or`/`not` — `_mask_clouds` decoding QA_PIXEL bits per scene |
| `mosaic_by_date` | **~80** | per-date mosaicking |
| **array + time-series metrics** | **~8** | `arrayReduce`/`arrayCat`/`arraySlice`/`toArray`/`arrayGet` combined — **< 1%** |

*(Excludes the profiling harness's own `reduce.mean`.) Reproduce with `scripts/profile_bpts.py`.*

**Conclusions / optimization priorities:**

1. **Do not optimize the array/metric code** — it's < 1% of cost. The careful padded-array design
   is essentially free; the expense is everything *upstream* of it.
2. **Prune predictors (highest-leverage, already in `BACKLOG.md`).** The LR arithmetic (~610) and
   much of the plumbing (~490) scale with term count; the `select` line alone is pure per-term
   band-selection overhead. 130 → ~40 terms could roughly halve total cost. Requires a refit +
   re-validation.
3. **Trim the padded window (#2 lever).** It cuts *every* per-image cost (LR, masking, mosaic,
   plumbing) in proportion to image count. The Sep(y−1)–Apr(y+1) window exists only to harvest
   3+2 padding obs; a shorter pad is a smaller change than pruning and needs no refit.
4. **Cloud masking is a surprising ~15%** (`_mask_clouds`, 6 bitwise ops × ~150 scenes) — reducible
   but riskier to touch.
5. **Wall-clock, today, with no code risk:** distribute across accounts. Per-account parallelism is
   capped at ~2–3 tasks, so a single year is bounded at ~2–3 days; splitting a year's tiles across
   N accounts (disjoint subsets) is the only lever that helps immediately — see
   `03-colab_multi_export.md` (currently splits *by year*, not within a year).

---

## 9. Reduced-LR pruning + EECU test — STATUS / HANDOFF (in progress)

Goal: deploy a **single reduced predictor set shared by all classes** to cut step-03 compute
(lever #2 of §8). Full pipeline and rationale: `notebooks/lr_term_pruning.qmd` (has a "Context &
constraints" intro for auditors).

**What's decided.** Rank terms by standardized coef `|β_z|` (= `coef_std` in the model CSVs),
normalize each class to sum-1, aggregate to a global importance weighted by **relative area in
Argentina** (smoothing **K=3**, `area^(1/3)`). Candidate sizes **P ∈ {30,40,50,60,80}** were refit
and compared on **out-of-fold AUC + Brier** vs full-129. Result: reduced set is ~lossless for every
class **except `grassland_pat`** (the #1-area class, 22%), which dips most at P=40 and recovers by
**P=50**. Area-weighted mean ΔAUC is ~0 at P≥50 under all weightings. **Leaning P=50.**

**Pipeline artifacts (all reproducible).**
- `config/pruning_terms.csv` — the candidate shared term sets (K3, each P; interaction hierarchy
  closed so a kept `A__B` keeps mains `A`,`B`). Written by the notebook.
- `scripts/refit_pruning_sweep.R` — refits all classes per P via `02-model_fitting.R`'s
  `KEEP_TERMS_CSV`+`RUN_TAG` hooks; outputs to `models-store/pruning/K3_P<P>/`, aggregates
  per-class OOF metrics to `models-store/pruning/metrics_by_P.csv` (read by the notebook plots).
  **DONE — all 5×23 fits complete.** Canonical `models/` was NOT touched.
- `02-model_fitting.R` hooks: `KEEP_TERMS_CSV` (glmnet `exclude`s non-listed cols) + `RUN_TAG`
  (outputs → `models-store/<tag>/`). Unset → full-129 to `models/`, as before.

**Key deployment fact.** GEE prediction is **term-count-driven**: `load_all_coefficients(models_dir)`
reads whatever rows are in the CSVs and `build_coeff_image`/`compute_burn_prob_img` build one band
per term — so **fewer rows → fewer bands → less compute**. The sweep's reduced CSVs still have 129
rows (zeros for pruned terms), which would compute like full-129. So deployment must use CSVs
**trimmed to the P-set rows**. Trimmed deploy sets already built:
`models-store/pruning/deploy_K3_P30/` (33 rows = intercept+32) and `deploy_K3_P50/` (52 = +51).

**EECU A/B/C test — RUNNING (read when SUCCEEDED).** Three Cholila exports, identical tile
(`SK-19-Y-A`, 2015) and **2-month padding** (the old full-129 run's 45.8 EECU-h used 4-month
padding so is NOT comparable), differing only in term count:

| task / asset (in `C.BP_TS_METRICS_COL`) | terms | interim EECU-h (mid-run) |
|---|---|---|
| `bpts_eecutest_full129_SK-19-Y-A` | 130 | (running) |
| `bpts_eecutest_K3P50_SK-19-Y-A`   | 52  | ~20.3 |
| `bpts_eecutest_K3P30_SK-19-Y-A`   | 33  | ~18.2 |

Read finals with `ee.data.listOperations()` → filter `description` contains `eecutest` →
`metadata['batchEecuUsageSeconds']/3600`. (Interim values are not final; wait for `SUCCEEDED`.)

**FINAL result (all SUCCEEDED):**

| task | terms | EECU-h | attempt | wall-clock |
|---|---|---|---|---|
| full129 | 130 | 27.3 | 1 | 22.8 min |
| K3P50 | 52 | **20.6** | 1 | 44.1 min |
| K3P30 | 33 | 24.0 | **2 (retried!)** | 39.8 min |

**Read it via the clean attempt-1 pair: full129 27.3 → P50 20.6 = ~25% less EECU** for 60% fewer
terms — monotonic, confirms the trimmed sets deploy fewer bands (not 129 zeroed). **K3P30's 24.0 is
a measurement artifact: `attempt=2` means it ran twice and `batchEecuUsageSeconds` bills retries
cumulatively** — its true single-run EECU would be well below P50's. (Re-run K3P30 if a clean P30
number is wanted.) Caveats: (a) 60% fewer terms → only ~25% EECU ⇒ a large *term-independent* fixed
cost (scene load, mosaic, array metrics; §8) that pruning can't cut; (b) **wall-clock is pure
scheduling/retry noise** (P50, lightest by EECU, took the longest) — use EECU@attempt-1 only, and
treat single-tile EECU as noisy (retries/worker variance).
The whole-tile EECU includes the term-independent fixed cost (scene load, mosaic, array metrics),
so the saving ratio is **less** than 52/130 — it's the *realized* tile-level payoff. Test assets
are deletable afterward (user runs deletions).

**RESOLVED (2026-06-27) — see §11.** P=50 was adopted. Rather than promoting into a single `models/`
deliverable, the coefficient sets were reorganised into git-tracked per-model folders
(`models/P129/`, `models/P050/`, …) so the deployed set travels with the repo for the Colab
multi-account export; `C.DEPLOYED_MODEL = "P050"` selects it. 2015 is being re-exported with P=50
(the earlier 2015 queue was the obsolete full-129 model and was cancelled).

## 10. Tile-merge export test — DONE (2026-06-27): merging REJECTED

Question: does exporting several cartas as **one merged image** take similar **wall-clock** to a
single tile? If yes, merging tiles per task would amortise the ~17-min per-task fixed floor (§8)
and cut wall-clock. It never cuts compute or storage (the merged image still processes every
tile's area) — acknowledged going in; the only hoped-for payoff was paying the fixed floor once.

**Setup.** `scripts/test-03-tilemerge.py` submitted three 2015 exports with the **reduced P=50
model** (`models-store/pruning/deploy_K3_P50`) and the 16-band output, identical except for how
many cartas were merged into one image. The four tiles formed a 2×2 square:
`tl=SK-19-V-B  tr=SK-19-X-A  bl=SK-19-V-D  br=SK-19-X-C` (each carta ~14k km²).

**FINAL result (all SUCCEEDED, attempt 1):**

| asset | tiles | EECU-h | wall-min | wall/tile | EECU-h/tile | wall vs 1× |
|---|---|---|---|---|---|---|
| `bpts_2015_tilemerge_1` | 1 | 38.3 | 48.9 | 48.9 | 38.3 | 1.0× |
| `bpts_2015_tilemerge_2` | 2 | 145.8 | 146.7 | 73.4 | 72.9 | **3.0×** |
| `bpts_2015_tilemerge_4` | 4 | 251.7 | 250.7 | 62.7 | 62.9 | **5.1×** |

**Conclusion — DO NOT merge tiles; production exports one carta per task.** Both wall-clock and
EECU grow **super-linearly** with merged area (4× tiles → 5.1× wall, 6.6× EECU), so per-tile cost
*rises* when merging (~49→~63–73 wall-min/tile). The decision rule was "merge only if `tilemerge_4`
wall ≪ 4× `tilemerge_1`" (≪ 195.6 min); it came in at **250.7**, *above* 4×. Why the floor doesn't
help: the single tile is the only run where wall (48.9) > EECU-h (38.3) — that ~10-min gap *is* the
fixed floor (§8) — but once merged, wall ≈ EECU-h (the task becomes purely compute-bound) and the
floor is swamped by the extra area's compute. Test assets (`tilemerge_2`/`_4`) are deletable; the
single-tile `tilemerge_1` was renamed to its production name `bpts_2015_SK-19-V-B` (it is a valid
P50/16-band export, so renaming avoids re-running that tile).

> The `tile_geom=` override added to `burn_prob_collection`/`bpts_image` for this test was
> **reverted** after the result — there is no production use for it. Single-tile geometry only.

**Downstream design notes reached this session (step 04 SNIC / regions).** Define fire-regions as
**unions of cartas with boundaries in low-fire zones**; build the SNIC input as a mosaic of *only*
those cartas. GEE's neighborhood ops fetch margins **only from the input image's definition** — a
region-only input has masked edges and imports nothing extra, so **no edge buffer is needed**
(boundaries avoid fires) and compute is minimal. The residual concern is GEE-SNIC's **internal
~256-px tile seams** (independent of region boundaries) — verify on one test segmentation before
committing the step-04 tiling. Step-03 export tiling and downstream regions are decoupled for
correctness but NOT cost: cheapest downstream is region = exact union of step-03 tiles, no buffer,
so align the export tiling to the hand-drawn fire-regions where export limits allow.

## 11. Deployed model — P=50 term-pruning (decided 2026-06-27)

**All production prediction/export uses the reduced P=50 model** (52 terms: intercept + 51), not
the full step-02 fit (130 terms).

**Where the coefficients live.** Each model variant has its own git-tracked folder under
`collection-01/models/`, named `P<NNN>` (3-digit, leading zeros; all are CV scheme **K=3**, so K is
not in the name):

| Folder | Model | Rows |
|---|---|---|
| `models/P129/` | full fit | 130 |
| `models/P080/` `P060/` `P040/` `P030/` | pruning variants (top-P cut) | 81 / 62 / 42 / 33 |
| `models/P050/` | **DEPLOYED** | 52 |

`P` is the top-P percentile cut on the global term ranking, *not* the term count. Reduced folders
hold only `intercept + kept terms` (trimmed at write time by `02-model_fitting.R`), so GEE builds
only the deployed bands — prediction is term-count-driven (§9). **These CSVs are git-tracked** so
the Colab multi-account export (`03-colab_multi_export.md`) gets them from a plain `git clone`; the
old `models-store/pruning/deploy_K3_P*` sets lived under the gitignored Insync symlink and could not
travel with the repo — that was the reason for this reorg.

**Wired as the default.** `C.DEPLOYED_MODEL = "P050"` and `C.COEF_DIR = models/P050`;
`load_all_coefficients()` reads `C.COEF_DIR` when called with no `models_dir`, so `bpts()` and every
export — all years, all worker accounts — use P=50 automatically. **Redeploy = change that one
line.** Pass an explicit folder (e.g. `C.MODELS_DIR / "P129"`) only for diagnostics.

**Why P=50.** The §9 term-pruning sweep (K3, P ∈ {30,40,50,60,80}) showed OOF predictive skill
essentially flat from the full model down to P≈50, with a real drop only below that. P=50 keeps the
skill of the full model while cutting terms 130→52, and realises ~25% lower EECU per tile than
full-129 at attempt-1 (§9 EECU test) — the rest being the term-independent fixed cost (scene load,
mosaic, array metrics; §8). It's the best skill-preserving point on the curve.

**Reproducing the folders.** `scripts/refit_pruning_sweep.R` re-runs each P (it sets `COEF_TAG=P<NNN>`
+ `KEEP_TERMS_CSV`); `02-model_fitting.R` with no env writes the full fit to `P129/`. The trimming is
deterministic: `models/P0<P>/` = the K3_P<P> reduced fit filtered to `intercept + keep_K3_P<P>` terms.
