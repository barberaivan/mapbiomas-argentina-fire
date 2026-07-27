#!/usr/bin/env Rscript
# =============================================================================
# objects_threshold.R — choose the fire/non-fire cut on OUT-OF-FOLD probabilities
# =============================================================================
# The 0.5 default is not the right cut: under grid-blocked CV the model runs
# sensitivity 0.73 against specificity 0.91, i.e. it under-detects, which is the wrong way
# round for a burned-area product. This sweeps every threshold on the OUT-OF-FOLD predictions
# (never in-sample — an in-sample cut is chosen against probabilities the model has already
# seen the answers for) and reports the optimum OVERALL and PER SIZE STRATUM.
#
# Run from the repo ROOT:
#   Rscript collection-01/scripts/objects_threshold.R [oof-file] [--boot N]
#     oof-file  default data/objects-predictions/oof_grid_5.csv (grid-blocked folds — the
#               deployment-relevant design, docs/06)
#     --boot N  bootstrap resamples for the threshold's stability interval (default 1000)
#
# FOUR CRITERIA, because "optimal" is a choice, not a fact:
#   J        Youden's J = sens + spec - 1. THE HEADLINE, because it is the only one here that
#            does not move with prevalence — and our labelled set is NOT a random sample of
#            objects (per-year prevalence runs 0.00-1.00, docs/06), so every prevalence-
#            dependent criterion is biased by how the points were collected, not by the model.
#   F1       2PR/(P+R). Reported, but it rewards the majority class and so drifts with that
#            same sampling bias.
#   acc      plain accuracy at the cut. Same caveat, worse.
#   J_area   Youden's J with every object WEIGHTED BY area_ha. The product is a burned-AREA
#            product, so this is the criterion that matches the deliverable — but read it
#            knowing a handful of huge objects dominate the weights (docs/06 "the 10 largest").
#
# STRATA: five disjoint size bands (<1, 1-50, 50-300, 300-1000, >=1000 ha) — the collection-00
# cases with the open-ended >=300 one split in two, because the optimal cut turned out to keep
# rising with size and the >=300 band was hiding that. Plus the pooled >=1 ha and all rows for
# reference (excluded from the deployable pick — they are views of the same objects).
#
# Outputs to collection-01/data/objects-explore/:
#   threshold_sweep_<tag>.csv        the full curve, overall and per stratum
#   threshold_chosen_<tag>.csv       one row per stratum x criterion + bootstrap interval
#   threshold_<tag>.png              criterion curves + ROC + the area consequence
# and the deployable pick to  collection-01/config/object_model_thresholds.csv  (tracked).
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(ggplot2)
  library(patchwork)
})
source("collection-01/scripts/objects_data_functions.R")

OUT_DIR    <- "collection-01/data/objects-explore"
CONFIG_OUT <- "collection-01/config/object_model_thresholds.csv"
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

argv <- commandArgs(trailingOnly = TRUE)
nboot <- { i <- match("--boot", argv); if (is.na(i)) 1000L else as.integer(argv[i + 1L]) }
oof_f <- { f <- grep("^--", argv, value = TRUE, invert = TRUE)
           if (length(f)) f[1] else "collection-01/data/objects-predictions/oof_grid_5.csv" }
tag   <- sub("^oof_", "", tools::file_path_sans_ext(basename(oof_f)))

msg <- function(...) write(sprintf(...), stderr())
hdr <- function(s) { msg(""); msg("== %s ==", s) }
show <- function(x, file = NULL) {
  print(x); if (!is.null(file)) fwrite(x, file.path(OUT_DIR, file), na = "NA"); invisible(x)
}
theme_set(theme_bw(base_size = 9))

d <- fread(oof_f)
stopifnot(all(c("class", "area_ha", "p_oof") %in% names(d)))
msg("%s: %d objects (%d fire / %d non-fire), prevalence %.3f",
    basename(oof_f), nrow(d), sum(d$class == 1L), sum(d$class == 0L), mean(d$class == 1L))

# ── the sweep ────────────────────────────────────────────────────────────────
# Candidate cuts are the observed probabilities themselves (plus 0/1), so no grid resolution is
# lost; everything is computed from cumulative sums over the p-ordered vector, which makes the
# whole curve one pass instead of one pass per candidate.
sweep <- function(p, y, w = rep(1, length(p))) {
  o <- order(-p); p <- p[o]; y <- y[o]; w <- w[o]
  P <- sum(w[y == 1L]); N <- sum(w[y == 0L])
  tp <- cumsum(w * (y == 1L)); fp <- cumsum(w * (y == 0L))
  # threshold = "call fire when p > t": t just below each p keeps that object in
  keep <- c(which(diff(p) != 0), length(p))          # collapse ties
  data.table(t = p[keep], tp = tp[keep], fp = fp[keep], fn = P - tp[keep], tn = N - fp[keep],
             sens = tp[keep] / P, spec = (N - fp[keep]) / N,
             prec = tp[keep] / (tp[keep] + fp[keep]),
             acc = (tp[keep] + N - fp[keep]) / (P + N))[
    , `:=`(J = sens + spec - 1, F1 = 2 * prec * sens / (prec + sens))][]
}

