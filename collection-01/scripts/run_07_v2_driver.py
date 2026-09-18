#!/usr/bin/env python
"""run_07_v2_driver.py — the unattended supervisor for the step-07 `_v2` re-export.

ROADMAP.md "Now — re-export the products as v2" is three branches whose steps are gated on each
other, and the gates are hours apart:

    A1 07a  month of burn, 27 GEE tasks          (comahue / mapbiomas-argentina)
    A2 07d  the nine subproducts, 9 GEE tasks    gated on ALL 27 month assets existing
    B  07e  the fire-object polygon layer, 1 task, then --verify, then --set-props   (gmail)
    C1 07b  the calendar scars, local, two passes: 28 fire-years then 27 calendar years
    C2 --   validate the 27 zips                 gated on C1
    C3 07c  the three scar rasters, 3 GEE tasks  gated on Iván's MANUAL ingest of the 27 zips

`sleep`-and-then-launch cannot survive a power cut, so this does not sleep.  Every invocation is
one TICK: it reads the state of the WORLD (assets on the server, files on disk, processes running),
does whatever is now unblocked, writes a status file and exits.  Run it from cron every 15 min —
cron starts at boot without a login, so the only thing a power cut costs is the time the box is
off.  GEE tasks are unaffected either way: once submitted they run server-side.

Everything it invokes is already idempotent (the workflow scripts skip an existing asset or an
in-flight task; `run_07_scars.sh` skips a finished year), so a tick that repeats work done by the
tick before it is a no-op, and a tick interrupted halfway is retried by the next one.

    collection-01/scripts/run_07_v2_driver.py [--once] [--dry-run] [--status]

State lives in `collection-01/logs/v2-driver/`:
    tick.log        every action, appended
    STATUS.md       the human-readable board — `cat` this first
    <stage>.done    stage markers (delete one to force that stage to run again)
    <stage>.tries   resubmission counter; a stage that has burned MAX_TRIES stops and shouts
    mob-progress.json  last tick's work-unit reading per in-flight 07a task — the stall watchdog's
                    only memory, because GEE serves a task's CURRENT progress but no history

A task that is RUNNING is not necessarily progressing: `mob_2002` sat 37 h at 14/18 work units in
Sep 2026 while every healthy year finished in 42-54 min.  `mob_stall_survey` diffs each tick's
reading against the last one and `cancel_wedged_mob` breaks a year that has been flat for
STALL_H, so one server-side stall no longer holds the whole pipeline until someone wakes up.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "collection-01"))

import ee  # noqa: E402
import utils.constants as C  # noqa: E402

PYTHON = os.environ.get("PYTHON", "/home/ivan/.venvs/gee/bin/python")
CRED_DIR = Path.home() / ".config/earthengine"
COMAHUE = ["--credentials", str(CRED_DIR / "credentials.comahue"),
           "--project", "mapbiomas-argentina"]
GMAIL = ["--credentials", str(CRED_DIR / "credentials.gmail"),
         "--project", C.GEE_PROJECT]

STATE = ROOT / "collection-01/logs/v2-driver"
BLAUNCH = STATE / "B-export.launched"   # mtime = when stage_B last submitted 07e's export
TICKLOG = STATE / "tick.log"
STATUS = STATE / "STATUS.md"
HEARTBEAT = STATE / "last_tick"     # mtime = the last tick that completed, however it went
MAX_TRIES = 8                     # a stage that has failed this often stops and shouts

N_CAL = len(C.CALENDAR_YEARS)     # 27
N_FIRE = 28                       # fire-years with a SNIC raster dir
PIX_CACHE = ROOT / "collection-01/data/scars-pixels-cache"
ZIP_DIR = ROOT / "collection-01/data/scars-upload-cache"
SCARS_SH = ROOT / "collection-01/scripts/run_07_scars.sh"

DRY = False


# ---------------------------------------------------------------------------
# plumbing
# ---------------------------------------------------------------------------
def log(msg):
    line = f"{dt.datetime.now():%F %T}  {msg}"
    print(line, flush=True)
    STATE.mkdir(parents=True, exist_ok=True)
    with TICKLOG.open("a") as fh:
        fh.write(line + "\n")


def marker(name):
    return STATE / f"{name}.done"


def done(name):
    return marker(name).exists()


def mark(name, note=""):
    marker(name).write_text(f"{dt.datetime.now():%F %T}  {note}\n")


def paused(name):
    """True when `<stage>.pause` exists — that stage is skipped entirely this tick.

    Deliberately NOT done by writing a `<stage>.done`.  A `.done` asserts the stage SUCCEEDED, and
    a marker that claims a success which never happened is the exact bug this project hit three
    times in Sep 2026 (stale `B.done`; the zip gate exiting 1 after passing; `stage_B` gated on its
    own stamp).  A pause is a different fact — "deprioritised, work not done" — so it gets its own
    file, is visible on the board as ⏸, and is undone by deleting it.

    Written by a human (or by whoever deprioritises the branch); the driver never creates one.
    Put the reason in the file: the board prints its first line.
    """
    return (STATE / f"{name}.pause").exists()


def pause_reason(name):
    p = STATE / f"{name}.pause"
    try:
        return (p.read_text().strip().splitlines() or [""])[0]
    except Exception:
        return ""


def tries(name, bump=False):
    p = STATE / f"{name}.tries"
    n = int(p.read_text().strip()) if p.exists() else 0
    if bump:
        n += 1
        p.write_text(str(n))
    return n


def run(name, argv, timeout=3600):
    """Run a command, tee its output to a per-stage log, return the exit code."""
    out = STATE / f"{name}.out"
    log(f"[{name}] RUN {' '.join(str(a) for a in argv)}")
    if DRY:
        return 0
    tries(name, bump=True)
    with out.open("a") as fh:
        fh.write(f"\n===== {dt.datetime.now():%F %T}  {' '.join(str(a) for a in argv)}\n")
        fh.flush()
        try:
            rc = subprocess.call(argv, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT,
                                 timeout=timeout)
        except subprocess.TimeoutExpired:
            fh.write("*** TIMED OUT ***\n")
            rc = 124
    log(f"[{name}] rc={rc}  (log: {out})")
    return rc


def spawn(name, argv):
    """Launch a long local job detached, so the tick returns immediately."""
    out = STATE / f"{name}.out"
    log(f"[{name}] SPAWN {' '.join(str(a) for a in argv)}")
    if DRY:
        return
    tries(name, bump=True)
    fh = out.open("a")
    fh.write(f"\n===== {dt.datetime.now():%F %T}  {' '.join(str(a) for a in argv)}\n")
    fh.flush()
    subprocess.Popen(argv, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT,
                     start_new_session=True)


def ensure_mem_monitor():
    """Keep `mem_monitor.sh` alongside the local passes (docs/05 "Run").  Memory, not CPU, is the
    binding constraint on the `scars` pass, and an OOM shows up as a bare rc=137 in the launcher
    log with nothing to explain it."""
    if running("mem_monitor.sh"):
        return
    log("[mem] starting mem_monitor.sh")
    if DRY:
        return
    subprocess.Popen(["bash", str(ROOT / "collection-01/scripts/mem_monitor.sh"),
                      str(STATE / "mem_monitor.log"), "30", "2048"],
                     cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def running(pattern):
    return subprocess.call(["pgrep", "-f", pattern],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


# ---------------------------------------------------------------------------
# the world
# ---------------------------------------------------------------------------
# Which compute project each stage's tasks live in.  CLAUDE.md: `listOperations()` is
# PROJECT-scoped, so a one-project watcher reports the other account's task as MISSING — which is
# indistinguishable from never having submitted it, and would make this driver resubmit a job
# that is already running (or, once the retry budget is spent, declare a healthy 3 h export dead).
ARG_PROJECT = "mapbiomas-argentina"          # comahue submits here: 07a, 07d
FIRE_PROJECT = C.GEE_PROJECT                 # gmail submits here:   07e, 07c
# 07c moved to comahue/ARG_PROJECT on 15 Sep: the gmail queue and the fire project are needed for
# the statistics exports (`MBFUEGO_ARG_COL1-*`), which write to GCS — comahue has no access there.
TASK_PROJECT = {"mob_": ARG_PROJECT, "arg07d_": ARG_PROJECT,
                "arg07e_": FIRE_PROJECT, "arg07c_": ARG_PROJECT}


def init_ee(account="comahue", project=ARG_PROJECT):
    st = json.loads((CRED_DIR / f"credentials.{account}").read_text())
    from google.oauth2.credentials import Credentials
    ee.Initialize(Credentials(
        None, refresh_token=st["refresh_token"], token_uri=ee.oauth.TOKEN_URI,
        client_id=st.get("client_id", ee.oauth.CLIENT_ID),
        client_secret=st.get("client_secret", ee.oauth.CLIENT_SECRET),
        scopes=st.get("scopes", ee.oauth.SCOPES),
        quota_project_id=st.get("project"),
    ), project=project)


def n_assets(parent):
    try:
        return len(ee.data.listAssets({"parent": parent}).get("assets", []))
    except ee.EEException:
        return 0                    # the container does not exist yet


def asset_exists(asset_id):
    try:
        ee.data.getAsset(asset_id)
        return True
    except ee.EEException:
        return False


_OPS = {}


def fetch_ops():
    """Pull the PENDING/RUNNING task list of BOTH compute projects, once per tick.

    ~13 s for `mapbiomas-argentina` (9.8 k operations) and a second or two for the fire project.
    Both lists are cross-user — the fire project holds the whole network's work — so every match
    below is on OUR namespaced prefix, never a bare product name.
    """
    for account, project in (("comahue", ARG_PROJECT), ("gmail", FIRE_PROJECT)):
        init_ee(account, project)
        # Keep the operation NAME alongside the metadata: `cancelOperation` addresses a task by
        # name, and the stall watchdog below is the only thing that can free a wedged year.
        _OPS[project] = [dict(o.get("metadata", {}), _name=o.get("name"))
                         for o in ee.data.listOperations()]
    init_ee("comahue", ARG_PROJECT)      # leave the session on the project the assets live in


def inflight(prefix):
    """Descriptions of PENDING/RUNNING tasks starting with `prefix`, in the project that
    prefix's tasks are actually submitted to."""
    return [m.get("description") for m in _OPS.get(TASK_PROJECT[prefix], [])
            if m.get("state") in ("PENDING", "RUNNING")
            and str(m.get("description", "")).startswith(prefix)]


