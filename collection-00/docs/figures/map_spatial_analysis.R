# Packages
library(terra)
library(tidyterra)
library(ggplot2)
library(patchwork)
library(ggspatial)

# Load data
r <- rast("raster_for_map.tif")

prob     <- r[["prob"]]
candseed <- r[["candseed"]]
snic     <- r[["snic"]]
rgb      <- r[[c("red", "green", "blue")]]

# Color scales
pal_prob <- c(
  "#000004", "#1c1044", "#4f127b", "#812581",
  "#b5367a", "#e55063", "#fb8761", "#fec287"
)

pal_candseed <- c(
  "0" = "#000004",
  "1" = "#3b4cc0",
  "2" = "#f768a1"
)

pal_snic <- c(
  "0" = "#000004",
  "1" = "#3bceac"
)

# Common theme and scale bar
theme_map <- theme_minimal() +
  theme(
    axis.text = element_text(size = 6),
    
    legend.key.width  = unit(0.4, "cm"),
    legend.key.height = unit(0.4, "cm"),
    
    legend.position = "bottom",
    legend.box.margin = margin(t = -4, r = 0, b = 0, l = 0, unit = "mm"),
    legend.title = element_text(size = 8),
    legend.text  = element_text(size = 8),
    
    plot.title   = element_text(size = 9, hjust = 0)
  )

sb_white <- annotation_scale(
  location = "br",
  width_hint = 0.20,
  bar_cols = c("black", "white"),
  text_col = "white",
  text_cex = 0.65,
  line_col = "black",
  height = unit(0.1, "cm"),
  pad_x = unit(0.4, "cm"),
  pad_y = unit(0.4, "cm")
)

na_tri <- annotation_north_arrow(
  location = "tr",
  which_north = "true",
  style = north_arrow_fancy_orienteering(
    fill = c("black", "white"),
    line_col = "black",
    text_col = "white"
  ),
  height = unit(0.6, "cm"),
  width  = unit(0.6, "cm"),
  pad_x = unit(0.4, "cm"),
  pad_y = unit(0.4, "cm")
)


# Panels

p_sat <- ggplot() +
  geom_spatraster_rgb(
    data = rgb,
    stretch = "lin",
    maxcell = Inf
  ) +
  sb_white +
  na_tri +
  scale_x_continuous(n.breaks = 5) + 
  scale_y_continuous(n.breaks = 5) +
  labs(title = "(A) Imagen RGB (post-incendio)") +
  theme_map +
  theme(axis.text.x = element_blank())
# p_sat

p_prob <- ggplot() +
  geom_spatraster(data = prob) +
  scale_fill_gradientn(
    colours = pal_prob,
    limits = c(0, 1),
    na.value = "black",
    name = NULL,
    guide = guide_colorbar(
      barheight = unit(0.25, "cm"),
      barwidth  = unit(4, "cm"),
      ticks = FALSE
    )
  ) +
  scale_x_continuous(n.breaks = 5) + 
  scale_y_continuous(n.breaks = 5) +
  labs(title = "(B) Probabilidad de quema anual") +
  theme_map + 
  theme(axis.text = element_blank())
# p_prob

p_candseed <- ggplot() +
  geom_spatraster(data = as.factor(candseed)) +
  scale_fill_manual(
    values = c(
      "1" = "#3b4cc0",  # candidate
      "2" = "#f768a1"   # seed
    ),
    na.value = "black",
    name = "",
    breaks = c("2", "1"),
    labels = c("Semilla", "Candidato")
  ) +
  labs(title = "(C) Semillas y candidatos") +
  scale_x_continuous(n.breaks = 5) + 
  scale_y_continuous(n.breaks = 5) +
  theme_map
# p_candseed

p_snic <- ggplot() +
  geom_spatraster(data = as.factor(snic)) +
  scale_fill_manual(
    values = c(
      "1" = "#3bceac"
    ),
    na.value = "black",
    name = ""
  ) +
  labs(title = "(D) Grupos de píxeles quemados") +
  scale_x_continuous(n.breaks = 5) + 
  scale_y_continuous(n.breaks = 5) +
  theme_map + 
  theme(
    legend.position = "none",
    axis.text.y = element_blank()
  )
# p_snic

# Assemble with patchwork
final_plot <-
  (p_sat | p_prob) /
  (p_candseed | p_snic)

# final_plot

# Export
ggsave(
  "spatial_analysis.png", final_plot,
  width = 15, height = 14, dpi = 300, units = "cm"
)