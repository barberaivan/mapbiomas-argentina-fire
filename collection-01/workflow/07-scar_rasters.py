#!/usr/bin/env python3
"""
collection-01/workflow/07-scar_rasters.py

Step 07c — the scar-size chain, from the uploaded calendar-year scar vectors.

Runs AFTER:
  * `07-calendar_scars.R scars` has built `data/scars-upload-cache/scars_<Y>.zip`, and
  * Iván has ingested each one by hand as `C.ANNUAL_BURNED_VECTORS/scars_<Y>`
    (no GCS bucket is reachable, so the zip is the deliverable — same hand-off as docs/06 §12).

Produces the network's three scar subproducts, each a SINGLE MULTIBAND image with one band per
calendar year — that is the published shape, confirmed by the launch guide ("Imagen multibanda
con el ID de cada cicatriz") and by `ToPublish/2-toAsset-Public`, whose `band_format` property
(`scar_area_ha_{year}`) only makes sense for a multiband image:

  | product                        | band              | encoding            | pyramiding |
  |--------------------------------|-------------------|---------------------|------------|
  | `annual_burned_id`             | `scar_id_YYYY`    | scar id, int        | mode       |
  | `annual_burned_area_ha`        | `scar_area_ha_YYYY` | ha, float         | median     |
  | `annual_burned_scar_size_range`| `scar_area_ha_YYYY` | class 1-8, uint8  | mode       |

Two deliberate departures from the reference script `5-export_annual_burned_id_and_size_by_year`:

  1. **We paint OUR `area_ha`, we do not recompute it.** The reference maps
     `area_ha = feat.geometry().area()/10000` over the FC. For a pixel-edge polygon with interior
     rings, GEE's geodesic polygon area is not the same number as the pixel-count area that every
     other figure we publish is built from — and the statistics stage is checked to ~1 %
     (docs/09). `07-calendar_scars.R` already wrote `area_ha` from the per-row cell area, so the
     `.map()` is dropped.
  2. **The size classes come from `C.SCAR_SIZE_LOWER_HA`, applied here and not baked into the
     vectors.** The reference script's ranges do NOT match the published Fogo col-5 legend on the
     same pixel values 1-8, so we use the LEGEND's (docs/08 §5.4). Keeping the classification
     server-side is what made that switch free after the vectors were already built -- one
     re-export, not 27 re-uploads.

And one invariant the reference cannot state, because its scars come from its own annual raster:
**the scar mask is forced to equal the month-of-burn mask** (docs/07 §5.6). They are built from
the same pixel set — verified exactly, see `07-calendar_scars.R`'s header — so `--check` reports
the residual per year and the export intersects the two masks so it is zero by construction.

Usage (from the repo ROOT)
--------------------------
  $PYTHON collection-01/workflow/07-scar_rasters.py --check --years 2003,2020  # mask agreement
  $PYTHON collection-01/workflow/07-scar_rasters.py                  # dry run
  $PYTHON collection-01/workflow/07-scar_rasters.py --launch         # 3 export tasks

Shape: three images of 27 BANDS, not 27 images of 3 bands (docs/07 §10) — also what the reference
does (script 5 exports `regions.union().geometry()` over `ee.List.sequence(1999, 2025)` in ONE task
per subproduct, for a whole country, with no region split).

**SETTLED 2026-07-29: the monolith holds.** All three tasks succeeded over the full country, and the
LANDED assets verify exactly — 27 bands each on the pinned grid, `month-only = scar-only = 0` on
2003/2020/2025, and every size class consistent with the painted `area_ha`. A `--per-year` +
`--merge` fallback (27 small tasks into a `scar_year_parts` collection, then a light re-stack) was
carried here in case one task painting 27 FeatureCollections would not hold; it went unused, so it
was deleted rather than left as a second path to maintain. No GEE limit was ever measured against
the monolith — it simply worked. The `--roi` smoke test went the same way.
"""

from __future__ import annotations

import argparse
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
        # --overwrite: replacing a published product is a decision, not a flag (docs/07 §9).
        if asset_exists(asset_id):
            print(f"[skip] {asset_id} already exists")
            continue
        img = img.set({"source": C.PRODUCT_SOURCE, "region": C.PRODUCT_REGION,
                       "band_format": ("scar_id_{year}" if sub == "annual_burned_id"
                                       else "scar_area_ha_{year}"),
                       "years": f"{years[0]}-{years[-1]}",
                       "scar_connectivity": "8-connected, calendar-year",
                       "scar_size_classes": str(C.SCAR_SIZE_LOWER_HA),
                       "area_source": "pixel-count (local), not geometry().area()"})
        if not launch:
            print(f"[dry] would export {asset_id}  ({len(years)} bands, pyramiding={pyr})")
            continue
        ee.batch.Export.image.toAsset(
            # NAMESPACED description: `ee.data.listOperations()` is project-scoped and the compute
            # project is shared with the whole network, so a bare `annual_burned_id` can collide with
            # another country's export (CLAUDE.md, docs/07 §12.7).
            image=img, description=f"{TASK_PREFIX}{sub}", assetId=asset_id, region=region,
            crs=C.SNIC_CRS, crsTransform=C.SNIC_TRANSFORM,
            maxPixels=int(1e13), pyramidingPolicy={".default": pyr},
        ).start()
        print(f"[launched] {asset_id}")


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
    ap.add_argument("--project", default=C.GEE_PROJECT)
    args = ap.parse_args()

    ee.Initialize(project=args.project)
    years = ([int(v) for v in args.years.split(",")] if args.years else C.CALENDAR_YEARS)

    if args.check:
        for y in years:
            check(y, args.roi)
        return

    # Both inputs are required: the scar FCs are painted, and the month-of-burn image supplies the
    # mask that forces scar and month coverage to agree (docs/07 §9).
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
