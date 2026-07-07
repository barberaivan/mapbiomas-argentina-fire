"""
collection-01/scripts/annual_data_download.py

Sample the ANNUAL burn-probability time-series metrics (step-03 `bpts`) at the
training points, and download one raw CSV per region.

ROLE (revised): the seed/candidate threshold study now recomputes the metrics
LOCALLY from the training observations, period-based, in
scripts/bp_ts_metrics_local_train.R (docs/04-snic.md §"Ground seeds & candidates
in the data") — that path needs no GEE and runs on all downloaded data now. This
script is retained as the VALIDATION sampler: it pulls the exported year-based
`bpts` values at a fire's points so the local computation can be hard-checked
against production on a single mid-year fire (scripts/test-bp_ts_metrics_local.R).

It emits the RAW per-point × per-sampled-year rows (int16 bands left encoded;
decoded downstream). This is calibration tooling, not a pipeline step, so it
lives in scripts/ alongside download_observations.py, not in workflow/.

What it does, per training fire (from that region's `training_fires`):
  1. Decide which year(s) of `bpts` to sample from the fire's burn window
     [pre_upr, post_lwr]:
       - within one calendar year  -> the single fire year
       - straddling Dec 31/Jan 1    -> BOTH {fire_year-1, fire_year}
     A straddling fire is ambiguous about which annual image shows a given
     point (and it varies point-to-point), so we sample both and let R pick
     the max-`delta3_peak` year per BURNED point (docs/04-snic.md §4).  Missing
     window bounds -> conservative double.
  2. For each such year, mosaic that year's `bpts` tiles (Argentina + the
     mapbiomas-chaco 1999-2009 overflow) and `sampleRegions` at the fire's
     training points.
  3. Tag each row with the point class (burned/unburned), fire/region,
     `sample_year`, and the fire's window bounds (pre_upr / post_lwr /
     post_upr) so R can run the `date_post`-vs-window contamination gate on
     the unburned points.

Band values are the RAW int16-encoded `bpts` bands (probabilities ×10000, days
as-is; see docs/03-bpts.md §3.7) — decoding is done in R, keeping this export
simple and compact.

NOTE ON COVERAGE: `bpts` is still exporting.  A fire whose year(s) are not yet
exported contributes nothing (its points fall on masked/absent tiles).  We
pre-check which years exist and log per-fire skips, so this is safe to run now
on the ready subset and re-run once exports complete (docs/04-snic.md §"Do it
now?").  Only production `bpts_YYYY_<tile>` assets are sampled (the merged
collections), never the eecutest/tilemerge test assets.

Usage
-----
  python collection-01/scripts/annual_data_download.py --region PAT
  python collection-01/scripts/annual_data_download.py --region ALL
  python collection-01/scripts/annual_data_download.py --region CHACO --fire fire_07
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C
from utils import functions as F

# Reuse the robust CSV fetch + writer from the observations downloader (same
# getDownloadURL + retry/backoff path).  Per-fire fetches stay well under the
# ~32 MB signed-URL cap, so no Drive round-trip is needed.
from download_observations import _fetch_csv, _write_csv, DATA_DIR


# ─── bpts access ──────────────────────────────────────────────────────────────

def available_bpts_years():
    """Set of focal years that have at least one exported `bpts` image, across
    the Argentina collection and the mapbiomas-chaco 1999-2009 overflow."""
    col = (ee.ImageCollection(C.BP_TS_METRICS_COL)
           .merge(ee.ImageCollection(C.BP_TS_METRICS_COL_CHACO)))
    return set(int(y) for y in col.aggregate_array("year").getInfo())


def bpts_mosaic(year):
    """Single mosaicked `bpts` image for a focal year (raw int16 bands)."""
    col = (ee.ImageCollection(C.BP_TS_METRICS_COL)
           .merge(ee.ImageCollection(C.BP_TS_METRICS_COL_CHACO))
           .filter(ee.Filter.eq("year", year)))
    return col.mosaic()


# ─── which year(s) to sample ────────────────────────────────────────────────

def _year(date_str):
    return int(str(date_str)[:4])


def years_to_sample(pre_upr, post_lwr):
    """(years, straddles, fire_year) for one fire.

    The burn is bracketed by (pre_upr, post_lwr].  If those bounds fall in
    different calendar years the fire straddles the New Year -> sample both
    {fire_year-1, fire_year}; otherwise the single fire year.  `fire_year`
    (nominal) = year(post_lwr) — the first confirmed post-fire observation.
    Missing pre_upr -> assume straddle (conservative double); missing post_lwr
    -> caller must skip (no nominal year).
    """
    if post_lwr is None:
        return [], False, None
    fire_year = _year(post_lwr)
    straddles = (pre_upr is None) or (_year(pre_upr) != fire_year)
    years = [fire_year - 1, fire_year] if straddles else [fire_year]
    return years, straddles, fire_year


# ─── per-fire sampling ──────────────────────────────────────────────────────

def _load_locations(fire_id, region):
    """training_locations FC for one fire (col1, PAT falls back to col0).
    Mirrors workflow/01-training_data_export.py:_load_locations."""
    token = C.fire_token(fire_id)
    path_col1 = f"{C.TRAINING_DATA_COL1}/{region}/training_locations-{token}"
    try:
        ee.data.getAsset(path_col1)
        return ee.FeatureCollection(path_col1)
    except Exception:
        pass
    if region == "PAT":
        path_col0 = f"{C.TRAINING_DATA_COL0}/training_locations-{token}"
        try:
            ee.data.getAsset(path_col0)
            return ee.FeatureCollection(path_col0)
        except Exception:
            pass
    return None


def sample_fire(props, region, locations, years):
    """FeatureCollection of point × year rows for one fire, over `years`.

    Carries the point's own class/point_id/coords plus fire metadata and the
    window bounds R needs for the contamination gate.
    """
    fire_id  = props["fire_id"]
    pre_upr  = props.get("pre_upr")
    post_lwr = props.get("post_lwr")
    post_upr = props.get("post_upr_long")

    locations = F.assign_point_ids(locations)   # sets point_id 0..n-1 per fire

    def _add_coords(f):
        c = f.geometry().coordinates()
        return f.set({"lon": c.get(0), "lat": c.get(1)})

    pts = locations.map(_add_coords)

    out = None
    for y in years:
        samp = bpts_mosaic(y).sampleRegions(
            collection=pts,
            scale=30,
            geometries=False,   # flat CSV; lon/lat carried as properties
            tileScale=4,
        )

        def _add_meta(feat, y=y):
            return feat.set({
                "fire_id":     fire_id,
                "region":      region,
                "sample_year": y,
                "pre_upr":     pre_upr,
                "post_lwr":    post_lwr,
                "post_upr":    post_upr,
            })

        fc = samp.map(_add_meta)
        out = fc if out is None else out.merge(fc)
    return out


# ─── main ────────────────────────────────────────────────────────────────────

def process_region(region, available, only_fire=None):
    fires_path = f"{C.TRAINING_DATA_COL1}/{region}/training_fires"
    fires_info = ee.FeatureCollection(fires_path).getInfo()["features"]

    if only_fire is not None:
        want = C.fire_token(only_fire)
        fires_info = [f for f in fires_info
                      if C.fire_token(f["properties"]["fire_id"]) == want]

    all_rows, fieldnames = [], []
    seen = set()
    fire_log = []

    for feat in fires_info:
        props   = feat["properties"]
        fire_id = props["fire_id"]

        years, straddles, fire_year = years_to_sample(
            props.get("pre_upr"), props.get("post_lwr"))
        if fire_year is None:
            print(f"  {fire_id}: no post_lwr → cannot date fire, skipping.")
            fire_log.append({"fire_id": fire_id, "status": "skipped",
                             "reason": "no post_lwr"})
            continue

        sample_years = [y for y in years if y in available]
        if not sample_years:
            print(f"  {fire_id}: bpts not exported for years {years}, skipping.")
            fire_log.append({"fire_id": fire_id, "status": "skipped",
                             "reason": f"years {years} not in bpts yet",
                             "fire_year": fire_year})
            continue

        locations = _load_locations(fire_id, region)
        if locations is None:
            print(f"  {fire_id}: WARNING training_locations not found, skipping.")
            fire_log.append({"fire_id": fire_id, "status": "skipped",
                             "reason": "no locations"})
            continue

        fc = sample_fire(props, region, locations, sample_years)
        try:
            rows, fields = _fetch_csv(fc)
        except Exception as exc:                       # noqa: BLE001
            print(f"  {fire_id}: FAILED ({exc})")
            fire_log.append({"fire_id": fire_id, "status": "failed",
                             "reason": str(exc)})
            continue

        # Union the field order across fires (masked bands can drop a column).
        for f in fields:
            if f not in seen:
                seen.add(f)
                fieldnames.append(f)
        all_rows.extend(rows)

        flag = " [straddle→2yr]" if straddles else ""
        print(f"  {fire_id}: {len(rows)} rows over years {sample_years}{flag}")
        fire_log.append({"fire_id": fire_id, "status": "ok",
                         "years": sample_years, "straddles": straddles,
                         "fire_year": fire_year, "n_rows": len(rows)})

    if not all_rows:
        print(f"No data for {region}.")
        return fire_log

    out_path = DATA_DIR / f"annual_data_{region}.csv"
    _write_csv(all_rows, fieldnames, out_path)
    print(f"\n{len(all_rows)} total rows → {out_path}")
    return fire_log


def main(region, only_fire=None):
    ee.Initialize(project=C.GEE_PROJECT)
    available = available_bpts_years()
    print(f"bpts years available: {sorted(available)}")

    regions = C.REGIONS if region == "ALL" else [region]
    run_log = {}
    for r in regions:
        print(f"\n=== Region: {r} ===")
        run_log[r] = process_region(r, available, only_fire=only_fire)

    log = {
        "run_at":           datetime.utcnow().isoformat() + "Z",
        "regions":          regions,
        "only_fire":        only_fire,
        "deployed_model":   C.DEPLOYED_MODEL,
        "bpts_collections": [C.BP_TS_METRICS_COL, C.BP_TS_METRICS_COL_CHACO],
        "available_years":  sorted(available),
        "fires":            run_log,
    }
    log_file = Path(__file__).with_suffix("") / "run.json"
    log_file.parent.mkdir(exist_ok=True)
    log_file.write_text(json.dumps(log, indent=2))
    print(f"\nRun log: {log_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sample annual bpts metrics at training points (seed/candidate study).")
    parser.add_argument("--region", choices=C.REGIONS + ["ALL"], default="PAT",
                        help="Region to sample, or ALL (default: PAT).")
    parser.add_argument("--fire", default=None,
                        help="Sample only this fire_id (test before a full run).")
    args = parser.parse_args()
    main(args.region, args.fire)
