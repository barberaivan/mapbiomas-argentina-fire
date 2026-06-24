#!/usr/bin/env Rscript
# collection-01/scripts/data_cleaning.R
#
# Adds a boolean `fit` column to data/training_observations_{region}_v{version}.csv,
# the gate that 02-model_fitting.R requires. See docs/02-data_cleaning.md for the spec.
#
# Two layers:
#   (1) BASE HARD FILTER (every fire, from training_fires windows): keep only obs
#       inside the valid window for the point's type; everything else -> fit=FALSE.
#       This also trims the PAT 1-30 fires that were exported with a longer span.
#   (2) PER-FIRE EDITS (the RULES table below, transcribed from data/data_cleaning.xlsx):
#       manual corrections, applied on top of the base filter.
#
# Run from repo root:
#   Rscript collection-01/scripts/data_cleaning.R [version]
#
# Re-running is idempotent: it only (re)computes the `fit` column; the original
# observation columns are untouched. Edit RULES and re-run to revise.

suppressPackageStartupMessages(library(data.table))

# ── Ordering semantics (see docs/02-data_cleaning.md) ─────────────────────────
# Count/range rules ("primeras/ultimas N", "a a b", "desde la k") rank the UNIQUE
# DATES of the fire's burned==1 observations, pooled across ALL its burned points
# (keyed region_fire_id), sorted ascending. The rule picks date positions; a
# burned==1 obs is kept iff its date is in the kept-date set. NOT per point: if a
# point lacks obs on date d2 but has d1 and d3, "keep first 3" keeps its d1 and d3.
# All rules act on burned==1 only, except: drop_fire, pre_trim_lt (all points),
# and drop_unburned_keep_first (also drops unburned-point obs).

