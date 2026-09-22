#!/usr/bin/env python3
"""
collection-01/validation/04_geodash_nbr.py

Ayuda visual para el intérprete en Collect Earth Online (CEO) / GeoDash — por cada uno de los
900 puntos de la muestra inicial (300/año-fuego × 3 fire-years), UNA imagen chica por punto
(círculo de 2 km de diámetro, radio 1 km, centrado en el píxel muestreado), todas juntas en una
sola `ImageCollection`:

    `sampling_ceo_dnbr` — una imagen por PUNTO (900 en total: 300 × 3 fire-years), con:

        dNBR                                        delta entre las dos composiciones (abajo)
        previo_BLUE/GREEN/RED/NIR/SWIR1/SWIR2/NBR    minNBR, año-fuego ANTERIOR (fy-1)
        focal_BLUE/GREEN/RED/NIR/SWIR1/SWIR2/NBR     minNBR, año-fuego focal (fy)

El gráfico de serie NBR pura (escena por escena) NO se exporta — decisión de Ramón (2026-09-08):
un layer en blanco (sin señal de quema) ya alcanza para descartar un punto rápido, y para los
casos dudosos el inspector GEE (`ceo_val_00_template`, repo `fuego`) ya tiene ese gráfico en vivo,
sin exportar nada. Se probó y se descartó exportarlo como asset — ver "POR QUÉ NO HAY SERIE NBR"
más abajo antes de retomar la idea.

POR QUÉ POR PUNTO Y NO UN ASSET POR AÑO — encontrado empíricamente, 2026-09-07
---------------------------------------------------------------------------------
La primera versión de este script hacía UN asset por fire-year, clipeado a los 300 círculos de
ese año. Un intento de export con `maxPixels` chico (1e8) falló con "Export too large: 7238627088
píxeles" — el `region=` que recibe `Export.image.toAsset` fija el RECTÁNGULO que lo contiene todo,
y como los 300 puntos están dispersos por todo el país, ese rectángulo es casi el país entero. Subir
`maxPixels` a 1e13 arrancó el export, pero quedó corriendo más de 1.5 h al 32% de progreso y ya
había consumido ~400 EECU-hora de `mapbiomas-argentina` — el compute project COMPARTIDO con toda
la red MapBiomas Fuego (ver CLAUDE.md, "shared compute project") — y se canceló ahí.

La causa de fondo: `qualityMosaic` (el método minNBR, ver abajo) tiene que evaluar TODO el dominio
combinado de las escenas Landsat que matchean el filtro espacial para decidir cuál es el mejor
píxel en cada lugar — y como esas ~2600+ escenas están repartidas en casi todos los path/row del
país (S3 sola cubre ~94% del área, docs/10 §4.6), ese dominio es prácticamente el país completo.
El `.clip()` al final no ayuda: pasa DESPUÉS de que `qualityMosaic` ya tuvo que mirar todo el
dominio.

La única forma de que el dominio de `qualityMosaic` sea chico es que la REGIÓN DE EXPORT en sí sea
chica — un círculo por vez, no 300 círculos dispersos nacionalmente en un solo export. De ahí el
cambio a una imagen por punto.

MÉTODO Y VENTANAS — copiados de `ceo_val_00_template` (repo `fuego`, NO reinventados)
--------------------------------------------------------------------------------------
El inspector GEE que ya usan los validadores (`collection-01/validation/ceo_val_00_template` en
`fuego`, leído de `origin/master` el 2026-09-07) ya resuelve exactamente este problema, en vivo,
sin exportar nada (ahí el dominio siempre es chico: un solo punto por corrida). Este script
reproduce su mismo método para que el dNBR de GeoDash coincida con el que ya ven en el Code
Editor:

- **Ventanas = año-fuego completo**, no un bracket corto: `focal` = 1 mayo fy → 1 mayo fy+1;
  `previo` = 1 mayo fy-1 → 1 mayo fy (el año-fuego ANTERIOR completo). Mismo `fire_year_window()`
  que ya usa `01_strata_export.py`, evaluado en `fy` y en `fy-1`.
- **minNBR, no mediana**: `qualityMosaic` sobre `-NBR` — se queda, píxel a píxel, con la
  observación de NBR MÁS BAJO de toda la ventana (la señal de quema más marcada). Así es como ya
  lo calcula `ceo_val_00_template::minNBR()`.
- `dNBR = previo_NBR - focal_NBR` (positivo = pérdida de vegetación / quemado) — mismo signo que
  `ceo_val_00_template::lsDelta`.
- El inspector también compone S2 SR y HLS además de Landsat (tres sensores); acá sólo Landsat,
  porque es la única fuente con cobertura completa desde 2003 (S2 arranca 2017, HLS 2013/2015).

Reutiliza `utils.functions.get_landsat` / `add_indices` (mismo cloud-mask QA_PIXEL + harmonización
ETM→OLI que ya usa el step 01 y que `funk.getLandsat` reproduce del lado JS) — no se reinventa la
fórmula de NBR (`normalizedDifference(['NIR','SWIR2'])`) ni el cloud-mask. Reutiliza también el
andamiaje de auth / chequeo de asset / chequeo de tarea en vuelo de `01_strata_export.py` (mismo
patrón que `03_ceo_export.py` ya usa para no duplicarlo).

Los puntos se leen del CSV local ya generado por `03_ceo_export.py`
(`outputs/ceo/upload/ceo_upload_fy<FY>.csv` — LON, LAT, PLOTID), no del asset de GEE
`ceo_points_fy<FY>`: ese asset tiene la geometría nativa VACÍA (`MultiPoint` con
`coordinates: []` — el upload por CSV a GEE no la arma sola a partir de columnas LON/LAT),
encontrado el 2026-09-07 al fallar un export con 0 escenas Landsat matcheadas. El inspector nunca
lo sufre porque ya reconstruye el punto a mano desde LON/LAT.

POR QUÉ NO HAY SERIE NBR EXPORTADA — probado y descartado, 2026-09-08
-------------------------------------------------------------------------
GeoDash's "Time Series Graph" widget exige un asset ImageCollection real con una banda ya
calculada por imagen (no hay campo de fórmula) Y una imagen POR FECHA real (no se puede empaquetar
una curva de ~80 fechas en una sola imagen multi-banda). Eso fuerza, como mínimo, una tarea de
export por escena Landsat agrupando todos los puntos que esa escena toca — se probó, y a
`scale=240` salía barato (~0.7 seg EECU/tarea, confirmado), pero para FY2003 solo (ventana ±6
meses, igual que el inspector) son ~10.600 escenas = ~10.600 tareas. Al lanzarlas se pegó contra
el **límite duro de GEE de 3000 tareas PENDING/RUNNING por compute project** — y ese límite es
del proyecto `mapbiomas-argentina` ENTERO, compartido con toda la red, no sólo nuestro. Se llegó a
ocupar las 3000 de una sola corrida, se canceló todo y se borró el asset parcial
(`sampling_ceo_nbr_ts`). No hay forma de tener la serie completa (una imagen por fecha real) sin
ese volumen de tareas — si se retoma, hay que trocear el envío en tandas bien por debajo de 3000 y
esperar a que la cola drene entre tandas.

USO
---
Autenticarse con la cuenta que tiene acceso a `mapbiomas-argentina` (ramonpagis@gmail.com):

    $PYTHON collection-01/validation/04_geodash_nbr.py --check  --year 2003
    $PYTHON collection-01/validation/04_geodash_nbr.py --launch --year 2003 --limit 10   # piloto
    $PYTHON collection-01/validation/04_geodash_nbr.py --launch --year 2003              # los 300
    $PYTHON collection-01/validation/04_geodash_nbr.py --acl
"""
from __future__ import annotations

