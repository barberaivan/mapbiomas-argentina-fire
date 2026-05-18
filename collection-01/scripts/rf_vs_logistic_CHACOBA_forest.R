# rf_vs_logistic_CHACOBA_forest.R
# Compare Random Forest regression vs. elastic-net logistic regression
# on CHACO-BA forest training observations using Brier score.
# Run from repo root: source("collection-01/scripts/rf_vs_logistic_CHACOBA_forest.R")

TEST_MODE <- FALSE   # set FALSE for full grid after test run looks sensible

# ── packages ────────────────────────────────────────────────────────────────
library(tidyverse)
library(googlesheets4)
library(rsample)
library(ranger)
library(glmnet)
library(Matrix)

# ── feature lists ───────────────────────────────────────────────────────────
FOCAL <- c("BLUE","GREEN","RED","NIR","SWIR1","SWIR2",
           "NBR","NBR2","MIRBI","NDVI","TCB","TCG","TCW",
           "NDMI","NDSI","SAVI","NDWI")

MOSAIC <- c(
  "mb_mos_blue_median",  "mb_mos_blue_median_dry",  "mb_mos_blue_median_wet",
  "mb_mos_green_median", "mb_mos_green_median_dry", "mb_mos_green_median_wet",
  "mb_mos_red_median",   "mb_mos_red_median_dry",   "mb_mos_red_median_wet",
  "mb_mos_nir_median",   "mb_mos_nir_median_dry",   "mb_mos_nir_median_wet",
  "mb_mos_swir1_median", "mb_mos_swir1_median_dry", "mb_mos_swir1_median_wet",
  "mb_mos_swir2_median", "mb_mos_swir2_median_dry", "mb_mos_swir2_median_wet",
  "mb_mos_ndvi_median",  "mb_mos_ndvi_median_dry",  "mb_mos_ndvi_median_wet"
)

ALL_FEATS <- c(FOCAL, MOSAIC)   # 38 features

# ── load data ────────────────────────────────────────────────────────────────
cat("Loading data...\n")
raw <- bind_rows(
  read_csv("collection-01/data/training_observations_BA_v1.csv",    show_col_types = FALSE),
  read_csv("collection-01/data/training_observations_CHACO_v1.csv", show_col_types = FALSE)
) |>
  mutate(region_fire = "CHACO-BA")

# ── fire-class filter: keep forest only ──────────────────────────────────────
cat("Fetching remap sheet...\n")
gs4_deauth()
remap_raw <- read_sheet(
  "https://docs.google.com/spreadsheets/d/17ZShb8D0JaJw4nLvBDzt19xF6Fdg8lGHYs4Jogh0X1A",
  sheet = "remap_by_region"
)

remap_chacoba <- remap_raw |>
  mutate(mb_class_raw = suppressWarnings(as.integer(unlist(id)))) |>
  filter(!is.na(mb_class_raw), region_fire == "CHACO-BA") |>
  group_by(mb_class_raw) |>
  summarise(veg_fire_name_2 = first(veg_fire_name_2), .groups = "drop")

dat_full <- raw |>
  left_join(remap_chacoba, by = "mb_class_raw") |>
  filter(veg_fire_name_2 == "forest") |>
  filter(if_all(all_of(ALL_FEATS), ~ !is.na(.)))

cat(sprintf("Forest rows (pre-downsample): %d  |  burned: %d  |  unburned: %d\n",
            nrow(dat_full), sum(dat_full$burned), sum(dat_full$burned == 0)))

# ── downsample to 50k per class (balanced) ───────────────────────────────────
N_PER_CLASS   <- 40000L
burned_rows   <- filter(dat_full, burned == 1L)
unburned_rows <- filter(dat_full, burned == 0L)
set.seed(42)
if (nrow(burned_rows)   > N_PER_CLASS) burned_rows   <- slice_sample(burned_rows,   n = N_PER_CLASS)
if (nrow(unburned_rows) > N_PER_CLASS) unburned_rows <- slice_sample(unburned_rows, n = N_PER_CLASS)
dat_full <- bind_rows(burned_rows, unburned_rows)
cat(sprintf("After downsample: %d rows  |  burned: %d  |  unburned: %d\n",
            nrow(dat_full), sum(dat_full$burned), sum(dat_full$burned == 0L)))

cat(sprintf("Unique fires: %s\n", paste(sort(unique(dat_full$fire_id)), collapse = ", ")))

# ── test-mode subsample (after ratio is established) ─────────────────────────
if (TEST_MODE) {
  set.seed(42)
  dat_full <- slice_sample(dat_full, n = min(2000L, nrow(dat_full)))
  cat(sprintf("[TEST_MODE] Further subsampled to %d rows\n", nrow(dat_full)))
}

