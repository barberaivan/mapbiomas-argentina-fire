# =============================================================================
# collection-01/statistics/factsheet_style.R
#
# The conventions of docs/10 §"Convenciones para gráficos multi-región", in code,
# so every figure in notebooks/factsheet.qmd is a member of one family and not a
# plot on its own. Sourced by the notebook; it loads the tables and defines the
# palette, the theme, the map-as-legend and the two figure variants.
#
#   COLOR POR REGIÓN, ESTABLE. One colour per ecorregión, the same in every
#   figure, so a colour learned on slide 2 still means something on slide 4.
#
#   PALETA ORDENADA POR LATITUD. Thirteen categorical colours that are all
#   distinguishable do not exist. So hue carries LATITUDE — warm in the north,
#   cool in the south — at constant luminance, and a reader infers "this line is
#   northern" without going to the map. Fine identity is carried by the map, not
#   by the colour.
#
#   EL MAPA ES LA LEYENDA. `map_legend()` is a small Argentina with each polygon
#   filled in its line's colour: it says not only which colour a region is but
#   WHERE it is. Exported on its own so the designer can place it.
#
#   DOS VARIANTES. `all_regions` (every line coloured, one panel) is for seeing
#   the set and picking who to highlight; the focal variant (the rest in pale
#   grey, one region in its colour and a thick stroke) is what a slide uses.
#
# Everything here is read-only against data/statistics/ — no analysis, no GAMs.
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
  library(sf)
})

STATS_DIR <- "collection-01/data/statistics"
FIG_DIR   <- file.path(STATS_DIR, "figures")

