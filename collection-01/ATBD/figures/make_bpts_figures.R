# ---------------------------------------------------------------------------
# ATBD figures: the burn-probability time-series metrics, schematically.
#
# English port of the two panels of
#   collection-01/notebooks/bpts_metrics_explained.qmd
# (originally written in Spanish to explain step 03 to the team). Same synthetic
# series, same seed, same geometry; only the labels and the titles are translated.
#
# Run from this directory:  Rscript make_bpts_figures.R
# Writes: bpts_metrics_k3.png, bpts_metrics_k2.png
# ---------------------------------------------------------------------------

suppressPackageStartupMessages({
  library(tidyverse)
})

theme_burn <- function(base_size = 16) {
  theme_minimal(base_size = base_size) +
    theme(
      strip.text.x       = element_text(face = "bold", size = base_size,
                                        margin = margin(b = 6)),
      panel.spacing      = unit(1.1, "lines"),
      panel.grid.minor   = element_blank(),
      panel.grid.major.x = element_blank(),
      panel.grid.major.y = element_line(colour = "grey90", linewidth = 0.35),
      axis.line          = element_line(colour = "grey50", linewidth = 0.4),
      plot.title         = element_text(face = "bold", size = base_size + 2,
                                        margin = margin(b = 6)),
      plot.subtitle      = element_text(size = base_size - 3, colour = "grey45",
                                        margin = margin(b = 8)),
      legend.position    = "top"
    )
}
theme_set(theme_burn())

# --- synthetic series: many zeros -> jump -> many ~1, with a little noise -----
set.seed(7)
n     <- 20
doy   <- round(seq(15, 355, length.out = n))   # ~18 d apart
base  <- c(rep(0, 10), rep(1, 10))             # clean step
noise <- rnorm(n, 0, 0.045)
p     <- pmin(pmax(base + noise, 0), 1)

tstar <- 11L
arr   <- arrow(length = unit(0.11, "inches"), ends = "both", type = "closed")
col_prev <- "#2C7FB8"; col_post <- "#D95F0E"

