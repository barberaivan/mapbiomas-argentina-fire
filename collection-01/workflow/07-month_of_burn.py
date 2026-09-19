#!/usr/bin/env python3
"""
collection-01/workflow/07-month_of_burn.py

Step 07a — MONTH OF BURN per CALENDAR YEAR, server-side in GEE.

This is the hand-off from our fire-year mapping to the network's calendar-year products
(docs/07 "candseed == 3", docs/07 "The verified calendar-year partition").  Nothing is uploaded here: the two inputs are already in GEE —
the step-06 object FeatureCollections (`objects_raw_<fy>`, one per fire-year, the WHOLE
object set with the `fire` call) and the SNIC per-pixel assets (`snic_<fy>.candseed`,
`snic_metrics_<fy>.abs_date`).  We paint the accepted objects, read each pixel's own burn
date from `abs_date`, and code it as the month within the calendar year.

    calendar year Y  =  Jan-Apr Y  from fire-year (Y-1)   ⊎   May-Dec Y  from fire-year Y

Verified over all 28 fire-years: no object's date range leaves its own fire-year window, so
the two contributions are a strict partition and the merge is a UNION — `max` only ever
arbitrates genuine reburn, where the later date is what the pixel looks like at year end.

Output: one image per calendar year in `C.MONTH_OF_BURN_COL`, single band
`burned_monthly`, uint8, value 1-12, MASKED everywhere else.  That collection is the
network's stage-3 pivot: every raster subproduct (annual, monthly, coverage, frequency,
accumulated, year-last-fire) is derived from it, and its mask is the mask the calendar-year
scar layer must reproduce (step 07b, `07-calendar_scars.R`).

Four things decide correctness — all four are in `_contribution()`:

  1. PIN THE GRID.  `crs=C.SNIC_CRS` + `crsTransform=C.SNIC_TRANSFORM`, never `scale=30`.
     All 56 SNIC assets share one lattice and so do the local carta tiles; `scale: 30` in
     EPSG:4326 is a different grid and a half-pixel shift would misalign this raster from
     the scar rasters painted from locally-built vectors.
  2. THE OBJECT FOOTPRINT IS `paint`, INTERSECTED WITH THE REAL BURNED MASK.  Step 05
     vectorized the accepted pixel set with holes as true interior rings, so painting
     reproduces it — but `.And(candseed > 0)` is kept as the belt-and-braces net, and
     `--check` reports how much the two disagree instead of trusting either.
  3. REPLAY THE DIEBACK LONGITUDE CUT.  Step 05 dropped `candseed==3` east of
     `C.DIEBACK_LON_CUT` before labelling; the `snic_<fy>` asset still carries those pixels.
  4. DIEBACK PIXELS TAKE THEIR PARENT OBJECT'S DATE (`C.DIEBACK_USE_PARENT_DATE`).  Their own
     `abs_date` is a next-year spring dieback-detection date, not a burn date.

GEE has no per-pixel date decomposition: `abs_date` is whole days since epoch and there is
no per-pixel `ee.Date`.  The month is recovered by thresholding against the 12 month-start
day numbers of the calendar year — `month = Σ_k (date >= b_k)` — which is exact because the
pixel set is already restricted to `[Y-01-01, (Y+1)-01-01)`.

Usage (from the repo ROOT)
--------------------------
  $PYTHON collection-01/workflow/07-month_of_burn.py --year 2015            # dry run
  $PYTHON collection-01/workflow/07-month_of_burn.py --year 2015 --check    # small-ROI audit
  $PYTHON collection-01/workflow/07-month_of_burn.py --year 2015 --launch
  $PYTHON collection-01/workflow/07-month_of_burn.py --all   --launch       # 27 tasks — tmux!

  # timing benchmark into TESTS/, nothing production touched (statistics/docs/statistics.md §4)
  $PYTHON collection-01/workflow/07-month_of_burn.py --year 2020 --launch \
      --out-collection projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/TESTS/month_of_burn_benchmark \
      --suffix _benchmark

  # deploy the agriculture filter once the threshold is chosen (statistics/docs/statistics.md §2, §6)
  $PYTHON collection-01/workflow/07-month_of_burn.py --all --launch --overwrite --agri-max 0.4

  # the local<->GEE cross-check (docs/07 "07b — the local scar build"). A year selector is always required, so use --all:
  $PYTHON collection-01/workflow/07-month_of_burn.py --all --stats --launch   # submit the batch jobs
  $PYTHON collection-01/workflow/07-month_of_burn.py --all --stats-read       # compare vs local

`--all --launch` submits one export task per calendar year; run it inside tmux
(CLAUDE.md "Running long scripts").  Resumable: a year whose asset exists, or whose export
is already PENDING/RUNNING, is skipped unless `--overwrite`.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils.constants as C  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
EPOCH = dt.date(1970, 1, 1)
# Per-year validation histograms (batch tasks; see stats_year).
STATS_COL = f"{C.CLASSIFICATION_COLLECTIONS}/mob_month_stats"


def initialize(project, credentials_path=None):
    """`ee.Initialize`, optionally with a credentials file that is NOT the resident one.

    Copied verbatim from `07-burned_area_polygons.py::initialize` (CLAUDE.md: prefer passing the
    file explicitly over `cp`-ing it into place).  The reason to bother here is the 27-task
    launch: the GEE task queue is PER USER, so half the years submitted as the second account
    start immediately instead of queueing behind the first account's. Only the COMPUTE project
    changes; the destination asset path is unaffected.
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


