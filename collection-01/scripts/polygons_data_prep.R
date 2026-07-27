#!/usr/bin/env Rscript
# =============================================================================
# polygons_data_prep.R — step-06 labels: GEE polygons-data assets -> one table
# =============================================================================
# Turns the per-collaborator fire/non-fire collections exported by the GEE
# `training_polygons_*` scripts (docs/06 "Exports") into the single labelled table the
# step-06 object model is fitted on. Two stages, either runnable on its own:
#
#   [download] one asset -> ONE FILE, GeoPackage, in collection-01/data/polygons_data/
#              `polygons_data_<author>.gpkg`. A file per asset ON PURPOSE: when one
#              collaborator adds points and re-runs their export, only that file is
#              re-downloaded. Existing files are SKIPPED unless --force.
#              GPKG, not SHP: the labels mix POINTS and POLYGONS in one table (shapefile
#              cannot), field names are not truncated to 10 chars, and it is what step 05
#              already writes.
#
#   [merge]    every label feature is matched to the step-05 fire OBJECTS OF ITS OWN
#              FIRE-YEAR, and the object's metrics are attached ->
#              collection-01/data/polygons_data/polygons_data_merged.csv
#              One row per (label feature, intersecting object) pair, so a drawn polygon
#              covering several objects labels all of them, and a point that hit nothing
#              is still present with oid = NA.
#
# Run from the repo ROOT:
#   Rscript collection-01/scripts/polygons_data_prep.R [all|download|merge] [--force] [author ...]
#     all       (default) download the missing assets, then merge
#     download  download only
#     merge     merge only — ALWAYS uses every .gpkg present in the folder, so the merged
#               table stays complete even when only one author was re-downloaded
#     --force   re-download assets whose .gpkg already exists
#     author…   restrict the DOWNLOAD to these authors (lowercase, as in the asset name)
#
# HOW THE MATCHING IS DONE (fast, and never loads a whole year)
# A year of objects is ~78 k polygons / ~330 MB and only a handful are ever hit, so a year is
# NEVER read whole. Two nested filters:
#   1. GPKG R-TREE, in GDAL: the year's labels are grouped into 1-degree blocks and each block
#      is read back with `terra::vect(extent = <that block's label bbox>)`. An extent filter is
#      answered from the GeoPackage spatial index, so only the few hundred objects near the
#      labels are ever parsed into R (ms per block).
#   2. EXACT PREDICATE: `terra::relate(labels, objects, "intersects")` on that small subset —
#      the T/F predicate only, no geometry is built. Labels go in chunks of LAB_CHUNK so the
#      logical matrix stays small.
# Correctness of the pre-filter: every label's own bbox lies inside its block rectangle, so any
# object touching a label necessarily has an envelope overlapping that rectangle and is returned
# by GDAL. The pre-filter can only ever return MORE candidates than needed; step 2 decides.
#
# WHY terra AND NOT sf FOR THE PREDICATE (measured, keep it this way): step-05 objects can be
# enormous MULTIPOLYGONs — 1999_24193 is 13 053 parts / 643 742 vertices, because the 1-px
# dilation welds a whole Corrientes fire season into one object. sf::st_intersects degrades
# pathologically on those: ONE point against that object costs ~55 s (identical with
# prepared = TRUE/FALSE and with the arguments swapped), which made FY 1999 alone take 176 s.
# terra::relate answers the same block in 1.6 s — 0.04 s for that object — and returns exactly
# the same pairs (verified pair-for-pair against sf on every FY 1999 block).
# One trap that cost a debugging round: terra cannot hold mixed geometry types in one
# SpatVector, so the labels are split POINT vs POLYGON per block and converted separately.
# Do NOT "fix" that by st_cast()ing the labels to POINT — a polygon label silently collapses to
# its first vertex and loses its objects (one 1999 polygon label went from 131 objects to 4).
#
# Fire-year, not calendar year (docs/04 §2): `fire_year` on a label is the FY start year Y1
# (FY = 1 May Y1 -> 30 Apr Y2) and step 05 names its outputs the same way, so the label's
# fire_year maps straight onto objects_<fire_year>.gpkg. A label drawn for a year RANGE was
# already written once per year by the GEE export, so nothing special happens here.
#
# Output columns of polygons_data_merged.csv:
#   feat_id                  label id, "<author>:<row in that author's gpkg>"
#   author src class fire_year y_lwr y_upr geom_type   as collected (class 1 fire / 0 non-fire)
#   lon lat                  label centroid, for tracing a suspect row back on the map
#   oid                      matched step-05 object ("<fy>_<n>"), NA when the label hit none
#   n_objects                objects this label hit (0 = unmatched, >1 = a polygon label)
#   oid_n_labels             labels that hit this object
#   oid_class_conflict       TRUE when this object was labelled BOTH fire and non-fire
#   <raster metrics>         objects_<fy>_raster_metrics.csv, joined on oid
#   <shape metrics>          objects_<fy>_shape_metrics.csv,  joined on oid
# The next step (object model) decides what to do with the flagged rows; nothing is dropped
# here, so a labelling problem is visible instead of silently resolved.
# =============================================================================

