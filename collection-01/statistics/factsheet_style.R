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
       # análisis 6 (docs/10 §6): las tres tablas del cambio de cobertura. Opcionales
       # por la misma razón — dependen de la tercera exportación (docs/09 §5.7).
       change        = rd_opt("factsheet_change.csv"),
       change_annual = rd_opt("factsheet_change_annual.csv"),
       change_sum    = rd_opt("factsheet_change_summary.csv"),
       change_q      = rd_opt("factsheet_change_q.csv"),
       # sólo bosques, nacional, las cuatro ventanas (docs/09 §5.9)
       bosques       = rd_opt("factsheet_bosques.csv"),
       bosques_dest  = rd_opt("factsheet_bosques_destinos.csv"),
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
ECO_SF_ALL <- local({
  g <- st_read(file.path(STATS_DIR, "ecoregions13_simple.gpkg"), quiet = TRUE)
  st_transform(g, ALBERS)
})

# Las 12 REPORTADAS: es la geometría de los DATOS — a ella se le unen los escalares y con
# ella se recortan los rásters.
ECO_SF <- local({
  g <- ECO_SF_ALL[ECO_SF_ALL$ecoregion %in% REGIONS, ]
  g$ecoregion <- factor(g$ecoregion, levels = REGIONS)
  g
})

# ── las Malvinas: territorio SIEMPRE, dato NUNCA ─────────────────────────────
# Todo mapa de la Argentina de este factsheet dibuja las Islas Malvinas. Van SIN PINTAR —
# contorno y nada más— y eso no es una omisión: es exactamente lo que dicen los datos.
# La ecorregión 13 (Islas del Atlántico Sur) está fuera de la grilla de procesamiento —
# ninguna de las 248 cartas la toca—, así que su "0 % quemado" sería un agujero del mapeo
# presentado como un hecho sobre el fuego, y por eso no entra en NINGUNA tabla ni en el
# denominador nacional (docs/09 §3.2). Dibujarla vacía dice las dos cosas a la vez: el
# territorio está, el dato no.
#
# Verificado sobre la capa (17 sep 2026): la ecorregión 13 de este asset es SÓLO las
# Malvinas — bbox -61,46/-52,95 a -57,72/-51,00, 451 partes, las dos mayores Soledad
# (6.410 km2) y Gran Malvina (4.402 km2). No trae Georgias ni Sandwich del Sur, que a
# -36 de longitud habrían estirado el lienzo de todos los mapas por un archipiélago que
# no se vería.
MALVINAS_SF <- ECO_SF_ALL[ECO_SF_ALL$ecoregion_id == 13L, ]

# La capa, una sola vez: se agrega a TODOS los mapas (`map_classes`, `map_last_fire`,
# `map_legend`, `map_scalar`, `map_month`). `colour` se pasa para que el contorno sea el
# mismo que el del mapa que la recibe — blanco sobre los coropletas, gris sobre los rásters.
#
# ⚠️ Va SIEMPRE dentro del `ggplot`, nunca después de `coord_sf`: al ser una capa más, es lo
# que extiende el lienzo hacia el este. Si se la agrega fuera, el mapa se dibuja con el bbox
# continental y las islas quedan recortadas — que es el modo de fallar que no se ve, porque
# el resto del mapa sigue estando bien.
# ⚠️ LA LÍNEA VA MÁS FINA QUE LA DEL CONTINENTE, y es una decisión de dibujo, no un descuido.
# El archipiélago son 451 partes en ~250 km: a la linewidth del continente (0,18-0,25) los
# islotes se tocan entre sí y el conjunto se imprime como una mancha gris en vez de como un
# contorno. A 0,1 se lee la silueta de Soledad y Gran Malvina, que es lo que hay que ver.
# No se descarta ningún islote: el problema es el grosor del trazo, no la geometría, y
# recortar territorio para que dibuje mejor sería la solución equivocada a este problema.
geom_malvinas <- function(colour = "grey35", linewidth = 0.1)
  geom_sf(data = MALVINAS_SF, inherit.aes = FALSE, fill = NA,
          colour = colour, linewidth = linewidth)

