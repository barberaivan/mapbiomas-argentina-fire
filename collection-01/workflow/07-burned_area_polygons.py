#!/usr/bin/env python3
"""
collection-01/workflow/07-burned_area_polygons.py

Step 07e — the FIRE-OBJECT POLYGON LAYER: every mapped fire, all 28 fire-years, in one
FeatureCollection, for sharing with early users.

    projects/…/FIRE/COLLECTION-1/FINAL_PRODUCTS/burned_area_polygons_v1

Nothing is computed here and no geometry is touched: the layer is the step-06 object set
(`objects_raw_<fy>`, 28 FCs) filtered to the accepted fires and stripped to ten properties,
merged and flattened across fire-years.  Measured: **1,263,079 polygons, 74.23 Mha**.

    fire == 1  AND  area_ha >= C.MIN_FIRE_HA

the same POSITIVE selection step 07a paints (docs/07 §1).  `fire` is the deployed call — the
collected label where there is one, else the probit-BART model (docs/06 §5) — so `fire_tag == -1`
means *unlabelled*, never *not fire*, and "not rejected" is not the same filter: 36 objects are
entirely `candseed==3` dieback with a null `fire`, and this excludes them.

WHY "polygons" AND NOT "vectors"
--------------------------------
`FINAL_PRODUCTS/annual_burned_vectors/` is already taken, by the CALENDAR-year scars that feed
the scar-size chain (07b/07c).  Those are a different thing from these — plain 8-connectivity,
calendar-clipped, one scar per connected burn — and reusing the network's word for both would put
two unrelated layers one line apart in the asset tree under near-identical names.  "polygons" also
says what a user actually gets, where a "vector" could be points or lines.

⚠️ THIS LAYER IS IN `FINAL_PRODUCTS` BY DELIBERATE OVERRIDE of docs/08 open #8, which parked the
fire-year vector database OUTSIDE `FINAL_PRODUCTS` until IPAM rules whether Argentina may publish
it.  Iván's call (2026-07-30): early users get a link that stays valid if the ruling is yes, and
Brazil's own col-5 `annual_burned_vectors` is the precedent that the door is open.  The leak risk
is small — `ToPublish/2-toAsset-Public` copies an EXPLICIT subproduct list, not the folder — but
if the ruling is no, this asset moves and the shared link dies with it.

THE TEN PROPERTIES
------------------
| property        | source        | meaning                                                     |
|-----------------|---------------|-------------------------------------------------------------|
| `oid`           | `oid`         | stable object id, `<fy>_<n>` — the key to join user feedback |
|                 |               | back to the object database and its 20 metrics              |
| `fire_year`     | asset name    | the NON-calendar mapping year: 1 May *fy* → 30 Apr *fy*+1   |
| `calendar_year` | `year_cal`    | the MODE of the object's per-pixel calendar years           |
| `area_ha`       | `area_ha`     | pixel-count area (NOT a geodesic polygon area)              |
| `date_med`      | `date_med`    | median burn date, ISO 8601 `YYYY-MM-DD`                     |
| `date_min/max`  | `date_min/max`| first / last burn date, same encoding                       |
| `p_mean`        | `p_mean`      | posterior mean fire probability (probit BART)               |
| `p_width`       | `p_width`     | width of its credible interval, `p_q95 - p_q05`             |
| `seed_mean`     | `seed_mean`   | mean SNIC seed burn probability over the object             |

`fire_year` is NOT a property of the source FCs — it is only implicit in the asset name, so it is
set per source collection here.  Every other name is carried through unchanged except `year_cal`,
which is renamed for people who have never read docs/06.

DATES ARE ISO STRINGS, AND THE FC IS `filterDate`-ABLE
------------------------------------------------------
The object database stores `date_med/min/max` as WHOLE DAYS since 1970-01-01 — an integer 19018
that no user can read in the Inspector or in a QGIS attribute table.  Here they are written as
`YYYY-MM-DD` strings instead (Iván, 2026-07-30).  Nothing is lost: the integers stay in the object
database, `oid` joins back to them, and ISO-8601 still sorts and range-filters correctly because
it sorts lexicographically (`ee.Filter.gte('date_med', '2021-01-01')`).

On top of that each feature carries a GEE timestamp, so the collection answers `filterDate()` —
the first thing a user reaches for:

    system:time_start = date_med   (midnight UTC of the MEDIAN burn day)

**`date_med`, and time_start ONLY — deliberately not the `date_min`..`date_max` interval** (Iván,
2026-07-30).  With `system:time_end` also set, the date filter passes on interval INTERSECTION, so a
fire burning 28 Dec → 4 Jan would be returned by a December query AND a January one, and summing
`area_ha` across months would double-count it.  One timestamp keeps one fire in exactly one bucket,
which is the same choice `calendar_year` already makes (the modal year, §13.3) — so `filterDate`
results stay summable.  The true span is not hidden: `date_min` and `date_max` are right there, and
readable.

`select()` DROPS unlisted properties, `system:time_*` included, so the timestamps are set AFTER
it — setting them first silently loses them (and a `filterDate` that quietly matches nothing looks
exactly like a collection with no fires in that window).

TWO THINGS TO TELL USERS, both recorded in the asset properties
---------------------------------------------------------------
1. **`calendar_year` is the object's MAJORITY year, and the rasters do not agree with it.**  It is
   `mode_int(cyear)` over the object's pixels (`05-objects_metrics.R:239`).  The published rasters
   assign the calendar year and month PER PIXEL, so a fire straddling 31 December is split between
   two years there and lands whole in one year here (docs/07 §1).  Neither is wrong; they answer
   different questions, and a user who cross-tabulates the two without knowing this will find
   "missing" area.
2. **Fire-year 1998 is in this layer and in no published raster.**  3,845 polygons carry
   `calendar_year` 1998 or 1999; the calendar series starts at 1999, so FY1998's Nov–Dec 1998 tail
   (1,058,206 px, ~76 kha) appears here only (docs/07 §2).

`oid` IS UNIQUE PER OBJECT, NOT PER FEATURE — one FY2000 object is 4 rows
-------------------------------------------------------------------------
`objects_raw_2000` itself stores `2000_57529` — a **1,706,171 ha** object — as **4 features** with
disjoint geometry parts, each repeating the whole object's `area_ha` and dates.  That is a vertex
split (`Export.table.toAsset(maxVertices=…)` cuts a geometry that exceeds the limit into pieces),
and it happened UPSTREAM, in the step-06 upload: the sources total **1,263,079 rows / 1,263,076
distinct `oid`**, and FY2000 is the only year affected (all 28 audited).  Two consequences:

* this layer carries all 4 rows, faithfully — merge/dissolve by `oid` to recover the object, and
  never `aggregate_sum('area_ha')` per `oid` without deduplicating first, or that one fire counts
  1.7 Mha four times;
* **never "fix" a duplicate with a blind `distinct('oid')`** — it would keep one part of that fire
  and silently drop 1.3 Mha of it.  `distinct(['oid', '.geo'])` is the safe form: it removes rows
  that are identical INCLUDING geometry, and leaves genuine split parts alone.

⚠️ THE FIRST MERGED EXPORT LANDED WITH 1,249 DUPLICATE ROWS (2026-07-30)
------------------------------------------------------------------------
It completed, and every object was present — but the landed asset held **1,264,328 rows** against
the sources' 1,263,079, and the surplus was **1,249 FY2021 features written twice**, byte-identical
in geometry and in all ten properties (checked: three sampled pairs hash equal; `objects_raw_2021`
has 53,263 rows, all distinct).  Nothing was lost and nothing was wrong per feature; the FY2021
`area_ha` total was inflated by 71,478 ha (3,595,965 vs 3,524,487) and the layer total by the same.

So a 1.26 M-feature table export can silently duplicate a shard, and **a task reaching COMPLETED is
not evidence that it wrote each feature once**.  `--verify` therefore audits row count AND distinct
`oid` per fire-year against the sources — the only check that catches this — and it must be run on
every re-export.  If duplicates come back, `distinct(['oid', '.geo'])` or `--per-year` is the fix.

IS ONE MERGED EXPORT FEASIBLE?  Measured, not assumed
-----------------------------------------------------
The 28 source shapefiles hold **5.12 GB** of raw `.shp` geometry for 1.689 M objects (~190
vertices/polygon), so the fire-only subset is ~4-4.5 GB.  GEE already stores exactly that in the
28 source assets — reading it is not the question.  One `Export.table.toAsset` shuffling 1.26 M
complex multipolygons is: there is no documented feature limit, but this is the upper end of where
such tasks succeed and the failure mode is `User memory limit exceeded` AFTER hours.  Precedent is
against it — Brazil ships `mbfogo_col5_<year>_v1` per year, our scars are 27 per-year assets,
`objects_raw` is 28; nobody in the network ships one merged all-years vector.  Building it locally
and ingesting instead is worse: >2 GB breaks the Shapefile limit and no GCS bucket is reachable
(docs/06 §12).

So it is worth ONE task to find out, with a fallback that wastes nothing:

    --year 2012     one fire-year (22 k polygons, minutes) -> validates the schema on a LANDED
                    asset, and is simultaneously the first asset of the fallback
    --launch        the single merged layer.  If it lands, that is the shareable FC.
    --per-year      the fallback: 28 assets in FINAL_PRODUCTS/burned_area_polygons_by_fire_year/,
                    which users load as one FC in a line (printed by --check)

Usage (from the repo ROOT)
--------------------------
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --check
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --year 2012 --launch   # validate
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --verify --year 2012   # on the asset
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --launch               # the merged one
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --launch --overwrite   # replace it
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --verify               # THE gate
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --per-year --launch    # the fallback
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --set-props            # after landing

`--overwrite` replaces the asset IN PLACE, keeping the name — which is the point: the path is
already shared with early users, so a re-export must not become `_v2`.  GEE writes the new table and
swaps it at completion, so the old one stays readable for the hours in between.

  # as the SECOND account, so this does not queue behind the first account's tasks (the GEE task
  # queue is per user). Only the compute project changes; the destination asset is the same:
  $PYTHON collection-01/workflow/07-burned_area_polygons.py --launch \
      --project mapbiomas-argentina \
      --credentials ~/.config/earthengine/credentials.comahue

Resumable: an asset that exists, or whose task is PENDING/RUNNING, is skipped.  Task descriptions
are namespaced `arg07e_` because `ee.data.listOperations()` is PROJECT-scoped and this compute
project is shared with every other country's team (docs/07 §12.7).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils.constants as C  # noqa: E402

TASK_PREFIX = "arg07e_"
SUBPRODUCT = "burned_area_polygons"

# The fallback's folder.  Distinct from the merged asset's name so the two can coexist while we
# find out whether the single task survives.
BY_YEAR_DIR = f"{C.FINAL_PRODUCTS}/{SUBPRODUCT}_by_fire_year"

# The ten properties, in order.  `fire_year` is set here (it is only implicit in the asset name);
# `year_cal` -> `calendar_year` is the one rename.  Everything else is carried through verbatim so
# the layer speaks the same vocabulary as the object database it came from.
SRC = ["oid", "fire_year", "year_cal", "area_ha",
       "date_med", "date_min", "date_max", "p_mean", "p_width", "seed_mean"]
DST = ["oid", "fire_year", "calendar_year", "area_ha",
       "date_med", "date_min", "date_max", "p_mean", "p_width", "seed_mean"]

FIRE_YEARS = list(range(1998, 2026))          # 28, the object database's full span

DAY_MS = 86_400_000   # the object database's `date_*` are WHOLE DAYS since 1970-01-01


# ---------------------------------------------------------------------------
# auth — run this export as the OTHER account, without swapping the resident file
# ---------------------------------------------------------------------------
def initialize(project, credentials_path=None):
    """`ee.Initialize`, optionally with a credentials file that is NOT the resident one.

    GEE's task queue is PER USER, so a long export submitted by the account that is already
    running 27 other tasks waits behind them.  Submitting it as the second account
    (`ivanbarbera@comahue-conicet.gob.ar`, on the `mapbiomas-argentina` compute project) starts it
    immediately.  Only the COMPUTE project changes — the destination asset path is unaffected, so
    the shared link is the same either way.

    `ee.oauth.get_credentials_path()` hardcodes `~/.config/earthengine/credentials` with no env
    override, and CLAUDE.md's answer is to `cp` the account you want into place.  Passing the file
    explicitly is better: nothing is clobbered, two accounts can be used in the same session, and a
    half-finished swap cannot leave the wrong token resident.  Keep per-account backups
    (`credentials.gmail`, `credentials.comahue`) and point `--credentials` at one.
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


