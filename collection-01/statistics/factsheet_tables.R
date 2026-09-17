#!/usr/bin/env Rscript
# =============================================================================
# collection-01/statistics/factsheet_tables.R  —  THE ANALYSIS PASS
#
# Turns the three raw sources into the plot-ready tables the factsheet notebook
# reads. Every table is small (hundreds to a few thousand rows) and every number
# the factsheet quotes is in one of them, so a new figure is a read and a ggplot,
# never a re-computation.
#
# THE THREE SOURCES (docs/09 §2)
#   the numerator    the network's toolkit, run on our 13-class ecoregion vector:
#                    annual / monthly / annual-coverage burned area, by calendar
#                    year x ecorregión (x LULC). Already decoded — the toolkit
#                    writes names, not codes.
#   the denominator  burnable_eco13.csv — ONE constant burnable area per
#                    ecorregión, the mode over 1998-2024 of the col-3 burnable
#                    classes. It does NOT vary by year (docs/09 §4).
#   the fire counts  fire_counts_by_month.csv, from statistics/fire_counts.R —
#                    events, not pixels, off the local polygons.
#   el cambio        lulc_change_eco13.csv, de statistics/lulc_change_export.py: lo
#                    quemado cruzado por la cobertura de Y-1 y la de Y+1 (análisis 6,
#                    docs/09 §5.7). OPCIONAL: si no está, la sección se saltea.
#
# WHAT IT WRITES  (all into data/statistics/)
#   factsheet_annual.csv        ecorregión x año: burned, burnable, %, % / media
#   factsheet_monthly.csv       ecorregión x año x mes: burned, %
#   factsheet_lulc.csv          ecorregión x año x clase LULC: burned
#   factsheet_lulc_share.csv    ecorregión x clase: qué se quemó, en % de lo quemado
#   factsheet_lulc_pct.csv      ecorregión x clase x año: % DE LA CLASE que se quemó
#   factsheet_lulc_pct_mean.csv idem, promediado sobre los años (el promedio, ÚLTIMO)
#   factsheet_trend_fits.csv    the GAM trend of % vs año, on a fine grid
#   factsheet_pirogram.csv      ecorregión x mes: área e incendios por año
#   factsheet_season_fits.csv   the cyclic GAM through the pirogram points
#   factsheet_region_scalars.csv one row per ecorregión — every scalar a map paints
#   factsheet_change.csv        ecorregión x nivel x año x clase ANTES x clase DESPUÉS
#   factsheet_change_annual.csv idem, resumido: cuánto ardió y cuánto cambió de clase
#   factsheet_change_summary.csv el escalar del análisis 6: % de lo quemado que cambió
#
# ALL CALENDAR YEAR. The fire year (1 May -> 30 Apr) is how the mapping is
# organised, never how anything is reported. The month axis is nonetheless
# DISPLAYED May -> April, so the fire season is not cut in half: that is the
# `month_fy` column (1 = mayo ... 12 = abril), a display order and nothing else.
#
# Usage (from the repo ROOT), after statistics/fire_counts.R:
#   Rscript collection-01/statistics/factsheet_tables.R
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(mgcv)
})

DIR <- "collection-01/data/statistics"

CAL_YEARS <- 1999:2025
NAT <- "Argentina"        # the national row's `ecoregion`, with ecoregion_id 0

# ── ecorregión 13 is NOT mapped, so it is not reported ───────────────────────
# Islas del Atlántico Sur has 1.16 Mha of burnable land and zero burned area —
# but that zero is a MAPPING GAP, not a finding: no carta of the processing grid
# overlaps the layer's bbox (measured 2026-09-15, 0 of 248 cartas), so no fire
# there could ever have been detected. Reporting "0 % quemado" would present a
# hole in the map as a fact about fire. It is dropped from every table, from the
# maps and from the national denominator (252.25 -> 251.09 Mha burnable).
UNMAPPED_REGIONS <- 13L

# ── las clases NO QUEMABLES no entran a ningún análisis de cobertura ─────────
# Area quemada sobre agua, glaciar, ciudad o suelo desnudo es ERROR DE MAPEO: esas clases
# no arden. Medido, es ruido — 0.09 % de lo quemado en el país (32,122 ha en 'Áreas sin
# vegetación' + 25,327 en 'Cuerpos de agua'), y 1.56 % en el peor caso (Estepa Patagónica).
# Dejarlo dentro no agrega información y sí confunde: mete dos categorías de barra invisible
# en cada gráfico y le roba un punto al 100 %.
#
# El corte va por FAMILIA (nivel 1) y es exacto, no una aproximación: las clases col-3 que
# existen en Argentina dentro de estas dos familias son 24, 25, 33 y 34 — exactamente las de
# `legends.py::NON_BURNABLE` que aparecen en el país (22 y 26 no ocurren). Verificado contra
# `lulc_area_eco13.csv`, que es la única tabla que trae el CÓDIGO al lado de los nombres.
#
# Con esto, la composición del análisis 4 suma 100 % sobre lo que PUEDE arder, que es lo que
# significa cuando se la lee.
NON_BURNABLE_N1 <- c("Áreas sin vegetación", "Cuerpos de agua")

K_TREND  <- 5      # docs/10 análisis 2 — a few bases, a smooth decadal shape
# docs/10 análisis 3.2 asks for k = 12, so that the curve FOLLOWS the 12 summary
# points. Measured, 12 does the opposite at the one place it matters: nationally
# it overshoots the August peak by 8 % and the Chaco's by 10.5 %, drawing a curve
# that is higher than any month actually is. k = 10 reproduces the national peak
# to 0.2 % and is the compromise across the 12 regions.
K_SEASON <- 10
MONTH_ES <- c("Ene", "Feb", "Mar", "Abr", "May", "Jun",
              "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")

msg <- function(...) cat(sprintf(...), "\n", sep = "")
rd <- function(f) fread(file.path(DIR, f), encoding = "UTF-8")
wr <- function(d, f) { fwrite(d, file.path(DIR, f))
                       msg("[out] %-30s %s rows", f, format(nrow(d), big.mark = ",")) }

# Display order for the month axis: 1 = mayo ... 12 = abril.
to_fy_month <- function(m) ((m - 5) %% 12) + 1

# ── the denominator ──────────────────────────────────────────────────────────
burn <- rd("burnable_eco13.csv")[status == "burnable" & !ecoregion_id %in% UNMAPPED_REGIONS,
                                 .(ecoregion_id, ecoregion, burnable_ha = area_ha)]
