#!/usr/bin/env bash
# Copies a run's scripts into the runtime, where the recorder can find them, and builds its code tour.
# The run folder stays the source of truth; the runtime copies are named <run-id>-ui / <run-id>-code.
# Usage: bash stage.sh <output-dir> <run-dir>      (relative or absolute paths)
#        bash stage.sh <output-dir> <run-dir> --patch <ui|code> <first-scene> <last-scene>
#   --patch stages a patch take, <run-id>-<part>-patch: the same script, the voice lines of first..last
#   only, and demos/<demo>.patch.json, which makes lib/sync.ts record that range and run the rest fast.
#   The delivered take's voice clips are reused, so only changed lines are voiced again.
set -euo pipefail

OUT="$(cd "${1:?usage: stage.sh <output-dir> <run-dir> [--patch <part> <first> <last>]}" && pwd)"
RUN="$(cd "${2:?run-dir}" && pwd)"
RT="$OUT/runtime"
ID="$(basename "$RUN")"
SRC="$RUN/3-scripts"

if [ "${3:-}" = "--patch" ]; then
  PART="${4:?--patch needs a part: ui or code}" FIRST="${5:?first scene}" LAST="${6:?last scene}"
  DEMO="$ID-$PART-patch"
  [ -f "$SRC/$PART.demo.ts" ] || { echo "no $SRC/$PART.demo.ts"; exit 1; }
  cp "$SRC/$PART.demo.ts" "$RT/demos/$DEMO.demo.ts"
  if [ -f "$SRC/cards.json" ]; then cp "$SRC/cards.json" "$RT/demos/$ID-cards.json"; fi   # loadCards() finds it by run id
  python3 - "$SRC/$PART.scenes.json" "$RT/demos/$DEMO" "$FIRST" "$LAST" <<'PY'
import json, sys
scenes, demo, first, last = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3], sys.argv[4]
order = [s["scene"] for s in scenes]
for name in (first, last):
    if name not in order:
        raise SystemExit(f"{name} is not a scene of this part ({', '.join(order)})")
a, b = order.index(first), order.index(last)
if a > b:
    raise SystemExit(f"{first} comes after {last}")
json.dump(scenes[a:b + 1], open(f"{demo}.scenes.json", "w"), indent=2, ensure_ascii=False)
json.dump({"first": first, "last": last, "order": order}, open(f"{demo}.patch.json", "w"), indent=2)
print(f"staged patch: {demo} records {first} to {last} ({b - a + 1} of {len(order)} scenes); the rest runs fast")
PY
  # Reuse the delivered take's voice clips (named by a hash of text and voice): only changed lines are voiced.
  if [ -d "$RT/.argo/$ID-$PART/clips" ]; then
    mkdir -p "$RT/.argo/$DEMO/clips"
    for clip in "$RT/.argo/$ID-$PART/clips/"*; do
      [ -e "$RT/.argo/$DEMO/clips/$(basename "$clip")" ] || cp "$clip" "$RT/.argo/$DEMO/clips/"
    done
  fi
else
  for part in ui code; do
    if [ -f "$SRC/$part.demo.ts" ]; then
      cp "$SRC/$part.demo.ts" "$RT/demos/$ID-$part.demo.ts"
      cp "$SRC/$part.scenes.json" "$RT/demos/$ID-$part.scenes.json"
      rm -f "$RT/demos/$ID-$part.patch.json"   # an ordinary take records everything
      if [ -f "$SRC/cards.json" ]; then cp "$SRC/cards.json" "$RT/demos/$ID-cards.json"; fi
      echo "staged demo: $ID-$part"
    fi
  done
fi

if [ -f "$SRC/tour.json" ]; then
  mkdir -p "$RT/tours/$ID"
  (cd "$RT" && node tools/build_tour.mjs "$SRC/tour.json" "tours/$ID")
  echo "built tour: $RT/tours/$ID"
fi
