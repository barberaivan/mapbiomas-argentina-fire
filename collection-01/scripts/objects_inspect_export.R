#!/usr/bin/env Rscript
# =============================================================================
# objects_inspect_export.R — look at the model on a map WITHOUT uploading to GEE
# =============================================================================
# A full-year ingest into GEE is a by-hand Code Editor upload (docs/06 §12: no GCS bucket,
# so `earthengine upload table` cannot be used). For *inspection* that is wasted
# time — the step-05 GPKG is already on disk, so this joins the model output onto it and
# writes layers you can open locally, today.
#
# Two products per fire-year:
#   [1] <fy>_objects_pred.gpkg   EVERY object of the year, with the INSPECTION field
#       set (see FIELDS below): the two verdicts (model / collection-00 filter), why the model
#       called it that way, and the evidence behind it.
#       -> QGIS: graduate the fill on p_mean or categorise on `verdict`, add an XYZ imagery
#          basemap, and walk cases with attribute-table filters. QGIS reads the GPKG spatial
#          index directly, so 78 k polygons pan smoothly.
#   [2] <fy>_objects_sample.geojson  OFF BY DEFAULT (`--sample 0`). A small stratified sample
#       (N per p_mean decile, geometry simplified) for a browser/geemap CLIENT-SIDE layer:
#       `Map.add_geojson(path)` puts it on the map next to GEE tiles with NO asset upload.
#       Inspection is done in QGIS off the GPKG, so this is opt-in: pass `--sample 20`.
#
# WHY A CURATED FIELD SET, NOT EVERYTHING (docs/06 §11): the 23 raw
# frac_c* columns are not model predictors (they are summed into 5 groups) and 28 years of them is dead weight in an
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
#     --sample N   objects per p_mean decile in the companion GeoJSON (default 0 = skip it)
#     --no-full    skip the big GPKG, write only the sample
#     --fields all keep every metric column, including the 23 raw frac_c*
#
# Writes to collection-01/data/objects-inspect-cache/ (up to ~350 MB per year; all 28 years is
# 6.3 GB). That directory is a CACHE — delete it freely, scripts/run_06_inspect.sh rebuilds it in
# about a minute from the prediction CSVs.
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(terra)
})
source("collection-01/scripts/objects_data_functions.R")

OUT_DIR  <- "collection-01/data/objects-inspect-cache"
PRED_DIR <- OBJ_PRED_DIR
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

msg <- function(...) write(sprintf(...), stderr())

argv    <- commandArgs(trailingOnly = TRUE)
no_full <- "--no-full" %in% argv
all_fld <- { i <- match("--fields", argv); !is.na(i) && identical(argv[i + 1L], "all") }
n_samp  <- { i <- match("--sample", argv); if (is.na(i)) 0L else as.integer(argv[i + 1L]) }
years   <- suppressWarnings(as.integer(grep("^[0-9]{4}$", argv, value = TRUE)))
if (!length(years)) {
  f <- list.files(PRED_DIR, pattern = "^objects_[0-9]{4}_pred\\.csv$")
  years <- sort(as.integer(sub("^objects_([0-9]{4}).*$", "\\1", f)))
}
if (!length(years)) stop("no predictions in ", PRED_DIR,
                         " — run scripts/run_06_predict.sh first")

# ── the inspection field set ────────────────────────────────────────────────
# Ordered the way you read a row: what is it, what did we decide, why, then the evidence.
FIELDS <- c(
  # identity and size. n_pixels is here because area is latitude-dependent (a pixel is
  # 900*cos(lat) m², 831 down to 517), so "how many pixels is this really" is a separate question.
  "oid", "fire_year", "area_ha", "n_pixels", "size_class",
  # the deployed call, its two inputs, and the c-00 baseline
  #   fire_model  the model at its size-band cut | fire_tag  the collected label (-1 = none)
  #   fire        THE DEPLOYED CALL: the tag where there is one, else the model
  "fire", "fire_model", "fire_tag", "c00_pass", "verdict",
  # WHY the model said that: the probability, its uncertainty, the cut that applied to this
  # object's size band, and the signed distance to it
  "p_mean", "p_width", "p_thresh", "p_margin", "th_band", "c00_case",
  # burn evidence and timing (all model predictors)
  "seed_mean", "burned_around_1", "burned_around_2", "burned_around_3",
  "doy_median", "date_span", "date_median_date",
  # the five aggregated vegetation fractions the model uses
  VEG_GROUP_COLS,
  # geometry shape metrics (near-meaningless below ~10 px — see the notebook)
  "perimeter_m", "convexity", "mbr_fill", "mbr_elongation", "circularity", "shape_index")

for (fy in years) {
  pf <- file.path(PRED_DIR, sprintf("objects_%d_pred.csv", fy))
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
  n_diff <- sum(th$fire != att$fire_model, na.rm = TRUE)
  if (n_diff > 0L)
    msg("  WARNING: %d object(s) disagree with the stored `fire` — thresholds changed since the
         prediction run. Re-run predict for this year.", n_diff)
  for (k in c("p_thresh", "p_margin", "th_band")) set(att, j = k, value = th[[k]])

  # one categorical for the disagreement map: this is the single most useful symbology here,
  # because "where do the model and the old empirical filter part ways" is exactly the question
  set(att, j = "verdict", value = fifelse(
    is.na(att$fire_model), "unscored",
    fifelse(att$fire_model == 1L & att$c00_pass, "both",
      fifelse(att$fire_model == 1L & !att$c00_pass, "model only",
        fifelse(att$fire_model == 0L & att$c00_pass, "c00 only", "neither")))))

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
    f <- file.path(OUT_DIR, sprintf("%d_objects_pred.gpkg", fy))
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
    f    <- file.path(OUT_DIR, sprintf("%d_objects_sample.geojson", fy))
    writeVector(sv, f, filetype = "GeoJSON", overwrite = TRUE)
    msg("  browser/geemap sample -> %s (%d objects, %.1f MB)", f, nrow(sv),
        file.size(f) / 1024^2)
  }
  rm(v, att); gc(FALSE)
}
