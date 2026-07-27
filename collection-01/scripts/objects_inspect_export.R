#!/usr/bin/env Rscript
# =============================================================================
# objects_inspect_export.R — look at the model on a map WITHOUT uploading to GEE
# =============================================================================
# A full-year ingest into GEE takes ~8 h (docs/06 "Uploading the classified fire subset":
# no GCS bucket, so it is a by-hand Code Editor upload). For *inspection* that is wasted
# time — the step-05 GPKG is already on disk, so this joins the model output onto it and
# writes layers you can open locally, today.
#
# Two products per fire-year:
#   [1] <fy>_objects_pred_<variant>.gpkg   EVERY object of the year: geometry + all metrics +
#       p_mean/p_sd/p_q05/p_q95/p_width + the collection-00 filter verdict (c00_pass).
#       -> QGIS: open it, graduate the fill on p_mean, add an XYZ imagery basemap, and use
#          the attribute table / filter expressions to walk through cases. QGIS reads the
#          GPKG spatial index directly, so 78 k polygons pan smoothly.
#   [2] <fy>_objects_sample_<variant>.geojson  a SMALL stratified sample (default 20 per
#       p_mean decile, geometry simplified) — small enough to drop into a browser map as a
#       CLIENT-SIDE layer: geemap/leafmap `Map.add_geojson(path)` puts it straight on the
#       map next to GEE tiles (candseed, Landsat min-NBR) with NO asset upload, because only
#       the GEE *imagery* is server-side. Keep it in the low thousands of features; the
#       limit here is the browser, not Earth Engine.
#
# Run from the repo ROOT (needs a `predict` run for the year first):
#   Rscript collection-01/scripts/objects_inspect_export.R [year ...] [--sample N] [--no-full]
#     year…      fire-years (default: every year that has a prediction CSV)
#     --sample N objects per p_mean decile in the GeoJSON (default 20; 0 = skip it)
#     --no-full  skip the big GPKG, write only the sample
#     --full     attach the full-predictor model's predictions (default: the grouped model)
#
# Writes to collection-01/data/objects-inspect/.
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(terra)
})
source("collection-01/scripts/objects_data_functions.R")

OUT_DIR  <- "collection-01/data/objects-inspect"
PRED_DIR <- "collection-01/data/objects-predictions"
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

msg <- function(...) write(sprintf(...), stderr())

argv    <- commandArgs(trailingOnly = TRUE)
no_full <- "--no-full" %in% argv
n_samp  <- { i <- match("--sample", argv); if (is.na(i)) 20L else as.integer(argv[i + 1L]) }
# which model's predictions to attach — matches the 06-object_model.R variant switch, and goes
# into the output names so the two models' layers never overwrite each other
VARIANT <- if ("--full" %in% argv) "full" else "grouped"
years   <- suppressWarnings(as.integer(grep("^[0-9]{4}$", argv, value = TRUE)))
if (!length(years)) {
  f <- list.files(PRED_DIR, pattern = sprintf("^objects_[0-9]{4}_pred_%s\\.csv$", VARIANT))
  years <- sort(as.integer(sub("^objects_([0-9]{4}).*$", "\\1", f)))
}
if (!length(years)) stop("no ", VARIANT, " predictions in ", PRED_DIR,
                         " — run 06-object_model.R predict first")

for (fy in years) {
  pf <- file.path(PRED_DIR, sprintf("objects_%d_pred_%s.csv", fy, VARIANT))
  if (!file.exists(pf)) { msg("FY %d: no %s — skipped", fy, basename(pf)); next }
  msg("")
  msg("== FY %d ==", fy)

  # attributes: step-05 metrics + the model output + the c-00 verdict, all keyed on oid
  att <- read_year_objects(fy)
  att[, c00_pass := c00_pass(att)]
  att <- merge(att, fread(pf)[, !"fire_year"], by = "oid", all.x = TRUE)
  msg("  %d objects, %d scored (p_mean > 0.5: %.1f %%)", nrow(att), sum(!is.na(att$p_mean)),
      100 * mean(att$p_mean > .5, na.rm = TRUE))

  t0 <- Sys.time()
  v  <- vect(file.path(POLY_DIR, sprintf("objects_%d.gpkg", fy)),
             layer = sprintf("objects_%d", fy))
  # merge() on a SpatVector keeps geometry and appends the columns, matched on oid
  v <- merge(v, as.data.frame(att), by = "oid", all.x = TRUE)
  msg("  geometry read + joined in %.0f s", as.numeric(difftime(Sys.time(), t0, units = "secs")))

  if (!no_full) {
    f <- file.path(OUT_DIR, sprintf("%d_objects_pred_%s.gpkg", fy, VARIANT))
    writeVector(v, f, overwrite = TRUE)
    msg("  QGIS layer -> %s (%.0f MB)", f, file.size(f) / 1024^2)
  }

  if (n_samp > 0L) {
    # stratified by p_mean decile so the sample spans confident-fire ... confident-non-fire
    # AND the uncertain middle, which is what you actually want to eyeball
    s <- as.data.table(as.data.frame(v))[!is.na(p_mean)]
    s[, dec := cut(p_mean, seq(0, 1, .1), include.lowest = TRUE)]
    set.seed(1L)
    pick <- s[, .(oid = if (.N <= n_samp) oid else sample(oid, n_samp)), by = dec]$oid
    sv   <- v[match(pick, v$oid), ]
    # simplify to keep the browser payload small; inspection does not need pixel-exact edges
    sv   <- simplifyGeom(sv, tolerance = 0.0003)   # ~30 m
    f    <- file.path(OUT_DIR, sprintf("%d_objects_sample_%s.geojson", fy, VARIANT))
    writeVector(sv, f, filetype = "GeoJSON", overwrite = TRUE)
    msg("  browser/geemap sample -> %s (%d objects, %.1f MB)", f, nrow(sv),
        file.size(f) / 1024^2)
  }
  rm(v, att); gc(FALSE)
}
