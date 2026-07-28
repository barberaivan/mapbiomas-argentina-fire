#!/usr/bin/env Rscript
# =============================================================================
# 06-object_model.R — object-based fire / non-fire classification (probit BART)
# =============================================================================
# Pipeline step 06 (R, stochtree). Fits ONE model on the labelled step-05 objects and
# scores every object of a fire-year with a POSTERIOR probability of being fire, so the
# step-07 upload carries a call per object and the round-2 point collection can be aimed
# at the objects the model is unsure about. Design + rationale: docs/06-object_model.md.
#
# Run from the repo ROOT:
#   Rscript collection-01/workflow/06-object_model.R                  # fit, then time one year
#   Rscript collection-01/workflow/06-object_model.R fit
#   Rscript collection-01/workflow/06-object_model.R predict 2020 2014
#   Rscript collection-01/workflow/06-object_model.R predict all      # every fire-year
#   Rscript collection-01/workflow/06-object_model.R cv               # spatially-blocked (regions)
#   Rscript collection-01/workflow/06-object_model.R cv grid 5         # 0.5 deg blocks -> 5 folds
#   Rscript collection-01/workflow/06-object_model.R cv random 5      # random 5-fold, for contrast
# Env: OBJ_THREADS (8) MCMC_ITER (2000) POST_DRAWS (500) NUM_GFR (10) PRED_CHUNK (20000)
# For all years use scripts/run_06_predict.sh (parallel, resumable) — see below.
#
# THE 20 PREDICTORS are objects_data_functions.R::PREDICTORS — 15 non-vegetation metrics plus 5
# aggregated vegetation fractions (the 23 raw frac_c* columns summed by group). docs/06.
#
# THE FITTING SET is the clean labelled table built by
# scripts/objects_data_functions.R::clean_tagged() — one row per OBJECT, with the
# unmatched labels, the both-classes objects, the duplicate labels and any NA predictor
# removed and each cut reported. Uneven label density across objects is deliberately NOT
# corrected: a label is a label, and reweighting by it would invent information.
#
# WHY probit BART VIA stochtree (docs/06 §3): no CV tuning to do honestly on ~5 k
# labels, and the posterior gives a per-object interval — the targeting signal for a round-2
# collection. stochtree's num_threads parallelises the GFR sampler and the MCMC, which is
# genuine within-chain scaling of the fit.
#
# PREDICTION IS SINGLE-THREADED (measured, stochtree 0.4.5): num_threads is a *sampler*
# setting, and predict.bartmodel takes no thread argument — nor do the C++ predict entry
# points. One process pegs one core, so `predict all` runs ~37 min on one core. The years
# are independent, so parallelise at the PROCESS level: scripts/run_06_predict.sh runs one
# Rscript per fire-year, 8 at a time (~5 min), resumable.
#
# MCMC BUDGET. num_mcmc is the RETAINED count and stochtree runs num_mcmc * keep_every
# iterations, so MCMC_ITER=2000 / POST_DRAWS=500 means 2000 iterations thinned by 4 to 500
# posterior draws. Thinning is what makes prediction affordable: cost is linear in draws,
# and 500 draws still put ~25 order statistics below p_q05.
#
# PREDICTION IS THE MEMORY RISK, NOT THE FIT (docs/06). Never pass the full object set as
# X_test to bart(): 1.69 M objects x 500 draws is 6.8 GB of doubles. Instead fit, serialize
# to JSON, and predict per fire-year in PRED_CHUNK-row blocks, reducing each block to its
# summaries and discarding the draws. Peak memory is then one block (20 k x 500 = 80 MB).
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(stochtree)
})
source("collection-01/scripts/objects_data_functions.R")

# ── args ─────────────────────────────────────────────────────────────────────
argv <- commandArgs(trailingOnly = TRUE)
pos  <- argv[!grepl("^--", argv)]
mode <- if (length(pos)) pos[1] else "probe"
rest <- if (length(pos)) pos[-1] else character()

# ── config ───────────────────────────────────────────────────────────────────
MODEL_DIR  <- OBJ_MODEL_DIR
PRED_DIR   <- OBJ_PRED_DIR
PROBE_YEAR <- 2020L        # the default single-year timing probe (78 k objects, the big one)

