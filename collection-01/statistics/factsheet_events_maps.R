#!/usr/bin/env Rscript
# =============================================================================
# collection-01/statistics/factsheet_events_maps.R  —  THE EVENT MAPS (láminas 6-8)
#
# One map per event (statistics/docs/factsheet-2026-spec.md "Láminas 6 a 8: los
# mapas de eventos"). It only DRAWS; the numbers quoted on the slides are
# computed by factsheet_events_stats.py. Each map is written as figNN_mapa_<key>
# (PNG 300 dpi + PDF) into data/statistics/factsheet_2026_figures_and_tables/,
# the folder the designer gets. Bottom to top:
#   1. Esri World Imagery, fetched by `maptiles` for the extent (date unknown);
#   2. the event's area of interest (AOI), as an outline;
#   3. every accepted fire in the extent, filled, clipped to the extent.
#
# THE AOI ONLY SAYS WHERE TO LOOK. The extent is the AOI's bbox plus a margin,
# and the map shows everything in it — fires outside the AOI included — so the
# AOI is a reference, not a mask.
#
# THE FIRE SET. The published selection, copied from fire_counts.R `accepted()`:
# `fire == 1 & area_ha >= 1 & not(rule A) & not(rule B)`. KEEP IN SYNC with it.
# Every event is a CALENDAR year, like the rest of the factsheet: the fires of
# fire-years cal-1 (its Jan-Apr) and cal (its May-Dec) whose `date_median` falls
# in that calendar year. A fire is drawn whole into the year of its median date;
# the numbers (factsheet_events_stats.py) split it by pixel date instead.
#
# THE HANDOFF TO PYTHON. For each event this writes data/statistics/events/
# <key>.geojson: two features, `role` = "aoi" and "frame" (the map extent), with
# the calendar year, the figure number and the AOI's name. factsheet_events_stats.py computes the slide numbers over
# exactly those two geometries, so they are defined once, here.
#
# THE AOIs. A lat-lon box is the extent itself and is not drawn (Cholila).
# Delta del Paraná is Ramón's pirorregión (data/statistics/
# pyrorregions/). The Quebrada del Condorito park is the OpenStreetMap boundary
# (relation 10371635, via Nominatim), downloaded once and cached under
# data/statistics/events/.
#
# Usage (from the repo ROOT):
#   Rscript collection-01/statistics/factsheet_events_maps.R            # all
#   Rscript collection-01/statistics/factsheet_events_maps.R pnqc_2025  # one
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(sf)
  library(terra)
  library(maptiles)
  library(tidyterra)
  library(ggplot2)
  library(ggspatial)
})
sf_use_s2(FALSE)

STAT_DIR <- "collection-01/data/statistics"
EVT_DIR  <- file.path(STAT_DIR, "events")
FIG_DIR  <- file.path(STAT_DIR, "factsheet_2026_figures_and_tables")
PYRO_ZIP <- file.path(STAT_DIR, "pyrorregions", "pirorregiones_preliminar_shp.zip")

# ── the events ───────────────────────────────────────────────────────────────
# aoi: a named AOI (outlined on the map) or a lat-lon box c(xmin, ymin, xmax,
# ymax) that IS the extent (no outline); name: the AOI's name, for the CSV (""
# for a box); fig: the figure number in the deliverable; cal: the calendar year;
# zoom: tile zoom level; pad: margin around the AOI's bbox, as a fraction of its
# width.
EVENTS <- list(
  cholila_2015 = list(aoi = c(-72.042341, -42.569838, -71.398399, -42.041381),
                      name = "", fig = 16, cal = 2015, zoom = 12, pad = 0),
  delta_2020   = list(aoi = "delta", name = "Pirorregión Delta del Paraná",
                      fig = 17, cal = 2020, zoom = 10, pad = 0.03),
  pnqc_2025    = list(aoi = "pnqc", name = "Parque Nacional Quebrada del Condorito",
                      fig = 18, cal = 2025, zoom = 13, pad = 0.10)
)

# ── the published object selection — KEEP IN SYNC with fire_counts.R ─────────
MIN_FIRE_HA   <- 1
T_GRASS       <- 0.70
GRASS_WINDOW  <- c("07-01", "11-15")
RULE_A_MAX_HA <- 150
T_AGRI        <- 0.40
EPOCH         <- as.Date("1970-01-01")

