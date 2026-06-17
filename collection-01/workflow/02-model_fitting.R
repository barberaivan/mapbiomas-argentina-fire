#!/usr/bin/env Rscript
# =============================================================================
# 02-model_fitting.R  — fit one elastic-net logistic regression per veg_fire class
# =============================================================================
# Pipeline step 02 (R). Fits locally with glmnet. The fitting unit is the
# **veg_fire class**, NOT the region: a class may span regions (e.g.
# shrubland_cuyo-pampa), so the driver loads whichever region tables a class
# needs (from config/veg_fire_remap.csv) and skips classes whose regions are not
# all exported yet. Run from repo root, in an R IDE (RStudio / Positron) or:
#
#   Rscript collection-01/workflow/02-model_fitting.R [version] [class_name ...]
#     version       default "1"
#     class_name…   optional; restrict to these veg_fire classes (default: all
#                   fittable classes whose region data is available)
#   e.g.  Rscript collection-01/workflow/02-model_fitting.R 1
#         Rscript collection-01/workflow/02-model_fitting.R 1 grassland_pat
#
# Run scripts/cv_feasibility_report.py FIRST per region to confirm usable K.
#
# STRUCTURE (region exceptions stay contained):
#   * Generic machinery — design matrix, fold packing, CV, tuning, metrics, IO —
#     is class/region-agnostic.
#   * ALL class-specific sample rules live in SAMPLE_RULES (keyed by veg_fire_name,
#     which already encodes region) and are applied by assemble_class_data().
#   * fit_one_class() fits one model; main() resolves regions per class and loops.
#
# CV design (see models/README.md):
#   Grouped K-fold (K=10), group = region-unique fire id (region_fireid, since
#   bare fire_ids repeat across regions) → leave-several-fires-out.
#   Folds per class via stratified greedy packing (balance obs + positives).
#   Pure-negative fires (ash/drought, crops; burned=0 within their region) are
#   point-distributed across folds, not held out. Adaptive K = min(10, n_fires_with_positives).
#   Elastic net alpha ∈ {0,.25,.5,.75,1}, same foldid across alphas, tuned on
#   binomial deviance. Out-of-fold p_i saved per obs.
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(glmnet)
  library(doParallel)
})

here_root <- function() {
  a <- commandArgs(FALSE); f <- sub("^--file=", "", a[grep("^--file=", a)])
  if (length(f)) normalizePath(file.path(dirname(f), "..", "..")) else normalizePath(".")
}

# ── config ───────────────────────────────────────────────────────────────────
args         <- commandArgs(trailingOnly = TRUE)
VERSION      <- if (length(args) >= 1) args[[1]] else "1"
CLASS_FILTER <- if (length(args) >= 2) args[-1] else character(0)
REGIONS_ALL  <- c("BA", "CHACO", "PAMPA", "CUYO", "PAT")
K_TARGET    <- 10
ALPHAS      <- c(0, 0.25, 0.5, 0.75, 1)
LAMBDA_RULE <- "1se"   # "1se" (more regularized, sparser) or "min" (best CV deviance)
CORES       <- as.integer(Sys.getenv("FIT_CORES", unset = "5"))  # parallel CV folds; override per run, e.g. FIT_CORES=2 (grassland is memory-heavy)
SEED        <- 1
EPS         <- 1e-15

root       <- here_root()
remap_csv  <- file.path(root, "collection-01", "config", "veg_fire_remap.csv")
out_dir    <- file.path(root, "collection-01", "models")
region_csv <- function(reg) file.path(root, "collection-01", "data",
                       sprintf("training_observations_%s_v%s.csv", reg, VERSION))
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

# ── class sample exceptions (the ONLY place class-specific logic lives) ───────
# ash_merge: train this class on its own non-ash obs + the pooled ash (negatives)
#            of all listed classes (when a class alone has too few ash negatives).
# ash_frac:  downsample this class's ash negatives to this fraction of its unburned.
SAMPLE_RULES <- list(
  forest_pat    = list(ash_merge = c("forest_pat", "shrubland_pat")),
  shrubland_pat = list(ash_merge = c("forest_pat", "shrubland_pat")),
  grassland_pat = list(ash_frac  = 0.10)
)

