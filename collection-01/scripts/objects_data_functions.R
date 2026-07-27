# =============================================================================
# objects_data_functions.R — shared step-06 object-data loaders / cleaning / filter
# =============================================================================
# Sourced by BOTH  scripts/objects_data_explore.R  and  workflow/06-object_model.R,
# so the "clean tagged table" they talk about is byte-for-byte the same table.
# Source it from the repo ROOT: source("collection-01/scripts/objects_data_functions.R")
#
# Contents
#   read_year_objects(fy) / read_all_objects()  step-05 raster+shape metrics, joined on oid
#   add_derived(m)                              doy_median + date_span (see note below)
#   PREDICTORS                                  the 40 model columns
#   clean_tagged()                              polygons_data_merged.csv -> one clean row per oid
#   c00_case(d) / c00_pass(d)                   the collection-00 empirical filter
# =============================================================================

suppressPackageStartupMessages(library(data.table))

POLY_DIR   <- "collection-01/data/snic-polygons"                              # step-05 outputs
MERGED_CSV <- "collection-01/data/polygons_data/polygons_data_merged.csv"     # step-06 labels
EPOCH      <- "1970-01-01"                                                    # abs_date origin

# MapBiomas Argentina regions, 2 km buffered — the blocks for the spatially-blocked CV
GEE_PROJECT   <- "mapbiomas-fire-485203"          # == utils/constants.py C.GEE_PROJECT
REGIONS_ASSET <- paste0("projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/",
                        "ARG-Regiones-MapBiomas-buffer2km")
REGIONS_GPKG  <- "collection-01/data/ancillary/ARG-Regiones-MapBiomas-buffer2km.gpkg"

# ── step-05 objects: one fire-year, raster + shape metrics joined on oid ──────
object_years <- function() {
  f <- list.files(POLY_DIR, pattern = "^objects_[0-9]{4}_raster_metrics\\.csv$")
  sort(as.integer(sub("^objects_([0-9]{4}).*$", "\\1", f)))
}

read_year_objects <- function(fy) {
  r <- fread(file.path(POLY_DIR, sprintf("objects_%d_raster_metrics.csv", fy)))
  s <- fread(file.path(POLY_DIR, sprintf("objects_%d_shape_metrics.csv", fy)))
  m <- merge(r, s, by = "oid", all.x = TRUE)
  m[, fire_year := fy]                    # the FY start year, == the oid prefix (docs/04 §2)
  add_derived(m)
}

read_all_objects <- function(years = object_years()) {
  rbindlist(lapply(years, read_year_objects), use.names = TRUE)
}

# ── derived date features ────────────────────────────────────────────────────
# date_{median,min,max} are ABSOLUTE day counts since the epoch, so their raw value is
# mostly a year label — a tree splitting on them would be splitting on the year twice, and
# the 7 fire-years with NO labels (2000, 2002, 2007, 2013, 2018, 2021, 2025) fall outside
# every training split, where trees are constant anyway. Keep the two parts that carry
# information a year identifier does not: WHEN in the season it burned, and for HOW LONG.
# The year itself stays available through fire_year / year_calendar (docs/06).
add_derived <- function(m) {
  m[, doy_median := as.integer(format(as.Date(date_median, origin = EPOCH), "%j"))]
  m[, date_span  := as.numeric(date_max - date_min)]
  m[]
}

# ── the model columns ────────────────────────────────────────────────────────
VEG_FRAC   <- sprintf("frac_c%d", 1:23)      # veg_fire abundance per class (docs/05 §3)
PREDICTORS <- c("n_pixels", "area_ha", "burned_around_1", "burned_around_2", "burned_around_3",
                "seed_mean", "n_mean", "doy_median", "date_span", "year_calendar", "fire_year",
                VEG_FRAC,
                "perimeter_m", "convexity", "mbr_fill", "mbr_elongation", "circularity",
                "shape_index")

