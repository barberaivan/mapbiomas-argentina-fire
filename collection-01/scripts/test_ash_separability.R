#!/usr/bin/env Rscript
# =============================================================================
# test_ash_separability.R — can NBR / NBR2 / AFRI tell ASH from real BURN?
# =============================================================================
# Ash and real burns both darken the SWIR-based burn indices, so ash is a major
# FALSE-POSITIVE source. Question (raised from the Karnieli 2001 AFRI paper): does
# AFRI — designed as a smoke/aerosol-resistant NDVI surrogate, but built on the same
# NIR/SWIR2 bands as NBR — separate ash from burn any better than NBR / NBR2?
#
# Test setup (grassland_pat, PAT, veg_fire = 16; mb_class_raw in {11,12,63,73}):
#   * BURNED  (positive) = all burned==1 obs in grassland_pat (post-fire window, real fires).
#   * ASH     (negative) = obs from fire_47 ("ash_2011", a PURE-NEGATIVE fire, all burned==0)
#                          that fall in grassland_pat. NO ordinary unburned added.
#   fire_46 ("drought_2015") is drought, NOT ash, so it is excluded.
#
# Two ash definitions are reported:
#   (a) ash_all  — every fire_47 grassland obs (incl. its pre-event window = normal veg);
#   (b) ash_post — only fire_47 obs in its ash/post window (date >= post_lwr 2011-08-01),
#                  i.e. the genuinely darkened ash. This is the fair burn-vs-ash contrast,
#                  since BURNED is itself post-fire-window only.
#
# Metric: Mann-Whitney AUC with BURNED as the positive class. sep = |AUC-0.5|*2 in [0,1]
#   (0 = index cannot tell ash from burn; 1 = perfectly separable). Higher sep = the index
#   discriminates real burn from ash better. Also: Cohen's d and per-group medians/means.
#
# Run from repo root:  Rscript collection-01/scripts/test_ash_separability.R
# =============================================================================

suppressPackageStartupMessages(library(data.table))

PAT_CSV   <- "collection-01/data/training_observations_PAT_v1.csv"
GRASS_MB  <- c(11L, 12L, 63L, 73L)          # grassland_pat (veg_fire 16) raw MB classes, PAT
ASH_FIRE  <- "fire_47"                       # ash_2011 (fire_46 = drought_2015, excluded)
ASH_POST_LWR <- "2011-08-01"                 # fire_47 post_lwr (ISO -> string compare ok)
INDICES   <- c("NBR", "NBR2", "AFRI")        # the three asked for
CONTEXT   <- c("MIRBI", "NDVI", "NDMI")      # extra burn/greenness indices for interpretation

# ── load only what we need ───────────────────────────────────────────────────
cols <- c("fire_id", "mb_class_raw", "burned", "date", unique(c(INDICES, CONTEXT)))
d <- fread(PAT_CSV, select = cols)
d <- d[mb_class_raw %in% GRASS_MB]           # restrict everything to grassland_pat

burned  <- d[burned == 1L]
ash_all <- d[fire_id == ASH_FIRE & burned == 0L]
ash_post<- ash_all[date >= ASH_POST_LWR]
cat(sprintf("grassland_pat: BURNED n=%d | ASH(all) n=%d | ASH(post >= %s) n=%d\n",
            nrow(burned), nrow(ash_all), ASH_POST_LWR, nrow(ash_post)))

# Land-cover-matched sets: the ash fire is ~97% Estepa (mb=63), so restrict BOTH groups to
# mb=63 to remove the steppe-vs-grassland confound and isolate ash-vs-char within steppe.
MATCH_MB     <- 63L
burned_63    <- burned[mb_class_raw == MATCH_MB]
ash_post_63  <- ash_post[mb_class_raw == MATCH_MB]
cat(sprintf("Estepa-only (mb=63): BURNED n=%d | ASH(post) n=%d\n",
            nrow(burned_63), nrow(ash_post_63)))

# ── separability of one index: BURNED (pos) vs ASH (neg) ─────────────────────
auc_mw <- function(x_pos, x_neg) {           # Mann-Whitney AUC, NA-safe, int-overflow-safe
  x_pos <- x_pos[is.finite(x_pos)]; x_neg <- x_neg[is.finite(x_neg)]
  n1 <- as.numeric(length(x_pos)); n0 <- as.numeric(length(x_neg))
  if (n1 == 0 || n0 == 0) return(NA_real_)
  r <- frank(c(x_pos, x_neg), ties.method = "average")
  (sum(r[seq_len(length(x_pos))]) - n1 * (n1 + 1) / 2) / (n1 * n0)
}
cohens_d <- function(x_pos, x_neg) {
  x_pos <- x_pos[is.finite(x_pos)]; x_neg <- x_neg[is.finite(x_neg)]
  n1 <- length(x_pos); n0 <- length(x_neg)
  sp <- sqrt(((n1 - 1) * var(x_pos) + (n0 - 1) * var(x_neg)) / (n1 + n0 - 2))
  (mean(x_pos) - mean(x_neg)) / sp
}

separability <- function(pos_dt, neg_dt, idx) {
  rbindlist(lapply(idx, function(f) {
    xp <- pos_dt[[f]]; xn <- neg_dt[[f]]
    a  <- auc_mw(xp, xn)
    data.table(index = f, auc = a, sep = abs(a - 0.5) * 2, cohens_d = cohens_d(xp, xn),
               med_burned = median(xp, na.rm = TRUE), med_ash = median(xn, na.rm = TRUE),
               mean_burned = mean(xp, na.rm = TRUE), mean_ash = mean(xn, na.rm = TRUE))
  }))
}
fmt <- function(dt) {
  dt[, c("auc","sep","cohens_d","med_burned","med_ash","mean_burned","mean_ash") :=
       lapply(.SD, round, 4),
     .SDcols = c("auc","sep","cohens_d","med_burned","med_ash","mean_burned","mean_ash")]
  dt[order(-sep)]
}

cat("\n========== BURNED vs ASH (all fire_47 grassland obs) ==========\n")
cat("--- requested indices ---\n");  print(fmt(separability(burned, ash_all, INDICES)))
cat("--- context indices   ---\n");  print(fmt(separability(burned, ash_all, CONTEXT)))

cat("\n========== BURNED vs ASH (post-window only, the fair contrast) ==========\n")
cat("--- requested indices ---\n");  print(fmt(separability(burned, ash_post, INDICES)))
cat("--- context indices   ---\n");  print(fmt(separability(burned, ash_post, CONTEXT)))

cat("\n========== BURNED vs ASH, ESTEPA ONLY (mb=63, post-window) — confound removed ==========\n")
cat("--- requested indices ---\n");  print(fmt(separability(burned_63, ash_post_63, INDICES)))
cat("--- context indices   ---\n");  print(fmt(separability(burned_63, ash_post_63, CONTEXT)))

cat("\nNote: AUC > 0.5 => index is HIGHER on burned than on ash; < 0.5 => lower on burned.\n",
    "sep near 0 => the index cannot distinguish ash from real burn (false-positive risk).\n",
    "Caveat: BURNED pools many fires/years/seasons; ASH is one 2011-12 PAT fire, so some\n",
    "separation may be phenological rather than purely ash-vs-char.\n", sep = "")
