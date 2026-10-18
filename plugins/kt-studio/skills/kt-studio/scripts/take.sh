#!/usr/bin/env bash
# One command for a rehearsal or a take of one part, so no step or path is missed:
#   make_scenes, stage, voice (only changed lines are voiced again), word timings, the code tour server,
#   the recorder, then the checks. The tour server is always stopped again, also after a failure.
#
# Usage: bash take.sh rehearse <output-dir> <run-dir> <ui|code> [--patch <first> <last>]
#        bash take.sh record   <output-dir> <run-dir> <ui|code> [--patch <first> <last>]
#
#   rehearse  KT_DRY=1: every write is blocked. Ends with check_sync on the rehearsal's own log.
#             With --patch, only first..last run at real pace (the rest runs fast): retry a few scenes
#             in a minute instead of rehearsing the whole part.
#   record    The real take. Run preflight.sh and get the gate-2 yes first. Then collect.sh and both
#             checks (check_video with --marks and the contact sheet, check_sync). With --patch it
#             records a patch take for patch.py splice (references/update.md) and checks only that.
#
# Pass the take's settings as environment variables, as for any Argo command: KT_BASE_URL and
# KT_STATE (Part A), KT_NAME, KT_TRANSCRIBE. When KT_BASE_URL is not set, Part A takes the first app's
# URL from run.json "apps", and it stops early when the app does not answer there. When KT_STATE is not
# set, it takes the login run.json names (the app's session, or .auth/kt-<run-id>.json for several apps),
# and it refuses to start when an app needs a login and its session is missing or expired. A take runs in real time and then encodes, about 2 to 3
# times the video's length: start it in the background and wait.
set -euo pipefail

MODE="${1:?usage: take.sh rehearse|record <output-dir> <run-dir> <ui|code> [--patch <first> <last>]}"
OUT="$(cd "${2:?output-dir}" && pwd)"
RUN="$(cd "${3:?run-dir}" && pwd)"
PART="${4:?part: ui or code}"
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RT="$OUT/runtime"
ID="$(basename "$RUN")"
DEMO="$ID-$PART"
PATCH=()
if [ "${5:-}" = "--patch" ]; then
  PATCH=(--patch "$PART" "${6:?first scene}" "${7:?last scene}")
  DEMO="$ID-$PART-patch"
fi
case "$MODE" in rehearse|record) ;; *) echo "mode must be rehearse or record"; exit 2 ;; esac
case "$PART" in ui|code) ;; *) echo "part must be ui or code"; exit 2 ;; esac

step() { printf '\n== %s\n' "$1"; }

# A rehearsal or take cut off halfway (a command time limit) can leave its recorder running, and a second
# one on top of it slips and fails. Stop first and say how to clear it.
left="$(ps -eo args= 2>/dev/null | awk '$1 ~ /(^|\/)node$/ && /\/argo (pipeline|record)/' | grep -F -- "$RT" || true)"
if [ -n "$left" ]; then
  echo "A recording of this project is still running (an earlier rehearsal or take that was cut off)."
  echo "Clear it first: bash $SKILL_DIR/scripts/cleanup.sh $OUT"
  exit 2
fi

