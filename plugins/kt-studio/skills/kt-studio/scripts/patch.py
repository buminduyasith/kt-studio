"""Updates a delivered KT video without recording it all again: only the changed scenes are recorded,
and the new stretch is spliced into the delivered video where the picture already matches.

  plan    Compares the storyboard with the one the video was made from (5-videos/storyboard.delivered.json),
          lists changed, added and removed scenes per part, and the code scenes whose cited lines changed in
          git since the video. Picks one range per part: the changed scenes plus one unchanged "bridge"
          scene after them, so the join back into the old video lands on a screen that already matches.
          Writes 4-checks/patch-plan.json and prints the next commands.
  splice  After the patch take (stage.sh --patch, argo pipeline <run-id>-<part>-patch), cuts the delivered
          video in the silent pause between two scenes, puts the new stretch in, and joins them with a plain
          cut when the frames on both sides match (they should: the patch take replays everything before the
          range). A short dissolve (0.25 s, never through black) is used only where the frames differ a
          little; a big difference fails, because a later scene would no longer fit. The voice of the new
          stretch is matched in loudness. Chapters, captions, scene marks, word timings and the cue log are
          rebuilt on the new time line. The previous version is kept in 5-videos/versions/v<N>/.

Usage:
  python3 patch.py plan <run> [--changed A1-05,B3-02] [--until B3-09] [--part ui|code]
  python3 patch.py splice <run> <ui|code> [--force]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import project  # noqa: E402

FPS = 30
PARTS = {"A": "ui", "B": "code"}
# What a viewer sees or hears of a scene. A change in any of these needs the scene recorded again.
SEEN = ("voice", "kind", "code", "note", "action", "terminal", "diagram", "screen", "flags", "overlay")
SEAMLESS = 2.0      # mean difference (0 to 255) of two frames that look the same (cursor, caret, anti-aliasing)
TOO_DIFFERENT = 25.0
DISSOLVE_S = 0.25
PAUSE_MS = 1500     # PAUSE_AFTER_POINT in lib/pacing.ts: where an old take without scene ends ended its scenes


def load(path: Path):
    return json.loads(path.read_text())


def scenes_by_part(board: dict) -> dict[str, list[dict]]:
    return {PARTS[p["id"]]: [s for c in p["chapters"] for s in c["scenes"]] for p in board["parts"] if p["id"] in PARTS}


def chapter_of(board: dict) -> dict[str, list[str]]:
    """Scene id -> the ids of its chapter, in order."""
    out = {}
    for p in board["parts"]:
        for c in p["chapters"]:
            ids = [s["id"] for s in c["scenes"]]
            for i in ids:
                out[i] = ids
    return out


def seen(scene: dict) -> dict:
    keep = {k: scene.get(k) for k in SEEN}
    if scene.get("kind") == "title":
        keep["title"] = scene.get("title")
    return keep


# ---- code that moved in git since the video -------------------------------------------------------------

def project_root(run: Path) -> Path | None:
    proj = project.find(run)
    return proj.root if proj.layout != "none" else None


def current_refs(root: Path) -> dict[str, tuple[Path, str]]:
    """repos[] of the config: key -> (path, ref), read without a YAML library."""
    text = project.find(root).config.read_text()
    block = re.search(r"^repos:\s*\n((?:[ \t]+.*\n?|\s*\n)*)", text, re.M)
    refs, key, path = {}, None, None
    for line in (block.group(1) if block else "").splitlines():
        line = line.split(" #")[0].rstrip()
        if m := re.match(r"\s*-\s*key:\s*(\S+)", line):
            key, path = m.group(1).strip("'\""), None
        elif m := re.match(r"\s+path:\s*(\S+)", line):
            path = m.group(1).strip("'\"")
        elif (m := re.match(r"\s+ref:\s*(\S+)", line)) and key:
            refs[key] = ((root / (path or ".")).resolve(), m.group(1).strip("'\""))
    return refs


def git_lines(repo: Path, ref: str, file: str, lines: str) -> list[str] | None:
    out = subprocess.run(["git", "-C", str(repo), "show", f"{ref}:./{file}"], capture_output=True, text=True)
    if out.returncode:
        return None
    a, _, b = lines.partition("-")
    all_lines = out.stdout.splitlines()
    return all_lines[int(a) - 1:int(b or a)]


def stale_code(run: Path, scenes: list[dict]) -> list[str]:
    """Code scenes whose cited lines read differently at the repo's current ref than in the video."""
    tour = run / "3-scripts" / "tour.json"
    root = project_root(run)
    if not tour.exists() or not root:
        return []
    shown = {k: (Path(v["path"]) if Path(v["path"]).is_absolute() else (tour.parent / v["path"]).resolve(), v.get("ref", "HEAD"))
             for k, v in load(tour)["repos"].items()}
    now = current_refs(root)
    found = []
    for s in scenes:
        c = s.get("code") or {}
        if s.get("kind") != "code" or not c.get("lines") or c.get("repo") not in shown:
            continue
        repo, was = shown[c["repo"]]
        ref = now.get(c["repo"], (repo, "HEAD"))[1]
        then, today = git_lines(repo, was, c["file"], c["lines"]), git_lines(repo, ref, c["file"], c["lines"])
        if then != today:
            why = "the file is gone" if today is None else f"lines {c['lines']} read differently"
            found.append(f"{s['id']}: {c['file']} at {ref}: {why} (the video shows {was})")
    return found


