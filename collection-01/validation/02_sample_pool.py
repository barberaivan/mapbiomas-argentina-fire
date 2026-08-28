#!/usr/bin/env python3
"""
collection-01/validation/02_sample_pool.py

Paso 2 de la validación — LAS LISTAS ORDENADAS CONGELADAS, por estrato y por año-fuego.
Traducción directa a Python del Appendix B de `docs/10-validation.md` (§5), más una columna
que pidió Iván (ver más abajo). Se corre DESPUÉS de que el paso 01 esté aterrizado y congelado
— nunca antes: el diseño entero depende de sortear sobre el raster de estratos ya fijo.

DOS MODOS, DOS MOMENTOS
------------------------
    --launch   en GEE: sortea 6.000 píxeles por estrato por año (sobre-muestreo, §5 regla 2),
               ordenados por una clave aleatoria, exporta a Drive como CSV. UNA tarea por
               estrato por año — 9 tareas para 3 años — para que un faltante se vea en vez de
               redistribuirse solo (§5 regla 2). NUNCA se pide un `stratifiedSample` de las tres
               clases juntas: eso es lo que hacía el borrador v2 y es exactamente lo que el
               diseño prohíbe.
    --freeze   LOCAL, una vez el CSV ya bajó de Drive: verifica el conteo de filas, la
               consistencia `burned == (stratum==1)`, trunca a los primeros 5.000 por orden,
               deriva `col`/`row` desde `lon`/`lat` con la retícula pinneada, y archiva.
               Nunca se vuelve a correr sobre la misma lista — regenerarla, resortearla o
               descartar una fila ya sorteada invalida el diseño (§5 regla 6).

LA COLUMNA NUEVA — `mb_class_raw` Y `region_id` (pedido de Iván, no está en el Appendix B)
--------------------------------------------------------------------------------------------
Cada punto sorteado lleva también la clase CRUDA de MapBiomas Argentina del año calendario
PREVIO al año-fuego (no la reclasificación `veg_fire`) y la región numérica. Se arma con las
mismas piezas que ya usa `utils/functions.py::veg_fire_image()` (lectura, no se edita ese
archivo): `get_mb_class_band(C.MAPBIOMAS_LULC, mb_year=min(fy-1, C.MB_LIMIT_YEAR))` → banda
`mb_class_raw`, y `C.REGION_RASTER`/`C.REGION_RASTER_BAND` → `region_id`.

POR QUÉ LEE EL ASSET POR `year`+`collection`, NO POR EL PATH ARMADO
-----------------------------------------------------------------------
El Appendix B filtra la ImageCollection por las dos propiedades mandatorias
(`ee.Filter.eq('collection', 1)` + `ee.Filter.eq('year', FY)`) en vez de construir
`sampling_strata_fy<FY>` a mano — es a propósito (docs/10 §4.4): esas dos propiedades son
"cómo los pasos de abajo eligen una imagen". Acá se hace lo mismo, aunque también validamos con
`asset_exists()` antes de lanzar para no mandar una tarea sobre una imagen que todavía no existe.

DESVÍO DEL TEXTO LITERAL DEL APPENDIX B — sin `dropNulls`, sin geometrías de punto
--------------------------------------------------------------------------------------
Dos ajustes de la API Python, no del diseño:
1. `gee-gotchas.md` ya documenta que la API Python de `stratifiedSample` usa `projection=`
   (no `crs=`) y **no acepta `dropNulls`** — se omite acá.
2. En vez de `geometries: true` (que en el CSV vuelve como una columna `.geo` GeoJSON), se
   agregan bandas `longitude`/`latitude` explícitas antes de muestrear, así el CSV sale con
   columnas planas listas para la fórmula de `col`/`row` de §5 regla 4 sin parsear GeoJSON.

USO
---
    $PYTHON collection-01/validation/02_sample_pool.py --check  --year 2022
    $PYTHON collection-01/validation/02_sample_pool.py --launch --year 2022
    $PYTHON collection-01/validation/02_sample_pool.py --launch --all-years
    # ... esperar que las 9 tareas terminen y bajar los CSV de Drive a outputs/raw/ ...
    $PYTHON collection-01/validation/02_sample_pool.py --freeze --year 2022 --stratum 1
"""
from __future__ import annotations

