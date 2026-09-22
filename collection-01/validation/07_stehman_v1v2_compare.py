#!/usr/bin/env python3
"""
collection-01/validation/07_stehman_v1v2_compare.py

Comparación v1 vs v2 pedida por Iván (WhatsApp, 2026-09-21): proporción de aciertos
(map_burned == ref_burned) POR ESTRATO, con su IC, para el mapa v1 y para el v2 corregido
("volantazo" de la semana previa) — NO el estimador poblacional de Stehman
(`06_stehman_compute.R`), que ya corrió y quedó dominado por la varianza de S3 (BACKLOG.md,
2026-09-20). Esto es un diagnóstico punto-a-punto sin ponderar por `Nh`.

DOS "v1" DISTINTOS — CUÁL SE USA ACÁ
-------------------------------------
`stehman_input_fy<FY>.csv` (paso 5) ya trae una columna `map_burned`, pero sale de
`C.MONTH_OF_BURN_COL` = `CLASSIFICATION_COLLECTIONS/collection1_fire_mask_v1`, el output CRUDO
del modelo (paso 07a), ANTES del post-procesamiento de red (paso 08). v2 sólo existe como
producto YA post-procesado (`FINAL_PRODUCTS/..._monthly_burned_v2`). Comparar ese `map_burned`
crudo contra v2 post-procesado mezclaría dos efectos (el fix de Iván + el post-procesamiento).

Por eso este paso IGNORA la columna `map_burned` del CSV y recalcula v1 Y v2 desde el mismo
asset post-procesado (`FINAL_PRODUCTS/..._monthly_burned_{v1,v2}`), la contraparte exacta una
de la otra — la única diferencia entre las dos queda aislada al fix real.

AÑO-FUEGO, NO AÑO CALENDARIO
-----------------------------
Las imágenes son un IMAGE multibanda por AÑO CALENDARIO (`burned_monthly_<year>`, 1–12). El
fire_year va de 1-mayo de FY a 30-abril de FY+1 — misma fórmula que `01_strata_export.py::mob()`
+ `our_burn()` (Apéndice A, docs/10-validation.md §3), aplicada acá contra el asset post-
procesado en lugar del asset de clasificación:

    our_burn(asset, fy) = (burned_monthly_<fy> >= 5) OR (burned_monthly_<fy+1> <= 4)

100% LOCAL salvo el sampleo de puntos en GEE (barato — ~50-70 puntos por año-fuego, una sola
llamada `sampleRegions` por año, sin exports).

QUÉ HACE
--------
Por año-fuego ya interpretado (`outputs/stehman_input_fy<FY>.csv`, filas `uninterpretable`
excluidas — mismo criterio que `06_stehman_compute.R`):
  1. Arma un FeatureCollection de puntos (lon/lat) con `plotid`.
  2. Sampleá `our_burn(V1, fy)` y `our_burn(V2, fy)` en esos puntos (`sampleRegions`, proyección
     pineada `C.SNIC_CRS`/`C.SNIC_TRANSFORM`, NUNCA `scale=30`).
  3. Por estrato y por versión: proporción de acierto = mean(map_burned_v{1,2} == ref_burned),
     con IC 95% Wilson (Wilson 1927 — cerrado, sin normal approx del CI ingenuo, mejor
     comportado con n chico y proporciones cerca de 0/1; no depende de scipy/statsmodels).
  4. Reporta por año-fuego Y pooled (los 3 años juntos) — por separado son ~50-68 puntos por
     estrato-año, muy poco para un IC angosto.
  5. Escribe `outputs/stratum_accuracy_v1_v2.csv` (hit-rate simple, diagnóstico) y
     `outputs/stehman_input_v1v2_fy<FY>.csv` (un archivo por año-fuego, `stratum`/`ref_burned`/
     `map_burned_v1`/`map_burned_v2`, listo para `08_stehman_v1v2_compute.R` — el estimador
     poblacional de Stehman corrido por separado para v1 y v2, NO pooled entre años: cada
     año-fuego tiene su propio `Nh`/área, pooling no aplica ahí).

USO
---
    $PYTHON collection-01/validation/07_stehman_v1v2_compare.py --check
    $PYTHON collection-01/validation/07_stehman_v1v2_compare.py --compute
"""
from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

import ee
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
_s1 = import_module("01_strata_export")
FIRE_YEARS = _s1.FIRE_YEARS
VAL_PROJECT = _s1.VAL_PROJECT
initialize = _s1.initialize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils.constants as C  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent / "outputs"

FINAL_PRODUCTS = "projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/FINAL_PRODUCTS"
MOB_ASSET = {
    "v1": f"{FINAL_PRODUCTS}/mapbiomas_argentina_fire_collection1_monthly_burned_v1",
    "v2": f"{FINAL_PRODUCTS}/mapbiomas_argentina_fire_collection1_monthly_burned_v2",
}
VERSIONS = ["v1", "v2"]
STRATA = [1, 2, 3]

Z_975 = 1.959963985  # normal 97.5th pct — Wilson score interval (Wilson 1927)


# ---------------------------------------------------------------------------
# GEE — our_burn(asset, fy), misma fórmula que 01_strata_export.py::our_burn()
# ---------------------------------------------------------------------------
def mob_band(asset_id, year):
    return ee.Image(asset_id).select(f"burned_monthly_{year}").unmask(0)