def _day(year, month=1, day=1):
    """Whole days since 1970-01-01 — the `abs_date` encoding."""
    return (dt.date(year, month, day) - EPOCH).days


# ---------------------------------------------------------------------------
# asset plumbing
# ---------------------------------------------------------------------------
def asset_exists(asset_id):
    try:
        ee.data.getAsset(asset_id)
        return True
    except ee.EEException:
        return False


def ensure_container(asset_id, kind):
    """Create a FOLDER / IMAGE_COLLECTION if it is not there yet (idempotent)."""
    if asset_exists(asset_id):
        return False
    ee.data.createAsset({"type": kind}, asset_id)
    print(f"[created] {kind:16s} {asset_id}")
    return True


def task_in_flight(description):
    for op in ee.data.listOperations():
        meta = op.get("metadata", {})
        if (meta.get("description") == description
                and meta.get("state") in ("PENDING", "RUNNING")):
            return True
    return False


# ---------------------------------------------------------------------------
# one fire-year's contribution to one calendar year
# ---------------------------------------------------------------------------
def accepted_objects(fire_year, rules=True, t_grass=None, window=None, t_agri=None):
    """The objects that contribute pixels: called fire, big enough, and matching NEITHER
    exclusion rule (docs/07 "Object exclusion ruleset").

    `fire` is the DEPLOYED call — the collected label where there is one, else the model
    (docs/06 "The three call columns").  `fire_tag = -1` means "unlabelled", never "not fire", which is why we
    filter on `fire` and not on the tag.  Positive selection is deliberate: 36 objects in
    the collection are all-dieback and have a null `fire`/`date_med`, so "not rejected"
    would wrongly admit them.

    Rule A is not just a composition threshold and a season: it also needs the object to
    be under `C.RULE_A_MAX_HA` and to INTERSECT `C.rule_a_aoi_ee()`, the hand-drawn
    agricultural-Pampa polygon.  Without those two the rule deleted two thirds of the
    Delta del Parana, whose marshes remap to the same veg_fire class as a Pampa pasture.

    THE EXCLUSION RULES ARE ON BY DEFAULT.  `rules=False` reproduces the pre-rule,
    unfiltered map (the `mob_month_stats` cross-check, TESTS/ exports) and is recorded as
    such in the asset properties — it is never the published selection.  The thresholds
    default to the FINAL constants; pass one only to explore.
    """
    fc = ee.FeatureCollection(f"{C.OBJECTS_RAW_COL}/objects_raw_{fire_year}")
    # `notNull(date_med)` is unconditional, not tied to DIEBACK_USE_PARENT_DATE. It drops the 36
    # all-dieback objects in the collection, which have no burn date at ALL — they are the wrong
    # thing to publish either way, and a null would paint NaN and poison the max. It also lets
    # _contribution() derive the object footprint from the painted date band's mask, halving the
    # rasterization work (see there).
    keep = [ee.Filter.eq("fire", 1),
            ee.Filter.gte("area_ha", C.MIN_FIRE_HA),
            ee.Filter.notNull(["date_med"])]
    if rules:
        t_grass = C.T_GRASS if t_grass is None else t_grass
        t_agri = C.T_AGRI if t_agri is None else t_agri
        # RULE B — agriculture. `frac_agri` is the object's abundance of veg_fire 1-3
        # (agriculture_{chaco,cuyo-pat,pampa}), EXCLUDING class 4 agriculture-per. Already a
        # property of every objects_raw_<fy> FC, so this costs nothing to evaluate. The rule
        # drops on `>`, so the keep is `<=` — not `<` (docs/07 "Object exclusion ruleset").
        keep.append(ee.Filter.lte("frac_agri", t_agri))
        # RULE A — Pampa grassland in the winter-spring window. `frac_c15` is the SINGLE
        # veg_fire class 15 `grassland_pampa`, not the aggregated `frac_gr_tp`. `date_med` is a
        # NUMBER of days since 1970-01-01, so the window is resolved to day numbers
        # client-side (C.grass_window_days) — no ee.Date round trip per feature.
        # Rule A is CONFINED (docs/07 "Object exclusion ruleset"): it fires only on objects under
        # C.RULE_A_MAX_HA that INTERSECT the hand-drawn agricultural-Pampa AOI.
        # `ee.Filter.bounds` is the exact-geometry intersects predicate and rides the
        # asset's spatial index; the AOI must be PLANAR (C.rule_a_aoi_ee) or its
        # geodesic edges bow away from the straight lon/lat lines the local build
        # tests against — measured, that alone moves 6 objects in FY2020.
        lo, hi = C.grass_window_days(fire_year, window)
        keep.append(ee.Filter.Not(ee.Filter.And(
            ee.Filter.gt("frac_c15", t_grass),
            ee.Filter.gte("date_med", lo),
            ee.Filter.lte("date_med", hi),
            ee.Filter.lt("area_ha", C.RULE_A_MAX_HA),
            ee.Filter.bounds(C.rule_a_aoi_ee()))))
    return fc.filter(ee.Filter.And(*keep))