# The size bands, in size order, then the two summary rows. SIZE_BANDS is the disjoint partition
# that gets deployed; `>=1 ha` and `all` are pooled views of the same objects, reported for
# reference and excluded from the deployable pick so nothing is double-counted.
SIZE_BREAKS <- c(0, 1, 50, 300, 1000, Inf)
SIZE_BANDS  <- c("<1 ha", "1-50 ha", "50-300 ha", "300-1000 ha", ">=1000 ha")
# What actually gets DEPLOYED. Not the same list, on purpose: 300-1000 and >=1000 come out at
# 0.562 and 0.579 with bootstrap intervals that almost coincide (0.50-0.85 / 0.50-0.77), i.e.
# the split above 300 ha buys no distinguishable cut — whereas 1-50 vs 50-300 vs >=300 have
# near-disjoint intervals and earn their own. Deploying the two top bands separately would add a
# knob that can only overfit, so >=300 ha is deployed as ONE pooled cut and the finer pair stays
# in the report. Same evidence standard both ways.
DEPLOY_BANDS <- c("<1 ha", "1-50 ha", "50-300 ha", ">=300 ha")

# stratum -> its sweep (unweighted) + area-weighted sweep, glued on the threshold column
strata_of <- function(d) {
  b <- cut(d$area_ha, SIZE_BREAKS, right = FALSE, labels = SIZE_BANDS)
  c(setNames(lapply(SIZE_BANDS, function(s) !is.na(b) & b == s), SIZE_BANDS),
    list(`>=300 ha` = d$area_ha >= 300, `>=1 ha` = d$area_ha >= 1, all = rep(TRUE, nrow(d))))
}
STRATUM_ORDER <- c(SIZE_BANDS, ">=300 ha", ">=1 ha", "all")

sw <- rbindlist(lapply(names(strata_of(d)), function(s) {
  i <- strata_of(d)[[s]]
  if (sum(i) < 20L || uniqueN(d$class[i]) < 2L) { msg("  stratum %s: too few / one class — skipped", s); return(NULL) }
  a <- sweep(d$p_oof[i], d$class[i])
  b <- sweep(d$p_oof[i], d$class[i], d$area_ha[i])[, .(t, J_area = J, sens_area = sens, spec_area = spec)]
  cbind(stratum = s, n = sum(i), merge(a, b, by = "t", all.x = TRUE))
}))
sw[, stratum := factor(stratum, levels = STRATUM_ORDER)]
setorder(sw, stratum, -t)
# the full curve is thousands of rows per stratum — written, not printed
fwrite(sw[, .(stratum, n, t, tp, fp, fn, tn, sens, spec, prec, acc, J, F1, J_area)],
       file.path(OUT_DIR, sprintf("threshold_sweep_%s.csv", tag)), na = "NA")
msg("swept %d cut(s) across %d strata", nrow(sw), uniqueN(sw$stratum))

# ── the optimum per stratum per criterion, with a stability interval ─────────
# Bootstrap the Youden pick: resample objects within the stratum, re-find argmax J. A wide
# interval means the cut is not identified by this many labels and should not be trusted to
# three decimals — expected for <1 ha (29 fire objects).
boot_ci <- function(p, y, B) {
  if (B <= 0L) return(c(NA_real_, NA_real_))
  set.seed(1L)
  t_star <- vapply(seq_len(B), function(b) {
    i <- sample.int(length(p), replace = TRUE)
    if (uniqueN(y[i]) < 2L) return(NA_real_)
    s <- sweep(p[i], y[i]); s$t[which.max(s$J)]
  }, numeric(1))
  unname(quantile(t_star, c(.05, .95), na.rm = TRUE))
}

