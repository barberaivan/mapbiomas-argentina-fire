"""
collection-01/workflow/00-status.py

Check the export status of training_observations assets across all regions.

For each fire in each region's training_fires asset, reports:
  DONE    — asset exists in GEE
  RUNNING — GEE task currently running
  PENDING — GEE task queued
  FAILED  — GEE task failed
  MISSING — no asset and no active task

Usage
-----
  python collection-01/workflow/00-status.py
  python collection-01/workflow/00-status.py --region PAT
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C

_ACTIVE = {"RUNNING", "READY"}
_LABEL_WIDTH = 9  # width of [RUNNING  ] etc.


def _get_task_index():
    """
    Return a dict mapping task description → task info for all recent
    training_obs tasks. Keeps the most recent entry per description.
    """
    index = {}
    for t in ee.data.getTaskList():
        desc = t.get("description", "")
        if not desc.startswith("training_obs_"):
            continue
        # prefer active tasks over completed/failed ones
        prev = index.get(desc)
        if prev is None or t["state"] in _ACTIVE:
            index[desc] = t
    return index


def _list_obs_assets(region):
    """Return set of short asset names (last path component) for training_observations in region."""
    folder = f"{C.TRAINING_DATA_COL1}/{region}"
    try:
        items = ee.data.listAssets({"parent": folder})
        return {a["name"].split("/")[-1] for a in items.get("assets", [])
                if "training_observations-fire_" in a["name"]}
    except Exception:
        return set()


def check_region(region, task_index):
    fires_path = f"{C.TRAINING_DATA_COL1}/{region}/training_fires"
    try:
        fires_info = ee.FeatureCollection(fires_path).getInfo()["features"]
    except Exception:
        print(f"\n=== {region} ===")
        print("  (no training_fires asset)")
        return 0, 0

    existing = _list_obs_assets(region)

    counts = {"DONE": 0, "RUNNING": 0, "PENDING": 0, "FAILED": 0, "MISSING": 0}
    lines = []
    for feat in fires_info:
        fire_id = feat["properties"]["fire_id"]
        fid_str = str(fire_id).removeprefix("fire_").zfill(2)

        # Check for any versioned asset
        done = [n for n in existing if n.startswith(f"training_observations-fire_{fid_str}")]
        if done:
            label = "DONE"
            detail = ", ".join(sorted(done))
        else:
            # Look for a matching task
            task_matches = [
                (desc, t) for desc, t in task_index.items()
                if f"_{region}_fire_{fid_str}_" in desc
            ]
            if task_matches:
                # pick the most recent active one, else the most recent overall
                desc, t = sorted(task_matches, key=lambda x: x[1]["state"] in _ACTIVE,
                                 reverse=True)[0]
                label  = t["state"] if t["state"] in ("RUNNING", "READY", "FAILED") else "FAILED"
                label  = "PENDING" if label == "READY" else label
                detail = f"task {t['id']}"
            else:
                label  = "MISSING"
                detail = ""

        counts[label] = counts.get(label, 0) + 1
        tag = f"[{label:<7}]"
        lines.append(f"  {fire_id}  {tag}  {detail}")

    n_total = len(fires_info)
    n_done  = counts["DONE"]
    print(f"\n=== {region} ({n_done}/{n_total} done) ===")
    for line in lines:
        print(line)
    return n_done, n_total


def main(regions):
    ee.Initialize(project=C.GEE_PROJECT)
    task_index = _get_task_index()

    grand_done, grand_total = 0, 0
    for region in regions:
        d, t = check_region(region, task_index)
        grand_done  += d
        grand_total += t

    if len(regions) > 1:
        print(f"\n{'─'*40}")
        print(f"Total: {grand_done}/{grand_total} fires done")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check training_observations export status.")
    parser.add_argument(
        "--region",
        choices=C.REGIONS,
        default=None,
        help="Check a single region (default: all regions).",
    )
    args = parser.parse_args()
    regions = [args.region] if args.region else C.REGIONS
    main(regions)
