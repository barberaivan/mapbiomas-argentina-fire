#!/usr/bin/env Rscript
# =============================================================================
# objects_importance_ale.R — what the object model actually leans on, and how
# =============================================================================
# Feeds notebooks/objects-analysis.qmd. Heavy (BART prediction is ~1.2 ms/object/500-draws and
# single-threaded), so it CACHES to CSV and the notebook only reads the cache.
#
# WHY. Two questions need the same evidence:
#   [1] Which metrics are worth carrying as properties on the uploaded FeatureCollection
#       (docs/07)? The model is never deployed in GEE, so the upload set is not "the model's
#       inputs" — it is "what an expert needs to see to adjudicate a call". Importance ranks the
#       candidates; the ALE shape says whether a variable carries a LEGIBLE effect or just noise.
#   [2] Is any predictor doing something it should not? This is how `fire_year` /
#       `year_calendar` were caught taking the top two split shares (docs/06 §4).
#
# FOUR MEASURES, because no single one is trustworthy here — the predictors are strongly
# correlated (area_ha / n_pixels / perimeter_m are near-collinear; burned_around_{1,2,3} are
# nested windows), and every importance measure mishandles correlation in its own way:
#
#   split_share    fraction of all splits in the forest taken by each column, plus the root-split
#                  share. BART's native measure, read straight from the saved forest JSON. Biased
#                  TOWARD high-cardinality continuous columns, and splits credit arbitrarily
#                  between correlated columns — use it to rank, never as an effect size.
#   perm_dp        mean |change in predicted probability| when the column is shuffled, over a
#                  sample of ALL objects. This is the measure that matches the upload question:
#                  how much does this column move the DEPLOYED output? Not circular (it measures
#                  output sensitivity, not fit), but a correlated pair can both look small.
#   perm_auc_drop  AUC lost on the LABELLED set when the column is shuffled. In-sample (the fit
#                  saw these labels), so read it as "what the model uses to separate the classes
#                  it was shown", not as validation.
#   ale_range      max - min of the 1-D ALE curve: the effect size in probability units over the
#                  deployed population. ALE, not PDP, precisely BECAUSE of the correlation — a
#                  PDP averages over combinations that do not exist (a 1-pixel object with a
#                  10 km perimeter) and invents effects there. ALE only ever moves a point within
#                  its own quantile interval.
#
# THE POPULATION MATTERS. Importance is computed over a random sample of ALL objects, not over
# the labelled set: the labels are deliberately NOT size-representative (notebooks/
# objects-analysis.qmd §5), and the question is about the model's behaviour where it is deployed.
# perm_auc_drop is the one exception — it needs labels by construction.
#
# Run from the repo ROOT, in tmux (~55 min at the defaults):
#   Rscript collection-01/scripts/objects_importance_ale.R
#   Rscript collection-01/scripts/objects_importance_ale.R --n 5000 --ale-k 10   # quick pass
# Options
#   --n N          objects sampled from the full set (default 20000)
#   --ale-k K      ALE quantile intervals per predictor (default 20)
#   --perm-reps R  permutation repeats (default 3 for dp, 5 for auc)
#   --model DIR    model dir (default collection-01/models-store/object_model)
# Writes to collection-01/data/objects-analysis/:
#   importance_objects.csv   one row per predictor, all four measures
#   ale_curves_objects.csv   long: predictor, x, ale, n_in_interval
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(stochtree)
})
source("collection-01/scripts/objects_data_functions.R")

OUT_DIR <- "collection-01/data/objects-analysis"
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

argv <- commandArgs(trailingOnly = TRUE)
opt  <- function(flag, default) {
  i <- match(flag, argv); if (is.na(i) || i == length(argv)) default else argv[i + 1L]
}
N_SAMPLE  <- as.integer(opt("--n", "20000"))
ALE_K     <- as.integer(opt("--ale-k", "20"))
PERM_REPS <- as.integer(opt("--perm-reps", "3"))
AUC_REPS  <- PERM_REPS   # follows --perm-reps: the AUC pass costs the same per repeat
MODEL_DIR <- opt("--model", "collection-01/models-store/object_model")
CHUNK     <- 20000L
SEED      <- 1L

