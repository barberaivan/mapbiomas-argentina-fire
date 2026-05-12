"""
collection-01/utils/constants.py

Single source of truth for all configuration.
Update this file when adapting to a new collection or year range.
"""

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

# Mosaic bands to include: visible + NIR + SWIR + NDVI, median/dry/wet aggregates only
MB_MOSAIC_BANDS = [
    "blue_median",  "blue_median_dry",  "blue_median_wet",
    "green_median", "green_median_dry", "green_median_wet",
    "red_median",   "red_median_dry",   "red_median_wet",
    "nir_median",   "nir_median_dry",   "nir_median_wet",
    "swir1_median", "swir1_median_dry", "swir1_median_wet",
    "swir2_median", "swir2_median_dry", "swir2_median_wet",
    "ndvi_median",  "ndvi_median_dry",  "ndvi_median_wet",
]

# ─── Spectral features (17 per Landsat observation) ──────────────────────────
OPTICAL_BANDS = ["BLUE", "GREEN", "RED", "NIR", "SWIR1", "SWIR2"]
FIRE_INDICES  = ["NBR", "NBR2", "MIRBI", "NDVI"]
TC_INDICES    = ["TCB", "TCG", "TCW"]        # Tasseled-cap (Baig et al. 2014, OLI coefs)
EXTRA_INDICES = ["NDMI", "NDSI", "SAVI", "NDWI"]
ALL_FOCAL_FEATURES = OPTICAL_BANDS + FIRE_INDICES + TC_INDICES + EXTRA_INDICES  # 17

# ─── MapBiomas → fire-vegetation class reclassification ──────────────────────
# Source: collection-00/utils/functions.js production version
# 0=unburnable, 1=forest, 2=shrubland, 3=grassland/agri
# NOTE: review and validate using notebooks/01-landcover_reclassification.qmd
MB_RECLASS_FROM = [3, 66, 6, 12, 11, 75, 63, 21,  9, 29, 25, 24, 33, 34, 27]
MB_RECLASS_TO   = [1,  2, 1,  3,  3,  3,  3,  3,  1,  0,  0,  0,  0,  0,  0]
MB_FIRE_CLASS_NAMES = {0: "unburnable", 1: "forest", 2: "shrubland", 3: "grassland_agri"}

# ─── RF hyperparameters ───────────────────────────────────────────────────────
# Populated after notebooks/03-rf_hyperparameter_tuning.qmd
# Structure: {region: {fire_class: {param: value}}}
RF_PARAMS: dict = {}
