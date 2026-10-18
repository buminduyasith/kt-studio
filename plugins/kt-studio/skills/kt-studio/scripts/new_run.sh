#!/usr/bin/env bash
# Creates the folder for one request, or returns the existing one so a whole session reuses it.
# Every feature has its own folder, and each video of it a run folder inside:
#   <output-dir>/features/<feature-slug>/runs/<run-id>/
# Usage: bash new_run.sh <output-dir> <feature-slug> [run-id]       slug: lowercase letters, digits, dashes
#   no run-id: today's run for this feature (created if missing)
#   run-id:    reuse exactly that run (for example to continue yesterday's work)
# The run id stays <date>-<feature>: the recorder names its demos after it, so it must be unique.
# Prints the run folder path on the last line.
set -euo pipefail

OUT="${1:?usage: new_run.sh <output-dir> <feature-slug> [run-id]}"
SLUG="${2:?feature-slug}"
# The slug names the recorder's demos, which accept only letters, digits, - and _.
if ! printf '%s' "$SLUG" | grep -Eq '^[a-z0-9][a-z0-9-]*$'; then
  echo "feature slug must be lowercase letters, digits and dashes, for example order-refunds (got: $SLUG)"; exit 1
fi
RUN_ID="${3:-$(date +%Y-%m-%d)-$SLUG}"
printf '%s' "$RUN_ID" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9_-]*$' || { echo "bad run id: $RUN_ID"; exit 1; }
RUN="$OUT/features/$SLUG/runs/$RUN_ID"
mkdir -p "$OUT"
python3 "$(dirname "$0")/project.py" --gitignore "$OUT"

if [ -d "$RUN" ]; then
  echo "reusing run: $RUN_ID"
else
  mkdir -p "$RUN/1-research" "$RUN/2-storyboard/shots" "$RUN/3-scripts" "$RUN/4-checks" "$RUN/5-videos"
  cat > "$RUN/run.json" <<EOF
{
  "id": "$RUN_ID",
  "feature": "$SLUG",
  "created": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "request": "",
  "instructions": [],
  "choices": {},
  "choices_help": "this video's answers (audience, show, environment, depth, ...), written by choices.py record",
  "apps": [],
  "apps_help": "the apps this video shows, written by apps.py: [{\"key\": \"shop-qa\", \"name\": \"Shop\", \"env\": \"qa\", \"url\": \"https://...\", \"login\": false, \"from\": \"request | instructions | docs | running | asked\"}]; [] for a video with no app",
  "storyboard": { "review": "", "artifact": "", "round": 0, "approved": false },
  "steps_values": "todo, in review (the storyboard, until approved), done, or skipped (for example screens for a project with no app)",
  "steps": { "research": "todo", "screens": "todo", "storyboard": "todo", "scripts": "todo", "rehearsal": "todo", "recording": "todo", "checks": "todo", "delivered": "todo" }
}
EOF
  # Logins are never kept between runs: delete any a stopped run left behind (only KT Studio's own;
  # sessions the project keeps itself in .auth are left alone).
  if [ -s "$OUT/runtime/.auth/.kt-made" ]; then
    bash "$(dirname "$0")/login.sh" forget "$OUT" >/dev/null
    echo "deleted logins left by an earlier run"
  fi
  echo "new run: $RUN_ID"
fi
echo "$RUN"
