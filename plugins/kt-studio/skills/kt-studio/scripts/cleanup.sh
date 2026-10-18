#!/usr/bin/env bash
# Stops everything kt-studio started, even after a failed run, then proves nothing is left.
# Usage: bash cleanup.sh <output-dir>
set -uo pipefail

OUT="${1:?usage: bash cleanup.sh <output-dir>}"
[ -d "$OUT/runtime" ] || { echo "nothing running (no runtime in $OUT)"; exit 0; }
RT="$(cd "$OUT/runtime" && pwd)"
# Only this project's processes: everything below is matched on this runtime's path.

for pidfile in "$RT"/tours/*/.server.pid; do
  [ -f "$pidfile" ] || continue
  kill "$(cat "$pidfile")" 2>/dev/null; rm -f "$pidfile" "$(dirname "$pidfile")/.server.port"
done
pkill -f "$RT/node_modules/.*argo.* (pipeline|record|tts|export)" 2>/dev/null
pkill -f "$RT/.argo/.*/playwright.record.config" 2>/dev/null
pkill -f "ffmpeg.*$RT/" 2>/dev/null
pkill -f "http.server .*--directory $RT/tours" 2>/dev/null
TAG="$(printf '%s' "$RT/.auth" | cksum | cut -c1-6)"
for session in $( (cd "$RT" && playwright-cli list 2>/dev/null) | grep -oE "kt-$TAG-[A-Za-z0-9_-]+" | sort -u); do
  (cd "$RT" && playwright-cli -s="$session" close >/dev/null 2>&1)
done
sleep 1

left="$(pgrep -fl "$RT/node_modules/.*argo|$RT/.argo/.*playwright.record.config|ffmpeg.*$RT/|http.server .*$RT" 2>/dev/null)"
if [ -n "$left" ]; then echo "still running:"; echo "$left"; exit 1; fi
echo "nothing running"
