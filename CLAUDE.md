# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Primary Focus

**Active development is almost always in `collection-01/`, running `.py` scripts from `collection-01/workflow/`.** 
Default to `collection-01/` context unless the user says otherwise.

## Next steps (work order, as of 2026-06-18 end-of-session)

### ▶▶ IMMEDIATE (2026-06-18): kill old grassland_pat, refit on the new design

The old `grassland_pat` fit (PID 49609, started 2026-06-17 08:17, OLD pre-checkpoint code,
full 642k obs, 5 alphas incl. ridge, 2 cores) was **KILLED on 2026-06-18** — it had run ~31h,
was still grinding a single alpha after ~18h, had **no checkpoints** (a power cut = total loss),
and we couldn't tell which alpha it was on. `02-model_fitting.R` was substantially upgraded this
session (see "New fitting design" below). **Action for next session (do this in a session with
remote control):**

```bash
# from repo root, venv not needed for R
FIT_CORES=4 Rscript collection-01/workflow/02-model_fitting.R 1 grassland_pat
```

This writes **`class_16_*` directly** (new remap code for grassland_pat) — so the old
"rename class_17→16" step is **obsolete** for grassland (no class_17 will be produced).
Expect ~357k obs (subsampled), 4 alphas, **per-alpha checkpoints** — if it dies, just re-run
the **same command** and it resumes from the last finished alpha. With the old fit killed,
~22 GB is free, so `FIT_CORES=4` is the pick at ~357k rows (~20 GB, 3 fold-waves for K=10;
5 is faster but tighter on RAM). Checkpoints make an OOM recoverable (resume), so 5 is also
safe to try and fall back from.

### New fitting design (`02-model_fitting.R`, rewritten 2026-06-18)

- **Alpha grid `{0.25, 0.5, 0.75, 1}`** — ridge (α=0) dropped: never best in CV across the
  fitted PAT classes (3–5.5% worse deviance) and the slowest to fit. (Diagnostics evidence:
  agriculture_pat→0.5, forest_pat→0.25, shrubland_pat→0.75; lasso also slightly worse than
  the interior, so keep the 0.5/0.75 middle.)
- **Negative subsampling for large classes** (`neg_subsample` rule in `SAMPLE_RULES`). Keep
  ALL positives; thin negatives to `NEG_RATIO` (=4) × positives via a per-(fire_uid,point_id)
  **spread-by-date cap** (`PER_POINT_CAP`, default 24; overridable per class via
  `per_point_cap=`) + a **season×fire ratio trim**, with **Horvitz–Thompson weights**
  (`w = 1/inclusion-prob`) passed to `cv.glmnet(weights=)`. The weighted fit is unbiased for
  the full-data fit (slopes AND intercept) → subsampled and fully-fit classes share one
  probability scale, **no manual intercept correction**. `subsample_negatives()` is verified
  on synthetic data; HT weights sum back to the full negative total.
  - Rationale on the intercept: the training design is choice-based (fires were sought, not
    random) so absolute prevalence is already fictional; the weights exist to keep classes on
    a common scale for any downstream global threshold, not to recover a "true" base rate.
  - The per-point cap is usually the **binding** knob below ~cap 24. Cap≥24 lets the 4:1 ratio
    bind; lower caps trim harder. Post-subsample sizes (capacity-checked 2026-06-18):
    | class | rule | obs | ratio |
    |---|---|--:|--:|
    | grassland_pampa | `neg_subsample, per_point_cap=16` | 491k | 3.2:1 |
    | grassland_pat | `ash_frac=0.10, neg_subsample, per_point_cap=16` | 357k | 2.9:1 |
    | forest-cerr_chaco | `neg_subsample` (cap 24) | 318k | 4:1 |
    | shrubland_cuyo-pampa | `neg_subsample` (cap 24) | 289k | 4:1 |
  - `ash_frac` (intentional ash downweighting) and `neg_subsample` **compose**: ash_frac runs
    first (unweighted, intentional bias), then neg_subsample thins the rest with HT weights.
