"""
collection-01/scripts/read-03-tilemerge.py

Read state + EECU-h + wall-clock for the three merged-tile test exports
submitted by test-03-tilemerge.py.  No compute — just ee.data.listOperations().

    $PYTHON collection-01/scripts/read-03-tilemerge.py
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C


def _parse(ts):
    if not ts or ts.startswith("1970"):
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def main():
    ee.Initialize(project=C.GEE_PROJECT)
    rows = []
    for op in ee.data.listOperations():
        md = op.get("metadata", {})
        desc = md.get("description", "")
        if "tilemerge" not in desc:
            continue
        eecu_s = md.get("batchEecuUsageSeconds")
        start, end = _parse(md.get("startTime")), _parse(md.get("endTime"))
        wall = (end - start).total_seconds() / 60 if (start and end) else None
        rows.append((desc, md.get("state"), md.get("attempt", "-"),
                     eecu_s, wall))
    rows.sort()
    print(f"{'asset':24s} {'state':10s} {'att':3s} {'EECU-h':>8s} {'wall-min':>9s}")
    for desc, state, att, eecu_s, wall in rows:
        eh = f"{eecu_s/3600:.2f}" if eecu_s else "-"
        wm = f"{wall:.1f}" if wall else "-"
        print(f"{desc:24s} {state:10s} {str(att):3s} {eh:>8s} {wm:>9s}")


if __name__ == "__main__":
    main()
