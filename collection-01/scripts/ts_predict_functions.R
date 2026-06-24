# collection-01/scripts/ts_predict_functions.R
#
# Predict burn probability from a class_NN_fit.rds, without loading glmnet.
# Adapted from models/README.md ("Predicting burn probability" -> "To predict on
# new observations"): every fit.rds carries RAW-scale coefficients (coef_raw), so
# prediction is a plain linear predictor + logistic. Verified there to reproduce
# glmnet's own predict(..., s = lambda) to machine precision (max |delta p| ~ 1e-14).
#
# Used by scripts/ts_plot_cache.R. Source this file, then call predict_class(d, fit).

FOCAL <- c("BLUE", "GREEN", "RED", "NIR", "SWIR1", "SWIR2", "NBR", "NBR2", "NDVI", "NDMI", "NDSI")  # 11
PREV  <- c("green", "nir", "swir1", "swir2", "ndvi", "ndwi", "npv", "ndfi")                          # 8
SUMM  <- c(med = "median", wet = "median_wet", dry = "median_dry", sd = "stdDev")                    # 4

num <- function(d, nm) { x <- as.numeric(d[[nm]]); x[is.na(x)] <- 0; x }

# Reconstruct the 129-column design on the RAW (uncentered) scale, ordered per
# fit$all_terms. fit$specs gives each interaction as list(name, fa, fb) of main
# column names already present in MM (no re-centering — fold_centering() in
# 02-model_fitting.R already folded the training-time centering into coef_raw).
design_raw <- function(d, fit) {
  Fm <- sapply(FOCAL, function(f) num(d, f)); colnames(Fm) <- paste0(FOCAL, "_t")
  pg <- expand.grid(s = names(SUMM), v = PREV, stringsAsFactors = FALSE)
  Pm <- sapply(seq_len(nrow(pg)), function(i) num(d, sprintf("mb_mos_%s_%s", pg$v[i], SUMM[[pg$s[i]]])))
  colnames(Pm) <- paste0(toupper(pg$v), "_", pg$s)
  MM <- cbind(Fm, Pm)
  Pr <- sapply(fit$specs, function(z) MM[, z$fa] * MM[, z$fb])
  colnames(Pr) <- sapply(fit$specs, `[[`, "name")
  cbind(MM, Pr)[, fit$all_terms, drop = FALSE]
}

# Burn probability for each row of d, using a class_NN_fit.rds object (coef_raw,
# specs, all_terms). Returns a numeric vector, length nrow(d).
predict_class <- function(d, fit) {
  eta <- fit$coef_raw[["(Intercept)"]] + as.numeric(design_raw(d, fit) %*% fit$coef_raw[fit$all_terms])
  plogis(eta)
}
