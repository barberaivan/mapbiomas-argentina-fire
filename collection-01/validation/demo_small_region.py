#!/usr/bin/env python3
"""
collection-01/validation/demo_small_region.py

DEMO / TUTORIAL — NO es parte del diseño congelado (`docs/10-validation.md`). No toca el asset de
producción (`FIRE/VALIDATION/sampling_strata`) ni las listas congeladas reales.

Dos pedidos de Iván en uno:
  1. Probar que el EXPORT en sí funciona (`Export.image.toAsset`, no sólo el `reduceRegion` de
     `--check`) sobre una región chica, mientras los 3 exports país-completo siguen corriendo.
  2. Reusar esa misma imagen para sacar unos puntos "económicos" (no 100/estrato, no 30k de
     reserva) en una zona tipo Sierras Grandes de Córdoba, listos para subir a CEO y mostrar el
     tutorial mañana.

Reusa `strata_image()` de `01_strata_export.py` SIN MODIFICARLA — lo que se prueba acá es el
código real de producción, acotado a un bbox chico, no una reimplementación en paralelo.

REGIÓN — aproximada, no una geometría oficial
------------------------------------------------
Bbox a ojo alrededor de Sierras Grandes / Pampa de Achala, Córdoba. Ajustar con `--bbox` si hace
falta más preciso.

ASSET DE SALIDA — carpeta separada de producción, no puede colisionar
--------------------------------------------------------------------------
`.../FIRE/VALIDATION/sampling_strata_demo/...` — `02_sample_pool.py` filtra la ImageCollection de
PRODUCCIÓN por `year`+`collection` (docs/10 §4.4), nunca por este path, así que un asset acá jamás
se cuela en el sorteo real aunque alguien corra `02` sin querer contra el año equivocado.

USO
---
    $PYTHON collection-01/validation/demo_small_region.py --check  --year 2022
    $PYTHON collection-01/validation/demo_small_region.py --launch --year 2022
    $PYTHON collection-01/validation/demo_small_region.py --draw   --year 2022
"""
from __future__ import annotations

import argparse
import json
import sys
from importlib import import_module
from pathlib import Path

import ee
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
_s1 = import_module("01_strata_export")
initialize = _s1.initialize
asset_exists = _s1.asset_exists
task_in_flight = _s1.task_in_flight
strata_image = _s1.strata_image           # SIN modificar — es lo que se prueba
VAL_PROJECT = _s1.VAL_PROJECT
STRATUM_LABELS = _s1.STRATUM_LABELS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils.constants as C  # noqa: E402

# ---------------------------------------------------------------------------
DEMO_COL = "projects/mapbiomas-argentina/assets/FIRE/VALIDATION/sampling_strata_demo"
DEMO_TAG = "sierras_cordoba"

# west, south, east, north — aproximado, ver docstring
DEFAULT_BBOX = [-65.3, -32.3, -64.6, -31.5]

DEFAULT_YEAR = 2022
N_PER_STRATUM = 15
STRATA = (1, 2, 3)
SEED = 43   # misma que CEO_SHUFFLE_SEED en 03_ceo_export.py — no hace falta que coincida, pero
            # tampoco hace daño reusarla para una demo

OUT_DIR = Path(__file__).resolve().parent / "outputs" / "demo"


def demo_asset(fy):
    return f"{DEMO_COL}/sampling_strata_demo_{DEMO_TAG}_fy{fy}"


def bbox_geom(bbox):
    return ee.Geometry.Rectangle(bbox, None, False)


# ---------------------------------------------------------------------------
def check(fy, bbox):
    geom = bbox_geom(bbox)
    hist = (strata_image(fy).select("stratum").reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=geom, crs=C.SNIC_CRS, crsTransform=C.SNIC_TRANSFORM,
        maxPixels=1e9).getInfo()["stratum"])
    print(f"[check] DEMO {DEMO_TAG} — año-fuego {fy}, bbox {bbox}")
    for k in ("1", "2", "3"):
        print(f"        {k} {STRATUM_LABELS[int(k)]:<20} {int(hist.get(k, 0)):>10,} px")
    print(f"        destino: {demo_asset(fy)}")


