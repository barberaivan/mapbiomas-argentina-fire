#!/usr/bin/env Rscript
# =============================================================================
# collection-01/statistics/fire_counts.R  —  THE VECTOR PASS
#
# Everything the factsheet needs that is counted on FIRES rather than on pixels,
# plus the light plotting geometry. It never touches Earth Engine: the fire
# objects, their metrics and their territory tags are already on disk.
#
# It is the only factsheet script that reads geometry, and that is the point
# (docs/09 §3): it runs once, in minutes, and writes small tables; every plot
# downstream is then a cheap read of a CSV, so a new figure idea costs nothing.
#
# WHAT IT WRITES  (all into data/statistics/)
#   fires.csv                 one row per mapped fire: calendar year + month, area
#   fires_regions.csv         one row per (fire, ecoregión) — the intersects tagging
#   fire_counts_by_month.csv  ecorregión (+ Argentina) x calendar year x month
#   fire_region_summary.csv   per ecorregión: fires/year, area/year, size quantiles
#   ecoregions13_meta.csv     id, name, centroid lat/lon, polygon area — the palette
#                             order (north -> south) and the density denominator
#   ecoregions13_simple.gpkg  the 13 polygons simplified for plotting (the map-legend)
#
# THE SELECTION IS THE PUBLISHED ONE. `fire == 1 & area_ha >= 1 & not(rule A) &
# not(rule B)`, mirrored from workflow/07-calendar_scars.R (docs/07 §1.1) — the
# factsheet counts the fires that are IN the published map, no more and no fewer.
# The thresholds are repeated here rather than imported because R has no access to
# utils/constants.py; they must be kept in sync with it and with 07-calendar_scars.R.
#
# CALENDAR YEAR AND MONTH, FROM `date_median`. The object database is stored by
# FIRE year (1 May -> 30 Apr), but everything the factsheet reports is calendar
# year (docs/09 §5). A fire is filed whole into the calendar year and month of its
# median date, so a fire that straddles 31 December lands in one year here and is
# split between two in the pixel-based area numbers. That divergence is expected
# and is stated in the captions.
#
# A CALENDAR YEAR NEEDS TWO FIRE-YEARS. Fire-year Y feeds calendar years Y and
# Y+1, so we read all 28 fire-years and assign the calendar year afterwards —
# never aggregate per file. Calendar 1998 (no Jan-Apr) and 2026 (no May-Dec) are
# therefore incomplete and are dropped; the published series is 1999-2025.
#
# ONE FIRE CAN COUNT IN SEVERAL ECORREGIONES. A fire belongs to every region its
# polygon INTERSECTS (`terra::relate(..., "intersects")`, a true/false — never an
# actual intersection geometry, which on 1.3 M polygons would cost hours for an
# answer nothing needs). Regional counts therefore sum to MORE than the national
# count, by design (docs/10, análisis 3.2). The national row is computed from the
# fire set itself, never by summing regions.
#
# Usage (from the repo ROOT):
#   Rscript collection-01/statistics/fire_counts.R
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(sf)
})
sf_use_s2(FALSE)

PRED_DIR <- "collection-01/data/objects-pred"
OBJ_DIR  <- "collection-01/data/objects-raw"
ANA_DIR  <- "collection-01/data/objects-analysis"
ANC_DIR  <- "collection-01/data/ancillary"
OUT_DIR  <- "collection-01/data/statistics"

FIRE_YEARS <- 1998:2025      # the mapping years
CAL_YEARS  <- 1999:2025      # the published calendar series (docs/07)
EPOCH      <- as.Date("1970-01-01")

# ── the published object selection (docs/07 §1.1) ────────────────────────────
# KEEP IN SYNC with utils/constants.py and workflow/07-calendar_scars.R. There is
# no automatic sync; a divergence here would report fires the map does not show.
MIN_FIRE_HA   <- 1
T_GRASS       <- 0.70                  # rule A: frac_c15 above this
GRASS_WINDOW  <- c("07-01", "11-15")   # rule A: date_median inside this window (MM-DD)
RULE_A_MAX_HA <- 150                   # rule A: only fires BELOW this area
T_AGRI        <- 0.40                  # rule B: frac_agri above this

