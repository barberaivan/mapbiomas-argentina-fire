#!/usr/bin/env python3
"""
collection-01/validation/05_stehman_export.py

Paso 5 de la validación — junta la interpretación de Collect Earth Online (CEO) con la tabla
llave (`ceo_crosswalk_fy<FY>.csv`, paso 3) y arma el input listo para `mapaccuracy::stehman2014()`
en R (docs/10-validation.md §9). Este repo no corre el estimador — no hay R instalado en esta
máquina (2026-09-20) y el estimador lo corre Iván de su lado; este paso deja preparado exactamente
lo que `stehman2014(s, r, m, Nh_strata)` espera, para que unirlo sea un `read.csv()`.

100% LOCAL — no toca GEE.

QUÉ HACE
--------
Por año-fuego:
  1. Lee el CSV de plot-data exportado por CEO (`ceo_data/preliminar_val_ceo/`, el más reciente
     que matchea el año) y se queda con las filas YA INTERPRETADAS (`collection_time` no vacío).
  2. Construye la etiqueta de referencia (`ref_burned`, "burned"/"unburned") desde las columnas
     one-hot `¿Se quemó...?:Si` / `:No` — el texto de la pregunta cambia por año (el rango de
     fechas), por eso se matchea por prefijo/sufijo, no por el string completo.
  3. Excluye del input al estimador las filas marcadas `flagged == true` (intérprete no pudo
     responder con confianza) — se cuentan y reportan aparte, nunca se les inventa una etiqueta.
  4. Junta por `PLOTID` con `outputs/ceo/ceo_crosswalk_fy<FY>.csv` (paso 3) para traer `stratum` y
     la clase del mapa (`map_burned`, la propia banda `burned` con la que se sorteó — no se
     recalcula ni se vuelve a mirar el asset).
  5. Escribe `outputs/stehman_input_fy<FY>.csv`, una fila por punto interpretado, listo para:

         s <- df$stratum;  r <- df$ref_burned;  m <- df$map_burned
         w <- read.csv("outputs/strata_weights_fy<FY>.csv")
         Nh_strata <- setNames(w$n_pixels, w$stratum)
         stehman2014(s, r, m, Nh_strata)

     `outputs/strata_weights_fy<FY>.csv` (paso 1, `--weights`) ya trae `Nh_strata` — este paso no
     lo duplica, sólo dejamos ambos archivos con la misma clave `stratum` para que el join en R
     sea directo.

NO calcula el área ajustada ni el accuracy — esos son la salida de `stehman2014()`, no de este
paso (docs/10 §9: "el estimador usado es Stehman 2014, no Olofsson", ver docstring de
`01_strata_export.py::weights_launch()` y el header de este módulo).

USO
---
    $PYTHON collection-01/validation/05_stehman_export.py --check
    $PYTHON collection-01/validation/05_stehman_export.py --export --year 2022
    $PYTHON collection-01/validation/05_stehman_export.py --export --all-years
"""
from __future__ import annotations

import argparse
import glob
import re
import sys
from importlib import import_module
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
_s1 = import_module("01_strata_export")
FIRE_YEARS = _s1.FIRE_YEARS

CEO_DIR = Path(__file__).resolve().parent / "ceo_data" / "preliminar_val_ceo"
CROSSWALK_DIR = Path(__file__).resolve().parent / "outputs" / "ceo"
OUT_DIR = Path(__file__).resolve().parent / "outputs"

BURNED_Q_RE = re.compile(r"^¿Se quemó.*:(Si|No)$")
BORDER_Q_RE = re.compile(r"^¿Es borde\?:(Si|No)$")
CONFIDENCE_Q_RE = re.compile(r"^Confianza:(\d+)$")


# ---------------------------------------------------------------------------
def find_ceo_csv(fy):
    pattern = str(CEO_DIR / f"ceo-MB-Fuego-Col-01---Validación-{fy}-plot-data-*.csv")
    hits = sorted(glob.glob(pattern))
    if not hits:
        sys.exit(f"[error] no encontré ningún export de CEO para fy{fy} en {CEO_DIR}")
    if len(hits) > 1:
        print(f"[warn] fy{fy}: {len(hits)} exports de CEO encontrados, uso el más reciente "
              f"por nombre: {Path(hits[-1]).name}")
    return Path(hits[-1])


