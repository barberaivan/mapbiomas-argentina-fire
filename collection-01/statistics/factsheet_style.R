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
  # Optional: análisis 5 needs the second GEE export (docs/09 §5.3). A notebook
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
       # the denominator export — the only table that carries the col-3 CLASS CODE
       # next to the three legend levels, so the crosswalk is read, never retyped
       lulc_area = rd_opt("lulc_area_eco13.csv"),
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
# TRES familias, no las cinco de la leyenda: agua, glaciar, ciudad y suelo desnudo no arden,
# así que el área quemada que cae ahí es error de mapeo (0,09 % de lo quemado en el país) y
# `factsheet_tables.R` ya la descartó. La composición suma 100 % sobre lo que puede arder.
LULC_N1 <- c("Bosques", "Vegetación natural herbácea y arbustiva",
             "Áreas de uso agropecuario")
LULC_COLORS <- setNames(c("#1F8D49", "#D6BC74", "#E0A81C"), LULC_N1)

# ── the NATIVE classes (nivel 2) ─────────────────────────────────────────────
# Nothing in this factsheet invents a land-cover class. The col-3 legend is nested
# and the network's toolkit decodes all three of ITS levels: nivel 2 is the class a
# MapBiomas user knows ("Bosque cerrado", "Herbaceas"), nivel 1 the family, nivel 0
# natural/antrópico. The figures show nivel 2 FIRST and the families after it.
#
# The order is family (LULC_N1) and, inside a family, by how much it burned
# nationally, so the stacked bar puts the big class of each family at the edge.
# The colours are OURS, not MapBiomas': the legend the toolkit ships carries names
# and no palette. Each family keeps its nivel-1 colour and its classes are shades
# of it, dark to light in that same order — so a nivel-2 bar still reads as the
# same five families from across the room.
mix_col <- function(a, b, p) {
  m <- (1 - p) * grDevices::col2rgb(a) + p * grDevices::col2rgb(b)
  grDevices::rgb(m[1], m[2], m[3], maxColorValue = 255)
}
LULC_N2_TBL <- local({
  d <- fs$lulc[ecoregion_id == 0 & nivel1 %in% LULC_N1,
               .(burned_ha = sum(burned_ha)), by = .(nivel1, nivel2)]
  d[, nivel1 := factor(nivel1, levels = LULC_N1)]
  setorder(d, nivel1, -burned_ha)
  d[]
})
LULC_N2 <- LULC_N2_TBL$nivel2
LULC_N2_COLORS <- local({
  parts <- lapply(split(LULC_N2_TBL, LULC_N2_TBL$nivel1, drop = TRUE), function(d) {
    base <- LULC_COLORS[[as.character(d$nivel1[1])]]
    n <- nrow(d)
    cols <- if (n == 1) base else
      grDevices::colorRampPalette(c(mix_col(base, "#000000", 0.30),
                                    mix_col(base, "#FFFFFF", 0.62)))(n)
    setNames(cols, d$nivel2)
  })
  do.call(c, unname(parts))
})

# The aggregation itself, READ and not retyped: `lulc_area_eco13.csv` is written by
# statistics/lulc_area_export.py through statistics/legends.py, which holds the col-3
# legend copied verbatim from the network's 00_Tools/Legends.js — the same dictionary
# the numerator was decoded with. A second, hand-typed copy here is exactly how the
# two sides would stop matching.
lulc_crosswalk <- function() {
  if (is.null(fs$lulc_area)) return(NULL)
  d <- unique(fs$lulc_area[, .(class_id, nivel0, nivel1, nivel2)])
  # Las mismas exclusiones que las figuras: si una clase no aparece en ningún gráfico,
  # listarla en el crosswalk sólo hace buscarla. `LULC_N1` ya son las tres quemables.
  d <- d[nivel1 %in% LULC_N1]
  d[, nivel1_f := factor(nivel1, levels = LULC_N1)]
  d[, n2_f := factor(nivel2, levels = LULC_N2)]
  setorder(d, nivel1_f, n2_f, class_id)
  d[, .(`código col-3` = class_id, `nivel 2 (clase nativa)` = nivel2,
        `nivel 1 (familia)` = nivel1, `nivel 0` = nivel0)]
}

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

# ── el ráster de "% de los años con fuego" ───────────────────────────────────
# El ÚNICO ráster del factsheet (statistics/burn_perc_export.py, docs/09 §5.5). Es
# `frequency_burned_v2 / 27` en porcentaje: el mismo número que la proporción quemada
# media anual del análisis 1, pero por píxel en vez de por ecorregión — por eso el mapa
# y el choropleth de al lado no pueden contradecirse.
#
# Opcional, como la tabla del análisis 5: un cuaderno renderizado antes de bajar el
# GeoTIFF se saltea la figura en vez de morir en el chunk de setup.
BURN_PERC_TIF <- file.path(STATS_DIR, "arg_burn_perc_480m_mean.tif")
HAS_BURN_PERC <- file.exists(BURN_PERC_TIF)

