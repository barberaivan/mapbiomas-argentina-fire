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
# DESIGN (reduced 129-term set; see notebooks/predictors_terms_correlations.qmd):
#   The old canonical 427-term design was highly collinear and slow to fit. It is
#   reduced to 129 terms (+ intercept): 11 focal mains (MIRBI dropped — exact
#   linear combo of SWIR1/SWIR2), 32 prev-year mains (blue/red dropped — visible
#   duplicates of green), 22 focal×focal interactions (pairwise-|r|>0.9 pruned +
#   VIF screen) and 64 prev×focal interactions (curated B4–B6 blocks, median+sd).
#   Interactions are formed from MEAN-CENTERED factors (better-conditioned under
#   the elastic-net penalty); after fitting, the centering is folded back into the
#   intercept + main slopes so the EXPORTED coefficients are on the RAW-product
#   scale and GEE deploys raw band products (no means vector). The fold-back is
#   verified numerically (predictions identical) on every fit.
#
# FITTING (see the qmd's CV-tuning section): the slow convergence was numerical,
#   not statistical. Full data (no subsampling), nlambda=50, lambda.min.ratio=1e-4,
#   thresh=1e-4 (relaxed from the 1e-7 default — the real speed lever), alpha grid
#   {0.25,0.5,0.75}, selected at lambda.min. No per-alpha checkpointing (fits are
#   fast). Cores per class are auto-sized to stay within a RAM budget.
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
#   Same foldid across alphas, tuned on binomial deviance. Out-of-fold p_i saved per obs.
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
K_TARGET     <- 10
ALPHAS       <- c(0.25, 0.5, 0.75)   # ridge (0) & lasso (1) dropped: never best in CV; interior keeps the ridge component that conditions the collinear design
LAMBDA_RULE  <- "min"                # "min" (best CV deviance — data-rich, near-MLE wanted) or "1se" (sparser)
NLAMBDA          <- 50               # finer path warm-starts better; 50 is smooth enough (curves nearly linear)
LAMBDA_MIN_RATIO <- 1e-4             # CV optimum sits near the path floor → go deep
THRESH           <- 1e-4             # glmnet convergence tol (relaxed from 1e-7 default: the real speed lever on this ill-conditioned design)
SEED         <- 1
EPS          <- 1e-15
# Cores for parallel CV folds are auto-sized per class to fit a RAM budget (this PC
# has 31 GB). Anchor (measured, full grassland_pat 819k × ~130 terms, fork backend):
# ~3.8 GB main + ~3.3 GB per fold-worker. FIT_CORES overrides the auto pick.
RAM_BUDGET_GB  <- as.numeric(Sys.getenv("FIT_RAM_GB", unset = "27"))   # leave ~4 GB for OS/desktop
CORES_OVERRIDE <- suppressWarnings(as.integer(Sys.getenv("FIT_CORES", unset = "")))
MEM_MAIN_REF   <- 3.8; MEM_WORKER_REF <- 3.3; MEM_N_REF <- 819208      # GB at n_ref obs
safe_cores <- function(n, K) {
  if (!is.na(CORES_OVERRIDE)) return(max(1L, CORES_OVERRIDE))
  main_gb   <- MEM_MAIN_REF   * n / MEM_N_REF
  worker_gb <- MEM_WORKER_REF * n / MEM_N_REF
  c <- floor((RAM_BUDGET_GB - main_gb) / worker_gb)
  max(1L, min(K, 10L, as.integer(c)))   # >K cores is useless (K folds); cap 10
}

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
# No negative subsampling: full data fits in RAM for every class.
SAMPLE_RULES <- list(
  forest_pat    = list(ash_merge = c("forest_pat", "shrubland_pat")),
  shrubland_pat = list(ash_merge = c("forest_pat", "shrubland_pat")),
  grassland_pat = list(ash_frac = 0.20)
)