import argparse
import json
import sys
from importlib import import_module
from pathlib import Path

import ee
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils.constants as C  # noqa: E402
import utils.functions as F  # noqa: E402  — SOLO lectura: get_mb_class_band()

sys.path.insert(0, str(Path(__file__).resolve().parent))
_s1 = import_module("01_strata_export")
initialize = _s1.initialize
asset_exists = _s1.asset_exists
task_in_flight = _s1.task_in_flight
strata_asset = _s1.strata_asset
STRATA_COL = _s1.STRATA_COL
FRAME_FC = _s1.FRAME_FC
FIRE_YEARS = _s1.FIRE_YEARS
VAL_PROJECT = _s1.VAL_PROJECT

# ---------------------------------------------------------------------------
N_DRAW = 6_000        # sobre-muestreo por estrato por año (§5 regla 2) — 20% de colchón sobre
                       # N_KEEP, misma lógica proporcional que el diseño original (40k/30k = 33%)
N_KEEP = 5_000         # tamaño final de la lista congelada — bajado de 30.000 (docs/10 §5),
                       # ver justificación en el doc mismo
SEED = 42              # fija y se registra para siempre (§5 regla 5) — la misma para todo el diseño
TILE_SCALE = 8
STRATA = (1, 2, 3)

DRIVE_FOLDER = "mapbiomas_fire_validation_10"   # no especificado en el Appendix B — elección propia

SELECTORS = ["stratum", "burned", "mb_class_raw", "region_id",
             "order_key", "longitude", "latitude"]

RAW_DIR = Path(__file__).resolve().parent / "outputs" / "raw"
FROZEN_DIR = Path(__file__).resolve().parent / "outputs" / "frozen"


# ---------------------------------------------------------------------------
# piezas server-side
# ---------------------------------------------------------------------------
def strata_by_year(fy):
    """La imagen de estratos para `fy`, elegida por (`year`,`collection`) — no por el path."""
    return ee.Image(ee.ImageCollection(STRATA_COL)
                    .filter(ee.Filter.eq("collection", 1))
                    .filter(ee.Filter.eq("year", fy))
                    .first())


def mb_class_raw_band(fy):
    """Clase cruda de MapBiomas, año calendario fy-1 (pedido de Iván) — banda `mb_class_raw`."""
    mb_year = min(fy - 1, C.MB_LIMIT_YEAR)
    return F.get_mb_class_band(ee.Image(C.MAPBIOMAS_LULC), mb_year)


def region_band():
    """Región numérica (pedido de Iván) — banda `region_id`."""
    return ee.Image(C.REGION_RASTER).select(C.REGION_RASTER_BAND).rename("region_id")


def attrs_image(fy):
    """Todo lo que va a viajar al CSV, salvo la ubicación: stratum/burned/mb_class_raw/
    region_id/order_key. Separada de `sel` a propósito — ver `draw()`."""
    strata_img = strata_by_year(fy)
    return (strata_img.select("stratum")
            .addBands(strata_img.select("burned"))
            .addBands(mb_class_raw_band(fy))
            .addBands(region_band())
            .addBands(ee.Image.random(SEED).rename("order_key")))


