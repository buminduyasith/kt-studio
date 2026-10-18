#!/usr/bin/env bash
# Checks everything a take needs, in seconds, before minutes of recording are spent on it.
# Project-specific checks (roles, demo data, settings) belong in the instructions' "Before the run".
#
# Usage: bash preflight.sh <output-dir> [--run <run-dir>] [--app <key>=<url>]... [--session <key>=<file>]... [--repo <path>@<ref>]...
#   --run: the apps of run.json "apps", each with its login (the session apps.py recorded). Use this.
#   --logins-only: only the apps and their logins (take.sh runs it before every Part A take).
#   bash preflight.sh .kt-studio --app shop-qa=https://qa.acme.example --repo ./api@origin/main --repo ./web@origin/main
# One --app per app the take shows (the keys and URLs in run.json "apps"). --env is the old spelling.
# --session: the app's login is a file the project keeps itself (its own login script), not one KT Studio
# saved, for example --session shop-qa=../../.auth-team/qa.json (relative to the runtime folder).
# Prints one line per check and exits 1 when any check fails.
set -uo pipefail

OUT="${1:?usage: preflight.sh <output-dir> [--run run-dir] [--app key=url]... [--repo path@ref]...}"
shift
RT="$OUT/runtime"
# --run <run-dir> adds --app (and --session for an app that logs in) for every app in run.json.
ONLY=0 args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --logins-only) ONLY=1; shift ;;
    --run)
      while IFS= read -r a; do [ -n "$a" ] && args+=("$a"); done < <(python3 - "${2:?run-dir}/run.json" <<'PY'
import json, sys
for a in json.load(open(sys.argv[1])).get("apps") or []:
    if a.get("url"):
        if a.get("login"):
            print("--session"); print(f"{a['key']}={a.get('session') or ''}")
            if a.get("how") == "script" and a.get("run"):
                print("--cmd"); print(f"{a['key']}={a['run']}")
        print("--app"); print(f"{a['key']}={a['url']}")
PY
)
      shift 2 ;;
    *) args+=("$1"); shift ;;
  esac
