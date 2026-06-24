#!/usr/bin/env Rscript
# collection-01/scripts/ts_plot_by_fire.R
#
# One time-series PNG per fire, written to
# models/prediction_plots/{region}/{region_fire_id}.png. A fire's points can
# belong to more than one veg_fire class (each point's previous-year land
# cover decides its class), so a fire's panel pools all of its points across
# every class it appears in -- the cache already carries the correct
# class-specific p_pred per point, so pooling does not mix models, only rows.
#
# This is the canonical per-fire plot. These same per-fire panels are also
# rebuilt in-memory (not re-read from disk) and combined with patchwork inside
# notebooks/_model_fit_diagnostics_child.qmd, which separately saves its own
# per-class combined grids to models/prediction_plots/class_NN_*/_combined.png
# (a different artifact -- a multi-fire grid for the rendered HTML report, not
# this script's one-fire-pooled-across-classes PNGs).
#
# Run from repo root:
#   Rscript collection-01/scripts/ts_plot_by_fire.R [version]

suppressPackageStartupMessages(library(data.table))
source("collection-01/scripts/ts_plot_functions.R")

run_by_fire <- function(version = "1",
                         models_dir = "collection-01/models",
                         cache_path = file.path(models_dir, sprintf("ts_plot_cache_v%s.rds", version)),
                         out_root   = file.path(models_dir, "prediction_plots")) {

  cache <- readRDS(cache_path)
  regions <- sort(unique(cache$region))
  message(sprintf("Plotting per-fire panels for %d regions to %s ...", length(regions), out_root))

  n_total <- 0L
  for (reg in regions) {
    sub_region <- cache[region == reg]
    out_dir <- file.path(out_root, reg)
    dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

    fires <- sort(unique(sub_region$region_fire_id))
    for (rf in fires) {
      panel <- plot_fire_panel(sub_region[region_fire_id == rf], title = rf)
      ggsave(file.path(out_dir, paste0(rf, ".png")), panel,
             width = 7, height = 7.5, dpi = 150, bg = "white")
    }
    message(sprintf("  %s: %d fires", reg, length(fires)))
    n_total <- n_total + length(fires)
  }
  message(sprintf("Done. Wrote %d PNGs across %d regions.", n_total, length(regions)))
}

args    <- commandArgs(trailingOnly = TRUE)
VERSION <- if (length(args) >= 1) args[[1]] else "1"
run_by_fire(version = VERSION)
