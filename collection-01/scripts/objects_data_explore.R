#!/usr/bin/env Rscript
# =============================================================================
# objects_data_explore.R — step-06 data exploration: size limits + the c-00 filter
# =============================================================================
# Two questions, answered on two tables:
#
#   [FULL]   every step-05 object of every fire-year (raster + shape metrics joined on
#            oid, ~1.69 M rows) — the size distribution, i.e. where a hard `area_ha`
#            cut could go and what it would actually cost in objects and in area.
#   [TAGGED] the CLEAN labelled table (scripts/objects_data_functions.R::clean_tagged,
#            the exact table workflow/06-object_model.R fits on) — how fire and non-fire
#            separate by size and by the four metrics the collection-00 filter uses.
#
# and then the empirical filter itself (collection-00/workflow/08-object_based_filtering.js,
# reproduced in objects_data_functions.R::c00_pass):
#   * how it SPLITS THE TAGGED DATA — confusion vs the labels, overall and per size case,
#     so its errors are attributable to a case and a threshold, not to "the filter";
#   * how it CHANGES THE FULL TABLE — objects and area retained, overall and per year.
#
# Run from the repo ROOT (~1-2 min, ~4 GB peak for the full table):
#   Rscript collection-01/scripts/objects_data_explore.R [year ...]
#     year…  restrict the FULL table to these fire-years (default: all of them)
#
# Writes CSVs + PNGs to collection-01/data/objects-explore/ and prints every table.
# Nothing here is a pipeline step — it exists to choose the cuts that step 06 will use.
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
  library(patchwork)
})
source("collection-01/scripts/objects_data_functions.R")

OUT_DIR <- "collection-01/data/objects-explore"
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

argv  <- commandArgs(trailingOnly = TRUE)
years <- if (length(argv)) as.integer(argv) else object_years()

msg <- function(...) write(sprintf(...), stderr())
hdr <- function(s) { msg(""); msg("== %s ==", s) }
show <- function(x, file = NULL) {
  print(x)
  if (!is.null(file)) fwrite(x, file.path(OUT_DIR, file), na = "NA")
  invisible(x)
}
theme_set(theme_bw(base_size = 9))

# ── [1] FULL table ───────────────────────────────────────────────────────────
hdr("FULL object table")
t0   <- Sys.time()
full <- read_all_objects(years)
msg("%d objects, %d fire-year(s), loaded in %.0f s (%.1f GB in memory)",
    nrow(full), length(years), as.numeric(difftime(Sys.time(), t0, units = "secs")),
    as.numeric(object.size(full)) / 1024^3)
full[, case := c00_case(full)]

show(full[, .(objects = .N, area_kha = sum(area_ha) / 1e3,
              px1 = sum(n_pixels == 1L), area_max_ha = max(area_ha),
              na_seed = sum(is.na(seed_mean))), by = fire_year][order(fire_year)],
     "full_by_year.csv")

hdr("area_ha distribution (FULL)")
qs <- c(.01, .05, .1, .25, .5, .75, .9, .95, .99, .999, 1)
show(data.table(q = qs, area_ha = quantile(full$area_ha, qs)), "full_area_quantiles.csv")

# The size-limit table: what a "drop everything below t" rule removes. The area column is
# what matters for a burned-area product — dropping 60 % of the OBJECTS can cost <1 % of
# the AREA, which is the whole argument for the small-object cut (docs/06).
hdr("candidate lower size cuts (FULL)")
thr  <- c(0.09, 0.18, 0.27, 0.45, 0.9, 1, 2, 5, 10, 25, 50, 100, 300)
tot_n <- nrow(full); tot_a <- sum(full$area_ha)
show(data.table(cut_ha = thr)[, .(
  cut_ha,
  n_below      = vapply(thr, function(t) sum(full$area_ha < t), numeric(1)),
  pct_objects  = vapply(thr, function(t) 100 * mean(full$area_ha < t), numeric(1)),
  area_below_ha = vapply(thr, function(t) sum(full$area_ha[full$area_ha < t]), numeric(1)),
  pct_area     = vapply(thr, function(t) 100 * sum(full$area_ha[full$area_ha < t]) / tot_a, numeric(1)),
  n_kept       = vapply(thr, function(t) sum(full$area_ha >= t), numeric(1)))],
  "full_size_cuts.csv")
msg("(total: %d objects, %.0f ha)", tot_n, tot_a)

hdr("the 10 largest objects (FULL) — dilation-bridged complexes, see docs/05 §2")
show(full[order(-area_ha)][1:10, .(oid, area_ha, n_pixels, seed_mean, convexity,
                                   shape_index, burned_around_3)], "full_largest.csv")

