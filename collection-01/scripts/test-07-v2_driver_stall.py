"""
collection-01/scripts/test-07-v2_driver_stall.py

Exercise `run_07_v2_driver.py`'s stall watchdog WITHOUT cancelling anything real.

The watchdog only ever runs in an emergency — a month-of-burn task wedged server-side at 3 a.m.
(see the driver's `stall_survey` docstring for the September 2026 `mob_2002` case) — so it cannot
be its own first test.  It is also the one place the driver CANCELS a task rather than launching
one, in a compute project shared with the whole MapBiomas Fuego network, which makes the refusal
paths the part that matters most.

Checks:
  1. The stall clock keeps running across an unchanged reading and resets on a changed one, down
     to a single sub-work-unit of creep.
  2. It resets when the same description belongs to a NEW operation — a resubmitted year must not
     inherit the dead task's clock and look wedged from birth.
  3. Every guard in `cancel_wedged_mob` refuses, and none of them reaches `cancelOperation`
     (which is monkeypatched to raise, so a leak fails the test rather than killing a task).
     The last case runs against a REAL finished `mob_` operation on the server.

State is redirected to a temp dir, so running this never touches `collection-01/logs/v2-driver/`.

    $PYTHON collection-01/scripts/test-07-v2_driver_stall.py
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "collection-01"))
spec = importlib.util.spec_from_file_location(
    "drv", ROOT / "collection-01/scripts/run_07_v2_driver.py")
drv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(drv)
import ee  # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(f"{'PASS' if ok else 'FAIL'}  {label}: got {got!r}, want {want!r}")
    if not ok:
        fails.append(label)


# --- redirect all watchdog state to a temp dir so the live driver is untouched -------------
tmp = Path(tempfile.mkdtemp())
drv.MOBPROG = tmp / "mob-progress.json"
drv.STATE = tmp
drv.TICKLOG = tmp / "tick.log"

OP = "projects/mapbiomas-argentina/operations/FAKEOPFAKEOPFAKEOP1"


def fake(units, name=OP, state="RUNNING", progress=0.5):
    return {"description": "mob_2002", "state": state, "progress": progress,
            "attempt": 1, "_name": name,
            "stages": [{"completeWorkUnits": units}, {"completeWorkUnits": None}]}


# 1. unchanged reading -> the clock keeps running -------------------------------------------
drv._OPS = {drv.ARG_PROJECT: [fake(14.0)]}
first = drv.stall_survey()["mob_"]
check("first sighting starts at ~0 h", round(first[0]["flat_h"], 3), 0.0)

# backdate the stored `since` by 3 h, then re-survey with the SAME reading
hist = json.loads(drv.MOBPROG.read_text())
hist["mob_2002"]["since"] -= 3 * 3600
drv.MOBPROG.write_text(json.dumps(hist))
again = drv.stall_survey()["mob_"]
check("unchanged reading keeps the clock", round(again[0]["flat_h"]), 3)
check("3 h flat is over STALL_H", again[0]["flat_h"] >= drv.STALL_H, True)

# 2a. a CHANGED reading resets the clock ----------------------------------------------------
hist = json.loads(drv.MOBPROG.read_text())
hist["mob_2002"]["since"] -= 3 * 3600
drv.MOBPROG.write_text(json.dumps(hist))
drv._OPS = {drv.ARG_PROJECT: [fake(14.001)]}       # one sub-work-unit of creep
moved = drv.stall_survey()["mob_"]
check("a changed reading resets the clock", round(moved[0]["flat_h"], 3), 0.0)

# 2b. same description, NEW operation -> reset (a resubmitted year must not inherit the clock)
hist = json.loads(drv.MOBPROG.read_text())
hist["mob_2002"]["since"] -= 9 * 3600
drv.MOBPROG.write_text(json.dumps(hist))
drv._OPS = {drv.ARG_PROJECT: [fake(14.001, name=OP[:-1] + "2")]}
fresh = drv.stall_survey()["mob_"]
check("a resubmitted year starts a new clock", round(fresh[0]["flat_h"], 3), 0.0)

# 2c. a task that is neither PENDING nor RUNNING is not tracked ------------------------------
drv._OPS = {drv.ARG_PROJECT: [fake(18.0, state="SUCCEEDED")]}
check("a finished task is not tracked", drv.stall_survey()["mob_"], [])

# 3. every guard in cancel_wedged_mob --------------------------------------------------------
ee.data.cancelOperation = lambda *a, **k: (_ for _ in ()).throw(
    AssertionError("cancelOperation must NOT be reached in this test"))

t = {"desc": "mob_2002", "name": OP, "flat_h": 9.0, "progress": 0.74}
check("guard: description is not mob_<year>",
      drv.cancel_wedged_mob({**t, "desc": "GT_Fuego-Bolivia-2020"}), False)
check("guard: year outside our calendar range",
      drv.cancel_wedged_mob({**t, "desc": "mob_1873"}), False)
check("guard: operation in the OTHER project",
      drv.cancel_wedged_mob(
          {**t, "name": "projects/mapbiomas-fire-485203/operations/XXXXXXXXXXXXXXXXXXXX"}), False)
check("guard: no operation name", drv.cancel_wedged_mob({**t, "name": None}), False)
check("guard: operation does not exist on the server", drv.cancel_wedged_mob(t), False)

# the real one: a genuinely SUCCEEDED mob_ task must be refused on its state ------------------
drv.init_ee("comahue", drv.ARG_PROJECT)
succeeded = next((o for o in ee.data.listOperations()
                  if str(o.get("metadata", {}).get("description", "")).startswith("mob_")
                  and o["metadata"].get("state") == "SUCCEEDED"), None)
if succeeded:
    d = succeeded["metadata"]["description"]
    check(f"guard: real SUCCEEDED task {d} refused on state",
          drv.cancel_wedged_mob({"desc": d, "name": succeeded["name"],
                                 "flat_h": 99.0, "progress": 1.0}), False)
else:
    print("SKIP  no SUCCEEDED mob_ task found to test the state guard against")

print()
print("ALL PASS" if not fails else f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
