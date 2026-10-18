"""Fill the fixed storyboard template with one feature's data. Every storyboard looks the same
because only storyboard.json changes; never edit the template per feature.

Usage: python3 build_storyboard.py <feature-dir>
Reads <feature-dir>/storyboard.json, writes <feature-dir>/storyboard.html.
Checks the data first and stops with a clear message when a required field is missing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "storyboard-template.html"
KINDS = {"ui", "code", "nav", "title", "diagram", "terminal"}
STATUSES = {"ready", "planned", "after-write"}


def diagram_problems(sid: str, use: dict, diagrams: dict) -> list[str]:
    """A diagram scene names a diagram from the top-level `diagrams` and the steps it lights."""
    d = diagrams.get(use.get("use"))
    if not d:
        return [f"{sid}: diagram.use must name one of the top-level diagrams ({sorted(diagrams) or 'none defined'})"]
    found = []
    names = {a if isinstance(a, str) else a.get("name") for a in d.get("actors", [])}
    for i, step in enumerate(d.get("steps", []), start=1):
        for side in ("from", "to"):
            if step.get(side) not in names:
                found.append(f"diagram {use['use']} step {i}: '{step.get(side)}' is not one of its actors")
    steps = use.get("steps", [])
    if not (isinstance(steps, list) and 1 <= len(steps) <= 2 and all(isinstance(n, int) and 1 <= n <= len(d.get("steps", [])) for n in steps)):
        found.append(f"{sid}: diagram.steps must be [first] or [first, last] within 1..{len(d.get('steps', []))}")
    return found


# Lists the template draws: a missing one would leave the artifact page blank.
LISTS = {"brief": ("readAs",), "overview": ("what", "explain", "repos", "notCovered", "set", "writes", "questions"),
         "production": ("pace", "pronounce", "deliver")}


def pronounce_pairs(value) -> list:
    """The pronounce map as [word, spoken] pairs: a list of pairs, or a map as in config.yml."""
    return [[k, v] for k, v in value.items()] if isinstance(value, dict) else value


def problems(data: dict, folder: Path) -> list[str]:
    found = []
    for key in ("meta", "brief", "overview", "parts", "production", "review"):
        if key not in data:
            found.append(f"missing top-level key: {key}")
    if not isinstance(data.get("review", []), list):
        found.append("review must be a list")
    for section, keys in LISTS.items():
        for key in keys:
            value = data.get(section, {}).get(key)
            if key == "pronounce" and isinstance(value, dict):
                continue
            if not isinstance(value, list):
                found.append(f"{section}.{key} must be a list (use [] when empty)")
    for repo in data.get("overview", {}).get("repos", []) or []:
        if not isinstance(repo.get("files", []), list):
            found.append(f"overview.repos {repo.get('name', '?')}: files must be a list")
    for part in data.get("parts", []):
        for chapter in part.get("chapters", []):
            for scene in chapter.get("scenes", []):
                if part.get("id") == "A" and scene.get("kind") in ("code", "nav", "diagram", "terminal"):
                    found.append(f"{scene.get('id', '?')}: {scene['kind']} scenes belong in Part B (Part A records the app)")
    seen = set()
    for part in data.get("parts", []):
        for chapter in part.get("chapters", []):
            for scene in chapter.get("scenes", []):
                sid = scene.get("id", "?")
                if sid in seen:
                    found.append(f"{sid}: duplicate scene id")
                seen.add(sid)
                for field in ("title", "voice", "kind", "status"):
                    if field not in scene:
                        found.append(f"{sid}: missing {field}")
                if scene.get("kind") not in KINDS:
                    found.append(f"{sid}: kind must be one of {sorted(KINDS)}")
                if scene.get("status") not in STATUSES:
                    found.append(f"{sid}: status must be one of {sorted(STATUSES)}")
                if scene.get("kind") in ("code", "nav") and not scene.get("code", {}).get("file"):
                    found.append(f"{sid}: code and nav scenes need code.file")
                if scene.get("kind") == "terminal":
                    t = scene.get("terminal", {})
                    if not (isinstance(t.get("cmd"), str) and t["cmd"].strip() and isinstance(t.get("output"), str)):
                        found.append(f"{sid}: terminal scenes need terminal.cmd and terminal.output (the real output, from running it)")
                    elif len(t["output"].splitlines()) > 14:
                        found.append(f"{sid}: terminal.output has {len(t['output'].splitlines())} lines; keep 14 or fewer (trim it, or pipe through head or jq)")
                if scene.get("kind") == "diagram":
                    found += diagram_problems(sid, scene.get("diagram", {}), data.get("diagrams", {}))
                shot = scene.get("shot")
                if shot and not (folder / shot).exists():
                    found.append(f"{sid}: shot not found: {shot}")
    return found


def spoken_words(text: str, pronounce: list) -> int:
    """Words the voice says: the pronounce map applied, and digits counted as spoken ("280" is four words)."""
    for word, say in pronounce:
        text = re.sub(rf"(?<![\w-]){re.escape(word)}(?![\w-])", say, text)
    words = 0
    for token in text.split():
        digits = re.sub(r"\D", "", token)
        words += max(1, len(digits) + (len(digits) > 2)) if digits else 1
    return words


def estimate(data: dict) -> list[str]:
    """Fills `seconds` (words / 2.4 + 2 at speed 0.9) when it is missing, and warns when a hand-set value is
    far from what the voice will take."""
    notes = []
    pronounce = pronounce_pairs(data.get("production", {}).get("pronounce", []))
    for part in data["parts"]:
        for chapter in part["chapters"]:
            for scene in chapter["scenes"]:
                est = round(spoken_words(scene["voice"], pronounce) / 2.4 + 2)
                if scene.get("kind") == "terminal":  # typing 40 ms a character, then the output line by line
                    t = scene.get("terminal", {})
                    est = max(est, round(len(t.get("cmd", "")) * 0.04 + 0.35 + len(t.get("output", "").splitlines()) * 0.15 + 2.5))
                if not isinstance(scene.get("seconds"), (int, float)):
                    scene["seconds"] = est
                elif abs(scene["seconds"] - est) > max(3, est * 0.25):
                    notes.append(f"{scene['id']}: seconds is {scene['seconds']}, the voice line needs about {est}")
    return notes


# What a viewer sees or hears of a scene (the same list as patch.py): a difference means "Changed in this update".
SEEN = ("voice", "kind", "code", "note", "action", "terminal", "diagram", "screen", "flags", "overlay")


def mark_changes(data: dict, folder: Path) -> int:
    """When the run already delivered a video, flag the scenes that differ from it, for an update round."""
    delivered = folder.parent / "5-videos" / "storyboard.delivered.json"
    if not delivered.exists():
        return 0
    seen = lambda s: {k: s.get(k) for k in SEEN} | ({"title": s.get("title")} if s.get("kind") == "title" else {})
    old = {s["id"]: seen(s) for p in json.loads(delivered.read_text())["parts"] for c in p["chapters"] for s in c["scenes"]}
    count = 0
    for part in data["parts"]:
        for chapter in part["chapters"]:
            for scene in chapter["scenes"]:
                scene["changed"] = scene["id"] not in old or seen(scene) != old[scene["id"]]
                count += scene["changed"]
    return count


def build(folder: Path) -> Path:
    data = json.loads((folder / "storyboard.json").read_text())
    issues = problems(data, folder)
    if issues:
        raise SystemExit("storyboard.json has problems:\n  " + "\n  ".join(issues))
    for note in estimate(data):
        print(f"note: {note}")
    changed = mark_changes(data, folder)
    if changed:
        print(f"update: {changed} scene(s) differ from the delivered video and are marked Changed")
    for name, d in (data.get("diagrams") or {}).items():
        for i, step in enumerate(d.get("steps", []), start=1):
            if len(step.get("label", "")) > 32:
                print(f"note: diagram {name} step {i}: label is {len(step['label'])} characters; keep it to about 32 so it does not run over the lifelines")
    data["production"]["pronounce"] = pronounce_pairs(data["production"]["pronounce"])
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = f"{data['meta'].get('short') or data['meta']['feature']} Storyboard"
    out = folder / "storyboard.html"
    out.write_text(TEMPLATE.read_text().replace("__TITLE__", title).replace("__DATA__", payload))
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 build_storyboard.py <feature-dir>")
    print(build(Path(sys.argv[1]).resolve()))
