#!/usr/bin/env bash
# Checks that everything kt-studio needs is in place: the tools on this computer, the project's
# settings (.kt-studio/config.yml), and the recorder runtime (Argo, Playwright and Chromium, the offline voice model).
# It changes nothing and needs no network. The skill runs it at the start of every run.
#
# Usage: bash doctor.sh [project-root] [--quiet] [--deep] [--data <plugin-data-dir>]
#   --quiet  print only problems and the result (the start of every run)
#   --deep   also start Chromium and speak one test sentence, about 10 s (init uses it)
#   --data   the plugin's data folder (${CLAUDE_PLUGIN_DATA}), where the shared recorder is installed
#
# Last lines: "doctor: ready", or "doctor: not ready" and numbered fixes. Each fix says who does it:
#   [you]    the person installs a tool on their computer
#   [init]   the person runs /kt-studio:init: it writes .kt-studio/ and is the only step that downloads
#            (the recorder, up to 1 GB the first time on a computer)
#   [setup]  the skill runs setup.sh --no-download: seconds, nothing is downloaded
# Exit 0 when ready, 1 when not.
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="." QUIET=0 DEEP=0 DATA=""
while [ $# -gt 0 ]; do
  case "$1" in
    --quiet) QUIET=1 ;;
    --deep) DEEP=1 ;;
    --data) DATA="${2:-}"; shift ;;
    -*) echo "unknown option: $1"; exit 2 ;;
    *) ROOT="$1" ;;
  esac
  shift
done
ROOT="$(cd "$ROOT" 2>/dev/null && pwd)" || { echo "no such folder: $ROOT"; exit 2; }

FIXES=()
title() { [ "$QUIET" = 1 ] || printf '\n%s\n' "$1"; }
ok() { [ "$QUIET" = 1 ] || printf '  ok    %s\n' "$1"; }
note() { [ "$QUIET" = 1 ] || printf '  -     %s\n' "$1"; }
# A note shown even with --quiet: the settings need a small change, but the run can go on.
tip() { printf '  TIP   %s\n' "$1"; }
warn() { printf '  warn  %s\n' "$1"; }
fail() {
  printf '  FAIL  %s\n' "$1"
  local f
  for f in "${FIXES[@]+"${FIXES[@]}"}"; do [ "$f" = "$2" ] && return; done
  FIXES+=("$2")
}
has() { command -v "$1" >/dev/null 2>&1; }
# Top-level "key: value" from the config, without its comment and quotes. No YAML library needed.
yml() { sed -n "s/^$1:[[:space:]]*//p" "$YML" | sed 's/[[:space:]]#.*//; s/^["'\'']//; s/["'\'']$//; s/[[:space:]]*$//' | head -1; }

# The skill version: plugin.json when the skill ships in a plugin, else "dev".
VERSION="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$SKILL_DIR/../../.claude-plugin/plugin.json" 2>/dev/null | head -1)"
[ "$QUIET" = 1 ] || echo "kt-studio ${VERSION:-dev} doctor: $ROOT"
# shellcheck source=studio-stamp.sh
. "$SKILL_DIR/scripts/studio-stamp.sh"

title "This computer"
if has node; then
  major="$(node -p 'process.versions.node.split(".")[0]')"
  [ "$major" -ge 20 ] && ok "node $(node -v)" || fail "node $(node -v) is too old" "[you] Install Node.js 20 or newer: https://nodejs.org (macOS: brew install node)"
else
  fail "node is not installed" "[you] Install Node.js 20 or newer: https://nodejs.org (macOS: brew install node)"
fi
has npm && ok "npm $(npm -v 2>/dev/null)" || fail "npm is not installed" "[you] Install Node.js 20 or newer (npm comes with it): https://nodejs.org"
if has python3 && python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
  ok "python $(python3 -c 'import platform; print(platform.python_version())')"
else
  fail "python 3.9 or newer is not installed" "[you] Install Python 3.9 or newer: https://www.python.org (macOS: brew install python)"
fi
if has ffmpeg && has ffprobe; then
  encoders="$(ffmpeg -hide_banner -encoders 2>/dev/null)"
  if printf '%s' "$encoders" | grep -q libx264 && printf '%s' "$encoders" | grep -qE ' aac '; then
    ok "ffmpeg $(ffmpeg -version 2>/dev/null | sed -n 's/^ffmpeg version \([^ ]*\).*/\1/p') (H.264 and AAC)"
  else
    fail "ffmpeg has no H.264 (libx264) or AAC encoder" "[you] Install a full ffmpeg build (macOS: brew install ffmpeg; Linux: sudo apt install ffmpeg)"
  fi
else
  fail "ffmpeg or ffprobe is not installed" "[you] Install ffmpeg (macOS: brew install ffmpeg; Linux: sudo apt install ffmpeg)"
fi
has git && ok "git $(git --version | awk '{print $3}')" || fail "git is not installed" "[you] Install git: https://git-scm.com"
has curl && ok "curl" || fail "curl is not installed" "[you] Install curl (macOS has it; Linux: sudo apt install curl)"