def merged_asset():
    """`FINAL_PRODUCTS/burned_area_polygons_v1` — a PLAIN name, deliberately.

    NOT `C.product_name()`. That builds the network's
    `mapbiomas_argentina_fire_collection1_<subproduct>_v1`, which is mandatory for the published
    raster subproducts because the platform's `band_format` lookup and the publish copy expect it.
    This layer is not one of those: it is ours, it is for people, and it is a name a user has to
    read and type (Iván, 2026-07-30).
    """
    return f"{C.FINAL_PRODUCTS}/{SUBPRODUCT}_v1"


def year_asset(fire_year):
    return f"{BY_YEAR_DIR}/{SUBPRODUCT}_{fire_year}"


# ---------------------------------------------------------------------------
# the layer
# ---------------------------------------------------------------------------
def fire_filter():
    """The accepted-fire filter.  A function, not a module constant: building an `ee.Filter` at
    import time runs before `ee.Initialize()` and dies with "client library not initialized"."""
    return ee.Filter.And(ee.Filter.eq("fire", 1),
                         ee.Filter.gte("area_ha", C.MIN_FIRE_HA))


def iso(days):
    """A `date_*` day number -> an ISO-8601 `YYYY-MM-DD` string, server-side."""
    return ee.Date(ee.Number(days).multiply(DAY_MS)).format("YYYY-MM-dd")


