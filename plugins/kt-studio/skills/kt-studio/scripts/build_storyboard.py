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
KINDS = {"ui", "code", "nav", "title", "diagram", "terminal", "map", "intro", "outro"}
NODE_KINDS = {"person", "app", "service", "job", "database", "cache", "queue", "external", "state"}
STEP_KINDS = {"call", "reply", "event", "write", "read", "fail"}
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


def map_problems(name: str, m: dict) -> list[str]:
    """A system map (top-level `maps`): nodes on a small grid, optional boundaries, and the steps of the journey."""
    found = []
    nodes = m.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return [f"map {name}: nodes must be a non-empty list"]
    ids = [n.get("id") for n in nodes]
    if len(set(ids)) != len(ids) or not all(isinstance(i, str) and i for i in ids):
        found.append(f"map {name}: every node needs a unique id")
    places = {}
    for i, n in enumerate(nodes):
        if n.get("kind", "service") not in NODE_KINDS:
            found.append(f"map {name} node {n.get('id')}: kind must be one of {sorted(NODE_KINDS)}")
        if not n.get("label"):
            found.append(f"map {name} node {n.get('id')}: missing label")
        col, row = n.get("col", i), n.get("row", 0)
        if not (isinstance(col, int) and isinstance(row, int) and col >= 0 and row >= 0):
            found.append(f"map {name} node {n.get('id')}: col and row must be whole numbers from 0")
            continue
        if (col, row) in places:
            found.append(f"map {name}: nodes {places[(col, row)]} and {n.get('id')} share col {col}, row {row}")
        places[(col, row)] = n.get("id")
    if len(nodes) > 9:
        found.append(f"map {name}: {len(nodes)} nodes; keep 9 or fewer on one map (split it, or zoom into one part)")
    where = {n.get("id"): (n.get("col", i), n.get("row", 0)) for i, n in enumerate(nodes)}
    for g in m.get("groups", []) or []:
        members = [where[i] for i in g.get("nodes", []) if i in where]
        if not g.get("label") or len(members) != len(g.get("nodes", [])) or not members:
            found.append(f"map {name}: group {g.get('label')!r} needs a label and nodes that exist")
            continue
        cols = range(min(c for c, _ in members), max(c for c, _ in members) + 1)
        rows = range(min(r for _, r in members), max(r for _, r in members) + 1)
        for other, (c, r) in where.items():
            if other not in g["nodes"] and c in cols and r in rows:
                found.append(f"map {name}: group {g['label']!r} would draw its box around {other}, which is not in it; move {other} out of cols {cols.start}-{cols.stop - 1}, rows {rows.start}-{rows.stop - 1}")
    steps = m.get("steps", [])
    if not isinstance(steps, list):
        return found + [f"map {name}: steps must be a list"]
    for i, s in enumerate(steps, start=1):
        targets = s.get("to") if isinstance(s.get("to"), list) else [s.get("to")]
        for side in [s.get("from"), *targets]:
            if side not in where:
                found.append(f"map {name} step {i}: '{side}' is not one of its nodes")
        if s.get("kind", "call") not in STEP_KINDS:
            found.append(f"map {name} step {i}: kind must be one of {sorted(STEP_KINDS)}")
        if not s.get("label"):
            found.append(f"map {name} step {i}: missing label")
        state = s.get("state")
        if state is not None and not (isinstance(state, dict) and state.get("text") and state.get("node", targets[0]) in where):
            found.append(f"map {name} step {i}: state must be {{node, text}} with a node of the map")
    return found


def map_scene_problems(sid: str, use: dict, maps: dict) -> list[str]:
    """A map scene names a map and says what it does: reveal nodes, play steps, show the overview, zoom, replay."""
    m = maps.get(use.get("use"))
    if not m:
        return [f"{sid}: map.use must name one of the top-level maps ({sorted(maps) or 'none defined'})"]
    found = []
    ids = {n.get("id") for n in m.get("nodes", [])}
    for i in use.get("reveal", []) or []:
        if i not in ids:
            found.append(f"{sid}: map.reveal names '{i}', which is not a node of {use['use']}")
    if use.get("zoom") is not None and use["zoom"] not in ids:
        found.append(f"{sid}: map.zoom names '{use['zoom']}', which is not a node of {use['use']}")
    steps = use.get("steps")
    count = len(m.get("steps", []))
    if steps is not None and not (isinstance(steps, list) and 1 <= len(steps) <= 2 and all(isinstance(n, int) and 1 <= n <= count for n in steps)):
        found.append(f"{sid}: map.steps must be [first] or [first, last] within 1..{count}")
    if not any(use.get(k) for k in ("reveal", "steps", "overview", "zoom", "replay")):
        found.append(f"{sid}: a map scene does something: reveal, steps, overview, zoom or replay")
    return found


