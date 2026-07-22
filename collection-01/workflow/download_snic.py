"""
collection-01/workflow/download_snic.py

Direct, tiled download of the step-04 SNIC products from GEE to local disk,
bypassing Drive + Insync (docs/04 §5, docs/05 §7b). For each fire-year it builds

    stack = snic_metrics_<y>.addBands( snic_<y>.select('candseed') )

(bands: abs_date, veg_fire, n, burned_around_{1,2,3}, candseed — burned_around is a burned-cell
COUNT, not a proportion; R divides by (2r+1)² for the proportion) and downloads it one
MapBiomas *carta* at a time via `geedim`, which internally sub-tiles each carta to the
Earth Engine computePixels request limit (≤32 MB / ≤10000 px / ≤1024 bands) and fetches
the tiles concurrently. This hits the synchronous compute-pixels endpoint — no batch
queue, no Drive, no Insync. Output, one GeoTIFF per carta:

    <out-dir>/<fire_year>/<carta_id>.tif     (int16, masked→NoData=0, terra-ready)

R (step 05) `terra::vrt()`s the per-carta tifs of a year into ONE whole-country mosaic
*before* labelling, so a scar that straddles two cartas is rejoined (objects stay global).
The per-carta files are also exactly the tiled product step 05 wants — read a tile, drop
NA, aggregate — so RAM never sees the whole ~3 B-cell country grid at once.

The carta set is the 248 cartas INTERSECTING the Argentina 2 km buffer (`C.ARG_BUFFER_FC`, the
same footprint bpts/SNIC use), not the full ~286-carta grid.

Why carta-by-carta rather than one whole-country geedim call (geedim tiles either way):
  * footprint — Argentina's bbox is ~half ocean/neighbours; per-carta requests stay on land.
  * resumable — a killed run resumes by skipping cartas whose .tif already exists.
  * parallel  — disjoint carta shards run under different GEE accounts at once:
                    ...download_snic.py --all-years --shard 0/2   # account A
                    ...download_snic.py --all-years --shard 1/2   # account B (swap credentials)
    So `geedim` = inner tiling (request limit), `carta` = outer partition (footprint /
    resume / cross-account) — different scales, both needed.

On COG / NoData (docs/05 §1, §7b): we do NOT need a COG here. The read-speed / OOM win
came from the NoData tag + sparse tiling, NOT the cloud-optimized overviews (which only
help partial/zoomed reads; step 05 does full-res full-coverage reads). `geedim` masks
background → the GeoTIFF NoData tag (we pin it to 0, never a valid value on burned pixels),
which terra honours automatically. Overviews would be dead weight.

Requires geedim (installed in the project venv):  $PYTHON -m pip install geedim

Run from the repo root:
    $PYTHON collection-01/workflow/download_snic.py --year 2000
    $PYTHON collection-01/workflow/download_snic.py --year 2000 --dry-run     # list, no geedim/download
    $PYTHON collection-01/workflow/download_snic.py --all-years
Under the comahue account (not on the default compute project), add e.g.
    --project mapbiomas-argentina
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C

# Repo-local default output. MUST stay OUTSIDE the Insync-synced store (the whole point
# is to stop round-tripping through Drive); this path is under the repo, not STORE_ROOT.
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "snic-direct"


def parse_shard(text):
    """'i/n' → (i, n) with 0 <= i < n; None for no sharding."""
    if text is None:
        return None
    i, n = (int(x) for x in text.split("/"))
    if not (0 <= i < n and n >= 1):
        raise argparse.ArgumentTypeError(f"--shard i/n needs 0 <= i < n (got {text})")
    return i, n


def carta_ids(shard):
    """Sorted carta ids INTERSECTING Argentina (the 2 km buffer, same footprint as bpts /
    the SNIC export → 248 cartas, not the full ~286-carta grid), optionally reduced to one
    round-robin shard."""
    arg = ee.FeatureCollection(C.ARG_BUFFER_FC).geometry()
    fc = ee.FeatureCollection(C.CARTAS_FC).filterBounds(arg)
    ids = sorted(set(fc.aggregate_array(C.CARTAS_ID_PROPERTY).getInfo()))
    if shard is not None:
        i, n = shard
        ids = [c for k, c in enumerate(ids) if k % n == i]
    return ids


def build_stack(fire_year, name_prefix, metrics_prefix):
    """snic_metrics_<y> + candseed(<y>) as one image, candseed last (never re-stored)."""
    metrics = ee.Image(f"{C.SNIC_METRICS_COL}/{metrics_prefix}{fire_year:04d}")
    candseed = ee.Image(f"{C.SNIC_COL}/{name_prefix}{fire_year:04d}").select("candseed")
    return metrics.addBands(candseed)


def download_carta(stack, carta_geom, out_path, crs, transform, overwrite, max_requests):
    """Fetch one carta of `stack` to a terra-ready int16 GeoTIFF via geedim.

    Clip to the carta polygon so each burned pixel lands in exactly one tile (no cross-carta
    double count); the carta bbox is the export region and `crs_transform` pins every tile to
    the shared bpts lattice so the per-carta tifs vrt cleanly. nodata=0 (safe: no band takes
    0 on a burned pixel — abs_date>0, veg 1-25, n>=1, burned_around >=1 (cell count), candseed 1-3)."""
    import geedim as gd
    img = stack.clip(carta_geom)
    gd.download.BaseImage(img).download(
        str(out_path),
        overwrite=overwrite,
        # nodata=True: tag the GeoTIFF NoData with the SAME value geedim fills masked int16
        # pixels with (its dtype nodata, -32768), so terra reads background as NA and stays
        # sparse. (A literal nodata=0 mismatched: tag 0 but fill -32768 → background read as data.)
        nodata=True,
        crs=crs,
        crs_transform=list(transform),
        region=carta_geom,
        dtype="int16",
        max_requests=max_requests,
    )


def download_year(year, ids, out_dir, crs, transform, name_prefix, metrics_prefix,
                  test, overwrite, dry_run, max_requests):
    metrics_id = f"{C.SNIC_METRICS_COL}/{metrics_prefix}{year:04d}"
    try:
        ee.data.getAsset(metrics_id)
    except ee.EEException:
        print(f"[skip] {metrics_id} not found — run `04-snic.py --to-asset` for FY{year} first")
        return
    stack = build_stack(year, name_prefix, metrics_prefix)
    fc = ee.FeatureCollection(C.CARTAS_FC)
    ydir = out_dir / (f"test_{year}" if test else f"{year}")   # R's load_snic matches this layout
    ydir.mkdir(parents=True, exist_ok=True)

    done = skipped = 0
    for cid in ids:
        out_path = ydir / f"{cid}.tif"
        if out_path.exists() and not overwrite:
            skipped += 1
            continue
        if dry_run:
            print(f"[dry] would download {out_path}")
            done += 1
            continue
        carta_geom = (fc.filter(ee.Filter.eq(C.CARTAS_ID_PROPERTY, cid))
                      .first().geometry())
        download_carta(stack, carta_geom, out_path, crs, transform, overwrite, max_requests)
        print(f"[done] {out_path}")
        done += 1
    verb = "would download" if dry_run else "downloaded"
    print(f"[FY{year}] {verb} {done} carta(s), skipped {skipped} existing")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--year", type=int, help="single fire-year (START year, e.g. 2000)")
    grp.add_argument("--all-years", action="store_true",
                     help=f"all fire-years {C.FIRST_FIRE_YEAR}..{C.LAST_FIRE_YEAR}")
    ap.add_argument("--test", action="store_true",
                    help="use the snic_test_/snic_metrics_test_ assets (tiny ROI)")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                    help="output root (default: %(default)s). Keep it OFF the Insync store.")
    ap.add_argument("--shard", type=parse_shard, default=None, metavar="i/n",
                    help="download only round-robin shard i of n cartas (fan across accounts)")
    ap.add_argument("--overwrite", action="store_true",
                    help="re-download cartas whose .tif already exists (default: skip)")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be downloaded (no geedim import, no fetch)")
    ap.add_argument("--max-requests", type=int, default=32,
                    help="max concurrent tile requests per carta (default: 32)")
    ap.add_argument("--project", default=C.GEE_PROJECT,
                    help="GEE compute project (default: %(default)s; e.g. 'mapbiomas-argentina' "
                         "under the comahue account)")
    args = ap.parse_args()

    ee.Initialize(project=args.project)

    name_prefix = "snic_test_" if args.test else "snic_"
    metrics_prefix = "snic_metrics_test_" if args.test else "snic_metrics_"
    # Pin output to the bpts 30 m grid (same lattice every step uses) so tiles vrt cleanly.
    proj = ee.Image(ee.ImageCollection(C.BP_TS_METRICS_COL).first()).projection()
    crs = proj.crs().getInfo()
    transform = proj.getInfo()["transform"]

    ids = carta_ids(args.shard)
    shard_note = f" (shard {args.shard[0]}/{args.shard[1]})" if args.shard else ""
    print(f"[cartas] {len(ids)} to process{shard_note}  ->  {args.out_dir}")

    years = (list(range(C.FIRST_FIRE_YEAR, C.LAST_FIRE_YEAR + 1))
             if args.all_years else [args.year])
    for y in years:
        download_year(y, ids, args.out_dir, crs, transform, name_prefix, metrics_prefix,
                      args.test, args.overwrite, args.dry_run, args.max_requests)


if __name__ == "__main__":
    main()
