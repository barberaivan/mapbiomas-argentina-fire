#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# One-time setup: record this machine's local paths and link the heavy DATA STORE.
#
# This repo holds CODE only. Two things are machine-specific and must NOT be in git:
#   • the heavy data (training inputs, model fits, CV metrics, prediction plots),
#     which lives in a separate "mapbiomas-arg-fire-store" folder synced via
#     Insync/Google Drive — this script symlinks it into the repo; and
#   • the Python interpreter (the GEE venv), whose path differs per machine.
# Both are saved to gitignored files so the docs can stay path-free (they say
# "run with $PYTHON") and each machine resolves them locally.
#
# USAGE
#   ./setup.sh /path/to/mapbiomas-arg-fire-store                       # store only (PYTHON=python3)
#   ./setup.sh /path/to/mapbiomas-arg-fire-store /path/to/venv/bin/python   # store + interpreter
#   ./setup.sh                                                          # later — reuses saved values
#
# See README.md ("Getting started") for where to download the store.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"                       # always operate from the repo root

# 1. Resolve machine-local values. Load anything saved before (gitignored), then
#    let command-line arguments override: arg 1 = store dir, arg 2 = python venv.
[ -f .local-paths ] && source .local-paths
[ "$#" -ge 1 ] && STORE_ROOT="$1"
[ "$#" -ge 2 ] && PYTHON="$2"

if [ -z "${STORE_ROOT:-}" ]; then
  echo "Usage: ./setup.sh /path/to/mapbiomas-arg-fire-store [/path/to/venv/bin/python]"
  echo "(the store is the heavy-data folder from Insync or Google Drive — see README.md)"
  exit 1
fi

# Python is optional — fall back to whatever python3 is on PATH.
PYTHON="${PYTHON:-python3}"

# Persist both for next time. Your shell can `source .local-paths` to get $PYTHON.
{
  echo "STORE_ROOT=$STORE_ROOT"
  echo "PYTHON=$PYTHON"
} > .local-paths

# 2. Make sure the store actually exists (the #1 novice mistake is a wrong path).
if [ ! -d "$STORE_ROOT" ]; then
  echo "ERROR: store folder not found: $STORE_ROOT"
  echo "Download it first (see README.md), then pass the correct path."
  exit 1
fi

# 3. Create one symlink per heavy folder. The store mirrors the repo's paths
#    exactly (STORE_ROOT/<rel>  <->  <rel>), so this is a mechanical loop:
#    adding a new heavy folder later = adding one line here.
LINKS=(
  collection-01/data            # heavy training inputs (active work)
  collection-01/models-store    # heavy model outputs: fits, cv_metrics, tuning, oof preds
  collection-00/models_fit/data       # collection-00 pilot inputs (reference)
  collection-00/models_fit/exports    # collection-00 pilot outputs (reference)
)
for rel in "${LINKS[@]}"; do
  target="$STORE_ROOT/$rel"
  if [ -e "$rel" ] && [ ! -L "$rel" ]; then
    echo "ERROR: $rel exists and is not a symlink — refusing to overwrite"; exit 1
  fi
  [ -d "$target" ] || echo "  note: $rel is empty in the store — creating it"
  mkdir -p "$target"
  ln -sfn "$target" "$rel"
  echo "linked  $rel  ->  $target"
done

# 4. Make $PYTHON visible to Claude Code. Claude Code reads its Bash environment
#    from .claude/settings.local.json (gitignored), NOT from .local-paths, so mirror
#    PYTHON into that file's env block — preserving permissions and anything else.
python3 - "$PYTHON" <<'PY'
import json, os, sys
py, path = sys.argv[1], ".claude/settings.local.json"
try:
    with open(path) as f:
        cfg = json.load(f)
except (FileNotFoundError, ValueError):
    cfg = {}
cfg.setdefault("env", {})["PYTHON"] = py
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
PY
echo "PYTHON=$PYTHON  (saved to .local-paths and .claude/settings.local.json)"

echo
echo "Setup complete — heavy data is linked and \$PYTHON is configured for this machine."