def _contribution(fire_year, cal_year, **rule_kw):
    """Month-of-burn (1-12) for the part of `cal_year` that fire-year `fire_year` covers.

    Masked everywhere else.  Returns None-free: an empty contribution is simply a
    fully-masked image, which `max()` ignores.
    """
    fc = accepted_objects(fire_year, **rule_kw)
    cs = ee.Image(f"{C.SNIC_COL}/snic_{fire_year}").select("candseed")
    date = ee.Image(f"{C.SNIC_METRICS_COL}/snic_metrics_{fire_year}").select("abs_date")

    # (2) object footprint — from ONE rasterization, not two. ee.Image().paint() is MASKED OUTSIDE
    # the features (verified), and `date_med` is notNull for every feature in `fc`, so the painted
    # date band is non-null exactly on the object footprint: its mask IS the footprint. Painting the
    # FC once instead of twice per fire-year halves what is the dominant cost of this export.
    parent_date = ee.Image().paint(fc, "date_med")
    footprint = parent_date.mask()

    # (3) replay step 05's Patagonia dieback longitude cut: candseed==3 survives only WEST.
    #
    # DO NOT "optimize" this into a clipped constant. `ee.Image.constant(1).clip(west_rect)` looks
    # cheaper than pixelLonLat (which materializes two float bands), but `clip` sets the image's
    # FOOTPRINT and `unmask(0)` does not reset it — so the .And()/.Or() below intersect footprints
    # and confine the ENTIRE result to west of the cut. Measured: the Chaco audit box (east of the
    # cut) went from 32,546 burned px to 0, i.e. it would have silently emptied most of the country.
    lon = ee.Image.pixelLonLat().select("longitude")
    burned = cs.gt(0).And(cs.neq(3).Or(lon.lte(C.DIEBACK_LON_CUT)))

    # (4) a dieback pixel has no burn date of its own — take the parent object's median.
    if C.DIEBACK_USE_PARENT_DATE:
        date = date.where(cs.eq(3), parent_date)

    # restrict to this calendar year. NOT shortcut to "Jan-Apr for the older fire-year":
    # substituted or not, dieback dates genuinely leave the fire-year window.
    lo, hi = _day(cal_year, 1, 1), _day(cal_year + 1, 1, 1)
    keep = footprint.And(burned).And(date.gte(lo)).And(date.lt(hi))

    # month = Σ_k (date >= first day of month k) — exact on [lo, hi).
    month = ee.Image.constant(0)
    for m in range(1, 13):
        month = month.add(date.gte(_day(cal_year, m, 1)))
    return month.updateMask(keep).rename(C.MONTH_OF_BURN_BAND).toUint8()


