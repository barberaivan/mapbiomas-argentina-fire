"""
collection-01/utils/functions.py

GEE helper functions shared across the collection-01 workflow.
Ported from collection-00/utils/functions.js, keeping only what is needed.
"""

import csv
from pathlib import Path

import ee

from utils import constants as C

# ─── Harmonization (Roy et al. 2016): ETM+ → OLI ─────────────────────────────
# Kept as plain lists; ee.Image.constant() is called inside _harmonize_etm so
# that ee.Initialize() has already run before these are evaluated.
_ETM_SLOPES_RAW = [0.8474, 0.8483, 0.9047, 0.8462, 0.8937, 0.9071]
_ETM_ITCPS_RAW  = [0.0003, 0.0088, 0.0061, 0.0412, 0.0254, 0.0172]

_OPT_BANDS = ["BLUE", "GREEN", "RED", "NIR", "SWIR1", "SWIR2"]


def _rename_l5_l7(img):
    return img.select(
        ["SR_B1", "SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B7", "QA_PIXEL"],
        ["BLUE",  "GREEN",  "RED",   "NIR",   "SWIR1", "SWIR2", "QA_PIXEL"],
    )


def _rename_l8_l9(img):
    return img.select(
        ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7", "QA_PIXEL"],
        ["BLUE",  "GREEN",  "RED",   "NIR",   "SWIR1", "SWIR2", "QA_PIXEL"],
    )


def _mask_clouds(img):
    """Mask cloud, cloud-shadow, snow, and water pixels (Landsat C2 QA_PIXEL)."""
    qa = img.select("QA_PIXEL")
    bad = (
        qa.bitwiseAnd(1 << 1)         # dilated cloud
        .Or(qa.bitwiseAnd(1 << 2))    # cirrus
        .Or(qa.bitwiseAnd(1 << 3))    # cloud
        .Or(qa.bitwiseAnd(1 << 4))    # shadow
        .Or(qa.bitwiseAnd(1 << 5))    # snow
        .Or(qa.bitwiseAnd(1 << 7))    # water
    )
    return img.updateMask(bad.Not())


def _harmonize_etm(img):
    """Scale and harmonize ETM+ (Landsat 5/7) bands to OLI equivalent."""
    slopes = ee.Image.constant(_ETM_SLOPES_RAW)
    itcps  = ee.Image.constant(_ETM_ITCPS_RAW)
    orig = img
    img = (
        _rename_l5_l7(img)
        .select(_OPT_BANDS)
        .multiply(0.0000275).add(-0.2)
        .multiply(slopes).add(itcps)
        .toFloat()
    )
    return img.addBands(orig.select("QA_PIXEL")).copyProperties(orig, orig.propertyNames())


def _prep_oli(img):
    """Scale OLI (Landsat 8/9) bands to surface reflectance."""
    orig = img
    img = _rename_l8_l9(img).multiply(0.0000275).add(-0.2).toFloat()
    return img.copyProperties(orig, orig.propertyNames())


def get_landsat(roi, start_date, end_date):
    """
    Load and merge Landsat 5/7/8/9 C2 T1 L2, cloud-masked and harmonized to OLI.

    Parameters
    ----------
    roi        : ee.Geometry or ee.FeatureCollection used as spatial filter
    start_date : str or ee.Date, inclusive
    end_date   : str or ee.Date, exclusive

    Returns
    -------
    ee.ImageCollection with bands BLUE, GREEN, RED, NIR, SWIR1, SWIR2
    and a 'sensor' property ('LT05', 'LE07', 'LC08', 'LC09') on each image.
    """
    col_filter = ee.Filter.And(
        ee.Filter.bounds(roi),
        ee.Filter.date(start_date, end_date),
    )
    ls5 = (ee.ImageCollection("LANDSAT/LT05/C02/T1_L2")
           .filter(col_filter).map(_mask_clouds).map(_harmonize_etm)
           .map(lambda img: img.set("sensor", "LT05")))
    ls7 = (ee.ImageCollection("LANDSAT/LE07/C02/T1_L2")
           .filter(col_filter).map(_mask_clouds).map(_harmonize_etm)
           .map(lambda img: img.set("sensor", "LE07")))
    ls8 = (ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
           .filter(col_filter).map(_mask_clouds).map(_prep_oli)
           .map(lambda img: img.set("sensor", "LC08")))
    ls9 = (ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")
           .filter(col_filter).map(_mask_clouds).map(_prep_oli)
           .map(lambda img: img.set("sensor", "LC09")))
    return (ls5.merge(ls7).merge(ls8).merge(ls9)
            .select(_OPT_BANDS))