# ── RULES: one entry per fire listed in the workbook ──────────────────────────
# `fire` is the sheet id (numeric, no zero-pad, no "fire_" prefix; or "sdeN").
# type/params:
#   keep_first n | drop_first n | drop_last n | keep_from k | keep_range a,b
#   keep_nbr_lt x
#   date_drop_ge date | date_drop_gt date | date_drop_lt date   (absolute "YYYY-MM-DD")
#   date_drop_ge_md / _gt_md / _lt_md  month,day   (year resolved within post-fire window)
#   date_keep_ym year, months
#   pre_trim_lt date           (drop ALL obs before date; trims pre-fire side)
#   drop_fire
#   drop_unburned_keep_first n (drop unburned-point obs; burned points keep_first n)
R_ <- function(region, fire, type, ...) c(list(region = region, fire = fire, type = type), list(...))
RULES <- list(
  # ---- CUYO ----
  R_("CUYO", 3,  "drop_last",  n = 1),
  R_("CUYO", 4,  "drop_last",  n = 4),
  R_("CUYO", 5,  "drop_fire"),
  R_("CUYO", 6,  "drop_last",  n = 3),
  R_("CUYO", 9,  "date_drop_ge", date = "2001-05-01"),   # posteriores a mayo 2001 inclusive
  R_("CUYO", 16, "drop_last",  n = 4),
  R_("CUYO", 22, "drop_last",  n = 3),
  R_("CUYO", 25, "drop_last",  n = 1),
  R_("CUYO", 27, "drop_first", n = 2),

  # ---- PAT ----
  R_("PAT", 27, "drop_last",  n = 5),
  R_("PAT", 32, "keep_nbr_lt", x = 0.1),
  R_("PAT", 33, "date_drop_gt", date = "2023-06-30"),    # luego de junio 2023
  R_("PAT", 34, "date_drop_gt", date = "2004-07-31"),    # luego de julio 2004
  R_("PAT", 35, "keep_first", n = 5),
  R_("PAT", 36, "date_keep_ym", year = 2001, months = c(3, 4, 5)),  # marzo abril mayo 2001
  R_("PAT", 37, "keep_first", n = 3),

  # ---- PAMPA ----
  R_("PAMPA", 2,  "drop_last",  n = 1),
  R_("PAMPA", 4,  "drop_last",  n = 3),
  R_("PAMPA", 5,  "date_drop_ge_md", month = 3,  day = 1),   # a partir de marzo inclusive
  R_("PAMPA", 11, "date_drop_lt_md", month = 10, day = 15),  # previas a 15 de octubre
  R_("PAMPA", 13, "date_drop_gt_md", month = 10, day = 10),  # posteriores a 10 de octubre
  R_("PAMPA", 14, "drop_first", n = 1),                      # 1ra del periodo post
  R_("PAMPA", 22, "drop_first", n = 1),                      # 1ra obs burn del periodo post
  R_("PAMPA", 42, "drop_last",  n = 2),
  R_("PAMPA", 52, "keep_first", n = 9),

  # ---- BA ----
  R_("BA", 1,  "keep_first", n = 3),
  R_("BA", 2,  "drop_last",  n = 5),
  R_("BA", 4,  "drop_unburned_keep_first", n = 15),
  R_("BA", 6,  "keep_range", a = 2, b = 6),
  R_("BA", 8,  "keep_range", a = 1, b = 2),
  R_("BA", 9,  "keep_range", a = 1, b = 3),
  R_("BA", 11, "keep_range", a = 3, b = 15),
  R_("BA", 12, "keep_range", a = 1, b = 4),
  R_("BA", 13, "keep_range", a = 1, b = 4),

  # ---- CHACO ----
  R_("CHACO", 1,  "drop_first", n = 1),
  R_("CHACO", 2,  "drop_first", n = 1),
  R_("CHACO", 7,  "keep_first", n = 3),
  R_("CHACO", 11, "drop_last",  n = 1),
  R_("CHACO", 15, "drop_first", n = 1),
  R_("CHACO", 22, "keep_first", n = 3),
  R_("CHACO", 31, "keep_first", n = 15),
  R_("CHACO", 32, "keep_first", n = 3),
  R_("CHACO", 33, "keep_first", n = 4),
  R_("CHACO", 34, "keep_first", n = 5),
  R_("CHACO", 35, "drop_last",  n = 3),
  R_("CHACO", 36, "drop_last",  n = 3),
  R_("CHACO", 37, "drop_last",  n = 1),
  R_("CHACO", 38, "keep_first", n = 4),
  R_("CHACO", 39, "drop_last",  n = 1),
  R_("CHACO", 41, "keep_first", n = 5),
  R_("CHACO", 51, "keep_first", n = 5),
  R_("CHACO", 52, "keep_first", n = 4),
  R_("CHACO", 53, "keep_first", n = 3),
  R_("CHACO", 54, "keep_first", n = 5),
  R_("CHACO", 59, "keep_from",  k = 3),
  R_("CHACO", 61, "drop_last",  n = 3),
  R_("CHACO", 63, "drop_last",  n = 2),
  R_("CHACO", 64, "drop_last",  n = 2),
  R_("CHACO", 67, "keep_first", n = 3),
  R_("CHACO", 74, "drop_last",  n = 2),
  R_("CHACO", 75, "keep_first", n = 4),
  R_("CHACO", 80, "keep_first", n = 2),
  R_("CHACO", 81, "keep_first", n = 7),
  R_("CHACO", 83, "keep_first", n = 3),
  R_("CHACO", 84, "keep_first", n = 2),
  R_("CHACO", 87, "drop_last",  n = 2),
  R_("CHACO", "sde1", "pre_trim_lt", date = "2009-03-01"),  # recorta el pre-fuego
  R_("CHACO", "sde3", "keep_first", n = 10),
  R_("CHACO", "sde4", "keep_first", n = 10),
  R_("CHACO", "sde5", "drop_last",  n = 1)
)

# ── Match a sheet fire id to the actual fire_id in the data (no zero-pad assumed) ──
# Numeric sheet id n matches the data fire_id whose numeric suffix == n; a "sdeN"
# id matches the fire_id with that exact suffix. Returns NA if absent.
match_fire_id <- function(sheet_fire, data_fire_ids) {
  suffix <- sub("^fire_", "", data_fire_ids)
  if (grepl("^[0-9]+$", as.character(sheet_fire))) {
    num <- suppressWarnings(as.integer(suffix))
    hit <- data_fire_ids[!is.na(num) & num == as.integer(sheet_fire)]
  } else {
    hit <- data_fire_ids[suffix == as.character(sheet_fire)]
  }
  if (length(hit) == 1) hit else NA_character_
}