make_panel <- function(K, outfile) {

  prev_idx <- (tstar - K):(tstar - 1L)
  post_idx <- tstar:(tstar + K - 1L)

  maxback   <- max(p[prev_idx])
  minfore   <- min(p[post_idx])
  delta     <- minfore - maxback
  jumpgap   <- doy[tstar] - doy[tstar - 1L]
  prevwidth <- doy[tstar - 1L] - doy[tstar - K]
  postwidth <- doy[tstar + K - 1L] - doy[tstar]
  date_post <- doy[tstar] + 1L

  lab_prev <- sprintf("back window (K = %d)", K)
  lab_post <- sprintf("fore window (K = %d)", K)

  role <- rep("other", n)
  role[prev_idx] <- lab_prev
  role[post_idx] <- lab_post
  role <- factor(role, levels = c(lab_prev, lab_post, "other"))

  panel_levels <- c(
    sprintf("A - The jump:  delta%d_peak, minfore%d_peak, maxback%d, jumpgap%d",
            K, K, K, K),
    sprintf("B - The time windows:  prevwidth%d, postwidth%d, date_post%d",
            K, K, K)
  )
  pA <- panel_levels[1]; pB <- panel_levels[2]

  df <- tidyr::crossing(
    panel = factor(panel_levels, levels = panel_levels),
    tibble(doy = doy, p = p, role = role)
  )

  # ---- panel A: level segments, the jump (delta) and the jumpgap ------------
  segA <- tibble(
    panel = factor(c(pA, pA), levels = panel_levels),
    x     = c(doy[prev_idx[1]], doy[post_idx[1]]),
    xend  = c(doy[prev_idx[K]], doy[post_idx[K]]),
    y     = c(maxback, minfore), yend = c(maxback, minfore)
  )
  x_delta <- doy[post_idx[K]]
  arrA <- tibble(panel = factor(pA, levels = panel_levels),
                 x = x_delta, xend = x_delta, y = maxback, yend = minfore)
  guiaA <- tibble(panel = factor(pA, levels = panel_levels),
                  x = doy[prev_idx[K]], xend = x_delta,
                  y = maxback, yend = maxback)
  arrA_gap <- tibble(panel = factor(pA, levels = panel_levels),
                     x = doy[tstar - 1L], xend = doy[tstar], y = 0.5, yend = 0.5)

  txtA <- tibble(
    panel = factor(pA, levels = panel_levels),
    x = c(mean(doy[prev_idx]), mean(doy[post_idx]), x_delta + 6,
          (doy[tstar - 1L] + doy[tstar]) / 2),
    y = c(-0.09, minfore + 0.08, (maxback + minfore) / 2, 0.42),
    label = c(sprintf("maxback%d", K), sprintf("minfore%d", K),
              sprintf("delta%d_peak\n= %.2f", K, delta),
              sprintf("jumpgap%d\n= %d d", K, jumpgap)),
    hjust = c(0.5, 0.5, 0, 0.5)
  )

  # ---- panel B: window widths and date_post --------------------------------
  arrB <- tibble(
    panel = factor(c(pB, pB), levels = panel_levels),
    x     = c(doy[prev_idx[1]], doy[post_idx[1]]),
    xend  = c(doy[prev_idx[K]], doy[post_idx[K]]),
    y     = c(maxback + 0.12, minfore - 0.12),
    yend  = c(maxback + 0.12, minfore - 0.12)
  )
  vlineB <- tibble(panel = factor(pB, levels = panel_levels), x = date_post)
  txtB <- tibble(
    panel = factor(c(pB, pB, pB), levels = panel_levels),
    x = c(mean(doy[prev_idx]) - 6, mean(doy[post_idx]) + 6, date_post + 4),
    y = c(maxback + 0.21, minfore - 0.21, 0.30),
    label = c(sprintf("prevwidth%d = %d d", K, prevwidth),
              sprintf("postwidth%d = %d d", K, postwidth),
              sprintf("date_post%d = DOY %d", K, date_post)),
    hjust = c(1, 0, 0)
  )

  fills <- setNames(c(col_prev, col_post, "grey80"),
                    c(lab_prev, lab_post, "other"))
  sizes <- setNames(c(3.2, 3.2, 2.0), c(lab_prev, lab_post, "other"))

  g <- ggplot(df, aes(doy, p)) +
    geom_hline(yintercept = 0, colour = "grey85", linewidth = 0.35) +
    geom_segment(data = guiaA, aes(x = x, xend = xend, y = y, yend = yend),
                 linetype = "dotted", colour = "grey55", linewidth = 0.5) +
    geom_segment(data = segA, aes(x = x, xend = xend, y = y, yend = yend),
                 colour = "grey20", linewidth = 1.1) +
    geom_segment(data = arrA, aes(x = x, xend = xend, y = y, yend = yend),
                 arrow = arr, colour = "#B30000", linewidth = 0.8) +
    geom_segment(data = arrA_gap, aes(x = x, xend = xend, y = y, yend = yend),
                 arrow = arr, colour = "#6A51A3", linewidth = 0.8) +
    geom_vline(data = vlineB, aes(xintercept = x),
               linetype = "dashed", colour = "#1B7837", linewidth = 0.7) +
    geom_segment(data = arrB, aes(x = x, xend = xend, y = y, yend = yend),
                 arrow = arr, colour = "grey20", linewidth = 0.8) +
    geom_line(colour = "grey55", linewidth = 0.55) +
    geom_point(aes(fill = role, size = role), shape = 21, colour = "grey25",
               stroke = 0.5) +
    geom_text(data = txtA, aes(x = x, y = y, label = label, hjust = hjust),
              size = 3.7, lineheight = 0.9, colour = "grey15") +
    geom_text(data = txtB, aes(x = x, y = y, label = label, hjust = hjust),
              size = 3.7, lineheight = 0.9, colour = "grey15") +
    facet_wrap(~ panel, ncol = 1) +
    scale_fill_manual(name = NULL, values = fills) +
    scale_size_manual(guide = "none", values = sizes) +
    scale_x_continuous(breaks = c(1, 91, 182, 274, 365)) +
    scale_y_continuous(limits = c(-0.15, 1.15), breaks = c(0, 0.5, 1)) +
    labs(
      x = "Day of year",
      y = "Burn probability",
      title = sprintf("K = %d metrics on a burn-probability series", K),
      subtitle = sprintf(paste0(
        "Same series in both panels (t* = the observation of maximum jump). ",
        "Blue = back window (%d obs), orange = fore window (%d obs)."), K, K)
    )

  ggsave(outfile, g, width = 12, height = 11, dpi = 160)
  message("wrote ", outfile)
}

make_panel(3, "bpts_metrics_k3.png")
make_panel(2, "bpts_metrics_k2.png")
