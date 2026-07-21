"""
collection-01/workflow/04-snic.py

Step 04 — supervised SNIC burned-area segmentation on a **non-calendar fire-year**,
in two stages sharing one construction:

  * default stage  (asset) — build `candseed` and export it to a GEE asset.
  * `--to-drive`   (Drive) — read an already-exported `candseed` asset and write
                             the R-facing COG (`candseed` + `abs_date` + `veg_fire`).

All tunable settings live in `utils/constants.py` (Step 04 section); this file
holds only procedure.

Design: docs/04-snic.md §2–§5. Summary, per fire-year `Y1`
(FY = 1 May Y1 → 30 Apr Y2, Y2 = Y1+1; named by the START year Y1 — §2):

  1. Load the TWO calendar `bpts` images the fire-year spans (Y1 and Y2), decoded
     (§4.1). Either may be absent at the archive edges (FY1998 has only the 1999
     image; FY2025 has only the 2025 image) — whichever exists is used, and the
     two TRIMMED edge fire-years (jan99-apr99, may25-dec25) are still mapped, with
     `system:time_start`/`time_end` set to their actual coverage and `partial=true`.
  2. Per image, classify seed / candidate with the per-veg, per-pixel-K thresholds
     (C.VEG_TABLE), and compute the K=2 mid-date (`date_post2 − jumpgap2/2`) as an
     ABSOLUTE day count since epoch (§4.1, cross-year safe).
  3. Window-filter each image to the fire-year (Y1 img → keeps May–Dec Y1; Y2 img →
     keeps Jan–Apr Y2) and combine per pixel: **seed > candidate > none** (`max`).
     Each pixel's `abs_date` follows the image that won the max.
  4. Patagonia slow-dieback forward padding (§4.3): in `forest_pat`/`shrubland_pat`
     west of C.PAT_LON_MAX, a pixel that is seed-or-candidate in the Y2 image with
     mid-date in [Jun, Nov] Y2 is added as a **candidate** (code `3`) where focal is 0.
  5. Supervised SNIC (seeds grown through the candidate footprint, seedless islands
     dropped) with `neighborhoodSize = C.SNIC_NEIGHBORHOOD_SIZE`.
  6. Export ONLY `candseed ∈ {1,2,3}` (int16) to asset (§5): 1 = candidate,
     2 = seed, 3 = next-year (Patagonia dieback) candidate.

`abs_date` / `veg_fire` are NOT stored in the asset. They are recreated at
Drive-export (`--to-drive`) by re-running this construction (steps 1–4) and
masking to the exported `candseed` asset (§5). SNIC is NOT recomputed at that
stage — the asset already holds the segmented mask.

Assets land in the COLLECTION-1 `snic` ImageCollection (`C.SNIC_COL`) as
`snic_<fire_year>` (e.g. `snic_2024`; a `--test` run uses `snic_test_<fire_year>`
over a tiny ROI), on the bpts 30 m grid, over Argentina buffered ~2 km
(`C.ARG_BUFFER_FC`), tagged `fire_year` / `system:time_start` (Y1-05-01) /
`system:time_end` ((Y1+1)-04-30). The Drive COG lands in `C.SNIC_DRIVE_FOLDER`.

Run from the repo root:

    # tiny-ROI feasibility test first (submits `snic_test_1998`):
    $PYTHON collection-01/workflow/04-snic.py --fire-year 1998 --test --launch
    # single fire-year, build + sanity-check only (no task submitted):
    $PYTHON collection-01/workflow/04-snic.py --fire-year 2015
    # actually submit the asset:
    $PYTHON collection-01/workflow/04-snic.py --fire-year 2015 --launch
    # once the asset exists, export the R-facing COG to Drive:
    $PYTHON collection-01/workflow/04-snic.py --fire-year 2015 --to-drive --launch
    # the whole archive (1998..2025) — many whole-country tasks, use tmux:
    $PYTHON collection-01/workflow/04-snic.py --all --launch
    $PYTHON collection-01/workflow/04-snic.py --all --to-drive --launch

Launching one fire-year is a single foreground-safe `task.start()`. A full `--all`
run submits ~28 whole-country export tasks; per CLAUDE.md launch it inside tmux. Both
stages are idempotent: the asset stage skips a fire-year whose asset already exists OR
that has a PENDING/RUNNING task; the Drive stage skips one whose asset is missing (run
the asset stage first) OR that has a PENDING/RUNNING Drive task.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C
from utils import functions as F

# All tunable config (thresholds, SNIC params, fire-year calendar, ROIs, paths)
# lives in utils/constants.py, Step 04 section. This script is procedure only.


# ---------------------------------------------------------------------------
# bpts loading / decoding
# ---------------------------------------------------------------------------
def decode_bpts(img):
    """7 probability bands ÷10000 (back to probability); day/DOY/n bands as-is."""
    prob = img.select(C.SNIC_PROB_BANDS).divide(10000)
    rest = img.bandNames().removeAll(C.SNIC_PROB_BANDS)
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
    """Turn C.VEG_TABLE into per-pixel threshold images keyed by the focal veg_fire class."""
    codes = [r[C.VEG_COL_CODE] for r in C.VEG_TABLE]

    def col(idx, glob):
        return [glob if r[idx] is None else r[idx] for r in C.VEG_TABLE]

    def remap(vals, default):
        return veg_fire.remap(codes, vals, default)

    return {
        "n_break": remap([r[C.VEG_COL_NBREAK] for r in C.VEG_TABLE], C.NBREAK_DEF),
        "cand_k2": remap(col(C.VEG_COL_K2C, C.G_K2_CAND), C.THR_DEF),
        "cand_k3": remap(col(C.VEG_COL_K3C, C.G_K3_CAND), C.THR_DEF),
        "seed_k2": remap(col(C.VEG_COL_K2S, C.G_K2_SEED), C.THR_DEF),
        "seed_k3": remap(col(C.VEG_COL_K3S, C.G_K3_SEED), C.THR_DEF),
    }


def _day_num(year, month, day):
    """Whole-day count from the 1970 epoch to YYYY-MM-DD (scalar ee.Number)."""
    return ee.Date.fromYMD(year, month, day).difference(ee.Date("1970-01-01"), "day")


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
    s_gap = ee.Image(C.S_GAP_SPARSE).where(n.gte(C.N_DENSE), C.S_GAP_DENSE)
    gap_ok = min_gap.lte(s_gap)

    seed_raw = delta_k.gte(seed_thr).And(gap_ok)
    cand = delta2.gte(thr["cand_k2"]) if C.CAND_FORCE_K2 \
        else delta_k.gte(thr["cand_k2"].where(use_k3, thr["cand_k3"]))

    # San Ramón exception: inside the box, also accept high-pmax pixels as candidates.
    if san_ramon_boost:
        rect = ee.Geometry.Polygon(C.SAN_RAMON_RECT_COORDS, None, False)
        in_box = ee.Image.constant(1).clip(rect).unmask(0)
        boost = metrics.select(C.SAN_RAMON_PMAX_BAND).gte(C.SAN_RAMON_PMAX_MIN).And(in_box)
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
    Pre-SNIC construction for the fire-year. Returns
      (candseed_pre {0,1,2,3} int16, abs_date int16, meta)
    or (None, None, None) if no bpts image spans the fire-year.

    `abs_date` is the per-pixel K=2 mid-date (days since epoch) of the observation
    that SET the candseed value — the Y1 or Y2 image that won seed>cand>none. For a
    code-3 dieback pixel it is that pixel's OWN next-year dieback date; R later
    overrides code-3 with the parent object's date (§5). Masked where candseed == 0.

    `meta` carries the ACTUAL data-coverage window (trimmed at the archive edges,
    §2) and a `partial` flag. Full FY covers May Y1 → Apr Y2; the two TRIMMED edge
    fire-years, mapped so the products span the whole 1999–2025 calendar archive:
      - FY1998 has no 1998 image → only its Jan–Apr 1999 tail  ("jan99-apr99").
      - FY2025 has no 2026 image → only its May–Dec 2025 head   ("may25-dec25").
    """
    y1, y2 = fire_year, fire_year + 1
    m_y1 = year_metrics(y1)
    m_y2 = year_metrics(y2)
    if m_y1 is None and m_y2 is None:
        return None, None, None

    veg_fire = F.veg_fire_image(y1)                # MB(y1-1); governs whole FY (§2)
    thr = veg_threshold_images(veg_fire)
    boost = fire_year in C.SAN_RAMON_FIRE_YEARS    # San Ramón easy-candidate exception (§4.5)

    fy_lo = _day_num(y1, C.FY_START_MONTH, 1)      # 1 May Y1  (inclusive)
    fy_hi = _day_num(y2, C.FY_START_MONTH, 1)      # 1 May Y2  (exclusive)

    # ---- per-image in-window status {0,1,2} and absolute mid-date ----
    st1 = st2 = mid1 = mid2 = c2 = s2 = None
    if m_y1 is not None:
        s1, c1, mid1 = classify_image(m_y1, thr, y1, san_ramon_boost=boost)
        st1 = _status_in_window(s1, c1, mid1, fy_lo, fy_hi)
    if m_y2 is not None:
        s2, c2, mid2 = classify_image(m_y2, thr, y2, san_ramon_boost=boost)
        st2 = _status_in_window(s2, c2, mid2, fy_lo, fy_hi)

    # ---- focal {1,2}: seed>cand>none, per-pixel max over the two images ----
    # `date` follows whichever image won the max (Y2 wins only if strictly higher).
    if st1 is not None and st2 is not None:
        focal = st1.max(st2)
        date = mid1.where(st2.gt(st1), mid2)
    elif st1 is not None:
        focal, date = st1, mid1
    else:
        focal, date = st2, mid2

    # ---- padding {3}: Patagonia forest/shrubland dieback, from the Y2 image only ----
    combined = focal
    if m_y2 is not None:
        pad_lo = _day_num(y2, C.PAD_MONTH_LO, 1)           # 1 Jun Y2
        pad_hi = _day_num(y2, C.PAD_MONTH_HI + 1, 1)       # 1 Dec Y2 (exclusive => thru 30 Nov)
        in_pad = mid2.gte(pad_lo).And(mid2.lt(pad_hi))
        pat_veg = veg_fire.eq(C.PAT_VEG_CODES[0])
        for code in C.PAT_VEG_CODES[1:]:
            pat_veg = pat_veg.Or(veg_fire.eq(code))
        west = ee.Image.pixelLonLat().select("longitude").lt(C.PAT_LON_MAX)
        pad = c2.Or(s2).And(in_pad).And(pat_veg).And(west).unmask(0)
        newly3 = combined.eq(0).And(pad)                   # focal {1,2} always wins
        combined = combined.where(newly3, 3)
        date = date.where(newly3, mid2)                    # code-3 keeps its own dieback date

    abs_date = date.updateMask(combined.gt(0)).toInt16().rename("abs_date")

    # Data-coverage window, trimmed to whichever calendar image(s) exist (§2).
    time_start = ee.Date.fromYMD(y1, 5, 1) if m_y1 is not None else ee.Date.fromYMD(y2, 1, 1)
    time_end = ee.Date.fromYMD(y2, 4, 30) if m_y2 is not None else ee.Date.fromYMD(y1, 12, 31)
    meta = {"time_start": time_start, "time_end": time_end,
            "partial": m_y1 is None or m_y2 is None}
    return combined.toInt16(), abs_date, meta