# ── los tres rásters del factsheet ───────────────────────────────────────────
# Todo lo demás del paso 09 son tablas; esto son imágenes, y son TRES archivos que salen de
# dos scripts (docs/09 §5.5 y §5.6):
#
#   arg_burn_perc_480m_mean.tif   banda 1 = % de los años con fuego (el promedio de la celda)
#                                 banda 2 = % de la celda que es QUEMABLE
#   arg_burn_perc_480m_max.tif    lo mismo con el reductor `max`: el píxel que MÁS ardió de
#                                 cada celda, que es el único que da conteos ENTEROS
#   arg_last_fire_480m_mean.tif   banda 1 = año medio del último fuego, (año-1998) x 100
#                                 banda 2 = % de lo quemable de la celda que ardió alguna vez
#
# Los tres son opcionales, como la tabla del análisis 5: un cuaderno renderizado antes de
# bajar un GeoTIFF se saltea esa figura en vez de morir en el chunk de setup.
#
# ⚠️ LOS DOS PRIMEROS ESTÁN EN EPSG:3857 Y EL TERCERO EN 4326 (docs/09 §5.6): los nueve
# subproductos v2 no comparten retícula, y cada ráster se agregó sobre la de SU asset para no
# remuestrear.  Acá da igual —los tres se reproyectan a Albers para dibujar— pero significa
# que no se pueden cruzar celda a celda; el cruce está hecho, sobre números nacionales, en
# `last_fire_export.py --check`.
RASTER_TIF <- c(perc = "arg_burn_perc_480m_mean.tif",
                max  = "arg_burn_perc_480m_max.tif",
                year = "arg_last_fire_480m_mean.tif")
raster_path <- function(which) file.path(STATS_DIR, RASTER_TIF[[which]])
has_raster  <- function(which) file.exists(raster_path(which))
HAS_BURN_PERC <- has_raster("perc")      # el nombre viejo, que el cuaderno ya usa en `eval:`
HAS_BURN_MAX  <- has_raster("max")
HAS_LAST_FIRE <- has_raster("year")

N_YEARS_SERIES <- 27                     # 1999-2025: lo que convierte "% de los años" en veces
NODATA <- 65535                          # el relleno explícito de los tres (uint16)
MIN_BURNABLE_FRAC <- 0.05                # celdas con menos del 5 % quemable: vacío, no un
                                         # cociente de ruido

# `res_m` es la resolución de DIBUJO, no la del dato: el archivo son 480 m y una figura de
# Argentina impresa a 20 cm y 300 dpi no resuelve mejor que ~1,6 km, así que 1 km ya es más
# fino que el papel.  Bajarlo sólo engorda la figura.
#
# ⚠️ El promedio del reproyectado MEZCLA ceros con no-ceros, así que "blanco" en la figura es
# "no hubo fuego en ~1 km a la redonda", no "no hubo fuego en estos 480 m".  Es la lectura
# correcta para un mapa nacional y la única que no llena el país de motas de un píxel.
raster_df <- function(which, res_m = 1000, decode = function(v) v / 100,
                      min_denom = MIN_BURNABLE_FRAC, method = "average") {
  stopifnot(requireNamespace("terra", quietly = TRUE))
  r <- terra::rast(raster_path(which))
  # El nodata viaja en el COG, pero un archivo reescrito podría perderlo: se lo vuelve a
  # aplicar a mano.  65535 leído como dato son 655 % o el año 2653, que no se ve como error
  # en un `cut()` — se ve como la última clase.
  r <- terra::classify(r, cbind(NODATA, NA))
  denom <- if (terra::nlyr(r) >= 2) r[[2]] / 100 / 100 else NULL   # banda 2: % x100 -> fracción
  v <- decode(r[[1]])
  if (!is.null(denom) && min_denom > 0) {
    # Una celda que es 99 % laguna y 1 % pastizal tiene un cociente con denominador de 1 %:
    # ruidoso, y pintado igual que una celda entera de pastizal.  Se dibuja como vacío.
    v <- terra::mask(v, denom >= min_denom, maskvalue = FALSE)
  }
  # A EQUAL-AREA, como todos los mapas de acá.  Los archivos vienen en 3857 o en 4326, donde
  # el área de suelo de la celda cae con la latitud: dibujados así la Patagonia ocuparía de
  # más.  En Albers la celda vale lo mismo en todo el país.
  poly <- terra::vect(ECO_SF)
  v <- terra::project(v, ALBERS, res = res_m, method = method)
  v <- terra::mask(terra::crop(v, poly), poly)
  d <- as.data.frame(v, xy = TRUE, na.rm = TRUE)
  names(d) <- c("x", "y", "value")
  # `geom_raster` avisa "uneven horizontal intervals" por el ruido de coma flotante que deja
  # la reproyección.  Las celdas SON regulares: se las devuelve a su grilla — anclando en el
  # primer centro, no en el múltiplo de `res_m` más cercano, que las correría medio píxel y
  # llegaría a fusionar dos vecinas.  (El aviso igual aparece al dibujar: es cosmético.
  # `geom_tile`, que es lo que sugiere, dibujaría millones de rectángulos y haría ilegible el
  # PDF; `geom_raster` escribe una sola imagen.)
  snap <- function(z) { z0 <- min(z); round((z - z0) / res_m) * res_m + z0 }
  d$x <- snap(d$x); d$y <- snap(d$y)
  d
}