# Reporting size bands for the fire counts. The pirogram's count half is normally
# read at >= 10 ha (docs/10, análisis 3.2); the others are there so a different cut
# is a column choice downstream and not a re-run of this script.
SIZE_CUTS <- c(0, 10, 100, 1000)

# Equal-area CRS for every area and density this file reports. The source layers
# are EPSG:3857, whose stored Shape_Area is in badly distorted units.
ALBERS <- paste0("+proj=aea +lat_1=-5 +lat_2=-42 +lat_0=-32 +lon_0=-60 ",
                 "+x_0=0 +y_0=0 +ellps=aust_SA +units=m +no_defs")

msg <- function(...) cat(sprintf(...), "\n", sep = "")

# ── rule A's window, in day numbers, for one fire year ───────────────────────
# The fire year runs 1 May fy -> 30 Apr fy+1, so a window month >= 5 belongs to fy
# and a month <= 4 to fy+1. Mirrors utils/constants.py::grass_window_days().
grass_window_days <- function(fy) {
  vapply(GRASS_WINDOW, function(md) {
    mm <- as.integer(substr(md, 1, 2))
    y  <- if (mm >= 5) fy else fy + 1L
    as.integer(as.Date(sprintf("%d-%s", y, md)) - EPOCH)
  }, numeric(1))
}

# ── one fire-year: the accepted fires ────────────────────────────────────────
accepted <- function(fy) {
  fp <- file.path(PRED_DIR, sprintf("objects_%d_pred.csv", fy))
  fm <- file.path(OBJ_DIR,  sprintf("objects_%d_raster_metrics.csv", fy))
  fa <- file.path(ANA_DIR,  sprintf("aoi_rule_a_%d.csv", fy))
  # A missing rule-A tag would silently treat every object as OUTSIDE the AOI,
  # disabling half of rule A and producing counts for a map we never published.
  if (!file.exists(fa))
    stop(sprintf("rule-A AOI tag missing for FY%d (%s) — build it with:\n  Rscript collection-01/scripts/rule_a_aoi_tag.R %d",
                 fy, fa, fy))
  if (!file.exists(fp) || !file.exists(fm)) stop(sprintf("FY%d: object tables missing", fy))

  p <- fread(fp, select = c("oid", "fire"))
  m <- fread(fm, select = c("oid", "area_ha", "date_median",
                            "frac_c1", "frac_c2", "frac_c3", "frac_c15"))
  a <- merge(p, m, by = "oid")[fire == 1 & area_ha >= MIN_FIRE_HA & !is.na(date_median)]
  n0 <- nrow(a)

  tag <- fread(fa, select = c("oid", "in_aoi"))
  a[tag, on = "oid", in_aoi := i.in_aoi]
  if (anyNA(a$in_aoi))
    stop(sprintf("FY%d: %d accepted objects absent from the rule-A AOI tag — it is stale (FORCE=1 to rebuild)",
                 fy, sum(is.na(a$in_aoi))))

  w <- grass_window_days(fy)
  a <- a[!(frac_c15 > T_GRASS & date_median >= w[1] & date_median <= w[2] &
           area_ha < RULE_A_MAX_HA & in_aoi == 1L)]
  nA <- n0 - nrow(a)
  a <- a[frac_c1 + frac_c2 + frac_c3 <= T_AGRI]
  nB <- n0 - nA - nrow(a)

  a[, fire_year := fy]
  a[, date := EPOCH + round(date_median)]
  a[, year  := as.integer(format(date, "%Y"))]
  a[, month := as.integer(format(date, "%m"))]
  msg("[FY%d] %6d fires kept of %6d  (rule A -%d, rule B -%d)", fy, nrow(a), n0, nA, nB)
  a[, .(oid, fire_year, date, year, month, area_ha)]
}

