# 03 — Burn-probability time-series metrics (`bpts`)

For every focal year × MapBiomas *carta* tile, this step applies the step-02 logistic
regression to **every Landsat observation** of every pixel, then reduces that per-pixel
probability series to a **16-band annual summary** — how high the probability got, how
persistently it stayed there, how sharply it jumped, when, and on how many observations the
answer rests. It is the temporal stage of the method: it never decides that a pixel burned, it
measures the evidence that step 04 segments and step 06 classifies.

## Foundations

**Burn probability has to be smoothed before it is read as detection** — a single high
observation is as likely to be shadow, ash or a wet scene as fire. Collection 0 smoothed with a
median over K=5 observations; here vegetation types recover at very different speeds and image
density varies by pixel and year, so we carry two shorter windows instead — **K=3** and **K=2** —
and export both. The median (not the mean) keeps values on the original probability scale;
nothing is transformed to logit or log.

**The evidence is three things: magnitude, persistence and change**, all measured in *numbers
of valid observations* and never in elapsed time, because the Landsat series is irregular and
its density is itself informative. Change is a **delta = `minfore` − `maxback`**: a jump in
probability that then *holds*. `minforeK` is the post-jump floor (minimum of the next K),
`maxbackK` the pre-jump baseline (maximum of the previous K) — and taking the *max* of the back
window is what stops a noisy low observation inside an already-burned scar from manufacturing a
second detection.

**Why one graph and one export.** The step is really two processes — per-observation
probability, then the per-pixel reduction — but the intermediate probability collection
(hundreds of images per tile) is far too large to store, so both run inside one computation and
only the annual summary is written. That is also why all the machinery lives in the one script.

## Inputs → Outputs

`Landsat C2 SR (padded window) + prev-year MB mosaic + veg_fire + P050 coefficients` →
**`bpts`** → `one 16-band int16 image per year × carta`

| Input / Output | What it is | Where |
|---|---|---|
| Landsat C2 SR | L5/L7/L8/L9, cloud-masked, deduped by date (`mosaic_by_date`) | `F.get_landsat`, `F.add_indices` |
| MapBiomas annual mosaic | previous-year spectral summaries (`med`/`wet`/`dry`/`sd`) | `F.get_mb_mosaic_bands` |
| `veg_fire` | previous-year LULC × region, the class that selects the coefficients | `F.veg_fire_image`, `C.REGION_RASTER` |
| Coefficients | the deployed model, one CSV per fittable class | `models/P050/` (`C.COEF_DIR`) |
| Tiles | the 248 cartas intersecting the buffered-Argentina FC | `C.CARTAS_FC`, `C.ARG_BUFFER_FC` |
| **Output** | `bpts_YYYY_<tile-id>`, 16 bands, int16, EPSG:4326 @ 30 m | `C.bpts_target_col(year)` |

Years are `C.YEARS` (1999–2025). Each asset carries `year`, `tile_id` and a mid-year
`system:time_start` (for the inspector). **The destination is year-dependent**: the
`mapbiomas-argentina` asset home ran out of space, so **1999–2009 export to
`mapbiomas-chaco`** instead (`C.BP_TS_METRICS_COL_CHACO`, a legacy-rooted project — no
`/assets/` segment in the path). The launcher routes each year with `C.bpts_target_col`; every
**reader** (step 04, the samplers) must `merge` the two collections, because a tile-year can be
in either.

## How it works

### The deployed logistic regression

`veg_fire` is the previous-year MapBiomas class crossed with the region raster
(`region_id * 100 + mb_class`, remapped by `C.VEG_FIRE_TO`); pixels outside any region or with
an unmapped class fall through to the **non-observed sentinel 25**, non-burnable covers to
**24**. The LULC year is `min(year − 1, C.MB_LIMIT_YEAR)`.

Every model CSV exports **raw-scale coefficients** — the mean-centering used while fitting is
folded into the intercept and main slopes (`models/README.md`) — so prediction is a plain dot
product with no centering before products: intercept + prev-year mosaic mains + focal spectral
mains + focal×focal + prev×focal, through a logistic. `_parse_term` reads the factors out of the
term names: `_t` is a focal index (`BLUE_t` → `BLUE`, matching `add_indices`), a summary suffix
is a mosaic band via `C.PREV_SUFFIX_MAP` (`GREEN_med` → `mb_mos_green_median`), `A__B` is a
product, and `(Intercept)` becomes `intercept_term` (parentheses are illegal band characters).

`build_coeff_image` turns the per-class coefficients into one band per term, assigned per pixel
by remapping `veg_fire` (non-fittable classes get 0 and are masked out anyway). The prev-only
part of the linear predictor and the prev factor of every cross term are **constant within a
year**, so `build_prev_scalar` and `build_cross_factor1_coef` precompute them once per tile-year
and only the focal factor is multiplied in per image. Every multiply first renames the feature
bands to the coefficient band names (`_select_renamed`), so both operands have identical names
in identical order — correct under any GEE band-matching rule.

