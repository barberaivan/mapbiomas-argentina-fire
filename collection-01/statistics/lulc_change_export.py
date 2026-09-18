#!/usr/bin/env python
"""
collection-01/statistics/lulc_change_export.py — QUÉ HABÍA ANTES Y QUÉ QUEDÓ DESPUÉS
(el análisis 6 del factsheet; statistics/docs/statistics.md §5.7, statistics/docs/factsheet-sep2026-spec.md §6)

La tercera —y última— reducción propia en Earth Engine.  `burnable_export.py` da el
denominador del "% de lo quemable que se quemó"; `lulc_area_export.py`, el del "% del
bosque que se quemó"; ésta responde otra pregunta, que no es un porcentaje de nada
preexistente: **de lo que se quemó, ¿qué cobertura tenía antes y cuál tiene después?**

DE DÓNDE VIENE EL DISEÑO
    De **Ferro et al. (2026)**, "Why are you burning? The interplay between land cover,
    climatic variability and fire activity in the dry forests of Argentina", Int. J.
    Wildland Fire 35: WF25126 — el trabajo del propio grupo sobre el Chaco Seco.  Esta
    exportación es, a grandes rasgos, su análisis de transiciones mediado por fuego, con
    tres diferencias: nuestro mapa de fuego a 30 m en vez de MCD64A1 a 500 m, todo el país
    en vez del Chaco Seco, y CONTABILIDAD DE SUPERFICIE exhaustiva en vez de un GLM
    multinomial sobre puntos muestreados (ellos sacan probabilidades con intervalos; acá
    salen hectáreas, sin incertidumbre).  Lo que sí se copia literal son las dos decisiones
    que definen el análisis: la ventana Y-1 -> Y+1 y la regla de exclusión (abajo).

QUÉ COMPUTA
    Para cada año calendario Y, el área del país cruzada por

        code = state * 1000000 + eco13 * 10000 + col3(Y-1) * 100 + col3(Y+offset)

    es decir la tabla completa área x estado de fuego x ecorregión x clase ANTES x clase
    DESPUÉS, anual.  Un solo entero, un solo `groupField`, una sola barrida — la misma
    estrategia de programación que copiamos de la app de la red (statistics/docs/statistics.md §2.1).

    ⚠️ El empaquetado NO entra en uint16 (tope 3*1000000+137777 = 3137777): la banda es
    int32.  Copiar el `toUint16()` de `lulc_area_export.py` desbordaría en silencio y las
    clases decodificarían mal — por eso `legends.decode_lulc_change` valida todo.

EL CONTROL, Y POR QUÉ LA TABLA CUBRE TODO EL PAÍS Y NO SÓLO LO QUEMADO
    "El 15 % de lo quemado cambió de cobertura" no significa nada sin saber cuánto cambia la
    cobertura CUANDO NO HAY FUEGO.  Por eso los cuatro estados de `legends.FIRE_STATE_NAMES`
    y por eso la reducción ya no se enmascara con el fuego: barre el país entero y el estado
    es una dimensión más del código.

    No cuesta casi nada.  Lo caro es LEER tres bandas de 30 m sobre 279 Mha, y eso se hacía
    igual con la máscara puesta —`reduceRegion` no lee menos por estar enmascarado—; lo único
    que crece es el número de grupos, que es memoria del reductor y filas del CSV.

    LA REGLA DE EXCLUSIÓN (Ferro et al. 2026, "Data analysis"): se usan sólo píxeles que no
    ardieron en el año anterior ni en el siguiente, para evitar errores de clasificación de
    la cobertura — que es exactamente el artefacto de la cicatriz.  Acá se aplica a LOS DOS
    grupos (estados 1 y 0), y los dos contaminados quedan como estados propios (3 y 2) en vez
    de desaparecer: la tabla los trae y R informa cuánta superficie son.

    EL NÚMERO QUE SALE DE ESTO es el cociente de Ferro:

        q = P(transición | ardió) / P(transición | no ardió)

    q > 1, el fuego promueve esa transición; q < 1, la limita.  En el Chaco Seco a 500 m les
    dio q = 12,96 para bosque -> agricultura y q = 0,79 para bosque que sigue siendo bosque.

LA VENTANA: `--offset 1` (por defecto) Y `--offset 3`
    `offset` es cuántos años después del fuego se mira la cobertura.  1 es el de Ferro et al.
    3 existe para separar lo transitorio de lo permanente: si una transición de Y+1 volvió a
    su clase en Y+3, era la cicatriz; si sigue, fue conversión.  Con offset 3 la ventana de
    exclusión es [Y-1, Y+3] — cinco años sin otro fuego —, que es MUCHO más exigente y deja
    bastante menos superficie en los estados limpios.  Es el precio de la pregunta.

POR QUÉ Y-1 Y NO Y
    Porque no se sabe si la cobertura del año del fuego es la de antes o la de después
    (Ferro et al. 2026).  Y-1 es además, exactamente, la que el numerador de la red le
    adjudica a la hectárea quemada (`annual_burned_coverage` cruza con
    `classification_<Y-1>`, statistics/docs/statistics.md §2.2): la columna "antes" de esta tabla tiene que
    reproducir el análisis 4 clase por clase, y la compuerta lo verifica.
    Y+offset es la cobertura DESPUÉS.  Eso acota la serie por arriba: la col-3 llega a 2025,
    así que con offset 1 el último año es 2024 (26 años) y con offset 3, 2022 (24 años).

LO QUE ESTE ANÁLISIS **NO** DICE (escribirlo en el epígrafe, no en una nota al pie)
    Que una hectárea figure como "bosque -> herbáceas" no prueba que el fuego causó el
    cambio: (a) la col-3 puede estar reaccionando a la cicatriz misma, y un bosque quemado
    clasificado como herbáceas en Y+1 puede volver a bosque en Y+3; (b) un año es una
    ventana corta para la recuperación; (c) el mismo píxel pudo cambiar por desmonte en
    Y+1 sin relación con el fuego.  Es una DESCRIPCIÓN de qué coberturas se suceden
    alrededor del fuego, no una atribución causal.

LA GRILLA, Y LA TRAMPA QUE TRAE (medido 17 sep 2026)
    `annual_burned_v2` está en EPSG:3857 y la col-3 en la retícula SNIC (4326).  Cruzarlas
    obliga a remuestrear UNA de las dos, y se elige remuestrear la del FUEGO: la reducción
    corre en `C.SNIC_CRS` + `C.SNIC_TRANSFORM`, que es la retícula nativa de la cobertura
    —la capa categórica, donde un corrimiento de medio píxel cambia la clase— y la misma
    sobre la que ya está calculado el denominador de `lulc_area_export.py`.  La máscara de
    fuego es binaria: el vecino más cercano le cuesta una fracción de por mil del total, y
    la compuerta mide cuánto exactamente contra la tabla publicada.

MASCARAS: exactamente DOS capas mandan
    la ecorregión (que teselan el país) y el fuego del año.  Las dos bandas de cobertura van
    `unmask(0)`eadas, así que un píxel que la colección no mapea sale como "No observado"
    VISIBLE y no se evapora de la tabla inflando todos los porcentajes.

USO (desde la RAÍZ del repo), en el orden en que se corre
    --test-rect   el mismo rectángulo de Córdoba que usan los otros dos. Segundos.
    --export      la corrida nacional como UNA tarea batch -> Drive C.STATS_DRIVE_FOLDER.
    --export --split   26 tareas, una por año.  Si la única resulta muy lenta.
    --status      estado de la(s) tarea(s).
    --fetch       baja de Drive a data/statistics/, decodifica y corre la compuerta.
    --check       re-corre la compuerta sobre el CSV crudo ya bajado (sin red).
`--credentials ~/.config/earthengine/credentials.comahue --project mapbiomas-argentina`
corre como la segunda cuenta (la cola de tareas es por usuario).
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "collection-01"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ee  # noqa: E402

import legends  # noqa: E402
from utils import constants as C  # noqa: E402
from lulc_area_export import drive_client, initialize  # noqa: E402

OUT_DIR = REPO_ROOT / "collection-01" / "data" / "statistics"

# La tabla contra la que cierra la compuerta: el área quemada por año y ecorregión que
# publica el toolkit de la red (statistics/docs/statistics.md §2).
TOOLKIT_CSV = OUT_DIR / "annual_burned_Ecorregiones.csv"

# El fuego cubre 1999-2025 y la col-3 llega a 2025: `FIRST_YEAR` es el primer año con
# cobertura ANTES (1998 existe) y el último con DESPUÉS depende del offset.
FIRST_YEAR = 1999
FIRE_FIRST_YEAR, FIRE_LAST_YEAR = 1999, 2025      # la ventana del producto annual_burned
LULC_LAST_YEAR = 2025

TEST_RECT = [-63.90, -31.55, -63.70, -31.35]      # el mismo recuadro de Córdoba
TASK_PREFIX = "arg09_lulc_change_eco13"
TOLERANCE_PCT = 2.0                                # ver `check()`


def years_for(offset: int, window: int | None = None) -> list:
    """Los años focales.  El tope lo pone el MAYOR de los dos: la cobertura "después" tiene
    que existir (Y+offset <= 2025) y la ventana de exclusión tiene que caber (Y+window)."""
    return list(range(FIRST_YEAR, LULC_LAST_YEAR - max(offset, window or offset) + 1))


def suffix(args) -> str:
    """`_y1`, `_y3_n44`, `_y1_w5_n44`: el lag, la ventana de exclusión si NO coincide con el
    lag, y el corte latitudinal si lo hubo.  Los tres van en el NOMBRE porque los tres
    cambian qué población describe el archivo, no sólo sus números."""
    lat = getattr(args, "lat_split", None)
    win = getattr(args, "window", None) or args.offset
    return (f"_y{args.offset}"
            + (f"_w{win}" if win != args.offset else "")
            + (f"_n{abs(int(lat))}" if lat else ""))


def raw_csv(args) -> Path:
    return OUT_DIR / f"lulc_change_eco13{suffix(args)}_raw.csv"    # como lo dio GEE


def tidy_csv(args) -> Path:
    return OUT_DIR / f"lulc_change_eco13{suffix(args)}.csv"        # decodificado


# ---------------------------------------------------------------------------
# la imagen
# ---------------------------------------------------------------------------
def eco_image() -> ee.Image:
    """`GEOCODE` pintado desde el VECTOR — una de las dos capas que manda sobre la máscara."""
    return ee.Image().paint(ee.FeatureCollection(C.ECOREGIONS13), C.ECOREGION_ID_PROPERTY)


def burned(year: int) -> ee.Image:
    """El fuego de UN año calendario: `annual_burned_v2`, banda 1-o-enmascarada -> 0/1.

    La banda se RENOMBRA: `ee.ImageCollection` exige colección homogénea y las bandas del
    producto son `burned_area_<año>`, así que sin esto el `max()` de la ventana falla con
    "Expected a homogeneous image collection".
    """
    return (ee.Image(f"{C.FINAL_PRODUCTS}/{C.product_name('annual_burned')}")
            .select(f"burned_area_{year}")
            .unmask(0)
            .rename("burned"))


def fire_state(year: int, window: int) -> ee.Image:
    """Los cuatro estados de `legends.FIRE_STATE_NAMES`, como banda 0/1/2/3.

    La ventana de exclusión es [Y-1, Y+window] RECORTADA a los años que el producto tiene
    (1999-2025).  Para Y = 1999 no hay 1998 y la ventana empieza en 1999: el control de ese
    año es por lo tanto un poco más laxo que el de los demás, y se dice acá en vez de
    fabricar un año de fuego que no existe.
    """
    lo = max(year - 1, FIRE_FIRST_YEAR)
    hi = min(year + window, FIRE_LAST_YEAR)
    others = [y for y in range(lo, hi + 1) if y != year]
    yr = burned(year)
    win = ee.ImageCollection([burned(y) for y in others]).max()
    # y=1,w=0 -> 1 (tratamiento limpio)   y=1,w=1 -> 3 (tratamiento sucio)
    # y=0,w=0 -> 0 (control)              y=0,w=1 -> 2 (control sucio)
    return yr.expression("y > 0 ? (w > 0 ? 3 : 1) : (w > 0 ? 2 : 0)",
                         {"y": yr, "w": win})


def code_image(year: int, offset: int, lat_split: float | None = None,
               window: int | None = None) -> ee.Image:
    """`[north * 1e7 +] state * 1e6 + eco * 1e4 + clase(Y-1) * 100 + clase(Y+offset)`, int32,
    TODO el país.

    La única capa que manda sobre la máscara es la ecorregión (que tesela el país): acá ya no
    hay máscara de fuego — el fuego es una dimensión del código, que es lo que hace posible
    el control (ver la cabecera).

    `lat_split` agrega una dimensión más: 1 al norte del paralelo, 0 al sur.  Sirve para
    partir una ecorregión que no es homogénea sin inventar una ecorregión nueva — el caso es
    Bosques Patagónicos, donde el norte (Chubut arriba) tiene un régimen de fuego distinto
    del sur (statistics/docs/statistics.md §5.7.3).
    """
    lulc = ee.Image(C.PRODUCT_LULC)
    prev = lulc.select(f"classification_{year - 1}").unmask(0)
    post = lulc.select(f"classification_{year + offset}").unmask(0)
    code = (fire_state(year, window or offset).multiply(legends.CHANGE_STATE_BASE)
            .add(eco_image().multiply(legends.CHANGE_CODE_BASE))
            .add(prev.multiply(100))
            .add(post))
    if lat_split is not None:
        north = ee.Image.pixelLonLat().select("latitude").gt(lat_split)
        code = code.add(north.multiply(legends.CHANGE_NORTH_BASE))
    return code.toInt32().rename("code")


def grouped_area(year: int, offset: int, geometry: ee.Geometry,
                 lat_split: float | None = None,
                 window: int | None = None) -> ee.Dictionary:
    return (
        ee.Image.pixelArea().divide(1e4)                       # m2 -> ha
        .addBands(code_image(year, offset, lat_split, window))
        .reduceRegion(
            reducer=ee.Reducer.sum().group(groupField=1, groupName="code"),
            geometry=geometry,
            crs=C.SNIC_CRS,                                    # la retícula de la COBERTURA
            crsTransform=C.SNIC_TRANSFORM,
            maxPixels=1e12,
        )
    )


def year_features(year: int, offset: int, geometry: ee.Geometry,
                  lat_split: float | None = None, window: int | None = None) -> ee.List:
    """Una feature por código, llevando el año — así todos los años comparten una tarea."""
    groups = ee.List(grouped_area(year, offset, geometry, lat_split, window).get("groups"))
    return groups.map(lambda d: ee.Feature(None, ee.Dictionary(d).set("year", year)))


def national_bounds() -> ee.Geometry:
    return ee.FeatureCollection(C.ARG_BUFFER_FC).geometry().bounds()


def rows_from(groups, year: int) -> list[dict]:
    out = []
    for g in groups:
        (north, state, state_name, eco, eco_name,
         prev, post) = legends.decode_lulc_change(g["code"])
        out.append({
            "year": year,
            "code": int(g["code"]),
            "north": north,
            "state_id": state,
            "state": state_name,
            "ecoregion_id": eco,
            "ecoregion": eco_name,
            "class_prev": prev,
            "class_post": post,
            "nivel1_prev": legends.LULC_NIVEL_1[prev],
            "nivel1_post": legends.LULC_NIVEL_1[post],
            "nivel2_prev": legends.LULC_NIVEL_2[prev],
            "nivel2_post": legends.LULC_NIVEL_2[post],
            "area_ha": float(g["sum"]),
        })
    return out


# ---------------------------------------------------------------------------
# el test del rectángulo
# ---------------------------------------------------------------------------
def check_rect(args) -> int:
    """El recuadro de Córdoba, con LOS CUATRO ESTADOS a la vista.

    Lo que verifica: que el empaquetado decodifique (`rows_from` levanta excepción con una
    clase, una ecorregión o un estado inválidos), que el área reportada cubra el rectángulo
    entero —ahora la reducción es espacialmente completa, así que ESO se puede exigir— y que
    haya fuego en algún año.
    """
    w, s, e, n = TEST_RECT
    rect = ee.Geometry.Rectangle([w, s, e, n], proj="EPSG:4326", geodesic=False)
    rect_ha = rect.area(maxError=1).divide(1e4).getInfo()
    print(f"\ntest rectangle  {w},{s} .. {e},{n}   (Córdoba: chaco seco / espinal)")
    print(f"  area del rectángulo: {rect_ha:,.1f} ha   |   offset Y+{args.offset}")
    ok, burnt = True, False
    for year in (FIRST_YEAR, years_for(args.offset, args.window)[-1]):
        t0 = time.time()
        rows = rows_from(
            ee.List(grouped_area(year, args.offset, rect, args.lat_split,
                                 args.window).get("groups")).getInfo(), year)
        total = sum(r["area_ha"] for r in rows)
        print(f"\n  {year}   {len(rows)} combinaciones   {time.time() - t0:.1f} s   "
              f"{total:,.1f} ha   ({100 * total / rect_ha:.2f} % del recuadro)")
        for st in sorted(legends.FIRE_STATE_NAMES):
            sub = [r for r in rows if r["state_id"] == st]
            a = sum(r["area_ha"] for r in sub)
            chg = sum(r["area_ha"] for r in sub if r["nivel1_prev"] != r["nivel1_post"])
            print(f"    {st} {legends.FIRE_STATE_NAMES[st]:<14} {a:>11,.1f} ha"
                  + (f"   cambió nivel 1: {100 * chg / a:5.1f} %" if a else ""))
        burnt |= any(r["state_id"] in (1, 3) for r in rows)
        ok &= 99.0 <= 100 * total / rect_ha <= 101.0
    ok &= burnt
    print(f"\n  VERDICT: {'PASS' if ok else 'LOOK AT THIS'}")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# la exportación nacional
# ---------------------------------------------------------------------------
def desc_for(args, year: int | None = None) -> str:
    ys = years_for(args.offset, getattr(args, "window", None))
    return (f"{TASK_PREFIX}{suffix(args)}_{ys[0]}_{ys[-1]}" if year is None
            else f"{TASK_PREFIX}{suffix(args)}_{year}")


def launch(fc: ee.FeatureCollection, desc: str, dry: bool) -> None:
    task = ee.batch.Export.table.toDrive(
        collection=fc,
        description=desc,                    # namespaced: el proyecto de cómputo es COMPARTIDO
        folder=C.STATS_DRIVE_FOLDER,
        fileNamePrefix=desc,
        fileFormat="CSV",
        selectors=["year", "code", "sum"],   # las columnas, pineadas
    )
    if dry:
        print(f"[dry] would export Drive:{C.STATS_DRIVE_FOLDER}/{desc}.csv")
        return
    task.start()
    print(f"[launched] {task.id}  ->  Drive:{C.STATS_DRIVE_FOLDER}/{desc}.csv")


def export(args) -> int:
    bounds = national_bounds()
    years = years_for(args.offset, args.window)
    lat, win = args.lat_split, args.window
    if args.split:
        for y in years:
            launch(ee.FeatureCollection(year_features(y, args.offset, bounds, lat, win)),
                   desc_for(args, y), args.dry_run)
        return 0
    fc = ee.FeatureCollection(
        ee.List([year_features(y, args.offset, bounds, lat, win) for y in years]).flatten())
    launch(fc, desc_for(args), args.dry_run)
    return 0


def status(args) -> int:
    found = 0
    for op in ee.data.listOperations():
        md = op.get("metadata", {})
        if f"{TASK_PREFIX}{suffix(args)}" in md.get("description", ""):
            found += 1
            print(f"{md.get('description')}  {md.get('state')}  "
                  f"{md.get('startTime', '')}  {md.get('updateTime', '')}")
    if not found:
        print(f"no operations matching {TASK_PREFIX}* in this compute project")
    return 0


# ---------------------------------------------------------------------------
# fetch, decode, compuerta
# ---------------------------------------------------------------------------
def fetch(args) -> int:
    drive = drive_client(args)
    names = ([desc_for(args)] if not args.split
             else [desc_for(args, y) for y in years_for(args.offset, args.window)])
    blobs = []
    for name in names:
        q = f"name = '{name}.csv' and trashed = false"
        files = drive.files().list(q=q, fields="files(id,name,modifiedTime,size)",
                                   orderBy="modifiedTime desc").execute().get("files", [])
        if not files:
            raise SystemExit(f"{name}.csv no está en Drive todavía — mirá --status")
        f0 = files[0]
        print(f"[drive] {f0['name']}  {f0.get('size')} B  {f0.get('modifiedTime')}")
        blobs.append(drive.files().get_media(fileId=f0["id"]).execute().decode("utf-8"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = raw_csv(args)
    if len(blobs) == 1:
        raw.write_text(blobs[0], encoding="utf-8")
    else:
        head = blobs[0].splitlines()[0]
        body = [ln for b in blobs for ln in b.splitlines()[1:] if ln.strip()]
        raw.write_text("\n".join([head] + body) + "\n", encoding="utf-8")
    print(f"wrote {raw.relative_to(REPO_ROOT)}")
    return check(args)


def read_raw_csv(args) -> list[dict]:
    raw = raw_csv(args)
    if not raw.exists():
        raise SystemExit(f"{raw} no existe — corré --export y después --fetch")
    rows = []
    with raw.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            val = r["sum"] if "sum" in r else r["area_ha"]
            rows.extend(rows_from([{"code": int(r["code"]), "sum": float(val)}],
                                  int(r["year"])))
    return rows


def write_tidy(rows: list[dict], args) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cols = ["year", "north", "state_id", "state", "ecoregion_id", "ecoregion",
            "class_prev", "class_post",
            "nivel1_prev", "nivel1_post", "nivel2_prev", "nivel2_post", "area_ha"]
    if args.lat_split is None:
        cols.remove("north")        # sin corte la columna sería 0 en todas las filas
    rows = sorted(rows, key=lambda r: (r["year"], r["north"], r["state_id"],
                                       r["ecoregion_id"], r["class_prev"], r["class_post"]))
    out = tidy_csv(args)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out.relative_to(REPO_ROOT)}  ({len(rows):,} filas)")


def check(args) -> int:
    """DOS compuertas y un informe.

    1. EL ÁREA QUEMADA (estados 1 + 3, "ardió en Y") contra la que publica el toolkit de la
       red, AÑO POR AÑO y no sólo en total: un off-by-one en `classification_<Y±1>` no mueve
       el total, mueve un año.  Es además la medida de lo que cuesta la trampa de la
       retícula (cabecera).
    2. LA COBERTURA ESPACIAL: ahora la reducción barre el país entero, así que la suma de
       TODOS los estados tiene que dar el área del país.  Si no da, la máscara de ecorregión
       está perdiendo píxeles y el CONTROL —que es casi todo el país— estaría sesgado sin que
       la compuerta 1, que sólo mira lo quemado, se entere.

    Y el informe: cuánta superficie cae en cada estado, y el cociente q de Ferro et al. para
    "cambió de clase", que es el número que el análisis existe para producir.
    """
    rows = read_raw_csv(args)
    write_tidy(rows, args)
    years = years_for(args.offset, getattr(args, "window", None))

    # --- 1. el área quemada contra el toolkit ---------------------------------
    mine = defaultdict(float)
    for r in rows:
        if r["state_id"] in (1, 3):
            mine[r["year"]] += r["area_ha"]

    ok = True
    if not TOOLKIT_CSV.exists():
        print(f"[.] {TOOLKIT_CSV.name} no está — sin compuerta 1")
    else:
        theirs = defaultdict(float)
        with TOOLKIT_CSV.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                y = int(r["Ano"])
                if years[0] <= y <= years[-1]:
                    theirs[y] += float(r["Área ha"])
        print(f"\n  ÁREA QUEMADA (estados 1+3) vs. el toolkit")
        print(f"  {'año':>6} {'esta tabla':>14} {'toolkit':>14} {'dif':>8}")
        worst, worst_y = 0.0, None
        for y in years:
            a, b = mine.get(y, 0.0), theirs.get(y, 0.0)
            d = 100 * (a - b) / b if b else float("nan")
            print(f"  {y:>6} {a:>14,.0f} {b:>14,.0f} {d:>7.2f} %")
            if abs(d) > worst:
                worst, worst_y = abs(d), y
        ta, tb = sum(mine.values()), sum(theirs.values())
        print(f"  {'TOTAL':>6} {ta:>14,.0f} {tb:>14,.0f} {100 * (ta - tb) / tb:>7.2f} %")
        print(f"  peor año: {worst_y} ({worst:.2f} %)   tolerancia {TOLERANCE_PCT:.1f} %")
        ok &= worst < TOLERANCE_PCT

    # --- 2. la cobertura espacial --------------------------------------------
    # El país, de la MISMA fuente que el denominador del factsheet: la suma de las áreas de
    # las 13 ecorregiones (statistics/docs/statistics.md §3).  Cada año tiene que dar eso, porque cada píxel del
    # país cae en exactamente un estado.
    per_year = defaultdict(float)
    for r in rows:
        per_year[r["year"]] += r["area_ha"]
    country = max(per_year.values())
    spread = 100 * (max(per_year.values()) - min(per_year.values())) / country
    print(f"\n  COBERTURA: {country / 1e6:.2f} Mha por año, dispersión entre años {spread:.4f} %")
    print("  (cada píxel del país cae en exactamente un estado, así que los años deben coincidir)")
    ok &= spread < 0.01

    # --- el informe: los estados y el cociente q ------------------------------
    print(f"\n  LOS CUATRO ESTADOS (suma de {len(years)} años, offset Y+{args.offset})")
    tot = sum(r["area_ha"] for r in rows)
    q = {}
    for st in sorted(legends.FIRE_STATE_NAMES):
        sub = [r for r in rows if r["state_id"] == st]
        a = sum(r["area_ha"] for r in sub)
        if not a:
            continue
        for lvl in ("nivel1", "nivel2"):
            chg = sum(r["area_ha"] for r in sub
                      if r[f"{lvl}_prev"] != r[f"{lvl}_post"])
            q[(st, lvl)] = 100 * chg / a
        print(f"    {st} {legends.FIRE_STATE_NAMES[st]:<14} {a / 1e6:>9.2f} Mha "
              f"({100 * a / tot:>5.2f} %)   cambió: n1 {q[(st, 'nivel1')]:5.2f} %  "
              f"n2 {q[(st, 'nivel2')]:5.2f} %")
    if (1, "nivel1") in q and (0, "nivel1") in q:
        print("\n  EL COCIENTE DE FERRO — P(cambió | ardió) / P(cambió | no ardió),")
        print("  tratamiento = estado 1, control = estado 0 (los dos limpios):")
        for lvl in ("nivel1", "nivel2"):
            print(f"    {lvl}:  {q[(1, lvl)]:.2f} % / {q[(0, lvl)]:.2f} % = "
                  f"q = {q[(1, lvl)] / q[(0, lvl)]:.2f}")

    print("\n  VERDICT: " + ("PASS" if ok else "LOOK AT THIS"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test-rect", action="store_true", help="el recuadro de Córdoba")
    ap.add_argument("--offset", type=int, default=1, choices=(1, 2, 3, 4, 5),
                    help="años después del fuego para la cobertura DESPUÉS (1 = Ferro et al.)")
    ap.add_argument("--window", type=int, default=None, choices=(1, 2, 3, 4, 5),
                    help="años de la VENTANA DE EXCLUSIÓN, si no es igual a --offset. "
                         "Fijarla para todos los lags da la MISMA cohorte de píxeles y de "
                         "años focales, que es la única forma de leer Y+1..Y+5 como una "
                         "trayectoria y no como cuatro poblaciones distintas (statistics/docs/statistics.md §5.7.2)")
    ap.add_argument("--lat-split", type=float, default=None, metavar="LAT",
                    help="parte cada ecorregión en norte/sur de ese paralelo (ej. -44), "
                         "como dimensión extra del código (statistics/docs/statistics.md §5.7.3)")
    ap.add_argument("--export", action="store_true", help="la corrida nacional")
    ap.add_argument("--split", action="store_true", help="una tarea por año")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--check", action="store_true", help="sólo la compuerta, sin red")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--credentials")
    ap.add_argument("--project", default=C.GEE_PROJECT)
    args = ap.parse_args()

    if args.check:
        return check(args)
    initialize(args.project, args.credentials)
    if args.test_rect:
        return check_rect(args)
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