grass_window_days <- function(fy) {
  vapply(GRASS_WINDOW, function(md) {
    mm <- as.integer(substr(md, 1, 2))
    y  <- if (mm >= 5) fy else fy + 1L
    as.integer(as.Date(sprintf("%d-%s", y, md)) - EPOCH)
  }, numeric(1))
}

accepted <- function(fy) {
  p <- fread(sprintf("collection-01/data/objects-pred/objects_%d_pred.csv", fy),
             select = c("oid", "fire"))
  m <- fread(sprintf("collection-01/data/objects-raw/objects_%d_raster_metrics.csv", fy),
             select = c("oid", "area_ha", "date_median",
                        "frac_c1", "frac_c2", "frac_c3", "frac_c15"))
  a <- merge(p, m, by = "oid")[fire == 1 & area_ha >= MIN_FIRE_HA & !is.na(date_median)]
  tag <- fread(sprintf("collection-01/data/objects-analysis/aoi_rule_a_%d.csv", fy),
               select = c("oid", "in_aoi"))
  a <- merge(a, tag, by = "oid", all.x = TRUE)
  stopifnot(!anyNA(a$in_aoi))
  w <- grass_window_days(fy)
  a <- a[!(frac_c15 > T_GRASS & date_median >= w[1] & date_median <= w[2] &
           area_ha < RULE_A_MAX_HA & in_aoi == 1L)]
  a <- a[frac_c1 + frac_c2 + frac_c3 <= T_AGRI]
  a[, year := as.integer(format(EPOCH + round(date_median), "%Y"))]
  a[, .(oid, area_ha, year)]
}

# ── the AOIs ─────────────────────────────────────────────────────────────────
load_aoi <- function(name) {
  if (is.numeric(name)) {
    x <- st_sf(geometry = st_as_sfc(st_bbox(
      c(xmin = name[1], ymin = name[2], xmax = name[3], ymax = name[4]),
      crs = st_crs(4326))))
  } else if (name == "delta") {
    d <- file.path(tempdir(), "pyro")
    unzip(PYRO_ZIP, exdir = d)
    x <- st_read(list.files(d, "\\.shp$", full.names = TRUE), quiet = TRUE)
    x <- x[x$nombre == "Delta del Paraná", ]
  } else if (name == "pnqc") {
    f <- file.path(EVT_DIR, "pnqc_osm.geojson")
    if (!file.exists(f)) {
      dir.create(EVT_DIR, showWarnings = FALSE, recursive = TRUE)
      x <- st_read(paste0("https://nominatim.openstreetmap.org/lookup?",
                          "osm_ids=R10371635&format=geojson&polygon_geojson=1"),
                   quiet = TRUE)
      st_write(x[, "display_name"], f, quiet = TRUE)
    }
    x <- st_read(f, quiet = TRUE)
  } else stop("unknown AOI: ", name)
  stopifnot(nrow(x) == 1)
  x
}

# ── graticule labels, sparse and in Spanish: 33° 30' S, 60° 00' O ────────────
# Two or three breaks per axis, at the coarsest round step that still gives two.
sparse_breaks <- function(lo, hi) {
  for (step in c(2, 1, 0.5, 0.25, 1/6, 1/12)) {
    b0 <- ceiling(lo / step) * step
    b1 <- floor(hi / step) * step
    if (b1 - b0 >= step - 1e-9) return(seq(b0, b1, by = step))
  }
  waiver()
}
dms <- function(x, pos, neg) {
  d <- floor(abs(x) + 1e-9); m <- round((abs(x) - d) * 60)
  sprintf("%d° %02d' %s", d, m, ifelse(x < 0, neg, pos))
}

