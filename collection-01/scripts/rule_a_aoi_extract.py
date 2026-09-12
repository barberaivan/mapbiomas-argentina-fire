#!/usr/bin/env python3
"""Pull the hand-drawn rule-A AOI out of the GEE explorer into `config/rule_a_aoi.geojson`.

Rule A's modification confines it to a hand-drawn polygon over the agricultural
Pampa (docs/07 §1.1). That polygon is drawn in the Code Editor, where it lives as
an `aoiA` geometry IMPORT serialised into the head of
`collection-01/visualization-misc/explore_rules_kept_vs_gone` in the `fuego`
repo — which means it is versioned, but only there, and the local side (07b) and
any diagnostic cannot read a Code Editor drawing.

So this is the download: parse that import block and write the same ring out as
GeoJSON, EPSG:4326, so GEE and R filter against ONE geometry. Re-run it whenever
Iván redraws the polygon and pushes.

    $PYTHON collection-01/scripts/rule_a_aoi_extract.py            # writes config/
    $PYTHON collection-01/scripts/rule_a_aoi_extract.py --check    # just report

Run from the repo root.
"""
import argparse
import json
import re
import sys
from pathlib import Path

GEE_REPO = Path("/home/ivan/dev/MapBiomas/mapbiomas-arg-fire-gee")
SCRIPT = GEE_REPO / "collection-01/visualization-misc/explore_rules_kept_vs_gone"
OUT = Path("collection-01/config/rule_a_aoi.geojson")
VAR = "aoiA"


def extract(text, var=VAR):
    """The coordinate ring of `var`'s ee.Geometry.Polygon, as [[lon, lat], ...]."""
    m = re.search(rf"var\s+{var}\s*=.*?ee\.Geometry\.Polygon\(\s*(\[\[\[.*?\]\]\])\s*\)",
                  text, re.S)
    if not m:
        sys.exit(f"no `{var}` ee.Geometry.Polygon found — was it renamed, or not pushed?")
    # The Code Editor writes JSON-compatible numbers with /* */ comments stripped above.
    ring = json.loads(re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S))[0]
    if ring[0] != ring[-1]:
        ring = ring + [ring[0]]          # GeoJSON wants an explicitly closed ring
    return ring


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report, write nothing")
    ap.add_argument("--script", default=str(SCRIPT))
    a = ap.parse_args()

    ring = extract(Path(a.script).read_text())
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    print(f"[rule_a_aoi] {len(ring) - 1} vertices  "
          f"lon {min(lons):.3f}..{max(lons):.3f}  lat {min(lats):.3f}..{max(lats):.3f}")
    print(f"[rule_a_aoi] source: {a.script}")
    if a.check:
        sys.exit(0)
    # No `crs` member: it is deprecated in RFC 7946 (GeoJSON is always WGS84
    # lon/lat) and GDAL warns "proj_create: crs not found" on the URN form.
    gj = {"type": "FeatureCollection",
          "name": "rule_a_aoi",
          "features": [{"type": "Feature",
                        "properties": {"name": "rule_a_aoi",
                                       "source": "explore_rules_kept_vs_gone :: aoiA"},
                        "geometry": {"type": "Polygon", "coordinates": [ring]}}]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(gj, indent=1) + "\n")
    print(f"[rule_a_aoi] wrote {OUT}")