suppressPackageStartupMessages({
  library(sf)          # reads the label gpkg (mixed point/polygon in one layer)
  library(terra)       # object reads + the intersects predicate (see note above)
  library(data.table)
})

# ── config ───────────────────────────────────────────────────────────────────
ASSET_DIR <- paste0("projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/",
                    "TRAINING-DATA/POLYGONS-DATA")
GEE_PROJECT <- "mapbiomas-fire-485203"          # == utils/constants.py C.GEE_PROJECT

DATA_DIR  <- "collection-01/data/polygons_data" # per-asset gpkg + the merged csv
POLY_DIR  <- "collection-01/data/snic-polygons" # step-05 objects (symlink into the store)
MERGED    <- file.path(DATA_DIR, "polygons_data_merged.csv")

BLOCK_DEG <- 1        # label-grouping block for the r-tree reads (degrees)
PAD_DEG   <- 1e-5     # ~1 m, keeps a single-point block from being a degenerate rectangle
LAB_CHUNK <- 256L     # labels per relate() call, caps the logical matrix at CHUNK x n_objects
CRS_WORK  <- 4326     # step-05 objects are WGS84; labels come out of GEE the same

# ── args ─────────────────────────────────────────────────────────────────────
argv    <- commandArgs(trailingOnly = TRUE)
force   <- "--force" %in% argv
argv    <- argv[argv != "--force"]
mode    <- if (length(argv) && argv[1] %in% c("all", "download", "merge")) argv[1] else "all"
authors <- setdiff(argv, c("all", "download", "merge"))

# progress goes to stderr: unbuffered, so a long run reports live through a pipe or tee
msg <- function(...) write(sprintf(...), stderr())

# ── [1] download: one asset -> one GeoPackage ────────────────────────────────
# rgee needs a python with earthengine-api; .local-paths records the project's venv
# (set by ./setup.sh) so this works without touching the user's global reticulate config.
init_ee <- function() {
  if (file.exists(".local-paths")) {
    kv <- read.dcf(textConnection(sub("=", ": ", readLines(".local-paths"), fixed = TRUE)))
    if ("PYTHON" %in% colnames(kv)) Sys.setenv(RETICULATE_PYTHON = kv[1, "PYTHON"])
  }
  suppressPackageStartupMessages(library(rgee))
  rgee::ee_Initialize(project = GEE_PROJECT, quiet = TRUE)
  invisible(TRUE)
}

download_assets <- function(only = character(), force = FALSE) {
  dir.create(DATA_DIR, showWarnings = FALSE, recursive = TRUE)
  init_ee()
  assets <- ee$data$listAssets(list(parent = ASSET_DIR))$assets
  if (!length(assets)) stop("no assets under ", ASSET_DIR)
  ids <- vapply(assets, function(a) a$id, character(1))
  names(ids) <- sub("^polygons_data_", "", basename(ids))
  if (length(only)) {
    miss <- setdiff(only, names(ids))
    if (length(miss)) stop("no asset for author(s): ", paste(miss, collapse = ", "))
    ids <- ids[only]
  }
  for (a in names(ids)) {
    out <- file.path(DATA_DIR, sprintf("polygons_data_%s.gpkg", a))
    if (file.exists(out) && !force) { msg("  skip %-9s (have %s)", a, basename(out)); next }
    # getDownloadURL is a signed URL — no auth needed on the GET, and unlike getInfo()
    # it has no 5000-element ceiling if a collection grows.
    url <- ee$FeatureCollection(ids[[a]])$getDownloadURL("GeoJSON")
    tmp <- tempfile(fileext = ".geojson")
    on.exit(unlink(tmp), add = TRUE)
    download.file(url, tmp, quiet = TRUE, mode = "wb")
    v <- sf::st_read(tmp, quiet = TRUE)
    if (is.na(sf::st_crs(v))) sf::st_crs(v) <- CRS_WORK   # GeoJSON is always WGS84
    # keep only the columns the GEE export defines (drops EE's own id/system:index)
    keep <- intersect(c("class", "fire_year", "y_lwr", "y_upr", "geom_type", "author", "src"),
                      names(v))
    v <- v[, keep]
    sf::st_write(v, out, layer = sprintf("polygons_data_%s", a),
                 delete_dsn = TRUE, quiet = TRUE)
    msg("  %-9s %5d features -> %s", a, nrow(v), basename(out))
  }
  invisible(TRUE)
}