# ── el cero es BLANCO, y es una clase aparte ─────────────────────────────────
# En los tres mapas, "no se quemó nunca" no es el primer tono de la rampa: es blanco.  Son
# dos cosas distintas —"acá no hubo fuego" y "acá hubo poco fuego"— y una rampa continua las
# pega.  El 71 % del país cae en la clase más baja del mapa de frecuencia, así que la
# diferencia entre esas dos lecturas ES el mapa.
#
# (Las celdas sin NADA quemable —lagos, salares, glaciares— tampoco son 0: están fuera de la
# máscara y quedan sin dibujar, que es otra cosa más y por eso el epígrafe la nombra.)
ZERO_LABEL  <- "0"
ZERO_COLOUR <- "#FFFFFF"

# Cortes de clase, no rampa continua: el grueso del país está por debajo de 1 % y una rampa
# lineal lo manda todo al primer tono (que es lo que tienta a agregar con max() y mentir).
BURN_BREAKS <- c(0, 0.2, 0.5, 1, 2, 5, 10, Inf)
BURN_LABELS <- c("< 0,2", "0,2 – 0,5", "0,5 – 1", "1 – 2", "2 – 5", "5 – 10", "> 10")

# Las etiquetas del mismo dato en VECES (docs/10 §0.2): % de los años x 27 / 100.  Es una
# reescala de los mismos cortes, no otro mapa — así las dos figuras son comparables tono a
# tono y la única diferencia es qué dice la leyenda.
count_lab <- function(x) formatC(x, format = "f", digits = 2, decimal.mark = ",")
COUNT_LABELS <- local({
  b <- BURN_BREAKS * N_YEARS_SERIES / 100
  lab <- paste(count_lab(head(b, -1)), "–", count_lab(b[-1]))
  lab[1] <- paste("<", count_lab(b[2])); lab[length(lab)] <- paste(">", count_lab(b[length(b) - 1]))
  lab
})
# La otra versión, la del reductor `max`: ahí el valor de la celda SÍ es un entero (el número
# de veces que ardió el píxel que más ardió), y la escala puede empezar en 1.
#
# ⚠️ Los enteros sólo sobreviven si el dibujo NO promedia. Medido: reproyectando a 1 km con
# `average`, la mediana de las celdas con fuego cae en 0,85 — la mitad del mapa quedaría por
# DEBAJO de 1, en una escala que dice empezar en 1. Por eso este mapa se dibuja a su
# resolución nativa y con el vecino más cercano (`map_burn_count(stat = "max")`).
COUNT_MAX_BREAKS <- c(1, 2, 3, 4, 5, 7, 10, Inf)
COUNT_MAX_LABELS <- c("1", "2", "3", "4", "5 – 6", "7 – 9", "≥ 10")

# viridis magma, INVERTIDA: el valor alto es el tono oscuro.  Sobre papel blanco lo oscuro es
# lo que salta, y "más fuego" tiene que saltar; de paso lo quemado queda negro, que es lo que
# es.  Se recorta el extremo claro (end = 0,92) para que la primera clase sea un naranja
# claro —no un amarillo pálido— y el salto 0 -> primera clase se vea sin buscarlo.
BURN_COLORS <- viridisLite::magma(length(BURN_LABELS), begin = 0.05, end = 0.84,
                                  direction = -1)

# El año del último fuego va en viridis C (plasma), que NO es la misma familia que la
# frecuencia: son dos variables distintas y compartir paleta las haría parecer la misma.
# También invertida — lo reciente, oscuro — y recortada en las dos puntas: el amarillo puro
# de plasma desaparece sobre blanco.
# Períodos REGULARES de cuatro años (el último son tres, porque la serie termina en 2025) y
# no cortes por cuantiles.  Medido sobre el ráster: el año del último fuego se reparte casi
# uniforme entre 1999 y 2025 (cuartiles 2004,8 / 2011,4 / 2018,0), así que un ancho constante
# ya da clases parejas Y la leyenda se lee sin traducir — "2011 – 2014" es un período, un
# corte por cuantiles habría dado "2009,4 – 2013,7", que en un mapa no significa nada.
YEAR_BREAKS <- c(1999, 2003, 2007, 2011, 2015, 2019, 2023, 2026)
YEAR_LABELS <- c("1999 – 2002", "2003 – 2006", "2007 – 2010", "2011 – 2014",
                 "2015 – 2018", "2019 – 2022", "2023 – 2025")
YEAR_COLORS <- viridisLite::plasma(length(YEAR_LABELS), begin = 0.05, end = 0.92,
                                   direction = -1)

# `right = FALSE` para los años ([1999, 2004) es "el promedio cae en los primeros cinco") y
# `right = TRUE` para los porcentajes, que es como se leen los cortes de una rampa.  El cero
# no lo decide `cut`: se lo saca antes, porque `include.lowest` lo metería en la primera clase
# — que es exactamente el error que esta función existe para no cometer.
class_of <- function(v, breaks, labels, right = TRUE, zero = ZERO_LABEL) {
  k <- as.character(cut(v, breaks, labels = labels, right = right, include.lowest = FALSE))
  factor(ifelse(!is.na(v) & v <= 0, zero, k), levels = c(zero, labels))
}

