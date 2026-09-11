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

⚠️ NEVER REDUCE THE EXPORTED ASSET AT A COARSER SCALE.  `--decimate` is what makes the
DENOMINATOR affordable (docs/11 §5.1), and the symmetry is tempting — but it is wrong here and
wrong silently.  Measured over a Chaco box, calendar 2020:

    reading the exported asset      k=1  22,228.3 ha   k=3  25,353.5 ha (+14.1 %)   k=4  +36.2 %
    painted on the fly (--from-objects)  22,228.3 ha        22,185.2 ha (-0.19 %)        -0.37 %

The asset is stored with `pyramidingPolicy={burned_monthly: "mode"}` (07a), and mode IGNORES
masked pixels — so at a coarse pyramid level a block containing one burned pixel comes back
burned.  The sparse burn mask DILATES.  Land cover does not suffer this because it is
space-filling: every pixel has a class, so mode is a real majority.

  **The rule: decimation is safe on a SPACE-FILLING layer and unsafe on a SPARSE MASKED one.**
  Happily that falls the right way — the expensive half (burnable, space-filling) can be
  decimated, and the half that cannot (burned, masked) is the cheap one, because its mask
  already restricts the sweep.

The same caution applies to ANY coarse read of our published burned-area rasters — a quick
whole-country `reduceRegion` at 500 m for a sanity check will over-report, and so will anything
else that lands on a pyramid level.  `--decimate > 1` is therefore REFUSED unless
`--from-objects` is given.

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

def _load(modname, filename):
    spec = _ilu.spec_from_file_location(
        modname, Path(__file__).resolve().parent / filename)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_burnable = _load("burnable_area", "11-burnable_area.py")
# 07a's own builder, so `--from-objects` paints EXACTLY what the published raster would
# contain rather than a re-implementation of it (see month_image()).
_mob = _load("month_of_burn", "07-month_of_burn.py")

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


def month_image(cal_year, collection, from_objects=False, agri_max=None):
    """The month-of-burn image for one calendar year: uint8 1-12, masked elsewhere.

    TWO SOURCES, and the choice decides what this step depends on.

    `collection` (default) reads the EXPORTED 07a asset — the published product, so the
    statistic is a statistic OF the published map.

    `from_objects` builds the same image on the fly with 07a's own `month_of_burn()`, from the
    object FCs and the SNIC assets, applying `agri_max` itself. This exists because 07a is the
    expensive step and the whole 27-year re-export sits on the critical path of everything
    (docs/11 §3): with `--from-objects` the factsheet's numbers can be produced from a FILTERED
    map in ONE pass, while the products are re-exported on their own schedule, instead of
    waiting for them.

    It is the same function 07a exports, not a copy, so the two cannot drift. What differs is
    only that nothing is written: paint and reduce happen in one task. The trade is that every
    year repaints (no reusable intermediate), so prefer reading the asset once it exists.

    A number produced this way is of a map that is not yet published — say so wherever it is
    used, per docs/11 §8.
    """
    if from_objects:
        return _mob.month_of_burn(cal_year, agri_max).select(C.MONTH_OF_BURN_BAND)
    ic = ee.ImageCollection(collection).filter(ee.Filter.eq("year", cal_year))
    return ee.Image(ic.first()).select(C.MONTH_OF_BURN_BAND)


def zone_image(cal_year, territory, collection, from_objects=False, agri_max=None):
    """zone = territory_id * 100 + month, masked to the burned pixels."""
    month = month_image(cal_year, collection, from_objects, agri_max)
    terr = territory_image(territory)
    return terr.multiply(100).add(month).rename("zone").toInt32()


def grouped_area(cal_year, territory, geometry, collection, decimate=1,
                 from_objects=False, agri_max=None):
    img = ee.Image.pixelArea().addBands(
        zone_image(cal_year, territory, collection, from_objects, agri_max))
    return ee.Image(img).reduceRegion(
        reducer=ee.Reducer.sum().group(groupField=1, groupName="zone"),
        geometry=geometry,
        crs=C.SNIC_CRS,
        crsTransform=(C.SNIC_TRANSFORM if decimate == 1 else decimated_transform(decimate)),
        maxPixels=int(1e13),
        bestEffort=False,
        tileScale=4,
    ).get("groups")


def year_table(cal_year, territory, geometry, collection, decimate=1,
               from_objects=False, agri_max=None):
    groups = ee.List(grouped_area(cal_year, territory, geometry, collection, decimate,
                                  from_objects, agri_max))

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