def draw(fy, h):
    """DOS llamadas GEE, no una — mismo sorteo, mucho más barato.

    El `stratifiedSample` original pedía las 8 bandas (`sel` + stratum/burned/mb_class_raw/
    region_id/order_key/lon/lat) en una sola pasada país-completo, y murió por OOM (Error code 8)
    en los tres estratos de fy2003 tras >1 día — S3 (~94% del país) es la máscara más grande y
    fue la que más EECU quemó (42.114 EECU-s, contra 311/26 de S1/S2): es volumen de datos
    arrastrado por `stratifiedSample`, no falta de turno en la cola.

    `stratifiedSample` elige QUÉ píxeles entran solo a partir de `classBand` + `seed` + `region` +
    `projection` — qué otras bandas viajen con él no cambia la selección. Separar en (1) sortear
    SOLO las `N_DRAW` ubicaciones sobre una imagen de una banda (`sel`), y (2) pegarles los
    atributos con `sampleRegions()` sobre esos puntos ya elegidos (no sobre el país entero) da el
    mismo resultado exacto — verificado fila por fila contra el método viejo, mismo seed, en S1 y
    S3, sobre el asset chico `sampling_strata_demo`."""
    strata_img = strata_by_year(fy)
    sel = strata_img.select("stratum").eq(h).selfMask().rename("sel")
    proj = ee.Projection(C.SNIC_CRS, C.SNIC_TRANSFORM)
    region = ee.FeatureCollection(FRAME_FC).geometry()

    locations = sel.stratifiedSample(
        numPoints=N_DRAW,
        classBand="sel",
        region=region,
        projection=proj,
        seed=SEED,
        geometries=True,
        tileScale=TILE_SCALE,
    )
    ll = ee.Image.pixelLonLat()
    sampled = (attrs_image(fy).addBands(ll)).sampleRegions(
        collection=locations,
        projection=proj,
        tileScale=TILE_SCALE,
        geometries=False,          # ya van longitude/latitude como bandas — ver docstring
    )
    return sampled.sort("order_key")


def task_name(fy, h):
    return f"val10_sample_fy{fy}_s{h}"


# ---------------------------------------------------------------------------
# comandos
# ---------------------------------------------------------------------------
def check(fy):
    strata_ok = asset_exists(strata_asset(fy))
    print(f"[check] año-fuego {fy}")
    print(f"        asset de estratos : {'✓' if strata_ok else '✗ FALTA — correr 01 --launch'}")
    if not strata_ok:
        return
    for h in STRATA:
        print(f"        estrato {h}: pedir {N_DRAW:,} → guardar {N_KEEP:,}  "
              f"tarea {task_name(fy, h)}")
    print(f"        destino: Drive/{DRIVE_FOLDER}")


def launch(fy, overwrite=False):
    if not asset_exists(strata_asset(fy)):
        print(f"[skip] {strata_asset(fy)} no existe — correr 01_strata_export.py --launch "
              f"para {fy} primero")
        return
    for h in STRATA:
        description = task_name(fy, h)
        if task_in_flight(description):
            print(f"[skip] {description} tiene tarea PENDING/RUNNING")
            continue
        task = ee.batch.Export.table.toDrive(
            collection=draw(fy, h),
            description=description,
            folder=DRIVE_FOLDER,
            fileNamePrefix=description,
            fileFormat="CSV",
            selectors=SELECTORS,
        )
        task.start()
        print(f"[launch] {description} → Drive/{DRIVE_FOLDER}  (task {task.id})")


