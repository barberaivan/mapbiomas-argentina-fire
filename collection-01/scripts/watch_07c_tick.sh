#!/usr/bin/env bash
# watch_07c_tick.sh — one tick of watch_07c.py, safe to call from cron every 2 minutes.
#
# Same shape and the same reasoning as v2_driver_tick.sh: no sleep loop, because a sleeping
# process dies with the session and with the machine.  Each tick reads the world and exits.
#
# TWO locks, and both matter:
#   * `$STATE/tick.lock` is the DRIVER's lock.  Taking it here is what makes it impossible for
#     the 15-min driver and this 2-min watcher to submit 07c at the same moment.  Driver stage C3
#     is also paused (`C3.pause`) while this file owns the launch, so this is the belt to that
#     brace — a pause file someone deletes must not become a duplicate submission.
#   * `-n` (non-blocking) means an overlapping tick is a no-op, not a queue: the gate run
#     (`validate_scar_zips.py --ingested`, 27 FeatureCollections) can hold a tick for minutes.
#
# Install:
#   */2 * * * * /home/ivan/dev/MapBiomas/mapbiomas-arg-fire/collection-01/scripts/watch_07c_tick.sh
#   @reboot     /home/ivan/dev/MapBiomas/mapbiomas-arg-fire/collection-01/scripts/watch_07c_tick.sh
# Remove both lines once `C3-watch.md` says the launch is submitted and the three assets have landed.
set -u
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PYTHON=/home/ivan/.venvs/gee/bin/python
export HOME=/home/ivan
REPO=/home/ivan/dev/MapBiomas/mapbiomas-arg-fire
STATE="$REPO/collection-01/logs/v2-driver"
mkdir -p "$STATE"
cd "$REPO" || exit 1
exec flock -n "$STATE/tick.lock" \
  "$PYTHON" "$REPO/collection-01/scripts/watch_07c.py" >> "$STATE/C3-watch-cron.log" 2>&1