# ── canonical-team design (427 terms; logistic_regression_terms.qmd §"Canonical team") ──
FOCAL <- c("BLUE","GREEN","RED","NIR","SWIR1","SWIR2","NBR","NBR2","MIRBI","NDVI",
           "TCB","TCG","TCW","NDMI","NDSI","SAVI","NDWI","AFRI","kNDVI","EVI2","NIRv")  # 21
PREV_VARS <- c("blue","green","red","nir","swir1","swir2","ndvi","ndwi","npv","ndfi") # 10
SUMM      <- c(med = "median", wet = "median_wet", dry = "median_dry", sd = "stdDev") # 4
FIRE_IDX  <- c("NBR","NBR2","MIRBI","NDVI")
FIRE_BAND <- c("RED","NIR","SWIR1","SWIR2")
SAMEBAND  <- c("blue","green","red","nir","swir1","swir2","ndvi","ndwi")
CONTEXT   <- c("ndvi","ndwi","npv","ndfi")
prev_col  <- function(v, s) sprintf("mb_mos_%s_%s", v, SUMM[[s]])
# Block sizes in build_design column order — used to label the coefficient export.
BLOCKS    <- c(focal = 21, prev = 40, pairs = 210, sameband = 32, cross_idx = 60, cross_band = 64)

# Design matrix in the GEE band-name convention (logistic_regression_terms.qmd §Computational):
#   focal -> "<FEAT>_t" ; prev -> "<VAR>_<med|wet|dry|sd>" ; interaction -> "A__B".
# Column ORDER matches the GEE block-multiply order (focal, prev, pairs, sameband,
# cross_idx, cross_band) so exported coefNames/coefValues line up band-for-band.
focal_nm <- function(f) paste0(f, "_t")
prev_nm  <- function(v, s) sprintf("%s_%s", toupper(v), s)        # s in med/wet/dry/sd

build_design <- function(d) {
  num <- function(nm) { x <- as.numeric(d[[nm]]); x[is.na(x)] <- 0; x }
  Fm <- vapply(FOCAL, num, numeric(nrow(d))); colnames(Fm) <- focal_nm(FOCAL)   # B1: 21

  pg  <- do.call(rbind, lapply(PREV_VARS, function(v) data.frame(v = v, s = names(SUMM),
                                                                 stringsAsFactors = FALSE)))
  Pm  <- vapply(seq_len(nrow(pg)), function(i) num(prev_col(pg$v[i], pg$s[i])), numeric(nrow(d)))
  colnames(Pm) <- prev_nm(pg$v, pg$s)                                           # B2: 40

  cb <- combn(colnames(Fm), 2)                                                  # B3: 210
  B3 <- Fm[, cb[1, ]] * Fm[, cb[2, ]]; colnames(B3) <- paste(cb[1, ], cb[2, ], sep = "__")

  cross <- function(prevs, focals, skip = NULL) {                               # B4–B6 helper
    cols <- list()
    for (v in prevs) for (s in names(SUMM)) for (f in focals) {
      if (!is.null(skip) && skip(v, f)) next
      pn <- prev_nm(v, s); fn <- focal_nm(f)
      cols[[paste(pn, fn, sep = "__")]] <- Pm[, pn] * Fm[, fn]
    }
    m <- do.call(cbind, cols); colnames(m) <- names(cols); m
  }
  B4 <- do.call(cbind, lapply(SAMEBAND, function(v) cross(v, toupper(v))))      # B4: 32
  B5 <- cross(CONTEXT, FIRE_IDX, skip = function(v, f) v == "ndvi" && f == "NDVI")  # B5: 60
  B6 <- cross(CONTEXT, FIRE_BAND)                                               # B6: 64

  X <- cbind(Fm, Pm, B3, B4, B5, B6); stopifnot(ncol(X) == sum(BLOCKS)); X
}

# ── generic helpers ──────────────────────────────────────────────────────────
log_loss  <- function(y, p) { p <- pmin(pmax(p, EPS), 1 - EPS); -mean(y*log(p)+(1-y)*log(1-p)) }
brier     <- function(y, p) mean((p - y)^2)
auc <- function(y, p) {
  n1 <- sum(y == 1); n0 <- sum(y == 0); if (n1 == 0 || n0 == 0) return(NA_real_)
  (sum(rank(p)[y == 1]) - n1 * (n1 + 1) / 2) / (n1 * n0)
}

