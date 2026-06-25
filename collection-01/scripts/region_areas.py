"""
collection-01/scripts/region_areas.py

Compute the absolute area (km²) of each of the 5 MapBiomas-Argentina fire regions
from the unbuffered regions FeatureCollection, and write config/region_areas.csv.

Needed because the `areas_regiones` sheet only gives reliable *within-region* class
fractions; turning those into all-Argentina shares (e.g. to weight per-class LR term
importance in notebooks/lr_term_pruning.qmd) requires each region's absolute area.

Run from the repo root:  $PYTHON collection-01/scripts/region_areas.py
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C

REGIONS_FC = "projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/regiones_arg_col1_simplificada"
OUT = Path(__file__).resolve().parents[1] / "config" / "region_areas.csv"

# FC `Region` (free-text Spanish) → the remap's region code / number (config/veg_fire_remap.csv).
FC_TO_REMAP = {
    "Puna,Monte y Altos Andes": ("CUYO", 1),
    "Patagonia":                ("PAT", 2),
    "Pampas":                   ("PAMPA", 3),
    "Chaco":                    ("CHACO", 4),
    "Bosque Atlantico":         ("BA", 5),
}


def main():
    ee.Initialize(project=C.GEE_PROJECT)
    fc = ee.FeatureCollection(REGIONS_FC).map(
        lambda f: f.set("area_km2", f.geometry().area(maxError=100).divide(1e6)))
    names = fc.aggregate_array("Region").getInfo()
    areas = fc.aggregate_array("area_km2").getInfo()

    rows = []
    for nm, ar in zip(names, areas):
        if nm not in FC_TO_REMAP:
            raise SystemExit(f"Unmapped FC region name: {nm!r} — update FC_TO_REMAP.")
        region, region_num = FC_TO_REMAP[nm]
        rows.append({"region": region, "region_num": region_num,
                     "fc_name": nm, "area_km2": round(ar, 1)})
    rows.sort(key=lambda r: r["region_num"])

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["region", "region_num", "fc_name", "area_km2"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {OUT}")
    for r in rows:
        print(f"  {r['region']:6s} ({r['region_num']}) {r['area_km2']:>12.1f} km²  [{r['fc_name']}]")


if __name__ == "__main__":
    main()
