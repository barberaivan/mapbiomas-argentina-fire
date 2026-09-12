#!/usr/bin/env python3
"""Rule A vs the Delta del Paraná — what an area cap or an AOI would give back.

Replays the docs/07 §1.1 selection on the LOCAL step-05/06 CSVs (no GEE round
trip: it is the same predicate as `07-calendar_scars.R::accepted_oids`), and
then asks what changes if rule A is applied only to objects below an area cap
and/or only outside the wetland ecoregions.

The question it exists to answer: veg_fire class 15 `grassland_pampa` is the
remap of MB classes 11 (Herbáceas Inundables), 12 (Herbáceas) and 15 (Pasturas)
*in the PAMPA region*, so the marshes of the Delta del Paraná carry it exactly
like a Pampa pasture does — and rule A was aimed at harvest/stubble on small
square crop-and-pasture fields, not at the Delta.

    $PYTHON collection-01/scripts/rule_a_cap_diagnostic.py --year 2020
    $PYTHON collection-01/scripts/rule_a_cap_diagnostic.py --all-years

Run from the repo root.
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "collection-01")
import utils.constants as C  # noqa: E402

def store_root():
    """STORE_ROOT from the env or .local-paths (machine-local, written by setup.sh)."""
    env = os.environ.get("STORE_ROOT")
    if env:
        return Path(env)
    lp = Path(__file__).resolve().parents[2] / ".local-paths"
    for line in lp.read_text().splitlines() if lp.exists() else []:
        if line.startswith("STORE_ROOT="):
            return Path(line.split("=", 1)[1].strip())
    sys.exit("no STORE_ROOT in env and none in .local-paths -- run ./setup.sh")


MIN_FIRE_HA = 1.0
# The two ecoregions whose "grassland_pampa" is flooded marsh, not cropland.
WETLANDS = ["Delta e Islas del Paraná", "Campos y Malezales"]
DELTA = "Delta e Islas del Paraná"
BANDS = [0, 10, 25, 50, 100, 150, 200, 300, 500, 1000, 5000, np.inf]


def load(fy, data_dir):
    """One fire year of accepted objects, tagged with both rules and its ecoregion."""
    pr = pd.read_csv(f"{data_dir}/objects-pred/objects_{fy}_pred.csv",
                     usecols=["oid", "fire"])
    mt = pd.read_csv(f"{data_dir}/objects-raw/objects_{fy}_raster_metrics.csv",
                     usecols=["oid", "area_ha", "date_median",
                              "frac_c1", "frac_c2", "frac_c3", "frac_c15"])
    d = pr.merge(mt, on="oid")
    d = d[(d.fire == 1) & (d.area_ha >= MIN_FIRE_HA) & d.date_median.notna()].copy()
    lo, hi = C.grass_window_days(fy)
    # Both rules drop on `>`, so the keep is `<=` (docs/07 §1.1).
    d["ruleA"] = ((d.frac_c15 > C.T_GRASS)
                  & (d.date_median >= lo) & (d.date_median <= hi))
    d["ruleB"] = (d.frac_c1 + d.frac_c2 + d.frac_c3) > C.T_AGRI
    rg = pd.read_csv(f"{data_dir}/objects-analysis/regions_{fy}_one.csv")
    rg = rg[rg.layer == "ecoregions13"][["oid", "region_name"]]
    return d.merge(rg, on="oid", how="left")


def pct(a, b):
    return 100.0 * a / b if b else float("nan")


def one_year(fy, data_dir):
    d = load(fy, data_dir)
    tot = d.area_ha.sum()
    A, B = d[d.ruleA], d[d.ruleB]
    print(f"=== FY{fy}  accepted before rules: {len(d):,} obj  {tot:,.0f} ha ===")
    print(f"  rule A {len(A):,} obj  {A.area_ha.sum():,.0f} ha  "
          f"({pct(A.area_ha.sum(), tot):.1f} %)")
    print(f"  rule B {len(B):,} obj  {B.area_ha.sum():,.0f} ha  "
          f"({pct(B.area_ha.sum(), tot):.1f} %)")
    gone = d[d.ruleA | d.ruleB]
    print(f"  A|B    {len(gone):,} obj  {gone.area_ha.sum():,.0f} ha  "
          f"({pct(gone.area_ha.sum(), tot):.1f} %)\n")

    print("--- rule-A drops by ecoregion ---")
    g = A.groupby("region_name").agg(n=("oid", "size"), ha=("area_ha", "sum"),
                                     med_ha=("area_ha", "median"),
                                     max_ha=("area_ha", "max"))
    g = g.join(d.groupby("region_name").area_ha.sum().rename("region_ha"))
    g["pct_of_region"] = 100 * g.ha / g.region_ha
    g["pct_of_A"] = 100 * g.ha / A.area_ha.sum()
    print(g.sort_values("ha", ascending=False).round(1).to_string(), "\n")

    print("--- rule-A drops by size band ---")
    ab = A.assign(band=pd.cut(A.area_ha, BANDS))
    print(ab.groupby("band", observed=True)
            .agg(n=("oid", "size"), ha=("area_ha", "sum"))
            .assign(pct_of_A=lambda t: (100 * t.ha / t.ha.sum()).round(1))
            .round(0).to_string(), "\n")

    print("--- rule A applied only BELOW a cap (rule B untouched) ---")
    rows = []
    for cap in [50, 100, 150, 200, 300, 500, 1000, 5000, np.inf]:
        drop = d[(d.ruleA & (d.area_ha < cap)) | d.ruleB]
        back = d[d.ruleA & (d.area_ha >= cap)]
        rows.append(dict(cap_ha=cap, dropped_ha=round(drop.area_ha.sum()),
                         pct_dropped=round(pct(drop.area_ha.sum(), tot), 1),
                         mapped_ha=round(tot - drop.area_ha.sum()),
                         rescued_ha=round(back.area_ha.sum()),
                         rescued_in_delta=round(
                             back[back.region_name == DELTA].area_ha.sum())))
    print(pd.DataFrame(rows).to_string(index=False), "\n")

    D = d[d.region_name == DELTA]
    DA = D[D.ruleA]
    print(f"--- the Delta, FY{fy} ---")
    print(f"  before rules {len(D):,} obj  {D.area_ha.sum():,.0f} ha")
    print(f"  rule A drops {len(DA):,} obj  {DA.area_ha.sum():,.0f} ha "
          f"({pct(DA.area_ha.sum(), D.area_ha.sum()):.1f} % of the ecoregion)")
    if len(DA):
        top = DA.nlargest(10, "area_ha")[["oid", "area_ha", "frac_c15", "date_median"]]
        top["date"] = pd.to_datetime(top.date_median, unit="D",
                                     origin="1970-01-01").dt.date
        print("  largest rule-A drops there:")
        print(top.drop(columns="date_median").round(3).to_string(index=False))


def all_years(data_dir, cap=150.0):
    rows = []
    for fy in range(C.FIRST_FIRE_YEAR, C.LAST_FIRE_YEAR + 1):
        d = load(fy, data_dir)
        A = d[d.ruleA]
        D = d[d.region_name == DELTA]
        keep = lambda m: d[~m].area_ha.sum()  # noqa: E731
        pub = keep(d.ruleA | d.ruleB)
        alt = keep((d.ruleA & (d.area_ha < cap)
                    & ~d.region_name.isin(WETLANDS)) | d.ruleB)
        rows.append(dict(
            fy=fy, acc_ha=d.area_ha.sum(), A_ha=A.area_ha.sum(),
            A_pct=pct(A.area_ha.sum(), d.area_ha.sum()),
            delta_ha=D.area_ha.sum(), delta_A_ha=D[D.ruleA].area_ha.sum(),
            delta_A_pct=pct(D[D.ruleA].area_ha.sum(), D.area_ha.sum()),
            A_in_delta_pct=pct(D[D.ruleA].area_ha.sum(), A.area_ha.sum()),
            published_ha=pub, modified_ha=alt))
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(t.round(1).to_string(index=False))
    s = t.sum()
    print(f"\nALL YEARS: accepted {s.acc_ha / 1e6:.2f} Mha | published "
          f"{s.published_ha / 1e6:.2f} Mha "
          f"(-{pct(s.acc_ha - s.published_ha, s.acc_ha):.1f} %) | "
          f"rule A only <{cap:g} ha and outside {'+'.join(WETLANDS)} "
          f"{s.modified_ha / 1e6:.2f} Mha "
          f"(-{pct(s.acc_ha - s.modified_ha, s.acc_ha):.1f} %)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2020)
    ap.add_argument("--all-years", action="store_true")
    ap.add_argument("--cap", type=float, default=150.0,
                    help="area cap for the --all-years modified column")
    ap.add_argument("--data-dir", default=None)
    a = ap.parse_args()
    a.data_dir = a.data_dir or f"{store_root()}/collection-01/data"
    if a.all_years:
        all_years(a.data_dir, a.cap)
    else:
        one_year(a.year, a.data_dir)