# ── clean tagged table: the fitting set ─────────────────────────────────────
# polygons_data_merged.csv is one row per (label, object) PAIR and keeps every problem case
# flagged rather than dropped (scripts/polygons_data_prep.R). Fitting needs the opposite:
# one row per OBJECT, no ambiguity, no NA. Four cuts, each reported:
#   [1] oid == NA          the label hit no object — nothing to classify
#   [2] oid_class_conflict the same object was labelled fire AND non-fire — unresolvable
#   [3] duplicates         many labels on one object collapse to one row (deterministic:
#                          lowest feat_id kept; the surviving author/src describe THAT label)
#   [4] NA predictors      all-dieback objects have no seed/date stats by design (docs/05 §3)
clean_tagged <- function(verbose = TRUE) {
  d  <- fread(MERGED_CSV, na.strings = c("NA", ""))
  rep <- list(pairs = nrow(d), labels = uniqueN(d$feat_id))

  d <- d[!is.na(oid)]
  rep$dropped_unmatched <- rep$pairs - nrow(d)

  conflicted <- unique(d[oid_class_conflict %in% TRUE]$oid)
  d <- d[!oid %in% conflicted]
  rep$dropped_conflict_objects <- length(conflicted)

  setorder(d, oid, feat_id)
  n_before <- nrow(d)
  d <- unique(d, by = "oid")
  rep$dropped_duplicate_rows <- n_before - nrow(d)

  d <- add_derived(d)
  ok <- complete.cases(d[, ..PREDICTORS])
  rep$dropped_na_objects <- sum(!ok)
  rep$dropped_na_oids    <- d$oid[!ok]
  d <- d[ok]

  rep$objects <- nrow(d)
  rep$fire    <- sum(d$class == 1L)
  rep$nonfire <- sum(d$class == 0L)
  attr(d, "clean_report") <- rep
  if (verbose) print_clean_report(rep)
  d
}

print_clean_report <- function(rep) {
  m <- function(...) write(sprintf(...), stderr())
  m("clean_tagged(): %d pair(s) from %d label(s) ->", rep$pairs, rep$labels)
  m("  -%5d row(s)     label hit no object (oid NA)",      rep$dropped_unmatched)
  m("  -%5d object(s)  labelled BOTH fire and non-fire",   rep$dropped_conflict_objects)
  m("  -%5d row(s)     duplicate labels on the same object", rep$dropped_duplicate_rows)
  m("  -%5d object(s)  NA in a predictor%s", rep$dropped_na_objects,
    if (length(rep$dropped_na_oids)) paste0(" (", paste(rep$dropped_na_oids, collapse = ", "), ")") else "")
  m("  =%5d object(s)  %d fire / %d non-fire", rep$objects, rep$fire, rep$nonfire)
}

# ── regions, for the spatially-blocked CV ───────────────────────────────────
# Same rgee bootstrap as scripts/polygons_data_prep.R::init_ee — if the venv discovery
# changes, change it in both.
init_ee <- function() {
  if (file.exists(".local-paths")) {
    kv <- read.dcf(textConnection(sub("=", ": ", readLines(".local-paths"), fixed = TRUE)))
    if ("PYTHON" %in% colnames(kv)) Sys.setenv(RETICULATE_PYTHON = kv[1, "PYTHON"])
  }
  suppressPackageStartupMessages(library(rgee))
  rgee::ee_Initialize(project = GEE_PROJECT, quiet = TRUE)
  invisible(TRUE)
}

# Downloads the regions asset once (5 features) into data/ancillary/.
ensure_regions <- function(force = FALSE) {
  if (file.exists(REGIONS_GPKG) && !force) return(REGIONS_GPKG)
  dir.create(dirname(REGIONS_GPKG), showWarnings = FALSE, recursive = TRUE)
  init_ee()
  url <- ee$FeatureCollection(REGIONS_ASSET)$getDownloadURL("GeoJSON")
  tmp <- tempfile(fileext = ".geojson")
  on.exit(unlink(tmp), add = TRUE)
  download.file(url, tmp, quiet = TRUE, mode = "wb")
  v <- terra::vect(tmp)
  terra::writeVector(v, REGIONS_GPKG, overwrite = TRUE)
  write(sprintf("downloaded %d region(s) -> %s", nrow(v), REGIONS_GPKG), stderr())
  REGIONS_GPKG
}

# Adds `region` / `zona` from the LABEL's lon/lat. Using the label location rather than the
# object's own is deliberate: it keeps every object a single drawn polygon labelled inside one
# block, which is the point of blocking. terra, not sf, for the same reason as everywhere else
# in step 06 (the region polygons are big multi-part geometries).
assign_region <- function(d) {
  reg <- terra::vect(ensure_regions())
  reg <- reg[order(reg$Zona), ]
  pts <- terra::vect(as.matrix(d[, .(lon, lat)]), type = "points", crs = "EPSG:4326")
  m   <- matrix(as.logical(terra::relate(pts, reg, "intersects")), nrow = nrow(d))
  # the 2 km buffer makes neighbouring regions overlap, so a point can be inside two ->
  # lowest Zona wins, deterministically
  idx <- apply(m, 1L, function(r) if (any(r)) which(r)[1] else NA_integer_)
  if (anyNA(idx)) {                    # just outside the buffered outline -> nearest region
    out <- which(is.na(idx))
    idx[out] <- terra::nearest(pts[out, ], reg)$to_id
    write(sprintf("assign_region(): %d label(s) outside every region -> nearest", length(out)),
          stderr())
  }
  d[, `:=`(region = reg$Region[idx], zona = reg$Zona[idx])]
}

