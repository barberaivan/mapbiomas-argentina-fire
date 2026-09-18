# 02 — Per-fire time-series diagnostic plots

One PNG per fire showing the fitted burn probability through time against the raw spectral
indices, used to spot fires whose pre-/post-fire date windows are mis-defined. It is the visual
counterpart to the `fit` gate of [`02-data_cleaning.md`](02-data_cleaning.md): the panels are how
you verify that a manual edit landed, and how you find the next fire that needs one.

## Inputs → Outputs

`class_NN_fit.rds` + the full training observations → **`ts_plot_cache.R` → `ts_plot_by_fire.R`**
→ one PNG per fire

| | What it is | Where |
|---|---|---|
| **in** | fitted models, one per `veg_fire` class | `models-store/class_NN_fit.rds` |
| **in** | training observations with the `fit` column | `data/training_observations_{region}_v{V}.csv` |
| **out** | prediction cache (rebuildable) | `models-store/ts_plot_cache_v1.rds` |
| **out** | one panel per fire | `models-store/prediction_plots/{region}/{region_fire_id}.png` |

## How it works

Each panel is 4 rows — NBR, NBR2, raw predicted burn probability, smoothed predicted burn
probability — with Burned points stacked above Unburned, one line per training point.
A fire's panel pools **every `veg_fire` class its points belong to**, because a point's class
depends on its previous-year land cover and one fire can therefore span classes.

The median marker is a solid burn-class–coloured point for dates whose observations were used in
fitting (`fit == TRUE`) and a **red asterisk** for held-out dates (`fit == FALSE`) — which is the
quick visual read of what the fit actually saw.

Script set, in `collection-01/scripts/`:

- `ts_predict_functions.R` — `design_raw()` / `predict_class()`: RAW-scale prediction from a
  `class_NN_fit.rds` without loading glmnet.
- `ts_plot_cache.R` — builds `models-store/ts_plot_cache_v1.rds`: predicts `p_pred` for every
  fitted class's full observation set, adds `burn_class` (point-level Burned/Unburned factor) and
  `p_pred_smooth` (n5 rolling median of `p_pred` per point, via `slider::slide_dbl`).
- `ts_plot_functions.R` — shared `plot_fire_panel()`.
- `ts_plot_by_fire.R` — the canonical and only driver.

## Run

```bash
Rscript collection-01/scripts/ts_plot_cache.R      # after any class_NN_fit.rds changes
Rscript collection-01/scripts/ts_plot_by_fire.R    # then refresh the PNGs
```

## Key decisions

- **Prediction is in-sample (`class_NN_fit.rds`), not out-of-fold.** The panels must cover every
  observation of every fire, including those the CV never held out, and the purpose is to inspect
  the date windows rather than to measure skill. The tradeoff is argued in
  [`../models/README.md`](../models/README.md) ("Predicting burn probability").
- **The aesthetic mirrors collection 0**, by explicit request: hex colours, thin-spaghetti plus
  bold-median-line geoms and a `theme_classic`-based theme follow the top two panels of
  `collection-00/data_viz_Lican/functions.R::plot_tempseg()`.

## Files

| File | Role |
|---|---|
| `scripts/ts_predict_functions.R` | RAW-scale prediction helpers |
| `scripts/ts_plot_cache.R` | builds the prediction cache |
| `scripts/ts_plot_functions.R` | `plot_fire_panel()` |
| `scripts/ts_plot_by_fire.R` | the driver — one PNG per fire |
| `models-store/prediction_plots/` | the output panels (gitignored) |

## Related

- [`02-model_fitting.md`](02-model_fitting.md) — the fit these panels visualise.
- [`02-data_cleaning.md`](02-data_cleaning.md) — the `fit` gate the red asterisks report on.
- `notebooks/model_fit_diagnostics.qmd` — the per-class diagnostics; the per-fire panels are
  deliberately **not** in it, they exist only as these standalone PNGs.