# ---------------------------------------------------------------------------
# congelado local (§5)
# ---------------------------------------------------------------------------
def freeze(fy, h, csv_dir=RAW_DIR, out_dir=FROZEN_DIR):
    src = Path(csv_dir) / f"{task_name(fy, h)}.csv"
    if not src.exists():
        sys.exit(f"[error] no encontrado: {src}  "
                  f"(bajar el export de Drive primero, con ese nombre, a {csv_dir})")

    df = pd.read_csv(src)
    n = len(df)
    print(f"[freeze] {task_name(fy, h)}: {n:,} filas leídas (se pidieron {N_DRAW:,})")
    if n < N_KEEP:
        sys.exit(f"[error] sólo {n:,} filas — menos que las {N_KEEP:,} necesarias. "
                  f"`stratifiedSample` puede devolver menos de lo pedido sobre regiones "
                  f"grandes (§5 regla 2) — no truncar con esto, volver a lanzar el draw")

    # consistencia gratis (§4): burned tiene que ser exactamente (stratum == 1)
    bad = df.index[df["burned"] != (df["stratum"] == 1).astype(int)]
    if len(bad):
        sys.exit(f"[error] {len(bad)} filas violan burned == (stratum==1) — algo está mal "
                  f"con el asset de estratos o con este export, no seguir")

    # truncar a los primeros N_KEEP por orden (§5 regla 2) — el CSV ya viene sorteado por
    # order_key porque el draw hace .sort('order_key') del lado del servidor
    df = df.iloc[:N_KEEP].reset_index(drop=True).copy()
    df["rank"] = df.index

    # col/row desde el píxel-centro lon/lat (§5 regla 4). ⚠️ dy tiene que ser la MAGNITUD del
    # paso de fila: C.SNIC_TRANSFORM[4] es NEGATIVO (norte arriba), así que se usa abs(sy) —
    # con sy crudo el signo de `row` sale invertido.
    sx, _, x0, _, sy, y0 = C.SNIC_TRANSFORM
    dx, dy = sx, abs(sy)
    df["col"] = ((df["longitude"] - x0) / dx - 0.5).round().astype(int)
    df["row"] = ((y0 - df["latitude"]) / dy - 0.5).round().astype(int)

    df["fire_year"] = fy
    df = df.rename(columns={"longitude": "lon", "latitude": "lat"})
    df = df.drop(columns=["order_key"])   # ya cumplió su función — §5 regla 5: no se guarda
    df = df[["fire_year", "stratum", "burned", "mb_class_raw", "region_id",
             "rank", "lon", "lat", "col", "row"]]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = out_dir / f"{task_name(fy, h)}_frozen.csv"
    df.to_csv(out_csv, index=False)

    meta = {
        "fire_year": fy, "stratum": h, "seed": SEED,
        "strata_asset": strata_asset(fy), "n_drawn": n, "n_frozen": len(df),
        "source_csv": str(src),
    }
    out_meta = out_dir / f"{task_name(fy, h)}_frozen.meta.json"
    out_meta.write_text(json.dumps(meta, indent=2))

    print(f"[freeze] escrito: {out_csv}  ({len(df):,} filas)")
    print(f"[freeze] metadata: {out_meta}")
    print("[freeze] Nh todavía no está en esta metadata — completar a mano desde "
          f"01_strata_export.py --weights --year {fy} (outputs/strata_weights_fy{fy}.csv)")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--year", type=int, help="un año-fuego")
    g.add_argument("--all-years", action="store_true",
                   help=f"los tres años elegidos ({FIRE_YEARS})")
    ap.add_argument("--stratum", type=int, choices=STRATA,
                    help="sólo un estrato (default: los tres) — usado con --freeze")
    ap.add_argument("--check", action="store_true", help="reportar sin exportar")
    ap.add_argument("--launch", action="store_true", help="lanzar los draws en GEE")
    ap.add_argument("--freeze", action="store_true",
                    help="post-procesar localmente un CSV ya bajado de Drive")
    ap.add_argument("--csv-dir", default=str(RAW_DIR),
                    help=f"dónde están los CSV crudos bajados de Drive (default {RAW_DIR})")
    ap.add_argument("--out-dir", default=str(FROZEN_DIR),
                    help=f"dónde escribir las listas congeladas (default {FROZEN_DIR})")
    ap.add_argument("--project", default=VAL_PROJECT,
                    help="compute project (default %(default)s — ver 01_strata_export.VAL_PROJECT)")
    ap.add_argument("--credentials", help="archivo de credenciales alternativo")
    args = ap.parse_args()

    years = list(FIRE_YEARS) if args.all_years else [args.year]

    if args.freeze:
        strata = [args.stratum] if args.stratum else list(STRATA)
        for fy in years:
            for h in strata:
                freeze(fy, h, args.csv_dir, args.out_dir)
        return

    initialize(args.project, args.credentials)

    if args.check:
        for fy in years:
            check(fy)
        return
    if args.launch:
        for fy in years:
            launch(fy)
        return
    ap.error("elegir uno: --check, --launch o --freeze")


if __name__ == "__main__":
    main()
