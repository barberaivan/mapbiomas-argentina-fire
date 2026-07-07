#!/usr/bin/env Rscript
# collection-01/scripts/bp_ts_metrics_local_train.R
#
# Local, PERIOD-BASED analogue of workflow/03-bp_ts_metrics.py, computed on the
# already-downloaded training observations — for the SNIC seed/candidate
# threshold study (docs/04-snic.md §"Ground seeds & candidates in the data").
#
# Rather than sample the exported annual `bpts` images at the training points,
# we recompute the burn-probability time-series metrics DIRECTLY from the
# training observations. This runs NOW on all downloaded regions (no wait for
# the GEE export), and because the metric window is the fire's OBSERVATION
# PERIOD (not a calendar year) it dissolves both the cross-year attribution and
# the annual-vs-window contamination problems (docs/04-snic.md).
#
# Pipeline (per region):
#   1. read data/training_observations_<region>_v1.csv
#   2. keep only fit == TRUE obs — the manual visual cleaning from
#      scripts/data_cleaning.R that removed bad labels/tags (docs/02-data_cleaning.md)
#   3. map veg_fire (region + mb_class_raw via config/veg_fire_remap.csv) and
#      apply the DEPLOYED P050 model per class → per-obs burn probability
#      (reusing predict_class from ts_predict_functions.R; raw-scale coefficients
#      reconstructed from the git-tracked models/P050/*.csv, matching production)
#   4. per point (region|fire_id|point_id), ordered by date: compute the same
#      metrics as step 03 (delta{2,3}_peak, minfore{2,3}_peak, pmax{1,2,3},
#      jumpgap, widths, date_post), plus an annualised obs density `n`.
#
# Min-obs quality gate (mirrors the step-03 padded-array length rule, 03-bpts §3.5):
#   K=3 family needs >= 6 obs, K=2 family needs >= 4 obs (that is exactly the
#   window each delta needs: 3 back + 2 fwd, resp. 2 back + 1 fwd). Points below
#   the bar get that family's metrics = NA (a quality flag, not an error).
#
# Output: data/annual_data_resolved.csv — one row per training point, consumed by
# notebooks/snic_candidates_seeds_definition.qmd.
#
# Validate the metric computation against production with the single-fire
# hard-check: scripts/test-bp_ts_metrics_local.R.
#
# Run from repo root:  Rscript collection-01/scripts/bp_ts_metrics_local_train.R [REGION ...]

suppressPackageStartupMessages(library(data.table))

ROOT       <- "collection-01"
DATA_DIR   <- file.path(ROOT, "data")
COEF_DIR   <- file.path(ROOT, "models", "P050")             # C.DEPLOYED_MODEL
REMAP_CSV  <- file.path(ROOT, "config", "veg_fire_remap.csv")
OBS_VERSION <- 1L
REGIONS    <- c("BA", "CHACO", "PAMPA", "CUYO", "PAT")      # constants.REGIONS

source(file.path(ROOT, "scripts", "ts_predict_functions.R"))  # design_raw(), predict_class()

# ── Reconstruct a P050 predict_class "fit" object from the tracked CSV ────────
# predict_class() needs $coef_raw (named, incl. "(Intercept)"), $all_terms
# (ordered, no intercept) and $specs (list(name, fa, fb) per interaction). The
# P050 CSVs (block, term, coefficient, coef_std) carry raw-scale coefficients;
# interaction terms are "A__B" whose factors are design_raw's own column names
# (focal "<BAND>_t", prev "<BAND>_<med|wet|dry|sd>"), so specs = split on "__".
.fit_cache <- new.env(parent = emptyenv())
load_p050_fit <- function(veg_fire_code) {
  key <- as.character(veg_fire_code)
  if (!is.null(.fit_cache[[key]])) return(.fit_cache[[key]])
  path <- file.path(COEF_DIR, sprintf("class_%02d_coefficients.csv", veg_fire_code))
  if (!file.exists(path)) return(NULL)                     # non-fittable class
  cf <- fread(path)
  coef_raw  <- setNames(cf$coefficient, cf$term)
  all_terms <- cf$term[cf$term != "(Intercept)"]
  inter     <- all_terms[grepl("__", all_terms, fixed = TRUE)]
  specs <- lapply(inter, function(t) {
    ab <- strsplit(t, "__", fixed = TRUE)[[1]]
    list(name = t, fa = ab[1], fb = ab[2])
  })
  fit <- list(coef_raw = coef_raw, all_terms = all_terms, specs = specs)
  .fit_cache[[key]] <- fit
  fit
}

