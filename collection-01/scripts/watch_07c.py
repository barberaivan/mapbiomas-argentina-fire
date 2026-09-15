#!/usr/bin/env python
"""watch_07c.py — the 2-minute watcher that launches step 07c when the scar ingest lands.

ROADMAP "After", item 1.  Iván ingests the 27 calendar-scar packages by hand as
`…/annual_burned_vectors_v2/scars_<Y>`; the three scar rasters (07c) cannot be built until they
are there.  `run_07_v2_driver.py` already has that gate (stage C3) but it ticks every 15 min and
launches on EXISTENCE alone.  This watcher is the same tick shape at 2-minute resolution, and it
does the two things the roadmap asks for between the ingest and the launch:

  1. **stamps `exclusion_rule_a` / `exclusion_rule_b` on each ingested FeatureCollection** — a
     property, not a filter: the collection was already filtered when the scars were built
     (docs/07 §1.1).  An asset that does not state its own selection cannot be told apart from
     one built before the rules existed.  The write MERGES: `updateAsset(..., ["properties"])`
     REPLACES the whole dict, which is the trap ROADMAP records for `audit_product_properties.py`.
  2. **runs the `--ingested` gate before launching**, not after — `validate_scar_zips.py` compares
     every FC's feature count and `area_ha` total against the local build, and a year that
     disagrees is dropped from the launch rather than painted into a published product.

While C3 is paused in the driver (`logs/v2-driver/C3.pause`) this file owns the launch; both run
under the SAME `tick.lock`, so the two can never submit at once.  Delete the pause file to hand
C3 back to the 15-min driver.

PARTIAL LAUNCHES.  Iván's instruction, 15 Sep 05:10: *"If some year ingest fails, run the
following steps with the available years, and I run tomorrow only the remaining ones."*  So the
watcher does not wait forever:

  * all 27 present                  -> launch the full product.
  * some missing, ingest in flight  -> wait (this is the normal case while uploads run).
  * some missing, still ingesting, but MAX_WAIT_MIN minutes have passed -> launch without them.
  * some missing, NOTHING in flight for QUIET_MIN minutes -> launch with the years that are there,
    provided at least MIN_PARTIAL of them are.  The three assets are then INCOMPLETE and say so
    in their own `partial` / `years` properties (07-scar_rasters.py), on the board, and in
    `logs/v2-driver/C3-PARTIAL.md`, which spells out what to delete and re-run to complete them.
    Below MIN_PARTIAL it refuses and shouts instead: a 5-band product at the published asset id
    costs more to undo than one night of waiting.

Run (from the repo ROOT; cron does this every 2 min via `watch_07c_tick.sh`):

    $PYTHON collection-01/scripts/watch_07c.py [--dry-run] [--status] [--force-partial]

State, alongside the driver's, in `collection-01/logs/v2-driver/`:
    C3-watch.log        every action + a heartbeat every 30 min
    C3-watch.md         the board for this watcher — `cat` this first
    C3-watch-gate.out   the `validate_scar_zips.py --ingested` transcript
    C3.out              the 07c launch transcript (shared with the driver's stage C3)
    C3.done             written once the launch is confirmed ON THE SERVER, never from rc=0
    C3-PARTIAL.md       written ONLY when the launch was partial — what is missing and how to fix
    C3-watch.quiet      first tick at which nothing was in flight any more (the QUIET_MIN clock)
    C3-watch.deadline   the hard stop on waiting for a missing year (the MAX_WAIT_MIN clock)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "collection-01"))

import ee  # noqa: E402
import utils.constants as C  # noqa: E402

PYTHON = os.environ.get("PYTHON", "/home/ivan/.venvs/gee/bin/python")
CRED_DIR = Path.home() / ".config/earthengine"
STATE = ROOT / "collection-01/logs/v2-driver"

LOG = STATE / "C3-watch.log"
BOARD = STATE / "C3-watch.md"
QUIET = STATE / "C3-watch.quiet"
DEADLINE = STATE / "C3-watch.deadline"   # epoch seconds; the hard stop on waiting for a year
SIGFILE = STATE / "C3-watch.sig"
DONE = STATE / "C3.done"              # the driver's own marker: written here, honoured there
TRIES = STATE / "C3-watch.tries"
PARTIAL_NOTE = STATE / "C3-PARTIAL.md"

ARG_PROJECT = "mapbiomas-argentina"   # the scar FCs, their ingests AND 07c all live here
# EVERYTHING here runs as comahue on `mapbiomas-argentina` (Iván, 15 Sep 05:25): the gmail account
# and the fire project are needed for the statistics exports, which land in GCS — comahue has no
# write access to the bucket.  The queue is PER USER, so keeping 07c off gmail also keeps it from
# queueing behind those.  The destination asset path is unaffected by either choice (CLAUDE.md).
ACCOUNT = "comahue"
TASK_PREFIX = "arg07c_"

YEARS = list(C.CALENDAR_YEARS)        # 1999-2025
N_CAL = len(YEARS)
QUIET_MIN = 25                        # no ingest in flight for this long = the rest are not coming
MAX_WAIT_MIN = 60                     # …and this is the hard stop even while ingests ARE running
MIN_PARTIAL = 20                      # fewer years than this: refuse and shout, do not publish
MAX_TRIES = 3                         # launch attempts before stopping for a human
HEARTBEAT_MIN = 30

DRY = False


# ---------------------------------------------------------------------------
# plumbing
# ---------------------------------------------------------------------------
def log(msg):
    line = f"{dt.datetime.now():%F %T}  {msg}"
    print(line, flush=True)
    STATE.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as fh:
        fh.write(line + "\n")


def init_ee(account=None, project=ARG_PROJECT):
    """Explicit credentials, never a `cp` over the resident file (CLAUDE.md)."""
    st = json.loads((CRED_DIR / f"credentials.{account or ACCOUNT}").read_text())
    from google.oauth2.credentials import Credentials
    ee.Initialize(Credentials(
        None, refresh_token=st["refresh_token"], token_uri=ee.oauth.TOKEN_URI,
        client_id=st.get("client_id", ee.oauth.CLIENT_ID),
        client_secret=st.get("client_secret", ee.oauth.CLIENT_SECRET),
        scopes=st.get("scopes", ee.oauth.SCOPES),
        quota_project_id=st.get("project"),
    ), project=project)


def run(name, argv, timeout=3600):
    """Run a command, tee it to `<name>.out`, return (rc, tail-of-output)."""
    out = STATE / f"{name}.out"
    log(f"[{name}] RUN {' '.join(str(a) for a in argv)}")
    if DRY:
        return 0, ""
    with out.open("a") as fh:
        fh.write(f"\n===== {dt.datetime.now():%F %T}  {' '.join(str(a) for a in argv)}\n")
        fh.flush()
        try:
            proc = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, timeout=timeout, text=True)
            rc, text = proc.returncode, proc.stdout
        except subprocess.TimeoutExpired as exc:
            rc, text = 124, (exc.stdout or "") + "\n*** TIMED OUT ***\n"
        fh.write(text)
    log(f"[{name}] rc={rc}  (log: {out})")
    return rc, text


def deadline_at():
    """When the watcher stops waiting for the missing years, whatever their ingests are doing.

    Written once, on the first tick that sees a year missing, and read from disk afterwards so a
    reboot or a killed tick cannot silently restart the hour.
    """
    if not DEADLINE.exists():
        DEADLINE.write_text(str(dt.datetime.now().timestamp() + MAX_WAIT_MIN * 60))
    return dt.datetime.fromtimestamp(float(DEADLINE.read_text().strip()))


def past_deadline():
    return dt.datetime.now() >= deadline_at()


def bump_tries():
    n = int(TRIES.read_text().strip()) if TRIES.exists() else 0
    n += 1
    TRIES.write_text(str(n))
    return n


def n_tries():
    return int(TRIES.read_text().strip()) if TRIES.exists() else 0


# ---------------------------------------------------------------------------
# the world
# ---------------------------------------------------------------------------
def present_years():
    """Calendar years whose scar FeatureCollection is on the server.

    A GEE table ingest is all-or-nothing — the asset appears only when it SUCCEEDS — so
    existence is the right test here, unlike the v2 image assets a previous run could also
    have written (run_07_v2_driver.py, "built with the CURRENT rules").  `annual_burned_vectors_v2`
    is a fresh folder for this version, so nothing older can be sitting in it.
    """
    try:
        ids = ee.data.listAssets({"parent": C.ANNUAL_BURNED_VECTORS}).get("assets", [])
    except ee.EEException:
        return set()
    out = set()
    for a in ids:
        m = re.fullmatch(r"scars_(\d{4})", a["id"].split("/")[-1])
        if m:
            out.add(int(m.group(1)))
    return out


_ING_PAT = re.compile(re.escape(C.ANNUAL_BURNED_VECTORS) + r"/scars_(\d{4})")


def ingest_state():
    """{year: [states]} for the hand-launched table ingests, from `listOperations`.

    The ingest is not ours to submit but it IS ours to watch: the operation's description carries
    the destination asset path (`Ingest table: "projects/…/annual_burned_vectors_v2/scars_2013"`),
    which is how a year still uploading is told apart from one whose upload failed.  Matching on
    the full asset path, never on a bare year, keeps the network's other work out of it (CLAUDE.md).
    """
    out = {}
    for op in ee.data.listOperations():
        m = op.get("metadata", {})
        if m.get("type") != "INGEST_TABLE":
            continue
        hit = _ING_PAT.search(str(m.get("description", "")))
        if hit:
            out.setdefault(int(hit.group(1)), []).append(m.get("state"))
    return out


def inflight_07c():
    """Our scar-raster tasks currently PENDING/RUNNING.

    `listOperations` is PROJECT-scoped (CLAUDE.md), so this only finds them because 07c is
    submitted to the same project this session is initialized against.  Match on our namespaced
    prefix and nothing else: the list is cross-USER, and `MBFUEGO_ARG_COL1-*` (the statistics
    exports) and the network's own work share it.
    """
    out = []
    for o in ee.data.listOperations():
        m = o.get("metadata", {})
        if (m.get("state") in ("PENDING", "RUNNING")
                and str(m.get("description", "")).startswith(TASK_PREFIX)):
            pct = m.get("progress")
            out.append(f"{m['description']} {m['state']}"
                       + (f" {100 * pct:.0f}%" if isinstance(pct, (int, float)) else ""))
    return sorted(out)


def failed_07c():
    """Our scar-raster tasks that FAILED or were CANCELLED, with the reason.

    Without this the board reads the same whether a task is still climbing or died at 04:00: "0/3
    landed, none in flight". A task that failed is the one thing here nobody would otherwise see
    until morning.
    """
    out = []
    for o in ee.data.listOperations():
        m = o.get("metadata", {})
        if (m.get("state") in ("FAILED", "CANCELLED")
                and str(m.get("description", "")).startswith(TASK_PREFIX)):
            why = str((o.get("error") or {}).get("message", ""))[:160]
            out.append(f"{m['description']} {m['state']}" + (f" — {why}" if why else ""))
    return sorted(set(out))


def scar_rasters_landed():
    try:
        have = {a["id"].split("/")[-1] for a in
                ee.data.listAssets({"parent": C.FINAL_PRODUCTS}).get("assets", [])}
    except ee.EEException:
        have = set()
    return sum(C.product_name(s) in have for s in
               ("annual_burned_id", "annual_burned_area_ha", "annual_burned_scar_size_range"))


# ---------------------------------------------------------------------------
# step 2 of the roadmap item: the rule properties
# ---------------------------------------------------------------------------
RULES = C.exclusion_rules()


def stamp(years):
    """Write `exclusion_rule_a`/`_b` (+ the small provenance block) on each FC that lacks them.

    MERGED, not replaced: `updateAsset(..., updateFields=["properties"])` overwrites the whole
    dict, so the existing block is read first and the rules are added to it.  Today the ingested
    FCs come up with an EMPTY block, but a merge costs one read and makes a re-run after someone
    has set something by hand a no-op instead of a silent deletion.
    """
    want = dict(RULES)
    want.update({
        "source": C.PRODUCT_SOURCE,
        "region": C.PRODUCT_REGION,
        "collection": 1,
        "unit": "one polygon per 8-connected burned-pixel group within the calendar year",
        "scar_connectivity": "8-connected, calendar-year (docs/07 §5)",
        "area_encoding": "area_ha: pixel-count area, not a geodesic polygon area",
        "derived_from": C.MONTH_OF_BURN_COL,
    })
    stamped, failed = [], []
    for y in sorted(years):
        aid = f"{C.ANNUAL_BURNED_VECTORS}/scars_{y}"
        try:
            have = dict(ee.data.getAsset(aid).get("properties") or {})
        except ee.EEException as exc:
            failed.append((y, f"getAsset: {exc}"))
            continue
        merged = dict(have)
        merged.update(want, year=y)
        if merged == have:
            continue
        if DRY:
            log(f"[stamp] would stamp scars_{y} ({len(merged)} properties)")
            stamped.append(y)
            continue
        try:
            ee.data.updateAsset(aid, {"properties": merged}, ["properties"])
            stamped.append(y)
        except ee.EEException as exc:
            failed.append((y, f"updateAsset: {exc}"))
    if stamped:
        log(f"[stamp] exclusion_rule_a/b written on {len(stamped)} FC(s): {stamped}")
    for y, why in failed:
        log(f"[stamp] ⚠ scars_{y} FAILED — {why}")
    return stamped, failed


# ---------------------------------------------------------------------------
# the gate + the launch
# ---------------------------------------------------------------------------
MISMATCH_RE = re.compile(r"MISMATCHED — re-upload these: \[([^\]]*)\]")


def gate(years):
    """`validate_scar_zips.py --ingested` on the candidate years.

    Returns (ok_years, bad_years).  This is the check the roadmap puts between the ingest and
    07c: feature count and `area_ha` total against the local build, and `scar_id` still numeric
    after the DBF round trip (a string there makes `ee.Image().paint()` reject the FC — the
    export would fail hours in, not at submission).
    """
    rc, text = run("C3-watch-gate",
                   [PYTHON, "collection-01/scripts/validate_scar_zips.py", "--ingested",
                    "--years", ",".join(str(y) for y in sorted(years)),
                    "--credentials", str(CRED_DIR / f"credentials.{ACCOUNT}"),
                    "--project", ARG_PROJECT],
                   timeout=3600)
    bad = set()
    for hit in MISMATCH_RE.finditer(text):
        for tok in hit.group(1).split(","):
            tok = tok.strip().strip("'\"")
            if tok.isdigit():
                bad.add(int(tok))
    if rc != 0 and not bad:
        # Exited non-zero for a reason the parser did not recognise (a non-numeric `scar_id`
        # reports the ASSET NAME, not a year, and any other failure is unknown territory).
        # Fail closed: do not launch on an unread verdict.
        log("[gate] ⚠ validate_scar_zips.py --ingested exited non-zero and named no year — "
            "NOT launching; read C3-watch-gate.out")
        return set(), set(years)
    if bad:
        log(f"[gate] ⚠ these years disagree with the local build and are DROPPED: {sorted(bad)}")
    return set(years) - bad, bad


def launch(years, partial):
    """Submit the three scar-raster exports for `years`, then confirm them ON THE SERVER."""
    live = inflight_07c()
    if live:
        log(f"[launch] {len(live)} {TASK_PREFIX} task(s) already in flight ({live}) — not "
            "submitting again")
        return False
    if n_tries() >= MAX_TRIES:
        log(f"[launch] ⚠ STOPPED after {MAX_TRIES} attempts — needs a human")
        return False
    bump_tries()
    rc, _ = run("C3", [PYTHON, "collection-01/workflow/07-scar_rasters.py", "--launch",
                       "--years", ",".join(str(y) for y in sorted(years)),
                       "--credentials", str(CRED_DIR / f"credentials.{ACCOUNT}"),
                       "--project", ARG_PROJECT], timeout=3600)
    if DRY:
        log("[launch] dry run — nothing submitted")
        return False
    # "Verify a launch on the server, not from rc=0" (ROADMAP, operating notes): the 00:21
    # subproduct launch was confirmed by listing the operations, and that is the only evidence
    # that survives a script that exits 0 without submitting.
    live = inflight_07c()
    log(f"[launch] rc={rc}; {TASK_PREFIX} tasks now in flight: {sorted(live)}")
    if not live:
        log("[launch] ⚠ nothing is in flight after the launch — will retry next tick")
        return False
    DONE.write_text(f"{dt.datetime.now():%F %T}  {len(live)} scar-raster task(s) submitted by "
                    f"watch_07c.py over {len(years)} calendar year(s)"
                    f"{' — PARTIAL, see C3-PARTIAL.md' if partial else ''}\n")
    if partial:
        write_partial_note(years)
    return True


def write_partial_note(years):
    missing = [y for y in YEARS if y not in years]
    subs = ["annual_burned_id", "annual_burned_area_ha", "annual_burned_scar_size_range"]
    PARTIAL_NOTE.write_text(f"""# ⚠ the three scar rasters are PARTIAL

