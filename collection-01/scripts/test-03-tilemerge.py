"""
collection-01/scripts/test-03-tilemerge.py

One-off TEST: does exporting several MapBiomas cartas as ONE merged image take
similar wall-clock to exporting a single tile?  If so, aggregating tiles per
export task amortises the ~17-min per-task fixed floor (docs/03-bpts.md §8) and
cuts wall-clock — it does NOT cut compute or storage (acknowledged).

Submits three step-03 exports for 2015, all with the **reduced P=50 model**
(models-store/pruning/deploy_K3_P50) and identical settings, differing only in
how many cartas are merged into one image:

    bpts_2015_tilemerge_1   tl
    bpts_2015_tilemerge_2   tl + tr
    bpts_2015_tilemerge_4   tl + tr + bl + br  (a 2x2 square)

    tl = SK-19-V-B   tr = SK-19-X-A
    bl = SK-19-V-D   br = SK-19-X-C

Read EECU + wall-clock afterwards from ee.data.listOperations() (filter
description contains 'tilemerge').  Assets land in C.BP_TS_METRICS_COL and are
deletable when done (user runs deletions).

Run from the repo root:

    $PYTHON collection-01/scripts/test-03-tilemerge.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C
from utils import functions as F

YEAR = 2015
P50_DIR = C.MODELS_DIR.parent / "models-store" / "pruning" / "deploy_K3_P50"

TL, TR, BL, BR = "SK-19-V-B", "SK-19-X-A", "SK-19-V-D", "SK-19-X-C"
TILE_SETS = {
    1: [TL],
    2: [TL, TR],
    4: [TL, TR, BL, BR],
}


def _union_geometry(tile_ids):
    """Dissolved geometry of the given cartas (compute region + export region)."""
    return (ee.FeatureCollection(C.CARTAS_FC)
            .filter(ee.Filter.inList(C.CARTAS_ID_PROPERTY, tile_ids))
            .geometry())


def main():
    ee.Initialize(project=C.GEE_PROJECT)

    terms = F.load_all_coefficients(models_dir=P50_DIR)
    print(f"Loaded {len(terms)} terms from {P50_DIR.name} (reduced P=50 model).")

    tasks = []
    for n, tile_ids in TILE_SETS.items():
        label = f"tilemerge_{n}"
        asset_name = f"bpts_{YEAR}_{label}"
        geom = _union_geometry(tile_ids)
        img = F.bpts_image(YEAR, label, terms=terms, tile_geom=geom)
        task = ee.batch.Export.image.toAsset(
            image=img,
            description=asset_name,
            assetId=f"{C.BP_TS_METRICS_COL}/{asset_name}",
            region=geom,
            scale=30,
            crs="EPSG:4326",
            maxPixels=int(1e10),
        )
        task.start()
        tasks.append(task)
        print(f"  submitted {asset_name}  ({n} tile(s): {', '.join(tile_ids)})")

    print(f"\nSubmitted {len(tasks)} merged-tile test export(s) → {C.BP_TS_METRICS_COL}")
    print("Read EECU/wall-clock with ee.data.listOperations() once SUCCEEDED.")


if __name__ == "__main__":
    main()