def _epoch(ts):
    """RFC3339 -> epoch seconds.  Trims over-long fractional seconds, which GEE emits and
    `fromisoformat` rejects, and which also make a plain string compare unsafe."""
    if not ts:
        return None
    ts = ts.replace("Z", "+00:00")
    if "." in ts:
        head, rest = ts.split(".", 1)
        frac, tz = rest[:-6], rest[-6:]
        ts = f"{head}.{frac[:6]}{tz}"
    return dt.datetime.fromisoformat(ts).timestamp()


MOBPROG = STATE / "mob-progress.json"   # per-task progress history, across ticks
STALL_H = 2.5                          # flat for this long = wedged; a healthy year takes ~50 min
MAX_STALL_KILLS = 3                    # after this many, stop cancelling and shout for a human

# Which prefixes the watchdog may CANCEL, as opposed to merely report.  Only `mob_`: we have 27
# measured healthy runs for it (42-54 min each), so STALL_H is calibrated.  We have no such
# baseline for the nine subproducts or the scar rasters — `accumulated_burned` folds 27 years —
# and a threshold guessed for those would eventually kill work that was merely slow.  They are
# tracked and shown on the board, which is what a human needs at 8 a.m.; they are never cancelled.
STALL_CANCELLABLE = ("mob_",)