# ── [2] TAGGED clean table ───────────────────────────────────────────────────
hdr("TAGGED clean table")
tag <- clean_tagged()
tag[, case := c00_case(tag)]
show(tag[, .(objects = .N, fire = sum(class == 1L), nonfire = sum(class == 0L),
             p_fire = mean(class == 1L)), by = fire_year][order(fire_year)],
     "tagged_by_year.csv")

hdr("P(fire | size) — TAGGED  (does a size cut alone separate the classes?)")
brk <- c(0, 0.09, 0.27, 0.9, 1, 2, 5, 10, 50, 100, 300, 1000, Inf)
tag[, area_bin := cut(area_ha, brk, right = FALSE, dig.lab = 4)]
show(tag[, .(n = .N, fire = sum(class == 1L), nonfire = sum(class == 0L),
             p_fire = round(mean(class == 1L), 3)), by = area_bin][order(area_bin)],
     "tagged_p_fire_by_size.csv")
msg("area_ha by class:")
show(tag[, as.list(round(quantile(area_ha, c(.05, .25, .5, .75, .95)), 3)), by = class][order(class)])

# ── [3] the collection-00 filter ON THE TAGGED DATA ──────────────────────────
hdr("collection-00 filter vs the labels (TAGGED)")
tag[, c00 := c00_pass(tag)]
show(pass_report(tag$c00, tag$class), "c00_tagged_overall.csv")
msg("(AUC of the filter as a 0/1 score: %.3f — a rule, not a ranking)",
    auc_fast(as.numeric(tag$c00), tag$class))

hdr("...broken down by size case (where the errors live)")
show(tag[, c(.(n = .N), as.list(pass_report(c00, class)[, -1])), by = case][order(case)],
     "c00_tagged_by_case.csv")

hdr("...and the size cut alone (area_ha >= 1), for reference")
show(pass_report(tag$area_ha >= C00$a1, tag$class), "c00_tagged_sizecut_only.csv")

# Per-threshold diagnostics: for each filter metric, inside each size case, the class
# quantiles + how many of each class the c-00 threshold would cut. This is the table to
# read when moving a threshold: a cut sitting inside the FIRE distribution is the problem.
hdr("filter metrics by class within each case (TAGGED) — threshold placement")
metrics <- c("convexity", "burned_around_3", "circularity", "shape_index")
thr_of  <- c(convexity = NA, burned_around_3 = NA, circularity = NA, shape_index = NA)
thr_diag <- rbindlist(lapply(metrics, function(v) {
  rbindlist(lapply(levels(tag$case), function(cs) {
    s <- tag[case == cs]
    if (!nrow(s)) return(NULL)
    t1 <- if (cs == levels(tag$case)[2]) C00$case1[v] else if (cs == levels(tag$case)[3]) C00$case2[v] else NA
    rbindlist(lapply(c(1L, 0L), function(k) {
      x <- s[class == k][[v]]
      if (!length(x)) return(NULL)
      data.table(metric = v, case = cs, class = k, n = length(x),
                 q05 = quantile(x, .05, na.rm = TRUE), q50 = median(x, na.rm = TRUE),
                 q95 = quantile(x, .95, na.rm = TRUE),
                 c00_thr = unname(if (is.na(t1)) NA_real_ else t1),
                 pct_cut_by_thr = if (is.na(t1)) NA_real_ else
                   100 * mean(if (v == "shape_index") x >= t1 else x <= t1, na.rm = TRUE))
    }))
  }))
}))
show(thr_diag, "c00_tagged_threshold_diagnostics.csv")

# ── [4] the filter ON THE FULL TABLE ────────────────────────────────────────
hdr("collection-00 filter applied to the FULL table")
full[, c00 := c00_pass(full)]
show(full[, .(objects = .N, kept = sum(c00), pct_objects = round(100 * mean(c00), 2),
              area_kha = sum(area_ha) / 1e3, area_kept_kha = sum(area_ha[c00]) / 1e3,
              pct_area = round(100 * sum(area_ha[c00]) / sum(area_ha), 2))],
     "c00_full_overall.csv")
show(full[, .(objects = .N, kept = sum(c00), pct_objects = round(100 * mean(c00), 1),
              area_kha = round(sum(area_ha) / 1e3, 1),
              area_kept_kha = round(sum(area_ha[c00]) / 1e3, 1),
              pct_area = round(100 * sum(area_ha[c00]) / sum(area_ha), 1)),
          by = fire_year][order(fire_year)], "c00_full_by_year.csv")

