#!/usr/bin/env bash
# Creates (or refreshes) the output folder: <output-dir>/runtime (shared recorder) and <output-dir>/features.
# Usage: bash setup.sh <output-dir> [shared-dir] [--no-download]        e.g. bash setup.sh ./.kt-studio
#   Downloads happen only here, and only from /kt-studio:init. Every other command runs it with
#   --no-download: it refreshes the studio files and links the shared recorder in seconds, and when
#   something would have to be downloaded it changes nothing, prints "needs a download" and exits 3
#   (the person runs /kt-studio:init).
#   shared-dir: where the recorder's packages and voice model are installed once for every project.
#   Default: the plugin's data folder (~/.claude/plugins/data/kt-studio-kt-studio), which Claude Code keeps
#   across updates and deletes on uninstall. A development copy of the skill (not in the plugin cache)
#   installs into the project instead.
# Safe to run again: after a skill update it refreshes the studio files. Installs pinned packages
# and the offline voice model (about 500 MB, once for every project) and the Playwright Chromium browser
# (about 500 MB, shared by every project and skipped when it is already installed), and the Whisper
# word-timing model (about 150 MB) when the project's voice.word_timing is whisper.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:?usage: bash setup.sh <output-dir> [shared-dir] [--no-download]}"
shift
NO_DOWNLOAD=0 SHARED_ARG=""
for arg in "$@"; do
  case "$arg" in
    --no-download) NO_DOWNLOAD=1 ;;
    *) SHARED_ARG="$arg" ;;
  esac
