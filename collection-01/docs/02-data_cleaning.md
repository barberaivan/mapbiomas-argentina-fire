# 02 — Observation cleaning (the `fit` gate)

A mandatory pass between the download of the training observations and the fit. It adds a
boolean **`fit`** column to each region CSV, marking which observations the model is allowed to
see; `workflow/02-model_fitting.R` refuses to run without it and fits only `fit == TRUE` rows.
It exists because the people who collected the fires make mistakes — a post-fire window set too
generously, a date that belongs to the next fire, an entire fire that should not be in the
training set — and those have to be trimmed before they teach the model something false.

It lives in `scripts/` rather than `workflow/` because it is local-CSV prep that exports no GEE
asset — the same tier as `download_observations.py`.

## Inputs → Outputs

`training_observations_{region}_v{V}.csv` + `data/data_cleaning.xlsx`
→ **`scripts/data_cleaning.R`** → the same CSVs, plus a `fit` column

| | What it is | Where |
|---|---|---|
| **in** | downloaded training observations, one CSV per region | `data/training_observations_{region}_v{V}.csv` |
| **in** | the per-fire manual edits, one sheet per region | `data/data_cleaning.xlsx` |
| **out** | the same CSVs with a boolean `fit` column added | in place |

Over the five regions the gate keeps **5,923,062 of the 6,177,098 downloaded observations** (95.9 %),
of which 541,789 (9.1 %) are labelled burned.

Re-running is **idempotent** — it recomputes only `fit`, and never touches the original columns.
Edit the `RULES` table and re-run to revise.

## How it works

Two passes, the second on top of the first.

1. **Base hard filter** (every fire, from the `training_fires` windows). Keeps only observations
   inside the valid window for the point's type:
   - burned points: pre-fire `pre_lwr → pre_upr` **or** post-fire `post_lwr → post_upr_long`;
   - unburned points: `pre_lwr → post_upr_long`;
   - `pre_lwr` fallback = `pre_upr` − 1 year (same month-day, matching the export);
     `post_upr_long` fallback = `post_upr_short`.

   Everything outside → `fit = FALSE`.

2. **Per-fire manual edits**, from the `RULES` table transcribed from `data/data_cleaning.xlsx`.
   Fires absent from the workbook get no extra handling.

### Ordering semantics of the manual edits (critical — easy to get wrong)

Count and range rules (`primeras/últimas N`, `a a b` = positions a–b, `desde la k`) operate on
**dates, not on per-point observation counts**. For each fire:

1. Take the fire's `burned == 1` observations, **pooled across all of its burned points** (key:
   `region_fire_id`) — *not* one point at a time.
2. Form the list of their **unique dates**, sorted ascending: `D = [d1, d2, d3, …]`.
3. The rule selects positions in `D` (`primeras 3` → `{d1,d2,d3}`; `quitar últimas 2` → drop
   `{d_{n−1}, d_n}`; `2 a 6` → `{d2..d6}`; `desde la 3ª` → `{d3..d_n}`).
4. A `burned == 1` observation keeps `fit = TRUE` **iff its date is in the selected set**.

Worked consequence: suppose a fire's first three post-fire dates are `d1, d2, d3`. A point with
no observation on `d2` (a cloud gap) but with observations on `d1` and `d3` keeps **2** rows
under "keep first 3" — because the ranking is over the fire's unique dates, not that point's own
count. Two points can therefore keep different numbers of observations from the same rule.

All rules act on `burned == 1` only, except `drop_fire` (the whole fire), `pre_trim_lt` (all
points — it trims the pre-fire side) and `drop_unburned_keep_first` (which also drops
unburned-point observations). Inferred-year date rules — a month and day with no year — resolve
the year inside the post-fire window `[post_lwr, post_upr_long]`.

### Fire-id ↔ workbook mapping

The workbook stores `fire_id` as a bare number (no zero-pad, no `fire_` prefix) or as `sdeN`.
`match_fire_id()` maps it to the real asset id by numeric value (`3` → `fire_03`) or exact suffix
(`sde1` → `fire_sde1`) — no zero-pad is assumed (see `fire_token` in `utils/constants.py`).

## Run

```bash
Rscript collection-01/scripts/data_cleaning.R [version]               # default version 1; all regions
CLEAN_REGIONS=CHACO Rscript collection-01/scripts/data_cleaning.R 1   # subset (debugging)
```

After re-cleaning, rebuild the diagnostic panels (`scripts/ts_plot_cache.R`, then
`scripts/ts_plot_by_fire.R`): they flag held-out (`fit == FALSE`) medians with a red asterisk,
which is how to verify the edits landed. See [`02-diagnostic_plots.md`](02-diagnostic_plots.md).

## Gotchas

- The rules are **date-ranked, not count-ranked**. Reading "keep first 3" as "keep 3 rows per
  point" is the single most common way to mis-transcribe a workbook row.
- The gate is mandatory: without a `fit` column the fit stops with
  `"The required dataset did not pass the cleaning step; …"`.
- A fire missing from the workbook is not an error — it simply gets the base filter only.

## Files

| File | Role |
|---|---|
| `scripts/data_cleaning.R` | the gate; holds the `RULES` table |
| `data/data_cleaning.xlsx` | the authored per-fire edits, one sheet per region |
| `workflow/02-model_fitting.R` | refuses to run without `fit` |

## Related

- [`01-training_data.md`](01-training_data.md) — where the windows the base filter uses come from.
- [`02-model_fitting.md`](02-model_fitting.md) — the fit this gate feeds.
- [`02-diagnostic_plots.md`](02-diagnostic_plots.md) — how to check an edit landed.
