# 03 — Burn-probability time-series metrics

> **Work in progress — stub.** To be written when the obs-level burn-probability
> time-series and its annual summary metrics are built into the prediction pipeline
> (workflow steps 03–04).

Planned content: how the per-pixel intra-annual burn-probability series is summarized into
annual metrics that will be used to define seeds and candidates for region-growing algorithm (snic).

## Related notebook

- `notebooks/burn_prob_ts_metrics.qmd` — exploration of candidate summary metrics (rolling
  means, forward differences, etc.) on synthetic signals.

## Main ideas

- bp (burn probability) must be smoothed before we detect something. In Col 0 we used the median of K = 5 obs. Now we have veg types that recover rapidly, so we should also use a smaller window. Not mean, just median, as it keeps the values in the original scale.

- Metrics are based mostly on (smoothed) probability magnitude (high prob), persistence, and change. Persistence and smoothing are based on number of consecutive obs, not time span, because the landsat series is very irregular. Smoothing should be softer (smaller K) in regions of rapid recovery and in moments of low image density, which can be computed pixel-wise, by year.

- In Col 0 we used median5 centred at the middle obs, because when a fire burned in the middle obs (just before observation), it showed the min prob of the 3 first burned obs. Then, computing the diff(median5), would show a large increase there. It can be softened to K = 3. 

- In Col 1 Claude proposed to use a delta (no smoothing) * min3: focal obs - min(3 following obs) (or reversed). That does not smooth the pre-jump period, which can be unnecessary, but I'd like to keep it. So we could compute for every t:
    - maxback = max((t-2):(t-1))
    - minfore = min(t:[t+2])
    - delta = minfore - maxback
    - forewidth = (t+2) - t # persistence magnitude, higher is better
    - deltat = t - (t-1) # speed of change, lower is better (not slow disturb)

Notation here is vague. The t is an index, so the time differences are date[t] really (example).
Time is stored as an image-based band, usually using fractional year.

Products like delta * minfore are not needed: it's more flexible to have the raw variables so we can create any rectangular space for seeds and candidates.

We won't use cumulative probability here, so the prob can simple be in probability scale (not linear predictor). There won't be an annual burn prob model; these metrics will feed the snic directly. 

## Annual metric extraction strategy

> **Draft — to revise (recorded 2026-06-22).** Captures the current preference; the
> single-value extraction rule below is the open design point and should be revisited.

No median smoothing. `minfore` (the forward consecutive min) is itself the spike-robust,
persistence-gated "high level", so it replaces the Col-0 median-5 pass. All quantities below
are **per-pixel time series over valid observations only** (clouds dropped, so "consecutive"
means consecutive *valid* obs; a gap just means more elapsed days to collect the window).
Everything is on the **probability scale**.

### Per-observation quantities (still a time series at this stage)

Let `p[t]` be the obs-level burn probability at valid obs `t`, dated `d[t]` (fractional year).

Forward persistence (post-jump level), both window sizes:

- `minfore3[t] = min(p[t], p[t+1], p[t+2])`   (K = 3)
- `minfore2[t] = min(p[t], p[t+1])`            (K = 2)

Pre-jump baseline (back), two estimators:

- `maxback2[t] = max(p[t-2], p[t-1])`          (conservative; = `diff(median5)` on monotone runs)
- `prev[t]     = p[t-1]`                        (most local; best under sparse sampling)

Time widths (record all — they feed gap/persistence weighting and the SNIC gates):

- `prevwidth[t]  = d[t-1] - d[t-2]`   (back-window span; relevant to `maxback2`)
- `jumpgap[t]    = d[t]   - d[t-1]`   (gap the jump is measured across; the τ_pre "diff certainty")
- `postwidth3[t] = d[t+2] - d[t]`     (persistence span, K = 3)
- `postwidth2[t] = d[t+1] - d[t]`     (persistence span, K = 2)

### Candidate jump (delta) definitions

Three parameterizations, each a time series over `t`:

- `deltaA[t] = minfore3[t] - maxback2[t]`
- `deltaB[t] = minfore3[t] - prev[t]`
- `deltaC[t] = minfore2[t] - prev[t]`

### Collapsing the time series to single annual values — **preferred rule**

We must reduce each per-pixel series to scalars for the SNIC step. Two options were weighed:

1. *(rejected)* Compute one delta (e.g. `minfore3 - maxback2`), take its argmax `t*`, and read
   **all** other variables at that single `t*`.
2. **(preferred)** Treat each delta definition independently: find **its own** argmax `t*`
   over the year, and extract **its own** relevant variables at that `t*`. So `deltaA`,
   `deltaB`, `deltaC` each yield a self-consistent bundle anchored at their own peak.

Rationale: the optimal transition obs differs by parameterization (K = 3 vs K = 2, `maxback2`
vs `prev`); tying everything to one delta's peak would mis-anchor the others.

At each delta's `t*`, extract (its own): the delta max value, the `minfore` (post level) and
the back value (`maxback2` or `prev`) used, the relevant `prevwidth`/`jumpgap`/`postwidth`, and
the dates (`date_pre = d[t-1]`, `date_post = d[t]`). A robust `pmax = max_t minfore` is a cheap
by-product worth keeping.

All variables exported always; the decision on which to use depends on image density later.

Smoothing with different K (for back and fore), should always be centred the same way. K=3 (fore) and K=2 (back) require the longest series: padding 2 extra obs before and after each focal obs. The initial series es computed that way. If lower K allows to exploit more aggregated data on this series, it is not used: if computing minfore2 - prev_t, we simply discard the first obs of the series that was padded only to compute maxback2. In this way, all the deltas have the same length. In addition, that avoids redundancy.

### To revise later

- Exact list of variables to extract per delta, and which are redundant once SNIC gates are set.
- How many obs to padd from neighbouring years? 2 before needed, but how many after? In Col0 we used a redundant approach; now I prefer not to be redundant, avoid repeating the same delta appearing in 2 years.
- Reduce compute to get the padded obs before (and after?): In Col0 we computed a full year to pad the latest obs; now we will compute only M months, and ideally, only from prev year, not both. But think this deeper.