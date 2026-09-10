#!/usr/bin/env python3
"""
collection-01/workflow/11-burnable_area.py

BURNABLE AREA per calendar year x territory x veg_fire class — the DENOMINATOR of every
"burned proportion" number in the factsheet (docs/11 §5.1) and the input the network's
statistics scripts do not compute for us.

WHAT "BURNABLE" MEANS HERE, and why it is not the published land cover
----------------------------------------------------------------------
Burnable is defined by OUR mapping method, so it is read off `veg_fire`, which is derived
from `C.MAPBIOMAS_LULC` — **LULC col-2 v8, the model-side layer** — of the PREVIOUS year
(`utils/functions.veg_fire_image`).  That is the layer the SNIC candidate set was built
from, so it is the only denominator for which "burned / burnable" is internally coherent:
a pixel that is non-burnable there could never have been mapped as burned, whatever a newer
land cover says about it.  (Iván, 2026-09-10 — docs/11 §5.1.)

Do NOT repoint this at `C.PRODUCT_LULC` (col-3).  The published `*_coverage` subproducts use
col-3 on purpose, because they answer a different question — "which PUBLISHED land cover
burned in year Y" — and mixing the two would put a col-3 numerator over a col-2 denominator.

  veg_fire 1..23  -> burnable
  veg_fire 24     -> non-burnable (water, urban, other non-vegetated, ice/snow)
  veg_fire 25     -> non-observed — EXCLUDED, does NOT count toward the burnable area
                     (factsheet-notes.md: "La clase no observado se ignora, no suma a lo
                     quemable")

Every class is reported, 24 and 25 included, so the exclusion is done at analysis time and
the "how much of the country was unobservable that year" number stays visible.

HOW IT IS COMPUTED
------------------
One grouped `pixelArea()` reduction per year over the whole country:

    zone  = territory_id * 100 + veg_fire            (values 101..1325, ~325 groups)
    area  = pixelArea() summed by zone

pinned to `C.SNIC_CRS` / `C.SNIC_TRANSFORM` — the SAME 30 m lattice the burned-area products
sit on, so numerator and denominator are counted on identical pixels.  Never `scale=30` in
EPSG:4326: that is a different grid (docs/07 §3).

ONE EXPORT PER YEAR, not one for the series: 27 small tasks are resumable, run two-at-a-time
per account (docs/11 §4.2), and give partial results if the window closes.  Each lands as a
FeatureCollection with one feature per (year, territory, veg_fire).

Usage (from the repo ROOT)
--------------------------
  $PYTHON collection-01/workflow/11-burnable_area.py --year 2020                 # dry run
  $PYTHON collection-01/workflow/11-burnable_area.py --year 2020 --check         # tiny ROI
  $PYTHON collection-01/workflow/11-burnable_area.py --year 2020 --launch
  $PYTHON collection-01/workflow/11-burnable_area.py --all --launch              # 27 tasks — tmux!
  $PYTHON collection-01/workflow/11-burnable_area.py --all --read --csv out.csv  # collect

  # timing benchmark, nothing production touched (docs/11 §4.4)
  $PYTHON collection-01/workflow/11-burnable_area.py --year 2020 --launch \
      --out-collection projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/TESTS/burnable_benchmark \
      --suffix _benchmark

  # second account — the task queue is PER USER
  $PYTHON collection-01/workflow/11-burnable_area.py --year 2012 --launch \
      --credentials ~/.config/earthengine/credentials.comahue --project mapbiomas-argentina
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils.constants as C          # noqa: E402
import utils.functions as F          # noqa: E402

TASK_PREFIX = "arg11_burnable_"      # namespaced: the compute project is shared (CLAUDE.md)
DEFAULT_COL = f"{C.FINAL_PRODUCTS}/../STATISTICS/burnable_area".replace("/../", "/")

# ---------------------------------------------------------------------------
# territories
# ---------------------------------------------------------------------------
_ANC = "projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG"

# name -> (asset, integer-id property, human-name property)
# `id_prop` must be a small positive integer and never 0: zone = id*100 + veg_fire, and the
# paint of an unpainted pixel is indistinguishable from a painted 0.
TERRITORIES = {
    # Burkart et al. 1999, the 13-class version — the factsheet default (factsheet-notes.md).
    "ecoregions13": (f"{_ANC}/ARG-Political_Level_2-13Ecorregiones_3857", "GEOCODE", "LEVEL_2"),
    # The 5 MapBiomas Argentina regions — the cut our own veg_fire remap is regionalised by.
    "mbregions":    (f"{_ANC}/ARG-Regiones-MapBiomas-buffer2km", "Zona", "Region"),
}


def territory_image(name):
    """Integer territory-id raster, masked outside the territories."""
    asset, id_prop, _ = TERRITORIES[name]
    return ee.Image().paint(ee.FeatureCollection(asset), id_prop).rename("territory")


def territory_names(name):
    """{id: human name} — resolved once, client-side, so the output CSV is readable."""
    asset, id_prop, name_prop = TERRITORIES[name]
    fc = ee.FeatureCollection(asset)
    ids = fc.aggregate_array(id_prop).getInfo()
    nms = fc.aggregate_array(name_prop).getInfo()
    return {int(i): str(n) for i, n in zip(ids, nms)}


# ---------------------------------------------------------------------------
# auth / asset plumbing
# ---------------------------------------------------------------------------
def initialize(project, credentials_path=None):
    """`ee.Initialize`, optionally as another account. Copied from 07-burned_area_polygons.py."""
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
    """Match the NAMESPACED description only — listOperations sees every user's tasks."""
    for op in ee.data.listOperations():
        meta = op.get("metadata", {})
        if (meta.get("description") == description
                and meta.get("state") in ("PENDING", "RUNNING")):
            return True
    return False


