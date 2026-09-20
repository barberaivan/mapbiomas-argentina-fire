"""
ATBD figure data — the four panels of `make_spatial_figure.R`, pulled from Collection 1.

Builds ONE six-band GeoTIFF (`raster_for_map_c01.tif`) over the Collection 0 pilot window
(Río Turbio and Cholila, Chubut) so the region-growing figure can be regenerated from
Collection 1 assets instead of the pilot's:

    RED, GREEN, BLUE   post-fire Landsat median, Dec 2015 – Feb 2016   -> panel (A)
    delta2_peak        the fire-year's change-in-burn-probability      -> panel (B)
    candseed           pre-SNIC seeds and candidates                   -> panel (C)
    snic               the seed-grown burned region                    -> panel (D)

**Fire-year 2014**, not 2015: both fires burned in February 2015, which falls inside
1 May 2014 – 30 Apr 2015 (docs/04-snic.md "The fire-year"). FY2015 holds only the
Patagonian dieback tail of the same scars.

Exactness. Panels B and C are built by IMPORTING `workflow/04-snic.py` and calling its own
`build_candseed_pre()`, so they are production code, not a re-implementation — and that
construction is strictly per-pixel, so clipping it to this window cannot change a value.
Panel D is read from the exported `snic_<fy>` asset rather than re-run here, because SNIC
growth depends on candidates outside the window: recomputing it on a clip would answer a
different question than the pipeline did.

The grid is the production SNIC lattice (`C.SNIC_TRANSFORM`), and the window is an INTEGER
offset into it — the same 2151 x 1142 cells as the Collection 0 `raster_for_map.tif`, so
the new panels register with the old figure cell for cell.

Everything is int16: reflectance and `delta2_peak` scaled by 10000, `candseed` and `snic`
as small codes. Six bands at this size is ~30 MB, over the synchronous download ceiling, so
each band is fetched on its own and the six are stitched with GDAL.

Run from this directory:  $PYTHON export_spatial_figure_raster.py
Writes: raster_for_map_c01.tif  (consumed in place by make_spatial_figure.R)
"""

import argparse
import importlib.util
import io
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
COLLECTION = REPO_ROOT / "collection-01"
sys.path.insert(0, str(COLLECTION))

import ee
from utils import constants as C
from utils import functions as F


