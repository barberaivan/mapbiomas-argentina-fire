#!/usr/bin/env bash
# mem_monitor.sh — lightweight whole-system RAM monitor.
#
# Samples /proc/meminfo every INTERVAL seconds, tracks peak memory + swap use,
# and appends a WARN line the moment available RAM drops below a threshold
# (so a morning glance at the log tells you if a run flirted with OOM).
# To keep the file tiny it only writes a SAMPLE line when a *new* peak is set
# (>= 200 MB above the last logged peak) — you get the climb curve for free.
#
# Usage: mem_monitor.sh [logfile] [interval_s] [warn_avail_mb]
#   logfile        default: mem_monitor.log
#   interval_s     seconds between samples (default 15)
#   warn_avail_mb  WARN when MemAvailable < this many MB (default 2048)
#
# Stop it with: kill <pid>  (writes a final STOP line with the peaks).
set -u

LOG=${1:-mem_monitor.log}
INT=${2:-15}
WARN_MB=${3:-2048}

peak_used_mb=0
peak_swap_mb=0
last_logged_peak=0
warned=0

log() { printf '%s %s\n' "$(date '+%F %T')" "$1" >> "$LOG"; }

cleanup() {
  trap - TERM INT EXIT   # disarm so this runs exactly once
  log "STOP  peak_used=${peak_used_mb}MB peak_swap_used=${peak_swap_mb}MB"
  exit 0
}
trap cleanup TERM INT EXIT

total_mb=$(awk '/^MemTotal:/{print int($2/1024)}' /proc/meminfo)
log "START pid=$$ interval=${INT}s warn_avail<${WARN_MB}MB total=${total_mb}MB"

while :; do
  read -r memtotal memavail swaptotal swapfree < <(awk '
    /^MemTotal:/{mt=$2} /^MemAvailable:/{ma=$2}
    /^SwapTotal:/{st=$2} /^SwapFree:/{sf=$2}
    END{print mt, ma, st, sf}' /proc/meminfo)

  used_mb=$(( (memtotal - memavail) / 1024 ))
  avail_mb=$(( memavail / 1024 ))
  swapused_mb=$(( (swaptotal - swapfree) / 1024 ))

  (( used_mb  > peak_used_mb )) && peak_used_mb=$used_mb
  (( swapused_mb > peak_swap_mb )) && peak_swap_mb=$swapused_mb

  # log the climb only when a meaningful new peak is reached
  if (( peak_used_mb >= last_logged_peak + 200 )); then
    log "PEAK  used=${peak_used_mb}MB avail=${avail_mb}MB swap_used=${swapused_mb}MB"
    last_logged_peak=$peak_used_mb
  fi

  if (( avail_mb < WARN_MB )); then
    if (( warned == 0 )); then
      log "WARN  MemAvailable=${avail_mb}MB < ${WARN_MB}MB  used=${used_mb}MB swap_used=${swapused_mb}MB  <-- NEAR OOM"
      warned=1
    fi
  else
    warned=0   # re-arm once we recover above the threshold
  fi

  sleep "$INT"
done