def snic_candseed(candseed_pre):
    """Supervised SNIC → candseed {1,2,3} masked to the seed-grown burned region."""
    # Seeds = focal seeds surviving the connected-speck drop; specked-out seeds fall
    # back to candidate (1) but stay in the footprint so SNIC can still grow through them.
    seed_mask = candseed_pre.eq(2)
    seed_size = seed_mask.selfMask().connectedPixelCount(maxSize=100, eightConnected=True)
    seed_kept = seed_size.gt(C.SNIC_SEED_MAX_DROP).unmask(0)

    candseed_pre = candseed_pre.where(candseed_pre.eq(2).And(seed_kept.Not()), 1)
    footprint = candseed_pre.gt(0)                 # 1,2,3 are all grow-into candidates
    seeds = candseed_pre.eq(2).And(seed_kept)

    snic = ee.Algorithms.Image.Segmentation.SNIC(
        image=footprint.selfMask(),
        seeds=seeds.selfMask(),
        compactness=C.SNIC_COMPACTNESS,
        connectivity=C.SNIC_CONNECTIVITY,
        neighborhoodSize=C.SNIC_NEIGHBORHOOD_SIZE,
    )
    burned = snic.select("clusters").mask()        # 1 where a seed-grown cluster exists
    return candseed_pre.updateMask(burned).toInt16().rename("candseed")