def _sig(m):
    """A signature of how far a task has got.  Not just `progress`: a task in its upload stage can
    sit at the same overall fraction while stage 2 moves, so fold in every stage's
    completeWorkUnits as well.  Any change at all resets the stall clock."""
    units = [str(s.get("completeWorkUnits")) for s in (m.get("stages") or [])]
    return f"{m.get('state')}|{m.get('progress')}|{'|'.join(units)}|{m.get('attempt')}"


def stall_survey():
    """Track every in-flight task of OURS across ticks and report how long each has been frozen.

    Returns `{prefix: [{desc, name, flat_h, progress}, ...]}`, one entry per PENDING/RUNNING task
    whose description carries one of our namespaced prefixes.  Other countries' tasks in the shared
    fire project are never touched, here or anywhere (CLAUDE.md).

    Why this exists.  On 12-13 Sep `mob_2002` ran 37 h stuck at 73.7 % (`progress` frozen at
    14/18 work units, `attempt: 1`) while the other 26 years each finished in 42-54 min.  It was
    a server-side stall — nothing in our code caused it and nothing in our code can prevent it.
    The only cure is cancel-and-resubmit, and until now that needed a human awake: `stage_A1`
    returns early whenever ANY task is in flight, so one wedged year silently holds A1, A2, A3,
    C3 and C4 for as long as it likes.  A supervisor that cannot tell "running" from "hung" is
    not unattended.

    Two things make this measurable.  `metadata.progress` and `stages[].completeWorkUnits` ARE
    readable per task (floats, so sub-work-unit creep shows) — but GEE keeps no history, so the
    previous tick's reading has to live on disk; that is all MOBPROG is.  And `updateTime` is NOT
    the signal: the server refreshes it on a stalled task too — the wedged 2002 op carried a fresh
    `updateTime` throughout its 37 h.  Only the work-unit count is real.

    Work units are lumpy, so a healthy task genuinely pauses at one count for minutes.  STALL_H is
    2.5 h for that reason: three times the longest healthy year, and the real wedge was flat for
    fifteen times it.
    """
    try:
        hist = json.loads(MOBPROG.read_text())
    except Exception:
        hist = {}
    now = dt.datetime.now().timestamp()
    live, out = {}, {p: [] for p in TASK_PROJECT}
    for prefix, project in TASK_PROJECT.items():
        for m in _OPS.get(project, []):
            desc = str(m.get("description", ""))
            if not desc.startswith(prefix) or m.get("state") not in ("PENDING", "RUNNING"):
                continue
            sig, prev = _sig(m), hist.get(desc)
            # `since` survives only while the signature is unchanged AND it is the same operation:
            # a resubmitted year reuses the description, and inheriting the dead task's clock would
            # make the fresh one look wedged from birth.
            since = (prev["since"] if prev and prev.get("sig") == sig
                     and prev.get("name") == m.get("_name") else now)
            live[desc] = {"sig": sig, "since": since, "name": m.get("_name")}
            out[prefix].append({"desc": desc, "name": m.get("_name"),
                                "flat_h": (now - since) / 3600.0, "progress": m.get("progress")})
    if not DRY:
        MOBPROG.write_text(json.dumps(live, indent=1))
    return out


