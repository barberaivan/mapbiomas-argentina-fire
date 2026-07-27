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
# The five aggregated veg fractions are built here too, so BOTH predictor variants are always
# present on any table the loaders return and the variant choice is purely a column selection.
add_derived <- function(m) {
  m[, doy_median := as.integer(format(as.Date(date_median, origin = EPOCH), "%j"))]
  m[, date_span  := as.numeric(date_max - date_min)]
  add_veg_groups(m)
}

# ── the model columns ────────────────────────────────────────────────────────
VEG_FRAC   <- sprintf("frac_c%d", 1:23)      # veg_fire abundance per class (docs/05 §3)
NON_VEG    <- c("n_pixels", "area_ha", "burned_around_1", "burned_around_2", "burned_around_3",
                "seed_mean", "n_mean", "doy_median", "date_span", "year_calendar", "fire_year",
                "perimeter_m", "convexity", "mbr_fill", "mbr_elongation", "circularity",
                "shape_index")
PREDICTORS <- c(NON_VEG, VEG_FRAC)                       # "full" variant: 40 columns

# ── aggregated vegetation groups — the "grouped" predictor variant ───────────
# Five summed fractions in place of the 23 raw class fractions (22 predictors instead of 40).
# Why: 23 sparse columns were most of the design matrix, many classes are near-empty in the
# labels, and BART draws split variables uniformly over what is available, so the sparse
# fractions dilute the split budget.
#
# Membership is derived from config/veg_fire_remap.csv BY NAME, not from a hand-typed list of
# codes, so a remap change follows through — and a code landing in two groups is an error, not
# a silent reshuffle.
#   [1] frac_agri        annual agriculture, EXCLUDING agriculture-per (perennial plants)
#   [2] frac_grass_inund inundable grassland (only grassland-inund_chaco carries that name;
#                        CUYO's "Herbaceas inundables" was folded into grassland_cuyo upstream)
#   [3] frac_pasture     pastures
#   [4] frac_grass_temp  grassland_{ba,chaco,pampa} — NOT cuyo, NOT patagonia
#   [5] frac_woody       every forest + shrubland class, EXCLUDING forest-inund
# Deliberately NOT region-separated, and deliberately NOT a partition: agriculture-per,
# forest-inund, grassland_cuyo and grassland_pat belong to no group, so the five fractions do
# NOT sum to 1 (the remainder is those four classes plus the 24/25 sentinels).
VEG_REMAP_CSV  <- "collection-01/config/veg_fire_remap.csv"
VEG_GROUP_COLS <- c("frac_agri", "frac_grass_inund", "frac_pasture", "frac_grass_temp",
                    "frac_woody")
PREDICTORS_GROUPED <- c(NON_VEG, VEG_GROUP_COLS)         # "grouped" variant: 22 columns

veg_groups <- function(verbose = FALSE) {
  d  <- unique(fread(VEG_REMAP_CSV)[, .(veg_fire, veg_fire_name)])[veg_fire <= 23L][order(veg_fire)]
  nm <- setNames(d$veg_fire_name, d$veg_fire)
  pick <- function(keep, drop = NULL) {
    k <- names(nm)[grepl(keep, nm)]
    if (!is.null(drop)) k <- setdiff(k, names(nm)[grepl(drop, nm)])
    sort(as.integer(k))
  }
  g <- list(
    frac_agri        = pick("^agriculture", "^agriculture-per"),
    frac_grass_inund = pick("^grassland-inund"),
    frac_pasture     = pick("^pasture"),
    frac_grass_temp  = pick("^grassland_(ba|chaco|pampa)$"),
    frac_woody       = pick("^(forest|shrubland)", "^forest-inund"))
  stopifnot(all(lengths(g) > 0L))
  dup <- unlist(g)[duplicated(unlist(g))]
  if (length(dup)) stop("veg group overlap on veg_fire code(s): ", paste(unique(dup), collapse = ", "))
  if (verbose) {
    for (k in names(g))
      write(sprintf("  %-16s %s", k, paste(sprintf("%d %s", g[[k]], nm[as.character(g[[k]])]),
                                           collapse = ", ")), stderr())
    write(sprintf("  %-16s %s", "(unused)",
                  paste(sprintf("%d %s", setdiff(d$veg_fire, unlist(g)),
                                nm[as.character(setdiff(d$veg_fire, unlist(g)))]),
                        collapse = ", ")), stderr())
  }
  g
}