# ── one map ──────────────────────────────────────────────────────────────────
make_map <- function(key, ev) {
  aoi   <- load_aoi(ev$aoi)
  aoi_m <- st_transform(aoi, 3857)

  # the extent: the AOI's bbox plus a margin, in Web Mercator (the tiles' CRS)
  bb    <- st_bbox(aoi_m)
  pad   <- ev$pad * unname(diff(bb[c(1, 3)]))
  ext_m <- st_as_sfc(st_bbox(c(xmin = bb[["xmin"]] - pad, ymin = bb[["ymin"]] - pad,
                               xmax = bb[["xmax"]] + pad, ymax = bb[["ymax"]] + pad),
                             crs = st_crs(3857)))

  # the geometry handoff to factsheet_events_stats.py
  dir.create(EVT_DIR, showWarnings = FALSE, recursive = TRUE)
  geo <- st_sf(role = c("aoi", "frame"), cal_year = ev$cal, fig = ev$fig,
               aoi_name = ev$name,
               geometry = c(st_geometry(st_transform(aoi, 4326)),
                            st_transform(ext_m, 4326)))
  f_geo <- file.path(EVT_DIR, sprintf("%s.geojson", key))
  if (file.exists(f_geo)) unlink(f_geo)
  st_write(geo, f_geo, quiet = TRUE)

  # every accepted fire in the extent, clipped to it
  fys <- c(ev$cal - 1L, ev$cal)
  a <- rbindlist(lapply(fys, accepted))[year == ev$cal]
  wkt   <- st_as_text(st_transform(ext_m, 4326))
  fires <- do.call(rbind, lapply(fys, function(fy)
    st_read(sprintf("collection-01/data/objects-raw/objects_%d.gpkg", fy),
            quiet = TRUE, wkt_filter = wkt)))
  fires <- fires[fires$oid %in% a$oid, ]
  touch <- lengths(st_intersects(fires, st_transform(aoi, st_crs(fires)))) > 0
  cat(sprintf("[%s] cal %d: %d fires in the extent, %d touch the AOI (%.0f ha, whole fires)\n",
              key, ev$cal, nrow(fires), sum(touch),
              sum(a[oid %in% fires$oid[touch]]$area_ha)))
  fires_m <- suppressWarnings(
    st_intersection(st_make_valid(st_transform(fires, 3857)), ext_m))

  bg     <- get_tiles(ext_m, provider = "Esri.WorldImagery", zoom = ev$zoom, crop = TRUE)
  ext_ll <- st_bbox(st_transform(ext_m, 4326))

  g <- ggplot() +
    geom_spatraster_rgb(data = bg, maxcell = 5e6) +
    { if (!is.numeric(ev$aoi))
        geom_sf(data = aoi_m, fill = NA, colour = "white", linewidth = 0.7) } +
    geom_sf(data = fires_m, fill = "#ff2a1a", colour = NA, alpha = 0.65) +
    annotation_scale(location = "bl", style = "ticks", text_col = "white",
                     line_col = "white") +
    scale_x_continuous(breaks = sparse_breaks(ext_ll[["xmin"]], ext_ll[["xmax"]]),
                       labels = function(x) dms(x, "E", "O")) +
    scale_y_continuous(breaks = sparse_breaks(ext_ll[["ymin"]], ext_ll[["ymax"]]),
                       labels = function(y) dms(y, "N", "S")) +
    coord_sf(crs = 3857, datum = 4326, expand = FALSE) +
    labs(caption = get_credit("Esri.WorldImagery")) +
    theme_void() +
    theme(axis.text.x  = element_text(size = 7, colour = "grey20", margin = margin(t = 2)),
          axis.text.y  = element_text(size = 7, colour = "grey20", margin = margin(r = 2),
                                      angle = 90, hjust = 0.5),
          axis.ticks   = element_line(colour = "grey20", linewidth = 0.3),
          axis.ticks.length = unit(2, "pt"),
          plot.caption = element_text(size = 6, colour = "grey30"),
          plot.margin  = margin(10, 10, 10, 10))

  # Size the canvas to the panel's aspect, so the white margin is the same on
  # all four sides instead of absorbing the slack at the top or bottom.
  r  <- diff(st_bbox(ext_m)[c(2, 4)]) / diff(st_bbox(ext_m)[c(1, 3)])
  W  <- 7
  pw <- W - 2 * 10 / 72 - 0.17                 # margins + the y labels' column
  H  <- pw * r + 2 * 10 / 72 + 0.17 + 0.14     # margins + x labels + caption
  out <- file.path(FIG_DIR, sprintf("fig%02d_mapa_%s", ev$fig, key))
  dir.create(FIG_DIR, showWarnings = FALSE, recursive = TRUE)
  ggsave(paste0(out, ".png"), g, width = W, height = H, dpi = 300, bg = "white")
  ggsave(paste0(out, ".pdf"), g, width = W, height = H, device = cairo_pdf, bg = "white")
  cat(sprintf("[%s] -> %s.{png,pdf}\n", key, out))
}

keys <- commandArgs(trailingOnly = TRUE)
if (!length(keys)) keys <- names(EVENTS)
stopifnot(all(keys %in% names(EVENTS)))
for (k in keys) make_map(k, EVENTS[[k]])
