#!/usr/bin/env bash
# run_07_upload_zips.sh — build the 28 per-fire-year zipped Shapefiles for the GEE table upload.
#
# WHY A LAUNCHER: `earthengine upload table` ingests only from `gs://`, and neither GEE account can
# reach a bucket (mapbiomas-fire-485203 has no billing account; no storage permission on
# mapbiomas-argentina) — see docs/06 §12. So the zip IS the deliverable and the upload is
# done by hand: Code Editor → Assets → NEW → Table upload → Shapefile, max vertices 1000000.
# 28 of those by hand is the price; building the 28 zips should at least be one command.
#
# Each year is an independent `objects_upload.py --dry-run` (build + zip, no ingest), so this
# parallelises at the process level like run_06_predict.sh. Peak memory is one year's geometry per
# worker (up to ~400 MB GPKG → OGR), hence a modest default of 4.
#
# Usage (from the repo ROOT, inside tmux — see CLAUDE.md "Running long scripts"):
#   collection-01/scripts/run_07_upload_zips.sh [-j WORKERS] [--force] [year ...]
#     -j WORKERS  parallel years (default 4)
#     --force     rebuild years whose .zip already exists
#     year …      only these fire-years (default: every year with a prediction CSV)
#
# RESUMABLE: a year whose objects_raw_<fy>.zip already exists is skipped unless --force.
set -u

cd "$(dirname "$0")/../.." || exit 1   # repo root

JOBS=4
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

PYTHON=$(sed -n 's/^PYTHON=//p' .local-paths)
[[ -n "$PYTHON" ]] || { echo "PYTHON not set in .local-paths — run ./setup.sh" >&2; exit 1; }
STORE=$(sed -n 's/^STORE_ROOT=//p' .local-paths)
PRED_DIR=collection-01/data/objects-pred
OUT_DIR="$STORE/collection-01/data/objects-upload-cache"
LOGDIR=collection-01/logs
STAMP=$(date '+%Y%m%d_%H%M%S')
RUNLOG="$LOGDIR/07_upload_zips_${STAMP}.log"
mkdir -p "$LOGDIR" "$OUT_DIR"

say() { printf '%s %s\n' "$(date '+%F %T')" "$1" | tee -a "$RUNLOG"; }

if (( ${#YEARS[@]} == 0 )); then
  while IFS= read -r f; do
    b=$(basename "$f"); YEARS+=("${b:8:4}")
  done < <(ls "$PRED_DIR"/objects_[0-9][0-9][0-9][0-9]_pred.csv 2>/dev/null)
fi
(( ${#YEARS[@]} )) || { echo "no prediction CSVs in $PRED_DIR" >&2; exit 1; }

# biggest first: the pool is only as fast as its last task
TODO=()
while IFS= read -r fy; do
  out="$OUT_DIR/objects_raw_${fy}.zip"
  if (( FORCE == 0 )) && [[ -s "$out" ]]; then
    say "SKIP  FY$fy (already built: $(basename "$out"))"
  else
    TODO+=("$fy")
  fi
done < <(for fy in "${YEARS[@]}"; do
           g="$STORE/collection-01/data/objects-raw/objects_${fy}.gpkg"
           printf '%s %s\n' "$( [[ -f $g ]] && stat -c%s "$g" || echo 0 )" "$fy"
         done | sort -rn | cut -d' ' -f2)

(( ${#TODO[@]} )) || { say "nothing to do — every year already built"; exit 0; }

say "BUILD ${#TODO[@]} zip(s) on $JOBS worker(s) -> $OUT_DIR"
say "  order (biggest first): ${TODO[*]}"

t0=$SECONDS
printf '%s\n' "${TODO[@]}" | xargs -P "$JOBS" -I{} bash -c '
  fy={}; log="'"$LOGDIR"'/07_upload_zips_${fy}.log"
  s=$SECONDS
  if '"$PYTHON"' collection-01/scripts/objects_upload.py --year "$fy" --dry-run > "$log" 2>&1; then
    z=$(sed -n "s/.*-> \(objects_raw_[0-9]*\.zip\) (\(.*\))/\1 \2/p" "$log" | tail -1)
    printf "%s YEAR  FY%s done in %ss  %s\n" "$(date "+%F %T")" "$fy" "$((SECONDS-s))" "$z"
  else
    printf "%s YEAR  FY%s FAILED rc=%s — see %s\n" "$(date "+%F %T")" "$fy" "$?" "$log"
  fi' | tee -a "$RUNLOG"

dt=$(( SECONDS - t0 ))
n=$(ls "$OUT_DIR"/objects_raw_[0-9][0-9][0-9][0-9].zip 2>/dev/null | wc -l)
tot=$(du -ch "$OUT_DIR"/objects_raw_*.zip 2>/dev/null | tail -1 | cut -f1)
say "BATCH done in $((dt/60))m$((dt%60))s — $n zip(s), $tot in $OUT_DIR"
