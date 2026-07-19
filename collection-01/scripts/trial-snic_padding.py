"""
collection-01/scripts/trial-snic_padding.py

TRIAL (not yet the production step 04): whole-country supervised SNIC for a focal
year WITH the §4 backward gap-fill (prev-year padding) — and, for size comparison,
the same year WITHOUT padding. Exports the self-describing `candseed` band
(docs/04-snic.md §4/§7.4):

    1 = focal-year candidate    2 = focal-year seed
    3 = prev-year  candidate    4 = prev-year  seed      (padded run only)

Background is masked; the burned footprint carries the 4 (or 2) unmasked codes.
NO firebreak is applied here — per the 2026-07-19 revision (§5.1) the temporal
firebreak is deferred to terra (edge-conditional connected components), so this
export is just gap-fill + supervised SNIC.

Seed/candidate settings are hand-synced to the fuego exploratory tool
`collection-01/visualization-misc/explore_snic_IB-02` (2026-07-19), INCLUDING its
San-Ramon-1999 candidate exception (see that script's end comment): for focal year
1999 only, inside the san_ramon_rect box, a pixel is also a candidate if
pmax3 >= 0.3 (the sparse 1999 San Ramon scar; harmless elsewhere/other years).

Prev-year padding window: the gap-fill pulls in prev-year (`y-1`) candidate/seed
pixels burned from `--pad-from-month` (default 7 = July 1, inclusive) onward — the
late-`y-1` near-boundary material of a cross-year scar (§4.1).

Exports to the COLLECTION-1 `snic` ImageCollection as:
    trial_<year>_<nsize:03d>_pad      (with prev-year padding, codes {1,2,3,4})
    trial_<year>_<nsize:03d>_nopad    (focal only,             codes {1,2})

Run from the repo root:
    $PYTHON collection-01/scripts/trial-snic_padding.py            # dry run
    $PYTHON collection-01/scripts/trial-snic_padding.py --launch   # submit tasks
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C
from utils import functions as F

# ---------------------------------------------------------------------------
# CONFIG — hand-synced to fuego `explore_snic_IB-02` (2026-07-19).
# SYNC: if that script's thresholds change, update these to match. No automatic
# sync between the fuego JS repo and this repo.
# ---------------------------------------------------------------------------
NSIZE_DEFAULT = 512               # px; neighborhoodSize (matches the 2015 512 trial)
CAND_FORCE_K2 = True              # candidate always delta2 + K2_cand (4-value form)
SEED_MAX_DROP = 5                 # drop seed components with <= this many px
SNIC_COMPACTNESS = 0
SNIC_CONNECTIVITY = 8

# GLOBAL hand-set delta cuts (decoded probability scale 0..1)
G_K2_CAND, G_K2_SEED = 0.25, 0.90
G_K3_CAND, G_K3_SEED = 0.25, 0.75

# Per-veg: [code, n_break, k2_cand, k2_seed, k3_cand, k3_seed]; None = use global cut
VEG_TABLE = [
    [1,  100, 0.5, 0.98, 0.5, 0.98],   # agriculture_chaco
    [2,  100, 0.5, 0.98, 0.5, 0.98],   # agriculture_cuyo-pat
    [3,  100, 0.5, 0.98, 0.5, 0.98],   # agriculture_pampa
    [4,   48, None, None, None, None],  # agriculture-per_chaco-ba
    [5,   46, None, None, None, None],  # forest_ba
    [6,   34, None, None, None, None],  # forest_cuyo
    [7,   49, None, None, None, None],  # forest_pampa
    [8,    7, None, None, None, None],  # forest_pat
    [9,   35, None, None, None, None],  # forest-cerr_chaco
    [10,  32, None, None, None, None],  # forest-inund-chaco
    [11,  31, None, None, None, None],  # forest-open_chaco
    [12, 100, None, None, None, None],  # grassland_ba
    [13, 100, 0.5, 0.98, 0.5, 0.98],   # grassland_chaco
    [14,  30, None, None, None, None],  # grassland_cuyo
    [15, 100, None, None, None, None],  # grassland_pampa
    [16,  20, None, None, None, None],  # grassland_pat
    [17, 100, 0.5, 0.98, 0.5, 0.98],   # grassland-inund_chaco
    [18,  34, None, None, None, None],  # pasture_ba
    [19,  39, None, None, None, None],  # pasture_chaco
    [20,  35, None, None, None, None],  # shrubland_cuyo-pampa
    [21,  30, 0.2, None, None, None],   # shrubland_pat
    [22,  21, None, None, None, None],  # shrubland-closed_chaco
    [23,  23, None, None, None, None],  # shrubland-open_chaco
]
C_CODE, C_NBREAK, C_K2C, C_K2S, C_K3C, C_K3S = 0, 1, 2, 3, 4, 5

# Seed temporal-gap ceiling (days): reject seeds where min(jumpgap2, jumpgap3) > S_GAP
S_GAP_DENSE, S_GAP_SPARSE, N_DENSE = 60, 90, 20

# Defaults for veg not in the table (non-burnable 24 / non-observed 25 / unmapped)
NBREAK_DEF, THR_DEF = 99999, 9

PROB_BANDS = ["delta3_peak", "minfore3_peak", "delta2_peak", "minfore2_peak",
              "pmax3", "pmax2", "pmax1"]

SNIC_COL = f"{C._FIRE_ROOT}/COLLECTION-1/WORKFLOW-EXPORTS/snic"

# San-Ramon-1999 candidate exception box (verbatim from explore_snic_IB-02 imports).
# Coords only — the ee.Geometry is built lazily (after ee.Initialize).
SAN_RAMON_COORDS = [[[-71.1795629588502, -40.836670267693194],
                     [-71.1795629588502, -41.21017094506833],
                     [-70.79641476549082, -41.21017094506833],
                     [-70.79641476549082, -40.836670267693194]]]


def decode_bpts(img):
    """7 probability bands ÷10000 (back to probability); day/DOY/n bands as-is."""
    prob = img.select(PROB_BANDS).divide(10000)
    rest = img.bandNames().removeAll(PROB_BANDS)
    return img.select(rest).addBands(prob)


def _jan1_abs(y):
    """Days from 1970-01-01 to Jan 1 of year y (absolute-date epoch offset, §2.1)."""
    return ee.Date.fromYMD(y, 1, 1).difference(ee.Date("1970-01-01"), "day")


def build_year(year):
    """The candidate/seed masks + abs_date + n for ONE year (no gap-fill yet).

    Applies the San-Ramon-1999 candidate exception when year == 1999 (a property of
    building 1999, whether it is the focal year or the padded prev year)."""
    bpts = (ee.ImageCollection(C.BP_TS_METRICS_COL)
            .merge(ee.ImageCollection(C.BP_TS_METRICS_COL_CHACO))
            .filterMetadata("year", "equals", year))
    metrics = decode_bpts(bpts.mosaic())

    veg_fire = F.veg_fire_image(year)
    codes = [r[C_CODE] for r in VEG_TABLE]

    def col(idx, glob):
        return [glob if r[idx] is None else r[idx] for r in VEG_TABLE]

    def veg_remap(vals, default):
        return veg_fire.remap(codes, vals, default)

    n_break_img = veg_remap([r[C_NBREAK] for r in VEG_TABLE], NBREAK_DEF)
    cand_k2 = veg_remap(col(C_K2C, G_K2_CAND), THR_DEF)
    cand_k3 = veg_remap(col(C_K3C, G_K3_CAND), THR_DEF)
    seed_k2 = veg_remap(col(C_K2S, G_K2_SEED), THR_DEF)
    seed_k3 = veg_remap(col(C_K3S, G_K3_SEED), THR_DEF)

    n_band = metrics.select("n")
    delta2 = metrics.select("delta2_peak")
    delta3 = metrics.select("delta3_peak")
    pmax3 = metrics.select("pmax3")

    use_k3 = n_band.gte(n_break_img)                  # per-pixel K = 3 where dense
    delta_k = delta2.where(use_k3, delta3)
    seed_thr = seed_k2.where(use_k3, seed_k3)

    # Per-pixel absolute burn day (DOY of the K used + epoch offset; §2.1).
    date_k = metrics.select("date_post2").where(use_k3, metrics.select("date_post3"))
    abs_date = date_k.add(ee.Image.constant(_jan1_abs(year))).subtract(1).toInt().rename("abs_date")

    min_gap = metrics.select("jumpgap2").min(metrics.select("jumpgap3"))
    s_gap = ee.Image(S_GAP_SPARSE).where(n_band.gte(N_DENSE), S_GAP_DENSE)
    seed_raw = delta_k.gte(seed_thr).And(min_gap.lte(s_gap))
    seed_size = seed_raw.selfMask().connectedPixelCount(maxSize=100, eightConnected=True)
    seed = seed_size.gt(SEED_MAX_DROP).unmask(0)       # 0/1

    cand_delta = delta2 if CAND_FORCE_K2 else delta_k
    cand_thr = cand_k2 if CAND_FORCE_K2 else cand_k2.where(use_k3, cand_k3)
    candidate = cand_delta.gte(cand_thr).unmask(0)     # 0/1

    if year == 1999:                                   # San-Ramon-1999 exception
        san_ramon = ee.Geometry.Polygon(SAN_RAMON_COORDS, None, False)
        in_sr = ee.Image(1).clip(san_ramon).unmask(0)
        candidate = candidate.where(in_sr, candidate.Or(pmax3.gte(0.3)))

    return {"candidate": candidate, "seed": seed, "abs_date": abs_date, "n": n_band}


def build_candseed(year, pad, pad_from_month):
    """Assemble the gap-filled candseed {1,2(,3,4)} and run supervised SNIC.

    Returns the candseed image masked to the seed-grown burned footprint (§7.4)."""
    focal = build_year(year)
    focal_code = ee.Image(0).where(focal["candidate"], 1).where(focal["seed"], 2)

    if pad and (year - 1) >= min(C.YEARS):    # skip padding when prev year has no bpts
        prev = build_year(year - 1)
        # Only prev-year pixels burned from `pad_from_month`/1 (inclusive) onward.
        pad_from_abs = ee.Date.fromYMD(year - 1, pad_from_month, 1) \
            .difference(ee.Date("1970-01-01"), "day")
        late = prev["abs_date"].gte(ee.Image.constant(pad_from_abs))
        prev_code = (ee.Image(0).where(prev["candidate"], 3).where(prev["seed"], 4)
                     .updateMask(late).unmask(0))
        candseed = focal_code.where(focal_code.eq(0), prev_code)
    else:
        candseed = focal_code

    footprint = candseed.gt(0)
    seeds = candseed.eq(2).Or(candseed.eq(4))
    snic = ee.Algorithms.Image.Segmentation.SNIC(
        image=footprint.selfMask(),
        seeds=seeds.selfMask(),
        compactness=SNIC_COMPACTNESS,
        connectivity=SNIC_CONNECTIVITY,
        neighborhoodSize=NSIZE,
    )
    burned = snic.select("clusters").mask()            # 1 where a seed-grown cluster
    return candseed.updateMask(burned).toInt16().rename("candseed")


NSIZE = NSIZE_DEFAULT   # set in main()


def main():
    global NSIZE
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, default=2022)
    ap.add_argument("--nsize", type=int, default=NSIZE_DEFAULT, help="neighborhoodSize (px)")
    ap.add_argument("--pad-from-month", type=int, default=7,
                    help="prev-year gap-fill reaches back to this month/1, inclusive (default 7=July)")
    ap.add_argument("--launch", action="store_true",
                    help="actually submit the export tasks (default: build + sanity check only)")
    args = ap.parse_args()
    NSIZE = args.nsize

    ee.Initialize(project=C.GEE_PROJECT)

    region = ee.FeatureCollection(C.ARG_BUFFER_FC).geometry()
    proj = ee.Image(ee.ImageCollection(C.BP_TS_METRICS_COL)
                    .filterMetadata("year", "equals", args.year).first()).projection()
    crs = proj.crs().getInfo()
    transform = proj.getInfo()["transform"]

    variants = [
        ("pad", True), ("nopad", False),
    ]
    for tag, pad in variants:
        asset_id = f"{SNIC_COL}/trial_{args.year}_{args.nsize:03d}_{tag}"
        try:
            ee.data.getAsset(asset_id)
            print(f"[skip] {asset_id} already exists")
            continue
        except ee.EEException:
            pass

        candseed = build_candseed(args.year, pad, args.pad_from_month).set(
            "year", args.year, "neighborhoodSize", args.nsize,
            "padded", pad, "padFromMonth", args.pad_from_month if pad else 0, "trial", True)
        task = ee.batch.Export.image.toAsset(
            image=candseed,
            description=f"trial_{args.year}_{args.nsize:03d}_{tag}",
            assetId=asset_id,
            region=region,
            crs=crs,
            crsTransform=transform,
            maxPixels=int(1e13),
            pyramidingPolicy={"candseed": "mode"},
        )
        if args.launch:
            task.start()
            print(f"[launched] {task.id}  ->  {asset_id}  (pad={pad}, nsize={args.nsize})")
        else:
            print(f"[dry] would export {asset_id}  bands={candseed.bandNames().getInfo()}  pad={pad}")

    if not args.launch:
        print("\nDry run only. Re-run with --launch to submit the tasks.")


if __name__ == "__main__":
    main()
