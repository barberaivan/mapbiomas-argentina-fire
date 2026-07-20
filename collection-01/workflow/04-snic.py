"""
collection-01/workflow/04-snic.py

Step 04 — supervised SNIC burned-area segmentation on a **non-calendar fire-year**.

Design: docs/04-snic.md §2–§5 (whole-country May–April fire-year + `candseed`
construction). Summary of what this script does, per fire-year `Y1`
(FY = 1 May Y1 → 30 Apr Y2, Y2 = Y1+1; named by the START year Y1 — §2):

  1. Load the TWO calendar `bpts` images the fire-year spans (Y1 and Y2), decoded
     (§4.1). Either may be absent at the archive edges (FY1998 has only the 1999
     image; FY2025 has only the 2025 image) — whichever exists is used, and the
     two TRIMMED edge fire-years (jan99-apr99, may25-dec25) are still mapped, with
     `system:time_start`/`time_end` set to their actual coverage and `partial=true`.
  2. Per image, classify seed / candidate with the per-veg, per-pixel-K thresholds
     (hand-copied from fuego `explore_snic_IB-02`), and compute the K=2 mid-date
     (`date_post2 − jumpgap2/2`) as an ABSOLUTE day count (§4.1, cross-year safe).
  3. Window-filter each image to the fire-year (Y1 img → keeps May–Dec Y1; Y2 img →
     keeps Jan–Apr Y2) and combine per pixel: **seed > candidate > none** (`max`).
  4. Patagonia slow-dieback forward padding (§4.3): in `forest_pat`/`shrubland_pat`
     west of −70.3°, a pixel that is seed-or-candidate in the Y2 image with mid-date
     in [Jun, Nov] Y2 is added as a **candidate** (code `3`) where focal is 0.
  5. Supervised SNIC (seeds grown through the candidate footprint, seedless islands
     dropped) with `neighborhoodSize = 512`.
  6. Export ONLY `candseed ∈ {1,2,3}` (int16) to asset (§5): 1 = candidate,
     2 = seed, 3 = next-year (Patagonia dieback) candidate. `abs_date`/`veg_fire`
     are recreated later at Drive-export by re-running this construction (§5),
     NOT stored here.

Assets land in the COLLECTION-1 `snic` ImageCollection as `candseed_<fire_year>`
(e.g. `candseed_2024`), on the bpts 30 m grid, over Argentina buffered ~2 km
(`C.ARG_BUFFER_FC`), tagged `fire_year` / `system:time_start` (Y1-05-01) /
`system:time_end` ((Y1+1)-04-30).

Run from the repo root:

    # single fire-year, build + sanity-check only (no task submitted):
    $PYTHON collection-01/workflow/04-snic.py --fire-year 2015
    # actually submit it:
    $PYTHON collection-01/workflow/04-snic.py --fire-year 2015 --launch
    # the whole archive (1998..2025) — many whole-country tasks, use tmux:
    $PYTHON collection-01/workflow/04-snic.py --all --launch

Launching one fire-year is a single foreground-safe `task.start()`. A full `--all`
run submits ~28 whole-country export tasks; per CLAUDE.md launch it inside tmux. The
launcher is idempotent: it skips a fire-year whose asset already exists OR that has a
PENDING/RUNNING export task.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C
from utils import functions as F

# ---------------------------------------------------------------------------
# CONFIG — seed/candidate thresholds hand-copied from fuego `explore_snic_IB-02`
# (2026-07-08). SYNC: if that script's thresholds change, update these to match.
# There is no automatic sync between the fuego JS repo and this repo.
# ---------------------------------------------------------------------------
NEIGHBORHOOD_SIZE = 512           # px; SNIC internal-tile buffer (§6). 15.4 km @30 m.
CAND_FORCE_K2 = True              # candidate always delta2 + K2_cand (4-value form)
SEED_MAX_DROP = 5                 # drop seed components with <= this many connected px
SNIC_COMPACTNESS = 0
SNIC_CONNECTIVITY = 8

# Fire-year definition (§2) and the Patagonia dieback-padding rule (§4.3).
FY_START_MONTH = 5                # fire-year begins 1 May of Y1
PAD_MONTH_LO, PAD_MONTH_HI = 6, 11   # dieback padding window [Jun, Nov] of Y2 (inclusive)
PAT_LON_MAX = -70.3              # padding only west of this LONGITUDE meridian
PAT_VEG_CODES = [8, 21]         # forest_pat (8), shrubland_pat (21) — from veg_fire_remap.csv
FIRST_FIRE_YEAR, LAST_FIRE_YEAR = 1998, 2025   # start years (§2)

# San Ramón exception (fuego explore_snic_IB-02 Observaciones). The Jan-Apr 1999
# San Ramón fire (fire-year 1998, "jan99-apr99") is very sparse ("ralo"); loosen
# the candidate to ALSO accept high max-probability pixels — but ONLY inside this
# box and ONLY for fire-year 1998. A pmax-based candidate breaks other years/areas
# (valle de rio negro), and San Ramón maps largely as agriculture so it cannot be
# separated by veg cover. Matches the -02 note: candidate .or(pmax3 >= 0.3).
SAN_RAMON_FIRE_YEARS = [1998]
SAN_RAMON_PMAX_BAND = "pmax3"
SAN_RAMON_PMAX_MIN = 0.3
SAN_RAMON_RECT = ee.Geometry.Polygon(
    [[[-71.1795629588502, -40.836670267693194],
      [-71.1795629588502, -41.21017094506833],
      [-70.79641476549082, -41.21017094506833],
      [-70.79641476549082, -40.836670267693194]]], None, False)

# GLOBAL hand-set delta cuts (decoded probability scale 0..1)
G_K2_CAND, G_K2_SEED = 0.25, 0.90
G_K3_CAND, G_K3_SEED = 0.30, 0.75

# Per-veg: [code, n_break, k2_cand, k2_seed, k3_cand, k3_seed]; None = use global cut
VEG_TABLE = [
    [1,  14, 0.5, 0.98, 0.5, 0.98],   # agriculture_chaco
    [2,   2, 0.5, 0.98, 0.5, 0.98],   # agriculture_cuyo-pat
    [3,  16, 0.5, 0.98, 0.5, 0.98],   # agriculture_pampa
    [4,  48, None, None, None, None],  # agriculture-per_chaco-ba
    [5,  46, None, None, None, None],  # forest_ba
    [6,  34, None, None, None, None],  # forest_cuyo
    [7,  49, None, None, None, None],  # forest_pampa
    [8,   7, None, None, None, None],  # forest_pat
    [9,  35, None, None, None, None],  # forest-cerr_chaco
    [10, 32, None, None, None, None],  # forest-inund-chaco
    [11, 31, None, None, None, None],  # forest-open_chaco
    [12, 52, None, None, None, None],  # grassland_ba
    [13, 25, 0.5, 0.98, 0.5, 0.98],   # grassland_chaco
    [14, 32, None, None, None, None],  # grassland_cuyo
    [15, 48, None, None, None, None],  # grassland_pampa
    [16, 36, None, None, None, None],  # grassland_pat
    [17, 26, 0.5, 0.98, 0.5, 0.98],   # grassland-inund_chaco
    [18, 34, None, None, None, None],  # pasture_ba
    [19, 39, None, None, None, None],  # pasture_chaco
    [20, 35, None, None, None, None],  # shrubland_cuyo-pampa
    [21,  7, None, None, None, None],  # shrubland_pat
    [22, 21, None, None, None, None],  # shrubland-closed_chaco
    [23, 23, None, None, None, None],  # shrubland-open_chaco
]
C_CODE, C_NBREAK, C_K2C, C_K2S, C_K3C, C_K3S = 0, 1, 2, 3, 4, 5

# Seed temporal-gap ceiling (days): reject seeds where min(jumpgap2, jumpgap3) > S_GAP
S_GAP_DENSE, S_GAP_SPARSE, N_DENSE = 60, 90, 20

# Defaults for veg not in the table (non-burnable 24 / non-observed 25 / unmapped):
# NBREAK huge -> always K2; THR 9 -> no delta ever passes -> no fire on non-veg.
NBREAK_DEF, THR_DEF = 99999, 9

PROB_BANDS = ["delta3_peak", "minfore3_peak", "delta2_peak", "minfore2_peak",
              "pmax3", "pmax2", "pmax1"]

SNIC_COL = f"{C._FIRE_ROOT}/COLLECTION-1/WORKFLOW-EXPORTS/snic"
EPOCH = ee.Date("1970-01-01")


# ---------------------------------------------------------------------------
# bpts loading / decoding
# ---------------------------------------------------------------------------
def decode_bpts(img):
    """7 probability bands ÷10000 (back to probability); day/DOY/n bands as-is."""
    prob = img.select(PROB_BANDS).divide(10000)
    rest = img.bandNames().removeAll(PROB_BANDS)
    return img.select(rest).addBands(prob)


def year_metrics(year):
    """Decoded bpts mosaic for a CALENDAR year, or None if the archive has none."""
    coll = (ee.ImageCollection(C.BP_TS_METRICS_COL)
            .merge(ee.ImageCollection(C.BP_TS_METRICS_COL_CHACO))
            .filterMetadata("year", "equals", year))
    if coll.size().getInfo() == 0:
        return None
    return decode_bpts(coll.mosaic())


# ---------------------------------------------------------------------------
# per-veg threshold images (depend on veg_fire only; n is applied per calendar image)
# ---------------------------------------------------------------------------
def veg_threshold_images(veg_fire):
    """Turn VEG_TABLE into per-pixel threshold images keyed by the focal veg_fire class."""
    codes = [r[C_CODE] for r in VEG_TABLE]

    def col(idx, glob):
        return [glob if r[idx] is None else r[idx] for r in VEG_TABLE]

    def remap(vals, default):
        return veg_fire.remap(codes, vals, default)

    return {
        "n_break": remap([r[C_NBREAK] for r in VEG_TABLE], NBREAK_DEF),
        "cand_k2": remap(col(C_K2C, G_K2_CAND), THR_DEF),
        "cand_k3": remap(col(C_K3C, G_K3_CAND), THR_DEF),
        "seed_k2": remap(col(C_K2S, G_K2_SEED), THR_DEF),
        "seed_k3": remap(col(C_K3S, G_K3_SEED), THR_DEF),
    }


def _day_num(year, month, day):
    """Whole-day count from the 1970 epoch to YYYY-MM-DD (scalar ee.Number)."""
    return ee.Date.fromYMD(year, month, day).difference(EPOCH, "day")


def classify_image(metrics, thr, cal_year, san_ramon_boost=False):
    """
    For one decoded calendar-year bpts mosaic, return:
      seed_raw  — boolean, passes the per-pixel-K seed threshold + gap gate
      cand      — boolean, passes the K=2 candidate threshold
      abs_mid   — absolute mid-date (days since epoch), from the K=2 fit (§4.1)
    No windowing yet — the caller masks to the fire-year / padding windows.
    `san_ramon_boost` ORs the pmax-based easy candidate inside SAN_RAMON_RECT.
    """
    n = metrics.select("n")
    delta2 = metrics.select("delta2_peak")
    delta3 = metrics.select("delta3_peak")

    use_k3 = n.gte(thr["n_break"])                 # per-pixel K = 3 where dense enough
    delta_k = delta2.where(use_k3, delta3)
    seed_thr = thr["seed_k2"].where(use_k3, thr["seed_k3"])

    min_gap = metrics.select("jumpgap2").min(metrics.select("jumpgap3"))
    s_gap = ee.Image(S_GAP_SPARSE).where(n.gte(N_DENSE), S_GAP_DENSE)
    gap_ok = min_gap.lte(s_gap)

    seed_raw = delta_k.gte(seed_thr).And(gap_ok)
    cand = delta2.gte(thr["cand_k2"]) if CAND_FORCE_K2 \
        else delta_k.gte(thr["cand_k2"].where(use_k3, thr["cand_k3"]))

    # San Ramón exception: inside the box, also accept high-pmax pixels as candidates.
    if san_ramon_boost:
        in_box = ee.Image.constant(1).clip(SAN_RAMON_RECT).unmask(0)
        boost = metrics.select(SAN_RAMON_PMAX_BAND).gte(SAN_RAMON_PMAX_MIN).And(in_box)
        cand = cand.Or(boost)

    # K=2 mid-date as an absolute day count: Jan-1-of-cal_year + (mid_doy - 1).
    mid_doy = metrics.select("date_post2").subtract(metrics.select("jumpgap2").divide(2))
    abs_mid = mid_doy.add(_day_num(cal_year, 1, 1)).subtract(1)
    return seed_raw, cand, abs_mid


def _status_in_window(seed_raw, cand, abs_mid, lo_day, hi_day):
    """0 / 1(cand) / 2(seed), masked to abs_mid ∈ [lo_day, hi_day) — unmasked to 0 elsewhere."""
    in_win = abs_mid.gte(lo_day).And(abs_mid.lt(hi_day))
    status = (ee.Image(0)
              .where(cand.Or(seed_raw).And(in_win), 1)
              .where(seed_raw.And(in_win), 2))
    return status.unmask(0)


# ---------------------------------------------------------------------------
# fire-year candseed construction (§3–§4)
# ---------------------------------------------------------------------------
def build_candseed_pre(fire_year):
    """
    Pre-SNIC candseed {0,1,2,3} for the fire-year, plus a metadata dict with the
    ACTUAL data-coverage window (trimmed at the archive edges) and a `partial` flag.
    Returns (None, None) if no bpts image spans the fire-year.

    Coverage (§2): a full FY covers May Y1 → Apr Y2. The two TRIMMED edge
    fire-years, mapped so the products span the whole 1999–2025 calendar archive:
      - FY1998 has no 1998 image → only its Jan–Apr 1999 tail  ("jan99-apr99").
      - FY2025 has no 2026 image → only its May–Dec 2025 head   ("may25-dec25").
    """
    y1, y2 = fire_year, fire_year + 1
    m_y1 = year_metrics(y1)
    m_y2 = year_metrics(y2)
    if m_y1 is None and m_y2 is None:
        return None, None

    veg_fire = F.veg_fire_image(y1)                # MB(y1-1); governs whole FY (§2)
    thr = veg_threshold_images(veg_fire)
    boost = fire_year in SAN_RAMON_FIRE_YEARS      # San Ramón easy-candidate exception (§4.1)

    fy_lo = _day_num(y1, FY_START_MONTH, 1)        # 1 May Y1  (inclusive)
    fy_hi = _day_num(y2, FY_START_MONTH, 1)        # 1 May Y2  (exclusive)

    # ---- focal {1,2}: seed>cand>none, per-pixel max over the two calendar images ----
    focal = ee.Image(0)
    mid2 = c2 = s2 = None
    if m_y1 is not None:
        s1, c1, mid1 = classify_image(m_y1, thr, y1, san_ramon_boost=boost)
        focal = focal.max(_status_in_window(s1, c1, mid1, fy_lo, fy_hi))
    if m_y2 is not None:
        s2, c2, mid2 = classify_image(m_y2, thr, y2, san_ramon_boost=boost)
        focal = focal.max(_status_in_window(s2, c2, mid2, fy_lo, fy_hi))

    # ---- padding {3}: Patagonia forest/shrubland dieback, from the Y2 image only ----
    combined = focal
    if m_y2 is not None:
        pad_lo = _day_num(y2, PAD_MONTH_LO, 1)             # 1 Jun Y2
        pad_hi = _day_num(y2, PAD_MONTH_HI + 1, 1)         # 1 Dec Y2 (exclusive => thru 30 Nov)
        in_pad = mid2.gte(pad_lo).And(mid2.lt(pad_hi))
        pat_veg = veg_fire.eq(PAT_VEG_CODES[0])
        for code in PAT_VEG_CODES[1:]:
            pat_veg = pat_veg.Or(veg_fire.eq(code))
        west = ee.Image.pixelLonLat().select("longitude").lt(PAT_LON_MAX)
        pad = c2.Or(s2).And(in_pad).And(pat_veg).And(west).unmask(0)
        combined = combined.where(combined.eq(0).And(pad), 3)   # focal {1,2} always wins

    # Data-coverage window, trimmed to whichever calendar image(s) exist (§2).
    time_start = ee.Date.fromYMD(y1, 5, 1) if m_y1 is not None else ee.Date.fromYMD(y2, 1, 1)
    time_end = ee.Date.fromYMD(y2, 4, 30) if m_y2 is not None else ee.Date.fromYMD(y1, 12, 31)
    meta = {"time_start": time_start, "time_end": time_end,
            "partial": m_y1 is None or m_y2 is None}
    return combined.toInt16(), meta


def snic_candseed(candseed_pre):
    """Supervised SNIC → candseed {1,2,3} masked to the seed-grown burned region."""
    # Seeds = focal seeds surviving the connected-speck drop; specked-out seeds fall
    # back to candidate (1) but stay in the footprint so SNIC can still grow through them.
    seed_mask = candseed_pre.eq(2)
    seed_size = seed_mask.selfMask().connectedPixelCount(maxSize=100, eightConnected=True)
    seed_kept = seed_size.gt(SEED_MAX_DROP).unmask(0)

    candseed_pre = candseed_pre.where(candseed_pre.eq(2).And(seed_kept.Not()), 1)
    footprint = candseed_pre.gt(0)                 # 1,2,3 are all grow-into candidates
    seeds = candseed_pre.eq(2).And(seed_kept)

    snic = ee.Algorithms.Image.Segmentation.SNIC(
        image=footprint.selfMask(),
        seeds=seeds.selfMask(),
        compactness=SNIC_COMPACTNESS,
        connectivity=SNIC_CONNECTIVITY,
        neighborhoodSize=NEIGHBORHOOD_SIZE,
    )
    burned = snic.select("clusters").mask()        # 1 where a seed-grown cluster exists
    return candseed_pre.updateMask(burned).toInt16().rename("candseed")


# ---------------------------------------------------------------------------
# idempotency + launch
# ---------------------------------------------------------------------------
def asset_exists(asset_id):
    try:
        ee.data.getAsset(asset_id)
        return True
    except ee.EEException:
        return False


def task_in_flight(description):
    """True if a PENDING/RUNNING export task already targets this description."""
    for op in ee.data.listOperations():
        meta = op.get("metadata", {})
        if (meta.get("description") == description
                and meta.get("state") in ("PENDING", "RUNNING")):
            return True
    return False


def process_fire_year(fire_year, region, crs, transform, launch):
    y1 = fire_year
    asset_id = f"{SNIC_COL}/candseed_{y1:04d}"
    description = f"snic_candseed_{y1:04d}"

    if asset_exists(asset_id):
        print(f"[skip] {asset_id} already exists")
        return
    if task_in_flight(description):
        print(f"[skip] {description} has a PENDING/RUNNING task")
        return

    candseed_pre, meta = build_candseed_pre(fire_year)
    if candseed_pre is None:
        print(f"[skip] FY{y1}: no bpts image spans May {y1}-Apr {y1 + 1}")
        return

    candseed = snic_candseed(candseed_pre).set(
        "fire_year", y1,
        "partial", meta["partial"],
        "neighborhoodSize", NEIGHBORHOOD_SIZE,
        "system:time_start", meta["time_start"].millis(),
        "system:time_end", meta["time_end"].millis(),
    )
    if meta["partial"]:
        print(f"[note] FY{y1} is a TRIMMED edge fire-year (partial coverage)")
    task = ee.batch.Export.image.toAsset(
        image=candseed,
        description=description,
        assetId=asset_id,
        region=region,
        crs=crs,
        crsTransform=transform,
        maxPixels=int(1e13),
        pyramidingPolicy={"candseed": "mode"},
    )
    if launch:
        task.start()
        print(f"[launched] {task.id}  ->  {asset_id}")
    else:
        bands = candseed.bandNames().getInfo()
        print(f"[dry] would export {asset_id}  bands={bands}  neighborhoodSize={NEIGHBORHOOD_SIZE}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--fire-year", type=int, help="single fire-year (START year, e.g. 2024)")
    grp.add_argument("--all", action="store_true",
                     help=f"all fire-years {FIRST_FIRE_YEAR}..{LAST_FIRE_YEAR}")
    ap.add_argument("--launch", action="store_true",
                    help="actually submit export task(s) (default: build + sanity check only)")
    args = ap.parse_args()

    ee.Initialize(project=C.GEE_PROJECT)

    region = ee.FeatureCollection(C.ARG_BUFFER_FC).geometry()
    # Pin output to the bpts 30 m grid (use any available bpts image for the projection).
    proj = ee.Image(ee.ImageCollection(C.BP_TS_METRICS_COL).first()).projection()
    crs = proj.crs().getInfo()
    transform = proj.getInfo()["transform"]

    fire_years = (list(range(FIRST_FIRE_YEAR, LAST_FIRE_YEAR + 1))
                  if args.all else [args.fire_year])
    for fy in fire_years:
        process_fire_year(fy, region, crs, transform, args.launch)

    if not args.launch:
        print("\nDry run only. Re-run with --launch to submit the task(s).")


if __name__ == "__main__":
    main()