make_foldid <- function(d, pure_neg, K) {
  ash <- d$fire_uid %in% pure_neg          # pure_neg is keyed on region-unique ids
  g   <- d$fire_uid
  per <- data.table(g = g, b = d$burned)[!ash, .(n = .N, pos = sum(b)), by = g]
  pos_fires  <- per[pos > 0][order(-pos)]
  zero_fires <- per[pos == 0][order(-n)]
  K <- min(K, nrow(pos_fires)); if (K < 2L) return(NULL)

  fold_pos <- numeric(K); fold_n <- numeric(K); fmap <- new.env(parent = emptyenv())
  place <- function(gn, n, pos, by) {
    k <- if (by == "pos") which.min(fold_pos) else which.min(fold_n)
    fold_pos[k] <<- fold_pos[k] + pos; fold_n[k] <<- fold_n[k] + n
    assign(gn, k, envir = fmap)
  }
  for (i in seq_len(nrow(pos_fires)))  place(pos_fires$g[i],  pos_fires$n[i],  pos_fires$pos[i], "pos")
  for (i in seq_len(nrow(zero_fires))) place(zero_fires$g[i], zero_fires$n[i], 0,                "n")

  fold_by_g <- vapply(ls(fmap), get, integer(1), envir = fmap)   # named: g -> fold
  foldid <- unname(fold_by_g[g])                                 # per-obs; NA on ash rows
  ash_idx <- which(is.na(foldid))
  if (length(ash_idx)) { s <- sample(ash_idx); foldid[s] <- rep_len(seq_len(K), length(s)) }
  as.integer(foldid)
}

# Apply the class sample rule; return this class's training rows from the loaded data.
assemble_class_data <- function(dt, code, name, name2code, pure_neg) {
  ash <- dt$fire_uid %in% pure_neg         # region-unique ids (see main())
  rule <- SAMPLE_RULES[[name]]
  if (is.null(rule)) return(dt[veg_fire == code])
  if (!is.null(rule$ash_merge)) {
    codes <- name2code[rule$ash_merge]
    return(rbind(dt[veg_fire == code & !ash], dt[veg_fire %in% codes & ash]))
  }
  if (!is.null(rule$ash_frac)) {
    own_non <- dt[veg_fire == code & !ash]; own_ash <- dt[veg_fire == code & ash]
    target  <- round(rule$ash_frac / (1 - rule$ash_frac) * sum(own_non$burned == 0))
    if (nrow(own_ash) > target) own_ash <- own_ash[sample(.N, target)]
    return(rbind(own_non, own_ash))
  }
  dt[veg_fire == code]
}