def cancel_wedged_mob(task):
    """Cancel ONE frozen month-of-burn task, so the next tick's top-up resubmits that year.

    Four assertions before anything is cancelled, because this is the one place the driver touches
    a task rather than launching one, and the compute project is shared with the whole MapBiomas
    Fuego network (CLAUDE.md): cancelling another country's export is unrecoverable for them.  The
    task must (1) be named `mob_<year>` for a year in our calendar range, (2) live under
    `projects/mapbiomas-argentina/operations/`, (3) still carry that exact description when we
    re-read it by name, and (4) still be PENDING/RUNNING at that moment — not one that finished
    while this tick was busy elsewhere.
    """
    desc, name = task["desc"], task["name"]
    year = desc[4:]
    if not (year.isdigit() and int(year) in C.CALENDAR_YEARS):
        log(f"[A1-stall] refusing to cancel {desc!r} — not a mob_<calendar year> task")
        return False
    if not name or not name.startswith(f"projects/{ARG_PROJECT}/operations/"):
        log(f"[A1-stall] refusing to cancel {desc!r} — operation {name!r} is not in {ARG_PROJECT}")
        return False
    init_ee("comahue", ARG_PROJECT)
    try:
        fresh = (ee.data.getOperation(name) or {}).get("metadata", {})
    except Exception as exc:
        log(f"[A1-stall] could not re-read {desc} ({name}): {type(exc).__name__}: {exc}")
        return False
    if str(fresh.get("description", "")) != desc:
        log(f"[A1-stall] refusing to cancel {name} — description is "
            f"{fresh.get('description')!r}, not {desc!r}")
        return False
    if fresh.get("state") not in ("PENDING", "RUNNING"):
        log(f"[A1-stall] {desc} is now {fresh.get('state')} — nothing to cancel")
        return False
    log(f"[A1-stall] ⚠ {desc} frozen for {task['flat_h']:.1f} h at progress={task['progress']} "
        f"— cancelling {name} (kill {tries('A1-stall') + 1}/{MAX_STALL_KILLS}); "
        f"the next tick resubmits that year")
    if DRY:
        return True
    tries("A1-stall", bump=True)
    try:
        ee.data.cancelOperation(name)
    except Exception as exc:
        log(f"[A1-stall] cancel FAILED: {type(exc).__name__}: {exc}")
        return False
    return True


def last_success_end(prefix):
    """Epoch end time of the most recent SUCCEEDED task with `prefix`, or None."""
    ends = [_epoch(m.get("endTime")) for m in _OPS.get(TASK_PROJECT[prefix], [])
            if m.get("state") == "SUCCEEDED"
            and str(m.get("description", "")).startswith(prefix)
            and m.get("endTime")]
    return max(ends) if ends else None


# ---------------------------------------------------------------------------
# "built with the CURRENT rules", not "exists"
# ---------------------------------------------------------------------------
# The first _v2 run went out with the UNCONFINED rule A (it deleted two thirds of the Delta
# del Paraná), so 19 month assets and the polygon layer exist and are WRONG.  Everything here
# is therefore re-launched with `--overwrite`, and an asset only counts as done when it
# carries the CURRENT `exclusion_rule_a` text.  Counting existence instead would let a tick
# read a half-overwritten collection as complete — the same trap docs/07 records for the v1
# markers, one level up: ANYTHING GATED ON A THING THE PREVIOUS RUN COULD ALSO HAVE WRITTEN
# is not a gate.
RULE_A_TEXT = C.exclusion_rules()["exclusion_rule_a"]


def month_years_current():
    """Calendar years whose month-of-burn asset carries the rule text we are building now.

    Returns the YEARS, not a count, because stage_A1 needs to know WHICH are missing: a
    relaunch that redoes the years already done is a 24 h round trip to fix one of them.
    """
    try:
        idx = (ee.ImageCollection(C.MONTH_OF_BURN_COL)
               .filter(ee.Filter.eq("exclusion_rule_a", RULE_A_TEXT))
               .aggregate_array("system:index").getInfo()) or []
    except ee.EEException:
        return set()
    out = set()
    for i in idx:
        tail = str(i)[-4:]
        if tail.isdigit():
            out.add(int(tail))
    return out


def poly_landed():
    """True when the polygon layer on the server is the output of THIS run — stamped or not.

    NOT just "carries the current rule A".  `Export.table.toAsset` REPLACES the asset, so a
    fresh export lands with an EMPTY property block; the rule text is written afterwards by
    `--set-props`, deliberately (07e::properties — "a property block is not worth risking a
    multi-hour table task on").  Gating the stamping step on the stamp is a deadlock, and it
    fired: at 17:30 on 12 Sep the driver relaunched a 9 h export over a layer that had landed
    correctly at 17:20, and would have kept doing so until MAX_TRIES without ever running
    --verify.

    So there are two ways to be landed.  Either it already carries the current rule text (it
    has been through --set-props), or its updateTime is at/after the end of an arg07e_ export
    that SUCCEEDED after we submitted one — which is what BLAUNCH's mtime records.  The
    BLAUNCH bound is what keeps the BROKEN run's asset from qualifying: that one was also the
    output of a successful export, just an older one.
    """
    try:
        a = ee.data.getAsset(f"{C.FINAL_PRODUCTS}/burned_area_polygons_v{C.PRODUCT_VERSION}")
    except ee.EEException:
        return False
    if (a.get("properties") or {}).get("exclusion_rule_a") == RULE_A_TEXT:
        return True
    if not BLAUNCH.exists():
        return False
    end = last_success_end("arg07e_")
    upd = _epoch(a.get("updateTime"))
    if not end or not upd or end < BLAUNCH.stat().st_mtime:
        return False
    return upd >= end - 120          # the asset is that export's output