import argparse
import sys
from importlib import import_module
from pathlib import Path

import ee
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import utils.constants as C  # noqa: E402
import utils.functions as F  # noqa: E402

_s1 = import_module("01_strata_export")
FIRE_YEARS = _s1.FIRE_YEARS
FY_MIN, FY_MAX = _s1.FY_MIN, _s1.FY_MAX
VAL_PROJECT = _s1.VAL_PROJECT
initialize = _s1.initialize
asset_exists = _s1.asset_exists
fire_year_window = _s1.fire_year_window

# ---------------------------------------------------------------------------
# constantes de este paso
# ---------------------------------------------------------------------------
DNBR_COL = "projects/mapbiomas-argentina/assets/FIRE/VALIDATION/sampling_ceo_dnbr"
POINTS_CSV_DIR = Path(__file__).resolve().parent / "outputs" / "ceo" / "upload"

CIRCLE_RADIUS_M = 1000       # 2 km de diámetro alrededor de cada píxel muestreado

OPT_BANDS = ["BLUE", "GREEN", "RED", "NIR", "SWIR1", "SWIR2"]
COMPOSITE_BANDS = OPT_BANDS + ["NBR"]


# ---------------------------------------------------------------------------
def load_points(fy):
    """Los 300 puntos (LON, LAT, PLOTID) del CSV local ya subido a CEO — ver "los puntos se leen
    del CSV local" en el docstring del módulo."""
    csv_path = POINTS_CSV_DIR / f"ceo_upload_fy{fy}.csv"
    if not csv_path.exists():
        sys.exit(f"[error] {csv_path} no existe — correr 03_ceo_export.py --export --year {fy}")
    return pd.read_csv(csv_path)