# ── fit one class ─────────────────────────────────────────────────────────────
fit_one_class <- function(sub, code, name, name2code, pure_neg) {
  set.seed(SEED + code)
  tag <- sprintf("class_%02d", code)
  message(sprintf("\n[%s] %s — %d obs, %d positives (rule: %s)", tag, name,
                  nrow(sub), sum(sub$burned),
                  if (is.null(SAMPLE_RULES[[name]])) "default" else
                    paste(names(SAMPLE_RULES[[name]]), collapse = ",")))

  foldid <- make_foldid(sub, pure_neg, K_TARGET)
  if (is.null(foldid)) { message("  too few positive-bearing fires — skipped."); return(NULL) }
  K <- length(unique(foldid))

  Xfull <- build_design(sub); y <- as.numeric(sub$burned)
  all_terms <- colnames(Xfull)                   # canonical 427, block order, GEE names
  keep <- which(apply(Xfull, 2, function(z) sd(z) > 0))
  if (length(keep) < ncol(Xfull)) message(sprintf("  dropped %d zero-variance terms", ncol(Xfull) - length(keep)))
  x <- Xfull[, keep, drop = FALSE]
  rm(Xfull); gc()                                # free the full design (~2 GB for big classes)

  # cv.glmnet handles the lambda path (warm starts), per-fold deviance, the across-
  # fold SE, and lambda.min/lambda.1se. keep=TRUE returns fit.preval = out-of-fold
  # fitted values per obs × lambda (link scale for binomial), our source for p_i.
  results <- vector("list", length(ALPHAS)); tuning <- vector("list", length(ALPHAS))
  for (j in seq_along(ALPHAS)) {
    a   <- ALPHAS[j]
    cvf <- cv.glmnet(x, y, family = "binomial", alpha = a, foldid = foldid,
                     type.measure = "deviance", keep = TRUE, parallel = TRUE)
    results[[j]] <- list(alpha = a, cvf = cvf,
                         imin = match(cvf$lambda.min, cvf$lambda),
                         i1se = match(cvf$lambda.1se, cvf$lambda))
    tuning[[j]]  <- data.table(alpha = a, lambda = cvf$lambda, cvm = cvf$cvm, cvsd = cvf$cvsd)
  }
  # alpha chosen on best achievable fit (lambda.min cvm); the lambda rule sets sparsity
  ja  <- which.min(vapply(results, function(r) r$cvf$cvm[r$imin], numeric(1)))
  r   <- results[[ja]]; cvf <- r$cvf
  sel_lambda <- if (LAMBDA_RULE == "1se") cvf$lambda.1se else cvf$lambda.min
  sel <- match(sel_lambda, cvf$lambda)
  to_prob <- function(v) if (all(v >= 0 & v <= 1, na.rm = TRUE)) v else plogis(v)  # link → prob
  best <- list(alpha = r$alpha, lambda = sel_lambda, dev = cvf$cvm[sel],
               oof = to_prob(cvf$fit.preval[, sel]),
               lambda_min = cvf$lambda.min, lambda_1se = cvf$lambda.1se,
               dev_min = cvf$cvm[r$imin], dev_1se = cvf$cvm[r$i1se])
  message(sprintf("  alpha=%.2f | lambda.min=%.4g (dev %.4f), lambda.1se=%.4g (dev %.4f) -> using %s (K=%d)",
                  best$alpha, best$lambda_min, best$dev_min, best$lambda_1se, best$dev_1se, LAMBDA_RULE, K))

  # Coefficients on the ORIGINAL feature scale (glmnet standardize=TRUE returns them so).
  # Export the full canonical 427 terms + intercept, block-labelled, in GEE block order,
  # with dropped/zeroed terms set to 0 — so GEE reads coefNames/coefValues positionally safe.
  glmfit <- cvf$glmnet.fit                       # full-data path already fit by cv.glmnet
  fitted <- coef(glmfit, s = sel_lambda)[, 1]    # named: "(Intercept)" + kept terms
  ic     <- which(names(fitted) == "(Intercept)")
  cf     <- setNames(numeric(length(all_terms)), all_terms)
  cf[names(fitted[-ic])] <- fitted[-ic]          # dropped zero-variance terms stay 0
  coef_dt <- rbind(
    data.table(block = "(intercept)", term = "(Intercept)", coefficient = unname(fitted[ic])),
    data.table(block = rep(names(BLOCKS), BLOCKS), term = all_terms, coefficient = as.numeric(cf)))
  p <- best$oof

  fwrite(coef_dt, file.path(out_dir, sprintf("%s_coefficients.csv", tag)))
  fwrite(rbindlist(tuning), file.path(out_dir, sprintf("%s_tuning.csv", tag)))
  fwrite(data.table(fire_id = sub$fire_id, point_id = sub$point_id, date = sub$date,
                    region = sub$region, veg_fire = code, burned = y, foldid = foldid, p_oof = p),
         file.path(out_dir, sprintf("%s_oof_predictions.csv", tag)))
  saveRDS(glmfit, file.path(out_dir, sprintf("%s_fit.rds", tag)))

  m <- data.table(veg_fire = code, veg_fire_name = name, regions = paste(sort(unique(sub$region)), collapse = "+"),
             n_obs = nrow(sub), n_pos = sum(y), K = K, n_terms = length(keep),
             alpha = best$alpha, lambda_rule = LAMBDA_RULE, lambda = best$lambda,
             lambda_min = best$lambda_min, lambda_1se = best$lambda_1se,
             cv_deviance = best$dev, cv_logloss = log_loss(y, p),
             cv_brier = brier(y, p), cv_auc = auc(y, p),
             n_nonzero = sum(cf != 0))
  fwrite(m, file.path(out_dir, sprintf("%s_cv_metrics.csv", tag)))   # per-class, self-contained
  m
}

