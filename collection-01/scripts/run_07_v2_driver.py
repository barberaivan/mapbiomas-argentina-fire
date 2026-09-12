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
TICKLOG = STATE / "tick.log"
STATUS = STATE / "STATUS.md"
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
    """Keep `mem_monitor.sh` alongside the local passes (docs/05 §4.1).  Memory, not CPU, is the
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
TASK_PROJECT = {"mob_": ARG_PROJECT, "arg07d_": ARG_PROJECT,
                "arg07e_": FIRE_PROJECT, "arg07c_": FIRE_PROJECT}


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
        _OPS[project] = [o.get("metadata", {}) for o in ee.data.listOperations()]
    init_ee("comahue", ARG_PROJECT)      # leave the session on the project the assets live in


def inflight(prefix):
    """Descriptions of PENDING/RUNNING tasks starting with `prefix`, in the project that
    prefix's tasks are actually submitted to."""
    return [m.get("description") for m in _OPS.get(TASK_PROJECT[prefix], [])
            if m.get("state") in ("PENDING", "RUNNING")
            and str(m.get("description", "")).startswith(prefix)]


def n_pixels_done():
    return len(list(PIX_CACHE.glob(".done_fy*"))) if PIX_CACHE.exists() else 0


def n_zips():
    return len(list(ZIP_DIR.glob("scars_*.zip"))) if ZIP_DIR.exists() else 0


# ---------------------------------------------------------------------------
# the stages
# ---------------------------------------------------------------------------
def stage_A1(st):
    """07a — 27 month-of-burn tasks, as comahue.  The script itself skips an existing asset or
    an in-flight task, so re-invoking it is how a FAILED year gets resubmitted."""
    if st["mob"] >= N_CAL:
        if not done("A1"):
            mark("A1", f"{st['mob']}/{N_CAL} month assets")
            log("[A1] COMPLETE — 27/27 month-of-burn assets")
        return
    if st["mob_inflight"]:
        return                      # tasks are running; nothing to do
    if tries("A1") >= MAX_TRIES:
        log(f"[A1] ⚠ STOPPED after {MAX_TRIES} submissions with {st['mob']}/{N_CAL} landed "
            f"— needs a human")
        return
    run("A1", [PYTHON, "collection-01/workflow/07-month_of_burn.py",
               "--all", "--launch", *COMAHUE], timeout=5400)


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
        run("B", [PYTHON, "collection-01/workflow/07-burned_area_polygons.py",
                  "--launch", *GMAIL], timeout=3600)
        return
    # it landed — gate it, then stamp it
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
                  "--launch", *GMAIL], timeout=3600) == 0:
        mark("C3", "3 scar-raster tasks submitted")


# ---------------------------------------------------------------------------
def survey():
    fetch_ops()
    mob = n_assets(C.MONTH_OF_BURN_COL)
    fp = {a["id"].split("/")[-1]
          for a in ee.data.listAssets({"parent": C.FINAL_PRODUCTS}).get("assets", [])}
    subs = ["monthly_burned", "annual_burned", "monthly_burned_coverage",
            "annual_burned_coverage", "frequency_burned", "frequency_burned_coverage",
            "accumulated_burned", "accumulated_burned_coverage", "year_last_fire"]
    scar_subs = ["annual_burned_id", "annual_burned_area_ha", "annual_burned_scar_size_range"]
    return {
        "mob": mob,
        "mob_inflight": inflight("mob_"),
        "d_inflight": inflight("arg07d_"),
        "e_inflight": inflight("arg07e_"),
        "c_inflight": inflight("arg07c_"),
        "subproducts": sum(C.product_name(s) in fp for s in subs),
        "scar_rasters": sum(C.product_name(s) in fp for s in scar_subs),
        "poly": f"burned_area_polygons_v{C.PRODUCT_VERSION}" in fp,
        "scarfc": n_assets(C.ANNUAL_BURNED_VECTORS),
        "pix": n_pixels_done(),
        "zips": n_zips(),
    }


def write_status(st):
    def tick(ok):
        return "✅" if ok else "⏳"
    lines = [
        "# step-07 `_v2` re-export — driver status",
        "",
        f"_last tick {dt.datetime.now():%F %T}_ — `collection-01/logs/v2-driver/`",
        "",
        "| | stage | state | detail |",
        "|---|---|---|---|",
        f"| A1 | 07a month of burn | {tick(st['mob'] >= N_CAL)} | "
        f"{st['mob']}/{N_CAL} assets, {len(st['mob_inflight'])} task(s) in flight |",
        f"| A2 | 07d nine subproducts | {tick(st['subproducts'] == 9)} | "
        f"{st['subproducts']}/9 assets, {len(st['d_inflight'])} in flight"
        f"{' — GATED on A1' if st['mob'] < N_CAL else ''} |",
        f"| B | 07e polygon layer | {tick(done('B'))} | "
        f"asset {'exists' if st['poly'] else 'not yet'}, {len(st['e_inflight'])} in flight, "
        f"verified={done('B')} |",
        f"| C1 | 07b local scars | {tick(done('C1'))} | "
        f"pixels {st['pix']}/{N_FIRE}, zips {st['zips']}/{N_CAL} |",
        f"| C2 | zip gate | {tick(done('C2'))} | validate_scar_zips.py |",
        f"| C3 | 07c scar rasters | {tick(st['scar_rasters'] == 3)} | "
        f"{st['scar_rasters']}/3 assets; ingested scar FCs {st['scarfc']}/{N_CAL}"
        f"{' — WAITING FOR THE MANUAL INGEST' if st['scarfc'] < N_CAL else ''}"
        f"{' — GATED on A1 (07c masks to the v2 month of burn)' if st['mob'] < N_CAL else ''} |",
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
    stuck = [n for n in ("A1", "A2", "B", "C1-pixels", "C1-scars", "C3")
             if tries(n) >= MAX_TRIES and not done(n.split("-")[0])]
    if stuck:
        lines += [f"## ⚠ Stopped after {MAX_TRIES} attempts: {', '.join(stuck)}", "",
                  "See the matching `*.out` in `collection-01/logs/v2-driver/`.", ""]
    STATUS.write_text("\n".join(lines))


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
        print(STATUS.read_text() if STATUS.exists() else "no status yet")
        return
    DRY = args.dry_run
    STATE.mkdir(parents=True, exist_ok=True)

    st = survey()
    log(f"tick  mob={st['mob']}/{N_CAL} sub={st['subproducts']}/9 poly={st['poly']} "
        f"scar_rasters={st['scar_rasters']}/3 scarfc={st['scarfc']}/{N_CAL} "
        f"pix={st['pix']}/{N_FIRE} zips={st['zips']}/{N_CAL}")

    for stage in (stage_A1, stage_A2, stage_B, stage_C1, stage_C2, stage_C3):
        try:
            stage(st)
        except Exception as exc:                       # one broken stage must not stop the rest
            log(f"[{stage.__name__}] ⚠ EXCEPTION {type(exc).__name__}: {exc}")

    write_status(st)


if __name__ == "__main__":
    main()
