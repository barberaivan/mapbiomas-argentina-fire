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

# Compute projects that contributors submit bpts export tasks from.  The in-flight
# skip (functions._inflight_bpts_names) scans ALL of these — plus GEE_PROJECT — and
# unions the result, so a launch never re-submits a tile-year that is already
# PENDING/RUNNING under any of them, no matter which account/project queued it.
# ``ee.data.listOperations(project=…)`` is project-scoped (returns every user's tasks
# in the project), so this list is the whole cross-account/cross-project picture.
BPTS_TASK_PROJECTS = ["mapbiomas-argentina", "mapbiomas-fire-485203"]

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
# Fitted-model coefficient CSVs live one-folder-per-model under MODELS_DIR:
#   models/P129/  full fit (130 terms incl. intercept)
#   models/P030/ … P080/   reduced term-pruning variants (P = top-P percentile cut;
#                          rows = intercept + kept terms, so P050 = 52 rows, etc.)
# All variants use CV scheme K=3 (not in the folder name; see docs/03-bpts.md §11).
# The CSVs are git-tracked (models/.gitignore re-includes *_coefficients.csv at any
# depth) so the Colab multi-account export clones them directly — do NOT depend on
# the models-store symlink for deployment.  Each folder is (re)produced by
# workflow/02-model_fitting.R writing to models/<COEF_TAG>/ (see that script).
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

# The single deployed model used by ALL production prediction/export, across every
# year and worker account.  Chosen P=50 (see docs/03-bpts.md §11 for rationale).
# load_all_coefficients() reads this by default; change this ONE line to redeploy.
DEPLOYED_MODEL = "P050"
COEF_DIR       = MODELS_DIR / DEPLOYED_MODEL

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

# Overflow destination for the early years: the mapbiomas-argentina asset is out of
# space, so 1999–2009 are exported into the mapbiomas-chaco project instead.  NOTE this
# is a LEGACY-ROOTED project — its asset home is `projects/mapbiomas-chaco/` directly,
# with NO `/assets/` segment (verified: `.../assets/FIRE/...` is denied / nonexistent,
# `.../FIRE/...` works).  Same asset-name pattern (bpts_YYYY_<tile-id>).
BP_TS_METRICS_COL_CHACO   = "projects/mapbiomas-chaco/FIRE/bp_ts_metrics"
BP_TS_METRICS_CHACO_YEARS = set(range(1999, 2010))   # 1999–2009 inclusive → chaco


def bpts_target_col(year):
    """Destination ImageCollection for a bpts tile-year: chaco for 1999–2009 (the
    Argentina asset is out of space), the Argentina collection otherwise."""
    return BP_TS_METRICS_COL_CHACO if year in BP_TS_METRICS_CHACO_YEARS else BP_TS_METRICS_COL

# Landsat padding window: how many months of context to pull from the neighbouring
# years (PAD_MONTHS on each side of the focal year), and how many padded observations
# are kept on each side when building the per-pixel array.
#
# Most years need only 2 months to harvest the 3+2 padding obs, and a narrower window
# is much cheaper (fewer scenes → less per-image LR/cloud-mask/plumbing; see
# docs/03-bpts.md §8).  The early Landsat era is sparse (L7 launched mid-1999), so the
# first focal years pad wider to still gather enough context: 1999 → 4 months,
# 2000 → 3 months, 2001+ → 2 months.
PAD_MONTHS_DEFAULT = 2
PAD_MONTHS_BY_YEAR = {1999: 4, 2000: 3}
PAD_OBS_LEFT  = 3   # max prev-year obs pulled into the padded array (K=3 back window)
PAD_OBS_RIGHT = 2   # max next-year obs pulled into the padded array (K=3 forward window)


def pad_months(year):
    """Months of Landsat context to pad before/after a focal year (see above)."""
    return PAD_MONTHS_BY_YEAR.get(year, PAD_MONTHS_DEFAULT)

# CSV prev-block term suffix → MapBiomas mosaic band suffix.
# e.g. 'GREEN_med' (CSV) → mb_mos_green_median (mosaic band).  Used when parsing
# the fitted coefficients into GEE feature names.
PREV_SUFFIX_MAP = {
    "med": "median",
    "wet": "median_wet",
    "dry": "median_dry",
    "sd":  "stdDev",
}
