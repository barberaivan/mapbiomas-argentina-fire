#!/usr/bin/env python
"""
collection-01/statistics/burnable_export.py — the BURNABLE DENOMINATOR (docs/09 §4.2-§4.3)

The one thing we still compute in Earth Engine.  The numerator (burned area by month x
year x ecorregión x LULC) comes from the network's toolkit; this produces the other half
of every `%` the factsheet reports: how much of each ecoregion is burnable at all.

WHAT IT COMPUTES
    burnable status per pixel = the MODE over 1998-2024 of "is this col-3 class burnable"
    (legends.BURNABLE / NON_BURNABLE), i.e. ONE CONSTANT LAYER with no year dimension.
    Then one grouped sum of pixelArea over

        code = ecoregion13 * 10 + status          # max 13*10+3 = 133, fits uint8

    status 0 = not burnable, 1 = burnable, 2 = never observed (masked every year),
    3 = tie (burnable in exactly half the observed years).

    2 and 3 are NOT folded into 0, deliberately.  `ee.Reducer.mode()` breaks a tie toward
    the SMALLER value, and "no observado" is supposed to be excluded from both sides of
    every ratio (docs/09 §6) — both would quietly shrink the denominator and inflate every
    percentage.  As their own rows they are measurable (gate 3, docs/09 §7) and the decode
    can then fold them wherever we decide, on the record.

PROGRAMMING STRATEGY — copied from the network's app (docs/09 §2), because the shape is
what makes it fast, not the reducer:
    * the whole crossing packed into ONE integer band, one group field, one sweep;
    * territory is `ee.Image().paint(fc, 'GEOCODE')` — never an intersected vector;
    * the reduction geometry is a `bounds()` RECTANGLE (paint() is masked outside the
      features, so the rectangle costs nothing and a 2 M-edge multipolygon would);
    * no `tileScale`;
    * everything in one task.
  The one divergence: `crs` + `crsTransform` instead of `scale: 30`, because every raster
  in this pipeline sits on one lattice (docs/09 §3).

MASKING RULE (the trap): `add()` propagates masks, so if two inputs were masked, any pixel
missing from EITHER would vanish from the reduction without a trace.  Exactly one layer is
allowed to drive the mask — the ecoregions, which tile the country — and everything else is
unmasked into a visible code.

USAGE (from the repo ROOT), in the order you actually run them
    --test-rect   the Córdoba sanity check: a small rectangle where nearly everything is
                  burnable.  Reported total vs the rectangle's own area, and the burnable
                  share.  Seconds.
    --export      the national run as ONE batch task -> Drive folder C.STATS_DRIVE_FOLDER.
                  Batch, so no client-side timeout can kill it.
    --status      state of that task.
    --fetch       download the finished CSV from Drive into data/statistics/, decode it,
                  and run the gate: burnable area <= each region's own area.
    --check       re-run the gate on the already-downloaded raw CSV (no network).
    --regions     FALLBACK ONLY: compute the table region by region with getInfo instead
                  of the batch export (13 reductions, cached, resumable).  Slow — the
                  national task returns the same 13 regions in one go — so use it only if
                  the batch export itself fails.
Add `--credentials ~/.config/earthengine/credentials.comahue --project mapbiomas-argentina`
to run as the second account; the default is the resident (gmail) one, whose Drive holds
`gee_fire_stats`.
"""
from __future__ import annotations

import argparse
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

# --- where things land -------------------------------------------------------------
OUT_DIR = REPO_ROOT / "collection-01" / "data" / "statistics"
RAW_CSV = OUT_DIR / "burnable_eco13_raw.csv"          # code, area_ha — as GEE returned it
TIDY_CSV = OUT_DIR / "burnable_eco13.csv"             # decoded, one row per eco x status
CACHE = OUT_DIR / ".burnable_regions_cache.json"      # per-region results, resumable

# LULC years to collapse.  1998-2024 = the previous-year range of calendar years
# 1999-2025, i.e. the same 27 layers a per-year design would have read (docs/09 §4.2).
FIRST_LULC_YEAR, LAST_LULC_YEAR = 1998, 2024

# The Córdoba test rectangle (docs/09 §4.5): dry Chaco / Espinal, west of Villa María.
# Natural woodland and cropland — both burnable — so the burnable share must come out
# near 100 %, and the reported TOTAL must come out near the rectangle's own area.
TEST_RECT = [-63.90, -31.55, -63.70, -31.35]          # W, S, E, N
TASK_PREFIX = "arg09_burnable_eco13"