def add_indices(img):
    """
    Compute and add all 21 focal-date spectral features.

    Input image must have bands: BLUE, GREEN, RED, NIR, SWIR1, SWIR2.
    Adds: NBR, NBR2, MIRBI, NDVI, TCB, TCG, TCW, NDMI, NDSI, SAVI, NDWI,
    AFRI, kNDVI, EVI2, NIRv.
    MIRBI is NOT sign-flipped (raw formula).
    AFRI is the 2.1 µm / 0.5-coefficient variant (Karnieli et al. 2001, Eq. 11a).
    """
    b = img.select("BLUE")
    g = img.select("GREEN")
    r = img.select("RED")
    n = img.select("NIR")
    s1 = img.select("SWIR1")
    s2 = img.select("SWIR2")

    nbr  = img.normalizedDifference(["NIR", "SWIR2"]).rename("NBR")
    nbr2 = img.normalizedDifference(["SWIR1", "SWIR2"]).rename("NBR2")
    ndvi = img.normalizedDifference(["NIR", "RED"]).rename("NDVI")
    mirbi = img.expression("10*S2 - 9.8*S1 + 2", {"S1": s1, "S2": s2}).rename("MIRBI")

    # Tasseled-cap (Baig et al. 2014, OLI coefficients)
    tcb = img.expression(
        "0.3029*B + 0.2786*G + 0.4733*R + 0.5599*N + 0.5080*S1 + 0.1872*S2",
        {"B": b, "G": g, "R": r, "N": n, "S1": s1, "S2": s2},
    ).rename("TCB")
    tcg = img.expression(
        "-0.2941*B - 0.2430*G - 0.5424*R + 0.7276*N + 0.0713*S1 - 0.1608*S2",
        {"B": b, "G": g, "R": r, "N": n, "S1": s1, "S2": s2},
    ).rename("TCG")
    tcw = img.expression(
        "0.1511*B + 0.1973*G + 0.3283*R + 0.3407*N - 0.7117*S1 - 0.4559*S2",
        {"B": b, "G": g, "R": r, "N": n, "S1": s1, "S2": s2},
    ).rename("TCW")

    ndmi = img.normalizedDifference(["NIR", "SWIR1"]).rename("NDMI")  # same formula as col0 ndwi_gao
    ndsi = img.normalizedDifference(["GREEN", "SWIR1"]).rename("NDSI")
    savi = img.expression(
        "1.5 * (N - R) / (N + R + 0.5)", {"N": n, "R": r}
    ).rename("SAVI")
    ndwi = img.normalizedDifference(["GREEN", "NIR"]).rename("NDWI")  # McFeeters 1996, water

    # ─── Canonical-team additions (logistic_regression_design.qmd §"Spectral feature equations") ──
    # AFRI uses the 2.1 µm (SWIR2) form with the 0.5 coefficient (Karnieli et al.
    # 2001, Eq. 11a = AFRI_2.1) — the variant that best penetrates smoke/aerosol.
    afri  = img.expression(
        "(N - 0.5*S2) / (N + 0.5*S2)", {"N": n, "S2": s2}
    ).rename("AFRI")
    kndvi = ndvi.pow(2).tanh().rename("kNDVI")                 # tanh(NDVI^2), Camps-Valls 2021
    evi2  = img.expression(
        "2.5 * (N - R) / (N + 2.4*R + 1)", {"N": n, "R": r}
    ).rename("EVI2")
    nirv  = n.multiply(ndvi).rename("NIRv")                    # NIR × NDVI, Badgley 2017

    return img.addBands([nbr, nbr2, ndvi, mirbi, tcb, tcg, tcw, ndmi, ndsi, savi, ndwi,
                         afri, kndvi, evi2, nirv])


def get_mb_class_band(lulc_img, mb_year):
    """
    Return a single-band image with the raw MapBiomas land-cover class for
    mb_year.  Caller is responsible for passing the correct previous year
    (mb_year = obs_year - 1).

    Band: 'mb_class_raw'.  Reclassification to fire-vegetation classes is
    deferred to model-fitting time using the per-region table in Google Sheets.
    """
    return lulc_img.select(f"classification_{mb_year}").rename("mb_class_raw")


def get_mb_mosaic_bands(mosaic_col, mb_year, roi, bands):
    """
    Return the MapBiomas mosaic image for mb_year, selecting only `bands`
    before mosaicking and renaming to 'mb_mos_<band>'.  Caller is responsible
    for passing the correct previous year (mb_year = obs_year - 1).
    """
    mosaic = (
        mosaic_col
        .filter(ee.Filter.eq("year", mb_year))
        .filter(ee.Filter.bounds(roi))
        .select(bands)
        .mosaic()
    )
    prefixed = [f"mb_mos_{b}" for b in bands]
    return mosaic.rename(prefixed)


def assign_point_ids(fc):
    """
    Assign a sequential integer 'point_id' (0-based) to each feature in fc.
    Overwrites any existing point_id.
    """
    fc_list = fc.toList(fc.size())
    ids = ee.List.sequence(0, fc.size().subtract(1))

    def _set_id(z):
        z = ee.List(z)
        return ee.Feature(z.get(1)).set("point_id", ee.Number(z.get(0)).int())

    return ee.FeatureCollection(ids.zip(fc_list).map(_set_id))


# ═══════════════════════════════════════════════════════════════════════════
# Step 03 — burn-probability time-series metrics
# ═══════════════════════════════════════════════════════════════════════════
#
# The fitted logistic regression (step 02) is a plain linear predictor on the
# RAW band scale (no centering/standardisation before products — the centering
# used while fitting is already folded into the intercept and main slopes; see
# models/README.md). So predicting burn probability in GEE is just:
#
#     eta  = intercept
#          + Σ prev_coef  · mb_mosaic_band                       (prev mains)
#          + Σ focal_coef · landsat_band                         (focal mains)
#          + Σ pairs_coef · focal_f1 · focal_f2                  (focal×focal)
#          + Σ cross_coef · mb_mosaic_f1 · landsat_f2            (prev×focal)
#     prob = 1 / (1 + exp(-eta))
#
# Each coefficient depends on the pixel's veg_fire class, so we turn the 23
# per-class coefficient vectors into a 130-band "coefficient image" by remapping
# veg_fire → coefficient, band by band.  The prev-only part of `eta` and the
# prev factor of every cross term are time-invariant within a year, so we
# precompute them once and reuse them for every Landsat image in the series.


# ─── Coefficient loading (pure Python, no ee) ────────────────────────────────

