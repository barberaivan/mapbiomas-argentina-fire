#!/usr/bin/env python3
"""
collection-01/scripts/validate_scar_zips.py

GATE the 27 calendar-year scar packages BEFORE any of them is ingested by hand.

The ingest is manual (no GCS bucket is reachable), so a malformed package costs a round trip
through the GEE asset manager and is discovered late. This checks every zip the same way
`validate_upload_zips.py` gates the step-06 object packages:

  * the zip holds a complete Shapefile set (.shp/.shx/.dbf/.prj) and nothing stray
  * it opens, and the layer's feature count matches `scars_<Y>_summary.csv` from the build
  * the field set is EXACTLY scar_id / area_ha / n_px / year, with the right types --
    `scar_id` must be an INTEGER (`ee.Image().paint` cannot use a string) and there must be
    NO size class (that is applied server-side, docs/07 §8)
  * `scar_id` is unique and gapless 1..n within the year
  * `area_ha` totals match the summary to within rounding, and no scar is 0 ha
  * the CRS is geographic WGS84 -- a projected .prj would silently misalign the painted raster
  * geometries are valid and non-empty

And `--ingested` closes the other half of the loop, AFTER the manual upload: it compares what
actually landed in GEE against the local build. That is where a silent error hides -- a hand ingest
has no failing pipeline either, and a partially-uploaded Shapefile still produces a valid-looking
FeatureCollection. It checks the feature count and the `area_ha` total per year, and that `scar_id`
survived as a NUMBER (`ee.Image().paint` cannot use a string).

Note ingest tasks are `INGEST_TABLE` and run in a DIFFERENT queue from `EXPORT_IMAGE`, so they do
not contend with the month-of-burn exports -- and `ee.data.listOperations()` is PROJECT-SCOPED, so a
Code Editor upload made while the session was on `mapbiomas-argentina` will not appear under
`mapbiomas-fire-485203`. Pass `--project` to look in the right place.

Usage (from the repo ROOT):
  $PYTHON collection-01/scripts/validate_scar_zips.py                     # gate the zips
  $PYTHON collection-01/scripts/validate_scar_zips.py --years 1999,2000
  $PYTHON collection-01/scripts/validate_scar_zips.py --ingested          # verify the upload
"""

from __future__ import annotations

import argparse
import csv
import sys
import zipfile
from pathlib import Path

from osgeo import ogr, osr

ogr.UseExceptions()
osr.UseExceptions()

REPO_ROOT = Path(__file__).resolve().parents[2]
ZIP_DIR = REPO_ROOT / "collection-01/data/scars-upload-cache"
SCAR_DIR = REPO_ROOT / "collection-01/data/objects-scars"

EXPECT_FIELDS = {"scar_id": "int", "area_ha": "real", "n_px": "int", "year": "int"}
SHP_PARTS = {".shp", ".shx", ".dbf", ".prj"}
OGR_KIND = {ogr.OFTInteger: "int", ogr.OFTInteger64: "int", ogr.OFTReal: "real",
            ogr.OFTString: "str"}


def check_year(year):
    """Return (ok, [messages]) for one calendar year."""
    msgs = []
    zpath = ZIP_DIR / f"scars_{year}.zip"
    if not zpath.exists():
        return False, [f"MISSING {zpath.name}"]

    with zipfile.ZipFile(zpath) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
    exts = {Path(n).suffix.lower() for n in names}
    if not SHP_PARTS <= exts:
        msgs.append(f"incomplete Shapefile set: missing {sorted(SHP_PARTS - exts)}")
    stems = {Path(n).stem for n in names}
    if stems != {f"scars_{year}"}:
        msgs.append(f"unexpected member stems: {sorted(stems)}")

    ds = ogr.Open(f"/vsizip/{zpath}")
    if ds is None:
        return False, msgs + ["OGR could not open the zip"]
    lyr = ds.GetLayer(0)

    # --- fields -----------------------------------------------------------
    defn = lyr.GetLayerDefn()
    got = {}
    for i in range(defn.GetFieldCount()):
        f = defn.GetFieldDefn(i)
        got[f.GetName()] = OGR_KIND.get(f.GetType(), str(f.GetType()))
    if set(got) != set(EXPECT_FIELDS):
        msgs.append(f"field set is {sorted(got)}, expected {sorted(EXPECT_FIELDS)}")
    for name, kind in EXPECT_FIELDS.items():
        if name in got and got[name] != kind:
            msgs.append(f"field {name} is {got[name]}, expected {kind}"
                        + (" — paint() needs a number" if name == "scar_id" else ""))

    # --- CRS --------------------------------------------------------------
    srs = lyr.GetSpatialRef()
    if srs is None:
        msgs.append("no CRS on the layer (.prj missing or unreadable)")
    elif srs.IsProjected():
        msgs.append("CRS is PROJECTED; the scar grid is geographic WGS84 — this would misalign")

    # --- features ---------------------------------------------------------
    ids, total_ha, zero_area, bad_geom, empty_geom = [], 0.0, 0, 0, 0
    for feat in lyr:
        ids.append(feat.GetField("scar_id") if "scar_id" in got else None)
        a = feat.GetField("area_ha") if "area_ha" in got else 0
        total_ha += a or 0
        if not a:
            zero_area += 1
        g = feat.GetGeometryRef()
        if g is None or g.IsEmpty():
            empty_geom += 1
        elif not g.IsValid():
            bad_geom += 1
    n = len(ids)

    if zero_area:
        msgs.append(f"{zero_area} scar(s) with area_ha = 0")
    if empty_geom:
        msgs.append(f"{empty_geom} empty geometry/ies")
    if bad_geom:
        msgs.append(f"{bad_geom} invalid geometry/ies")
    if None not in ids:
        if len(set(ids)) != n:
            msgs.append(f"scar_id not unique ({n - len(set(ids))} duplicate(s))")
        if ids and (min(ids) != 1 or max(ids) != n):
            msgs.append(f"scar_id not gapless 1..{n} (min={min(ids)}, max={max(ids)})")

    # --- cross-check against the build summary ----------------------------
    spath = SCAR_DIR / f"scars_{year}_summary.csv"
    if not spath.exists():
        msgs.append(f"no build summary ({spath.name}) to cross-check against")
    else:
        with open(spath, newline="") as fh:
            row = next(csv.DictReader(fh))
        want_n, want_ha = int(row["n_scars"]), float(row["area_ha"])
        if want_n != n:
            msgs.append(f"feature count {n:,} != summary n_scars {want_n:,}")
        if want_ha and abs(total_ha - want_ha) / want_ha > 1e-4:
            msgs.append(f"area_ha total {total_ha:,.1f} != summary {want_ha:,.1f}")

    ok = not msgs
    head = (f"{'OK  ' if ok else 'FAIL'} {year}  {n:>7,} scars  {total_ha:>12,.0f} ha  "
            f"{zpath.stat().st_size / 1e6:>6.1f} MB")
    return ok, [head] + [f"       - {m}" for m in msgs]


