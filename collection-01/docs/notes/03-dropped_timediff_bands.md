# 03 — The dropped `timediff_*` bands (18 → 16), and the empty-`diffs` crash

> **Extracted from** `collection-01/docs/03-bpts.md` §3.3, §3.7 and §5 gotcha 4
> @ `76dca98` (2026-09-18) — the output is 16 bands and those passages are gone.
> Lab notebook — the record of building the step, not documentation of it.

The doc keeps the outcome (16 bands, `n` is the only density channel) and one clause of the
trap, because it will reappear for any future whole-series reducer over a length-`n−1` array.

## 3.3 (the note under "Collapsing to annual scalars")

> The per-pixel inter-obs gap bands `timediff_med`/`timediff_max` were **dropped** (2026-06):
> largely redundant with `n` as a density signal, and removing them saves storage. The code no
> longer computes the `diffs` array — see §3.7.

## 3.7 (the note under the output-band table)

> **Dropped (2026-06):** `timediff_med` / `timediff_max` (median/max inter-obs gap, days). They
> were largely redundant with `n` as a density signal, so they were removed to save storage — the
> output went from 18 → **16 bands** and `compute_bp_ts_metrics` no longer builds the `diffs`
> array. The §5 gotcha #4 (the `n>=2` mask that guarded those reducers) is now moot.

## 5. gotcha 4

4. **Whole-series reducers over `focal_arr` aren't covered by the padded-array masks.** *(Now
   historical — the `timediff_*` bands this guarded were dropped, §3.7. Kept here because the
   same trap will reappear if any future whole-series reducer over a length-`n−1` array is
   added.)* A fittable pixel with exactly **1 focal obs** has a non-empty `focal_arr` (so it
   isn't masked) but an **empty `diffs` array** (length `n−1 = 0`); reducing it throws an
   out-of-bounds `arrayGet`. This is common (sparse Landsat) and crashed a 22-minute export. Fix
   that was used: `diffs.updateMask(n.gte(2))` before the reducers, so n<2 pixels short-circuit.
   (`pmax1` is safe: n=1 reduces fine, n=0 is already masked.)