meta <- rd("ecoregions13_meta.csv")[!ecoregion_id %in% UNMAPPED_REGIONS]
burn <- rbind(burn, data.table(ecoregion_id = 0L, ecoregion = NAT,
                               burnable_ha = sum(burn$burnable_ha)))
msg("denominador: %d ecorregiones, %.2f Mha quemables (nacional)",
    nrow(burn) - 1L, burn[ecoregion_id == 0, burnable_ha] / 1e6)

# ── the numerator ────────────────────────────────────────────────────────────
# The toolkit writes only the rows that burned, so a region-year with no fire is
# simply ABSENT. Every table below is therefore built on a complete grid and
# filled with zeros — otherwise a mean over years silently divides by the number
# of years that happened to burn.
regions <- burn[ecoregion_id != 0]
grid_ry <- CJ(ecoregion_id = regions$ecoregion_id, year = CAL_YEARS)
grid_rym <- CJ(ecoregion_id = regions$ecoregion_id, year = CAL_YEARS, month = 1:12)

read_toolkit <- function(f, extra = character(0)) {
  d <- rd(f)
  setnames(d, c("Área ha", "Ano", "Ecorregión"), c("burned_ha", "year", "ecoregion"))
  d <- d[ecoregion %in% regions$ecoregion]
  d[regions, on = "ecoregion", ecoregion_id := i.ecoregion_id]
  d[, c("ecoregion_id", "ecoregion", "year", "burned_ha", extra), with = FALSE]
}

# The national row carries `ecoregion_id = 0`; the NAME is attached afterwards,
# from `burn`, so there is exactly one place where a region id becomes a label.
add_national <- function(d, by) rbind(
  d, d[, .(ecoregion_id = 0L, burned_ha = sum(burned_ha)), by = by],
  use.names = TRUE)

# ── 1. annual: burned, burnable, % ───────────────────────────────────────────
ann <- read_toolkit("annual_burned_Ecorregiones.csv")[
  , .(burned_ha = sum(burned_ha)), by = .(ecoregion_id, year)]
ann <- merge(grid_ry, ann, by = c("ecoregion_id", "year"), all.x = TRUE)
ann[is.na(burned_ha), burned_ha := 0]
ann <- add_national(ann, "year")
ann[burn, on = "ecoregion_id", `:=`(ecoregion = i.ecoregion, burnable_ha = i.burnable_ha)]
ann[, pct := 100 * burned_ha / burnable_ha]
# "veces el año típico" (docs/10 análisis 2): the series divided by its own mean,
# so regions of wildly different magnitude can share one panel and be compared by
# SHAPE. 1 is a normal year for that region, 4 is four times its normal.
ann[, pct_rel := pct / mean(pct), by = ecoregion_id]
setcolorder(ann, c("ecoregion_id", "ecoregion", "year"))
setorder(ann, ecoregion_id, year)
wr(ann, "factsheet_annual.csv")

# ── 2. monthly ───────────────────────────────────────────────────────────────
mon <- rd("monthly_burned_Ecorregiones.csv")
setnames(mon, c("Área ha", "Ano", "Ecorregión", "Mes_id"),
         c("burned_ha", "year", "ecoregion", "month"))
mon <- mon[ecoregion %in% regions$ecoregion]
mon[regions, on = "ecoregion", ecoregion_id := i.ecoregion_id]
mon <- mon[, .(burned_ha = sum(burned_ha)), by = .(ecoregion_id, year, month)]
mon <- merge(grid_rym, mon, by = c("ecoregion_id", "year", "month"), all.x = TRUE)
mon[is.na(burned_ha), burned_ha := 0]
mon <- add_national(mon, c("year", "month"))
mon[burn, on = "ecoregion_id", `:=`(ecoregion = i.ecoregion, burnable_ha = i.burnable_ha)]
mon[, pct := 100 * burned_ha / burnable_ha]
mon[, month_fy := to_fy_month(month)]
mon[, month_name := MONTH_ES[month]]
setcolorder(mon, c("ecoregion_id", "ecoregion", "year", "month", "month_fy", "month_name"))
setorder(mon, ecoregion_id, year, month)
wr(mon[, .(ecoregion_id, ecoregion, year, month, month_fy, month_name, burned_ha, pct)],
   "factsheet_monthly.csv")

# ── 3. burned x land cover ───────────────────────────────────────────────────
# TWO different questions, and only one of them is answerable here:
#   "qué se quemó"        the COMPOSITION of the burned area — what share of what
#                         burned in this region was forest. Denominator = the
#                         region's own burned area, which we have. ✅
#   "qué % del bosque se  would need a denominator WITH A CLASS DIMENSION, which
#    quemó"               the constant burnable layer does not have (§4.4). ❌
# So `factsheet_lulc.csv` carries absolute areas, `factsheet_lulc_share.csv` the
# composition, and neither is a "% of the class that burned".
#
# This cross reads the PREVIOUS year's land cover — what burned, not what the
# pixel became (docs/09 §2.2).
lulc <- read_toolkit("annual_burned_coverage_Ecorregiones.csv",
                     c("Nivel 0", "Nivel 1", "Nivel 2"))
lulc[, ecoregion := NULL]
setnames(lulc, c("Nivel 0", "Nivel 1", "Nivel 2"), c("nivel0", "nivel1", "nivel2"))
# "No observado" is excluded from every ratio in this stage (§8), so it is dropped
# here too rather than becoming a sliver of every composition bar. Measured: 0.24 ha
# in the whole country over 27 years — one pixel in 2025. Reported, not assumed.
n_obs <- lulc[nivel1 == "No observado", sum(burned_ha)]
msg("LULC: se descartan %.2f ha de 'No observado' (%.1e %% de lo quemado)",
    n_obs, 100 * n_obs / sum(lulc$burned_ha))
lulc <- lulc[nivel1 != "No observado"]
n_nb <- lulc[nivel1 %in% NON_BURNABLE_N1, sum(burned_ha)]
msg("LULC: se descartan %s ha en clases NO QUEMABLES (%.2f %% de lo quemado) — %s",
    format(round(n_nb), big.mark = ","), 100 * n_nb / sum(lulc$burned_ha),
    paste(NON_BURNABLE_N1, collapse = ", "))
lulc <- lulc[!nivel1 %in% NON_BURNABLE_N1]
lulc <- lulc[, .(burned_ha = sum(burned_ha)),
             by = .(ecoregion_id, year, nivel0, nivel1, nivel2)]
