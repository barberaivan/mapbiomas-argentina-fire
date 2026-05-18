"""
collection-01/scripts/download_observations.py

Download training data from GEE assets to local CSVs for exploration.
Not a pipeline step — run this ad-hoc after 01-training_data_export.py has completed.

Two tables are available:
  fires  — training_fires FeatureCollection (one row per fire event, includes post_upr_short)
  obs    — training_observations (one row per Landsat obs × training point, fire-by-fire loop)

Usage
-----
  python collection-01/scripts/download_observations.py --region PAT --version 1 --what all
  python collection-01/scripts/download_observations.py --region PAT --version 1 --what obs
  python collection-01/scripts/download_observations.py --region PAT --what fires
"""

import argparse
import csv
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
import requests
from utils import constants as C

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _fetch_csv(fc):
    """Download a FeatureCollection as (rows, fieldnames) via GEE's signed URL."""
    url = fc.getDownloadURL(filetype="CSV")
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()

    if resp.content[:2] == b"PK":          # ZIP magic bytes
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            name = next(n for n in zf.namelist() if n.endswith(".csv"))
            text = zf.read(name).decode("utf-8")
    else:
        text = resp.content.decode("utf-8")

    reader = csv.DictReader(io.StringIO(text))
    return list(reader), reader.fieldnames


def _write_csv(rows, fieldnames, path):
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def download_fires(region):
    asset_path = f"{C.TRAINING_DATA_COL1}/{region}/training_fires"
    print(f"training_fires ({region}) ...", end=" ", flush=True)
    rows, fieldnames = _fetch_csv(ee.FeatureCollection(asset_path))
    out_path = DATA_DIR / f"training_fires_{region}.csv"
    _write_csv(rows, fieldnames, out_path)
    print(f"{len(rows)} rows → {out_path}")


def download_obs(region, version):
    region_path = f"{C.TRAINING_DATA_COL1}/{region}"
    assets = ee.data.listAssets({"parent": region_path}).get("assets", [])
    obs_assets = sorted(
        a["name"] for a in assets
        if "training_observations" in a["name"] and f"_v{version}" in a["name"]
    )

    if not obs_assets:
        print(f"No training_observations assets found for {region} v{version}.")
        return

    print(f"training_observations ({region} v{version}): {len(obs_assets)} fire asset(s)")

    all_rows = []
    fieldnames = None
    for asset_path in obs_assets:
        name = asset_path.split("/")[-1]
        print(f"  {name} ...", end=" ", flush=True)
        try:
            rows, fields = _fetch_csv(ee.FeatureCollection(asset_path))
            if fieldnames is None:
                fieldnames = fields
            all_rows.extend(rows)
            print(f"{len(rows)} rows")
        except Exception as exc:
            print(f"FAILED ({exc})")

    if not all_rows:
        print("No data downloaded.")
        return

    out_path = DATA_DIR / f"training_observations_{region}_v{version}.csv"
    _write_csv(all_rows, fieldnames, out_path)
    print(f"\n{len(all_rows)} total rows → {out_path}")


def main(region, version, what):
    ee.Initialize(project=C.GEE_PROJECT)
    if what in ("fires", "all"):
        download_fires(region)
    if what in ("obs", "all"):
        download_obs(region, version)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download training data to local CSVs.")
    parser.add_argument("--region", choices=C.REGIONS, default="PAT")
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--what", choices=["obs", "fires", "all"], default="all",
                        help="Which table(s) to download (default: all).")
    args = parser.parse_args()
    main(args.region, args.version, args.what)