def month_of_burn(cal_year, **rule_kw):
    """The published month-of-burn image for one calendar year."""
    parts = [_contribution(fy, cal_year, **rule_kw) for fy in (cal_year - 1, cal_year)]
    img = (ee.ImageCollection(parts).max()          # union; later date wins on reburn
           .rename(C.MONTH_OF_BURN_BAND).toUint8())
    return img.set({
        "source": C.PRODUCT_SOURCE,
        "pixel_unit": "month",
        "name": f"{C.product_name('fire_mask')}_{cal_year}",
        "year": cal_year,
        "region": C.PRODUCT_REGION,
        "fire_years": f"{cal_year - 1},{cal_year}",
        "min_fire_ha": C.MIN_FIRE_HA,
        "fire_call": "fire",                        # docs/06 "The three call columns"
        "dieback_parent_date": int(C.DIEBACK_USE_PARENT_DATE),
        "lulc_mask": "embedded-upstream (veg_fire non-burnable classes are unreachable "
                     "as SNIC candidates; stricter than the reference water-only rule)",
        "solitary_pixel_filter": f"embedded-upstream (object >= {C.MIN_FIRE_HA} ha)",
        "system:time_start": ee.Date.fromYMD(cal_year, 1, 1).millis(),
        "system:time_end": ee.Date.fromYMD(cal_year + 1, 1, 1).millis(),
        # The two object exclusion rules, in words, so the asset states its own selection.
        **C.exclusion_rules(t_grass=rule_kw.get("t_grass"), window=rule_kw.get("window"),
                            t_agri=rule_kw.get("t_agri"),
                            applied=rule_kw.get("rules", True)),
    })


