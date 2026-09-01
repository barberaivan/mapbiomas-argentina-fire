#!/usr/bin/env python3
"""
collection-01/validation/02_sample_pool.py

Paso 2 de la validación — LAS LISTAS ORDENADAS CONGELADAS, por estrato y por año-fuego.
Se corre DESPUÉS de que el paso 01 esté aterrizado y congelado — nunca antes: el diseño entero
depende de sortear sobre el raster de estratos ya fijo.

⚠️ CAMINO RECOMENDADO (2026-08-31): `--pilot-launch` → `--pilot-report` → `--launch-pool` →
`--freeze --from-pool`. NO usar `--launch`/`--launch-by-carta` — ver "LA SAGA DEL OOM" abajo.

LA SAGA DEL OOM Y LA CAUSA REAL (2026-08-30/31) — leer antes de tocar este archivo
--------------------------------------------------------------------------------------
El plan original (Appendix B de `docs/10-validation.md`, un `stratifiedSample` por estrato)
murió por OOM (GEE error code 8) en TODAS las variantes probadas esa noche: país-completo, con
`tileScale`/`classValues` altos, partido en las ~248 cartas de MapBiomas, con `reduceRegion` en
vez de `stratifiedSample` — seis intentos distintos, misma falla. La causa NO era `stratum`, ni
`stratifiedSample` vs `sample()`, ni el particionado: era la GEOMETRÍA de región. `FRAME_FC`
(`ARG-Political_Level_1-Pais`) tiene más de 2 millones de bordes (el mismo límite político que ya
hace fallar `.bounds()` en otros contextos de este proyecto). Cualquier operación que reciba esa
geometría como `region=` — sortear, reducir, lo que sea — paga el costo de decidir "¿este
candidato cae adentro?" contra una forma gigantesca, sin importar el algoritmo de arriba.

Prueba de control 2026-08-31: mismo `sample()`, mismas bandas mínimas, mismo asset de estratos
(que además está `.clip()`eado a este mismo límite complejo desde que se exportó, Apéndice A) —
con `FRAME_FC.geometry()` como región: OOM, 5/5 intentos. Con un rectángulo simple
(`ee.Geometry.Rectangle`, ver `arg_bbox()`) como región: éxito, 3/3 veces, ~15-20s de reloj para
20k-100k puntos. El límite complejo "horneado" en el asset no importa — lo que importa es la
geometría que se pasa EN EL MOMENTO de la consulta.

Con eso resuelto, el método de sorteo también cambió — no por necesidad (el fix de geometría solo
ya hubiera alcanzado para `stratifiedSample`), sino porque ya se había armado un camino más simple
mientras se buscaba la causa: en vez de pedir "solo los píxeles de esta clase" (`stratifiedSample`,
un pedido por estrato), se sortea un POOL sin estratificar (`Image.sample()`, sin `classBand`, un
solo pedido por año) y la separación por estrato se hace LOCAL, en pandas — ver el bloque "POOL NO
ESTRATIFICADO" más abajo para el detalle completo (incluye por qué es estadísticamente idéntico).

DOS MODOS VIEJOS (país-completo / por carta) — SUPERADOS, quedan como referencia histórica
------------------------------------------------------------------------------------------------
    --launch            en GEE: sortea 6.000 píxeles por estrato por año directo con
                         `stratifiedSample` país-completo. MUERE POR OOM — ver la saga arriba.
    --launch-by-carta    ídem, particionado por carta. TAMBIÉN muere por OOM (el particionado no
                         alcanzaba sin el fix de geometría). No se volvió a intentar después del
                         fix porque el pool ya lo reemplazó, no porque se descartara la idea.
    --freeze             LOCAL, una vez el CSV ya bajó de Drive: verifica el conteo de filas, la
                         consistencia `burned == (stratum==1)`, trunca a los primeros 5.000 por
                         orden, deriva `col`/`row` desde `lon`/`lat` con la retícula pinneada, y
                         archiva. Nunca se vuelve a correr sobre la misma lista — regenerarla,
                         resortearla o descartar una fila ya sorteada invalida el diseño (§5
                         regla 6). Sigue siendo el motor de `--freeze --from-pool` (§ ver abajo).

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

USO — camino recomendado (pool)
--------------------------------
    $PYTHON collection-01/validation/02_sample_pool.py --pilot-launch --year 2022
    # ... bajar val10_pilot_fy2022.csv de Drive a outputs/raw/ ...
    $PYTHON collection-01/validation/02_sample_pool.py --pilot-report --year 2022
    # ... calcular n_full con size_full_draw() a partir de esos conteos (ver docstring de la función) ...
    $PYTHON collection-01/validation/02_sample_pool.py --launch-pool <N> --year 2022
    # ... bajar val10_pool_fy2022.csv de Drive a outputs/raw/ ...
    $PYTHON collection-01/validation/02_sample_pool.py --freeze --from-pool --year 2022 --stratum 1

ESTADO (2026-08-31): los 3 años del diseño (2003/2013/2022) ya corrieron este camino completo —
9 listas congeladas en outputs/frozen/, y `03_ceo_export.py --export --all-years` ya generó y
subió (a mano, vía Code Editor → Assets → NEW → CSV file) los 3 `ceo_upload_fy<FY>.csv` como
`projects/mapbiomas-argentina/assets/FIRE/VALIDATION/ceo_points/ceo_points_fy<FY>`. Pendiente:
el pool 2 (extender a las 5.000/estrato congeladas — mecanismo sin implementar todavía, ver
`docs/10-validation.md`) y el censo exacto de Nh (`01_strata_export.py --weights-launch` sigue
bloqueado por el mismo tipo de OOM, no probado con el fix de geometría — VERIFICAR antes de asumir
que sigue roto).
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
TILE_SCALE = 16        # subido de 8 -> 16 (2026-08-30): fy2003 S1/S2/S3 murieron por OOM (code 8)
                       # incluso después de separar stratifiedSample de sampleRegions — el EECU
                       # quemado antes de morir es idéntico al de la corrida vieja de S1 (310 EECU-s
                       # en ambas), así que el cuello de botella es el propio stratifiedSample
                       # país-completo, no lo que viene después. Tiles más chicos = menos memoria
                       # por worker; probar primero, es el cambio más barato.
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
        # classValues/classPoints explícitos (2026-08-30): `sel` sólo tiene la clase 1 (el resto
        # está enmascarado), pero sin esto GEE igual tiene que descubrir qué clases hay barriendo
        # el país entero antes de repartir la cuota. Decírselo de entrada evita esa pasada.
        classValues=[1],
        classPoints=[N_DRAW],
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
# SORTEO POR CARTA (2026-08-30)
# ---------------------------------------------------------------------------
# `draw()` país-completo murió por OOM (code 8) en los 3 estratos de fy2003 — probado dos
# veces, con y sin el split stratifiedSample/sampleRegions, con y sin tileScale/classValues
# altos. La causa: `stratum` NO tiene máscara (cada uno de los ~3.1e9 px del país vale 1, 2 o
# 3), así que cualquier reduce o sample sobre ella es denso a escala país sin importar el
# algoritmo — se probó también con `weights_launch` (reduceRegion, no stratifiedSample) y murió
# igual. Un recorte "buscar sólo donde está la clase" tampoco sirve: S1/fy2003 vive en 10.985
# blobs desconectados (~1,9 km) — unir esa geometría sería una operación tan pesada como la que
# se quiere evitar.
#
# La solución es particionar por CARTA (`C.CARTAS_FC`, ~248 cartas, ~1/250 del país cada una,
# ~12M px a 30 m) — el mismo grid que step 03 ya usa para las predicciones imagen-por-imagen
# país-completo, por la misma razón. Cada `stratifiedSample`/`reduceRegion` corre sobre UNA
# carta (chico, manejable) en vez del país entero.
#
# Para que el sorteo por carta sea estadísticamente IDÉNTICO a un muestreo aleatorio simple
# país-completo (no un diseño distinto), la cuota de cada carta tiene que ser EXACTAMENTE
# proporcional a cuánto de ese estrato hay en esa carta (`Nh_carta / Nh_total × N_DRAW`):
# asignación proporcional + SRS dentro de cada parte = SRS del total (ver docs/10 §5 — el mismo
# principio que ya justifica "truncar a 5.000 por orden es un SRS válido"). Por eso hace falta
# el paso de pesos POR CARTA antes de poder sortear — no se puede adivinar una cuota pareja.
CARTAS_ID = C.CARTAS_ID_PROPERTY


def cartas_in_frame():
    """Las ~248 cartas que cubren el país — mismo grid que `C.CARTAS_FC` (step 03)."""
    return ee.FeatureCollection(C.CARTAS_FC).filterBounds(
        ee.FeatureCollection(FRAME_FC).geometry())


MAX_PX_PER_REGION = 50_000_000   # la carta más grande mide ~19.2M px a 30 m (medido 2026-08-30);
                                  # el default de reduceRegions() es 10M — por debajo de eso. Sin
                                  # este parámetro explícito, la primera corrida murió por OOM en
                                  # 37 min (vs. horas/días de los intentos país-completo): apilar
                                  # las 3 bandas booleanas en un solo Image.cat() antes de reducir
                                  # triplicaba encima el volumen por carta.


def weights_by_carta_launch(fy):
    """Nh POR CARTA, TRES tareas batch (una por estrato, no las 3 bandas juntas — ver
    MAX_PX_PER_REGION) usando `reduceRegions`, no 248 exports separados: cada carta es ~1/250
    del país, así que el reduce individual es manejable aunque la banda de origen (`stratum`)
    no tenga máscara. Sale a Drive como CSV (no es parte del diseño congelado — es un insumo
    local para `compute_quotas()`, así que no necesita vivir como asset de GEE como sí lo es
    `weights_asset()` en 01_strata_export.py)."""
    strata_img = strata_by_year(fy)
    cartas = cartas_in_frame().select([CARTAS_ID])
    for h in STRATA:
        description = f"val10_weights_by_carta_fy{fy}_s{h}"
        if task_in_flight(description):
            print(f"[skip] {description} tiene una tarea PENDING/RUNNING")
            continue
        band = strata_img.select("stratum").eq(h).rename(f"n{h}")
        fc = band.reduceRegions(
            collection=cartas,
            reducer=ee.Reducer.sum().unweighted(),
            crs=C.SNIC_CRS, crsTransform=C.SNIC_TRANSFORM,
            tileScale=TILE_SCALE,
            maxPixelsPerRegion=MAX_PX_PER_REGION,
        )
        task = ee.batch.Export.table.toDrive(
            collection=fc, description=description, folder=DRIVE_FOLDER,
            fileNamePrefix=description, fileFormat="CSV",
            selectors=[CARTAS_ID, f"n{h}"],
        )
        task.start()
        print(f"[weights-by-carta] {description} → Drive/{DRIVE_FOLDER}  (task {task.id})")


def compute_quotas(fy, csv_dir=None, n_draw=N_DRAW):
    """Lee los 3 CSV YA bajados de Drive (`weights_by_carta_launch` — uno por estrato, ver
    MAX_PX_PER_REGION), reparte `n_draw` puntos por estrato entre las cartas EXACTAMENTE
    proporcional a Nh_carta/Nh_total, con el método del resto más grande (Hamilton) para que la
    suma dé `n_draw` exacto pese al redondeo. Devuelve `{h: {grid_name: quota}}`, listo para
    `draw_by_carta()`."""
    csv_dir = Path(csv_dir) if csv_dir else RAW_DIR
    quotas = {}
    for h in STRATA:
        col = f"n{h}"
        path = csv_dir / f"val10_weights_by_carta_fy{fy}_s{h}.csv"
        if not path.exists():
            sys.exit(f"[error] no encontrado: {path}  (bajar de Drive/{DRIVE_FOLDER} primero)")
        df = pd.read_csv(path)
        total = int(df[col].sum())
        if total == 0:
            sys.exit(f"[error] estrato {h} tiene 0 píxeles en TODAS las cartas — revisar {path}")
        raw = df[col].to_numpy() / total * n_draw
        base = np.floor(raw).astype(int)
        remainder = n_draw - int(base.sum())
        if remainder > 0:
            top = np.argsort(raw - base)[::-1][:remainder]
            base[top] += 1
        quotas[h] = {str(gid): int(q) for gid, q in zip(df[CARTAS_ID], base) if q > 0}
    return quotas


def draw_by_carta(fy, h, quotas_h):
    """Igual resultado que `draw()`, particionado por carta (ver nota arriba). `quotas_h` es
    `{grid_name: quota}` de `compute_quotas()` — SÓLO las cartas con cuota > 0 entran al dict,
    las demás no aportan candidatos (evita pedirle `stratifiedSample` con `numPoints=0`, que no
    hace falta probar si falla o no)."""
    strata_img = strata_by_year(fy)
    sel = strata_img.select("stratum").eq(h).selfMask().rename("sel")
    proj = ee.Projection(C.SNIC_CRS, C.SNIC_TRANSFORM)
    quota_dict = ee.Dictionary(quotas_h)

    def per_carta(feature):
        quota = quota_dict.get(feature.get(CARTAS_ID), None)
        return ee.FeatureCollection(ee.Algorithms.If(
            quota,
            sel.stratifiedSample(
                numPoints=ee.Number(quota), classBand="sel", region=feature.geometry(),
                projection=proj, seed=SEED, classValues=[1], classPoints=[ee.Number(quota)],
                geometries=True, tileScale=TILE_SCALE),
            ee.FeatureCollection([])))

    cartas = cartas_in_frame().filter(ee.Filter.inList(CARTAS_ID, list(quotas_h.keys())))
    locations = ee.FeatureCollection(cartas.toList(300).map(per_carta)).flatten()

    ll = ee.Image.pixelLonLat()
    sampled = (attrs_image(fy).addBands(ll)).sampleRegions(
        collection=locations, projection=proj, tileScale=TILE_SCALE, geometries=False)
    return sampled.sort("order_key")


def launch_by_carta(fy, quotas):
    """`quotas` = `{h: {grid_name: quota}}` de `compute_quotas()`. Misma salida (Drive, mismo
    nombre de tarea `task_name()`) que `launch()` — `freeze()` no necesita saber si el CSV vino
    del sorteo país-completo o del particionado por carta, el formato es idéntico."""
    for h in STRATA:
        description = task_name(fy, h)
        if task_in_flight(description):
            print(f"[skip] {description} tiene tarea PENDING/RUNNING")
            continue
        n_cartas = len(quotas[h])
        task = ee.batch.Export.table.toDrive(
            collection=draw_by_carta(fy, h, quotas[h]),
            description=description,
            folder=DRIVE_FOLDER,
            fileNamePrefix=description,
            fileFormat="CSV",
            selectors=SELECTORS,
        )
        task.start()
        print(f"[launch-by-carta] {description} ({n_cartas} cartas con cuota > 0) → "
              f"Drive/{DRIVE_FOLDER}  (task {task.id})")


# ---------------------------------------------------------------------------
# POOL NO ESTRATIFICADO (2026-08-31)
# ---------------------------------------------------------------------------
# `draw()` y `draw_by_carta()` murieron por OOM en todas sus variantes (país-completo, por
# carta, con/sin tileScale alto) porque `stratifiedSample`/`reduceRegion` necesitan EXAMINAR
# los valores de la banda en toda la región pedida para poder armar el índice por clase o
# acumular un conteo — un costo que escala con el ÁREA de entrada, no con cuántos puntos se
# piden. Confirmado con evidencia directa: hasta pedirle una cuota chica a una sola carta (unos
# pocos puntos, de las 6.000 totales) seguía muriendo — no es el tamaño del pedido, es tener que
# buscar.
#
# `Image.sample()` (SIN classBand) es un primitivo distinto: elige N ubicaciones al azar sobre
# la GEOMETRÍA de la región (no mira el contenido de la imagen para elegir dónde), y recién
# después lee el valor en esas N ubicaciones. Su costo escala con N, no con el país — no importa
# si la clase que nos interesa está concentrada o dispersa en 11.000 parches (que es lo que
# medimos para S1 — ver el bloque "SORTEO POR CARTA" arriba).
#
# Mecánica: un sorteo grande y SIN estratificar (cualquier píxel del país, sin filtrar por
# `stratum`), y la separación por estrato se hace LOCAL, en pandas, después de bajar el CSV — no
# en GEE. Es estadísticamente idéntico a sortear dentro de cada estrato por separado (condicionar
# por estrato conmuta con el sorteo al azar), solo cambia el orden de las operaciones.
#
# DOS ETAPAS, no una sola tirada gigante (decisión del usuario, 2026-08-30): el pool 1 (este
# bloque) se dimensiona SOLO para cubrir con margen la muestra inicial de 100/estrato/año
# (docs/10 §1) — no las 5.000 congeladas del diseño completo. Si más adelante hace falta
# extender, un pool 2 independiente (más grande) se puede sumar sin re-sortear nada — dedup por
# (col,row) contra lo que el pool 1 ya usó, nunca tocar/resortear una lista ya congelada
# (§5 regla 6). El pool 2 no se implementa acá.
N_PILOT = 20_000       # prueba chica y barata: confirmar que sample() no revienta ANTES de
                       # comprometerse a nada más grande, y medir la prevalencia real por año
W_FLOOR = 10_000_000 / 3_103_000_000   # ≈ 0.0032 — piso documentado para S1 (docs/10 §5: "S1
                                        # tiene del orden de diez millones de píxeles en un año
                                        # típico" / ~3.1e9 píxeles totales del país)

# CAUSA REAL DEL OOM, encontrada 2026-08-31: no era `stratum` ni `stratifiedSample` vs `sample`
# — era la GEOMETRÍA de región. `FRAME_FC` (`ARG-Political_Level_1-Pais`) tiene más de 2 millones
# de bordes (el mismo límite político que ya hace fallar `.bounds()` en otros contextos de este
# proyecto — ver los gotchas globales de GEE). Cualquier operación que la reciba como `region=`
# paga ese costo, sin importar qué se esté sorteando. Prueba de control 2026-08-31: MISMO `sample()`,
# MISMAS bandas mínimas (`stratum`+`burned`+lon/lat), MISMO asset de estratos (que además está
# `.clip()`eado a este mismo límite complejo desde que se exportó, Apéndice A) — con `FRAME_FC`
# como región murió por OOM (5/5 intentos); con este rectángulo simple como región, ÉXITO al
# primer intento. Así que el límite complejo "horneado" en el asset no importa — lo que importa
# es la geometría que se pasa en el momento de la consulta. Rectángulo generoso, no preciso —
# los puntos que caen fuera de Argentina (Chile, Uruguay, océano, etc.) simplemente salen con
# `stratum` nulo y no cuentan para ningún estrato — `pilot_report()`/`size_full_draw()` ya miden
# la prevalencia REALIZADA, así que ese descarte queda contemplado sin tocar nada más.
ARG_BBOX_COORDS = [-74.0, -55.5, -53.0, -21.5]   # función, no constante ee.* a nivel de módulo
                                                   # -- ee.Geometry.* necesita initialize() ya
                                                   # corrido, y este módulo se importa antes de eso


def arg_bbox():
    return ee.Geometry.Rectangle(ARG_BBOX_COORDS, None, False)


def pool_image(fy):
    """`attrs_image(fy)` + lon/lat — mismas bandas que la mitad de atributos de `draw()`,
    reutilizada sin cambios."""
    return attrs_image(fy).addBands(ee.Image.pixelLonLat())


def _pool_sample(fy, n, seed=SEED):
    """SIN classBand — sortea ubicaciones sobre la geometría, no sobre el contenido (ver nota
    arriba). `dropNulls=False` a propósito: `mb_class_raw` puede tener nulos incidentales cerca
    de bordes/agua (no hay máscara explícita en `F.get_mb_class_band`, no se verificó); con
    `dropNulls=True` cualquier banda nula tira la FILA ENTERA, lo que encogería en silencio el
    marco muestral de "país entero" (docs §1) por una razón ajena al diseño. `stratum`/`burned`
    nunca son nulos (vienen del asset sin máscara), así que el chequeo obligatorio
    `burned == stratum==1` en `freeze_df()` no se ve afectado. `region=arg_bbox()`, NUNCA
    `ee.FeatureCollection(FRAME_FC).geometry()` — ver la nota arriba de `ARG_BBOX_COORDS`, es la
    causa real de todos los OOM de esta noche, no `stratum` ni `stratifiedSample` vs `sample`."""
    proj = ee.Projection(C.SNIC_CRS, C.SNIC_TRANSFORM)
    return pool_image(fy).sample(
        region=arg_bbox(), projection=proj, numPixels=n, seed=seed,
        dropNulls=False, tileScale=TILE_SCALE, geometries=False,
    ).sort("order_key")


def pilot_task_name(fy):
    return f"val10_pilot_fy{fy}"


def pilot_launch(fy, n_pilot=N_PILOT):
    description = pilot_task_name(fy)
    if task_in_flight(description):
        print(f"[skip] {description} tiene una tarea PENDING/RUNNING")
        return
    task = ee.batch.Export.table.toDrive(
        collection=_pool_sample(fy, n_pilot), description=description,
        folder=DRIVE_FOLDER, fileNamePrefix=description, fileFormat="CSV",
        selectors=SELECTORS,
    )
    task.start()
    print(f"[pilot-launch] {description} → Drive/{DRIVE_FOLDER}  (task {task.id})")


def pilot_report(fy, n_pilot=N_PILOT, csv_dir=None):
    """Lee el CSV del piloto ya bajado de Drive, reporta conteo/Ŵh por estrato con su error
    estándar — insumo directo de `size_full_draw()`."""
    csv_dir = Path(csv_dir) if csv_dir else RAW_DIR
    path = csv_dir / f"{pilot_task_name(fy)}.csv"
    if not path.exists():
        sys.exit(f"[error] no encontrado: {path}  (bajar de Drive/{DRIVE_FOLDER} primero)")
    df = pd.read_csv(path)
    n = len(df)
    print(f"[pilot-report] año-fuego {fy}: {n:,} filas (se pidieron {n_pilot:,})")
    counts = {}
    for h in STRATA:
        c = int((df["stratum"] == h).sum())
        counts[h] = c
        p = c / n
        se = (p * (1 - p) / n) ** 0.5
        print(f"          S{h}: {c:>7,}/{n:,}   Ŵ{h}={p:.5f}  SE={se:.5f} ({se / p:.1%} rel)"
              if p > 0 else f"          S{h}: {c:>7,}/{n:,}   Ŵ{h}=0 — ¡revisar!")
    return counts


def size_full_draw(counts_pilot, n_pilot, n_target, safety, w_floor=W_FLOOR):
    """`numPixels` para que incluso el estrato más raro supere `n_target*safety` en esperanza.
    Usa max(estimado del piloto, piso documentado) por estrato — protege contra un conteo de
    piloto demasiado chico para confiar (ruido de Poisson con pocos casos) o un año realmente
    más flaco que lo que le tocó al piloto."""
    w_hat = {h: max(counts_pilot[h] / n_pilot, w_floor) for h in STRATA}
    n_full = int(np.ceil(n_target * safety / min(w_hat.values())))
    return n_full, w_hat


def pool_task_name(fy):
    return f"val10_pool_fy{fy}"


def draw_pool(fy, n_full):
    return _pool_sample(fy, n_full)


def launch_pool(fy, n_full):
    description = pool_task_name(fy)
    if task_in_flight(description):
        print(f"[skip] {description} tiene una tarea PENDING/RUNNING")
        return
    task = ee.batch.Export.table.toDrive(
        collection=draw_pool(fy, n_full), description=description,
        folder=DRIVE_FOLDER, fileNamePrefix=description, fileFormat="CSV",
        selectors=SELECTORS,
    )
    task.start()
    print(f"[launch-pool] {description} (n={n_full:,}) → Drive/{DRIVE_FOLDER}  (task {task.id})")


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
def freeze_df(df, fy, h, out_dir=FROZEN_DIR, source_note="", min_rows=N_KEEP, out_prefix=None):
    """Cuerpo real de `freeze()` — separado para que `freeze_from_pool()` lo reuse sin duplicar
    nada. `min_rows` es el piso ACEPTABLE (falla si hay menos); lo que se guarda es
    `min(N_KEEP, filas disponibles)` — nunca más de N_KEEP=5.000 aunque haya de sobra (S2/S3
    del pool van a tener mucho más), nunca menos de `min_rows` o no llega a este punto."""
    out_prefix = out_prefix or task_name(fy, h)
    n = len(df)
    print(f"[freeze] {out_prefix}: {n:,} filas leídas (mínimo aceptable {min_rows:,})")
    if n < min_rows:
        sys.exit(f"[error] sólo {n:,} filas — menos que las {min_rows:,} necesarias. "
                  f"No truncar con esto, volver a lanzar el draw con un N mayor")

    # consistencia gratis (§4): burned tiene que ser exactamente (stratum == 1)
    bad = df.index[df["burned"] != (df["stratum"] == 1).astype(int)]
    if len(bad):
        sys.exit(f"[error] {len(bad)} filas violan burned == (stratum==1) — algo está mal "
                  f"con el asset de estratos o con este export, no seguir")

    # truncar a los primeros min(N_KEEP, n) por orden (§5 regla 2) — el CSV ya viene sorteado
    # por order_key porque el draw hace .sort('order_key') del lado del servidor
    keep = min(N_KEEP, n)
    df = df.iloc[:keep].reset_index(drop=True).copy()
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
    out_csv = out_dir / f"{out_prefix}_frozen.csv"
    df.to_csv(out_csv, index=False)

    meta = {
        "fire_year": fy, "stratum": h, "seed": SEED,
        "strata_asset": strata_asset(fy), "n_drawn": n, "n_frozen": len(df),
        "source_csv": source_note,
    }
    out_meta = out_dir / f"{out_prefix}_frozen.meta.json"
    out_meta.write_text(json.dumps(meta, indent=2))

    print(f"[freeze] escrito: {out_csv}  ({len(df):,} filas)")
    print(f"[freeze] metadata: {out_meta}")
    print("[freeze] Nh todavía no está en esta metadata — completar a mano desde "
          f"01_strata_export.py --weights --year {fy} (outputs/strata_weights_fy{fy}.csv)")
    return out_csv


def freeze(fy, h, csv_dir=RAW_DIR, out_dir=FROZEN_DIR):
    """Ruta original: un CSV YA por estrato (país-completo o por carta), sorteado con N_DRAW=6.000
    para garantizar >= N_KEEP=5.000 (§5 regla 2) — `min_rows` queda en el default N_KEEP."""
    src = Path(csv_dir) / f"{task_name(fy, h)}.csv"
    if not src.exists():
        sys.exit(f"[error] no encontrado: {src}  "
                  f"(bajar el export de Drive primero, con ese nombre, a {csv_dir})")
    df = pd.read_csv(src)
    return freeze_df(df, fy, h, out_dir, source_note=str(src))


def freeze_from_pool(fy, h, min_rows=100, csv_dir=RAW_DIR, out_dir=FROZEN_DIR):
    """Ruta del pool 1 (no estratificado): un único CSV por año con las 3 clases mezcladas —
    filtra a `stratum==h` ACÁ, local, antes de pasarle el resto a `freeze_df()` sin cambios.
    `min_rows=100` porque el pool 1 está dimensionado para la muestra inicial (docs §1), no para
    las 5.000 congeladas — ver `size_full_draw()`."""
    src = Path(csv_dir) / f"{pool_task_name(fy)}.csv"
    if not src.exists():
        sys.exit(f"[error] no encontrado: {src}  "
                  f"(bajar el export de Drive primero, con ese nombre, a {csv_dir})")
    df_all = pd.read_csv(src)
    df_h = df_all[df_all["stratum"] == h].reset_index(drop=True)
    return freeze_df(df_h, fy, h, out_dir, source_note=f"{src} (stratum={h} subset, pool 1)",
                      min_rows=min_rows, out_prefix=task_name(fy, h))


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
    ap.add_argument("--launch", action="store_true",
                    help="lanzar los draws en GEE (país-completo — murió por OOM, ver "
                         "--weights-by-carta-launch / --launch-by-carta)")
    ap.add_argument("--weights-by-carta-launch", action="store_true",
                    help="Nh por carta → Drive, insumo de --launch-by-carta (país-completo "
                         "murió por OOM en fy2003, ver nota arriba de cartas_in_frame())")
    ap.add_argument("--launch-by-carta", action="store_true",
                    help="lanzar los draws particionados por carta — lee los 3 CSV de "
                         "--weights-by-carta-launch (uno por estrato) ya bajados de Drive")
    ap.add_argument("--pilot-launch", action="store_true",
                    help=f"pool SIN estratificar, chico ({N_PILOT:,} pts) — confirma que "
                         "sample() no revienta y mide Ŵh real antes de --launch-pool")
    ap.add_argument("--pilot-report", action="store_true",
                    help="leer el CSV de --pilot-launch ya bajado, reportar Ŵh por estrato")
    ap.add_argument("--launch-pool", type=int, metavar="N",
                    help="pool 1 SIN estratificar, tamaño N (de size_full_draw() sobre el "
                         "piloto) — reemplaza --launch/--launch-by-carta, que murieron por OOM")
    ap.add_argument("--freeze", action="store_true",
                    help="post-procesar localmente un CSV ya bajado de Drive")
    ap.add_argument("--from-pool", action="store_true",
                    help="con --freeze: leer del CSV de --launch-pool (una sola tirada, las 3 "
                         "clases mezcladas) en vez del CSV ya-por-estrato de --launch/--launch-by-carta")
    ap.add_argument("--min-rows", type=int, default=100,
                    help="con --freeze --from-pool: piso aceptable de filas (default 100, la "
                         "muestra inicial — el pool 1 no está dimensionado para las 5.000)")
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
                if args.from_pool:
                    freeze_from_pool(fy, h, args.min_rows, args.csv_dir, args.out_dir)
                else:
                    freeze(fy, h, args.csv_dir, args.out_dir)
        return
    if args.pilot_report:
        for fy in years:
            pilot_report(fy, csv_dir=args.csv_dir)
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
    if args.weights_by_carta_launch:
        for fy in years:
            weights_by_carta_launch(fy)
        return
    if args.launch_by_carta:
        for fy in years:
            quotas = compute_quotas(fy, args.csv_dir)
            launch_by_carta(fy, quotas)
        return
    if args.pilot_launch:
        for fy in years:
            pilot_launch(fy)
        return
    if args.launch_pool is not None:
        for fy in years:
            launch_pool(fy, args.launch_pool)
        return
    ap.error("elegir uno: --check, --launch, --weights-by-carta-launch, --launch-by-carta, "
             "--pilot-launch, --pilot-report, --launch-pool o --freeze")


if __name__ == "__main__":
    main()