# ── reduced design (129 terms; notebooks/predictors_terms_correlations.qmd) ────
FOCAL     <- c("BLUE","GREEN","RED","NIR","SWIR1","SWIR2","NBR","NBR2","NDVI","NDMI","NDSI")  # 11 (no MIRBI)
PREV_VARS <- c("green","nir","swir1","swir2","ndvi","ndwi","npv","ndfi")                      # 8 (no blue/red)
SUMM      <- c(med = "median", wet = "median_wet", dry = "median_dry", sd = "stdDev")          # 4
# focal × focal interactions kept (frozen on the full 5.72M-obs pooled data: 55 candidates
# → 25 pairwise-|r|>0.9 pruned (11 mains protected) → 22 after the VIF-on-mains screen).
FOCAL_INT <- c("BLUE:NBR","BLUE:NBR2","BLUE:NDMI","BLUE:RED","BLUE:SWIR1","GREEN:NIR",
               "NBR:NBR2","NBR:NDMI","NBR2:NDSI","NBR2:NDVI","NDMI:NDSI","NDVI:NDMI",
               "NDVI:NDSI","NIR:NBR","NIR:NDSI","NIR:SWIR1","NIR:SWIR2","SWIR1:NDMI",
               "SWIR1:NDSI","SWIR1:NDVI","SWIR1:SWIR2","SWIR2:NDVI")                            # 22
# prev × focal curated blocks, restricted to median + sd:
PREV_SUMM2 <- c("med","sd")
SAMEBAND_K <- c("green","nir","swir1","swir2","ndvi")          # B4: prev band × its own focal band
CONTEXT    <- c("ndvi","ndwi","npv","ndfi")                    # B5/B6: prev veg/fraction state ×
FIRE_IDX   <- c("NBR","NBR2","NDVI")                           #   focal fire index (skip ndvi×NDVI)
FIRE_BAND  <- c("RED","NIR","SWIR1","SWIR2")                   #   focal fire band
# Block sizes in build_design column order — used to label the coefficient export.
# Names match block_lvls in notebooks/model_fit_diagnostics.qmd.
BLOCKS <- c(focal = 11, prev = 32, pairs = 22, sameband = 10, cross_idx = 22, cross_band = 32)  # 129

# GEE band-name convention: focal -> "<FEAT>_t"; prev -> "<VAR>_<med|wet|dry|sd>";
# interaction -> "A__B". Column order matches the GEE block-multiply order so
# exported coefNames/coefValues line up band-for-band.
focal_nm <- function(f) paste0(f, "_t")
prev_col <- function(v, s) sprintf("mb_mos_%s_%s", v, SUMM[[s]])
prev_nm  <- function(v, s) sprintf("%s_%s", toupper(v), s)     # s in med/wet/dry/sd

# Interaction specs: each = list(name, fa, fb) with fa/fb = MAIN column names. Built once
# (pure function of the constants), consumed by build_design (centered products) and the
# coefficient fold-back. Order: pairs, sameband, cross_idx, cross_band (matches BLOCKS).
SPECS <- local({
  s <- list(); add <- function(fa, fb) s[[length(s) + 1L]] <<- list(name = paste(fa, fb, sep = "__"), fa = fa, fb = fb)
  for (p in strsplit(FOCAL_INT, ":", fixed = TRUE)) add(focal_nm(p[1]), focal_nm(p[2]))          # pairs (22)
  for (v in SAMEBAND_K) for (ss in PREV_SUMM2) add(prev_nm(v, ss), focal_nm(toupper(v)))          # sameband (10)
  for (v in CONTEXT) for (ss in PREV_SUMM2) for (f in FIRE_IDX)
    if (!(v == "ndvi" && f == "NDVI")) add(prev_nm(v, ss), focal_nm(f))                           # cross_idx (22)
  for (v in CONTEXT) for (ss in PREV_SUMM2) for (f in FIRE_BAND) add(prev_nm(v, ss), focal_nm(f)) # cross_band (32)
  s
})
stopifnot(length(SPECS) == sum(BLOCKS[c("pairs","sameband","cross_idx","cross_band")]))

