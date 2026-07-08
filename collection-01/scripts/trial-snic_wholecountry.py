"""
collection-01/scripts/trial-snic_wholecountry.py

TRIAL (not the production step 04): run supervised SNIC over the WHOLE COUNTRY for
a single year and export the `candseed` result, to validate the whole-country
approach and pick `neighborhoodSize` by diffing internal tile seams
(docs/04-snic.md §7.3).

What it does — for `--year` (default 2015), NO previous-year padding (§4), so
`candseed ∈ {1,2}` only (focal candidate / seed; the `{3,4}` prev-year codes are a
production-padding concern, not this feasibility test):

  1. Rebuild the seed/candidate `candseed` surface with the SAME thresholds/logic as
     the fuego exploratory tool `collection-01/visualization-misc/explore_snic_IB-02`
     (hand-copied below — see SYNC note).
  2. Supervised SNIC (seeds grown through candidates), once per `neighborhoodSize`.
  3. Export ONLY `candseed` (1 band, int16) per §7.4 — `abs_date`/`veg_fire` are
     recreated later at Drive-export, not stored here.

Exports to the COLLECTION-1 `snic` ImageCollection as `trial_<year>_<nsize:03d>`
(e.g. `trial_2015_064`, `trial_2015_128`, `trial_2015_256`), on the bpts 30 m grid,
over Argentina buffered ~2 km (`C.ARG_BUFFER_FC`).

Run from the repo root:

    # build + sanity-check only (no tasks submitted):
    $PYTHON collection-01/scripts/trial-snic_wholecountry.py
    # actually submit the two export tasks:
    $PYTHON collection-01/scripts/trial-snic_wholecountry.py --launch

Submitting is a couple of task.start() round-trips (foreground-safe); the tasks
themselves run server-side for a while — monitor in the Code Editor Tasks panel.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C
from utils import functions as F

# ---------------------------------------------------------------------------
# CONFIG — hand-copied from fuego `explore_snic_IB-02` (2026-07-08).
# SYNC: if that script's thresholds change, update these to match. There is no
# automatic sync between the fuego JS repo and this repo.
# ---------------------------------------------------------------------------
NEIGHBORHOODS = [64, 128, 256]    # px; one export each. See §7.3 seam test.
CAND_FORCE_K2 = True              # candidate always delta2 + K2_cand (4-value form)
SEED_MAX_DROP = 5                 # drop seed components with <= this many px
SNIC_COMPACTNESS = 0
SNIC_CONNECTIVITY = 8

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

# Defaults for veg not in the table (non-burnable 24 / non-observed 25 / unmapped)
NBREAK_DEF, THR_DEF = 99999, 9

PROB_BANDS = ["delta3_peak", "minfore3_peak", "delta2_peak", "minfore2_peak",
              "pmax3", "pmax2", "pmax1"]

SNIC_COL = f"{C._FIRE_ROOT}/COLLECTION-1/WORKFLOW-EXPORTS/snic"


def decode_bpts(img):
    """7 probability bands ÷10000 (back to probability); day/DOY/n bands as-is."""
    prob = img.select(PROB_BANDS).divide(10000)
    rest = img.bandNames().removeAll(PROB_BANDS)
    return img.select(rest).addBands(prob)


def build_candseed(year):
    """The focal-year candseed {1,2} surface + the SNIC-ready seed/candidate images."""
    bpts = (ee.ImageCollection(C.BP_TS_METRICS_COL)
            .merge(ee.ImageCollection(C.BP_TS_METRICS_COL_CHACO))
            .filterMetadata("year", "equals", year))
    metrics = decode_bpts(bpts.mosaic())

    veg_fire = F.veg_fire_image(year)   # prev-year veg_fire class, remapped

    codes = [r[C_CODE] for r in VEG_TABLE]
    n_break = [r[C_NBREAK] for r in VEG_TABLE]

    def col(idx, glob):
        return [glob if r[idx] is None else r[idx] for r in VEG_TABLE]

    def veg_remap(vals, default):
        return veg_fire.remap(codes, vals, default)

    n_break_img = veg_remap(n_break, NBREAK_DEF)
    cand_k2 = veg_remap(col(C_K2C, G_K2_CAND), THR_DEF)
    cand_k3 = veg_remap(col(C_K3C, G_K3_CAND), THR_DEF)
    seed_k2 = veg_remap(col(C_K2S, G_K2_SEED), THR_DEF)
    seed_k3 = veg_remap(col(C_K3S, G_K3_SEED), THR_DEF)

    n_band = metrics.select("n")
    delta2 = metrics.select("delta2_peak")
    delta3 = metrics.select("delta3_peak")

    use_k3 = n_band.gte(n_break_img)                  # per-pixel K = 3 where dense
    delta_k = delta2.where(use_k3, delta3)
    seed_thr = seed_k2.where(use_k3, seed_k3)

    min_gap = metrics.select("jumpgap2").min(metrics.select("jumpgap3"))
    s_gap = ee.Image(S_GAP_SPARSE).where(n_band.gte(N_DENSE), S_GAP_DENSE)
    gap_ok = min_gap.lte(s_gap)

    seed_raw = delta_k.gte(seed_thr).And(gap_ok)
    seed_size = seed_raw.selfMask().connectedPixelCount(maxSize=100, eightConnected=True)
    seed = seed_size.gt(SEED_MAX_DROP).selfMask()      # >SEED_MAX_DROP connected seeds

    if CAND_FORCE_K2:
        cand_delta, cand_thr = delta2, cand_k2
    else:
        cand_delta, cand_thr = delta_k, cand_k2.where(use_k3, cand_k3)
    candidate = cand_delta.gte(cand_thr)

    return seed, candidate


def snic_candseed(seed, candidate, nsize):
    """Supervised SNIC → candseed {1,2} masked to the seed-grown burned region."""
    snic = ee.Algorithms.Image.Segmentation.SNIC(
        image=candidate.selfMask(),
        seeds=seed,
        compactness=SNIC_COMPACTNESS,
        connectivity=SNIC_CONNECTIVITY,
        neighborhoodSize=nsize,
    )
    burned = snic.select("clusters").mask()            # 1 where a seed-grown cluster
    # candseed: 1 = candidate part of a burned cluster, 2 = seed part.
    candseed = (ee.Image(1)
                .where(seed.mask(), 2)
                .updateMask(burned)
                .toInt16()
                .rename("candseed"))
    return candseed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, default=2015)
    ap.add_argument("--launch", action="store_true",
                    help="actually submit the export tasks (default: build + sanity check only)")
    args = ap.parse_args()

    ee.Initialize(project=C.GEE_PROJECT)

    region = ee.FeatureCollection(C.ARG_BUFFER_FC).geometry()
    proj = ee.Image(ee.ImageCollection(C.BP_TS_METRICS_COL)
                    .filterMetadata("year", "equals", args.year).first()).projection()
    crs = proj.crs().getInfo()
    transform = proj.getInfo()["transform"]

    seed, candidate = build_candseed(args.year)

    for nsize in NEIGHBORHOODS:
        asset_id = f"{SNIC_COL}/trial_{args.year}_{nsize:03d}"
        try:
            ee.data.getAsset(asset_id)
            print(f"[skip] {asset_id} already exists")
            continue
        except ee.EEException:
            pass

        candseed = snic_candseed(seed, candidate, nsize).set(
            "year", args.year, "neighborhoodSize", nsize, "trial", True)
        task = ee.batch.Export.image.toAsset(
            image=candseed,
            description=f"trial_{args.year}_{nsize:03d}",
            assetId=asset_id,
            region=region,
            crs=crs,
            crsTransform=transform,
            maxPixels=int(1e13),
            pyramidingPolicy={"candseed": "mode"},
        )
        if args.launch:
            task.start()
            print(f"[launched] {task.id}  ->  {asset_id}  (neighborhoodSize={nsize})")
        else:
            bands = candseed.bandNames().getInfo()
            print(f"[dry] would export {asset_id}  bands={bands}  neighborhoodSize={nsize}")

    if not args.launch:
        print("\nDry run only. Re-run with --launch to submit the tasks.")


if __name__ == "__main__":
    main()
