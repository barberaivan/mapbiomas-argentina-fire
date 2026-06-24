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

- `minfore3[t] = min(p[t], p[t+1], p[t+2])`   (K = 3)
- `minfore2[t] = min(p[t], p[t+1])`            (K = 2)

Pre-jump baseline (back), two estimators:

- `maxback2[t] = max(p[t-2], p[t-1])`          (conservative; = `diff(median5)` on monotone runs)
- `prev[t]     = p[t-1]`                        (most local; best under sparse sampling)

Time widths (record all — they inform gaps, persistence, and rate of change):

- `prevwidth[t]  = d[t-1] - d[t-2]`   (back-window span; relevant to `maxback2`)
- `jumpgap[t]    = d[t]   - d[t-1]`   (gap the jump is measured across)
- `postwidth3[t] = d[t+2] - d[t]`     (persistence span, K = 3)
- `postwidth2[t] = d[t+1] - d[t]`     (persistence span, K = 2)

jumpgap is particularly useful to detect slow or fast changes. It's stronger fire evidence when short. If long, may be a slow change (not fire) or fire under low image density.

Change variables (delta), computed from the previous metrics:

Three parameterizations, each a time series over `t`:

- `deltaA[t] = minfore3[t] - maxback2[t]`
- `deltaB[t] = minfore3[t] - prev[t]`
- `deltaC[t] = minfore2[t] - prev[t]`

### Collapsing the time series to single annual values (multiband image per year)

We must reduce each per-pixel series to scalars for the SNIC step: 

Treat each delta definition independently: find **its own** argmax `t*`
over the year, and extract **its own** relevant variables at that `t*`. So `deltaA`, `deltaB`, `deltaC` each yield a self-consistent bundle anchored at their own peak.

Rationale: the optimal transition obs differs by parameterization (K = 3 vs K = 2, `maxback2` vs `prev`); tying everything to one delta's peak would mis-anchor the others.

At each delta's `t*`, extract (its own): 
- the delta value (the max in the series), 
- the `minfore` (post level),
- the back value used (`maxback2` or `prev`), 
- `jumpgap` (always, no matter which delta)
- the corresponding `prevwidth`/`postwidth`, depending on the window used
- the focal date (`date_post = d[t]`). (date_post - jumpgap / 2 gives the middle date, a good burn candidate-date)

A few metrics to export for the whole series (not based on each delta):
- robust `pmax_f = max_t minfore`: the maximun of minfore_f across the whole series and the maximum raw probability: `pmax1`, `pmax2` and `pmax3`.
- n: the number of observations in the series (quality band)
- timediff_med: median(diff(date)), the median gap, transformed to days
- timediff_max: max(diff(date)), the maximum gap, transformed to days

All variables exported always; the decision on which to use depends on image density later.

### Building the raw burn probability time-series

Using variable-width windows to compute aggregates implies that a series looses a variable number of observations at the extremes: minfore_3 needs 2 extra obs ahead; maxback_2 needs 2 obs before for each t. In turn, minfore_2 needs only 1 ahead, and prev, only 1 before. To make the aggregate time-series have equal length no matter their requirements, we will pad 2 extra obs before and ahead to the year time-series, but the less-requiring metrics will ignore the extreme padded obs. 

Suppose we index the raw probability time series within a year as p[1:T]. We concatenate the 2-previous and 2-posterior consecutive obs, getting the series c(p[-1:0], p[1:T], p[(T+1):(T+2)]). We then compute the aggregate metrics over the indices 1:T. This means that when we compute minfore2[T], the T+2 obs will not be used (only the T+1). Similarly, to compute prev[1], the -1 obs is ignored too. This avoids the burn signal being repeated in consecutive years. 

This whole treatment is per-pixel, indexing only valid observations (passed quality filters from landsat). Unfortunately, to padd previous- and next-year observations we cannot just take the nearest 2 images from neighbouring years, because they may have missing data. We have to compute the burn probability time series for the M nearest months, create a per-pixel array of probability and take the 2 latest and 2 earliest obs, respectively. 
M = 4 seems a good starting point.

**Previous-year images to use**: The burn probability model uses the previous-year land cover and previous-year mapbiomas mosaic bands as predictors. Strictly, the burn probability for padded observations from neighbouring years should use *their own* previous year. However, as only the 2 before and after obs are padded, we consider more appropriate to use the focal-year's previous-year, because those padded obs will be probably better represented as if they were in the focal. This is not so in the terrible cases of very low image density, but we cannot solve all. 

Example for target year 2010:
padd pre-year obs: latest 2 obs from september 2009 to december 2009 (included).
padd post-year obs: first 2 obs from jan 2011 to april 2011 (included).
(Beware: in GEE, the end date of filterDate() is exclusive, you have to advance 1 day to get it right).
All obs, even the padded ones, use the mapbiomas land cover and mosaic data from 2009 to compute burn probability.

