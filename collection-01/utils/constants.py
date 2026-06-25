"""
collection-01/utils/constants.py

Single source of truth for all configuration.
Update this file when adapting to a new collection or year range.
"""

import csv
import os
from pathlib import Path

# ─── Year range ───────────────────────────────────────────────────────────────
YEARS = list(range(1999, 2026))  # 1999–2025 inclusive (range() excludes the upper bound)
MB_LIMIT_YEAR = 2024             # last year available in the MapBiomas LULC asset

# ─── Regions ─────────────────────────────────────────────────────────────────
# BA=Bosque Atlántico, CHACO=Chaco, PAMPA=Pampas, CUYO=Monte/Puna/Altos Andes, PAT=Patagonia
REGIONS = ["BA", "CHACO", "PAMPA", "CUYO", "PAT"]

# ─── GEE project ─────────────────────────────────────────────────────────────
# The Cloud project that pays for / quotas the GEE compute (NOT where assets land).
# Contributors run from different projects (e.g. MapBiomas Argentina vs Fire): each
# sets their own via the GEE_PROJECT env var, or passes project= to ee.Initialize.
# Asset destinations are fixed regardless of compute project; every contributor's
# account just needs write access to BP_TS_METRICS_COL.
GEE_PROJECT = os.environ.get("GEE_PROJECT", "mapbiomas-fire-485203")

# ─── Asset paths ─────────────────────────────────────────────────────────────
_FIRE_ROOT = "projects/mapbiomas-argentina/assets/FIRE"

TRAINING_DATA_COL1 = f"{_FIRE_ROOT}/COLLECTION-1/TRAINING-DATA"
TRAINING_DATA_COL0 = f"{_FIRE_ROOT}/COLLECTION-0/TRAINING-DATA"


# ─── Fire id ─────────────────────────────────────────────────────────────────
def fire_token(fire_id):
    """Canonical ``fire_<id>`` asset token for one fire.

    The ONLY guaranteed structure of a fire id is the ``fire_`` prefix; the
    remainder is verbatim and need not be numeric or two digits — e.g.
    ``fire_sde10`` is as valid as ``fire_07``. We therefore never zero-pad or
    coerce the body; we only ensure the prefix is present, so the same value
    round-trips between the asset's ``fire_id`` property and its asset name.

    Accepts a full id (``"fire_07"`` / ``"fire_sde10"``) or a bare body
    (``"07"`` / ``"sde10"``); returns the full token unchanged in the first case.
    Bare numeric ids are NOT padded — pass the id exactly as it appears in
    ``training_fires`` (the source of truth).
    """
    s = str(fire_id)
    return s if s.startswith("fire_") else f"fire_{s}"


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
# Canonical-team additions (logistic_regression_design.qmd §"Spectral feature equations").
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
                "region_class": int(r["region_class"]),
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

# GEE remap: region_class (region_num*100 + mb_class_raw) → veg_fire.
# In GEE: region_class_img.remap(REGION_CLASS_FROM, VEG_FIRE_TO, VEG_FIRE_REMAP_DEFAULT)
# Ghost classes (integration artefacts not present in the remap table) fall through
# to VEG_FIRE_REMAP_DEFAULT and are treated as non-observed.
REGION_CLASS_FROM    = [r["region_class"] for r in VEG_FIRE_REMAP]
VEG_FIRE_TO          = [r["veg_fire"]     for r in VEG_FIRE_REMAP]
VEG_FIRE_REMAP_DEFAULT = 25  # non-observed

# Sentinel veg_fire codes used in the burn-probability product's `n` band.
VEG_FIRE_NON_BURNABLE = 24   # burnable=FALSE land cover (e.g. water, urban) → n = -1
VEG_FIRE_NON_OBSERVED = 25   # outside the remap / non-observed                → n = -2

# ─── Step 03 — burn-probability time-series metrics ──────────────────────────
# Fitted-model coefficient CSVs (one per veg_fire class), written by step 02.
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

# Region-id raster (1–5, with a 2 km buffer beyond the Argentina boundary) and the
# band that holds the region code.  Built by scripts/export_region_raster.py.
REGION_RASTER      = "projects/mapbiomas-argentina/assets/ANCILLARY_DATA/RASTER/ARG/ARG-Regiones-MapBiomas-buffer2km"
REGION_RASTER_BAND = "region_id"

# Prediction tiling grid (MapBiomas cartas) and its tile-id property, plus the
# buffered-Argentina polygon used to select the tiles to process.
CARTAS_FC           = "projects/mapbiomas-chaco/BASE/cartas-argentina"
CARTAS_ID_PROPERTY  = "grid_name"   # e.g. 'SK-19-Y-A'
ARG_BUFFER_FC       = "projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_1-Pais_buffer"

# Output ImageCollection for this step (asset name pattern: bpts_YYYY_<tile-id>).
BP_TS_METRICS_COL = f"{_FIRE_ROOT}/COLLECTION-1/WORKFLOW-EXPORTS/bp_ts_metrics"

# Landsat padding window: how many months of context to pull from the neighbouring
# years (Sep of y-1 through Apr of y+1, i.e. PAD_MONTHS on each side of the focal year),
# and how many padded observations are kept on each side when building the per-pixel array.
PAD_MONTHS    = 4   # months of Landsat context before/after the focal year
PAD_OBS_LEFT  = 3   # max prev-year obs pulled into the padded array (K=3 back window)
PAD_OBS_RIGHT = 2   # max next-year obs pulled into the padded array (K=3 forward window)

# CSV prev-block term suffix → MapBiomas mosaic band suffix.
# e.g. 'GREEN_med' (CSV) → mb_mos_green_median (mosaic band).  Used when parsing
# the fitted coefficients into GEE feature names.
PREV_SUFFIX_MAP = {
    "med": "median",
    "wet": "median_wet",
    "dry": "median_dry",
    "sd":  "stdDev",
}
