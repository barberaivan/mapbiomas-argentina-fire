"""
collection-01/scripts/watch_bpts_export.py

Poll GEE task operations for bpts export jobs and write a Markdown report that
records per-task timing, progress, and error messages.

Run from the repo root:

    $PYTHON collection-01/scripts/watch_bpts_export.py --year 2015
    $PYTHON collection-01/scripts/watch_bpts_export.py --year 2015 --interval 120 --output bpts_2015_watch.md
    $PYTHON collection-01/scripts/watch_bpts_export.py  # all bpts tasks

The report is rewritten on every poll cycle.  It covers only operations whose
createTime is >= --since (default: today's date) so old failed/cancelled tasks
from previous runs don't pollute the output.

Ctrl+C to stop watching; the last written report stays on disk.
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ee
from utils import constants as C

# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_iso(ts: str) -> datetime | None:
    """Parse a GEE ISO-8601 timestamp; return None for the epoch sentinel."""
    if not ts or ts.startswith("1970-01-01"):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _fmt_duration(seconds: float) -> str:
    """Format a duration in seconds as 'Xh Ym Zs'."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m or h:
        parts.append(f"{m}m")
    parts.append(f"{sec}s")
    return " ".join(parts)


def _fetch_ops(year: int | None, since_date: str) -> list[dict]:
    """
    Return all listOperations entries for bpts tasks whose createTime >= since_date
    (YYYY-MM-DD string in UTC).  If year is given, also filter by description prefix.
    """
    prefix = f"bpts_{year}_" if year is not None else "bpts_"
    ops = ee.data.listOperations()
    result = []
    for op in ops:
        meta = op.get("metadata", {})
        desc = meta.get("description", "")
        if not desc.startswith(prefix):
            continue
        create_ts = meta.get("createTime", "")
        if create_ts[:10] < since_date:
            continue
        result.append(op)
    return result


def _state_emoji(state: str) -> str:
    return {
        "PENDING":   "⏳",
        "RUNNING":   "🔄",
        "SUCCEEDED": "✅",
        "FAILED":    "❌",
        "CANCELLED": "⛔",
    }.get(state, "❓")


# ── report ───────────────────────────────────────────────────────────────────

