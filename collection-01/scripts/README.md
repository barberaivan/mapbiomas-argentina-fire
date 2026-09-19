# `scripts/` — what is in here

Everything that is **not** a numbered pipeline step. The steps themselves are in
[`../workflow/`](../workflow/); each one is documented in [`../docs/`](../docs/), and the design
lives there, not here. This file is a **signpost**: it says which group a file belongs to and which
doc explains that group. How to invoke any single script is its own `--help` or header comment.

Four kinds of thing live here, and it is worth knowing which you are looking at:

- **launchers** (`run_*.sh`) — one process per year over a whole step, resumable, biggest year
  first. Launch from `tmux` with an **absolute path**; they log to `../logs/`.
- **gates** (`validate_*`) — run them **before** a by-hand GEE ingest, never after.
- **watchers / drivers** (`watch_*`, `*_tick.sh`, `run_07_v2_driver.py`) — unattended supervisors
  for long GEE runs. A `_tick.sh` is one safe-to-cron iteration of its sibling.
- **trials and reports** (`trial-*`, `*_report.py`, `profile_*`) — measurements kept for the record.
  They are not on any path; what they concluded is in the relevant `../docs/notes/` entry.

| Group | Files | Documented in |
|---|---|---|
| **01–02 · training data, cleaning, the fit** | `download_observations.py`, `data_cleaning.R`, `cv_feasibility_report.py`, `veg-fire_remap_clean-google-sheet.R`, `refit_pruning_sweep.R`, `make_fires_table_stats.R`, `status.py` | [`01-training_data.md`](../docs/01-training_data.md), [`02-data_cleaning.md`](../docs/02-data_cleaning.md), [`02-vegetation_remap.md`](../docs/02-vegetation_remap.md), [`02-model_fitting.md`](../docs/02-model_fitting.md) |
| **02 · per-fire diagnostic plots** | `ts_plot_by_fire.R`, `ts_plot_cache.R`, `ts_plot_functions.R`, `ts_predict_functions.R` | [`02-diagnostic_plots.md`](../docs/02-diagnostic_plots.md) |
| **02 · the deployed model** | `export_region_raster.py` (paints `C.REGION_RASTER`), `test-03-model_load.py` | [`02-burn_probability.md`](../docs/02-burn_probability.md) |
| **03 · burn-probability time series** | `test-03-bp_ts.py`, `annual_data_download.py`, `bp_ts_metrics_local_train.R`, `test-bp_ts_metrics_local.R`, `profile_bpts.py`, `bpts_timing_report.py`, `watch_bpts_export.py`, `colab_bpts_export.ipynb` | [`03-bpts.md`](../docs/03-bpts.md), [`03-colab_multi_export.md`](../docs/03-colab_multi_export.md) |
| **04 · SNIC segmentation** | `download_snic.py`, `trial-snic_padding.py`, `trial-snic_wholecountry.py`, `colab_snic_export.ipynb` | [`04-snic.md`](../docs/04-snic.md) |
| **05 · objects and metrics** | `run_05_years.sh`, `mem_monitor.sh`, `objects-benchmarks/` | [`05-object_metrics.md`](../docs/05-object_metrics.md) |
| **06 · labels, model, review, upload** | `objects_labels_prep.R`, `objects_data_functions.R`, `objects_data_explore.R`, `objects_threshold.R`, `objects_importance_ale.R`, `objects_inspect_export.R`, `objects_upload.py`, `validate_upload_zips.py`, `run_06_predict.sh`, `run_06_inspect.sh`, `run_07_upload_zips.sh` | [`06-object_labels.md`](../docs/06-object_labels.md), [`06-object_model.md`](../docs/06-object_model.md), [`06-object_inspection.md`](../docs/06-object_inspection.md) |
| **07 · calendar-year pixels and the exclusion rules** | `run_07_scars.sh`, `validate_scar_zips.py`, `rule_a_aoi_extract.py`, `rule_a_aoi_tag.R`, `rule_a_cap_diagnostic.py` | [`07-vector_to_raster.md`](../docs/07-vector_to_raster.md) |
| **07 · the published products, and driving their export** | `run_07_v2_driver.py`, `v2_driver_tick.sh`, `test-07-v2_driver_stall.py`, `watch_07c.py`, `watch_07c_tick.sh`, `audit_product_properties.py`, `delete_07e_by_year_assets.py` | [`07-published_products.md`](../docs/07-published_products.md) |
| **09 · statistics (episodic)** | `objects_region_tag.R`, `region_areas.py` | [`../statistics/`](../statistics/) |
| **validation (episodic)** | `10_burned_area_by_fire_year.py` | [`../validation/`](../validation/) |