# ---------------------------------------------------------------------------
# the computation
# ---------------------------------------------------------------------------
def zone_image(year, territory):
    """zone = territory_id * 100 + veg_fire, for the PREVIOUS year's land cover."""
    veg = F.veg_fire_image(year)                       # already prev-year, capped at MB_LIMIT_YEAR
    terr = territory_image(territory)
    return terr.multiply(100).add(veg).rename("zone").toInt32()


def decimated_transform(k):
    """Our own 30 m lattice, kept, but sampled every k-th pixel.

    `--decimate` exists because the denominator is the expensive half of the factsheet: it has no
    burned-pixel mask to shrink it, so it sweeps the whole country 27 times (docs/11 §5.1).

    DECIMATING THE LATTICE, NOT PASSING `scale=90`. `scale` in EPSG:4326 puts the reduction on a
    DIFFERENT grid with a different origin (docs/07 §3); multiplying the pixel step by an integer
    keeps the same origin and every sampled pixel is a real pixel of our own grid — the same trick
    docs/10 §4 uses to build the validation strata (30 m decimated x16).

    It is a SYSTEMATIC SUBSAMPLE, so it estimates class area rather than measuring it: unbiased in
    expectation, but noisier for fragmented classes (agriculture especially). k=1 is the truth;
    validate any k>1 against it before using it for a published number.
    """
    tx, _, x0, _, ty, y0 = C.SNIC_TRANSFORM
    return [tx * k, 0, x0, 0, ty * k, y0]


def grouped_area(year, territory, geometry, decimate=1):
    """{zone: area_m2} as a server-side ee.Dictionary-backed list of groups.

    `pixelArea()` is evaluated on the SAMPLED grid, so each retained pixel already carries the
    area of its k x k block: the sum estimates true area directly and needs no k**2 correction.
    """
    img = ee.Image.pixelArea().addBands(zone_image(year, territory))
    return ee.Image(img).reduceRegion(
        reducer=ee.Reducer.sum().group(groupField=1, groupName="zone"),
        geometry=geometry,
        crs=C.SNIC_CRS,
        crsTransform=(C.SNIC_TRANSFORM if decimate == 1 else decimated_transform(decimate)),
        maxPixels=int(1e13),
        bestEffort=False,
        tileScale=4,          # the group reduction is the memory risk, not the pixel sweep
    ).get("groups")


def year_table(year, territory, geometry, decimate=1):
    """One feature per (year, territory_id, veg_fire) with area_ha. No client-side call."""
    groups = ee.List(grouped_area(year, territory, geometry, decimate))

    def to_feature(g):
        g = ee.Dictionary(g)
        zone = ee.Number(g.get("zone")).toInt()
        return ee.Feature(None, {
            "year": year,
            "territory_id": zone.divide(100).floor().toInt(),
            "veg_fire": zone.mod(100).toInt(),
            "area_ha": ee.Number(g.get("sum")).divide(1e4),
        })

    return ee.FeatureCollection(groups.map(to_feature))


# ---------------------------------------------------------------------------
# run modes
# ---------------------------------------------------------------------------
def check(year, territory, roi, decimate=1):
    """Interactive, SMALL roi only — a whole-country reduceRegion is a batch job, not a call."""
    names = territory_names(territory)
    groups = ee.List(grouped_area(year, territory, roi, decimate)).getInfo()
    lulc_year = min(year - 1, C.MB_LIMIT_YEAR)
    print(f"[check] year={year}  lulc={lulc_year}  territory={territory}  "
          f"decimate={decimate} (~{30 * decimate} m)  groups={len(groups)}")
    tot_burnable = tot_nonburn = tot_nonobs = 0.0
    for g in sorted(groups, key=lambda d: d["zone"]):
        tid, veg = divmod(int(g["zone"]), 100)
        ha = g["sum"] / 1e4
        if veg <= 23:
            tot_burnable += ha
        elif veg == 24:
            tot_nonburn += ha
        else:
            tot_nonobs += ha
        print(f"   {names.get(tid, tid):<28s} veg_fire {veg:>2d} "
              f"{C.VEG_FIRE_CLASSES.get(veg, {}).get('name', '?'):<22s} {ha:12,.1f} ha")
    print(f"   {'':<28s} {'BURNABLE (1-23)':<26s} {tot_burnable:12,.1f} ha")
    print(f"   {'':<28s} {'non-burnable (24)':<26s} {tot_nonburn:12,.1f} ha")
    print(f"   {'':<28s} {'non-observed (25, excl.)':<26s} {tot_nonobs:12,.1f} ha")