.veg_groups_cache <- NULL
add_veg_groups <- function(m) {
  if (is.null(.veg_groups_cache)) .veg_groups_cache <<- veg_groups()
  for (k in names(.veg_groups_cache))
    m[, (k) := rowSums(.SD), .SDcols = sprintf("frac_c%d", .veg_groups_cache[[k]])]
  m[]
}

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

# Lower bound of a size-band label, parsed from the label itself ("<1 ha" -> 0, "1-50 ha" -> 1,
# ">=300 ha" -> 300, "300-1000 ha" -> 300). Lets config/object_model_thresholds.csv gain or lose
# bands without any code knowing their names.
band_lower <- function(s) {
  ifelse(grepl("^<", s), 0, suppressWarnings(as.numeric(sub("^[^0-9]*([0-9.]+).*$", "\\1", s))))
}

# ── display size classes ────────────────────────────────────────────────────
# The bands used for LOOKING at the data (the size notebook, the QGIS layer). They are NOT the
# threshold bands and must not be conflated:
#   * these split 1 ha into <0.5 / 0.5-1 and 300+ into 300-1000 / >=1000, because the question
#     they serve is "where do we cut the collection's minimum size", and that decision lives
#     entirely inside the first two;
#   * config/object_model_thresholds.csv has FOUR bands (<1, 1-50, 50-300, >=300) because a
#     band only earns its own threshold if it has enough labels to place one — below 1 ha there
#     are 114 labels total, and above 300 ha the two halves were statistically indistinguishable
#     (docs/06 "Threshold").
# So a QGIS row can sit in display class ">=1000 ha" while its fire call came from band ">=300 ha".
# NOTE ON THE QUANTUM: area_ha is NOT n_pixels * 0.09. The objects are in EPSG:4326 with ~30 m
# cells defined at the equator and area measured on the ellipsoid, so a pixel is 900*cos(lat) m²
# — 831 m² in Formosa down to 517 m² in southern Santa Cruz (median 778). A sub-hectare class is
# therefore a pixel-count RANGE, not a fixed count: 0.5 ha is 6-10 px and 1 ha is 12-19 px
# depending on latitude, so the same 15-px object is >=1 ha in the north and <1 ha in Patagonia.
SIZE_BREAKS_VIEW <- c(0, 0.5, 1, 50, 300, 1000, Inf)
SIZE_LABELS_VIEW <- c("<0.5 ha", "0.5-1 ha", "1-50 ha", "50-300 ha", "300-1000 ha", ">=1000 ha")

size_class <- function(area_ha) {
  cut(area_ha, breaks = SIZE_BREAKS_VIEW, labels = SIZE_LABELS_VIEW, right = FALSE)
}

# ── the deployed fire call ──────────────────────────────────────────────────
# One implementation, used by 06-object_model.R (writing the `fire` column) and by
# objects_inspect_export.R (showing WHY each object was called). Returns the threshold that
# applies to each object alongside the call, so the QGIS layer can be filtered on how close a
# call was rather than only on its outcome.
THRESH_CSV <- "collection-01/config/object_model_thresholds.csv"

threshold_table <- function(path = THRESH_CSV) {
  th <- fread(path)
  th[, lo := band_lower(stratum)]
  if (anyNA(th$lo)) stop("unparseable size band(s) in ", path, ": ",
                         paste(th$stratum[is.na(th$lo)], collapse = ", "))
  setorder(th, lo)
  th
}

apply_thresholds <- function(area_ha, p, path = THRESH_CSV) {
  th <- threshold_table(path)
  i  <- findInterval(area_ha, th$lo)
  data.table(fire     = as.integer(p > th$threshold[i]),
             p_thresh = th$threshold[i],
             th_band  = th$stratum[i],
             # signed distance to the cut: |p_margin| small = the calls to eyeball first
             p_margin = round(p - th$threshold[i], 4))
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
