#!/usr/bin/env python3
"""
collection-01/validation/03_ceo_export.py

Paso 3 de la validación — LA MUESTRA INICIAL, en el formato de "custom plot" que exige
Collect Earth Online (CEO): columnas `LON`, `LAT`, `PLOTID`, `PLOTID` único, y cualquier
columna extra DESPUÉS de esas tres. No está en `docs/10-validation.md` (el spec llega hasta la
lista congelada, §5) — este paso lo agrega para que esa lista se pueda subir a CEO sin fricción.

100% LOCAL — no toca GEE. Corre después de que `02_sample_pool.py --freeze` ya dejó las listas
congeladas en `outputs/frozen/`.

QUÉ HACE
--------
Por año-fuego: toma las primeras 100 filas (`frozen_rank < 100`) de cada una de las 3 listas
congeladas — la "muestra inicial" de 100/estrato/año que fija docs/10 §1 — las junta (300 filas),
las baraja con una semilla propia y fija (`CEO_SHUFFLE_SEED`, distinta de la que usa el sorteo en
GEE), y numera `PLOTID` 1..300 según ese orden ya barajado.

Barajar es necesario porque docs/10 §7 exige que los lotes mezclen estratos y años — un lote de
100 filas seguidas, todas estrato 1, le delata al intérprete que ese tramo es "quemado por
construcción" y rompe el blind labelling.

`LON`/`LAT` YA SON EL CENTRO EXACTO DEL PÍXEL — no algo que arme este paso
------------------------------------------------------------------------------
`02_sample_pool.py::draw()` pasa `projection=ee.Projection(C.SNIC_CRS, C.SNIC_TRANSFORM)` a
`stratifiedSample` (nunca `scale`), así que `lon`/`lat` en la lista congelada ya son el centro de
píxel exacto de la grilla del producto. Este paso sólo los renombra a mayúscula y los preserva —
no los recalcula. El shape/size del plot en CEO (cuadrado de 30 m, para que la unidad mostrada al
intérprete sea el píxel y no un punto) se configura al crear el proyecto en CEO, fuera del alcance
de este CSV.

DOS ARCHIVOS DE SALIDA, NO UNO — corregido 2026-08-25
--------------------------------------------------------
La primera versión de este paso subía `stratum`/`burned` en el mismo CSV que se sube a CEO,
razonando que CEO no las muestra al intérprete (no se encontró ningún camino de UI que lo haga,
grepeando `openforis/collect-earth-online`). Pero la nota de diseño de Iván en el repo `fuego`
(`collection-01/validacion/CLAUDE.md`, §"Higiene de CEO") es más estricta y ya documenta un
precedente real: **"En v1 el CSV exponía `stratum` y `burned_frac` — error real."** — la regla no
es "que CEO no la muestre", es "que la columna no exista en lo que se sube". Así que ahora:

  1. `ceo_upload_fy<FY>.csv`  → **SOLO** `LON, LAT, PLOTID`. Esto y nada más se sube a CEO.
  2. `ceo_crosswalk_fy<FY>.csv` → la tabla llave completa (`PLOTID` + todo lo demás: `stratum`,
     `burned`, `mb_class_raw`, `region_id`, `frozen_rank`, `col`, `row`), **queda local, nunca se
     sube a ningún lado** — ni a CEO ni como asset de GEE. Sirve para reunir la etiqueta del
     intérprete con la respuesta del mapa después de la interpretación, uniendo por `PLOTID`
     (único dentro de cada año — el join siempre es por año-fuego).

El mismo `ceo_upload_fy<FY>.csv` es también la fuente del lookup por PLOTID del inspector GEE
(plantilla `ceo_val_template`, cada validador corre su propia copia `ceo_val_<NOMBRE>`) — al no
llevar `stratum`/`burned`, subirlo como asset de tabla para ese lookup no reabre el mismo agujero.

USO
---
    $PYTHON collection-01/validation/03_ceo_export.py --check   --year 2022
    $PYTHON collection-01/validation/03_ceo_export.py --export  --year 2022
    $PYTHON collection-01/validation/03_ceo_export.py --export  --all-years
"""
from __future__ import annotations

import argparse
import json
import sys
from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
_s1 = import_module("01_strata_export")
_s2 = import_module("02_sample_pool")
FIRE_YEARS = _s1.FIRE_YEARS
FROZEN_DIR = _s2.FROZEN_DIR
STRATA = _s2.STRATA
task_name = _s2.task_name

# ---------------------------------------------------------------------------
N_INITIAL = 100          # por estrato, por año (docs/10 §1 — "muestra inicial")
CEO_SHUFFLE_SEED = 43    # fija y se registra para siempre — distinta de SEED=42 del sorteo en GEE