map_classes <- function(d, colors, labels, legend, zero = ZERO_LABEL, outline = TRUE,
                        show_legend = TRUE) {
  p <- ggplot(d, aes(x, y)) +
    geom_raster(aes(fill = clase)) +
    scale_fill_manual(values = setNames(c(ZERO_COLOUR, colors), c(zero, labels)),
                      drop = FALSE, name = legend,
                      guide = if (show_legend) guide_legend(reverse = TRUE) else "none")
  # Los bordes NO van en blanco: con el cero en blanco, una línea blanca sobre el fondo del
  # país no existe.  Gris medio se ve sobre las dos puntas de la rampa y sobre el blanco.
  if (outline)
    p <- p + geom_sf(data = ECO_SF, inherit.aes = FALSE, fill = NA,
                     colour = "grey35", linewidth = 0.18)
  p <- p + geom_malvinas()          # territorio siempre, dato nunca (arriba)
  p + coord_sf(datum = NA, expand = FALSE) + theme_map() +
    theme(legend.position = if (show_legend) "right" else "none",
          legend.key.width = grid::unit(0.8, "lines"),
          legend.text = element_text(size = rel(0.8), colour = "grey20"),
          legend.title = element_text(size = rel(0.8), colour = "grey20"))
}

# ── los tres mapas ───────────────────────────────────────────────────────────
map_burn_perc <- function(res_m = 1000, outline = TRUE, legend = TRUE) {
  d <- raster_df("perc", res_m)
  d$clase <- class_of(d$value, BURN_BREAKS, BURN_LABELS)
  map_classes(d, BURN_COLORS, BURN_LABELS, "% de los años\ncon fuego",
              outline = outline, show_legend = legend)
}

# El MISMO dato en veces (`stat = "mean"`, la celda promedio) o el máximo de la celda
# (`stat = "max"`, el único que da enteros).  Ver docs/10 §0.2 para cuál dice qué.
map_burn_count <- function(res_m = 1000, stat = c("mean", "max"), outline = TRUE,
                           legend = TRUE) {
  stat <- match.arg(stat)
  if (stat == "mean") {
    d <- raster_df("perc", res_m, decode = function(v) v / 100 * N_YEARS_SERIES / 100)
    d$clase <- class_of(d$value, BURN_BREAKS * N_YEARS_SERIES / 100, COUNT_LABELS)
    map_classes(d, BURN_COLORS, COUNT_LABELS, "veces que ardió\n(promedio de la celda)",
                outline = outline, show_legend = legend)
  } else {
    # 480 m y `near`, no 1 km y `average`: ver COUNT_MAX_BREAKS. Cuesta ~4x más celdas que
    # los otros mapas (y `geom_raster` igual escribe UNA imagen, así que el PDF no crece).
    d <- raster_df("max", if (missing(res_m)) 480 else res_m, method = "near",
                   decode = function(v) v / 100 * N_YEARS_SERIES / 100)
    d$value <- round(d$value)          # el x100 y el redondeo del uint16 dejan 0,99999
    d$clase <- class_of(d$value, COUNT_MAX_BREAKS, COUNT_MAX_LABELS, right = FALSE)
    map_classes(d, BURN_COLORS, COUNT_MAX_LABELS, "veces que ardió\n(el píxel que más)",
                outline = outline, show_legend = legend)
  }
}