### Per-observation quantities

For a valid observation `t` with probability `p[t]` at **day-number** `d[t]` — integer days
from the focal year's 1 January, via EE's calendar-aware `'day'` unit, so focal observations are
0–365, prev-year padding is negative and next-year padding > 365, and every difference below is
an exact whole-day count across the year boundary:

- forward persistence `minfore3[t] = min(p[t..t+2])`, `minfore2[t] = min(p[t..t+1])`;
- pre-jump baseline `maxback3[t] = max(p[t−3..t−1])` (conservative), `maxback2[t] =
  max(p[t−2..t−1])` (permissive);
- change `delta3 = minfore3 − maxback3`, `delta2 = minfore2 − maxback2`;
- widths in days: `prevwidth3 = d[t−1] − d[t−3]`, `prevwidth2 = d[t−1] − d[t−2]`,
  `jumpgap = d[t] − d[t−1]`, `postwidth3 = d[t+2] − d[t]`, `postwidth2 = d[t+1] − d[t]`.

`jumpgap` is strong fire evidence when **short**; a long one may be slow change rather than
fire, or fire seen through a thin image series.

### Padding the focal year

Window metrics starve at the series extremes — `maxback3` needs three observations behind,
`minfore3` two ahead — so the focal year borrows **3 observations before and 2 after**:
asymmetric on purpose, because symmetric padding of 2 would under-supply `maxback3` at the first
focal observation. The argmax search is always restricted to focal observations, so a padded
observation is only ever *context*; a burn can never be detected twice in adjacent years.

The neighbours' images cannot be taken as-is (the literal nearest scene may be cloud-masked at
this pixel), so burn probability is computed for **M months** on each side (`C.pad_months`) and
the **3 latest** prev and **2 earliest** next observations are kept (`C.PAD_OBS_LEFT`/`RIGHT`).
Padded observations use the **focal year's** previous-year LULC/mosaic context — strictly they
should use their own, but for 3+2 observations the focal year's is the better approximation.
**M is year-dependent**: 2 months from 2001 on, 4 for 1999 and 3 for 2000, because the early
Landsat era is sparse (L7 launched mid-1999). A narrower pad is also much cheaper, since every
per-image cost scales with scene count.

### Two padded arrays, one per window

We build **two** padded arrays rather than one with variable left-padding, so that
**fixed-offset array slices are always correct** for unmasked pixels:

- the **K=3** array `[≤3 prev | T focal | ≤2 next]`, kept only where length ≥ 6;
- the **K=2** array `[≤2 prev | T focal | ≤1 next]`, kept only where length ≥ 4.

`arraySlice` clamps when a side has fewer observations, and the length test then keeps only
pixels wide enough that, after dropping the leading 3 (resp. 2) and trailing 2 (resp. 1)
positions, at least one focal observation has full back and fore context. The fixed offsets
*automatically drop* boundary focal observations that genuinely lack it — with only 2 prev
observations, the first focal one, which cannot have a real `maxback3`, is excluded — however
many padding observations arrived. A pixel failing one window's test has *that window's* bands
masked: a quality flag, not an error.

### The peak and its bundle

Each delta is collapsed **independently**: it finds its own argmax `t*` over the focal year and
its bundle is read there, because the optimal transition observation differs by window and tying
both to one peak would mis-anchor the other. The bundle is a `[T,6]` array
`[delta, minfore, d_t, d_{t−1}, d_{t−3}, d_{t+2}]`, sorted descending by the delta column; the
top row gives the six scalars. Stored at `t*`: the delta, `minforeK` (the post level — `maxback`
is recoverable as `minforeK − deltaK`, so it is not stored), `jumpgap`, the relevant
`prevwidth`/`postwidth`, and `date_post = d[t*] + 1`, the day-of-year of the post-jump
observation. Since `t*` is always a focal observation, `date_post` falls inside the focal year.

Three whole-series bands are not tied to any peak: `pmax1` (max raw probability), `pmax2`
(max `minfore2`) and `pmax3` (max `minfore3`). `n` — the count of focal observations — is the
**sole density/quality channel**. All bands are always exported; which of them to trust at a
given pixel is a downstream decision.

### Output bands and encoding

All 16 bands are **int16-encoded** (≈ half the float32 asset size), applied in `bpts_image`;
the band groups and `PROB_SCALE` live in `workflow/03-bp_ts_metrics.py`.