hdr("...which case does the keeping (FULL)")
show(full[, .(objects = .N, kept = sum(c00), pct_kept = round(100 * mean(c00), 1),
              area_kept_kha = round(sum(area_ha[c00]) / 1e3, 1),
              share_of_kept_area = NA_real_), by = case][
       order(case)][, share_of_kept_area := round(100 * area_kept_kha / sum(area_kept_kha), 1)][],
     "c00_full_by_case.csv")

# ── [5] figures ──────────────────────────────────────────────────────────────
hdr("figures")
lx <- scale_x_log10(labels = function(v) format(v, scientific = FALSE, trim = TRUE))
p1 <- ggplot(full[area_ha > 0], aes(area_ha)) +
  geom_histogram(bins = 80, fill = "grey35") + lx +
  geom_vline(xintercept = c(C00$a1, C00$a2, C00$a3), colour = "red", linetype = 2) +
  labs(title = "FULL: object size", subtitle = sprintf("%d objects; red = c-00 breaks", nrow(full)),
       x = "area_ha (log)", y = "objects")
    # thinned to ~20 k points: the curve is smooth and ggsave on 1.69 M would not be
p2 <- ggplot(full[order(area_ha)][, .(area_ha, cum = cumsum(area_ha) / sum(area_ha),
                                      cn = seq_len(.N) / .N)][
                seq(1L, nrow(full), length.out = min(20000L, nrow(full)))]) +
  geom_line(aes(area_ha, cum), colour = "firebrick") +
  geom_line(aes(area_ha, cn), colour = "steelblue") + lx +
  geom_vline(xintercept = C00$a1, colour = "red", linetype = 2) +
  labs(title = "FULL: cumulative share below a size",
       subtitle = "red line = area, blue = objects", x = "area_ha (log)", y = "cumulative share")
p3 <- ggplot(tag[area_ha > 0], aes(area_ha, fill = factor(class))) +
  geom_histogram(bins = 50, position = "identity", alpha = .55) + lx +
  geom_vline(xintercept = c(C00$a1, C00$a2, C00$a3), colour = "red", linetype = 2) +
  scale_fill_manual(values = c("0" = "steelblue", "1" = "firebrick"),
                    labels = c("non-fire", "fire"), name = NULL) +
  labs(title = "TAGGED: size by class", x = "area_ha (log)", y = "objects")
p4 <- ggplot(tag[, .(p = mean(class == 1L), n = .N), by = area_bin][!is.na(area_bin)],
             aes(area_bin, p, size = n)) +
  geom_point(colour = "firebrick") + geom_hline(yintercept = .5, linetype = 3) +
  labs(title = "TAGGED: P(fire | size bin)", x = NULL, y = "P(fire)") +
  theme(axis.text.x = element_text(angle = 45, hjust = 1), legend.position = "none")
ggsave(file.path(OUT_DIR, "size_distribution.png"), (p1 | p2) / (p3 | p4),
       width = 10, height = 7, dpi = 140)

pm <- lapply(metrics, function(v) {
  d <- tag[case %in% levels(tag$case)[2:3]]
  ggplot(d, aes(factor(class), .data[[v]], fill = factor(class))) +
    geom_boxplot(outlier.size = .4, linewidth = .3) + facet_wrap(~case) +
    geom_hline(data = data.table(case = levels(tag$case)[2:3],
                                 y = c(C00$case1[v], C00$case2[v])),
               aes(yintercept = y), colour = "red", linetype = 2, na.rm = TRUE) +
    scale_fill_manual(values = c("0" = "steelblue", "1" = "firebrick"), guide = "none") +
    scale_x_discrete(labels = c("0" = "non-fire", "1" = "fire")) +
    labs(title = v, x = NULL, y = NULL)
})
ggsave(file.path(OUT_DIR, "c00_metric_thresholds.png"), Reduce(`|`, pm[1:2]) / Reduce(`|`, pm[3:4]),
       width = 10, height = 7, dpi = 140)

p5 <- ggplot(full[, .(pct_objects = 100 * mean(c00),
                      pct_area = 100 * sum(area_ha[c00]) / sum(area_ha)), by = fire_year],
             aes(fire_year)) +
  geom_col(aes(y = pct_objects), fill = "steelblue", alpha = .7) +
  geom_line(aes(y = pct_area), colour = "firebrick", linewidth = .7) +
  geom_point(aes(y = pct_area), colour = "firebrick", size = 1) +
  labs(title = "c-00 filter on the FULL table, per fire-year",
       subtitle = "bars = % objects kept, red = % area kept", x = NULL, y = "%")
ggsave(file.path(OUT_DIR, "c00_full_by_year.png"), p5, width = 9, height = 4, dpi = 140)

msg("wrote CSVs + 3 PNGs to %s", OUT_DIR)
