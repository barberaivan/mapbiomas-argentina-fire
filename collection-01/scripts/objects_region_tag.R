#!/usr/bin/env Rscript
# =============================================================================
# collection-01/scripts/objects_region_tag.R
#
# Tag every fire OBJECT with the territories it falls in — the one prerequisite of
# the factsheet's "Family B" analyses (statistics/docs/statistics.md §5.2): number of fires per month per
# region, fire-size distributions per region, anything counted on the fire-year
# object database rather than on pixels.
#
# WHY LOCALLY, AND WHY THIS IS THE CHEAP HALF. Family B needs no GEE and no
# re-export: the geometries are already on disk (`objects-raw/objects_<fy>.gpkg`)
# and the metrics are already in CSVs. That makes it THRESHOLD-AGNOSTIC — the
# agriculture filter (statistics/docs/statistics.md §2) is a `filter()` on the output, so this can be
# built before the threshold is chosen and never rebuilt.
#
# TWO ASSIGNMENTS, because the factsheet needs both:
#
#   regions_<fy>_multi.csv   one row per (oid, layer, region) — an object is listed
#                            in EVERY territory it intersects, however slightly.
#                            This is what `presentations/factsheet-notes.md`
#                            specifies for counting fires: "todos los polígonos que
#                            intersectan la región, no importa si sólo tocan un
#                            extremo... muchos fuegos serán contados más de una vez,
#                            pero no es problema". Sums over regions therefore
#                            EXCEED the national count, by design.
#
#   regions_<fy>_one.csv     one row per oid — the region containing the object's
#                            CENTROID. Use it wherever double counting would be
#                            wrong (a size distribution, a national partition).
#
#                            Centroid, not largest-overlap: `st_intersection` of
#                            1.69 M polygons against 13 complex ecoregion
#                            boundaries is hours, and the two agree for every
#                            object that does not straddle a boundary — which is
#                            nearly all of them. Where they disagree the fire is
#                            genuinely in two regions and `_multi` is the honest
#                            answer anyway.
#
# BOTH TERRITORIAL CUTS in one pass (statistics/docs/statistics.md §6): `ecoregions13` (Burkart et al.
# 1999, the factsheet default) and `mbregions` (the 5 MapBiomas Argentina regions —
# the cut our own veg_fire remap is regionalised by, so it is what `frac_c1/c2/c3`
# already speak).
#
# NO FIRE FILTER IS APPLIED. Every object is tagged, `fire == 0` included, so the
# same table serves the fire layer, an omission analysis, and any later threshold.
# Join to `objects-pred/objects_<fy>_pred.csv` on `oid` to filter.
#
# Usage (from the repo ROOT):
#   Rscript collection-01/scripts/objects_region_tag.R            # all fire-years
#   Rscript collection-01/scripts/objects_region_tag.R 2012 2020  # just these
#   FORCE=1 Rscript collection-01/scripts/objects_region_tag.R    # ignore existing
# =============================================================================

suppressPackageStartupMessages({
  library(sf)
  library(data.table)
  library(parallel)
})
sf_use_s2(FALSE)   # planar predicates on WGS84: intersects/within only, no areas

OBJ_DIR  <- "collection-01/data/objects-raw"
ANC_DIR  <- "collection-01/data/ancillary"
OUT_DIR  <- "collection-01/data/objects-analysis"
FIRE_YEARS <- 1998:2025

LAYERS <- list(
  ecoregions13 = list(file = "ecoregions13.geojson", id = "GEOCODE", name = "LEVEL_2"),
  mbregions    = list(file = "mbregions.geojson",    id = "Zona",    name = "Region")
)

msg <- function(...) cat(sprintf(...), "\n", sep = "")

load_layer <- function(spec) {
  x <- st_read(file.path(ANC_DIR, spec$file), quiet = TRUE)
  x <- x[, c(spec$id, spec$name)]
  names(x)[1:2] <- c("region_id", "region_name")
  x$region_id <- as.integer(x$region_id)

  # GEE's geojson export writes some features as GEOMETRYCOLLECTIONs, which several sf
  # predicates refuse outright (st_coordinates dies on one) and none handle well.
  if (any(st_geometry_type(x) == "GEOMETRYCOLLECTION")) {
    x <- st_cast(st_collection_extract(x, "POLYGON"), "MULTIPOLYGON")
    msg("  [cast] GEOMETRYCOLLECTION -> MULTIPOLYGON")
  }
  # ...and the cast SPLITS such a feature into one row per polygon: ecoregion 9 (Pampa)
  # came back as 2 rows, which would have listed an object in Pampa twice in `_multi` and
  # inflated every per-region count silently. Dissolve back to one row per territory and
  # assert it, rather than trusting the source to be one-row-per-region.
  if (anyDuplicated(x$region_id)) {
    msg("  [dissolve] %d rows -> one per region_id", nrow(x))
    keys <- unique(x[, c("region_id", "region_name"), drop = TRUE])
    geoms <- lapply(keys$region_id, function(k) st_union(st_geometry(x)[x$region_id == k]))
    x <- st_sf(keys, geometry = st_sfc(do.call(c, geoms), crs = st_crs(x)))
  }
  stopifnot(!anyDuplicated(x$region_id))
  # A self-intersecting territory makes st_intersects silently wrong rather than
  # erroring, so repair rather than trust the source.
  bad <- !st_is_valid(x)
  if (any(bad)) {
    msg("  [fix] %d invalid territory geometr%s repaired", sum(bad),
        if (sum(bad) == 1) "y" else "ies")
    x <- st_make_valid(x)
  }
  x
}

