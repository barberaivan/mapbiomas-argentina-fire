#!/usr/bin/env bash
# run_06_predict.sh — score every fire-year with the step-06 object model, IN PARALLEL.
#
# WHY THIS EXISTS: stochtree's prediction is single-threaded. `num_threads` is a *sampler*
# setting — it covers the GFR and MCMC loops during `fit`, but predict.bartmodel (0.4.5) takes
# no thread argument at all and neither do the C++ predict entry points. So `predict all` in one
# process pegs exactly one core and takes ~37 min for the 1.69 M objects. The years are
# completely independent, so the parallelism belongs at the process level: one Rscript per
# fire-year, N at a time. 8 workers turn ~37 min into ~5.
#
# Each worker deserializes the ~97 MB fit JSON itself (~4 s, ~1.4 GB RSS), so peak memory is
# WORKERS * 1.4 GB — keep 8 workers under ~12 GB. That redundant load is the price of not
# sharing an in-process model, and it is cheap next to the scoring.
#
# Usage (from the repo ROOT, inside tmux — see CLAUDE.md "Running long scripts"):
#   collection-01/scripts/run_06_predict.sh [-j WORKERS] [--full] [--force] [year ...]
#     -j WORKERS  parallel years (default 8 = physical cores)
#     --full      the 40-predictor variant (default: grouped, the deployed one)
#     --force     re-score years that already have a prediction CSV
#     year …      only these fire-years (default: every year with step-05 metrics)
#
# RESUMABLE: a year whose objects_<fy>_pred_<variant>.csv already exists is skipped unless
# --force, so a killed-and-relaunched run never redoes finished years.
set -u

cd "$(dirname "$0")/../.." || exit 1   # repo root (the R scripts expect to run from here)

JOBS=8
VARIANT=grouped
VFLAG=""
FORCE=0
YEARS=()
while (( $# )); do
  case "$1" in
    -j)      JOBS=$2; shift 2 ;;
    --full)  VARIANT=full; VFLAG="--full"; shift ;;
    --force) FORCE=1; shift ;;
    [0-9][0-9][0-9][0-9]) YEARS+=("$1"); shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

POLY_DIR=collection-01/data/snic-polygons
PRED_DIR=collection-01/data/objects-predictions
LOGDIR=collection-01/logs
STAMP=$(date '+%Y%m%d_%H%M%S')
RUNLOG="$LOGDIR/06_predict_${VARIANT}_${STAMP}.log"
mkdir -p "$LOGDIR" "$PRED_DIR"

say() { printf '%s %s\n' "$(date '+%F %T')" "$1" | tee -a "$RUNLOG"; }

# every year that has step-05 metrics, unless the caller named some
if (( ${#YEARS[@]} == 0 )); then
  while IFS= read -r f; do
    b=$(basename "$f"); YEARS+=("${b:8:4}")
  done < <(ls "$POLY_DIR"/objects_[0-9][0-9][0-9][0-9]_raster_metrics.csv 2>/dev/null)
fi
(( ${#YEARS[@]} )) || { echo "no step-05 metrics in $POLY_DIR" >&2; exit 1; }

# BIGGEST YEARS FIRST. The pool is only as fast as its last task, and the years differ by ~5x in
# object count — starting with the big ones keeps a 250 k-object year from being picked up last
# and running alone while 7 workers idle.
TODO=()
while IFS= read -r fy; do
  out="$PRED_DIR/objects_${fy}_pred_${VARIANT}.csv"
  if (( FORCE == 0 )) && [[ -s "$out" ]]; then
    say "SKIP  FY$fy (already scored: $(basename "$out"))"
  else
    TODO+=("$fy")
  fi
done < <(for fy in "${YEARS[@]}"; do
           printf '%s %s\n' "$(stat -c%s "$POLY_DIR/objects_${fy}_raster_metrics.csv")" "$fy"
         done | sort -rn | cut -d' ' -f2)

(( ${#TODO[@]} )) || { say "nothing to do — every year already scored"; exit 0; }

say "PREDICT ${#TODO[@]} year(s) on $JOBS worker(s), variant=$VARIANT  log=$RUNLOG"
say "  order (biggest first): ${TODO[*]}"

t0=$SECONDS
# One Rscript per year. Per-year logs so a failure is attributable; the pool is plain xargs -P.
printf '%s\n' "${TODO[@]}" | xargs -P "$JOBS" -I{} bash -c '
  fy={}; log="'"$LOGDIR"'/06_predict_'"$VARIANT"'_${fy}.log"
  s=$SECONDS
  if Rscript collection-01/workflow/06-object_model.R predict "$fy" '"$VFLAG"' > "$log" 2>&1; then
    printf "%s YEAR  FY%s done in %ss\n" "$(date "+%F %T")" "$fy" "$((SECONDS-s))"
  else
    printf "%s YEAR  FY%s FAILED rc=%s — see %s\n" "$(date "+%F %T")" "$fy" "$?" "$log"
  fi' | tee -a "$RUNLOG"

dt=$(( SECONDS - t0 ))
n=$(ls "$PRED_DIR"/objects_[0-9][0-9][0-9][0-9]_pred_${VARIANT}.csv 2>/dev/null | wc -l)
say "BATCH done in $((dt/60))m$((dt%60))s — $n year(s) now scored in $PRED_DIR"
