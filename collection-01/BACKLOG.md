# Backlog — collection-01

Pending work items not yet scheduled. Add new items at the top of each section.

---

## Data preparation

This is probably for collection 2.

- [ ] Sample training points for the 3 missing fires in BA (check `training_locations_status.txt`). The fires are commented in the script that creates the training_fires asset. They must be included in that asset and then, points must be sampled.
- [ ] Add a column to the `toma_de_muestras` Drive table to flag whether the exported GEE asset exists and is validated. A lot of `training_locations` files were not exported, and doing that takes time.

---

## Burn probability model (obs)

- [ ] Refine models. In Collection 1 the set was hardly decreased so that glmnet converged, but maybe that was not so necessary; maybe we can prune highly correlated variables by veg_fire class, not globally. Anyway, keeping a smaller set is good for reducing the prediction compute.

---

## Diagnostics / notebooks

- [ ] **Per-fire NBR / NBR2 / burn-probability time-series plot (for Lican).** Add a per-fire
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

*Format: `- [ ]` open, `- [x]` done.*
