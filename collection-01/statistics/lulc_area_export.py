#!/usr/bin/env python
"""
collection-01/statistics/lulc_area_export.py — the PER-CLASS DENOMINATOR (statistics/docs/statistics.md §5.4)

The second and last thing we compute in Earth Engine.  `burnable_export.py` gives the
denominator of "% del área quemable que se quemó"; this one gives the denominator of
**"% del bosque que se quemó"** — the area of every col-3 land-cover class, per ecorregión,
per year.

WHY IT IS NOT THE TOOLKIT'S JOB.  Every dataset in the network's app is a FIRE product:
its reductions are masked to burned pixels, so they can tell you how much forest burned
and never how much forest there was.  A space-filling per-class area is a different
reduction, and it is the one statistics/docs/statistics.md §3.3 costed as "§3 plus a digit".  Same route as the
burnable layer, same programming strategy, our own small export.

WHAT IT COMPUTES
    For each year 1998-2024, one grouped sum of pixelArea over

        code = ecoregion13 * 100 + col3_class      # max 13*100+77 = 1377, fits uint16

    i.e. the full cross-tab area x ecorregión x class x year, space-filling — every pixel
    of the country in exactly one row, burned or not.

WHICH YEARS, AND WHY THOSE.  1998-2024, the PREVIOUS-year range of calendar years
1999-2025.  The numerator (`annual_burned_coverage`) crosses fire in year Y with
`classification_<Y-1>` (statistics/docs/statistics.md §2.2), so the class label on a burned hectare refers to
Y-1 and its denominator must be the class area in Y-1.  Pairing Y with Y with be wrong by
one year in a way no gate would catch.

PROGRAMMING STRATEGY — copied from the network's app (statistics/docs/statistics.md §2.1):
    * the whole crossing packed into ONE integer band, one group field, one sweep;
    * territory is `ee.Image().paint(fc, 'GEOCODE')` — never an intersected vector;
    * the reduction geometry is a `bounds()` RECTANGLE;
    * no `tileScale`;
    * ALL 27 YEARS IN ONE TASK — 27 reductions flattened into a single `Export.table`,
      one queue slot, one CSV.  `--split` falls back to one task per year.
  The one divergence: `crs` + `crsTransform` instead of `scale: 30` (statistics/docs/statistics.md §2.3).

MASKING RULE (the trap, same as burnable_export): `add()` propagates masks, so exactly one
layer may drive the mask — the ecoregions, which tile the country.  The LULC band is
`unmask(0)`ed first, so a pixel the collection does not map becomes a VISIBLE
"No observado" row instead of vanishing from the denominator and inflating every `%`.

USAGE (from the repo ROOT), in the order you actually run them
    --test-rect   the same Córdoba rectangle burnable_export uses.  Does the reported area
                  add up to the rectangle, and do the classes decode?  Seconds.
    --export      the national run as ONE batch task -> Drive folder C.STATS_DRIVE_FOLDER.
    --export --split   27 tasks, one per year.  Use if the single task is too slow.
    --status      state of the task(s).
    --fetch       download from Drive into data/statistics/, decode, and gate.
    --check       re-run the gate on the already-downloaded raw CSV (no network).
Add `--credentials ~/.config/earthengine/credentials.comahue --project mapbiomas-argentina`
to run as the second account; the default is the resident (gmail) one, whose Drive holds
`gee_fire_stats`.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "collection-01"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ee  # noqa: E402

import legends  # noqa: E402
from utils import constants as C  # noqa: E402

OUT_DIR = REPO_ROOT / "collection-01" / "data" / "statistics"
RAW_CSV = OUT_DIR / "lulc_area_eco13_raw.csv"     # year, code, area_ha — as GEE returned it
TIDY_CSV = OUT_DIR / "lulc_area_eco13.csv"        # decoded, one row per eco x class x year

# The previous-year range of calendar years 1999-2025 — see the header.
FIRST_LULC_YEAR, LAST_LULC_YEAR = 1998, 2024
YEARS = list(range(FIRST_LULC_YEAR, LAST_LULC_YEAR + 1))

TEST_RECT = [-63.90, -31.55, -63.70, -31.35]      # the same Córdoba box as burnable_export
TEST_YEARS = [1998, 2024]                          # first and last, so a band-name typo shows
TASK_PREFIX = "arg09_lulc_area_eco13"


# ---------------------------------------------------------------------------
# auth — same pattern as burnable_export.py::initialize()
# ---------------------------------------------------------------------------
def initialize(project: str, credentials_path: str | None = None) -> None:
    if not credentials_path:
        ee.Initialize(project=project)
        print(f"[auth] resident credentials  |  compute project {project}")
        return
    from google.oauth2.credentials import Credentials

    stored = json.loads(Path(credentials_path).expanduser().read_text())
    ee.Initialize(
        Credentials(
            None,
            refresh_token=stored["refresh_token"],
            token_uri=ee.oauth.TOKEN_URI,
            client_id=stored.get("client_id", ee.oauth.CLIENT_ID),
            client_secret=stored.get("client_secret", ee.oauth.CLIENT_SECRET),
            scopes=stored.get("scopes", ee.oauth.SCOPES),
            quota_project_id=stored.get("project"),
        ),
        project=project,
    )
    print(f"[auth] {credentials_path}  |  compute project {project}")


# ---------------------------------------------------------------------------
# the image
# ---------------------------------------------------------------------------
def eco_image() -> ee.Image:
    """`GEOCODE` painted from the VECTOR — the ONLY layer allowed to drive the mask."""
    return ee.Image().paint(ee.FeatureCollection(C.ECOREGIONS13), C.ECOREGION_ID_PROPERTY)


def code_image(year: int) -> ee.Image:
    """`ecoregion13 * 100 + col3_class` for one year, uint16."""
    lulc = ee.Image(C.PRODUCT_LULC).select(f"classification_{year}").unmask(0)
    return eco_image().multiply(100).add(lulc).toUint16().rename("code")


def grouped_area(year: int, geometry: ee.Geometry) -> ee.Dictionary:
    return (
        ee.Image.pixelArea().divide(1e4)                       # m2 -> ha
        .addBands(code_image(year))
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="code"),
            geometry=geometry,
            crs=C.SNIC_CRS,
            crsTransform=C.SNIC_TRANSFORM,
            maxPixels=1e12,
        )
    )


def year_features(year: int, geometry: ee.Geometry) -> ee.List:
    """One feature per code for `year`, carrying the year — so all years can share a task."""
    groups = ee.List(grouped_area(year, geometry).get("groups"))
    return groups.map(
        lambda d: ee.Feature(None, ee.Dictionary(d).set("year", year))
    )


def national_bounds() -> ee.Geometry:
    return ee.FeatureCollection(C.ARG_BUFFER_FC).geometry().bounds()


def rows_from(groups, year: int) -> list[dict]:
    out = []
    for g in groups:
        eco, eco_name, cls, n0, n1, n2 = legends.decode_lulc(g["code"])
        out.append({
            "year": year,
            "code": int(g["code"]),
            "ecoregion_id": eco,
            "ecoregion": eco_name,
            "class_id": cls,
            "nivel0": n0,
            "nivel1": n1,
            "nivel2": n2,
            "area_ha": float(g["sum"]),
        })
    return out


# ---------------------------------------------------------------------------
# the rectangle test
# ---------------------------------------------------------------------------
def check_rect(args) -> int:
    w, s, e, n = TEST_RECT
    rect = ee.Geometry.Rectangle([w, s, e, n], proj="EPSG:4326", geodesic=False)
    rect_ha = rect.area(maxError=1).divide(1e4).getInfo()
    print(f"\ntest rectangle  {w},{s} .. {e},{n}   (Córdoba: dry Chaco / Espinal)")
    print(f"  rectangle area (geodesic) : {rect_ha:>12,.1f} ha")

    ok = True
    for year in TEST_YEARS:
        t0 = time.time()
        rows = rows_from(ee.List(grouped_area(year, rect).get("groups")).getInfo(), year)
        total = sum(r["area_ha"] for r in rows)
        cover = 100 * total / rect_ha
        print(f"\n  {year}   {len(rows)} classes   {time.time() - t0:.1f} s")
        for r in sorted(rows, key=lambda r: -r["area_ha"]):
            print(f"    {r['ecoregion']:<20} {r['class_id']:>3} {r['nivel2']:<34} "
                  f"{r['area_ha']:>11,.1f} ha")
        print(f"    {'TOTAL reported':<59} {total:>11,.1f} ha   "
              f"({cover:.2f} % of the rectangle)")
        ok &= 99.0 <= cover <= 101.0
    print(f"\n  VERDICT: {'PASS' if ok else 'LOOK AT THIS'}")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# the national export
# ---------------------------------------------------------------------------
def desc_for(year: int | None) -> str:
    return (f"{TASK_PREFIX}_{FIRST_LULC_YEAR}_{LAST_LULC_YEAR}" if year is None
            else f"{TASK_PREFIX}_{year}")


def launch(fc: ee.FeatureCollection, desc: str, dry: bool) -> None:
    task = ee.batch.Export.table.toDrive(
        collection=fc,
        description=desc,                    # namespaced: the compute project is SHARED
        folder=C.STATS_DRIVE_FOLDER,
        fileNamePrefix=desc,
        fileFormat="CSV",
        selectors=["year", "code", "sum"],   # pin the columns, do not let GEE choose
    )
    if dry:
        print(f"[dry] would export Drive:{C.STATS_DRIVE_FOLDER}/{desc}.csv")
        return
    task.start()
    print(f"[launched] {task.id}  ->  Drive:{C.STATS_DRIVE_FOLDER}/{desc}.csv")


def export(args) -> int:
    bounds = national_bounds()
    if args.split:
        # One task per year. Costs 27 queue slots but each is small and a single slow year
        # cannot hold up the other 26.
        for y in YEARS:
            launch(ee.FeatureCollection(year_features(y, bounds)), desc_for(y), args.dry_run)
        return 0
    fc = ee.FeatureCollection(
        ee.List([year_features(y, bounds) for y in YEARS]).flatten()
    )
    launch(fc, desc_for(None), args.dry_run)
    return 0


def status(args) -> int:
    found = 0
    for op in ee.data.listOperations():
        md = op.get("metadata", {})
        if TASK_PREFIX in md.get("description", ""):
            found += 1
            print(f"{md.get('description')}  {md.get('state')}  "
                  f"{md.get('startTime', '')}  {md.get('updateTime', '')}")
    if not found:
        print(f"no operations matching {TASK_PREFIX}* in this compute project")
    return 0


# ---------------------------------------------------------------------------
# fetch, decode, gate
# ---------------------------------------------------------------------------
def drive_client(args):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    # No quota project — the shared compute project has no Drive API enabled, and enabling
    # one there to read our own file is not ours to do (statistics/docs/statistics.md §3).
    stored = json.loads(
        Path(args.credentials or "~/.config/earthengine/credentials").expanduser().read_text()
    )
    creds = Credentials(
        None,
        refresh_token=stored["refresh_token"],
        token_uri=ee.oauth.TOKEN_URI,
        client_id=stored.get("client_id", ee.oauth.CLIENT_ID),
        client_secret=stored.get("client_secret", ee.oauth.CLIENT_SECRET),
        scopes=stored.get("scopes", ee.oauth.SCOPES),
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def fetch(args) -> int:
    drive = drive_client(args)
    names = [desc_for(None)] if not args.split else [desc_for(y) for y in YEARS]
    blobs = []
    for name in names:
        q = f"name = '{name}.csv' and trashed = false"
        files = drive.files().list(q=q, fields="files(id,name,modifiedTime,size)",
                                   orderBy="modifiedTime desc").execute().get("files", [])
        if not files:
            raise SystemExit(f"{name}.csv is not in Drive yet — check --status")
        f0 = files[0]
        print(f"[drive] {f0['name']}  {f0.get('size')} B  {f0.get('modifiedTime')}")
        blobs.append(drive.files().get_media(fileId=f0["id"]).execute().decode("utf-8"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if len(blobs) == 1:
        RAW_CSV.write_text(blobs[0], encoding="utf-8")
    else:                                  # concatenate the per-year files, one header
        head = blobs[0].splitlines()[0]
        body = [ln for b in blobs for ln in b.splitlines()[1:] if ln.strip()]
        RAW_CSV.write_text("\n".join([head] + body) + "\n", encoding="utf-8")
    print(f"wrote {RAW_CSV.relative_to(REPO_ROOT)}")
    return check(args)


def read_raw_csv() -> list[dict]:
    if not RAW_CSV.exists():
        raise SystemExit(f"{RAW_CSV} not found — run --export then --fetch first")
    rows = []
    with RAW_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            val = r["sum"] if "sum" in r else r["area_ha"]
            rows.extend(rows_from([{"code": int(r["code"]), "sum": float(val)}],
                                  int(r["year"])))
    return rows


def check(args) -> int:
    rows = read_raw_csv()
    write_tidy(rows)
    return report(rows)


def write_tidy(rows: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = ["year", "ecoregion_id", "ecoregion", "class_id", "nivel0", "nivel1", "nivel2",
            "area_ha"]
    rows = sorted(rows, key=lambda r: (r["year"], r["ecoregion_id"], r["class_id"]))
    with TIDY_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {TIDY_CSV.relative_to(REPO_ROOT)}  ({len(rows):,} rows)")


def report(rows: list[dict]) -> int:
    """The gates: every year present, every year closes to the same national area."""
    import collections

    by_year = collections.defaultdict(float)
    by_year_eco = collections.defaultdict(float)
    for r in rows:
        by_year[r["year"]] += r["area_ha"]
        by_year_eco[(r["year"], r["ecoregion_id"])] += r["area_ha"]

    missing = [y for y in YEARS if y not in by_year]
    if missing:
        print(f"\n  MISSING YEARS: {missing}")

    totals = sorted(by_year.items())
    lo, hi = min(t for _, t in totals), max(t for _, t in totals)
    spread = 100 * (hi - lo) / lo if lo else float("nan")

    print(f"\n{'year':>6} {'total Mha':>11} {'no observado Mha':>18} {'classes':>8}")
    nobs = collections.defaultdict(float)
    ncls = collections.defaultdict(set)
    for r in rows:
        if r["class_id"] in legends.NO_OBSERVADO:
            nobs[r["year"]] += r["area_ha"]
        ncls[r["year"]].add(r["class_id"])
    for y, t in totals:
        print(f"{y:>6} {t/1e6:>11.3f} {nobs[y]/1e6:>18.3f} {len(ncls[y]):>8}")

    print(f"\n  national area spread across years: {spread:.3f} %  "
          "(the country does not change size, so this must be ~0)")
    ok = not missing and spread < 0.01
    # Every ecoregion must appear in every year, or a ratio silently averages over
    # fewer years than it claims.
    holes = [(y, e) for y in YEARS for e in legends.ECO13_NAMES
             if (y, e) not in by_year_eco]
    if holes:
        print(f"  MISSING (year, ecoregion) pairs: {len(holes)}  e.g. {holes[:5]}")
        ok = False
    print(f"\n  VERDICT: {'PASS' if ok else 'LOOK AT THIS'}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test-rect", action="store_true", help="Córdoba rectangle check")
    ap.add_argument("--export", action="store_true", help="national run -> Drive")
    ap.add_argument("--split", action="store_true", help="one task per year")
    ap.add_argument("--status", action="store_true", help="state of the export task(s)")
    ap.add_argument("--fetch", action="store_true", help="download from Drive, decode, gate")
    ap.add_argument("--check", action="store_true", help="re-run the gate on the local CSV")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--credentials", default=None)
    ap.add_argument("--project", default=C.GEE_PROJECT)
    args = ap.parse_args()

    initialize(args.project, args.credentials)

    rc = 0
    if args.test_rect:
        rc |= check_rect(args)
    if args.export:
        rc |= export(args)
    if args.status:
        rc |= status(args)
    if args.fetch:
        rc |= fetch(args)
    if args.check:
        rc |= check(args)
    if not any([args.test_rect, args.export, args.status, args.fetch, args.check]):
        ap.print_help()
    return rc


if __name__ == "__main__":
    sys.exit(main())