FIT_JSON   <- file.path(MODEL_DIR, "bart_object_model.json")
FIT_META   <- file.path(MODEL_DIR, "bart_object_model_meta.rds")

envi <- function(k, d) { v <- suppressWarnings(as.integer(Sys.getenv(k, ""))); if (is.na(v)) d else v }
# 8 = PHYSICAL cores. Tree sampling is memory-bandwidth-bound, so the 8 extra hyperthreads
# mostly add contention (docs/06). num_threads == 1 on Linux/gcc would mean a broken build.
THREADS    <- envi("OBJ_THREADS", 8L)
MCMC_ITER  <- envi("MCMC_ITER",  2000L)
POST_DRAWS <- envi("POST_DRAWS",  500L)
NUM_GFR    <- envi("NUM_GFR",      10L)   # grow-from-root warm start; iterations are cheap
PRED_CHUNK <- envi("PRED_CHUNK", 20000L)
GRID_DEG   <- 0.5          # ~50 km spatial blocks for `cv grid` (see do_cv)
# Size-band cuts on p_mean live in THRESH_CSV (objects_data_functions.R), chosen on out-of-fold
# predictions by scripts/objects_threshold.R. Absent -> predict falls back to 0.5 and says so.
# The bands rise with size (0.18 / 0.41 / 0.60) because the model is far more confident on big
# objects; docs/06 §6.

msg <- function(...) write(sprintf(...), stderr())
hdr <- function(s) { msg(""); msg("== %s ==", s) }
elapsed <- function(t0) as.numeric(difftime(Sys.time(), t0, units = "secs"))

# ── design matrix — one definition, used by fit and by predict ───────────────
# Column ORDER is part of the model: it is stored in the meta file and re-imposed here, so
# a predict run in a fresh process cannot silently permute the predictors.
design <- function(d, cols = PREDICTORS) {
  miss <- setdiff(cols, names(d))
  if (length(miss)) stop("missing predictor(s): ", paste(miss, collapse = ", "))
  as.matrix(d[, ..cols])
}

fit_bart <- function(X, y) {
  msg("fitting: %d objects x %d predictors | %d GFR + %d MCMC iterations thinned by %d",
      nrow(X), ncol(X), NUM_GFR, MCMC_ITER, MCMC_ITER %/% POST_DRAWS)
  msg("         -> %d retained posterior draws | num_threads = %d", POST_DRAWS, THREADS)
  t0 <- Sys.time()
  m <- bart(
    X_train = X, y_train = y,
    num_gfr = NUM_GFR, num_burnin = 0L, num_mcmc = POST_DRAWS,
    general_params = list(
      # probit BART (Albert-Chib latent augmentation). The residual-variance warning is
      # expected: with a probit link sigma^2 is fixed at 1, not sampled.
      outcome_model = OutcomeModel(outcome = "binary", link = "probit"),
      keep_every    = MCMC_ITER %/% POST_DRAWS,
      num_threads   = THREADS))
  msg("fit done in %.1f s", elapsed(t0))
  m
}

# n x draws probability matrix -> the four DBF-safe per-object summaries (docs/06).
# These bound the PROBABILITY (epistemic uncertainty about the fitted function), not the
# class label: a predictive interval for a Bernoulli draw would be 0/1 and useless.
summarise_draws <- function(P) {
  k  <- ncol(P)
  mu <- rowMeans(P)
  sd <- sqrt(pmax(0, (rowSums(P * P) - k * mu * mu) / (k - 1)))
  q  <- apply(P, 1L, quantile, probs = c(0.05, 0.95), names = FALSE, na.rm = TRUE)
  data.table(p_mean = round(mu, 4), p_sd = round(sd, 4),
             p_q05 = round(q[1, ], 4), p_q95 = round(q[2, ], 4),
             p_width = round(q[2, ] - q[1, ], 4))
}

