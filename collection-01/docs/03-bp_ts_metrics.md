# 03 — Burn-probability time-series metrics

## Related notebook

- `notebooks/burn_prob_ts_metrics.qmd` — exploration of candidate summary metrics (rolling means, forward differences, etc.) on synthetic signals. Already analyzed and thought about, but mentioned for the curious. Ideas in this md are more mature.

## Main ideas

- bp (burn probability) must be smoothed before we detect something. In Col 0 we used the median of K = 5 obs. Now we have veg types that recover rapidly, so we should also use a smaller window. Not mean, just median, so it keeps the values in the original scale.

- Metrics are based mostly on (smoothed) probability magnitude (high prob), persistence, and change. Persistence and smoothing are based on number of consecutive obs, not time span, because the landsat series is irregular and the observation density varies by pixel and year. Smoothing should be softer (smaller K) in regions of rapid recovery and in moments of low image density, which can be computed pixel-wise, by year.

- In Col 0 we used median5 centred at the middle obs, because when a fire burned in the middle obs (just before observation), it showed the minimum prob of the 3 first burned obs. Then, computing the diff(median5), would show a large increase there. It can be softened to K = 3. 

- In Col 1 Claude proposed to use a delta (no smoothing) * min3: focal obs - min(3 following obs) (or reversed). That detects a jump in burn prob followed by persistence, but does not smooth the pre-jump period, which can be necessary (in burned areas with stable burned signal there are low-prob noisy observations, which would create false detections if the pre-jump is not smoothed). 

## Annual metrics extraction strategy

We part from the observation-level burn probability and process all pixel-wise. We use only valid observations (clouds dropped, so "consecutive" means consecutive *valid* obs; a gap just means more elapsed days to collect the window).

Everything is on the **probability scale**, neither logit nor log.

### Per-observation quantities: aggregate time-series (still a time series at this stage)

Let `p[t]` be the obs-level burn probability at valid obs `t`, dated `d[t]` (fractional year).

Forward persistence (post-jump level), both window sizes:

- `minfore3[t] = min(p[t], p[t+1], p[t+2])` (K = 3)
- `minfore2[t] = min(p[t], p[t+1])`         (K = 2)

Pre-jump baseline (back), two estimators:

- `maxback3[t] = max(p[t-3], p[t-2], p[t-1])`  (conservative; = `diff(median5)` on monotone runs)
- `maxback2[t] = max(p[t-2], p[t-1])`           (permissive; = `diff(median3)` on monotone runs)

Time widths (record all — they inform gaps, persistence, and rate of change):

- `prevwidth3[t]  = d[t-1] - d[t-3]`  (back-window span; relevant to `maxback3`)
- `prevwidth2[t]  = d[t-1] - d[t-2]`  (back-window span; relevant to `maxback2`)
- `jumpgap[t]    = d[t]   - d[t-1]`   (gap the jump is measured across)
- `postwidth3[t] = d[t+2] - d[t]`     (persistence span, K = 3)
- `postwidth2[t] = d[t+1] - d[t]`     (persistence span, K = 2)

jumpgap is particularly useful to detect slow or fast changes. It's stronger fire evidence when short. If long, may be a slow change (not fire) or fire under low image density.

Change variables (delta), computed from the previous metrics:

Three parameterizations, each a time series over `t`:

- `delta3[t] = minfore3[t] - maxback3[t]`  (both K=3 windows)
- `delta2[t] = minfore2[t] - maxback2[t]`  (both K=2 windows)

### Collapsing the time series to single annual values (multiband image per year)

We must reduce each per-pixel series to scalars for the SNIC step: 

Treat each delta definition independently: find **its own** argmax `t*`
over the year, and extract **its own** relevant variables at that `t*`. So `delta2` and `delta2` each yield a self-consistent bundle anchored at their own peak.

Rationale: the optimal transition obs differs by parameterization (K = 3 vs K = 2); tying everything to one delta's peak would mis-anchor the others.