done
RT="$OUT/runtime"
# needs <what>: with --no-download, stop before changing anything more.
needs() { echo "needs a download ($1): run /kt-studio:init, which downloads it once for every project"; exit 3; }

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing: $1. $2"; exit 1; }; }
need node "Install Node.js 20 or newer."
need npm "It comes with Node.js."
need ffmpeg "macOS: brew install ffmpeg. Linux: apt install ffmpeg."
need python3 "Install Python 3."
need git "Install git."
need curl "Install curl."
major="$(node -p 'process.versions.node.split(".")[0]')"
[ "$major" -ge 20 ] || { echo "Node 20 or newer is needed (found $(node -v))."; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' || { echo "Python 3.9 or newer is needed (found $(python3 --version))."; exit 1; }
command -v playwright-cli >/dev/null 2>&1 || echo "note: playwright-cli is not installed. It is only needed to log in to a hosted site: npm install -g @playwright/cli@0.1.13"

. "$SKILL_DIR/scripts/studio-stamp.sh"
SHARED="${SHARED_ARG:-$(plugin_data_dir "$SKILL_DIR")}"
OUT="$(python3 -c 'import os, sys; print(os.path.abspath(sys.argv[1]))' "$OUT")" RT="$OUT/runtime"
CONFIG="$(python3 "$SKILL_DIR/scripts/project.py" "$(dirname "$OUT")" --shell | sed -n "s/^KT_CONFIG=//p" | tr -d "'")"
WORD_TIMING="$( { sed -n 's/^[[:space:]]*word_timing:[[:space:]]*\([a-z]*\).*/\1/p' "$CONFIG" 2>/dev/null || true; } | head -1)"
WHISPER_FILE="node_modules/@huggingface/transformers/.cache/Xenova/whisper-base.en/onnx/encoder_model.onnx"
if [ "$NO_DOWNLOAD" = 1 ]; then
  # Check first: nothing is changed when a download would be needed.
  if [ -n "$SHARED" ]; then
    [ -f "$SHARED/recorder-$(deps_stamp "$SKILL_DIR")/.ready" ] || needs "the recorder's packages and voice model, about 500 MB"
    BASE="$SHARED/recorder-$(deps_stamp "$SKILL_DIR")"
  else
    [ -d "$RT/node_modules" ] && [ "$(cat "$RT/.kt-deps-stamp" 2>/dev/null)" = "$(deps_stamp "$SKILL_DIR")" ] \
      || needs "the recorder's packages and voice model, about 500 MB"
    BASE="$RT"
  fi
  (cd "$BASE" && node -e 'process.exit(require("fs").existsSync(require("playwright").chromium.executablePath()) ? 0 : 1)' 2>/dev/null) \
    || needs "Chromium, about 500 MB"
  if [ "$WORD_TIMING" = whisper ] && [ ! -f "$BASE/$WHISPER_FILE" ]; then needs "the Whisper word-timing model, about 150 MB"; fi
fi

mkdir -p "$OUT/features" "$RT/demos" "$RT/tours" "$RT/videos" "$RT/.auth"
cp "$SKILL_DIR/assets/output-readme.md" "$OUT/README.md"
python3 "$SKILL_DIR/scripts/project.py" --gitignore "$OUT"
cp -R "$SKILL_DIR/assets/studio/." "$RT/"
cd "$RT"
if [ -n "$SHARED" ]; then
  # One copy of the pinned packages and the voice model for every project (about 500 MB), in the
  # plugin's data folder; the project links to it. Installed into a temporary folder and moved into
  # place at the end, so a second project setting up at the same time never sees half an install.
  DEPS="$SHARED/recorder-$(deps_stamp "$SKILL_DIR")"
  if [ ! -f "$DEPS/.ready" ]; then
    echo "installing the recorder once for every project: $DEPS"
    TMP="$DEPS.tmp-$$"
    rm -rf "$TMP"; mkdir -p "$TMP"
    cp "$SKILL_DIR/assets/studio/package.json" "$SKILL_DIR/assets/studio/package-lock.json" "$TMP/"
    if (cd "$TMP" && npm install --no-audit --no-fund \
      && node --input-type=module -e "const { KokoroTTS } = await import('kokoro-js'); await KokoroTTS.from_pretrained('onnx-community/Kokoro-82M-v1.0-ONNX', { dtype: 'q8' }); console.log('voice model ready')" \
      && touch .ready); then
      if [ -f "$DEPS/.ready" ]; then rm -rf "$TMP"; else rm -rf "$DEPS"; mv "$TMP" "$DEPS"; fi
    else
      rm -rf "$TMP"; echo "the install failed (see above); run setup again"; exit 1
    fi
  else
    echo "the recorder is already installed for every project: $DEPS"
  fi
  [ -f "$DEPS/.ready" ] || needs "the recorder's packages and voice model, about 500 MB"
  if [ -d node_modules ] && [ ! -L node_modules ]; then
    rm -rf node_modules
    echo "deleted this project's own copy of the recorder's packages (it uses the shared one now)"
  fi
  ln -sfn "$DEPS/node_modules" node_modules
  # Copies for older package versions are no longer used once each project has run setup again (the
  # doctor asks for it after every update). Keep them while any recording still runs from one.
  for old in "$SHARED"/recorder-*; do
    [ -d "$old" ] && [ "$old" != "$DEPS" ] || continue
    if ps -eo args= 2>/dev/null | grep -qF -- "$old"; then continue; fi
    rm -rf "$old" && echo "deleted an older shared copy: $(basename "$old")"
  done
elif [ "$NO_DOWNLOAD" = 0 ]; then
  npm install --no-audit --no-fund
  # The offline voice model (about 90 MB), now rather than in the middle of a run.
  node --input-type=module -e "const { KokoroTTS } = await import('kokoro-js'); await KokoroTTS.from_pretrained('onnx-community/Kokoro-82M-v1.0-ONNX', { dtype: 'q8' }); console.log('voice model ready')"
  deps_stamp "$SKILL_DIR" > .kt-deps-stamp
fi
if [ "$NO_DOWNLOAD" = 0 ]; then
  # On Linux, Chromium also needs system libraries: npx playwright install-deps chromium (asks for sudo).
  # Chromium is shared by every project already (Playwright keeps it in its own cache folder).
  npx playwright install chromium
  # Whisper word times (voice.word_timing: whisper): its model now, not in the middle of a run.
  if [ "$WORD_TIMING" = whisper ] && [ ! -f "$WHISPER_FILE" ]; then
    node --input-type=module -e "const { pipeline } = await import('@huggingface/transformers'); await pipeline('automatic-speech-recognition', 'Xenova/whisper-base.en'); console.log('word timing model ready')"
  fi
  (cd "${DEPS:-.}" && npm audit >/dev/null 2>&1) && echo "npm audit: clean" || (cd "${DEPS:-.}" && npm audit | tail -3)
fi
# Remember which version of the studio files this runtime has: doctor.sh compares it after an update.
studio_stamp "$SKILL_DIR" > .kt-studio-stamp
echo "ready: $OUT (runtime: $RT). Check it: bash $SKILL_DIR/scripts/doctor.sh <project-root>"
