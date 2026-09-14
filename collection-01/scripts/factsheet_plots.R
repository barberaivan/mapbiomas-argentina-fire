#!/usr/bin/env Rscript
# =============================================================================
# collection-01/scripts/factsheet_plots.R
#
# The factsheet's MULTI-REGION figures (factsheet-notes.md, analyses 2 and 4):
# per-region temporal SHAPE, with the magnitude normalised away so that the
# Patagonia is not a flat line squashed against zero next to the Chaco.
#
# Produces, for each of the two analyses, an `all` panel plus one focal panel
# per region, and the little Argentina map that serves as the legend — each map
# written as its OWN file, because the designer places it separately.
#
#   intraanual_all.pdf        all regions, % of each region's burned area by month
#   intraanual_focal_<id>.pdf one region in colour, the rest in grey
#   interanual_all.pdf        all regions, burned area / region's own mean, by fire year
#   interanual_focal_<id>.pdf idem
#   mapa_all.pdf              13 polygons, each in its line's colour
#   mapa_focal_<id>.pdf       grey country, focal polygon in its colour
#
# INPUT is the OBJECT-based table, i.e. FIRE YEAR and month = month of the
# polygon's `date_median`, so a whole fire's area lands in a single month. That
# is not the published per-pixel number and the two will not add up — say which
# one a figure came from (factsheet_object_stats.R header, and analysis 4).
#
# Parameters, all environment variables:
#   TAG      counts-table tag           (default min10ha — factsheet analysis 3)
#   LAYER    territory set              (default ecoregions13)
#   VALUE    area_ha | n_fires          (default area_ha)
#   FIG_DIR  output directory           (default data/objects-analysis/factsheet-figures)
#
# Usage (from the repo ROOT):
#   Rscript collection-01/scripts/factsheet_plots.R
#   VALUE=n_fires TAG=min50ha Rscript collection-01/scripts/factsheet_plots.R
# =============================================================================

source("collection-01/scripts/factsheet_plot_functions.R")

ANA_DIR <- "collection-01/data/objects-analysis"
ANC_GEO <- "collection-01/data/ancillary/ecoregions13.geojson"

TAG     <- Sys.getenv("TAG", "min10ha")
LAYER   <- Sys.getenv("LAYER", "ecoregions13")
VALUE   <- Sys.getenv("VALUE", "area_ha")
FIG_DIR <- Sys.getenv("FIG_DIR", file.path(ANA_DIR, "factsheet-figures"))

VALUE_LABEL <- c(area_ha = "área quemada", n_fires = "cantidad de incendios")[VALUE]
if (is.na(VALUE_LABEL)) stop("VALUE must be area_ha or n_fires, got '", VALUE, "'")

# Figure sizes, in inches, designed at the width they are placed at: the deck is
# 720 x 405 pt, so a half-slide plot is ~4.5 in wide. CONTEXT-typst.md §figures
# fixes VECTOR output, hence cairo_pdf — which also embeds the accents in
# "Bosques Patagónicos" correctly, where the default pdf() device does not.
W_LINE <- 4.5; H_LINE <- 2.8
W_MAP  <- 2.0; H_MAP  <- 3.4

save_fig <- function(p, name, w, h) {
  f <- file.path(FIG_DIR, paste0(name, ".pdf"))
  ggsave(f, p, width = w, height = h, device = cairo_pdf)
  f
}

# ── inputs ───────────────────────────────────────────────────────────────────
counts_f <- file.path(ANA_DIR, sprintf("factsheet_counts_by_month_%s.csv", TAG))
if (!file.exists(counts_f))
  stop("no counts table at ", counts_f, "\n",
       "  Run scripts/objects_region_tag.R, then scripts/factsheet_object_stats.R",
       if (TAG != "min10ha") sprintf(" with MIN_HA/AGRI_MAX giving TAG=%s", TAG) else "",
       ".", call. = FALSE)

msg("TAG = %s   LAYER = %s   VALUE = %s", TAG, LAYER, VALUE)
counts <- fread(counts_f)
eco <- load_eco13(ANC_GEO)
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

dm <- norm_month(counts, LAYER, VALUE)
dy <- norm_year(counts, LAYER, VALUE)

# ── the two invariants ───────────────────────────────────────────────────────
# If either of these drifts, every figure below is quietly wrong, so check them
# before writing anything rather than eyeballing the curves afterwards.
bad_m <- dm[, .(s = sum(pct)), by = region_id][abs(s - 100) > 1e-6]
bad_y <- dy[, .(m = mean(ratio)), by = region_id][abs(m - 1) > 1e-6]
if (nrow(bad_m)) stop("monthly curves do not sum to 100 %: region(s) ",
                      paste(bad_m$region_id, collapse = ", "), call. = FALSE)
if (nrow(bad_y)) stop("annual series do not have mean 1: region(s) ",
                      paste(bad_y$region_id, collapse = ", "), call. = FALSE)

regions <- sort(intersect(unique(dm$region_id), eco$region_id))
msg("%d regions, fire years %d-%d", length(regions),
    min(dy$fire_year), max(dy$fire_year))

# ── all-regions panels ───────────────────────────────────────────────────────
save_fig(plot_intraanual(dm, value_label = VALUE_LABEL), "intraanual_all", W_LINE, H_LINE)
save_fig(plot_interanual(dy, value_label = VALUE_LABEL), "interanual_all", W_LINE, H_LINE)
save_fig(region_map(eco), "mapa_all", W_MAP, H_MAP)

# ── focal panels, one set per region ─────────────────────────────────────────
for (r in regions) {
  save_fig(plot_intraanual(dm, focal = r, value_label = VALUE_LABEL),
           sprintf("intraanual_focal_%02d", r), W_LINE, H_LINE)
  save_fig(plot_interanual(dy, focal = r, value_label = VALUE_LABEL),
           sprintf("interanual_focal_%02d", r), W_LINE, H_LINE)
  save_fig(region_map(eco, focal = r), sprintf("mapa_focal_%02d", r), W_MAP, H_MAP)
}

msg("[out] %s  (%d files)", FIG_DIR, 3 + 3 * length(regions))

# The month each region peaks in — the scalar version of analysis 4, and the
# number a caption quotes. Printed rather than written: it is a sentence for a
# slide, not a table anyone joins against.
peak <- dm[, .(mes_pico = month[which.max(pct)], pct_pico = round(max(pct), 1)),
           by = .(region_id, region_name)]
setorder(peak, -pct_pico)
print(peak)
msg("done")
