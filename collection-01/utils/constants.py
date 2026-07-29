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

# ─── Step 04 — SNIC burned-area segmentation (fire-year) ─────────────────────
# Config for workflow/04-snic.py.  Kept here (not in the script) so a new
# collection re-tunes settings in ONE place; the script holds only procedure.
# See docs/04-snic.md for the design behind every value below.
#
# SYNC: the seed/candidate thresholds (VEG_TABLE + the G_* global cuts) are
# hand-copied from the fuego JS tuning script `explore_snic_IB-02` (last synced
# 2026-07-21) and also mirrored in `explore_snic_IB-03` / `explore_snic_asset`.
# There is NO automatic
# sync between the fuego JS repo and this repo — if the JS thresholds change,
# update these to match (docs/04-snic.md §6, Tools / SYNC).

# Output ImageCollection (asset name pattern: snic_<fire_year>; --test → snic_test_<fy>).
SNIC_COL = f"{_FIRE_ROOT}/COLLECTION-1/WORKFLOW-EXPORTS/snic"
# Companion ImageCollection with the R-facing per-pixel metric bands, materialized by
# `04-snic.py --to-asset` from the exported candseed asset: abs_date, veg_fire, n and
# the burned_around_<r> context bands. candseed is NOT duplicated here — the direct
# downloader (download_snic.py) re-attaches it from SNIC_COL at download time. Baking
# these to an asset lets the tiled direct download be a cheap pixel READ (no per-tile
# recompute of the §4 construction). Asset pattern: snic_metrics_<fy> / snic_metrics_test_<fy>.
SNIC_METRICS_COL = f"{_FIRE_ROOT}/COLLECTION-1/WORKFLOW-EXPORTS/snic_metrics"
# Drive folder for the R-facing COG export (04-snic.py --to-drive); files are
# named like the assets (snic_<fire_year> / snic_test_<fire_year>).
# GEE's toDrive `folder` is a folder NAME, not a path: it writes into an existing
# Drive folder of that name wherever it lives. This one already exists on the
# comahue account's Drive at MapBiomas/mapbiomas-arg-fire-store/collection-01/data/
# objects-raw, which Insync syncs to STORE_ROOT/collection-01/data/objects-raw.
SNIC_DRIVE_FOLDER = "objects-raw"

# Fire-year calendar (§2): FY Y1 = 1 May Y1 → 30 Apr (Y1+1), named by START year Y1.
FY_START_MONTH = 5
FIRST_FIRE_YEAR, LAST_FIRE_YEAR = 1998, 2025   # start years

# SNIC segmentation params (§4.4 / §6).
SNIC_NEIGHBORHOOD_SIZE = 512   # px; SNIC internal-tile buffer. 15.4 km @30 m.
SNIC_COMPACTNESS = 0
SNIC_CONNECTIVITY = 8
SNIC_SEED_MAX_DROP = 5         # drop seed components with <= this many connected px

# Pixel-level "context_burned" (sparseness): for r in SNIC_CONTEXT_RADII, burned_around_<r> =
# burned-pixel COUNT in the (2r+1)² square window = sum of the 0/1 burned mask
# (reduceNeighborhood). Computed in GEE (ported from collection-00 07-objects_metrics), baked
# into the metrics asset — NOT in terra (a local focal, but terra densifies the grid; docs/05
# §3, §7b). Kept the collection-00 band NAME burned_around_<r>, but its SCALE is a plain int16
# CELL COUNT (max (2r+1)² = 49 at r=3), not the proportion — so the download stays integer with
# no scale factor; R divides by (2r+1)² for the [0,1] proportion (real scar → near 1; speckle →
# low). A burned pixel's own centre keeps count ≥ 1, so 0 stays a safe masked/NoData sentinel.
SNIC_CONTEXT_RADII = (1, 2, 3)

# bpts probability bands decode_bpts rescales (÷10000 → probability); rest as-is.
SNIC_PROB_BANDS = ["delta3_peak", "minfore3_peak", "delta2_peak", "minfore2_peak",
                   "pmax3", "pmax2", "pmax1"]

# Candidate is always the K=2 delta form (4-value candidate); see classify_image.
CAND_FORCE_K2 = True

# GLOBAL hand-set delta cuts (decoded probability 0..1), per K: [candidate, seed].
G_K2_CAND, G_K2_SEED = 0.25, 0.90
G_K3_CAND, G_K3_SEED = 0.25, 0.75