def n_pixels_done():
    return len(list(PIX_CACHE.glob(".done_fy*"))) if PIX_CACHE.exists() else 0


def n_zips():
    return len(list(ZIP_DIR.glob("scars_*.zip"))) if ZIP_DIR.exists() else 0


# ---------------------------------------------------------------------------
# the stages
# ---------------------------------------------------------------------------
def stage_A1(st):
    """07a — 27 month-of-burn tasks, as comahue, with --overwrite.  The script skips an
    in-flight task, so re-invoking it is how a FAILED year gets resubmitted; `st["mob"]`
    counts only assets stamped with the CURRENT rule A, so a leftover from the first _v2
    run can never read as done."""
    if st["mob"] >= N_CAL:
        if not done("A1"):
            mark("A1", f"{st['mob']}/{N_CAL} month assets")
            log("[A1] COMPLETE — 27/27 month-of-burn assets")
        return
    if st["mob_inflight"]:
        # "In flight" is not the same as "progressing".  A wedged year holds this stage — and
        # therefore A2, A3, C3 and C4 — indefinitely, so before returning, check whether any of
        # those tasks has stopped moving and break it if so (mob_stall_survey).
        wedged = [t for t in st["stall"]["mob_"] if t["flat_h"] >= STALL_H]
        if wedged and tries("A1-stall") >= MAX_STALL_KILLS:
            log(f"[A1-stall] ⚠ STOPPED — {MAX_STALL_KILLS} tasks already cancelled for stalling "
                f"and {[t['desc'] for t in wedged]} is frozen again. This is no longer a GEE "
                f"lottery; a human must look at it.")
            return
        for t in wedged:
            cancel_wedged_mob(t)    # the NEXT tick sees no task in flight and tops that year up
        return                      # tasks are running; nothing else to do
    if tries("A1") >= MAX_TRIES:
        log(f"[A1] ⚠ STOPPED after {MAX_TRIES} submissions with {st['mob']}/{N_CAL} landed "
            f"— needs a human")
        return
    # --overwrite: an existing month asset from the first _v2 run carries the unconfined rule A
    # and must be REPLACED in place, not skipped as "already there".
    #
    # But submit ONLY the years that are actually missing.  `--all --overwrite` re-exports the
    # years already done too, so a top-up after ONE year got stuck would redo the other 26 --
    # ~24 h to repair ~50 min of work, and it would tear down 26 good assets to do it.  That is
    # what forced a hand-pause on 13 Sep when mob_2002 wedged at 26/27.
    missing = [y for y in C.CALENDAR_YEARS if y not in st["mob_years"]]
    if len(missing) == N_CAL:
        run("A1", [PYTHON, "collection-01/workflow/07-month_of_burn.py",
                   "--all", "--launch", "--overwrite", *COMAHUE], timeout=5400)
        return
    log(f"[A1] topping up {len(missing)} missing year(s): {missing}")
    for y in missing:
        run("A1", [PYTHON, "collection-01/workflow/07-month_of_burn.py",
                   "--year", str(y), "--launch", "--overwrite", *COMAHUE], timeout=1800)


def stage_A2(st):
    """07d — the nine subproducts.  MUST NOT start before all 27 month assets exist (docs/07
    §12.7): this is an asset-existence test, which is exactly why it can be automated."""
    if done("A2"):
        return
    if st["mob"] < N_CAL:
        return
    if st["d_inflight"]:
        return
    if tries("A2") >= MAX_TRIES:
        log(f"[A2] ⚠ STOPPED after {MAX_TRIES} submissions — needs a human")
        return
    if run("A2", [PYTHON, "collection-01/workflow/07-subproducts.py",
                  "--launch", *COMAHUE], timeout=5400) == 0:
        mark("A2", "9 subproduct tasks submitted")