# ── Time-series metrics on one point's ordered probability series ─────────────
# p, day: same length, ORDERED ascending by day (integer days since epoch), one
# value per date. Returns a one-row list of step-03-equivalent metrics.
ts_metrics <- function(p, day) {
  T <- length(p)
  res <- list(
    n_obs = T,
    pmax1 = if (T >= 1) max(p) else NA_real_,
    pmax2 = NA_real_, pmax3 = NA_real_,
    delta2_peak = NA_real_, minfore2_peak = NA_real_,
    jumpgap2 = NA_integer_, prevwidth2 = NA_integer_, postwidth2 = NA_integer_, date_post2 = NA_integer_,
    delta3_peak = NA_real_, minfore3_peak = NA_real_,
    jumpgap3 = NA_integer_, prevwidth3 = NA_integer_, postwidth3 = NA_integer_, date_post3 = NA_integer_)

  if (T >= 4) {                                            # K=2 family
    minfore2 <- c(pmin(p[1:(T - 1)], p[2:T]), NA_real_)                 # valid t = 1..T-1
    maxback2 <- c(rep(NA_real_, 2), pmax(p[1:(T - 2)], p[2:(T - 1)]))   # valid t = 3..T
    delta2   <- minfore2 - maxback2                                     # valid t = 3..T-1
    res$pmax2 <- max(minfore2, na.rm = TRUE)
    t2 <- which.max(delta2)
    res$delta2_peak   <- delta2[t2];   res$minfore2_peak <- minfore2[t2]
    res$jumpgap2   <- day[t2]     - day[t2 - 1]
    res$prevwidth2 <- day[t2 - 1] - day[t2 - 2]
    res$postwidth2 <- day[t2 + 1] - day[t2]
    res$date_post2 <- day[t2]
  }
  if (T >= 6) {                                            # K=3 family
    minfore3 <- c(pmin(p[1:(T - 2)], p[2:(T - 1)], p[3:T]), rep(NA_real_, 2))     # valid t = 1..T-2
    maxback3 <- c(rep(NA_real_, 3), pmax(p[1:(T - 3)], p[2:(T - 2)], p[3:(T - 1)])) # valid t = 4..T
    delta3   <- minfore3 - maxback3                                              # valid t = 4..T-2
    res$pmax3 <- max(minfore3, na.rm = TRUE)
    t3 <- which.max(delta3)
    res$delta3_peak   <- delta3[t3];   res$minfore3_peak <- minfore3[t3]
    res$jumpgap3   <- day[t3]     - day[t3 - 1]
    res$prevwidth3 <- day[t3 - 1] - day[t3 - 3]
    res$postwidth3 <- day[t3 + 2] - day[t3]
    res$date_post3 <- day[t3]
  }
  res
}