done
set -- "${args[@]+"${args[@]}"}"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
fails=0
ok() { printf 'ok    %s\n' "$1"; }
warn() { printf 'WARN  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; fails=$((fails + 1)); }

if [ "$ONLY" = 0 ]; then
for tool in node npm ffmpeg ffprobe python3 git curl; do
  command -v "$tool" >/dev/null 2>&1 && ok "$tool" || fail "$tool is not installed"
done
major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
[ "$major" -ge 20 ] && ok "node $major" || fail "Node 20 or newer is needed"

if [ -d "$RT/node_modules/@argo-video/cli" ]; then ok "runtime $RT"; else fail "no runtime: bash $SKILL_DIR/scripts/setup.sh $OUT"; fi
if [ -d "$RT/node_modules" ]; then
  (cd "$RT" && node -e 'const fs=require("fs");process.exit(fs.existsSync(require("playwright").chromium.executablePath())?0:1)' 2>/dev/null) \
    && ok "chromium" || fail "chromium missing: cd $RT && npx playwright install chromium"
  ls "$RT/node_modules/@huggingface/transformers/.cache/onnx-community" >/dev/null 2>&1 \
    && ok "voice model cached" || warn "voice model not cached yet: the first tts generate downloads it (about 90 MB)"
fi

# A busy computer makes the recorder's frames arrive late: the picture slides behind the voice.
cores="$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
load="$(uptime 2>/dev/null | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p' | tr -d ,)"
if [ -n "$load" ] && awk -v l="$load" -v c="$cores" 'BEGIN { exit !(l > c * 0.6) }'; then
  warn "the computer is busy (load $load on $cores cores): stop other work and wait until uptime shows a 1-minute load under $(awk -v c="$cores" 'BEGIN { printf "%.1f", c * 0.6 }') (a rehearsal that just ended clears in about a minute), or the picture can lag the voice"
else
  ok "computer not busy (load ${load:-?} on $cores cores)"
fi

free_kb="$(df -Pk "$OUT" 2>/dev/null | awk 'NR==2 {print $4}')"
[ "${free_kb:-0}" -ge 2097152 ] && ok "disk: $((free_kb / 1048576)) GB free" || fail "less than 2 GB free next to $OUT (a take needs about 1 GB while it records)"

if grep -qx 8765 "$RT"/tours/*/.server.port 2>/dev/null; then
  ok "port 8765 is this project's own tour server"
elif python3 -c 'import socket,sys; sys.exit(0 if socket.socket().connect_ex(("127.0.0.1", 8765)) == 0 else 1)'; then
  warn "port 8765 is busy: serve.sh picks the next free port and prints the KT_TOUR_URL to set"
else
  ok "port 8765 free"
fi
# One take at a time on a computer: two recordings share the CPU, and frames and cues then slip.
# Only real recorder processes (node running argo), not a shell whose command line mentions it.
left="$(ps -eo args= 2>/dev/null | awk '$1 ~ /(^|\/)node$/ && /\/argo (pipeline|record)/')"
if [ -z "$left" ]; then
  ok "no other take running on this computer"
elif printf '%s' "$left" | grep -q -- "$RT"; then
  fail "a take of this project is still running: bash $SKILL_DIR/scripts/cleanup.sh $OUT"
else
  fail "another project is recording on this computer; wait until it ends (two takes at once slip out of sync)"
fi

fi

# --session can come anywhere: collect them first.
SESSIONS=() CMDS=()
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  [ "${args[$i]}" = --session ] && SESSIONS+=("${args[$((i + 1))]:-}")
  [ "${args[$i]}" = --cmd ] && CMDS+=("${args[$((i + 1))]:-}")
done
while [ $# -gt 0 ]; do
  case "$1" in
    --session|--cmd)
      shift 2 ;;
    --app|--env)
      name="${2%%=*}"; url="${2#*=}"; shift 2
      code="$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$url" || true)"
      case "$code" in
        2*|3*|401|403) ok "$name reachable ($code)" ;;
        *) fail "$name not reachable at $url (HTTP ${code:-none})" ;;
      esac
      own="$(printf '%s\n' "${SESSIONS[@]+"${SESSIONS[@]}"}" | sed -n "s|^$name=||p" | head -1)"
      listed="$(printf '%s\n' "${SESSIONS[@]+"${SESSIONS[@]}"}" | grep -c "^$name=" || true)"
      cmd="$(printf '%s\n' "${CMDS[@]+"${CMDS[@]}"}" | sed -n "s|^$name=||p" | head -1)"
      how="${cmd:+the person runs: $cmd}"; how="${how:-the person logs in again in the window: bash $SKILL_DIR/scripts/login.sh open $OUT $name $url}"
      if [ "$listed" -gt 0 ] && { [ -z "$own" ] || [ ! -f "$own" ]; }; then
        fail "$name needs a login and has no session yet${own:+ ($own)}: $how"
      elif [ -n "$own" ]; then
        bash "$SKILL_DIR/scripts/login.sh" check "$OUT" "$name" "$url" "$own" >/dev/null 2>&1 \
          && ok "$name session valid ($own)" || fail "$name session expired ($own): $how"
      elif [ -f "$RT/.auth/kt-$name.json" ]; then
        bash "$SKILL_DIR/scripts/login.sh" check "$OUT" "$name" "$url" >/dev/null 2>&1 \
          && ok "$name session valid" || fail "$name session expired: log in again (login.sh open, then wait; references/config.md)"
      else
        ok "$name has no session (the app needs no login)"
      fi
      ;;
    --repo)
      repo="${2%@*}"; ref="${2##*@}"; shift 2
      if git -C "$repo" rev-parse --verify --quiet "${ref}^{commit}" >/dev/null; then
        ok "$repo at $ref ($(git -C "$repo" rev-parse --short "$ref"))"
      else
        fail "$repo has no ref $ref (git -C $repo fetch?)"
      fi
      ;;
    *) fail "unknown option $1"; shift ;;
  esac
done

if [ "$fails" -gt 0 ]; then echo "preflight: $fails problem(s)"; exit 1; fi
echo "preflight: ready"