def stage_B(st):
    """07e — the polygon layer, on the OTHER account so it runs beside A1: launch, then the
    --verify gate, then --set-props."""
    if done("B"):
        return
    if not st["poly"]:
        if st["e_inflight"]:
            return
        if tries("B") >= MAX_TRIES:
            log(f"[B] ⚠ STOPPED after {MAX_TRIES} submissions — needs a human")
            return
        if run("B", [PYTHON, "collection-01/workflow/07-burned_area_polygons.py",
                     "--launch", "--overwrite", *GMAIL], timeout=3600) == 0:
            BLAUNCH.touch()     # poly_landed() dates "ours" from here
        return
    # it landed — gate it, then stamp it.  st["poly"] is poly_landed(), so we get here on the
    # tick after the export succeeds, with the property block still empty; --verify is what
    # decides whether that asset deserves the stamp.
    if tries("B-verify") >= MAX_TRIES:
        log(f"[B] ⚠ STOPPED — --verify has failed {MAX_TRIES} times on the landed layer; "
            f"see B-verify.out. v1 took three submissions for exactly this reason (docs/07 §13.6)")
        return
    if run("B-verify", [PYTHON, "collection-01/workflow/07-burned_area_polygons.py",
                        "--verify", *GMAIL], timeout=7200) != 0:
        log("[B] ⚠ --verify FAILED on the landed layer — see B-verify.out")
        return
    if run("B-props", [PYTHON, "collection-01/workflow/07-burned_area_polygons.py",
                       "--set-props", *GMAIL], timeout=3600) == 0:
        mark("B", "exported, verified, properties set")
        log("[B] COMPLETE")


