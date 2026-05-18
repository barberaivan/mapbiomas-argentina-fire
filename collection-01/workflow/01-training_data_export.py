"""
collection-01/workflow/01-training_data_export.py

Export observation-level training data for the col1 burn-probability model.

For each region, produces one GEE FeatureCollection asset where each row is:
  one training point × one valid Landsat observation

with all 17 focal-date spectral features and previous-year MapBiomas
land-cover + mosaic data attached.

Usage
-----
  python collection-01/workflow/01-training_data_export.py --region PAT --version 1

PAT includes training fires from collection-00 (automatically checked).

Definition of done: run end-to-end on one fire first, review output schema,
then run the full region. See also TASK-DATA-EXPORT.md.
"""

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path

# Add collection-01/ to sys.path so `utils` package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C
from utils import functions as F

# Max points per export task. Larger fires are split into ceil(n / CHUNK_SIZE)
# balanced chunks to avoid OOM (fire_47 v2 failed at 10k, v3 split-in-half at
# 5k also OOMed; 2k is known to work).
CHUNK_SIZE = 2000

# ─── Sampling ────────────────────────────────────────────────────────────────

def _sample_collection(landsat_col, points, fire_id, region, burned_value):
    """
    Sample every image in landsat_col at the given points.
    Attaches burned label, fire/region metadata, coordinates, and date.
    Drops geometry from each sampled feature to keep asset size manageable.
    """
    def _sample_image(img):
        date = ee.Date(img.get("system:time_start"))
        samples = img.sampleRegions(
            collection=points,
            scale=30,
            geometries=True,   # keep point geometry; required by toAsset (no null geometries)
            tileScale=4,
        )
        def _add_meta(feat):
            return feat.set({
                "date":       date.format("YYYY-MM-dd"),
                "focal_year": date.get("year"),
                "landsat_id": img.get("system:id"),
                "sensor":     img.get("sensor"),
                "fire_id":    fire_id,
                "region":     region,
                "burned":     burned_value,
            })
        return samples.map(_add_meta)

    return landsat_col.map(_sample_image).flatten()


# ─── Per-fire processing ──────────────────────────────────────────────────────

def process_fire(fire_props, region, locations):
    """
    Build and return the sampled FeatureCollection for one fire event.

    Parameters
    ----------
    fire_props : dict of properties from the training_fires FeatureCollection
    region     : str, region code
    locations  : ee.FeatureCollection of training points (point_id already set)
    """
    fire_id  = fire_props["fire_id"]
    pre_upr  = fire_props["pre_upr"]
    post_lwr = fire_props["post_lwr"]
    post_upr = fire_props["post_upr_long"]   # use long window; short-window split done at training time

    # pre_lwr is null in most assets → compute as pre_upr minus one year
    pre_lwr = fire_props.get("pre_lwr")
    if pre_lwr is None:
        dt = datetime.strptime(pre_upr[:10], "%Y-%m-%d")
        pre_lwr = dt.replace(year=dt.year - 1).strftime("%Y-%m-%d")

    print(f"    fire {fire_id}: {pre_lwr} → {post_upr}")

    lulc      = ee.Image(C.MAPBIOMAS_LULC)
    mosaic_ic = ee.ImageCollection(C.MAPBIOMAS_MOSAIC)

    obs_start_year = datetime.strptime(pre_lwr[:10],  "%Y-%m-%d").year
    obs_end_year   = datetime.strptime(post_upr[:10], "%Y-%m-%d").year
    mb_start_year  = obs_start_year - 1
    mb_end_year    = min(obs_end_year - 1, C.MB_LIMIT_YEAR)

    # For each previous-year MB layer, fetch the corresponding Landsat year
    # (obs_year = mb_year + 1) and attach the land-cover and mosaic.
    year_collections = []
    for mb_year in range(mb_start_year, mb_end_year + 1):
        obs_year  = mb_year + 1
        mb_class  = F.get_mb_class_band(lulc, mb_year)
        mb_mosaic = F.get_mb_mosaic_bands(mosaic_ic, mb_year, locations, C.MB_MOSAIC_BANDS)

        ls = (F.get_landsat(locations, f"{obs_year}-01-01", f"{obs_year + 1}-01-01")
              .map(F.add_indices)
              .map(lambda img: img.addBands([mb_class, mb_mosaic])))
        year_collections.append(ls)

    # Merge all focal years into one collection
    full_ls = year_collections[0]
    for col in year_collections[1:]:
        full_ls = full_ls.merge(col)

    # Separate burned vs unburned points
    burned_pts   = locations.filter(ee.Filter.eq("class", "burned"))
    unburned_pts = locations.filter(ee.Filter.eq("class", "unburned"))

    # Pre-fire observations from burned points → burned = 0
    pre_samples = _sample_collection(
        full_ls.filterDate(pre_lwr, pre_upr),
        burned_pts, fire_id, region, 0,
    )

    # Post-fire observations from burned points → burned = 1
    post_samples = _sample_collection(
        full_ls.filterDate(post_lwr, post_upr),
        burned_pts, fire_id, region, 1,
    )

    # All observations from unburned points → burned = 0
    unburned_samples = _sample_collection(
        full_ls.filterDate(pre_lwr, post_upr),
        unburned_pts, fire_id, region, 0,
    )

    return pre_samples.merge(post_samples).merge(unburned_samples)