FIT_JSON <- file.path(MODEL_DIR, "bart_object_model.json")
FIT_META <- file.path(MODEL_DIR, "bart_object_model_meta.rds")

msg <- function(...) write(sprintf(...), stderr())
hdr <- function(s) { msg(""); msg("== %s ==", s) }
elapsed <- function(t0) as.numeric(difftime(Sys.time(), t0, units = "secs"))

# ── model ────────────────────────────────────────────────────────────────────
if (!file.exists(FIT_JSON)) stop("no fit at ", FIT_JSON, " — run 06-object_model.R fit first")
meta  <- readRDS(FIT_META)
PREDS <- meta$predictors                     # the fitted column ORDER is part of the model
msg("model: %s  (%d predictors, %d draws, %d training objects, fitted %s)",
    FIT_JSON, length(PREDS), meta$draws, meta$n_train, format(meta$fitted_at, "%Y-%m-%d %H:%M"))
t0 <- Sys.time()
model <- createBARTModelFromJsonFile(FIT_JSON)
msg("loaded in %.1f s", elapsed(t0))

# posterior-mean probability, chunked so peak memory is one chunk of draws, not all of them
pmean <- function(X) {
  idx <- split(seq_len(nrow(X)), ceiling(seq_len(nrow(X)) / CHUNK))
  unlist(lapply(idx, function(i) {
    p <- predict(model, X[i, , drop = FALSE], type = "posterior", terms = "y_hat",
                 scale = "probability")
    if (is.list(p)) p <- p$y_hat
    rowMeans(p)
  }), use.names = FALSE)
}

# ── [1] split share, straight from the saved forest ──────────────────────────
# 500 posterior forests x 200 trees. `split_index` is the 0-based predictor index at each node;
# `internal_nodes` lists the nodes that actually split (node 0 is the root).
hdr("split share")
t0 <- Sys.time()
j  <- jsonlite::fromJSON(FIT_JSON, simplifyVector = FALSE)
fc <- j$forests$forest_0
fk <- grep("^forest_", names(fc), value = TRUE)
tot <- integer(length(PREDS)); root <- integer(length(PREDS)); ntree <- 0L
for (f in fk) {
  forest <- fc[[f]]
  for (tk in grep("^tree_", names(forest), value = TRUE)) {
    t <- forest[[tk]]; ntree <- ntree + 1L
    si <- unlist(t$split_index, use.names = FALSE)
    ino <- unlist(t$internal_nodes, use.names = FALSE)
    if (!length(ino)) next                       # a stump: no split, contributes nothing
    v <- si[ino + 1L] + 1L                       # 0-based node ids and 0-based predictor index
    tot[] <- tot + tabulate(v, nbins = length(PREDS))
    if (0L %in% ino) root[si[1L] + 1L] <- root[si[1L] + 1L] + 1L
  }
}
rm(j, fc); gc(FALSE)
imp <- data.table(predictor = PREDS, splits = tot, root_splits = root)
imp[, `:=`(split_share = splits / sum(splits), root_share = root_splits / sum(root_splits))]
msg("%s trees, %s splits, in %.1f s", format(ntree, big.mark = ","),
    format(sum(tot), big.mark = ","), elapsed(t0))

# ── the sample the rest is measured on ───────────────────────────────────────
hdr("sample")
obj <- read_all_objects()
obj <- obj[complete.cases(obj[, ..PREDS])]
set.seed(SEED)
smp <- obj[sample(.N, min(.N, N_SAMPLE))]
X   <- as.matrix(smp[, ..PREDS])
rm(obj); gc(FALSE)
msg("%s objects sampled from all fire-years (%d predictors)", format(nrow(X), big.mark = ","),
    ncol(X))
t0 <- Sys.time(); p0 <- pmean(X)
msg("baseline prediction in %.0f s (%.2f ms/object)", elapsed(t0), 1000 * elapsed(t0) / nrow(X))

# ── [2] permutation dp — how much each column moves the deployed output ──────
hdr("permutation |dp| on the object sample")
set.seed(SEED)
dp <- sapply(PREDS, function(v) {
  t1 <- Sys.time()
  d <- replicate(PERM_REPS, {
    Xp <- X; Xp[, v] <- Xp[sample(nrow(Xp)), v]
    mean(abs(pmean(Xp) - p0))
  })
  msg("  %-18s mean|dp| %.4f  (%.0f s)", v, mean(d), elapsed(t1))
  mean(d)
})
imp[, perm_dp := as.numeric(dp[predictor])]