At each delta's `t*`, extract (its own): 
- the delta value (which is the max in the series), 
- the `minforeK` (post level)
[backmax is not stored because it can be computed as minforeK-deltaK]

- `jumpgap` (always, no matter which delta)
- the corresponding `prevwidth`/`postwidth`, depending on the window used
- the focal date (`date_post = d[t]`). (date_post - jumpgap / 2 gives the middle date, a good burn candidate-date)

A few metrics to export for the whole series (not based on related to each delta's max):
- `pmax1`: maximum raw probability,
- `pmax2` = max(`minfore2`)
- `pmax3` = max(`minfore3`)

And the following quality metrics:
- `n`: the number of observations in the series (quality band)
- `timediff_med`: median(diff(date)), the median gap, transformed to days
- `timediff_max`: max(diff(date)), the maximum gap, transformed to days

All variables exported always; the decision on which to use depends on image density later.

Minimum obs required — implemented as two separately padded arrays with guaranteed structure:

- **K=3 padded array** [3 prev + T focal + 2 next]: requires 3 obs from prev year AND 2 obs from next year to be available; masked otherwise. Minimum T = 1 focal obs → extended length 6. Minimum requirement: `ext_len_k3 >= 6`.
- **K=2 padded array** [2 prev + T focal + 1 next]: requires 2 obs from prev year AND 1 obs from next year. Minimum T = 1 focal obs → extended length 4. Minimum requirement: `ext_len_k2 >= 4`.

Using two arrays with guaranteed structure (rather than one combined array with variable left-padding) ensures the fixed-offset array slices used to compute window metrics are always correct for unmasked pixels.

Pixels where a padding requirement cannot be met (e.g., the previous year had fewer than 3 valid obs in the Sep–Dec window) will have the corresponding K=3 or K=2 bands masked — not an error, just a quality flag.

Arrays must be masked by availability before computation so GEE does not throw errors on insufficient data.

### Building the raw burn probability time-series

Using variable-width windows to compute aggregates implies that a series looses a variable number of observations at the extremes: `minfore3` needs 2 extra obs ahead; `maxback3` needs 3 obs behind for each t. In turn, `minfore2` needs only 1 ahead, and `maxback2` only 2 behind. To give all metrics enough context at the extremes we pad **3 obs before** and **2 obs after** the focal year, but the narrower metrics will ignore some of the extreme padded obs. 

Suppose we index the raw probability time series within a year as p[1:T]. We concatenate the **3-previous** and **2-posterior** consecutive obs, getting the series c(p[-2:0], p[1:T], p[(T+1):(T+2)]). We then compute the aggregate metrics over the indices 1:T.

The asymmetric padding (3 left, 2 right) is required because `maxback3` at the first focal obs (t=1) looks back three steps — needing p[-2], p[-1], p[0] — while `minfore3` at the last focal obs (t=T) only looks forward two steps — needing p[T+1], p[T+2]. Symmetric padding of 2 on each side would leave `maxback3` under-supplied at t=1.

This means that when we compute `minfore2[T]`, the `T+2` obs is not used (only `T+1`). Similarly, to compute `maxback2[1]`, only two of the three padded prev obs are used (`p[-1]` and `p[0]`). This avoids the burn signal being repeated in consecutive years: the argmax search for any metric is always restricted to the focal indices 1:T; padded obs can only influence the background (`maxback`) context for the first or last focal obs, never become the detected event themselves.

This whole treatment is per-pixel, indexing only valid observations (passed quality filters from Landsat). Unfortunately, to pad previous- and next-year observations we cannot just take the nearest images from neighbouring years, because they may have missing data. We have to compute the burn probability time series for the M nearest months, create a per-pixel array of probability and take the **3 latest** and **2 earliest** obs, respectively.
M = 4 seems a good starting point.

**Previous-year images to use**: The burn probability model uses the previous-year land cover and previous-year mapbiomas mosaic bands as predictors. Strictly, the burn probability for padded observations from neighbouring years should use *their own* previous year. However, as only the 3 before and 2 after obs are padded, we consider more appropriate to use the focal-year's previous-year, because those padded obs will be probably better represented as if they were in the focal year. This is not so in the terrible cases of very low image density, but we cannot solve all. 

Example for target year 2010:
padd pre-year obs: latest 3 obs from september 2009 to december 2009 (included).
padd post-year obs: first 2 obs from jan 2011 to april 2011 (included).
(Beware: in GEE, the end date of filterDate() is exclusive, you have to advance 1 day to get it right).
All obs, even the padded ones, use the mapbiomas land cover and mosaic data from 2009 to compute burn probability.

## Implementation (done)

Implemented per `docs/03-plan.md`. Code lives in:

- `utils/functions.py` — the building blocks and the `bpts(year, tile_id, export=...)`
  driver: coefficient loading/parsing (`load_all_coefficients`), the GEE linear-predictor
  builders (`build_coeff_image`, `build_prev_scalar`, `build_cross_factor1_coef`,
  `compute_burn_prob_img`), the Landsat assembly (`mosaic_by_date`, `safe_to_array`), and the
  array metrics (`compute_bp_ts_metrics`). New constants in `utils/constants.py`
  (`MODELS_DIR`, `REGION_RASTER`, `CARTAS_FC`/`CARTAS_ID_PROPERTY`, `ARG_BUFFER_FC`,
  `BP_TS_METRICS_COL`, `PAD_*`, `PREV_SUFFIX_MAP`).
- `workflow/03-bp_ts_metrics.py` — thin CLI: `--year`/`--tile` (both optional; omit = all).
- `scripts/test-03-bp_ts.py` — interactive map + headless `validate()` (default 2015 / SK-19-Y-A).

**Prerequisite — not yet satisfied:** `C.REGION_RASTER`
(`…/ARG-Regiones-MapBiomas-buffer2km`) does not exist yet; export it first with
`scripts/export_region_raster.py`. (Validation used the older non-buffered
`…/ARG-Regiones-MapBiomas` as a stand-in.)

**Validation done** (band `region_id`, classes 1–5; tile grid property `grid_name`; 248 tiles
intersect the buffer): coefficient parsing exact (130 terms, 7 blocks); GEE burn probability
reproduces the hand-computed raw-scale logit to ~7e-9 (band alignment + raw products correct);
all 18 metric bands verified on a synthetic series; insufficient-padding pixels mask cleanly
(GEE short-circuits masked raster pixels — the col-0 pattern). Note: interactive
`getInfo`/`reduceRegion` on the full graph can hit the user memory limit; the batch
`Export.image.toAsset` tiles and is the intended run path.

> **Array gotchas (all fixed during impl — verified by exporting `bpts_2015_SK-19-Y-A`):**
> 1. `arraySort(keys)` requires `keys` to have the **same dimensionality** as the array, with
>    multiple elements only along the sort axis — pass the `[T,1]` delta column negated, **not**
>    an `arrayProject([0])`'d 1-D key.
> 2. An **empty `ee.Array` cannot stay 2-D** (slicing to zero rows collapses it to 1-D), which
>    breaks `arraySlice(1, …)`. `safe_to_array` therefore prepends a **fully-masked 2-band
>    sentinel** image instead of returning an empty stub, so `toArray()` is always statically 2-D.
> 3. `compute_burn_prob_img` must **carry `system:time_start`** onto its output, or the
>    `filterDate` split into prev/focal/next returns empty (symptom: `n = 0` everywhere).
> 4. Whole-series reducers over `focal_arr` aren't covered by the padded-array masks: the
>    inter-obs `diffs` array is **empty & unmasked at `n = 1` pixels**, so `updateMask(n.gte(2))`
>    before reducing (`timediff_*`) is required to avoid an out-of-bounds `arrayReduce`.
>
> General rule (from col-0): empty arrays only throw on **unmasked** pixels and on **constant**
> array images (eager eval); masked raster pixels short-circuit cleanly. So every
> `arrayReduce`/`arrayGet` site must reach either a non-empty array or a masked pixel.