- **Per-alpha checkpointing (power-cut resilience).** After each alpha a COMPACT checkpoint
  `.class_NN_ckpt_aJJ.rds` is written **atomically** (`.tmp`→rename) holding only the cvm
  path, the winning-λ sparse glmnet path, and the OOF column at the selected λ (NOT the
  multi-GB `fit.preval`). On (re)start, sub/x/foldid are rebuilt deterministically
  (`set.seed`) and finished alphas are skipped; checkpoints are deleted only after all final
  outputs are written; a stale checkpoint (n/K/alpha changed, e.g. cap/ratio edited) is
  ignored and refit. **Verified end-to-end:** resume reproduces byte-identical
  coefficients/OOF/metrics; prep re-run on resume is ~minutes (NOT hours).
- **Memory.** True R footprint measured at ~22 GB for the old 642k/2-core run (PSS; system
  RSS over-counts COW-shared worker pages by ~7–8 GB). Per CV worker ≈ 6.5 GB private.
  `rm(Xfull);gc()` after the design subset, `rm(dt);gc()` after assembling, and the alpha
  loop keeps only one fit in memory. **Core guidance:** heaviest class (`grassland_pampa`,
  ~491k) → `FIT_CORES=2` (3 risks OOM on 31 GB, and K=10 folds only gain ~1.25× from a 3rd
  core); smaller subsampled classes (~290–360k) → `FIT_CORES=3–4`.
- **Output additions:** `cv_metrics.csv` gains `n_eff` (= sum of weights); `oof_predictions.csv`
  gains a `weight` column. When rebuilding `cv_metrics_v1.csv` across old + new classes use
  `rbindlist(..., fill=TRUE)` (older PAT fits lack `n_eff`).
- **Progress watcher (optional):** `/tmp/grassland_alpha_watch.sh` logs each cv.glmnet worker
  generation change (= one alpha done) to `/tmp/grassland_alpha_watch.log` — passive `ps`-only,
  was watching the now-killed PID 49609.

**▶ Remap v2 RESOLVED (2026-06-17).** The Google Sheet was updated and
`config/veg_fire_remap.csv` regenerated. The two blocking problems are fixed:
`agriculture_cuyo` (was K=2, unfittable) is merged with `agriculture_pat` into a new
cross-region class **`agriculture_cuyo-pat`** (CUYO+PAT, K=10, 18 fires+), which also
absorbs the previously-unmapped CUYO class 19. `cv_feasibility_report.py` was re-run and
`land_cover_remap.qmd` re-rendered: 23 fittable classes, **0 unmapped observations**,
Table 2 matches `cv_feasibility_v1.csv` exactly. Low-K (<10 fires) classes are accepted
as fittable (no longer flagged).

**▶ Class numbering CHANGED with remap v2 — rename the existing model outputs (do NOT
refit).** Dropping `agriculture_cuyo` and adding the merged `agriculture_cuyo-pat` shifted
every veg_fire code at/above the change, so the `class_NN` files already on disk (fit under
the *old* numbering) are now mislabeled. The PAT classes' MB-class membership did **not**
change in remap v2 — only the integer code moved — so the existing fits are still valid.
**Decision: rename the files to the new codes; do not re-fit `forest_pat` or `grassland_pat`
(nor `shrubland_pat`).** Only `agriculture` actually changed.

| veg_fire_name | old code / file | new code / file | action |
|---|---|---|---|
| agriculture_pat | 4 — `class_04_*` | — (class dropped) | **delete `class_04_*`** |
| agriculture_cuyo-pat | (new) | 2 — `class_02_*` | **fit** (only new fit needed) |
| forest_pat | 9 — `class_09_*` | 8 — `class_08_*` | **rename** (do not refit) — `class_09` slot is now `forest-cerr_chaco` |
| grassland_pat | (old fit killed) | 16 — `class_16_*` | **REFIT on new design** (subsampled+checkpointed) — see "IMMEDIATE" above. Writes `class_16` directly. `class_17` slot is now `grassland-inund_chaco` |
| shrubland_pat | 22 — `class_22_*` | 21 — `class_21_*` | **rename** (do not refit) — `class_22` slot is now `shrubland-closed_chaco` |

