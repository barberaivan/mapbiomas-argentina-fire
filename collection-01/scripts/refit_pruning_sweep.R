#!/usr/bin/env Rscript
# collection-01/scripts/refit_pruning_sweep.R
#
# Refit the reduced burn-probability LR for each candidate P from
# config/pruning_terms.csv (written by notebooks/lr_term_pruning.qmd), reusing the
# full machinery of workflow/02-model_fitting.R via its KEEP_TERMS_CSV / RUN_TAG hooks.
#
# Each P is a full all-classes fit: trimmed coefficient CSVs (intercept + kept terms) land in the
# tracked models/P<NNN>/ folder (COEF_TAG), heavy artifacts in models-store/pruning/K3_P<P>/
# (RUN_TAG). The full-129 deliverable (models/P129/) is never touched. Afterwards, per-class OOF
# metrics from every run
# plus the full-129 baseline (models-store/class_*_cv_metrics.csv) are aggregated to
# models-store/pruning/metrics_by_P.csv for the comparison plot in lr_term_pruning.qmd.
#
# Heavy (one elastic-net CV fit per class per P) — run in tmux. From the repo root:
#   Rscript collection-01/scripts/refit_pruning_sweep.R                 # all P, all classes
#   P_LIST=40 Rscript collection-01/scripts/refit_pruning_sweep.R agriculture-per_chaco-ba   # smoke test
# Env: P_LIST (comma list, default = all P in the CSV), VERSION (default 1). Trailing args =
# class-name filter forwarded to 02-model_fitting.R.

suppressMessages(library(data.table))

here_root <- function() {
  a <- commandArgs(FALSE); f <- sub("^--file=", "", a[grep("^--file=", a)])
  if (length(f)) normalizePath(file.path(dirname(f), "..", "..")) else normalizePath(".")
}
root       <- here_root()
col1       <- file.path(root, "collection-01")
fit_script <- file.path(col1, "workflow", "02-model_fitting.R")
pterms     <- fread(file.path(col1, "config", "pruning_terms.csv"))
store      <- file.path(col1, "models-store")
sweep_dir  <- file.path(store, "pruning")
dir.create(sweep_dir, recursive = TRUE, showWarnings = FALSE)

class_filter <- commandArgs(trailingOnly = TRUE)          # optional veg_fire_name(s) for 02
VERSION      <- Sys.getenv("VERSION", "1")
P_LIST       <- as.integer(strsplit(Sys.getenv("P_LIST",
                  paste(sort(unique(pterms$P)), collapse = ",")), ",")[[1]])

cat(sprintf("Refit sweep: P in {%s}  |  version %s%s\n",
            paste(P_LIST, collapse = ", "), VERSION,
            if (length(class_filter)) sprintf("  |  classes: %s", paste(class_filter, collapse = ", ")) else ""))

for (Pval in P_LIST) {
  keep      <- pterms[P == Pval, .(term)]
  keep_file <- file.path(sweep_dir, sprintf("keep_K3_P%d.csv", Pval))
  fwrite(keep, keep_file)
  tag      <- sprintf("pruning/K3_P%d", Pval)   # heavy artifacts → models-store/pruning/K3_P<P>/
  coef_tag <- sprintf("P%03d", Pval)            # tracked trimmed coefficients → models/P<NNN>/
  cat(sprintf("\n=================================================================\n"))
  cat(sprintf(">>> REFIT  P = %d   (%d terms)   ->  models/%s + models-store/%s\n",
              Pval, nrow(keep), coef_tag, tag))
  cat(sprintf("=================================================================\n"))
  flush.console()
  Sys.setenv(KEEP_TERMS_CSV = keep_file, RUN_TAG = tag, COEF_TAG = coef_tag)
  st <- system2("Rscript", c(fit_script, VERSION, class_filter), stdout = "", stderr = "")
  if (st != 0) stop(sprintf("fit for P=%d exited with status %d", Pval, st))
}
Sys.unsetenv(c("KEEP_TERMS_CSV", "RUN_TAG", "COEF_TAG"))

# ── aggregate per-class OOF metrics: each reduced run + the full-129 baseline ────────────────
read_metrics <- function(dir, Plabel) {
  fs <- Sys.glob(file.path(dir, "class_*_cv_metrics.csv"))
  if (!length(fs)) return(NULL)
  rbindlist(lapply(fs, function(f)
    fread(f)[, .(veg_fire, veg_fire_name, cv_brier, cv_auc, n_nonzero)]))[, P := Plabel][]
}
parts <- list(read_metrics(store, "full"))                                   # full-129 baseline
for (Pval in P_LIST)
  parts <- c(parts, list(read_metrics(file.path(sweep_dir, sprintf("K3_P%d", Pval)), as.character(Pval))))
metrics <- rbindlist(Filter(Negate(is.null), parts), use.names = TRUE)
out <- file.path(sweep_dir, "metrics_by_P.csv")
fwrite(metrics, out)
cat(sprintf("\nWrote %s  (%d rows; P values: %s)\n", out, nrow(metrics),
            paste(sort(unique(metrics$P)), collapse = ", ")))
