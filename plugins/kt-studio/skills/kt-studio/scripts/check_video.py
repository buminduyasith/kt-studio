"""Checks a rendered video before anyone sees it.

1. Blink check: samples brightness 10 times a second. A frame far darker than the frames around it
   (the median of the 20 s around it, so a dark code tour next to a bright UI part is fine) or a big jump
   between neighbours fails the check. A fade to black or a white flash between screens shows up here.
2. Picture timing (with --marks): the recorder stamps each frame when it arrives, so on a busy computer
   the picture can slide seconds behind the voice while the script's own log (check_sync.py) still looks
   perfect. This finds where the picture changes a lot (a file opens, a page loads, a highlight lands)
   right after each scene mark, and fails when those changes come later and later through the video.
3. Contact sheet: one frame per scene (from Argo's scene report) in one image, to compare with the
   storyboard by eye.

Usage: python3 check_video.py <video.mp4> [--report scene-report.json] [--sheet sheet.png] [--marks timing.json]
       (--marks: <run>/4-checks/<part>-timing.json, the scene marks collect.sh copies next to the report)
Exit code 1 when the blink check or the picture timing check fails.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import tempfile
from pathlib import Path


def brightness(video: Path) -> list[float]:
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "yavg.txt"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(video), "-vf",
             f"fps=10,scale=320:-1,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file={log}",
             "-f", "null", "-"],
            check=True, stdin=subprocess.DEVNULL,
        )
        return [float(m.group(1)) for m in (re.search(r"YAVG=([\d.]+)", line) for line in log.read_text().splitlines()) if m]


DRIFT_FAIL_S = 0.6  # the picture's lag behind the voice may not grow by more than this through a video


def changes(video: Path, fps: int = 10) -> list[float]:
    """How much the picture changes from one sample to the next (mean absolute difference, 0 to 255)."""
    w, h = 160, 90
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale={w}:{h},format=gray",
                          "-f", "rawvideo", "-"], check=True, capture_output=True, stdin=subprocess.DEVNULL).stdout
    size = w * h
    frames = [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)]
    return [0.0] + [sum(abs(a - b) for a, b in zip(frames[i], frames[i - 1])) / size for i in range(1, len(frames))]


def picture_lag(video: Path, marks_file: Path) -> tuple[list[tuple[str, float, float]], float | None]:
    """Anchors are the scene marks and, when the cue log sits next to the marks file, the word each click
    waited for. For each anchor: how long after it the picture makes its first clear change (a file opens,
    a page loads, a list drops). A scene with no clear change is left out; a steady delay (a highlight that
    always lands 0.8 s in) is fine; a delay that grows from the first third of the video to the last is the
    picture lagging behind the voice."""
    fps = 10
    diff = changes(video, fps)
    marks = json.loads(marks_file.read_text())
    # Marks are on the recording's clock; Argo cuts the setup before the first mark (less 0.2 s, when over 0.5 s).
    trim = max(0, min(marks.values()) - 200) if marks else 0
    trim = trim / 1000 if trim > 500 else 0.0
    anchors = [(scene, ms / 1000 - trim) for scene, ms in marks.items() if not scene.startswith("kt-")]
    cues = marks_file.with_name(marks_file.name.replace("-timing.json", "-cues.jsonl"))
    if cues.exists():
        for line in cues.read_text().splitlines():
            cue = json.loads(line)
            if "wordMs" in cue:
                anchors.append((f"{cue['scene']} '{cue['phrase']}'", cue["wordMs"] / 1000 - trim))
    anchors.sort(key=lambda a: a[1])
    # A clear change: well above the cursor gliding (about 0.06 at this size), and among the biggest 3%.
    clear = max(0.5, statistics.quantiles(diff, n=100)[96])
    found = []
    for name, at in anchors:
        start = int((at - 0.6) * fps)  # a change made just before (navigate, then say; a list that opens early) counts
        for i in range(max(1, start), min(len(diff), start + int(4.6 * fps))):
            if diff[i] >= clear:
                found.append((name, at, i / fps - at))
                break
    if len(found) < 6:
        return found, None
    third = len(found) // 3
    early = statistics.median(d for _, _, d in found[:third])
    late = statistics.median(d for _, _, d in found[-third:])
    return found, late - early


PER_SHEET = 12  # 3 x 4 frames: a sheet that stays readable when opened whole


def grab(video: Path, at: float, label: str, out: Path) -> None:
    """One frame at 640 wide, with its scene id in a band at the top (without the label if ffmpeg has no fonts)."""
    band = "scale=640:-1,drawbox=x=0:y=0:w=iw:h=28:color=black@0.65:t=fill"
    for vf in (f"{band},drawtext=text='{label}':fontcolor=white:fontsize=18:x=10:y=5", band):
        done = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1",
                               "-vf", vf, str(out)], stdin=subprocess.DEVNULL, capture_output=True)
        if done.returncode == 0:
            return
    raise SystemExit(f"could not read a frame at {at:.1f} s of {video}")


def sheet(video: Path, report: Path, out: Path) -> None:
    """One frame per scene, 70% into it. More than 12 scenes: several sheets, <name>-1.png, <name>-2.png, ..."""
    scenes = json.loads(report.read_text())["scenes"]
    pages = [scenes[i:i + PER_SHEET] for i in range(0, len(scenes), PER_SHEET)]
    written = []
    with tempfile.TemporaryDirectory() as tmp:
        for n, page in enumerate(pages, 1):
            frames = []
            for i, scene in enumerate(page):
                frame = Path(tmp) / f"{n}-{i:03d}.png"
                grab(video, (scene["startMs"] + scene["durationMs"] * 0.7) / 1000, scene["scene"], frame)
                frames.append(frame)
            cols = 3
            while len(frames) % cols or len(frames) < cols:
                frames.append(frames[-1])
            inputs = [arg for f in frames for arg in ("-i", str(f))]
            layout = "|".join(f"{(i % cols) * 640}_{(i // cols) * 360}" for i in range(len(frames)))
            target = out if len(pages) == 1 else out.with_name(f"{out.stem}-{n}{out.suffix}")
            subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex",
                            f"xstack=inputs={len(frames)}:layout={layout}:fill=black", str(target)],
                           check=True, stdin=subprocess.DEVNULL)
            written.append(target.name)
    print(f"contact sheet: {', '.join(written)} in {out.parent} ({len(scenes)} scenes, {PER_SHEET} per sheet)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--sheet", type=Path)
    parser.add_argument("--marks", type=Path, help="<part>-timing.json: scene marks, for the picture timing check")
    args = parser.parse_args()

    values = brightness(args.video)
    median = statistics.median(values)
    # Local, not global: a joined video has bright UI parts and dark code parts.
    window = 100  # samples each side: 10 s at 10 per second
    local = [statistics.median(values[max(0, i - window): i + window + 1]) for i in range(len(values))]
    dark_at = [i for i, v in enumerate(values) if v < local[i] * 0.6]
    # A jump is measured against the brighter of the two frames, so a 1 s cross-fade is fine. A change that
    # comes back within 1.5 s (a white flash, a dip) fails above 25%; one that stays (a dialog's backdrop
    # opening) only above 50% (a hard cut between a dark and a bright screen).
    def comes_back(i: int) -> bool:
        return any(abs(values[j] - values[i - 1]) <= values[i - 1] * 0.08 for j in range(i + 1, min(len(values), i + 16)))
    jump_at = [i for i in range(1, len(values))
               if abs(values[i] - values[i - 1]) > max(values[i], values[i - 1]) * (0.25 if comes_back(i) else 0.5)]
    dark, jumps = len(dark_at), len(jump_at)
    print(f"brightness median {median:.1f}, min {min(values):.1f}, dark frames {dark}, sudden jumps {jumps}")
    for i in (dark_at + jump_at)[:8]:
        print(f"  at {i / 10:.1f} s: brightness {values[i]:.0f} (around it {local[i]:.0f})")
    failed = False
    if dark or jumps:
        print("FAIL: the video dips or jumps in brightness (check for scene fades or a flash between screens)")
        failed = True
    else:
        print("PASS: no blinks")
    if args.marks:
        found, growth = picture_lag(args.video, args.marks)
        if growth is None:
            print(f"picture timing: only {len(found)} scenes change clearly after their mark; not enough to judge")
        else:
            lags = ", ".join(f"{scene} +{lag:.1f}" for scene, _, lag in found[:: max(1, len(found) // 6)])
            print(f"picture timing: first change after each mark, sampled: {lags} s; growth early to late {growth:+.2f} s")
            if growth > DRIFT_FAIL_S:
                print(f"FAIL: the picture falls {growth:.1f} s further behind the voice by the end. The computer was "
                      "too busy while recording (another take, a build). Record again with nothing else running")
                failed = True
            else:
                print("PASS: picture keeps time with the voice")
    if args.report and args.sheet:
        sheet(args.video, args.report, args.sheet)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
