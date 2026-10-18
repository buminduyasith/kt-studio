#!/usr/bin/env bash
# Logs the recorder in for one run, without the agent ever typing a password: the person logs in.
#
#   bash login.sh probe <output-dir> <name> <app-url>          does this page need a login? (headless, no session)
#   bash login.sh open  <output-dir> <name> <app-url>          visible browser at the app; the person logs in
#   bash login.sh wait  <output-dir> <name> <app-url> [secs]   waits until the person is logged in, then saves
#   bash login.sh check <output-dir> <name> <app-url> [file]   is the saved session still valid? (headless;
#        [file]: a session the project keeps itself, for example .auth/dev.json)
#   bash login.sh close <output-dir> <name>
#   bash login.sh merge <output-dir> <run-id> <name|file> <name|file>...   one session for a take that
#        moves between apps: .auth/kt-<run-id>.json holds the cookies and storage of all of them (a name
#        is a session this script saved; a file is a session the project keeps itself)
#   bash login.sh forget <output-dir>                          closes the windows and deletes every saved
#        session of this project (end of the run: sessions are never kept between runs)
#
# <name> is the app's key for this run (run.json "apps", for example shop-qa). The session is saved to
# <output-dir>/runtime/.auth/kt-<name>.json (owner-only, git-ignored) and lives only until the run ends.
# Any login works (password, SSO, 2FA, magic link): the person does it in the window.
#
# .auth/ may also hold sessions the project keeps itself (some teams link .auth to their own folder and
# log in with their own script). This script never touches those: it writes only kt-* names, lists every
# file it makes in .auth/.kt-made, and forget deletes only what that list names.
#
# Logged in = the page stays on the app's own host and shows no password field (or shows
# KT_LOGGED_IN_TEXT, text only a signed-in person sees, when it is set). Single-page apps
# often sit on their own URL for several seconds before redirecting to the login page, and a valid
# session can pass through the login host for a moment, so the answer must hold STABLE times in a row.
set -euo pipefail

cmd="${1:?usage: login.sh probe|open|wait|check|close|merge|forget <output-dir> <name> ...}"
mkdir -p "${2:?output-dir}/runtime/.auth"
AUTH="$(cd "$2/runtime/.auth" && pwd)"
ENV_NAME="${3:-}"
[ "$cmd" = forget ] || [ -n "$ENV_NAME" ] || { echo "name needed: login.sh $cmd <output-dir> <name> ..."; exit 1; }
URL="${4:-}"
ORIGIN="$(printf '%s' "$URL" | grep -oE '^https?://[^/]+' || true)"
STABLE=6
# Browser sessions are named per project, so cleanup.sh closes only this project's.
TAG="$(printf '%s' "$AUTH" | cksum | cut -c1-6)"
SESSION="kt-$TAG-$ENV_NAME"
STATE="$AUTH/kt-$ENV_NAME.json"
PROFILE="$AUTH/kt-$ENV_NAME-profile"
MADE="$AUTH/.kt-made"
# made <file>: remember that this script made it, so forget may delete it later.
made() { touch "$MADE"; grep -qxF "$(basename "$1")" "$MADE" || basename "$1" >> "$MADE"; }
# ours <file>: did this script make it?
ours() { [ -f "$MADE" ] && grep -qxF "$(basename "$1")" "$MADE"; }
# playwright-cli keeps its working files in the current folder: keep them inside the output folder.
cd "$(dirname "$AUTH")"

# Signed in = on the app's own origin, and the page shows KT_LOGGED_IN_TEXT (text only a signed-in person
# sees, for example "Log out", when the instructions name one). Without it: no password field, which
# can misread email-first forms, SSO buttons and magic links as signed in; the person confirms in the chat.
MARK_B64="$(printf '%s' "${KT_LOGGED_IN_TEXT:-}" | base64 | tr -d '\n')"
# A visible password field always means "not signed in", even when the signed-in text is somewhere on the
# page (an app can keep its "Log out" button in the page while it shows the login form).
SIGNED_IN_JS="() => { const m = decodeURIComponent(escape(atob('$MARK_B64'))); const pw = [...document.querySelectorAll('input[type=password]')].some((e) => e.getClientRects().length > 0); const ok = !pw && (m ? document.body.innerText.includes(m) : true); return location.origin + (ok ? '#app' : '#login'); }"