# ── Resolve a month/day to the year that falls inside the post-fire window ────
resolve_md <- function(month, day, post_lwr, post_upr) {
  yrs <- seq(year(post_lwr), year(post_upr))
  cand <- as.IDate(sprintf("%d-%02d-%02d", yrs, month, day))
  ok <- cand[cand >= post_lwr & cand <= post_upr]
  if (length(ok) >= 1) {
    if (length(ok) > 1) warning(sprintf("ambiguous month/day %02d-%02d in window; using %s", month, day, ok[1]))
    ok[1]
  } else {
    warning(sprintf("month/day %02d-%02d not in post window [%s,%s]; using post_lwr year",
                    month, day, post_lwr, post_upr))
    as.IDate(sprintf("%d-%02d-%02d", year(post_lwr), month, day))
  }
}

# ── Date positions kept by a count/range rule, given sorted unique dates D ─────
kept_dates <- function(D, type, p) {
  L <- length(D)
  idx <- switch(type,
    keep_first = seq_len(min(p$n, L)),
    drop_first = if (p$n < L) seq.int(p$n + 1L, L) else integer(0),
    drop_last  = if (p$n < L) seq_len(L - p$n) else integer(0),
    keep_from  = if (p$k <= L) seq.int(p$k, L) else integer(0),
    keep_range = if (p$a <= L) seq.int(p$a, min(p$b, L)) else integer(0),
    stop("not a date-rank rule: ", type))
  D[idx]
}

DATE_RANK <- c("keep_first", "drop_first", "drop_last", "keep_from", "keep_range")

# ── Apply one rule to a fire's rows; return updated `fit` (logical) ───────────
apply_rule <- function(d, type, p, win) {
  fit <- d$fit
  is_burned_obs <- d$burned == 1L
  if (type %in% DATE_RANK) {
    D <- sort(unique(d$date[is_burned_obs & fit]))   # fire-level unique post-fire dates
    keep <- kept_dates(D, type, p)
    fit[is_burned_obs & !(d$date %in% keep)] <- FALSE
  } else if (type == "keep_nbr_lt") {
    fit[is_burned_obs & !(d$NBR < p$x)] <- FALSE
  } else if (type == "date_drop_ge") {
    fit[is_burned_obs & d$date >= as.IDate(p$date)] <- FALSE
  } else if (type == "date_drop_gt") {
    fit[is_burned_obs & d$date >  as.IDate(p$date)] <- FALSE
  } else if (type == "date_drop_lt") {
    fit[is_burned_obs & d$date <  as.IDate(p$date)] <- FALSE
  } else if (type == "date_drop_ge_md") {
    cut <- resolve_md(p$month, p$day, win$post_lwr, win$post_upr_long)
    fit[is_burned_obs & d$date >= cut] <- FALSE
  } else if (type == "date_drop_gt_md") {
    cut <- resolve_md(p$month, p$day, win$post_lwr, win$post_upr_long)
    fit[is_burned_obs & d$date >  cut] <- FALSE
  } else if (type == "date_drop_lt_md") {
    cut <- resolve_md(p$month, p$day, win$post_lwr, win$post_upr_long)
    fit[is_burned_obs & d$date <  cut] <- FALSE
  } else if (type == "date_keep_ym") {
    in_keep <- year(d$date) == p$year & month(d$date) %in% p$months
    fit[is_burned_obs & !in_keep] <- FALSE
  } else if (type == "pre_trim_lt") {
    fit[d$date < as.IDate(p$date)] <- FALSE            # all points
  } else if (type == "drop_fire") {
    fit[] <- FALSE
  } else if (type == "drop_unburned_keep_first") {
    fit[!d$is_burned_pt] <- FALSE                      # drop unburned-point obs
    D <- sort(unique(d$date[is_burned_obs & fit]))
    keep <- kept_dates(D, "keep_first", list(n = p$n))
    fit[is_burned_obs & !(d$date %in% keep)] <- FALSE
  } else {
    stop("unknown rule type: ", type)
  }
  fit
}

