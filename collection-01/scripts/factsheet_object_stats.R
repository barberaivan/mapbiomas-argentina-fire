#!/usr/bin/env Rscript
# =============================================================================
# collection-01/scripts/factsheet_object_stats.R
#
# The factsheet's OBJECT-BASED tables — "Family B" in docs/11 §5.2: everything
# counted on fires rather than on pixels. No GEE, no re-export, no dependency on
# the September remap: it reads the step-05/06 CSVs and the territory tags from
# `objects_region_tag.R`, so it can be run today and re-run in seconds under a
# different agriculture threshold.
#
# WHAT IT PRODUCES (all in data/objects-analysis/, tidy long format, one row per
# cut — plotting and smoothing happen downstream, in the notebook):
#
#   factsheet_counts_by_month.csv   n fires and their area, by
#                                   layer x region x FIRE YEAR x month
#   factsheet_region_summary.csv    per region: fires/year, area/year, density
#                                   per 10,000 km2, median and p95 fire size
#
# EVERYTHING HERE IS FIRE-YEAR, NOT CALENDAR YEAR, and deliberately so
# (factsheet-notes.md, analysis 3): a fire is one object, its month is the month
# of `date_median`, and the fire-year is the mapping year. The published rasters
# partition per PIXEL into calendar years, which splits a fire that straddles
# 31 December — right for area, wrong for counting events. The two will not add
# up and are not meant to; say which one a number came from.
#
# REGION COUNTS USE `_multi`: an object is counted in every territory it
# intersects, however slightly, so regional counts SUM TO MORE THAN THE NATIONAL
# COUNT. That is what factsheet-notes.md asks for ("muchos fuegos seran contados
# mas de una vez, pero no es problema"). The national row is computed from the
# object set directly, never by summing regions.
#
# TWO PARAMETERS, both environment variables so a sweep is a shell loop:
#   MIN_HA    minimum fire size to count      (default 10 — factsheet analysis 3)
#   AGRI_MAX  drop objects with frac_agri >= this  (default: no filter)
#
# `frac_agri` = frac_c1 + frac_c2 + frac_c3, i.e. veg_fire agriculture_{chaco,
# cuyo-pat, pampa}, EXCLUDING class 4 agriculture-per (docs/11 §2.1).
#
# Usage (from the repo ROOT):
#   Rscript collection-01/scripts/factsheet_object_stats.R
#   MIN_HA=50 AGRI_MAX=0.4 Rscript collection-01/scripts/factsheet_object_stats.R
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
FIRE_YEARS <- 1998:2025
EPOCH <- as.Date("1970-01-01")

MIN_HA   <- as.numeric(Sys.getenv("MIN_HA", "10"))
AGRI_MAX <- suppressWarnings(as.numeric(Sys.getenv("AGRI_MAX", NA)))
TAG <- sprintf("min%gha%s", MIN_HA,
               if (is.na(AGRI_MAX)) "" else sprintf("_agri%g", AGRI_MAX))

msg <- function(...) cat(sprintf(...), "\n", sep = "")

# ── the object set ───────────────────────────────────────────────────────────
# `fire == 1 & area_ha >= MIN_FIRE_HA` is the deployed selection every published
# product paints (docs/07 §1); MIN_HA is an ADDITIONAL reporting threshold on top
# of it, not a replacement, so what is counted is always a subset of what is mapped.
load_objects <- function() {
  out <- lapply(FIRE_YEARS, function(fy) {
    fp <- file.path(PRED_DIR, sprintf("objects_%d_pred.csv", fy))
    fm <- file.path(OBJ_DIR,  sprintf("objects_%d_raster_metrics.csv", fy))
    if (!file.exists(fp) || !file.exists(fm)) return(NULL)
    p <- fread(fp, select = c("oid", "fire"))
    m <- fread(fm, select = c("oid", "area_ha", "date_median",
                              "frac_c1", "frac_c2", "frac_c3"))
    d <- merge(p, m, by = "oid")
    d[, fire_year := fy]
    d[fire == 1 & area_ha >= 1 & !is.na(date_median)]
  })
  d <- rbindlist(out)
  d[, frac_agri := frac_c1 + frac_c2 + frac_c3]
  d[, date := EPOCH + date_median]
  d[, month := as.integer(format(date, "%m"))]
  d[, c("frac_c1", "frac_c2", "frac_c3") := NULL]
  d[]
}