# Per-veg thresholds: [code, n_break, k2_cand, k2_seed, k3_cand, k3_seed].
#   code     = veg_fire class (see config/veg_fire_remap.csv)
#   n_break  = obs count (`n`) at/above which a pixel uses the K=3 fit, not K=2
#   k*_cand / k*_seed = delta cut for candidate / seed at that K; None = use G_*
VEG_TABLE = [
    [1,  100, 0.5, 0.98, 0.5, 0.98],   # agriculture_chaco
    [2,  100, 0.5, 0.98, 0.5, 0.98],   # agriculture_cuyo-pat
    [3,  100, 0.5, 0.98, 0.5, 0.98],   # agriculture_pampa
    [4,   48, None, None, None, None],  # agriculture-per_chaco-ba
    [5,   46, None, None, None, None],  # forest_ba
    [6,   34, None, None, None, None],  # forest_cuyo
    [7,   49, None, None, None, None],  # forest_pampa
    [8,    7, None, None, None, None],  # forest_pat
    [9,   35, None, None, None, None],  # forest-cerr_chaco
    [10,  32, None, None, None, None],  # forest-inund-chaco
    [11,  31, None, None, None, None],  # forest-open_chaco
    [12, 100, None, None, None, None],  # grassland_ba
    [13, 100, 0.5, 0.98, 0.5, 0.98],   # grassland_chaco
    [14,  30, None, None, None, None],  # grassland_cuyo
    [15, 100, None, None, None, None],  # grassland_pampa
    [16,  20, None, None, None, None],  # grassland_pat (steppe)
    [17, 100, 0.5, 0.98, 0.5, 0.98],   # grassland-inund_chaco
    [18, 100, None, None, None, None],  # pasture_ba
    [19, 100, None, None, None, None],  # pasture_chaco
    [20,  35, None, None, None, None],  # shrubland_cuyo-pampa
    [21,  30, 0.2, None, None, None],   # shrubland_pat (K2_cand override 0.2)
    [22,  21, None, None, None, None],  # shrubland-closed_chaco
    [23,  23, None, None, None, None],  # shrubland-open_chaco
]
# Column indices into a VEG_TABLE row.
VEG_COL_CODE, VEG_COL_NBREAK, VEG_COL_K2C, VEG_COL_K2S, VEG_COL_K3C, VEG_COL_K3S = 0, 1, 2, 3, 4, 5

# Defaults for veg not in VEG_TABLE (non-burnable 24 / non-observed 25 / unmapped):
# NBREAK huge -> always K2; THR 9 -> no delta ever passes -> no fire on non-veg.
NBREAK_DEF, THR_DEF = 99999, 9

# Seed temporal-gap ceiling (days): reject seeds where min(jumpgap2, jumpgap3) > gap.
# Denser pixels (n >= N_DENSE) get the tighter ceiling.
S_GAP_DENSE, S_GAP_SPARSE, N_DENSE = 60, 90, 20

# Patagonia slow-dieback forward padding (§4.3): a candidate/seed in the NEXT-year
# (Y2) image with mid-date in [PAD_MONTH_LO, PAD_MONTH_HI] of Y2, west of
# PAT_LON_MAX, in a Patagonia forest/shrubland class, becomes candseed=3 where
# the fire-year focal value is 0.
PAD_MONTH_LO, PAD_MONTH_HI = 6, 11
PAT_LON_MAX = -70.3
PAT_VEG_CODES = [8, 21]        # forest_pat (8), shrubland_pat (21)

# San Ramón exception (fire-year 1998 only; §4.5): inside SAN_RAMON_RECT, also
# accept high max-probability pixels as candidates (the sparse Jan-Apr 1999 fire).
SAN_RAMON_FIRE_YEARS = [1998]
SAN_RAMON_PMAX_BAND = "pmax3"
SAN_RAMON_PMAX_MIN = 0.3
SAN_RAMON_RECT_COORDS = [[[-71.1795629588502, -40.836670267693194],
                          [-71.1795629588502, -41.21017094506833],
                          [-70.79641476549082, -41.21017094506833],
                          [-70.79641476549082, -40.836670267693194]]]

# Tiny ROI for a --test export (near San Ramón: exercises the Patagonia padding
# and the San Ramón exception on a fast, small extent).
TEST_ROI_COORDS = [[[-71.04026772918293, -41.14289047797963],
                    [-71.04026772918293, -41.18424486013236],
                    [-70.96885659637043, -41.18424486013236],
                    [-70.96885659637043, -41.14289047797963]]]