def _parse_feature(token):
    """
    Map one CSV factor token to its GEE feature band name and source.

    Focal factors carry the ``_t`` suffix and use the raw spectral-index name
    produced by ``add_indices`` (``BLUE_t`` → ``BLUE``).  Prev factors carry a
    summary suffix (``med``/``wet``/``dry``/``sd``) and map to a MapBiomas mosaic
    band (``GREEN_med`` → ``mb_mos_green_median``), matching the names produced
    by ``get_mb_mosaic_bands``.

    Returns ``(feature_name, src)`` with ``src`` in {'focal', 'prev'}.
    """
    if token.endswith("_t"):
        return token[:-2], "focal"                      # BLUE_t  → BLUE  (focal)
    base, suffix = token.rsplit("_", 1)                 # GREEN_med → GREEN, med
    mb_band = f"mb_mos_{base.lower()}_{C.PREV_SUFFIX_MAP[suffix]}"
    return mb_band, "prev"                              # → mb_mos_green_median


def _parse_term(block, term):
    """
    Parse one CSV (block, term) into the structure the GEE builders need.

    Returns a dict with:
      block     : the CSV block name (drives which contribution group it joins)
      term      : the original CSV term (kept for reference)
      band_name : a GEE-safe band name for this term's coefficient
      factor1   : first feature name (or None for the intercept)
      f1_src    : 'focal' / 'prev' / None
      factor2   : second feature name (only for product terms; else None)
    """
    if block == "(intercept)":
        return {"block": block, "term": term, "band_name": "intercept_term",
                "factor1": None, "f1_src": None, "factor2": None}

    # CSV term names (e.g. 'BLUE_t', 'NDVI_med__RED_t') are already valid GEE
    # band names — only the intercept's parentheses would be illegal.
    band_name = term
    if "__" in term:                                    # product term: f1 · f2
        left, right = term.split("__")
        f1, s1 = _parse_feature(left)
        f2, _  = _parse_feature(right)                  # f2 is always focal here
        return {"block": block, "term": term, "band_name": band_name,
                "factor1": f1, "f1_src": s1, "factor2": f2}
    f1, s1 = _parse_feature(term)                       # main effect: single factor
    return {"block": block, "term": term, "band_name": band_name,
            "factor1": f1, "f1_src": s1, "factor2": None}


def load_all_coefficients(models_dir=None, classes=None):
    """
    Read every per-class coefficient CSV and return one list of term dicts.

    Each term dict is the parsed structure from ``_parse_term`` plus a ``coefs``
    mapping {veg_fire_class: float} holding that term's RAW coefficient for all
    fittable classes.  All class CSVs are required to share the same term order;
    a mismatch raises (so a stale/partial export is caught early).

    Parameters
    ----------
    models_dir : Path or str, optional — defaults to ``C.MODELS_DIR``
    classes    : list[int], optional   — defaults to ``C.FITTABLE_VEG_FIRE``

    Returns
    -------
    list[dict] — 130 term dicts in CSV order (the order is reused everywhere so
    coefficient bands and feature bands stay aligned).
    """
    models_dir = Path(models_dir) if models_dir is not None else C.MODELS_DIR
    classes = list(classes) if classes is not None else list(C.FITTABLE_VEG_FIRE)

    terms = None            # canonical term list (from the first class read)
    key_order = None        # list of (block, term) used to enforce identical order

    for cls in classes:
        path = models_dir / f"class_{cls:02d}_coefficients.csv"
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        keys = [(r["block"], r["term"]) for r in rows]
        if terms is None:
            # First class: build the parsed skeleton and remember the order.
            key_order = keys
            terms = [_parse_term(r["block"], r["term"]) for r in rows]
            for t in terms:
                t["coefs"] = {}
        elif keys != key_order:
            raise ValueError(
                f"class_{cls:02d} term order differs from class_{classes[0]:02d} "
                f"— refit/export is inconsistent"
            )

        for t, r in zip(terms, rows):
            t["coefs"][cls] = float(r["coefficient"])

    return terms


# ─── GEE coefficient / linear-predictor image building ───────────────────────

def build_coeff_image(veg_fire_img, terms, classes=None):
    """
    Build a 130-band image where each band holds, per pixel, the coefficient of
    one term for that pixel's veg_fire class.

    Implemented as one ``remap`` per term: veg_fire class → coefficient, with a
    default of 0.0 for any non-fittable class (so non-fittable pixels contribute
    nothing and are masked out separately before prediction).
    """
    classes = list(classes) if classes is not None else list(C.FITTABLE_VEG_FIRE)
    bands = []
    for t in terms:
        coef_values = [t["coefs"][c] for c in classes]
        band = veg_fire_img.remap(classes, coef_values, 0.0).rename(t["band_name"])
        bands.append(band)
    return ee.Image.cat(bands)


def _select_renamed(img, terms, factor_key):
    """
    Select the ``factor_key`` ('factor1'/'factor2') feature of each term from
    ``img`` and rename the selected bands to the terms' coefficient band names.

    Renaming to identical names (in identical order) makes the subsequent
    band-wise multiply unambiguous: coefficient bands and feature bands line up
    by name AND by position, so the product is correct regardless of how GEE
    matches bands.
    """
    feat_names = [t[factor_key] for t in terms]
    band_names = [t["band_name"] for t in terms]
    return img.select(feat_names, band_names)


def build_prev_scalar(coeff_img, mb_mosaic_img, terms):
    """
    Build the time-invariant part of the linear predictor: the intercept plus
    every prev-block main effect (prev_coef · mb_mosaic_band), summed.

    Computed once per year and added to every Landsat image's predictor.
    Returns a single-band image 'prev_scalar'.
    """
    prev_terms = [t for t in terms if t["block"] == "prev"]
    names = [t["band_name"] for t in prev_terms]
    coef = coeff_img.select(names)
    feat = _select_renamed(mb_mosaic_img, prev_terms, "factor1")
    prev_sum = coef.multiply(feat).reduce(ee.Reducer.sum())
    return coeff_img.select("intercept_term").add(prev_sum).rename("prev_scalar")