| band | definition | decode | masked when |
|---|---|---|---|
| `delta3_peak` | max(delta3) over the focal year | ÷10000 | K=3 array short |
| `minfore3_peak` | minfore3 at the delta3 argmax | ÷10000 | K=3 array short |
| `jumpgap3` | d[t*]−d[t*−1], days | as-is | K=3 array short |
| `prevwidth3` | d[t*−1]−d[t*−3], days | as-is | K=3 array short |
| `postwidth3` | d[t*+2]−d[t*], days | as-is | K=3 array short |
| `date_post3` | d[t*]+1, day-of-year (1–366) | as-is | K=3 array short |
| `delta2_peak` … `date_post2` | the same six for K=2 (`prevwidth2 = d[t*−1]−d[t*−2]`, `postwidth2 = d[t*+1]−d[t*]`) | idem | K=2 array short |
| `pmax3` / `pmax2` | max minfore3 / minfore2, whole series | ÷10000 | that array short |
| `pmax1` | max raw probability, whole series | ÷10000 | n = 0 |
| `n` | focal obs count; **−1** non-burnable, **−2** non-observed | as-is | **never masked** |

**Everything is signed int16, including the day bands.** Every value fits well inside ±32767:
probabilities ×10000 span 0–10000, the deltas are genuinely signed, day gaps are ≲250, DOY is
1–366, `n` carries the sentinels. The gaps are mathematically ≥ 0 (the array is sorted ascending
by date), but keeping them signed means a stray negative stays visibly negative instead of
wrapping to a huge unsigned value, and downstream reads stay uniform. Missing data is never
given a probability — masked pixels contribute no array elements, so a fittable pixel with no
observations comes back with `n = 0`.

## Run

```bash
# one tile-year (foreground is fine — one task)
$PYTHON collection-01/workflow/03-bp_ts_metrics.py --year 2015 --tile SK-19-Y-A
# a whole year — ~one task per carta, hundreds of task.start() round-trips: always tmux
tmux new-session -d -s bpts2015 \
  '$PYTHON -u collection-01/workflow/03-bp_ts_metrics.py --year 2015 2>&1 | tee bpts2015.log'
# progress only: done / in flight / to launch
$PYTHON collection-01/workflow/03-bp_ts_metrics.py --year 2015 --status
```

