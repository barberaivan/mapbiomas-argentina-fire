#!/usr/bin/env bash
# v2_driver_tick.sh — one tick of run_07_v2_driver.py, safe to call from cron.
#
# WHY CRON AND NOT A SLEEP LOOP.  The step-07 v2 re-export has gates hours apart (07d waits for
# all 27 month assets; 07c waits for a manual ingest), and the obvious "wait, then launch next"
# shape dies with the session — a power cut takes the terminal, tmux and any sleeping process
# with it.  cron's job is started by the cron daemon, which comes up at boot without a login, so
# the only thing an outage costs is the hours the box is off.  Submitted GEE tasks are unaffected
# either way: they run server-side.
#
# `flock -n` makes an overlapping tick a no-op rather than a second submitter — a tick can take
# ~15 min (listOperations over this project's ~10 k operations is ~13 s, and A1 submits 27 tasks).
#
# Install (already done, `crontab -l` to confirm):
#   */15 * * * * /home/ivan/dev/MapBiomas/mapbiomas-arg-fire/collection-01/scripts/v2_driver_tick.sh
#   @reboot      /home/ivan/dev/MapBiomas/mapbiomas-arg-fire/collection-01/scripts/v2_driver_tick.sh
set -u
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PYTHON=/home/ivan/.venvs/gee/bin/python
export HOME=/home/ivan
REPO=/home/ivan/dev/MapBiomas/mapbiomas-arg-fire
STATE="$REPO/collection-01/logs/v2-driver"
mkdir -p "$STATE"
cd "$REPO" || exit 1
exec flock -n "$STATE/tick.lock" \
  "$PYTHON" "$REPO/collection-01/scripts/run_07_v2_driver.py" >> "$STATE/cron.log" 2>&1