# ── territory areas, for the density column ──────────────────────────────────
# Areas come from the territory polygons themselves, not from a `Shape_Area`
# property: the source layers are in EPSG:3857 and their stored Shape_Area is in
# that projection's badly distorted units. Equal-area (South America Albers)
# instead, which is what a "per 10,000 km2" number has to mean.
territory_areas <- function() {
  ALBERS <- paste0("+proj=aea +lat_1=-5 +lat_2=-42 +lat_0=-32 +lon_0=-60 ",
                   "+x_0=0 +y_0=0 +ellps=aust_SA +units=m +no_defs")
  specs <- list(ecoregions13 = c("ecoregions13.geojson", "GEOCODE"),
                mbregions    = c("mbregions.geojson", "Zona"))
  rbindlist(lapply(names(specs), function(nm) {
    x <- st_read(file.path(ANC_DIR, specs[[nm]][1]), quiet = TRUE)
    if (any(st_geometry_type(x) == "GEOMETRYCOLLECTION"))
      x <- st_cast(st_collection_extract(x, "POLYGON"), "MULTIPOLYGON")
    id <- as.integer(x[[specs[[nm]][2]]])
    a  <- as.numeric(st_area(st_transform(x, ALBERS))) / 1e6      # km2
    data.table(layer = nm, region_id = id, area_km2 = a)[, .(area_km2 = sum(area_km2)),
                                                         by = .(layer, region_id)]
  }))
}

# ── tags ─────────────────────────────────────────────────────────────────────
load_tags <- function(kind) {
  f <- list.files(ANA_DIR, pattern = sprintf("^regions_\\d{4}_%s\\.csv$", kind),
                  full.names = TRUE)
  if (!length(f)) stop("no ", kind, " region tags in ", ANA_DIR,
                       " — run scripts/objects_region_tag.R first")
  rbindlist(lapply(f, fread))
}

# ── main ─────────────────────────────────────────────────────────────────────
msg("MIN_HA = %g   AGRI_MAX = %s", MIN_HA, if (is.na(AGRI_MAX)) "none" else AGRI_MAX)

d <- load_objects()
msg("mapped fires (fire==1, >=1 ha): %s  |  %.2f Mha",
    format(nrow(d), big.mark = ","), sum(d$area_ha) / 1e6)

# A PARTIAL tag set is the dangerous failure here: merge() just drops the untagged
# years, every regional number comes out scaled down by the fraction of years present,
# and nothing in the output says so. objects_region_tag.R takes ~an hour, so running
# this while it is still going is an easy mistake to make.
tagged <- sort(unique(as.integer(substr(
  list.files(ANA_DIR, pattern = "^regions_\\d{4}_multi\\.csv$"), 9, 12))))
missing <- setdiff(sort(unique(d$fire_year)), tagged)
if (length(missing))
  stop(sprintf("region tags missing for fire-year(s) %s — objects_region_tag.R has %d of %d. %s",
               paste(missing, collapse = ", "), length(tagged),
               length(unique(d$fire_year)),
               "Every regional number would be silently scaled down; refusing to write."))

tags <- load_tags("multi")
# ── the agriculture table, per territory ─────────────────────────────────────
# Computed on the UNFILTERED object set, before AGRI_MAX is applied, because its whole
# purpose is to show what each threshold WOULD do — including the one currently chosen.
# This is the table to read when picking the threshold (docs/11 §6) and the one §8's
# Pampa question depends on.
#
# `agri_px_ha` is PIXEL-weighted: sum(area_ha * frac_agri), i.e. the cropland area inside
# mapped fires. `drop_pct_@T` is OBJECT-level: the share of burned area in objects the
# filter removes whole. The gap between them is the point — an object filter removes whole
# spurious crop fires but leaves the cropland inside mixed objects (docs/11 §2.2a), so
# `resid_agri_px_ha@T` says how much cropland is still in the map after filtering at T.
agri_table <- function(d, tags_one) {
  x <- merge(d[, .(oid, area_ha, frac_agri)], tags_one, by = "oid")
  nat <- copy(d)[, `:=`(layer = "national", region_id = 0L, region_name = "Argentina")]
  x <- rbind(x[, .(oid, area_ha, frac_agri, layer, region_id, region_name)],
             nat[, .(oid, area_ha, frac_agri, layer, region_id, region_name)])
  thr <- c(0.2, 0.3, 0.4, 0.5, 0.6)
  out <- x[, {
    tot <- sum(area_ha)
    r <- list(n_fires = .N, burned_ha = tot,
              agri_px_ha = sum(area_ha * frac_agri),
              pct_agri_px = 100 * sum(area_ha * frac_agri) / tot)
    for (t in thr) {
      r[[sprintf("drop_pct_%g", t)]] <- 100 * sum(area_ha[frac_agri >= t]) / tot
      r[[sprintf("resid_agri_px_ha_%g", t)]] <-
        sum(area_ha[frac_agri < t] * frac_agri[frac_agri < t])
    }
    r
  }, by = .(layer, region_id, region_name)]
  setorder(out, layer, -burned_ha)
  out[]
}

