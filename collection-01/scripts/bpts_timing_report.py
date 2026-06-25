"""
collection-01/scripts/bpts_timing_report.py

Post-hoc timing/cost analysis for a bpts export run.  Pulls every bpts task from
GEE's operation list for a given year and reports, per tile: queue wait, run
duration, EECU; and an account-level rollup (total wall-clock, total EECU,
state counts, duration distribution, and the effective throughput given the
2-tasks-in-parallel limit).

Run from the repo root:

    $PYTHON collection-01/scripts/bpts_timing_report.py --year 2015
    $PYTHON collection-01/scripts/bpts_timing_report.py --year 2015 --since 2026-06-25 --csv bpts_2015_timing.csv

Only operations created on/after --since (default: today UTC) are included, so
old/cancelled tasks from previous runs don't pollute the numbers.  All tasks in
one run share one account, so the account rollup == the run as a whole.
"""

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C


def _iso(ts):
    if not ts or ts.startswith("1970-01-01"):
        return None
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _fmt_min(seconds):
    return f"{seconds/60:.1f}" if seconds is not None else "—"


def main():
    ap = argparse.ArgumentParser(description="bpts export timing/cost report.")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--since", default=None,
                    help="Include tasks created on/after this date (YYYY-MM-DD, default: today UTC).")
    ap.add_argument("--csv", default=None, help="Optional path to write the per-tile table as CSV.")
    ap.add_argument("--project", default=None)
    args = ap.parse_args()

    ee.Initialize(project=args.project or C.GEE_PROJECT)
    since = args.since or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prefix = f"bpts_{args.year}_"

    ops = ee.data.listOperations()
    rows = []
    for op in ops:
        m = op.get("metadata", {})
        desc = m.get("description", "")
        if not desc.startswith(prefix):
            continue
        if m.get("createTime", "")[:10] < since:
            continue
        create, start, end = _iso(m.get("createTime")), _iso(m.get("startTime")), _iso(m.get("endTime"))
        wait = (start - create).total_seconds() if (start and create) else None
        run = (end - start).total_seconds() if (start and end) else None
        rows.append({
            "tile": desc[len(prefix):],
            "state": m.get("state"),
            "create": create, "start": start, "end": end,
            "wait_s": wait, "run_s": run,
            "eecu_h": (m.get("batchEecuUsageSeconds") or 0) / 3600.0,
            "error": op.get("error", {}).get("message", ""),
        })

    if not rows:
        print(f"No bpts_{args.year}_* tasks found created on/after {since}.")
        return

    # ── per-tile table ────────────────────────────────────────────────────────
    rows.sort(key=lambda r: (r["run_s"] is None, -(r["run_s"] or 0)))
    print(f"\n=== Per-tile (year {args.year}, since {since}) — slowest first ===")
    print(f"{'tile':16s} {'state':10s} {'wait(min)':>9s} {'run(min)':>9s} {'EECU(h)':>8s}  error")
    for r in rows:
        print(f"{r['tile']:16s} {r['state']:10s} {_fmt_min(r['wait_s']):>9s} "
              f"{_fmt_min(r['run_s']):>9s} {r['eecu_h']:>8.2f}  {r['error'][:50]}")

    # ── account rollup ──────────────────────────────────────────────────────────
    done = [r for r in rows if r["state"] == "SUCCEEDED"]
    failed = [r for r in rows if r["state"] == "FAILED"]
    runtimes = sorted(r["run_s"] for r in rows if r["run_s"] is not None)
    creates = [r["create"] for r in rows if r["create"]]
    ends = [r["end"] for r in rows if r["end"]]
    total_eecu = sum(r["eecu_h"] for r in rows)

    print(f"\n=== Account rollup (year {args.year}) ===")
    print(f"tasks: {len(rows)}  succeeded: {len(done)}  failed: {len(failed)}  "
          f"other: {len(rows)-len(done)-len(failed)}")
    if runtimes:
        n = len(runtimes)
        med = runtimes[n//2] / 60
        mean = sum(runtimes) / n / 60
        print(f"run time (min):  min={runtimes[0]/60:.1f}  median={med:.1f}  "
              f"mean={mean:.1f}  max={runtimes[-1]/60:.1f}")
    print(f"total EECU: {total_eecu:.1f} h  (mean {total_eecu/len(rows):.2f} h/tile)")
    if creates and ends:
        wall = (max(ends) - min(creates)).total_seconds() / 3600
        print(f"wall-clock so far (first create → last end): {wall:.1f} h")
    if runtimes:
        # With P tasks in parallel, ideal wall-clock = sum(runtimes)/P.
        total_run_h = sum(runtimes) / 3600
        for P in (2, 4, 6):
            print(f"  projected wall-clock @ {P} parallel: {total_run_h/P:.1f} h "
                  f"({total_run_h/P/24:.1f} days)")
        print(f"  (sum of all run times = {total_run_h:.1f} EECU-equivalent tile-hours)")

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["tile", "state", "wait_min", "run_min", "eecu_h", "error"])
            for r in rows:
                w.writerow([r["tile"], r["state"],
                            f"{r['wait_s']/60:.1f}" if r["wait_s"] is not None else "",
                            f"{r['run_s']/60:.1f}" if r["run_s"] is not None else "",
                            f"{r['eecu_h']:.3f}", r["error"]])
        print(f"\nPer-tile CSV → {args.csv}")


if __name__ == "__main__":
    main()