# ---------------------------------------------------------------------------
# idempotency
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


# ---------------------------------------------------------------------------
# stage 1 — build candseed and export to asset
# ---------------------------------------------------------------------------
def process_fire_year(fire_year, region, crs, transform, launch, name_prefix):
    y1 = fire_year
    asset_id = f"{C.SNIC_COL}/{name_prefix}{y1:04d}"
    description = f"{name_prefix}{y1:04d}"

    if asset_exists(asset_id):
        print(f"[skip] {asset_id} already exists")
        return
    if task_in_flight(description):
        print(f"[skip] {description} has a PENDING/RUNNING task")
        return

    candseed_pre, _abs_date, meta = build_candseed_pre(fire_year)
    if candseed_pre is None:
        print(f"[skip] FY{y1}: no bpts image spans May {y1}-Apr {y1 + 1}")
        return

    candseed = snic_candseed(candseed_pre).set(
        "fire_year", y1,
        "partial", meta["partial"],
        "neighborhoodSize", C.SNIC_NEIGHBORHOOD_SIZE,
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
        print(f"[dry] would export {asset_id}  bands={bands}  "
              f"neighborhoodSize={C.SNIC_NEIGHBORHOOD_SIZE}")


# ---------------------------------------------------------------------------
# stage 2 — read the candseed asset, attach abs_date + veg_fire, export COG to Drive
# ---------------------------------------------------------------------------
def process_fire_year_drive(fire_year, region, crs, transform, launch, name_prefix):
    y1 = fire_year
    asset_id = f"{C.SNIC_COL}/{name_prefix}{y1:04d}"
    file_prefix = f"{name_prefix}{y1:04d}"
    description = f"{file_prefix}_drive"

    if not asset_exists(asset_id):
        print(f"[skip] {asset_id} not exported yet — run the asset stage first")
        return
    if task_in_flight(description):
        print(f"[skip] {description} has a PENDING/RUNNING task")
        return

    # candseed comes straight from the exported asset (SNIC is NOT recomputed);
    # abs_date + veg_fire are recreated from the §4 construction and masked to it.
    _pre, abs_date, _meta = build_candseed_pre(fire_year)
    candseed = ee.Image(asset_id).select("candseed")
    burned = candseed.mask()
    veg_fire = F.veg_fire_image(y1).updateMask(burned).toInt16().rename("veg_fire")
    abs_date = abs_date.updateMask(burned)
    stack = candseed.addBands(abs_date).addBands(veg_fire)

    task = ee.batch.Export.image.toDrive(
        image=stack,
        description=description,
        folder=C.SNIC_DRIVE_FOLDER,
        fileNamePrefix=file_prefix,
        region=region,
        crs=crs,
        crsTransform=transform,
        maxPixels=int(1e13),
        fileFormat="GeoTIFF",
        formatOptions={"cloudOptimized": True},
    )
    if launch:
        task.start()
        print(f"[launched] {task.id}  ->  Drive:{C.SNIC_DRIVE_FOLDER}/{file_prefix}")
    else:
        bands = stack.bandNames().getInfo()
        print(f"[dry] would export Drive:{C.SNIC_DRIVE_FOLDER}/{file_prefix}  bands={bands}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--fire-year", type=int, help="single fire-year (START year, e.g. 2024)")
    grp.add_argument("--all", action="store_true",
                     help=f"all fire-years {C.FIRST_FIRE_YEAR}..{C.LAST_FIRE_YEAR}")
    ap.add_argument("--launch", action="store_true",
                    help="actually submit export task(s) (default: build + sanity check only)")
    ap.add_argument("--test", action="store_true",
                    help="export over the tiny TEST_ROI as snic_test_<fy> (feasibility check)")
    ap.add_argument("--to-drive", action="store_true",
                    help="Drive stage: export candseed+abs_date+veg_fire COG from the existing asset")
    args = ap.parse_args()

    ee.Initialize(project=C.GEE_PROJECT)

    region = (ee.Geometry.Polygon(C.TEST_ROI_COORDS, None, False) if args.test
              else ee.FeatureCollection(C.ARG_BUFFER_FC).geometry())
    name_prefix = "snic_test_" if args.test else "snic_"
    # Pin output to the bpts 30 m grid (use any available bpts image for the projection).
    proj = ee.Image(ee.ImageCollection(C.BP_TS_METRICS_COL).first()).projection()
    crs = proj.crs().getInfo()
    transform = proj.getInfo()["transform"]

    fire_years = (list(range(C.FIRST_FIRE_YEAR, C.LAST_FIRE_YEAR + 1))
                  if args.all else [args.fire_year])
    run = process_fire_year_drive if args.to_drive else process_fire_year
    for fy in fire_years:
        run(fy, region, crs, transform, args.launch, name_prefix)

    if not args.launch:
        print("\nDry run only. Re-run with --launch to submit the task(s).")


if __name__ == "__main__":
    main()
