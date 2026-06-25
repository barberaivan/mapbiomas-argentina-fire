"""
collection-01/scripts/test-03-bp_ts.py

Interactive / sanity-check harness for step 03 (burn-probability time-series
metrics).  Designed to be run line-by-line in Positron (or imported), but also
runs a headless validation when executed directly.

Default test case: focal year 2015, tile SK-19-Y-A — the Cholila fire (Patagonia
forest) burned in Feb 2015 and should show a large patch of high `delta3_peak`
and `pmax1` in the forest zone.

Interactive use (Positron):

    from scripts import test_03_bp_ts as T   # or run this file's body line by line
    m = T.show(2015, "SK-19-Y-A")            # geemap Map with all layers
    m                                        # display it

    # Per-observation time series for the inspector (NBR, NBR2, prob vs date):
    col = T.bp_inspector_collection(2015, "SK-19-Y-A")

Headless use:

    $PYTHON collection-01/scripts/test-03-bp_ts.py --year 2015 --tile SK-19-Y-A
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C
from utils import functions as F

YEAR = 2015
TILE = "SK-19-Y-A"


def _init():
    ee.Initialize(project=C.GEE_PROJECT)


# ─── Visualisation params ────────────────────────────────────────────────────
FALSE_COLOR_VIS = {"bands": ["NIR", "SWIR1", "SWIR2"], "min": 0.0, "max": 0.4}
PROB_VIS  = {"bands": ["prob"], "min": 0.0, "max": 1.0,
             "palette": ["000004", "781c6d", "ed6925", "fcffa4"]}
DELTA_VIS = {"min": 0.0, "max": 1.0, "palette": ["000004", "781c6d", "ed6925", "fcffa4"]}
PMAX_VIS  = {"min": 0.0, "max": 1.0, "palette": ["000004", "781c6d", "ed6925", "fcffa4"]}
VEGFIRE_VIS = {"min": 1, "max": 25, "palette": [
    "1f78b4", "33a02c", "b2df8a", "a6cee3", "fb9a99", "e31a1c", "fdbf6f",
    "ff7f00", "cab2d6", "6a3d9a", "ffff99", "b15928", "8dd3c7", "ffffb3",
    "bebada", "fb8072", "80b1d3", "fdb462", "b3de69", "fccde5", "d9d9d9",
    "bc80bd", "ccebc5", "000000", "ffffff"]}


def bp_inspector_collection(year=YEAR, tile_id=TILE):
    """Per-date collection carrying spectral indices + prob (for the inspector)."""
    col, _ = F.burn_prob_collection(year, tile_id, keep_indices=True)
    return col


def show(year=YEAR, tile_id=TILE):
    """
    Build a geemap Map for one tile-year with:
      - a single mid-series Landsat false-color image,
      - the veg_fire class,
      - one observation's burn-probability layer,
      - the bpts metric image (delta3_peak, pmax1, n).
    Returns the geemap.Map (display it in a notebook / Positron).
    """
    import geemap

    tile_geom = F._tile_geometry(tile_id)
    veg_fire = F.veg_fire_image(year)

    bp_col = bp_inspector_collection(year, tile_id)
    # A representative focal-year image roughly mid-season (around the fire date).
    sample_img = ee.Image(
        bp_col.filterDate(ee.Date.fromYMD(year, 2, 1), ee.Date.fromYMD(year, 4, 1))
        .sort("system:time_start").first()
    )

    metrics = F.bpts_image(year, tile_id)

    m = geemap.Map()
    m.centerObject(tile_geom, 9)
    m.addLayer(sample_img.clip(tile_geom), FALSE_COLOR_VIS, "Landsat false-color (sample obs)")
    m.addLayer(veg_fire.clip(tile_geom), VEGFIRE_VIS, "veg_fire class", False)
    m.addLayer(sample_img.clip(tile_geom), PROB_VIS, "burn prob (sample obs)")
    m.addLayer(metrics.select("delta3_peak").clip(tile_geom), DELTA_VIS, "delta3_peak")
    m.addLayer(metrics.select("pmax1").clip(tile_geom), PMAX_VIS, "pmax1", False)
    # The full per-obs collection (NBR/NBR2/prob) for the time-series inspector.
    m.addLayer(bp_col.select("prob"), PROB_VIS, "prob collection (inspector)", False)
    return m


def validate(year=YEAR, tile_id=TILE):
    """
    Headless check: build the metrics image and reduce a small box near the
    Cholila fire to confirm the whole graph computes without error and produces
    sensible values (high delta3_peak / pmax1, n > 0).
    """
    metrics = F.bpts_image(year, tile_id)
    print("bpts bands:", metrics.bandNames().getInfo())

    # ~5 km box near the centre of the 2015 Cholila burn scar (Patagonia forest).
    box = ee.Geometry.Point([-71.50, -42.55]).buffer(2500).bounds()
    stats = metrics.select(["delta3_peak", "pmax1", "n", "date_post3"]).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=box,
        scale=120,
        maxPixels=int(1e8),
    ).getInfo()
    print("Cholila box means:", stats)
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sanity-check step 03 (bp_ts_metrics).")
    parser.add_argument("--year", type=int, default=YEAR)
    parser.add_argument("--tile", default=TILE)
    args = parser.parse_args()
    _init()
    validate(args.year, args.tile)