# ---- plan --------------------------------------------------------------------------------------------------

def plan(args) -> None:
    run = args.run.resolve()
    board = load(run / "2-storyboard" / "storyboard.json")
    snapshot = run / "5-videos" / "storyboard.delivered.json"
    forced = {s.strip() for s in (args.changed or "").split(",") if s.strip()}
    if not snapshot.exists() and not forced:
        raise SystemExit("no 5-videos/storyboard.delivered.json (videos made before patching existed): name the "
                         "changed scenes with --changed A1-05,B3-02")
    old_board = load(snapshot) if snapshot.exists() else board
    new_parts, old_parts = scenes_by_part(board), scenes_by_part(old_board)
    chapters = chapter_of(board)
    feature = load(run / "run.json")["feature"]
    result = {}
    for part, new in new_parts.items():
        if args.part and part != args.part:
            continue
        old = {s["id"]: s for s in old_parts.get(part, [])}
        old_order = [s["id"] for s in old_parts.get(part, [])]
        order = [s["id"] for s in new]
        if not (run / "5-videos" / f"{feature}-{part}.mp4").exists():
            continue
        changed = [i for i, s in enumerate(new) if s["id"] in forced or s["id"] not in old or seen(s) != seen(old[s["id"]])]
        # A removed scene: the scene that now follows its last surviving predecessor is recorded again.
        for k, sid in enumerate(old_order):
            if sid in order:
                continue
            before = next((old_order[j] for j in range(k - 1, -1, -1) if old_order[j] in order), None)
            changed.append(order.index(before) + 1 if before else 0)
        changed = sorted({min(i, len(order) - 1) for i in changed})
        stale = stale_code(run, new)
        if not changed:
            result[part] = {"changed": [], "stale": stale}
            continue
        first, last = changed[0], changed[-1]
        reason = []
        if part == "ui":
            touched = new[first:last + 1]
            if any("writes" in (s.get("flags") or []) or (s["id"] in old and s.get("action") != old[s["id"]].get("action"))
                   for s in touched):
                # What the app shows later may change too (a different booking, another row): record to the end
                # of the chapter, where the next chapter starts from a fresh screen.
                last = max(last, order.index(chapters[new[last]["id"]][-1]))
                reason.append("an action or a write changed: recorded to the end of its chapter")
        if args.until:
            last = max(last, order.index(args.until))
        # One unchanged bridge scene after the change, so the join back lands on a screen the old video has.
        bridge = None
        if last + 1 < len(order):
            last += 1
            bridge = order[last]
        prev = order[first - 1] if first > 0 else None
        seconds = lambda ss: sum(s.get("seconds", 10) for s in ss)
        patch_s = seconds(new[first:last + 1]) + 2.5 * first
        full_s = seconds(new)
        result[part] = {
            "changed": [order[i] for i in changed], "removed": [s for s in old_order if s not in order],
            "first": order[first], "last": order[last], "prev": prev, "bridge": bridge,
            "stale": stale, "reason": reason, "patchSeconds": round(patch_s), "fullSeconds": round(full_s),
        }
    out = run / "4-checks" / "patch-plan.json"
    out.write_text(json.dumps(result, indent=2) + "\n")

    run_id = run.name
    for part, p in result.items():
        print(f"\n{part}:")
        for line in p.get("stale", []):
            print(f"  code changed since the video: {line}")
        if not p.get("changed"):
            print("  nothing changed in the storyboard" + (" (update the scenes above first)" if p.get("stale") else ""))
            continue
        print(f"  changed: {', '.join(p['changed'])}" + (f"; removed: {', '.join(p['removed'])}" if p["removed"] else ""))
        for r in p["reason"]:
            print(f"  note: {r}")
        print(f"  record {p['first']} to {p['last']}" + (f" ({p['bridge']} is the unchanged bridge back into the video)" if p["bridge"] else " (to the end)"))
        print(f"  about {p['patchSeconds'] // 60}:{p['patchSeconds'] % 60:02} of recording instead of {p['fullSeconds'] // 60}:{p['fullSeconds'] % 60:02} for the whole part")
        ids = [s["id"] for s in new_parts[part]]
        total, span = len(ids), ids.index(p["last"]) - ids.index(p["first"]) + 1
        if span > total * 0.6:
            print(f"  advice: {span} of {total} scenes: recording the whole part again is about as fast, and simpler")
        print(f"  next: bash <skill>/scripts/stage.sh <out> {run} --patch {part} {p['first']} {p['last']}")
        print(f"        cd <rt> && npx argo tts generate demos/{run_id}-{part}-patch.scenes.json && node tools/beats.mjs {run_id}-{part}-patch")
        print(f"        npx argo pipeline {run_id}-{part}-patch      (gate 2 first: the fast part replays every write before the range)")
        print(f"        python3 <skill>/scripts/patch.py splice {run} {part}")
    print(f"\nplan written to {out}")