lulc <- rbind(lulc, lulc[, .(ecoregion_id = 0L, burned_ha = sum(burned_ha)),
                         by = .(year, nivel0, nivel1, nivel2)], use.names = TRUE)
lulc[burn, on = "ecoregion_id", ecoregion := i.ecoregion]
setcolorder(lulc, c("ecoregion_id", "ecoregion", "year"))
setorder(lulc, ecoregion_id, year, -burned_ha)
wr(lulc, "factsheet_lulc.csv")

# The composition, over the whole series, at both legend levels. Summing the years
# before dividing (rather than averaging per-year shares) weights each year by how
# much it burned, which is what "de todo lo que se quemó en esta región" means.
share_by <- function(cols) {
  d <- lulc[, .(burned_ha = sum(burned_ha)), by = c("ecoregion_id", "ecoregion", cols)]
  d[, share := 100 * burned_ha / sum(burned_ha), by = ecoregion_id]
  d[, level := if (length(cols) == 1) "nivel1" else "nivel2"]
  setnames(d, cols[length(cols)], "clase")
  if (length(cols) == 1) d[, nivel1 := clase]
  d[, .(ecoregion_id, ecoregion, level, nivel1, clase, burned_ha, share)]
}
lulc_share <- rbind(share_by("nivel1"), share_by(c("nivel1", "nivel2")))
setorder(lulc_share, level, ecoregion_id, -share)
wr(lulc_share, "factsheet_lulc_share.csv")

# ── 3b. % OF EACH CLASS THAT BURNED ─────────────────────────────────────────
# The other land-cover question (§3.3), and the one that needs the second export:
# `lulc_area_eco13.csv` is the area of every col-3 class per ecorregión per year,
# space-filling, from statistics/lulc_area_export.py.
#
# THE YEAR OFFSET IS THE WHOLE POINT. The numerator crosses fire in year Y with
# `classification_<Y-1>`, so the class label on a burned hectare refers to Y-1 and
# its denominator is the class area in Y-1. Joining Y to Y would be wrong by one
# year in a way no gate would catch, so the join is written once, here.
#
# THE MEAN IS TAKEN LAST. pct is computed per year and then averaged over years —
# never sum(burned)/sum(area). Two reasons, both real: a ratio of sums is not the
# mean of the ratios (Jensen), and summing burned area over 27 years double-counts
# every reburn, so the pooled numerator can exceed the class area outright.
LULC_AREA <- file.path(DIR, "lulc_area_eco13.csv")
if (!file.exists(LULC_AREA)) {
  msg("[skip] %s no está — corré statistics/lulc_area_export.py --export --fetch", LULC_AREA)
} else {
  # Las dos exclusiones, a los DOS lados del cociente: 'No observado' y las clases no
  # quemables. El numerador ya viene filtrado de arriba; el denominador se filtra acá.
  area <- rd("lulc_area_eco13.csv")[!ecoregion_id %in% UNMAPPED_REGIONS &
                                    !nivel1 %in% c("No observado", NON_BURNABLE_N1)]
  burned <- lulc[!nivel1 %in% c("No observado", NON_BURNABLE_N1)]

  # One level at a time: at nivel1 several codes share a name, so the denominator has
  # to be aggregated by NAME before the join — the same aggregation the toolkit's
  # decode already applied to the numerator.
  pct_at <- function(lvl) {
    a <- area[, .(area_ha = sum(area_ha)),
              by = c("ecoregion_id", "ecoregion", "year", lvl)]
    b <- burned[ecoregion_id != 0, .(burned_ha = sum(burned_ha)),
                by = c("ecoregion_id", "year", lvl)]
    setnames(a, lvl, "clase"); setnames(b, lvl, "clase")
    # fire year Y  <->  land-cover year Y-1
    a[, year := year + 1L]
    a <- a[year %in% CAL_YEARS & area_ha > 0]

    # Region level: every (región, clase, año) whose class EXISTS gets a row, so a
    # year with no fire contributes a 0 and not a gap. A class with zero area that
    # year has no row at all — its `%` is undefined, not zero.
    r <- merge(a, b, by = c("ecoregion_id", "year", "clase"), all.x = TRUE)
    r[is.na(burned_ha), burned_ha := 0]

    # ORPHANS: burned hectares whose (región, clase, año) has no denominator row. It
    # should be impossible — a burned pixel of class c is a pixel of class c — but the
    # two sides are reduced by different teams on grids that differ by a sub-pixel phase
    # (docs/09 §2.3), so an edge sliver can produce one. `all.x = TRUE` would drop it
    # without a word, and dropped numerator is the one error that makes every `%` look
    # fine and be too low. Counted, not assumed.
    orph <- b[!r, on = c("ecoregion_id", "year", "clase")]
    if (nrow(orph))
      msg("  [%s] %d filas quemadas sin denominador (%.1f ha, %.2e %% de lo quemado) — %s",
          lvl, nrow(orph), sum(orph$burned_ha),
          100 * sum(orph$burned_ha) / sum(b$burned_ha),
          paste(unique(orph$clase), collapse = ", "))

    # National: sum both sides across regions FIRST, then divide — the national `%`
    # is one ratio per year, not an average of regional ratios.
    n <- r[, .(ecoregion_id = 0L, ecoregion = NAT,
               area_ha = sum(area_ha), burned_ha = sum(burned_ha)),
           by = .(year, clase)]
    out <- rbind(r, n, use.names = TRUE)
    out[, pct := 100 * burned_ha / area_ha]
    out[, level := lvl]
    out[, .(ecoregion_id, ecoregion, level, clase, year, burned_ha, area_ha, pct)]
  }

  lulc_pct <- rbind(pct_at("nivel1"), pct_at("nivel2"))
  setorder(lulc_pct, level, ecoregion_id, clase, year)
  wr(lulc_pct, "factsheet_lulc_pct.csv")

  # THE MEAN, LAST.
  lulc_pct_mean <- lulc_pct[, .(
    n_years        = .N,
    mean_pct       = mean(pct),
    sd_pct         = sd(pct),
    max_pct        = max(pct),
    max_year       = year[which.max(pct)],
    mean_burned_ha = mean(burned_ha),
    mean_area_ha   = mean(area_ha)),
    by = .(ecoregion_id, ecoregion, level, clase)]
  setorder(lulc_pct_mean, level, ecoregion_id, -mean_pct)
  wr(lulc_pct_mean, "factsheet_lulc_pct_mean.csv")

  msg("")
  print(dcast(lulc_pct_mean[level == "nivel1"], ecoregion ~ clase,
              value.var = "mean_pct")[, lapply(.SD, function(x)
                if (is.numeric(x)) round(x, 2) else x)])
}