def build_cross_factor1_coef(coeff_img, mb_mosaic_img, terms):
    """
    Precompute, for every cross term (sameband / cross_idx / cross_band), the
    product ``prev_factor · coefficient`` as a multi-band image.

    Cross terms are prev×focal: only the prev factor and the coefficient are
    time-invariant, so we fold them together once per year.  At runtime each
    band is multiplied by its focal factor (see ``compute_burn_prob_img``).
    Bands are named by the terms' coefficient band names, in cross-term order.
    """
    cross_terms = [t for t in terms if t["block"] in ("sameband", "cross_idx", "cross_band")]
    names = [t["band_name"] for t in cross_terms]
    coef = coeff_img.select(names)
    feat1 = _select_renamed(mb_mosaic_img, cross_terms, "factor1")
    return coef.multiply(feat1)            # band names kept from `coef` (term names)


def _day_num(img, focal_year):
    """
    Integer day-number of an image's date relative to Jan 1 of the focal year,
    using EE's exact, calendar-aware ``'day'`` unit.

    Focal-year obs get 0..365 (so DOY = ``day_num + 1``); prev-year padding obs
    are negative (e.g. Dec y-1 ≈ -12) and next-year padding obs are > 365 — so
    date *differences* are exact integer day counts that stay correct across the
    year boundary.  This replaces the old fractional-year column, which divided
    elapsed time by EE's fixed 365.2425-day mean year and so could not yield
    exact whole-day gaps or an exact day-of-year.
    """
    d = ee.Date(img.get("system:time_start"))
    day_num = d.difference(ee.Date.fromYMD(focal_year, 1, 1), "day")
    return ee.Image.constant(day_num).toFloat().rename("day_num")


def compute_burn_prob_img(img, prev_scalar, coeff_img, cross_f1_coef_img, terms,
                          focal_year):
    """
    Compute burn probability for one Landsat image (with spectral indices added).

    Returns a 2-band image ['prob', 'day_num'] where ``day_num`` is the date as
    integer days relative to Jan 1 of ``focal_year`` (see ``_day_num``).  Both
    bands carry the image's valid-data mask, so cloudy / no-data pixels are
    excluded from the per-pixel array later — never assigned a spurious
    probability.

    Predictors are used on their RAW scale (no centering/standardisation).
    """
    # Focal main effects: focal_coef · focal_band.
    focal_terms = [t for t in terms if t["block"] == "focal"]
    fc_names = [t["band_name"] for t in focal_terms]
    focal_main = (coeff_img.select(fc_names)
                  .multiply(_select_renamed(img, focal_terms, "factor1"))
                  .reduce(ee.Reducer.sum()))

    # Focal×focal pairs: pairs_coef · f1 · f2.
    pair_terms = [t for t in terms if t["block"] == "pairs"]
    pr_names = [t["band_name"] for t in pair_terms]
    pairs_contrib = (coeff_img.select(pr_names)
                     .multiply(_select_renamed(img, pair_terms, "factor1"))
                     .multiply(_select_renamed(img, pair_terms, "factor2"))
                     .reduce(ee.Reducer.sum()))

    # Prev×focal cross terms: (prev_coef · prev_f1) · focal_f2.  The prev part is
    # already folded into cross_f1_coef_img; multiply by the focal factor here.
    cross_terms = [t for t in terms if t["block"] in ("sameband", "cross_idx", "cross_band")]
    cross_contrib = (cross_f1_coef_img
                     .multiply(_select_renamed(img, cross_terms, "factor2"))
                     .reduce(ee.Reducer.sum()))

    eta = prev_scalar.add(focal_main).add(pairs_contrib).add(cross_contrib)
    prob = eta.multiply(-1).exp().add(1).pow(-1).rename("prob")   # logistic
    day = _day_num(img, focal_year).updateMask(prob.mask())       # same mask as prob
    # Carry system:time_start so the caller can filterDate() the resulting
    # collection into prev / focal / next windows (a fresh image would lose it).
    return prob.addBands(day).set("system:time_start", img.get("system:time_start"))


# ─── Landsat time-series assembly ────────────────────────────────────────────

def mosaic_by_date(imgcol):
    """
    Collapse images sharing the same calendar date into one (mean reducer), so
    overlapping Landsat scenes on the same day do not produce duplicate
    observations.  A single-image date is unchanged by the mean.

    Returns an ImageCollection sorted by time, with one image per unique date.
    """
    def _tag(img):
        return img.set("ymd", ee.Date(img.get("system:time_start")).format("YYYY-MM-dd"))

    tagged = imgcol.map(_tag)
    dates = tagged.aggregate_array("ymd").distinct()

    def _mosaic_one(ymd):
        ymd = ee.String(ymd)
        day = ee.Date.parse("YYYY-MM-dd", ymd)
        return (tagged.filter(ee.Filter.eq("ymd", ymd))
                .mean()
                .set("system:time_start", day.millis(), "ymd", ymd))

    return ee.ImageCollection(dates.map(_mosaic_one)).sort("system:time_start")


def safe_to_array(imgcol):
    """
    Convert a 2-band [prob, day_num] ImageCollection (already sorted by time)
    into an [N×2] array image, robust to a globally-empty collection.

    ``toArray`` stacks images along axis 0 and bands along axis 1 → [N, 2].  The
    catch: an *empty* ee.Array cannot stay 2-D — slicing any array down to zero
    rows collapses it to 1-D, which then breaks the ``arraySlice(1, …)`` calls in
    ``compute_bp_ts_metrics``.  So instead of an empty stub we prepend one
    fully-masked 2-band sentinel image: the collection is never empty (toArray is
    always statically 2-D), and because the sentinel is masked everywhere it
    contributes no per-pixel array elements — pixels with no real observation
    just come back masked (length 0), exactly as before.
    """
    sentinel = (ee.Image.constant([0.0, 0.0]).rename(["prob", "day_num"]).toFloat()
                .updateMask(ee.Image.constant(0))          # masked everywhere
                .set("system:time_start", 0))
    return ee.ImageCollection([sentinel]).merge(imgcol).toArray()