# ── CV splits ────────────────────────────────────────────────────────────────
# No PAT-style fixed fires in CHACO-BA; dat_fixed will be empty — bind_rows is a no-op
FIXED_FIRES <- character(0)
dat_cv    <- dat_full
dat_fixed <- dat_full[0L, ]

n_folds <- if (TEST_MODE) 2L else 5L
folds   <- group_vfold_cv(dat_cv, group = "fire_id", v = n_folds)

# ── hyperparameter grids ─────────────────────────────────────────────────────
if (TEST_MODE) {
  rf_grid  <- tibble(mtry = 6L, min_node_size = 100L)
  en_alpha <- 0.5
  n_trees  <- 20L
} else {
  rf_grid  <- expand_grid(mtry          = c(3L, 6L, 12L),
                          min_node_size = c(50L, 100L, 150L))
  en_alpha <- c(0.1, 0.5, 0.9)
  n_trees  <- 300L
}

# ── helpers ──────────────────────────────────────────────────────────────────

z_score <- function(ref_data, newdata, cols) {
  mu <- colMeans(ref_data[, cols], na.rm = TRUE)
  sd <- apply(ref_data[, cols], 2, sd, na.rm = TRUE)
  sd[sd == 0] <- 1
  sweep(sweep(as.matrix(newdata[, cols]), 2, mu, "-"), 2, sd, "/")
}

build_design <- function(mat) {
  idx <- setNames(seq_along(ALL_FEATS), ALL_FEATS)

  interact_pairs <- list(
    c("RED","NIR"), c("RED","SWIR1"), c("RED","SWIR2"),
    c("NIR","SWIR1"), c("NIR","SWIR2"), c("SWIR1","SWIR2")
  )
  ndvi_mos_pairs <- list(
    c("mb_mos_ndvi_median","NBR"), c("mb_mos_ndvi_median","NBR2")
  )
  matched_pairs <- list(
    c("mb_mos_blue_median","BLUE"),   c("mb_mos_green_median","GREEN"),
    c("mb_mos_red_median","RED"),     c("mb_mos_nir_median","NIR"),
    c("mb_mos_swir1_median","SWIR1"), c("mb_mos_swir2_median","SWIR2")
  )

  all_pairs <- c(interact_pairs, ndvi_mos_pairs, matched_pairs)
  int_cols  <- lapply(all_pairs, function(p) mat[, idx[p[1]]] * mat[, idx[p[2]]])
  int_names <- sapply(all_pairs, function(p) paste(p, collapse = "x"))

  out <- cbind(mat, do.call(cbind, int_cols))
  colnames(out) <- c(ALL_FEATS, int_names)
  out
}

brier <- function(y, p) mean((p - y)^2, na.rm = TRUE)

# ── main CV loop ─────────────────────────────────────────────────────────────
cat("Running cross-validation...\n")

results_list <- vector("list", n_folds)
oof_list     <- vector("list", n_folds)

for (i in seq_len(n_folds)) {
  split <- folds$splits[[i]]
  trn   <- bind_rows(training(split), dat_fixed)
  tst   <- testing(split)

  y_trn <- trn$burned
  y_tst <- tst$burned

  fold_rows <- list()

  # ── RF ─────────────────────────────────────────────────────────────────────
  X_trn_rf <- as.matrix(trn[, ALL_FEATS])
  X_tst_rf <- as.matrix(tst[, ALL_FEATS])

  oof_rf_best <- NULL

  for (r in seq_len(nrow(rf_grid))) {
    hp  <- rf_grid[r, ]
    fit <- ranger(
      x               = X_trn_rf,
      y               = y_trn,
      num.trees       = n_trees,
      mtry            = hp$mtry,
      min.node.size   = hp$min_node_size,
      replace         = TRUE,
      sample.fraction = 0.5,
      num.threads     = 8L,
      seed            = 42
    )
    p_tst <- predict(fit, data = X_tst_rf)$predictions

    fold_rows[[length(fold_rows) + 1]] <- tibble(
      model         = "RF",
      alpha         = NA_real_,
      lambda_min    = NA_real_,
      mtry          = hp$mtry,
      min_node_size = hp$min_node_size,
      fold          = i,
      brier         = brier(y_tst, p_tst)
    )

    if (r == 1) oof_rf_best <- tibble(
      obs_idx       = which(dat_full$fire_id %in% tst$fire_id),
      y             = y_tst,
      p             = p_tst,
      model         = "RF",
      mtry          = hp$mtry,
      min_node_size = hp$min_node_size,
      fold          = i
    )
  }

  # ── Elastic net ────────────────────────────────────────────────────────────
  Z_trn <- z_score(trn, trn, ALL_FEATS)
  Z_tst <- z_score(trn, tst, ALL_FEATS)

  DM_trn <- build_design(Z_trn)
  DM_tst <- build_design(Z_tst)

  oof_en_best <- NULL

  for (a in en_alpha) {
    cv_fit <- cv.glmnet(
      x           = DM_trn,
      y           = y_trn,
      family      = "binomial",
      alpha       = a,
      standardize = FALSE,
      nfolds      = 5L
    )
    lam   <- cv_fit$lambda.min
    p_tst <- as.vector(predict(cv_fit, newx = DM_tst, s = "lambda.min",
                               type = "response"))

    fold_rows[[length(fold_rows) + 1]] <- tibble(
      model         = "ElasNet",
      alpha         = a,
      lambda_min    = lam,
      mtry          = NA_integer_,
      min_node_size = NA_integer_,
      fold          = i,
      brier         = brier(y_tst, p_tst)
    )

    if (a == en_alpha[1]) oof_en_best <- tibble(
      obs_idx = which(dat_full$fire_id %in% tst$fire_id),
      y       = y_tst,
      p       = p_tst,
      model   = "ElasNet",
      alpha   = a,
      fold    = i
    )
  }

  results_list[[i]] <- bind_rows(fold_rows)

  oof_list[[i]] <- bind_rows(
    select(oof_rf_best, obs_idx, y, p, model, fold),
    select(oof_en_best, obs_idx, y, p, model, fold)
  )

  cat(sprintf("  fold %d done\n", i))
}