# ---------------------------------------------------------------------------
# audit — small region only, so it stays cheap
# ---------------------------------------------------------------------------
def check(cal_year, roi, **rule_kw):
    """Per-month pixel histogram + the footprint/candseed disagreement, over a small ROI.

    The histogram is the number to compare against `07-calendar_scars.R`'s per-year
    validation CSV: if the local mask and this raster agree, the scar layer's mask is the
    month raster's mask, which is what docs/07 "07c — the scar rasters" requires.
    """
    img = month_of_burn(cal_year, **rule_kw)
    hist = img.reduceRegion(ee.Reducer.frequencyHistogram(), roi,
                            crs=C.SNIC_CRS, crsTransform=C.SNIC_TRANSFORM,
                            maxPixels=int(1e10)).getInfo()
    h = {int(float(k)): int(v) for k, v in (hist.get(C.MONTH_OF_BURN_BAND) or {}).items()}
    total = sum(h.values())
    print(f"\n[check] calendar {cal_year}: {total:,} burned px in the ROI")
    for m in sorted(h):
        print(f"          month {m:>2}: {h[m]:>12,}")

    # how much would we lose / gain by trusting polygon fill alone?
    for fy in (cal_year - 1, cal_year):
        fc = accepted_objects(fy)
        paint = ee.Image().paint(fc, 1).gt(0)
        cs = ee.Image(f"{C.SNIC_COL}/snic_{fy}").select("candseed")
        lon = ee.Image.pixelLonLat().select("longitude")
        burned = cs.gt(0).And(cs.neq(3).Or(lon.lte(C.DIEBACK_LON_CUT)))
        pair = (paint.unmask(0).rename("paint")
                .addBands(burned.unmask(0).rename("burned")))
        d = pair.reduceRegion(ee.Reducer.sum(), roi,
                              crs=C.SNIC_CRS, crsTransform=C.SNIC_TRANSFORM,
                              maxPixels=int(1e10)).getInfo()
        only_paint = (paint.unmask(0).And(burned.unmask(0).Not())
                      .reduceRegion(ee.Reducer.sum(), roi, crs=C.SNIC_CRS,
                                    crsTransform=C.SNIC_TRANSFORM,
                                    maxPixels=int(1e10)).getInfo())
        print(f"        FY{fy}: painted={int(d['paint']):,}  burned(cand)={int(d['burned']):,}  "
              f"painted-but-not-burned={int(list(only_paint.values())[0]):,}")


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
def stats_year(cal_year, region, launch):
    """Submit a BATCH task for the whole-country per-month pixel histogram of one year.

    Must be a batch task, not `reduceRegion(...).getInfo()`: an interactive whole-country reduce at
    30 m over a 74085 x 123601 grid hits "Computation timed out" (measured on 2000). Batch tasks
    have no such deadline.

    The result is the number that `07-calendar_scars.R`'s `scars_<Y>_months.csv` must match. Both
    sides derive from the same object pixel set — verified exact — so any divergence is a bug, not
    tolerance. Read the finished tables back with `--stats-read`.
    """
    asset_id = f"{STATS_COL}/mob_months_{cal_year}"
    if asset_exists(asset_id):
        print(f"[skip] {asset_id} already exists")
        return
    # Reduce over the EXPORTED image when it exists — reading a materialized, pyramided asset is
    # far cheaper than re-running the paint chain just to count its pixels. Fall back to computing
    # it only if the year has not finished exporting yet.
    img_id = f"{C.MONTH_OF_BURN_COL}/{C.product_name('fire_mask')}_{cal_year}"
    if asset_exists(img_id):
        img = ee.Image(img_id)
    else:
        print(f"[note] {cal_year} not exported yet — reducing the computed image instead")
        img = month_of_burn(cal_year)
    # ONE SCALAR PROPERTY PER MONTH, never a Dictionary. Two export-time failures are baked in
    # here, both measured, both silent until the task died hours later:
    #
    #   1. `ee.Feature(None, …)` -> "Unable to export features with null geometry". A table ASSET
    #      cannot hold a null-geometry feature (toDrive/CSV can, but then --stats-read cannot read
    #      it back). The point below is a placeholder and carries no meaning.
    #   2. A `frequencyHistogram` dictionary -> "Unable to encode value 'histogram' of feature 0:
    #      invalid type Dictionary<Long>". A table asset's properties are SCALARS; there is no
    #      dictionary column. All 27 tasks failed this way on 2026-07-29. So the histogram is
    #      flattened into `m01`..`m12` before it ever reaches the feature.
    #
    # `img.eq(m)` keeps the image's mask, so summing it counts burned pixels of that month only —
    # no unmask(0) and no dense pass over the 9.16 B-cell grid. And `.unweighted()` is not
    # optional: reduceRegion weights partial pixels at the region boundary by default, which
    # returns a FRACTIONAL pixel count and would put this check permanently a few pixels off the
    # local build (the same artefact docs/07 "07c — the scar rasters" records for the scar check).
    months = ee.Image.cat([img.eq(m).rename(f"m{m:02d}") for m in range(1, 13)])
    d = months.reduceRegion(ee.Reducer.sum().unweighted(), region,
                            crs=C.SNIC_CRS, crsTransform=C.SNIC_TRANSFORM,
                            maxPixels=int(1e13))
    props = {f"m{m:02d}": ee.Number(d.get(f"m{m:02d}")).round() for m in range(1, 13)}
    props["year"] = cal_year
    props["n_px"] = ee.Number(ee.List(list(props[f"m{m:02d}"] for m in range(1, 13)))
                              .reduce(ee.Reducer.sum()))
    fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([-64.0, -34.0]), props)])
    task = ee.batch.Export.table.toAsset(collection=fc, description=f"mobstats_{cal_year}",
                                         assetId=asset_id)
    if launch:
        task.start()
        print(f"[launched] {task.id} -> {asset_id}")
    else:
        print(f"[dry] would submit histogram task for {cal_year} -> {asset_id}")