# ── Per-region: obs -> cleaned -> predicted -> per-point metrics ──────────────
process_region <- function(region, remap, only_fire = NULL) {
  obs_path <- file.path(DATA_DIR, sprintf("training_observations_%s_v%d.csv", region, OBS_VERSION))
  if (!file.exists(obs_path)) { message(sprintf("  %s: no obs CSV, skipping.", region)); return(NULL) }
  d <- fread(obs_path)
  if (!is.null(only_fire)) d <- d[fire_id == only_fire]   # single-fire path (test)
  if (!"fit" %in% names(d)) stop("no `fit` column — run scripts/data_cleaning.R first.")

  # (2) RECOVER trimmed obs. data_cleaning.R's fit==FALSE mostly trims post-fire
  # (burned==1) obs for LABEL quality, but those are valid observations, and
  # dropping them starves the K=3 minfore window (a scar's high-prob obs sit at
  # the series end -> pmax3/delta3 collapse). So build the metric series from ALL
  # obs of "usable" points — points with >=1 fit==TRUE obs, which excludes whole
  # exclusions (drop_fire, fully-dropped unburned points). K=3 is later NA'd for
  # points with genuinely <3 post-fire obs (fast-recovery veg -> use K=2 there).
  d[, pt_key := paste(region, fire_id, point_id, sep = "|")]
  usable <- d[fit == TRUE, unique(pt_key)]
  d <- d[pt_key %in% usable]

  # post_lwr per fire (first confirmed post-fire obs) → fire_year + K=3 post-obs gate.
  tf <- fread(file.path(DATA_DIR, sprintf("training_fires_%s.csv", region)))[
          , .(fire_id, post_lwr_day = as.integer(as.IDate(post_lwr)))]
  d <- tf[d, on = "fire_id"]
  d[, fire_year := year(as.IDate(post_lwr_day))]

  # (3) veg_fire = production's FOCAL-year rule (03-bpts §2.1, §3.4): ONE veg_fire
  # per point = MapBiomas(fire_year-1), applied to the WHOLE series (production
  # uses the focal year's prev-year land cover for every obs, incl. padding — NOT
  # each obs's own prev-year). Take it from the point's obs in fire_year (the
  # `focal_year` column is the obs year; its mb_class_raw = MB(obs_year-1)), so an
  # obs with focal_year==fire_year carries MB(fire_year-1). Fallback: own class.
  reg <- region
  focal_mb <- d[focal_year == fire_year, .(mb_focal = mb_class_raw[1L]), by = pt_key]
  d <- focal_mb[d, on = "pt_key"]
  d[is.na(mb_focal), mb_focal := mb_class_raw]
  vf <- unique(remap[region == reg, .(mb_class_raw, veg_fire, veg_fire_name, fittable)])
  d[vf, on = c(mb_focal = "mb_class_raw"),
    `:=`(veg_fire = i.veg_fire, veg_fire_name = i.veg_fire_name, fittable = i.fittable)]
  d <- d[fittable == TRUE & !is.na(veg_fire)]

  parts <- list()                                          # predict per class (like ts_plot_cache.R)
  for (code in sort(unique(d$veg_fire))) {
    mdl <- load_p050_fit(code)   # NOT `fit`: shadowed by the `fit` column in j-scope
    if (is.null(mdl)) next
    sub <- d[veg_fire == code]
    sub[, p_pred := predict_class(sub, mdl)]
    parts[[length(parts) + 1L]] <- sub
  }
  if (!length(parts)) return(NULL)
  d <- rbindlist(parts)
  d <- d[!is.na(p_pred)]

  # integer day; collapse same-day obs (≈ production mosaic_by_date). veg_fire /
  # mb_focal are now single per point.
  d[, day := as.integer(as.IDate(date))]
  d <- d[, .(p = mean(p_pred), veg_fire = veg_fire[1L], mb_class_raw = mb_focal[1L],
             post_lwr_day = post_lwr_day[1L]),
         by = .(pt_key, region, fire_id, point_id, class, day)]
  setorder(d, pt_key, day)

  # (4) metrics per point + annualised n + post-fire obs count.
  m <- d[, {
    mm <- ts_metrics(p, day)
    days_elapsed <- if (.N > 1L) day[.N] - day[1L] else 0L
    n_annual <- if (days_elapsed > 0L) as.integer(round(mm$n_obs / days_elapsed * 365)) else mm$n_obs
    c(mm, list(days_elapsed = days_elapsed, n = n_annual,
               post_obs = sum(day >= post_lwr_day[1L])))
  }, by = .(pt_key, region, fire_id, point_id, class)]

  # K=3 needs >=3 post-fire obs to register sustained burn; burned points below
  # that are genuinely fast-recovery (K=2 is the right metric there) → NA the K=3
  # family so they don't pollute the seed-metric distribution with false lows.
  k3 <- intersect(c("delta3_peak", "minfore3_peak", "jumpgap3", "prevwidth3",
                    "postwidth3", "date_post3", "pmax3"), names(m))
  m[class == "burned" & post_obs < 3L, (k3) := NA]

  # point-level land cover: the single focal veg_fire / mb_class_raw.
  attrs <- d[, .(veg_fire = veg_fire[1L], mb_class_raw = mb_class_raw[1L]), by = pt_key]
  out <- unique(remap[, .(veg_fire, veg_fire_name)])[attrs[m, on = "pt_key"], on = "veg_fire"]
  out[, label := as.integer(class == "burned")]
  message(sprintf("  %s: %d points (%d burned, %d unburned)",
                  region, nrow(out), sum(out$label == 1L), sum(out$label == 0L)))
  out[]
}

run_all <- function(regions = REGIONS) {
  remap <- fread(REMAP_CSV)
  res <- rbindlist(lapply(regions, process_region, remap = remap), use.names = TRUE, fill = TRUE)
  if (!nrow(res)) stop("No points produced.")
  # day-number date columns back to real dates for readability
  for (b in c("date_post2", "date_post3", "date_post"))
    if (b %in% names(res)) res[[b]] <- as.IDate(res[[b]])
  out_path <- file.path(DATA_DIR, "annual_data_resolved.csv")
  fwrite(res, out_path)
  message(sprintf("Wrote %d points → %s", nrow(res), out_path))
  invisible(res)
}

# ── Helper: list good hard-check targets — fires that burn MID-YEAR ────────────
# A fire whose burn window [pre_upr, post_lwr] sits inside ONE calendar year, with
# the burn month away from the Dec/Jan edges, is the cleanest test case (its
# period-based and year-based series bracket the same transition). Reads the
# downloaded training_fires_<region>.csv. Sorted best-first.
list_midyear_fires <- function(region) {
  f <- fread(file.path(DATA_DIR, sprintf("training_fires_%s.csv", region)))
  f[, `:=`(pre_upr = as.IDate(pre_upr), post_lwr = as.IDate(post_lwr))]
  f[, `:=`(burn_month = month(post_lwr),
           within_year = year(pre_upr) == year(post_lwr))]
  f[, edge_dist := pmin(burn_month - 1L, 12L - burn_month)]   # months from year edge
  setorder(f, -within_year, -edge_dist, post_lwr)
  f[, .(fire_id, pre_upr, post_lwr, burn_year = year(post_lwr),
        burn_month, within_year, edge_dist)]
}

# Run when invoked as a script; when source()-d (e.g. by the test) just load fns.
if (sys.nframe() == 0L) {
  args <- commandArgs(trailingOnly = TRUE)
  if (length(args) && args[1] == "--midyear") {
    regs <- if (length(args) > 1) args[-1] else REGIONS
    for (r in regs) { cat(sprintf("\n=== %s — mid-year (best-first) ===\n", r)); print(list_midyear_fires(r)) }
  } else {
    run_all(if (length(args)) args else REGIONS)
  }
}