# Per-object fire call. Reads the size-band thresholds if they exist, else 0.5 everywhere.
# The band lookup itself is apply_thresholds() (objects_data_functions.R) so that the QGIS
# inspection layer calls fire exactly the way the product does.
fire_call <- function(area_ha, p) {
  if (!file.exists(THRESH_CSV)) {
    msg("  no %s — calling fire at the 0.5 default", basename(THRESH_CSV))
    return(list(fire = as.integer(p > 0.5), rule = "p > 0.5"))
  }
  th <- threshold_table()
  list(fire = apply_thresholds(area_ha, p)$fire,
       rule = paste(sprintf("%s: p>%.3f", th$stratum, th$threshold), collapse = " | "))
}

# n x draws matrix of P(fire). With terms = "y_hat" stochtree returns the matrix bare;
# with several terms it returns a named list — accept both so a version bump cannot break it.
predict_prob <- function(model, X) {
  p <- predict(model, X, type = "posterior", terms = "y_hat", scale = "probability")
  if (is.list(p)) p$y_hat else p
}

# ── [1] fit ──────────────────────────────────────────────────────────────────
do_fit <- function() {
  hdr("fitting set")
  tag <- clean_tagged()
  X <- design(tag); y <- as.numeric(tag$class)

  hdr("fit")
  m <- fit_bart(X, y)

  hdr("in-sample fit (NOT validation — see `cv` mode for out-of-fold)")
  p <- rowMeans(predict_prob(m, X))
  msg("AUC %.4f | accuracy@0.5 %.4f", auc_fast(p, tag$class), mean((p > .5) == (tag$class == 1L)))
  print(pass_report(p > .5, tag$class))

  dir.create(MODEL_DIR, showWarnings = FALSE, recursive = TRUE)
  saveBARTModelToJsonFile(m, FIT_JSON)
  saveRDS(list(predictors = PREDICTORS, n_train = nrow(X), draws = POST_DRAWS,
               mcmc_iter = MCMC_ITER, num_gfr = NUM_GFR, threads = THREADS,
               clean_report = attr(tag, "clean_report"), fitted_at = Sys.time(),
               train_auc = auc_fast(p, tag$class)), FIT_META)
  msg("saved %s (%.1f MB) + %s", FIT_JSON, file.size(FIT_JSON) / 1024^2, basename(FIT_META))
  invisible(m)
}

