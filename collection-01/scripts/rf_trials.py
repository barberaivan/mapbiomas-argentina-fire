"""
collection-01/scripts/rf_trials.py

Submit GEE classifier export tasks to trial different RF hyperparameters.
One task per tree count; each exports a trained ee.Classifier asset to
COLLECTION-1/MODELS/TRIALS/.

Usage
-----
  python collection-01/scripts/rf_trials.py \\
      --region-fire CHACO-BA --fire-class grassland --version 1

  # custom tree counts
  python collection-01/scripts/rf_trials.py \\
      --region-fire CHACO-BA --fire-class grassland --version 1 \\
      --n-trees 100 200 300 500

Run from the repo root.  Idempotent: if a run log already exists for this
region-fire / fire-class / version, status is printed and no tasks are
re-submitted.  Delete (or rename) the run log to force a fresh submission.

Run log
-------
  JSON: collection-01/workflow/rf_trials_{region_fire}_{fire_class}_v{version}.json
  CSV : collection-01/workflow/rf_trials_{region_fire}_{fire_class}_v{version}.csv
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import ee
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.constants import (
    GEE_PROJECT,
    TRAINING_DATA_COL1,
    ALL_FOCAL_FEATURES,
    MB_MOSAIC_FEATURE_NAMES,
)

# ─── Constants ────────────────────────────────────────────────────────────────

TRIALS_ROOT = (
    "projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/MODELS/TRIALS"
)

SHEET_CSV = (
    "https://docs.google.com/spreadsheets/d/"
    "17ZShb8D0JaJw4nLvBDzt19xF6Fdg8lGHYs4Jogh0X1A"
    "/export?format=csv&sheet=remap_by_region"
)

FIRE_CLASS_INT = {
    "forest":       1,
    "shrubland":    2,
    "grassland":    3,
    "agriculture":  4,
    "non-burnable": 0,
    "non-observed": -1,
}

# region-fire → list of region codes whose assets contribute to it
REGION_FIRE_MEMBERS = {
    "CHACO-BA": ["CHACO", "BA"],
    "PAT":      ["PAT"],
    "CUYO":     ["CUYO"],
    "PAMPA":    ["PAMPA"],
}

WORKFLOW_DIR = Path(__file__).resolve().parents[1] / "workflow"
INPUT_FEATURES = ALL_FOCAL_FEATURES + MB_MOSAIC_FEATURE_NAMES  # 17 focal + 21 mosaic = 38
LABEL = "burned"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def load_training_obs(region_fire: str) -> ee.FeatureCollection:
    """Merge all exported training-observation assets for a region-fire."""
    regions = REGION_FIRE_MEMBERS[region_fire]
    asset_ids = []
    for region in regions:
        run_log = WORKFLOW_DIR / f"01-training_data_export/run_{region}_v1.json"
        with open(run_log) as f:
            fires = json.load(f)["fires"]
        asset_ids.extend(fire["output_asset"] for fire in fires)
    print(f"  Merging {len(asset_ids)} assets for {region_fire} …")
    return ee.FeatureCollection([ee.FeatureCollection(a) for a in asset_ids]).flatten()


def build_remap(region_fire: str) -> tuple[list, list]:
    """
    Read the Google Sheets remap table and return (from_list, to_list) for
    proposal-2 (veg_fire_name_2), filtered to region_fire.
    """
    remap_raw = pd.read_csv(SHEET_CSV)
    remap_raw["mb_class_raw"] = pd.to_numeric(remap_raw["id"], errors="coerce")
    remap_raw = remap_raw.dropna(subset=["mb_class_raw"])
    remap_raw["mb_class_raw"] = remap_raw["mb_class_raw"].astype(int)

    remap = (
        remap_raw.loc[remap_raw["region_fire"] == region_fire,
                      ["mb_class_raw", "veg_fire_name_2"]]
        .drop_duplicates(subset=["mb_class_raw"])
        .dropna(subset=["veg_fire_name_2"])
        .copy()
    )
    remap["fire_class"] = remap["veg_fire_name_2"].map(FIRE_CLASS_INT)
    remap = remap.dropna(subset=["fire_class"])
    remap["fire_class"] = remap["fire_class"].astype(int)
    return remap["mb_class_raw"].tolist(), remap["fire_class"].tolist()


def apply_remap(obs: ee.FeatureCollection,
                from_list: list, to_list: list) -> ee.FeatureCollection:
    from_ee = ee.List(from_list)
    to_ee   = ee.List(to_list)

    def _remap(f):
        idx = from_ee.indexOf(f.getNumber("mb_class_raw"))
        fire_class = ee.Number(
            ee.Algorithms.If(idx.gte(0), to_ee.get(idx), -1)
        ).toInt()
        return f.set("fire_class", fire_class)

    return obs.map(_remap)


def ensure_trials_folder():
    for folder in [
        "projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/MODELS",
        TRIALS_ROOT,
    ]:
        try:
            ee.data.createAsset({"type": "Folder"}, folder)
            print(f"  Created folder: {folder}")
        except Exception:
            pass  # already exists


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region-fire",  default="CHACO-BA",
                        choices=list(REGION_FIRE_MEMBERS))
    parser.add_argument("--fire-class",   default="grassland",
                        choices=[k for k in FIRE_CLASS_INT if k not in ("non-burnable", "non-observed")])
    parser.add_argument("--version",      type=int, default=1)
    parser.add_argument("--n-trees",      type=int, nargs="+", default=[100, 200, 300, 500])
    args = parser.parse_args()

    region_fire = args.region_fire
    fire_class  = args.fire_class
    version     = args.version
    n_trees_list = sorted(args.n_trees)

    slug = f"rf_trials_{region_fire}_{fire_class}_v{version}".replace("-", "_")
    json_path = WORKFLOW_DIR / f"{slug}.json"
    csv_path  = WORKFLOW_DIR / f"{slug}.csv"

    ee.Initialize(project=GEE_PROJECT)

    # ── Idempotency check ────────────────────────────────────────────────────
    if json_path.exists():
        with open(json_path) as f:
            run_log = json.load(f)
        print(f"\nRun log found: {json_path}")
        print(f"{'n_trees':<10} {'task_id':<30} {'state'}")
        print("-" * 60)
        for entry in run_log["tasks"]:
            s = ee.data.getTaskStatus(entry["task_id"])[0]
            print(f"  {entry['n_trees']:<8} {entry['task_id']:<30} {s['state']}")
        print("\nDelete the run log to re-submit.")
        return

    # ── Build training set ───────────────────────────────────────────────────
    print(f"\nLoading training observations for {region_fire} …")
    obs = load_training_obs(region_fire)

    print("Reading proposal-2 remap from Google Sheets …")
    from_list, to_list = build_remap(region_fire)

    fire_class_int = FIRE_CLASS_INT[fire_class]
    obs_remapped = apply_remap(obs, from_list, to_list)
    training_obs = (
        obs_remapped
        .filter(ee.Filter.eq("fire_class", fire_class_int))
        .filter(ee.Filter.notNull(INPUT_FEATURES))
    )
    print(f"Training set: {region_fire} / {fire_class} (fire_class={fire_class_int}), null-filtered")

    ensure_trials_folder()

    # ── Submit tasks ─────────────────────────────────────────────────────────
    print(f"\nSubmitting {len(n_trees_list)} RF trial tasks …")
    tasks = []
    submitted_at = datetime.now(timezone.utc).isoformat()

    for n_trees in n_trees_list:
        description = f"rf_{region_fire}_{fire_class}_{n_trees}trees_v{version}".replace("-", "_")
        asset_id    = f"{TRIALS_ROOT}/{description}"

        clf = (
            ee.Classifier.smileRandomForest(numberOfTrees=n_trees)
            .train(
                features=training_obs,
                classProperty=LABEL,
                inputProperties=INPUT_FEATURES,
            )
            .setOutputMode("PROBABILITY")
        )
        task = ee.batch.Export.classifier.toAsset(
            classifier=clf,
            description=description,
            assetId=asset_id,
        )
        task.start()
        tasks.append({
            "n_trees":      n_trees,
            "task_id":      task.id,
            "description":  description,
            "asset_id":     asset_id,
            "submitted_at": submitted_at,
        })
        print(f"  {n_trees:>4} trees → {task.id}")

    # ── Write run log ────────────────────────────────────────────────────────
    run_log = {
        "submitted_at":  submitted_at,
        "region_fire":   region_fire,
        "fire_class":    fire_class,
        "version":       version,
        "n_trees_list":  n_trees_list,
        "input_features": INPUT_FEATURES,
        "label":         LABEL,
        "output_mode":   "PROBABILITY",
        "tasks":         tasks,
    }
    with open(json_path, "w") as f:
        json.dump(run_log, f, indent=2)

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["n_trees", "task_id", "description",
                                               "asset_id", "submitted_at"])
        writer.writeheader()
        writer.writerows(tasks)

    print(f"\nRun log → {json_path}")
    print(f"CSV     → {csv_path}")


if __name__ == "__main__":
    main()