# ── Main ──────────────────────────────────────────────────────────────────────
clean_region <- function(region, version, data_dir) {
  obs_path <- file.path(data_dir, sprintf("training_observations_%s_v%s.csv", region, version))
  tf_path  <- file.path(data_dir, sprintf("training_fires_%s.csv", region))
  message(sprintf("\n=== %s ===", region))
  message(sprintf("  reading %s ...", basename(obs_path)))
  d <- fread(obs_path)
  d[, date := as.IDate(date)]

  # fire windows; pre_lwr fallback = pre_upr - 1 year (same month-day, matching
  # the export's datetime.replace(year=year-1))
  tf <- fread(tf_path)
  for (col in c("pre_lwr", "post_upr_short")) if (!col %in% names(tf)) tf[, (col) := NA_character_]
  tf <- tf[, .(fire_id, pre_lwr = as.IDate(pre_lwr), pre_upr = as.IDate(pre_upr),
               post_lwr = as.IDate(post_lwr), post_upr_long = as.IDate(post_upr_long),
               post_upr_short = as.IDate(post_upr_short))]
  tf[is.na(pre_lwr), pre_lwr := as.IDate(sprintf("%d-%s", year(pre_upr) - 1L, format(pre_upr, "%m-%d")))]
  tf[is.na(post_upr_long), post_upr_long := post_upr_short]   # fallback per docs/02-data_cleaning.md
  d <- merge(d, tf, by = "fire_id", all.x = TRUE, sort = FALSE)

  # point identity (a point is "burned" if it ever carries a burned==1 obs)
  d[, is_burned_pt := any(burned == 1L), by = .(fire_id, point_id)]

  # (1) BASE HARD FILTER — valid window per point type
  d[, fit := fifelse(
    is_burned_pt,
    (date >= pre_lwr & date <= pre_upr) | (date >= post_lwr & date <= post_upr_long),
    date >= pre_lwr & date <= post_upr_long)]
  n_base_drop <- d[fit == FALSE, .N]
  message(sprintf("  base filter: %s obs dropped (outside valid window)", format(n_base_drop, big.mark = ",")))

  # (2) PER-FIRE EDITS
  region_rules <- Filter(function(r) r$region == region, RULES)
  data_fire_ids <- unique(d$fire_id)
  setkey(d, fire_id)
  summary_rows <- list()
  for (r in region_rules) {
    fid <- match_fire_id(r$fire, data_fire_ids)
    if (is.na(fid)) { warning(sprintf("  [%s] fire '%s' not found in data — skipped", region, r$fire)); next }
    rows <- d[fire_id == fid, which = TRUE]
    sub  <- d[rows]
    win  <- list(post_lwr = sub$post_lwr[1], post_upr_long = sub$post_upr_long[1])
    before_fit <- sum(sub$fit)
    new_fit <- apply_rule(sub, r$type, r, win)
    d[rows, fit := new_fit]
    dropped <- before_fit - sum(new_fit)
    summary_rows[[length(summary_rows) + 1]] <- data.table(
      fire = fid, rule = r$type,
      n_burned = sub[burned == 1L, .N], dropped_by_rule = dropped, fit_after = sum(new_fit))
  }
  if (length(summary_rows)) {
    cat(sprintf("  per-fire edits (%d fires):\n", length(summary_rows)))
    print(rbindlist(summary_rows), row.names = FALSE)
  }

  # drop the merged window cols; keep `fit` + originals
  d[, c("pre_lwr", "pre_upr", "post_lwr", "post_upr_long", "post_upr_short", "is_burned_pt") := NULL]
  message(sprintf("  writing %s (fit: %s TRUE / %s total) ...",
                  basename(obs_path), format(sum(d$fit), big.mark = ","), format(nrow(d), big.mark = ",")))
  fwrite(d, obs_path)
  invisible(NULL)
}

args     <- commandArgs(trailingOnly = TRUE)
VERSION  <- if (length(args) >= 1) args[[1]] else "1"
DATA_DIR <- "collection-01/data"
# CLEAN_REGIONS env (comma-separated) overrides the default all-region run.
REGIONS  <- if (nzchar(Sys.getenv("CLEAN_REGIONS")))
  strsplit(Sys.getenv("CLEAN_REGIONS"), ",")[[1]] else c("BA", "CHACO", "PAMPA", "CUYO", "PAT")
for (reg in REGIONS) clean_region(reg, VERSION, DATA_DIR)
message("\nDone. `fit` column written to all region observation CSVs.")