# ─── Per-pixel time-series → annual metrics ──────────────────────────────────

def compute_bp_ts_metrics(focal_arr, prev_arr, next_arr):
    """
    Reduce per-pixel burn-probability time-series arrays to 18 annual metric
    bands.  All arrays are [N, 2] with column 0 = prob, column 1 = day-number
    (integer days relative to focal-year Jan 1; see ``_day_num``), sorted
    ascending by date.  Date differences are therefore exact whole-day counts,
    and ``date_post`` = ``day_num[t*] + 1`` is an exact day-of-year (t* is always
    a focal obs, so it lands in 1..366).

    Two independently padded arrays are built so that fixed-offset array slices
    are always correct for unmasked pixels (see docs/03-bpts.md):

      K=3 array: up to 3 prev + focal + up to 2 next  (delta3 / minfore3 family)
      K=2 array: up to 2 prev + focal + up to 1 next  (delta2 / minfore2 family)

    A pixel is masked for a given window when its padded length is too short to
    define that window — a quality flag, not an error.  The ``n`` band is never
    masked (caller applies the -1/-2 sentinels for non-burnable / non-observed).
    """
    # ── K=3 padded array: [≤3 prev | T focal | ≤2 next] ──────────────────────
    # arraySlice clamps when a side has fewer obs; the length>=6 mask then keeps
    # only pixels wide enough that, after dropping the 3 leading and 2 trailing
    # positions, at least one focal obs with full back/fore context remains.
    prev_tail3 = prev_arr.arraySlice(0, -3)            # last ≤3 prev obs
    next_head2 = next_arr.arraySlice(0, 0, 2)          # first ≤2 next obs
    padded3 = prev_tail3.arrayCat(focal_arr, 0).arrayCat(next_head2, 0)
    padded3 = padded3.updateMask(padded3.arrayLength(0).gte(6))

    p3 = padded3.arraySlice(1, 0, 1)                   # prob column [L, 1]
    d3 = padded3.arraySlice(1, 1, 2)                   # date column [L, 1]

    # Fixed offsets: the focal candidates are positions [3 .. L-3]; for each we
    # read its three back and two forward neighbours by shifting the window.
    p3_b3 = p3.arraySlice(0, 0, -5)   # p[t-3]
    p3_b2 = p3.arraySlice(0, 1, -4)   # p[t-2]
    p3_b1 = p3.arraySlice(0, 2, -3)   # p[t-1]
    p3_f  = p3.arraySlice(0, 3, -2)   # p[t]
    p3_f1 = p3.arraySlice(0, 4, -1)   # p[t+1]
    p3_f2 = p3.arraySlice(0, 5)       # p[t+2]
    d3_b3 = d3.arraySlice(0, 0, -5)   # d[t-3]
    d3_b1 = d3.arraySlice(0, 2, -3)   # d[t-1]
    d3_f  = d3.arraySlice(0, 3, -2)   # d[t]
    d3_f2 = d3.arraySlice(0, 5)       # d[t+2]

    minfore3 = p3_f.arrayCat(p3_f1, 1).arrayCat(p3_f2, 1).arrayReduce(ee.Reducer.min(), [1])
    maxback3 = p3_b3.arrayCat(p3_b2, 1).arrayCat(p3_b1, 1).arrayReduce(ee.Reducer.max(), [1])
    delta3 = minfore3.subtract(maxback3)               # [T_valid, 1]

    # Find t* = argmax(delta3) by sorting the bundle of all quantities-at-t* by
    # delta3 descending and taking the first row.
    bundle3 = (delta3.arrayCat(minfore3, 1)
               .arrayCat(d3_f, 1).arrayCat(d3_b1, 1)
               .arrayCat(d3_b3, 1).arrayCat(d3_f2, 1))                  # [T, 6]
    # Sort rows by delta3 descending and take the top row (the argmax t*).  The
    # sort key must match the array's dimensionality with multiple elements only
    # along the sort axis, so keep it as the [T, 1] column (negated for descending).
    peak3 = bundle3.arraySort(delta3.multiply(-1)).arraySlice(0, 0, 1)

    delta3_peak   = peak3.arrayGet([0, 0]).rename("delta3_peak")
    minfore3_peak = peak3.arrayGet([0, 1]).rename("minfore3_peak")
    d_t3   = peak3.arrayGet([0, 2])
    d_b1_3 = peak3.arrayGet([0, 3])
    d_b3_3 = peak3.arrayGet([0, 4])
    d_f2_3 = peak3.arrayGet([0, 5])
    jumpgap3   = d_t3.subtract(d_b1_3).rename("jumpgap3")      # d[t]-d[t-1], days
    prevwidth3 = d_b1_3.subtract(d_b3_3).rename("prevwidth3")  # d[t-1]-d[t-3], days
    postwidth3 = d_f2_3.subtract(d_t3).rename("postwidth3")    # d[t+2]-d[t], days
    date_post3 = d_t3.add(1).rename("date_post3")              # day-of-year (1..366)

    # ── K=2 padded array: [≤2 prev | T focal | ≤1 next] ──────────────────────
    prev_tail2 = prev_arr.arraySlice(0, -2)
    next_head1 = next_arr.arraySlice(0, 0, 1)
    padded2 = prev_tail2.arrayCat(focal_arr, 0).arrayCat(next_head1, 0)
    padded2 = padded2.updateMask(padded2.arrayLength(0).gte(4))

    p2 = padded2.arraySlice(1, 0, 1)
    d2 = padded2.arraySlice(1, 1, 2)
    p2_b2 = p2.arraySlice(0, 0, -3)   # p[t-2]
    p2_b1 = p2.arraySlice(0, 1, -2)   # p[t-1]
    p2_f  = p2.arraySlice(0, 2, -1)   # p[t]
    p2_f1 = p2.arraySlice(0, 3)       # p[t+1]
    d2_b2 = d2.arraySlice(0, 0, -3)   # d[t-2]
    d2_b1 = d2.arraySlice(0, 1, -2)   # d[t-1]
    d2_f  = d2.arraySlice(0, 2, -1)   # d[t]
    d2_f1 = d2.arraySlice(0, 3)       # d[t+1]

    minfore2 = p2_f.arrayCat(p2_f1, 1).arrayReduce(ee.Reducer.min(), [1])
    maxback2 = p2_b2.arrayCat(p2_b1, 1).arrayReduce(ee.Reducer.max(), [1])
    delta2 = minfore2.subtract(maxback2)

    bundle2 = (delta2.arrayCat(minfore2, 1)
               .arrayCat(d2_f, 1).arrayCat(d2_b1, 1)
               .arrayCat(d2_b2, 1).arrayCat(d2_f1, 1))                  # [T, 6]
    peak2 = bundle2.arraySort(delta2.multiply(-1)).arraySlice(0, 0, 1)

    delta2_peak   = peak2.arrayGet([0, 0]).rename("delta2_peak")
    minfore2_peak = peak2.arrayGet([0, 1]).rename("minfore2_peak")
    d_t2   = peak2.arrayGet([0, 2])
    d_b1_2 = peak2.arrayGet([0, 3])
    d_b2_2 = peak2.arrayGet([0, 4])
    d_f1_2 = peak2.arrayGet([0, 5])
    jumpgap2   = d_t2.subtract(d_b1_2).rename("jumpgap2")      # d[t]-d[t-1], days
    prevwidth2 = d_b1_2.subtract(d_b2_2).rename("prevwidth2")  # d[t-1]-d[t-2], days
    postwidth2 = d_f1_2.subtract(d_t2).rename("postwidth2")    # d[t+1]-d[t], days
    date_post2 = d_t2.add(1).rename("date_post2")              # day-of-year (1..366)

    # ── Whole-series metrics (from the focal array directly) ──────────────────
    p_focal = focal_arr.arraySlice(1, 0, 1)
    d_focal = focal_arr.arraySlice(1, 1, 2)

    pmax1 = p_focal.arrayReduce(ee.Reducer.max(), [0]).arrayGet([0, 0]).rename("pmax1")
    pmax3 = minfore3.arrayReduce(ee.Reducer.max(), [0]).arrayGet([0, 0]).rename("pmax3")
    pmax2 = minfore2.arrayReduce(ee.Reducer.max(), [0]).arrayGet([0, 0]).rename("pmax2")

    # n: focal obs count.  Never masked — an all-cloud pixel yields a 0-length
    # array (n=0); sentinels for non-burnable/non-observed are applied by caller.
    n = focal_arr.arrayLength(0).unmask(0).rename("n")

    # Inter-observation gaps (days): defined only when n >= 2.  A pixel with
    # exactly 1 focal obs has an EMPTY diff array that is NOT mask-propagated
    # (focal_arr is non-empty), so reducing it directly would throw.  Mask the
    # diff array by n>=2 first: masked pixels short-circuit the reducer (the
    # col-0 pattern), so only n>=2 pixels actually reduce.
    diffs = (d_focal.arraySlice(0, 1)
             .subtract(d_focal.arraySlice(0, 0, -1))
             .updateMask(n.gte(2)))
    timediff_med = diffs.arrayReduce(ee.Reducer.median(), [0]).arrayGet([0, 0]).rename("timediff_med")
    timediff_max = diffs.arrayReduce(ee.Reducer.max(),    [0]).arrayGet([0, 0]).rename("timediff_max")

    return ee.Image.cat([
        delta3_peak, minfore3_peak, jumpgap3, prevwidth3, postwidth3, date_post3,
        delta2_peak, minfore2_peak, jumpgap2, prevwidth2, postwidth2, date_post2,
        pmax3, pmax2, pmax1, n, timediff_med, timediff_max,
    ])


