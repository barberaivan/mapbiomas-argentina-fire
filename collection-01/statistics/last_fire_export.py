#!/usr/bin/env python
"""
collection-01/statistics/last_fire_export.py — EL MAPA DEL AÑO DEL ÚLTIMO FUEGO (docs/09 §5.6)

El segundo ráster que baja el factsheet, hermano de `burn_perc_export.py`: misma grilla,
mismo factor, mismo camino (tarea batch -> Drive/GCS -> `data/statistics/`) y la misma
compuerta al final.  Todo el andamiaje —OAuth, Drive, GCS, `transform()`, la máscara
denominador— se IMPORTA de ahí; acá vive sólo lo que es propio de esta imagen.

QUÉ COMPUTA
    `year_last_fire_v2`, banda `classification_2026` = el año del fuego más reciente de
    cada píxel sobre 1999–2025.

    ⚠️ LA BANDA ES `year_last_fire_<año+1>`: el off-by-one está en el código de referencia
    de la red y la plataforma lo espera (docs/07 §12.3.1).  `year_last_fire_2026` ES la
    serie 1999–2025 completa; `year_last_fire_2025` se detendría en 2024.  (El `band_format`
    que publica la red para este subproducto dice `classification_{year}`, pero el ASSET
    exportado lleva el nombre del subproducto — verificado 17 sep 2026 sobre el v2.)

    El producto está `selfMask`eado, así que **nunca-quemado está AUSENTE, no en 0** — que
    es justo lo que queremos: en el mapa, lo que nunca ardió va en BLANCO, no en el primer
    tono de la rampa (docs/10 §2.1).  Por eso acá, al revés que en `burn_perc_export.py`,
    NO hay `unmask(0)`: sumar ceros al promedio de una fecha no significa nada.

EL REDUCTOR ES `mean` (decidido con Iván, 17 sep 2026)
    `reduceResolution` ignora los píxeles enmascarados, así que el valor de la celda es el
    promedio del año de último fuego SOBRE LOS PÍXELES QUE ARDIERON, y una celda donde no
    ardió nada sale enmascarada.  Las otras dos opciones se descartaron:
      * `max` ("el año más reciente en que ardió algo en la celda") satura — en el Chaco
        casi toda celda de 480 m tiene algún píxel quemado en los últimos dos años, así que
        el mapa queda plano;
      * `mode` es inestable cuando la celda tiene pocos píxeles quemados repartidos.
    El precio del promedio es que el año sale FRACCIONARIO (2011,4).  Para el dibujo da
    igual: la figura va en clases, no en rampa continua.

LA GRILLA NO ES LA DEL MAPA DE FRECUENCIA, Y ESO ES DELIBERADO (medido 17 sep 2026)
    Los nueve subproductos v2 NO están todos en la misma grilla:

        frequency_burned_v2 / annual_burned_v2   EPSG:3857, 30 m, origen -8189460/-2483190
        year_last_fire_v2                        EPSG:4326, paso SNIC, origen
                                                 -73.56770985602505 / -21.73446880468659
        PRODUCT_LULC (col-3)                     EPSG:4326, paso SNIC, origen
                                                 -73.5666318776841 / -21.780821873347158

    Las dos últimas comparten retícula: el origen difiere en EXACTAMENTE 4 columnas y 172
    filas del mismo paso, así que un factor entero anida sin remuestrear.  La primera no.
    (Las dos, además, están a un offset entero de `C.SNIC_TRANSFORM`: +63/+110 la de fuego,
    +67/-62 la de cobertura — la misma retícula del paso 04, con otros recortes.)
    Por eso este ráster se agrega sobre la retícula de SU PROPIO asset (4326) y no sobre la
    de `burn_perc_export.py` (3857): pedir 3857 obligaría a remuestrear el año Y la máscara
    de "dónde hubo fuego", que es lo que define la huella que el mapa dibuja.

    La consecuencia es que los dos rásters del factsheet NO se pueden cruzar celda a celda.
    La compuerta de acá cruza NÚMEROS NACIONALES (la huella quemada), que no dependen de la
    retícula.  Para el dibujo da igual: R reproyecta los dos a Albers igual (docs/10 §2.1).

LAS DOS BANDAS, Y SUS ENCODINGS (distintos entre sí — leer antes de decodificar)
    1. `last_fire`  = (año_medio − 1998) × 100, uint16.  Rango 100 (1999) … 2700 (2025).
       El offset existe porque 2025 × 100 = 202500 NO entra en uint16; restar la base sí.
    2. `burned_pct` = % de los píxeles QUEMABLES de la celda que ardieron alguna vez,
       × 100, uint16.  Mismo encoding que las dos bandas de `burn_perc_export.py`.
       Sale del MISMO asset que la banda 1 (`year_last_fire` está `selfMask`eado, así que
       "tiene año" ES "ardió alguna vez") y no de `frequency_burned`, que vive en otra
       retícula: así las dos bandas cuentan exactamente los mismos píxeles y la compuerta 2
       es una identidad, no una aproximación.
    Ambas con `nodata` EXPLÍCITO (65535): en uint16 el relleno por defecto de lo enmascarado
    es 0, que acá sería "1998" y "nunca ardió", dos mentiras distintas.

    La banda 2 no es decorado: es el denominador visual.  Una celda donde ardió el 0,4 % de
    la superficie lleva un año igual que una que ardió entera, y pintadas iguales el mapa
    exagera la huella.  Con la banda 2, R decide (`MIN_BURNED_FRAC` en `factsheet_style.R`).

USO (desde la RAÍZ del repo), en el orden en que se corre
    --export     lanza UNA tarea batch -> Drive C.STATS_DRIVE_FOLDER (GeoTIFF).
    --status     estado de esa tarea.
    --fetch      la baja a data/statistics/ y corre la compuerta.
    --check      re-corre la compuerta sobre el archivo ya bajado (sin red).
Opciones: --factor 16 (480 m, por defecto) | --denom burnable|land | --to-gcs.
`--credentials ~/.config/earthengine/credentials.comahue --project mapbiomas-argentina`
corre como la segunda cuenta (la cola de tareas es por usuario).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "collection-01"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ee  # noqa: E402

from utils import constants as C  # noqa: E402
from burn_perc_export import (  # noqa: E402
    GCS_BUCKET, GCS_PREFIX, NODATA, OUT_DIR, SCALE_FACTOR,
    denominator, download_from_drive, download_from_gcs, ecoregions, initialize,
)

TASK_PREFIX = "arg_last_fire"        # namespaced: el proyecto de cómputo es COMPARTIDO

# La banda: `year_last_fire_<último año + 1>`.  Escrita acá y no derivada del asset, por la
# misma razón que la grilla en `burn_perc_export.py`: si río arriba cambia, queremos que
# falle ruidosamente y no que baje un ráster silenciosamente distinto.
YLF_BAND = "year_last_fire_2026"
FIRST_YEAR, LAST_YEAR = 1999, 2025
N_YEARS_SERIES = LAST_YEAR - FIRST_YEAR + 1   # 27, para la compuerta 3
YEAR_BASE = 1998                     # el offset del encoding de la banda 1 (ver cabecera)

# La retícula del asset `year_last_fire_v2`, verificada 17 sep 2026 (ver la cabecera).  El
# paso es el de `C.SNIC_TRANSFORM`; el origen difiere en un número ENTERO de pasos, así que
# es la misma retícula con otro recorte.  Se reusa el paso de constants y se escribe el
# origen acá: si el asset se re-exporta corrido, la compuerta 2 lo delata.
CRS = C.SNIC_CRS
PIXEL = C.SNIC_TRANSFORM[0]
ORIGIN_X, ORIGIN_Y = -73.56770985602505, -21.73446880468659


def transform(factor: int) -> list:
    """La grilla pineada, `factor` píxeles nativos por celda.  NO es `transform()` de
    `burn_perc_export`: otra proyección, otro origen — por eso se redefine en vez de
    importarse, que es el error que dejaría los dos rásters medio corridos."""
    s = PIXEL * factor
    return [s, 0, ORIGIN_X, 0, -s, ORIGIN_Y]


def name_of(args) -> str:
    return f"{TASK_PREFIX}_{round(30 * args.factor)}m_mean"


# ---------------------------------------------------------------------------
# la imagen
# ---------------------------------------------------------------------------
def last_fire(args) -> ee.Image:
    """Banda 1: el año medio del último fuego sobre los píxeles que ardieron."""
    ylf = (ee.Image(f"{C.FINAL_PRODUCTS}/{C.product_name('year_last_fire')}")
           .select(YLF_BAND)
           .updateMask(denominator(args.denom))     # sin `unmask`: ver la cabecera
           .rename("last_fire"))
    if args.factor == 1:
        return ylf
    return (ylf
            .reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)
            .reproject(crs=CRS, crsTransform=transform(args.factor)))


def burned_pct(args) -> ee.Image:
    """Banda 2: % de los píxeles quemables de la celda que ardieron alguna vez.

    Del MISMO asset que la banda 1 y no de `frequency_burned` (ver la cabecera): el producto
    está `selfMask`eado, así que "tiene año" es exactamente "ardió alguna vez", y las dos
    bandas quedan definidas sobre el mismo conjunto de píxeles y la misma retícula.
    """
    ever = (ee.Image(f"{C.FINAL_PRODUCTS}/{C.product_name('year_last_fire')}")
            .select(YLF_BAND)
            .unmask(0)                              # acá SÍ: el denominador es la celda
            .gte(FIRST_YEAR)
            .updateMask(denominator(args.denom))
            .multiply(100)
            .rename("burned_pct"))
    if args.factor == 1:
        return ever
    return (ever
            .reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)
            .reproject(crs=CRS, crsTransform=transform(args.factor)))


def export_image(args) -> ee.Image:
    """Las dos bandas, uint16, con DOS encodings distintos (cabecera) y nodata explícito."""
    b1 = (last_fire(args).subtract(YEAR_BASE).multiply(SCALE_FACTOR)
          .round().toUint16().unmask(NODATA))
    b2 = burned_pct(args).multiply(SCALE_FACTOR).round().toUint16().unmask(NODATA)
    return b1.addBands(b2).toUint16()


# ---------------------------------------------------------------------------
# export / status / fetch
# ---------------------------------------------------------------------------
def export(args) -> int:
    desc = name_of(args)
    common = dict(
        image=export_image(args),
        description=desc,
        region=ecoregions().geometry().bounds(),
        crs=CRS,
        crsTransform=transform(args.factor),   # la grilla, pineada (nunca `scale=`)
        maxPixels=int(1e13),
        fileFormat="GeoTIFF",
        formatOptions={"cloudOptimized": True, "noData": NODATA},
    )
    if args.to_gcs:
        dest = f"gs://{GCS_BUCKET}/{GCS_PREFIX}/{desc}.tif"
        task = ee.batch.Export.image.toCloudStorage(
            bucket=GCS_BUCKET, fileNamePrefix=f"{GCS_PREFIX}/{desc}", **common)
    else:
        dest = f"Drive:{C.STATS_DRIVE_FOLDER}/{desc}.tif"
        task = ee.batch.Export.image.toDrive(
            folder=C.STATS_DRIVE_FOLDER, fileNamePrefix=desc, **common)
    if args.dry_run:
        print(f"[dry] would export {dest}")
        return 0
    task.start()
    print(f"[launched] {task.id}  ->  {dest}")
    return 0


def status(args) -> int:
    found = 0
    for op in ee.data.listOperations():
        md = op.get("metadata", {})
        if TASK_PREFIX in md.get("description", ""):
            found += 1
            print(f"{md.get('description')}  {md.get('state')}  "
                  f"{md.get('startTime', '')}  {md.get('updateTime', '')}")
    if not found:
        print(f"no operations matching {TASK_PREFIX}* in this compute project")
    return 0


def fetch(args) -> int:
    desc = name_of(args)
    if args.to_gcs:
        download_from_gcs(args, desc)
    else:
        download_from_drive(args, desc)
    return check(args)


# ---------------------------------------------------------------------------
# la compuerta
# ---------------------------------------------------------------------------
def check(args) -> int:
    """Tres verificaciones. Ninguna es "el número publicado": el año del último fuego no es
    una cuenta, es una fecha, y no hay tabla contra la cual cerrarlo.  Lo que sí se exige:

      1. TODO año decodificado cae en [1999, 2025].  Un promedio de años no puede salirse del
         rango, así que un valor afuera delata el encoding (el offset de 1998, el x100 o el
         nodata) — que es exactamente el error que no se ve mirando el mapa.
      2. LAS DOS BANDAS COINCIDEN CELDA A CELDA: hay año si y sólo si `burned_pct > 0`.  Es
         una identidad por construcción (las dos salen del mismo asset y la misma retícula),
         así que cualquier desacuerdo es un bug del encoding o del recorte, no un redondeo.
      3. LOS DOS RÁSTERS JUNTOS: EL PROMEDIO DE FUEGOS POR PÍXEL QUEMADO.

         ⚠️ NO se puede comparar "la huella" de los dos.  El mapa de frecuencia da el
         PROMEDIO de veces que ardió la celda, y de un promedio NO se recupera qué fracción
         de los píxeles ardió alguna vez: una celda con 0,25 de promedio puede ser un cuarto
         de los píxeles ardiendo una vez o un octavo ardiendo dos.  La primera versión de
         esta compuerta comparaba 14,68 % (fracción de píxeles quemables que ardieron alguna
         vez, de la banda 2 de acá) contra 26,45 % (fracción del área quemable que cae en
         celdas con ALGÚN píxel quemado, del mapa de frecuencia) y fallaba por 11,8 pp
         midiendo dos cosas distintas.  El segundo número es mayor por construcción — es una
         dilatación al tamaño de celda— y no es un error de ninguno de los dos rásters.

         Lo que SÍ relaciona a los dos, y es la cuenta que cierra:

             fuegos promedio por píxel quemado = (veces que ardió el píxel promedio)
                                                 / (fracción de píxeles que ardió alguna vez)

         El numerador sale del mapa de frecuencia (`burn_perc` x 27 / 100, ponderado por lo
         quemable) y el denominador de la banda 2 de acá.  El cociente TIENE que caer en
         [1, 27]: un píxel que ardió, ardió al menos una vez, y no más veces que años tiene la
         serie.  Por debajo de 1 hay una inconsistencia real entre los dos productos.
    """
    try:
        from osgeo import gdal
        import numpy as np
    except ImportError:
        print("[skip] falta GDAL/numpy en este intérprete")
        return 0

    path = OUT_DIR / f"{name_of(args)}.tif"
    if not path.exists():
        raise SystemExit(f"{path} no existe — corré --fetch")
    ds = gdal.Open(str(path))
    gt = ds.GetGeoTransform()
    raw = ds.GetRasterBand(1).ReadAsArray().astype("float64")
    has_year = raw != NODATA
    year = np.where(has_year, raw / SCALE_FACTOR + YEAR_BASE, np.nan)
    rawp = ds.GetRasterBand(2).ReadAsArray().astype("float64")
    has_pct = rawp != NODATA
    pct = np.where(has_pct, rawp / SCALE_FACTOR, np.nan)
    burned = has_pct & (pct > 0)

    # área de suelo de la celda en 4326: constante en grados, ∝ cos(lat) en el terreno
    lat = gt[3] + (np.arange(ds.RasterYSize) + 0.5) * gt[5]
    W = np.broadcast_to(np.cos(np.deg2rad(lat))[:, None], raw.shape)

    ok = True
    print(f"  celdas con dato          {int(has_pct.sum()):,} de {raw.size:,}")
    print(f"  celdas con año           {int(has_year.sum()):,}")
    lo, hi = np.nanmin(year), np.nanmax(year)
    print(f"  rango del año            {lo:.2f} .. {hi:.2f}   (esperado {FIRST_YEAR}..{LAST_YEAR})")
    ok &= bool(FIRST_YEAR - 0.001 <= lo and hi <= LAST_YEAR + 0.001)

    disagree = int((has_year ^ burned).sum())
    print(f"  año XOR burned_pct>0     {disagree:,} celdas   (esperado 0, es una identidad)")
    ok &= disagree == 0

    # cuartiles del año ponderados por la superficie QUEMADA de la celda — que es lo que el
    # mapa dibuja: una celda que ardió entera pesa más que una que ardió en un 1 %.
    w = np.where(burned, pct * W, 0.0).ravel()
    ys = year.ravel()
    o = np.argsort(np.where(np.isnan(ys), np.inf, ys))
    ys, w = ys[o], w[o]
    keep = ~np.isnan(ys)
    cum = np.cumsum(w[keep]) / w[keep].sum()
    qs = [float(ys[keep][np.searchsorted(cum, q)]) for q in (0.25, 0.5, 0.75)]
    print(f"  cuartiles del año        {qs[0]:.1f} / {qs[1]:.1f} / {qs[2]:.1f}   (pond. área quemada)")

    # la huella: % del área quemable que ardió alguna vez.  `burned_pct` YA es ese % dentro
    # de la celda, así que el número nacional es su promedio ponderado por área de celda.
    huella = float((np.where(has_pct, pct, 0) * W).sum() / W[has_pct].sum())
    print(f"  huella nacional          {huella:.2f} % del área quemable ardió alguna vez")

    freq_path = OUT_DIR / "arg_burn_perc_480m_mean.tif"
    if freq_path.exists():
        fd = gdal.Open(str(freq_path))
        fgt = fd.GetGeoTransform()
        fp = fd.GetRasterBand(1).ReadAsArray().astype("float64")
        fhave = fp != NODATA
        fp = np.where(fhave, fp / SCALE_FACTOR, 0.0)         # % de los años con fuego
        R = 6378137.0                                        # 3857: el área cae con cos^2(lat)
        fy = fgt[3] + (np.arange(fd.RasterYSize) + 0.5) * fgt[5]
        flat = 2 * np.arctan(np.exp(fy / R)) - np.pi / 2
        FW = np.broadcast_to((np.cos(flat) ** 2)[:, None], fp.shape).astype("float64")
        if fd.RasterCount >= 2:
            fr = fd.GetRasterBand(2).ReadAsArray().astype("float64")
            fr = np.where(fr != NODATA, fr / SCALE_FACTOR / 100.0, 0.0)
            FW = FW * fr                                     # peso por lo QUEMABLE de la celda
        # el mismo promedio nacional que publica `burn_perc_export.py --check`
        perc_nac = float((FW * fp)[fhave].sum() / FW[fhave].sum())
        veces = perc_nac / 100 * N_YEARS_SERIES
        ratio = veces / (huella / 100)
        print(f"  veces/píxel (mapa de %)  {veces:.4f}   (= {perc_nac:.3f} % x {N_YEARS_SERIES} / 100)")
        print(f"  fuegos por píxel quemado {ratio:.2f}   (tiene que caer en [1, {N_YEARS_SERIES}])")
        ok &= 1.0 <= ratio <= N_YEARS_SERIES
    else:
        print("  [.] `arg_burn_perc_480m_mean.tif` no está bajado — sin cruce (compuerta 3)")

    print("\n  VERDICT: " + ("PASS" if ok else "LOOK AT THIS"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", action="store_true", help="lanza la tarea batch")
    ap.add_argument("--status", action="store_true", help="estado de la tarea")
    ap.add_argument("--fetch", action="store_true", help="baja el GeoTIFF y corre la compuerta")
    ap.add_argument("--check", action="store_true", help="sólo la compuerta, sin red")
    ap.add_argument("--factor", type=int, default=16,
                    help="factor entero sobre los 30 m nativos (16 = 480 m, por defecto)")
    ap.add_argument("--denom", choices=("burnable", "land"), default="burnable")
    ap.add_argument("--to-gcs", action="store_true",
                    help=f"exportar/bajar desde gs://{GCS_BUCKET}/{GCS_PREFIX} en vez de Drive")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--credentials")
    ap.add_argument("--project", default=C.GEE_PROJECT)
    args = ap.parse_args()

    if args.check:                       # sin red: no inicializa EE
        return check(args)
    initialize(args.project, args.credentials)
    if args.export:
        return export(args)
    if args.status:
        return status(args)
    if args.fetch:
        return fetch(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