# Cortes de clase, no rampa continua: el grueso del país está por debajo de 1 % y una
# rampa lineal lo manda todo al primer tono (que es lo que tienta a agregar con max() y
# mentir). Las etiquetas van en % de los años; el epígrafe las traduce a "1 año de cada N".
MIN_BURNABLE_FRAC <- 0.05   # celdas con menos del 5 % quemable: vacío, no un cociente de ruido
BURN_BREAKS <- c(0, 0.2, 0.5, 1, 2, 5, 10, Inf)
BURN_LABELS <- c("< 0,2", "0,2 – 0,5", "0,5 – 1", "1 – 2", "2 – 5", "5 – 10", "> 10")
BURN_COLORS <- c("#F7F3E8", "#FBE3A2", "#F9C552", "#F09422",
                 "#DD6A10", "#B23C06", "#7F2704")

burn_perc_df <- function(res_m = 1000) {
  stopifnot(requireNamespace("terra", quietly = TRUE))
  # Banda 1 = % de los años con fuego; banda 2 = % de la celda que es quemable (la que hace
  # verificable a la 1, docs/09 §5.5). Las dos son porcentajes guardados x 100 en uint16.
  r <- terra::rast(BURN_PERC_TIF)
  frac <- if (terra::nlyr(r) >= 2) r[[2]] / 100 / 100 else NULL
  r <- r[[1]] / 100
  # A EQUAL-AREA, como todos los mapas de acá. El ráster viene en EPSG:3857 —la grilla
  # nativa de los productos v2—, donde el área de suelo de la celda cae con cos²(lat):
  # dibujado así la Patagonia ocuparía de más, y cualquier promedio sub-pesaría el norte.
  # En Albers la celda vale lo mismo en todo el país, así que el promedio simple de este
  # ráster ES el número ponderado por área (0,838 %; docs/09 §5.5).
  v <- terra::vect(ECO_SF)
  if (!is.null(frac)) {
    # Una celda que es 99 % laguna y 1 % pastizal tiene un cociente con denominador de 1 %:
    # ruidoso, y pintado igual que una celda entera de pastizal. Se dibuja como vacío.
    r <- terra::mask(r, frac >= MIN_BURNABLE_FRAC, maskvalue = FALSE)
  }
  r <- terra::project(r, ALBERS, res = res_m, method = "average")
  r <- terra::mask(terra::crop(r, v), v)
  d <- as.data.frame(r, xy = TRUE, na.rm = TRUE)
  names(d) <- c("x", "y", "pct")
  # `geom_raster` avisa "uneven horizontal intervals" por el ruido de coma flotante que
  # deja la reproyección. Las celdas SON regulares: se las devuelve a su grilla — anclando
  # en el primer centro, no en el múltiplo de `res_m` más cercano, que las correría medio
  # píxel y llegaría a fusionar dos vecinas.
  snap <- function(z) { z0 <- min(z); round((z - z0) / res_m) * res_m + z0 }
  d$x <- snap(d$x)
  d$y <- snap(d$y)
  # ggplot igual avisa "uneven horizontal intervals" al dibujar: es cosmético — verificado
  # que los espaciados son iguales y que no hay celdas repetidas. `geom_tile`, que es lo
  # que sugiere, dibujaría 2,7 M de rectángulos y haría ilegible el PDF; `geom_raster`
  # escribe una sola imagen. El cuaderno suprime warnings, así que sólo se ve en consola.
  d$clase <- cut(d$pct, BURN_BREAKS, labels = BURN_LABELS, include.lowest = TRUE)
  d
}

# `res_m` es la resolución de DIBUJO, no la del dato: el archivo son 480 m y una figura
# de Argentina impresa a 20 cm y 300 dpi no resuelve mejor que ~1,6 km, así que 1 km ya
# es más fino que el papel. Bajarlo sólo engorda la figura.
map_burn_perc <- function(res_m = 1000, outline = TRUE, legend = TRUE) {
  d <- burn_perc_df(res_m)
  p <- ggplot(d, aes(x, y)) +
    geom_raster(aes(fill = clase)) +
    scale_fill_manual(values = setNames(BURN_COLORS, BURN_LABELS), drop = FALSE,
                      name = "% de los años\ncon fuego",
                      guide = if (legend) guide_legend(reverse = TRUE) else "none")
  # Los bordes NO van en blanco: el 71 % del país cae en la clase más clara, que es un
  # crema, y una línea blanca encima de un crema no existe. Gris medio se ve sobre las dos
  # puntas de la rampa.
  if (outline)
    p <- p + geom_sf(data = ECO_SF, inherit.aes = FALSE, fill = NA,
                     colour = "grey35", linewidth = 0.18)
  p + coord_sf(datum = NA, expand = FALSE) + theme_map() +
    theme(legend.position = if (legend) "right" else "none",
          legend.key.width = grid::unit(0.8, "lines"),
          legend.text = element_text(size = rel(0.8), colour = "grey20"),
          legend.title = element_text(size = rel(0.8), colour = "grey20"))
}

