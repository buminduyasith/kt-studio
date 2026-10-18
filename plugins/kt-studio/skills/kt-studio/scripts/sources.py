#!/usr/bin/env python3
"""The places research reads before the code: the project's knowledge sources and a feature's own.

`knowledge:` in .kt-studio/config.yml lists them for the whole project, one entry per line. An empty
list (`knowledge: []`) means code only. Four kinds of entry:

    docs/                           a folder or file in the project (relative to the project root)
    ~/notes/shop-design/            a folder or file outside the project (absolute, or starting with ~)
    https://wiki.acme.example/...   a web page, read with the web fetch tool (never logged in to)
    connector: Help center space    a wiki or drive read through a tool already connected in Claude Code

A feature can add its own in features/<feature>/feature.yml (`knowledge:`), and a video can be "code
only" (`sources: code-only` in feature.yml or in run.json `choices`): then the project's list is
skipped, while the feature's own entries are still read.

Usage: python3 sources.py <root> [<feature>] [--run <run-folder>] [--json] [--check]
  Prints what research reads for this video, each with its kind and whether it is there.
  --json   the same as JSON, for scripts
  --check  only the problems (a path that is not on this computer), for the doctor; prints nothing when
           all is well. Always exits 0: a missing source is a tip, not a failure.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import project  # noqa: E402

CONNECTOR = re.compile(r"^connector:\s*(.+)$", re.I)


def config_entries(proj: project.Project) -> list[str]:
    """The `knowledge:` list of config.yml, as written (comments and quotes removed)."""
    text = proj.config.read_text(errors="ignore") if proj.config.is_file() else ""
    m = re.search(r"^knowledge:[ \t]*(.*)\n((?:[ \t]+.*\n?|[ \t]*\n)*)", text, re.M)
    if not m:
        return []
    out = []
    for line in m.group(2).splitlines():
        item = re.match(r"^\s+-\s*(.+?)\s*$", line)
        if item:
            out.append(clean(item.group(1)))
    return [e for e in out if e]


def clean(entry: str) -> str:
    entry = entry.strip()
    if entry.startswith(("'", '"')):
        try:
            return json.loads(entry) if entry.startswith('"') else entry.strip("'")
        except ValueError:
            return entry.strip("'\"")
    return re.sub(r"\s+#.*$", "", entry).strip()


def describe(proj: project.Project, entry: str, origin: str) -> dict:
    """One entry with its kind, where it points and whether it is there."""
    item = {"entry": entry, "from": origin}
    con = CONNECTOR.match(entry)
    if con:
        return {**item, "kind": "connector", "what": con.group(1).strip(),
                "how": "read it with a tool already connected in Claude Code; never log in for the person"}
    if re.match(r"^https?://", entry, re.I):
        return {**item, "kind": "link", "how": "read it with the web fetch tool; a page that needs a login is "
                                                 "skipped (ask the person to paste it or save it as a file)"}
    path = Path(entry).expanduser()
    if not path.is_absolute():
        path = proj.root / entry
    try:
        path.resolve().relative_to(proj.root.resolve())
        inside = True
    except ValueError:
        inside = False
    return {**item, "kind": "project" if inside else "outside", "path": str(path), "there": path.exists()}


def feature_settings(proj: project.Project, feature: str) -> dict:
    if not feature:
        return {}
    import choices  # here, not at the top: choices imports this module
    return choices.read_yml(proj.feature(feature) / "feature.yml")


def collect(proj: project.Project, feature: str = "", run: Path | None = None) -> dict:
    saved = feature_settings(proj, feature)
    picked = ""
    if run and (run / "run.json").is_file():
        picked = json.loads((run / "run.json").read_text()).get("choices", {}).get("sources", "")
    picked = picked or (saved.get("sources") if isinstance(saved.get("sources"), str) else "")
    code_only = picked == "code-only"
    entries = [] if code_only else [describe(proj, e, "config.yml") for e in config_entries(proj)]
    extra = saved.get("knowledge") if isinstance(saved.get("knowledge"), list) else []
    seen = {e["entry"] for e in entries}
    entries += [describe(proj, e, "feature.yml") for e in extra if e not in seen]
    return {"code_only": code_only, "sources": entries}


def main() -> None:
    args = sys.argv[1:]
    flags = {a for a in args if a in ("--json", "--check")}
    run = ""
    if "--run" in args:
        i = args.index("--run")
        run = args[i + 1] if i + 1 < len(args) else ""
        args = args[:i] + args[i + 2:]
    rest = [a for a in args if a not in flags]
    if not rest:
        raise SystemExit(__doc__.split("Usage:")[1])
    proj = project.find(rest[0])
    feature = rest[1] if len(rest) > 1 else ""
    result = collect(proj, feature, Path(run) if run else None)
    if "--check" in flags:
        for s in result["sources"]:
            if s["kind"] in ("project", "outside") and not s["there"]:
                where = "a path outside the project, " if s["kind"] == "outside" else ""
                print(f"knowledge source not found: {s['entry']} ({where}in {s['from']})")
        return
    if "--json" in flags:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print("Read these before the code" + (" (code only: the project's list is skipped)" if result["code_only"] else "") + ":")
    if not result["sources"]:
        print("  nothing: code only")
    for s in result["sources"]:
        state = ""
        if s["kind"] in ("project", "outside"):
            state = "ok" if s["there"] else "NOT FOUND on this computer: skip it and say so in the brief"
        else:
            state = s["how"]
        print(f"  {s['kind']:<9} {s['entry']}  ({s['from']}) {state}")


if __name__ == "__main__":
    main()