def card_problems(data: dict) -> list[str]:
    """The intro opens the video and the outro closes it: each is one scene in its place, with its card."""
    found = []
    scenes = [s for p in data.get("parts", []) for c in p.get("chapters", []) for s in c.get("scenes", [])]
    for kind, where, at in (("intro", "first", 0), ("outro", "last", -1)):
        mine = [s for s in scenes if s.get("kind") == kind]
        if not mine:
            continue
        if len(mine) > 1:
            found.append(f"only one {kind} scene: {', '.join(s.get('id', '?') for s in mine)}")
        if scenes[at] is not mine[0]:
            found.append(f"{mine[0].get('id', '?')}: the {kind} must be the {where} scene of the video")
        card = data.get(kind)
        if not isinstance(card, dict):
            found.append(f"an {kind} scene needs the top-level `{kind}` card")
            continue
        for key in ("builtBy",):
            if key in card and not isinstance(card[key], list):
                found.append(f"{kind}.{key} must be a list (use [] to show no names)")
    intro, outro = data.get("intro"), data.get("outro")
    if isinstance(intro, dict):
        learn = intro.get("learn", [])
        if not (isinstance(learn, list) and 1 <= len(learn) <= 4):
            found.append("intro.learn must list 1 to 4 things the viewer will learn")
        if len(intro.get("tagline", "")) > 140:
            found.append(f"intro.tagline is {len(intro['tagline'])} characters; keep it to one line, about 140")
    if isinstance(outro, dict):
        remember = outro.get("remember", [])
        if not (isinstance(remember, list) and 1 <= len(remember) <= 4):
            found.append("outro.remember must list 1 to 4 things to remember (three is best)")
        if not all(isinstance(n, dict) and n.get("label") for n in outro.get("next", [])):
            found.append("outro.next must be a list of {label, detail}")
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
                if part.get("id") == "A" and scene.get("kind") in ("code", "nav", "diagram", "terminal", "map"):
                    found.append(f"{scene.get('id', '?')}: {scene['kind']} scenes belong in Part B (Part A records the app)")
    for name, m in (data.get("maps") or {}).items():
        found += map_problems(name, m)
    found += card_problems(data)
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
                if scene.get("kind") == "map":
                    found += map_scene_problems(sid, scene.get("map", {}), data.get("maps", {}))
                here = scene.get("where")
                if here is not None:
                    m = (data.get("maps") or {}).get(here.get("map")) if isinstance(here, dict) else None
                    if not m or here.get("node") not in {n.get("id") for n in m.get("nodes", [])}:
                        found.append(f"{sid}: where must be {{map, node}} naming a node of one of the top-level maps")
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
SEEN = ("voice", "kind", "code", "note", "action", "terminal", "diagram", "map", "where", "screen", "flags", "overlay")


def mark_changes(data: dict, folder: Path) -> int:
    """When the run already delivered a video, flag the scenes that differ from it, for an update round."""
    delivered = folder.parent / "5-videos" / "storyboard.delivered.json"
    if not delivered.exists():
        return 0
    def seen_in(board: dict):
        # A title scene shows its title; an intro or outro shows its card.
        return lambda s: ({k: s.get(k) for k in SEEN} | ({"title": s.get("title")} if s.get("kind") == "title" else {})
                          | ({"card": board.get(s["kind"])} if s.get("kind") in ("intro", "outro") else {}))
    before = json.loads(delivered.read_text())
    seen_old, seen = seen_in(before), seen_in(data)
    old = {s["id"]: seen_old(s) for p in before["parts"] for c in p["chapters"] for s in c["scenes"]}
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
    kinds = {s.get("kind") for p in data["parts"] for c in p["chapters"] for s in c["scenes"]}
    for kind, what in (("intro", "opens the video: who built it, what you will learn, the chapters"),
                       ("outro", "closes it: what to remember, next steps, who to ask")):
        if kind not in kinds:
            print(f"note: no {kind} scene; an {kind} {what} (references/kt-design.md)")
    if changed:
        print(f"update: {changed} scene(s) differ from the delivered video and are marked Changed")
    for name, m in (data.get("maps") or {}).items():
        for i, step in enumerate(m.get("steps", []), start=1):
            if len(step.get("payload", step.get("label", ""))) > 36:
                print(f"note: map {name} step {i}: the travelling text is {len(step.get('payload', step.get('label', '')))} characters; keep it to about 36")
    for name, d in (data.get("diagrams") or {}).items():
        for i, step in enumerate(d.get("steps", []), start=1):
            if len(step.get("label", "")) > 32:
                print(f"note: diagram {name} step {i}: label is {len(step['label'])} characters; keep it to about 32 so it does not run over the lifelines")
    data["production"]["pronounce"] = pronounce_pairs(data["production"]["pronounce"])
    # The project's brand (config.yml `branding`), so the intro and outro previews look like the video.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import brand
    import project
    look = brand.resolved(project.find(folder))
    if look.get("note"):
        print(f"note: brand: {look['note']}")
    data["brand"] = {k: v for k, v in look.items() if k != "note"}
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    title = f"{data['meta'].get('short') or data['meta']['feature']} Storyboard"
    out = folder / "storyboard.html"
    out.write_text(TEMPLATE.read_text().replace("__TITLE__", title).replace("__DATA__", payload))
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 build_storyboard.py <feature-dir>")
    print(build(Path(sys.argv[1]).resolve()))
