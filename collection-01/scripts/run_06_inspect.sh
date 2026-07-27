#!/usr/bin/env bash
# run_06_inspect.sh — build the QGIS inspection layers for every fire-year, IN PARALLEL.
#
# Wraps scripts/objects_inspect_export.R (one Rscript per fire-year, N at a time). Same reason
# as run_06_predict.sh: the years are independent and the work is single-threaded, so the
# parallelism belongs at the process level.
#
# UNLIKE PREDICTION, THIS IS I/O AND MEMORY BOUND, NOT CPU BOUND. Each worker reads a whole
# year's geometry (up to 386 MB / 93 k multipolygons) into a SpatVector, joins the attributes and
# writes a ~350 MB GPKG, so peak RSS is a couple of GB per worker and the disk is doing real work.
# Hence -j 6 by default rather than 8, and the RAM monitor runs alongside. Budget ~7 GB of output
# for the full 28 years.
#
# Usage (from the repo ROOT, inside tmux — see CLAUDE.md "Running long scripts"):
#   collection-01/scripts/run_06_inspect.sh [-j WORKERS] [--sample N] [--force] [year ...]
#     -j WORKERS  parallel years (default 6)
#     --sample N  objects per p_mean decile in the companion GeoJSON (default 20; 0 = skip)
#     --force     rebuild years that already have an output GPKG
#     year …      only these fire-years (default: every year with a prediction CSV)
#
# RESUMABLE: a year whose <fy>_objects_pred.gpkg already exists is skipped unless --force.
set -u

cd "$(dirname "$0")/../.." || exit 1   # repo root (the R scripts expect to run from here)

JOBS=6
SAMPLE=20
FORCE=0
YEARS=()
while (( $# )); do
  case "$1" in
    -j)       JOBS=$2; shift 2 ;;
    --sample) SAMPLE=$2; shift 2 ;;
    --force)  FORCE=1; shift ;;
    [0-9][0-9][0-9][0-9]) YEARS+=("$1"); shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

POLY_DIR=collection-01/data/snic-polygons
PRED_DIR=collection-01/data/objects-predictions
OUT_DIR=collection-01/data/objects-inspect
LOGDIR=collection-01/logs
MONITOR=collection-01/scripts/mem_monitor.sh
STAMP=$(date '+%Y%m%d_%H%M%S')
RUNLOG="$LOGDIR/06_inspect_${STAMP}.log"
MEMLOG="$LOGDIR/06_inspect_mem_${STAMP}.log"
mkdir -p "$LOGDIR" "$OUT_DIR"

say() { printf '%s %s\n' "$(date '+%F %T')" "$1" | tee -a "$RUNLOG"; }

# default: every year that has been scored
if (( ${#YEARS[@]} == 0 )); then
  while IFS= read -r f; do
    b=$(basename "$f"); YEARS+=("${b:8:4}")
  done < <(ls "$PRED_DIR"/objects_[0-9][0-9][0-9][0-9]_pred.csv 2>/dev/null)
fi
(( ${#YEARS[@]} )) || { echo "no predictions in $PRED_DIR — run run_06_predict.sh first" >&2; exit 1; }

# biggest years first, by source geometry size — keeps a 386 MB year off the tail of the pool
TODO=()
while IFS= read -r fy; do
  out="$OUT_DIR/${fy}_objects_pred.gpkg"
  if (( FORCE == 0 )) && [[ -s "$out" ]]; then
    say "SKIP  FY$fy (already built: $(basename "$out"))"
  else
    TODO+=("$fy")
  fi
done < <(for fy in "${YEARS[@]}"; do
           printf '%s %s\n' "$(stat -c%s "$POLY_DIR/objects_${fy}.gpkg" 2>/dev/null || echo 0)" "$fy"
         done | sort -rn | cut -d' ' -f2)

(( ${#TODO[@]} )) || { say "nothing to do — every year already built"; exit 0; }

# generic whole-system RAM sampler (scripts/mem_monitor.sh): warn under 3 GB available, since 6
# workers each holding a year of geometry is the memory risk here
bash "$MONITOR" "$MEMLOG" 15 3072 &
MON=$!
trap 'kill "$MON" 2>/dev/null' EXIT

say "INSPECT ${#TODO[@]} year(s) on $JOBS worker(s), sample=$SAMPLE"
say "  log=$RUNLOG mem=$MEMLOG"
say "  order (biggest first): ${TODO[*]}"

t0=$SECONDS
printf '%s\n' "${TODO[@]}" | xargs -P "$JOBS" -I{} bash -c '
  fy={}; log="'"$LOGDIR"'/06_inspect_${fy}.log"
  s=$SECONDS
  if Rscript collection-01/scripts/objects_inspect_export.R "$fy" --sample '"$SAMPLE"' > "$log" 2>&1; then
    mb=$(du -m "'"$OUT_DIR"'/${fy}_objects_pred.gpkg" 2>/dev/null | cut -f1)
    printf "%s YEAR  FY%s done in %ss (%s MB)\n" "$(date "+%F %T")" "$fy" "$((SECONDS-s))" "${mb:-?}"
  else
    printf "%s YEAR  FY%s FAILED rc=%s — see %s\n" "$(date "+%F %T")" "$fy" "$?" "$log"
  fi' | tee -a "$RUNLOG"

dt=$(( SECONDS - t0 ))
n=$(ls "$OUT_DIR"/[0-9][0-9][0-9][0-9]_objects_pred.gpkg 2>/dev/null | wc -l)
tot=$(du -sh "$OUT_DIR" 2>/dev/null | cut -f1)
say "BATCH done in $((dt/60))m$((dt%60))s — $n layer(s), $tot in $OUT_DIR"
grep -c WARN "$MEMLOG" >/dev/null 2>&1 && say "  NOTE: $(grep -c WARN "$MEMLOG") near-OOM WARN line(s) in $MEMLOG"