# ── [2] predict one fire-year, in chunks, timed ─────────────────────────────
do_predict <- function(years) {
  if (!file.exists(FIT_JSON)) stop("no fit at ", FIT_JSON, " — run `fit` first")
  meta  <- readRDS(FIT_META)
  t0    <- Sys.time()
  model <- createBARTModelFromJsonFile(FIT_JSON)
  msg("loaded fit (%d draws, %d training objects) in %.1f s",
      meta$draws, meta$n_train, elapsed(t0))
  dir.create(PRED_DIR, showWarnings = FALSE, recursive = TRUE)
  # the collected labels, once for every year: fire_tag overrides fire_model in the deployed
  # `fire` column (objects_data_functions.R "the collected tag, and the deployed fire call")
  tags <- tag_lookup(verbose = TRUE)

  for (fy in years) {
    hdr(sprintf("predict fire-year %d", fy))
    t_load <- Sys.time()
    obj <- read_year_objects(fy)
    msg("  %d objects read in %.1f s", nrow(obj), elapsed(t_load))

    # NA predictors cannot be scored (all-dieback objects, docs/05 §3): carry them through
    # with NA probabilities rather than dropping the oid from the year's output.
    ok <- complete.cases(obj[, ..PREDICTORS])
    X  <- design(obj[ok], meta$predictors)

    t_pred <- Sys.time()
    idx <- split(seq_len(nrow(X)), ceiling(seq_len(nrow(X)) / PRED_CHUNK))
    out <- vector("list", length(idx))
    for (i in seq_along(idx)) {
      out[[i]] <- summarise_draws(predict_prob(model, X[idx[[i]], , drop = FALSE]))
      if (i %% 2L == 0L || i == length(idx))
        msg("  chunk %d/%d (%d rows) %.1f s elapsed", i, length(idx), length(idx[[i]]),
            elapsed(t_pred))
    }
    dt_pred <- elapsed(t_pred)

    res <- data.table(oid = obj$oid, fire_year = fy)
    res[ok, names(out[[1]]) := rbindlist(out)]
    fc <- fire_call(obj$area_ha, res$p_mean)
    res[, fire_model := fc$fire]
    # fire_tag: -1 where no collaborator labelled this object (NOT 0 — see TAG_NONE)
    res[tags, fire_tag := i.fire_tag, on = "oid"]
    res[is.na(fire_tag), fire_tag := TAG_NONE]
    res[, fire := resolve_fire(fire_model, fire_tag)]
    f <- file.path(PRED_DIR, sprintf("objects_%d_pred.csv", fy))
    fwrite(res, f, na = "NA")

    # DERIVED PREDICTORS, for the upload (docs/07). 12 of the 20 predictors are verbatim columns of
    # the step-05 metrics CSVs, but 8 are built here by add_derived()/add_veg_groups() and exist
    # nowhere on disk. scripts/objects_upload.py needs all 20 on the FeatureCollection, and
    # reimplementing the veg grouping in Python would duplicate logic that is deliberately derived
    # from config/veg_fire_remap.csv BY NAME — so R writes them out instead. Keyed on oid.
    derived <- intersect(c("doy_sin", "doy_cos", "date_span", VEG_GROUP_COLS), names(obj))
    fd <- file.path(PRED_DIR, sprintf("objects_%d_derived.csv", fy))
    fwrite(obj[, c("oid", derived), with = FALSE], fd, na = "NA")
    n_tag <- sum(res$fire_tag >= 0L)
    if (n_tag)
      msg("  %d tagged object(s) (%d fire / %d non-fire) override the model on %d call(s)",
          n_tag, sum(res$fire_tag == 1L), sum(res$fire_tag == 0L),
          sum(res$fire_tag >= 0L & res$fire_tag != res$fire_model, na.rm = TRUE))

    msg("  predicted %d objects x %d draws in %.1f s (%.0f obj/s, %.1f us/obj/draw)",
        nrow(X), meta$draws, dt_pred, nrow(X) / dt_pred,
        1e6 * dt_pred / (nrow(X) * meta$draws))
    msg("  fire call [%s]", fc$rule)
    msg("  -> %d objects (%.1f %%), %.0f of %.0f kha   [at 0.5 it would be %d / %.0f kha]",
        sum(res$fire_model, na.rm = TRUE), 100 * mean(res$fire_model, na.rm = TRUE),
        sum(obj$area_ha[which(res$fire_model == 1L)]) / 1e3, sum(obj$area_ha) / 1e3,
        sum(res$p_mean > .5, na.rm = TRUE), sum(obj$area_ha[which(res$p_mean > .5)]) / 1e3)
    msg("  mean p_width %.3f | widest decile > %.3f  (round-2 collection targets)",
        mean(res$p_width, na.rm = TRUE), quantile(res$p_width, .9, na.rm = TRUE))
    msg("  -> %s (%.1f MB)", f, file.size(f) / 1024^2)

    # what the same rate implies for the whole country, the number that decides whether
    # per-year chunked prediction is viable at all (docs/06 §3)
    all_n <- 1689419
    msg("  extrapolated to all %s objects: %.1f min at this rate", format(all_n, big.mark = ","),
        dt_pred / nrow(X) * all_n / 60)
    rm(obj, X, out, res); gc(FALSE)
  }
}

# ── [3] cross-validation — not tuning (BART needs none), just honest error ──
# `cv` (default) = SPATIALLY BLOCKED, leave-one-region-out over the 5 MapBiomas Argentina
# regions (2 km buffered asset, scripts/objects_data_functions.R::assign_region). Blocking is
# the point: objects labelled by one drawn polygon are adjacent, and random folds put those
# neighbours on both sides of the split, which flatters the model. Held-out region prevalence
# ranges 0.10 (Patagonia) to 0.83 (Pampas), so read the AUC (prevalence-invariant) as the
# headline and treat sensitivity/specificity at the fixed 0.5 cut as confounded by that shift.
# `cv random [K]` keeps the optimistic version for comparison.
group_metrics <- function(p, y, g, label = "group") {
  out <- rbindlist(lapply(sort(unique(g)), function(k) {
    i <- which(g == k)
    cbind(data.table(grp = as.character(k), prevalence = round(mean(y[i] == 1L), 3),
                     auc = round(auc_fast(p[i], y[i]), 4)),
          pass_report(p[i] > .5, y[i]))
  }))
  setnames(out, "grp", label)
  out[]
}