# --- `workflow/04-snic.py` is production code we CALL, not code we copy ------------------
def _load_snic_module():
    """Import workflow/04-snic.py by path (the name is not a valid identifier)."""
    path = COLLECTION / "workflow" / "04-snic.py"
    spec = importlib.util.spec_from_file_location("snic_step04", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the window ---------------------------------------------------------------------------
# Integer cell offsets into C.SNIC_TRANSFORM. Verified: the Collection 0 pilot raster's
# origin sits exactly 5765 cells east and 75906 cells south of the lattice origin, so this
# window IS that raster's footprint, to the cell.
WIN_COL, WIN_ROW = 5765, 75906
WIN_WIDTH, WIN_HEIGHT = 2151, 1142

FIRE_YEAR = 2014

# Panel (A): the summer AFTER the fire, for reference only. Same window as Collection 0's
# `burn_prob_maps_export_image_4_ATBD`, so the two RGBs are the same scene.
RGB_START, RGB_END = "2015-12-15", "2016-02-28"

REFL_SCALE = 10000  # int16 encoding for reflectance and delta2_peak, as in bpts

OUT_NAME = "raster_for_map_c01.tif"


def window_grid():
    """(crs, crsTransform, ee.Geometry) of the export window on the SNIC lattice."""
    step = C.SNIC_TRANSFORM[0]
    x0 = C.SNIC_TRANSFORM[2] + WIN_COL * step
    y0 = C.SNIC_TRANSFORM[5] - WIN_ROW * step
    transform = [step, 0, x0, 0, -step, y0]
    region = ee.Geometry.Rectangle(
        [x0, y0 - WIN_HEIGHT * step, x0 + WIN_WIDTH * step, y0],
        proj=C.SNIC_CRS, geodesic=False,
    )
    return C.SNIC_CRS, transform, region


# --- the four layers ------------------------------------------------------------------------
def rgb_image(region):
    """Post-fire Landsat median, int16 x REFL_SCALE. Gaps (all-cloud) stay 0, as in col 0."""
    coll = F.get_landsat(region, RGB_START, RGB_END)
    med = coll.select(["RED", "GREEN", "BLUE"]).median().unmask(0)
    return med.multiply(REFL_SCALE).toInt16()


def delta2_window_max(snic_mod, fire_year):
    """
    `delta2_peak` as step 04 sees it for the fire-year: each calendar image's K=2 jump,
    masked to the detections whose mid-date falls inside 1 May Y1 - 1 May Y2, then combined
    per pixel by max. Clipped below at 0 and 0 where the fire-year holds no detection, so
    the panel shows only evidence this fire-year was allowed to use.

    This is the quantity the candidate cut of panel (C) is applied to.
    """
    y1, y2 = fire_year, fire_year + 1
    lo = snic_mod._day_num(y1, C.FY_START_MONTH, 1)
    hi = snic_mod._day_num(y2, C.FY_START_MONTH, 1)

    parts = []
    for cal_year in (y1, y2):
        metrics = snic_mod.year_metrics(cal_year)
        if metrics is None:
            continue
        # The K=2 mid-date, exactly as classify_image() derives it.
        mid_doy = (metrics.select("date_post2")
                   .subtract(metrics.select("jumpgap2").divide(2)))
        abs_mid = mid_doy.add(snic_mod._day_num(cal_year, 1, 1)).subtract(1)
        in_win = abs_mid.gte(lo).And(abs_mid.lt(hi))
        parts.append(metrics.select("delta2_peak").updateMask(in_win))

    if not parts:
        raise RuntimeError(f"no bpts image spans fire-year {fire_year}")

    delta = ee.ImageCollection(parts).max().unmask(0).max(0)
    return delta.multiply(REFL_SCALE).toInt16().rename("delta2_peak")


def candseed_image(snic_mod, fire_year):
    """
    Pre-SNIC candseed from production's own `build_candseed_pre`, with the Patagonian
    dieback code 3 folded into 1: padding enters SNIC as a candidate and survives as one,
    so the figure has two classes, seed and candidate, and no third legend entry.
    """
    pre, _, _, _ = snic_mod.build_candseed_pre(fire_year)
    if pre is None:
        raise RuntimeError(f"no bpts image spans fire-year {fire_year}")
    return pre.where(pre.eq(3), 1).unmask(0).toInt16().rename("candseed")


def snic_image(fire_year):
    """The exported product: 1 where a seed-grown cluster covers the pixel, else 0."""
    asset = ee.Image(f"{C.SNIC_COL}/snic_{fire_year}")
    return asset.select("candseed").mask().toInt16().rename("snic")


# --- download -------------------------------------------------------------------------------
def fetch_band(img, band, crs, transform, region, dest):
    """One single-band GeoTIFF via the synchronous endpoint, pinned to the window grid."""
    url = img.select([band]).getDownloadURL({
        "region": region,
        "crs": crs,
        "crs_transform": transform,
        "format": "GEO_TIFF",
    })
    with urllib.request.urlopen(url) as resp:
        payload = resp.read()
    # The endpoint answers GEO_TIFF directly, but falls back to a zip for some requests.
    if payload[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            name = next(n for n in zf.namelist() if n.endswith(".tif"))
            payload = zf.read(name)
    dest.write_bytes(payload)
    print(f"  {band:<12} {len(payload) / 1e6:6.1f} MB  -> {dest.name}")


def stitch(band_files, out_path):
    """Six single-band tifs -> one six-band tif, band descriptions preserved."""
    vrt = out_path.with_suffix(".vrt")
    subprocess.run(
        ["gdalbuildvrt", "-separate", "-q", str(vrt), *[str(p) for _, p in band_files]],
        check=True,
    )
    # gdalbuildvrt numbers the bands and drops the names; put them back in the VRT so
    # gdal_translate carries them into the GeoTIFF and terra reads them as layer names.
    text = vrt.read_text()
    for i, (band, _) in enumerate(band_files, start=1):
        marker = f'<VRTRasterBand dataType="Int16" band="{i}">'
        assert marker in text, f"unexpected VRT layout for band {i}"
        text = text.replace(marker, marker + f"\n    <Description>{band}</Description>", 1)
    vrt.write_text(text)

    subprocess.run(
        ["gdal_translate", "-q", "-co", "COMPRESS=LZW", str(vrt), str(out_path)],
        check=True,
    )
    vrt.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fire-year", type=int, default=FIRE_YEAR)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / OUT_NAME)
    args = parser.parse_args()

    ee.Initialize(project=C.GEE_PROJECT)
    snic_mod = _load_snic_module()

    crs, transform, region = window_grid()
    fy = args.fire_year

    stack = (rgb_image(region)
             .addBands(delta2_window_max(snic_mod, fy))
             .addBands(candseed_image(snic_mod, fy))
             .addBands(snic_image(fy)))

    bands = ["RED", "GREEN", "BLUE", "delta2_peak", "candseed", "snic"]
    tmp = args.out.parent / f".{args.out.stem}-parts"
    tmp.mkdir(exist_ok=True)

    print(f"fire-year {fy}, {WIN_WIDTH}x{WIN_HEIGHT} cells on the SNIC lattice")
    try:
        band_files = []
        for band in bands:
            dest = tmp / f"{band}.tif"
            fetch_band(stack, band, crs, transform, region, dest)
            band_files.append((band, dest))
        stitch(band_files, args.out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    info = subprocess.run(["gdalinfo", str(args.out)], capture_output=True, text=True).stdout
    size = next(line for line in info.splitlines() if line.startswith("Size is"))
    print(f"wrote {args.out.name} — {size}")
    if f"Size is {WIN_WIDTH}, {WIN_HEIGHT}" not in info:
        print(f"WARNING: expected Size is {WIN_WIDTH}, {WIN_HEIGHT} — the window shifted")


if __name__ == "__main__":
    main()