# ── the map as legend ────────────────────────────────────────────────────────
# `labels = TRUE` adds the classic key — the region NAMES, in palette order
# (north -> south), next to the map. The map alone is the legend of every other
# figure; this variant is the one place the names themselves are written down, so
# a reader who does not know the ecorregiones can learn them once.
map_legend <- function(focal = NULL, labels = FALSE) {
  g <- ECO_SF
  if (is.null(focal)) {
    p <- ggplot(g) + geom_sf(aes(fill = ecoregion), colour = "white", linewidth = 0.15) +
      scale_fill_manual(
        values = REGION_COLORS, limits = REGIONS, name = NULL,
        guide = if (labels) guide_legend(ncol = 1, byrow = TRUE,
                                         keywidth = grid::unit(0.9, "lines"),
                                         keyheight = grid::unit(0.9, "lines"))
                else "none")
  } else {
    g$focal <- g$ecoregion == focal
    p <- ggplot(g) +
      geom_sf(fill = GREY_FILL, colour = "white", linewidth = 0.15) +
      geom_sf(data = g[g$focal, ], fill = REGION_COLORS[[focal]],
              colour = "white", linewidth = 0.2)
  }
  p + coord_sf(datum = NA) + theme_map() +
    theme(legend.position = if (labels && is.null(focal)) "right" else "none",
          legend.text = element_text(size = rel(0.8), colour = "grey20"),
          legend.key.spacing.y = grid::unit(1, "pt"))
}

# ── el mes pico, con paleta CÍCLICA ──────────────────────────────────────────
# Un mes no es una magnitud: diciembre y enero son vecinos, y cualquier rampa
# secuencial los pinta en las dos puntas opuestas — el error clásico de estos mapas.
# La paleta es entonces la rueda de tonos completa, 30° por mes a luminancia y croma
# constantes, así que el color vuelve sobre sí mismo igual que el calendario.
#
# El anclaje no es arbitrario: enero cae en rojo y julio en cian, de modo que en el
# hemisferio sur el color además se lee solo — cálido = pico de verano, frío = pico de
# invierno. Es la misma familia `hcl()` que la paleta de regiones, por coherencia.
MONTH_COLORS <- setNames(hcl(h = ((seq_len(12) - 1) * 30 + 20) %% 360, c = 75, l = 60),
                         MONTH_ES)

# La leyenda se ordena de mayo a abril, como el eje de meses de todo el análisis 3, y
# muestra sólo los meses que existen en el mapa. Los nombres van en tres letras: un
# número de mes obliga a traducir mentalmente, que es justo lo que un mapa no debe pedir.
map_month <- function(column = "peak_month_area", title = NULL, subtitle = NULL,
                      legend = NULL, caption = NULL) {
  d <- fs$scalars[ecoregion_id != 0, .(ecoregion, .mes = get(column))]
  g <- merge(ECO_SF, d, by = "ecoregion")
  g$mes <- factor(MONTH_ES[g$.mes], levels = MONTH_FY_LAB)
  ggplot(g) +
    geom_sf(aes(fill = mes), colour = "white", linewidth = 0.15) +
    scale_fill_manual(values = MONTH_COLORS, drop = TRUE, name = legend,
                      guide = guide_legend(ncol = 1, keywidth = grid::unit(0.9, "lines"),
                                           keyheight = grid::unit(0.9, "lines"))) +
    coord_sf(datum = NA) + theme_map() +
    labs(title = title, subtitle = subtitle, caption = caption) +
    theme(legend.position = "right",
          legend.text = element_text(size = rel(0.8), colour = "grey20"),
          legend.title = element_text(size = rel(0.8), colour = "grey20"),
          legend.key.spacing.y = grid::unit(1, "pt"))
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

# ── las tablas ───────────────────────────────────────────────────────────────
# El cuaderno no imprime `data.table`s crudas. Varias de estas tablas se citan en el
# factsheet y las lee gente que no vive en una consola, así que van como tablas HTML:
# `knitr::kable` + las clases de Bootstrap que el tema ya trae — kableExtra no está
# instalado y para esto no aporta nada.
#
# Los números salen en castellano (coma decimal, punto de miles), y eso impone UNA regla:
# ninguna columna de AÑOS entra a una de estas tablas, porque `big.mark` la escribiría
# "2.001". Si alguna vez hace falta un año en una columna, va como texto — o `es = FALSE`.
tbl <- function(d, ..., digits = getOption("digits"), es = TRUE) {
  knitr::kable(d, format = "html", digits = digits,
               format.args = if (es) list(decimal.mark = ",", big.mark = ".") else list(),
               table.attr = 'class="table table-sm table-striped table-hover"', ...)
}

fmt_ha <- function(x) formatC(x, format = "f", big.mark = ".", decimal.mark = ",", digits = 0)
fmt_mha <- function(x, d = 2) formatC(x / 1e6, format = "f", decimal.mark = ",", digits = d)
fmt_pct <- function(x, d = 2) formatC(x, format = "f", decimal.mark = ",", digits = d)
