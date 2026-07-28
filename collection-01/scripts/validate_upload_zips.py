"""
collection-01/scripts/validate_upload_zips.py

Pre-upload gate for the 28 zipped Shapefiles in data/objects-upload-cache/ (built by
scripts/run_07_upload_zips.sh). The upload is done BY HAND, one Code Editor dialog per fire-year
(docs/06 §12 — no GCS bucket), so a bad zip is not discovered by a failing pipeline: it is
discovered weeks later as a wrong map. Everything cheap enough to check is checked here.

WHAT IT CHECKS, per year
  structure   zip is FLAT (GEE rejects nested paths) and carries .shp/.shx/.dbf/.prj
  crs         EPSG:4326 — GEE-native; a reprojection here would silently shift every polygon
  schema      all 20 model predictors present under their renamed names, plus oid / fire /
              fire_model / fire_tag / p_mean / p_width / year_cal / date_medd; and n_mean ABSENT
              (dropped on purpose — docs/06 §4)
  count       feature count == rows in the year's prediction CSV (nothing lost in the join)
  oid         unique, non-empty
  codes       fire / fire_model / fire_tag are NEVER NULL and only ever -1/0/1. This is the check
              that matters most: OGR writes an unset DBF integer as null and GEE reads it as 0, so a
              null fire_tag would be indistinguishable from "a human labelled this NOT fire".
  rule        fire == (fire_tag if fire_tag >= 0 else fire_model), feature by feature
  geometry    no null geometries; max vertices per feature, flagging >1e6 (the ingest needs
              `max vertices = 1000000` set in the dialog, else GEE can reject the feature)

Parallel: one worker per year (vertex counting is the cost). Writes a per-year summary CSV and
exits non-zero if any year fails, so it can gate a later scripted ingest.

Run from the repo ROOT, in tmux:
  $PYTHON collection-01/scripts/validate_upload_zips.py
  $PYTHON collection-01/scripts/validate_upload_zips.py -j 4 --dir /some/other/dir 2014 2020
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import importlib.util
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Reuse the upload script's own RENAME / PREDICTOR_NAMES rather than restating them: the point is to
# validate against what the writer believes it wrote.
_spec = importlib.util.spec_from_file_location(
    "objects_upload", REPO_ROOT / "collection-01" / "scripts" / "objects_upload.py"
)
_up = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_up)

from osgeo import ogr  # noqa: E402  (after the module load, which calls UseExceptions)

ogr.UseExceptions()

PRED_TARGETS = {v for k, v in _up.RENAME.items() if k in _up.PREDICTOR_NAMES}
REQUIRED = PRED_TARGETS | {
    "oid", "fire", "fire_model", "fire_tag", "p_mean", "p_width", "year_cal", "date_medd",
}
FORBIDDEN = {"n_mean"}
VERTEX_LIMIT = 1_000_000


def n_vertices(geom) -> int:
    if geom.GetGeometryCount():
        return sum(n_vertices(geom.GetGeometryRef(i)) for i in range(geom.GetGeometryCount()))
    return geom.GetPointCount()


def expected_count(pred_dir: Path, year: str) -> int | None:
    f = pred_dir / f"objects_{year}_pred.csv"
    if not f.exists():
        return None
    with f.open() as fh:
        return sum(1 for _ in fh) - 1  # minus header


def check_year(zip_path: Path, pred_dir: Path) -> dict:
    year = zip_path.stem.split("_")[-1]
    r: dict = {
        "year": year, "zip_mb": round(zip_path.stat().st_size / 1e6, 1),
        "features": 0, "max_vertices": 0, "tag_1": 0, "tag_0": 0, "tag_none": 0,
        "fire_1": 0, "unscored": 0, "p_null": 0, "errors": [],
    }
    tmp = Path(tempfile.mkdtemp(prefix=f"vz{year}_"))
    try:
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            if any("/" in n or "\\" in n for n in names):
                r["errors"].append("zip-not-flat")
            exts = {os.path.splitext(n)[1].lower() for n in names}
            for need in (".shp", ".shx", ".dbf", ".prj"):
                if need not in exts:
                    r["errors"].append(f"missing{need}")
            zf.extractall(tmp)

        shp = tmp / f"objects_raw_{year}.shp"
        if not shp.exists():
            r["errors"].append("shp-name-mismatch")
            return r
        ds = ogr.Open(str(shp))
        lyr = ds.GetLayer(0)

        srs = lyr.GetSpatialRef()
        code = srs.GetAuthorityCode(None) if srs is not None else None
        if code != "4326":
            r["errors"].append(f"crs={code}")

        defn = lyr.GetLayerDefn()
        fields = {defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())}
        r["n_fields"] = len(fields)
        for miss in sorted(REQUIRED - fields):
            r["errors"].append(f"no-field:{miss}")
        for bad in sorted(FORBIDDEN & fields):
            r["errors"].append(f"forbidden-field:{bad}")
        for name in ("fire", "fire_model", "fire_tag"):
            if name in fields:
                t = defn.GetFieldDefn(defn.GetFieldIndex(name)).GetType()
                if t != ogr.OFTInteger:
                    r["errors"].append(f"{name}-not-integer")

        seen_oid: set[str] = set()
        dup = null_code = bad_rule = bad_val = null_geom = 0
        feat = lyr.GetNextFeature()
        while feat:
            r["features"] += 1
            oid = feat.GetField("oid")
            if not oid:
                r["errors"].append("empty-oid") if "empty-oid" not in r["errors"] else None
            elif oid in seen_oid:
                dup += 1
            else:
                seen_oid.add(oid)

            t, m, fi = (feat.GetField(k) for k in ("fire_tag", "fire_model", "fire"))
            if None in (t, m, fi):
                null_code += 1
            else:
                if not {t, m, fi} <= {-1, 0, 1}:
                    bad_val += 1
                if fi != (t if t >= 0 else m):
                    bad_rule += 1
                r["tag_1"] += t == 1
                r["tag_0"] += t == 0
                r["tag_none"] += t == -1
                r["fire_1"] += fi == 1
                r["unscored"] += m == -1
            if feat.GetField("p_mean") is None:
                r["p_null"] += 1

            g = feat.GetGeometryRef()
            if g is None:
                null_geom += 1
            else:
                v = n_vertices(g)
                if v > r["max_vertices"]:
                    r["max_vertices"] = v
            feat = lyr.GetNextFeature()
        ds = None

        if dup:
            r["errors"].append(f"duplicate-oid={dup}")
        if null_code:
            r["errors"].append(f"NULL-code-field={null_code}")
        if bad_val:
            r["errors"].append(f"code-out-of-range={bad_val}")
        if bad_rule:
            r["errors"].append(f"fire-rule-violated={bad_rule}")
        if null_geom:
            r["errors"].append(f"null-geometry={null_geom}")

        exp = expected_count(pred_dir, year)
        r["expected"] = exp
        if exp is not None and exp != r["features"]:
            r["errors"].append(f"count {r['features']}!={exp}")
    except Exception as exc:  # a corrupt zip must fail this year, not the whole run
        r["errors"].append(f"{type(exc).__name__}:{str(exc)[:60]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return r


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("years", nargs="*", help="only these fire-years (default: all found)")
    ap.add_argument("-j", type=int, default=8, help="parallel workers (default 8)")
    ap.add_argument("--dir", default=None, help="zip directory (default: the store's cache)")
    ap.add_argument("--out", default="collection-01/data/objects-analysis/upload_zip_validation.csv")
    args = ap.parse_args()

    zdir = Path(args.dir) if args.dir else _up.store_root() / "collection-01" / "data" / "objects-upload-cache"
    pred_dir = REPO_ROOT / "collection-01" / "data" / "objects-pred"
    zips = sorted(zdir.glob("objects_raw_*.zip"))
    if args.years:
        zips = [z for z in zips if z.stem.split("_")[-1] in set(args.years)]
    if not zips:
        sys.exit(f"no objects_raw_*.zip in {zdir}")

    print(f"validating {len(zips)} zip(s) in {zdir} on {args.j} worker(s)", flush=True)
    print(f"required fields: {len(REQUIRED)} ({len(PRED_TARGETS)} predictors)", flush=True)

    rows = []
    with cf.ProcessPoolExecutor(max_workers=args.j) as ex:
        futs = {ex.submit(check_year, z, pred_dir): z for z in zips}
        for fut in cf.as_completed(futs):
            r = fut.result()
            rows.append(r)
            status = "PASS" if not r["errors"] else "FAIL"
            print(
                f"  [{status}] FY{r['year']}  {r['features']:>7,} feat  "
                f"{r['zip_mb']:>6.1f} MB  maxvert {r['max_vertices']:>9,}  "
                f"tag {r['tag_1']}/{r['tag_0']}  fire1 {r['fire_1']:>7,}  "
                f"unscored {r['unscored']:>2}" + (f"  -> {'; '.join(r['errors'])}" if r["errors"] else ""),
                flush=True,
            )

    rows.sort(key=lambda x: x["year"])
    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["year", "zip_mb", "features", "expected", "n_fields", "max_vertices",
            "tag_1", "tag_0", "tag_none", "fire_1", "unscored", "p_null", "errors"]
    with out.open("w") as fh:
        fh.write(",".join(cols) + "\n")
        for r in rows:
            fh.write(",".join(str(r.get(c, "")).replace(",", ";") for c in cols) + "\n")

    failed = [r for r in rows if r["errors"]]
    over = [r for r in rows if r["max_vertices"] > VERTEX_LIMIT]
    tot_f = sum(r["features"] for r in rows)
    print("\n" + "=" * 78, flush=True)
    print(f"{len(rows)} year(s), {tot_f:,} features, "
          f"{sum(r['tag_1'] + r['tag_0'] for r in rows):,} tagged, "
          f"{sum(r['fire_1'] for r in rows):,} called fire, "
          f"{sum(r['unscored'] for r in rows)} unscored", flush=True)
    print(f"summary -> {out}", flush=True)
    if over:
        print(f"\nNOTE: {len(over)} year(s) exceed {VERTEX_LIMIT:,} vertices in one feature "
              f"({', '.join('FY' + r['year'] for r in over)}).", flush=True)
        print("      Set 'max vertices = 1000000' in the Code Editor upload dialog for ALL years "
              "(GEE then subdivides inside the feature; oid and properties survive).", flush=True)
    if failed:
        print(f"\nFAILED: {', '.join('FY' + r['year'] for r in failed)}", flush=True)
        sys.exit(1)
    print("\nALL PASS — the 28 zips are safe to upload.", flush=True)


if __name__ == "__main__":
    main()
