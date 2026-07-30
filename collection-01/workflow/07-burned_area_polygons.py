#!/usr/bin/env python3
"""
collection-01/workflow/07-burned_area_polygons.py

Step 07e — the FIRE-OBJECT POLYGON LAYER: every mapped fire, all 28 fire-years, in one
FeatureCollection, for sharing with early users.

    projects/…/FIRE/COLLECTION-1/FINAL_PRODUCTS/burned_area_polygons_v1

Nothing is computed here and no geometry is touched: the layer is the step-06 object set
(`objects_raw_<fy>`, 28 FCs) filtered to the accepted fires and stripped to ten properties,
merged and flattened across fire-years.  Measured: **1,263,079 polygons, 74.23 Mha**.

    fire == 1  AND  area_ha >= C.MIN_FIRE_HA

the same POSITIVE selection step 07a paints (docs/07 §1).  `fire` is the deployed call — the
collected label where there is one, else the probit-BART model (docs/06 §5) — so `fire_tag == -1`
means *unlabelled*, never *not fire*, and "not rejected" is not the same filter: 36 objects are
entirely `candseed==3` dieback with a null `fire`, and this excludes them.

WHY "polygons" AND NOT "vectors"
--------------------------------
`FINAL_PRODUCTS/annual_burned_vectors/` is already taken, by the CALENDAR-year scars that feed
the scar-size chain (07b/07c).  Those are a different thing from these — plain 8-connectivity,
calendar-clipped, one scar per connected burn — and reusing the network's word for both would put
two unrelated layers one line apart in the asset tree under near-identical names.  "polygons" also
says what a user actually gets, where a "vector" could be points or lines.

⚠️ THIS LAYER IS IN `FINAL_PRODUCTS` BY DELIBERATE OVERRIDE of docs/08 open #8, which parked the
fire-year vector database OUTSIDE `FINAL_PRODUCTS` until IPAM rules whether Argentina may publish
it.  Iván's call (2026-07-30): early users get a link that stays valid if the ruling is yes, and
Brazil's own col-5 `annual_burned_vectors` is the precedent that the door is open.  The leak risk
is small — `ToPublish/2-toAsset-Public` copies an EXPLICIT subproduct list, not the folder — but
if the ruling is no, this asset moves and the shared link dies with it.

THE TEN PROPERTIES
------------------
| property        | source        | meaning                                                     |
|-----------------|---------------|-------------------------------------------------------------|
| `oid`           | `oid`         | stable object id, `<fy>_<n>` — the key to join user feedback |
|                 |               | back to the object database and its 20 metrics              |
| `fire_year`     | asset name    | the NON-calendar mapping year: 1 May *fy* → 30 Apr *fy*+1   |
| `calendar_year` | `year_cal`    | the MODE of the object's per-pixel calendar years           |
| `area_ha`       | `area_ha`     | pixel-count area (NOT a geodesic polygon area)              |
| `date_med`      | `date_med`    | median burn date, whole days since 1970-01-01               |
| `date_min/max`  | `date_min/max`| first / last burn date, same encoding                       |
| `p_mean`        | `p_mean`      | posterior mean fire probability (probit BART)               |
| `p_width`       | `p_width`     | width of its credible interval, `p_q95 - p_q05`             |
| `seed_mean`     | `seed_mean`   | mean SNIC seed burn probability over the object             |

`fire_year` is NOT a property of the source FCs — it is only implicit in the asset name, so it is
set per source collection here.  Every other name is carried through unchanged except `year_cal`,
which is renamed for people who have never read docs/06.

TWO THINGS TO TELL USERS, both recorded in the asset properties
---------------------------------------------------------------
1. **`calendar_year` is the object's MAJORITY year, and the rasters do not agree with it.**  It is
   `mode_int(cyear)` over the object's pixels (`05-objects_metrics.R:239`).  The published rasters
   assign the calendar year and month PER PIXEL, so a fire straddling 31 December is split between
   two years there and lands whole in one year here (docs/07 §1).  Neither is wrong; they answer
   different questions, and a user who cross-tabulates the two without knowing this will find
   "missing" area.
2. **Fire-year 1998 is in this layer and in no published raster.**  3,845 polygons carry
   `calendar_year` 1998 or 1999; the calendar series starts at 1999, so FY1998's Nov–Dec 1998 tail
   (1,058,206 px, ~76 kha) appears here only (docs/07 §2).

IS ONE MERGED EXPORT FEASIBLE?  Measured, not assumed
-----------------------------------------------------
The 28 source shapefiles hold **5.12 GB** of raw `.shp` geometry for 1.689 M objects (~190
vertices/polygon), so the fire-only subset is ~4-4.5 GB.  GEE already stores exactly that in the
28 source assets — reading it is not the question.  One `Export.table.toAsset` shuffling 1.26 M
complex multipolygons is: there is no documented feature limit, but this is the upper end of where
such tasks succeed and the failure mode is `User memory limit exceeded` AFTER hours.  Precedent is
against it — Brazil ships `mbfogo_col5_<year>_v1` per year, our scars are 27 per-year assets,
`objects_raw` is 28; nobody in the network ships one merged all-years vector.  Building it locally
and ingesting instead is worse: >2 GB breaks the Shapefile limit and no GCS bucket is reachable
(docs/06 §12).

So it is worth ONE task to find out, with a fallback that wastes nothing:

    --year 2012     one fire-year (22 k polygons, minutes) -> validates the schema on a LANDED
                    asset, and is simultaneously the first asset of the fallback
    --launch        the single merged layer.  If it lands, that is the shareable FC.
    --per-year      the fallback: 28 assets in FINAL_PRODUCTS/burned_area_polygons_by_fire_year/,
                    which users load as one FC in a line (printed by --check)

Usage (from the repo ROOT)
--------------------------
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --check
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --year 2012 --launch   # validate
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --verify --year 2012   # on the asset
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --launch               # the merged one
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --per-year --launch    # the fallback
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --set-props            # after landing

  # as the SECOND account, so this does not queue behind the first account's tasks (the GEE task
  # queue is per user). Only the compute project changes; the destination asset is the same:
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --launch \
      --project mapbiomas-argentina \
      --credentials ~/.config/earthengine/credentials.comahue

Resumable: an asset that exists, or whose task is PENDING/RUNNING, is skipped.  Task descriptions
are namespaced `arg07e_` because `ee.data.listOperations()` is PROJECT-scoped and this compute
project is shared with every other country's team (docs/07 §12.7).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils.constants as C  # noqa: E402

TASK_PREFIX = "arg07e_"
SUBPRODUCT = "burned_area_polygons"

# The fallback's folder.  Distinct from the merged asset's name so the two can coexist while we
# find out whether the single task survives.
BY_YEAR_DIR = f"{C.FINAL_PRODUCTS}/{SUBPRODUCT}_by_fire_year"

# The ten properties, in order.  `fire_year` is set here (it is only implicit in the asset name);
# `year_cal` -> `calendar_year` is the one rename.  Everything else is carried through verbatim so
# the layer speaks the same vocabulary as the object database it came from.
SRC = ["oid", "fire_year", "year_cal", "area_ha",
       "date_med", "date_min", "date_max", "p_mean", "p_width", "seed_mean"]
DST = ["oid", "fire_year", "calendar_year", "area_ha",
       "date_med", "date_min", "date_max", "p_mean", "p_width", "seed_mean"]

FIRE_YEARS = list(range(1998, 2026))          # 28, the object database's full span


# ---------------------------------------------------------------------------
# auth — run this export as the OTHER account, without swapping the resident file
# ---------------------------------------------------------------------------
def initialize(project, credentials_path=None):
    """`ee.Initialize`, optionally with a credentials file that is NOT the resident one.

    GEE's task queue is PER USER, so a long export submitted by the account that is already
    running 27 other tasks waits behind them.  Submitting it as the second account
    (`ivanbarbera@comahue-conicet.gob.ar`, on the `mapbiomas-argentina` compute project) starts it
    immediately.  Only the COMPUTE project changes — the destination asset path is unaffected, so
    the shared link is the same either way.

    `ee.oauth.get_credentials_path()` hardcodes `~/.config/earthengine/credentials` with no env
    override, and CLAUDE.md's answer is to `cp` the account you want into place.  Passing the file
    explicitly is better: nothing is clobbered, two accounts can be used in the same session, and a
    half-finished swap cannot leave the wrong token resident.  Keep per-account backups
    (`credentials.gmail`, `credentials.comahue`) and point `--credentials` at one.
    """
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
    print(f"[auth] {credentials_path}  |  compute project {project}")


# ---------------------------------------------------------------------------
# asset plumbing
# ---------------------------------------------------------------------------
def asset_exists(asset_id):
    try:
        ee.data.getAsset(asset_id)
        return True
    except ee.EEException:
        return False


def ensure_container(asset_id, kind):
    if asset_exists(asset_id):
        return False
    ee.data.createAsset({"type": kind}, asset_id)
    print(f"[created] {kind:16s} {asset_id}")
    return True


def task_in_flight(description):
    for op in ee.data.listOperations():
        meta = op.get("metadata", {})
        if (meta.get("description") == description
                and meta.get("state") in ("PENDING", "RUNNING")):
            return True
    return False


def merged_asset():
    """`FINAL_PRODUCTS/burned_area_polygons_v1` — a PLAIN name, deliberately.

    NOT `C.product_name()`. That builds the network's
    `mapbiomas_argentina_fire_collection1_<subproduct>_v1`, which is mandatory for the published
    raster subproducts because the platform's `band_format` lookup and the publish copy expect it.
    This layer is not one of those: it is ours, it is for people, and it is a name a user has to
    read and type (Iván, 2026-07-30).
    """
    return f"{C.FINAL_PRODUCTS}/{SUBPRODUCT}_v1"


def year_asset(fire_year):
    return f"{BY_YEAR_DIR}/{SUBPRODUCT}_{fire_year}"


# ---------------------------------------------------------------------------
# the layer
# ---------------------------------------------------------------------------
def fire_filter():
    """The accepted-fire filter.  A function, not a module constant: building an `ee.Filter` at
    import time runs before `ee.Initialize()` and dies with "client library not initialized"."""
    return ee.Filter.And(ee.Filter.eq("fire", 1),
                         ee.Filter.gte("area_ha", C.MIN_FIRE_HA))


def fires(fire_year):
    """One fire-year's accepted fires, stripped to the ten properties.

    `Feature.select(SRC, DST)` keeps the geometry (retainGeometry defaults True) and DROPS every
    property not listed — which is the point: the source FCs carry all 20 predictors plus the
    three call columns, and this layer is not the object database.
    """
    fc = ee.FeatureCollection(f"{C.OBJECTS_RAW_COL}/objects_raw_{fire_year}").filter(fire_filter())
    return fc.map(lambda f: ee.Feature(f.set("fire_year", fire_year)).select(SRC, DST))


def merged(years=FIRE_YEARS):
    """All fire-years, merged and flattened into one FeatureCollection."""
    return ee.FeatureCollection([fires(fy) for fy in years]).flatten()


def properties(years, n_features=None):
    """The asset property block — where the two caveats above are written down.

    Set AFTER the export lands (`--set-props`), via `ee.data.updateAsset`, rather than with
    `.set()` on the collection: a property block is not worth risking a multi-hour table task on,
    and updateAsset is deterministic and free.
    """
    p = {
        "source": C.PRODUCT_SOURCE,
        "region": C.PRODUCT_REGION,
        "collection": 1,
        "unit": "one polygon per mapped fire (SNIC fire object)",
        "fire_years": f"{years[0]}-{years[-1]}",
        "fire_year_definition": "non-calendar: 1 May <fire_year> to 30 Apr <fire_year>+1",
        "fire_call": ("fire == 1 — the deployed call: the collected label where there is one, "
                      "else the probit-BART object model (docs/06 §5)"),
        "min_fire_ha": C.MIN_FIRE_HA,
        "calendar_year_definition": (
            "MODE of the object's per-pixel calendar years. The published RASTER products assign "
            "the calendar year per PIXEL, so a fire straddling 31 December is split between two "
            "years there and lands whole in one year here — the two layers answer different "
            "questions and will not cross-tabulate exactly (docs/07 §1)"),
        "date_encoding": "date_med / date_min / date_max: whole days since 1970-01-01",
        "area_encoding": "area_ha: pixel-count area, not a geodesic polygon area",
        "p_mean": "posterior mean fire probability (probit BART, docs/06)",
        "p_width": "width of the probability's credible interval (p_q95 - p_q05)",
        "seed_mean": "mean SNIC seed burn probability over the object",
        "series_note": ("fire-year 1998 is included and appears in NO published raster: the "
                        "calendar series starts at 1999, so FY1998's Nov-Dec 1998 tail "
                        "(~76 kha) is here only (docs/07 §2)"),
        "derived_from": C.OBJECTS_RAW_COL,
    }
    if n_features is not None:
        p["n_features"] = n_features
    return p


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------
def check(years):
    """Per-fire-year counts and the property schema, before committing a long task."""
    sizes, areas = [], []
    for fy in years:
        k = ee.FeatureCollection(f"{C.OBJECTS_RAW_COL}/objects_raw_{fy}").filter(fire_filter())
        sizes.append(k.size())
        areas.append(k.aggregate_sum("area_ha"))
    n, ha = ee.List([ee.List(sizes), ee.List(areas)]).getInfo()

    print(f"{'fire_year':>10} {'polygons':>10} {'area_ha':>14}")
    for i, fy in enumerate(years):
        print(f"{fy:>10} {n[i]:>10,} {ha[i]:>14,.0f}")
    print(f"{'TOTAL':>10} {sum(n):>10,} {sum(ha):>14,.0f}")

    got = sorted(fires(years[-1]).first().propertyNames().getInfo())
    want = sorted(DST + ["system:index"])
    print(f"\n[schema] {got}")
    if got != want:
        print(f"[schema] ⚠️ MISMATCH — expected {want}")
    else:
        print("[schema] exactly the ten properties (+ system:index)")

    print(f"\nOne feature of FY{years[-1]}:")
    for k_, v in sorted(fires(years[-1]).first().toDictionary().getInfo().items()):
        print(f"   {k_:16s} {v}")

    print(f"\nIf the merged export fails, the fallback loads as one FC:\n"
          f"  var fc = ee.FeatureCollection(\n"
          f"      ee.List.sequence({years[0]}, {years[-1]}).map(function (y) {{\n"
          f"        return ee.FeatureCollection(ee.String('{BY_YEAR_DIR}/{SUBPRODUCT}_')\n"
          f"                                   .cat(ee.Number(y).format('%d')));\n"
          f"      }})).flatten();")


def verify(asset_id):
    """Check a LANDED asset — size, schema, and a feature — not the graph that built it."""
    if not asset_exists(asset_id):
        print(f"[verify] {asset_id} does not exist yet")
        return
    fc = ee.FeatureCollection(asset_id)
    n, props, first = ee.List([fc.size(), fc.first().propertyNames(),
                               fc.first().toDictionary()]).getInfo()
    print(f"[verify] {asset_id}\n         {n:,} features")
    got = sorted(p for p in props if p != "system:index")
    print(f"         schema {'OK' if got == sorted(DST) else 'MISMATCH: ' + str(got)}")
    for k_, v in sorted(first.items()):
        print(f"         {k_:16s} {v}")
    stored = ee.data.getAsset(asset_id).get("properties") or {}
    print(f"         {len(stored)} asset properties set" if stored
          else "         no asset properties yet — run --set-props")


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
def export_one(fc, asset_id, description, launch):
    if asset_exists(asset_id):
        print(f"[skip] {asset_id} already exists")
        return
    if task_in_flight(description):
        print(f"[skip] {description} has a PENDING/RUNNING task")
        return
    if not launch:
        print(f"[dry] would export {asset_id}  (description {description})")
        return
    task = ee.batch.Export.table.toAsset(collection=fc, description=description, assetId=asset_id)
    task.start()
    print(f"[launched] {task.id}  ->  {asset_id}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--launch", action="store_true",
                    help="actually submit the export task(s) (default: build + report only)")
    ap.add_argument("--check", action="store_true",
                    help="per-fire-year counts + the property schema, without exporting")
    ap.add_argument("--verify", action="store_true",
                    help="inspect the LANDED asset (with --year, that fire-year's asset)")
    ap.add_argument("--year", type=int,
                    help="export ONE fire-year into the by_fire_year folder — the schema "
                         "validation run, and simultaneously the first asset of the fallback")
    ap.add_argument("--per-year", action="store_true",
                    help="the fallback: one asset per fire-year instead of the merged layer")
    ap.add_argument("--set-props", action="store_true",
                    help="write the asset property block onto the landed asset(s)")
    ap.add_argument("--project", default=C.GEE_PROJECT,
                    help="compute project (default %(default)s). Use `mapbiomas-argentina` with "
                         "the comahue credentials — the destination asset path does not change")
    ap.add_argument("--credentials",
                    help="path to a credentials file to authenticate with instead of the resident "
                         "~/.config/earthengine/credentials (e.g. …/credentials.comahue). Lets this "
                         "export run as the second account so it does not queue behind the first "
                         "account's tasks, without swapping any file")
    args = ap.parse_args()

    initialize(args.project, args.credentials)

    years = FIRE_YEARS
    if args.year is not None:
        if args.year not in FIRE_YEARS:
            ap.error(f"fire year {args.year} outside {FIRE_YEARS[0]}-{FIRE_YEARS[-1]}")

    if args.check:
        check(years)
        return

    if args.verify:
        verify(year_asset(args.year) if args.year is not None else merged_asset())
        return

    if args.set_props:
        targets = ([year_asset(args.year)] if args.year is not None
                   else [year_asset(fy) for fy in years] if args.per_year
                   else [merged_asset()])
        for asset_id in targets:
            if not asset_exists(asset_id):
                print(f"[skip] {asset_id} does not exist")
                continue
            yrs = [args.year] if args.year is not None else years
            n = ee.FeatureCollection(asset_id).size().getInfo()
            ee.data.updateAsset(asset_id, {"properties": properties(yrs, n)}, ["properties"])
            print(f"[props] {asset_id}  ({n:,} features)")
        return

    if args.year is not None:
        if args.launch:
            ensure_container(BY_YEAR_DIR, "FOLDER")
        export_one(fires(args.year), year_asset(args.year),
                   f"{TASK_PREFIX}{SUBPRODUCT}_{args.year}", args.launch)
    elif args.per_year:
        if args.launch:
            ensure_container(BY_YEAR_DIR, "FOLDER")
        for fy in years:
            export_one(fires(fy), year_asset(fy),
                       f"{TASK_PREFIX}{SUBPRODUCT}_{fy}", args.launch)
    else:
        export_one(merged(years), merged_asset(), f"{TASK_PREFIX}{SUBPRODUCT}", args.launch)

    if not args.launch:
        print("\nDry run only. Re-run with --launch to submit.")


if __name__ == "__main__":
    main()