# ── [2] labels: every gpkg in the folder, stacked ────────────────────────────
read_labels <- function() {
  files <- sort(list.files(DATA_DIR, pattern = "^polygons_data_[^.]+\\.gpkg$",
                           full.names = TRUE))
  if (!length(files)) stop("no polygons_data_*.gpkg in ", DATA_DIR, " — run the download first")
  parts <- lapply(files, function(f) {
    v <- sf::st_read(f, quiet = TRUE)
    a <- sub("^polygons_data_", "", tools::file_path_sans_ext(basename(f)))
    if (!"author" %in% names(v) || any(is.na(v$author))) v$author <- a
    # feat_id = one row of that author's exported table (ranges were already written once
    # per year in GEE, so the replicas are separate rows and get separate ids).
    v$feat_id <- sprintf("%s:%d", a, seq_len(nrow(v)))
    v <- sf::st_transform(v, CRS_WORK)
    v[, c("feat_id", "author", "src", "class", "fire_year", "y_lwr", "y_upr", "geom_type")]
  })
  labs <- do.call(rbind, parts)
  msg("labels: %d features from %d files (%s)", nrow(labs), length(files),
      paste(sprintf("%s %d", basename(files), vapply(parts, nrow, integer(1))), collapse = ", "))
  labs
}

# ── [3] one fire-year: label -> object pairs ─────────────────────────────────
# sf subset of ONE geometry type -> SpatVector carrying feat_id (terra refuses mixed types)
as_spat <- function(x) {
  v <- terra::vect(sf::st_as_text(sf::st_geometry(x)), crs = "EPSG:4326")
  v$feat_id <- x$feat_id
  v
}

# T/F intersects, labels chunked so the logical matrix stays small -> (feat_id, oid) pairs
pairs_of <- function(lv, ov) {
  out <- vector("list", ceiling(nrow(lv) / LAB_CHUNK))
  for (k in seq_along(out)) {
    i <- seq.int((k - 1L) * LAB_CHUNK + 1L, min(k * LAB_CHUNK, nrow(lv)))
    m <- matrix(as.logical(terra::relate(lv[i, ], ov, "intersects")), nrow = length(i))
    w <- which(m, arr.ind = TRUE)
    out[[k]] <- data.table(feat_id = lv$feat_id[i][w[, 1]], oid = ov$oid[w[, 2]])
  }
  rbindlist(out)
}

match_year <- function(labs_y, fy) {
  gpkg  <- file.path(POLY_DIR, sprintf("objects_%d.gpkg", fy))
  layer <- sprintf("objects_%d", fy)
  if (!file.exists(gpkg)) {
    warning(sprintf("FY %d: %s missing — %d labels left unmatched", fy, gpkg, nrow(labs_y)),
            call. = FALSE)
    return(data.table(feat_id = labs_y$feat_id, oid = NA_character_))
  }
  # per-label bbox, then 1-degree blocks so each GDAL read is one index-friendly rectangle
  bb  <- do.call(rbind, lapply(sf::st_geometry(labs_y),
                               function(g) as.numeric(sf::st_bbox(g))))
  blk <- paste(floor(((bb[, 1] + bb[, 3]) / 2) / BLOCK_DEG),
               floor(((bb[, 2] + bb[, 4]) / 2) / BLOCK_DEG))
  gtp <- as.character(sf::st_geometry_type(labs_y))
  ublk  <- unique(blk)
  pairs <- vector("list", length(ublk))
  nobj  <- 0L
  for (i in seq_along(ublk)) {
    idx  <- which(blk == ublk[i])
    rect <- c(min(bb[idx, 1]) - PAD_DEG, min(bb[idx, 2]) - PAD_DEG,
              max(bb[idx, 3]) + PAD_DEG, max(bb[idx, 4]) + PAD_DEG)
    objs <- terra::vect(gpkg, layer = layer,
                        extent = terra::ext(rect[1], rect[3], rect[2], rect[4]))
    nobj <- nobj + nrow(objs)
    if (!nrow(objs)) next
    # one relate() per geometry type present in this block (POINT and POLYGON never mix)
    pairs[[i]] <- rbindlist(lapply(unique(gtp[idx]), function(g)
      pairs_of(as_spat(labs_y[idx[gtp[idx] == g], ]), objs)))
  }
  pairs <- rbindlist(pairs)
  # labels that hit nothing stay in, with oid = NA
  lost <- setdiff(labs_y$feat_id, pairs$feat_id)
  out  <- rbindlist(list(pairs, data.table(feat_id = lost, oid = NA_character_)))
  msg("  FY %d: %4d labels in %2d block(s), %6d candidate objects read -> %5d pair(s), %4d unmatched",
      fy, nrow(labs_y), length(ublk), nobj, nrow(pairs), length(lost))
  out
}