# lo único que sube a CEO (y lo único que sube como asset de puntos para el inspector)
CEO_UPLOAD_COLUMNS = ["LON", "LAT", "PLOTID"]
# tabla llave completa — SOLO local, nunca se sube a ningún lado
CROSSWALK_COLUMNS = ["PLOTID", "LON", "LAT", "fire_year", "stratum", "burned",
                      "mb_class_raw", "region_id", "frozen_rank", "col", "row"]

OUT_DIR = Path(__file__).resolve().parent / "outputs" / "ceo"


# ---------------------------------------------------------------------------
def load_stratum(fy, h):
    src = FROZEN_DIR / f"{task_name(fy, h)}_frozen.csv"
    if not src.exists():
        sys.exit(f"[error] no encontrado: {src}  "
                 f"(correr 02_sample_pool.py --freeze --year {fy} --stratum {h} primero)")
    df = pd.read_csv(src)
    if len(df) < N_INITIAL:
        sys.exit(f"[error] {src} tiene sólo {len(df)} filas — se necesitan {N_INITIAL}")
    return df.iloc[:N_INITIAL].copy()


def build(fy):
    """Todas las columnas juntas — el split en archivo limpio / crosswalk pasa en `export()`."""
    df = pd.concat([load_stratum(fy, h) for h in STRATA], ignore_index=True)

    rng = np.random.default_rng(CEO_SHUFFLE_SEED)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    df["PLOTID"] = df.index + 1

    df = df.rename(columns={"lon": "LON", "lat": "LAT", "rank": "frozen_rank"})
    return df[CROSSWALK_COLUMNS]


# ---------------------------------------------------------------------------
# comandos
# ---------------------------------------------------------------------------
def check(fy):
    print(f"[check] año-fuego {fy}")
    for h in STRATA:
        src = FROZEN_DIR / f"{task_name(fy, h)}_frozen.csv"
        print(f"        estrato {h}: {'✓' if src.exists() else '✗ FALTA — correr 02 --freeze'} "
              f"({src.name})")
    n = N_INITIAL * len(STRATA)
    print(f"        sube a CEO:  {OUT_DIR / f'ceo_upload_fy{fy}.csv'}  "
          f"({n} filas — SOLO LON,LAT,PLOTID)")
    print(f"        local only:  {OUT_DIR / f'ceo_crosswalk_fy{fy}.csv'}  "
          f"({n} filas — PLOTID + stratum/burned/etc., nunca se sube)")


def export(fy, overwrite=False):
    out_csv = OUT_DIR / f"ceo_upload_fy{fy}.csv"
    crosswalk_csv = OUT_DIR / f"ceo_crosswalk_fy{fy}.csv"
    if out_csv.exists() and not overwrite:
        print(f"[skip] {out_csv} ya existe (usar --overwrite para reemplazarlo)")
        return

    df = build(fy)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df[CEO_UPLOAD_COLUMNS].to_csv(out_csv, index=False)
    df.to_csv(crosswalk_csv, index=False)

    meta = {
        "fire_year": fy,
        "n_rows": len(df),
        "n_per_stratum": N_INITIAL,
        "shuffle_seed": CEO_SHUFFLE_SEED,
        "ceo_upload_columns": CEO_UPLOAD_COLUMNS,
        "crosswalk_csv": str(crosswalk_csv),
        "source_csv": [str(FROZEN_DIR / f"{task_name(fy, h)}_frozen.csv") for h in STRATA],
    }
    out_meta = OUT_DIR / f"ceo_upload_fy{fy}_meta.json"
    out_meta.write_text(json.dumps(meta, indent=2))

    print(f"[export] {out_csv}  ({len(df):,} filas, sólo LON/LAT/PLOTID — esto es lo que sube a CEO)")
    print(f"[export] {crosswalk_csv}  (tabla llave completa, local, NO subir a ningún lado)")
    print(f"          por estrato: {df['stratum'].value_counts().sort_index().to_dict()}")
    print(f"[export] metadata: {out_meta}")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--year", type=int, help="un año-fuego")
    g.add_argument("--all-years", action="store_true",
                   help=f"los tres años elegidos ({FIRE_YEARS})")
    ap.add_argument("--check", action="store_true", help="reportar sin exportar")
    ap.add_argument("--export", action="store_true", help="armar y escribir el CSV para CEO")
    ap.add_argument("--overwrite", action="store_true",
                    help="reemplazar el CSV si ya existe (reasigna PLOTID)")
    args = ap.parse_args()

    years = list(FIRE_YEARS) if args.all_years else [args.year]

    if args.check:
        for fy in years:
            check(fy)
    elif args.export:
        for fy in years:
            export(fy, args.overwrite)
    else:
        ap.error("elegir uno: --check o --export")


if __name__ == "__main__":
    main()
