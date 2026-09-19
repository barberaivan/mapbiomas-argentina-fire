#!/usr/bin/env python3
"""
Step 07c — the scar-size chain, from the uploaded calendar-year scar vectors.

Paints the ingested `scars_<Y>` FeatureCollections into the network's three scar
subproducts: `annual_burned_id`, `annual_burned_area_ha` and
`annual_burned_scar_size_range`. Each is ONE multiband image with one band per
calendar year, never one image per year.

Runs AFTER `07-calendar_scars.R scars` has built the zips and Ivan has ingested each
one by hand as `C.ANNUAL_BURNED_VECTORS/scars_<Y>`.

Usage (from the repo ROOT; --help for the full flag list)
---------------------------------------------------------
  $PYTHON collection-01/workflow/07-scar_rasters.py --check --years 2003,2020  # mask agreement
  $PYTHON collection-01/workflow/07-scar_rasters.py                  # dry run
  $PYTHON collection-01/workflow/07-scar_rasters.py --launch         # 3 export tasks

Design, the two departures from the reference script and the mask invariant:
docs/07-vector_to_raster.md "07c — the scar rasters, and the mask invariant". The
published shape and the band names: docs/07-published_products.md "Products, and the
shape they take". Sequence: docs/07-vector_to_raster.md "Order of operations".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils.constants as C  # noqa: E402


def asset_exists(asset_id):
    try:
        ee.data.getAsset(asset_id)
        return True
    except ee.EEException:
        return False


# See CLAUDE.md: the compute project is shared with the whole MapBiomas Fuego network, so every task
# description is namespaced rather than left as the bare subproduct name.
TASK_PREFIX = "arg07c_"


def scars_fc(cal_year):
    return ee.FeatureCollection(f"{C.ANNUAL_BURNED_VECTORS}/scars_{cal_year}")


def month_image(cal_year):
    return ee.Image(f"{C.MONTH_OF_BURN_COL}/{C.product_name('fire_mask')}_{cal_year}")


def size_class(area_ha):
    """1..8 from the lower bounds in C.SCAR_SIZE_LOWER_HA (class 1 = below the first bound)."""
    cls = ee.Image.constant(1)
    for lo in C.SCAR_SIZE_LOWER_HA:
        cls = cls.add(area_ha.gte(lo))
    return cls.updateMask(area_ha.mask()).toUint8()


def year_bands(cal_year):
    """(scar_id, area_ha, size_class) for one calendar year, all masked to the month mask."""
    fc = scars_fc(cal_year)
    mask = month_image(cal_year).mask()

    scar_id = ee.Image().paint(fc, "scar_id").updateMask(mask).toInt32()
    area_ha = ee.Image().paint(fc, "area_ha").updateMask(mask).toFloat()
    return (scar_id.rename(f"scar_id_{cal_year}"),
            area_ha.rename(f"scar_area_ha_{cal_year}"),
            size_class(area_ha).rename(f"scar_area_ha_{cal_year}"))


def check(cal_year, roi=None):
    """Do the scar vectors cover exactly the month-of-burn mask?

    Pass an `roi` unless you mean it: an interactive reduceRegion over the whole 74085 x 123601
    country grid returns "Computation timed out" (measured on the month histogram, which is why
    07-month_of_burn.py --stats submits a batch task instead). A small box is enough here, because
    the export masks by mob.mask() anyway, so this is a diagnostic rather than a gate.
    """
    fc_id = f"{C.ANNUAL_BURNED_VECTORS}/scars_{cal_year}"
    if not asset_exists(fc_id):
        print(f"[{cal_year}] scar FC not ingested yet ({fc_id})")
        return
    mob = month_image(cal_year).mask()
    painted = ee.Image().paint(scars_fc(cal_year), 1).gt(0)
    region = (ee.Geometry.Rectangle([float(v) for v in roi.split(",")], None, False) if roi
              else ee.FeatureCollection(C.ARG_BUFFER_FC).geometry())
    stats = (mob.rename("mob").addBands(painted.unmask(0).rename("scar"))
             .addBands(mob.And(painted.unmask(0).Not()).rename("mob_only"))
             .addBands(painted.unmask(0).And(mob.Not()).rename("scar_only"))
             # .unweighted() matters: reduceRegion weights partial pixels at the region edge by
             # default, so a plain sum() returns a FRACTIONAL "pixel count" (measured 15493.906
             # on a 0.5 deg box where the true count is 15492). The agreement verdict is unaffected
             # -- month_only/scar_only are reduced the same way -- but the reported numbers would
             # not be integers, and someone would eventually chase the difference as a bug.
             .reduceRegion(ee.Reducer.sum().unweighted(), region,
                           crs=C.SNIC_CRS, crsTransform=C.SNIC_TRANSFORM,
                           maxPixels=int(1e13)).getInfo())
    n = scars_fc(cal_year).size().getInfo()
    print(f"[{cal_year}] {n:,} scars | month px {int(stats['mob']):,} | scar px {int(stats['scar']):,} "
          f"| month-only {int(stats['mob_only']):,} | scar-only {int(stats['scar_only']):,}")


def _export_products(specs, years, launch):
    """Export the three multiband products, whole country, on the pinned grid."""
    region = ee.FeatureCollection(C.ARG_BUFFER_FC).geometry()
    for sub, img, pyr in specs:
        asset_id = f"{C.FINAL_PRODUCTS}/{C.product_name(sub)}"
        # Skip what is already there, so a re-run is resumable rather than three tasks that grind
        # through the whole country only to die on "Cannot overwrite asset". Deliberately NOT an
        # --overwrite: replacing a published product is a decision, not a flag (docs/07 "07c — the scar rasters").
        if asset_exists(asset_id):
            print(f"[skip] {asset_id} already exists")
            continue
        # A year set with a HOLE in it must not describe itself as a range.  `--years` exists
        # so a night is not lost when one of the 27 hand ingests fails (ROADMAP "After"), and a
        # product that lands over 26 years while saying "1999-2025" is a product nobody can tell
        # apart from the complete one.  So: spell the years out when they are not contiguous, and
        # say `partial` when any calendar year of the collection is absent.
        contiguous = years == list(range(years[0], years[-1] + 1))
        absent = [y for y in C.CALENDAR_YEARS if y not in years]
        img = img.set({"source": C.PRODUCT_SOURCE, "region": C.PRODUCT_REGION,
                       "band_format": ("scar_id_{year}" if sub == "annual_burned_id"
                                       else "scar_area_ha_{year}"),
                       "years": (f"{years[0]}-{years[-1]}" if contiguous
                                 else ",".join(str(y) for y in years)),
                       "scar_connectivity": "8-connected, calendar-year",
                       "scar_size_classes": str(C.SCAR_SIZE_LOWER_HA),
                       "area_source": "pixel-count (local), not geometry().area()",
                       "derived_from": C.ANNUAL_BURNED_VECTORS,
                       # The object exclusion rules the SCARS were labelled under (docs/07
                       # "Object exclusion ruleset"). They are inherited from 07b, not applied here — but the
                       # product must still state them, or a scar raster cannot be told
                       # apart from one built before the rules existed.
                       **C.exclusion_rules()})
        if absent:
            img = img.set({"partial": (
                f"INCOMPLETE — {len(years)} of {len(C.CALENDAR_YEARS)} calendar years. "
                f"Missing: {','.join(str(y) for y in absent)}. The missing years had no ingested "
                f"scar FeatureCollection when this was exported; completing the series needs the "
                f"asset deleted and re-exported, since a band cannot be added to a landed image")})
        if not launch:
            print(f"[dry] would export {asset_id}  ({len(years)} bands, pyramiding={pyr})")
            continue
        ee.batch.Export.image.toAsset(
            # NAMESPACED description: `ee.data.listOperations()` is project-scoped and the compute
            # project is shared with the whole network, so a bare `annual_burned_id` can collide with
            # another country's export (CLAUDE.md, docs/07-published_products "Namespace the task descriptions").
            image=img, description=f"{TASK_PREFIX}{sub}", assetId=asset_id, region=region,
            crs=C.SNIC_CRS, crsTransform=C.SNIC_TRANSFORM,
            maxPixels=int(1e13), pyramidingPolicy={".default": pyr},
        ).start()
        print(f"[launched] {asset_id}")


def initialize(project, credentials_path=None):
    """`ee.Initialize`, optionally with a credentials file that is NOT the resident one.

    Same helper as `07-month_of_burn.py` / `07-burned_area_polygons.py` (CLAUDE.md: copy the
    pattern, never `cp` the credentials file into place).  The GEE task queue is PER USER, so
    submitting as the second account (`ivanbarbera@comahue-conicet.gob.ar`, compute project
    `mapbiomas-argentina`) starts the export immediately instead of behind the first account's
    tasks.  Only the COMPUTE project changes — the destination asset path is unaffected.
    """
    if not credentials_path:
        ee.Initialize(project=project)
        return
    from google.oauth2.credentials import Credentials
    stored = json.loads(Path(credentials_path).expanduser().read_text())
    ee.Initialize(Credentials(
        None,
        refresh_token=stored["refresh_token"],
        token_uri=ee.oauth.TOKEN_URI,
        client_id=stored.get("client_id", ee.oauth.CLIENT_ID),
        client_secret=stored.get("client_secret", ee.oauth.CLIENT_SECRET),
        scopes=stored.get("scopes", ee.oauth.SCOPES),
        quota_project_id=stored.get("project"),
    ), project=project)
    print(f"[auth] {credentials_path}  |  compute project {project}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--launch", action="store_true", help="submit the three export tasks")
    ap.add_argument("--check", action="store_true",
                    help="per-year scar-vs-month mask agreement (whole country — one "
                         "reduceRegion per year, so run it on a few years at a time)")
    ap.add_argument("--roi",
                    help="--check extent, 'xmin,ymin,xmax,ymax' (default: the whole country, which "
                         "is a slow interactive reduce — pass a box)")
    ap.add_argument("--years", help="comma-separated calendar years (default: all)")
    ap.add_argument("--project", default=C.GEE_PROJECT,
                    help="compute project to submit under (e.g. mapbiomas-argentina with "
                         "the comahue credentials — the destination asset path does not change)")
    ap.add_argument("--credentials",
                    help="path to a credentials file to authenticate with instead of the "
                         "resident ~/.config/earthengine/credentials (e.g. "
                         "…/credentials.comahue). Nothing on disk is clobbered.")
    args = ap.parse_args()

    initialize(args.project, args.credentials)
    years = ([int(v) for v in args.years.split(",")] if args.years else C.CALENDAR_YEARS)

    if args.check:
        for y in years:
            check(y, args.roi)
        return

    # Both inputs are required: the scar FCs are painted, and the month-of-burn image supplies the
    # mask that forces scar and month coverage to agree (docs/07 "07c — the scar rasters").
    missing_fc = [y for y in years
                  if not asset_exists(f"{C.ANNUAL_BURNED_VECTORS}/scars_{y}")]
    missing_mob = [y for y in years
                   if not asset_exists(f"{C.MONTH_OF_BURN_COL}/{C.product_name('fire_mask')}_{y}")]
    if missing_fc or missing_mob:
        if missing_fc:
            print(f"[abort] scar FeatureCollections not ingested for: {missing_fc}")
            print(f"        upload data/scars-upload-cache/scars_<Y>.zip to "
                  f"{C.ANNUAL_BURNED_VECTORS}/")
        if missing_mob:
            print(f"[abort] month-of-burn images not exported for: {missing_mob}")
            print("        run 07-month_of_burn.py --all --launch and wait for the tasks")
        return

    ids, areas, classes = ee.Image().select(), ee.Image().select(), ee.Image().select()
    for y in years:
        a, b, c = year_bands(y)
        ids, areas, classes = ids.addBands(a), areas.addBands(b), classes.addBands(c)

    _export_products([("annual_burned_id", ids, "mode"),
                      ("annual_burned_area_ha", areas, "median"),
                      ("annual_burned_scar_size_range", classes, "mode")],
                     years, args.launch)

    if not args.launch:
        print("\nDry run only. Re-run with --launch to submit.")


if __name__ == "__main__":
    main()
