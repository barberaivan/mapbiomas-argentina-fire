#!/usr/bin/env python3
"""
collection-01/workflow/07-subproducts.py

Step 07d — the nine DERIVED subproducts, all of them from step 07a's month-of-burn
collection plus the MapBiomas LULC.  No new vectors, no local work, no re-labelling
(docs/07 §12).

    monthly_burned              annual_burned
    monthly_burned_coverage     annual_burned_coverage
    frequency_burned            frequency_burned_coverage
    accumulated_burned          accumulated_burned_coverage
    year_last_fire

**DO NOT INNOVATE ON THE ENCODINGS.**  They are what the MapBiomas platform decodes and what
the statistics stage reads; every country writes them identically.  This script is a port of
`Reference/2-Collection_Fire_Subproducts/{1_burned_area_products_monthly_annual_coverage,
2_burned_area_frequency_accumulated_coverage,3_year_last_fire}` — same bands, same encodings,
same dtypes, same pyramiding (`mode` throughout).  Three deliberate departures, all of them
about plumbing rather than pixel values:

  1. **The grid is pinned** (`crs=C.SNIC_CRS` + `crsTransform=C.SNIC_TRANSFORM`), never
     `scale=30` — which in EPSG:4326 is a *different* grid (docs/07 §3).  Same rule as 07a/07c.
  2. **The export region is `C.ARG_BUFFER_FC`** (Argentina + 2 km), because
     `regiones_fuego_argentina_v1` does not exist as a FeatureCollection (docs/07 §11); the
     reference uses `regions.union().geometry()`.
  3. **All nine products read the 07a month collection**, whereas the reference exports
     `annual_burned` first and then has scripts 2 and 3 read that ASSET.  Ours is a plumbing
     change only — `annual_burned` is *defined* as `month > 0`, so frequency built from the
     month images is bit-identical to frequency built from the exported annual product, and
     both being derived from the one pivot makes them consistent by construction rather than
     by sequencing.  It also means the nine tasks are independent: no waiting for a 27-band
     export to land before the 53-band ones can be submitted, and any single product can be
     re-run alone.

And the reference's `accumulated_burned` filename typo is NOT copied: script 2 builds
`..._accumulate1_burned_v1` where the publish list expects `..._accumulated_burned_v1`
(docs/07 §12.3.2).

Usage (from the repo ROOT)
--------------------------
  $PYTHON collection-01/workflow/07-subproducts.py                       # dry run, all 9
  $PYTHON collection-01/workflow/07-subproducts.py --check               # ROI audit
  $PYTHON collection-01/workflow/07-subproducts.py --launch              # 9 tasks
  $PYTHON collection-01/workflow/07-subproducts.py --launch --only frequency_burned

  # cheap smoke test of the 53-band graphs before committing hours of compute:
  $PYTHON collection-01/workflow/07-subproducts.py --launch \
      --roi=-61.6,-25.6,-61.1,-25.1        # -> <name>_roitest, delete afterwards

Resumable: a product whose asset exists, or whose task is PENDING/RUNNING, is skipped.

The LULC year, and the 2025 duplication
---------------------------------------
`C.MAPBIOMAS_LULC` (the published Argentina land-cover integration, NOT our internal
`veg_fire` remap — docs/07 §12.1) ends at `classification_2024`, so 2025 is duplicated
forward from 2024, exactly as every reference country does.  The coverage products use the
**same** calendar year as the burn (not the previous year, unlike `veg_fire`): they answer
"which land cover burned in year Y, as classified in year Y".

VERIFIED 2026-07-29: the LULC asset sits on the SAME 30 m lattice as the SNIC grid — same
pixel size, and its origin is offset by exactly 9953 columns / -25102 rows (integer).  So
combining it with the month raster on `C.SNIC_TRANSFORM` involves no resampling and no
half-pixel shift, and its footprint contains the 2 km buffer (`contains == True`), so no
burned pixel can fall outside the LULC and silently drop out of a `*_coverage` product.
`--check` re-measures that residual per year rather than trusting it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils.constants as C  # noqa: E402

# Band-name prefix of the two window products.  The reference SCRIPT writes
# `fire_frequency_<y1>_<y2>` while `ToPublish/2-toAsset-Public`'s band_format map says
# `frequency_burned_{year1}_{year2}`; the `fire_accumulated_*` pair agrees in both places, so
# only frequency is in doubt (docs/08 open #9).  We write what the script writes — that is the
# code that produced every published country's asset — and record it in the `band_format`
# property.  If IPAM rules the other way, this ONE line changes plus a re-export of the two
# frequency products.
FREQ_BAND_PREFIX = "fire_frequency"
ACCUM_BAND_PREFIX = "fire_accumulated"

# Default --check extent: the Chaco 0.5 deg audit box used throughout step 07 (docs/07 §7).
CHECK_ROI = "-61.6,-25.6,-61.1,-25.1"


# ---------------------------------------------------------------------------
# asset plumbing
# ---------------------------------------------------------------------------
def asset_exists(asset_id):
    try:
        ee.data.getAsset(asset_id)
        return True
    except ee.EEException:
        return False


def task_in_flight(description):
    for op in ee.data.listOperations():
        meta = op.get("metadata", {})
        if (meta.get("description") == description
                and meta.get("state") in ("PENDING", "RUNNING")):
            return True
    return False


def product_asset(sub, suffix=""):
    return f"{C.FINAL_PRODUCTS}/{C.product_name(sub)}{suffix}"


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------
def month_image(cal_year):
    """The 07a month-of-burn image for one calendar year: 1-12, masked elsewhere.

    Addressed by name rather than `filter(year).mosaic()` as the reference does — ours is one
    whole-country image per year (no region dimension), so a mosaic over a one-image collection
    would only hide a missing year instead of failing loudly.  The band is renamed to the
    reference's working name `burned_coverage_<year>`, which is what the two coverage products
    publish; `monthly_burned` and `annual_burned` rename it again on the way out.
    """
    img_id = f"{C.MONTH_OF_BURN_COL}/{C.product_name('fire_mask')}_{cal_year}"
    return ee.Image(img_id).select([C.MONTH_OF_BURN_BAND],
                                   [f"burned_coverage_{cal_year}"])


def lulc_series(years, verbose=True):
    """`year -> classification_<year>` band, duplicating the last available year forward.

    `C.MAPBIOMAS_LULC` ends at `classification_2024` and the series runs to 2025, so 2025 takes
    2024's classification — what every reference country does
    (`.slice(-1).rename(['classification_2025'])`).  The available band list is read from the
    asset rather than from `C.MB_LIMIT_YEAR` so this self-corrects the day the LULC is extended.
    """
    lulc = ee.Image(C.MAPBIOMAS_LULC)
    have = sorted(int(b.split("_")[1]) for b in lulc.bandNames().getInfo()
                  if b.startswith("classification_"))
    out, filled = {}, []
    for y in years:
        src = y if y in have else have[-1]
        out[y] = lulc.select([f"classification_{src}"], [f"classification_{y}"])
        if src != y:
            filled.append((y, src))
    if filled and verbose:
        print("[lulc] " + ", ".join(f"{y} <- classification_{src}" for y, src in filled)
              + "  (duplicated forward, as every reference country does)")
    return out


# ---------------------------------------------------------------------------
# the nine products
# ---------------------------------------------------------------------------
def _windows(years, hits, lulc):
    """The two-sided frequency accumulation: {(y1, y2): (freq, freq_coverage)}.

    A FORWARD pass accumulates `years[0]…y` and a BACKWARD pass `y…years[-1]`; both band sets
    are concatenated and sorted, and the window that both passes produce — the full
    `years[0]…years[-1]` — is kept from the forward pass only (the reference drops the backward
    duplicate with `freqPost.slice(0,-1)`).  27 + 27 - 1 = 53 bands.

    The coverage variant always encodes the LULC of the window's MOVING end: `y` in the forward
    pass (the window's end), `y` in the backward pass (the window's start).  In both it is the
    year that varies, not the fixed anchor.

    Never-burned pixels are `selfMask`ed out, so frequency is 1..N-or-absent, never 0.
    """
    y_first, y_last = years[0], years[-1]
    counts, run = {}, None
    for y in years:                                             # forward: y_first … y
        run = hits[y] if run is None else run.add(hits[y])
        counts[(y_first, y)] = run
    run = None
    for y in reversed(years):                                   # backward: y … y_last
        run = hits[y] if run is None else run.add(hits[y])
        counts.setdefault((y, y_last), run)                     # setdefault keeps the forward
                                                                # pass's (y_first, y_last)
    out = {}
    for (y1, y2), count in counts.items():
        moving = y2 if y1 == y_first else y1
        name = f"{FREQ_BAND_PREFIX}_{y1}_{y2}"
        freq = count.rename(name).selfMask()
        out[(y1, y2)] = (freq, freq.multiply(100).add(lulc[moving]).rename(name).toInt16())
    return out


def build(years, verbose=True):
    """(subproduct, image, band_format) for all nine products, in publication order."""
    lulc = lulc_series(years, verbose)
    month = ee.Image.cat([month_image(y) for y in years])          # burned_coverage_<y>, 1-12
    lc = ee.Image.cat([lulc[y] for y in years])

    # 🟡 month of occurrence, 1-12.  Masked outside the burn, so no 0 is ever written.
    monthly = month.rename([f"burned_monthly_{y}" for y in years]).toUint8()

    # 🟢 annual presence.  `gt(0)` keeps the mask, so the band is 1-or-masked, not 1/0 — which
    # is why everything that COUNTS it below has to `unmask(0)` first.
    annual = month.gt(0).rename([f"burned_area_{y}" for y in years]).toUint8()

    # 🟠 month * 100 + LULC class, and 🔵 presence * LULC class.  Band names stay
    # `burned_coverage_<year>` for BOTH — that is the published band_format for
    # annual_burned_coverage, and the reference never renames the monthly one either.
    monthly_cov = month.multiply(100).add(lc).toUint16()
    annual_cov = month.gte(1).multiply(lc).toUint8()

    # the 53 frequency windows, and the accumulated pair derived from them
    hits = {y: month_image(y).gt(0).unmask(0) for y in years}       # 1/0, never masked
    windows = _windows(years, hits, lulc)
    keys = sorted(windows, key=lambda k: f"{FREQ_BAND_PREFIX}_{k[0]}_{k[1]}")
    freq = ee.Image.cat([windows[k][0] for k in keys]).toInt16()
    freq_cov = ee.Image.cat([windows[k][1] for k in keys])

    # 🟡/🟢 accumulated = "burned at least once in the window", and its LULC recovered from the
    # frequency coverage code by `mod 100`.  Band names are the frequency ones with the prefix
    # swapped; both are selfMask()ed, so a never-burned pixel is absent, not 0.
    acc_names = [f"{ACCUM_BAND_PREFIX}_{y1}_{y2}" for y1, y2 in keys]
    accum = freq.gte(1).rename(acc_names).selfMask().toUint8()
    accum_cov = freq_cov.mod(100).rename(acc_names).selfMask().toUint8()

    # 🔴 year of the most recent fire up to each year.  Iterative carry-forward: start from 0,
    # and each year replace the burned pixels with that year, keeping the previous value
    # elsewhere.  The test must be the UNMASKED hit — a masked test is not a reliable "false"
    # for `where()`, and the annual bands are 1-or-masked.
    #
    # ⚠️ THE BANDS ARE `classification_<year+1>`, NOT `classification_<year>`.  That off-by-one
    # is in the reference and in the publish map; it looks like a bug and the platform expects
    # it (docs/07 §12.3.1).  So the 1999-2025 series is carried by bands 2000-2026.
    ylf, prev = [], ee.Image(0)
    for y in years:
        prev = prev.where(hits[y], y).rename(f"classification_{y + 1}")
        ylf.append(prev)
    year_last_fire = ee.Image.cat(ylf).selfMask().toUint16()

    freq_fmt = f"{FREQ_BAND_PREFIX}_{{year1}}_{{year2}}"
    accum_fmt = f"{ACCUM_BAND_PREFIX}_{{year1}}_{{year2}}"
    return [
        ("monthly_burned", monthly, "burned_monthly_{year}"),
        ("annual_burned", annual, "burned_area_{year}"),
        ("monthly_burned_coverage", monthly_cov, "burned_coverage_{year}"),
        ("annual_burned_coverage", annual_cov, "burned_coverage_{year}"),
        ("frequency_burned", freq, freq_fmt),
        ("frequency_burned_coverage", freq_cov, freq_fmt),
        ("accumulated_burned", accum, accum_fmt),
        ("accumulated_burned_coverage", accum_cov, accum_fmt),
        ("year_last_fire", year_last_fire, "classification_{year}"),
    ]


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------
def check(years, roi_str):
    """Band bookkeeping for all nine, then per-year pixel counts over a SMALL roi.

    Pass an `--roi` and mean it: an interactive `reduceRegion` over the 74085 x 123601 country
    grid returns "Computation timed out" (measured — that is why 07a's whole-country histogram
    is a batch task).  What matters here is not the absolute counts but that
    `month == annual == coverage` pixel-for-pixel and that `lulc_missing` is 0: a burned pixel
    whose LULC band is masked would silently vanish from BOTH coverage products while staying in
    `annual_burned`, and the statistics stage is checked to ~1 % (docs/09).

    The band listing is the other half of the audit — 53 windows over two prefixes, one dropped
    duplicate window and an off-by-one in `year_last_fire`'s names is where this goes wrong.
    """
    for sub, img, fmt in build(years):
        names = img.bandNames().getInfo()
        print(f"  {sub:28s} {len(names):>3} bands  {names[0]} … {names[-1]}   {fmt}")

    roi = ee.Geometry.Rectangle([float(v) for v in roi_str.split(",")], None, False)
    lulc = lulc_series(years, verbose=False)
    print(f"\n[check] roi={roi_str}  (per-year pixel counts; lulc_missing MUST be 0)")
    for y in years:
        month = month_image(y)
        # .unweighted(): reduceRegion weights partial pixels at the region edge by default, so a
        # plain sum() returns a FRACTIONAL pixel count (docs/07 §9 / 07-scar_rasters.py).
        d = (month.mask().rename("month")
             .addBands(month.gt(0).unmask(0).rename("annual"))
             .addBands(month.multiply(100).add(lulc[y]).mask().rename("coverage"))
             .addBands(month.mask().And(lulc[y].mask().Not()).rename("lulc_missing"))
             .reduceRegion(ee.Reducer.sum().unweighted(), roi, crs=C.SNIC_CRS,
                           crsTransform=C.SNIC_TRANSFORM, maxPixels=int(1e10)).getInfo())
        flag = "" if int(d["lulc_missing"]) == 0 else "   <-- LULC GAP"
        print(f"  {y}  month {int(d['month']):>10,} | annual {int(d['annual']):>10,} | "
              f"coverage {int(d['coverage']):>10,} | lulc_missing "
              f"{int(d['lulc_missing']):>6,}{flag}")


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
def export(specs, years, launch, roi=None):
    region = (ee.Geometry.Rectangle([float(v) for v in roi.split(",")], None, False) if roi
              else ee.FeatureCollection(C.ARG_BUFFER_FC).geometry())
    suffix = "_roitest" if roi else ""
    for sub, img, band_format in specs:
        asset_id = product_asset(sub, suffix)
        description = sub + suffix
        if asset_exists(asset_id):
            print(f"[skip] {asset_id} already exists")
            continue
        if task_in_flight(description):
            print(f"[skip] {description} has a PENDING/RUNNING task")
            continue
        img = img.set({
            "source": C.PRODUCT_SOURCE,
            "region": C.PRODUCT_REGION,
            "band_format": band_format,
            "years": f"{years[0]}-{years[-1]}",
            "lulc_asset": C.MAPBIOMAS_LULC,
            "lulc_year": "same calendar year as the burn",
            "derived_from": C.MONTH_OF_BURN_COL,
        })
        if not launch:
            print(f"[dry] would export {asset_id}\n"
                  f"      {len(img.bandNames().getInfo())} bands, band_format={band_format}")
            continue
        task = ee.batch.Export.image.toAsset(
            image=img, description=description, assetId=asset_id, region=region,
            crs=C.SNIC_CRS,                       # pin the grid — never scale=30 (docs/07 §3)
            crsTransform=C.SNIC_TRANSFORM,
            maxPixels=int(1e13),
            pyramidingPolicy={".default": "mode"},
        )
        task.start()
        print(f"[launched] {task.id}  ->  {asset_id}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--launch", action="store_true",
                    help="actually submit the export tasks (default: build + report only)")
    ap.add_argument("--check", action="store_true",
                    help="audit instead of exporting: band bookkeeping for all nine products, "
                         "then per-year pixel counts and the LULC-coverage residual over --roi")
    ap.add_argument("--roi", default=None,
                    help=f"'xmin,ymin,xmax,ymax'. With --check, the audit extent (default the "
                         f"Chaco box {CHECK_ROI}). With --launch, a SMOKE TEST: exports the full "
                         f"multiband products over that rectangle to <name>_roitest, which "
                         f"proves the 53-band graphs build in minutes instead of hours. Delete "
                         f"the test assets afterwards.")
    ap.add_argument("--only", help="comma-separated subproduct names to build (default: all 9)")
    ap.add_argument("--years", help="comma-separated calendar years (default: the whole series)")
    ap.add_argument("--project", default=C.GEE_PROJECT)
    args = ap.parse_args()

    ee.Initialize(project=args.project)
    years = [int(v) for v in args.years.split(",")] if args.years else list(C.CALENDAR_YEARS)

    if args.check:
        check(years, args.roi or CHECK_ROI)
        return

    missing = [y for y in years
               if not asset_exists(f"{C.MONTH_OF_BURN_COL}/{C.product_name('fire_mask')}_{y}")]
    if missing:
        print(f"[abort] 07a month-of-burn images missing for: {missing}")
        print("        run 07-month_of_burn.py --all --launch and wait for the tasks")
        return

    specs = build(years)
    if args.only:
        want = [s.strip() for s in args.only.split(",")]
        bad = [w for w in want if w not in [s[0] for s in specs]]
        if bad:
            ap.error(f"unknown subproduct(s) {bad}; choose from "
                     f"{[s[0] for s in specs]}")
        specs = [s for s in specs if s[0] in want]

    export(specs, years, args.launch, args.roi)
    if not args.launch:
        print("\nDry run only. Re-run with --launch to submit the task(s).")


if __name__ == "__main__":
    main()