# ── [3] permutation AUC drop on the labelled set ─────────────────────────────
hdr("permutation AUC drop on the labelled set (in-sample)")
tag  <- clean_tagged(verbose = FALSE)
Xl   <- as.matrix(tag[, ..PREDS])
auc0 <- auc_fast(pmean(Xl), tag$class)
msg("baseline in-sample AUC %.4f", auc0)
set.seed(SEED)
ad <- sapply(PREDS, function(v) {
  d <- replicate(AUC_REPS, {
    Xp <- Xl; Xp[, v] <- Xp[sample(nrow(Xp)), v]
    auc_fast(pmean(Xp), tag$class)
  })
  msg("  %-18s AUC %.4f -> drop %.4f", v, mean(d), auc0 - mean(d))
  auc0 - mean(d)
})
imp[, perm_auc_drop := as.numeric(ad[predictor])]

# ── [4] 1-D ALE ──────────────────────────────────────────────────────────────
# Apley & Zhu accumulated local effects. For each quantile interval, every point IN that
# interval is predicted at the interval's two edges and the difference averaged — so a point is
# only ever moved within its own neighbourhood, never to a combination that does not exist.
hdr("1-D ALE curves")
ale_one <- function(v) {
  t1 <- Sys.time()
  x  <- X[, v]
  z  <- unique(quantile(x, probs = seq(0, 1, length.out = ALE_K + 1L), names = FALSE, type = 1))
  if (length(z) < 2L) {                                  # constant column: no curve to draw
    msg("  %-18s constant — skipped", v)
    return(NULL)
  }
  # interval index 1..K-1; findInterval puts the minimum in interval 0, fold it into 1
  k  <- pmax(findInterval(x, z, rightmost.closed = TRUE), 1L)
  Xlo <- X; Xlo[, v] <- z[k]
  Xhi <- X; Xhi[, v] <- z[k + 1L]
  d   <- pmean(Xhi) - pmean(Xlo)
  agg <- data.table(k = k, d = d)[, .(delta = mean(d), n = .N), by = k][order(k)]
  # intervals with no points contribute zero increment, so the curve stays defined on every edge
  full <- data.table(k = seq_len(length(z) - 1L))
  agg  <- merge(full, agg, by = "k", all.x = TRUE)[order(k)]
  agg[is.na(delta), `:=`(delta = 0, n = 0L)]
  a <- c(0, cumsum(agg$delta))                            # uncentered, on the K+1 edges
  # centre on the sample: weight each edge by the points around it, so ale = 0 at the mean effect
  w <- c(agg$n[1], (head(agg$n, -1) + tail(agg$n, -1)) / 2, tail(agg$n, 1))
  w <- w[seq_along(a)]
  a <- a - sum(a * w) / sum(w)
  msg("  %-18s range %.4f over %d interval(s)  (%.0f s)", v, max(a) - min(a), length(z) - 1L,
      elapsed(t1))
  data.table(predictor = v, x = z, ale = a, n_left = c(agg$n, NA_integer_)[seq_along(a)])
}
ale <- rbindlist(lapply(PREDS, ale_one))
rng <- ale[, .(ale_range = max(ale) - min(ale)), by = predictor]
imp <- merge(imp, rng, by = "predictor", all.x = TRUE)

# ── write ────────────────────────────────────────────────────────────────────
setorder(imp, -split_share)
imp[, `:=`(n_sample = nrow(X), ale_k = ALE_K, model = FIT_JSON)]
fwrite(imp, file.path(OUT_DIR, "importance_objects.csv"))
fwrite(ale, file.path(OUT_DIR, "ale_curves_objects.csv"))

hdr("importance (ordered by split share)")
print(imp[, .(predictor, split_share = round(split_share, 4), root_share = round(root_share, 4),
              perm_dp = round(perm_dp, 4), perm_auc_drop = round(perm_auc_drop, 4),
              ale_range = round(ale_range, 4))])
msg("")
msg("-> %s", file.path(OUT_DIR, "importance_objects.csv"))
msg("-> %s", file.path(OUT_DIR, "ale_curves_objects.csv"))
