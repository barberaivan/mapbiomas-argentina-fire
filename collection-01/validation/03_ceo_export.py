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

COLUMNAS EXTRA — por qué van igual en el CSV
-----------------------------------------------
`stratum`/`burned` viajan en el CSV (después de LON/LAT/PLOTID, como exige CEO). Investigado
2026-08-24 contra el código fuente de CEO (`openforis/collect-earth-online`, `main`): no aparece
ningún camino de UI que las muestre al intérprete durante la colección (se grepeó
`collection.jsx`, `simpleCollection.jsx`, `CollectionSidebar.jsx` y los widgets de Geo-Dash — cero
matches), aunque la documentación de CEO dice que "pueden mostrarse" en el panel de colección.
Doc y código no coinciden — antes de confiar en esto para el blind labelling de §7, vale un chequeo
empírico: subir un proyecto de prueba con una columna obvia y confirmar que no aparece en la
pantalla de colección.

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

CEO_COLUMNS = ["LON", "LAT", "PLOTID", "fire_year", "stratum", "burned",
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
    df = pd.concat([load_stratum(fy, h) for h in STRATA], ignore_index=True)

    rng = np.random.default_rng(CEO_SHUFFLE_SEED)
    df = df.iloc[rng.permutation(len(df))].reset_index(drop=True)
    df["PLOTID"] = df.index + 1

    df = df.rename(columns={"lon": "LON", "lat": "LAT", "rank": "frozen_rank"})
    return df[CEO_COLUMNS]


# ---------------------------------------------------------------------------
# comandos
# ---------------------------------------------------------------------------
def check(fy):
    print(f"[check] año-fuego {fy}")
    for h in STRATA:
        src = FROZEN_DIR / f"{task_name(fy, h)}_frozen.csv"
        print(f"        estrato {h}: {'✓' if src.exists() else '✗ FALTA — correr 02 --freeze'} "
              f"({src.name})")
    print(f"        salida: {OUT_DIR / f'ceo_upload_fy{fy}.csv'}  "
          f"({N_INITIAL * len(STRATA)} filas: {N_INITIAL}/estrato, barajadas)")


def export(fy, overwrite=False):
    out_csv = OUT_DIR / f"ceo_upload_fy{fy}.csv"
    if out_csv.exists() and not overwrite:
        print(f"[skip] {out_csv} ya existe (usar --overwrite para reemplazarlo)")
        return

    df = build(fy)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)

    meta = {
        "fire_year": fy,
        "n_rows": len(df),
        "n_per_stratum": N_INITIAL,
        "shuffle_seed": CEO_SHUFFLE_SEED,
        "source_csv": [str(FROZEN_DIR / f"{task_name(fy, h)}_frozen.csv") for h in STRATA],
    }
    out_meta = OUT_DIR / f"ceo_upload_fy{fy}_meta.json"
    out_meta.write_text(json.dumps(meta, indent=2))

    print(f"[export] {out_csv}  ({len(df):,} filas)")
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
