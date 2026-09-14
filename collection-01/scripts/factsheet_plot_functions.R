#!/usr/bin/env Rscript
# =============================================================================
# collection-01/scripts/factsheet_plot_functions.R
#
# Palette, theme and builders for the factsheet's MULTI-REGION line plots
# (factsheet-notes.md, "Convenciones para graficos multi-region" + analyses 2/4).
# Sourced by scripts/factsheet_plots.R; nothing here writes a file or reads the
# environment, so it can be sourced from a notebook too.
#
# The two normalisations are deliberately DIFFERENT and both live here:
#   norm_month()  months sum to 100 %  -- "que % de lo que se quema ocurre en
#                                         cada mes" (analysis 4)
#   norm_year()   series / its own mean -- "veces el anio tipico" (analysis 2)
# With 28 years a sum-to-100 % axis averages ~3.6 % per year, which reads as
# nothing; with 12 months and a seasonal peak the % reads well. Hence the split.
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
  library(sf)
})

msg <- function(...) cat(sprintf(...), "\n", sep = "")

# ── the 13 ecoregions ────────────────────────────────────────────────────────
# GEOCODE -> name, from the verified 16->13 crosswalk in docs/09-statistics.md
# §4.2. Names are the clean UTF-8 ones of the 13-class asset (the Stats-Arg_*
# layers are Latin-1-as-UTF-8 and must not reach a CSV a designer reads).
ECO13_NAMES <- c(
  "1"  = "Altos Andes",            "2"  = "Bosques Patagónicos",
  "3"  = "Campos y Malezales",     "4"  = "Chaco",
  "5"  = "Delta e Islas del Paraná", "6" = "Espinal",
  "7"  = "Estepa Patagónica",      "8"  = "Monte",
  "9"  = "Pampa",                  "10" = "Puna",
  "11" = "Selva Paranaense",       "12" = "Yungas",
  "13" = "Islas del Atlántico Sur")

# North -> south by approximate centroid latitude. This ordering IS the palette:
# hue runs warm (north) to cool (south) along it, so a reader infers "this line
# is northern" from hue alone, without going to the map.
ECO13_NORTH_TO_SOUTH <- c(10, 12, 11, 4, 3, 1, 5, 6, 8, 9, 7, 2, 13)

# Lightness alternates along the ramp on purpose. A smooth warm->cool gradient
# would make latitude-adjacent regions nearly identical, which is exactly when
# two lines are most likely to overlap; alternating value keeps neighbours apart
# in the line plot AND keeps adjacent polygons readable on the map, at the cost
# of a slightly less silky gradient.
ECO13_COLORS <- setNames(
  c("#7F2704",  # Puna
    "#F16913",  # Yungas
    "#A63603",  # Selva Paranaense
    "#FDAE6B",  # Chaco
    "#E6B800",  # Campos y Malezales
    "#8C8C3A",  # Altos Andes
    "#A1D99B",  # Delta e Islas del Paraná
    "#238B45",  # Espinal
    "#66C2A4",  # Monte
    "#00695C",  # Pampa
    "#6BAED6",  # Estepa Patagónica
    "#08519C",  # Bosques Patagónicos
    "#6A51A3"), # Islas del Atlántico Sur
  as.character(ECO13_NORTH_TO_SOUTH))

# Islas del Atlantico Sur reaches ~36 deg W, some 2,000 km east of the mainland:
# leaving it in blows the map extent out and squashes Argentina into a sliver.
# It also carries essentially no fire. Excluded by default from BOTH the map and
# the line plots so the two always show the same set of regions.
ECO13_DROP <- 13L

C_GREY_LINE <- "#CCCCCC"   # non-focal lines
C_GREY_FILL <- "#E8E8E8"   # non-focal polygons
C_GREY_EDGE <- "#FFFFFF"   # polygon borders

# South America Albers — the same equal-area projection territory_areas() uses
# in factsheet_object_stats.R. The source layers are EPSG:3857, which makes
# Patagonia look enormous; for a shape-legend map that matters.
ALBERS <- paste0("+proj=aea +lat_1=-5 +lat_2=-42 +lat_0=-32 +lon_0=-60 ",
                 "+x_0=0 +y_0=0 +ellps=aust_SA +units=m +no_defs")

# ── fire-year month axis ─────────────────────────────────────────────────────
# The fire year runs 1 May Y -> 30 Apr Y+1 (utils/constants.py §2), so the month
# axis runs May..Apr: that is the order of the data AND it stops the fire season
# being cut in half at the panel edge.
FY_MONTHS <- c(5:12, 1:4)
FY_MONTH_LABELS <- c("M", "J", "J", "A", "S", "O", "N", "D",
                     "E", "F", "M", "A")