# All metric bands except `n` (the `n` band is rebuilt with sentinels by bpts_image).
NON_N_BANDS = [
    "delta3_peak", "minfore3_peak", "jumpgap3", "prevwidth3", "postwidth3", "date_post3",
    "delta2_peak", "minfore2_peak", "jumpgap2", "prevwidth2", "postwidth2", "date_post2",
    "pmax3", "pmax2", "pmax1", "timediff_med", "timediff_max",
]

# Integer-encoding band groups for export (see docs/03-bpts.md §3.7).  Every band is
# stored as signed int16: probabilities are scaled by PROB_SCALE (decode: value /
# PROB_SCALE) and delta* are signed (range −1..1); day-widths/gaps, inter-obs gaps and
# date_post* (day-of-year 1..366) are whole numbers stored as-is; `n` keeps its -1/-2
# sentinels.  All fit in ±32767.  See bpts_image for why signed, not uint16.
PROB_SCALE  = 10000
PROB_BANDS  = ["delta3_peak", "minfore3_peak", "delta2_peak", "minfore2_peak",
               "pmax3", "pmax2", "pmax1"]
DAY_BANDS   = ["jumpgap3", "prevwidth3", "postwidth3",
               "jumpgap2", "prevwidth2", "postwidth2",
               "timediff_med", "timediff_max"]
DOY_BANDS   = ["date_post3", "date_post2"]


