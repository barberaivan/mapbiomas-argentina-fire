#!/usr/bin/env python3
"""Delete the 07e per-fire-year TEST assets and their folder.

    FINAL_PRODUCTS/burned_area_polygons_by_fire_year/burned_area_polygons_2012
    FINAL_PRODUCTS/burned_area_polygons_by_fire_year/burned_area_polygons_2021
    FINAL_PRODUCTS/burned_area_polygons_by_fire_year/            (the folder itself)

Both are leftovers of the 07e investigation, and both did their job (docs/07 §13.6):

* **2012** proved the schema on a LANDED asset — that ISO date strings and `system:time_start`
  survive `Export.table.toAsset`, which would otherwise have been discovered 3 h into a merged run;
* **2021** proved the duplication is in the STORED SOURCE and not a function of export size: 53 k
  features exported alone came out with the same 1,249 duplicate rows as the 1.26 M-feature merge.

Neither is a product.  The shareable layer is the merged `burned_area_polygons_v1`, which is verified
clean, and the `--per-year` code path that would have written more of these is gone.

CLAUDE.md's rule is that **the user runs deletions** — so this is a dry run by default and prints
exactly what it would delete.  Pass `--apply` to do it.  Before deleting anything it asserts the
asset's TYPE and its full PATH, and asserts the folder is EMPTY, so a mistyped path or an unexpected
asset type stops the script instead of removing something else.

    $PYTHON collection-01/scripts/delete_07e_by_year_assets.py            # dry run
    $PYTHON collection-01/scripts/delete_07e_by_year_assets.py --apply    # delete

The assets live in `mapbiomas-argentina` but were created by BOTH accounts (2012 by the primary,
2021 by the primary; the merged layer by comahue), and deletion needs write access to the project —
add `--credentials ~/.config/earthengine/credentials.comahue` if the resident account is refused.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils.constants as C  # noqa: E402

FOLDER = f"{C.FINAL_PRODUCTS}/burned_area_polygons_by_fire_year"
TABLES = [f"{FOLDER}/burned_area_polygons_{fy}" for fy in (2012, 2021)]


def initialize(project, credentials_path=None):
    if not credentials_path:
        ee.Initialize(project=project)
        return
    from google.oauth2.credentials import Credentials
    stored = json.loads(Path(credentials_path).expanduser().read_text())
    ee.Initialize(Credentials(
        None,
        refresh_token=stored["refresh_token"],
        token_uri=ee.oauth.TOKEN_URI,
        client_id=stored.get("client_id", ee.oauth.CLIENT_ID),
        client_secret=stored.get("client_secret", ee.oauth.CLIENT_SECRET),
        scopes=stored.get("scopes", ee.oauth.SCOPES),
        quota_project_id=stored.get("project"),
    ), project=project)
    print(f"[auth] {credentials_path}  |  project {project}")


def get(asset_id):
    try:
        return ee.data.getAsset(asset_id)
    except ee.EEException:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry run)")
    ap.add_argument("--project", default="mapbiomas-argentina")
    ap.add_argument("--credentials")
    args = ap.parse_args()
    initialize(args.project, args.credentials)

    # The merged layer must exist and be the real one before anything is removed: these assets are
    # only disposable BECAUSE it is there and verified.
    merged = f"{C.FINAL_PRODUCTS}/burned_area_polygons_v1"
    info = get(merged)
    assert info and info["type"] == "TABLE", f"{merged} missing or not a TABLE — refusing to delete"
    n = ee.FeatureCollection(merged).size().getInfo()
    print(f"[guard] {merged}\n        exists, TABLE, {n:,} features")
    assert n == 1_263_079, f"expected 1,263,079 features in the merged layer, found {n:,}"

    for asset_id in TABLES:
        a = get(asset_id)
        if a is None:
            print(f"[gone] {asset_id}")
            continue
        assert a["type"] == "TABLE", f"{asset_id} is {a['type']}, not TABLE — refusing"
        assert a["name"].endswith(asset_id.split("/assets/")[-1]), f"path mismatch on {asset_id}"
        size = ee.FeatureCollection(asset_id).size().getInfo()
        if args.apply:
            ee.data.deleteAsset(asset_id)
            print(f"[deleted] TABLE  {asset_id}  ({size:,} features)")
        else:
            print(f"[dry] would delete TABLE  {asset_id}  ({size:,} features)")

    a = get(FOLDER)
    if a is None:
        print(f"[gone] {FOLDER}")
    else:
        assert a["type"] == "FOLDER", f"{FOLDER} is {a['type']}, not FOLDER — refusing"
        children = ee.data.listAssets({"parent": FOLDER}).get("assets", [])
        if args.apply:
            assert not children, f"{FOLDER} still has {len(children)} children — refusing"
            ee.data.deleteAsset(FOLDER)
            print(f"[deleted] FOLDER {FOLDER}")
        else:
            print(f"[dry] would delete FOLDER {FOLDER}  "
                  f"(currently {len(children)} child asset(s) — deleted first, above)")

    print("\n[after] " + ("re-listing FINAL_PRODUCTS:" if args.apply else "dry run only, nothing changed."))
    if args.apply:
        for x in ee.data.listAssets({"parent": C.FINAL_PRODUCTS}).get("assets", []):
            print(f"   {x['type']:6s} {x['name'].split('/')[-1]}")


if __name__ == "__main__":
    main()