# Build the design. Mains enter RAW; interactions are products of MEAN-CENTERED factors.
# Returns: X (mains + centered products), MM (raw mains), means (per-main centering const),
# specs (the SPECS list). Names follow the GEE convention.
build_design <- function(d) {
  num <- function(nm) { x <- as.numeric(d[[nm]]); x[is.na(x)] <- 0; x }
  Fm <- vapply(FOCAL, num, numeric(nrow(d))); colnames(Fm) <- focal_nm(FOCAL)              # focal mains 11
  pg <- do.call(rbind, lapply(PREV_VARS, function(v) data.frame(v = v, s = names(SUMM), stringsAsFactors = FALSE)))
  Pm <- vapply(seq_len(nrow(pg)), function(i) num(prev_col(pg$v[i], pg$s[i])), numeric(nrow(d)))
  colnames(Pm) <- prev_nm(pg$v, pg$s)                                                      # prev mains 32
  MM <- cbind(Fm, Pm)
  a  <- colMeans(MM)
  Pint <- vapply(SPECS, function(z) (MM[, z$fa] - a[z$fa]) * (MM[, z$fb] - a[z$fb]), numeric(nrow(MM)))
  colnames(Pint) <- vapply(SPECS, `[[`, character(1), "name")
  X <- cbind(MM, Pint); stopifnot(ncol(X) == sum(BLOCKS))
  list(X = X, MM = MM, means = a, specs = SPECS)
}

# Fold the centering of interaction factors back into intercept + main slopes, so the
# returned coefficients act on RAW products (x_k·x_l), not centered ones. Exact algebra:
#   γ·(x_k−a_k)(x_l−a_l) = γ·x_k x_l − γ a_l·x_k − γ a_k·x_l + γ a_k a_l
# → interaction coef γ unchanged; main slope β_j -= Σ γ·(partner mean); intercept += Σ γ a_k a_l.
# (Every interaction factor is also a main term, so this folds into existing terms — no new ones.)
fold_centering <- function(beta, b0, means, specs) {
  for (z in specs) {
    g <- beta[[z$name]]
    if (is.na(g) || g == 0) next
    beta[z$fa] <- beta[z$fa] - g * means[[z$fb]]
    beta[z$fb] <- beta[z$fb] - g * means[[z$fa]]
    b0 <- b0 + g * means[[z$fa]] * means[[z$fb]]
  }
  list(intercept = b0, beta = beta)
}

# ── generic helpers ──────────────────────────────────────────────────────────
log_loss <- function(y, p, w = NULL) { if (is.null(w)) w <- rep(1, length(y))
  p <- pmin(pmax(p, EPS), 1 - EPS); -sum(w*(y*log(p)+(1-y)*log(1-p))) / sum(w) }