def check(cal_year, territory, roi, collection, decimate=1,
          from_objects=False, agri_max=None):
    names = territory_names(territory)
    groups = ee.List(grouped_area(cal_year, territory, roi, collection, decimate,
                                  from_objects, agri_max)).getInfo()
    src = f"objects (agri_max={agri_max})" if from_objects else "published 07a asset"
    print(f"[check] year={cal_year}  territory={territory}  decimate={decimate}  "
          f"source={src}  groups={len(groups)}")
    tot = 0.0
    for g in sorted(groups, key=lambda d: d["zone"]):
        tid, month = divmod(int(g["zone"]), 100)
        ha = g["sum"] / 1e4
        tot += ha
        print(f"   {names.get(tid, tid):<28s} month {month:>2d} {ha:12,.1f} ha")
    print(f"   {'':<28s} {'TOTAL BURNED':<9s} {tot:12,.1f} ha")


def export_year(cal_year, territory, geometry, launch, out_col, collection,
                suffix="", decimate=1, from_objects=False, agri_max=None):
    asset_id = f"{out_col}/burned_{territory}_{cal_year}{suffix}"
    description = f"{TASK_PREFIX}{territory}_{cal_year}{suffix}"

    if asset_exists(asset_id):
        print(f"[skip] {asset_id} already exists")
        return
    if task_in_flight(description):
        print(f"[skip] {description} has a PENDING/RUNNING task")
        return

    fc = year_table(cal_year, territory, geometry, collection, decimate,
                    from_objects, agri_max).set({
        "year": cal_year,
        "territory": territory,
        "territory_asset": TERRITORIES[territory][0],
        "month_of_burn_collection": ("(none — painted from objects on the fly)"
                                     if from_objects else collection),
        "agriculture_filter": ("none" if agri_max is None
                               else f"object dropped when frac_agri >= {agri_max}"),
        "published_map": int(not from_objects),
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
    ap.add_argument("--from-objects", action="store_true",
                    help="paint the month image from the OBJECTS on the fly (07a's own "
                         "month_of_burn) instead of reading the exported asset, so the "
                         "factsheet's numbers do not wait for the 27-year 07a re-export "
                         "(docs/11 §3). Pair with --agri-max. A number produced this way is "
                         "of a map that is NOT yet published — label it as such.")
    ap.add_argument("--agri-max", type=float, default=None, metavar="T",
                    help="with --from-objects: drop objects with frac_agri >= T (docs/11 §2). "
                         "Ignored when reading an exported asset, whose filter is already baked "
                         "in — use --collection to pick which one.")
    ap.add_argument("--decimate", type=int, default=1, metavar="K",
                    help="sample every K-th pixel of our 30 m lattice. ONLY VALID WITH "
                         "--from-objects: decimating a read of the EXPORTED asset inflates "
                         "burned area by 14-36 %% (see the module docstring).")
    ap.add_argument("--project", default=C.GEE_PROJECT)
    ap.add_argument("--credentials", default=None, metavar="FILE")
    args = ap.parse_args()
    # See the module docstring. Measured, not suspected: reading the exported asset at k=3
    # over a Chaco box in 2020 gives 25,353 ha against the true 22,228 -- +14.1 %, and +36.2 %
    # at k=4. The same reduction computed on the fly is -0.19 % and -0.37 %. A silent 14 %
    # inflation of the headline burned-area number is not something to leave behind a flag.
    if args.decimate > 1 and not args.from_objects:
        ap.error("--decimate > 1 reads the exported asset's OVERVIEW PYRAMID, which was built "
                 "with pyramidingPolicy 'mode'. Mode ignores masked pixels, so a coarse block "
                 "holding a single burned pixel comes back burned: the sparse burn mask "
                 "DILATES and burned area is inflated 14-36 %. Either drop --decimate, or add "
                 "--from-objects (painted on the fly, no pyramid, error < 0.4 %).")

    if args.agri_max is not None and not args.from_objects:
        ap.error("--agri-max only applies with --from-objects; an exported asset already "
                 "carries whatever filter it was painted with (see its `agriculture_filter` "
                 "property). Use --collection to choose which asset to read.")

    initialize(args.project, args.credentials)

    years = C.CALENDAR_YEARS if args.all else [args.year]
    bad = [y for y in years if y not in C.CALENDAR_YEARS]
    if bad:
        ap.error(f"calendar year(s) {bad} outside {C.CALENDAR_YEARS[0]}-{C.CALENDAR_YEARS[-1]}")

    if args.check:
        roi = (ee.Geometry.Polygon(C.TEST_ROI_COORDS, None, False) if args.roi == "test"
               else ee.Geometry.Rectangle([float(v) for v in args.roi.split(",")], None, False))
        for y in years:
            check(y, args.territory, roi, args.collection, args.decimate,
                  args.from_objects, args.agri_max)
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
                    args.collection, args.suffix, args.decimate,
                    args.from_objects, args.agri_max)

    if not args.launch:
        print("\nDry run only. Re-run with --launch to submit the task(s).")


if __name__ == "__main__":
    main()
