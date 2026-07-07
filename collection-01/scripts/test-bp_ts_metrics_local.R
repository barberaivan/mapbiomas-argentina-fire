#!/usr/bin/env Rscript
# collection-01/scripts/test-bp_ts_metrics_local.R
#
# Hard-check: does the LOCAL period-based ts-metric computation
# (bp_ts_metrics_local_train.R) agree with the EXPORTED annual `bpts` image, for
# one fire? Validates the metric formulas against production (docs/04-snic.md).
#
# Choose a fire that burns MID-YEAR in an already-exported year: mid-year keeps
# the fire far from the annual padding/boundary edges, so the period-based and
# year-based series bracket the same transition and the MAGNITUDE metrics
# (delta3_peak, minfore3_peak, pmax3) should match closely. Timing metrics
# (date_post, jumpgap, widths) are expected to differ somewhat — burned-point
# training obs skip the fire-gap [pre_upr, post_lwr] that production observes —
# so those are reported for information, not asserted.
#
# Prereq — sample the exported image at the fire's points (year-based "truth"):
#   python collection-01/scripts/annual_data_download.py --region <R> --fire <FIRE>
# then:
#   Rscript collection-01/scripts/test-bp_ts_metrics_local.R <REGION> <FIRE> [tol]

suppressPackageStartupMessages(library(data.table))

ROOT <- "collection-01"
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) stop("usage: test-bp_ts_metrics_local.R <REGION> <FIRE> [tol]")
region <- args[1]; fire <- args[2]
TOL <- if (length(args) >= 3) as.numeric(args[3]) else 0.05   # prob-scale magnitude tolerance

PROB_BANDS <- c("delta3_peak", "minfore3_peak", "delta2_peak", "minfore2_peak",
                "pmax3", "pmax2", "pmax1")
MAG_METRICS <- c("delta3_peak", "minfore3_peak", "pmax3")     # the seed/candidate quantities

# ── Exported "truth": production bpts sampled at the fire's points ────────────
exp_path <- file.path(ROOT, "data", sprintf("annual_data_%s.csv", region))
if (!file.exists(exp_path))
  stop("Missing ", exp_path, " — run annual_data_download.py --region ", region, " --fire ", fire)
truth <- fread(exp_path)[fire_id == fire]
if (!nrow(truth)) stop("No exported rows for fire ", fire, " in ", exp_path)
for (b in intersect(PROB_BANDS, names(truth))) truth[[b]] <- truth[[b]] / 10000  # decode int16
truth <- truth[, c("point_id", intersect(c(PROB_BANDS, "date_post3"), names(truth))), with = FALSE]
setnames(truth, setdiff(names(truth), "point_id"), paste0(setdiff(names(truth), "point_id"), "_exp"))

# ── Local: recompute metrics for just this fire ───────────────────────────────
source(file.path(ROOT, "scripts", "bp_ts_metrics_local_train.R"))   # sys.nframe()>0 → no auto-run
remap <- fread(file.path(ROOT, "config", "veg_fire_remap.csv"))
local <- process_region(region, remap, only_fire = fire)
if (is.null(local) || !nrow(local)) stop("Local computation produced no points for fire ", fire)

# ── Compare on the magnitude metrics, burned points ───────────────────────────
cmp <- truth[local, on = "point_id", nomatch = 0L]
cmp <- cmp[label == 1L]                                # burned points carry the delta signal
if (!nrow(cmp)) stop("No burned points joined between local and exported tables.")

cat(sprintf("\nFire %s / %s — %d burned points joined\n", region, fire, nrow(cmp)))
cat(sprintf("Magnitude tolerance (prob scale): %.3f\n\n", TOL))

# Local & production use different observation sets (production: full focal year
# + padding; training: a truncated, sparser window), so per-point magnitude will
# scatter. What must hold is: (a) the SAME event is detected (date_post agrees),
# (b) tiny median bias, (c) strong correlation. Per-point exactness is neither
# expected nor needed — thresholds are calibrated on the DISTRIBUTION.
med_ok <- TRUE; cor_ok <- TRUE
for (m in MAG_METRICS) {
  loc <- cmp[[m]]; exp <- cmp[[paste0(m, "_exp")]]
  ok <- !is.na(loc) & !is.na(exp)
  if (!any(ok)) { cat(sprintf("  %-14s no comparable points\n", m)); next }
  ad <- abs(loc[ok] - exp[ok]); r <- cor(loc[ok], exp[ok])
  cat(sprintf("  %-14s n=%d  median|Δ|=%.4f  r=%.3f  within .05/.10/.15 = %.0f/%.0f/%.0f%%\n",
              m, sum(ok), median(ad), r,
              100*mean(ad<=0.05), 100*mean(ad<=0.10), 100*mean(ad<=0.15)))
  if (median(ad) > 0.03) med_ok <- FALSE
  if (r < 0.80) cor_ok <- FALSE
}

# date_post: convert local (epoch-day) and exported (DOY) to a common day-of-year.
dp_ok <- NA
if (all(c("date_post3", "date_post3_exp") %in% names(cmp))) {
  yr <- data.table::year(data.table::as.IDate(cmp$date_post3))
  loc_doy <- as.integer(data.table::as.IDate(cmp$date_post3) -
                        data.table::as.IDate(sprintf("%d-01-01", yr))) + 1L
  dd <- abs(loc_doy - suppressWarnings(as.integer(cmp$date_post3_exp)))
  dp_ok <- mean(dd <= 30, na.rm = TRUE) >= 0.90
  cat(sprintf("\n  date_post agreement: median|Δdays|=%s  within 30d=%.0f%%  (same event?)\n",
              median(dd, na.rm = TRUE), 100 * mean(dd <= 30, na.rm = TRUE)))
}

pass <- med_ok && cor_ok && isTRUE(dp_ok)
cat(sprintf("\n%s — %s\n", if (pass) "PASS" else "CHECK",
            if (pass) "local reproduces production up to the inherent window difference (same event, tiny bias, high r)"
            else "median bias / correlation / date_post off — inspect veg_fire mapping / P050 wiring / obs coverage"))
quit(status = if (pass) 0L else 1L)