brier    <- function(y, p, w = NULL) { if (is.null(w)) w <- rep(1, length(y)); sum(w*(p - y)^2) / sum(w) }
auc <- function(y, p) {
  n1 <- as.numeric(sum(y == 1)); n0 <- as.numeric(sum(y == 0))   # numeric: n1*n0 overflows integer for big classes
  if (n1 == 0 || n0 == 0) return(NA_real_)
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

# Apply the class sample rule; return this class's training rows (+ weight column w=1).
assemble_class_data <- function(dt, code, name, name2code, pure_neg) {
  ash <- dt$fire_uid %in% pure_neg         # region-unique ids (see main())
  rule <- SAMPLE_RULES[[name]]
  out <-
    if (is.null(rule)) {
      dt[veg_fire == code]
    } else if (!is.null(rule$ash_merge)) {
      codes <- name2code[rule$ash_merge]
      rbind(dt[veg_fire == code & !ash], dt[veg_fire %in% codes & ash])
    } else if (!is.null(rule$ash_frac)) {
      own_non <- dt[veg_fire == code & !ash]; own_ash <- dt[veg_fire == code & ash]
      target  <- round(rule$ash_frac / (1 - rule$ash_frac) * sum(own_non$burned == 0))
      if (nrow(own_ash) > target) own_ash <- own_ash[sample(.N, target)]
      rbind(own_non, own_ash)
    } else {
      dt[veg_fire == code]
    }
  out[, w := 1]                            # no subsampling → uniform weights (kept for n_eff/plumbing)
  out[]
}

# ── fit one class ─────────────────────────────────────────────────────────────
fit_one_class <- function(sub, code, name, name2code, pure_neg) {
  set.seed(SEED + code)
  tag <- sprintf("class_%02d", code)
  message(sprintf("\n[%s] %s — SETUP: %d obs, %d positives (%.1f%%) (rule: %s)", tag, name,
                  nrow(sub), sum(sub$burned), 100 * mean(sub$burned),
                  if (is.null(SAMPLE_RULES[[name]])) "default" else
                    paste(names(SAMPLE_RULES[[name]]), collapse = ",")))

  foldid <- make_foldid(sub, pure_neg, K_TARGET)
  if (is.null(foldid)) { message("  too few positive-bearing fires — skipped."); return(NULL) }
  K <- length(unique(foldid))

  cores <- safe_cores(nrow(sub), K)
  registerDoParallel(cores = cores)              # fork backend; parallelizes CV folds
  message(sprintf("  parallel CV folds across %d core(s) (auto-sized to ~%g GB budget; FIT_CORES to override)", cores, RAM_BUDGET_GB))

  wv <- sub$w                                    # uniform (1) — kept for weighted metrics / n_eff
  des <- build_design(sub); y <- as.numeric(sub$burned)
  all_terms <- colnames(des$X)                   # 129, block order, GEE names
  keep <- which(apply(des$X, 2, function(z) sd(z) > 0))
  if (length(keep) < ncol(des$X)) message(sprintf("  dropped %d zero-variance terms", ncol(des$X) - length(keep)))
  x  <- des$X[, keep, drop = FALSE]
  MM <- des$MM; means <- des$means; specs <- des$specs
  rm(des); gc()                                  # free the full design; x (kept) + MM remain

  to_prob <- function(v) if (all(v >= 0 & v <= 1, na.rm = TRUE)) v else plogis(v)  # link -> prob

  # alpha grid: fit each cv.glmnet, keep ONLY the running-best alpha's heavy objects
  # (glmnet path + OOF), discard the rest. No checkpointing (fits are fast).
  tuning <- vector("list", length(ALPHAS)); best <- NULL
  for (j in seq_along(ALPHAS)) {
    a <- ALPHAS[j]
    message(sprintf("  [%s] alpha %d/%d (=%.2f) — fitting cv.glmnet (%d obs x %d terms, K=%d, nlambda=%d) ...",
                    tag, j, length(ALPHAS), a, nrow(x), ncol(x), K, NLAMBDA))
    cvf  <- cv.glmnet(x, y, family = "binomial", alpha = a, foldid = foldid, weights = wv,
                      nlambda = NLAMBDA, lambda.min.ratio = LAMBDA_MIN_RATIO,
                      type.measure = "deviance", keep = TRUE, parallel = TRUE)
    imin <- match(cvf$lambda.min, cvf$lambda); i1se <- match(cvf$lambda.1se, cvf$lambda)
    isel <- if (LAMBDA_RULE == "1se") i1se else imin
    tuning[[j]] <- data.table(alpha = a, lambda = cvf$lambda, cvm = cvf$cvm, cvsd = cvf$cvsd)
    message(sprintf("  [%s] alpha %.2f done — lambda.min dev %.4f (idx %d/%d%s)", tag, a, cvf$cvm[imin],
                    imin, length(cvf$lambda), if (imin >= length(cvf$lambda)) ", AT FLOOR — inspect curve" else ""))
    if (is.null(best) || cvf$cvm[imin] < best$cvm_min) {
      best <- list(alpha = a, K = K, cvm_min = cvf$cvm[imin], cvm_1se = cvf$cvm[i1se], cvm_sel = cvf$cvm[isel],
                   lambda_min = cvf$lambda.min, lambda_1se = cvf$lambda.1se, sel_lambda = cvf$lambda[isel],
                   glmnet_fit = cvf$glmnet.fit, oof_sel = to_prob(cvf$fit.preval[, isel]))
    }
    rm(cvf); gc()
  }

  r <- best; sel_lambda <- r$sel_lambda
  message(sprintf("  WINNER alpha=%.2f | lambda.min=%.4g (dev %.4f), lambda.1se=%.4g (dev %.4f) -> using %s (K=%d)",
                  r$alpha, r$lambda_min, r$cvm_min, r$lambda_1se, r$cvm_1se, LAMBDA_RULE, K))

  # coefficients on the FITTED (centered-product) scale, then fold centering -> RAW-product scale
  fitted <- coef(r$glmnet_fit, s = sel_lambda)[, 1]   # named: "(Intercept)" + kept terms
  ic  <- which(names(fitted) == "(Intercept)")
  b0  <- unname(fitted[ic])
  cf  <- setNames(numeric(length(all_terms)), all_terms)   # full vector, 0 for dropped/zeroed
  cf[names(fitted[-ic])] <- fitted[-ic]
  raw <- fold_centering(cf, b0, means, specs)             # -> raw-product intercept + slopes

  # VERIFY the fold-back: predictions from the centered fit must equal the raw-product model.
  idx  <- if (nrow(MM) > 1e5) sample.int(nrow(MM), 1e5) else seq_len(nrow(MM))
  beta_kept <- fitted[-ic]
  eta_c <- b0 + as.numeric(x[idx, names(beta_kept), drop = FALSE] %*% beta_kept)
  Praw  <- vapply(specs, function(z) MM[idx, z$fa] * MM[idx, z$fb], numeric(length(idx)))
  colnames(Praw) <- vapply(specs, `[[`, character(1), "name")
  Xraw  <- cbind(MM[idx, , drop = FALSE], Praw)
  eta_r <- raw$intercept + as.numeric(Xraw[, all_terms, drop = FALSE] %*% raw$beta[all_terms])
  dmax  <- max(abs(eta_c - eta_r))
  if (dmax > 1e-6) stop(sprintf("[%s] centering fold-back FAILED: max |Δη| = %.3g over %d rows", tag, dmax, length(idx)))
  message(sprintf("  centering fold-back verified (max |Δη| = %.2g on %d rows)", dmax, length(idx)))

  # standardized coefficients (|β|·sd of the deployed RAW column) — effect size for diagnostics
  sds <- setNames(numeric(length(all_terms)), all_terms)
  for (m in colnames(MM)) sds[m] <- sd(MM[, m])
  for (z in specs)        sds[z$name] <- sd(MM[, z$fa] * MM[, z$fb])
  coef_std <- raw$beta[all_terms] * sds[all_terms]

  coef_dt <- rbind(
    data.table(block = "(intercept)", term = "(Intercept)", coefficient = raw$intercept, coef_std = NA_real_),
    data.table(block = rep(names(BLOCKS), BLOCKS), term = all_terms,
               coefficient = as.numeric(raw$beta[all_terms]), coef_std = as.numeric(coef_std)))

  p <- r$oof_sel; stopifnot(length(p) == nrow(sub))
  fwrite(coef_dt, file.path(out_dir, sprintf("%s_coefficients.csv", tag)))
  fwrite(rbindlist(tuning), file.path(out_dir, sprintf("%s_tuning.csv", tag)))
  fwrite(data.table(fire_id = sub$fire_id, point_id = sub$point_id, date = sub$date,
                    region = sub$region, veg_fire = code, burned = y, foldid = foldid,
                    p_oof = p, weight = wv),
         file.path(out_dir, sprintf("%s_oof_predictions.csv", tag)))
  # fit.rds: self-contained deployment artifact (raw-scale coef + centering means + the
  # glmnet path). Not read by the diagnostics notebook; kept for inspection/reproducibility.
  saveRDS(list(glmnet_fit = r$glmnet_fit, alpha = r$alpha, lambda = sel_lambda, lambda_rule = LAMBDA_RULE,
               centering_means = means, specs = specs, all_terms = all_terms, blocks = BLOCKS,
               coef_raw = c("(Intercept)" = raw$intercept, raw$beta[all_terms])),
          file.path(out_dir, sprintf("%s_fit.rds", tag)))

  m <- data.table(veg_fire = code, veg_fire_name = name, regions = paste(sort(unique(sub$region)), collapse = "+"),
             n_obs = nrow(sub), n_pos = sum(y), n_eff = sum(wv), K = K, n_terms = length(keep),
             alpha = r$alpha, lambda_rule = LAMBDA_RULE, lambda = sel_lambda,
             lambda_min = r$lambda_min, lambda_1se = r$lambda_1se,
             cv_deviance = r$cvm_sel, cv_logloss = log_loss(y, p, wv),
             cv_brier = brier(y, p, wv), cv_auc = auc(y, p),
             n_nonzero = sum(raw$beta != 0))
  fwrite(m, file.path(out_dir, sprintf("%s_cv_metrics.csv", tag)))   # per-class, self-contained
  message(sprintf("  [%s] outputs written.", tag))
  m
}

# ── main: resolve regions per class, load only what's needed, fit ─────────────
main <- function() {
  stopifnot(file.exists(remap_csv))
  glmnet.control(thresh = THRESH)                   # set convergence tol globally (avoids per-call deprecation)
  on.exit(stopImplicitCluster(), add = TRUE)
  remap <- fread(remap_csv)
  classes   <- unique(remap[fittable == TRUE, .(veg_fire, veg_fire_name)])[order(veg_fire)]
  name2code <- setNames(classes$veg_fire, classes$veg_fire_name)
  if (length(CLASS_FILTER)) classes <- classes[veg_fire_name %in% CLASS_FILTER]
  message(sprintf("Design: %d terms (+intercept) | alphas {%s} | nlambda=%d, lambda.min.ratio=%.0e, thresh=%.0e | lambda.%s",
                  sum(BLOCKS), paste(ALPHAS, collapse = ","), NLAMBDA, LAMBDA_MIN_RATIO, THRESH, LAMBDA_RULE))

  avail <- REGIONS_ALL[file.exists(vapply(REGIONS_ALL, region_csv, character(1)))]
  message(sprintf("Available region tables (v%s): %s", VERSION,
                  if (length(avail)) paste(avail, collapse = ", ") else "NONE"))

  load_region <- function(reg) {
    message(sprintf("  loading %s ...", basename(region_csv(reg))))
    d <- fread(region_csv(reg))
    obs_regs <- unique(as.character(d$region))
    if (!all(obs_regs == reg))
      stop(sprintf("Region label mismatch in %s: 'region' column = {%s} but expected '%s'. ",
                   basename(region_csv(reg)), paste(obs_regs, collapse = ", "), reg),
           "Reconcile the export or the region token before fitting.")
    rmp <- remap[region == reg, .(mb_class_raw, veg_fire, veg_fire_name, fittable)]
    if (!nrow(rmp))
      stop(sprintf("No remap rows for region '%s' in %s.", reg, basename(remap_csv)))
    d <- merge(d, rmp, by = "mb_class_raw", all.x = TRUE)
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
    dt <- if (length(regs) == 1) load_region(regs) else rbindlist(lapply(regs, load_region))
    dt[, fire_uid := paste0(region, "_", fire_id)]      # region-unique fire key
    pure_neg <- dt[, .(p = sum(burned)), by = fire_uid][p == 0, fire_uid]
    sub      <- assemble_class_data(dt, code, name, name2code, pure_neg)
    rm(dt); gc()
    m <- fit_one_class(sub, code, name, name2code, pure_neg)
    rm(sub); gc()
    if (!is.null(m)) metrics[[length(metrics) + 1]] <- m
  }

  if (length(metrics)) {
    fwrite(rbindlist(metrics, fill = TRUE), file.path(out_dir, sprintf("cv_metrics_v%s.csv", VERSION)))
    message(sprintf("\nDone. Fitted %d class(es). Outputs in collection-01/models/.", length(metrics)))
  } else {
    message("\nNo classes fitted (no complete region data for the requested classes).")
  }
}

main()