# Prints "<origin>#app" or "<origin>#login" for the page in session $1.
where() {
  playwright-cli -s="$1" eval "$SIGNED_IN_JS" 2>/dev/null \
    | grep -o '"http[^"]*"' | head -1 | tr -d '"'
}

case "$cmd" in
  open)
    [ -n "$URL" ] || { echo "app-url needed"; exit 1; }
    # The window uses the recorder's own Chromium: playwright-cli would otherwise look for Google Chrome,
    # which many computers don't have. Running as root (a Linux server or container), Chromium needs its
    # sandbox off.
    # Always a fresh browser profile: a profile left by a run that was stopped halfway could still be
    # logged in, and logins are never kept between runs.
    playwright-cli -s="$SESSION" close >/dev/null 2>&1 || true
    if ours "$PROFILE"; then rm -rf -- "$PROFILE"; fi
    if ours "$STATE"; then rm -f -- "$STATE"; fi
    made "$PROFILE"
    RT_DIR="$(dirname "$AUTH")"
    CHROME="$(cd "$RT_DIR" && node -p 'require("playwright").chromium.executablePath()' 2>/dev/null || true)"
    CFG="$RT_DIR/.login-browser.json"
    if [ -n "$CHROME" ] && [ -e "$CHROME" ]; then
      SANDBOX=true; [ "$(id -u)" = 0 ] && SANDBOX=false
      printf '{"browser":{"browserName":"chromium","launchOptions":{"executablePath":"%s","chromiumSandbox":%s}}}\n' "$CHROME" "$SANDBOX" > "$CFG"
      playwright-cli -s="$SESSION" open "$URL" --headed --persistent --profile "$PROFILE" --config "$CFG" >/dev/null
    else
      playwright-cli -s="$SESSION" open "$URL" --headed --persistent --profile "$PROFILE" >/dev/null
    fi
    playwright-cli -s="$SESSION" resize 1920 1080 >/dev/null
    echo "browser open at $URL (session $SESSION). The person logs in now."
    ;;
  wait)
    [ -n "$ORIGIN" ] || { echo "app-url needed"; exit 1; }
    LIMIT="${5:-600}"
    hits=0
    for _ in $(seq 1 $((LIMIT / 3))); do
      at="$(where "$SESSION" || true)"
      if [ "$at" = "$ORIGIN#app" ]; then hits=$((hits + 1)); else hits=0; fi
      if [ "$hits" -ge "$STABLE" ]; then
        made "$STATE"
        playwright-cli -s="$SESSION" state-save "$STATE" >/dev/null
        chmod 600 "$STATE"
        # A login leaves a cookie or stored data behind; an empty session means the page only looked signed in.
        if node -e 'const s = require(process.argv[1]); process.exit((s.cookies || []).length || (s.origins || []).some((o) => (o.localStorage || []).length) ? 0 : 1)' "$STATE"; then
          echo "logged in, saved: $STATE"
          exit 0
        fi
        rm -f "$STATE"; hits=0
      fi
      sleep 3
    done
    echo "timeout: still at ${at:-unknown}"
    exit 1
    ;;
  check)
    [ -n "$ORIGIN" ] || { echo "app-url needed"; exit 1; }
    if [ -n "${5:-}" ]; then case "$5" in /*) STATE="$5" ;; *) STATE="$(dirname "$AUTH")/$5" ;; esac; fi
    [ -f "$STATE" ] || { echo "no saved session: $STATE"; exit 1; }
    # Uses the runtime's Playwright: playwright-cli state-load did not apply saved login cookies (0.1.13).
    RT="$(cd "$(dirname "$AUTH")" && pwd)" STATE="$STATE" URL="$URL" ORIGIN="$ORIGIN" STABLE="$STABLE" SIGNED_IN_JS="$SIGNED_IN_JS" node --input-type=module -e '
      import { createRequire } from "node:module";
      const { chromium } = createRequire(process.env.RT + "/package.json")("playwright");
      const { STATE, URL, ORIGIN } = process.env, STABLE = Number(process.env.STABLE);
      const SIGNED_IN = (0, eval)(process.env.SIGNED_IN_JS);
      const browser = await chromium.launch();
      const page = await (await browser.newContext({ storageState: STATE })).newPage();
      await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 60000 }).catch(() => {});
      let hits = 0, misses = 0, at = "";
      for (let i = 0; i < 30 && hits < STABLE && misses < STABLE; i++) {
        await page.waitForTimeout(2000);
        at = await page.evaluate(SIGNED_IN).catch(() => "loading");
        if (at === ORIGIN + "#app") { hits++; misses = 0; } else { misses++; hits = 0; }
      }
      await browser.close();
      console.log(hits >= STABLE ? "session valid" : `session expired (at ${at})`);
      process.exit(hits >= STABLE ? 0 : 1);
    '
    ;;
  close)
    playwright-cli -s="$SESSION" close >/dev/null 2>&1 || true
    echo "closed $SESSION"
    ;;
  merge)
    shift 3
    [ $# -ge 2 ] || { echo "usage: login.sh merge <output-dir> <run-id> <name|file> <name|file>..."; exit 1; }
    files=()
    for env in "$@"; do
      case "$env" in */*|*.json) f="$env" ;; *) f="$AUTH/kt-$env.json" ;; esac
      [ -f "$f" ] || { echo "no saved session: $f"; exit 1; }
      files+=("$f")
    done
    set -- "${files[@]}"
    made "$STATE"
    OUT_STATE="$STATE" AUTH="$AUTH" node -e '
      const fs = require("fs");
      const cookies = new Map(), origins = new Map();
      for (const file of process.argv.slice(1)) {
        const state = JSON.parse(fs.readFileSync(file, "utf8"));
        for (const c of state.cookies ?? []) cookies.set(`${c.name}|${c.domain}|${c.path}`, c);
        for (const o of state.origins ?? []) origins.set(o.origin, o);
      }
      fs.writeFileSync(process.env.OUT_STATE, JSON.stringify({ cookies: [...cookies.values()], origins: [...origins.values()] }, null, 2), { mode: 0o600 });
      console.log(`merged ${process.argv.length - 1} sessions: ${cookies.size} cookies, ${origins.size} origins -> ${process.env.OUT_STATE}`);
    ' "$@"
    ;;
  probe)
    [ -n "$ORIGIN" ] || { echo "app-url needed"; exit 1; }
    # A fresh browser with no session: does the app show itself, or a login page (here or on another host)?
    RT="$(cd "$(dirname "$AUTH")" && pwd)" URL="$URL" ORIGIN="$ORIGIN" STABLE="$STABLE" SIGNED_IN_JS="$SIGNED_IN_JS" node --input-type=module -e '
      import { createRequire } from "node:module";
      const { chromium } = createRequire(process.env.RT + "/package.json")("playwright");
      const { URL, ORIGIN } = process.env, STABLE = Number(process.env.STABLE);
      const SIGNED_IN = (0, eval)(process.env.SIGNED_IN_JS);
      const browser = await chromium.launch();
      const page = await (await browser.newContext()).newPage();
      const res = await page.goto(URL, { waitUntil: "domcontentloaded", timeout: 60000 }).catch((e) => e);
      if (res instanceof Error) { console.log(`not reachable: ${URL}`); await browser.close(); process.exit(1); }
      let same = 0, at = "", last = "";
      for (let i = 0; i < 20 && same < STABLE; i++) {
        await page.waitForTimeout(1000);
        at = await page.evaluate(SIGNED_IN).catch(() => "loading");
        same = at === last ? same + 1 : 0; last = at;
      }
      await browser.close();
      if (at === ORIGIN + "#app") { console.log("no login needed"); process.exit(0); }
      console.log(`login needed (the page shows a login at ${at.replace(/#.*$/, "")})`);
      process.exit(2);
    '
    ;;
  forget)
    TAG_ALL="kt-$TAG-"
    for session in $(playwright-cli list 2>/dev/null | grep -oE "${TAG_ALL}[A-Za-z0-9_-]+" | sort -u); do
      playwright-cli -s="$session" close >/dev/null 2>&1 || true
    done
    # Only what this script made: never a session the project keeps itself.
    n=0
    if [ -f "$MADE" ]; then
      while IFS= read -r f; do
        case "$f" in kt-*) ;; *) continue ;; esac
        [ -e "$AUTH/$f" ] && { rm -rf -- "${AUTH:?}/$f"; n=$((n + 1)); }
      done < "$MADE"
      rm -f -- "$MADE"
    fi
    echo "forgot $n login file(s) KT Studio made in $AUTH (other files there are left alone)"
    ;;
  *)
    echo "unknown command: $cmd"; exit 1 ;;
esac