# ─── Per-tile-year orchestration ─────────────────────────────────────────────

def _tile_geometry(tile_id):
    """Geometry of one MapBiomas carta tile, by its grid-name id."""
    return (ee.FeatureCollection(C.CARTAS_FC)
            .filter(ee.Filter.eq(C.CARTAS_ID_PROPERTY, tile_id))
            .geometry())


def _tiles_in_buffer():
    """Sorted list of all carta tile-ids intersecting the buffered-Argentina FC."""
    cartas = (ee.FeatureCollection(C.CARTAS_FC)
              .filterBounds(ee.FeatureCollection(C.ARG_BUFFER_FC)))
    return sorted(cartas.aggregate_array(C.CARTAS_ID_PROPERTY).getInfo())


def _year_dates(year):
    """
    The six Landsat filter boundaries for a focal year, padded ``C.pad_months(year)``
    on each side (2 months for most years; 4 for 1999, 3 for 2000 — the sparse early
    Landsat era).  filterDate's end is exclusive, so e.g. with a 2-month pad
    ``next_end`` = Mar 1 keeps observations through the last day of February.
    """
    pad = C.pad_months(year)
    return {
        "prev_start":  ee.Date.fromYMD(year - 1, 12 - pad + 1, 1),  # (13-pad) 1, y-1
        "prev_end":    ee.Date.fromYMD(year, 1, 1),
        "focal_start": ee.Date.fromYMD(year, 1, 1),
        "focal_end":   ee.Date.fromYMD(year + 1, 1, 1),
        "next_start":  ee.Date.fromYMD(year + 1, 1, 1),
        "next_end":    ee.Date.fromYMD(year + 1, pad + 1, 1),       # (pad+1) 1, y+1
    }


def veg_fire_image(year):
    """
    Previous-year veg_fire class image for a focal year.

    veg_fire = remap(region_class), where region_class = region_id·100 +
    prev-year MapBiomas class.  Uses mb_year = min(year-1, MB_LIMIT_YEAR) since
    the LULC asset stops at MB_LIMIT_YEAR.  Pixels outside any region (region 0)
    or with an unmapped class fall through to the non-observed sentinel (25).
    """
    mb_year = min(year - 1, C.MB_LIMIT_YEAR)
    mb_class = get_mb_class_band(ee.Image(C.MAPBIOMAS_LULC), mb_year)
    region = ee.Image(C.REGION_RASTER).select(C.REGION_RASTER_BAND)
    region_class = region.multiply(100).add(mb_class)
    return region_class.remap(
        C.REGION_CLASS_FROM, C.VEG_FIRE_TO, C.VEG_FIRE_REMAP_DEFAULT
    ).rename("veg_fire")


def burn_prob_collection(year, tile_id, terms=None, keep_indices=False):
    """
    Build the per-date burn-probability collection for one tile-year.

    Loads the prev-year veg_fire class and MapBiomas mosaic, precomputes the
    static linear-predictor pieces, then maps the logistic regression over every
    (date-mosaicked) Landsat image in the padded window (C.pad_months(year) on each
    side of the focal year; default 2 months, wider for 1999/2000).

    Returns ``(bp_col, veg_fire_img)`` where ``bp_col`` is an ImageCollection of
    2-band [prob, day_num] images masked to fittable classes.  With
    ``keep_indices=True`` each image also carries its spectral bands/indices
    (handy for inspecting NBR/NBR2 vs prob in the Code Editor inspector).
    """
    terms = terms if terms is not None else load_all_coefficients()
    tile_geom = _tile_geometry(tile_id)
    mb_year = min(year - 1, C.MB_LIMIT_YEAR)

    veg_fire = veg_fire_image(year)
    mb_mosaic = get_mb_mosaic_bands(
        ee.ImageCollection(C.MAPBIOMAS_MOSAIC), mb_year, tile_geom, C.MB_MOSAIC_BANDS
    )

    # Static (time-invariant within the year) linear-predictor components.
    coeff_img = build_coeff_image(veg_fire, terms)
    prev_scalar = build_prev_scalar(coeff_img, mb_mosaic, terms)
    cross_f1_coef = build_cross_factor1_coef(coeff_img, mb_mosaic, terms)
    is_fittable = veg_fire.gte(1).And(veg_fire.lte(23))

    dates = _year_dates(year)
    col = get_landsat(tile_geom, dates["prev_start"], dates["next_end"])
    col = mosaic_by_date(col)                    # one image per unique date

    def _add_bp(img):
        img = add_indices(img)
        bp = compute_burn_prob_img(
            img, prev_scalar, coeff_img, cross_f1_coef, terms, year
        ).updateMask(is_fittable)
        return img.addBands(bp).updateMask(is_fittable) if keep_indices else bp

    return col.map(_add_bp), veg_fire