def _build_report(
    ops: list[dict],
    year: int | None,
    since_date: str,
    poll_num: int,
    wall_start: datetime,
) -> str:
    now_utc = datetime.now(timezone.utc)
    elapsed = (now_utc - wall_start).total_seconds()

    # Aggregate states
    by_state: dict[str, list[dict]] = {}
    for op in ops:
        s = op["metadata"]["state"]
        by_state.setdefault(s, []).append(op)

    n_total     = len(ops)
    n_pending   = len(by_state.get("PENDING", []))
    n_running   = len(by_state.get("RUNNING", []))
    n_succeeded = len(by_state.get("SUCCEEDED", []))
    n_failed    = len(by_state.get("FAILED", []))
    n_cancelled = len(by_state.get("CANCELLED", []))
    n_done      = n_succeeded + n_failed + n_cancelled

    year_label = str(year) if year is not None else "all years"
    lines = [
        f"# bpts export watch — {year_label}",
        "",
        f"_Report generated: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}  "
        f"· Poll #{poll_num}  · Watcher running for {_fmt_duration(elapsed)}_",
        f"_Filtering tasks created on/after: {since_date}_",
        "",
        "## Summary",
        "",
        f"| State | Count |",
        f"|-------|-------|",
        f"| ⏳ Pending   | {n_pending} |",
        f"| 🔄 Running   | {n_running} |",
        f"| ✅ Succeeded | {n_succeeded} |",
        f"| ❌ Failed    | {n_failed} |",
        f"| ⛔ Cancelled | {n_cancelled} |",
        f"| **Total**   | **{n_total}** |",
        "",
    ]

    # Collect per-task rows for all states
    rows = []
    for op in ops:
        meta   = op["metadata"]
        desc   = meta["description"]
        state  = meta["state"]
        create = _parse_iso(meta.get("createTime", ""))
        start  = _parse_iso(meta.get("startTime", ""))
        end    = _parse_iso(meta.get("endTime", ""))

        # Duration: if done use start→end; if running use start→now
        if start and end:
            dur = _fmt_duration((end - start).total_seconds())
        elif start and state == "RUNNING":
            dur = _fmt_duration((now_utc - start).total_seconds()) + " ▶"
        else:
            dur = "—"

        wait = (
            _fmt_duration((start - create).total_seconds())
            if start and create
            else "—"
        )

        progress = meta.get("progress")
        prog_str = f"{progress*100:.1f}%" if progress is not None else "—"

        error_msg = op.get("error", {}).get("message", "")
        eecu = meta.get("batchEecuUsageSeconds")
        eecu_str = f"{eecu/3600:.2f} h" if eecu else "—"

        rows.append({
            "desc":      desc,
            "state":     state,
            "create":    create.strftime("%H:%M:%S") if create else "—",
            "wait":      wait,
            "duration":  dur,
            "progress":  prog_str,
            "eecu":      eecu_str,
            "error":     error_msg,
        })

    # Sort: running first, then pending, then succeeded, then failed
    order = {"RUNNING": 0, "PENDING": 1, "SUCCEEDED": 2, "FAILED": 3, "CANCELLED": 4}
    rows.sort(key=lambda r: (order.get(r["state"], 9), r["desc"]))

    # ── Running tasks section ─────────────────────────────────────────────────
    running_rows = [r for r in rows if r["state"] == "RUNNING"]
    if running_rows:
        lines += ["## Running tasks", ""]
        lines += [
            "| Task | Start (UTC) | Elapsed | Progress | EECU |",
            "|------|-------------|---------|----------|------|",
        ]
        for r in running_rows:
            lines.append(
                f"| `{r['desc']}` | {r['create']} | {r['duration']} | {r['progress']} | {r['eecu']} |"
            )
        lines.append("")

    # ── Failed tasks section ──────────────────────────────────────────────────
    failed_rows = [r for r in rows if r["state"] == "FAILED"]
    if failed_rows:
        lines += ["## Failed tasks", ""]
        lines += [
            "| Task | Wait | Duration | EECU | Error |",
            "|------|------|----------|------|-------|",
        ]
        for r in failed_rows:
            err = r["error"].replace("|", "\\|")
            lines.append(
                f"| `{r['desc']}` | {r['wait']} | {r['duration']} | {r['eecu']} | {err} |"
            )
        lines.append("")

    # ── All tasks table ───────────────────────────────────────────────────────
    lines += ["## All tasks", ""]
    lines += [
        "| Task | State | Queued | Wait | Duration | Progress | EECU | Error |",
        "|------|-------|--------|------|----------|----------|------|-------|",
    ]
    for r in rows:
        emoji = _state_emoji(r["state"])
        err = r["error"].replace("|", "\\|")[:80]
        lines.append(
            f"| `{r['desc']}` | {emoji} {r['state']} | {r['create']} | {r['wait']} "
            f"| {r['duration']} | {r['progress']} | {r['eecu']} | {err} |"
        )

    return "\n".join(lines) + "\n"


# ── main loop ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Watch GEE bpts export tasks and write a Markdown report."
    )
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument(
        "--since",
        default=None,
        help="Only include tasks created on/after this date (YYYY-MM-DD, default: today UTC).",
    )
    parser.add_argument(
        "--interval", type=int, default=60,
        help="Poll interval in seconds (default: 60).",
    )
    parser.add_argument(
        "--output", default=None,
        help="Path for the Markdown report (default: bpts_<year>_watch.md in repo root).",
    )
    parser.add_argument("--project", default=None)
    args = parser.parse_args()

    ee.Initialize(project=args.project or C.GEE_PROJECT)

    since_date = args.since or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    year_tag   = str(args.year) if args.year is not None else "all"
    out_path   = Path(args.output) if args.output else Path(f"bpts_{year_tag}_watch.md")
    wall_start = datetime.now(timezone.utc)

    print(f"Watching bpts tasks (year={year_tag}, since={since_date})")
    print(f"Report → {out_path.resolve()}")
    print(f"Poll interval: {args.interval}s  |  Ctrl+C to stop\n")

    poll_num = 0
    try:
        while True:
            poll_num += 1
            ops = _fetch_ops(args.year, since_date)

            # Terminal summary
            by_state = {}
            for op in ops:
                s = op["metadata"]["state"]
                by_state[s] = by_state.get(s, 0) + 1
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            summary = "  ".join(f"{s}={n}" for s, n in sorted(by_state.items()))
            print(f"[{ts}] poll #{poll_num}: {len(ops)} tasks — {summary}")

            report = _build_report(ops, args.year, since_date, poll_num, wall_start)
            out_path.write_text(report, encoding="utf-8")

            # Stop if all tasks are terminal (no PENDING or RUNNING)
            active = by_state.get("PENDING", 0) + by_state.get("RUNNING", 0)
            if ops and active == 0:
                print(f"\nAll {len(ops)} tasks finished. Report saved to {out_path.resolve()}")
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\nStopped. Report at: {out_path.resolve()}")


if __name__ == "__main__":
    main()
