#!/usr/bin/env python3
"""
collection-01/validation/01_strata_export.py

Paso 1 de la validación — LA IMAGEN DE ESTRATOS, en la grilla del producto (30 m), por año-fuego.
Traducción directa a Python del Appendix A de `docs/10-validation.md` (§4) — ese doc es el
diseño CERRADO, no un borrador; acá no se innova, se implementa.

    projects/mapbiomas-argentina/assets/FIRE/VALIDATION/sampling_strata/sampling_strata_fy<FY>

Dos bandas:

    stratum  (uint8)  1 = quemado (S1) · 2 = borde/evidencia (S2) · 3 = resto (S3)
    burned   (uint8)  0/1 — la propia llamada del mapa (`our_burn`), o sea burned == (stratum==1)

LOS TRES ESTRATOS (§4)
-----------------------
    S2 = dilate( our_burn OR MCD64A1 OR VNP64A1 OR FireCCI51 OR FIRMS )  AND NOT our_burn
    S1 = our_burn
    S3 = NOT S1 AND NOT S2

UNIÓN, no intersección — y dilatada — porque tiene que capturar dos tipos de omisión a la vez
(§4.1): fuegos que Col-1 no vio en absoluto (evidencia externa) y cicatrices que sí vio pero
dibujó de menos (nuestra propia capa, dilatada). Favorecer recall sobre precisión en S2 es
la regla de diseño: sub-incluir empuja omisión a S3, que carga ~94% del peso de área y por lo
tanto la mayor parte de la varianza.

LA GRILLA GRUESA TIENE QUE ANIDAR EN LA GRILLA DEL PRODUCTO (§4.2)
--------------------------------------------------------------------
No es una grilla de 500 m independiente ni la sinusoidal de MODIS: es la grilla del producto
(`C.SNIC_TRANSFORM`) decimada ×16 (~480 m), mismo origen. Cada celda gruesa es un bloque exacto
de 16×16 píxeles del producto — la agregación es exacta y la reproyección gruesa→30 m es
replicación de bloque, sin ambigüedad de resampleo.

`max`, NUNCA `mode`, como reductor de agregación (§4.3) — con `mode` una celda de 16×16 sólo
cuenta "quemado" si más de 128 píxeles lo están (~>10 ha adentro de esa única celda), y el
fuego mínimo mapeado es 1 ha (`C.MIN_FIRE_HA`): borraría casi todos los fuegos chicos de la
unión. `mode` es correcto para bajar la resolución de un mapa categórico para visualizar; acá
invierte el objetivo del diseño.

DESVÍO DEL TEXTO LITERAL DEL APPENDIX A — projección default antes de `reduceResolution`
-------------------------------------------------------------------------------------------
El Appendix A hace `.max()` sobre las ImageCollections de MCD64A1/VNP64A1/FireCCI51 y pasa el
resultado directo a `reduceResolution`. Por el gotcha ya documentado en
`~/Desktop/geospatial-skills/SKILLS/gee-gotchas.md` ("setDefaultProjection antes de
reduceResolution": `.max()` sobre una ImageCollection pierde la proyección nativa, y sin
proyección `reduceResolution` falla con "no valid default projection"), acá se le pide la
proyección a `collection.first()` y se fija con `setDefaultProjection` antes de agregar. Es una
corrección mecánica para que el código corra — no toca la definición de S2, el orden de
operaciones ni el resultado que el diseño espera.

EL AÑO-FUEGO ES 1 MAYO fy → 30 ABRIL fy+1 (§3)
------------------------------------------------
`our_burn` sale de `C.MONTH_OF_BURN_COL` (banda `burned_monthly`, 1–12, ya filtrada a
`fire==1 & area_ha>=1`), armado como el OR de dos cortes de calendario:

    our_burn(fy) = (burned_monthly[fy] >= 5) OR (burned_monthly[fy+1] <= 4)

Exacto porque el mes/año se asignó por PÍXEL desde `abs_date` en el paso 07 — nunca por objeto.
Requiere que exista el año calendario fy+1, así que el rango validable es FY 1999–2024.

LA GRILLA VA PINNEADA — `crs` + `crsTransform`, NUNCA `scale=30`
-------------------------------------------------------------------
`scale: 30` en EPSG:4326 es otra grilla — otro origen, y 30 m no es ese paso en grados. Medio
píxel de corrimiento desalinearía S1 contra el raster de estratos.

USO
---
Autenticarse con la cuenta que tiene acceso a `mapbiomas-argentina` (ramonpagis@gmail.com):

    ~/.venvs/gee/bin/earthengine authenticate

    $PYTHON collection-01/validation/01_strata_export.py --check   --year 2022
    $PYTHON collection-01/validation/01_strata_export.py --launch  --year 2022
    $PYTHON collection-01/validation/01_strata_export.py --weights --year 2022

`--weights` corre sobre el ASSET YA ATERRIZADO, no sobre la cadena de pintado (§4.4: `Nh` es a
la vez el peso `Wh = Nh/ΣNh` y el fingerprint de reproducibilidad, ya que un asset de GEE no se
puede checksumear). Avisa si `W2 = N2/ΣNh` sale <2% o >15% (§4.6) — hay que revisar el radio de
dilatación ANTES de congelar si eso pasa; después de sortear las listas ya no se puede.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils.constants as C  # noqa: E402

# ---------------------------------------------------------------------------
# constantes de este paso
# ---------------------------------------------------------------------------
STRATA_COL = "projects/mapbiomas-argentina/assets/FIRE/VALIDATION/sampling_strata"

# El frame de POBLACIÓN es el país SIN buffer — no es C.ARG_BUFFER_FC, que es un superset usado
# para exportar los productos (§4.4). Hardcodeado tal cual el Appendix A, no vive en C.*.
FRAME_FC = ("projects/mapbiomas-argentina/assets/"
            "ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_1-Pais")

MCD64A1 = "MODIS/061/MCD64A1"
VNP64A1 = "NASA/VIIRS/002/VNP64A1"
FIRECCI = "ESA/CCI/FireCCI/5_1"
FIRMS = "FIRMS"

VNP64A1_RANGE = (2012, 2024)   # §4.5 — VIIRS burned area, GEE público desde 2012-03
FIRECCI_RANGE = (2001, 2019)   # §4.5 — cobertura FireCCI51

FACTOR = 16       # grilla gruesa = grilla del producto / FACTOR  (~480 m)
RAD_PX = 1        # focalMax radius, píxeles gruesos, kernel cuadrado

FY_MIN, FY_MAX = 1999, 2024   # rango validable (§3) — requiere que exista el año calendario fy+1
FIRE_YEARS = [2003, 2013, 2022]   # los tres años elegidos para esta validación

STRATUM_LABELS = {1: "quemado (S1)", 2: "borde/evidencia (S2)", 3: "resto (S3)"}

# COMPUTE PROJECT — a propósito distinto del default del repo.
#
# `C.GEE_PROJECT` es `mapbiomas-fire-485203`, el proyecto de Iván. Los assets que esta
# validación lee y escribe están en `mapbiomas-argentina`, y la cuenta con acceso a ese cloud
# project es ramonpagis@gmail.com. El compute project define contra qué cuota corre el cómputo;
# el path del asset define dónde viven los datos — son dos cosas independientes, pero conviene
# que coincidan porque `ee.data.listOperations()` está scopeado al compute project.
VAL_PROJECT = "mapbiomas-argentina"

OUT_DIR = Path(__file__).resolve().parent / "outputs"


# ---------------------------------------------------------------------------
# auth — mismo patrón que 07-burned_area_polygons.py::initialize()
# ---------------------------------------------------------------------------
def initialize(project, credentials_path=None):
    """`ee.Initialize`, opcionalmente con un archivo de credenciales que NO es el residente.

    Pasar el archivo explícito en vez de `cp`-ear sobre `~/.config/earthengine/credentials`:
    nada se clobberea, dos cuentas conviven en una sesión, y un `cp` a medias no deja el token
    equivocado puesto.
    """
    if not credentials_path:
        ee.Initialize(project=project)
        return
    from google.oauth2.credentials import Credentials
    stored = json.loads(Path(credentials_path).expanduser().read_text())
    ee.Initialize(Credentials(
        None,
        refresh_token=stored["refresh_token"],
        token_uri=ee.oauth.TOKEN_URI,
        client_id=stored.get("client_id", ee.oauth.CLIENT_ID),
        client_secret=stored.get("client_secret", ee.oauth.CLIENT_SECRET),
        scopes=stored.get("scopes", ee.oauth.SCOPES),
        quota_project_id=stored.get("project"),
    ), project=project)
    print(f"[auth] {credentials_path}  |  compute project {project}")


def asset_exists(asset_id):
    try:
        ee.data.getAsset(asset_id)
        return True
    except ee.EEException:
        return False


def task_in_flight(description):
    for op in ee.data.listOperations():
        meta = op.get("metadata", {})
        if (meta.get("description") == description
                and meta.get("state") in ("PENDING", "RUNNING")):
            return True
    return False


# ---------------------------------------------------------------------------
# grilla
# ---------------------------------------------------------------------------
def coarse_projection():
    """La grilla gruesa: `C.SNIC_TRANSFORM` decimado ×FACTOR, mismo origen (§4.2)."""
    t = C.SNIC_TRANSFORM
    coarse_t = [t[0] * FACTOR, 0, t[2], 0, t[4] * FACTOR, t[5]]
    return ee.Projection(C.SNIC_CRS, coarse_t)


def fire_year_window(fy):
    t0 = ee.Date.fromYMD(fy, 5, 1)
    return t0, t0.advance(1, "year")


def strata_asset(fy):
    return f"{STRATA_COL}/sampling_strata_fy{fy}"


# ---------------------------------------------------------------------------
# S1 — nuestra capa
# ---------------------------------------------------------------------------
def mob(y):
    """Imagen de mes-de-quema del año calendario y, banda `burned_monthly`, 1–12."""
    return (ee.Image(ee.ImageCollection(C.MONTH_OF_BURN_COL)
            .filter(ee.Filter.eq("year", y)).first())
            .select("burned_monthly").unmask(0))


def our_burn(fy):
    """`our_burn(fy)` — OR de los dos cortes de calendario que arman el año-fuego (§3)."""
    m_next = mob(fy + 1)
    return mob(fy).gte(5).Or(m_next.gte(1).And(m_next.lte(4)))


# ---------------------------------------------------------------------------
# evidencia externa (§4, §4.5)
# ---------------------------------------------------------------------------
def _burned_evidence(collection_id, band, t0, t1):
    """`.max()` sobre la colección filtrada — SIN proyección default (ver docstring del módulo:
    desvío del texto literal para que `reduceResolution` no falle más adelante)."""
    coll = ee.ImageCollection(collection_id).filterDate(t0, t1).select(band)
    proj = ee.Image(coll.first()).projection()
    return (coll.max().gte(1).unmask(0).setDefaultProjection(proj))


def firms_evidence(t0, t1):
    coll = ee.ImageCollection(FIRMS).filterDate(t0, t1).select("T21")
    proj = ee.Image(coll.first()).projection()
    return coll.max().gt(0).unmask(0).setDefaultProjection(proj)   # sin filtro de confidence — §4.1


def to_coarse_fine(img, coarse):
    """Finer-or-igual a COARSE (nuestra 30 m, FireCCI 250 m, VNP64A1/MCD64A1 463 m).
    `maxPixels=1024` porque el default de 64 es menor a los 256 píxeles de entrada de un
    bloque 16×16 (§4.3)."""
    return img.reduceResolution(reducer=ee.Reducer.max(), maxPixels=1024).reproject(coarse)


def to_coarse_coarse(img, coarse):
    """Coarser que COARSE (FIRMS, 927 m): el vecino más cercano replica la celda, no pierde nada."""
    return img.reproject(coarse)


def products_for(fy):
    """Qué productos externos entran en la unión para este año-fuego (§4.5)."""
    names = ["ours", "MCD64A1", "FIRMS"]
    if VNP64A1_RANGE[0] <= fy <= VNP64A1_RANGE[1]:
        names.append("VNP64A1")
    if FIRECCI_RANGE[0] <= fy <= FIRECCI_RANGE[1]:
        names.append("FireCCI51")
    return names


# ---------------------------------------------------------------------------
# el raster de estratos
# ---------------------------------------------------------------------------
def strata_image(fy):
    t0, t1 = fire_year_window(fy)
    coarse = coarse_projection()

    s1 = our_burn(fy)

    parts = [to_coarse_fine(s1, coarse),
             to_coarse_fine(_burned_evidence(MCD64A1, "BurnDate", t0, t1), coarse),
             to_coarse_coarse(firms_evidence(t0, t1), coarse)]
    if VNP64A1_RANGE[0] <= fy <= VNP64A1_RANGE[1]:
        parts.append(to_coarse_fine(_burned_evidence(VNP64A1, "Burn_Date", t0, t1), coarse))
    if FIRECCI_RANGE[0] <= fy <= FIRECCI_RANGE[1]:
        parts.append(to_coarse_fine(_burned_evidence(FIRECCI, "BurnDate", t0, t1), coarse))

    union = parts[0]
    for p in parts[1:]:
        union = union.Or(p)

    # dilatar en la grilla gruesa, después volver a la grilla del producto (replicación exacta)
    dilated = (union
               .focalMax(radius=RAD_PX, units="pixels", kernelType="square")
               .reproject(crs=C.SNIC_CRS, crsTransform=C.SNIC_TRANSFORM))

    s2 = dilated.And(s1.Not())
    s3 = s1.Not().And(s2.Not())

    stratum = (ee.Image(1).multiply(s1)
               .add(ee.Image(2).multiply(s2))
               .add(ee.Image(3).multiply(s3))
               .rename("stratum").toByte())

    products = products_for(fy)

    return (stratum
            .addBands(s1.rename("burned"))
            .toByte()
            .clip(ee.FeatureCollection(FRAME_FC))
            .set(
                "year", fy,                # año FUEGO — nunca calendario
                "collection", 1,
                "source", "mapbiomas-fuego",
                "region", "argentina",
                "fire_year_definition", "non-calendar: 1 May <year> to 30 Apr <year>+1",
                "coarse_factor", FACTOR,
                "dilation_radius_px", RAD_PX,
                "products", ",".join(products),
                "frame", "ARG-Political_Level_1-Pais",
                "bands", "stratum(1=mapped burned,2=evidence buffer,3=rest);burned(our map 0/1)",
            ))


# ---------------------------------------------------------------------------
# comandos
# ---------------------------------------------------------------------------
def check(fy):
    t0, t1 = fire_year_window(fy)
    print(f"[check] año-fuego {fy}: {t0.format().getInfo()} → {t1.format().getInfo()}")
    print(f"        productos externos incluidos: {', '.join(products_for(fy))}")

    win = ee.Geometry.Rectangle([-64.0, -38.0, -63.0, -37.0], None, False)  # ventana Pampa
    hist = (strata_image(fy).select("stratum").reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=win, crs=C.SNIC_CRS, crsTransform=C.SNIC_TRANSFORM,
        maxPixels=1e9).getInfo()["stratum"])
    print("        ventana de prueba (Pampa, 1°×1°):")
    for k in ("1", "2", "3"):
        print(f"          {k} {STRATUM_LABELS[int(k)]:<20} {int(hist.get(k, 0)):>10,} px")
    print(f"        destino: {strata_asset(fy)}")


def launch(fy, overwrite=False):
    asset_id = strata_asset(fy)
    description = f"val10_strata_fy{fy}"
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
        region=ee.FeatureCollection(FRAME_FC).geometry(),
        maxPixels=1e13,
        pyramidingPolicy={".default": "mode"},
    )
    task.start()
    print(f"[launch] {description} → {asset_id}  (task {task.id})")
    print("         seguir con `earthengine task list` o la pestaña Tasks")


def weights(fy):
    """`Wh = Nh/ΣNh` desde el asset ya aterrizado (§4.4). También el fingerprint de
    reproducibilidad, ya que un asset de GEE no se puede checksumear."""
    asset_id = strata_asset(fy)
    if not asset_exists(asset_id):
        sys.exit(f"[error] {asset_id} no existe todavía — correr --launch y esperar la tarea")

    img = ee.Image(asset_id).select("stratum")
    hist = img.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=ee.FeatureCollection(FRAME_FC).geometry(),
        crs=C.SNIC_CRS, crsTransform=C.SNIC_TRANSFORM,
        maxPixels=1e13, tileScale=4).getInfo()["stratum"]

    counts = {h: int(hist.get(str(h), 0)) for h in (1, 2, 3)}
    total = sum(counts.values())
    if total == 0:
        sys.exit("[error] el histograma dio 0 píxeles — revisar la máscara del asset")

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"strata_weights_fy{fy}.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["fire_year", "stratum", "label", "n_pixels", "Wh"])
        for h in (1, 2, 3):
            w.writerow([fy, h, STRATUM_LABELS[h], counts[h], f"{counts[h] / total:.10f}"])

    w2 = counts[2] / total
    print(f"[weights] año-fuego {fy} — total {total:,} px")
    for h in (1, 2, 3):
        print(f"          {h} {STRATUM_LABELS[h]:<20} {counts[h]:>15,} px   "
              f"Wh = {counts[h] / total:.6f}")
    if w2 < 0.02 or w2 > 0.15:
        print(f"[warn] W2 = {w2:.4f} fuera del rango esperado (2%–15%, §4.6) — "
              f"revisar el radio de dilatación ANTES de congelar las listas")
    print(f"[weights] escrito: {out}")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, required=True, help="año-fuego (1 may Y → 30 abr Y+1)")
    ap.add_argument("--check", action="store_true", help="conteos, sin exportar")
    ap.add_argument("--launch", action="store_true", help="exportar el asset de estratos")
    ap.add_argument("--weights", action="store_true",
                    help="calcular Wh desde el asset ya aterrizado → outputs/")
    ap.add_argument("--overwrite", action="store_true", help="reemplazar el asset si ya existe")
    ap.add_argument("--project", default=VAL_PROJECT,
                    help="compute project (default %(default)s — NO es C.GEE_PROJECT, "
                         "ver la nota en VAL_PROJECT)")
    ap.add_argument("--credentials",
                    help="archivo de credenciales alternativo (ver docstring de initialize)")
    args = ap.parse_args()

    if not (FY_MIN <= args.year <= FY_MAX):
        sys.exit(f"[error] {args.year} fuera del rango validable FY {FY_MIN}–{FY_MAX} (§3)")
    if args.year not in FIRE_YEARS:
        print(f"[warn] {args.year} no es uno de los tres años elegidos {FIRE_YEARS} — "
              f"seguimos igual, pero confirmar que es intencional")

    initialize(args.project, args.credentials)

    if args.check:
        check(args.year)
    elif args.launch:
        launch(args.year, args.overwrite)
    elif args.weights:
        weights(args.year)
    else:
        ap.error("elegir uno: --check, --launch o --weights")


if __name__ == "__main__":
    main()