# El año del último fuego (docs/10 §2.1).  `min_denom` es el de la banda 2 de ESTE archivo, que no es la
# fracción quemable sino la fracción QUEMADA: 0 dibuja todo lo que ardió alguna vez, y
# subirlo esconde las celdas donde ardieron dos píxeles.  Por defecto no se esconde nada — el
# color acá codifica una FECHA, no una magnitud, así que una celda que ardió poco no miente
# sobre cuánto, sólo sobre cuándo, y eso ya lo dice el mapa de frecuencia de al lado.
map_last_fire <- function(res_m = 1000, outline = TRUE, legend = TRUE, min_denom = 0) {
  d <- raster_df("year", res_m, decode = function(v) v / 100 + 1998, min_denom = min_denom)
  # Acá no hay clase "0": lo que nunca ardió no tiene año, está enmascarado y no llega.
  d$clase <- factor(as.character(cut(d$value, YEAR_BREAKS, labels = YEAR_LABELS,
                                     right = FALSE, include.lowest = TRUE)),
                    levels = YEAR_LABELS)
  p <- ggplot(d, aes(x, y)) +
    geom_raster(aes(fill = clase)) +
    scale_fill_manual(values = setNames(YEAR_COLORS, YEAR_LABELS), drop = FALSE,
                      name = "año del\núltimo fuego",
                      guide = if (legend) guide_legend(reverse = TRUE) else "none")
  if (outline)
    p <- p + geom_sf(data = ECO_SF, inherit.aes = FALSE, fill = NA,
                     colour = "grey35", linewidth = 0.18)
  p <- p + geom_malvinas()
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
      geom_malvinas(colour = "grey45") +
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
      geom_malvinas(colour = "grey45") +
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
    geom_malvinas(colour = "grey45") +
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
# `data` existe para el análisis 6, que tiene DOS escalares por región (uno por nivel de
# leyenda) y por lo tanto no cabe como columna de `fs$scalars`: se le pasa la tabla ya
# filtrada. Por defecto sigue siendo la de siempre, así que ninguna llamada existente cambia.
map_scalar <- function(column, title = NULL, subtitle = NULL, legend = NULL,
                       palette = "YlOrRd", direction = 1, labels = waiver(),
                       trans = "identity", midpoint = NULL,
                       low = "#2166AC", high = "#B2182B", data = fs$scalars) {
  d <- as.data.table(data)[ecoregion_id != 0, .(ecoregion, value = get(column))]
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
    geom_malvinas(colour = "grey45") +
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


# ── análisis 6: el cambio de cobertura alrededor del fuego ───────────────────
# Tres vistas de la misma tabla (`factsheet_change.csv`), y el orden importa porque cada una
# es el zoom de la anterior (docs/10 §6):
#
#   (a) de todo lo que ardió, ¿qué proporción figura con OTRA cobertura un año después?
#   (b1) de lo que NO cambió, ¿cómo se reparte entre clases?  (suma 100 %)
#   (b2) de lo que SÍ cambió, ¿de qué clase a qué clase?      (suma 100 %) — el Sankey
#
# LO QUE NO DICEN, y que va en el epígrafe y no en una nota al pie: esto NO es "el fuego
# transformó X hectáreas".  La col-3 puede estar reaccionando a la cicatriz misma, un año es
# poco para la recuperación, y un píxel pudo cambiar por desmonte sin relación con el fuego.
# Es una descripción de qué coberturas se suceden alrededor del fuego (docs/09 §5.7).
HAS_CHANGE  <- !is.null(fs$change)
HAS_BOSQUES <- !is.null(fs$bosques)

# La paleta: las tres familias quemables son las de siempre —una figura del análisis 6 tiene
# que poder leerse con los colores aprendidos en el 4—; las clases que sólo aparecen del lado
# "después" (agua, suelo desnudo, ciudad, no observado) se agregan acá, en grises y azules
# que no compiten con las tres.
CHANGE_EXTRA_N1 <- c("Cuerpos de agua"      = "#4C7FBF",
                     "Áreas sin vegetación" = "#9C9C9C",
                     "No observado"         = "#DCDCDC")
CHANGE_EXTRA_N2 <- c("Cuerpos de agua"                       = "#4C7FBF",
                     "Ríos, lagunas, lagos y océano"         = "#2E5E9E",
                     "Áreas sin vegetación"                  = "#9C9C9C",
                     "Otras áreas no vegetadas"              = "#B0A99F",
                     "Áreas urbanas"                         = "#6E6E6E",
                     "Glaciares descubiertos y nieve perenne" = "#CFE8F3",
                     "No observado"                          = "#DCDCDC")

# El ORDEN de las clases es el mismo del análisis 4 (familia, y dentro de la familia por área
# quemada nacional), con las clases sólo-destino al final. Un orden distinto entre dos
# figuras de la misma leyenda es lo que hace que el lector las lea como dos leyendas.
change_levels <- function(level) {
  base <- if (level == "nivel1") LULC_N1 else LULC_N2
  extra <- names(if (level == "nivel1") CHANGE_EXTRA_N1 else CHANGE_EXTRA_N2)
  c(base, setdiff(extra, base))
}
change_colors <- function(level) {
  base <- if (level == "nivel1") LULC_COLORS else LULC_N2_COLORS
  extra <- if (level == "nivel1") CHANGE_EXTRA_N1 else CHANGE_EXTRA_N2
  c(base, extra[setdiff(names(extra), names(base))])
}

# Las filas de un ámbito y un nivel, sumadas sobre los 26 años (la tabla es anual; las figuras
# suman — docs/09 §5.7).  `scope` es el nombre de la ecorregión, o NAT para el país.
# El argumento se llama `lv` y no `level` A PROPÓSITO: `level` es también una COLUMNA de la
# tabla, y el optimizador de `data.table` no encuentra `..level` cuando el nombre coincide
# ("object '..level' not found").  Un nombre distinto es la solución, no un `get()`.
change_rows <- function(scope = NAT, lv = "nivel1", off = 1L) {
  d <- fs$change[ecoregion == scope & level == lv & offset == off,
                 .(burned_ha = sum(burned_ha)), by = .(clase_prev, clase_post, cambio)]
  lvls <- change_levels(lv)
  d[, `:=`(clase_prev = factor(clase_prev, levels = lvls),
           clase_post = factor(clase_post, levels = lvls))]
  d[]
}

# (a) el escalar, como barras — una por región, la nacional aparte, igual que fig01-barras.
bars_changed <- function(lv = "nivel1", off = 1L) {
  d <- fs$change_sum[ecoregion %in% REGIONS & level == lv & offset == off &
                     state == "burned_any"][order(changed_pct)]
  d[, ecoregion := factor(ecoregion, levels = ecoregion)]
  nat <- fs$change_sum[ecoregion == NAT & level == lv & offset == off &
                       state == "burned_any", changed_pct]
  ggplot(d, aes(changed_pct, ecoregion, fill = ecoregion)) +
    geom_col(width = 0.72) +
    geom_vline(xintercept = nat, linetype = "22", colour = REGION_COLORS[[NAT]],
               linewidth = 0.5) +
    geom_text(aes(label = fmt_pct(changed_pct, 1)), hjust = -0.18, size = 3.1,
              colour = "grey30") +
    scale_fill_manual(values = REGION_COLORS, guide = "none") +
    scale_x_continuous(expand = expansion(mult = c(0, 0.12))) +
    labs(x = "% de lo quemado que figura con otra cobertura al año siguiente", y = NULL)
}

# (b1) la repartija de lo que NO cambió.  Una barra apilada horizontal —no un torta— porque
# es la misma forma que usa el análisis 4 y se puede poner una al lado de la otra.
bar_unchanged <- function(scope = NAT, lv = "nivel1", off = 1L) {
  d <- change_rows(scope, lv, off)[cambio == FALSE]
  d[, share := 100 * burned_ha / sum(burned_ha)]
  setorder(d, clase_prev)
  ggplot(d, aes(share, "x", fill = clase_prev)) +
    geom_col(width = 0.6) +
    geom_text(aes(label = ifelse(share >= 6, fmt_pct(share, 0), "")),
              position = position_stack(vjust = 0.5), size = 3.1, colour = "white") +
    scale_fill_manual(values = change_colors(lv), limits = change_levels(lv),
                      drop = TRUE, name = NULL) +
    scale_x_continuous(expand = c(0, 0), limits = c(0, 100)) +
    labs(x = "% de lo quemado que NO cambió de cobertura", y = NULL) +
    theme(axis.text.y = element_blank(), axis.ticks.y = element_blank(),
          legend.position = "bottom",
          legend.text = element_text(size = rel(if (lv == "nivel1") 0.85 else 0.7))) +
    # Nivel 2 son 20+ clases: en filas, la leyenda se sale del lienzo y las etiquetas se
    # cortan. En 3 columnas entra, a costa de alto — de ahí el `h` distinto al guardar.
    guides(fill = if (lv == "nivel1") guide_legend(nrow = 1, byrow = TRUE)
                  else guide_legend(ncol = 3, byrow = TRUE))
}

# (b2) el Sankey (diagrama aluvial): de qué clase a qué clase va lo que SÍ cambió.
#
# `min_share` tira las transiciones por debajo de ese % del total dibujado.  No se las
# junta en una categoría "otras": una clase inventada en el eje de una leyenda nested es peor
# que una ausencia, y lo que se pierde se dice en el epígrafe — la función devuelve la
# cobertura dibujada en `attr(p, "cobertura")`.
#
# ⚠️ EL UMBRAL ES POR TRANSICIÓN, Y ESO SESGA LA LECTURA POR DESTINO.  Una clase de llegada
# alimentada por MUCHOS flujos chicos se dibuja mucho más flaca de lo que es, mientras que una
# alimentada por uno grande se dibuja entera.  Medido, nacional, Y+1, hacia bosque: en nivel 1
# son 0,891 Mha en DOS bandas y se dibuja el 100 %; las MISMAS 0,891 Mha en nivel 2 se reparten
# entre 37 transiciones y con umbral 1,5 % sobrevive UNA (0,355 Mha, el 24 %).  De ahí la
# impresión —falsa— de que en nivel 2 llega menos bosque que en nivel 1.  Por eso el nivel 2
# quiere umbrales bajos, y por eso el subtítulo SIEMPRE imprime la cobertura.
#
# `keep_unchanged = TRUE` agrega la DIAGONAL (lo que permaneció en su clase).  Cambia la
# pregunta y por lo tanto el denominador: el total pasa a ser todo lo quemado, no sólo lo que
# cambió, y `min_share` se mide contra ése.  Sale una figura dominada por las bandas
# horizontales —que es el hecho: la mayor parte de lo que arde sigue siendo lo que era—, con el
# cambio como la cinta fina.  Es la versión honesta y la que NO se puede leer para comparar
# transiciones entre sí.
wrap_lab <- function(x, w = 16)
  vapply(as.character(x), function(z) paste(strwrap(z, w), collapse = "\n"), "")

sankey_change <- function(scope = NAT, lv = "nivel1", min_share = 1, off = 1L,
                          keep_unchanged = FALSE) {
  stopifnot(requireNamespace("ggalluvial", quietly = TRUE))
  d <- change_rows(scope, lv, off)
  if (!keep_unchanged) d <- d[cambio == TRUE]
  total <- sum(d$burned_ha)
  d[, share := 100 * burned_ha / total]
  keep <- d[share >= min_share]
  if (!nrow(keep)) keep <- d[order(-share)][1:min(5L, nrow(d))]
  cobertura <- 100 * sum(keep$burned_ha) / total
  keep[, `:=`(clase_prev = droplevels(clase_prev), clase_post = droplevels(clase_post))]
  p <- ggplot(keep, aes(y = burned_ha, axis1 = clase_prev, axis2 = clase_post)) +
    ggalluvial::geom_alluvium(aes(fill = clase_prev), width = 0.22, alpha = 0.75,
                              curve_type = "sigmoid") +
    ggalluvial::geom_stratum(width = 0.22, fill = "grey97", colour = "grey60",
                             linewidth = 0.3) +
    # `stat = ggalluvial::StatStratum` y NO `stat = "stratum"`: la cadena hace que ggplot2
    # busque `StatStratum` en el search path, y acá ggalluvial está sólo cargado con `::`.
    # La etiqueta va ENVUELTA: "Vegetación natural herbácea y arbustiva" mide cinco veces el
    # ancho de la caja y se derrama sobre las bandas.
    geom_text(stat = ggalluvial::StatStratum, aes(label = after_stat(wrap_lab(stratum))),
              size = 2.5, lineheight = 0.92, colour = "grey15") +
    scale_fill_manual(values = change_colors(lv), guide = "none") +
    scale_x_discrete(limits = c("antes", "después"), expand = c(0.16, 0.16)) +
    scale_y_continuous(labels = function(y) fmt_mha(y, 1), expand = expansion(mult = c(0, 0.02))) +
    labs(x = NULL, y = "Mha (suma de la serie)")
  attr(p, "cobertura") <- cobertura
  attr(p, "total_ha") <- total
  p
}

# ── el control: q, y las dos figuras que lo muestran ─────────────────────────
# `q = P(cambió | ardió) / P(cambió | no ardió)`, tratamiento = estado 1 y control = estado 0
# (los dos LIMPIOS, docs/09 §5.7.1).  q > 1 el fuego promueve el cambio, q < 1 lo limita, y
# q = 1 es "lo mismo que le pasa a la tierra sin fuego".
#
# Es EL número del análisis 6: "el 15 % de lo quemado cambió de cobertura" no se puede leer
# sin saber que el país cambia un 4 % sin fuego alguno.  Sin el control, Pampa es la región
# donde más cambia lo quemado (33,9 %) — con el control baja al tercer puesto, porque es
# además la región donde más cambia TODO.
STATE_COLORS <- c(burned = "#B23C06", control = "grey55")
STATE_LABS   <- c(burned = "ardió", control = "no ardió (control)")

q_of <- function(lv = "nivel1", off = 1L)
  fs$change_sum[level == lv & offset == off & state_id %in% c(0L, 1L, 13L)]

# (1) LAS DOS TASAS, UNA AL LADO DE LA OTRA.  La figura honesta: dos puntos por región unidos
# por un segmento — la distancia ES el efecto del fuego, y el punto gris dice cuánto de lo
# que se ve habría pasado igual.  Ordenada por q, que es lo que el segmento mide.
dumbbell_change <- function(lv = "nivel1", off = 1L) {
  d <- q_of(lv, off)[ecoregion %in% REGIONS & state_id %in% c(0L, 1L)]
  ord <- d[state_id == 1L][order(q_changed), ecoregion]
  d[, ecoregion := factor(ecoregion, levels = ord)]
  d[, grp := ifelse(state_id == 1L, "burned", "control")]
  w <- dcast(d, ecoregion ~ grp, value.var = "changed_pct")
  ggplot(d, aes(changed_pct, ecoregion)) +
    geom_segment(data = w, aes(x = control, xend = burned, y = ecoregion, yend = ecoregion),
                 inherit.aes = FALSE, colour = "grey78", linewidth = 1.1) +
    geom_point(aes(colour = grp), size = 2.6) +
    scale_colour_manual(values = STATE_COLORS, labels = STATE_LABS, name = NULL) +
    scale_x_continuous(expand = expansion(mult = c(0.02, 0.08))) +
    labs(x = "% que figura con otra cobertura al año siguiente", y = NULL) +
    theme(legend.position = "top")
}

# (2) q, EN BARRAS Y EN ESCALA LOG.  log porque q es un cociente: 0,5 y 2 tienen que estar a
# la misma distancia de 1, y en escala lineal el lado "el fuego limita el cambio" se aplasta
# contra el eje.  La línea del 1 es la referencia, no un adorno.
bars_q <- function(lv = "nivel1", off = 1L) {
  d <- q_of(lv, off)[ecoregion %in% REGIONS & state_id == 1L][order(q_changed)]
  d[, ecoregion := factor(ecoregion, levels = ecoregion)]
  nat <- q_of(lv, off)[ecoregion == NAT & state_id == 1L, q_changed]
  ggplot(d, aes(q_changed, ecoregion, fill = q_changed > 1)) +
    geom_col(width = 0.72) +
    geom_vline(xintercept = 1, colour = "grey25", linewidth = 0.4) +
    geom_vline(xintercept = nat, linetype = "22", colour = REGION_COLORS[[NAT]],
               linewidth = 0.5) +
    geom_text(aes(label = formatC(q_changed, format = "f", digits = 1, decimal.mark = ","),
                  hjust = ifelse(q_changed > 1, -0.25, 1.25)),
              size = 3.1, colour = "grey30") +
    scale_fill_manual(values = c(`TRUE` = "#B23C06", `FALSE` = "#2166AC"), guide = "none") +
    scale_x_continuous(trans = "log10", expand = expansion(mult = c(0.12, 0.12))) +
    labs(x = "q — veces que el fuego multiplica la probabilidad de cambio", y = NULL)
}

# (3) LA VENTANA: Y+1 CONTRA Y+3.  La prueba del artefacto de la cicatriz (docs/09 §5.7.2).
# Si lo que se ve a un año fuera la col-3 mirando la quemadura, a tres años habría vuelto:
# la tasa de lo quemado caería hacia el control y q se desplomaría a 1.  Que no pase es la
# evidencia de que las transiciones son persistentes.
lines_window <- function(lv = "nivel1") {
  offs <- sort(unique(fs$change_sum$offset))
  d <- fs$change_sum[level == lv & state_id %in% c(0L, 1L) & ecoregion %in% c(NAT, REGIONS)]
  d[, grp := ifelse(state_id == 1L, "burned", "control")]
  ggplot(d[ecoregion != NAT], aes(offset, changed_pct, group = interaction(ecoregion, grp),
                                  colour = grp)) +
    geom_line(linewidth = 0.5, alpha = 0.45) +
    geom_line(data = d[ecoregion == NAT], linewidth = 1.3) +
    geom_point(data = d[ecoregion == NAT], size = 2.4) +
    scale_colour_manual(values = STATE_COLORS, labels = STATE_LABS, name = NULL) +
    scale_x_continuous(breaks = offs, labels = paste0("Y+", offs),
                       expand = expansion(mult = c(0.08, 0.08))) +
    labs(x = "cobertura 'después' leída a", y = "% que cambió de cobertura") +
    theme(legend.position = "top")
}

# (4) q POR TRANSICIÓN — la matriz de Ferro et al., que es donde q deja de ser un promedio.
# Una celda por (clase antes -> clase después); el color es log(q). Las transiciones que no
# ocurren sin fuego dan q infinito: se las marca, no se las rellena con un número inventado.
tile_q <- function(scope = NAT, lv = "nivel1", off = 1L, min_area_ha = 1000) {
  d <- fs$change_q[ecoregion == scope & level == lv & offset == off &
                   area_burned >= min_area_ha]
  lvls <- change_levels(lv)
  d[, `:=`(clase_prev = factor(clase_prev, levels = lvls),
           clase_post = factor(clase_post, levels = rev(lvls)))]
  d[, lab := ifelse(is.finite(q),
                    formatC(q, format = "f", digits = 1, decimal.mark = ","), "∞")]
  d[, fill := ifelse(is.finite(q), log10(pmax(q, 1e-3)), NA_real_)]
  ggplot(d, aes(clase_prev, clase_post)) +
    geom_tile(aes(fill = fill), colour = "white", linewidth = 0.6) +
    geom_text(aes(label = lab), size = 3, colour = "grey15") +
    scale_fill_gradient2(low = "#2166AC", mid = "grey93", high = "#B23C06", midpoint = 0,
                         na.value = "#F2D5C4", name = "log₁₀ q",
                         labels = function(x) formatC(10^x, format = "fg", digits = 2)) +
    scale_x_discrete(labels = function(x) wrap_lab(x, 14), position = "top") +
    scale_y_discrete(labels = function(x) wrap_lab(x, 14)) +
    labs(x = "cobertura ANTES", y = "cobertura DESPUÉS") +
    theme(panel.grid = element_blank(),
          axis.text.x.top = element_text(size = rel(0.8)),
          axis.text.y = element_text(size = rel(0.8)))
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