def check_ingested(years, project):
    """Compare the INGESTED FeatureCollections against the local build.

    Only years already present are compared; the rest are reported as still-in-flight rather than
    as failures, because 27 hand uploads land over a long stretch.
    """
    import ee
    sys.path.insert(0, str(REPO_ROOT / "collection-01"))
    import utils.constants as C

    ee.Initialize(project=project)
    present = {a["id"].split("/")[-1] for a in
               ee.data.listAssets(C.ANNUAL_BURNED_VECTORS).get("assets", [])}
    print(f"ingested into {C.ANNUAL_BURNED_VECTORS}\n")
    print(f"{'year':>5} {'GEE feats':>11} {'local':>11} {'GEE ha':>13} {'local ha':>13}  verdict")

    bad, waiting, checked = [], [], 0
    for y in years:
        if f"scars_{y}" not in present:
            waiting.append(y)
            continue
        fc = ee.FeatureCollection(f"{C.ANNUAL_BURNED_VECTORS}/scars_{y}")
        n = fc.size().getInfo()
        ha = fc.aggregate_sum("area_ha").getInfo() or 0.0
        spath = SCAR_DIR / f"scars_{y}_summary.csv"
        if not spath.exists():
            print(f"{y:>5} {n:>11,} {'?':>11} {ha:>13,.0f} {'?':>13}  no local summary")
            continue
        row = next(csv.DictReader(open(spath, newline="")))
        ln, lha = int(row["n_scars"]), float(row["area_ha"])
        ok = (n == ln) and (lha == 0 or abs(ha - lha) / lha < 1e-6)
        checked += 1
        if not ok:
            bad.append(y)
        print(f"{y:>5} {n:>11,} {ln:>11,} {ha:>13,.0f} {lha:>13,.0f}  "
              f"{'MATCH' if ok else 'MISMATCH'}")

    # scar_id must have survived the DBF round trip as a number, or paint() cannot use it
    if present:
        one = sorted(present)[0]
        props = ee.Feature(ee.FeatureCollection(
            f"{C.ANNUAL_BURNED_VECTORS}/{one}").first()).getInfo()["properties"]
        kinds = {k: type(v).__name__ for k, v in props.items()}
        print(f"\nproperty types on {one}: {kinds}")
        if not isinstance(props.get("scar_id"), (int, float)):
            print("  ERROR scar_id is not numeric — ee.Image().paint() will reject it")
            bad.append(one)

    print(f"\n{checked}/{len(years)} verified against the local build")
    if waiting:
        print(f"still ingesting (not a failure): {waiting}")
    if bad:
        print(f"MISMATCHED — re-upload these: {sorted(set(bad))}")
        sys.exit(1)
    if not waiting:
        print("All 27 ingests verified. Run 07-scar_rasters.py --check next.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", help="comma-separated calendar years (default: 1999-2025)")
    ap.add_argument("--ingested", action="store_true",
                    help="verify the UPLOADED FeatureCollections against the local build "
                         "(feature count, area_ha total, scar_id type) instead of the zips")
    ap.add_argument("--project", default="mapbiomas-fire-485203",
                    help="GEE project to initialize under (default: %(default)s)")
    args = ap.parse_args()
    years = ([int(v) for v in args.years.split(",")] if args.years
             else list(range(1999, 2026)))

    if args.ingested:
        check_ingested(years, args.project)
        return

    failed = []
    for y in years:
        ok, lines = check_year(y)
        print("\n".join(lines))
        if not ok:
            failed.append(y)

    print(f"\n{len(years) - len(failed)}/{len(years)} package(s) passed")
    if failed:
        print(f"DO NOT UPLOAD — fix and rebuild: {failed}")
        sys.exit(1)
    print("All packages pass. Safe to ingest by hand into "
          ".../COLLECTION-1/FINAL_PRODUCTS/annual_burned_vectors/scars_<Y>")


if __name__ == "__main__":
    main()