title "Project"
# Where the settings are: .kt-studio/config.yml.
KT_LAYOUT=none KT_CONFIG="$ROOT/.kt-studio/config.yml" KT_INSTRUCTIONS="$ROOT/.kt-studio/instructions.md" KT_OUT="$ROOT/.kt-studio"
eval "$(python3 "$SKILL_DIR/scripts/project.py" "$ROOT" --shell 2>/dev/null)" || true
[ "$KT_LAYOUT" = none ] || ROOT="$KT_ROOT"
YML="$KT_CONFIG"
rel() { case "$1" in "$ROOT"/*) printf '%s' "${1#"$ROOT"/}" ;; *) printf '%s' "$1" ;; esac; }
OUT_NAME="$(rel "$KT_OUT")"
instructions="$(rel "$KT_INSTRUCTIONS")"
if [ "$KT_LAYOUT" != none ]; then
  project="$(yml project)"
  ok "$(rel "$YML") (project: ${project:-not set}, output: $OUT_NAME)"
  if [ -f "$KT_INSTRUCTIONS" ]; then
    ok "instructions: $instructions"
    if ! grep -qiE '^##[[:space:]]+Addresses' "$KT_INSTRUCTIONS"; then
      tip "$instructions has no ## Addresses table yet: this run adds the services and addresses it uses (scripts/apps.py), so the next run finds them there"
    fi
  else
    note "no $instructions yet (your rules, your services and where they run): the first run that shows an app creates it"
  fi
  if grep -qiE '^##[[:space:]]+Logging in' "$KT_INSTRUCTIONS" 2>/dev/null \
    && ! sed -n '/^##[[:space:]]*Logging in/,/^##[[:space:]]/p' "$KT_INSTRUCTIONS" | grep -qiE '^\|.*How'; then
    tip "## Logging in in $instructions is written as sentences: make it a table (Service | Environment | How | The person runs | Session file) so every run follows it exactly. /kt-studio:init can draft it"
  fi
  # A knowledge source that is not on this computer: research skips it.
  while IFS= read -r missing; do
    [ -n "$missing" ] && tip "$missing: research skips it. Fix the path under knowledge: in $(rel "$YML"), or delete the line"
  done < <(python3 "$SKILL_DIR/scripts/sources.py" "$ROOT" --check 2>/dev/null)
  WORD_TIMING="$(sed -n 's/^[[:space:]]*word_timing:[[:space:]]*\([a-z]*\).*/\1/p' "$YML" | head -1)"
  VOICE="$(sed -n '/^voice:/,/^[^[:space:]#]/s/^[[:space:]]*name:[[:space:]]*\([a-z_]*\).*/\1/p' "$YML" | head -1)"
else
  fail "no KT Studio settings in $ROOT (.kt-studio/config.yml)" "[init] Set up this project: /kt-studio:init"
fi
if has playwright-cli; then
  ok "playwright-cli $(playwright-cli --version 2>/dev/null) (opens the window where you log in, when a page needs it)"
else
  note "playwright-cli not installed (only needed when a page needs a login: npm install -g @playwright/cli@0.1.13)"
fi

title "Recorder runtime"
OUT="$KT_OUT"
RT="$OUT/runtime"
# Only /kt-studio:init downloads. When everything big is already on this computer (the shared recorder
# of this version, Chromium), a refresh without downloads fixes the rest in seconds.
SHARED="${DATA:-$(plugin_data_dir "$SKILL_DIR")}"
INSTALL="[init] Install the recorder: /kt-studio:init (the only step that downloads: up to 1 GB the first time on this computer)"
REFRESH="[setup] bash $SKILL_DIR/scripts/setup.sh $OUT${SHARED:+ $SHARED} --no-download (seconds, nothing is downloaded)"
if [ -n "$SHARED" ]; then
  [ -f "$SHARED/recorder-$(deps_stamp "$SKILL_DIR")/.ready" ] && SETUP="$REFRESH" || SETUP="$INSTALL"
else
  [ "$(cat "$OUT/runtime/.kt-deps-stamp" 2>/dev/null)" = "$(deps_stamp "$SKILL_DIR")" ] && SETUP="$REFRESH" || SETUP="$INSTALL"
fi
pinned() { sed -n "s|.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*|\1|p" "$SKILL_DIR/assets/studio/package.json" | head -1; }
installed() { sed -n 's/^[[:space:]]*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$RT/node_modules/$1/package.json" 2>/dev/null | head -1; }
if [ ! -d "$RT/node_modules" ]; then
  fail "no runtime yet at $RT (first run in this project)" "$SETUP"
else
  for pkg in @argo-video/cli playwright kokoro-js; do
    want="$(pinned "$pkg")" have="$(installed "$pkg")"
    if [ -z "$have" ]; then fail "$pkg is missing" "$SETUP"
    elif [ "$have" != "$want" ]; then fail "$pkg $have, this skill needs $want" "$SETUP"
    else ok "$pkg $have"; fi
  done
  if [ -L "$RT/node_modules" ]; then
    note "recorder packages and voice model: shared by every project ($(dirname "$(readlink "$RT/node_modules")"))"
  fi
  chrome="$(cd "$RT" && node -p 'require("playwright").chromium.executablePath()' 2>/dev/null)"
  if [ -n "$chrome" ] && [ -e "$chrome" ]; then ok "Chromium for Playwright"; else fail "Chromium for Playwright is not installed" "$INSTALL"; fi
  CACHE="$RT/node_modules/@huggingface/transformers/.cache"
  if [ -f "$CACHE/onnx-community/Kokoro-82M-v1.0-ONNX/onnx/model_quantized.onnx" ]; then
    ok "voice model (Kokoro 82M, offline)"
  else
    fail "voice model not downloaded" "$SETUP"
  fi
  if [ -f "$CACHE/Xenova/whisper-base.en/onnx/encoder_model.onnx" ]; then
    ok "word timing model (Whisper base.en)"
  elif [ "${WORD_TIMING:-estimate}" = whisper ]; then
    fail "word_timing is whisper, but its model (about 150 MB) is not downloaded" "$INSTALL"
  else
    note "Whisper not downloaded (only for voice.word_timing: whisper)"
  fi
  stamp="$(cat "$RT/.kt-studio-stamp" 2>/dev/null)"
  if [ -n "$stamp" ] && [ "$stamp" = "$(studio_stamp "$SKILL_DIR")" ]; then
    ok "studio files match this skill version"
  elif [ -z "$stamp" ]; then
    fail "setup did not finish here (it was stopped, or ran with an older skill)" "$SETUP"
  else
    fail "studio files are older than this skill (it was updated)" "$SETUP"
  fi
  if grep -qxF '!config.yml' "$OUT/.gitignore" 2>/dev/null; then
    ok "$OUT_NAME: git ignores everything but the settings"
  elif [ -f "$OUT/.gitignore" ] && [ ! -f "$OUT/config.yml" ]; then
    ok "$OUT_NAME is ignored by git"
  else
    fail "$OUT_NAME/.gitignore is missing or would hide the settings from git" "$SETUP"
  fi
  sessions="$(cd "$RT/.auth" 2>/dev/null && ls -1 -- kt-*.json 2>/dev/null | sed 's/^kt-//; s/\.json$//' | tr '\n' ' ')"
  [ -n "$sessions" ] && note "logins of the current run: $sessions(deleted when the run ends)"
fi

title "Disk"
free_kb="$(df -Pk "$ROOT" 2>/dev/null | awk 'NR==2 {print $4}')"
need_kb=$([ -d "$RT/node_modules" ] && echo 1048576 || echo 2621440)
if [ "${free_kb:-0}" -ge "$need_kb" ]; then
  ok "$((free_kb / 1048576)) GB free"
else
  fail "only $((${free_kb:-0} / 1024)) MB free" "[you] Free at least $((need_kb / 1048576)) GB of disk space next to the project"
fi

if [ "$DEEP" = 1 ] && [ ${#FIXES[@]} -eq 0 ]; then
  title "Live test"
  if (cd "$RT" && node --input-type=module -e '
      import { createRequire } from "node:module";
      const { chromium } = createRequire(process.cwd() + "/package.json")("playwright");
      const browser = await chromium.launch();
      const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
      await page.setContent("<h1>kt-studio</h1>");
      if (await page.textContent("h1") !== "kt-studio") process.exit(1);
      await browser.close();' >/dev/null 2>&1); then
    ok "Chromium starts and renders a page"
  else
    fail "Chromium does not start" "[you] On Linux, Chromium needs system libraries: cd $RT && npx playwright install-deps chromium (asks for sudo)"
  fi
  WAV="$RT/videos/.doctor.wav"
  if (cd "$RT" && VOICE="${VOICE:-af_heart}" WAV="$WAV" node --input-type=module -e '
      const { KokoroTTS } = await import("kokoro-js");
      const tts = await KokoroTTS.from_pretrained("onnx-community/Kokoro-82M-v1.0-ONNX", { dtype: "q8" });
      const audio = await tts.generate("The studio is ready.", { voice: process.env.VOICE });
      await audio.save(process.env.WAV);' >/dev/null 2>&1) && [ -s "$WAV" ]; then
    secs="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$WAV" 2>/dev/null)"
    ok "voice ${VOICE:-af_heart} speaks (${secs%%.*}.$(printf '%s' "${secs#*.}" | cut -c1) s test line)"
  else
    fail "the voice model does not speak (voice ${VOICE:-af_heart})" "$SETUP"
  fi
  rm -f "$WAV"
fi

echo
if [ ${#FIXES[@]} -eq 0 ]; then
  echo "doctor: ready"
  exit 0
fi
echo "doctor: not ready"
i=1
for f in "${FIXES[@]}"; do echo "  $i. $f"; i=$((i + 1)); done
exit 1