best <- rbindlist(lapply(levels(droplevels(sw$stratum)), function(s) {
  x <- sw[stratum == s]
  i <- strata_of(d)[[s]]
  ci <- boot_ci(d$p_oof[i], d$class[i], nboot)
  rbindlist(lapply(c("J", "F1", "acc", "J_area"), function(cr) {
    k <- which.max(x[[cr]])
    data.table(stratum = s, n = x$n[1], criterion = cr, t = round(x$t[k], 4),
               sens = round(x$sens[k], 3), spec = round(x$spec[k], 3),
               prec = round(x$prec[k], 3), acc = round(x$acc[k], 3),
               J = round(x$J[k], 3), F1 = round(x$F1[k], 3),
               J_area = round(x$J_area[k], 3),
               t_boot_q05 = round(ci[1], 3), t_boot_q95 = round(ci[2], 3))
  }))
}))
hdr("optimum per stratum per criterion (t_boot_* is the J pick's 5-95 % bootstrap interval)")
show(best, sprintf("threshold_chosen_%s.csv", tag))

hdr("what the 0.5 default does, for comparison")
show(rbindlist(lapply(levels(droplevels(sw$stratum)), function(s) {
  x <- sw[stratum == s][which.min(abs(t - 0.5))]
  data.table(stratum = s, n = x$n, t = round(x$t, 3), sens = round(x$sens, 3),
             spec = round(x$spec, 3), prec = round(x$prec, 3), acc = round(x$acc, 3),
             J = round(x$J, 3))
})), sprintf("threshold_at_0.5_%s.csv", tag))

# ── the deployable pick ─────────────────────────────────────────────────────
# Youden, per size stratum, at the four collection-00 size bands (the <1 / >=1 split is a
# summary of the same thing and would double-count). <1 ha objects are the noisiest stratum and
# 3.4 % of objects for 0.04 % of area (docs/06), so the size cut, not the threshold, is the
# right tool there — recorded here anyway so the choice is explicit rather than implied.
pick <- best[criterion == "J" & stratum %in% DEPLOY_BANDS,
             .(stratum, n, threshold = t, sens, spec, J, t_boot_q05, t_boot_q95)]
pick <- pick[order(band_lower(stratum))]
pick[, `:=`(oof_source = basename(oof_f), criterion = "youden_J")]
hdr("deployable: Youden threshold per size band")
show(pick)
fwrite(pick, CONFIG_OUT)
msg("-> %s", CONFIG_OUT)

# area consequence of one global cut vs the per-band cuts, against the labelled truth
area_true <- sum(d$area_ha[d$class == 1L])
t_glob <- best[stratum == "all" & criterion == "J"]$t
# the DEPLOYED rule: each object gets the cut of the band it falls in (bands read off `pick`,
# so this follows the config rather than restating the breaks)
t_band <- pick$threshold[findInterval(d$area_ha, band_lower(pick$stratum))]
hdr("area kept, vs the labelled burned area of the same objects")
show(data.table(
  rule = c("p > 0.5", sprintf("p > %.3f (global J)", t_glob), "per-band J", "labelled truth"),
  area_kha = round(c(sum(d$area_ha[d$p_oof > .5]), sum(d$area_ha[d$p_oof > t_glob]),
                     sum(d$area_ha[d$p_oof > t_band]), area_true) / 1e3, 1),
  n_objects = c(sum(d$p_oof > .5), sum(d$p_oof > t_glob), sum(d$p_oof > t_band),
                sum(d$class == 1L))))

# ── figures ─────────────────────────────────────────────────────────────────
p1 <- ggplot(melt(sw[, .(stratum, t, J, F1, acc, J_area)], id.vars = c("stratum", "t")),
             aes(t, value, colour = variable)) +
  geom_line(linewidth = .4) + facet_wrap(~stratum) +
  geom_vline(xintercept = 0.5, linetype = 3) +
  labs(title = "criterion vs threshold", x = "threshold on p_mean", y = NULL, colour = NULL)
p2 <- ggplot(sw, aes(1 - spec, sens, colour = stratum)) +
  geom_line(linewidth = .4) + geom_abline(linetype = 3) +
  geom_point(data = best[criterion == "J"], aes(1 - spec, sens), size = 1.6) +
  labs(title = "ROC, dot = Youden pick", x = "1 - specificity", y = "sensitivity", colour = NULL)
p3 <- ggplot(sw[stratum == "all"], aes(t)) +
  geom_line(aes(y = (tp + fp) / sum(d$class == 1L)), colour = "grey30") +
  geom_hline(yintercept = 1, linetype = 2, colour = "firebrick") +
  geom_vline(xintercept = c(0.5, t_glob), linetype = c(3, 1), colour = c("black", "steelblue")) +
  labs(title = "objects called fire / labelled fire objects",
       subtitle = "red = parity; blue = global Youden cut; dotted = 0.5", x = "threshold", y = "ratio")
ggsave(file.path(OUT_DIR, sprintf("threshold_%s.png", tag)), (p1 / (p2 | p3)),
       width = 10, height = 8, dpi = 140)
msg("wrote figures + CSVs to %s", OUT_DIR)