# ── [4] metrics of one fire-year, raster + shape joined on oid ───────────────
year_metrics <- function(fy) {
  r <- file.path(POLY_DIR, sprintf("objects_%d_raster_metrics.csv", fy))
  s <- file.path(POLY_DIR, sprintf("objects_%d_shape_metrics.csv", fy))
  if (!file.exists(r)) {
    warning(sprintf("FY %d: %s missing — metrics left NA", fy, basename(r)), call. = FALSE)
    return(NULL)
  }
  m <- fread(r)
  if (file.exists(s)) m <- merge(m, fread(s), by = "oid", all.x = TRUE)
  m
}

# ── [5] merge: pairs + metrics + QC flags -> one csv ─────────────────────────
merge_all <- function() {
  labs <- read_labels()
  stopifnot(!anyNA(labs$fire_year), !anyNA(labs$class))
  ctr <- suppressWarnings(sf::st_coordinates(sf::st_centroid(sf::st_geometry(labs))))
  lab <- as.data.table(sf::st_drop_geometry(labs))
  lab[, `:=`(lon = round(ctr[, 1], 6), lat = round(ctr[, 2], 6))]

  years <- sort(unique(lab$fire_year))
  msg("matching %d fire-year(s): %s", length(years), paste(years, collapse = " "))
  out <- vector("list", length(years))
  for (i in seq_along(years)) {
    fy   <- years[i]
    sel  <- lab$fire_year == fy
    prs  <- match_year(labs[sel, ], fy)
    met  <- year_metrics(fy)
    if (!is.null(met)) prs <- merge(prs, met, by = "oid", all.x = TRUE, sort = FALSE)
    out[[i]] <- merge(lab[sel], prs, by = "feat_id", all.x = TRUE, sort = FALSE)
  }
  res <- rbindlist(out, fill = TRUE)

  # QC flags — how many objects a label hit, and whether an object got both classes
  res[, n_objects := sum(!is.na(oid)), by = feat_id]
  res[!is.na(oid), oid_n_labels := uniqueN(feat_id), by = oid]
  res[!is.na(oid), oid_class_conflict := uniqueN(class) > 1L, by = oid]

  lead <- c("feat_id", "author", "src", "class", "fire_year", "y_lwr", "y_upr", "geom_type",
            "lon", "lat", "oid", "n_objects", "oid_n_labels", "oid_class_conflict")
  setcolorder(res, c(lead, setdiff(names(res), lead)))
  setorder(res, fire_year, author, feat_id, oid)

  dir.create(DATA_DIR, showWarnings = FALSE, recursive = TRUE)
  # na = "NA" so an unmatched oid reads back as missing in BOTH fread and pandas
  # (an empty field would come back as the empty string in a character column)
  fwrite(res, MERGED, na = "NA")

  # ── report ────────────────────────────────────────────────────────────────
  msg("")
  msg("wrote %s: %d rows, %d columns", MERGED, nrow(res), ncol(res))
  msg("  labels          %d  (%d fire / %d non-fire)",
      uniqueN(res$feat_id),
      uniqueN(res[class == 1]$feat_id), uniqueN(res[class == 0]$feat_id))
  msg("  matched objects %d unique oid, %d label-object pair(s)",
      uniqueN(res[!is.na(oid)]$oid), nrow(res[!is.na(oid)]))
  msg("  unmatched       %d label(s) hit no object (oid = NA)", uniqueN(res[is.na(oid)]$feat_id))
  msg("  multi-object    %d label(s) hit >1 object (drawn polygons)",
      uniqueN(res[n_objects > 1]$feat_id))
  msg("  conflicts       %d object(s) labelled BOTH fire and non-fire",
      uniqueN(res[!is.na(oid_class_conflict) & oid_class_conflict]$oid))
  msg("")
  print(dcast(res[!is.na(oid)], fire_year ~ class, value.var = "oid",
              fun.aggregate = uniqueN, fill = 0L))
  msg("")
  print(res[, .(labels = uniqueN(feat_id), objects = uniqueN(oid[!is.na(oid)]),
                unmatched = uniqueN(feat_id[is.na(oid)])), by = author][order(author)])
  invisible(res)
}

# ── main ─────────────────────────────────────────────────────────────────────
if (mode %in% c("all", "download")) {
  msg("== download (%s) ==", if (force) "force" else "skip existing")
  download_assets(only = authors, force = force)
}
if (mode %in% c("all", "merge")) {
  msg("== merge ==")
  merge_all()
}
