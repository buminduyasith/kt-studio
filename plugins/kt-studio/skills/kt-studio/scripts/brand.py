#!/usr/bin/env python3
"""Your brand on the videos: a logo and one colour, set once per project in .kt-studio/config.yml.

    branding:
      logo: docs/brand/logo.svg     # a file in the project: svg, png, jpg or webp, at most 1 MB
      accent: "#0e7ad3"             # one colour for highlights
      name: Acme                    # optional: shown next to the logo

or `branding: none` for KT Studio's own look. /kt-studio:init asks once ("Add your brand?") and writes
one of the two; a project with neither is never asked during a video (the doctor only mentions it).

The logo shows on the intro and the outro cards; the colour on the cards, the map's active path and
the code highlight. A colour too dark to read on the dark screens is lightened until it is readable,
and the script says so.

Usage:
  python3 brand.py <root> --find       what init can offer, as JSON: logo files and brand colours found
                                        in the project's own files, best first
  python3 brand.py <root> --check      problems with the branding setting, one per line (nothing when fine)
  python3 brand.py <root> --resolved   the brand as the video uses it, as JSON:
                                        {accent, accentSoft, logo (a data URI), name, note}, or {} for the default look
"""
from __future__ import annotations

import base64
import colorsys
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detect  # noqa: E402
import project  # noqa: E402

LOGO_TYPES = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
LOGO_NAME = re.compile(r"(logo|brand|wordmark|favicon|icon)[^/]*\.(svg|png|webp|jpe?g)$", re.I)
MAX_LOGO = 1_000_000
HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
BACKGROUND = "#1e1e1e"   # the lightest of the dark screens the colour sits on (tour, maps, cards)
DEFAULT_ACCENT = "#ffc400"
# Where projects keep their brand colour: CSS custom properties, Sass variables, theme objects, web manifests.
COLOUR_PATTERNS = [
    re.compile(r"--(?:brand|primary|accent|theme)[\w-]*\s*:\s*(#[0-9a-fA-F]{3,6})\b"),
    re.compile(r"\$(?:brand|primary|accent)[\w-]*\s*:\s*(#[0-9a-fA-F]{3,6})\b"),
    re.compile(r"[\"']?(?:brand|primary|accent)[\w-]*[\"']?\s*:\s*[\"'](#[0-9a-fA-F]{3,6})[\"']"),
    re.compile(r"\"theme_color\"\s*:\s*\"(#[0-9a-fA-F]{3,6})\""),
]
COLOUR_FILES = re.compile(r".*\.(css|scss|sass|less|styl)$|^tailwind\.config\.[cm]?[jt]s$|^(site\.)?(web)?manifest\.json$|"
                          r".*(theme|tokens|colou?rs)[^/]*\.(json|[cm]?[jt]s)$", re.I)


def settings(proj: project.Project) -> dict | None:
    """The `branding:` block of config.yml: None when it is not there, {} for `branding: none`."""
    text = proj.config.read_text(errors="ignore") if proj.config.is_file() else ""
    m = re.search(r"^branding:[ \t]*([^\n#]*)(?:#[^\n]*)?\n((?:[ \t]+.*\n?|[ \t]*\n)*)", text + "\n", re.M)
    if not m:
        return None
    if m.group(1).strip().strip("'\"").lower() in ("none", "no", "false", "{}"):
        return {}
    found = re.findall(r"^[ \t]+([A-Za-z_]+):[ \t]*([^\n]*)", m.group(2), re.M)
    out = {}
    for k, v in found:
        v = v.strip()
        v = v[1:v.index(v[0], 1)] if v[:1] in "'\"" and v.count(v[0]) >= 2 else re.sub(r"\s+#.*$", "", v).strip()
        if v:
            out[k] = v
    return out


# ---- colour

def rgb(hex_: str) -> tuple[int, int, int]:
    h = hex_.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hexed(c: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in c)


