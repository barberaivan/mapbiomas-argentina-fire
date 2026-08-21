#!/usr/bin/env python3
"""Whole-country burned area per FIRE YEAR, per product — the input to choosing which
years to validate (docs/10 §8).

One row per (product, fire_year): area in ha over `ARG-Political_Level_1-Pais`
(279.27 Mha), the population frame of the validation design.

FIRE YEAR Y = 1 May Y -> 30 Apr Y+1, named by the start year. Every product is windowed
to that span, never to a calendar year.

Two ways of measuring area, chosen per product:

  * coarse-native products (MCD64A1, VNP64A1 463 m; FireCCI51 250 m) — sum
    `pixelArea()` masked by the burned mask, at the product's native scale. ~13 M
    pixels over Argentina at 463 m, so this is cheap and exact; there is nothing to
    gain from coarsening to 1 km.

  * ours (30 m) — `reduceResolution(mean)` of the binary mask onto the ~480 m grid,
    times the coarse cell area. NOT a coarse `reduceRegion`: the month-of-burn band's
    pyramidingPolicy is MODE, so reading it at 480 m through the pyramid would return
    the modal month of each 16x16 block and erase every sparse burn — the same trap
    docs/10 §4.3 rejects for the strata. reduceResolution forces the native read.

Resumable: rows are appended one at a time and completed (product, year) pairs are
skipped, so a killed run can be relaunched.

Usage (from the repo root):
    $PYTHON collection-01/scripts/10_burned_area_by_fire_year.py            # all products
    $PYTHON collection-01/scripts/10_burned_area_by_fire_year.py -p mcd64   # one product
"""
import argparse
import csv
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import ee  # noqa: E402

import utils.constants as C  # noqa: E402

# --------------------------------------------------------------------------- config
FRAME_FC = ("projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/"
            "ARG-Political_Level_1-Pais")

COARSE_FACTOR = 16          # docs/10 §4.2 — our grid decimated x16, ~480 m
OUT_CSV = os.path.join(os.path.dirname(__file__), "..", "validation",
                       "burned_area_by_fire_year.csv")
FIELDS = ["product", "fire_year", "area_ha", "scale_m", "partial", "note"]

# Per product: the fire years it can cover, and the years where the temporal window is
# only PARTIALLY covered by the archive (flagged, not dropped — a partial year's area is
# an undercount and must not be read as a low fire year).
#   ours       month-of-burn calendar 1999-2025 -> FY needs Y and Y+1 -> FY1999-2024
#   MCD64A1    Nov 2000 -> Jun 2026            -> FY2001-2025 full, FY2000 partial
#   VNP64A1    Mar 2012 -> Jun 2026            -> FY2012-2025 full, FY2011 partial
#   FireCCI51  Jan 2001 -> Dec 2020            -> FY2001-2019 full, FY2020 partial
PRODUCTS = {
    "ours":    dict(years=range(1999, 2025), partial=(),     scale=None),
    "mcd64":   dict(years=range(2000, 2026), partial=(2000,), scale=463.313),
    "vnp64":   dict(years=range(2011, 2026), partial=(2011,), scale=463.313),
    "firecci": dict(years=range(2001, 2021), partial=(2020,), scale=250.0),
}


def initialize():
    ee.Initialize(project=C.GEE_PROJECT)


def frame():
    """The population frame as a RASTER mask plus a bounding box.

    Reducing over the country polygon itself costs ~68 s per year — the outline is very
    detailed. Painting it to a mask and reducing over its bounding box gives the same
    answer to 0.003 % (measured: 2,095,352 vs 2,095,407 ha, MCD64A1 FY2015) in ~8 s.
    """
    fc = ee.FeatureCollection(FRAME_FC)
    mask = ee.Image.constant(0).byte().paint(fc, 1).selfMask()
    return mask, fc.geometry().bounds()


# ------------------------------------------------------------------ per-product masks
def fire_year_window(fy):
    """1 May fy -> 1 May fy+1."""
    t0 = ee.Date.fromYMD(fy, 5, 1)
    return t0, t0.advance(1, "year")


def mask_ours(fy):
    """(burned_monthly[fy] >= 5) OR (burned_monthly[fy+1] in 1..4) — docs/10 §3.

    Exact, because step 07 assigned the month and calendar year PER PIXEL from abs_date.
    """
    col = ee.ImageCollection(C.MONTH_OF_BURN_COL)

    def mob(year):
        img = ee.Image(col.filter(ee.Filter.eq("year", year)).first())
        return img.select(C.MONTH_OF_BURN_BAND).unmask(0)

    nxt = mob(fy + 1)
    return mob(fy).gte(5).Or(nxt.gte(1).And(nxt.lte(4)))


