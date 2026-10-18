#!/usr/bin/env bash
# Brings a run's finished videos back from the runtime into the run folder.
#   5-videos/: <feature>-ui.mp4 / <feature>-code.mp4 with their .srt and .vtt (captions rebuilt phrase by phrase)
#   4-checks/: Argo's scene reports, mark times, word timings and cue log, for check_sync.py
#   5-videos/storyboard.delivered.json: the storyboard these videos follow, for patch.py plan later
# A take is copied only when it is newer than the run's copy, so a video updated by patch.py splice is
# never replaced by the older full take still in the runtime.
# Usage: bash collect.sh <output-dir> <run-dir>
set -euo pipefail

OUT="$(cd "${1:?usage: collect.sh <output-dir> <run-dir>}" && pwd)"
RUN="$(cd "${2:?run-dir}" && pwd)"
RT="$OUT/runtime"
ID="$(basename "$RUN")"
FEATURE="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['feature'])" "$RUN/run.json")"
collected=0

for part in ui code; do
  demo="$ID-$part"
  [ -f "$RT/videos/$demo.mp4" ] || continue
  if [ -f "$RUN/5-videos/$FEATURE-$part.mp4" ] && ! [ "$RT/videos/$demo.mp4" -nt "$RUN/5-videos/$FEATURE-$part.mp4" ]; then
    echo "kept $FEATURE-$part.mp4 (the run's copy is newer than the take in the runtime)"
    continue
  fi
  if [ -f "$RT/demos/$demo.beats.json" ] && [ -f "$RT/.argo/$demo/scene-report.json" ]; then
    (cd "$RT" && node tools/captions.mjs "$demo")
  fi
  for ext in mp4 srt vtt; do
    src="$RT/videos/$demo.$ext"
    [ -f "$src" ] && cp "$src" "$RUN/5-videos/$FEATURE-$part.$ext"
  done
  copy() { [ -f "$1" ] && cp "$1" "$RUN/4-checks/$2" || true; }
  copy "$RT/.argo/$demo/scene-report.json" "$part-scene-report.json"
  copy "$RT/.argo/$demo/.timing.json" "$part-timing.json"
  copy "$RT/.argo/$demo/cues.jsonl" "$part-cues.jsonl"
  copy "$RT/demos/$demo.beats.json" "$part-beats.json"
  collected=1
done
if [ "$collected" = 1 ] && [ -f "$RUN/2-storyboard/storyboard.json" ]; then
  cp "$RUN/2-storyboard/storyboard.json" "$RUN/5-videos/storyboard.delivered.json"
fi
ls -1 "$RUN/5-videos"
