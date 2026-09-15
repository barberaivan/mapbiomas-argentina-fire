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

K_TREND  <- 5      # docs/10 análisis 2 — a few bases, a smooth decadal shape
# docs/10 análisis 3 asks for k = 12, so that the curve FOLLOWS the 12 summary
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
  area <- rd("lulc_area_eco13.csv")[!ecoregion_id %in% UNMAPPED_REGIONS &
                                    !nivel1 %in% "No observado"]
  burned <- lulc[!nivel1 %in% "No observado"]

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
# análisis 3); it comes from the polygons and is filed whole into the month of
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
# The intra-annual SHAPES (docs/10 análisis 4): each region's 12 months sum to
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
# what makes it do that (docs/10 análisis 3).
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
  out
}), fill = TRUE)
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
N1_COL <- c("Bosques"                                 = "share_bosques",
            "Vegetación natural herbácea y arbustiva" = "share_herb_arbust",
            "Áreas de uso agropecuario"               = "share_agro",
            "Áreas sin vegetación"                    = "share_no_veg",
            "Cuerpos de agua"                         = "share_agua")
n1 <- lulc_share[level == "nivel1"]
stopifnot(all(n1$clase %in% names(N1_COL)))
n1 <- dcast(n1, ecoregion_id ~ N1_COL[clase], value.var = "share", fill = 0)
scal[n1, on = "ecoregion_id",
     (setdiff(names(n1), "ecoregion_id")) := mget(paste0("i.", setdiff(names(n1), "ecoregion_id")))]

fs <- rd("fire_region_summary.csv")[!ecoregion_id %in% UNMAPPED_REGIONS]
scal[fs, on = "ecoregion_id",
     `:=`(fires_per_year = i.fires_per_year, median_ha = i.median_ha,
          p95_ha = i.p95_ha, biggest_fire_ha = i.max_ha,
          fires_ge10_per_10kkm2 = i.fires_per_year_per_10kkm2)]
scal <- merge(scal, rbind(meta[, .(ecoregion_id, lat, lon, area_km2, palette_order)],
                          data.table(ecoregion_id = 0L, lat = NA_real_, lon = NA_real_,
                                     area_km2 = sum(meta$area_km2), palette_order = 0L)),
              by = "ecoregion_id")
setorder(scal, -mean_pct)
wr(scal, "factsheet_region_scalars.csv")

msg("")
print(scal[, .(ecoregion, quemable_Mha = round(burnable_ha / 1e6, 2),
               media_Mha_ano = round(mean_burned_ha / 1e6, 3),
               pct_medio = round(mean_pct, 2), b_rel_pct = round(100 * b_rel, 1),
               x_serie = round(trend_ratio, 2),
               pico = peak_month_area_name, ano_max = max_year)])
msg("done")