def mask_external(product, fy):
    t0, t1 = fire_year_window(fy)
    spec = {
        "mcd64":   ("MODIS/061/MCD64A1", "BurnDate", 1),
        "vnp64":   ("NASA/VIIRS/002/VNP64A1", "Burn_Date", 1),
        "firecci": ("ESA/CCI/FireCCI/5_1", "BurnDate", 1),
    }[product]
    cid, band, floor = spec
    col = ee.ImageCollection(cid).filterDate(t0, t1).select(band)
    return ee.Image(col.max()).gte(floor).unmask(0), col.size()


# ------------------------------------------------------------------------ area
def area_ha_coarse_native(mask, scale, fmask, box):
    """Sum pixelArea() under the mask, at the product's native scale."""
    out = (ee.Image.pixelArea().updateMask(mask.selfMask()).updateMask(fmask)
           .reduceRegion(reducer=ee.Reducer.sum(), geometry=box,
                         scale=scale, maxPixels=int(1e13), tileScale=4))
    return ee.Number(out.get("area")).divide(1e4)      # m2 -> ha


def area_ha_ours(mask, fmask, box):
    """Mean burned fraction on the ~480 m nested grid x coarse cell area.

    reduceResolution (not a coarse reduceRegion) because the band's pyramid is MODE.
    """
    coarse_t = [C.SNIC_TRANSFORM[0] * COARSE_FACTOR, 0, C.SNIC_TRANSFORM[2],
                0, C.SNIC_TRANSFORM[4] * COARSE_FACTOR, C.SNIC_TRANSFORM[5]]
    coarse = ee.Projection(C.SNIC_CRS, coarse_t)
    frac = (mask.unmask(0).rename("frac")
            .reduceResolution(reducer=ee.Reducer.mean(), maxPixels=1024)
            .reproject(coarse))
    out = (frac.multiply(ee.Image.pixelArea()).rename("frac").updateMask(fmask)
           .reduceRegion(reducer=ee.Reducer.sum(), geometry=box,
                         crs=C.SNIC_CRS, crsTransform=coarse_t,
                         maxPixels=int(1e13), tileScale=4))
    return ee.Number(out.get("frac")).divide(1e4)


# ------------------------------------------------------------------------ driver
def done_pairs(path):
    if not os.path.exists(path):
        return set()
    with open(path) as fh:
        return {(r["product"], int(r["fire_year"])) for r in csv.DictReader(fh)}


def append_row(path, row):
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-p", "--products", default=",".join(PRODUCTS),
                    help="comma-separated subset of: " + ",".join(PRODUCTS))
    ap.add_argument("-o", "--out", default=OUT_CSV)
    ap.add_argument("--years", default=None,
                    help="restrict to FY range 'A-B' (inclusive)")
    args = ap.parse_args()

    initialize()
    fmask, box = frame()
    out_path = os.path.abspath(args.out)
    already = done_pairs(out_path)
    print(f"[info] out  {out_path}\n[info] done {len(already)} rows already")

    lo, hi = (None, None)
    if args.years:
        lo, hi = (int(v) for v in args.years.split("-"))

    for product in args.products.split(","):
        product = product.strip()
        if product not in PRODUCTS:
            sys.exit(f"unknown product {product!r}; pick from {list(PRODUCTS)}")
        spec = PRODUCTS[product]
        for fy in spec["years"]:
            if lo is not None and not (lo <= fy <= hi):
                continue
            if (product, fy) in already:
                continue
            t = time.time()
            note = ""
            if product == "ours":
                payload = ee.Dictionary({
                    "area": area_ha_ours(mask_ours(fy), fmask, box), "n": -1})
                scale = C.SNIC_TRANSFORM[0] * COARSE_FACTOR * 111320  # ~m, N-S
            else:
                mask, n_img = mask_external(product, fy)
                payload = ee.Dictionary({
                    "area": area_ha_coarse_native(mask, spec["scale"], fmask, box),
                    "n": n_img})
                scale = spec["scale"]
            try:
                got = payload.getInfo()          # one round trip, area + composite count
            except Exception as exc:                      # noqa: BLE001
                print(f"[FAIL] {product} FY{fy}: {str(exc)[:160]}")
                continue
            value = got["area"]
            if got["n"] >= 0:
                note = f"{got['n']} monthly composites in window"
            row = dict(product=product, fire_year=fy,
                       area_ha=None if value is None else round(value, 1),
                       scale_m=round(scale, 1),
                       partial=int(fy in spec["partial"]), note=note)
            append_row(out_path, row)
            flag = "  PARTIAL" if row["partial"] else ""
            print(f"[ok] {product:8s} FY{fy}  {row['area_ha'] or 0:>12,.0f} ha"
                  f"  ({time.time() - t:5.1f}s){flag}")


if __name__ == "__main__":
    main()
