#!/usr/bin/env python3
"""
collection-01/workflow/11-burned_area_stats.py

BURNED AREA per calendar year x month x territory — the NUMERATOR that pairs with
`11-burnable_area.py`'s denominator (docs/11 §5.1).  Together they are factsheet analyses
1 (mean annual burned proportion), 2 (the time series and its trend) and the "% burned per
month" half of 3 (the pirogram).

READS THE MONTH-OF-BURN COLLECTION (07a), NOT `annual_burned`/`monthly_burned`
--------------------------------------------------------------------------------
`C.MONTH_OF_BURN_COL` is the pivot every raster subproduct is derived from (docs/07 §1), and
it carries the month in the pixel VALUE (1-12, masked elsewhere).  So one grouped reduction
over it yields the annual total AND the monthly breakdown at once, where reading
`monthly_burned` would mean twelve band reductions and reading `annual_burned` would lose the
month.  It also means this script does not care which of the nine subproducts have been
re-exported — it reads the thing they all come from.

  zone = territory_id * 100 + month        (values 101..1312, ~156 groups)
  area = pixelArea() summed by zone

Pinned to `C.SNIC_CRS` / `C.SNIC_TRANSFORM` — the SAME lattice `11-burnable_area.py` uses, so
the ratio is computed on identical pixels.  Never `scale=30` in EPSG:4326 (docs/07 §3).

CALENDAR YEAR AND MONTH ARE PER PIXEL, and that is a real difference from the object-based
tables in `scripts/factsheet_object_stats.R`: a fire straddling 31 December contributes to two
calendar years here and to one fire-year there.  Right for area, wrong for counting events —
which is exactly why the factsheet's counts come from the objects and its areas come from here
(docs/11 §5.2).  Do not reconcile the two; label them.

THE AGRICULTURE FILTER IS NOT APPLIED HERE.  It lives upstream, in 07a: this reads whatever
object set was painted.  So a filtered number requires the month-of-burn collection to have
been re-exported with `--agri-max` (docs/11 §3) — pass `--collection` to point at a test
collection meanwhile.

Usage (from the repo ROOT)
--------------------------
  $PYTHON collection-01/workflow/11-burned_area_stats.py --year 2020                 # dry run
  $PYTHON collection-01/workflow/11-burned_area_stats.py --year 2020 --check         # tiny ROI
  $PYTHON collection-01/workflow/11-burned_area_stats.py --all --launch              # 27 tasks
  $PYTHON collection-01/workflow/11-burned_area_stats.py --all --read --csv out.csv  # collect
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils.constants as C                                    # noqa: E402

# `11-burnable_area.py` cannot be imported by name — it starts with a digit and contains a
# hyphen — so load it by path. Reusing it is the point: the two scripts MUST agree about what
# a territory is and which grid they count on, or the ratio is between two different maps.
import importlib.util as _ilu                                  # noqa: E402

_spec = _ilu.spec_from_file_location(
    "burnable_area", Path(__file__).resolve().parent / "11-burnable_area.py")
_burnable = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_burnable)

TERRITORIES = _burnable.TERRITORIES
territory_image = _burnable.territory_image
territory_names = _burnable.territory_names
initialize = _burnable.initialize
asset_exists = _burnable.asset_exists
ensure_container = _burnable.ensure_container
decimated_transform = _burnable.decimated_transform

TASK_PREFIX = "arg11_burned_"
DEFAULT_COL = f"{C._FIRE_ROOT}/COLLECTION-1/STATISTICS/burned_area"


def task_in_flight(description):
    for op in ee.data.listOperations():
        meta = op.get("metadata", {})
        if (meta.get("description") == description
                and meta.get("state") in ("PENDING", "RUNNING")):
            return True
    return False


def month_image(cal_year, collection):
    """The month-of-burn image for one calendar year: uint8 1-12, masked elsewhere."""
    ic = ee.ImageCollection(collection).filter(ee.Filter.eq("year", cal_year))
    return ee.Image(ic.first()).select(C.MONTH_OF_BURN_BAND)


def zone_image(cal_year, territory, collection):
    """zone = territory_id * 100 + month, masked to the burned pixels."""
    month = month_image(cal_year, collection)
    terr = territory_image(territory)
    return terr.multiply(100).add(month).rename("zone").toInt32()


def grouped_area(cal_year, territory, geometry, collection, decimate=1):
    img = ee.Image.pixelArea().addBands(zone_image(cal_year, territory, collection))
    return ee.Image(img).reduceRegion(
        reducer=ee.Reducer.sum().group(groupField=1, groupName="zone"),
        geometry=geometry,
        crs=C.SNIC_CRS,
        crsTransform=(C.SNIC_TRANSFORM if decimate == 1 else decimated_transform(decimate)),
        maxPixels=int(1e13),
        bestEffort=False,
        tileScale=4,
    ).get("groups")


def year_table(cal_year, territory, geometry, collection, decimate=1):
    groups = ee.List(grouped_area(cal_year, territory, geometry, collection, decimate))

    def to_feature(g):
        g = ee.Dictionary(g)
        zone = ee.Number(g.get("zone")).toInt()
        return ee.Feature(None, {
            "year": cal_year,
            "territory_id": zone.divide(100).floor().toInt(),
            "month": zone.mod(100).toInt(),
            "area_ha": ee.Number(g.get("sum")).divide(1e4),
        })

    return ee.FeatureCollection(groups.map(to_feature))


def check(cal_year, territory, roi, collection, decimate=1):
    names = territory_names(territory)
    groups = ee.List(grouped_area(cal_year, territory, roi, collection, decimate)).getInfo()
    print(f"[check] year={cal_year}  territory={territory}  decimate={decimate}  "
          f"groups={len(groups)}")
    tot = 0.0
    for g in sorted(groups, key=lambda d: d["zone"]):
        tid, month = divmod(int(g["zone"]), 100)
        ha = g["sum"] / 1e4
        tot += ha
        print(f"   {names.get(tid, tid):<28s} month {month:>2d} {ha:12,.1f} ha")
    print(f"   {'':<28s} {'TOTAL BURNED':<9s} {tot:12,.1f} ha")


def export_year(cal_year, territory, geometry, launch, out_col, collection,
                suffix="", decimate=1):
    asset_id = f"{out_col}/burned_{territory}_{cal_year}{suffix}"
    description = f"{TASK_PREFIX}{territory}_{cal_year}{suffix}"

    if asset_exists(asset_id):
        print(f"[skip] {asset_id} already exists")
        return
    if task_in_flight(description):
        print(f"[skip] {description} has a PENDING/RUNNING task")
        return

    fc = year_table(cal_year, territory, geometry, collection, decimate).set({
        "year": cal_year,
        "territory": territory,
        "territory_asset": TERRITORIES[territory][0],
        "month_of_burn_collection": collection,
        "grid": "C.SNIC_CRS + C.SNIC_TRANSFORM",
        "decimate": decimate,
        "partition": "calendar year and month assigned PER PIXEL from abs_date (docs/07 §1)",
        "source": C.PRODUCT_SOURCE,
    })
    if not launch:
        print(f"[dry] would export {asset_id}   (task {description})")
        return
    task = ee.batch.Export.table.toAsset(
        collection=fc, description=description, assetId=asset_id)
    task.start()
    print(f"[launched] {task.id}  ->  {asset_id}")


def read_years(years, territory, out_col, suffix, csv_path=None):
    names = territory_names(territory)
    rows = []
    for y in years:
        asset_id = f"{out_col}/burned_{territory}_{y}{suffix}"
        if not asset_exists(asset_id):
            print(f"[{y}] not finished ({asset_id})")
            continue
        feats = ee.FeatureCollection(asset_id).getInfo()["features"]
        for f in feats:
            p = f["properties"]
            p["territory_name"] = names.get(int(p["territory_id"]), "")
            rows.append(p)
        tot = sum(f["properties"]["area_ha"] for f in feats)
        print(f"[{y}] {len(feats):>4d} rows | burned {tot:>12,.0f} ha")
    if csv_path and rows:
        cols = ["year", "month", "territory_id", "territory_name", "area_ha"]
        with open(csv_path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"[csv] {len(rows)} rows -> {csv_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--year", type=int, help="single CALENDAR year")
    grp.add_argument("--all", action="store_true",
                     help=f"every calendar year {C.CALENDAR_YEARS[0]}..{C.CALENDAR_YEARS[-1]}")
    ap.add_argument("--territory", default="ecoregions13", choices=sorted(TERRITORIES))
    ap.add_argument("--collection", default=C.MONTH_OF_BURN_COL,
                    help="month-of-burn ImageCollection to reduce (default: the published "
                         "one). Point at a TESTS collection to score a filtered re-export "
                         "before it replaces production.")
    ap.add_argument("--launch", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--roi", default="test")
    ap.add_argument("--read", action="store_true")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--out-collection", default=DEFAULT_COL)
    ap.add_argument("--suffix", default="")
    ap.add_argument("--decimate", type=int, default=1, metavar="K",
                    help="sample every K-th pixel of our 30 m lattice. Use with more care "
                         "than on the denominator: burned scars are smaller and more "
                         "fragmented than land-cover blocks, so the sampling error is larger.")
    ap.add_argument("--project", default=C.GEE_PROJECT)
    ap.add_argument("--credentials", default=None, metavar="FILE")
    args = ap.parse_args()

    initialize(args.project, args.credentials)

    years = C.CALENDAR_YEARS if args.all else [args.year]
    bad = [y for y in years if y not in C.CALENDAR_YEARS]
    if bad:
        ap.error(f"calendar year(s) {bad} outside {C.CALENDAR_YEARS[0]}-{C.CALENDAR_YEARS[-1]}")

    if args.check:
        roi = (ee.Geometry.Polygon(C.TEST_ROI_COORDS, None, False) if args.roi == "test"
               else ee.Geometry.Rectangle([float(v) for v in args.roi.split(",")], None, False))
        for y in years:
            check(y, args.territory, roi, args.collection, args.decimate)
        return

    if args.read:
        read_years(years, args.territory, args.out_collection, args.suffix, args.csv)
        return

    if args.launch:
        ensure_container(args.out_collection.rsplit("/", 1)[0], "FOLDER")
        ensure_container(args.out_collection, "FOLDER")

    geometry = ee.FeatureCollection(C.ARG_BUFFER_FC).geometry()
    for y in years:
        export_year(y, args.territory, geometry, args.launch, args.out_collection,
                    args.collection, args.suffix, args.decimate)

    if not args.launch:
        print("\nDry run only. Re-run with --launch to submit the task(s).")


if __name__ == "__main__":
    main()