# ─── Helpers to load assets ───────────────────────────────────────────────────

def _load_locations(fire_id, region):
    """
    Load training_locations FeatureCollection for one fire.
    For PAT, falls back to collection-00 if not found in collection-01.
    Returns None if not found in either location.
    """
    # fire_id may be int (32), numeric str ("32"), or prefixed str ("fire_32")
    fid_str = str(fire_id).removeprefix("fire_").zfill(2)

    path_col1 = f"{C.TRAINING_DATA_COL1}/{region}/training_locations-fire_{fid_str}"
    try:
        ee.data.getAsset(path_col1)
        return ee.FeatureCollection(path_col1)
    except Exception:
        pass

    if region == "PAT":
        path_col0 = f"{C.TRAINING_DATA_COL0}/training_locations-fire_{fid_str}"
        try:
            ee.data.getAsset(path_col0)
            return ee.FeatureCollection(path_col0)
        except Exception:
            pass

    return None


# ─── Main ────────────────────────────────────────────────────────────────────

def main(region, version, test_fire=None):
    ee.Initialize(project=C.GEE_PROJECT)
    print(f"\n=== Region: {region}  version: {version} ===")

    fires_path = f"{C.TRAINING_DATA_COL1}/{region}/training_fires"
    fires_info = ee.FeatureCollection(fires_path).getInfo()["features"]

    if test_fire is not None:
        fires_info = [f for f in fires_info if str(f["properties"]["fire_id"]) == str(test_fire)]
        if not fires_info:
            print(f"Fire {test_fire} not found. Check fire_id in {fires_path}.")
            return

    fire_log = []
    for feat in fires_info:
        props    = feat["properties"]
        geom     = feat["geometry"]
        fire_id  = props["fire_id"]
        fid_str  = str(fire_id).removeprefix("fire_").zfill(2)
        locations = _load_locations(fire_id, region)

        if locations is None:
            print(f"  {fire_id}: WARNING training_locations not found, skipping.")
            fire_log.append({"fire_id": fire_id, "status": "skipped", "reason": "no locations"})
            continue

        n_total    = locations.size().getInfo()
        n_burned   = locations.filter(ee.Filter.eq("class", "burned")).size().getInfo()
        n_unburned = n_total - n_burned
        if n_total == 0:
            print(f"  {fire_id}: WARNING training_locations is empty, skipping.")
            fire_log.append({"fire_id": fire_id, "status": "skipped", "reason": "empty"})
            continue
        if n_burned == 0:
            print(f"  {fire_id}: WARNING no 'burned' points (unburned-only export).")
        if n_unburned == 0:
            print(f"  {fire_id}: WARNING no 'unburned' points (burned-only export).")

        locations = F.assign_point_ids(locations)

        is_multipoly = (geom["type"] == "MultiPolygon"
                        and len(geom["coordinates"]) > 1)

        if is_multipoly:
            # Per-sub-polygon split: cuts both point count AND Landsat scene
            # count per task (large multi-poly fires like fire_47 OOM otherwise
            # because their bbox pulls in too many scenes). Skips empty polys.
            sub_polys = geom["coordinates"]
            chunks = []
            for i, poly_coords in enumerate(sub_polys):
                sub_geom = ee.Geometry.Polygon(poly_coords)
                sub_locs = locations.filterBounds(sub_geom)
                n_sub = sub_locs.size().getInfo()
                if n_sub == 0:
                    print(f"  {fire_id} _part{i + 1:02d}: 0 points in polygon, skipping")
                    continue
                chunks.append((f"_part{i + 1:02d}", sub_locs, n_sub))
            print(f"  {fire_id}: MultiPolygon ({len(sub_polys)} polys) → "
                  f"{len(chunks)} non-empty parts to export")
        elif n_total > CHUNK_SIZE:
            n_chunks = math.ceil(n_total / CHUNK_SIZE)
            chunk_size = math.ceil(n_total / n_chunks)
            chunks = []
            for i in range(n_chunks):
                lo = i * chunk_size
                hi = min((i + 1) * chunk_size, n_total)
                chunk = locations.filter(
                    ee.Filter.And(
                        ee.Filter.gte("point_id", lo),
                        ee.Filter.lt("point_id", hi),
                    )
                )
                chunks.append((f"_part{i + 1:02d}", chunk, hi - lo))
            print(f"  {fire_id}: n={n_total} > {CHUNK_SIZE}, "
                  f"splitting into {n_chunks} parts of ~{chunk_size}")
        else:
            chunks = [("", locations, n_total)]

        for suffix, loc_chunk, n_chunk in chunks:
            fc = process_fire(props, region, loc_chunk)
            output_path = (f"{C.TRAINING_DATA_COL1}/{region}/"
                           f"training_observations-fire_{fid_str}_v{version}{suffix}")
            task = ee.batch.Export.table.toAsset(
                collection=fc,
                description=f"training_obs_{region}_fire_{fid_str}_v{version}{suffix}",
                assetId=output_path,
            )
            task.start()
            task_id = task.status()["id"]
            print(f"  {fire_id}{suffix} (n={n_chunk}): submitted → "
                  f"{output_path.split('/')[-1]}  [{task_id}]")
            fire_log.append({"fire_id": fire_id, "chunk": suffix or None,
                             "n_points": n_chunk, "status": "submitted",
                             "output_asset": output_path, "task_id": task_id})

    # Write sidecar run-log
    log = {
        "run_at":           datetime.utcnow().isoformat() + "Z",
        "region":           region,
        "version":          version,
        "test_fire":        test_fire,
        "training_fires":   fires_path,
        "mapbiomas_lulc":   C.MAPBIOMAS_LULC,
        "mapbiomas_mosaic": C.MAPBIOMAS_MOSAIC,
        "mb_mosaic_bands":  C.MB_MOSAIC_BANDS,
        "focal_features":   C.ALL_FOCAL_FEATURES,
        "fires":            fire_log,
    }
    log_file = Path(__file__).with_suffix("") / f"run_{region}_v{version}.json"
    log_file.parent.mkdir(exist_ok=True)
    log_file.write_text(json.dumps(log, indent=2))
    print(f"\n  Run log: {log_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export observation-level training data.")
    parser.add_argument(
        "--region",
        choices=C.REGIONS,
        default="PAT",
        help="Region to process (default: PAT; use for initial test).",
    )
    parser.add_argument(
        "--version",
        type=int,
        default=1,
        help="Asset version suffix added to output path (default: 1).",
    )
    parser.add_argument(
        "--test-fire",
        default=None,
        help="Process only this fire_id (for testing before full run).",
    )
    args = parser.parse_args()
    main(args.region, args.version, args.test_fire)