# ── territory tags: the intersects assignment, ecoregions13 only ─────────────
load_tags <- function() {
  f <- file.path(ANA_DIR, sprintf("regions_%d_multi.csv", FIRE_YEARS))
  missing <- FIRE_YEARS[!file.exists(f)]
  # A PARTIAL tag set is the dangerous failure: the join would just drop the
  # untagged years and every regional number would come out scaled down, with
  # nothing in the output saying so.
  if (length(missing))
    stop(sprintf("region tags missing for fire-year(s) %s — run scripts/objects_region_tag.R",
                 paste(missing, collapse = ", ")))
  t <- rbindlist(lapply(f, fread))[layer == "ecoregions13"]
  setnames(t, c("region_id", "region_name"), c("ecoregion_id", "ecoregion"))
  t[!is.na(ecoregion_id), .(oid, ecoregion_id, ecoregion)]
}

# ── the ecoregion layer: metadata + a light geometry for plotting ────────────
region_layer <- function() {
  x <- st_read(file.path(ANC_DIR, "ecoregions13.geojson"), quiet = TRUE)
  x <- x[, c("GEOCODE", "LEVEL_2")]
  names(x)[1:2] <- c("ecoregion_id", "ecoregion")
  x$ecoregion_id <- as.integer(x$ecoregion_id)
  # GEE's geojson export writes some features as GEOMETRYCOLLECTIONs, and the cast
  # splits one territory into several rows — which would duplicate a region on the
  # map and in the meta table. Dissolve back and assert one row per id.
  if (any(st_geometry_type(x) == "GEOMETRYCOLLECTION"))
    x <- st_cast(st_collection_extract(x, "POLYGON"), "MULTIPOLYGON")
  if (anyDuplicated(x$ecoregion_id)) {
    keys  <- unique(st_drop_geometry(x))
    geoms <- lapply(keys$ecoregion_id, function(k) st_union(st_geometry(x)[x$ecoregion_id == k]))
    x <- st_sf(keys, geometry = st_sfc(do.call(c, geoms), crs = st_crs(x)))
  }
  stopifnot(!anyDuplicated(x$ecoregion_id))
  if (any(!st_is_valid(x))) x <- st_make_valid(x)
  x
}

# ─────────────────────────────────────────────────────────────────────────────
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

msg("— the published fire selection, 28 fire-years —")
fires <- rbindlist(lapply(FIRE_YEARS, accepted))
msg("total mapped fires: %s  |  %.2f Mha",
    format(nrow(fires), big.mark = ","), sum(fires$area_ha) / 1e6)

# Calendar 1998 and 2026 exist only as fragments of one fire-year each.
edge <- fires[!year %in% CAL_YEARS]
msg("dropping %s fires outside calendar %d-%d (incomplete years %s)",
    format(nrow(edge), big.mark = ","), min(CAL_YEARS), max(CAL_YEARS),
    paste(sort(unique(edge$year)), collapse = ", "))
fires <- fires[year %in% CAL_YEARS]

tags <- load_tags()
tags <- tags[oid %in% fires$oid]
untagged <- fires[!oid %in% tags$oid, .N]
msg("fires with no ecorregión (outside every polygon): %d", untagged)

fwrite(fires, file.path(OUT_DIR, "fires.csv"))
fwrite(tags,  file.path(OUT_DIR, "fires_regions.csv"))
msg("[out] fires.csv (%s rows) | fires_regions.csv (%s rows)",
    format(nrow(fires), big.mark = ","), format(nrow(tags), big.mark = ","))

# ── the geometry, once ───────────────────────────────────────────────────────
msg("— the ecoregion layer —")
eco <- region_layer()
ctr <- suppressWarnings(st_centroid(st_geometry(eco)))
meta <- data.table(
  ecoregion_id = eco$ecoregion_id,
  ecoregion    = eco$ecoregion,
  lon          = st_coordinates(ctr)[, 1],
  lat          = st_coordinates(ctr)[, 2],
  area_km2     = as.numeric(st_area(st_transform(eco, ALBERS))) / 1e6)