def point_circle(lon, lat):
    return ee.Geometry.Point([lon, lat]).buffer(CIRCLE_RADIUS_M, 1)


def dnbr_asset(fy, plotid):
    return f"{DNBR_COL}/sampling_ceo_dnbr_fy{fy}_p{plotid:03d}"


# ---------------------------------------------------------------------------
def _min_nbr_composite(circle, start, end, prefix):
    """`qualityMosaic` sobre `-NBR` en [start, end) — el píxel de NBR más bajo de la ventana,
    igual que `ceo_val_00_template::minNBR()`. Bandas prefijadas por `prefix`. `circle` es la
    región de UN solo punto — mantener el dominio chico es lo que hace esto barato (ver
    "POR QUÉ POR PUNTO" en el docstring del módulo)."""
    col = (F.get_landsat(circle, start, end)
           .map(F.add_indices)
           .map(lambda img: img.addBands(img.select("NBR").multiply(-1).rename("inv_NBR"))))
    img = col.qualityMosaic("inv_NBR").select(COMPOSITE_BANDS)
    return img.rename([f"{prefix}_{b}" for b in COMPOSITE_BANDS])


def dnbr_image(fy, lon, lat):
    focal_t0, focal_t1 = fire_year_window(fy)
    previo_t0, previo_t1 = fire_year_window(fy - 1)
    circle = point_circle(lon, lat)

    previo = _min_nbr_composite(circle, previo_t0, previo_t1, "previo")
    focal = _min_nbr_composite(circle, focal_t0, focal_t1, "focal")
    dnbr = previo.select("previo_NBR").subtract(focal.select("focal_NBR")).rename("dNBR")

    return (dnbr.addBands(focal).addBands(previo)
            .toFloat()
            .clip(circle)
            .set(
                "year", fy,                # año FUEGO — misma convención que sampling_strata
                "collection", 1,
                "source", "mapbiomas-fuego",
                "region", "argentina",
                "purpose", "CEO GeoDash - ayuda visual del validador, NO un producto de mapeo",
                "circle_radius_m", CIRCLE_RADIUS_M,
                "method", "minNBR (qualityMosaic sobre -NBR), año-fuego completo — "
                          "igual que ceo_val_00_template::minNBR()",
                "formula", "dNBR = previo_NBR - focal_NBR",
            ))


def check(fy):
    focal_t0, focal_t1 = fire_year_window(fy)
    previo_t0, previo_t1 = fire_year_window(fy - 1)
    df = load_points(fy)
    print(f"[check] año-fuego {fy}: {len(df)} puntos (de {POINTS_CSV_DIR / f'ceo_upload_fy{fy}.csv'})")
    print(f"        previo (fy-1) = minNBR [{previo_t0.format().getInfo()}, "
          f"{previo_t1.format().getInfo()})")
    print(f"        focal  (fy)   = minNBR [{focal_t0.format().getInfo()}, "
          f"{focal_t1.format().getInfo()})")
    print(f"        bandas por imagen: dNBR + previo_{{{','.join(COMPOSITE_BANDS)}}} "
          f"+ focal_{{{','.join(COMPOSITE_BANDS)}}}")
    print(f"        una imagen por punto (círculo de {CIRCLE_RADIUS_M} m radio) en {DNBR_COL}")


def ensure_container(asset_id, kind):
    """Crear un FOLDER / IMAGE_COLLECTION si no existe todavía (idempotente) — mismo patrón que
    `07-month_of_burn.py::ensure_container()`: el Export a un asset adentro de una colección falla
    si la colección contenedora no existe todavía."""
    if asset_exists(asset_id):
        return False
    ee.data.createAsset({"type": kind}, asset_id)
    print(f"[created] {kind:16s} {asset_id}")
    return True


def _existing_names(col):
    """Nombres de imagen ya exportadas en `col` — un solo `listAssets`, no un `getAsset` por
    punto (900 llamadas sería lento e innecesario)."""
    if not asset_exists(col):
        return set()
    return {a["name"].split("/")[-1] for a in
            ee.data.listAssets({"parent": col}).get("assets", [])}


