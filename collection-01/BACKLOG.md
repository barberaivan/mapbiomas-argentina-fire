# Backlog — collection-01

Pending work items not yet scheduled. Add new items at the top of each section.

---

## Data preparation

This is probably for collection 2.

- [ ] **Reconcile CHACO `id_local` gaps in the `areas_regiones` sheet vs the remap.** The remap's
  `local_class` "ID=NN" ids are missing from the sheet for some Chaco classes, so the long-run
  area crosswalk drops/undercounts them: **grassland_chaco (veg_fire 13)** ids 42/43 → 0 km²,
  **shrubland-open_chaco (veg_fire 23)** ids 44/45 → undercounted. This biases the area weights in
  `notebooks/lr_term_pruning.qmd` (worked around by imputing the **median** area to zero-area
  classes) and `land_cover_remap.qmd`'s `area_frac`. Fix the sheet ids (or the remap
  `local_class`), then drop the median workaround.
- [ ] Sample training points for the 3 missing fires in BA (check `training_locations_status.txt`). The fires are commented in the script that creates the training_fires asset. They must be included in that asset and then, points must be sampled.
- [ ] Add a column to the `toma_de_muestras` Drive table to flag whether the exported GEE asset exists and is validated. A lot of `training_locations` files were not exported, and doing that takes time.

---

## Burn probability model (obs)

- [ ] Refine models. In Collection 1 the set was hardly decreased so that glmnet converged, but maybe that was not so necessary; maybe we can prune highly correlated variables by veg_fire class, not globally. Anyway, keeping a smaller set is good for reducing the prediction compute.

---

## Diagnostics / notebooks

- [x] **Per-fire NBR / NBR2 / burn-probability time-series plot (for Lican).** Add a per-fire
  diagnostic to `notebooks/model_fit_diagnostics.qmd` (or a sibling) to spot fires whose
  pre-/post-fire date windows are mis-defined. A 3-facet "spaghetti" time series per fire —
  rows: **NBR**, **NBR2**, **OOF-predicted burn probability**; x-axis: observation date; one
  line per training point (`point_id`); colour by burned vs unburned. Reading: if burned
  points' predicted probability stays low across the post-fire window, the post-fire date was
  likely set too generously.
  - Use the **OOF** probability (`p_oof` from `models/class_NN_oof_predictions.csv`), not an
    in-sample refit.
  - Auto-flag fires: plot only those whose **median `p_oof` over burned obs** is below a
    threshold (notebook param, default 0.6); allow an optional manual `fire_id` override.
  - Data (both git-ignored — download separately): `data/training_observations_{region}_v1.csv`
    (`NBR`, `NBR2`, `date`, `point_id`, `fire_id`, `region`, `burned`) joined to
    `models/class_NN_oof_predictions.csv` on `(region, fire_id, point_id, date)`. Key fires
    region-uniquely (`region_fire_id = paste(region, fire_id)`).
  - Lican has reference code from collection-00 that produced this plot (not in this repo) — adapt it.

---

## Prediction pipeline (step 03 — bp-ts export)

- [ ] **Handle write-permission failures on the output collection.** Several users hit
  `Error: Insufficient permissions to create asset
  'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/WORKFLOW-EXPORTS/bp_ts_metrics/bpts_YYYY_<carta>'`
  (Error code 3). It's a **write-ACL** problem on the destination collection (separate from the
  Celda 2 compute project): the authenticated account lacks Writer on `.../bp_ts_metrics`, or they
  authenticated with an email not in the permissions table. Two things to build:
  - A **pre-flight check** in the notebook that, right after auth, verifies the account can write
    to the output collection and fails loudly with a clear message — instead of failing tile by tile.
  - An admin **batch-grant script/checklist**: give Writer on `.../WORKFLOW-EXPORTS/bp_ts_metrics`
    (or a parent folder) to every email in the permissions table.
- [ ] **Make the compute project selectable in the Colab export notebook
  (`scripts/colab_bpts_export.ipynb`).** Celda 2 now hardcodes `GEE_PROJECT = 'mapbiomas-argentina'`
  (switched from `mapbiomas-fire-485203`, which kept failing for several accounts). If the fire
  project gets fixed, let users choose between `mapbiomas-argentina` and `mapbiomas-fire` as the
  compute project (e.g. a variable at the top of Celda 2 with the alternative commented). Confirm
  which project each account can actually initialize/export with before making it the default.

---

## Object model (step 06)

- [x] **Grouped-vegetation variant of the object model** (2026-07-27). Five summed fractions
  (`frac_agri`, `frac_grass_inund`, `frac_pasture`, `frac_grass_temp`, `frac_woody`, derived from
  `config/veg_fire_remap.csv` by name) replace the 23 raw class fractions: 22 predictors instead of
  40. It wins on every grid-blocked metric (AUC 0.902 → 0.921, accuracy 0.786 → 0.812) with the gain
  concentrated in the weak 1–50 ha band (0.872 → 0.903), and is now the DEFAULT variant. See
  docs/06 "Predictor variant".
- [ ] **Pick the classification threshold on out-of-fold predictions**, not at 0.5. Under
  grid-blocked CV sensitivity at 0.5 is 0.73 overall and 0.61 in the 1–50 ha band, while specificity
  is 0.91 — the cut is in the wrong place for a burned-area product that would rather over- than
  under-detect. `data/objects-predictions/oof_grouped_grid_5.csv` has what is needed.
- [ ] **More labels in the 1–50 ha band**, which holds 61 % of all objects and is where the
  model is weakest (grid-blocked AUC 0.90 vs 0.95 for ≥300 ha). Aim round-2 collection with
  `p_width` from a `predict all` run.

---

*Format: `- [ ]` open, `- [x]` done.*
