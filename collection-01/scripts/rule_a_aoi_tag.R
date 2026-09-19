#!/usr/bin/env Rscript
# =============================================================================
# collection-01/scripts/rule_a_aoi_tag.R
#
# Tag every fire OBJECT with whether it intersects the rule-A AOI — the hand-drawn
# agricultural-Pampa polygon that confines rule A (docs/07 "Object exclusion ruleset").
#
# WHY A TAG AND NOT A GEOMETRY TEST INSIDE THE RULE. Rule A is read in three
# places (07a in GEE, 07b locally, 07e in GEE) and they must agree to the object.
# A spatial predicate evaluated three times in two languages is exactly the kind
# of thing that drifts, so it is evaluated ONCE, here, and the other three read a
# column. The AOI itself comes from `config/rule_a_aoi.geojson`, written by
# `rule_a_aoi_extract.py` from the `aoiA` import in the GEE explorer, so there is
# one geometry and one provenance.
#
# INTERSECTS, NOT CENTROID, and not the intersection itself: `terra::is.related()`
# answers the yes/no question directly, which is all the rule asks. Computing
# `terra::intersect()` would build clipped geometries for 78 k polygons a year to
# then throw them away. An object that merely touches the AOI is INSIDE it — that
# is the deliberate reading: the rule is a statement about a region, and a scar
# straddling the edge is half in the agricultural Pampa.
#
# NO FIRE FILTER IS APPLIED — every object is tagged, `fire == 0` included, so the
# table is threshold-agnostic. Join on `oid`.
#
# Usage (from the repo ROOT):
#   Rscript collection-01/scripts/rule_a_aoi_tag.R            # all fire-years
#   Rscript collection-01/scripts/rule_a_aoi_tag.R 2020       # just these
#   FORCE=1 Rscript collection-01/scripts/rule_a_aoi_tag.R    # ignore existing
# =============================================================================

suppressPackageStartupMessages({
  library(terra)
  library(data.table)
})

REPO <- normalizePath(".")
lp <- file.path(REPO, ".local-paths")
STORE <- Sys.getenv("STORE_ROOT")
if (!nzchar(STORE) && file.exists(lp)) {
  ln <- grep("^STORE_ROOT=", readLines(lp), value = TRUE)
  if (length(ln)) STORE <- sub("^STORE_ROOT=", "", ln[1])
}
if (!nzchar(STORE)) stop("no STORE_ROOT in env or .local-paths -- run ./setup.sh")

OBJ_DIR <- file.path(STORE, "collection-01/data/objects-raw")
OUT_DIR <- file.path(STORE, "collection-01/data/objects-analysis")
AOI_FILE <- file.path(REPO, "collection-01/config/rule_a_aoi.geojson")
FORCE <- nzchar(Sys.getenv("FORCE"))

args <- commandArgs(TRUE)
years <- if (length(args)) as.integer(args) else 1998:2025

aoi <- terra::vect(AOI_FILE)
message(sprintf("[aoi] %s  (%d part(s), crs %s)", AOI_FILE, nrow(aoi),
                substr(terra::crs(aoi, describe = TRUE)$code, 1, 12)))

for (fy in years) {
  gpkg <- file.path(OBJ_DIR, sprintf("objects_%d.gpkg", fy))
  out <- file.path(OUT_DIR, sprintf("aoi_rule_a_%d.csv", fy))
  if (!file.exists(gpkg)) { message(sprintf("[FY%d] no gpkg -- skipped", fy)); next }
  if (file.exists(out) && !FORCE) { message(sprintf("[FY%d] exists -- skipped", fy)); next }

  t0 <- Sys.time()
  v <- terra::vect(gpkg)
  if (!terra::same.crs(v, aoi)) v <- terra::project(v, terra::crs(aoi))
  # The PREDICATE, one logical per object -- `is.related()` is `relate()` reduced
  # over y (the AOI is one polygon, so they agree, and this returns a vector not a
  # matrix). NOT intersect(), which would build 78 k clipped geometries only to
  # discard them.
  hit <- terra::is.related(v, aoi, "intersects")
  data.table::fwrite(data.table(oid = v$oid, in_aoi = as.integer(hit)), out)
  message(sprintf("[FY%d] %s of %s objects intersect the AOI  (%.1f min)  -> %s",
                  fy, format(sum(hit), big.mark = ","),
                  format(length(hit), big.mark = ","),
                  as.numeric(difftime(Sys.time(), t0, units = "mins")), basename(out)))
}
