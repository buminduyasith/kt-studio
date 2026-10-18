"""Writes the voice files for the recorder from the approved storyboard, so the narration is exactly
the storyboard's words: 3-scripts/ui.scenes.json (part A) and 3-scripts/code.scenes.json (part B),
3-scripts/diagrams.json when the storyboard has sequence diagrams, and 3-scripts/maps.json when it has
system maps.

Each entry: { "scene", "text" (spoken: the pronounce map applied), "caption" (on-screen spelling, only
when it differs) }. An "overlay" already in the file is kept, so it can be added by hand once.

Usage: python3 make_scenes.py <run>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 make_scenes.py <run>")
    run = Path(sys.argv[1])
    board = json.loads((run / "2-storyboard" / "storyboard.json").read_text())
    pronounce = board.get("production", {}).get("pronounce", [])
    if isinstance(pronounce, dict):  # the config.yml form, word: spoken
        pronounce = list(pronounce.items())

    def spoken(text: str) -> str:
        for word, say in pronounce:
            text = re.sub(rf"(?<![\w-]){re.escape(word)}(?![\w-])", say, text)
        return text

    for part, name in (("A", "ui"), ("B", "code")):
        scenes = [s for p in board["parts"] if p["id"] == part for c in p["chapters"] for s in c["scenes"]]
        if not scenes:
            continue
        out = run / "3-scripts" / f"{name}.scenes.json"
        kept = {e["scene"]: e for e in json.loads(out.read_text())} if out.exists() else {}
        entries = []
        for s in scenes:
            entry = {"scene": s["id"], "text": spoken(s["voice"])}
            if entry["text"] != s["voice"]:
                entry["caption"] = s["voice"]
            if "overlay" in kept.get(s["id"], {}):
                entry["overlay"] = kept[s["id"]]["overlay"]
            elif part == "A" and s["kind"] == "ui" and s.get("note"):
                # A UI scene's on-screen note becomes a caption at the bottom (showOverlay in the script).
                entry["overlay"] = {"type": "lower-third", "text": re.sub(r"</?(b|code)>", "", s["note"]),
                                    "placement": "bottom-center", "motion": "fade-in"}
            elif part == "A" and s["kind"] == "title":
                # Part A records the app: a title scene is a card over the first screen (showOverlay in the script).
                entry["overlay"] = {"type": "headline-card", "title": s["title"], "body": s.get("screen", ""),
                                    "placement": "center", "motion": "fade-in"}
            entries.append(entry)
        out.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")
        print(f"{out}: {len(entries)} scenes")

    # Terminal scenes for the code tour: the command and its recorded output, by scene id.
    terminals = {s["id"]: s["terminal"] for p in board["parts"] for c in p["chapters"] for s in c["scenes"]
                 if s.get("kind") == "terminal"}
    if terminals:
        out = run / "3-scripts" / "terminals.json"
        out.write_text(json.dumps(terminals, indent=2, ensure_ascii=False) + "\n")
        print(f"{out}: {len(terminals)} terminal scenes")

    # Sequence diagrams for the code tour (build_tour.mjs reads diagrams.json next to tour.json).
    if board.get("diagrams"):
        out = run / "3-scripts" / "diagrams.json"
        out.write_text(json.dumps(board["diagrams"], indent=2, ensure_ascii=False) + "\n")
        print(f"{out}: {len(board['diagrams'])} diagrams")

    # System maps for the code tour (build_tour.mjs reads maps.json next to tour.json).
    if board.get("maps"):
        out = run / "3-scripts" / "maps.json"
        out.write_text(json.dumps(board["maps"], indent=2, ensure_ascii=False) + "\n")
        print(f"{out}: {len(board['maps'])} maps")


if __name__ == "__main__":
    main()