setorder(meta, -lat)                       # north -> south: the palette order
meta[, palette_order := .I]
fwrite(meta, file.path(OUT_DIR, "ecoregions13_meta.csv"))

# The plotting layer: 28 MB of coastline detail is invisible at factsheet size and
# makes every ggplot redraw slow. 0.01 deg ~ 1 km, well under a printed pixel.
simple <- st_simplify(eco, dTolerance = 0.01, preserveTopology = TRUE)
f_gpkg <- file.path(OUT_DIR, "ecoregions13_simple.gpkg")
if (file.exists(f_gpkg)) unlink(f_gpkg)
st_write(simple, f_gpkg, quiet = TRUE)
msg("[out] ecoregions13_meta.csv (%d rows) | ecoregions13_simple.gpkg (%.1f MB)",
    nrow(meta), file.size(f_gpkg) / 1e6)

# ── counts by month ──────────────────────────────────────────────────────────
# n_fires counts everything mapped (>= 1 ha); n_ge10/100/1000 are the reporting
# bands. area_ha is the WHOLE object's area filed into its median month — it is a
# fire-count companion, never the burned-area number (that is the toolkit's, and
# it is split per pixel; docs/09 §5).
count_block <- function(d, by) d[, {
  r <- list(n_fires = .N, area_ha = sum(area_ha))
  for (k in SIZE_CUTS[-1]) r[[sprintf("n_ge%d", k)]] <- sum(area_ha >= k)
  r
}, by = by]

reg <- merge(fires[, .(oid, year, month, area_ha)], tags, by = "oid",
             allow.cartesian = TRUE)
counts <- rbind(
  count_block(reg, c("ecoregion_id", "ecoregion", "year", "month")),
  count_block(fires, c("year", "month"))[, `:=`(ecoregion_id = 0L, ecoregion = "Argentina")],
  use.names = TRUE)
setcolorder(counts, c("ecoregion_id", "ecoregion", "year", "month"))
setorder(counts, ecoregion_id, year, month)
fwrite(counts, file.path(OUT_DIR, "fire_counts_by_month.csv"))
msg("[out] fire_counts_by_month.csv (%s rows)", format(nrow(counts), big.mark = ","))

# ── per-region summary ───────────────────────────────────────────────────────
nyears <- length(CAL_YEARS)
summ_block <- function(d, by) d[, .(
  n_fires   = .N,
  n_ge10    = sum(area_ha >= 10),
  area_ha   = sum(area_ha),
  median_ha = median(area_ha),
  p95_ha    = quantile(area_ha, 0.95),
  max_ha    = max(area_ha)), by = by]

summ <- rbind(
  summ_block(reg, c("ecoregion_id", "ecoregion")),
  summ_block(fires, character(0))[, `:=`(ecoregion_id = 0L, ecoregion = "Argentina")],
  use.names = TRUE)
summ <- merge(summ, meta[, .(ecoregion_id, area_km2)], by = "ecoregion_id", all.x = TRUE)
summ[ecoregion_id == 0L, area_km2 := sum(meta$area_km2)]
summ[, fires_per_year := n_fires / nyears]
summ[, ha_per_year := area_ha / nyears]
summ[, fires_per_year_per_10kkm2 := (n_ge10 / nyears) / (area_km2 / 1e4)]
setcolorder(summ, c("ecoregion_id", "ecoregion"))
setorder(summ, -ha_per_year)
fwrite(summ, file.path(OUT_DIR, "fire_region_summary.csv"))
msg("[out] fire_region_summary.csv (%d rows)", nrow(summ))

print(summ[, .(ecoregion, fires_per_year = round(fires_per_year),
               ha_per_year = round(ha_per_year),
               ge10_per_10kkm2 = round(fires_per_year_per_10kkm2, 1),
               median_ha = round(median_ha, 1), max_ha = round(max_ha))])
msg("done")
