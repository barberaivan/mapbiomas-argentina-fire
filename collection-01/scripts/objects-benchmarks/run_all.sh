#!/bin/bash
# Extract is cached. Run: union-find label -> Path A (write+polygonize+dissolve) -> Path B (13c) -> compare.
set -uo pipefail
D="$F2000_DIR"; PY=/home/ivan/.venvs/gee/bin/python
cd /home/ivan/dev/MapBiomas/mapbiomas-arg-fire

echo "==================== STAGE 0b: union-find label ===================="
/usr/bin/time -v Rscript "$D/stage0_label_uf.R" 2>&1
grep -q "STAGE0 DONE" "$D/meta.json" 2>/dev/null
if [ ! -f "$D/pid.i32" ]; then echo "LABEL FAILED (no pid.i32) — aborting"; exit 1; fi

echo "==================== PATH A: write + polygonize ===================="
/usr/bin/time -v "$PY" "$D/stageA.py" 2>&1
echo "-------------------- Path A dissolve-by-pid (R) --------------------"
/usr/bin/time -v Rscript "$D/stageA_dissolve.R" 2>&1

echo "==================== PATH B: per-object, 13 cores ===================="
export F2000_CORES=13
/usr/bin/time -v Rscript "$D/stageB.R" 2>&1

echo "==================== COMPARE ===================="
Rscript "$D/compare.R" 2>&1
echo "ALLDONE"