def stats_read(years, csv_path=None):
    """Print the GEE histograms next to the local ones and flag any disagreement.

    `--csv` dumps them long-format. These 27 assets are the whole-country per-month burned
    PIXEL COUNT for 1999-2025 and they already exist (they were the 07b cross-check), so the
    national time series and the national pirogram are available with no compute at all
    (statistics/docs/statistics.md §5.1).

    Two caveats that must travel with the numbers:
      * PIXEL COUNTS, NOT HECTARES, and the naive conversion is badly wrong. The lattice step
        is 0.000269494585236 DEGREES, so a pixel is ~30 m north-south everywhere but only
        ~30*cos(lat) m east-west: 0.09 ha is the equatorial figure. Measured against the object
        database, px x 0.09 gives 81.93 Mha where the truth is 69.12 Mha -- **an 18.5 %
        overstatement**, i.e. a mean effective pixel of 0.0759 ha (lat ~32 deg).
        And the bias is not uniform across months: Patagonian fires (lat ~45 deg, 0.064 ha/px)
        peak in summer while Chaco fires (lat ~25 deg, 0.082 ha/px) peak in late winter, so
        even the PIROGRAM'S SHAPE is skewed toward the southern months by this.
        Use these counts for RELATIVE structure only. Anything quoted in hectares comes
        from the network's toolkit (statistics/docs/statistics.md §2), which sums `ee.Image.pixelArea()`.
      * They describe the CURRENT, UNFILTERED map — no agriculture filter (statistics/docs/statistics.md §2).
    """
    local_dir = REPO_ROOT / "collection-01/data/objects-scars"
    any_bad = False
    rows = []
    for y in years:
        asset_id = f"{STATS_COL}/mob_months_{y}"
        if not asset_exists(asset_id):
            print(f"[{y}] histogram task not finished ({asset_id})")
            continue
        f = ee.FeatureCollection(asset_id).first().toDictionary().getInfo() or {}
        gee = {m: int(f.get(f"m{m:02d}", 0)) for m in range(1, 13)}
        gee = {m: v for m, v in gee.items() if v}
        lpath = local_dir / f"scars_{y}_months.csv"
        loc = {}
        if lpath.exists():
            with open(lpath, newline="") as fh:
                loc = {int(r["month"]): int(r["n_px"]) for r in csv.DictReader(fh)}
        diffs = {m: gee.get(m, 0) - loc.get(m, 0) for m in range(1, 13)
                 if gee.get(m, 0) != loc.get(m, 0)}
        tag = "MATCH" if (loc and not diffs) else ("no local months csv" if not loc else "DIFFERS")
        if loc and diffs:
            any_bad = True
        print(f"[{y}] GEE {sum(gee.values()):>12,} px | local {sum(loc.values()):>12,} px | {tag}"
              + (f" {diffs}" if diffs else ""))
        for m in range(1, 13):
            rows.append({"year": y, "month": m, "n_px": gee.get(m, 0)})
    if csv_path and rows:
        with open(csv_path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["year", "month", "n_px"])
            w.writeheader()
            w.writerows(rows)
        print(f"\n[csv] {len(rows)} rows -> {csv_path}   (PIXEL COUNTS, unfiltered map)")
    if any_bad:
        print("\nA divergence here is a BUG, not tolerance — both sides come from the same "
              "object pixel set (docs/07 'Why the object polygons can be trusted as the pixel set').")


