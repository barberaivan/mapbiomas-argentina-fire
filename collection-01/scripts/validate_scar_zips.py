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

Usage (from the repo ROOT):
  $PYTHON collection-01/scripts/validate_scar_zips.py
  $PYTHON collection-01/scripts/validate_scar_zips.py --years 1999,2000
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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", help="comma-separated calendar years (default: 1999-2025)")
    args = ap.parse_args()
    years = ([int(v) for v in args.years.split(",")] if args.years
             else list(range(1999, 2026)))

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