do_cv <- function(spec = "region") {
  tag <- clean_tagged()
  X <- design(tag); y <- as.numeric(tag$class)
  if (identical(spec, "region")) {
    tag  <- assign_region(tag)
    fold <- tag$region
    hdr("spatially-blocked CV — leave-one-region-out")
  } else if (grepl("^grid", spec)) {
    # The middle design, and the one closest to deployment: block by GRID_DEG cells, then deal
    # whole cells into K folds. Every region is present in every fold (so the model is never
    # asked to extrapolate to an unseen ecoregion, which it never has to do in production),
    # but no label shares a neighbourhood with its own fold-mates.
    K <- as.integer(sub("^grid:?", "", spec)); if (is.na(K)) K <- 5L
    cell <- paste(floor(tag$lon / GRID_DEG), floor(tag$lat / GRID_DEG))
    set.seed(1L)
    u    <- sample(unique(cell))
    fold <- as.character(setNames(rep_len(seq_len(K), length(u)), u)[cell])
    hdr(sprintf("spatially-blocked CV — %g deg blocks dealt into %d folds (%d blocks)",
                GRID_DEG, K, length(u)))
  } else {
    K <- as.integer(spec); set.seed(1L)
    fold <- as.character(sample(rep_len(seq_len(K), nrow(X))))
    hdr(sprintf("random %d-fold CV (optimistic — adjacent objects straddle folds)", K))
  }
  p <- rep(NA_real_, nrow(X))
  for (k in sort(unique(fold))) {
    t0 <- Sys.time(); tr <- fold != k
    m <- fit_bart(X[tr, , drop = FALSE], y[tr])
    p[!tr] <- rowMeans(predict_prob(m, X[!tr, , drop = FALSE]))
    msg("  held out %-26s n=%4d (prev %.2f) | train n=%4d | AUC %.4f | %.0f s",
        k, sum(!tr), mean(tag$class[!tr] == 1L), sum(tr),
        auc_fast(p[!tr], tag$class[!tr]), elapsed(t0))
  }

  hdr("out-of-fold — whole labelled set")
  print(group_metrics(p, tag$class, rep("all", length(p)), "set"))
  hdr("out-of-fold — by size, i.e. where the error lives")
  print(group_metrics(p, tag$class, ifelse(tag$area_ha < 1, "1 <1 ha", "2 >=1 ha"), "size"))
  print(group_metrics(p, tag$class, as.character(c00_case(tag)), "size_case"))
  hdr(sprintf("out-of-fold — per %s", if (identical(spec, "region")) "region" else "fold"))
  print(group_metrics(p, tag$class, fold, "fold"))

  dir.create(PRED_DIR, showWarnings = FALSE, recursive = TRUE)
  f <- file.path(PRED_DIR, sprintf("oof_%s.csv", gsub("[^A-Za-z0-9]+", "_", spec)))
  fwrite(data.table(oid = tag$oid, class = tag$class, fire_year = tag$fire_year,
                    area_ha = round(tag$area_ha, 3),
                    region = if ("region" %in% names(tag)) tag$region else NA_character_,
                    fold = fold, p_oof = round(p, 4)), f)
  msg("out-of-fold predictions -> %s", f)
}

# ── main ─────────────────────────────────────────────────────────────────────
# cv arg forms: (none)->region | region | grid [K] | random [K]
cv_spec <- function(a) {
  if (!length(a)) return("region")
  if (identical(a[1], "grid"))   return(paste0("grid:", if (length(a) > 1L) a[2] else "5"))
  if (identical(a[1], "random")) return(if (length(a) > 1L) a[2] else "5")
  a[1]
}

years_arg <- function(a) if (!length(a)) PROBE_YEAR else
  if (identical(a[1], "all")) object_years() else as.integer(a)

switch(mode,
  fit     = do_fit(),
  predict = do_predict(years_arg(rest)),
  cv      = do_cv(cv_spec(rest)),
  probe   = { do_fit(); do_predict(PROBE_YEAR) },
  stop("unknown mode '", mode, "' — use fit | predict | cv"))