def export_year(cal_year, region, launch, overwrite=False,
                out_col=None, suffix="", **rule_kw):
    """Export one calendar year.

    `out_col` + `suffix` exist so a timing/benchmark run lands in TESTS/ instead of next to a
    published product (statistics/docs/statistics.md §4.4). The task description carries the same suffix, because the
    in-flight check matches on description and the compute project is shared with the whole
    network (CLAUDE.md): a bare `mob_2012` could collide with another country's task.
    """
    out_col = out_col or C.MONTH_OF_BURN_COL
    asset_id = f"{out_col}/{C.product_name('fire_mask')}_{cal_year}{suffix}"
    description = f"mob_{cal_year}{suffix}"

    exists = asset_exists(asset_id)
    if exists and not overwrite:
        print(f"[skip] {asset_id} already exists (use --overwrite to replace)")
        return
    if task_in_flight(description):
        print(f"[skip] {description} has a PENDING/RUNNING task")
        return

    img = month_of_burn(cal_year, **rule_kw)
    task = ee.batch.Export.image.toAsset(
        image=img,
        description=description,
        assetId=asset_id,
        region=region,
        crs=C.SNIC_CRS,               # pin the grid — never scale=30 (see module docstring)
        crsTransform=C.SNIC_TRANSFORM,
        maxPixels=int(1e13),
        pyramidingPolicy={C.MONTH_OF_BURN_BAND: "mode"},
        overwrite=overwrite,
    )
    if launch:
        task.start()
        print(f"[launched] {task.id}  ->  {asset_id}")
    else:
        print(f"[dry] would export {asset_id}  bands={img.bandNames().getInfo()}  "
              f"fire_years={cal_year - 1},{cal_year}\n"
              f"      rules: {img.get('exclusion_rule_a').getInfo()}\n"
              f"             {img.get('exclusion_rule_b').getInfo()}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--year", type=int, help="single CALENDAR year (e.g. 2015)")
    grp.add_argument("--all", action="store_true",
                     help=f"every calendar year {C.CALENDAR_YEARS[0]}..{C.CALENDAR_YEARS[-1]}")
    ap.add_argument("--launch", action="store_true",
                    help="actually submit the export task(s) (default: build + report only)")
    ap.add_argument("--check", action="store_true",
                    help="audit over a SMALL roi (--roi) instead of exporting: per-month "
                         "pixel histogram + polygon-fill vs candseed disagreement")
    ap.add_argument("--roi", default="test",
                    help="--check extent: 'test' (the tiny San Ramon ROI) or "
                         "'xmin,ymin,xmax,ymax'. Never the whole country — reduceRegion at "
                         "30 m over Argentina is not a cheap call.")
    ap.add_argument("--stats", action="store_true",
                    help="submit a BATCH task per year for the whole-country per-month pixel "
                         "histogram (an interactive reduce over Argentina times out). This is the "
                         "cross-check against 07-calendar_scars.R's scars_<Y>_months.csv")
    ap.add_argument("--stats-read", action="store_true",
                    help="print finished --stats histograms beside the local ones and flag any "
                         "disagreement")
    ap.add_argument("--csv", default=None, metavar="FILE",
                    help="--stats-read: also write the whole-country per-month pixel counts "
                         "long-format. Pixel counts, not hectares, and of the UNFILTERED map")
    ap.add_argument("--overwrite", action="store_true",
                    help="re-export a year whose asset exists, replacing it in place")
    ap.add_argument("--no-exclusions", action="store_true",
                    help="build the UNFILTERED map — neither exclusion rule applied. Only for "
                         "reproducing the pre-rule numbers (mob_month_stats) or a TESTS/ export; "
                         "never for a published asset. Recorded in the asset properties.")
    ap.add_argument("--t-agri", type=float, default=None, metavar="T",
                    help=f"override rule B's threshold (default C.T_AGRI = {C.T_AGRI}); "
                         "docs/07 'Object exclusion ruleset'. For exploration only — the default is FINAL.")
    ap.add_argument("--t-grass", type=float, default=None, metavar="T",
                    help=f"override rule A's threshold (default C.T_GRASS = {C.T_GRASS}); "
                         "docs/07 'Object exclusion ruleset'. For exploration only — the default is FINAL.")
    ap.add_argument("--out-collection", default=None, metavar="ASSET",
                    help="write to this ImageCollection instead of the published one — for "
                         "benchmark/timing runs (statistics/docs/statistics.md §4.4). Created if missing.")
    ap.add_argument("--suffix", default="", metavar="STR",
                    help="appended to the asset name AND the task description, e.g. '_benchmark'")
    ap.add_argument("--project", default=C.GEE_PROJECT,
                    help="GEE compute project to initialize under (default: %(default)s)")
    ap.add_argument("--credentials", default=None, metavar="FILE",
                    help="submit as another account (the task queue is PER USER) — e.g. "
                         "~/.config/earthengine/credentials.comahue, which needs "
                         "--project mapbiomas-argentina")
    args = ap.parse_args()

    initialize(args.project, args.credentials)

    # The exclusion rules are ON unless explicitly disabled (docs/07 "Object exclusion ruleset"). Passed as one dict
    # so every entry point below — check, export_year, month_of_burn — cannot disagree.
    rule_kw = {"rules": not args.no_exclusions,
               "t_grass": args.t_grass, "t_agri": args.t_agri}
    if args.no_exclusions:
        print("[filter] NO EXCLUSION RULES — this is not the published selection")
    else:
        # Printed from C.exclusion_rules(), the SAME text stamped on the exported asset, so
        # this line cannot drift from what is actually applied.  Hand-written here, it did:
        # 8032aa2 added `area_ha < 150` and the AOI intersect to the filter and left this print
        # describing the UNCONFINED rule, so the 2002 relaunch on 13 Sep announced the broken
        # selection while building the correct one.  This is the line a human reads to check
        # which selection is being built.
        r = C.exclusion_rules(t_grass=args.t_grass, t_agri=args.t_agri)
        print(f"[filter] {r['exclusion_rule_a']}")
        print(f"[filter] {r['exclusion_rule_b']}")

    years = C.CALENDAR_YEARS if args.all else [args.year]
    bad = [y for y in years if y not in C.CALENDAR_YEARS]
    if bad:
        ap.error(f"calendar year(s) {bad} outside {C.CALENDAR_YEARS[0]}-{C.CALENDAR_YEARS[-1]}")

    if args.stats_read:
        stats_read(years, args.csv)
        return

    if args.stats:
        if args.launch:            # a dry run must not leave containers behind
            ensure_container(STATS_COL, "FOLDER")
        region = ee.FeatureCollection(C.ARG_BUFFER_FC).geometry()
        for y in years:
            stats_year(y, region, args.launch)
        if not args.launch:
            print("\nDry run only. Re-run with --launch to submit.")
        return

    if args.check:
        roi = (ee.Geometry.Polygon(C.TEST_ROI_COORDS, None, False) if args.roi == "test"
               else ee.Geometry.Rectangle([float(v) for v in args.roi.split(",")], None, False))
        for y in years:
            check(y, roi, **rule_kw)
        return

    out_col = args.out_collection or C.MONTH_OF_BURN_COL
    if args.launch:                # ditto — creating assets is not a dry-run side effect
        if args.out_collection:
            parent = out_col.rsplit("/", 1)[0]
            ensure_container(parent, "FOLDER")
            ensure_container(out_col, "IMAGE_COLLECTION")
        else:
            ensure_container(C.CLASSIFICATION_COLLECTIONS, "FOLDER")
            ensure_container(C.MONTH_OF_BURN_COL, "IMAGE_COLLECTION")

    region = ee.FeatureCollection(C.ARG_BUFFER_FC).geometry()
    for y in years:
        export_year(y, region, args.launch, args.overwrite,
                    out_col=out_col, suffix=args.suffix, **rule_kw)

    if not args.launch:
        print("\nDry run only. Re-run with --launch to submit the task(s).")


if __name__ == "__main__":
    main()