# ─── Step 06 — uploaded object FeatureCollections ─────────────────────────────
# One FC per fire-year, the WHOLE object set with all 20 predictors and the three
# call columns (docs/06 §12).  Field names are the <=10-char Shapefile ones from
# scripts/objects_upload.py::RENAME — `fire`, `area_ha`, `date_med`, `year_cal`.
OBJECTS_RAW_COL = f"{_FIRE_ROOT}/COLLECTION-1/WORKFLOW-EXPORTS/objects_raw"

# ─── Step 07 — calendar-year products (month of burn, scars) ──────────────────
# See docs/07-vector_to_raster.md.  The published series is CALENDAR years, built
# from the non-calendar fire-year objects: calendar Y = Jan-Apr Y (from FY Y-1)
# ⊎ May-Dec Y (from FY Y).  Verified over all 28 fire-years: no object's date range
# leaves its own fire-year window, so the two contributions are a strict partition
# and merging them is a union, not an arbitration (the only overlap is real reburn,
# where the later date wins).  EXCEPT for candseed==3 dieback pixels, whose own
# abs_date is a NEXT-year spring date and does leave the window — hence the general
# `date in [Y, Y+1)` test per fire-year, never a "Jan-Apr only" shortcut.
CALENDAR_YEARS = list(range(1999, 2026))   # 1999-2025, matches YEARS

# Minimum mapped fire: an OBJECT (fire-year entity) must reach this to contribute
# any pixel (docs/07 §1).  Applied on the object, before the calendar-year split, so
# a calendar-year part of a qualifying object may itself be smaller.
MIN_FIRE_HA = 1.0

# The canonical 30 m grid of every SNIC asset.  VERIFIED 2026-07-29: all 56 assets
# (28 `snic_<fy>` + 28 `snic_metrics_<fy>`) share this exact crs + transform, and the
# per-carta tiles in data/snic-rasters/ sit on the same lattice (offset 22578 columns,
# 0 rows).  PIN THIS ON EVERY EXPORT.  `scale: 30` in EPSG:4326 — what all the
# reference scripts use — is a DIFFERENT grid (origin 0,0 and a different degree step),
# and a half-pixel shift would misalign the painted rasters from the month raster.
SNIC_CRS = "EPSG:4326"
SNIC_TRANSFORM = [0.000269494585236, 0, -73.58468801489491,
                  0, -0.000269494585236, -21.764113209062533]

# `abs_date` (SNIC metrics) is whole days since this epoch — same encoding as
# 05-objects_metrics.R::EPOCH.
EPOCH = "1970-01-01"

# Patagonia dieback longitude cut, MIRRORED from 05-objects_metrics.R::DIEBACK_LON_CUT.
# Step 05 dropped candseed==3 pixels EAST of this before labelling, so the objects were
# built without them — but the `snic_<fy>` asset still carries them (65,752 px over the
# 28 fire-years).  GEE must replay the cut or the painted pixel set is not the one the
# objects describe.  KEEP IN SYNC with the R constant.
DIEBACK_LON_CUT = -70.6

# candseed==3 dieback pixels take their PARENT OBJECT's median date, not their own
# abs_date (docs/07 §4.3).  Their own date is a next-year spring DIEBACK-detection date,
# a different physical event from the burn — Jun-Nov, measured: 881k such pixels (~79 kha)
# survive the longitude cut over the 28 fire-years, 4.0 % of all candidate pixels west of
# the cut and 14-18 % in FY2014/2015/2021/2024.  Left raw they would (a) report Andean
# Patagonia burning in austral winter and (b) fall into the NEXT calendar year whenever the
# parent fire burned May-Dec, splitting the scar and minting a phantom scar with its own id
# and size class.  Substituting costs nothing (`date_med` is already a property on the
# uploaded FCs) and no pixel that has a real measured date is touched.
# 36 objects in the whole collection are ALL dieback, so their `date_med` is null (<=4 ha
# total); they carry no usable date and are excluded outright.
DIEBACK_USE_PARENT_DATE = True

