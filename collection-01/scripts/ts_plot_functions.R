# collection-01/scripts/ts_plot_functions.R
#
# Shared per-fire plotting function for the time-series diagnostic figures.
# plot_fire_panel() builds one patchwork object for a single fire: two
# vertically-faceted blocks (by `variable`, not by burn_class — burn_class is
# color-only here) stacked with patchwork, since they need different y-axis
# behavior that a single facet_grid() can't express in one call:
#   - index block:       NBR / NBR2          -- free y-axis per row
#   - probability block: P_raw / P_smoothMedian5 -- fixed y-axis, always 0-1,
#                         with a soft reference gridline at 0.5
# Both blocks get monthly x-axis breaks/gridlines. The aesthetic (colors, thin
# per-point lines + bold per-burn_class median line+point) mirrors the top two
# panels of collection-00/data_viz_Lican/functions.R::plot_tempseg(). The bold
# median point is swapped for a red asterisk on dates whose obs were held out
# of fitting (`fit == FALSE` in training_observations) -- the median line
# stays color-by-burn_class throughout.
#
# dt_fire must already be filtered to one region_fire_id, so each fire's date
# axis is naturally bounded to its own observations (no shared x-axis across
# fires). Consumed by ts_plot_by_fire.R (one PNG per fire).

suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
  library(patchwork)
})

CLASS_COLORS <- c(Burned = "#FFB90F", Unburned = "#1E90FF",
                   Burned_avg = "#EE4000", Unburned_avg = "#104E8B")

nice_ts_theme <- function() {
  theme_classic(base_size = 11) +
    theme(panel.border = element_blank(),
          panel.grid.minor = element_blank(),
          panel.grid.major.y = element_blank(),
          panel.grid.major.x = element_line(linewidth = 0.15, color = "grey85"),
          axis.line = element_line(linewidth = 0.35),
          axis.text = element_text(size = 9),
          axis.text.x = element_text(angle = 45, hjust = 1),
          axis.title = element_text(size = 10),
          strip.text = element_text(size = 10),
          strip.background = element_blank(),
          strip.text.y = element_text(angle = 0),
          legend.position = "bottom",
          legend.title = element_blank(),
          legend.key.size = unit(0.6, "lines"),
          legend.text = element_text(size = 8))
}

# Long-format (date, point_id, burn_class, fit, variable, value, avg, fit_avg)
# for a set of columns of dt_fire. vars_map: named list, display name ->
# column name, e.g. list(NBR = "NBR", NBR2 = "NBR2"). avg = per (date,
# burn_class, variable) cross-point median, for the bold line/point.
# fit_avg = whether the obs feeding that median come from the fitting split
# (TRUE) or were held out (FALSE) -- a date's points are always uniformly one
# or the other, so all() correctly recovers that per-date status.
ts_long <- function(dt_fire, vars_map) {
  long <- rbindlist(lapply(names(vars_map), function(nm) {
    sub <- dt_fire[, .(date, point_id, burn_class, fit, value = get(vars_map[[nm]]))]
    sub[, variable := nm]
    sub
  }))
  long[, variable := factor(variable, levels = names(vars_map))]
  avg <- long[, .(avg = median(value, na.rm = TRUE), fit_avg = all(fit)),
              by = .(date, burn_class, variable)]
  merge(long, avg, by = c("date", "burn_class", "variable"), all.x = TRUE)
}

# Pre/post-fire window shading (rects) + boundary lines (dashed vlines) for
# one fire, mirroring collection-00/data_viz_Lican/functions.R's
# dates_burn/dates_unburn zones. burn_class is now a point identity (see
# ts_plot_cache.R), so these zones are no longer split by burn_class either —
# one consistent set of zones per fire. post_upr uses post_upr_short for
# grassland classes (faster regrowth), post_upr_long otherwise, matching the
# reference's veg_type branch. Returns list() if window dates are unavailable.
window_layers <- function(dt_fire) {
  w <- unique(dt_fire[, .(pre_lwr, pre_upr, post_lwr, post_upr_long, post_upr_short, veg_fire_name)])[1]
  if (is.na(w$pre_upr) || is.na(w$post_lwr)) return(list())
  w[, post_upr := if (grepl("^grassland", veg_fire_name)) post_upr_short else post_upr_long]

  list(
    geom_rect(data = w, aes(xmin = pre_lwr, xmax = pre_upr, ymin = -Inf, ymax = Inf),
              inherit.aes = FALSE, fill = "#104E8B", alpha = 0.15),
    geom_rect(data = w, aes(xmin = post_lwr, xmax = post_upr, ymin = -Inf, ymax = Inf),
              inherit.aes = FALSE, fill = "#EE4000", alpha = 0.15),
    geom_vline(data = w, aes(xintercept = pre_upr),
               linetype = "dashed", linewidth = 0.3, color = "grey40"),
    geom_vline(data = w, aes(xintercept = post_lwr),
               linetype = "dashed", linewidth = 0.3, color = "grey40"),
    geom_vline(data = w, aes(xintercept = post_upr),
               linetype = "dashed", linewidth = 0.3, color = "grey40")
  )
}

# One vertically-faceted (by variable) block, color-mapped by burn_class only
# (no facet on burn_class). y_limits = NULL -> free y-axis per row; a numeric
# pair (e.g. c(0, 1)) -> fixed/shared y-axis across rows, with a soft
# reference line at the midpoint.
ts_block <- function(dt_fire, vars_map, y_limits = NULL) {
  d <- ts_long(dt_fire, vars_map)
  d[, burn_class_avg := paste0(burn_class, "_avg")]

  p <- ggplot(d, aes(date, value, color = burn_class))
  for (ly in window_layers(dt_fire)) p <- p + ly
  if (!is.null(y_limits)) {
    p <- p + geom_hline(yintercept = mean(y_limits), color = "grey80", linewidth = 0.3)
  }
  p <- p +
    geom_line(aes(group = point_id), alpha = 0.5, linewidth = 0.1) +
    geom_line(aes(y = avg, color = burn_class_avg), alpha = 0.8, linewidth = 0.8,
               show.legend = FALSE) +
    geom_point(data = d[fit_avg == TRUE], aes(y = avg, color = burn_class_avg),
               alpha = 0.8, size = 1.2, show.legend = FALSE) +
    geom_point(data = d[fit_avg == FALSE], aes(y = avg),
               color = "red", shape = 8, size = 1.5, show.legend = FALSE) +
    scale_color_manual(values = CLASS_COLORS, breaks = c("Burned", "Unburned")) +
    facet_grid(rows = vars(variable), scales = if (is.null(y_limits)) "free_y" else "fixed") +
    scale_x_date(date_breaks = "1 month", date_labels = "%b %Y") +
    labs(x = NULL, y = NULL) +
    nice_ts_theme()
  if (!is.null(y_limits)) p <- p + coord_cartesian(ylim = y_limits)
  p
}

# Full panel for one fire: index block (NBR/NBR2, free y) over probability
# block (P_raw/P_smoothMedian5, fixed 0-1 y), patchwork-stacked.
plot_fire_panel <- function(dt_fire, title = NULL) {
  block_idx  <- ts_block(dt_fire, list(NBR = "NBR", NBR2 = "NBR2"))
  block_prob <- ts_block(dt_fire, list(P_raw = "p_pred", P_smoothMedian5 = "p_pred_smooth"),
                          y_limits = c(0, 1))

  (block_idx / block_prob) +
    plot_annotation(title = title,
                     theme = theme(plot.title = element_text(hjust = 0.5, size = 11)))
}