# ── main: resolve regions per class, load only what's needed, fit ─────────────
main <- function() {
  stopifnot(file.exists(remap_csv))
  registerDoParallel(cores = CORES)                 # fork backend; parallelizes CV folds
  on.exit(stopImplicitCluster(), add = TRUE)
  message(sprintf("Parallel CV folds across %d cores.", CORES))
  remap <- fread(remap_csv)
  classes   <- unique(remap[fittable == TRUE, .(veg_fire, veg_fire_name)])[order(veg_fire)]
  name2code <- setNames(classes$veg_fire, classes$veg_fire_name)
  if (length(CLASS_FILTER)) classes <- classes[veg_fire_name %in% CLASS_FILTER]

  avail <- REGIONS_ALL[file.exists(vapply(REGIONS_ALL, region_csv, character(1)))]
  message(sprintf("Available region tables (v%s): %s", VERSION,
                  if (length(avail)) paste(avail, collapse = ", ") else "NONE"))

  load_region <- function(reg) {
    message(sprintf("  loading %s ...", basename(region_csv(reg))))
    d <- fread(region_csv(reg))
    # Guard: the obs 'region' column must match the remap/filename spelling, else the
    # mb_class_raw join (which selects remap[region == reg]) is silently wrong.
    obs_regs <- unique(as.character(d$region))
    if (!all(obs_regs == reg))
      stop(sprintf("Region label mismatch in %s: 'region' column = {%s} but expected '%s'. ",
                   basename(region_csv(reg)), paste(obs_regs, collapse = ", "), reg),
           "Reconcile the export or the region token before fitting.")
    rmp <- remap[region == reg, .(mb_class_raw, veg_fire, veg_fire_name, fittable)]
    if (!nrow(rmp))
      stop(sprintf("No remap rows for region '%s' in %s.", reg, basename(remap_csv)))
    d <- merge(d, rmp, by = "mb_class_raw", all.x = TRUE)
    # Guard: every obs must map to a veg_fire class (mb_class_raw present in remap).
    n_unmapped <- d[is.na(veg_fire), .N]
    if (n_unmapped > 0L)
      warning(sprintf("%s: %d obs have mb_class_raw not in the %s remap (veg_fire = NA); "
                      , basename(region_csv(reg)), n_unmapped, reg),
              "they are excluded from all class fits. mb_class_raw values: ",
              paste(sort(unique(d[is.na(veg_fire), mb_class_raw])), collapse = ", "))
    d
  }

  metrics <- list()
  for (i in seq_len(nrow(classes))) {
    code <- classes$veg_fire[i]; name <- classes$veg_fire_name[i]
    regs <- sort(remap[veg_fire_name == name, unique(region)])
    miss <- setdiff(regs, avail)
    if (length(miss)) {
      message(sprintf("[class_%02d] %s — SKIP (needs %s; missing %s)",
                      code, name, paste(regs, collapse = "+"), paste(miss, collapse = ",")))
      next
    }
    dt       <- if (length(regs) == 1) load_region(regs) else rbindlist(lapply(regs, load_region))
    # fire_ids repeat across regions, so build a region-unique key (region_fireid)
    # before any fire-level grouping: pure-neg detection, fold packing, ash masking.
    dt[, fire_uid := paste0(region, "_", fire_id)]
    pure_neg <- dt[, .(p = sum(burned)), by = fire_uid][p == 0, fire_uid]
    sub      <- assemble_class_data(dt, code, name, name2code, pure_neg)
    rm(dt); gc()
    m <- fit_one_class(sub, code, name, name2code, pure_neg)
    if (!is.null(m)) metrics[[length(metrics) + 1]] <- m
  }

  if (length(metrics)) {
    fwrite(rbindlist(metrics), file.path(out_dir, sprintf("cv_metrics_v%s.csv", VERSION)))
    message(sprintf("\nDone. Fitted %d class(es). Outputs in collection-01/models/.", length(metrics)))
  } else {
    message("\nNo classes fitted (no complete region data for the requested classes).")
  }
}

main()