# Destination for the month-of-burn collection — the network's stage-3 pivot, one image per
# calendar year, value 1-12 = month of burn, masked elsewhere.  Kept under OUR `COLLECTION-1`
# spelling (docs/08 open decision #1); the asset NAMES inside follow the network exactly, and
# the mapbiomas-public copy is renamed at publish time.
# The name says `mask` because that is what every downstream reference script reads, but for
# Argentina the LULC mask is a NO-OP applied upstream, not skipped: `veg_fire` comes from the
# previous-year MapBiomas LULC and every non-burnable class is unreachable as a SNIC candidate
# (no VEG_TABLE entry -> THR_DEF = 9 -> no delta passes).  Verified on FY2000/2014/2023: zero
# candseed>0 pixels on veg_fire 24 (non-burnable) or 25 (non-observed).  That is STRICTER than
# the reference rule, which drops water (26) only.  Recorded as the `lulc_mask` property.
CLASSIFICATION_COLLECTIONS = f"{_FIRE_ROOT}/COLLECTION-1/CLASSIFICATION_COLLECTIONS"
MONTH_OF_BURN_COL = f"{CLASSIFICATION_COLLECTIONS}/collection1_fire_mask_v1"
MONTH_OF_BURN_BAND = "burned_monthly"

# Final products + the calendar-year scar vectors that feed the scar-size chain.
FINAL_PRODUCTS = f"{_FIRE_ROOT}/COLLECTION-1/FINAL_PRODUCTS"
ANNUAL_BURNED_VECTORS = f"{FINAL_PRODUCTS}/annual_burned_vectors"

# Scar-size classes 1..8 — LOWER bounds in ha.  These are the classes the PUBLISHED PLATFORM
# legend defines, confirmed 2026-07-29 from two independent sources:
#   * "CODIGO DE LEGENDA FOGO COLECAO 5" (brasil.mapbiomas.org, May 2026): 1 '< 10 ha',
#     2 '10 - 250 ha', 3 '250 - 500 ha', 4 '500 - 5.000 ha', 5 '5.000 - 10.000 ha',
#     6 '10.000 - 50.000 ha', 7 '50.000 - 100.000 ha', 8 '>= 100.000 ha'.
#   * the live MapBiomas Fogo col-5 platform legend (launched July 2026), which is TWO-LEVEL:
#     level 2 is the 8 classes above; level 1 aggregates them into <250 / 250-500 /
#     500-10.000 / 10.000-100.000 / >100.000 ha.  We write ONLY level 2 (1-8), exactly as
#     Brazil's own asset does; the platform derives level 1.
#
# ⚠️ DO NOT copy the LatAm reference script `6-export_scar_size_range_by_year`.  It writes
# <5 / 5-25 / 25-50 / 50-250 / 250-500 / 500-1000 / 1000-5000 / >=5000 onto the SAME pixel
# values 1-8, which does NOT match the legend the platform renders — a raster built with the
# script and registered with the legend is silently mislabelled in every class (docs/08 §5.4).
#
# docs/08 previously guessed the reference ranges were "almost certainly right for us" because
# Brazil's are tuned to Amazon-scale scars.  MEASURED over all 27 calendar years (2,734,416
# scars, 69,020,102 ha), that guess was wrong — the Brazil scheme populates ALL 8 classes here,
# because Argentina does reach the top bin (24 scars >= 100,000 ha, largest 219,410 ha in 2003):
#     <10 ha  76.14 % of scars /  5.67 % of area      5k-10k    0.02 % /  5.48 %
#     10-250  22.78 %           / 35.41 %             10k-50k   0.02 % / 11.57 %
#     250-500  0.57 %           /  7.71 %             50k-100k  0.00 % /  4.47 %
#     500-5k   0.48 %           / 22.85 %             >=100k    0.00 % /  6.83 %
# The count is concentrated in class 1 (small fires dominate everywhere), but the AREA spreads
# across all eight, which is what the product is read for.  Legend compatibility decides this
# anyway: the pixel values must mean what the registered legend says.
SCAR_SIZE_LOWER_HA = [10, 250, 500, 5000, 10000, 50000, 100000]

# Common property block for every step-07/08 output (the reference's stage-3 block).
PRODUCT_SOURCE = "mapbiomas-fuego"
PRODUCT_REGION = "argentina"   # one image per year, whole country: our predictions are tiled
                               # by cartas, not by the network's fire regions


def product_name(subproduct, collection=1, version=1):
    """Network-standard asset name, e.g.
    ``mapbiomas_argentina_fire_collection1_annual_burned_v1``."""
    return (f"mapbiomas_{PRODUCT_REGION}_fire_collection{collection}"
            f"_{subproduct}_v{version}")