def bpts_image(year, tile_id, terms=None):
    """
    Compute the 18-band burn-probability time-series-metrics image for one
    tile-year (the unit exported by ``bpts``).  See docs/03-bpts.md.
    """
    terms = terms if terms is not None else load_all_coefficients()
    bp_col, veg_fire = burn_prob_collection(year, tile_id, terms)
    bp_col = bp_col.select(["prob", "day_num"])
    dates = _year_dates(year)

    # Split the padded series into prev / focal / next, each a sorted [N×2] array.
    prev_arr = safe_to_array(
        bp_col.filterDate(dates["prev_start"], dates["prev_end"]).sort("system:time_start"))
    focal_arr = safe_to_array(
        bp_col.filterDate(dates["focal_start"], dates["focal_end"]).sort("system:time_start"))
    next_arr = safe_to_array(
        bp_col.filterDate(dates["next_start"], dates["next_end"]).sort("system:time_start"))

    metrics = compute_bp_ts_metrics(focal_arr, prev_arr, next_arr)

    # `n` sentinels for non-fittable classes (the `n` band is otherwise the
    # focal obs count and is never masked): -1 non-burnable, -2 non-observed.
    n_final = (metrics.select("n")
               .where(veg_fire.eq(C.VEG_FIRE_NON_BURNABLE), ee.Image.constant(-1))
               .where(veg_fire.eq(C.VEG_FIRE_NON_OBSERVED), ee.Image.constant(-2)))

    # Integer encoding for storage (≈half the float32 size; see docs/03-bpts.md
    # §3.7).  Everything is int16 (signed): probabilities ×PROB_SCALE fit ±10000,
    # day-gaps (≲250) and DOY (1..366) fit well under 32767, and `n` keeps its
    # -1/-2 sentinels.  Signed (not uint16) on purpose — day-gaps are guaranteed
    # ≥0 by the ascending-date sort, but a stray negative would stay visibly
    # negative rather than silently wrapping to a huge unsigned value.  Masks are
    # preserved by the casts, so short-window bands stay masked.
    prob_int = metrics.select(PROB_BANDS).multiply(PROB_SCALE).round().toInt16()
    day_int  = metrics.select(DAY_BANDS).round().toInt16()
    doy_int  = metrics.select(DOY_BANDS).round().toInt16()
    n_int    = n_final.round().toInt16().rename("n")

    result = (prob_int.addBands(day_int).addBands(doy_int).addBands(n_int)
              .select(NON_N_BANDS + ["n"]))
    return result.set({
        "year": year,
        "tile_id": tile_id,
        "system:time_start": ee.Date.fromYMD(year, 7, 1).millis(),
    })


def _export_bpts_image(img, year, tile_id, tile_geom):
    """Submit one ``bpts_YYYY_<tile-id>`` image-to-asset export task."""
    asset_name = f"bpts_{year}_{tile_id}"
    task = ee.batch.Export.image.toAsset(
        image=img,
        description=asset_name,
        assetId=f"{C.BP_TS_METRICS_COL}/{asset_name}",
        region=tile_geom,
        scale=30,
        crs="EPSG:4326",
        maxPixels=int(1e10),
    )
    task.start()
    return task


def _existing_bpts_names():
    """
    Set of already-exported asset leaf names (e.g. ``{'bpts_2015_SK-19-Y-A', …}``)
    in ``C.BP_TS_METRICS_COL``.  One paged ``listAssets`` call.

    Note: an asset only appears here once its export has *completed* — a task
    that is still RUNNING is not listed.  So don't run the same year from two
    places at once (the per-year Excel sign-out is what prevents that); the
    skip just makes re-running / resuming a year idempotent.
    """
    names = set()
    page_token = None
    while True:
        params = {"parent": C.BP_TS_METRICS_COL}
        if page_token:
            params["pageToken"] = page_token
        try:
            resp = ee.data.listAssets(params)
        except Exception:
            return names                       # collection missing/empty → nothing exported
        for asset in resp.get("assets", []):
            names.add(asset["id"].split("/")[-1])
        page_token = resp.get("nextPageToken")
        if not page_token:
            return names


def bpts(year=None, tile_id=None, export=True, overwrite=False):
    """
    Burn-probability time-series metrics for tile-year(s).

    Parameters
    ----------
    year      : int or None  — None = all years in ``C.YEARS``
    tile_id   : str or None  — None = all tiles intersecting the ARG buffer
                               (e.g. 'SK-19-Y-A')
    export    : bool         — False returns the ee.Image for inspection and
                               requires both ``year`` and ``tile_id``
    overwrite : bool         — by default tile-years whose asset already exists
                               are skipped (safe to re-run / resume a year).  Set
                               True to submit them anyway — but GEE will not
                               overwrite an existing asset, so delete it first.

    Returns
    -------
    ee.Image (export=False) or list[ee.batch.Task] (export=True).
    """
    if not export and (year is None or tile_id is None):
        raise ValueError("export=False requires both year and tile_id")

    terms = load_all_coefficients()

    if not export:
        return bpts_image(year, tile_id, terms)

    years = [year] if year is not None else list(C.YEARS)
    tile_ids = [tile_id] if tile_id is not None else _tiles_in_buffer()

    existing = set() if overwrite else _existing_bpts_names()

    tasks, skipped = [], 0
    for tid in tile_ids:
        tile_geom = _tile_geometry(tid)
        for y in years:
            if f"bpts_{y}_{tid}" in existing:
                skipped += 1
                continue
            img = bpts_image(y, tid, terms)
            tasks.append(_export_bpts_image(img, y, tid, tile_geom))
    print(f"Submitted {len(tasks)} bpts export task(s)"
          f"{f', skipped {skipped} already exported' if skipped else ''}"
          f" → {C.BP_TS_METRICS_COL}")
    return tasks


def bpts_status(year=None):
    """
    Report export progress against the expected tile list (all tiles intersecting
    the ARG buffer).  Run it any time, from any account that can read the output
    collection — it only does a ``listAssets`` (no compute).

    Prints ``done / total`` per year and returns ``{year: [missing tile-ids]}`` so
    you can mark the Excel done and resume exactly the tiles that failed.
    """
    existing = _existing_bpts_names()
    tiles = _tiles_in_buffer()
    years = [year] if year is not None else list(C.YEARS)

    missing_by_year = {}
    for y in years:
        missing = [t for t in tiles if f"bpts_{y}_{t}" not in existing]
        missing_by_year[y] = missing
        done = len(tiles) - len(missing)
        flag = " ✓ complete" if not missing else f", {len(missing)} missing"
        print(f"{y}: {done}/{len(tiles)} tiles done{flag}")
    return missing_by_year