# ── 4. the trend: a GAM through the annual % series ──────────────────────────
# One normal GAM per region, k = 5 (docs/10 análisis 2). The scalar it is
# summarised by is the MEAN SLOPE over the series — evaluated at every observed
# year and averaged, which for a straight line is just the slope.
trend_one <- function(d) {
  fit <- gam(pct ~ s(year, k = K_TREND), data = d, method = "REML")
  gy <- seq(min(CAL_YEARS), max(CAL_YEARS), by = 0.1)
  p  <- predict(fit, newdata = data.frame(year = gy), se.fit = TRUE)
  list(fits = data.table(year = gy, fit = as.numeric(p$fit), se = as.numeric(p$se.fit)),
       # finite differences on the fine grid, read at the observed years
       slope = {
         der <- diff(as.numeric(p$fit)) / diff(gy)
         mean(approx(gy[-1] - 0.05, der, xout = CAL_YEARS, rule = 2)$y)
       },
       fit_first = as.numeric(p$fit[1]), fit_last = as.numeric(p$fit[length(gy)]))
}
tr <- lapply(split(ann, ann$ecoregion_id), trend_one)
trend_fits <- rbindlist(lapply(names(tr), function(k) {
  x <- copy(tr[[k]]$fits); x[, ecoregion_id := as.integer(k)]; x }))
trend_fits[burn, on = "ecoregion_id", ecoregion := i.ecoregion]
trend_fits[, `:=`(lo = fit - 2 * se, hi = fit + 2 * se)]
setcolorder(trend_fits, c("ecoregion_id", "ecoregion", "year"))
wr(trend_fits, "factsheet_trend_fits.csv")

# ── 5. the pirogram: área e incendios por mes ────────────────────────────────
# Both halves are MEANS OVER THE 27 YEARS of that month's value — "un mes de
# septiembre típico", not a total. The count half is the >= 10 ha fires (docs/10
# análisis 3.2); it comes from the polygons and is filed whole into the month of
# `date_median`, while the area half is split per pixel. Same shape, different
# values — say which one a number came from.
cnt <- rd("fire_counts_by_month.csv")[!ecoregion_id %in% UNMAPPED_REGIONS]
cnt <- merge(CJ(ecoregion_id = c(0L, regions$ecoregion_id), year = CAL_YEARS, month = 1:12),
             cnt[, .(ecoregion_id, year, month, n_fires, n_ge10, n_ge100, n_ge1000)],
             by = c("ecoregion_id", "year", "month"), all.x = TRUE)
for (j in c("n_fires", "n_ge10", "n_ge100", "n_ge1000")) set(cnt, which(is.na(cnt[[j]])), j, 0L)

nyears <- length(CAL_YEARS)
piro <- merge(mon[, .(burned_ha = sum(burned_ha) / nyears, pct = sum(pct) / nyears),
                  by = .(ecoregion_id, ecoregion, month, month_fy, month_name)],
              cnt[, .(n_fires = sum(n_fires) / nyears, n_ge10 = sum(n_ge10) / nyears,
                      n_ge100 = sum(n_ge100) / nyears), by = .(ecoregion_id, month)],
              by = c("ecoregion_id", "month"))
# The intra-annual SHAPES (docs/10 análisis 3.3): each region's 12 months sum to
# 100 %, so magnitude is divided out and only the season's shape is compared.
piro[, share_area := 100 * burned_ha / sum(burned_ha), by = ecoregion_id]
piro[, share_fires := 100 * n_ge10 / sum(n_ge10), by = ecoregion_id]
piro <- merge(piro, rbind(meta[, .(ecoregion_id, area_km2)],
                          data.table(ecoregion_id = 0L, area_km2 = sum(meta$area_km2))),
              by = "ecoregion_id")
piro[, dens_ge10_10kkm2 := n_ge10 / (area_km2 / 1e4)]
setorder(piro, ecoregion_id, month)
wr(piro[, .(ecoregion_id, ecoregion, month, month_fy, month_name, burned_ha, pct,
            n_fires, n_ge10, n_ge100, share_area, share_fires, dens_ge10_10kkm2)],
   "factsheet_pirogram.csv")

# ── 6. the cyclic GAM through the pirogram ───────────────────────────────────
# Fitted on the 12 SUMMARY points, not on the raw year-by-month data: it is there
# to follow the mean curve, an aesthetic device, and fitting it to the summary is
# what makes it do that (docs/10 análisis 3.2).
season_one <- function(d, yname) {
  y <- d[[yname]]
  if (sum(y) <= 0) return(data.table(month = numeric(0), fit = numeric(0)))
  f <- gam(y ~ s(month, bs = "cc", k = K_SEASON), data = data.frame(month = d$month, y = y),
           knots = list(month = c(0.5, 12.5)), method = "REML")
  gm <- seq(1, 12.999, by = 0.02)
  data.table(month = gm, fit = pmax(0, as.numeric(predict(f, data.frame(month = gm)))))
}
season_fits <- rbindlist(lapply(split(piro, piro$ecoregion_id), function(d) {
  setorder(d, month)
  out <- Reduce(function(a, b) merge(a, b, by = "month"), list(
    setnames(season_one(d, "share_area"),  "fit", "share_area"),
    setnames(season_one(d, "share_fires"), "fit", "share_fires"),
    setnames(season_one(d, "pct"),         "fit", "pct"),
    setnames(season_one(d, "n_ge10"),      "fit", "n_ge10")))
  out[, `:=`(ecoregion_id = d$ecoregion_id[1], ecoregion = d$ecoregion[1],
             month_fy = to_fy_month(month))]
  # THE CURVE MUST NOT OUTLIVE THE DATA. The grid is a full cycle in CALENDAR
  # month (1 -> 12.999), which in DISPLAY coordinates (mayo = 1 ... abril = 12)
  # wraps to 12.999: drawn, the curve ran a whole extra month past abril, into a
  # second mayo that has no point under it. The fit is cyclic, so that tail is a
  # redrawing of mayo, not an extrapolation — but it reads as one. Cut at 12.
  out[month_fy <= 12]
}), fill = TRUE)
setorder(season_fits, ecoregion_id, month_fy)
setcolorder(season_fits, c("ecoregion_id", "ecoregion", "month", "month_fy"))
wr(season_fits, "factsheet_season_fits.csv")

