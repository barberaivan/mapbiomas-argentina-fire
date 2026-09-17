#!/usr/bin/env python
"""
collection-01/statistics/burn_perc_export.py — EL MAPA DE "% DE LOS AÑOS CON FUEGO"

El primero de los tres rásters que baja el factsheet (los otros dos son la corrida
`--reducer max` de acá mismo y `last_fire_export.py`).  Todo lo demás son tablas; esto es
una imagen, porque la figura de apertura quiere el mapa nacional al lado del mapa de
ecorregiones (docs/10 §0).

QUÉ COMPUTA
    `frequency_burned_v2`, banda `fire_frequency_1999_2025` (cuántos de los 27 años
    calendario quemó cada píxel), dividida por 27 y en porcentaje: "% de los años en
    que se quemó".  El CONTEO no sirve para publicar — depende del largo de la serie —
    y el porcentaje, además, es el MISMO número que la proporción quemada media anual
    del análisis 1, pero por píxel.  Verificado: el mapa, ponderado por área de suelo,
    da 0.838 % nacional = 63.23 Mha / 279.5 Mha / 27 años, exacto.

LAS TRES TRAMPAS (las mismas que documenta el script de GEE `explore_burn_perc_display`)
  1. EL PRODUCTO ESTÁ `selfMask`eado: nunca-quemado está AUSENTE, no en 0.  `unmask(0)`
     va antes de agregar o el promedio se toma sólo sobre lo quemado.
  2. EL REDUCTOR ES `mean`, no `max`.  Medido en el Chaco (verdad a 30 m 1.71 %): mean
     da 1.71 % a toda escala, max da 3.69 % a 480 m y 7.56 % a 1920 m.  `mean` es el
     único que conserva el número; `max` propaga el peor píxel de la celda.
  3. LA GRILLA ES LA DE LOS PRODUCTOS v2: EPSG:3857 a 30 m — NO la 4326 del SNIC, que
     es donde estaban los v1.  Se agrega por un factor ENTERO conservando el origen,
     así que las celdas de 480 m anidan exacto en las de 30 m: sin remuestreo.

     ⚠️ En 3857 el área de suelo de la celda cae con cos²(lat).  El ráster se DIBUJA,
     no se promedia: un `mean()` ingenuo sobre sus celdas da 0.759 % en vez de 0.838 %
     (sub-pesa el norte, que es donde está el fuego).  Cualquier estadístico va
     ponderado por área de celda — pero para la figura no importa.

POR QUÉ UNA TAREA BATCH Y NO `getDownloadURL`.  Medido: el chequeo de tamaño de la
descarga interactiva se hace sobre la resolución NATIVA (30 m), no sobre la grilla
pedida, así que un recuadro de 2° ya devuelve "Object too large (247 MB)" para un
resultado real de 0.5 MB, y uno de 1° revienta por memoria con la máscara quemable
(27 bandas de LULC).  El país entero en tiles de 0.75° serían ~900 pedidos.  La tarea
batch no tiene ninguno de esos límites y tarda minutos.

USO (desde la RAÍZ del repo), en el orden en que se corre
    --export     lanza UNA tarea batch -> Drive C.STATS_DRIVE_FOLDER (GeoTIFF).
    --status     estado de esa tarea.
    --fetch      la baja de Drive a data/statistics/ y corre la compuerta.
    --check      re-corre la compuerta sobre el archivo ya bajado (sin red).
Opciones: --factor 16 (480 m, por defecto) | --reducer mean|max|p90 | --denom burnable|land.

`--reducer max` es una SEGUNDA corrida y un SEGUNDO archivo, no una variante de dibujo: es el
mapa de conteos ENTEROS del factsheet ("el píxel que más ardió de esta celda ardió N veces",
docs/09 §5.5.1).  Es otra cuenta y exagera a propósito, así que `--check` informa los números
y NO cierra compuerta: el 0,933 % nacional sólo lo conserva `mean`.
`--credentials ~/.config/earthengine/credentials.comahue --project mapbiomas-argentina`
corre como la segunda cuenta (la cola de tareas es por usuario).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "collection-01"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ee  # noqa: E402

import legends  # noqa: E402
from utils import constants as C  # noqa: E402

OUT_DIR = REPO_ROOT / "collection-01" / "data" / "statistics"
TASK_PREFIX = "arg_burn_perc"        # namespaced: el proyecto de cómputo es COMPARTIDO

# GCS: el mismo bucket donde el toolkit de la red deja las tablas de Argentina (docs/09 §2),
# bajo el mismo prefijo del país. Medido 2026-09-16: las credenciales residentes tienen
# objects.{create,get,list,delete} ahí. Es alternativa a Drive, no reemplazo — `--to-gcs`.
GCS_BUCKET = "mapbiomas-fire"
GCS_PREFIX = "data-container/stats/mapbiomas_fuego_argentina_collection1/raster"

N_YEARS = 27                         # 1999..2025, la ventana de la banda
FREQ_BAND = "fire_frequency_1999_2025"
FIRST_LULC_YEAR, LAST_LULC_YEAR = 1998, 2024     # el modo quemable (docs/09 §4.2)

# La grilla nativa de los productos v2.  NO derivarla del asset en tiempo de ejecución:
# escrita acá, un cambio de grilla río arriba se ve como una falla de la compuerta y no
# como un ráster silenciosamente distinto.
CRS = "EPSG:3857"
ORIGIN_X, ORIGIN_Y, PIXEL = -8189460, -2483190, 30

SCALE_FACTOR = 100      # % x 100 -> uint16 (0.01 % de resolución numérica).  LAS DOS bandas
                        # son porcentajes con esta misma escala: un solo decode para ambas.

# Los dos números que publican las tablas, y contra los que corre la compuerta.  Cuál aplica
# lo decide `--denom`: no es el mismo porcentaje sobre el área quemable que sobre el país.
EXPECTED = {"burnable": 0.9327,   # 63.23 Mha / 251.09 Mha / 27 años  (= mean_pct nacional)
            "land": 0.8380}       # 63.23 Mha / 279.51 Mha / 27 años
NODATA = 65535
REDUCERS = {"mean": lambda: ee.Reducer.mean(),
            "max": lambda: ee.Reducer.max(),
            "p90": lambda: ee.Reducer.percentile([90])}


def transform(factor: int) -> list:
    s = PIXEL * factor
    return [s, 0, ORIGIN_X, 0, -s, ORIGIN_Y]


def name_of(args) -> str:
    return f"{TASK_PREFIX}_{PIXEL * args.factor}m_{args.reducer}"


# ---------------------------------------------------------------------------
# la imagen
# ---------------------------------------------------------------------------
def ecoregions() -> ee.FeatureCollection:
    """Las 12 reportadas.  Islas del Atlántico Sur queda afuera: su 0 es un hueco del
    mapeo, no un dato (docs/09 §3.2)."""
    return ee.FeatureCollection(C.ECOREGIONS13).filter(
        ee.Filter.neq(C.ECOREGION_ID_PROPERTY, 13))


def denominator(denom: str) -> ee.Image:
    """La máscara que define el DENOMINADOR de cada celda gruesa.

    `reduceResolution` ignora los píxeles enmascarados, así que esta máscara es
    literalmente el denominador: con 'burnable', "% de los años en que se quemó la
    parte quemable de la celda" — el mismo denominador que el resto del factsheet.
    """
    land = ee.Image().paint(ecoregions(), 1).mask()
    if denom != "burnable":
        return land
    lulc = ee.Image(C.PRODUCT_LULC)
    frm = legends.BURNABLE + legends.NON_BURNABLE
    to = [1] * len(legends.BURNABLE) + [0] * len(legends.NON_BURNABLE)
    # 0 y 27 ("no observado") no están en ninguna lista: remap los deja ENMASCARADOS y
    # nunca entran al promedio — que ES "no observado se excluye" (docs/09 §6).
    ind = [lulc.select(f"classification_{y}").remap(frm, to)
           for y in range(FIRST_LULC_YEAR, LAST_LULC_YEAR + 1)]
    mean = ee.ImageCollection(ind).mean()
    # Una celda sin NADA quemable (un lago, un salar, un glaciar) sale enmascarada, no
    # en 0: "no es quemable" y "es quemable y nunca se quemó" son cosas distintas.
    return mean.gt(0.5).And(land)


def burn_perc(args) -> ee.Image:
    perc = (ee.Image(f"{C.FINAL_PRODUCTS}/{C.product_name('frequency_burned')}")
            .select(FREQ_BAND)
            .unmask(0)                      # TRAMPA 1 — antes de cualquier agregación
            .divide(N_YEARS).multiply(100)
            .updateMask(denominator(args.denom))
            .rename("burn_perc"))
    if args.factor == 1:
        return perc
    return (perc
            .reduceResolution(reducer=REDUCERS[args.reducer](), maxPixels=65536)
            .reproject(crs=CRS, crsTransform=transform(args.factor)))


def burnable_pct(args) -> ee.Image:
    """Banda 2: QUÉ PORCENTAJE DE LA CELDA es quemable.

    Sin ella la banda 1 no se puede verificar.  El valor de cada celda es un COCIENTE con
    su propio denominador (los píxeles quemables de esa celda), y el promedio nacional que
    publican las tablas pesa por área QUEMABLE, no por área de celda.  Promediar las celdas
    a peso igual da 0.893 % donde la tabla dice 0.933 % — no porque el mapa esté mal, sino
    porque es otra cuenta.  Con esta banda el peso es el correcto y la compuerta cierra.

    De paso sirve para dibujar: una celda que es 99 % laguna y 1 % pastizal no merece el
    mismo tono que una entera de pastizal, y con esto R puede decidirlo.
    """
    land = ee.Image().paint(ecoregions(), 1).mask()
    # `unmask` sobre una constante deja la imagen SIN proyección fija, y reduceResolution
    # exige una ("does not have a valid default projection").  Se la fijamos a la grilla
    # nativa de 30 m — la misma sobre la que se agrega la banda 1, así que las dos bandas
    # cuentan exactamente los mismos píxeles.
    frac = (denominator("burnable").unmask(0).updateMask(land)
            .setDefaultProjection(crs=CRS, crsTransform=transform(1)))
    if args.factor == 1:
        return frac.multiply(100).rename("burnable_pct")
    return (frac.multiply(100)
            .reduceResolution(reducer=ee.Reducer.mean(), maxPixels=65536)
            .reproject(crs=CRS, crsTransform=transform(args.factor))
            .rename("burnable_pct"))


def export_image(args) -> ee.Image:
    """Dos bandas, ambas en % x 100, uint16 con nodata EXPLÍCITO: en uint16 el relleno por
    defecto de lo enmascarado es 0, que acá es un valor legítimo ("quemable y nunca
    quemado")."""
    img = burn_perc(args).rename("burn_perc")
    if args.denom == "burnable":
        img = img.addBands(burnable_pct(args))
    return img.multiply(SCALE_FACTOR).round().toUint16().unmask(NODATA).toUint16()


# ---------------------------------------------------------------------------
# export / status / fetch
# ---------------------------------------------------------------------------
def export(args) -> int:
    """Una tarea batch. Drive por defecto; `--to-gcs` manda el GeoTIFF al bucket de la red.

    Cuál conviene: para ESTA imagen da igual — lo que tarda es el cómputo (la máscara
    quemable son 27 bandas de LULC a 30 m sobre todo el país), no la transferencia de
    ~24 MB. GCS gana cuando el archivo es grande (descarga resumible y paralela por HTTPS
    con el mismo token, sin la API de Drive ni el rodeo del quota project) y porque es
    donde el resto del paso 09 ya lee.
    """
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


def drive_client(args):
    """Cliente de Drive SIN quota project — la misma razón que `burnable_export.py`:
    las credenciales guardadas llevan `project = mapbiomas-fire-485203`, que es el
    proyecto COMPARTIDO de la red y no tiene la API de Drive habilitada.  Habilitarla
    ahí para leer un archivo nuestro no nos corresponde; sin quota project la llamada
    se factura al cliente OAuth, funciona, y no toca nada."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    stored = json.loads(
        Path(args.credentials or "~/.config/earthengine/credentials").expanduser().read_text())
    creds = Credentials(
        None,
        refresh_token=stored["refresh_token"],
        token_uri=ee.oauth.TOKEN_URI,
        client_id=stored.get("client_id", ee.oauth.CLIENT_ID),
        client_secret=stored.get("client_secret", ee.oauth.CLIENT_SECRET),
        scopes=stored.get("scopes", ee.oauth.SCOPES),
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def oauth_credentials(args):
    """Las credenciales guardadas, como objeto OAuth. Sirven para EE, para Drive y para
    GCS: el archivo trae `devstorage.full_control` entre sus scopes."""
    from google.oauth2.credentials import Credentials

    stored = json.loads(
        Path(args.credentials or "~/.config/earthengine/credentials").expanduser().read_text())
    return Credentials(
        None,
        refresh_token=stored["refresh_token"],
        token_uri=ee.oauth.TOKEN_URI,
        client_id=stored.get("client_id", ee.oauth.CLIENT_ID),
        client_secret=stored.get("client_secret", ee.oauth.CLIENT_SECRET),
        scopes=stored.get("scopes", ee.oauth.SCOPES),
    )


def download_from_gcs(args, desc: str, out_dir: Path = OUT_DIR) -> Path:
    """Baja `desc.tif` de GCS por HTTPS con el mismo token. Sin API de Drive y sin rodeos.

    GENÉRICA a propósito (`desc` es argumento, no `name_of(args)`): `last_fire_export.py`
    baja su propio ráster con esta misma función en vez de copiar cuarenta líneas de OAuth.
    """
    import requests
    from google.auth.transport.requests import Request

    creds = oauth_credentials(args)
    creds.refresh(Request())
    obj = f"{GCS_PREFIX}/{desc}.tif"
    url = (f"https://storage.googleapis.com/storage/v1/b/{GCS_BUCKET}/o/"
           f"{requests.utils.quote(obj, safe='')}")
    head = requests.get(url, headers={"Authorization": f"Bearer {creds.token}"}, timeout=60)
    if head.status_code == 404:
        raise SystemExit(f"gs://{GCS_BUCKET}/{obj} no está todavía — mirá --status")
    head.raise_for_status()
    print(f"[gcs] {obj}  {int(head.json()['size'])/1e6:.1f} MB  {head.json()['updated']}")

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{desc}.tif"
    with requests.get(url, params={"alt": "media"}, stream=True,
                      headers={"Authorization": f"Bearer {creds.token}"}, timeout=600) as r:
        r.raise_for_status()
        with open(out, "wb") as fh:
            for chunk in r.iter_content(8 << 20):
                fh.write(chunk)
    print(f"wrote {out.relative_to(REPO_ROOT)}")
    return out


def download_from_drive(args, desc: str, out_dir: Path = OUT_DIR) -> Path:
    """Lo mismo, desde Drive. También genérica, y por la misma razón."""
    from googleapiclient.http import MediaIoBaseDownload
    import io

    drive = drive_client(args)
    q = f"name = '{desc}.tif' and trashed = false"
    files = drive.files().list(q=q, fields="files(id,name,modifiedTime,size)",
                               orderBy="modifiedTime desc").execute().get("files", [])
    if not files:
        raise SystemExit(f"{desc}.tif no está en Drive todavía — mirá --status")
    f0 = files[0]
    print(f"[drive] {f0['name']}  {int(f0.get('size', 0))/1e6:.1f} MB  {f0.get('modifiedTime')}")

    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{desc}.tif"
    buf = io.FileIO(out, "wb")
    dl = MediaIoBaseDownload(buf, drive.files().get_media(fileId=f0["id"]),
                             chunksize=32 * 1024 * 1024)
    done = False
    while not done:
        st, done = dl.next_chunk()
        print(f"  {int(st.progress() * 100):>3d} %", end="\r")
    buf.close()
    print(f"\nwrote {out.relative_to(REPO_ROOT)}")
    return out


def fetch(args) -> int:
    desc = name_of(args)
    if args.to_gcs:
        download_from_gcs(args, desc)
    else:
        download_from_drive(args, desc)
    return check(args)


def check(args) -> int:
    """LA COMPUERTA: el promedio del ráster contra el número que publican las tablas.

    Dos pesos, y los dos hacen falta:
      * área de suelo — en 3857 el área de la celda cae con cos²(lat), así que el promedio
        simple sub-pesa el norte, que es donde está el fuego;
      * área QUEMABLE de la celda (banda 2) — porque el valor de cada celda es un cociente
        con su propio denominador, y el número nacional pesa por lo quemable, no por celda.
    Sin el segundo, el resultado es 0.893 % contra 0.933 % y parece un error del mapa.
    """
    try:
        from osgeo import gdal, osr
        import numpy as np
    except ImportError:
        print("[skip] falta GDAL/numpy en este intérprete — corré la compuerta en R")
        return 0

    path = OUT_DIR / f"{name_of(args)}.tif"
    if not path.exists():
        raise SystemExit(f"{path} no existe — corré --fetch")
    ds = gdal.Open(str(path))
    gt = ds.GetGeoTransform()
    band = ds.GetRasterBand(1)
    a = band.ReadAsArray().astype("float64")
    a[a == NODATA] = np.nan
    a /= SCALE_FACTOR
    frac = None
    if ds.RasterCount >= 2:
        frac = ds.GetRasterBand(2).ReadAsArray().astype("float64")
        frac[frac == NODATA] = np.nan
        frac = frac / SCALE_FACTOR / 100.0          # % -> fracción

    # área de suelo de cada fila: en Mercator esférico, dA ∝ cos²(lat) del centro de fila
    srs = osr.SpatialReference(); srs.ImportFromEPSG(3857)
    R = srs.GetSemiMajor()
    rows = np.arange(ds.RasterYSize)
    y = gt[3] + (rows + 0.5) * gt[5]
    lat = 2 * np.arctan(np.exp(y / R)) - np.pi / 2
    w = np.cos(lat) ** 2                      # peso por fila, hasta una constante

    ok = ~np.isnan(a)
    W = np.broadcast_to(w[:, None], a.shape)
    def wmean(weights):
        m = ok & ~np.isnan(weights)
        return float((np.where(m, a, 0) * np.where(m, weights, 0)).sum()
                     / np.where(m, weights, 0).sum())
    expected = EXPECTED[args.denom]
    print(f"  celdas con dato          {int(ok.sum()):,} de {a.size:,}")
    if args.reducer != "mean":
        # Sólo `mean` conserva el número nacional (TRAMPA 2): el max de la celda es otra
        # cuenta y no tiene contra qué cerrar.  Se informa y no se falla — si no, la corrida
        # de `--reducer max` (el mapa de conteo entero, docs/09 §5.5.1) parece rota.
        print(f"  promedio simple          {np.nanmean(a):.3f} %")
        print(f"  máximo                   {np.nanmax(a):.3f} %")
        print(f"\n  SIN COMPUERTA: `--reducer {args.reducer}` no conserva el número nacional "
              f"({expected:.3f} %) — es otra cuenta, a propósito.")
        return 0
    print(f"  promedio simple          {np.nanmean(a):.3f} %   (Mercator: sub-pesa el norte)")
    print(f"  ponderado por área       {wmean(W):.3f} %   (celda, no lo quemable de la celda)")
    got = wmean(W)
    if frac is not None:
        got = wmean(W * frac)
        print(f"  ponderado por quemable   {got:.3f} %   <- el que corresponde")
    else:
        print("  [!] falta la banda 2 (burnable_pct): sin ella el peso no puede ser el correcto")
    print(f"  esperado ({args.denom})   {expected:.3f} %")
    off = abs(got - expected)
    tol = 0.01 if frac is not None else 0.05
    print("\n  VERDICT: " + ("PASS" if off < tol else f"LOOK AT THIS — difiere en {off:.3f} pp"))
    return 0 if off < tol else 1


def initialize(project, credentials_path=None):
    """`ee.Initialize`, opcionalmente con un archivo de credenciales que NO es el
    residente (CLAUDE.md: pasar las credenciales, nunca `cp`-earlas encima)."""
    if not credentials_path:
        ee.Initialize(project=project)
        return
    from google.oauth2.credentials import Credentials
    stored = json.loads(Path(credentials_path).expanduser().read_text())
    ee.Initialize(credentials=Credentials(
        None,
        refresh_token=stored["refresh_token"],
        token_uri=ee.oauth.TOKEN_URI,
        client_id=stored.get("client_id", ee.oauth.CLIENT_ID),
        client_secret=stored.get("client_secret", ee.oauth.CLIENT_SECRET),
        scopes=stored.get("scopes", ee.oauth.SCOPES),
    ), project=project)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--export", action="store_true", help="lanza la tarea batch -> Drive")
    ap.add_argument("--status", action="store_true", help="estado de la tarea")
    ap.add_argument("--fetch", action="store_true", help="baja de Drive y corre la compuerta")
    ap.add_argument("--check", action="store_true", help="sólo la compuerta, sin red")
    ap.add_argument("--factor", type=int, default=16,
                    help="factor entero sobre los 30 m nativos (16 = 480 m, por defecto)")
    ap.add_argument("--reducer", choices=sorted(REDUCERS), default="mean")
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