tags_one <- load_tags("one")
agri <- agri_table(d, tags_one)
f0 <- file.path(ANA_DIR, "factsheet_agriculture_by_region.csv")
fwrite(agri, f0)
msg("[out] %s  (%d rows)", f0, nrow(agri))
print(agri[layer == "ecoregions13",
           .(region_name, burned_Mha = round(burned_ha / 1e6, 3),
             pct_agri_px = round(pct_agri_px, 1),
             drop_0.3 = round(drop_pct_0.3, 1), drop_0.4 = round(drop_pct_0.4, 1),
             drop_0.6 = round(drop_pct_0.6, 1))])

if (!is.na(AGRI_MAX)) {
  before <- nrow(d); before_ha <- sum(d$area_ha)
  d <- d[frac_agri < AGRI_MAX]
  msg("agriculture filter frac_agri < %g: dropped %s fires (%.1f %%), %.2f Mha (%.1f %%)",
      AGRI_MAX, format(before - nrow(d), big.mark = ","),
      100 * (before - nrow(d)) / before,
      (before_ha - sum(d$area_ha)) / 1e6,
      100 * (before_ha - sum(d$area_ha)) / before_ha)
}

d <- d[area_ha >= MIN_HA]
msg("counted fires (>= %g ha): %s  |  %.2f Mha",
    MIN_HA, format(nrow(d), big.mark = ","), sum(d$area_ha) / 1e6)

dt <- merge(d[, .(oid, fire_year, month, area_ha)], tags, by = "oid",
            allow.cartesian = TRUE)

# The national row is the object set itself, NOT the sum over regions — regions
# double-count boundary fires on purpose (see the header).
nat <- d[, .(layer = "national", region_id = 0L, region_name = "Argentina",
             n_fires = .N, area_ha = sum(area_ha)), by = .(fire_year, month)]
reg <- dt[, .(n_fires = .N, area_ha = sum(area_ha)),
          by = .(layer, region_id, region_name, fire_year, month)]
counts <- rbind(reg, nat[, names(reg), with = FALSE])
setorder(counts, layer, region_id, fire_year, month)

f1 <- file.path(ANA_DIR, sprintf("factsheet_counts_by_month_%s.csv", TAG))
fwrite(counts, f1)
msg("[out] %s  (%s rows)", f1, format(nrow(counts), big.mark = ","))

# ── per-region summary ───────────────────────────────────────────────────────
nyears <- length(unique(d$fire_year))
areas  <- territory_areas()
summ <- rbind(
  dt[, .(n_fires = .N, area_ha = sum(area_ha), median_ha = median(area_ha),
         p95_ha = quantile(area_ha, 0.95)), by = .(layer, region_id, region_name)],
  d[, .(layer = "national", region_id = 0L, region_name = "Argentina",
        n_fires = .N, area_ha = sum(area_ha), median_ha = median(area_ha),
        p95_ha = quantile(area_ha, 0.95))])
summ <- merge(summ, areas, by = c("layer", "region_id"), all.x = TRUE)
summ[layer == "national", area_km2 := sum(areas[layer == "ecoregions13", area_km2])]
summ[, fires_per_year := n_fires / nyears]
summ[, ha_per_year := area_ha / nyears]
summ[, fires_per_year_per_10kkm2 := fires_per_year / (area_km2 / 1e4)]
setorder(summ, layer, -ha_per_year)

f2 <- file.path(ANA_DIR, sprintf("factsheet_region_summary_%s.csv", TAG))
fwrite(summ, f2)
msg("[out] %s  (%d rows)", f2, nrow(summ))
print(summ[layer == "ecoregions13",
           .(region_name, fires_per_year = round(fires_per_year),
             ha_per_year = round(ha_per_year),
             per_10kkm2 = round(fires_per_year_per_10kkm2, 1),
             median_ha = round(median_ha, 1))])
msg("done")