fy_month_factor <- function(month) factor(month, levels = FY_MONTHS)

# ── theme ────────────────────────────────────────────────────────────────────
theme_factsheet <- function(base_size = 11) {
  theme_minimal(base_size = base_size) +
    theme(
      panel.grid.minor = element_blank(),
      panel.grid.major.x = element_blank(),
      panel.grid.major.y = element_line(colour = "grey90"),
      axis.title = element_text(size = base_size * 0.9),
      plot.title = element_text(face = "bold", size = base_size * 1.05),
      plot.subtitle = element_text(colour = "grey35", size = base_size * 0.85),
      legend.position = "none")
}

theme_legend_map <- function() {
  # A legend map wants no axes, no graticule, no scale bar — it is a glyph, not
  # a map you read coordinates off.
  theme_void() + theme(plot.margin = margin(0, 0, 0, 0))
}

# ── territory polygons ───────────────────────────────────────────────────────
# Ported from load_layer() in scripts/objects_region_tag.R, which already solves
# the two traps this layer carries. Kept as a copy rather than sourcing that
# script, because sourcing it runs an hour of tagging at top level.
load_eco13 <- function(path = "collection-01/data/ancillary/ecoregions13.geojson") {
  if (!file.exists(path))
    stop("no ecoregion polygons at ", path, "\n",
         "  Export ARG-Political_Level_2-13Ecorregiones_3857 from GEE as GeoJSON ",
         "(see docs/09-statistics.md §4.2) and save it there.", call. = FALSE)

  x <- st_read(path, quiet = TRUE)
  x <- x[, c("GEOCODE", "LEVEL_2")]
  names(x)[1:2] <- c("region_id", "region_name")
  x$region_id <- as.integer(x$region_id)

  # GEE's geojson export writes some features as GEOMETRYCOLLECTIONs, which
  # several sf predicates refuse outright.
  if (any(st_geometry_type(x) == "GEOMETRYCOLLECTION"))
    x <- st_cast(st_collection_extract(x, "POLYGON"), "MULTIPOLYGON")

  # ...and that cast SPLITS such a feature into one row per polygon: the Pampa
  # comes back as 2 rows, which would draw it twice and, worse, make a focal map
  # highlight only half of it. Dissolve back to one row per territory.
  if (anyDuplicated(x$region_id)) {
    keys <- unique(x[, c("region_id", "region_name"), drop = TRUE])
    geoms <- lapply(keys$region_id,
                    function(k) st_union(st_geometry(x)[x$region_id == k]))
    x <- st_sf(keys, geometry = st_sfc(do.call(c, geoms), crs = st_crs(x)))
  }
  stopifnot(!anyDuplicated(x$region_id))

  bad <- !st_is_valid(x)
  if (any(bad)) x <- st_make_valid(x)

  st_transform(x[!x$region_id %in% ECO13_DROP, ], ALBERS)
}

# ── normalisations ───────────────────────────────────────────────────────────
# Both take the tidy counts table from factsheet_object_stats.R:
#   layer, region_id, region_name, fire_year, month, n_fires, area_ha

.prep <- function(counts, layer, value) {
  lyr <- layer   # `layer` alone would resolve to the column, not the argument
  d <- as.data.table(counts)[layer == lyr & !region_id %in% ECO13_DROP]
  if (!nrow(d)) stop("no rows for layer '", layer, "'", call. = FALSE)
  if (!value %in% names(d)) stop("no column '", value, "'", call. = FALSE)
  d[, .(region_id, region_name, fire_year, month, v = get(value))]
}

# Both normalisations divide by a per-region total, so a region that never burned
# is 0/0 -> NaN, and ggplot draws it as a silent gap rather than complaining.
# Drop it here, loudly, instead.
.drop_empty <- function(d) {
  dead <- d[, .(tot = sum(v)), by = region_id][tot == 0, region_id]
  if (length(dead)) {
    msg("  [skip] %d region(s) with no burned area: %s", length(dead),
        paste(ECO13_NAMES[as.character(dead)], collapse = ", "))
    d <- d[!region_id %in% dead]
  }
  d
}