Steps:
1. **Delete the dropped class**: `collection-01/models/class_04_*` (coefficients, cv_metrics,
   fit.rds, oof_predictions, tuning).
2. **Fit the merged class** (the only refit):
   `Rscript collection-01/workflow/02-model_fitting.R 1 agriculture_cuyo-pat` → `class_02_*`.
3. **Rename the PAT model files** to the new codes (forest_pat 9→8, grassland_pat 17→16
   *(after the running fit finishes)*, shrubland_pat 22→21). For each class, rename all five
   sidecars — `class_NN_{coefficients,cv_metrics,tuning,oof_predictions}.csv` and
   `class_NN_fit.rds` — **and** fix the stale `veg_fire` integer column *inside*
   `cv_metrics.csv` and `oof_predictions.csv` (a bare file rename leaves the old code in the
   data). Everything else (coefficients, tuning, fit.rds) is code-agnostic. Do the renames
   in descending order (22→21, 17→16, 9→8) so a new name never overwrites a not-yet-renamed
   file.
4. Rebuild `models/cv_metrics_v1.csv` (see "Fit the remaining classes" below). Then confirm
   the `class_NN` ↔ veg_fire_name mapping against `config/veg_fire_remap.csv`.

**⏳ NOTHING RUNNING (as of 2026-06-18):** the old `grassland_pat` fit was killed (see
"IMMEDIATE" above). Next session, launch the new-design grassland_pat refit (writes
`class_16`), then the other subsampled big classes.

**▶ Models on disk are under the OLD (pre-remap-v2) numbering, except grassland_pat (refit).**
`class_04` (agriculture_pat), `class_09` (forest_pat), `class_22` (shrubland_pat) were fit
before the code shift; their *content* is still valid (MB-class membership unchanged in remap
v2 — only the integer code moved), so they are **renamed**, not re-fit (rename the files + fix
the `veg_fire` code column inside `cv_metrics`/`oof_predictions`): forest_pat 9→8,
shrubland_pat 22→21; agriculture_pat 4 is dropped. **grassland_pat is the exception** — its
old fit was killed and it is **refit** on the new design (writes `class_16` directly, so no
rename for it).

**▶ Fit the remaining classes** (remap v2 validated; all 5 regions downloaded — BA includes
fire_09 v2). **23 fittable classes**, all with usable K (`models/cv_feasibility_v1.csv`);
low-K (<10 fires) classes are accepted. So far only the 4 PAT classes are fitted (under old
codes). Still to fit — every non-PAT class plus the merged `agriculture_cuyo-pat`:
- `agriculture_cuyo-pat` (2), `agriculture_chaco` (1), `agriculture_pampa` (3),
  `agriculture-per_chaco-ba` (4); `forest_ba` (5), `forest_cuyo` (6), `forest_pampa` (7),
  `forest-cerr_chaco` (9), `forest-inund-chaco` (10), `forest-open_chaco` (11);
  `grassland_ba` (12), `grassland_chaco` (13), `grassland_cuyo` (14), `grassland_pampa` (15),
  `grassland-inund_chaco` (17); `pasture_ba` (18), `pasture_chaco` (19);
  `shrubland_cuyo-pampa` (20), `shrubland-closed_chaco` (22), `shrubland-open_chaco` (23).
- Run one class at a time. Subsampled big classes (see "New fitting design"):
  `grassland_pampa` → `FIT_CORES=2`; `forest-cerr_chaco`, `shrubland_cuyo-pampa`,
  `grassland_pat` → `FIT_CORES=4`. All are checkpointed — re-run the same command to resume.
  Example: `FIT_CORES=2 Rscript collection-01/workflow/02-model_fitting.R 1 grassland_pampa`.
  `02-model_fitting.R` filters each class and `rm()`s the full region table before fitting.
- Review each in `notebooks/model_fit_diagnostics.qmd` (it auto-discovers every fitted
  `class_*` and renders one section per class).
