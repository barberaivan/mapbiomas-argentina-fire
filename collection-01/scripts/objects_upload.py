"""
collection-01/scripts/objects_upload.py

Package one fire-year of step-05 objects — geometry + ALL 20 predictors + the model/label calls —
for the GEE table upload, and ingest it if a GCS bucket is reachable (as of 2026-07 none is, so the
zip IS the deliverable and the upload is done by hand). docs/06 §12.

EVERY object goes up, not only the ones called fire: a fire-only layer can show commission error
but never omission, and the rejected objects with their predictors are what aims the next label
campaign. One asset per fire-year -> .../WORKFLOW-EXPORTS/objects_raw/objects_raw_YYYY.

Pipeline per year:
  1. read <store>/collection-01/data/objects-raw/objects_<fy>.gpkg   (oid + geometry)
  2. join objects_<fy>_{raster,shape}_metrics.csv + the step-06 prediction and derived-predictor
     CSVs on `oid`
  3. write a zipped ESRI Shapefile with EXPLICITLY renamed <=10-char fields
  4. stage the .zip in GCS (the `earthengine` CLI only accepts gs:// sources)
  5. `earthengine upload table` -> projects/.../objects_raw/objects_raw_<fy>
  6. delete the staged object once ingestion is queued (unless --keep-staged)

Build all 28 with scripts/run_07_upload_zips.sh, then GATE them with
scripts/validate_upload_zips.py before uploading anything by hand.

Why zipped Shapefile and not GeoJSON: geometry is the whole cost here (the GPKGs
carry no attributes). Measured on 2014, one year is 73 MB GPKG -> 166 MB GeoJSON
but only 13 MB zipped SHP. Shapefile's 10-char field limit is handled by renaming
every field by hand below -- never let OGR auto-truncate, `date_median` /
`date_median_date` and `burned_around_{1,2,3}` collide.

Usage
-----
  $PYTHON collection-01/scripts/objects_upload.py --year 2000
  $PYTHON collection-01/scripts/objects_upload.py --year 2000 --dry-run     # build zip, no upload
  $PYTHON collection-01/scripts/objects_upload.py --year 2000 --force       # overwrite the asset
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import pandas as pd
from osgeo import ogr, osr

ogr.UseExceptions()
osr.UseExceptions()

REPO_ROOT = Path(__file__).resolve().parents[2]

ASSET_FOLDER = (
    "projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/WORKFLOW-EXPORTS/objects_raw"
)
ASSET_PREFIX = "objects_raw"
# Staging bucket for the ingest hand-off. Lives in the GEE compute project; the
# object is deleted after the ingestion task is queued.
DEFAULT_BUCKET = "mapbiomas-fire-485203-ee-staging"
DEFAULT_BUCKET_PROJECT = "mapbiomas-fire-485203"
DEFAULT_BUCKET_LOCATION = "southamerica-east1"

# --- field renaming ---------------------------------------------------------
# Shapefile DBF caps field names at 10 chars. Map every source column by hand so
# the GEE property names are ones we chose, not OGR's truncation.
RENAME = {
    # raster metrics
    "oid": "oid",
    # the deployed call and its two inputs. fire_tag is -1 where nothing was labelled, NEVER
    # absent: OGR writes an unset DBF integer as 0, which would be indistinguishable from a
    # human labelling the object NOT fire (objects_data_functions.R::TAG_NONE).
    "fire": "fire",
    "fire_model": "fire_model",
    "fire_tag": "fire_tag",
    "p_mean": "p_mean",
    "p_width": "p_width",
    # the 8 DERIVED predictors (the other 12 are verbatim metrics columns above). Written by
    # 06-object_model.R into objects_<fy>_derived.csv, because add_veg_groups() resolves group
    # membership from config/veg_fire_remap.csv by NAME and must not be reimplemented here.
    "doy_sin": "doy_sin",
    "doy_cos": "doy_cos",
    "date_span": "date_span",
    "frac_agri": "frac_agri",
    "frac_grass_inund": "frac_gr_in",
    "frac_pasture": "frac_past",
    "frac_grass_temp": "frac_gr_tp",
    "frac_woody": "frac_woody",
    "n_pixels": "n_pixels",
    "area_ha": "area_ha",
    "burned_around_1": "burn_ar1",
    "burned_around_2": "burn_ar2",
    "burned_around_3": "burn_ar3",
    "seed_mean": "seed_mean",
    "date_median": "date_med",
    "date_min": "date_min",
    "date_max": "date_max",
    "year_calendar": "year_cal",
    "date_median_date": "date_medd",
    # shape metrics
    "perimeter_m": "perim_m",
    "convexity": "convexity",
    "mbr_fill": "mbr_fill",
    "mbr_elongation": "mbr_elong",
    "circularity": "circ",
    "shape_index": "shape_idx",
}
# frac_c1 .. frac_c23 are already <=10 chars; keep them verbatim.
RENAME.update({f"frac_c{i}": f"frac_c{i}" for i in range(1, 24)})

# Columns written as text rather than a number.
STRING_FIELDS = {"oid", "date_medd"}
# Written as DBF integers, not reals: they are codes, and a real-typed 1.0000000001 in GEE would
# break `fire == 1` filters.
INT_FIELDS = {"fire", "fire_model", "fire_tag"}
# "no usable label" -- must match objects_data_functions.R::TAG_NONE
TAG_NONE = -1

# Present in the step-05 metrics but deliberately NOT uploaded. `n_mean` is an era proxy that was
# removed as a predictor (docs/06 §4); collection 2 should
# not compute it at all. Dropped explicitly rather than left to trip the RENAME check, so the
# omission is a stated decision instead of an error someone "fixes" by adding it back.
DROP_COLS = {"n_mean"}

# The 20 step-06 predictors, mirroring objects_data_functions.R::PREDICTORS. Kept here only to
# ASSERT that every one of them reaches the upload (see load_metrics); the model itself never
# reads this list, so a drift between the two is caught as a missing column, not silently used.
PREDICTOR_NAMES = {
    "n_pixels", "area_ha", "burned_around_1", "burned_around_2", "burned_around_3",
    "seed_mean", "doy_sin", "doy_cos", "date_span", "perimeter_m", "convexity", "mbr_fill",
    "mbr_elongation", "circularity", "shape_index", "frac_agri", "frac_grass_inund",
    "frac_pasture", "frac_grass_temp", "frac_woody",
}


def log(msg: str) -> None:
    print(f"[objects_upload] {msg}", flush=True)


def store_root() -> Path:
    """STORE_ROOT from .local-paths (machine-local, written by setup.sh)."""
    env = os.environ.get("STORE_ROOT")
    if env:
        return Path(env)
    lp = REPO_ROOT / ".local-paths"
    if not lp.exists():
        sys.exit(f"no STORE_ROOT in env and {lp} not found -- run ./setup.sh")
    for line in lp.read_text().splitlines():
        if line.startswith("STORE_ROOT="):
            return Path(line.split("=", 1)[1].strip())
    sys.exit(f"STORE_ROOT not set in {lp}")


def load_metrics(poly_dir: Path, pred_dir: Path, year: int) -> pd.DataFrame:
    """Join the metric CSVs + the step-06 prediction on `oid`, renamed to DBF-safe names."""
    raster = poly_dir / f"objects_{year}_raster_metrics.csv"
    shape = poly_dir / f"objects_{year}_shape_metrics.csv"
    pred = pred_dir / f"objects_{year}_pred.csv"
    derived = pred_dir / f"objects_{year}_derived.csv"
    for p in (raster, shape, pred, derived):
        if not p.exists():
            sys.exit(f"missing input file: {p}")

    df_r = pd.read_csv(raster)
    df_s = pd.read_csv(shape)
    df = df_r.merge(df_s, on="oid", how="left", validate="one_to_one")

    # The model output is the point of the layer: the deployed call `fire`, the two inputs it is
    # built from (`fire_model` / `fire_tag`), and the posterior summaries an expert needs to judge
    # a call. `fire_year` is dropped -- it is already the `oid` prefix (docs/05 SS3).
    df_p = pd.read_csv(pred, usecols=["oid", "p_mean", "p_width", "fire", "fire_model", "fire_tag"])
    df = df.merge(df_p, on="oid", how="left", validate="one_to_one")
    df_d = pd.read_csv(derived)
    df = df.merge(df_d, on="oid", how="left", validate="one_to_one")
    # -1 IN ALL THREE CODE COLUMNS MEANS "no value", and it has to be written explicitly: OGR
    # leaves an unset DBF integer null, which GEE reads as 0 -- indistinguishable from "a human
    # said NOT fire" (fire_tag) or "the model said NOT fire" (fire_model / fire). Two sources of
    # missingness, one encoding:
    #   fire_tag                  -1 = nobody labelled this object (the common case)
    #   fire_model / fire         -1 = NOT CLASSIFIED -- the object has an NA predictor and could
    #                                  not be scored at all (all-dieback objects, docs/05 SS3)
    # The CSVs keep R-native NA; the sentinel exists only because DBF cannot express it.
    n_unscored = int(df["fire_model"].isna().sum())
    if n_unscored:
        log(f"{n_unscored:,} unscored object(s) (NA predictor) -> fire_model/fire = -1")
    for col in ("fire", "fire_model", "fire_tag"):
        n_na = int(df[col].isna().sum())
        if n_na and col == "fire_tag" and n_na != n_unscored:
            log(f"WARNING: {n_na:,} row(s) had no prediction row; {col} set to -1")
        df[col] = df[col].fillna(TAG_NONE).astype("int64")
    log(
        f"tags: {int((df.fire_tag >= 0).sum()):,} labelled "
        f"({int((df.fire_tag == 1).sum()):,} fire / {int((df.fire_tag == 0).sum()):,} non-fire)"
    )

    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])

    unknown = [c for c in df.columns if c not in RENAME]
    if unknown:
        sys.exit(
            "columns present in the CSVs but absent from RENAME (add them, "
            f"keeping names <=10 chars): {unknown}"
        )
    df = df.rename(columns=RENAME)

    # A DBF cannot hold two fields with the same name.
    dupes = df.columns[df.columns.duplicated()].tolist()
    if dupes:
        sys.exit(f"RENAME produced duplicate field names: {dupes}")
    too_long = [c for c in df.columns if len(c) > 10]
    if too_long:
        sys.exit(f"field names longer than 10 chars: {too_long}")

    # Every model predictor MUST reach the FeatureCollection: the layer exists so an expert can
    # re-examine a call, which is impossible without the inputs the call was made from. Names here
    # are post-RENAME, so this also catches a rename that silently drops one.
    missing = [v for k, v in RENAME.items() if k in PREDICTOR_NAMES and v not in df.columns]
    if missing:
        sys.exit(f"predictor column(s) missing from the upload table: {missing}")
    log(
        f"metrics: {len(df):,} rows x {len(df.columns)} columns "
        f"(all {len(PREDICTOR_NAMES)} predictors present)"
    )
    return df


def build_shapefile(gpkg: Path, df: pd.DataFrame, out_dir: Path, year: int) -> Path:
    """Stream the GPKG features into a Shapefile, attaching the joined metrics."""
    out_dir.mkdir(parents=True, exist_ok=True)
    shp_path = out_dir / f"{ASSET_PREFIX}_{year}.shp"

    src = ogr.Open(str(gpkg))
    if src is None:
        sys.exit(f"cannot open {gpkg}")
    src_layer = src.GetLayer(0)
    n_src = src_layer.GetFeatureCount()

    attrs = df.set_index("oid")
    field_names = [c for c in df.columns if c != "oid"]

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)

    drv = ogr.GetDriverByName("ESRI Shapefile")
    dst = drv.CreateDataSource(str(shp_path))
    # Force MultiPolygon: the dilation-bridge objects (05 SS2.3) are multipart, and a
    # Shapefile layer holds a single geometry type.
    dst_layer = dst.CreateLayer(
        shp_path.stem, srs, ogr.wkbMultiPolygon, options=["ENCODING=UTF-8"]
    )

    dst_layer.CreateField(_make_field("oid", ogr.OFTString))
    for name in field_names:
        if name in STRING_FIELDS:
            dst_layer.CreateField(_make_field(name, ogr.OFTString))
        elif name in INT_FIELDS:
            dst_layer.CreateField(_make_field(name, ogr.OFTInteger))
        else:
            dst_layer.CreateField(_make_field(name, ogr.OFTReal))

    defn = dst_layer.GetLayerDefn()
    records = attrs.to_dict("index")

    n_written = n_missing = 0
    max_vertices = 0
    dst_layer.StartTransaction()
    for i, feat in enumerate(src_layer):
        oid = feat.GetField("oid")
        row = records.get(oid)
        if row is None:
            n_missing += 1
            continue

        geom = feat.GetGeometryRef()
        if geom is None:
            n_missing += 1
            continue
        max_vertices = max(max_vertices, _count_vertices(geom))

        out = ogr.Feature(defn)
        out.SetGeometry(ogr.ForceToMultiPolygon(geom))
        out.SetField("oid", str(oid))
        for name in field_names:
            value = row[name]
            if pd.isna(value):
                continue
            if name in STRING_FIELDS:
                out.SetField(name, str(value))
            elif name in INT_FIELDS:
                out.SetField(name, int(value))
            else:
                out.SetField(name, float(value))
        dst_layer.CreateFeature(out)
        out = None
        n_written += 1

        if (i + 1) % 20000 == 0:
            log(f"  ... {i + 1:,}/{n_src:,} features")
    dst_layer.CommitTransaction()
    dst = None
    src = None

    if n_missing:
        log(f"WARNING: {n_missing:,} features skipped (no metrics row / null geometry)")
    log(f"shapefile: {n_written:,} features, max {max_vertices:,} vertices in one feature")
    if max_vertices > 1_000_000:
        log("WARNING: a feature exceeds 1M vertices; consider --max-vertices on ingest")
    return shp_path


def _make_field(name: str, ftype: int) -> ogr.FieldDefn:
    fld = ogr.FieldDefn(name, ftype)
    if ftype == ogr.OFTReal:
        fld.SetWidth(24)
        fld.SetPrecision(10)
    elif ftype == ogr.OFTInteger:
        fld.SetWidth(3)          # -1 .. 1
    else:
        fld.SetWidth(64)
    return fld


def _count_vertices(geom: ogr.Geometry) -> int:
    if geom.GetGeometryCount():
        return sum(
            _count_vertices(geom.GetGeometryRef(i)) for i in range(geom.GetGeometryCount())
        )
    return geom.GetPointCount()


def zip_shapefile(shp_path: Path) -> Path:
    """Zip the .shp/.shx/.dbf/.prj set flat at the archive root (what GEE expects)."""
    zip_path = shp_path.with_suffix(".zip")
    parts = sorted(shp_path.parent.glob(shp_path.stem + ".*"))
    parts = [p for p in parts if p.suffix != ".zip"]
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in parts:
            zf.write(p, arcname=p.name)
    log(
        f"zipped {len(parts)} components -> {zip_path.name} "
        f"({zip_path.stat().st_size / 1e6:.1f} MB)"
    )
    return zip_path


class NoStagingBucket(RuntimeError):
    """No GCS bucket reachable -- fall back to the manual Code Editor upload."""


def stage_to_gcs(zip_path: Path, bucket_name: str, project: str, location: str) -> str:
    """Upload the zip to GCS; the earthengine CLI ingests only from gs:// URIs."""
    import ee
    from google.cloud import storage
    from google.api_core.exceptions import Forbidden

    ee.Initialize()
    client = storage.Client(project=project, credentials=ee.data.get_persistent_credentials())

    bucket = client.bucket(bucket_name)
    try:
        if not bucket.exists():
            log(f"creating staging bucket gs://{bucket_name} ({location})")
            bucket = client.create_bucket(bucket, location=location)
    except Forbidden as exc:
        raise NoStagingBucket(str(exc)) from exc

    blob = bucket.blob(f"table-uploads/{zip_path.name}")
    log(f"staging -> gs://{bucket_name}/{blob.name}")
    t0 = time.time()
    blob.upload_from_filename(str(zip_path), timeout=3600)
    log(f"staged in {time.time() - t0:.0f}s")
    return f"gs://{bucket_name}/{blob.name}"