# ── 7. every scalar a map can paint ──────────────────────────────────────────
peak <- function(d, col) d[which.max(d[[col]]), month]
scal <- ann[, .(mean_burned_ha = mean(burned_ha), mean_pct = mean(pct),
                sd_pct = sd(pct), burnable_ha = burnable_ha[1],
                max_year = year[which.max(burned_ha)], max_ha = max(burned_ha),
                max_pct = max(pct),
                min_year = year[which.min(burned_ha)], min_ha = min(burned_ha)),
            by = .(ecoregion_id, ecoregion)]
scal[, `:=`(
  # the trend, three ways. b_abs is puntos porcentuales/año — comparable only
  # between regions that burn alike. b_rel divides it by the region's own mean,
  # so it reads "fracción del año típico ganada por año" and IS comparable; it is
  # the one the map paints. trend_ratio is the fitted end over the fitted start,
  # the same statement as a factor over the whole series, which reads best in a
  # caption.
  b_abs       = vapply(as.character(ecoregion_id), function(k) tr[[k]]$slope, 0),
  fit_first   = vapply(as.character(ecoregion_id), function(k) tr[[k]]$fit_first, 0),
  fit_last    = vapply(as.character(ecoregion_id), function(k) tr[[k]]$fit_last, 0))]
scal[, b_rel := b_abs / mean_pct]
scal[, trend_ratio := fit_last / fit_first]
scal[, cv_pct := sd_pct / mean_pct]
scal[piro[, .(peak_month_area = month[which.max(share_area)],
              peak_month_fires = month[which.max(share_fires)],
              peak_share_area = max(share_area)), by = ecoregion_id],
     on = "ecoregion_id", `:=`(peak_month_area = i.peak_month_area,
                               peak_month_fires = i.peak_month_fires,
                               peak_share_area = i.peak_share_area)]
scal[, `:=`(peak_month_area_name = MONTH_ES[peak_month_area],
            peak_month_fires_name = MONTH_ES[peak_month_fires])]
# The composition shares, so a map can paint "% de lo quemado que era bosque".
# Keyed by the legend's own nivel-1 strings; a class absent from a region is 0, and
# a class absent from THIS list is a legend change that must be noticed, not
# silently dropped — hence the stopifnot.
# Tres familias, no cinco: las no quemables ya no llegan hasta acá (§ arriba).
N1_COL <- c("Bosques"                                 = "share_bosques",
            "Vegetación natural herbácea y arbustiva" = "share_herb_arbust",
            "Áreas de uso agropecuario"               = "share_agro")
n1 <- lulc_share[level == "nivel1"]
stopifnot(all(n1$clase %in% names(N1_COL)))
n1 <- dcast(n1, ecoregion_id ~ N1_COL[clase], value.var = "share", fill = 0)
scal[n1, on = "ecoregion_id",
     (setdiff(names(n1), "ecoregion_id")) := mget(paste0("i.", setdiff(names(n1), "ecoregion_id")))]

fs <- rd("fire_region_summary.csv")[!ecoregion_id %in% UNMAPPED_REGIONS]
scal[fs, on = "ecoregion_id",
     `:=`(fires_per_year = i.fires_per_year, median_ha = i.median_ha,
          p95_ha = i.p95_ha, biggest_fire_ha = i.max_ha,
          fires_ge10_per_10kkm2 = i.fires_per_year_per_10kkm2,
          total_fires = i.n_fires, total_ge10 = i.n_ge10)]
# The totals over the whole series, which the pirograma normalizado annotates (docs/10 análisis 3.4): a
# PMF divides magnitude out, so the panel has to carry the magnitude in text or it
# says nothing about how much burned. The area is the RASTER side (the sum of the
# annual table, recurrences and all — a hectare that burned four times is in it four
# times); the counts are the POLYGON side, and a fire is counted in every ecorregión
# it touches, so the regional counts sum to MORE than the national one. Two different
# kinds of number: stored apart, labelled apart.
scal[ann[, .(total_burned_ha = sum(burned_ha)), by = ecoregion_id], on = "ecoregion_id",
     total_burned_ha := i.total_burned_ha]
scal <- merge(scal, rbind(meta[, .(ecoregion_id, lat, lon, area_km2, palette_order)],
                          data.table(ecoregion_id = 0L, lat = NA_real_, lon = NA_real_,
                                     area_km2 = sum(meta$area_km2), palette_order = 0L)),
              by = "ecoregion_id")
setorder(scal, -mean_pct)
wr(scal, "factsheet_region_scalars.csv")

# ── 6. el cambio de cobertura alrededor del fuego (docs/09 §5.7, docs/10 §6) ──
# La fuente son `lulc_change_eco13_y{1,3}.csv` (statistics/lulc_change_export.py): el país
# entero cruzado por estado de fuego x ecorregión x clase col-3 de Y-1 x clase de Y+offset,
# por año. OPCIONAL, como el análisis 5: un factsheet regenerado antes de que aterrice esa
# exportación se saltea la sección en vez de morir acá.
#
# EL DISEÑO ES EL DE FERRO ET AL. (2026) — el trabajo del grupo sobre el Chaco Seco—, acá a
# 30 m y para todo el país. De ahí vienen la ventana Y-1 -> Y+1, la regla de exclusión y el
# cociente q; docs/09 §5.7 dice qué se copia y qué cambia.
#
# LOS CUATRO ESTADOS, y qué usa cada figura (legends.py::FIRE_STATE_NAMES):
#   1 burned_clean + 3 burned_repeat = TODO lo que ardió en Y -> el titular del análisis
#     ("de lo que ardió, cuánto figura con otra cobertura") y las figuras de composición.
#   1 contra 0 (los dos LIMPIOS, sin fuego en el resto de la ventana) -> el cociente q, que
#     es la única forma de saber si ese titular es mucho o poco.
#
# CINCO DECISIONES, todas visibles en la salida de este bloque:
#
#   1. EL NIVEL SE AGREGA ANTES DE COMPARAR. "Cambió de cobertura" no es una propiedad de la
#      hectárea, es una propiedad de la hectárea Y DEL NIVEL con que se la mira: bosque
#      cerrado -> bosque abierto CAMBIA en nivel 2 y NO cambia en nivel 1. Por eso las dos
#      tablas se construyen por separado desde el código de clase, y nunca una de la otra.
#
#   2. EL LADO "ANTES" SE FILTRA COMO EL ANÁLISIS 4 — EN LOS CUATRO ESTADOS. Una hectárea
#      que ya era agua o ciudad ANTES es error de mapeo (si ardió) o no es tierra quemable
#      (si no), y en los dos casos no pertenece a este análisis. Va el mismo NON_BURNABLE_N1
#      que la composición, y va en el control TAMBIÉN: si el tratamiento se filtra y el
#      control no, q compara dos poblaciones distintas y el número no significa nada.
#      El lado "después" NO se filtra: una herbácea inundable que figura como agua después es
#      una transición legítima —el Delta se inunda—, y el destino no tiene por qué ser
#      quemable. Consecuencia deliberada: el Sankey tiene más categorías a la derecha.
#
#   3. q SE CONDICIONA A LA CLASE DE ORIGEN. La probabilidad de transición es
#      P(prev -> post | prev, estado): dentro de cada clase de origen las probabilidades
#      suman 1. Sin condicionar, q mediría sobre todo qué clases arden, que es el análisis 4
#      y no éste.
#
#   4. "NO OBSERVADO" SE QUEDA, VISIBLE. Es una categoría de la leyenda, no un NA.
#
#   5. LA TABLA ES ANUAL, LAS FIGURAS SUMAN.
CHANGE_OFFSETS <- c(1L, 3L)
change_file <- function(off) sprintf("lulc_change_eco13_y%d.csv", off)
have_off <- CHANGE_OFFSETS[file.exists(file.path(DIR, sapply(CHANGE_OFFSETS, change_file)))]

