"""
collection-01/scripts/export_region_raster.py

Export a single-band region-ID raster to a GEE asset.

The image is created by painting the 'Zona' property of the
regiones_arg_col1_simplificada FeatureCollection.  Each pixel encodes the
fire-processing region:

    1 = CUYO  (Puna / Monte / Altos Andes)
    2 = PAT   (Patagonia)
    3 = PAMPA (Pampas)
    4 = CHACO (Chaco)
    5 = BA    (Bosque Atlántico)
    0 = outside all regions

The image is used alongside the MapBiomas LULC multi-band asset to apply
per-region land-cover → fire-class remaps on the fly in GEE, without
storing multiple region-specific copies of the LULC asset.

Usage
-----
    python collection-01/scripts/export_region_raster.py

Run from the repo root.  The GEE task is submitted and the script exits;
monitor progress in the Code Editor Tasks panel or with 00-status.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C

REGIONS_FC   = "projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/regiones_arg_col1_simplificada"
ARGENTINA_FC = "projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_1-Pais"
ASSET_ID     = "projects/mapbiomas-argentina/assets/ANCILLARY_DATA/RASTER/ARG/ARG-Regiones-MapBiomas"

ee.Initialize(project=C.GEE_PROJECT)

regions   = ee.FeatureCollection(REGIONS_FC)
argentina = ee.FeatureCollection(ARGENTINA_FC)

# The FC has a 'Region' string property, not a numeric 'Zona'.
# Map it to integers 1–5 so we can paint a single-band raster.
ZONA_MAP = ee.Dictionary({
    "Puna,Monte y Altos Andes": 1,
    "Patagonia":                2,
    "Pampas":                   3,
    "Chaco":                    4,
    "Bosque Atlantico":         5,
})
regions_coded = regions.map(
    lambda f: f.set("Zona", ZONA_MAP.get(f.get("Region")))
)

# Paint Zona (1–5) onto a constant-0 byte image.
region_raster = (
    ee.Image(0).byte()
    .paint(featureCollection=regions_coded, color="Zona")
    .rename("region_id")
)

# Match the LULC image projection exactly so pixels are grid-aligned.
lc_proj = ee.Image(C.MAPBIOMAS_LULC).projection().getInfo()

task = ee.batch.Export.image.toAsset(
    image=region_raster,
    description="ARG-Regiones-MapBiomas",
    assetId=ASSET_ID,
    crs=lc_proj["crs"],
    crsTransform=lc_proj["transform"],
    region=argentina.geometry(),
    maxPixels=int(1e10),
    pyramidingPolicy={"region_id": "mode"},
)
task.start()
print(f"Task submitted: {task.id}")
print(f"Asset: {ASSET_ID}")
