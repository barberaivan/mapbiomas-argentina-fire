# ---------------------------------------------------------------------------
# ATBD figure: the region-growing step, illustrated.
#
# Four panels over the Collection 0 pilot window (Rio Turbio and Cholila,
# Chubut), but all four are now Collection 1's own layers -- fire-year 2014,
# the fire-year that holds the February 2015 fires. The raster is built by
# `export_spatial_figure_raster.py`, which pulls every band from the Collection 1
# assets and pins them to the production SNIC lattice.
#
#   (A) RED/GREEN/BLUE   post-fire Landsat median, Dec 2015 - Feb 2016
#   (B) delta2_peak      the fire-year's change in burn probability
#   (C) candseed         pre-SNIC seeds and candidates
#   (D) snic             the seed-grown burned region
#
# Reflectance and delta2_peak arrive as int16 scaled by 10000 (the bpts
# encoding); this script divides. Panel (C) has two classes, not three: the
# Patagonian dieback padding (candseed 3) is folded into the candidates by the
# export, because that is what it is by the time SNIC has run.
#
# Run from this directory:  Rscript make_spatial_figure.R
# Writes: spatial_analysis.png
# ---------------------------------------------------------------------------

# tidyterra and ggspatial are installed in the SITE library, but R searches the user
# library first, so an older user-library copy of a shared dependency (dplyr, tidyr)
# shadows the newer one they require and the load fails. Prefer the site library; the
# user library stays on the path as a fallback for anything only installed there.
.libPaths(c(.Library.site, .libPaths()))

suppressPackageStartupMessages({
  library(terra); library(tidyterra); library(ggplot2)
  library(patchwork); library(ggspatial)
})

SRC <- "raster_for_map_c01.tif"
if (!file.exists(SRC)) {
  stop("missing ", SRC, " -- run: $PYTHON export_spatial_figure_raster.py")
}
r <- rast(SRC)

SCALE <- 10000  # int16 encoding of reflectance and delta2_peak

delta    <- r[["delta2_peak"]] / SCALE
candseed <- r[["candseed"]]
snic     <- r[["snic"]]
rgb      <- r[[c("RED", "GREEN", "BLUE")]] / SCALE

pal_delta <- c("#000004", "#1c1044", "#4f127b", "#812581",
               "#b5367a", "#e55063", "#fb8761", "#fec287")

theme_map <- theme_minimal() +
  theme(
    axis.text         = element_text(size = 6),
    legend.key.width  = unit(0.4, "cm"),
    legend.key.height = unit(0.4, "cm"),
    legend.position   = "bottom",
    legend.box.margin = margin(t = -4, r = 0, b = 0, l = 0, unit = "mm"),
    legend.title      = element_text(size = 8),
    legend.text       = element_text(size = 8),
    plot.title        = element_text(size = 9, hjust = 0)
  )

sb_white <- annotation_scale(
  location = "br", width_hint = 0.20,
  bar_cols = c("black", "white"), text_col = "white", text_cex = 0.65,
  line_col = "black", height = unit(0.1, "cm"),
  pad_x = unit(0.4, "cm"), pad_y = unit(0.4, "cm")
)

na_tri <- annotation_north_arrow(
  location = "tr", which_north = "true",
  style = north_arrow_fancy_orienteering(
    fill = c("black", "white"), line_col = "black", text_col = "white"),
  height = unit(0.6, "cm"), width = unit(0.6, "cm"),
  pad_x = unit(0.4, "cm"), pad_y = unit(0.4, "cm")
)

p_sat <- ggplot() +
  geom_spatraster_rgb(data = rgb, stretch = "lin", maxcell = Inf) +
  sb_white + na_tri +
  scale_x_continuous(n.breaks = 5) + scale_y_continuous(n.breaks = 5) +
  labs(title = "(A) RGB image (post-fire)") +
  theme_map + theme(axis.text.x = element_blank())

p_delta <- ggplot() +
  geom_spatraster(data = delta, maxcell = Inf) +
  scale_fill_gradientn(
    colours = pal_delta, limits = c(0, 1), na.value = "black", name = NULL,
    guide = guide_colorbar(barheight = unit(0.25, "cm"),
                           barwidth = unit(4, "cm"), ticks = FALSE)) +
  scale_x_continuous(n.breaks = 5) + scale_y_continuous(n.breaks = 5) +
  labs(title = "(B) Change in burn probability") +
  theme_map + theme(axis.text = element_blank())

p_candseed <- ggplot() +
  geom_spatraster(data = as.factor(candseed), maxcell = Inf) +
  scale_fill_manual(
    values = c("1" = "#3b4cc0", "2" = "#f768a1"),
    na.value = "black", name = "",
    breaks = c("2", "1"), labels = c("Seed", "Candidate")) +
  labs(title = "(C) Seeds and candidates") +
  scale_x_continuous(n.breaks = 5) + scale_y_continuous(n.breaks = 5) +
  theme_map

p_snic <- ggplot() +
  geom_spatraster(data = as.factor(snic), maxcell = Inf) +
  scale_fill_manual(values = c("1" = "#3bceac"), na.value = "black", name = "") +
  labs(title = "(D) Burned-pixel clusters") +
  scale_x_continuous(n.breaks = 5) + scale_y_continuous(n.breaks = 5) +
  theme_map + theme(legend.position = "none", axis.text.y = element_blank())

final_plot <- (p_sat | p_delta) / (p_candseed | p_snic)

ggsave("spatial_analysis.png", final_plot,
       width = 15, height = 14, dpi = 300, units = "cm")
message("wrote spatial_analysis.png")