# ---- splice ------------------------------------------------------------------------------------------------

def probe(path: Path) -> dict:
    return json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_chapters",
                                               "-show_format", "-of", "json", str(path)]))


def video_seconds(info: dict) -> float:
    for s in info["streams"]:
        if s["codec_type"] == "video" and s.get("duration"):
            return float(s["duration"])
    return float(info["format"]["duration"])


def snap(t: float) -> float:
    return round(t * FPS) / FPS


def frame(video: Path, t: float) -> bytes:
    return subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1",
                           "-vf", "scale=320:180,format=gray", "-f", "rawvideo", "-"],
                          check=True, capture_output=True, stdin=subprocess.DEVNULL).stdout


def difference(a: bytes, b: bytes) -> float:
    n = min(len(a), len(b))
    return sum(abs(x - y) for x, y in zip(a[:n], b[:n])) / max(1, n) if n else 255.0


def loudness(video: Path, start: float, end: float) -> float | None:
    out = subprocess.run(["ffmpeg", "-v", "info", "-nostats", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(video),
                          "-vn", "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
                         capture_output=True, text=True, stdin=subprocess.DEVNULL).stderr
    m = re.findall(r"I:\s*(-?[\d.]+) LUFS", out)
    return float(m[-1]) if m and float(m[-1]) > -70 else None


def read_srt(path: Path) -> list[tuple[float, float, str]]:
    if not path.exists():
        return []
    cues = []
    for block in path.read_text().strip().split("\n\n"):
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+) --> (\d+):(\d+):(\d+)[,.](\d+)\n(.*)", block, re.S)
        if m:
            g = [int(x) for x in m.groups()[:8]]
            cues.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000, m.group(9).strip()))
    return cues