tag_year <- function(fy, layers) {
  gpkg <- file.path(OBJ_DIR, sprintf("objects_%d.gpkg", fy))
  if (!file.exists(gpkg)) { msg("[%d] no gpkg, skipped", fy); return(invisible(NULL)) }

  f_multi <- file.path(OUT_DIR, sprintf("regions_%d_multi.csv", fy))
  f_one   <- file.path(OUT_DIR, sprintf("regions_%d_one.csv", fy))
  if (file.exists(f_multi) && file.exists(f_one) && Sys.getenv("FORCE") == "") {
    msg("[%d] already done, skipped", fy); return(invisible(NULL))
  }

  t0 <- Sys.time()
  g <- st_read(gpkg, quiet = TRUE)
  # The centroid of a WGS84 polygon warns about lon/lat; it is used only to pick a
  # containing territory, never as a distance or an area, so the warning is noise.
  ctr <- suppressWarnings(st_centroid(st_geometry(g)))

  multi <- list(); one <- list()
  for (lname in names(layers)) {
    lay <- layers[[lname]]

    hits <- st_intersects(st_geometry(g), st_geometry(lay))
    n <- lengths(hits)
    multi[[lname]] <- data.table(
      oid       = rep(g$oid, n),
      layer     = lname,
      region_id = lay$region_id[unlist(hits)],
      region_name = lay$region_name[unlist(hits)])

    # ST_INTERSECTS, NOT ST_WITHIN, for the centroids. They are equivalent for a point
    # against a polygon (a point is within iff it intersects, boundary aside), but sf
    # only takes the indexed/prepared path for intersects: MEASURED on 2,000 objects
    # against the 13 ecoregions (692 k vertices), st_within is 23.4 s and st_intersects
    # is 2.4 s — 5.5 hours vs 34 minutes over the whole 1.69 M-object collection.
    w <- st_intersects(ctr, st_geometry(lay))
    idx <- vapply(w, function(z) if (length(z)) z[1] else NA_integer_, integer(1))
    # A centroid can land in a hole or just outside a coastal boundary. Fall back to
    # the first intersecting territory before giving up, so `_one` stays a near-total
    # assignment instead of quietly dropping coastal fires.
    miss <- is.na(idx)
    if (any(miss)) {
      idx[miss] <- vapply(hits[miss], function(z) if (length(z)) z[1] else NA_integer_,
                          integer(1))
    }
    one[[lname]] <- data.table(
      oid       = g$oid,
      layer     = lname,
      region_id = ifelse(is.na(idx), NA_integer_, lay$region_id[idx]),
      region_name = ifelse(is.na(idx), NA_character_, lay$region_name[idx]))
  }

  multi <- rbindlist(multi); one <- rbindlist(one)
  fwrite(multi, f_multi); fwrite(one, f_one)

  unassigned <- one[is.na(region_id), .N, by = layer]
  msg("[%d] %s objects | multi %s rows | unassigned %s | %.1f s",
      fy, format(nrow(g), big.mark = ","), format(nrow(multi), big.mark = ","),
      if (nrow(unassigned)) paste(sprintf("%s=%d", unassigned$layer, unassigned$N),
                                  collapse = " ") else "0",
      as.numeric(difftime(Sys.time(), t0, units = "secs")))
}

argv <- commandArgs(trailingOnly = TRUE)
years <- if (length(argv)) as.integer(argv) else FIRE_YEARS
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

msg("loading territories")
layers <- lapply(LAYERS, load_layer)
for (lname in names(layers))
  msg("  %-14s %d features", lname, nrow(layers[[lname]]))

# The years are independent and the territories are read-only, so mclapply's forks share
# the 692 k-vertex layer copy-on-write instead of each rebuilding it — the same reason
# run_07_scars.sh prefers cores inside a year over more year processes (docs/07).
cores <- as.integer(Sys.getenv("OBJ_CORES", "4"))
msg("tagging %d fire-year(s) on %d core(s)", length(years), cores)
invisible(mclapply(years, function(fy) tag_year(fy, layers), mc.cores = cores))
msg("done")