if (!length(have_off)) {
  msg("[.] lulc_change_eco13_y*.csv no está — análisis 6 salteado "
      %+% "(corré statistics/lulc_change_export.py)")
} else {
  # Un offset a la vez; todo lo que sale lleva la columna `offset`, así que las tablas de
  # Y+1 y de Y+3 conviven y una figura elige con un filtro.
  parts <- lapply(have_off, function(off) {
    raw <- rd(change_file(off))[!ecoregion_id %in% UNMAPPED_REGIONS]
    tot0 <- sum(raw$area_ha)
    msg("")
    msg("análisis 6, Y+%d: %s filas, %d-%d, %.2f Mha/año de país",
        off, format(nrow(raw), big.mark = ","), min(raw$year), max(raw$year),
        tot0 / length(unique(raw$year)) / 1e6)
    msg("  lado ANTES no quemable (descartado en los 4 estados): %.3f %%",
        100 * raw[nivel1_prev %in% NON_BURNABLE_N1, sum(area_ha)] / tot0)
    raw <- raw[!nivel1_prev %in% NON_BURNABLE_N1]

    # los dos niveles, cada uno agregado desde el código de clase (decisión 1)
    long <- rbindlist(lapply(c("nivel1", "nivel2"), function(lv) {
      d <- raw[, .(burned_ha = sum(area_ha)),
               by = .(ecoregion_id, state_id, year,
                      clase_prev = get(paste0(lv, "_prev")),
                      clase_post = get(paste0(lv, "_post")))]
      d <- add_national(d, c("state_id", "year", "clase_prev", "clase_post"))
      d[, `:=`(level = lv, offset = off)][]
    }))
    long[burn, on = "ecoregion_id", ecoregion := i.ecoregion]
    long[, cambio := clase_prev != clase_post]
    long[]
  })
  change_all <- rbindlist(parts)

  # ── lo que ardió: la tabla que dibujan las figuras ─────────────────────────
  # Estados 1 + 3 = "ardió en Y". El estado se colapsa acá: para la composición y el Sankey
  # la pregunta es qué le pasa a lo quemado, no si además ardió en otro año de la ventana.
  change <- change_all[state_id %in% c(1L, 3L),
                       .(burned_ha = sum(burned_ha)),
                       by = .(ecoregion_id, ecoregion, offset, level, year,
                              clase_prev, clase_post, cambio)]
  setcolorder(change, c("ecoregion_id", "ecoregion", "offset", "level", "year",
                        "clase_prev", "clase_post", "cambio", "burned_ha"))
  setorder(change, offset, level, ecoregion_id, year, -burned_ha)
  wr(change, "factsheet_change.csv")

  # ── (a) el escalar, por estado: cuánto cambió ──────────────────────────────
  # Con los cuatro estados adentro, porque el control es la mitad del análisis.
  chg_annual <- change_all[, .(area_ha = sum(burned_ha),
                               changed_ha = sum(burned_ha[cambio])),
                           by = .(ecoregion_id, ecoregion, offset, level, state_id, year)]
  chg_annual[, changed_pct := 100 * changed_ha / area_ha]
  setorder(chg_annual, offset, level, state_id, ecoregion_id, year)
  wr(chg_annual, "factsheet_change_annual.csv")

  chg_sum <- chg_annual[, .(area_ha = sum(area_ha), changed_ha = sum(changed_ha)),
                        by = .(ecoregion_id, ecoregion, offset, level, state_id)]
  chg_sum[, changed_pct := 100 * changed_ha / area_ha]
  # El titular: lo quemado son 1 + 3; el control limpio es 0. `q` compara los dos LIMPIOS.
  burned_row <- chg_annual[state_id %in% c(1L, 3L),
                           .(area_ha = sum(area_ha), changed_ha = sum(changed_ha)),
                           by = .(ecoregion_id, ecoregion, offset, level)]
  burned_row[, `:=`(state_id = 13L, changed_pct = 100 * changed_ha / area_ha)]
  chg_sum <- rbind(chg_sum, burned_row, use.names = TRUE)
  chg_sum[, state := ifelse(state_id == 13L, "burned_any",
                            c("control", "burned_clean", "window_fire",
                              "burned_repeat")[state_id + 1L])]
  qq <- dcast(chg_sum[state_id %in% c(0L, 1L)],
              ecoregion_id + ecoregion + offset + level ~ state,
              value.var = "changed_pct")
  qq[, q_changed := burned_clean / control]
  chg_sum[qq, on = .(ecoregion_id, offset, level), q_changed := i.q_changed]
  setorder(chg_sum, offset, level, state_id, -changed_pct)
  wr(chg_sum, "factsheet_change_summary.csv")

  # ── (b) q por TRANSICIÓN, condicionado a la clase de origen (decisión 3) ───
  qtab <- change_all[state_id %in% c(0L, 1L),
                     .(area_ha = sum(burned_ha)),
                     by = .(ecoregion_id, ecoregion, offset, level, state_id,
                            clase_prev, clase_post)]
  qtab[, p := area_ha / sum(area_ha), by = .(ecoregion_id, offset, level, state_id, clase_prev)]
  qtab <- dcast(qtab, ecoregion_id + ecoregion + offset + level + clase_prev + clase_post ~
                  state_id, value.var = c("area_ha", "p"), fill = 0)
  setnames(qtab, c("area_ha_0", "area_ha_1", "p_0", "p_1"),
           c("area_control", "area_burned", "p_control", "p_burned"))
  # q = P(transición | ardió) / P(transición | no ardió). Sin control la transición existe
  # SÓLO con fuego: `Inf` es la respuesta correcta y no se la reemplaza por un número.
  qtab[, q := p_burned / p_control]
  setorder(qtab, offset, level, ecoregion_id, clase_prev, -p_burned)
  wr(qtab, "factsheet_change_q.csv")

  msg("")
  msg("cuánto cambió de cobertura, y el cociente q (nivel 1, Y+%d)", have_off[1])
  print(chg_sum[offset == have_off[1] & level == "nivel1" & state_id %in% c(0L, 1L, 13L),
                .(ecoregion, state, pct = round(changed_pct, 1),
                  q = round(q_changed, 1))][order(-q)][
                  , dcast(.SD, ecoregion + q ~ state, value.var = "pct")][order(-q)])
}