- Once all `class_*_cv_metrics.csv` exist, rebuild the summary:
  `Rscript -e "library(data.table); fwrite(rbindlist(lapply(Sys.glob('collection-01/models/class_*_cv_metrics.csv'), fread)), 'collection-01/models/cv_metrics_v1.csv')"`

**▶ TASK FOR LICAN — per-fire NBR / NBR2 / burn-probability time-series plot — RESOLVED,
final design (historical reference, 2026-06-22).** The first implementation (a standalone
`notebooks/ts_diagnostics.qmd` aggregating 4 driver scripts — by_fire/flagged/by_class/
by_region — into `models/figures/`) was replaced same-day by a simpler design: the per-fire
panels now live **inside the existing** `notebooks/model_fit_diagnostics.qmd`, appended at
the end of each class's "By fire" section, instead of a separate notebook. Final script set
in `collection-01/scripts/`: `ts_predict_functions.R` (unchanged — `design_raw()` /
`predict_class()`); `ts_plot_cache.R` (builds `models/ts_plot_cache_v1.rds`; adds
`burn_class`, a Burned-first factor, and `p_pred_smooth`, an n5 rolling-median of `p_pred`
per point via `slider::slide_dbl`, mirroring collection-00's `p_med5`); `ts_plot_functions.R`
+ `ts_plot_by_fire.R` (one `plot_fire_panel()` per class×fire: 3 `patchwork`-stacked rows —
NBR / NBR2 / smoothed probability — each `facet_grid`-ed Burned-over-Unburned). Aesthetic
(hex colors, thin-spaghetti + bold-median-line geoms, `theme_classic`-based theme) mirrors
the top two panels of `collection-00/data_viz_Lican/functions.R::plot_tempseg()` by explicit
request, replacing the first implementation's ad-hoc styling. The 4 old drivers
(`ts_plot_flagged_fires.R`, `ts_plot_by_class.R`, `ts_plot_by_region.R`) and the standalone
`ts_diagnostics.qmd`/`.html` were deleted — the auto-flagging concept was dropped, since
every fire's panel is now visible in the notebook in order. `ts_plot_by_fire.R` still saves
one PNG per fire standalone, now under
`models/prediction_plots/{region}/{region_fire_id}.png` — pooled across every veg_fire class
a fire's points belong to (one fire, one PNG; not one PNG per class×fire). Inside
`_model_fit_diagnostics_child.qmd`, these same per-fire panels are rebuilt in-memory (not
re-read from disk) and combined with `patchwork::wrap_plots(ncol = 3)` — never a shared
ggplot facet across fires — so each fire keeps its own date range no matter how many fires
share a page; classes spanning more than one region (e.g. `agriculture_cuyo-pat`) get one
combined grid per region instead of one mixed grid. See `collection-01/README.md` for run
commands.

**▶ `prediction_plots/class_NN_*/` folders deleted (2026-06-23), regenerate on next render.**
These hold `_combined.png` / `_combined_{region}.png` — a per-class multi-fire grid embedded
into the rendered `model_fit_diagnostics.html`, written by the chunk in
`_model_fit_diagnostics_child.qmd` (not by `ts_plot_by_fire.R`, and not a stale leftover —
this is a second, currently-active artifact alongside the by-region/by-fire PNGs from
`ts_plot_by_fire.R`). They were deleted as stale-on-disk scratch (regenerable, gitignored);
re-rendering `model_fit_diagnostics.qmd` recreates them.


## Remap v2 — RESOLVED 2026-06-17 (historical reference)

> **Resolved.** The problems below were fixed by merging `agriculture_cuyo` into
> `agriculture_cuyo-pat` (CUYO+PAT) and mapping CUYO class 19. The table is kept for
> reference; `cv_feasibility_v1.csv` and `land_cover_remap.qmd` were regenerated and
> now show 23 fittable classes, K≥10 for `agriculture_cuyo-pat`, and 0 unmapped obs. See
> the resolution notes in "Next steps" above.

**CV feasibility report** (the *pre-fix* run) found:

| class | regions | obs | pos | fires+ | K | pos/fold | note |
|---|---|---|---|---|---|---|---|
| grassland_pampa | PAMPA | 1,177,881 | 117,325 | 33 | 10 | 11,732 | ok |
| grassland_pat | PAT | 819,566 | 92,651 | 45 | 10 | 9,265 | 31.9% ash neg |
| forest-cerr_chaco | CHACO | 700,799 | 63,692 | 56 | 10 | 6,369 | ok |
| shrubland_cuyo-pampa | CUYO+PAMPA | 554,106 | 57,731 | 29 | 10 | 5,773 | ok |
| forest_ba | BA | 331,610 | 60,237 | 11 | 10 | 6,024 | ok |
| grassland_chaco | CHACO | 271,665 | 46,409 | 35 | 10 | 4,641 | ok |
| forest_pat | PAT | 229,233 | 42,824 | 19 | 10 | 4,282 | ok |
| shrubland_pat | PAT | 189,039 | 42,320 | 40 | 10 | 4,232 | ok |
| agriculture_pampa | PAMPA | 182,001 | 6,632 | 7 | **7** | 947 | low K |
| forest_pampa | PAMPA | 166,727 | 10,987 | 19 | 10 | 1,099 | ok |
| grassland_ba | BA | 163,945 | 12,518 | 6 | **6** | 2,086 | low K |
| forest-open_chaco | CHACO | 149,057 | 14,892 | 34 | 10 | 1,489 | ok |
| grassland_cuyo | CUYO | 145,918 | 13,032 | 24 | 10 | 1,303 | ok |
| forest-inund-chaco | CHACO | 121,421 | 12,570 | 9 | **9** | 1,397 | ok |
| shrubland-open_chaco | CHACO | 120,175 | 8,643 | 27 | 10 | 864 | ok |
| agriculture_chaco | CHACO | 65,620 | 8,517 | 26 | 10 | 852 | ok |
| shrubland-closed_chaco | CHACO | 64,429 | 8,443 | 24 | 10 | 844 | ok |
| grassland-inund_chaco | CHACO | 64,246 | 6,228 | 20 | 10 | 623 | ok |
| forest_cuyo | CUYO | 61,799 | 7,977 | 20 | 10 | 798 | ok |
| pasture_chaco | CHACO | 51,587 | 7,507 | 16 | 10 | 751 | ok |
| pasture_ba | BA | 28,555 | 2,057 | 11 | 10 | 206 | ok |
| agriculture-per_chaco-ba | BA+CHACO | 22,822 | 3,952 | 15 | 10 | 395 | ok |
| agriculture_pat | PAT | 20,069 | 2,506 | 16 | 10 | 251 | ok |
| **agriculture_cuyo** | CUYO | 1,096 | 118 | 2 | **2** | 59 | **PROBLEM** |

Pure-negative fires (ash/drought, point-distributed across folds): PAT_fire_46,
PAT_fire_47, PAMPA_fire_43/44/45/51.
Also: 183 CUYO obs with `mb_class_raw=19` (Cultivos temporarios) not in CUYO remap.

> **Note (region-key fix, 2026-06-17 PM):** fire ids are now keyed region-uniquely
> (`region_fireid`) everywhere — `cv_feasibility_report.py`, `02-model_fitting.R`, and
> `land_cover_remap.qmd`. Bare `fire_id`s repeat across regions; the old keying
> conflated them. `cv_feasibility_v1.csv` was regenerated. The table above is from the
> *pre-fix* run; the cells that changed are `shrubland_cuyo-pampa` fires+ (29→38) and the
> Pampa/non-burnable `ash%neg` (the four PAMPA pure-neg fires now count: `agriculture_pampa`
> 0→18.1%, `grassland_pampa` 0→0.6%, `non-burnable` 33.4→34.0%). K and the
> `agriculture_cuyo` / mb=19 conclusions are unchanged.

**`agriculture_cuyo` (K=2) was the main concern** — only 2 fires with positives made
CV meaningless. ✅ Resolved: merged with `agriculture_pat` into `agriculture_cuyo-pat`
(K=10), which also absorbs the 183 CUYO `mb_class=19` obs that were unmapped.

**`land_cover_remap.qmd`** (re-rendered 2026-06-17 against the resolved remap; this is the
v2 notebook, which replaced and now carries the name of the original — deleted — remap
notebook) with two tables:

**Table 1 — raw class × region** (one row per mb_class_raw + region combination):
- Same columns as the existing remap notebook: area by land cover class, N obs,
  N fires with positives, burned/unburned counts, per-fire robustness stats.
- Add columns: proposed `veg_fire` name and numeric code.
- Source: `training_observations_*_v1.csv` + `config/veg_fire_remap.csv`.

**Table 2 — proposed remap summary** (one row per veg_fire class, aggregated):
- Same columns as `models/cv_feasibility_v1.csv`: obs, pos, %pos, fires+, K, pos/fold,
  ash%neg, regions.
- Basis for deciding whether to merge, split, or drop classes (especially
  `agriculture_cuyo`).

## Project Overview

MapBiomas Argentina Fire is a geospatial pipeline for detecting and mapping burned areas in Argentina using Landsat satellite imagery. The algorithm produces annual burned area products across two collections:

- **Collection 0** (`collection-00/`): Pilot — complete and operational. Covers Patagonia only.
- **Collection 1** (`collection-01/`): In development. Covers all five regions (BA, CHACO, PAMPA, CUYO, PAT).

## Technology Stack

| Component | Collection 0 | Collection 1 |
|-----------|-------------|-------------|
| GEE processing | JavaScript API | Python API (`earthengine-api`) |
| Model fitting | R (logistic regression -LR-) | same |
| Source imagery | Landsat C2 SR — L5, L7, L8, L9 | same |
| Land cover reference | MapBiomas Argentina LULC | same + MapBiomas annual mosaic |
| Spatial segmentation | SNIC (GEE native) | same (steps 04+) |

## Development Environment

- **Python venv**: `/home/ivan/.venvs/gee` — always use `/home/ivan/.venvs/gee/bin/python` to run collection-01 workflow scripts. Never create a new venv for this repo.
- **GEE project**: `mapbiomas-fire-485203` (hardcoded in `collection-01/utils/constants.py`).
- **Run scripts from the repo root**, not from inside `collection-01/`. The scripts add `collection-01/` to `sys.path` at startup.

## Collection 0 — Architecture

1. **Training data** (`samples/`): GEE JS scripts extract Landsat time-series for 30 labeled fires (PAT only), export to Google Drive as CSVs.
2. **Model fitting** (`models_fit/`, R): Two-level logistic regression. Coefficients exported as JS constants into `utils/constants.js`.
3. **GEE workflow** (`workflow/`, 8 steps): burn index summaries → obs-level probability → annual probability → SNIC → manual masking → vectorization → polygon metrics → object filtering.

Key files:
- `collection-00/utils/constants.js` — model coefficients (63 obs-level + 47 annual-level), paths, ROI geometry
- `collection-00/utils/functions.js` — Landsat preprocessing, index computation, summary statistics
- `collection-00/README_00.md` — full reproduction instructions and GCS asset paths

## Collection 1 — Architecture

1. **Training data export** (`workflow/01-training_data_export.py`): samples Landsat + MapBiomas mosaic at training points, exports one GEE asset per fire.
2. **LR model fitting** (locally in R, `glmnet`): fit one regularized logistic regression per region × fire-class, using the canonical-team predictor set. Coefficients exported back for the GEE prediction pipeline.
3. **Prediction pipeline** (`workflow/03–08`, stubs): same burn-probability → SNIC → masking → filtering structure as collection 0.

Key files:
- `collection-01/utils/constants.py` — single source of truth: paths, year range, spectral features, MB reclass table, LR terms, MB mosaic band list
- `collection-01/utils/functions.py` — Landsat preprocessing, index computation, MB class and mosaic helpers
- `collection-01/workflow/00-status.py` — check training_observations export status across all regions
- `collection-01/workflow/01-training_data_export.py` — export training data (one GEE task per fire)
- `collection-01/BACKLOG.md` — pending work items

## Collection 1 — Design Decisions

**Training data export**
- One GEE task per fire. Output asset: `training_observations-fire_NN_v{version}` under `COLLECTION-1/TRAINING-DATA/{region}/`.
- Task description format: `training_obs_{region}_fire_{NN}_v{version}` — region included because fire_ids repeat across regions.
- PAT fires 01–30 fall back to `COLLECTION-0/TRAINING-DATA/` for training_locations. Fires without locations are skipped with a warning.
- Fires with no burned points (fire_46, fire_47 — drought/ash negatives) export unburned-only without being skipped.
- `fire_id` is stored as a string `"fire_NN"` in GEE assets. Use `str(fire_id).removeprefix("fire_").zfill(2)` to get the zero-padded numeric part.

**Spectral features (21 focal-date — `ALL_FOCAL_FEATURES` in `constants.py`)**
- Optical: BLUE, GREEN, RED, NIR, SWIR1, SWIR2
- Fire indices: NBR, NBR2, MIRBI (raw — not sign-flipped as in col0), NDVI
- Tasseled-cap (Baig 2014 OLI coefficients): TCB, TCG, TCW
- Auxiliary: NDMI (vegetation moisture = NIR−SWIR1/NIR+SWIR1, same formula as col0's `ndwi_gao`), NDSI (snow), SAVI (sparse veg), NDWI (open water, McFeeters 1996 — new in col1)
- Canonical-team additions: AFRI, kNDVI, EVI2, NIRv

**MapBiomas mosaic**
- 40 bands selected from 111: optical (6) + NDVI + NDWI + NPV + NDFI, each with median/dry/wet/stdDev aggregates.
- Selection (`.select()`) happens before `.mosaic()` so only the 40 bands are processed.
- Previous-year mosaic: for observations in year Y, the mosaic for year Y−1 is attached.
- The loop variable is `mb_year` (the actual MB data year). `obs_year = mb_year + 1`. Range: `mb_start_year = obs_start_year − 1` to `mb_end_year = obs_end_year − 1`.

**MapBiomas land cover remap**
- The previous-year land cover is used to fit separate models, but with a remap of the argentina-level legend to have only a few classes by region (fire-class).
- Fire-class remap info is in the following [Google Sheets table](https://docs.google.com/spreadsheets/d/17ZShb8D0JaJw4nLvBDzt19xF6Fdg8lGHYs4Jogh0X1A/edit?gid=1376068841#gid=1376068841).
- `remap_by_region` sheet has `id` as argentina-wide classes, with `veg_fire_name_1` and `veg_fire_name_2` being to remap proposals. 
- Area analysis for the remaps are in `collection-01/notebooks/land_cover_remap.qmd`.
- The remap is still being decided, so there are no reliable constants, but the most updated source is the Google Sheets.

**Burned label at observation level**
- `burned=0`: all observations from unburned points, and observations from burned points in the pre-fire window.
- `burned=1`: observations from burned points in the post-fire window (post_lwr → post_upr_long).
- `post_upr_short` is preserved in `training_fires` for filtering at training time but not used to assign labels.
- `pre_lwr` is often null in assets → computed as `pre_upr` minus one year.

**Prediction tiling (GEE)**
- All image-based predictions in GEE are run over the MapBiomas *cartas* grid, not Landsat tiles (WRS-2 path/row).
- Carta asset: `projects/mapbiomas-chaco/BASE/cartas-argentina`.

**LR fitting (steps 02+)**
- Fitted locally in R using `glmnet` for regularization (not Random Forest, not in GEE).
- Predictor set: the **canonical-team set** (the agreed-upon term structure), described in `collection-01/notebooks/logistic_regression_terms.qmd`.
- Fire-veg classes (the land-cover remap that defines the per-region fire-classes) are defined in the [Google Sheets table](https://docs.google.com/spreadsheets/d/17ZShb8D0JaJw4nLvBDzt19xF6Fdg8lGHYs4Jogh0X1A/edit?gid=1376068841#gid=1376068841) — see the **MapBiomas land cover remap** decision above.
- One LR per region × fire-class.
- The exported training asset is the canonical training set; a large CSV download (all fires together) is used to fit locally.

## Collection 1 — Notebooks

All notebooks are Quarto-R (`.qmd`) in `collection-01/notebooks/`. Render with `quarto render` or run chunks interactively in RStudio.

| Notebook | What's in it |
|----------|-------------|
| `algo-fuego.qmd` | Flowchart of the full fire-mapping algorithm (Mermaid/DOT). No analysis code. |
| `land_cover_remap.qmd` | Evaluates the **current canonical remap** (`config/veg_fire_remap.csv`) against the full v1 observations. (Supersedes the original proposal-1-vs-2 remap notebook, now deleted.) Two tables: (1) mb_class_raw × region with area, obs, burned/unburned, fires+, per-fire robustness, and proposed veg_fire name/code; (2) proposed remap summary (one row per veg_fire class) matching `cv_feasibility_v1.csv` columns (cross-checked against it — exact match). Plus an unmapped-classes table and a discussion section. As of the remap v2 resolution (2026-06-17): 23 fittable classes, 0 unmapped obs, and the former `agriculture_cuyo`/CUYO-mb19 gaps closed via `agriculture_cuyo-pat`. Low-K (<10 fires) classes are accepted (not flagged). |
| `data_collection_stats.qmd` | Stats on the field data collection effort: time, authors, points and observations per fire. Requires `fires_table_stats.csv` — if obs CSVs changed, run `scripts/make_fires_table_stats.R` first. |
| `logistic_regression_terms.qmd` | Design of the LR term structure for the obs-level burn-probability model. Covers which features and interactions to include. |
| `logistic_regression_feature_engineering_ideas.qmd` | Exploratory ideas for feature engineering (non-linearities, interactions) for the LR model. Conceptual, not production code. |
| `burn_prob_ts_metrics.qmd` | Explores summary metrics derived from the intra-annual burn-probability time series. Compares rolling means, forward differences, and other statistics on synthetic signals. |

## GEE Code Editor Scripts

GEE JavaScript scripts live in a separate git repo cloned from Google's hosting:

- **Local path**: `/home/ivan/Insync/MapBiomas/mapbiomas-argentina-fire-gee/`
- **Remote**: `https://earthengine.googlesource.com/users/mapbiomas-arg/fuego` (repo name: `mapbiomas-arg/fuego`)
- **Credentials**: set up in `~/.gitcookies` (Google-issued token)

The user does **not** regularly pull this repo, so it may be behind. **Always `git pull` before editing any file in it**, then edit, then `git push`. The Code Editor reflects the push immediately on next refresh.

```bash
cd /home/ivan/Insync/MapBiomas/mapbiomas-argentina-fire-gee && git pull
# … edit files …
git add <file> && git commit -m "message" && git push
```

The `fuego` repo is the sole source of truth for all GEE JS code — do not keep `.js` copies in this repo.

## Running Long Scripts

For local processing estimated to take more than ~15 minutes, use `tmux` so the run survives session closure. GEE task-submission scripts are short enough to run normally.

```bash
tmux new-session -d -s <name> \
  '/home/ivan/.venvs/gee/bin/python -u <script> [args] 2>&1 | tee <logfile>'
```

Reattach with `tmux attach -t <name>`; detach without killing with `Ctrl+B D`. If unsure whether a run is heavy enough, ask the user before launching.

## General Design Decisions

- **Asset-based processing**: each workflow step exports intermediate GEE assets, avoiding memory/computation limits and allowing inspection at each stage.
- **Manual masking step** (step 05): removes false positives from ash/drought; requires domain expert review before vectorization.
- **Run logs**: each `01-training_data_export.py` run writes a JSON sidecar with input paths, task IDs, versions, and parameters for reproducibility.