# Months summing to 100 % per region. Analysis 4.
norm_month <- function(counts, layer = "ecoregions13", value = "area_ha") {
  d <- .prep(counts, layer, value)
  d <- d[, .(v = sum(v)), by = .(region_id, region_name, month)]

  # A region with no fire in some month has NO ROW, not a zero. Left as is, the
  # line would skip the gap and draw a segment straight across it, inventing a
  # season the region does not have.
  full <- CJ(region_id = unique(d$region_id), month = FY_MONTHS, unique = TRUE)
  d <- d[full, on = .(region_id, month)]
  d[is.na(v), v := 0]
  d[, region_name := ECO13_NAMES[as.character(region_id)]]
  d <- .drop_empty(d)

  d[, pct := 100 * v / sum(v), by = region_id]
  d[, month_f := fy_month_factor(month)]
  setorder(d, region_id, month_f)
  d[]
}

# Series divided by its own mean. Analysis 2.
norm_year <- function(counts, layer = "ecoregions13", value = "area_ha") {
  d <- .prep(counts, layer, value)
  d <- d[, .(v = sum(v)), by = .(region_id, region_name, fire_year)]

  # Same gap problem as above: a fire-year with no fire must be a zero, and it
  # must be in the mean — dropping it would quietly raise every ratio.
  full <- CJ(region_id = unique(d$region_id),
             fire_year = seq(min(d$fire_year), max(d$fire_year)), unique = TRUE)
  d <- d[full, on = .(region_id, fire_year)]
  d[is.na(v), v := 0]
  d[, region_name := ECO13_NAMES[as.character(region_id)]]
  d <- .drop_empty(d)

  d[, ratio := v / mean(v), by = region_id]
  setorder(d, region_id, fire_year)
  d[]
}

# ── line plots ───────────────────────────────────────────────────────────────
# `focal` NULL draws every region in its colour; a region_id draws the rest in
# grey and the focal one on top, thick and coloured.

.line_plot <- function(d, x, y, focal, xlab, ylab, title, subtitle, hline = NA) {
  d <- copy(d)
  d[, is_focal := if (is.null(focal)) TRUE else region_id == focal]
  setorder(d, is_focal)   # focal drawn last, so it sits on top

  cols <- ECO13_COLORS[as.character(sort(unique(d$region_id)))]
  p <- ggplot(d, aes(x = .data[[x]], y = .data[[y]], group = region_id))

  if (!is.na(hline))
    p <- p + geom_hline(yintercept = hline, colour = "grey75",
                        linewidth = 0.3, linetype = "22")

  if (is.null(focal)) {
    p <- p + geom_line(aes(colour = factor(region_id)), linewidth = 0.7) +
      scale_colour_manual(values = cols)
  } else {
    p <- p +
      geom_line(data = d[is_focal == FALSE], colour = C_GREY_LINE,
                linewidth = 0.45) +
      geom_line(data = d[is_focal == TRUE],
                colour = ECO13_COLORS[as.character(focal)], linewidth = 1.3)
  }

  p + labs(x = xlab, y = ylab, title = title, subtitle = subtitle) +
    theme_factsheet()
}

plot_intraanual <- function(dm, focal = NULL, value_label = "área quemada") {
  .line_plot(
    dm, x = "month_f", y = "pct", focal = focal,
    xlab = NULL,
    ylab = sprintf("%% de la %s anual", value_label),
    title = if (is.null(focal)) "¿Cuándo se quema cada región?"
            else ECO13_NAMES[as.character(focal)],
    subtitle = "% del total histórico de cada región, por mes (mayo–abril)") +
    scale_x_discrete(labels = FY_MONTH_LABELS)
}

plot_interanual <- function(dy, focal = NULL, value_label = "área quemada") {
  .line_plot(
    dy, x = "fire_year", y = "ratio", focal = focal,
    xlab = "Año de fuego",
    ylab = sprintf("%s / media de la región", value_label),
    title = if (is.null(focal)) "¿Cómo varía año a año cada región?"
            else ECO13_NAMES[as.character(focal)],
    subtitle = "Veces el año típico de cada región",
    hline = 1)
}

# ── the map that acts as the legend ──────────────────────────────────────────
region_map <- function(eco, focal = NULL) {
  eco <- eco[order(eco$region_id), ]
  if (is.null(focal)) {
    fills <- ECO13_COLORS[as.character(eco$region_id)]
  } else {
    fills <- rep(C_GREY_FILL, nrow(eco))
    fills[eco$region_id == focal] <- ECO13_COLORS[as.character(focal)]
  }
  ggplot(eco) +
    geom_sf(fill = fills, colour = C_GREY_EDGE, linewidth = 0.15) +
    theme_legend_map()
}