def stamp(t: float, sep: str) -> str:
    ms = max(0, int(round(t * 1000)))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}{sep}{ms % 1000:03}"


PATCH_IN = "kt-patch-in"  # lib/sync.ts: the silent mark where a patch take's range starts


def head_trim(timing: dict) -> float:
    """Seconds Argo cut from the start of the video: everything before the first mark, less 0.2 s, when that
    is more than 0.5 s (computeHeadTrimMs). Marks and cues are on the recording's clock; the video is not."""
    if not timing:
        return 0.0
    trim = max(0, min(timing.values()) - 200)
    return trim / 1000 if trim > 500 else 0.0


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def scene_ends(timing: dict, report: dict, beats: dict, cues: list[dict]) -> dict[str, float]:
    """Where each scene ended in a take, in seconds: logged by s.end() in newer takes, else worked out the
    way s.end() waits (the last spoken sound plus the pause, never before the clip ends)."""
    ends = {c["scene"]: c["endMs"] / 1000 for c in cues if "endMs" in c}
    placed = {s["scene"]: s for s in report.get("scenes", [])}
    for scene, mark in timing.items():
        if scene in ends:
            continue
        start = placed.get(scene, {}).get("startMs", mark)
        b = beats.get(scene)
        if b:
            ends[scene] = max(start + b["speechMs"][1] + PAUSE_MS, start + b["clipMs"] + 100) / 1000
        else:
            ends[scene] = (start + placed.get(scene, {}).get("durationMs", 0) + PAUSE_MS) / 1000
    return ends


