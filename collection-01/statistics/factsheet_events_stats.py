#!/usr/bin/env python
"""
collection-01/statistics/factsheet_events_stats.py — THE NUMBERS OF THE EVENT SLIDES (láminas 6-8)

The maps are drawn by `factsheet_events_maps.R`; this computes what the slide text quotes
about them (statistics/docs/factsheet-2026-spec.md "Láminas extra para diciembre 2026"):

    * the burned area, in the AOI and in the whole map frame;
    * the AOI's area, so "XX % del parque / de la pirorregión se quemó";
    * what the burned area was the year BEFORE, as col-3 nivel-1 classes.

THE GEOMETRY COMES FROM THE MAPS.  `factsheet_events_maps.R` writes
`data/statistics/events/<key>.geojson` — the AOI and the frame, plus the calendar year — and
this reads those files.  Run the R script first; there is no second definition of an AOI
here to drift out of sync.

THE FIRE IS THE PUBLISHED PRODUCT, NOT THE OBJECTS.  `annual_burned_v2`, band
`burned_area_<Y>`, the calendar-year map everyone downloads, so every number here is one a
reader can reproduce from the platform.  The map draws the fire OBJECTS (whole, filed into the
year of their median date), so the two can differ slightly at the edges of the year — a fire
that straddles 31 December is split by pixel here and drawn whole there.

THE LAND COVER IS THE PREVIOUS YEAR, `classification_<Y-1>` of `C.PRODUCT_LULC` — the same
convention as the whole factsheet (statistics/docs/statistics.md "The land-cover year: we cross
the PREVIOUS one"): a fire burns what was there before it, and the same-year class is partly
the fire's own scar.

PROGRAMMING STRATEGY — borrowed from `lulc_change_export.py`: one integer band
`burned * 100 + class(Y-1)`, one grouped `pixelArea` sum per geometry, on the land cover's own
lattice (`C.SNIC_CRS` + `C.SNIC_TRANSFORM`), so only the binary fire layer is resampled.  The
fire band is `unmask(0)`ed and the class band too, so every pixel of the geometry lands in a
row: the unburned rows give the AOI's total area and its composition for free.  The geometries
are small (one pirorregión at most), so it runs interactively, no export task.

OUTPUT
    data/statistics/events_stats.csv   event x region (aoi/frame) x burned (0/1) x class:
                                       the full cross-tab, area in ha
    factsheet_2026_figures_and_tables/figNN_datos.csv
                                       per map, the numbers its slide quotes: per region,
                                       the region's area, % burned, and the burned area by
                                       nivel-1 class.  Spanish, UTF-8 with BOM, like the
                                       other `_datos.csv` of the deliverable
    and, on the console, the same numbers.

USAGE (from the repo ROOT)
    $PYTHON collection-01/statistics/factsheet_events_stats.py              # all events
    $PYTHON collection-01/statistics/factsheet_events_stats.py pnqc_2025    # one
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "collection-01"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ee  # noqa: E402

import legends  # noqa: E402
from lulc_area_export import initialize  # noqa: E402
from utils import constants as C  # noqa: E402

OUT_DIR = REPO_ROOT / "collection-01" / "data" / "statistics"
EVT_DIR = OUT_DIR / "events"
OUT_CSV = OUT_DIR / "events_stats.csv"
DESIGN_DIR = OUT_DIR / "factsheet_2026_figures_and_tables"
REGION_LABEL = {"frame": "Área del mapa"}
REGIONS = ("aoi", "frame")


def load_event(key: str) -> tuple[int, dict[str, ee.Geometry], dict]:
    f = EVT_DIR / f"{key}.geojson"
    if not f.exists():
        raise SystemExit(f"{f} not found — run factsheet_events_maps.R {key} first")
    gj = json.loads(f.read_text(encoding="utf-8"))
    geoms, years = {}, set()
    for feat in gj["features"]:
        p = feat["properties"]
        years.add(int(p["cal_year"]))
        meta = {"fig": int(p["fig"]), "aoi_name": p.get("aoi_name") or ""}
        # geodesic=False: the frame is a lat-lon rectangle, and its edges are straight in
        # lat-lon, not great circles.
        geoms[p["role"]] = ee.Geometry(feat["geometry"], "EPSG:4326", False)
    assert len(years) == 1 and set(geoms) == set(REGIONS), f
    return years.pop(), geoms, meta


def code_image(year: int) -> ee.Image:
    """`burned * 100 + class(Y-1)`, every pixel unmasked."""
    fire = (ee.Image(f"{C.FINAL_PRODUCTS}/{C.product_name('annual_burned')}")
            .select(f"burned_area_{year}").unmask(0).gt(0))
    lulc = ee.Image(C.PRODUCT_LULC).select(f"classification_{year - 1}").unmask(0)
    return fire.multiply(100).add(lulc).toUint16().rename("code")


def grouped_area(year: int, geom: ee.Geometry) -> ee.Dictionary:
    return (
        ee.Image.pixelArea().divide(1e4)                       # m2 -> ha
        .addBands(code_image(year))
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="code"),
            geometry=geom,
            crs=C.SNIC_CRS,                                    # the land cover's lattice
            crsTransform=C.SNIC_TRANSFORM,
            maxPixels=1e12,
        )
    )


def event_rows(key: str) -> list[dict]:
    year, geoms, meta = load_event(key)
    # Both regions in one round trip.
    res = ee.Dictionary({r: grouped_area(year, geoms[r]).get("groups") for r in REGIONS}
                        ).getInfo()
    rows = []
    for region in REGIONS:
        for g in res[region]:
            code = int(g["code"])
            cls = code % 100
            rows.append({
                "event": key, "region": region, "cal_year": year, "lulc_year": year - 1,
                "burned": code // 100, "class_id": cls,
                "nivel1": legends.LULC_NIVEL_1.get(cls, f"? {cls}"),
                "nivel2": legends.LULC_NIVEL_2.get(cls, f"? {cls}"),
                "area_ha": float(g["sum"]),
            })
    return rows, meta


def summary(rows: list[dict], region: str) -> tuple[float, float, dict[str, float]]:
    """(region area, burned area, burned area by nivel 1) for one region."""
    rr = [r for r in rows if r["region"] == region]
    by1 = collections.defaultdict(float)
    for r in rr:
        if r["burned"]:
            by1[r["nivel1"]] += r["area_ha"]
    return (sum(r["area_ha"] for r in rr), sum(by1.values()),
            dict(sorted(by1.items(), key=lambda kv: -kv[1])))


def write_datos(rows: list[dict], meta: dict) -> None:
    """`figNN_datos.csv`: one row per region x nivel-1 class that burned.

    A box AOI (Cholila) IS the frame, so only the frame is written; a drawn AOI gets its
    own rows first, under its name.
    """
    regions = ([("aoi", meta["aoi_name"])] if meta["aoi_name"] else []) + \
              [("frame", REGION_LABEL["frame"])]
    f = DESIGN_DIR / f"fig{meta['fig']:02d}_datos.csv"
    with f.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["region", "area_region_ha", "quemado_ha", "pct_region_quemada",
                    "cobertura_anio_previo", "quemado_cobertura_ha", "pct_de_lo_quemado"])
        for region, label in regions:
            total, burned, by1 = summary(rows, region)
            for name, ha in by1.items():
                w.writerow([label, round(total), round(burned),
                            round(100 * burned / total, 2), name, round(ha),
                            round(100 * ha / burned, 1)])
    print(f"wrote {f.relative_to(REPO_ROOT)}")


def report(key: str, rows: list[dict]) -> None:
    year = rows[0]["cal_year"]
    print(f"\n=== {key}  (calendar {year}, land cover {year - 1}) ===")
    for region in REGIONS:
        total, burned, by1 = summary(rows, region)
        print(f"  {region:<5}  area {total:>13,.0f} ha   burned {burned:>11,.0f} ha   "
              f"({100 * burned / total:.2f} % of the {region})")
        for name, ha in by1.items():
            print(f"         {name:<42} {ha:>11,.0f} ha   {100 * ha / burned:5.1f} % of burned")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("events", nargs="*", help="event keys; default: every events/*.geojson "
                    "written by the maps script")
    ap.add_argument("--credentials", default=None)
    ap.add_argument("--project", default=C.GEE_PROJECT)
    args = ap.parse_args()

    keys = args.events or sorted(
        f.stem for f in EVT_DIR.glob("*.geojson")
        if "role" in f.read_text(encoding="utf-8")[:2000])
    initialize(args.project, args.credentials)

    # Keep the other events' rows when only some are recomputed.
    rows = []
    if OUT_CSV.exists():
        with OUT_CSV.open(encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r["event"] not in keys]
    for key in keys:
        new, meta = event_rows(key)
        report(key, new)
        write_datos(new, meta)
        rows.extend(new)

    cols = ["event", "region", "cal_year", "lulc_year", "burned", "class_id", "nivel1",
            "nivel2", "area_ha"]
    rows.sort(key=lambda r: (r["event"], r["region"], -int(r["burned"]), int(r["class_id"])))
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {OUT_CSV.relative_to(REPO_ROOT)}  ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