def fires(fire_year):
    """One fire-year's accepted fires, stripped to the ten properties.

    `Feature.select(SRC, DST)` keeps the geometry (retainGeometry defaults True) and DROPS every
    property not listed — which is the point: the source FCs carry all 20 predictors plus the
    three call columns, and this layer is not the object database.

    The three dates become ISO strings, and `system:time_start` is stamped from `date_med` so the
    collection answers `filterDate()`.  Both are set AFTER `select()`, which drops anything unlisted
    — `system:time_*` included.  No accepted object has a null date (all 28 fire-years audited
    2026-07-30), so `ee.Number` on them cannot fail mid-export.
    """
    fc = ee.FeatureCollection(f"{C.OBJECTS_RAW_COL}/objects_raw_{fire_year}").filter(fire_filter())

    def one(f):
        med = ee.Number(f.get("date_med"))
        return (ee.Feature(f)
                .set({"fire_year": fire_year,
                      "date_med": iso(med),
                      "date_min": iso(f.get("date_min")),
                      "date_max": iso(f.get("date_max"))})
                .select(SRC, DST)
                .set("system:time_start", med.multiply(DAY_MS)))

    return fc.map(one)


def merged(years=FIRE_YEARS):
    """All fire-years, merged and flattened into one FeatureCollection."""
    return ee.FeatureCollection([fires(fy) for fy in years]).flatten()


