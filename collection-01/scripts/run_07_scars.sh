#!/usr/bin/env bash
# run_07_scars.sh — build the calendar-year scar vectors, one process per year, in parallel.
#
# Two passes (see workflow/07-calendar_scars.R for why they are split):
#   pixels  one process per FIRE-year (28)     -> scars-pixels-cache/cy<Y>_fy<fy>.rds
#   scars   one process per CALENDAR year (27) -> objects-scars/ + scars-upload-cache/*.zip
# `scars` needs BOTH of a calendar year's fire-years done, so run `pixels` to completion first.
#
# One Rscript per year, as in run_05_years.sh / run_06_predict.sh: an OOM kills only that year
# (rc=137), not the batch. RESUMABLE — a year with its completion marker (pixels) or its .zip
# (scars) is skipped unless --force, so a killed-and-relaunched run never redoes finished work.
# BIGGEST YEARS FIRST: the pool is only as fast as its last task and the years differ ~10x in
# burned area, so a huge year picked up last would run alone while the other workers idle.
#
# Memory is the binding constraint, not CPU. `pixels` peaks ~2-3 GB (the per-fire-year cell
# table); `scars` peaks ~4-6 GB on the biggest calendar years (~100 M pixels through the
# union-find). Defaults are tuned for a 31 GB box — raise -j only with mem_monitor.sh watching.
#
# Usage (from the repo ROOT, inside tmux — CLAUDE.md "Running long scripts"):
#   collection-01/scripts/run_07_scars.sh pixels [-j 4] [--force] [fire_year ...]
#   collection-01/scripts/run_07_scars.sh scars  [-j 3] [--force] [cal_year ...]
set -u

cd "$(dirname "$0")/../.." || exit 1   # repo root (the R script expects to run from here)

MODE=${1:-}
case "$MODE" in
  pixels|scars) shift ;;
  *) echo "usage: $0 pixels|scars [-j N] [--force] [year ...]" >&2; exit 2 ;;
esac

JOBS=0
FORCE=0
YEARS=()
while (( $# )); do
  case "$1" in
    -j)      JOBS=$2; shift 2 ;;
    --force) FORCE=1; shift ;;
    [0-9][0-9][0-9][0-9]) YEARS+=("$1"); shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
# `scars` holds a whole calendar year's pixel set in RAM at once, so it gets fewer workers
(( JOBS > 0 )) || { if [[ $MODE == pixels ]]; then JOBS=4; else JOBS=3; fi; }

SNIC_DIR=collection-01/data/snic-rasters
PIX_CACHE=collection-01/data/scars-pixels-cache
SCAR_DIR=collection-01/data/objects-scars
ZIP_DIR=collection-01/data/scars-upload-cache
LOGDIR=collection-01/logs
STAMP=$(date '+%Y%m%d_%H%M%S')
RUNLOG="$LOGDIR/07_${MODE}_${STAMP}.log"
mkdir -p "$LOGDIR" "$PIX_CACHE" "$SCAR_DIR" "$ZIP_DIR"

say() { printf '%s %s\n' "$(date '+%F %T')" "$1" | tee -a "$RUNLOG"; }

if (( ${#YEARS[@]} == 0 )); then
  if [[ $MODE == pixels ]]; then
    while IFS= read -r d; do YEARS+=("$(basename "$d")"); done \
      < <(find "$SNIC_DIR" -mindepth 1 -maxdepth 1 -type d -regex '.*/[0-9][0-9][0-9][0-9]' | sort)
  else
    YEARS=($(seq 1999 2025))
  fi
fi
(( ${#YEARS[@]} )) || { echo "no years to process" >&2; exit 1; }

# Size proxy for the biggest-first ordering: the step-05 metrics CSV grows with object count.
size_of() {
  local y=$1 f
  if [[ $MODE == pixels ]]; then f="collection-01/data/objects-raw/objects_${y}_raster_metrics.csv"
  else f="collection-01/data/objects-raw/objects_${y}_raster_metrics.csv"; fi
  [[ -s $f ]] && stat -c%s "$f" || echo 0
}

done_marker() { echo "$PIX_CACHE/.done_fy$1"; }

TODO=()
while IFS= read -r y; do
  if [[ $MODE == pixels ]]; then out=$(done_marker "$y"); else out="$ZIP_DIR/scars_${y}.zip"; fi
  if (( FORCE == 0 )) && [[ -s "$out" || -f "$out" ]]; then
    say "SKIP  $y (already done: $(basename "$out"))"
  else
    TODO+=("$y")
  fi
done < <(for y in "${YEARS[@]}"; do printf '%s %s\n' "$(size_of "$y")" "$y"; done | sort -rn | cut -d' ' -f2)

(( ${#TODO[@]} )) || { say "nothing to do — every year already built"; exit 0; }

say "07 $MODE: ${#TODO[@]} year(s) on $JOBS worker(s)  log=$RUNLOG"
say "  order (biggest first): ${TODO[*]}"

t0=$SECONDS
printf '%s\n' "${TODO[@]}" | xargs -P "$JOBS" -I{} bash -c '
  y={}; mode='"$MODE"'; log="'"$LOGDIR"'/07_${mode}_${y}.log"
  s=$SECONDS
  OBJ_CORES=${OBJ_CORES:-4} Rscript collection-01/workflow/07-calendar_scars.R "$mode" "$y" \
    > "$log" 2>&1
  rc=$?
  d=$(( SECONDS - s ))
  if (( rc == 0 )); then
    [[ $mode == pixels ]] && touch "'"$PIX_CACHE"'/.done_fy${y}"
    printf "%s OK    %s %s in %dm%02ds\n" "$(date "+%F %T")" "$mode" "$y" $((d/60)) $((d%60))
  elif (( rc == 137 )); then
    printf "%s OOM   %s %s KILLED after %dm%02ds (rc=137) — see %s\n" "$(date "+%F %T")" "$mode" "$y" $((d/60)) $((d%60)) "$log"
  else
    printf "%s FAIL  %s %s rc=%d after %dm%02ds — see %s\n" "$(date "+%F %T")" "$mode" "$y" "$rc" $((d/60)) $((d%60)) "$log"
  fi
' 2>&1 | tee -a "$RUNLOG"

say "07 $MODE finished in $(( (SECONDS-t0)/60 )) min"
if [[ $MODE == scars ]]; then
  say "packages ready to upload: $(ls "$ZIP_DIR"/scars_*.zip 2>/dev/null | wc -l) / 27"
fi
