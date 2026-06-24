# 02 — Observation cleaning (the `fit` gate)

A mandatory step **between download (`scripts/download_observations.py`) and the fit
(`workflow/02-model_fitting.R`)**. It adds a boolean **`fit`** column to each
`data/training_observations_{region}_v{version}.csv`; `02-model_fitting.R` refuses to run
without it (`stop("The required dataset did not pass the cleaning step; …")`) and fits only
`fit == TRUE` rows. Implemented in `scripts/data_cleaning.R`; the per-fire edits are
transcribed from the `data/data_cleaning.xlsx` workbook (one sheet per region).

It lives in `scripts/` (not `workflow/`) because it is local-CSV prep that exports no GEE
asset — the same tier as `download_observations.py`.

## What it does

1. **Base hard filter** (every fire, from `training_fires` windows). Keeps only obs inside the
   valid window for the point's type:
   - burned points: pre-fire `pre_lwr→pre_upr` **or** post-fire `post_lwr→post_upr_long`;
   - unburned points: `pre_lwr→post_upr_long`.
   - `pre_lwr` fallback = `pre_upr` − 1 year (same month-day, matching the export);
     `post_upr_long` fallback = `post_upr_short`. Everything outside → `fit = FALSE`.
2. **Per-fire manual edits** (`RULES` table, transcribed from `data/data_cleaning.xlsx`),
   applied on top. Fires absent from the workbook get no extra handling.

## Ordering semantics (critical — easy to get wrong)

Count/range rules (`primeras/últimas N`, `a a b` = positions a–b, `desde la k`) operate on
**dates, not on per-point observation counts**. For each fire:

1. Take the fire's `burned == 1` observations, **pooled across all of its burned points**
   (key: `region_fire_id`) — *not* one point at a time.
2. Form the list of their **unique dates**, sorted ascending: `D = [d1, d2, d3, …]`.
3. The rule selects positions in `D` (e.g. `primeras 3` → `{d1,d2,d3}`; `quitar últimas 2` →
   drop `{d_{n-1}, d_n}`; `2 a 6` → `{d2..d6}`; `desde la 3ª` → `{d3..d_n}`).
4. A `burned == 1` observation keeps `fit = TRUE` **iff its date is in the selected set**.

Worked consequence: suppose a fire's first three post-fire dates are `d1,d2,d3`. A point that has
no observation on `d2` (cloud gap) but does on `d1` and `d3` keeps **2** rows under "keep first
3" — because the ranking is over the fire's unique dates, not that point's own count. Two points
can therefore keep different numbers of observations from the same rule.

All rules act on `burned == 1` only, except: `drop_fire` (whole fire), `pre_trim_lt` (all
points — trims the pre-fire side), and `drop_unburned_keep_first` (also drops unburned-point
obs). Inferred-year date rules (a month/day with no year) resolve the year inside the
post-fire window `[post_lwr, post_upr_long]`.

## Run

```bash
Rscript collection-01/scripts/data_cleaning.R [version]      # default version 1; all regions
CLEAN_REGIONS=CHACO Rscript collection-01/scripts/data_cleaning.R 1   # subset (debugging)
```

Re-running is **idempotent** — it only recomputes `fit`; original columns are untouched. Edit
`RULES` and re-run to revise. After re-cleaning, rebuild the diagnostic cache and plots
(`scripts/ts_plot_cache.R`, `scripts/ts_plot_by_fire.R`) — the per-fire panels flag held-out
(`fit == FALSE`) medians with a red asterisk, which is how to verify the edits landed.

## Fire-id ↔ workbook mapping

The workbook stores `fire_id` as a bare number (no zero-pad, no `fire_` prefix) or `sdeN`.
`match_fire_id()` maps it to the real asset id by numeric value (`3` → `fire_03`) or exact
suffix (`sde1` → `fire_sde1`) — no zero-pad is assumed (see `fire_token` in `utils/constants.py`).