NAT <- "Argentina"
MONTH_ES <- c("Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
# The month axis is DISPLAYED mayo -> abril so the fire season is not cut in two.
# The data behind it is calendar-year throughout (docs/09 §5).
MONTH_FY_LAB <- MONTH_ES[c(5:12, 1:4)]

# ── the tables ───────────────────────────────────────────────────────────────
fs <- local({
  rd <- function(f) fread(file.path(STATS_DIR, f), encoding = "UTF-8")
  # Optional: análisis 6 needs the second GEE export (docs/09 §5.3). A notebook
  # rendered before that export has landed should skip the section, not die in the
  # setup chunk with an unrelated-looking file-not-found.
  rd_opt <- function(f) if (file.exists(file.path(STATS_DIR, f))) rd(f) else NULL
  list(annual   = rd("factsheet_annual.csv"),
       monthly  = rd("factsheet_monthly.csv"),
       lulc     = rd("factsheet_lulc.csv"),
       trend    = rd("factsheet_trend_fits.csv"),
       pirogram = rd("factsheet_pirogram.csv"),
       season   = rd("factsheet_season_fits.csv"),
       scalars  = rd("factsheet_region_scalars.csv"),
       lulc_share = rd("factsheet_lulc_share.csv"),
       lulc_pct_mean = rd_opt("factsheet_lulc_pct_mean.csv"),
       counts   = rd("fire_counts_by_month.csv"),
       meta     = rd("ecoregions13_meta.csv"))
})

# The regions the factsheet reports, north -> south. `factsheet_tables.R` has
# already dropped the unmapped one; this is only the ORDER.
REGIONS <- fs$scalars[ecoregion_id != 0][order(palette_order), ecoregion]
N_REG   <- length(REGIONS)

# ── the palette ──────────────────────────────────────────────────────────────
# Hue 12 (rojo) -> 280 (violeta) along the latitude order, so the ramp is ordered
# and a reader infers north/south from the hue alone. Luminance and chroma
# ALTERNATE along it: neighbours in the ramp are also neighbours on the map, and
# with hue alone the mid-ramp teals (Delta, Espinal, Pampa — three adjacent
# regions) came out nearly identical. Alternating lightness separates them
# without disturbing the north-to-south reading.
REGION_COLORS <- local({
  i <- seq_len(N_REG)
  setNames(hcl(h = seq(12, 280, length.out = N_REG),
               c = ifelse(i %% 2, 78, 55),
               l = ifelse(i %% 2, 45, 62)), REGIONS)
})
REGION_COLORS[NAT] <- "#1A1A1A"

# The MapBiomas nivel-1 families, in the platform's own colour language so a reader
# who has seen a land-cover map recognises the bars: green = bosque, tan = herbácea
# y arbustiva, amber = agropecuario. Order is the stacking order.
LULC_N1 <- c("Bosques", "Vegetación natural herbácea y arbustiva",
             "Áreas de uso agropecuario", "Áreas sin vegetación", "Cuerpos de agua")
LULC_COLORS <- setNames(c("#1F8D49", "#D6BC74", "#E0A81C", "#B85B3C", "#2532E4"), LULC_N1)

GREY_LINE <- "grey82"     # the non-focal regions
GREY_FILL <- "grey90"     # the non-focal polygons on a focal map
ACCENT    <- "#B2182B"

scale_region <- function(...) scale_colour_manual(
  values = REGION_COLORS, limits = REGIONS, name = NULL, ...)

# ── the theme ────────────────────────────────────────────────────────────────
theme_fs <- function(base_size = 12) {
  theme_minimal(base_size = base_size) +
    theme(panel.grid.minor = element_blank(),
          panel.grid.major.x = element_blank(),
          panel.grid.major.y = element_line(colour = "grey92", linewidth = 0.3),
          axis.line.x = element_line(colour = "grey40", linewidth = 0.3),
          axis.ticks.x = element_line(colour = "grey40", linewidth = 0.3),
          plot.title = element_text(face = "bold", size = rel(1.05)),
          plot.subtitle = element_text(colour = "grey35", size = rel(0.9)),
          plot.caption = element_text(colour = "grey45", size = rel(0.75), hjust = 0),
          legend.position = "none",
          plot.title.position = "plot",
          plot.caption.position = "plot")
}
theme_map <- function(base_size = 12) {
  theme_void(base_size = base_size) +
    # theme_void centres every title; the rest of the family is left-aligned, and
    # a map whose title sits in a different place reads as a different figure.
    theme(plot.title = element_text(face = "bold", size = rel(1.05), hjust = 0),
          plot.subtitle = element_text(colour = "grey35", size = rel(0.9), hjust = 0),
          plot.caption = element_text(colour = "grey45", size = rel(0.75), hjust = 0),
          legend.position = "right",
          plot.title.position = "plot",
          plot.caption.position = "plot")
}

# ggplot does not wrap a caption, it just runs it off the canvas — silently, so a
# clipped sentence looks like a design choice. Wrap to the figure's own width.
cap <- function(..., width = 95) paste(strwrap(paste0(...), width), collapse = "\n")
theme_set(theme_fs())

# ── the geometry ─────────────────────────────────────────────────────────────
# Equal-area for South America: an Argentina drawn in raw lon/lat is visibly
# stretched east-west in the north and squashed in the south.
ALBERS <- paste0("+proj=aea +lat_1=-5 +lat_2=-42 +lat_0=-32 +lon_0=-60 ",
                 "+x_0=0 +y_0=0 +ellps=aust_SA +units=m +no_defs")
ECO_SF <- local({
  g <- st_read(file.path(STATS_DIR, "ecoregions13_simple.gpkg"), quiet = TRUE)
  g <- g[g$ecoregion %in% REGIONS, ]
  g$ecoregion <- factor(g$ecoregion, levels = REGIONS)
  st_transform(g, ALBERS)
})

# ── the map as legend ────────────────────────────────────────────────────────
map_legend <- function(focal = NULL) {
  g <- ECO_SF
  if (is.null(focal)) {
    p <- ggplot(g) + geom_sf(aes(fill = ecoregion), colour = "white", linewidth = 0.15) +
      scale_fill_manual(values = REGION_COLORS, limits = REGIONS, guide = "none")
  } else {
    g$focal <- g$ecoregion == focal
    p <- ggplot(g) +
      geom_sf(fill = GREY_FILL, colour = "white", linewidth = 0.15) +
      geom_sf(data = g[g$focal, ], fill = REGION_COLORS[[focal]],
              colour = "white", linewidth = 0.2)
  }
  p + coord_sf(datum = NA) + theme_map()
}

# ── a choropleth of any per-region scalar ────────────────────────────────────
# `midpoint` switches it to a diverging scale, for a quantity with a meaningful
# neutral value — a trend ratio, where 1 means "no change" and the two sides mean
# opposite things. A sequential ramp there would read as a magnitude and hide the
# sign, which is the whole message.
map_scalar <- function(column, title = NULL, subtitle = NULL, legend = NULL,
                       palette = "YlOrRd", direction = 1, labels = waiver(),
                       trans = "identity", midpoint = NULL,
                       low = "#2166AC", high = "#B2182B") {
  d <- fs$scalars[ecoregion_id != 0, .(ecoregion, value = get(column))]
  g <- merge(ECO_SF, d, by = "ecoregion")
  sc <- if (is.null(midpoint))
    scale_fill_distiller(palette = palette, direction = direction, name = legend,
                         labels = labels, trans = trans)
  else
    scale_fill_gradient2(low = low, mid = "grey93", high = high,
                         midpoint = midpoint, name = legend, labels = labels,
                         trans = trans)
  ggplot(g) +
    geom_sf(aes(fill = value), colour = "white", linewidth = 0.2) + sc +
    coord_sf(datum = NA) + theme_map() +
    labs(title = title, subtitle = subtitle)
}

# ── the two variants of a multi-region line figure ───────────────────────────
# `draw` takes a data.table and a colour/linewidth spec and returns the layers;
# the two wrappers below only decide WHICH rows are grey and which are coloured.
lines_all <- function(d, x, y, national = TRUE) {
  reg <- d[ecoregion %in% REGIONS]
  p <- ggplot(reg, aes(.data[[x]], .data[[y]], colour = ecoregion, group = ecoregion)) +
    geom_line(linewidth = 0.7) + scale_region()
  if (national && NAT %in% d$ecoregion)
    p <- p + geom_line(data = d[ecoregion == NAT], colour = REGION_COLORS[[NAT]],
                       linewidth = 1.1, linetype = "22")
  p
}

lines_focal <- function(d, x, y, focal) {
  reg <- d[ecoregion %in% REGIONS]
  ggplot(mapping = aes(.data[[x]], .data[[y]], group = ecoregion)) +
    geom_line(data = reg[ecoregion != focal], colour = GREY_LINE, linewidth = 0.5) +
    geom_line(data = reg[ecoregion == focal], colour = REGION_COLORS[[focal]],
              linewidth = 1.4)
}

# ── saving ───────────────────────────────────────────────────────────────────
# PNG for the PowerPoint draft, PDF (vector) for the graphic designer. cairo_pdf
# rather than the default pdf device: the titles carry acentos and ñ, which the
# base device drops silently in some font configurations.
save_fig <- function(p, name, w = 7, h = 4.6, write = TRUE) {
  if (isTRUE(write)) {
    dir.create(FIG_DIR, showWarnings = FALSE, recursive = TRUE)
    ggsave(file.path(FIG_DIR, paste0(name, ".png")), p, width = w, height = h,
           dpi = 300, bg = "white")
    ggsave(file.path(FIG_DIR, paste0(name, ".pdf")), p, width = w, height = h,
           device = cairo_pdf, bg = "white")
  }
  invisible(p)
}

# A filename-safe token for a region name: "Delta e Islas del Paraná" -> "delta_e_islas_del_parana".
slug <- function(x) {
  x <- iconv(x, to = "ASCII//TRANSLIT")
  gsub("_+", "_", gsub("[^a-z0-9]+", "_", tolower(x)))
}

fmt_ha <- function(x) formatC(x, format = "f", big.mark = ".", decimal.mark = ",", digits = 0)
fmt_mha <- function(x, d = 2) formatC(x / 1e6, format = "f", decimal.mark = ",", digits = d)
fmt_pct <- function(x, d = 2) formatC(x, format = "f", decimal.mark = ",", digits = d)
