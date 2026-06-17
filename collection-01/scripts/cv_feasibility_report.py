"""
collection-01/scripts/cv_feasibility_report.py

Pre-flight CV feasibility check — RUN THIS BEFORE FITTING.

For each fittable veg_fire class, reports the numbers that determine whether
grouped (leave-fires-out) K-fold CV is viable, so class definitions can be
revised *before* fitting models. Cross-region classes (e.g. shrubland_cuyo-pampa,
agriculture-per_chaco-ba) are handled correctly: their obs from all contributing
regions are merged before computing stats.

Per class it reports: total obs, positives, negatives, the number of fires
that carry positives (this caps K), the realized K = min(10, that count), and the
mean positives-per-fold at that K. It also flags pure-negative fires (burned=0 everywhere
within their region, e.g. PAT_fire_46/47, some Pampa crop fires) and their share
per class: those are handled as point-distributed hard negatives, NOT as held-out
folds. Fire ids are made region-unique (region_fireid) before any fire-level count,
because bare fire_ids repeat across regions.

Usage
-----
  python collection-01/scripts/cv_feasibility_report.py --version 1
  python collection-01/scripts/cv_feasibility_report.py --version 1 --region BA CHACO
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import constants as C  # noqa: E402

csv.field_size_limit(10**9)
DATA_DIR   = Path(__file__).resolve().parents[1] / "data"
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
TARGET_K          = 10
MIN_POS_PER_FOLD  = 50  # advisory floor; warn below this


def _is_burned(v):
    return v in ("1", "1.0", "True", "true")


def main(version, region_filter=None):
    # Build remap keyed by (region, mb_class_raw) — the same raw class can map
    # to different veg_fire classes in different regions.
    remap = {}
    class_info    = {}               # veg_fire_name → {veg_fire, fittable}
    class_regions = defaultdict(set) # veg_fire_name → set of regions it spans

    for r in C.VEG_FIRE_REMAP:
        if not r.get("veg_fire_name"):
            continue
        try:
            mb = int(float(r["mb_class_raw"]))
        except (TypeError, ValueError):
            continue
        remap[(r["region"], mb)] = r
        class_info[r["veg_fire_name"]] = {
            "veg_fire": r["veg_fire"],
            "fittable": r["fittable"],
        }
        class_regions[r["veg_fire_name"]].add(r["region"])

    # Which region CSVs exist on disk?
    avail = [
        reg for reg in C.REGIONS
        if (DATA_DIR / f"training_observations_{reg}_v{version}.csv").exists()
    ]
    if region_filter:
        avail = [r for r in avail if r in region_filter]

    if not avail:
        sys.exit(f"No training_observations CSVs found for v{version} "
                 f"(looked in {DATA_DIR}).")

    print(f"Available region CSVs (v{version}): {', '.join(avail)}")

    # Single streaming pass over all available region CSVs.
    cls_obs      = defaultdict(int)
    cls_pos      = defaultdict(int)
    cls_fires_pos = defaultdict(set)            # fires with >=1 positive
    fire_burned  = defaultdict(int)             # total positives per fire_id
    cls_fire_neg = defaultdict(lambda: defaultdict(int))  # class→fire→neg count
    unmapped     = defaultdict(lambda: defaultdict(int))  # region→mb→count

    for reg in avail:
        path = DATA_DIR / f"training_observations_{reg}_v{version}.csv"
        print(f"  reading {path.name} ...", flush=True)
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                # fire_ids repeat across regions (fire_01 exists in every region),
                # so key every fire-level statistic on a region-unique id.
                fuid = f"{reg}_{row['fire_id']}"
                b    = _is_burned(row["burned"])
                fire_burned[fuid] += int(b)
                try:
                    mb = int(float(row["mb_class_raw"]))
                except (TypeError, ValueError):
                    mb = None
                r = remap.get((reg, mb))
                if r is None:
                    unmapped[reg][mb] += 1
                    continue
                name = r["veg_fire_name"]
                cls_obs[name] += 1
                if b:
                    cls_pos[name] += 1
                    cls_fires_pos[name].add(fuid)
                else:
                    cls_fire_neg[name][fuid] += 1

    # Region-unique ids: a fire that is pure-negative within its region is detected
    # even when its bare fire_id burns in another region.
    pure_neg_fires = {fuid for fuid, nb in fire_burned.items() if nb == 0}

    # ── report ────────────────────────────────────────────────────────────────
    print(f"\nCV feasibility — v{version}   "
          f"(pure-negative fires: {', '.join(sorted(pure_neg_fires)) or 'none'})\n")
    hdr = (f"{'class':28}{'regions':20}{'obs':>10}{'pos':>9}{'%pos':>6}"
           f"{'fires+':>8}{'K':>4}{'pos/fold':>10}{'ash%neg':>9}")
    print(hdr); print("-" * len(hdr))

    all_names = sorted(
        cls_obs,
        key=lambda x: (not class_info.get(x, {}).get("fittable"), -cls_obs[x]),
    )
    rows_out = []
    for name in all_names:
        info     = class_info.get(name, {})
        fittable = info.get("fittable", False)
        needed   = class_regions.get(name, set())
        missing  = needed - set(avail)

        obs, pos = cls_obs[name], cls_pos[name]
        neg      = obs - pos
        n_fires_pos = len(cls_fires_pos[name])
        K        = min(TARGET_K, n_fires_pos) if (fittable and not missing) else 0
        pos_fold = pos / K if K else 0
        ash_neg  = sum(n for fuid, n in cls_fire_neg[name].items()
                       if fuid in pure_neg_fires)
        ash_pct  = 100 * ash_neg / neg if neg else 0.0

        flag = ""
        if fittable and not missing and 0 < pos_fold < MIN_POS_PER_FOLD:
            flag += "  <-- low pos/fold"
        if not fittable:
            flag += "  [non-fittable]"
        if missing:
            flag += f"  [missing regions: {','.join(sorted(missing))}]"

        regions_str = "+".join(sorted(needed))
        print(f"{name:28}{regions_str:20}{obs:>10,}{pos:>9,}{100*pos/obs:>6.1f}"
              f"{n_fires_pos:>8}{K:>4}{pos_fold:>10,.0f}{ash_pct:>8.1f}%{flag}")
        rows_out.append({
            "veg_fire_name":            name,
            "veg_fire":                 info.get("veg_fire"),
            "regions":                  regions_str,
            "fittable":                 fittable,
            "all_regions_available":    not bool(missing),
            "n_obs":                    obs,
            "n_pos":                    pos,
            "n_neg":                    neg,
            "n_fires_with_pos":         n_fires_pos,
            "realized_K":               K,
            "mean_pos_per_fold":        round(pos_fold, 1),
            "pct_neg_from_pure_neg_fires": round(ash_pct, 1),
        })

    for reg, ump in unmapped.items():
        if ump:
            print(f"\nWARNING ({reg}): {sum(ump.values()):,} unmapped obs "
                  f"(mb_class_raw not in remap): {dict(ump)}")

    if rows_out:
        MODELS_DIR.mkdir(exist_ok=True)
        out = MODELS_DIR / f"cv_feasibility_v{version}.csv"
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows_out[0].keys()))
            w.writeheader(); w.writerows(rows_out)
        print(f"\nWrote {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Pre-flight CV feasibility report.")
    p.add_argument("--version", type=int, default=1)
    p.add_argument("--region", nargs="*", choices=C.REGIONS, dest="region_filter",
                   metavar="REGION",
                   help="Restrict to these region CSVs (default: all available).")
    args = p.parse_args()
    main(args.version, args.region_filter)