Launched {dt.datetime.now():%F %T} by `watch_07c.py` over **{len(years)}/{N_CAL}** calendar years,
because these years had no ingested scar FeatureCollection and none was still uploading:

    missing: {', '.join(str(y) for y in missing)}

The three assets therefore have **{len(years)} bands, not {N_CAL}**, and each says so in its own
`partial` and `years` properties. They are at the published ids, so anything reading them reads an
incomplete series until this is fixed.

## To complete them

1. Ingest the missing years:
   `{C.ANNUAL_BURNED_VECTORS}/scars_<Y>`
   from `collection-01/data/scars-upload-cache/scars_<Y>.zip`.
2. Verify: `$PYTHON collection-01/scripts/validate_scar_zips.py --ingested`
3. **Delete the three partial assets** (deletions are Iván's to run — CLAUDE.md):
{chr(10).join(f'     {C.FINAL_PRODUCTS}/{C.product_name(s)}' for s in subs)}
4. Clear the markers and let the watcher (or the driver's stage C3) run again:
     `rm collection-01/logs/v2-driver/C3.done collection-01/logs/v2-driver/C3-watch.tries \\
         collection-01/logs/v2-driver/C3-PARTIAL.md collection-01/logs/v2-driver/C3-watch.quiet`

A re-export over all {N_CAL} years is the ONLY way to complete them: the products are one
multiband image per subproduct, and a band cannot be added to a landed asset.
""")
    log(f"[launch] ⚠ PARTIAL — missing {missing}; wrote {PARTIAL_NOTE}")


# ---------------------------------------------------------------------------
# the board
# ---------------------------------------------------------------------------
def write_board(st):
    missing = [y for y in YEARS if y not in st["present"]]
    verdict = st["verdict"]
    BOARD.write_text(f"""# 07c watcher — the scar ingest and the three scar rasters

_last tick {dt.datetime.now():%F %T}_ — ticks every 2 min from cron
(`collection-01/scripts/watch_07c_tick.sh`). **If that stamp is more than ~5 min old it is not
running** (`crontab -l`, then `C3-watch.log`).

| | state |
|---|---|
| ingested scar FCs | **{len(st['present'])}/{N_CAL}** |
| missing | {', '.join(str(y) for y in missing) or '— none'} |
| ingests still in flight | {', '.join(str(y) for y in st['ingesting']) or '— none'} |
| hard deadline on waiting | {deadline_at():%F %H:%M} ({MAX_WAIT_MIN} min after the first tick that saw a year missing) |
| `exclusion_rule_*` stamped | {st['stamped_n']}/{len(st['present'])} |
| 07c tasks in flight | {'<br>'.join(st['inflight']) or '— none'} |
| 07c assets landed | {st['landed']}/3 |
| 07c tasks FAILED | {'<br>'.join(st.get('failed') or []) or '— none'} |
| launch | {verdict} |

Driver stage C3 is paused (`C3.pause`) while this file owns the launch; C4 (the scar-vs-month
check on the landed assets) still belongs to the 15-min driver.
""")


# ---------------------------------------------------------------------------
def tick(force_partial=False):
    init_ee()
    present = present_years()
    st = {"present": present, "ingesting": [], "stamped_n": 0, "inflight": [],
          "landed": 0, "failed": [], "verdict": ""}

    if DONE.exists():
        # The launch has happened.  Keep refreshing the board so the tasks can be followed from
        # it, but only every 10 min: `listOperations` on the shared fire project walks ~1.2 k
        # operations, and there is nothing left for this file to decide.
        fresh = BOARD.exists() and dt.datetime.now().timestamp() - BOARD.stat().st_mtime < 600
        if not fresh:
            st["inflight"] = inflight_07c()
            st["landed"] = scar_rasters_landed()
            st["failed"] = failed_07c()
            st["verdict"] = f"✅ submitted — {DONE.read_text().strip()}"
            st["stamped_n"] = len(present)
            write_board(st)
        return ("done-failed" if st.get("failed") and st["landed"] < 3 else "done"), len(present)

    stamped, failed = stamp(present)
    st["stamped_n"] = len(present) - len(failed)

    # --- is the set complete, or is more still coming? --------------------------------------
    missing = [y for y in YEARS if y not in present]
    if missing:
        ings = ingest_state()
        st["ingesting"] = sorted(y for y in missing
                                 if any(s in ("PENDING", "RUNNING") for s in ings.get(y, [])))
    partial = bool(missing)

    overdue = past_deadline()
    if not missing:
        QUIET.unlink(missing_ok=True)
    elif st["ingesting"] and not overdue:
        QUIET.unlink(missing_ok=True)          # still uploading: the quiet clock restarts
        st["verdict"] = (f"⏳ waiting — {len(st['ingesting'])} ingest(s) in flight "
                         f"({', '.join(str(y) for y in st['ingesting'])}); deadline "
                         f"{deadline_at():%H:%M}")
        write_board(st)
        return "waiting", len(present)
    elif st["ingesting"]:
        # The DEADLINE, not the quiet clock: Iván, 15 Sep 05:35 — "only 2008 and 2009 still
        # ingesting scars FC. If in 1 h they're not done, launch without them."  An ingest that
        # is still RUNNING is therefore no longer a reason to hold the night; a year that lands
        # five minutes after this is simply one of the years to be added tomorrow.
        log(f"[deadline] {deadline_at():%F %T} passed with {st['ingesting']} still ingesting — "
            f"launching without them")
    else:
        # Nothing in flight and years still missing: start (or read) the quiet clock.  The delay
        # is deliberate — an upload that failed is usually retried by hand within minutes, and a
        # partial product costs a delete + a full re-export to undo.
        if not QUIET.exists():
            QUIET.write_text(f"{dt.datetime.now():%F %T}\n")
        quiet_min = (dt.datetime.now().timestamp() - QUIET.stat().st_mtime) / 60
        if not force_partial and not overdue and quiet_min < QUIET_MIN:
            st["verdict"] = (f"⏳ {len(missing)} year(s) missing with no ingest in flight — "
                             f"partial launch in {QUIET_MIN - quiet_min:.0f} min unless they land")
            write_board(st)
            return "quiet", len(present)
        if len(present) < MIN_PARTIAL:
            st["verdict"] = (f"⛔ only {len(present)}/{N_CAL} years ingested — too few to publish "
                             f"a partial product (MIN_PARTIAL={MIN_PARTIAL}). NEEDS A HUMAN.")
            write_board(st)
            log(f"[gate] ⛔ {len(present)}/{N_CAL} ingested and nothing in flight — refusing to "
                f"publish a {len(present)}-band product. Missing: {missing}")
            return "too-few", len(present)

    # --- the gate, then the launch ------------------------------------------------------------
    ok, bad = gate(present)
    if not ok:
        st["verdict"] = "⛔ the --ingested gate rejected every year — read C3-watch-gate.out"
        write_board(st)
        return "gate-failed", len(present)
    partial = partial or bool(bad)
    if partial and len(ok) < MIN_PARTIAL:
        st["verdict"] = (f"⛔ only {len(ok)} year(s) passed the gate — too few to publish "
                         f"(MIN_PARTIAL={MIN_PARTIAL}). NEEDS A HUMAN.")
        write_board(st)
        return "too-few", len(present)

    log(f"[launch] gate passed for {len(ok)}/{N_CAL} years"
        + (f"; PARTIAL, missing {[y for y in YEARS if y not in ok]}" if partial else " — COMPLETE"))
    launched = launch(sorted(ok), partial)
    st["inflight"] = inflight_07c()
    st["landed"] = scar_rasters_landed()
    st["verdict"] = (f"{'⚠ PARTIAL — read C3-PARTIAL.md' if partial else '✅'} submitted "
                     f"{len(st['inflight'])} task(s) "
                     f"over {len(ok)} year(s)" if launched
                     else "⚠ launch attempted and not confirmed — see C3-watch.log")
    write_board(st)
    return ("launched" if launched else "launch-failed"), len(present)


def main():
    global DRY
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="say what it would do, write nothing")
    ap.add_argument("--status", action="store_true", help="print the board and exit")
    ap.add_argument("--force-partial", action="store_true",
                    help="skip the %d-minute quiet wait before a partial launch" % QUIET_MIN)
    args = ap.parse_args()
    DRY = args.dry_run

    if args.status:
        print(BOARD.read_text() if BOARD.exists() else "(no tick yet)")
        return

    STATE.mkdir(parents=True, exist_ok=True)
    try:
        verdict, n_present = tick(force_partial=args.force_partial)
    except Exception as exc:                       # a tick that cannot see the server is not a
        log(f"⚠ EXCEPTION {type(exc).__name__}: {exc}")   # failure — the next one is 2 min away
        raise
    # Quiet by default: 720 ticks a night would bury the lines that matter.  Log when the world
    # changed, and a heartbeat every HEARTBEAT_MIN so silence is still distinguishable from death.
    sig = f"{verdict}|{n_present}"
    last = SIGFILE.read_text().strip() if SIGFILE.exists() else ""
    stale = (not LOG.exists() or
             dt.datetime.now().timestamp() - LOG.stat().st_mtime > HEARTBEAT_MIN * 60)
    if sig != last or stale:
        log(f"tick  {verdict}  scarfc={n_present}/{N_CAL}")
        SIGFILE.write_text(sig)


if __name__ == "__main__":
    main()