def properties(years, n_features=None):
    """The asset property block — where the two caveats above are written down.

    Set AFTER the export lands (`--set-props`), via `ee.data.updateAsset`, rather than with
    `.set()` on the collection: a property block is not worth risking a multi-hour table task on,
    and updateAsset is deterministic and free.
    """
    p = {
        "source": C.PRODUCT_SOURCE,
        "region": C.PRODUCT_REGION,
        "collection": 1,
        "unit": "one polygon per mapped fire (SNIC fire object)",
        "fire_years": f"{years[0]}-{years[-1]}",
        "fire_year_definition": "non-calendar: 1 May <fire_year> to 30 Apr <fire_year>+1",
        "fire_call": ("fire == 1 — the deployed call: the collected label where there is one, "
                      "else the probit-BART object model (docs/06 §5)"),
        "min_fire_ha": C.MIN_FIRE_HA,
        "calendar_year_definition": (
            "MODE of the object's per-pixel calendar years. The published RASTER products assign "
            "the calendar year per PIXEL, so a fire straddling 31 December is split between two "
            "years there and lands whole in one year here — the two layers answer different "
            "questions and will not cross-tabulate exactly (docs/07 §1)"),
        "date_encoding": "date_med / date_min / date_max: ISO 8601 YYYY-MM-DD (UTC calendar days)",
        "time_start": ("system:time_start is set from date_med — one fire, one instant, so "
                       "filterDate() results can be summed without double-counting a fire that "
                       "straddles the window edge. The real span is date_min..date_max"),
        "area_encoding": "area_ha: pixel-count area, not a geodesic polygon area",
        "oid_uniqueness": (
            "oid identifies an OBJECT, not a row: one FY2000 object (2000_57529, 1,706,171 ha) is "
            "stored as 4 features with disjoint geometry parts, each repeating the whole object's "
            "area_ha and dates — a vertex split inherited from the source upload. Dissolve by oid "
            "to recover the object, and deduplicate before summing area_ha per oid"),
        "p_mean": "posterior mean fire probability (probit BART, docs/06)",
        "p_width": "width of the probability's credible interval (p_q95 - p_q05)",
        "seed_mean": "mean SNIC seed burn probability over the object",
        "series_note": ("fire-year 1998 is included and appears in NO published raster: the "
                        "calendar series starts at 1999, so FY1998's Nov-Dec 1998 tail "
                        "(~76 kha) is here only (docs/07 §2)"),
        "derived_from": C.OBJECTS_RAW_COL,
    }
    if n_features is not None:
        p["n_features"] = n_features
    return p


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------
def check(years):
    """Per-fire-year counts and the property schema, before committing a long task."""
    sizes, areas = [], []
    for fy in years:
        k = ee.FeatureCollection(f"{C.OBJECTS_RAW_COL}/objects_raw_{fy}").filter(fire_filter())
        sizes.append(k.size())
        areas.append(k.aggregate_sum("area_ha"))
    n, ha = ee.List([ee.List(sizes), ee.List(areas)]).getInfo()

    print(f"{'fire_year':>10} {'polygons':>10} {'area_ha':>14}")
    for i, fy in enumerate(years):
        print(f"{fy:>10} {n[i]:>10,} {ha[i]:>14,.0f}")
    print(f"{'TOTAL':>10} {sum(n):>10,} {sum(ha):>14,.0f}")

    got = sorted(fires(years[-1]).first().propertyNames().getInfo())
    user = [p for p in got if not p.startswith("system:")]
    print(f"\n[schema] {got}")
    if user != sorted(DST):
        print(f"[schema] ⚠️ MISMATCH — expected {sorted(DST)}")
    else:
        print("[schema] exactly the ten properties")
    print(f"[schema] system:time_start {'present' if 'system:time_start' in got else '⚠️ MISSING'}"
          " — what makes filterDate() work")

    print(f"\nOne feature of FY{years[-1]}:")
    for k_, v in sorted(fires(years[-1]).first().toDictionary().getInfo().items()):
        print(f"   {k_:16s} {v}")

    print(f"\nIf the merged export fails, the fallback loads as one FC:\n"
          f"  var fc = ee.FeatureCollection(\n"
          f"      ee.List.sequence({years[0]}, {years[-1]}).map(function (y) {{\n"
          f"        return ee.FeatureCollection(ee.String('{BY_YEAR_DIR}/{SUBPRODUCT}_')\n"
          f"                                   .cat(ee.Number(y).format('%d')));\n"
          f"      }})).flatten();")