def load_ceo(fy):
    """Filas YA interpretadas (`collection_time` no vacío), con `ref_burned`/`is_border`/
    `confidence` ya extraídas de las columnas one-hot. NO excluye `flagged==true` acá — eso se
    reporta y se filtra en `build()`, para que el conteo de no-interpretables quede visible."""
    src = find_ceo_csv(fy)
    df = pd.read_csv(src, encoding="utf-8-sig")
    df = df[df["collection_time"].notna() & (df["collection_time"] != "")].copy()

    burned_si_col = next(c for c in df.columns if BURNED_Q_RE.match(c) and c.endswith(":Si"))
    burned_no_col = next(c for c in df.columns if BURNED_Q_RE.match(c) and c.endswith(":No"))
    border_si_col = next(c for c in df.columns if BORDER_Q_RE.match(c) and c.endswith(":Si"))
    conf_cols = [c for c in df.columns if CONFIDENCE_Q_RE.match(c)]

    df["uninterpretable"] = df["flagged"].astype(str).str.lower() == "true"

    si = df[burned_si_col].fillna(0) > 0
    no = df[burned_no_col].fillna(0) > 0
    unanswered = ~(si | no)
    # una fila `flagged==true` (intérprete no pudo decidir) legítimamente no responde la pregunta
    # de quema — se excluye del estimador en build(), no es un error del export.
    bad = unanswered & ~df["uninterpretable"]
    if bad.any():
        sys.exit(f"[error] fy{fy}: {bad.sum()} filas interpretadas y NO flaggeadas sin Si/No en "
                  f"la pregunta de quema — revisar el export de CEO")
    df["ref_burned"] = si.map({True: "burned", False: "unburned"})
    df.loc[unanswered, "ref_burned"] = pd.NA
    df["is_border"] = df[border_si_col].fillna(0) > 0

    def confidence(row):
        for c in conf_cols:
            if row.get(c, 0) and float(row[c]) > 0:
                return int(CONFIDENCE_Q_RE.match(c).group(1))
        return pd.NA
    df["confidence"] = df.apply(confidence, axis=1)
    df["plotid"] = df["plotid"].astype(int)

    return df[["plotid", "email", "collection_time", "analysis_duration", "ref_burned",
               "is_border", "confidence", "uninterpretable", "flagged_reason"]]


def load_crosswalk(fy):
    src = CROSSWALK_DIR / f"ceo_crosswalk_fy{fy}.csv"
    if not src.exists():
        sys.exit(f"[error] {src} no existe — correr 03_ceo_export.py --export --year {fy} primero")
    df = pd.read_csv(src)
    df["PLOTID"] = df["PLOTID"].astype(int)
    df["stratum"] = df["stratum"].astype(int)
    df["map_burned"] = df["burned"].map({1: "burned", 1.0: "burned", 0: "unburned", 0.0: "unburned"})
    return df[["PLOTID", "LON", "LAT", "stratum", "map_burned"]]


def weights_csv_exists(fy):
    return (OUT_DIR / f"strata_weights_fy{fy}.csv").exists()


# ---------------------------------------------------------------------------
def build(fy):
    ceo = load_ceo(fy)
    cross = load_crosswalk(fy)

    df = ceo.merge(cross, left_on="plotid", right_on="PLOTID", how="left", validate="one_to_one")
    missing = df["stratum"].isna()
    if missing.any():
        sys.exit(f"[error] fy{fy}: {missing.sum()} PLOTID interpretados no aparecen en el "
                  f"crosswalk — ¿export de CEO de un año/versión distinta?")

    n_total = len(df)
    n_uninterp = int(df["uninterpretable"].sum())
    usable = df[~df["uninterpretable"]].copy()

    df.insert(0, "fire_year", fy)
    df = df.rename(columns={"LON": "lon", "LAT": "lat"})
    cols = ["fire_year", "plotid", "lon", "lat", "stratum", "map_burned", "ref_burned",
            "confidence", "is_border", "uninterpretable", "flagged_reason",
            "email", "collection_time", "analysis_duration"]
    df = df[cols].sort_values("plotid")

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"stehman_input_fy{fy}.csv"
    df.to_csv(out, index=False)

    by_stratum = usable["stratum"].value_counts().sort_index()
    print(f"[export] fy{fy} — {n_total} interpretados, {n_uninterp} no-interpretables excluidos, "
          f"{len(usable)} usables")
    print(f"          usables por estrato: " +
          ", ".join(f"S{h}={by_stratum.get(h, 0)}" for h in (1, 2, 3)))
    if not weights_csv_exists(fy):
        print(f"          [warn] outputs/strata_weights_fy{fy}.csv no existe todavía — "
              f"correr 01_strata_export.py --weights --year {fy} antes de pasarle esto a Iván")
    print(f"          escrito: {out}")
    return df


def check(fy):
    ceo_src = find_ceo_csv(fy)
    ceo = load_ceo(fy)
    print(f"[check] fy{fy} — CEO: {ceo_src.name}  ({len(ceo)} interpretados, "
          f"{int(ceo['uninterpretable'].sum())} no-interpretables)")
    cross_src = CROSSWALK_DIR / f"ceo_crosswalk_fy{fy}.csv"
    print(f"         crosswalk: {'ok' if cross_src.exists() else 'FALTA'} ({cross_src})")
    w_src = OUT_DIR / f"strata_weights_fy{fy}.csv"
    print(f"         weights:   {'ok' if w_src.exists() else 'FALTA'} ({w_src})")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="sólo reporta qué inputs existen")
    ap.add_argument("--export", action="store_true", help="arma outputs/stehman_input_fy<FY>.csv")
    ap.add_argument("--year", type=int, choices=FIRE_YEARS)
    ap.add_argument("--all-years", action="store_true")
    args = ap.parse_args()

    if not (args.year or args.all_years):
        ap.error("elegir --year <FY> o --all-years")
    years = FIRE_YEARS if args.all_years else [args.year]

    if args.check:
        for fy in years:
            check(fy)
    elif args.export:
        frames = [build(fy) for fy in years]
        if len(frames) > 1:
            combined = pd.concat(frames, ignore_index=True)
            out = OUT_DIR / "stehman_input_all.csv"
            combined.to_csv(out, index=False)
            print(f"[export] combinado: {out}  ({len(combined)} filas)")
    else:
        ap.error("elegir uno: --check o --export")


if __name__ == "__main__":
    main()