def ingest(gs_uri: str, asset_id: str, force: bool, max_vertices: int | None) -> None:
    ee_cli = Path(sys.executable).parent / "earthengine"
    cmd = [str(ee_cli), "upload", "table", f"--asset_id={asset_id}"]
    if force:
        cmd.append("--force")
    if max_vertices:
        cmd.append(f"--max_vertices={max_vertices}")
    cmd.append(gs_uri)
    log("running: " + " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(res.stdout)
    sys.stderr.write(res.stderr)
    if res.returncode != 0:
        sys.exit(f"ingestion failed (rc={res.returncode})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, required=True, help="fire-year to upload")
    ap.add_argument("--asset-folder", default=ASSET_FOLDER)
    ap.add_argument("--bucket", default=DEFAULT_BUCKET)
    ap.add_argument("--bucket-project", default=DEFAULT_BUCKET_PROJECT)
    ap.add_argument("--bucket-location", default=DEFAULT_BUCKET_LOCATION)
    ap.add_argument("--work-dir", default=None, help="where to build the zip")
    # Some objects are enormous (2000 has one of 2.2M vertices -- a dilation-bridged
    # complex). GEE subdivides any geometry above this into pieces inside the same
    # feature, properties untouched; without it the ingest can reject the feature.
    ap.add_argument("--max-vertices", type=int, default=1_000_000)
    ap.add_argument("--force", action="store_true", help="overwrite an existing asset")
    ap.add_argument("--dry-run", action="store_true", help="build the zip, do not upload")
    ap.add_argument("--keep-staged", action="store_true", help="keep the GCS object")
    ap.add_argument("--keep-local", action="store_true", help="keep the local work dir")
    args = ap.parse_args()

    poly_dir = store_root() / "collection-01" / "data" / "objects-raw"
    pred_dir = store_root() / "collection-01" / "data" / "objects-pred"
    gpkg = poly_dir / f"objects_{args.year}.gpkg"
    if not gpkg.exists():
        sys.exit(f"missing {gpkg}")
    log(f"source: {gpkg} ({gpkg.stat().st_size / 1e6:.0f} MB)")

    # Default to a durable dir in the store: with no GCS staging the zip IS the deliverable
    # (manual Code Editor upload), so it must survive the run. Named *-cache because it is
    # regenerable from the metrics + prediction CSVs at any time.
    work_dir = (Path(args.work_dir) if args.work_dir
                else store_root() / "collection-01" / "data" / "objects-upload-cache")
    log(f"work dir: {work_dir}")

    try:
        df = load_metrics(poly_dir, pred_dir, args.year)
        shp = build_shapefile(gpkg, df, work_dir, args.year)
        zip_path = zip_shapefile(shp)

        if args.dry_run:
            log(f"--dry-run: stopping. zip at {zip_path}")
            args.keep_local = True
            return

        asset_id = f"{args.asset_folder}/{ASSET_PREFIX}_{args.year}"
        try:
            gs_uri = stage_to_gcs(
                zip_path, args.bucket, args.bucket_project, args.bucket_location
            )
        except NoStagingBucket as exc:
            args.keep_local = True
            log(f"no GCS staging available: {exc}")
            log(
                "\n  Neither GEE account can create/reach a GCS bucket "
                "(mapbiomas-fire-485203 has no billing account, and we lack\n"
                "  storage permissions on mapbiomas-argentina), and the `earthengine` "
                "CLI ingests only from gs:// URIs.\n"
                "  Upload it by hand instead -- the Code Editor uses GEE's own staging, "
                "no billing needed:\n"
                "    Code Editor -> Assets -> NEW -> Table upload -> Shapefile\n"
                f"    file:     {zip_path}\n"
                f"    asset id: {asset_id}\n"
                "    Advanced -> 'Max error / max vertices': set max vertices to 1000000\n"
            )
            return

        ingest(gs_uri, asset_id, args.force, args.max_vertices)

        log(f"ingestion queued -> {asset_id}")
        log("watch it with: earthengine task list")
        if args.keep_staged:
            log(f"staged object kept at {gs_uri}")
        else:
            log(
                "NOTE: the staged object is needed until ingestion finishes; "
                f"delete it afterwards:\n  gs://{args.bucket}/table-uploads/{zip_path.name}"
            )
    finally:
        if not args.keep_local and work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
            log("removed local work dir")


if __name__ == "__main__":
    main()