# ── 6b. el caso patagónico: el corte latitudinal y la COHORTE FIJA ───────────
# Un sub-análisis con nombre propio porque contesta una objeción concreta: en los bosques
# andino-patagónicos el fuego es de alta severidad y la bibliografía habla de ~95 % de
# mortalidad del rodal, contra el 44 % de cambio de cobertura que daba el análisis a un año.
# La pregunta era si el mapa está mal o si TARDA. Resultó lo segundo, con un techo.
#
# Necesita dos cosas que el análisis general no tiene, y las dos salen de
# `lulc_change_export.py` con banderas (docs/09 §5.7.3):
#
#   --lat-split -44   Bosques Patagónicos no es homogénea: el norte (de la mitad de Chubut
#                     para arriba) concentra el 87 % de lo quemado y tiene otro régimen.
#   --window 5        LA COHORTE FIJA. Sin esto, cada lag tiene su propia ventana de
#                     exclusión y por lo tanto su propio rango de años focales: Y+5 se pierde
#                     los incendios de 2021-2024 y Y+1 no, así que los cuatro números son
#                     cuatro POBLACIONES y no una trayectoria. Con la ventana clavada en 5
#                     los cuatro lags miran los MISMOS píxeles y los MISMOS años (1999-2020),
#                     y recién ahí Y+1 -> Y+5 se puede leer como "cuánto tarda".
#
# Las dos cohortes se guardan, la móvil y la fija, porque la comparación entre ellas es parte
# del resultado: la fija da números MÁS ALTOS en todos los lags (48,9 % contra 45,6 % en Y+1),
# que es lo que tiene que pasar si los incendios recientes que la fija excluye todavía no
# tuvieron tiempo de convertirse.
PAT_REGION <- "Bosques Patagónicos"
FOREST_N2  <- c("Bosques", "Bosque cerrado", "Bosque abierto", "Bosque inundable")
PAT_LAGS   <- c(1L, 3L, 4L, 5L)

pat_file <- function(lag, fixed) {
  # Y+5 con ventana 5 ES la corrida `_y5_n44`: pedirle `_w5` sería pedir un archivo que no
  # existe, porque el sufijo sólo se escribe cuando la ventana DIFIERE del lag.
  f <- if (fixed && lag != 5L) sprintf("lulc_change_eco13_y%d_w5_n44.csv", lag)
       else sprintf("lulc_change_eco13_y%d_n44.csv", lag)
  if (file.exists(file.path(DIR, f))) f else NA_character_
}

pat_read <- function(fixed) {
  fs_ <- vapply(PAT_LAGS, pat_file, "", fixed = fixed)
  if (anyNA(fs_)) return(NULL)
  rbindlist(lapply(seq_along(PAT_LAGS), function(i) {
    x <- rd(fs_[i])[ecoregion == PAT_REGION & nivel2_prev %in% FOREST_N2 &
                    state_id %in% c(0L, 1L)]
    x[, .(area_ha = sum(area_ha)), by = .(north, state_id, nivel2_post)][
      , `:=`(offset = PAT_LAGS[i], cohorte = if (fixed) "fija" else "móvil")][]
  }))
}

pat <- rbindlist(Filter(Negate(is.null), list(pat_read(FALSE), pat_read(TRUE))))
if (!nrow(pat)) {
  msg("[.] no están los lulc_change_eco13_y*_n44.csv — el caso patagónico se saltea")
} else {
  pat[, zona := ifelse(north == 1L, "norte de -44", "sur de -44")]

  # (a) la trayectoria: qué fracción DEJA DE SER BOSQUE en cada lag
  traj <- pat[, .(kha = sum(area_ha) / 1e3,
                  pct_sale = 100 * sum(area_ha[!nivel2_post %in% FOREST_N2]) / sum(area_ha)),
              by = .(cohorte, zona, offset, state_id)]
  q <- dcast(traj, cohorte + zona + offset ~ state_id, value.var = c("pct_sale", "kha"))
  setnames(q, c("pct_sale_0", "pct_sale_1", "kha_1"), c("control", "ardio", "kha_ardio"))
  q[, q_sale := ardio / control]
  wr(q[, .(cohorte, zona, offset, kha_ardio, ardio, control, q_sale)],
     "factsheet_patagonia_bosque.csv")

  # (b) a qué se convierte — sólo lo quemado, que es de lo que habla el resultado
  dest <- pat[state_id == 1L, .(area_ha = sum(area_ha)),
              by = .(cohorte, zona, offset, nivel2_post)]
  dest[, pct := 100 * area_ha / sum(area_ha), by = .(cohorte, zona, offset)]
  setorder(dest, cohorte, zona, offset, -area_ha)
  wr(dest, "factsheet_patagonia_destinos.csv")

  msg("")
  msg("bosques patagónicos al norte de -44: %% que deja de ser bosque")
  print(dcast(q[zona == "norte de -44"], offset ~ cohorte, value.var = "ardio")[
    , lapply(.SD, function(x) if (is.numeric(x)) round(x, 1) else x)])
}

