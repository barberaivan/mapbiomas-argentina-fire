#!/usr/bin/env bash
# run_05_years.sh — run step-05 (05-objects_metrics.R) ONE fire-year per Rscript
# process, in a loop, so an OOM on one year kills only that year and the batch
# marches on. Records per-year exit code + wall time and flags rc=137 (SIGKILL,
# the kernel OOM killer's signature) as a likely OOM. Runs the RAM monitor
# alongside. Resumable: skips a year whose shape-metrics CSV already exists.
#
# Usage (launch inside tmux — see CLAUDE.md "Running long scripts"):
#   collection-01/workflow/run_05_years.sh [start_year] [end_year]
#   defaults: 2001 2025
set -u

cd "$(dirname "$0")/../.." || exit 1   # repo root (scripts expect to run from here)

START=${1:-2001}
END=${2:-2025}
STAMP=$(date '+%Y%m%d_%H%M%S')

LOGDIR=collection-01/logs
OUTDIR=collection-01/data/snic-polygons
RSCRIPT=collection-01/workflow/05-objects_metrics.R
MONITOR=collection-01/workflow/mem_monitor.sh
mkdir -p "$LOGDIR"

RUNLOG="$LOGDIR/05_run_${START}-${END}_${STAMP}.log"
MEMLOG="$LOGDIR/05_mem_${START}-${END}_${STAMP}.log"

say() { printf '%s %s\n' "$(date '+%F %T')" "$1" | tee -a "$RUNLOG"; }

# --- background RAM monitor: sample 15s, warn under 2 GB available ---
bash "$MONITOR" "$MEMLOG" 15 2048 &
MON=$!
trap 'kill "$MON" 2>/dev/null' EXIT

say "BATCH start FY${START}..${END}  run=$RUNLOG  mem=$MEMLOG  monitor_pid=$MON"

for fy in $(seq "$START" "$END"); do
  # completion sentinel: shape CSV is written LAST by the R script
  done_marker="$OUTDIR/objects_${fy}_shape_metrics.csv"
  if [[ -s "$done_marker" ]]; then
    say "SKIP  FY$fy (already done: $(basename "$done_marker"))"
    continue
  fi

  say "YEAR  FY$fy start"
  t0=$SECONDS
  # tee so the step messages show in the tmux window AND land in the log.
  # PIPESTATUS[0] = Rscript's real exit code (tee would otherwise mask rc=137).
  Rscript "$RSCRIPT" "$fy" 2>&1 | tee -a "$RUNLOG"
  rc=${PIPESTATUS[0]}
  dt=$(( SECONDS - t0 )); mm=$(( dt / 60 )); ss=$(( dt % 60 ))

  if   (( rc == 0 ));   then say "YEAR  FY$fy done rc=0 in ${mm}m${ss}s"
  elif (( rc == 137 )); then say "YEAR  FY$fy *** LIKELY OOM (rc=137 / SIGKILL) *** after ${mm}m — see $MEMLOG"
  else                       say "YEAR  FY$fy FAILED rc=$rc after ${mm}m — see $RUNLOG"
  fi
done

say "BATCH done"
