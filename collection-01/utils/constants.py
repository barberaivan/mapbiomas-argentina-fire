"""
collection-01/utils/constants.py

Single source of truth for all configuration.
Update this file when adapting to a new collection or year range.
"""

import csv
from pathlib import Path

# ─── Year range ───────────────────────────────────────────────────────────────
YEARS = list(range(1999, 2025))  # 1999–2025
MB_LIMIT_YEAR = 2024             # last year available in the MapBiomas LULC asset

# ─── Regions ─────────────────────────────────────────────────────────────────
# BA=Bosque Atlántico, CHACO=Chaco, PAMPA=Pampas, CUYO=Monte/Puna/Altos Andes, PAT=Patagonia
REGIONS = ["BA", "CHACO", "PAMPA", "CUYO", "PAT"]

# ─── GEE project ─────────────────────────────────────────────────────────────
GEE_PROJECT = "mapbiomas-fire-485203"

# ─── Asset paths ─────────────────────────────────────────────────────────────
_FIRE_ROOT = "projects/mapbiomas-argentina/assets/FIRE"

TRAINING_DATA_COL1 = f"{_FIRE_ROOT}/COLLECTION-1/TRAINING-DATA"
TRAINING_DATA_COL0 = f"{_FIRE_ROOT}/COLLECTION-0/TRAINING-DATA"


# MapBiomas land-cover: multi-band image, one band per year named classification_YYYY
MAPBIOMAS_LULC = (
    "projects/mapbiomas-argentina/assets/LAND-COVER/COLLECTION-2/INTEGRATION/"
    "mapbiomas_argentina_collection1_integration_v8_buffer"
)

# MapBiomas annual mosaic: ImageCollection, filter by 'year' integer property
MAPBIOMAS_MOSAIC = "projects/nexgenmap/MapBiomas2/LANDSAT/ARGENTINA/mosaics-1"

# Mosaic bands: optical × {median,dry,wet,stdDev} + NDVI/NDWI/NPV/NDFI × same (40 total)
MB_MOSAIC_BANDS = [
    "blue_median",  "blue_median_dry",  "blue_median_wet",  "blue_stdDev",
    "green_median", "green_median_dry", "green_median_wet", "green_stdDev",
    "red_median",   "red_median_dry",   "red_median_wet",   "red_stdDev",
    "nir_median",   "nir_median_dry",   "nir_median_wet",   "nir_stdDev",
    "swir1_median", "swir1_median_dry", "swir1_median_wet", "swir1_stdDev",
    "swir2_median", "swir2_median_dry", "swir2_median_wet", "swir2_stdDev",
    "ndvi_median",  "ndvi_median_dry",  "ndvi_median_wet",  "ndvi_stdDev",
    "ndwi_median",  "ndwi_median_dry",  "ndwi_median_wet",  "ndwi_stdDev",
    "npv_median",   "npv_median_dry",   "npv_median_wet",   "npv_stdDev",
    "ndfi_median",  "ndfi_median_dry",  "ndfi_median_wet",  "ndfi_stdDev",
]

# Names as they appear in exported training assets (get_mb_mosaic_bands adds
# the 'mb_mos_' prefix; MB_MOSAIC_BANDS are the original names used for .select())
MB_MOSAIC_FEATURE_NAMES = [f"mb_mos_{b}" for b in MB_MOSAIC_BANDS]

# ─── Spectral features (21 per Landsat observation) ──────────────────────────
OPTICAL_BANDS = ["BLUE", "GREEN", "RED", "NIR", "SWIR1", "SWIR2"]
FIRE_INDICES  = ["NBR", "NBR2", "MIRBI", "NDVI"]
TC_INDICES    = ["TCB", "TCG", "TCW"]        # Tasseled-cap (Baig et al. 2014, OLI coefs)
EXTRA_INDICES = ["NDMI", "NDSI", "SAVI", "NDWI"]
# Canonical-team additions (logistic_regression_terms.qmd §"Canonical team").
# AFRI is the 2.1 µm / 0.5-coefficient variant (Karnieli et al. 2001, Eq. 11a).
CANONICAL_TEAM_INDICES = ["AFRI", "kNDVI", "EVI2", "NIRv"]
ALL_FOCAL_FEATURES = (
    OPTICAL_BANDS + FIRE_INDICES + TC_INDICES + EXTRA_INDICES + CANONICAL_TEAM_INDICES
)  # 21


# ─── veg_fire land-cover remap ────────────────────────────────────────────────
# Canonical remap (MB country-level class × region → veg_fire class) lives in
# config/veg_fire_remap.csv, generated from the working Google Sheet by
# scripts/veg-fire_remap_clean-google-sheet.R. That CSV is the single source of
# truth shared with the R model-fitting code; this file only loads it.
VEG_FIRE_REMAP_CSV = Path(__file__).resolve().parent.parent / "config" / "veg_fire_remap.csv"


def _load_veg_fire_remap(path: Path = VEG_FIRE_REMAP_CSV) -> list[dict]:
    """Load the remap table as a list of typed row dicts."""
    with open(path, newline="", encoding="utf-8") as f:
        return [
            {
                "mb_class_raw": int(r["mb_class_raw"]),
                "arg_name": r["arg_name"] or None,
                "region": r["region"],
                "region_num": int(r["region_num"]),
                "local_class": r["local_class"] or None,
                "veg_fire": int(r["veg_fire"]),
                "veg_fire_name": r["veg_fire_name"],
                "fittable": r["fittable"].strip().upper() == "TRUE",
            }
            for r in csv.DictReader(f)
        ]


# Full table: one row per (region × MB class). Join key is (region_num, mb_class_raw).
VEG_FIRE_REMAP = _load_veg_fire_remap()

# veg_fire code → {name, fittable} (deduped across regions).
VEG_FIRE_CLASSES = {
    r["veg_fire"]: {"name": r["veg_fire_name"], "fittable": r["fittable"]}
    for r in VEG_FIRE_REMAP
}

# veg_fire codes that get a model fitted (non-burnable / non-observed excluded).
FITTABLE_VEG_FIRE = sorted(c for c, v in VEG_FIRE_CLASSES.items() if v["fittable"])
