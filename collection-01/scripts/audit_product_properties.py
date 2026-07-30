#!/usr/bin/env python3
"""
collection-01/scripts/audit_product_properties.py

Audit — and optionally repair — the property block of the nine landed 07d subproducts against what
`workflow/07-subproducts.py` writes today.  Metadata only; it never touches a pixel and never
re-exports.

    $PYTHON collection-01/scripts/audit_product_properties.py            # audit (dry run)
    $PYTHON collection-01/scripts/audit_product_properties.py --apply    # write the blocks

Run it as an audit whenever the products are re-exported or `C.PRODUCT_LULC` moves: a silent drift in
these blocks is how a published asset ends up advertising the wrong land-cover collection.

It was written to fix two real leftovers of the first launch (docs/07 §12.8), both repaired
2026-07-30:

  * the five NON-coverage products carried `lulc_asset` / `lulc_year` although they encode no land
    cover at all — and after the col-3 switch (§12.1) that value was stale as well, since only the
    four `*_coverage` products were re-exported against col-3;
  * `monthly_burned` had inherited the 1999 month image's OWN block through `ee.Image.cat` —
    `year: 1999`, `fire_years: 1998,1999`, `name: …fire_mask_v1_1999`, `pixel_unit`, `min_fire_ha`,
    `fire_call`, `lulc_mask`, `solitary_pixel_filter` — every one of them false or meaningless on a
    27-band product.  The other eight escaped it because they are built by arithmetic, which drops
    input properties.  `07-subproducts.py` now inserts an `.add(0)` for exactly this reason, so a
    re-export cannot reintroduce it.  The mask statements still live on the 07a month images, which
    is where they are true.

⚠️ `updateFields=["properties"]` REPLACES the entire property dict rather than merging, which is why
the desired block is built in full and the diff is printed before anything is written.
"""
import sys, json, ee
sys.path.insert(0, "collection-01")
import utils.constants as C
ee.Initialize(project=C.GEE_PROJECT)

SPECS = [("monthly_burned", "burned_monthly_{year}"), ("annual_burned", "burned_area_{year}"),
         ("monthly_burned_coverage", "burned_coverage_{year}"),
         ("annual_burned_coverage", "burned_coverage_{year}"),
         ("frequency_burned", "fire_frequency_{year1}_{year2}"),
         ("frequency_burned_coverage", "fire_frequency_{year1}_{year2}"),
         ("accumulated_burned", "fire_accumulated_{year1}_{year2}"),
         ("accumulated_burned_coverage", "fire_accumulated_{year1}_{year2}"),
         ("year_last_fire", "classification_{year}")]
YEARS = list(C.CALENDAR_YEARS)
APPLY = "--apply" in sys.argv

for sub, band_format in SPECS:
    aid = f"{C.FINAL_PRODUCTS}/{C.product_name(sub)}"
    have = ee.data.getAsset(aid).get("properties") or {}
    want = {"source": C.PRODUCT_SOURCE, "region": C.PRODUCT_REGION,
            "band_format": band_format, "years": f"{YEARS[0]}-{YEARS[-1]}",
            "derived_from": C.MONTH_OF_BURN_COL}
    if sub.endswith("_coverage"):
        want["lulc_asset"] = C.PRODUCT_LULC
        want["lulc_year"] = "same calendar year as the burn"
    else:
        want["lulc"] = "not used — this product encodes no land cover"
    drop = {k: have[k] for k in have if k not in want}
    change = {k: (have.get(k), want[k]) for k in want if have.get(k) != want[k]}
    print(f"\n{sub}")
    if not drop and not change:
        print("   already correct"); continue
    for k, v in sorted(drop.items()):
        print(f"   - drop  {k} = {json.dumps(v)[:90]}")
    for k, (old, new) in sorted(change.items()):
        print(f"   ~ set   {k}: {json.dumps(old)[:60]} -> {json.dumps(new)[:70]}")
    if APPLY:
        ee.data.updateAsset(aid, {"properties": want}, ["properties"])
        print("   [applied]")
print("\n(dry run — pass --apply to write)" if not APPLY else "\ndone")
