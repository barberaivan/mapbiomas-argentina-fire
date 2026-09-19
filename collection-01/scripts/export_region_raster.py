"""
Paint the buffered region-ID raster that `veg_fire` uses to pick a model per pixel.

Writes `C.REGION_RASTER`, single band `region_id`, on the MapBiomas LULC grid:

    1 = CUYO (Puna / Monte / Altos Andes)   4 = CHACO
    2 = PAT  (Patagonia)                    5 = BA (Bosque Atlantico)
    3 = PAMPA (Pampas)                      0 = outside all regions and the 2 km buffer

Each region is buffered by 2 km and then clipped against the union of the OTHER
(non-buffered) regions, so the buffer expands only beyond Argentina's border and never
into an adjacent Argentine region.

TWO STAGES, and that is the whole point. Painting regions whose geometry is computed
lazily (`buffer().difference()`) makes GEE re-derive those geometries for every export
tile, which dominates the cost. So the buffered FC is materialized to an asset first,
and the raster paints the STORED, static FC.

Usage (from the repo ROOT; --help for the full flag list)
---------------------------------------------------------
    # both stages, waiting for the FC before submitting the raster:
    $PYTHON collection-01/scripts/export_region_raster.py --phase orchestrate

    # or one stage at a time:
    $PYTHON collection-01/scripts/export_region_raster.py --phase fc
    $PYTHON collection-01/scripts/export_region_raster.py --phase raster

Run once; both stages are idempotent and skip an asset that already exists. Where this
raster is used: docs/02-burn_probability.md "Which model judges the pixel".
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C

REGIONS_FC       = "projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/regiones_arg_col1_simplificada"
ARGENTINA_BUF_FC = "projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_1-Pais_buffer"
VECTOR_ASSET     = "projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/ARG-Regiones-MapBiomas-buffer2km"
RASTER_ASSET     = C.REGION_RASTER   # the deployed raster — utils/constants.py owns the path
BUFFER_M         = 2000


def build_regions_buffered():
    """The buffered-and-differenced region FC (codes 1-5 in property 'Zona').

    Each region is buffered by BUFFER_M and then clipped against the union of the
    *other* (non-buffered) regions, so the buffer expands only beyond Argentina's
    border, never into an adjacent Argentine region.
    """
    regions = ee.FeatureCollection(REGIONS_FC)
    zona_map = ee.Dictionary({
        "Puna,Monte y Altos Andes": 1,
        "Patagonia":                2,
        "Pampas":                   3,
        "Chaco":                    4,
        "Bosque Atlantico":         5,
    })
    regions_coded = regions.map(lambda f: f.set("Zona", zona_map.get(f.get("Region"))))

    def buffer_region(f):
        others      = regions.filter(ee.Filter.neq("Region", f.get("Region")))
        others_geom = others.geometry(maxError=1)
        buffered    = f.geometry().buffer(BUFFER_M, maxError=1)
        clipped     = buffered.difference(others_geom, maxError=1)
        return f.setGeometry(clipped)

    return regions_coded.map(buffer_region)


def submit_fc_export():
    """Submit the vector (FeatureCollection) export and return the task."""
    task = ee.batch.Export.table.toAsset(
        collection=build_regions_buffered(),
        description="ARG-Regiones-MapBiomas-buffer2km-FC",
        assetId=VECTOR_ASSET,
    )
    task.start()
    return task


def submit_raster_export(fc_asset=VECTOR_ASSET):
    """Paint the *stored* buffered FC into the region-id raster and export it."""
    regions_buffered = ee.FeatureCollection(fc_asset)
    region_raster = (
        ee.Image(0).byte()
        .paint(featureCollection=regions_buffered, color="Zona")
        .rename(C.REGION_RASTER_BAND)
    )
    lc_proj = ee.Image(C.MAPBIOMAS_LULC).projection().getInfo()  # grid-align to LULC
    task = ee.batch.Export.image.toAsset(
        image=region_raster,
        description="arg_region_raster",
        assetId=RASTER_ASSET,
        crs=lc_proj["crs"],
        crsTransform=lc_proj["transform"],
        region=ee.FeatureCollection(ARGENTINA_BUF_FC).geometry(),
        maxPixels=int(1e10),
        pyramidingPolicy={C.REGION_RASTER_BAND: "mode"},
    )
    task.start()
    return task


def _asset_exists(asset_id):
    try:
        ee.data.getAsset(asset_id)
        return True
    except Exception:
        return False


def poll(task, label, interval=45):
    """Block until `task` reaches a terminal state; print state transitions."""
    last = None
    while True:
        status = task.status()
        state = status.get("state")
        if state != last:
            print(time.strftime("%H:%M:%S"), label, state,
                  status.get("error_message") or "", flush=True)
            last = state
        if state in ("COMPLETED", "FAILED", "CANCELLED"):
            return state
        time.sleep(interval)


def orchestrate():
    """Phase 1 (FC) → wait → Phase 2 (raster)."""
    if _asset_exists(VECTOR_ASSET):
        print(f"FC asset already exists, skipping phase 1: {VECTOR_ASSET}", flush=True)
    else:
        fc_task = submit_fc_export()
        print("Phase 1 — FC export submitted:", fc_task.id, flush=True)
        state = poll(fc_task, "FC")
        if state != "COMPLETED":
            print(f"FC export ended {state}; NOT submitting the raster.", flush=True)
            return

    if _asset_exists(RASTER_ASSET):
        print(f"Raster asset already exists, nothing to do: {RASTER_ASSET}", flush=True)
        return
    r_task = submit_raster_export()
    print("Phase 2 — raster export submitted:", r_task.id, flush=True)
    poll(r_task, "RASTER")
    print("Done.", flush=True)


def main(phase):
    ee.Initialize(project=C.GEE_PROJECT)
    if phase == "fc":
        t = submit_fc_export()
        print("FC export submitted:", t.id, "→", VECTOR_ASSET)
    elif phase == "raster":
        # Gated + idempotent so it is safe to drive from a retry loop
        # (e.g. `until ... --phase raster; do sleep 60; done`) while the FC export
        # is still running: exit 0 if already done, exit 1 (retry) if FC not ready.
        if _asset_exists(RASTER_ASSET):
            print("Raster already exists, nothing to do:", RASTER_ASSET)
            return
        if not _asset_exists(VECTOR_ASSET):
            print("FC asset not ready yet, retry later:", VECTOR_ASSET)
            sys.exit(1)
        t = submit_raster_export()
        print("Raster export submitted:", t.id, "→", RASTER_ASSET)
    else:
        orchestrate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Two-stage region-raster export.")
    parser.add_argument(
        "--phase", choices=["fc", "raster", "orchestrate"], default="orchestrate",
        help="'fc' = export the buffered FC; 'raster' = paint the stored FC; "
             "'orchestrate' (default) = FC, wait, then raster.",
    )
    args = parser.parse_args()
    main(args.phase)