# ---------------------------------------------------------------------------
# auth — same pattern as workflow/07-burned_area_polygons.py::initialize()
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
def burnable_status() -> ee.Image:
    """One band, no year dimension: 0 not burnable / 1 burnable / 2 never observed / 3 tie.

    Built from the MEAN of the per-year 0/1 indicator rather than `ee.Reducer.mode()`
    directly.  The two agree everywhere except exact 50/50 pixels, which mode would send
    silently to 0 and this sends to 3 — same answer, plus the diagnostic.
    """
    remap_from = legends.BURNABLE + legends.NON_BURNABLE
    remap_to = [1] * len(legends.BURNABLE) + [0] * len(legends.NON_BURNABLE)
    lulc = ee.Image(C.PRODUCT_LULC)

    def indicator(year: int) -> ee.Image:
        # No-observado (0, 27) is in NEITHER list, so remap leaves it masked and it never
        # reaches the mean — which IS "no observado is excluded everywhere" (docs/09 §6).
        return lulc.select(f"classification_{year}").remap(remap_from, remap_to)

    years = range(FIRST_LULC_YEAR, LAST_LULC_YEAR + 1)
    mean = ee.ImageCollection([indicator(y) for y in years]).reduce(ee.Reducer.mean())
    return (
        ee.Image(0)
        .where(mean.gt(0.5), 1)
        .where(mean.eq(0.5), 3)
        .updateMask(mean.mask())    # observed pixels only...
        .unmask(2)                  # ...everything else is "never observed"
        .rename("status")
    )


def ecoregions() -> ee.FeatureCollection:
    return ee.FeatureCollection(C.ECOREGIONS13)


def code_image() -> ee.Image:
    """`ecoregion13 * 10 + status`, uint8.  The ecoregions are the ONLY mask driver."""
    eco = ee.Image().paint(ecoregions(), C.ECOREGION_ID_PROPERTY)   # masked outside Argentina
    return eco.multiply(10).add(burnable_status()).toUint8().rename("code")


def grouped_area(geometry: ee.Geometry) -> ee.Dictionary:
    """Hectares per code over `geometry`, on the pinned lattice."""
    return (
        ee.Image.pixelArea().divide(1e4)                      # m2 -> ha
        .addBands(code_image())
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="code"),
            geometry=geometry,
            crs=C.SNIC_CRS,
            crsTransform=C.SNIC_TRANSFORM,
            maxPixels=1e12,
        )
    )


def national_bounds() -> ee.Geometry:
    # A RECTANGLE, never the multipolygon (docs/09 §2, point 3).
    return ee.FeatureCollection(C.ARG_BUFFER_FC).geometry().bounds()


def rows_from(groups) -> list[dict]:
    out = []
    for g in groups:
        eco, eco_name, status, status_name = legends.decode(g["code"])
        out.append({
            "code": int(g["code"]),
            "ecoregion_id": eco,
            "ecoregion": eco_name,
            "status_id": status,
            "status": status_name,
            "area_ha": float(g["sum"]),
        })
    return sorted(out, key=lambda r: (r["ecoregion_id"], r["status_id"]))


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------
def check_rect(args) -> int:
    """Córdoba rectangle: does the reported area add up to the rectangle's own area?"""
    w, s, e, n = TEST_RECT
    rect = ee.Geometry.Rectangle([w, s, e, n], proj="EPSG:4326", geodesic=False)
    rect_ha = rect.area(maxError=1).divide(1e4).getInfo()

    print(f"\ntest rectangle  {w},{s} .. {e},{n}   (Córdoba: dry Chaco / Espinal)")
    print(f"  rectangle area (geodesic) : {rect_ha:>12,.1f} ha")

    t0 = time.time()
    groups = ee.List(grouped_area(rect).get("groups")).getInfo()
    rows = rows_from(groups)
    print(f"  reduction took {time.time() - t0:.1f} s\n")

    total = sum(r["area_ha"] for r in rows)
    burn = sum(r["area_ha"] for r in rows if r["status_id"] == 1)
    for r in rows:
        print(f"    {r['ecoregion']:<26} {r['status']:<14} {r['area_ha']:>12,.1f} ha")
    print(f"    {'TOTAL reported':<41} {total:>12,.1f} ha")

    cover = 100 * total / rect_ha
    share = 100 * burn / total if total else 0.0
    print(f"\n  reported / rectangle : {cover:6.2f} %   (pixels only fall inside Argentina,"
          " so <100 % means the rectangle pokes outside an ecoregion)")
    print(f"  burnable / reported  : {share:6.2f} %   (Córdoba: expect the high 90s)")

    ok = 99.0 <= cover <= 101.0 and share >= 90.0
    print(f"\n  VERDICT: {'PASS' if ok else 'LOOK AT THIS'}")
    return 0 if ok else 1


