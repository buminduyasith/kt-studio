"""Writes the voice files for the recorder from the approved storyboard, so the narration is exactly
the storyboard's words: 3-scripts/ui.scenes.json (part A) and 3-scripts/code.scenes.json (part B),
3-scripts/diagrams.json when the storyboard has sequence diagrams, 3-scripts/maps.json when it has
system maps, and 3-scripts/cards.json for the intro and outro cards (lib/cards.ts), with what the
storyboard leaves out filled in: the title, the chapter list, the length and the code version, and
3-scripts/brand.json when config.yml has a brand (scripts/brand.py).

Each entry: { "scene", "text" (spoken: the pronounce map applied), "caption" (on-screen spelling, only
when it differs) }. An "overlay" already in the file is kept, so it can be added by hand once.

Usage: python3 make_scenes.py <run>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brand  # noqa: E402
import build_storyboard  # noqa: E402
import project  # noqa: E402


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

    # The project's brand (config.yml `branding`): the cards and the code tour use its logo and colour.
    look = brand.resolved(project.find(run))
    if look.get("note"):
        print(f"brand: {look['note']}")
    brand_file = run / "3-scripts" / "brand.json"
    if look:
        brand_file.write_text(json.dumps({k: v for k, v in look.items() if k != "note"}, ensure_ascii=False) + "\n")
    elif brand_file.exists():
        brand_file.unlink()

    # The intro and outro cards (lib/cards.ts reads cards.json, staged next to the demo).
    cards = cards_for(board)
    if cards and look:
        cards["brand"] = {k: v for k, v in look.items() if k != "note"}
    if cards:
        out = run / "3-scripts" / "cards.json"
        out.write_text(json.dumps(cards, indent=2, ensure_ascii=False) + "\n")
        print(f"{out}: {', '.join(k for k in cards if k != 'brand')}{' (with the brand)' if 'brand' in cards else ''}")


def cards_for(board: dict) -> dict:
    """The storyboard's intro and outro, with the parts it may leave out filled in."""
    kinds = {s.get("kind") for p in board["parts"] for c in p["chapters"] for s in c["scenes"]}
    cards = {}
    if "intro" in kinds:
        intro = dict(board.get("intro") or {})
        intro.setdefault("title", board["meta"].get("feature", ""))
        intro.setdefault("agenda", [c["title"] for p in board["parts"] for c in p["chapters"]
                                    if not all(s.get("kind") in ("intro", "outro") for s in c["scenes"])])
        if "length" not in intro:
            build_storyboard.estimate(board)
            total = sum(s["seconds"] for p in board["parts"] for c in p["chapters"] for s in c["scenes"])
            intro["length"] = f"About {max(1, round(total / 60))} minute{'s' if round(total / 60) > 1 else ''}"
        if "code" not in intro and board["meta"].get("sources"):
            src = board["meta"]["sources"][0]
            ref = re.sub(r"^origin/", "", src.get("ref", ""))
            intro["code"] = f"Code: {src.get('repo', '')} {ref} @ {src.get('sha', '')[:8]} · {board['meta'].get('date', '')}".replace("  ", " ")
        cards["intro"] = intro
    if "outro" in kinds:
        outro = dict(board.get("outro") or {})
        outro.setdefault("builtBy", (board.get("intro") or {}).get("builtBy", []))
        cards["outro"] = outro
    return cards


if __name__ == "__main__":
    main()