def splice(args) -> None:
    run = args.run.resolve()
    part = args.part
    plans = load(run / "4-checks" / "patch-plan.json")
    p = plans.get(part)
    if not p or not p.get("changed"):
        raise SystemExit(f"the plan has nothing to record for {part}: run patch.py plan first")
    feature = load(run / "run.json")["feature"]
    out_dir = run.parent.parent
    rt = out_dir / "runtime"
    demo = f"{run.name}-{part}-patch"
    checks, videos = run / "4-checks", run / "5-videos"

    old_video = videos / f"{feature}-{part}.mp4"
    new_video = rt / "videos" / f"{demo}.mp4"
    argo = rt / ".argo" / demo
    for f in (old_video, new_video, argo / ".timing.json"):
        if not f.exists():
            raise SystemExit(f"missing {f}: record the patch take first (argo pipeline {demo})")
    subprocess.run(["node", "tools/captions.mjs", demo], cwd=rt, check=True)

    old = {"timing": load(checks / f"{part}-timing.json"), "report": load(checks / f"{part}-scene-report.json"),
           "beats": load(checks / f"{part}-beats.json") if (checks / f"{part}-beats.json").exists() else {},
           "cues": read_jsonl(checks / f"{part}-cues.jsonl")}
    new = {"timing": load(argo / ".timing.json"), "report": load(argo / "scene-report.json"),
           "beats": load(rt / "demos" / f"{demo}.beats.json"), "cues": read_jsonl(argo / "cues.jsonl")}
    order = load(rt / "demos" / f"{demo}.patch.json")["order"]
    first, last = order.index(p["first"]), order.index(p["last"])
    before, inside, after = order[:first], order[first:last + 1], order[last + 1:]
    missing = [s for s in inside if s not in new["timing"]]
    if missing:
        raise SystemExit(f"the patch take did not record {', '.join(missing)}: check its log")

    old_len, new_len = video_seconds(probe(old_video)), video_seconds(probe(new_video))
    # Everything below is on each video's own clock: the recording's clock less Argo's head trim.
    for take in (old, new):
        trim_ms = head_trim(take["timing"]) * 1000
        take["timing"] = {k: v - trim_ms for k, v in take["timing"].items() if k != PATCH_IN}
        for c in take["cues"]:
            for key in ("wordMs", "actMs", "calledMs", "endMs", "ms"):
                if key in c and isinstance(c[key], (int, float)):
                    c[key] -= trim_ms
    old_ends = scene_ends(old["timing"], old["report"], old["beats"], old["cues"])
    new_ends = scene_ends(new["timing"], new["report"], new["beats"], new["cues"])
    marker = next((c for c in new["cues"] if c.get("patch") == "in"), None)
    if marker is None:
        raise SystemExit("the patch take has no start marker: was it staged with stage.sh --patch?")
    cut_in = snap(old_ends[p["prev"]]) if p["prev"] else 0.0
    new_in = snap(max(0.0, marker["ms"] / 1000))
    at_end = not after
    cut_out = old_len if at_end else snap(old_ends[p["last"]])
    new_out = new_len if at_end else snap(new_ends[p["last"]])

    # Do the screens match on both sides of each join?
    joins = []
    if p["prev"]:
        joins.append(("in", difference(frame(old_video, cut_in - 1 / FPS), frame(new_video, new_in))))
    if not at_end:
        joins.append(("out", difference(frame(new_video, new_out - 1 / FPS), frame(old_video, cut_out))))
    fades = {}
    for name, diff in joins:
        where = f"after {p['prev']}" if name == "in" else f"after {p['last']}"
        if diff < SEAMLESS:
            fades[name] = 0.0
            print(f"join {where}: the screens match (difference {diff:.1f}): a plain cut")
        elif diff < TOO_DIFFERENT or args.force:
            fades[name] = DISSOLVE_S
            print(f"join {where}: the screens differ a little (difference {diff:.1f}): a {DISSOLVE_S} s dissolve")
        else:
            raise SystemExit(f"FAIL: join {where}: the screens differ a lot (difference {diff:.1f}). The patch take did not "
                             "reach the delivered video's state. Check the fast part of the take, or record a longer range "
                             "(patch.py plan --until <scene>). --force joins them with a dissolve anyway.")

    gain = 0.0
    old_lufs, new_lufs = loudness(old_video, 0, old_len), loudness(new_video, new_in, new_out)
    if old_lufs is not None and new_lufs is not None:
        gain = max(-6.0, min(6.0, old_lufs - new_lufs))
    print(f"voice loudness: delivered {old_lufs} LUFS, new stretch {new_lufs} LUFS, gain {gain:+.1f} dB")

    # Pieces on the new time line.
    pieces = []
    if cut_in > 0:
        pieces.append(("old", 0.0, cut_in, 0.0))
    pieces.append(("new", new_in, new_out, gain))
    if not at_end:
        pieces.append(("old", cut_out, old_len, 0.0))
    fade_in, fade_out = fades.get("in", 0.0), fades.get("out", 0.0)
    graph, v_last, a_last, length = [], None, None, 0.0
    starts = []
    # One ffmpeg input per piece: two pieces read from one input make ffmpeg hold every frame between them
    # in memory (gigabytes for a few minutes of 1080p), and the encode is killed.
    for k, (src, a, b, db) in enumerate(pieces):
        i = k
        v, s = f"v{k}", f"a{k}"
        graph.append(f"[{i}:v]trim=start={a:.4f}:end={b:.4f},setpts=PTS-STARTPTS,fps={FPS},format=yuv420p,setsar=1[{v}]")
        vol = f",volume={db:.2f}dB" if db else ""
        graph.append(f"[{i}:a]aresample=48000:async=1:first_pts=0,atrim=start={a:.4f}:end={b:.4f},asetpts=PTS-STARTPTS{vol},apad,atrim=duration={b - a:.4f}[{s}]")
        if v_last is None:
            v_last, a_last, length = v, s, b - a
            starts.append(0.0)
            continue
        fade = fade_in if src == "new" else fade_out
        if fade:
            graph.append(f"[{v_last}][{v}]xfade=transition=fade:duration={fade}:offset={length - fade:.4f}[x{k}]")
            graph.append(f"[{a_last}][{s}]acrossfade=d={fade}[y{k}]")
        else:
            graph.append(f"[{v_last}][{a_last}][{v}][{s}]concat=n=2:v=1:a=1[x{k}][y{k}]")
        starts.append(length - fade)
        v_last, a_last = f"x{k}", f"y{k}"
        length += (b - a) - fade

    first_new = 1 if cut_in > 0 else 0
    new_start = starts[first_new]
    tail_start = starts[first_new + 1] if not at_end else None

    def old_t(t: float) -> float | None:
        if t < cut_in:
            return t
        if tail_start is not None and t >= cut_out:
            return tail_start + (t - cut_out)
        return None

    def new_t(t: float) -> float | None:
        return new_start + (t - new_in) if new_in - 0.05 <= t <= new_out + 0.05 else None

    ms = lambda t: int(round(t * 1000))
    # Scene marks, placements, word timings and cues on the new time line.
    timing, report_scenes, beats, cues = {}, [], {}, []
    old_placed = {s["scene"]: s for s in old["report"]["scenes"]}
    new_placed = {s["scene"]: s for s in new["report"]["scenes"]}
    for scene in order:
        src, shift = (new, new_t) if scene in inside else (old, old_t)
        if scene not in src["timing"]:
            continue
        t = shift(src["timing"][scene] / 1000)
        if t is None:
            continue
        timing[scene] = ms(t)
        placed = (new_placed if scene in inside else old_placed).get(scene)
        if placed:
            report_scenes.append({**placed, "startMs": ms(shift(placed["startMs"] / 1000) or t)})
        if scene in src["beats"]:
            beats[scene] = src["beats"][scene]
    for scene_set, src, shift in ((set(before) | set(after), old, old_t), (set(inside), new, new_t)):
        for c in src["cues"]:
            if c.get("scene") not in scene_set:
                continue
            moved = dict(c)
            for key in ("wordMs", "actMs", "calledMs", "endMs"):
                if key in c:
                    t = shift(c[key] / 1000)
                    if t is None:
                        break
                    moved[key] = ms(t)
            else:
                cues.append(moved)
    report = {**old["report"], "scenes": sorted(report_scenes, key=lambda s: s["startMs"])}

    # Chapters (one per scene) and captions.
    chapters = []
    for info, shift, keep in ((probe(old_video), old_t, set(before) | set(after)), (probe(new_video), new_t, set(inside))):
        for ch in info.get("chapters", []):
            title = ch.get("tags", {}).get("title", "")
            t = shift(float(ch["start_time"]))
            if title in keep and t is not None:
                chapters.append((t, title))
    chapters.sort()
    captions = [(old_t(a), old_t(a) + (b - a), x) for a, b, x in read_srt(videos / f"{feature}-{part}.srt") if old_t(a) is not None]
    captions += [(new_t(a), new_t(a) + (b - a), x) for a, b, x in read_srt(rt / "videos" / f"{demo}.srt") if new_t(a) is not None]
    captions.sort()

    out = videos / f"{feature}-{part}.mp4"
    versions = videos / "versions"
    n = 1 + max([int(d.name[1:]) for d in versions.glob("v*") if d.name[1:].isdigit()] or [0])
    keep = versions / f"v{n}"
    with tempfile.TemporaryDirectory() as tmp:
        meta = [";FFMETADATA1"]
        for k, (t, title) in enumerate(chapters):
            end = chapters[k + 1][0] if k + 1 < len(chapters) else length
            meta += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={ms(t)}", f"END={ms(end)}", f"title={title}"]
        meta_file = Path(tmp) / "chapters.txt"
        meta_file.write_text("\n".join(meta) + "\n")
        tmp_out = Path(tmp) / out.name
        inputs = [arg for src, *_ in pieces for arg in ("-i", str(old_video if src == "old" else new_video))]
        subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-i", str(meta_file),
                        "-filter_complex", ";".join(graph), "-map", f"[{v_last}]", "-map", f"[{a_last}]",
                        "-map_chapters", str(len(pieces)),
                        "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp_out)],
                       check=True, stdin=subprocess.DEVNULL)
        # Encoded: only now keep the delivered version (a failed encode leaves everything as it was).
        keep.mkdir(parents=True)
        for f in [*videos.glob(f"{feature}-{part}.*"), videos / "storyboard.delivered.json", *checks.glob(f"{part}-*")]:
            if f.is_file():
                shutil.copy2(f, keep / f.name)
        shutil.move(str(tmp_out), out)
    (videos / f"{feature}-{part}.srt").write_text("".join(f"{i}\n{stamp(a, ',')} --> {stamp(b, ',')}\n{t}\n\n" for i, (a, b, t) in enumerate(captions, 1)))
    (videos / f"{feature}-{part}.vtt").write_text("WEBVTT\n\n" + "".join(f"{stamp(a, '.')} --> {stamp(b, '.')}\n{t}\n\n" for a, b, t in captions))
    (checks / f"{part}-timing.json").write_text(json.dumps(timing, indent=2) + "\n")
    (checks / f"{part}-scene-report.json").write_text(json.dumps(report, indent=2) + "\n")
    (checks / f"{part}-beats.json").write_text(json.dumps(beats, indent=2, ensure_ascii=False) + "\n")
    (checks / f"{part}-cues.jsonl").write_text("".join(json.dumps(c) + "\n" for c in cues))

    # The storyboard the video now follows: this part's scenes from the current storyboard.
    board = load(run / "2-storyboard" / "storyboard.json")
    p["spliced"] = True
    (run / "4-checks" / "patch-plan.json").write_text(json.dumps(plans, indent=2) + "\n")
    if all(v.get("spliced") or not v.get("changed") for v in plans.values()):
        (videos / "storyboard.delivered.json").write_text(json.dumps(board, indent=2, ensure_ascii=False) + "\n")
    run_json = load(run / "run.json")
    run_json.setdefault("versions", []).append({"version": n + 1, "date": date.today().isoformat(), "part": part,
                                                "recorded": f"{p['first']}..{p['last']}", "changed": p["changed"],
                                                "previous": f"5-videos/versions/v{n}"})
    (run / "run.json").write_text(json.dumps(run_json, indent=2, ensure_ascii=False) + "\n")

    gap = abs(video_seconds(probe(out)) - float(probe(out)["format"]["duration"]))
    print(f"{out.name}: {length:.1f} s (was {old_len:.1f} s), {len(chapters)} chapters, {len(captions)} captions; "
          f"recorded {p['first']}..{p['last']}, kept the rest; previous version in {keep.relative_to(run)}")
    print(f"next: python3 <skill>/scripts/check_video.py {out} --report {checks / f'{part}-scene-report.json'} "
          f"--sheet {checks / f'{part}-sheet.png'} --marks {checks / f'{part}-timing.json'}")
    print(f"      python3 <skill>/scripts/check_sync.py {rt / '.argo' / demo}   (the new stretch, from the patch take's own log)")
    print("      python3 <skill>/scripts/finish.py <run>   (when the parts are delivered as one file)")
    if gap > 0.15:
        raise SystemExit(f"FAIL: sound and picture lengths differ by {gap * 1000:.0f} ms")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plan")
    a.add_argument("run", type=Path)
    a.add_argument("--changed", help="scene ids to record again even if the storyboard did not change them")
    a.add_argument("--until", help="record at least to this scene")
    a.add_argument("--part", choices=["ui", "code"])
    b = sub.add_parser("splice")
    b.add_argument("run", type=Path)
    b.add_argument("part", choices=["ui", "code"])
    b.add_argument("--force", action="store_true", help="join with a dissolve even when the screens differ a lot")
    args = ap.parse_args()
    plan(args) if args.cmd == "plan" else splice(args)


if __name__ == "__main__":
    main()