def luminance(hex_: str) -> float:
    def lin(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(hex_)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(a: str, b: str, t: float) -> str:
    ca, cb = rgb(a), rgb(b)
    return hexed(tuple(x + (y - x) * t for x, y in zip(ca, cb)))


def readable(accent: str, background: str = BACKGROUND, needed: float = 4.5) -> str:
    """The accent, made lighter just enough to be read on the dark background. Only the lightness
    changes, so the hue stays the brand's (navy becomes a clear blue, not grey)."""
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in rgb(accent)))
    while l <= 1:
        c = hexed(tuple(v * 255 for v in colorsys.hls_to_rgb(h, l, s)))
        if contrast(c, background) >= needed:
            return c
        l += 0.02
    return "#ffffff"


# ---- find, check, resolve

def find(root: Path) -> dict:
    logos, colours, where = [], Counter(), defaultdict(set)
    for path in detect.walk(root, 4):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if LOGO_NAME.search(path.name) and path.suffix.lower() in LOGO_TYPES and path.stat().st_size <= MAX_LOGO:
            logos.append(rel)
        if COLOUR_FILES.match(path.name) and path.stat().st_size < 500_000:
            text = detect.read(path)
            for pattern in COLOUR_PATTERNS:
                for c in pattern.findall(text):
                    c = c.lower() if len(c) == 7 else "#" + "".join(ch * 2 for ch in c[1:].lower())
                    if len(c) == 7:
                        colours[c] += 1
                        where[c].add(rel)
    # "logo" before "icon", vector before bitmap, near the top of the project first.
    logos.sort(key=lambda p: ("logo" not in p.lower(), "icon" in p.lower(), not p.lower().endswith(".svg"), p.count("/"), p))
    return {"logos": logos[:3],
            "colours": [{"hex": c, "found_in": sorted(where[c])[:2]} for c, _ in colours.most_common(3)]}


def check(proj: project.Project) -> list[str]:
    b = settings(proj)
    if not b:
        return []
    problems = []
    logo = b.get("logo")
    if logo:
        path = (proj.root / logo).resolve()
        try:
            path.relative_to(proj.root.resolve())
        except ValueError:
            problems.append(f"branding.logo {logo}: keep the logo inside the project, so the whole team has it")
        if not path.is_file():
            problems.append(f"branding.logo {logo}: file not found")
        elif path.suffix.lower() not in LOGO_TYPES:
            problems.append(f"branding.logo {logo}: use an svg, png, jpg or webp file")
        elif path.stat().st_size > MAX_LOGO:
            problems.append(f"branding.logo {logo}: {path.stat().st_size // 1024} KB; keep it under 1 MB")
    accent = b.get("accent")
    if accent and not HEX.match(accent):
        problems.append(f"branding.accent {accent}: write a colour like \"#0e7ad3\" (in quotes)")
    if len(b.get("name", "")) > 40:
        problems.append("branding.name: keep it to about 40 characters")
    return problems


def resolved(proj: project.Project) -> dict:
    """The brand as the video draws it; {} for KT Studio's own look (or a setting with problems)."""
    b = settings(proj)
    if not b or check(proj):
        return {}
    out = {}
    note = []
    accent = b.get("accent")
    if accent:
        accent = accent.lower()
        use = readable(accent)
        if use != accent:
            note.append(f"the colour {accent} is too dark to read on the dark screens; the videos use {use}, a lighter shade of it")
        out["accent"] = use
        out["accentSoft"] = mix(use, "#ffffff", 0.6)
    if b.get("logo"):
        path = proj.root / b["logo"]
        out["logo"] = f"data:{LOGO_TYPES[path.suffix.lower()]};base64,{base64.b64encode(path.read_bytes()).decode()}"
    if b.get("name"):
        out["name"] = b["name"]
    if note:
        out["note"] = "; ".join(note)
    return out


def main() -> None:
    args = sys.argv[1:]
    if len(args) != 2 or args[1] not in ("--find", "--check", "--resolved"):
        raise SystemExit(__doc__.split("Usage:")[1])
    proj = project.find(args[0])
    if args[1] == "--find":
        print(json.dumps(find(proj.root), indent=2))
    elif args[1] == "--check":
        for line in check(proj):
            print(line)
    else:
        print(json.dumps(resolved(proj)))


if __name__ == "__main__":
    main()