def export_year(year, territory, geometry, launch, out_col, suffix="", decimate=1):
    asset_id = f"{out_col}/burnable_{territory}_{year}{suffix}"
    description = f"{TASK_PREFIX}{territory}_{year}{suffix}"

    if asset_exists(asset_id):
        print(f"[skip] {asset_id} already exists")
        return
    if task_in_flight(description):
        print(f"[skip] {description} has a PENDING/RUNNING task")
        return

    fc = year_table(year, territory, geometry, decimate).set({
        "year": year,
        "lulc_year": min(year - 1, C.MB_LIMIT_YEAR),
        "lulc_asset": C.MAPBIOMAS_LULC,
        "territory": territory,
        "territory_asset": TERRITORIES[territory][0],
        "grid": "C.SNIC_CRS + C.SNIC_TRANSFORM (the burned-area lattice)",
        "decimate": decimate,
        "sampled_m": 30 * decimate,
        "burnable_classes": "veg_fire 1-23; 24 non-burnable; 25 non-observed (exclude)",
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
        asset_id = f"{out_col}/burnable_{territory}_{y}{suffix}"
        if not asset_exists(asset_id):
            print(f"[{y}] not finished ({asset_id})")
            continue
        feats = ee.FeatureCollection(asset_id).getInfo()["features"]
        for f in feats:
            p = f["properties"]
            p["territory_name"] = names.get(int(p["territory_id"]), "")
            p["veg_fire_name"] = C.VEG_FIRE_CLASSES.get(int(p["veg_fire"]), {}).get("name", "")
            rows.append(p)
        burnable = sum(p["area_ha"] for p in
                       (f["properties"] for f in feats) if p["veg_fire"] <= 23)
        print(f"[{y}] {len(feats):>4d} rows | burnable {burnable:>14,.0f} ha")
    if csv_path and rows:
        cols = ["year", "territory_id", "territory_name", "veg_fire", "veg_fire_name", "area_ha"]
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
    ap.add_argument("--territory", default="ecoregions13", choices=sorted(TERRITORIES),
                    help="territorial cut (default: %(default)s)")
    ap.add_argument("--launch", action="store_true", help="submit the export task(s)")
    ap.add_argument("--check", action="store_true",
                    help="interactive audit over a SMALL --roi instead of exporting")
    ap.add_argument("--roi", default="test",
                    help="--check extent: 'test' or 'xmin,ymin,xmax,ymax'. Never the country.")
    ap.add_argument("--read", action="store_true", help="read finished assets back")
    ap.add_argument("--csv", default=None, help="--read: write the rows to this CSV")
    ap.add_argument("--out-collection", default=DEFAULT_COL,
                    help="destination FeatureCollection folder (default: %(default)s)")
    ap.add_argument("--suffix", default="", help="appended to asset name AND task description")
    ap.add_argument("--decimate", type=int, default=1, metavar="K",
                    help="sample every K-th pixel of our 30 m lattice (K=3 ~90 m, K=4 ~120 m). "
                         "Cuts the sweep by K**2. Systematic subsample: unbiased in expectation, "
                         "noisier for fragmented classes — validate against K=1 first.")
    ap.add_argument("--project", default=C.GEE_PROJECT)
    ap.add_argument("--credentials", default=None, metavar="FILE",
                    help="submit as another account — the GEE task queue is PER USER")
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
            check(y, args.territory, roi, args.decimate)
        return

    if args.read:
        read_years(years, args.territory, args.out_collection, args.suffix, args.csv)
        return

    if args.launch:
        parent = args.out_collection.rsplit("/", 1)[0]
        ensure_container(parent, "FOLDER")
        ensure_container(args.out_collection, "FOLDER")

    geometry = ee.FeatureCollection(C.ARG_BUFFER_FC).geometry()
    for y in years:
        export_year(y, args.territory, geometry, args.launch,
                    args.out_collection, args.suffix, args.decimate)

    if not args.launch:
        print("\nDry run only. Re-run with --launch to submit the task(s).")


if __name__ == "__main__":
    main()
