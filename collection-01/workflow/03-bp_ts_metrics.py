"""
collection-01/workflow/03-bp_ts_metrics.py

Apply the fitted logistic-regression classifier (step 02) to every Landsat
observation over the country, producing an observation-level burn-probability
time series, then reduce it to annual summary metrics for the downstream
segmentation step.

For each focal year × MapBiomas carta tile this exports a 16-band image
``bpts_YYYY_<tile-id>`` to ``C.BP_TS_METRICS_COL``.  The heavy lifting lives in
``utils/functions.py`` (``bpts`` and its building blocks) so the same code can be
driven interactively from ``scripts/test-03-bp_ts.py``; this file is the CLI.

Run from the repo root:

    # one tile-year
    $PYTHON collection-01/workflow/03-bp_ts_metrics.py --year 2015 --tile SK-19-Y-A
    # all tiles for one year
    $PYTHON collection-01/workflow/03-bp_ts_metrics.py --year 2015
    # all years for one tile
    $PYTHON collection-01/workflow/03-bp_ts_metrics.py --tile SK-19-Y-A
    # everything (all years × all tiles — thousands of tasks)
    $PYTHON collection-01/workflow/03-bp_ts_metrics.py

Each invocation submits GEE export tasks and exits; monitor them in the Code
Editor Tasks panel or with scripts/status.py.
"""

import argparse
import sys
from pathlib import Path

# Add collection-01/ to sys.path so `utils` package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C
from utils import functions as F


def main(year=None, tile_id=None, project=None, overwrite=False, status=False):
    ee.Initialize(project=project or C.GEE_PROJECT)
    if status:
        F.bpts_status(year=year)
        return
    F.bpts(year=year, tile_id=tile_id, export=True, overwrite=overwrite)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export burn-probability time-series metrics (step 03)."
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Focal year to process (default: all years in C.YEARS).",
    )
    parser.add_argument(
        "--tile",
        default=None,
        help="Carta tile grid_name, e.g. SK-19-Y-A (default: all tiles in the ARG buffer).",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="GEE compute project to bill (default: C.GEE_PROJECT / $GEE_PROJECT).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-submit tile-years even if their asset exists (delete it first; GEE won't overwrite).",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print export progress (done/missing tiles) for --year instead of exporting.",
    )
    args = parser.parse_args()
    main(args.year, args.tile, args.project, args.overwrite, args.status)
