# 03 — Where the per-tile compute goes, and what pruning bought

> **Extracted from** `collection-01/docs/03-bpts.md` §7 (the cost-lever bullets), §8, §8.1 and §9
> @ `76dca98` (2026-09-18) — those sections no longer exist under those names.
> Lab notebook — the record of building the step, not documentation of it.

The doc keeps only the outcomes: the array machinery is not the cost (so do not optimize it),
production deploys the P=50 model, and a complete year is ~55 GiB.

## 7. (the two cost bullets of "Open items / future changes")

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

### 8.1 Storage footprint (for planning the next collection)

Measured from `sizeBytes` on the exported assets (`ee.data.listAssets` over `BP_TS_METRICS_COL`),
averaged across the 9 fully-complete years (248/248 tiles: 2015–2021, 2024, 2025) as of 2026-07-03:

- **~54.7 GiB per complete year** (≈ 58.7 GB), for the 16-band `int` output at 30 m over the 248
  ARG *cartas*. Tight spread — every complete year is 51–57 GiB, so this is a reliable per-year
  figure.
- **Full 27-year run (1999–2025) ≈ 1.44 TiB** (27 × 54.7 GiB) once every year is complete.
  Incomplete years track in line (e.g. 2022 at 200/248 tiles = ~49.7 GiB).

Use these to size the next collection's asset quota up front. The figure scales with band count and
output dtype (§3.7), so a pruned/rescaled output would shift it proportionally.

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