def our_burn(asset_id, fy):
    m, m_next = mob_band(asset_id, fy), mob_band(asset_id, fy + 1)
    return m.gte(5).Or(m_next.gte(1).And(m_next.lte(4)))


def sample_fy(df_usable, fy):
    """Sampleá our_burn(v1) y our_burn(v2) en los puntos usables de este fire_year.
    Devuelve dict plotid -> {"map_burned_v1": bool, "map_burned_v2": bool}."""
    img = (our_burn(MOB_ASSET["v1"], fy).rename("map_burned_v1")
           .addBands(our_burn(MOB_ASSET["v2"], fy).rename("map_burned_v2")))
    feats = [ee.Feature(ee.Geometry.Point([float(r.lon), float(r.lat)]), {"plotid": int(r.plotid)})
              for r in df_usable.itertuples()]
    locations = ee.FeatureCollection(feats)
    proj = ee.Projection(C.SNIC_CRS, C.SNIC_TRANSFORM)
    sampled = img.sampleRegions(collection=locations, projection=proj, tileScale=4,
                                 geometries=False).getInfo()["features"]
    return {f["properties"]["plotid"]: f["properties"] for f in sampled}


# ---------------------------------------------------------------------------
# Wilson score interval — Wilson, E.B. (1927), JASA 22(158):209-212
# ---------------------------------------------------------------------------
def wilson_ci(hits, n, z=Z_975):
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    phat = hits / n
    denom = 1 + z * z / n
    center = phat + z * z / (2 * n)
    adj = z * ((phat * (1 - phat) / n + z * z / (4 * n * n)) ** 0.5)
    return phat, (center - adj) / denom, (center + adj) / denom


# ---------------------------------------------------------------------------
def load_usable(fy):
    src = OUT_DIR / f"stehman_input_fy{fy}.csv"
    if not src.exists():
        sys.exit(f"[error] {src} no existe — correr 05_stehman_export.py --export --year {fy} primero")
    df = pd.read_csv(src)
    return df[~df["uninterpretable"]].copy()


def build(years):
    rows = []
    per_year = {}
    for fy in years:
        usable = load_usable(fy)
        sampled = sample_fy(usable, fy)

        missing = set(usable["plotid"]) - set(sampled)
        if missing:
            sys.exit(f"[error] fy{fy}: {len(missing)} plotid sin sampleo GEE (fuera de máscara?) "
                      f"— revisar: {sorted(missing)[:10]}")

        usable = usable.copy()
        for v in VERSIONS:
            usable[f"map_burned_{v}"] = usable["plotid"].map(
                lambda p: "burned" if sampled[p][f"map_burned_{v}"] else "unburned")
            usable[f"hit_{v}"] = usable[f"map_burned_{v}"] == usable["ref_burned"]
        per_year[fy] = usable

        r_input = usable[["stratum", "ref_burned", "map_burned_v1", "map_burned_v2"]]
        r_out = OUT_DIR / f"stehman_input_v1v2_fy{fy}.csv"
        r_input.to_csv(r_out, index=False)
        print(f"[escrito] {r_out}  ({len(r_input)} filas, para 08_stehman_v1v2_compute.R)")

        for h in STRATA:
            sub = usable[usable["stratum"] == h]
            for v in VERSIONS:
                n = len(sub)
                hits = int(sub[f"hit_{v}"].sum())
                p, lo, hi = wilson_ci(hits, n)
                rows.append({"fire_year": fy, "stratum": h, "version": v,
                             "n": n, "hits": hits, "proportion": round(p, 4),
                             "ci_low": round(lo, 4), "ci_high": round(hi, 4)})

    pooled = pd.concat(per_year.values(), ignore_index=True)
    for h in STRATA:
        sub = pooled[pooled["stratum"] == h]
        for v in VERSIONS:
            n = len(sub)
            hits = int(sub[f"hit_{v}"].sum())
            p, lo, hi = wilson_ci(hits, n)
            rows.append({"fire_year": "pooled", "stratum": h, "version": v,
                         "n": n, "hits": hits, "proportion": round(p, 4),
                         "ci_low": round(lo, 4), "ci_high": round(hi, 4)})

    out_df = pd.DataFrame(rows)
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "stratum_accuracy_v1_v2.csv"
    out_df.to_csv(out, index=False)

    print(f"\n{'fy':<8}{'S':<3}{'ver':<5}{'n':<5}{'hits':<6}{'prop':<8}{'ci95':<20}")
    for _, r in out_df.iterrows():
        print(f"{str(r.fire_year):<8}{r.stratum:<3}{r.version:<5}{r.n:<5}{r.hits:<6}"
              f"{r.proportion:<8.4f}[{r.ci_low:.4f}, {r.ci_high:.4f}]")
    print(f"\n[escrito] {out}")
    return out_df


def check(years):
    for fy in years:
        src = OUT_DIR / f"stehman_input_fy{fy}.csv"
        print(f"[check] fy{fy}: {'ok' if src.exists() else 'FALTA'} ({src})")


# ---------------------------------------------------------------------------
def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--compute", action="store_true")
    ap.add_argument("--credentials", help="ver 01_strata_export.py::initialize()")
    args = ap.parse_args()

    if not (args.check or args.compute):
        ap.error("elegir --check o --compute")

    if args.check:
        check(FIRE_YEARS)
        return

    initialize(VAL_PROJECT, args.credentials)
    build(FIRE_YEARS)


if __name__ == "__main__":
    main()