# ── Results tables ────────────────────────────────────────────────────────────
full_tbl <- bind_rows(results_list) |>
  arrange(model, alpha, mtry, min_node_size, fold)

cat("\n=== Full results (all hyperparams × folds) ===\n")
print(full_tbl, n = Inf)

summary_tbl <- full_tbl |>
  group_by(model, alpha, mtry, min_node_size) |>
  summarise(
    mean_brier = mean(brier),
    cv_sd      = sd(brier),
    .groups    = "drop"
  ) |>
  arrange(mean_brier)

cat("\n=== Summary (mean ± SD across folds) ===\n")
print(summary_tbl, n = Inf)

best_rf  <- filter(summary_tbl, model == "RF")      |> slice(1)
all_en   <- filter(summary_tbl, model == "ElasNet") |> arrange(alpha)

cat("\n=== Best RF + all ElasNet alphas ===\n")
print(bind_rows(best_rf, all_en))

# ── Save results ──────────────────────────────────────────────────────────────
write_csv(full_tbl,             "collection-01/scripts/rf_vs_logistic_CHACOBA_forest_full.csv")
write_csv(summary_tbl,          "collection-01/scripts/rf_vs_logistic_CHACOBA_forest_summary.csv")
write_csv(bind_rows(best_rf, all_en), "collection-01/scripts/rf_vs_logistic_CHACOBA_forest_best.csv")
cat("\nResults saved to collection-01/scripts/rf_vs_logistic_CHACOBA_forest_{full,summary,best}.csv\n")

# ── Calibration plot ──────────────────────────────────────────────────────────
oof_df <- bind_rows(oof_list)

cal_df <- oof_df |>
  mutate(bin = cut(p, breaks = seq(0, 1, 0.1), include.lowest = TRUE,
                   right = FALSE)) |>
  group_by(model, bin) |>
  summarise(
    mean_pred = mean(p),
    obs_frac  = mean(y),
    n         = n(),
    .groups   = "drop"
  )

cal_plot <- ggplot(cal_df, aes(x = mean_pred, y = obs_frac, colour = model)) +
  geom_abline(slope = 1, intercept = 0, linetype = "dashed", colour = "grey50") +
  geom_line() +
  geom_point(aes(size = n)) +
  scale_colour_manual(values = c(RF = "#E07B39", ElasNet = "#3B82C4")) +
  labs(
    title    = "Calibration -- CHACO-BA forest (out-of-fold)",
    subtitle = "Best RF vs. best elastic-net",
    x        = "Mean predicted probability",
    y        = "Observed fraction burned",
    colour   = NULL, size = "n obs"
  ) +
  theme_bw()

out_png <- "collection-01/scripts/rf_vs_logistic_CHACOBA_forest_calibration.png"
ggsave(out_png, cal_plot, width = 7, height = 5, dpi = 150)
cat(sprintf("\nCalibration plot saved to %s\n", out_png))
print(cal_plot)

# ── Back-transform note (for GEE deployment) ──────────────────────────────────
# To recover elastic-net coefficients in the original (unscaled) feature space:
#   For a main-effect predictor j with training sd_j:
#     beta_j_orig = beta_j_scaled / sd_j
#   For an interaction term (i x j):
#     beta_ij_orig = beta_ij_scaled / (sd_i * sd_j)
#   Intercept adjustment:
#     intercept_orig = intercept_scaled - sum(beta_j_scaled * mu_j / sd_j)