def _inflight_names(prefix):
    """Descripciones PENDING/RUNNING que empiezan con `prefix` — un solo `listOperations`."""
    names = set()
    for op in ee.data.listOperations():
        meta = op.get("metadata", {})
        desc = meta.get("description", "")
        if desc.startswith(prefix) and meta.get("state") in ("PENDING", "RUNNING"):
            names.add(desc)
    return names


def launch(fy, limit=None, overwrite=False):
    ensure_container(DNBR_COL, "IMAGE_COLLECTION")
    df = load_points(fy)
    if limit:
        df = df.head(limit)

    done = set() if overwrite else _existing_names(DNBR_COL)
    inflight = set() if overwrite else _inflight_names(f"geodash_dnbr_fy{fy}_")

    n_launched, n_skip_done, n_skip_inflight = 0, 0, 0
    for row in df.itertuples():
        plotid = int(row.PLOTID)
        asset_id = dnbr_asset(fy, plotid)
        asset_name = asset_id.split("/")[-1]
        description = f"geodash_dnbr_fy{fy}_p{plotid:03d}"
        if asset_name in done:
            n_skip_done += 1
            continue
        if description in inflight:
            n_skip_inflight += 1
            continue
        circle = point_circle(row.LON, row.LAT)
        task = ee.batch.Export.image.toAsset(
            image=dnbr_image(fy, row.LON, row.LAT),
            description=description,
            assetId=asset_id,
            crs=C.SNIC_CRS,
            crsTransform=C.SNIC_TRANSFORM,
            region=circle,
            maxPixels=1e7,
        )
        task.start()
        n_launched += 1

    skip_msg = ", ".join(s for s in (
        f"{n_skip_done} ya exportados" if n_skip_done else "",
        f"{n_skip_inflight} en vuelo" if n_skip_inflight else "") if s)
    print(f"[launch] fy{fy}: {n_launched} tarea(s) lanzada(s)"
          f"{f' (salteados: {skip_msg})' if skip_msg else ''} → {DNBR_COL}")
    print("         seguir con `earthengine task list` o la pestaña Tasks")


# ---------------------------------------------------------------------------
# ACL — hacer público (docs/09 §"Public GEE assets": setAssetAcl(all_users_can_read))
# ---------------------------------------------------------------------------
def set_public(asset_id):
    ee.data.setAssetAcl(asset_id, {"all_users_can_read": True})


def acl():
    """Sólo la colección — GEE no permite `setAssetAcl` en una imagen cuyo padre es una
    colección ("Parent of the asset ... is a collection; operation not allowed", encontrado el
    2026-09-08 al intentar setearlo por-imagen): las hijas heredan el ACL del padre."""
    if not asset_exists(DNBR_COL):
        sys.exit(f"[error] {DNBR_COL} no existe todavía")
    set_public(DNBR_COL)
    n = len(ee.data.listAssets({"parent": DNBR_COL}).get("assets", []))
    print(f"[acl] {DNBR_COL} → público ({n} imagen(es) adentro, heredan el ACL del padre)")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, help="año-fuego (requerido salvo --acl)")
    ap.add_argument("--check", action="store_true", help="reportar, sin exportar")
    ap.add_argument("--launch", action="store_true", help="exportar (una tarea chica por punto)")
    ap.add_argument("--limit", type=int, help="lanzar sólo los primeros N puntos (piloto)")
    ap.add_argument("--acl", action="store_true",
                    help="hacer público el asset (colección + cada imagen adentro)")
    ap.add_argument("--overwrite", action="store_true",
                    help="relanzar aunque el punto ya tenga imagen exportada")
    ap.add_argument("--project", default=VAL_PROJECT, help="compute project (default %(default)s)")
    ap.add_argument("--credentials", help="archivo de credenciales alternativo")
    args = ap.parse_args()

    if not args.acl and args.year is None:
        ap.error("--year es requerido salvo con --acl")
    if args.year is not None and not (FY_MIN <= args.year <= FY_MAX):
        sys.exit(f"[error] {args.year} fuera del rango validable FY {FY_MIN}-{FY_MAX}")
    if args.year is not None and args.year not in FIRE_YEARS:
        print(f"[warn] {args.year} no es uno de los tres años elegidos {FIRE_YEARS} — "
              f"seguimos igual, confirmar que es intencional")

    initialize(args.project, args.credentials)

    if args.acl:
        acl()
    elif args.check:
        check(args.year)
    elif args.launch:
        launch(args.year, args.limit, args.overwrite)
    else:
        ap.error("elegir uno: --check, --launch o --acl")


if __name__ == "__main__":
    main()