def launch(fy, bbox, overwrite=False):
    asset_id = demo_asset(fy)
    description = f"val10_demo_{DEMO_TAG}_fy{fy}"
    if asset_exists(asset_id) and not overwrite:
        print(f"[skip] {asset_id} ya existe (usar --overwrite para reemplazarlo)")
        return
    if task_in_flight(description):
        print(f"[skip] {description} tiene una tarea PENDING/RUNNING")
        return
    task = ee.batch.Export.image.toAsset(
        image=strata_image(fy),
        description=description,
        assetId=asset_id,
        crs=C.SNIC_CRS,
        crsTransform=C.SNIC_TRANSFORM,
        region=bbox_geom(bbox),
        maxPixels=1e13,
        pyramidingPolicy={".default": "mode"},
    )
    task.start()
    print(f"[launch] {description} → {asset_id}  (task {task.id})")
    print("         región chica — debería aterrizar en minutos, no en el día del país entero")


def draw(fy, bbox, overwrite=False):
    asset_id = demo_asset(fy)
    if not asset_exists(asset_id):
        sys.exit(f"[error] {asset_id} no existe todavía — correr --launch y esperar la tarea")

    out_upload = OUT_DIR / f"demo_ceo_upload_fy{fy}_{DEMO_TAG}.csv"
    if out_upload.exists() and not overwrite:
        print(f"[skip] {out_upload} ya existe (usar --overwrite para reemplazarlo)")
        return

    img = ee.Image(asset_id)
    ll = ee.Image.pixelLonLat()
    rows = []
    for h in STRATA:
        sel = img.select("stratum").eq(h).selfMask().rename("sel")
        pool = (sel
                .addBands(img.select("stratum"))
                .addBands(img.select("burned"))
                .addBands(ll))
        fc = pool.stratifiedSample(
            numPoints=N_PER_STRATUM,
            classBand="sel",
            region=bbox_geom(bbox),
            projection=ee.Projection(C.SNIC_CRS, C.SNIC_TRANSFORM),
            seed=SEED,
            geometries=False,
            tileScale=4,
        ).getInfo()["features"]
        n = len(fc)
        if n < N_PER_STRATUM:
            print(f"[warn] estrato {h}: sólo {n}/{N_PER_STRATUM} píxeles disponibles en el bbox")
        for f in fc:
            p = f["properties"]
            rows.append({
                "stratum": p["stratum"], "burned": p["burned"],
                "lon": p["longitude"], "lat": p["latitude"],
            })

    if not rows:
        sys.exit("[error] no se sorteó ningún punto — revisar el bbox / el asset demo")

    df = pd.DataFrame(rows)
    rng = np.random.default_rng(SEED)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    df["PLOTID"] = df.index + 1
    df = df.rename(columns={"lon": "LON", "lat": "LAT"})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df[["LON", "LAT", "PLOTID"]].to_csv(out_upload, index=False)

    out_crosswalk = OUT_DIR / f"demo_ceo_crosswalk_fy{fy}_{DEMO_TAG}.csv"
    df[["PLOTID", "LON", "LAT", "stratum", "burned"]].to_csv(out_crosswalk, index=False)

    print(f"[draw] {out_upload}  ({len(df)} filas, sólo LON/LAT/PLOTID — esto es lo que sube a CEO)")
    print(f"[draw] {out_crosswalk}  (local, NO subir a ningún lado)")
    print(f"        por estrato: {df['stratum'].value_counts().sort_index().to_dict()}")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=DEFAULT_YEAR, help=f"año-fuego (default {DEFAULT_YEAR})")
    ap.add_argument("--bbox", type=float, nargs=4, default=DEFAULT_BBOX,
                    metavar=("WEST", "SOUTH", "EAST", "NORTH"),
                    help=f"default {DEFAULT_BBOX} (Sierras Grandes de Córdoba, aproximado)")
    ap.add_argument("--check", action="store_true", help="conteos, sin exportar")
    ap.add_argument("--launch", action="store_true", help="exportar el asset demo (Export.image.toAsset real)")
    ap.add_argument("--draw", action="store_true", help="sortear puntos + armar CSV para CEO")
    ap.add_argument("--overwrite", action="store_true", help="reemplazar asset/CSV si ya existe")
    ap.add_argument("--project", default=VAL_PROJECT)
    ap.add_argument("--credentials")
    args = ap.parse_args()

    initialize(args.project, args.credentials)

    if args.check:
        check(args.year, args.bbox)
    elif args.launch:
        launch(args.year, args.bbox, args.overwrite)
    elif args.draw:
        draw(args.year, args.bbox, args.overwrite)
    else:
        ap.error("elegir uno: --check, --launch o --draw")


if __name__ == "__main__":
    main()
