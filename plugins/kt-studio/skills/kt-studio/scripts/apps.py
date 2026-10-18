#!/usr/bin/env python3
"""Records the apps a run shows, and keeps the project's services and addresses up to date, in one step.

Usage: python3 apps.py <project-root> <run-dir> '<json list of apps>'

Each app: {"name": "Shop", "env": "qa", "url": "https://qa.acme.example",
           "from": "request | instructions | docs | running | asked",
           "for": "what it is for, one line", "talks": "what it talks to", "login_note": "how people log in"}
"name" is the service as the ## Services table names it, "env" the environment (a column of
## Addresses: local, dev, qa, ...). An empty list ('[]') records a video with no app.

For each app with an address it first runs `login.sh probe` (a fresh browser with no session): the
answer sets "login" (true when the page shows a login) and is printed, so the agent asks for a login
only where one is needed. When the probe cannot run (no recorder yet) or the app does not answer, the
given "login" stays and the line says so.

Then it settles how each app is logged in, from the "## Logging in" table of the instructions
(services.logins): none, window (the person logs in in a window KT Studio opens) or script (the person
runs the team's own login command, and KT Studio uses the session file it saves). No row: window when
the probe saw a login, else none. It prints the exact next steps under "NEXT", and records "login",
"how", "run" and "session" for each app, so take.sh and preflight.sh find the session by themselves
and refuse to record an app that needs a login without one.

Then it writes the list to <run>/run.json "apps" and updates the instructions file (services.py): a
## Services row for a new service, an ## Addresses column for a new environment, an address for an
empty cell. It never changes or removes what the person wrote. It prints one line per change, for the
agent to tell the user ("Added Shop (qa) to ## Addresses in .kt-studio/instructions.md").
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import project  # noqa: E402
import services  # noqa: E402


def key(app: dict) -> str:
    """A short name for files and browser sessions: "Help center" in dev -> help-center-dev."""
    words = f"{app['name']} {app.get('env') or ''}"
    return re.sub(r"[^a-z0-9]+", "-", words.lower()).strip("-") or "app"


def probe(out: Path, app: dict) -> None:
    """Sets app["login"] from login.sh probe, and prints what it found."""
    script = Path(__file__).with_name("login.sh")
    try:
        res = subprocess.run(["bash", str(script), "probe", str(out), app["key"], app["url"]],
                             capture_output=True, text=True, timeout=120)
        said = (res.stdout.strip().splitlines() or [res.stderr.strip() or "no answer"])[-1]
        code = res.returncode
    except subprocess.TimeoutExpired:
        said, code = "no answer in 120 s", 1
    if code == 0:
        app["login"] = False
    elif code == 2:
        app["login"] = True
    print(f"probe {app['name']} ({app.get('env') or '-'}) {app['url']}: {said}"
          + ("" if code in (0, 2) else f" (login stays {str(bool(app.get('login'))).lower()})"))


def settle_login(proj: project.Project, out: Path, app: dict) -> str | None:
    """Sets how / run / session from the ## Logging in table (or the probe). Returns a warning, if any."""
    row = services.login_for(proj.instructions, app["name"], app.get("env") or "")
    env = app.get("env") or ""
    warn = None
    how = row["how"] if row else ("window" if app.get("login") else "none")
    if row and how == "none" and app.get("login"):
        warn = (f"{app['name']} ({env}): ## Logging in says no login, but the page shows a login form: "
                "using the window. Ask the person whether to fix the table")
        how = "window"
    app["how"], app["run"], app["session"] = how, "", ""
    if how == "script":
        app["run"] = row["run"].replace("{env}", env)
        session = row["session"].replace("{env}", env)
        app["session"] = str((proj.root / session).resolve()) if session else ""
        if not app["run"] or not app["session"]:
            warn = (f"{app['name']} ({env}): ## Logging in says script, but the row needs both the command the "
                    "person runs and the session file it writes. Ask the person and fix the row")
    elif how == "window":
        app["session"] = str((out / "runtime" / ".auth" / f"kt-{app['key']}.json").resolve())
    app["login"] = how != "none"
    return warn


def next_steps(out: Path, run_id: str, apps: list[dict]) -> list[str]:
    login = Path(__file__).with_name("login.sh")
    lines = ["NEXT, logins (do exactly this; never type into a login form, never run a login command yourself):"]
    for a in apps:
        if not (a.get("url") or "").strip():
            continue
        k, u = a["key"], a["url"]
        if a["how"] == "none":
            lines.append(f"- {k}: no login.")
        elif a["how"] == "window":
            lines.append(f"- {k}: bash {login} open {out} {k} {u}  -> tell the person to log in in that window their "
                         f"own way, then: bash {login} wait {out} {k} {u}  (in the background, up to 10 minutes)")
        else:
            lines.append(f"- {k}: first try the saved session: bash {login} check {out} {k} {u} {a['session']}  "
                         f"-> if it says expired or no session, ask the person to run this themselves and tell you "
                         f"when it is done: {a['run']}  -> then check again")
    if sum(1 for a in apps if a.get("login")) > 1:
        files = " ".join(a["session"] for a in apps if a.get("login"))
        lines.append(f"- one take shows several apps: after all logins, bash {login} merge {out} {run_id} {files}")
    return lines


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit("usage: python3 apps.py <project-root> <run-dir> '<json list of apps>'")
    proj, run = project.find(sys.argv[1]), Path(sys.argv[2]).resolve()
    try:
        apps = json.loads(sys.argv[3])
        assert isinstance(apps, list) and all(isinstance(a, dict) and a.get("name") for a in apps)
    except (ValueError, AssertionError):
        sys.exit("apps must be a JSON list of objects, each with at least a \"name\"")
    for a in apps:
        if (a.get("url") or "").strip() and not (a.get("env") or "").strip():
            sys.exit(f"{a['name']}: give the environment too (\"env\": \"local\", \"dev\", \"qa\", ...), "
                     "the ## Addresses column this address belongs in")

    for a in apps:
        a["key"] = key(a)
        if (a.get("url") or "").strip():
            probe(run.parent.parent, a)
        else:
            a["login"] = False

    out = run.parent.parent
    for a in apps:
        warn = settle_login(proj, out, a)
        if warn:
            print("WARN " + warn)

    run_json = run / "run.json"
    data = json.loads(run_json.read_text())
    data["apps"] = [{"key": a["key"], "name": a["name"], "env": a.get("env", ""), "url": a.get("url", ""),
                     "login": bool(a.get("login")), "how": a["how"], "run": a["run"], "session": a["session"],
                     "from": a.get("from", "")} for a in apps]
    run_json.write_text(json.dumps(data, indent=2) + "\n")
    print(f"run.json: {len(apps)} app(s): " + (", ".join(
        f"{a['key']} = {a['name']} ({a.get('env') or '-'}) {a.get('url') or '(no address)'}" for a in apps) or "none (no app in this video)"))

    if not apps:
        return  # nothing learned: the services list stays as it is
    for line in services.update(proj.instructions, apps, proj.rel(proj.instructions)):
        print(line)
    print("\n".join(next_steps(out, run.name, apps)))


if __name__ == "__main__":
    main()