def check_regions(args) -> int:
    """FALLBACK: one interactive reduction per ecoregion, cached and resumable.

    The batch export (--export) returns all 13 regions in one task and cannot be killed by
    a client-side timeout, so this path exists only for when that fails.  Measured
    2026-09-14: the first region alone ran >13 min here, against ~15 min for the whole
    national batch task.  Do not make it the default.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}

    fc = ecoregions()
    meta = fc.reduceColumns(
        ee.Reducer.toList(3),
        [C.ECOREGION_ID_PROPERTY, C.ECOREGION_NAME_PROPERTY, "system:index"],
    ).getInfo()["list"]
    meta = sorted(((int(g), n, i) for g, n, i in meta), key=lambda x: x[0])

    rows: list[dict] = []
    for eco_id, eco_name, idx in meta:
        key = str(eco_id)
        if key in cache and not args.force:
            print(f"[cached] {eco_id:>2} {eco_name}")
            rows.extend(cache[key])
            continue
        feat = fc.filter(ee.Filter.eq(C.ECOREGION_ID_PROPERTY, eco_id)).first()
        geom = ee.Feature(feat).geometry()
        t0 = time.time()
        groups = ee.List(grouped_area(geom.bounds()).get("groups")).getInfo()
        got = [r for r in rows_from(groups) if r["ecoregion_id"] == eco_id]
        poly_ha = geom.area(maxError=100).divide(1e4).getInfo()
        for r in got:
            r["polygon_ha"] = poly_ha
        cache[key] = got
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
        rows.extend(got)
        print(f"[done]   {eco_id:>2} {eco_name:<26} {time.time() - t0:6.1f} s")

    write_tables(rows)
    return report(rows)


def polygon_areas() -> dict[int, float]:
    """Hectares per ecoregion, from the VECTOR — the independent reference for the gate.

    Geodesic polygon area, computed by GEE from the geometry itself, so it shares nothing
    with the raster path except the asset: if the paint, the lattice or the packing were
    wrong, these two would not agree.
    """
    fc = ecoregions()
    pairs = (fc.map(lambda f: f.set("_ha", f.geometry().area(maxError=100).divide(1e4)))
             .reduceColumns(ee.Reducer.toList(2), [C.ECOREGION_ID_PROPERTY, "_ha"])
             .getInfo()["list"])
    return {int(g): float(a) for g, a in pairs}


def read_raw_csv() -> list[dict]:
    import csv

    if not RAW_CSV.exists():
        raise SystemExit(f"{RAW_CSV} not found — run --export then --fetch first")
    with RAW_CSV.open(encoding="utf-8") as f:
        # The Drive export writes `code,sum`; a locally-computed copy writes `code,area_ha`.
        # Accept either rather than rewriting GEE's own file — RAW_CSV is meant to be
        # verbatim what the export produced.
        groups = [{"code": int(r["code"]),
                   "sum": float(r["sum"] if "sum" in r else r["area_ha"])}
                  for r in csv.DictReader(f)]
    return rows_from(groups)


def fetch(args) -> int:
    """Pull the finished export out of Drive, decode it, and run the gate."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    desc = f"{TASK_PREFIX}_{FIRST_LULC_YEAR}_{LAST_LULC_YEAR}"
    # Build the Drive client WITHOUT a quota project.  The stored credentials carry
    # `project = mapbiomas-fire-485203`, and that project — shared with the whole
    # MapBiomas Fuego network — does not have the Drive API enabled.  Enabling an API on
    # a shared project to read one of our own files is not ours to do; dropping the quota
    # project bills the call to the OAuth client instead, which works and touches nothing.
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
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    q = f"name = '{desc}.csv' and trashed = false"
    files = drive.files().list(q=q, fields="files(id,name,modifiedTime,size)",
                               orderBy="modifiedTime desc").execute().get("files", [])
    if not files:
        raise SystemExit(f"{desc}.csv is not in Drive yet — check --status")
    f0 = files[0]
    print(f"[drive] {f0['name']}  {f0.get('size')} B  {f0.get('modifiedTime')}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    blob = drive.files().get_media(fileId=f0["id"]).execute().decode("utf-8")
    RAW_CSV.write_text(blob, encoding="utf-8")
    print(f"wrote {RAW_CSV.relative_to(REPO_ROOT)}")
    return check(args)


def check(args) -> int:
    """The gate: decode the raw table, attach polygon areas, compare."""
    rows = read_raw_csv()
    poly = polygon_areas()
    for r in rows:
        r["polygon_ha"] = poly.get(r["ecoregion_id"], 0.0)
    write_tables(rows)
    return report(rows)


def write_tables(rows: list[dict]) -> None:
    import csv

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not RAW_CSV.exists():        # never clobber the verbatim file fetched from Drive
        with RAW_CSV.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["code", "area_ha"])
            for r in rows:
                w.writerow([r["code"], f"{r['area_ha']:.4f}"])
    cols = ["ecoregion_id", "ecoregion", "status_id", "status", "area_ha", "polygon_ha"]
    with TIDY_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\nwrote {RAW_CSV.relative_to(REPO_ROOT)}\nwrote {TIDY_CSV.relative_to(REPO_ROOT)}")