# Part A needs the app's address. When KT_BASE_URL is not set, take the first app of the run
# (run.json "apps"; an older run's "environment": "<name> <url>"), and stop with a clear message when
# there is none or the app doesn't answer: the recorder's own default (localhost:3000) only gives a
# confusing page.goto error. A saved login of the run is used the same way when KT_STATE is not set.
if [ "$PART" = ui ]; then
  read -r _ APP_URL < <(python3 -c "import json,sys
d = json.load(open(sys.argv[1]))
apps = d.get('apps') or []
if apps:
    print(apps[0].get('key') or apps[0].get('name') or 'app', apps[0].get('url') or '')
else:
    env = str(d.get('environment') or '').split()
    url = next((w for w in env if w.startswith(('http://', 'https://'))), '')
    print(env[0] if env and not env[0].startswith('http') else 'app', url)" "$RUN/run.json")
  if [ -z "${KT_BASE_URL:-}" ] && [ -n "${APP_URL:-}" ]; then
    KT_BASE_URL="$APP_URL"
    echo "KT_BASE_URL not set: using $KT_BASE_URL from run.json"
  fi
  if [ -z "${KT_BASE_URL:-}" ]; then
    echo "KT_BASE_URL is not set and run.json names no app URL."
    echo "Add the app to run.json \"apps\", or set it, for example: KT_BASE_URL=http://localhost:8080 bash take.sh ..."
    exit 2
  fi
  export KT_BASE_URL
  if ! curl -s -o /dev/null --max-time 10 "$KT_BASE_URL"; then
    echo "The app does not answer at $KT_BASE_URL. Start it (see \"Before each take\" in the project instructions), then run this again."
    exit 2
  fi
  # The login comes from run.json (apps.py wrote how each app logs in and where its session is), never
  # from memory: a take of an app that needs a login does not start without a valid session.
  if [ -z "${KT_STATE:-}" ]; then
    LOGIN="$(python3 - "$RUN/run.json" "$RT/.auth/kt-$ID.json" <<'PY'
import json, sys
apps = [a for a in json.load(open(sys.argv[1])).get("apps") or [] if a.get("login")]
if not apps:
    print("none")
elif len(apps) == 1:
    a = apps[0]
    print(f"one\t{a.get('session') or ''}\t{a['key']}\t{a.get('how', 'window')}\t{a.get('run', '')}")
else:
    print(f"many\t{sys.argv[2]}\t" + " ".join(a.get("session") or "" for a in apps))
PY
)"
    case "$LOGIN" in
      none) ;;
      one*)
        IFS=$'\t' read -r _ SESSION KEY HOW CMD <<< "$LOGIN"
        if [ ! -f "$SESSION" ]; then
          echo "$KEY needs a login and has no session yet ($SESSION)."
          [ "$HOW" = script ] && echo "Ask the person to run their login command: $CMD" \
            || echo "Open the login window: bash $SKILL_DIR/scripts/login.sh open $OUT $KEY $KT_BASE_URL"
          exit 2
        fi
        export KT_STATE="$SESSION"; echo "using the login of $KEY: $KT_STATE" ;;
      many*)
        IFS=$'\t' read -r _ MERGED FILES <<< "$LOGIN"
        if [ ! -f "$MERGED" ]; then
          echo "This take shows several apps that need a login: merge their sessions first:"
          echo "bash $SKILL_DIR/scripts/login.sh merge $OUT $ID $FILES"
          exit 2
        fi
        export KT_STATE="$MERGED"; echo "using the merged login: $KT_STATE" ;;
    esac
  fi
  # Every login still valid? (A session can expire within the run.) preflight.sh checks each one.
  if ! bash "$SKILL_DIR/scripts/preflight.sh" "$OUT" --run "$RUN" --logins-only; then
    echo "A login is missing or expired: the person logs in again (see NEXT from apps.py), then run this again."
    exit 2
  fi
fi

TOUR="$RT/tours/$ID"
cleanup() { [ "$PART" = code ] && bash "$SKILL_DIR/scripts/serve.sh" stop "$TOUR" >/dev/null 2>&1 || true; }
trap cleanup EXIT

step "voice files and staging"
python3 "$SKILL_DIR/scripts/make_scenes.py" "$RUN"
bash "$SKILL_DIR/scripts/stage.sh" "$OUT" "$RUN" "${PATCH[@]}"

step "voice and word timings"
(cd "$RT" && npx argo tts generate "demos/$DEMO.scenes.json" && node tools/beats.mjs "$DEMO")

if [ "$PART" = code ]; then
  step "code tour server"
  url="$(bash "$SKILL_DIR/scripts/serve.sh" start "$TOUR" | tail -1)"
  export KT_TOUR_URL="$url"
  echo "tour: $url"
fi

if [ "$MODE" = rehearse ]; then
  step "rehearsal (writes blocked)"
  (cd "$RT" && KT_DRY=1 npx argo record "$DEMO")
  step "sync check of the rehearsal"
  python3 "$SKILL_DIR/scripts/check_sync.py" "$RT/.argo/$DEMO"
  exit 0
fi

step "take"
(cd "$RT" && npx argo pipeline "$DEMO")
cleanup

if [ ${#PATCH[@]} -gt 0 ]; then
  step "sync check of the patch take"
  python3 "$SKILL_DIR/scripts/check_sync.py" "$RT/.argo/$DEMO"
  echo
  echo "next: python3 $SKILL_DIR/scripts/patch.py splice $RUN $PART"
  exit 0
fi

step "collect"
bash "$SKILL_DIR/scripts/collect.sh" "$OUT" "$RUN"
FEATURE="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['feature'])" "$RUN/run.json")"
status=0
step "picture check"
python3 "$SKILL_DIR/scripts/check_video.py" "$RUN/5-videos/$FEATURE-$PART.mp4" \
  --report "$RUN/4-checks/$PART-scene-report.json" --sheet "$RUN/4-checks/$PART-sheet.png" \
  --marks "$RUN/4-checks/$PART-timing.json" || status=1
step "sync check"
python3 "$SKILL_DIR/scripts/check_sync.py" "$RUN/4-checks" "$PART" || status=1
exit $status
