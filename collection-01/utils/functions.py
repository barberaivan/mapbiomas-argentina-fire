"""
collection-01/utils/functions.py

GEE helper functions shared across the collection-01 workflow.
Ported from collection-00/utils/functions.js, keeping only what is needed.
"""

import ee

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

    # ─── Canonical-team additions (logistic_regression_terms.qmd §"Canonical team") ──
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
