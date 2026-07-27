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
#   [1] <fy>_objects_pred_<variant>.gpkg   EVERY object of the year, with the INSPECTION field
#       set (see FIELDS below): the two verdicts (model / collection-00 filter), why the model
#       called it that way, and the evidence behind it.
#       -> QGIS: graduate the fill on p_mean or categorise on `verdict`, add an XYZ imagery
#          basemap, and walk cases with attribute-table filters. QGIS reads the GPKG spatial
#          index directly, so 78 k polygons pan smoothly.
#   [2] <fy>_objects_sample_<variant>.geojson  a SMALL stratified sample (default 20 per p_mean
#       decile, geometry simplified) — small enough to drop into a browser map as a CLIENT-SIDE
#       layer: geemap/leafmap `Map.add_geojson(path)` puts it straight on the map next to GEE
#       tiles with NO asset upload, because only the GEE *imagery* is server-side.
#
# WHY A CURATED FIELD SET, NOT EVERYTHING (docs/06 "Looking at it on a map"): the 23 raw
# frac_c* columns are not in the deployed model and 28 years of them is dead weight in an
# attribute table you have to read by eye. `--fields all` brings them back for one year.
#
# THE QGIS EXPRESSIONS THIS FIELD SET IS DESIGNED FOR:
#   "verdict" != 'both'            where the model and the c-00 filter disagree
#   abs("p_margin") < 0.05         the borderline calls — the ones worth eyeballing
#   "p_width" > 0.5                where the model has no idea (round-2 collection targets)
#   "size_class" IN ('<0.5 ha','0.5-1 ha')   the minimum-size decision
#
# Run from the repo ROOT (needs a `predict` run for the year first — scripts/run_06_predict.sh):
#   Rscript collection-01/scripts/objects_inspect_export.R [year ...] [options]
#     year…        fire-years (default: every year that has a prediction CSV)
#     --sample N   objects per p_mean decile in the GeoJSON (default 20; 0 = skip it)
#     --no-full    skip the big GPKG, write only the sample
#     --fields all keep every metric column, including the 23 raw frac_c*
#     --full       attach the full-predictor model's predictions (default: the grouped model)
#
# Writes to collection-01/data/objects-inspect/ (~350 MB per year — 28 years is ~9 GB, so
# expect to keep only the years you are actively looking at).
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
all_fld <- { i <- match("--fields", argv); !is.na(i) && identical(argv[i + 1L], "all") }
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
                         " — run scripts/run_06_predict.sh first")

# ── the inspection field set ────────────────────────────────────────────────
# Ordered the way you read a row: what is it, what did we decide, why, then the evidence.
FIELDS <- c(
  # identity and size. n_pixels is here because area is latitude-dependent (a pixel is
  # 900*cos(lat) m², 831 down to 517), so "how many pixels is this really" is a separate question.
  "oid", "fire_year", "area_ha", "n_pixels", "size_class",
  # the two verdicts and their disagreement, as one categorical to symbolise on
  "fire", "c00_pass", "verdict",
  # WHY the model said that: the probability, its uncertainty, the cut that applied to this
  # object's size band, and the signed distance to it
  "p_mean", "p_width", "p_thresh", "p_margin", "th_band", "c00_case",
  # burn evidence and timing (all model predictors)
  "seed_mean", "n_mean", "burned_around_1", "burned_around_2", "burned_around_3",
  "doy_median", "date_span", "date_median_date",
  # the five aggregated vegetation fractions the deployed model actually uses
  VEG_GROUP_COLS,
  # geometry shape metrics (near-meaningless below ~10 px — see the notebook)
  "perimeter_m", "convexity", "mbr_fill", "mbr_elongation", "circularity", "shape_index")

for (fy in years) {
  pf <- file.path(PRED_DIR, sprintf("objects_%d_pred_%s.csv", fy, VARIANT))
  if (!file.exists(pf)) { msg("FY %d: no %s — skipped", fy, basename(pf)); next }
  msg("")
  msg("== FY %d ==", fy)

  # attributes: step-05 metrics + the model output + both verdicts, all keyed on oid
  att <- read_year_objects(fy)
  set(att, j = "c00_pass", value = c00_pass(att))
  set(att, j = "c00_case", value = as.character(c00_case(att)))
  set(att, j = "size_class", value = as.character(size_class(att$area_ha)))
  att <- merge(att, fread(pf)[, !"fire_year"], by = "oid", all.x = TRUE)

  # recompute the threshold that applied, so the layer can show WHY — and cross-check it against
  # the `fire` column the predict run wrote. A mismatch means config/object_model_thresholds.csv
  # changed after the prediction, which would make the map lie about the product.
  th <- apply_thresholds(att$area_ha, att$p_mean)
  n_diff <- sum(th$fire != att$fire, na.rm = TRUE)
  if (n_diff > 0L)
    msg("  WARNING: %d object(s) disagree with the stored `fire` — thresholds changed since the
         prediction run. Re-run predict for this year.", n_diff)
  for (k in c("p_thresh", "p_margin", "th_band")) set(att, j = k, value = th[[k]])

  # one categorical for the disagreement map: this is the single most useful symbology here,
  # because "where do the model and the old empirical filter part ways" is exactly the question
  set(att, j = "verdict", value = fifelse(
    is.na(att$fire), "unscored",
    fifelse(att$fire == 1L & att$c00_pass, "both",
      fifelse(att$fire == 1L & !att$c00_pass, "model only",
        fifelse(att$fire == 0L & att$c00_pass, "c00 only", "neither")))))

  keep <- if (all_fld) names(att) else intersect(FIELDS, names(att))
  miss <- setdiff(FIELDS, names(att))
  if (!all_fld && length(miss)) stop("missing expected field(s): ", paste(miss, collapse = ", "))
  att <- att[, ..keep]

  msg("  %d objects, %d scored | fire %.1f %% | c00 %.1f %% | disagree %.1f %%",
      nrow(att), sum(!is.na(att$p_mean)), 100 * mean(att$fire == 1L, na.rm = TRUE),
      100 * mean(att$c00_pass, na.rm = TRUE), 100 * mean(att$verdict %in% c("model only", "c00 only")))
  msg("  %d field(s): %s", ncol(att), paste(head(names(att), 8), collapse = ", "))

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