def verify(asset_id, years):
    """Audit a LANDED asset against the SOURCES — the gate a re-export has to pass.

    The count that matters is **rows AND distinct `oid`, per fire-year**.  The first merged export
    reached COMPLETED while writing 1,249 FY2021 features twice (docstring), and no other check
    noticed: the schema was right, every object was present, and a spot-checked feature was perfect.
    Only counting caught it.  Expected, measured on the sources 2026-07-30:

        1,263,079 rows / 1,263,076 distinct oid / 74,234,381 ha
        the 3-row surplus is FY2000's vertex-split object, and belongs there.

    Runs 28 filtered aggregations on the asset plus 28 on the sources — a few minutes, not free, and
    worth it before a path is shared with anyone.
    """
    if not asset_exists(asset_id):
        print(f"[verify] {asset_id} does not exist yet")
        return
    fc = ee.FeatureCollection(asset_id)
    props, first, t0 = ee.List([fc.first().propertyNames(), fc.first().toDictionary(),
                                fc.first().get("system:time_start")]).getInfo()
    print(f"[verify] {asset_id}")
    got = sorted(p for p in props if not p.startswith("system:"))
    print(f"         schema {'OK' if got == sorted(DST) else 'MISMATCH: ' + str(got)}")
    stamp = f"set: {t0}" if t0 else "⚠️ MISSING — filterDate() will match nothing"
    print(f"         system:time_start {stamp}")
    for k_, v in sorted(first.items()):
        print(f"         {k_:16s} {v}")

    q = []
    for fy in years:
        a = fc.filter(ee.Filter.eq("fire_year", fy))
        s = ee.FeatureCollection(f"{C.OBJECTS_RAW_COL}/objects_raw_{fy}").filter(fire_filter())
        q += [a.size(), a.aggregate_count_distinct("oid"), a.aggregate_sum("area_ha"),
              s.size(), s.aggregate_count_distinct("oid"), s.aggregate_sum("area_ha")]
    r = ee.List(q).getInfo()

    print(f"\n{'fy':>5} {'rows':>9} {'oid':>9} {'area_ha':>12} | "
          f"{'src rows':>9} {'src oid':>9} {'src ha':>12}  verdict")
    tot = [0, 0, 0.0, 0, 0, 0.0]
    bad = []
    for i, fy in enumerate(years):
        v = r[6 * i:6 * i + 6]
        tot = [t + x for t, x in zip(tot, v)]
        ok = v[0] == v[3] and v[1] == v[4] and abs(v[2] - v[5]) < 1.0
        if not ok:
            bad.append((fy, v))
        note = "ok" if ok else (f"⚠️ {v[0] - v[3]:+,} rows, {v[1] - v[4]:+,} oid, "
                                f"{v[2] - v[5]:+,.0f} ha")
        print(f"{fy:>5} {v[0]:>9,} {v[1]:>9,} {v[2]:>12,.0f} | "
              f"{v[3]:>9,} {v[4]:>9,} {v[5]:>12,.0f}  {note}")
    print(f"{'TOT':>5} {tot[0]:>9,} {tot[1]:>9,} {tot[2]:>12,.0f} | "
          f"{tot[3]:>9,} {tot[4]:>9,} {tot[5]:>12,.0f}")
    # The only legitimate surplus is FY2000's vertex-split object: 4 rows, one oid (§13.7).
    dup, want = tot[0] - tot[1], 3 if 2000 in years else 0
    print(f"\n[verify] {dup:,} row(s) share an oid with another row — expected {want}"
          f"{' (FY2000 vertex split)' if want else ''}"
          f"{'  ✅' if dup == want else '  ⚠️ DUPLICATED ROWS'}")
    print("[verify] " + ("✅ every fire-year matches its source, rows and distinct oid"
                         if not bad else
                         f"❌ {len(bad)} fire-year(s) disagree with the source: "
                         f"{[b[0] for b in bad]} — do NOT share this asset"))

    stored = ee.data.getAsset(asset_id).get("properties") or {}
    print(f"[verify] {len(stored)} asset properties set" if stored
          else "[verify] no asset properties yet — run --set-props")


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
def export_one(fc, asset_id, description, launch, overwrite=False):
    """One `Export.table.toAsset`, resumable — and with `--overwrite`, re-runnable IN PLACE.

    Without `overwrite` an existing asset is skipped, because a re-`--launch` would otherwise grind
    for hours and die on "cannot overwrite".  With it, `Export.table.toAsset(overwrite=True)` (API
    ≥ 1.7) replaces the table under the SAME name — which is the only acceptable way to fix a layer
    whose path has already been handed to users.
    """
    if asset_exists(asset_id):
        if not overwrite:
            print(f"[skip] {asset_id} already exists  (--overwrite to replace it in place)")
            return
        print(f"[overwrite] {asset_id} exists and will be REPLACED when the task completes")
    if task_in_flight(description):
        print(f"[skip] {description} has a PENDING/RUNNING task")
        return
    if not launch:
        print(f"[dry] would export {asset_id}  (description {description}"
              f"{', overwrite' if overwrite else ''})")
        return
    task = ee.batch.Export.table.toAsset(collection=fc, description=description, assetId=asset_id,
                                         overwrite=overwrite)
    task.start()
    print(f"[launched] {task.id}  ->  {asset_id}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--launch", action="store_true",
                    help="actually submit the export task(s) (default: build + report only)")
    ap.add_argument("--check", action="store_true",
                    help="per-fire-year counts + the property schema, without exporting")
    ap.add_argument("--verify", action="store_true",
                    help="audit the LANDED asset against the sources — rows AND distinct oid per "
                         "fire-year, the only check that catches a duplicated shard. Run it after "
                         "every export (with --year, that fire-year's asset)")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace the destination asset in place, keeping its name — for "
                         "re-exporting a layer whose path is already shared")
    ap.add_argument("--year", type=int,
                    help="export ONE fire-year into the by_fire_year folder — the schema "
                         "validation run, and simultaneously the first asset of the fallback")
    ap.add_argument("--per-year", action="store_true",
                    help="the fallback: one asset per fire-year instead of the merged layer")
    ap.add_argument("--set-props", action="store_true",
                    help="write the asset property block onto the landed asset(s)")
    ap.add_argument("--project", default=C.GEE_PROJECT,
                    help="compute project (default %(default)s). Use `mapbiomas-argentina` with "
                         "the comahue credentials — the destination asset path does not change")
    ap.add_argument("--credentials",
                    help="path to a credentials file to authenticate with instead of the resident "
                         "~/.config/earthengine/credentials (e.g. …/credentials.comahue). Lets this "
                         "export run as the second account so it does not queue behind the first "
                         "account's tasks, without swapping any file")
    args = ap.parse_args()

    initialize(args.project, args.credentials)

    years = FIRE_YEARS
    if args.year is not None:
        if args.year not in FIRE_YEARS:
            ap.error(f"fire year {args.year} outside {FIRE_YEARS[0]}-{FIRE_YEARS[-1]}")

    if args.check:
        check(years)
        return

    if args.verify:
        if args.year is not None:
            verify(year_asset(args.year), [args.year])
        else:
            verify(merged_asset(), years)
        return

    if args.set_props:
        targets = ([year_asset(args.year)] if args.year is not None
                   else [year_asset(fy) for fy in years] if args.per_year
                   else [merged_asset()])
        for asset_id in targets:
            if not asset_exists(asset_id):
                print(f"[skip] {asset_id} does not exist")
                continue
            yrs = [args.year] if args.year is not None else years
            n = ee.FeatureCollection(asset_id).size().getInfo()
            ee.data.updateAsset(asset_id, {"properties": properties(yrs, n)}, ["properties"])
            print(f"[props] {asset_id}  ({n:,} features)")
        return

    if args.year is not None:
        if args.launch:
            ensure_container(BY_YEAR_DIR, "FOLDER")
        export_one(fires(args.year), year_asset(args.year),
                   f"{TASK_PREFIX}{SUBPRODUCT}_{args.year}", args.launch, args.overwrite)
    elif args.per_year:
        if args.launch:
            ensure_container(BY_YEAR_DIR, "FOLDER")
        for fy in years:
            export_one(fires(fy), year_asset(fy),
                       f"{TASK_PREFIX}{SUBPRODUCT}_{fy}", args.launch, args.overwrite)
    else:
        export_one(merged(years), merged_asset(), f"{TASK_PREFIX}{SUBPRODUCT}",
                   args.launch, args.overwrite)

    if not args.launch:
        print("\nDry run only. Re-run with --launch to submit.")


if __name__ == "__main__":
    main()
