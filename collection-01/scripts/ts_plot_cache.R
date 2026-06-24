#!/usr/bin/env Rscript
# collection-01/scripts/ts_plot_cache.R
#
# Prep/cache step for the time-series diagnostic plots (scripts/ts_plot_*.R,
# notebooks/ts_diagnostics.qmd). For every veg_fire class with a class_NN_fit.rds
# present, predicts burn probability (p_pred) over its FULL set of observations
# (not just the OOF subset in class_NN_oof_predictions.csv) using the RAW-scale
# recipe in ts_predict_functions.R. This is an IN-SAMPLE prediction — see
# models/README.md ("Predicting burn probability") and PLAN_ts_diagnostics.md for
# why that tradeoff is accepted for this diagnostic.
#
# Run from repo root:
#   Rscript collection-01/scripts/ts_plot_cache.R [version]
#
# Re-run manually after syncing new/updated class_NN_fit.rds files — there is no
# file-watch; the present/missing report printed on each run makes staleness evident.

suppressPackageStartupMessages({
  library(data.table)
  library(slider)   # rolling median for p_pred_smooth, below
})
source("collection-01/scripts/ts_predict_functions.R")

KEY_COLS <- c("region", "fire_id", "point_id", "date", "burned", "mb_class_raw", "fit")

build_ts_cache <- function(version = "1",
                            data_dir   = "collection-01/data",
                            models_dir = "collection-01/models-store",
                            out_path   = file.path(models_dir, sprintf("ts_plot_cache_v%s.rds", version))) {

  remap <- fread("collection-01/config/veg_fire_remap.csv")
  classes <- unique(remap[fittable == TRUE, .(veg_fire, veg_fire_name)])[order(veg_fire)]
  classes[, regions := vapply(veg_fire_name, function(nm)
    paste(sort(remap[veg_fire_name == nm, unique(region)]), collapse = "+"), character(1))]

  fit_files <- Sys.glob(file.path(models_dir, "class_*_fit.rds"))
  fit_codes <- as.integer(sub(".*class_0*([0-9]+)_fit\\.rds$", "\\1", fit_files))
  classes[, fit_present := veg_fire %in% fit_codes]
  classes[, fit_path := file.path(models_dir, sprintf("class_%02d_fit.rds", veg_fire))]

  message("Class fit.rds availability:")
  print(classes[, .(class = sprintf("class_%02d", veg_fire), veg_fire_name, regions, fit_present)])
  if (!any(classes$fit_present))
    stop("No class_*_fit.rds found in ", models_dir, " — nothing to predict.")

  fitted <- classes[fit_present == TRUE]
  regions_needed <- sort(unique(remap[veg_fire_name %in% fitted$veg_fire_name & fittable == TRUE, region]))
  message(sprintf("\nRegions to load: %s", paste(regions_needed, collapse = ", ")))

  mb_mos_cols  <- unlist(lapply(PREV, function(v) sprintf("mb_mos_%s_%s", v, SUMM)))
  needed_cols  <- unique(c(KEY_COLS, FOCAL, mb_mos_cols))

  cache_parts <- list()
  for (reg in regions_needed) {
    f <- file.path(data_dir, sprintf("training_observations_%s_v%s.csv", reg, version))
    message(sprintf("\nLoading %s ...", basename(f)))
    d <- fread(f, select = needed_cols)
    d[, date := as.IDate(date)]
    rmp <- remap[region == reg, .(mb_class_raw, veg_fire, veg_fire_name)]
    d <- merge(d, rmp, by = "mb_class_raw", all.x = TRUE)

    for (i in seq_len(nrow(fitted))) {
      code <- fitted$veg_fire[i]
      sub <- d[veg_fire == code]
      if (!nrow(sub)) next
      mdl <- readRDS(fitted$fit_path[i])              # not `fit`: would be shadowed by the `fit` column in sub's j-scope
      sub[, p_pred := predict_class(sub, mdl)]
      message(sprintf("  [class_%02d] %s — %s obs predicted", code, fitted$veg_fire_name[i], format(nrow(sub), big.mark = ",")))
      cache_parts[[length(cache_parts) + 1]] <-
        sub[, .(region, fire_id, point_id, date, burned, fit, veg_fire, veg_fire_name, NBR, NBR2, p_pred)]
    }
    rm(d); gc()
  }

  cache <- rbindlist(cache_parts)
  cache[, region_fire_id := paste(region, fire_id)]

  # burn_class is a POINT-level identity (was this point EVER burned, i.e. does
  # it carry any burned==1 obs), not the per-observation flag -- so a burned
  # point's whole trajectory (its pre-fire history included) is one consistent
  # color. burned==1 obs only occur for burned points in their post-fire window
  # (see CLAUDE.md's labeling rule), so any(burned==1) correctly recovers point
  # identity. Burned first -> top of any future Burned/Unburned ordering.
  cache[, is_burned_pt := any(burned == 1), by = .(region_fire_id, point_id)]
  cache[, burn_class := factor(is_burned_pt, c(TRUE, FALSE), c("Burned", "Unburned"))]
  cache[, is_burned_pt := NULL]

  # n5 rolling median of p_pred per point's own time series, mirroring
  # collection-00/data_viz_Lican/functions.R's p_med5 (slide_dbl, .before=2,.after=2).
  setorder(cache, region_fire_id, point_id, date)
  cache[, p_pred_smooth := slide_dbl(p_pred, median, .before = 2, .after = 2,
                                      .complete = FALSE, na.rm = TRUE),
        by = .(region_fire_id, point_id)]

  # Fire pre/post-fire window dates, for the dashed-line/ribbon overlay in
  # ts_plot_functions.R (mirrors collection-00/data_viz_Lican/functions.R's
  # dates_burn/dates_unburn zones). training_fires_BA/CUYO lack pre_lwr -- same
  # fallback as the reference: pre_lwr = post_lwr - 365.
  windows <- rbindlist(lapply(regions_needed, function(reg) {
    tf <- fread(file.path(data_dir, sprintf("training_fires_%s.csv", reg)))
    if (!"pre_lwr" %in% names(tf)) tf[, pre_lwr := NA_character_]
    tf <- tf[, .(region = reg, fire_id, pre_lwr = as.IDate(pre_lwr), pre_upr = as.IDate(pre_upr),
                 post_lwr = as.IDate(post_lwr), post_upr_long = as.IDate(post_upr_long),
                 post_upr_short = as.IDate(post_upr_short))]
    tf[is.na(pre_lwr), pre_lwr := post_lwr - 365]
    tf
  }))
  windows[, region_fire_id := paste(region, fire_id)]
  windows[, c("region", "fire_id") := NULL]
  cache <- merge(cache, windows, by = "region_fire_id", all.x = TRUE)

  saveRDS(cache, out_path)
  message(sprintf("\nWritten %s: %s rows, %d classes, %d fires.",
                  out_path, format(nrow(cache), big.mark = ","),
                  uniqueN(cache$veg_fire), uniqueN(cache$region_fire_id)))
  invisible(cache)
}

args    <- commandArgs(trailingOnly = TRUE)
VERSION <- if (length(args) >= 1) args[[1]] else "1"
build_ts_cache(version = VERSION)