The launcher is **idempotent**: a tile-year is skipped if its asset exists **or** it already
has a PENDING/RUNNING task. Both checks are **cross-account**, which is what makes a
multi-account run safe — done comes from the shared output collections, in-flight from
`listOperations`, which is *project-scoped* (it returns every user's tasks) and is polled over
every project in `C.BPTS_TASK_PROJECTS` plus the active one. If the running account cannot read
one of them, a `UserWarning` names the projects that *were* evaluated; that residual gap is
covered by the per-year Excel sign-out. `--status` (in Python, `bpts_status(year)`) reports the
same three states and returns the `to_launch` list, with no GEE compute, so a killed run resumes
exactly the missing tiles.
`--overwrite` resubmits anyway (GEE still will not overwrite an asset — delete it first), and
`--target-col` forces one destination for every requested year. Distributed multi-account runs:
`03-colab_multi_export.md`.

## Key decisions

- **The deployed model is P=50, not the full fit** (52 coefficient rows). Skill is flat from
  the 130-term fit down to P≈50 and drops below it, and GEE prediction is **term-count-driven** —
  `load_all_coefficients` builds one band per row present in the CSVs, so a trimmed CSV really
  does compute less (measured: ~25 % lower EECU per tile). Each variant keeps its own tracked
  folder (`models/P129/`, `models/P050/`, …) so the deployed set travels with a plain
  `git clone` for the Colab export, `C.DEPLOYED_MODEL` selects it, and **redeploying is that one
  line**. Route and evidence: `notes/02-lr_term_reduction.md`,
  `notes/03-performance_profile.md`.
- **One carta per task; tiles are never merged.** Merging was tested to amortise the per-task
  fixed floor and both wall-clock and EECU grew *super-linearly* with merged area, so per-tile
  cost rises. `notes/03-tile_merge_test.md`.
- **Two windows, each with its own argmax.** K=3 is the conservative reading, K=2 the permissive
  one; they are collapsed independently so neither is anchored on the other's peak. Step 04 then
  chooses between them **per pixel** on `n` (dense → the K=3 pair, sparse → K=2) and takes its
  date from the K=2 pair.
- **`n` is the only quality channel.** The inter-observation gap bands were dropped as redundant
  with it (18 → 16 bands); `notes/03-dropped_timediff_bands.md`.
- **Do not optimize the array code.** Profiling puts the whole array/time-series machinery at
  **< 1 %** of per-tile cost — the expense is the LR arithmetic, cloud masking and graph
  plumbing over ~150 scenes. `notes/03-performance_profile.md`.

## Gotchas

**The governing array rule, inherited from collection 0**: an empty array only *throws* on
(a) **unmasked** pixels and (b) **constant** array images, which GEE evaluates eagerly. Masked
raster pixels short-circuit cleanly. So every `arrayReduce` / `arrayGet` / `arraySlice(axis ≥ 1)`
site must reach either a non-empty array or a masked pixel. **Read this before touching the
array code** — each item below is a fix that is still load-bearing:

- **`arraySort(keys)` needs keys of the same rank as the array.** Sorting the `[T,6]` bundle with
  an `arrayProject([0])`'d 1-D key throws *"Image and keys must have same dimensions"*; sort with
  the negated `[T,1]` delta column.
- **An empty `ee.Array` cannot stay 2-D.** Slicing to zero rows collapses it to 1-D, which breaks
  the downstream `arraySlice(1, …)` whenever a prev/focal/next sub-collection is globally empty.
  `safe_to_array` therefore never returns an empty stub: it prepends a fully-masked 2-band
  sentinel image, so `toArray()` is always statically 2-D and no-obs pixels still come back
  masked with `n = 0`.
- **`compute_burn_prob_img` must carry `system:time_start`.** It builds a fresh
  `prob.addBands(day_num)` image; without copying the timestamp the `filterDate` split into
  prev/focal/next returns empty and every pixel gets `n = 0` — a structurally fine, entirely
  empty product, which only showed after a full export.
- **A whole-series reducer over a length-`n−1` array needs an `n ≥ 2` guard.** A pixel with
  exactly one focal observation has a non-empty array (so it is not masked) but an empty derived
  one, and reducing it throws. No current band hits this; the next one added might
  (`notes/03-dropped_timediff_bands.md`).
- Three smaller ones: `updateMask(cond)` leaves unmasked **where the condition holds**;
  `ImageCollection.toArray()` stacks images on axis 0 and bands on axis 1, so select
  `['prob','day_num']` first to fix the column order; `arrayLength` is the one array op that is
  safe on an empty array, and `n` uses it with `unmask(0)` before the −1/−2 sentinels are
  applied.

**Interactive `getInfo` / `reduceRegion` on the full graph hits the user memory limit** — even
`bandNames()`, because `safe_to_array` forces the collection to be built. That is not a bug: the
batch export tiles the computation and is the intended run path. For interactive debugging feed
`compute_bp_ts_metrics` small synthetic arrays, or sample a single Landsat image.

**`date_post` is not the fire date.** It is the day-of-year of the *post-jump* observation; the
burn date used downstream is the K=2 mid-date `date_post2 − jumpgap2/2`, computed in step 04.
Over a known scar `date_post3` has been seen to land months late (`notes/03-validation_2015.md`).

## Files

| File | Role |
|---|---|
| `workflow/03-bp_ts_metrics.py` | **everything**: coefficient loading, the LR in GEE, the array metrics, the `bpts` driver, the CLI |
| `utils/functions.py` | the cross-step helpers it calls — `get_landsat`, `add_indices`, `get_mb_mosaic_bands`, `veg_fire_image` |
| `utils/constants.py` | years, tiles, the two destination collections, padding, `DEPLOYED_MODEL`, the `veg_fire` table |
| `models/P050/` | the deployed coefficients (one CSV per fittable class) |
| `scripts/test-03-bp_ts.py` | interactive/headless checks; also the `importlib`-by-path idiom every step-03 consumer needs, since the filename is not a valid Python identifier |
| `scripts/test-03-model_load.py` | asserts the deployed CSVs parse into the expected term set |
| `scripts/profile_bpts.py` | reproduces the EECU profile |
| `scripts/export_region_raster.py` | paints `C.REGION_RASTER` (the buffered region ids) |

## Related

- [`00-overview.md`](00-overview.md) — where the temporal stage sits; [`02-model_fitting.md`](02-model_fitting.md) — the model being deployed here; [`04-snic.md`](04-snic.md) — what consumes these bands.
- [`03-colab_multi_export.md`](03-colab_multi_export.md) — the distributed multi-account export.
- `notes/03-performance_profile.md`, `notes/03-tile_merge_test.md`, `notes/03-validation_2015.md`, `notes/03-dropped_timediff_bands.md`, `notes/02-lr_term_reduction.md`.
- `notebooks/burn_prob_ts_metrics.qmd` (the candidate metrics explored on synthetic signals), `notebooks/bpts_metrics_explained.qmd` (the band-by-band walkthrough, in Spanish), `notebooks/lr_term_pruning.qmd` (the P sweep).
- `scripts/bp_ts_metrics_local_train.R` + `scripts/annual_data_download.py` — a local, period-based replica of these metrics over the training observations, built for step 04's threshold study (`04-snic.md` "Seed and candidate").
