"""
collection-01/scripts/profile_bpts.py

Profile where the per-tile time goes in step 03 (see docs/03-bpts.md §8).

You cannot profile an Export task (it runs async server-side and only reports a
single total EECU at the end).  Instead use GEE's built-in profiler,
``ee.profilePrinting()``, on a SYNCHRONOUS reduceRegion().getInfo() over a small
box — it prints an EECU·seconds-per-operation table for the whole graph, which is
the real server-side cost attribution.

Use a small box (a few km², native 30 m): the full 130-band × full-Landsat-series
graph over a whole tile exceeds the interactive user-memory limit (see §5), but a
small box exercises every operation (LR, cloud mask, mosaic, the array metrics)
and so gives a faithful *relative* breakdown.

Run from the repo root:

    $PYTHON collection-01/scripts/profile_bpts.py
"""

import importlib.util
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee


def _load_step03():
    """Load workflow/03-bp_ts_metrics.py by PATH.

    bpts_image lives in that file, but its name starts with a digit and has a hyphen —
    an invalid Python module identifier — so it cannot be `import`ed by name.
    importlib-by-path is the GEE require() analog: it runs the file's top-level defs but
    NOT its main() (guarded by `if __name__ == "__main__"`).
    """
    path = Path(__file__).resolve().parents[1] / "workflow" / "03-bp_ts_metrics.py"
    spec = importlib.util.spec_from_file_location("step03_bpts", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


S = _load_step03()

ee.Initialize(project="mapbiomas-fire-485203")

YEAR, TILE = 2015, "SK-19-Y-A"                     # Cholila (dense forest burn)
box = ee.Geometry.Point([-71.50, -42.55]).buffer(3000).bounds()   # ~6 km box

img = S.bpts_image(YEAR, TILE).select("delta3_peak")

print(f"=== TRUE EE PROFILER — full bpts graph over 6 km box @30 m "
      f"({TILE}, {YEAR}) ===")
print("Cost is dominated by the per-image LR + cloud-mask + plumbing over ~150 "
      "mosaicked\nscenes; the array/time-series metrics are < 1%.  See "
      "docs/03-bpts.md §8.\n")
with ee.profilePrinting():
    img.reduceRegion(ee.Reducer.mean(), box, 30, maxPixels=int(1e9)).getInfo()