# ── 6b. SÓLO BOSQUES, nacional, en las cuatro ventanas (docs/09 §5.9) ────────
# El mismo aparato del bloque patagónico —`pat_file()` lee los `_n44`, que son el PAÍS ENTERO
# con un bit norte/sur de más— pero sin filtrar por región y colapsando ese bit. Existe porque
# la pregunta "¿cuánto más probable es que un bosque deje de serlo si se quema?" es la que va a
# la lámina, y necesita cuatro cosas que las tablas del bloque 6 no dan juntas:
#
#   1. Y+4 e Y+5 NACIONALES. El análisis general sólo corre Y+1 e Y+3, pero los archivos
#      `_n44` de lags 4 y 5 son país entero, así que los cuatro lags ya están exportados y no
#      hace falta ninguna corrida nueva de GEE.
#   2. LA CLASE DE ORIGEN DE NIVEL 2, con "salir de la FAMILIA" como evento. Son dos ejes
#      distintos y hay que cruzarlos: "bosque cerrado deja de ser bosque cerrado" incluye
#      pasar a bosque abierto, que NO es perder el bosque. El evento que se reporta es
#      `nivel1_post != "Bosques"`, medido por clase de origen de nivel 2.
#   3. EL PROMEDIO DE LA FAMILIA ESCONDE EL RESULTADO. Medido, Y+1: bosque cerrado q = 14,0;
#      bosque abierto 2,2; bosque inundable **1,0**, es decir el fuego no le hace NADA
#      medible. La familia entera da 6,4, que es un promedio sobre tres sistemas que no se
#      comportan igual. Por eso la tabla trae las tres clases Y la familia, y nunca una sola.
#   4. LAS DOS COHORTES, por lo mismo que en el bloque patagónico: sin la ventana clavada,
#      cada lag mira años focales distintos y la serie Y+1..Y+5 no es una trayectoria.
if (!nrow(pat)) {
  msg("[.] sin los `_n44` tampoco sale el bloque de bosques nacional")
} else {
  bosq_read <- function(fixed) {
    fs_ <- vapply(PAT_LAGS, pat_file, "", fixed = fixed)
    if (anyNA(fs_)) return(NULL)
    rbindlist(lapply(seq_along(PAT_LAGS), function(i) {
      x <- rd(fs_[i])[!ecoregion_id %in% UNMAPPED_REGIONS & nivel1_prev == "Bosques" &
                      state_id %in% c(0L, 1L, 3L)]
      # el bit norte/sur se colapsa acá: este bloque es nacional
      x[, .(area_ha = sum(area_ha)),
        by = .(state_id, clase_prev = nivel2_prev, nivel1_post, nivel2_post)][
        , `:=`(offset = PAT_LAGS[i], cohorte = if (fixed) "fija" else "móvil")][]
    }))
  }
  bosq <- rbindlist(Filter(Negate(is.null), list(bosq_read(FALSE), bosq_read(TRUE))))
  bosq[, sale := nivel1_post != "Bosques"]

  # (a) el escalar: % que DEJA DE SER BOSQUE, con fuego y sin fuego, y q.
  # `q` compara los dos estados LIMPIOS (0 y 1), igual que en todo el análisis 6; el titular
  # "de lo quemado" son 1 + 3 y se guarda aparte para no mezclar las dos cuentas.
  esc <- function(d, by_cols) {
    a <- d[state_id %in% c(0L, 1L), .(area_ha = sum(area_ha),
                                      sale_ha = sum(area_ha[sale])), by = c(by_cols, "state_id")]
    a[, pct := 100 * sale_ha / area_ha]
    w <- dcast(a, as.formula(paste(paste(by_cols, collapse = " + "), "~ state_id")),
               value.var = c("pct", "area_ha"))
    setnames(w, c("pct_0", "pct_1", "area_ha_1"), c("control", "ardio", "ha_ardio"))
    b <- d[state_id %in% c(1L, 3L), .(ha_quemado = sum(area_ha),
                                      pct_quemado = 100 * sum(area_ha[sale]) / sum(area_ha)),
           by = by_cols]
    w[b, on = by_cols, `:=`(ha_quemado = i.ha_quemado, pct_quemado = i.pct_quemado)]
    w[, q_sale := ardio / control][]
  }
  por_clase  <- esc(bosq, c("cohorte", "offset", "clase_prev"))
  familia    <- esc(bosq, c("cohorte", "offset"))[, clase_prev := "Bosques (familia)"][]
  bosq_esc   <- rbind(por_clase, familia, use.names = TRUE)
  setcolorder(bosq_esc, c("cohorte", "offset", "clase_prev"))
  setorder(bosq_esc, cohorte, offset, -q_sale)
  wr(bosq_esc, "factsheet_bosques.csv")

  # (b) a dónde va el bosque quemado. Estados 1 + 3 (todo lo que ardió), porque es una
  # descripción de lo quemado y no una comparación contra el control.
  # SE GUARDA TAMBIÉN LO QUE SIGUE SIENDO BOSQUE (`sale == FALSE`), con dos porcentajes: el
  # Sankey de la lámina necesita el pool entero —la banda gruesa que permanece es la mitad de
  # la lectura— y la tabla de destinos necesita el reparto de lo que sale. Un solo archivo con
  # las dos columnas evita que las dos figuras salgan de cuentas distintas.
  bosq_dest <- bosq[state_id %in% c(1L, 3L),
                    .(area_ha = sum(area_ha)),
                    by = .(cohorte, offset, clase_prev, sale, nivel1_post, nivel2_post)]
  bosq_dest[, pct := 100 * area_ha / sum(area_ha), by = .(cohorte, offset, clase_prev)]
  bosq_dest[sale == TRUE, pct_sale := 100 * area_ha / sum(area_ha),
            by = .(cohorte, offset, clase_prev)]
  setorder(bosq_dest, cohorte, offset, clase_prev, -area_ha)
  wr(bosq_dest, "factsheet_bosques_destinos.csv")

  msg("")
  msg("bosques, nacional: %% que DEJA DE SER BOSQUE (cohorte móvil, cada lag su ventana)")
  print(dcast(bosq_esc[cohorte == "móvil"], clase_prev ~ offset,
              value.var = c("ardio", "q_sale"))[
        , lapply(.SD, function(x) if (is.numeric(x)) round(x, 1) else x)])
}

msg("")
print(scal[, .(ecoregion, quemable_Mha = round(burnable_ha / 1e6, 2),
               media_Mha_ano = round(mean_burned_ha / 1e6, 3),
               pct_medio = round(mean_pct, 2), b_rel_pct = round(100 * b_rel, 1),
               x_serie = round(trend_ratio, 2),
               pico = peak_month_area_name, ano_max = max_year)])
msg("done")
