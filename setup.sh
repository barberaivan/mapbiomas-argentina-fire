#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# One-time setup: link the heavy DATA STORE into this code repo.
#
# This repo holds CODE only. The heavy data (training inputs, model fits, CV
# metrics, prediction plots) is NOT in git — it lives in a separate folder named
# "mapbiomas-arg-fire-store", synced via Insync/Google Drive. This script creates
# the symlinks that connect the two, so the scripts find the data where they expect.
#
# USAGE
#   ./setup.sh /path/to/mapbiomas-arg-fire-store   # first time — give the store location
#   ./setup.sh                                      # later — reuses the saved location
#
# See README.md ("Getting started") for where to download the store.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"                       # always operate from the repo root

# 1. Find the store location: a command-line argument wins; otherwise reuse the
#    saved .local-paths (gitignored, machine-specific).
if [ "$#" -ge 1 ]; then
  STORE_ROOT="$1"
  echo "STORE_ROOT=$STORE_ROOT" > .local-paths        # remember it for next time
elif [ -f .local-paths ]; then
  source .local-paths
else
  echo "Usage: ./setup.sh /path/to/mapbiomas-arg-fire-store"
  echo "(the store is the heavy-data folder from Insync or Google Drive — see README.md)"
  exit 1
fi
: "${STORE_ROOT:?STORE_ROOT is empty — pass the store path: ./setup.sh /path/to/store}"

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

echo
echo "Setup complete — heavy data is now linked into the repo."