def report(rows: list[dict]) -> int:
    """The gate the whole exercise is for: burnable <= the region's own area."""
    by_eco: dict[int, dict] = {}
    for r in rows:
        d = by_eco.setdefault(r["ecoregion_id"], {"name": r["ecoregion"],
                                                  "polygon_ha": r.get("polygon_ha", 0.0)})
        d[r["status"]] = d.get(r["status"], 0.0) + r["area_ha"]

    print(f"\n{'ecoregion':<26} {'burnable Mha':>12} {'not burn.':>10} {'never obs':>10} "
          f"{'tie':>8} {'raster Mha':>11} {'polygon Mha':>12} {'burn/poly':>10}")
    bad = []
    tot_burn = tot_poly = 0.0
    for eco_id in sorted(by_eco):
        d = by_eco[eco_id]
        burn = d.get("burnable", 0.0)
        nb = d.get("no_burnable", 0.0)
        nobs = d.get("never_observed", 0.0)
        tie = d.get("tie", 0.0)
        tot = burn + nb + nobs + tie
        poly = d["polygon_ha"]
        ratio = 100 * burn / poly if poly else float("nan")
        tot_burn += burn
        tot_poly += poly
        flag = ""
        if burn > poly * 1.01:
            flag = "  <-- BURNABLE > REGION AREA"
            bad.append(d["name"])
        if tot > poly * 1.02:
            flag += "  <-- RASTER > POLYGON"
            bad.append(d["name"])
        print(f"{d['name']:<26} {burn/1e6:>12.3f} {nb/1e6:>10.3f} {nobs/1e6:>10.3f} "
              f"{tie/1e6:>8.3f} {tot/1e6:>11.3f} {poly/1e6:>12.3f} {ratio:>9.1f} %{flag}")
    print(f"{'TOTAL':<26} {tot_burn/1e6:>12.3f} {'':>10} {'':>10} {'':>8} {'':>11} "
          f"{tot_poly/1e6:>12.3f} {100*tot_burn/tot_poly:>9.1f} %")

    if bad:
        print(f"\n  VERDICT: LOOK AT THIS — {sorted(set(bad))}")
        return 1
    print("\n  VERDICT: PASS — every region's burnable area is inside its own area")
    return 0


# ---------------------------------------------------------------------------
# the national export
# ---------------------------------------------------------------------------
def export(args) -> int:
    groups = ee.List(grouped_area(national_bounds()).get("groups"))
    fc = ee.FeatureCollection(
        groups.map(lambda d: ee.Feature(None, ee.Dictionary(d)))
    )
    desc = f"{TASK_PREFIX}_{FIRST_LULC_YEAR}_{LAST_LULC_YEAR}"
    task = ee.batch.Export.table.toDrive(
        collection=fc,
        description=desc,               # namespaced: the compute project is SHARED
        folder=C.STATS_DRIVE_FOLDER,
        fileNamePrefix=desc,
        fileFormat="CSV",
        selectors=["code", "sum"],      # pin the columns, do not let GEE choose
    )
    if args.dry_run:
        print(f"[dry] would export Drive:{C.STATS_DRIVE_FOLDER}/{desc}.csv")
        return 0
    task.start()
    print(f"[launched] {task.id}  ->  Drive:{C.STATS_DRIVE_FOLDER}/{desc}.csv")
    return 0


def status(args) -> int:
    found = 0
    for op in ee.data.listOperations():
        md = op.get("metadata", {})
        if TASK_PREFIX in md.get("description", ""):
            found += 1
            print(f"{md.get('description')}  {md.get('state')}  "
                  f"{md.get('startTime', '')}  {md.get('updateTime', '')}")
            for note in md.get("notes", []) or []:
                print(f"    {note}")
    if not found:
        print(f"no operations matching {TASK_PREFIX}* in this compute project")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test-rect", action="store_true", help="Córdoba rectangle check")
    ap.add_argument("--export", action="store_true", help="national run -> Drive")
    ap.add_argument("--status", action="store_true", help="state of the export task")
    ap.add_argument("--fetch", action="store_true", help="download from Drive, decode, gate")
    ap.add_argument("--check", action="store_true", help="re-run the gate on the local CSV")
    ap.add_argument("--regions", action="store_true",
                    help="FALLBACK: per-region getInfo instead of the batch export")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="ignore the per-region cache")
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
    if args.regions:
        rc |= check_regions(args)
    if not any([args.test_rect, args.export, args.status, args.fetch, args.check,
                args.regions]):
        ap.print_help()
    return rc


if __name__ == "__main__":
    sys.exit(main())
