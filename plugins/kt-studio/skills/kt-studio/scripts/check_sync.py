"""Checks that voice and picture stay together, from what the recorder logged (no guessing from pixels).

For each scene it reads where the voice was meant to start (the mark), where it really starts (the
placement), the word cues the script waited for, and the silence before the next line.

Usage: python3 check_sync.py <run>/4-checks <part>      after a take: part = ui or code
       python3 check_sync.py <rt>/.argo/<run-id>-<part>    after a rehearsal (argo record), before the take
The first reads <part>-timing.json, <part>-scene-report.json, and when present <part>-beats.json and
<part>-cues.jsonl (collect.sh copies them). The second reads the recorder's own files; without a scene
report, voice lines are placed from the clip lengths. Exit code 1 when a voice line starts late or an
action misses its word.

Limits (references/quality.md):
  voice late    > 250 ms   the line starts after its picture, because the line before it ran long
  cue late      > 400 ms   the action happens after its word was already spoken
  silence       > 4 s      no voice for that long between two lines (a warning, not a failure)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

VOICE_LATE_MS = 250
CUE_LATE_MS = 400
SILENCE_S = 4.0


def main() -> None:
    if len(sys.argv) == 3:
        folder, part = Path(sys.argv[1]), sys.argv[2]
        files = {k: folder / f"{part}-{k}" for k in ("timing.json", "scene-report.json", "beats.json", "cues.jsonl")}
    elif len(sys.argv) == 2 and (Path(sys.argv[1]) / ".timing.json").exists():
        argo_dir = Path(sys.argv[1])
        demos = argo_dir.parent.parent / "demos"
        files = {"timing.json": argo_dir / ".timing.json", "scene-report.json": argo_dir / "scene-report.json",
                 "beats.json": demos / f"{argo_dir.name}.beats.json", "cues.jsonl": argo_dir / "cues.jsonl"}
    else:
        raise SystemExit("usage: python3 check_sync.py <run>/4-checks <part>   or   python3 check_sync.py <rt>/.argo/<run-id>-<part>")
    timing = json.loads(files["timing.json"].read_text())
    beats = json.loads(files["beats.json"].read_text()) if files["beats.json"].exists() else {}
    logged = [json.loads(line) for line in files["cues.jsonl"].read_text().splitlines() if line.strip()] if files["cues.jsonl"].exists() else []
    cues = [c for c in logged if "phrase" in c]
    blocked = [c["blocked"] for c in logged if "blocked" in c]

    first = min(timing.values())
    head = first - 200 if first - 200 > 500 else 0  # Argo trims setup before the first mark
    # kt-patch-in is a patch take's silent start mark (lib/sync.ts): it moves the trim, but has no voice.
    timing = {k: v for k, v in timing.items() if not k.startswith("kt-")}
    if files["scene-report.json"].exists() and len(sys.argv) == 3:
        report = json.loads(files["scene-report.json"].read_text())
    else:
        # A rehearsal: place each line where Argo would (at its mark, after the line before it ends).
        print("(rehearsal: voice lines placed from the clip lengths)")
        report, previous = {"scenes": []}, 0
        for scene, mark in sorted(timing.items(), key=lambda kv: kv[1]):
            length = beats.get(scene, {}).get("clipMs", 0)
            start = mark if mark >= previous else previous + 100
            report["scenes"].append({"scene": scene, "startMs": start - head, "durationMs": length})
            previous = start + length
    placed = {s["scene"]: s for s in report["scenes"]}
    order = sorted(timing.items(), key=lambda kv: kv[1])

    failures, warnings = [], []
    print(f"{'scene':8} {'mark':>7} {'voice':>7} {'late':>6} {'speech':>13} {'silence':>8}  cues")
    previous_end = None
    for scene, mark in order:
        p = placed.get(scene)
        if not p:
            continue
        start = (p["startMs"] + head) / 1000
        late = start * 1000 - mark
        speech = beats.get(scene, {}).get("speechMs", [0, p["durationMs"]])
        talk_from, talk_to = start + speech[0] / 1000, start + speech[1] / 1000
        gap = talk_from - previous_end if previous_end is not None else 0
        previous_end = talk_to
        mine = [c for c in cues if c.get("scene") == scene]
        cue_text = " ".join(
            f"{c['phrase']}:MISSING" if c.get("missing") else f"{c['phrase']}{'' if c['lateMs'] <= CUE_LATE_MS else ':+' + str(c['lateMs'])}"
            for c in mine)
        print(f"{scene:8} {mark / 1000:7.2f} {start:7.2f} {late:+6.0f} {talk_from:6.2f}-{talk_to:6.2f} {gap:8.1f}  {cue_text}")
        if late > VOICE_LATE_MS:
            failures.append(f"{scene}: voice starts {late:.0f} ms after its mark (the line before it is longer than its scene)")
        if gap > SILENCE_S:
            warnings.append(f"{scene}: {gap:.1f} s of silence before this line")
        for c in mine:
            if c.get("missing"):
                failures.append(f"{scene}: cue word '{c['phrase']}' is not in the voice line")
            elif c["lateMs"] > CUE_LATE_MS:
                failures.append(f"{scene}: '{c['phrase']}' happens {c['lateMs']} ms after the word (actions before it are too slow)")

    if report.get("overflowMs"):
        print(f"note: the last frame is held {report['overflowMs'] / 1000:.1f} s while the last line finishes (normal on a still screen)")
    cue_count = sum(1 for c in cues if not c.get("missing"))
    on_time = sum(1 for c in cues if not c.get("missing") and c["lateMs"] <= CUE_LATE_MS)
    print(f"\nscenes {len(order)}, cues on their word {on_time}/{cue_count}, words from {sorted({b.get('source') for b in beats.values()}) or ['none']}")
    if blocked:
        print(f"rehearsal: {len(blocked)} write(s) blocked, as they should be: " + ", ".join(blocked[:5]))
    for w in warnings:
        print(f"WARN: {w}")
    for f in failures:
        print(f"FAIL: {f}")
    if failures:
        raise SystemExit(1)
    print("PASS: voice and picture in sync")


if __name__ == "__main__":
    main()