def stage_C1(st):
    """07b — the local scar build, two passes.  `pixels` must finish for ALL 28 fire-years
    before any `scars` year starts: a calendar year needs BOTH of its fire-years, and a mix of
    v1 and v2 pixel caches would silently build a scar layer from two different selections."""
    if done("C1"):
        return
    ensure_mem_monitor()
    if running("run_07_scars.sh"):
        return
    if st["pix"] < N_FIRE:
        if tries("C1-pixels") >= MAX_TRIES:
            log(f"[C1] ⚠ STOPPED — the pixels pass has been relaunched {MAX_TRIES} times and is "
                f"still at {st['pix']}/{N_FIRE}; see collection-01/logs/07_pixels_<year>.log")
            return
        spawn("C1-pixels", ["bash", str(SCARS_SH), "pixels", "-j", "5"])
        return
    if st["zips"] < N_CAL:
        if tries("C1-scars") >= MAX_TRIES:
            log(f"[C1] ⚠ STOPPED — the scars pass has been relaunched {MAX_TRIES} times and is "
                f"still at {st['zips']}/{N_CAL}; see collection-01/logs/07_scars_<year>.log")
            return
        env = dict(os.environ, OBJ_CORES="6")
        log("[C1] pixels 28/28 — starting the scars pass")
        if not DRY:
            tries("C1-scars", bump=True)
            fh = (STATE / "C1-scars.out").open("a")
            fh.write(f"\n===== {dt.datetime.now():%F %T}  scars -j 2 OBJ_CORES=6\n")
            fh.flush()
            subprocess.Popen(["bash", str(SCARS_SH), "scars", "-j", "2"], cwd=ROOT, env=env,
                             stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
        return
    mark("C1", f"{st['pix']}/{N_FIRE} pixel caches, {st['zips']}/{N_CAL} zips")
    log("[C1] COMPLETE — 27/27 scar packages built")


def stage_C2(st):
    """Gate the 27 zips before they are handed over for the manual ingest."""
    if done("C2") or not done("C1"):
        return
    if run("C2", [PYTHON, "collection-01/scripts/validate_scar_zips.py"], timeout=3600) == 0:
        mark("C2", "27/27 zips validated — READY FOR IVÁN'S MANUAL INGEST")
        log("[C2] COMPLETE — the zips are gated and ready to ingest")


def stage_A3(st):
    """Once the nine subproducts have landed, leave an audit on disk for Monday morning: the
    band bookkeeping + ROI counts (`--check`) and the property-block audit, which is a DRY RUN —
    `audit_product_properties.py` only writes with `--apply`.  Neither touches a pixel."""
    if done("A3") or st["subproducts"] < 9:
        return
    run("A3-check", [PYTHON, "collection-01/workflow/07-subproducts.py", "--check", *GMAIL],
        timeout=7200)
    run("A3-props", [PYTHON, "collection-01/scripts/audit_product_properties.py"], timeout=3600)
    mark("A3", "subproducts checked + property block audited (READ A3-*.out)")
    log("[A3] the nine subproducts are audited — read A3-check.out and A3-props.out")


def stage_C4(st):
    """Same for the three scar rasters: the scar-vs-month agreement check on the Chaco box
    (docs/07 §9.1). Whole-country is one reduceRegion per year and far too slow to run blind."""
    if done("C4") or st["scar_rasters"] < 3:
        return
    run("C4-check", [PYTHON, "collection-01/workflow/07-scar_rasters.py", "--check",
                     "--years", "2003,2020", "--roi=-61.6,-25.6,-61.1,-25.1", *COMAHUE],
        timeout=7200)
    mark("C4", "scar rasters checked against the month mask (READ C4-check.out)")
    log("[C4] the three scar rasters are checked — read C4-check.out")


def stage_C3(st):
    """07c — the three scar rasters.  TWO gates, not one: the 27 v2 scar FCs must be ingested by
    hand into `annual_burned_vectors_v2`, AND all 27 v2 month-of-burn assets must exist — the
    month image supplies the mask that forces scar and month coverage to agree (docs/07 §9), so
    07c painted against a partial 07a is a partial product.  The script re-checks both itself and
    aborts, so an early tick costs nothing but a wasted try."""
    if done("C3"):
        return
    if st["scarfc"] < N_CAL or st["mob"] < N_CAL:
        return
    if st["c_inflight"]:
        return
    if tries("C3") >= MAX_TRIES:
        log(f"[C3] ⚠ STOPPED after {MAX_TRIES} submissions — needs a human")
        return
    if run("C3", [PYTHON, "collection-01/workflow/07-scar_rasters.py",
                  "--launch", *COMAHUE], timeout=3600) == 0:
        mark("C3", "3 scar-raster tasks submitted")


# ---------------------------------------------------------------------------
def survey():
    fetch_ops()
    stall = stall_survey()          # must run every tick: it is what dates the next tick's clock
    mob_years = month_years_current()
    fp = {a["id"].split("/")[-1]
          for a in ee.data.listAssets({"parent": C.FINAL_PRODUCTS}).get("assets", [])}
    subs = ["monthly_burned", "annual_burned", "monthly_burned_coverage",
            "annual_burned_coverage", "frequency_burned", "frequency_burned_coverage",
            "accumulated_burned", "accumulated_burned_coverage", "year_last_fire"]
    scar_subs = ["annual_burned_id", "annual_burned_area_ha", "annual_burned_scar_size_range"]
    return {
        "mob": len(mob_years),
        "mob_years": mob_years,
        "mob_inflight": inflight("mob_"),
        "stall": stall,
        "d_inflight": inflight("arg07d_"),
        "e_inflight": inflight("arg07e_"),
        "c_inflight": inflight("arg07c_"),
        "subproducts": sum(C.product_name(s) in fp for s in subs),
        "scar_rasters": sum(C.product_name(s) in fp for s in scar_subs),
        "poly": poly_landed(),
        "scarfc": n_assets(C.ANNUAL_BURNED_VECTORS),
        "pix": n_pixels_done(),
        "zips": n_zips(),
    }


def health(st, prefix):
    """How a stage's in-flight tasks are actually doing, for the board.

    "1 task in flight" was the whole content of the A1 cell for the 37 h `mob_2002` was wedged, and
    it read identically to a healthy run.  Say the progress and how long it has been flat, so the
    person reading this at 8 a.m. can tell slow from hung without opening a Python shell."""
    tasks = (st.get("stall") or {}).get(prefix) or []
    bits = []
    for t in sorted(tasks, key=lambda t: t["desc"]):
        pct = f"{100 * t['progress']:.0f}%" if t["progress"] is not None else "?"
        flag = (" ⚠ WEDGED" if t["flat_h"] >= STALL_H else "") if prefix in STALL_CANCELLABLE \
            else (" ⚠ FLAT — check it" if t["flat_h"] >= STALL_H else "")
        bits.append(f"`{t['desc']}` {pct}, flat {t['flat_h'] * 60:.0f} min{flag}")
    return " — " + "; ".join(bits) if bits else ""


def write_status(st):
    def tick(ok, name=None):
        if name and paused(name):
            return "⏸"
        return "✅" if ok else "⏳"
    lines = [
        "# step-07 `_v2` re-export — driver status",
        "",
        f"_last tick {dt.datetime.now():%F %T}_ — `collection-01/logs/v2-driver/`. "
        f"The supervisor ticks every 15 min from cron: **if that stamp is more than ~20 min old "
        f"it is not running** (`crontab -l`, then `cron.log`).",
        "",
        "| | stage | state | detail |",
        "|---|---|---|---|",
        f"| A1 | 07a month of burn | {tick(st['mob'] >= N_CAL)} | "
        f"{st['mob']}/{N_CAL} assets, {len(st['mob_inflight'])} task(s) in flight"
        f"{health(st, 'mob_')} |",
        f"| A2 | 07d nine subproducts | {tick(st['subproducts'] == 9, 'A2')} | "
        f"{st['subproducts']}/9 assets, {len(st['d_inflight'])} in flight"
        f"{' — ⏸ PAUSED: ' + pause_reason('A2') if paused('A2') else ''}"
        f"{' — GATED on A1' if st['mob'] < N_CAL else ''}{health(st, 'arg07d_')} |",
        f"| A3 | 07d audit | {tick(done('A3'), 'A3')} | "
        f"`--check` + property audit, once the nine land — read `A3-*.out` |",
        f"| B | 07e polygon layer | {tick(done('B'))} | "
        f"asset {'exists' if st['poly'] else 'not yet'}, {len(st['e_inflight'])} in flight, "
        f"verified={done('B')} |",
        f"| C1 | 07b local scars | {tick(done('C1'))} | "
        f"pixels {st['pix']}/{N_FIRE}, zips {st['zips']}/{N_CAL} |",
        f"| C2 | zip gate | {tick(done('C2'))} | validate_scar_zips.py |",
        f"| C3 | 07c scar rasters | {tick(st['scar_rasters'] == 3)} | "
        f"{st['scar_rasters']}/3 assets; ingested scar FCs {st['scarfc']}/{N_CAL}"
        f"{' — WAITING FOR THE MANUAL INGEST' if st['scarfc'] < N_CAL else ''}"
        f"{' — GATED on A1 (07c masks to the v2 month of burn)' if st['mob'] < N_CAL else ''}"
        f"{health(st, 'arg07c_')} |",
        f"| C4 | 07c check | {tick(done('C4'))} | "
        f"scar-vs-month agreement on the Chaco box — read `C4-check.out` |",
        "",
    ]
    if done("C2") and st["scarfc"] < N_CAL:
        lines += [
            "## ⚠ Waiting on you",
            "",
            f"The 27 zips in `collection-01/data/scars-upload-cache/` are built and gated.",
            f"Ingest them by hand as `{C.ANNUAL_BURNED_VECTORS}/scars_<Y>`, set",
            "`exclusion_rule_a` / `exclusion_rule_b` on each FC, and the next tick launches 07c",
            "on its own. Then `$PYTHON collection-01/scripts/validate_scar_zips.py --ingested`.",
            "",
        ]
    stuck = [n for n in ("A1", "A2", "B", "B-verify", "C1-pixels", "C1-scars", "C3")
             if tries(n) >= MAX_TRIES and not done(n.split("-")[0])]
    if stuck:
        lines += [f"## ⚠ Stopped after {MAX_TRIES} attempts: {', '.join(stuck)}", "",
                  "See the matching `*.out` in `collection-01/logs/v2-driver/`.", ""]
    STATUS.write_text("\n".join(lines))


def staleness_line():
    """A board nobody can date is worse than no board.  The supervisor ticks every 15 min, so
    anything older than ~20 min means it is NOT running — which otherwise looks exactly like
    `nothing has changed yet`."""
    if not HEARTBEAT.exists():
        return "⚠ no heartbeat file — the driver has never finished a tick."
    age = (dt.datetime.now().timestamp() - HEARTBEAT.stat().st_mtime) / 60
    if age <= 20:
        return f"(last tick {age:.0f} min ago — the supervisor is ticking)"
    return (f"⚠ LAST TICK WAS {age:.0f} MIN AGO — the supervisor is NOT running. "
            f"Check `crontab -l` and {STATE / 'cron.log'}")


def main():
    global DRY
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="survey and write STATUS.md, but run nothing")
    ap.add_argument("--status", action="store_true",
                    help="print STATUS.md and exit (no server calls)")
    args = ap.parse_args()

    if args.status:
        if not STATUS.exists():
            print("no status yet — the driver has not completed a tick. "
                  "Check `crontab -l` and collection-01/logs/v2-driver/cron.log")
            return
        print(STATUS.read_text())
        print(staleness_line())
        return
    DRY = args.dry_run
    STATE.mkdir(parents=True, exist_ok=True)

    try:
        st = survey()
    except Exception as exc:
        # A tick that dies HERE writes no board, and a board that silently stops updating reads
        # exactly like one where nothing has happened yet.  Say so on the board itself.
        log(f"[survey] ⚠ EXCEPTION {type(exc).__name__}: {exc}")
        if STATUS.exists():
            STATUS.write_text(STATUS.read_text().split("\n<!--tick-->")[0] +
                              f"\n<!--tick-->\n\n> ⚠ the tick at {dt.datetime.now():%F %T} could "
                              f"not reach Earth Engine: `{type(exc).__name__}: {exc}`. The numbers "
                              f"above are from the last tick that did. Retrying in 15 min.\n")
        HEARTBEAT.touch()          # it IS ticking; it just could not see the server
        raise

    log(f"tick  mob={st['mob']}/{N_CAL} sub={st['subproducts']}/9 poly={st['poly']} "
        f"scar_rasters={st['scar_rasters']}/3 scarfc={st['scarfc']}/{N_CAL} "
        f"pix={st['pix']}/{N_FIRE} zips={st['zips']}/{N_CAL}")

    # Publish the survey BEFORE running anything.  A stage like 07e's --verify runs synchronously
    # and can hold the tick (and the flock) for the best part of an hour; without this the board
    # keeps showing the PREVIOUS tick's numbers throughout, which is the one time someone is most
    # likely to be reading it.
    write_status(st)
    HEARTBEAT.touch()

    for stage in (stage_A1, stage_A2, stage_A3, stage_B,
                  stage_C1, stage_C2, stage_C3, stage_C4):
        name = stage.__name__.replace("stage_", "")
        if paused(name):
            continue
        try:
            stage(st)
        except Exception as exc:                       # one broken stage must not stop the rest
            log(f"[{stage.__name__}] ⚠ EXCEPTION {type(exc).__name__}: {exc}")

    write_status(st)
    HEARTBEAT.touch()


if __name__ == "__main__":
    main()