# ── the collection-00 empirical filter ──────────────────────────────────────
# Verbatim from collection-00/workflow/08-object_based_filtering.js: a size-stratified rule,
# NOT a model. Three accept cases; anything else (incl. area_ha < a1) is rejected.
#   case 1   a1 <= area < a2 : convexity > .5, burned_around_3 > .7, circularity > .01, shape_index < 7
#   case 2   a2 <= area < a3 : convexity > .4, burned_around_3 > .6,                    shape_index < 7
#   case 3        area >= a3 : accepted outright (very large objects are rarely non-fire)
# Note burned_around_3 is a PROPORTION in both collections (step 05 stores the 7x7 cell count
# already divided; collection-00 divided in GEE), so the thresholds transfer as written.
C00 <- list(
  a1 = 1, a2 = 50, a3 = 300,
  case1 = c(convexity = 0.5, burned_around_3 = 0.7, circularity = 0.01, shape_index = 7),
  case2 = c(convexity = 0.4, burned_around_3 = 0.6, shape_index = 7))

# size stratum of each row, named by the filter case that applies to it
c00_case <- function(d) {
  cut(d$area_ha, breaks = c(-Inf, C00$a1, C00$a2, C00$a3, Inf), right = FALSE,
      labels = c("0 <1ha (reject)", sprintf("1 [%g,%g)", C00$a1, C00$a2),
                 sprintf("2 [%g,%g)", C00$a2, C00$a3), sprintf("3 >=%g", C00$a3)))
}

C00_COLS <- c("area_ha", "convexity", "burned_around_3", "circularity", "shape_index")

# TRUE = kept as fire. NA in any tested metric counts as a FAIL (never silently a pass).
c00_pass <- function(d) {
  # an absent column would make d$col NULL and the whole & chain logical(0), which recycles
  # into a silent all-NA answer instead of an error — so check first
  miss <- setdiff(C00_COLS, names(d))
  if (length(miss)) stop("c00_pass(): missing column(s): ", paste(miss, collapse = ", "))
  t1 <- C00$case1; t2 <- C00$case2
  yes <- function(x, thr, op = `>`) !is.na(x) & op(x, thr)
  c1 <- yes(d$area_ha, C00$a1, `>=`) & yes(d$area_ha, C00$a2, `<`) &
        yes(d$convexity, t1[["convexity"]]) & yes(d$burned_around_3, t1[["burned_around_3"]]) &
        yes(d$circularity, t1[["circularity"]]) & yes(d$shape_index, t1[["shape_index"]], `<`)
  c2 <- yes(d$area_ha, C00$a2, `>=`) & yes(d$area_ha, C00$a3, `<`) &
        yes(d$convexity, t2[["convexity"]]) & yes(d$burned_around_3, t2[["burned_around_3"]]) &
        yes(d$shape_index, t2[["shape_index"]], `<`)
  c3 <- yes(d$area_ha, C00$a3, `>=`)
  c1 | c2 | c3
}

# binary-classification summary of any pass/fail vector against the labels
pass_report <- function(pass, truth) {
  tp <- sum(pass & truth == 1L); fp <- sum(pass & truth == 0L)
  fn <- sum(!pass & truth == 1L); tn <- sum(!pass & truth == 0L)
  data.table(n = length(truth), tp = tp, fp = fp, fn = fn, tn = tn,
             sensitivity = tp / (tp + fn), specificity = tn / (tn + fp),
             precision   = tp / (tp + fp), accuracy    = (tp + tn) / length(truth))
}

# rank-based AUC (no extra package)
auc_fast <- function(score, truth) {
  r <- rank(score); n1 <- sum(truth == 1L); n0 <- sum(truth == 0L)
  if (n1 == 0 || n0 == 0) return(NA_real_)
  (sum(r[truth == 1L]) - n1 * (n1 + 1) / 2) / (n1 * n0)
}
