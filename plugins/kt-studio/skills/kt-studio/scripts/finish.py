"""Joins the parts of a run into one video, in one encode, keeping voice and picture together.

  Part A (<feature>-ui.mp4) then Part B (<feature>-code.mp4), whichever exist, with a short
  cross-fade between them. Optional cuts remove dead stretches (a page loading, a slow server) with a
  short cross-fade at each cut. Chapters and captions are carried over to the new time line.

Sync: every piece's sound is padded or trimmed to exactly its picture's length before anything is
joined, and cut points are snapped to whole frames, so a join or a cut can never shift the voice.

Chapters: one per storyboard chapter, named as in the storyboard ("Try it", "How it works · On the server"),
not one per scene. Run it for a single part too: the delivered file gets those chapters.

Usage: python3 finish.py <run> [--cut ui:108.7-122.6 --cut ui:250.3-256.8] [--fade 1.0] [--cut-fade 0.5]
A cut that overlaps a voice line (from 4-checks/<part>-scene-report.json) is refused unless --force.
Writes <run>/5-videos/<feature>.mp4, .srt and .vtt, and 4-checks/joined-timing.json and joined-cues.jsonl
(the scene marks and word cues on the final time line, for check_video.py --marks).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

FPS = 30


def probe(path: Path) -> dict:
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_chapters", "-show_format", "-of", "json", str(path)])
    return json.loads(out)


def stream_seconds(info: dict, kind: str) -> float:
    for s in info["streams"]:
        if s["codec_type"] == kind and s.get("duration"):
            return float(s["duration"])
    return float(info["format"]["duration"])


def snap(t: float) -> float:
    return round(t * FPS) / FPS


def stamp(t: float, sep: str) -> str:
    ms = max(0, int(round(t * 1000)))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}{sep}{ms % 1000:03}"


def read_cues(path: Path) -> list[tuple[float, float, str]]:
    if not path.exists():
        return []
    cues = []
    for block in path.read_text().strip().split("\n\n"):
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+) --> (\d+):(\d+):(\d+)[,.](\d+)\n(.*)", block, re.S)
        if m:
            g = [int(x) for x in m.groups()[:8]]
            cues.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000, m.group(9).strip()))
    return cues


class Piece:
    """One part, with the stretches it keeps after the cuts, placed on the final time line."""

    def __init__(self, name: str, path: Path, cuts: list[tuple[float, float]], cut_fade: float):
        self.name, self.path = name, path
        self.info = probe(path)
        self.length = snap(stream_seconds(self.info, "video"))
        keep, at = [], 0.0
        for a, b in sorted((snap(a), snap(b)) for a, b in cuts):
            if a > at:
                keep.append((at, a))
            at = max(at, b)
        if at < self.length:
            keep.append((at, self.length))
        self.keep = keep
        self.cut_fade = cut_fade
        self.start = 0.0  # where this part begins in the final video

    @property
    def edited(self) -> float:
        return sum(b - a for a, b in self.keep) - self.cut_fade * (len(self.keep) - 1)

    def place(self, t: float) -> float | None:
        """Time t of this part on the final time line (None when t falls in a cut)."""
        done = 0.0
        for k, (a, b) in enumerate(self.keep):
            if t < a:
                return None
            if t <= b:
                return self.start + done - self.cut_fade * k + (t - a)
            done += b - a
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=Path)
    ap.add_argument("--cut", action="append", default=[], help="part:start-end in seconds, e.g. ui:108.7-122.6")
    ap.add_argument("--fade", type=float, default=1.0, help="cross-fade between parts, seconds")
    ap.add_argument("--cut-fade", type=float, default=0.5, help="cross-fade at each cut, seconds")
    ap.add_argument("--force", action="store_true", help="allow a cut that overlaps a voice line")
    args = ap.parse_args()

    run = args.run.resolve()
    feature = json.loads((run / "run.json").read_text())["feature"]
    videos = run / "5-videos"
    board_file = run / "2-storyboard" / "storyboard.json"
    board = json.loads(board_file.read_text()) if board_file.exists() else {"parts": []}
    titles = {p["id"]: p["title"] for p in board["parts"]}
    # Scene id -> the storyboard chapter it opens (only the first scene of each chapter starts a chapter).
    opens = {c["scenes"][0]["id"]: c["title"] for p in board["parts"] for c in p["chapters"] if c["scenes"]}
    in_chapter = {s["id"] for p in board["parts"] for c in p["chapters"] for s in c["scenes"]}
    cuts = {}
    for c in args.cut:
        part, span = c.split(":", 1)
        a, b = (float(x) for x in span.split("-"))
        cuts.setdefault(part, []).append((a, b))

    # A cut must fall in silence: cutting into a voice line drops words and breaks the scene.
    for part, spans in cuts.items():
        report, beats_file = run / "4-checks" / f"{part}-scene-report.json", run / "4-checks" / f"{part}-beats.json"
        if not report.exists():
            continue
        beats = json.loads(beats_file.read_text()) if beats_file.exists() else {}
        for scene in json.loads(report.read_text())["scenes"]:
            speech = beats.get(scene["scene"], {}).get("speechMs", [0, scene["durationMs"]])
            talk = ((scene["startMs"] + speech[0]) / 1000, (scene["startMs"] + speech[1]) / 1000)
            for a, b in spans:
                if a < talk[1] and b > talk[0] and not args.force:
                    raise SystemExit(f"FAIL: cut {part}:{a}-{b} cuts into the voice of {scene['scene']} "
                                     f"({talk[0]:.1f}-{talk[1]:.1f} s). Cut only in silence, or pass --force.")

    pieces = []
    for name, part_id in (("ui", "A"), ("code", "B")):
        path = videos / f"{feature}-{name}.mp4"
        if path.exists():
            piece = Piece(name, path, cuts.get(name, []), args.cut_fade)
            piece.title = titles.get(part_id, "Use it" if name == "ui" else "How it works")
            pieces.append(piece)
    if not pieces:
        raise SystemExit(f"no part videos in {videos}")

    # Filter graph: every kept stretch is cut from its part, its sound forced to the picture's length.
    graph, inputs, at = [], [], 0.0
    v_last = a_last = None
    for i, piece in enumerate(pieces):
        inputs += ["-i", str(piece.path)]
        piece.start = at if i == 0 else at - args.fade
        for k, (a, b) in enumerate(piece.keep):
            v, s = f"v{i}_{k}", f"a{i}_{k}"
            graph.append(f"[{i}:v]trim=start={a:.4f}:end={b:.4f},setpts=PTS-STARTPTS,fps={FPS},format=yuv420p,setsar=1[{v}]")
            # async + first_pts: fill any gap before the first sample, so every sample sits at its real time
            # (Argo's audio can start 35 ms after its picture; trimming without this shifts the voice).
            graph.append(f"[{i}:a]aresample=48000:async=1:first_pts=0,atrim=start={a:.4f}:end={b:.4f},asetpts=PTS-STARTPTS,apad,atrim=duration={b - a:.4f}[{s}]")
            if v_last is None:
                v_last, a_last, length = v, s, b - a
                continue
            fade = args.cut_fade if k else args.fade
            graph.append(f"[{v_last}][{v}]xfade=transition=fade:duration={fade}:offset={length - fade:.4f}[x{i}_{k}]")
            graph.append(f"[{a_last}][{s}]acrossfade=d={fade}[y{i}_{k}]")
            v_last, a_last = f"x{i}_{k}", f"y{i}_{k}"
            length += (b - a) - fade
        at = length
    total = length

    # Chapters and captions on the new time line.
    meta, marks, cues = [";FFMETADATA1"], [], []
    for piece in pieces:
        for ch in piece.info.get("chapters", []):
            t = piece.place(float(ch["start_time"]))
            name = ch.get("tags", {}).get("title", "")
            if t is None or (name in in_chapter and name not in opens):
                continue
            name = opens.get(name, name)
            marks.append((t, f"{piece.title} · {name}".strip(" ·") if len(pieces) > 1 else name))
        for a, b, text in read_cues(videos / f"{feature}-{piece.name}.srt"):
            pa, pb = piece.place(a), piece.place(b)
            if pa is not None:
                cues.append((pa, pb if pb is not None else pa + (b - a), text))
    marks.sort()
    for k, (t, title) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else total
        meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(t * 1000)}", f"END={int(end * 1000)}", f"title={title}"]
    cues.sort()

    out = videos / f"{feature}.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        meta_file = Path(tmp) / "chapters.txt"
        meta_file.write_text("\n".join(meta) + "\n")
        subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-i", str(meta_file),
                        "-filter_complex", ";".join(graph), "-map", f"[{v_last}]", "-map", f"[{a_last}]",
                        "-map_chapters", str(len(pieces)), "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)],
                       check=True, stdin=subprocess.DEVNULL)
    (videos / f"{feature}.srt").write_text("".join(f"{i}\n{stamp(a, ',')} --> {stamp(b, ',')}\n{t}\n\n" for i, (a, b, t) in enumerate(cues, 1)))
    (videos / f"{feature}.vtt").write_text("WEBVTT\n\n" + "".join(f"{stamp(a, '.')} --> {stamp(b, '.')}\n{t}\n\n" for a, b, t in cues))

    # Scene marks and word cues on the final time line, so check_video.py --marks checks the delivered file.
    checks = run / "4-checks"
    timing, moved = {}, []
    for piece in pieces:
        part_timing = checks / f"{piece.name}-timing.json"
        if part_timing.exists():
            for scene, ms in json.loads(part_timing.read_text()).items():
                t = piece.place(ms / 1000)
                if t is not None:
                    timing[scene] = int(round(t * 1000))
        part_cues = checks / f"{piece.name}-cues.jsonl"
        for line in (part_cues.read_text().splitlines() if part_cues.exists() else []):
            cue = json.loads(line)
            if "wordMs" in cue and (t := piece.place(cue["wordMs"] / 1000)) is not None:
                moved.append({**cue, "wordMs": int(round(t * 1000))})
    (checks / "joined-timing.json").write_text(json.dumps(timing, indent=2) + "\n")
    (checks / "joined-cues.jsonl").write_text("".join(json.dumps(c) + "\n" for c in moved))

    info = probe(out)
    gap = abs(stream_seconds(info, "video") - stream_seconds(info, "audio"))
    for piece in pieces:
        print(f"{piece.title}: starts at {piece.start:.2f} s, {piece.edited:.1f} s long, {len(piece.keep) - 1} cuts")
    print(f"{out.name}: {total:.1f} s, {len(marks)} chapters, {len(cues)} captions, sound vs picture length {gap * 1000:.0f} ms apart")
    if gap > 0.1:
        raise SystemExit("FAIL: the sound and the picture have different lengths")


if __name__ == "__main__":
    main()
