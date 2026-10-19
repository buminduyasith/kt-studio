#!/usr/bin/env python3
"""Who built a feature, from git: the people with the most commits on the feature's files, for the
"Who built this feature?" question of the intro and the outro. Names only: never emails, never bots.

Usage: python3 authors.py <repo-path> <ref> <path>... [--top 3]
  <path>: the files or folders on the feature's code path (from the brief). Prints a JSON list of names,
  most commits first, for `choices.py ask ... --offer '{"built_by": [...]}'`. The person picks who is
  shown, or no names at all; nothing here goes on screen by itself.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys

BOT = re.compile(r"\[bot\]|\bbot\b|dependabot|renovate|github-actions|greenkeeper|snyk|semantic-release", re.I)


def authors(repo: str, ref: str, paths: list[str], top: int = 3) -> list[str]:
    out = subprocess.run(["git", "-C", repo, "shortlog", "-sn", "--no-merges", ref, "--", *paths],
                         capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(f"git shortlog failed: {out.stderr.strip()}")
    names = []
    for line in out.stdout.splitlines():
        m = re.match(r"^\s*\d+\s+(.+?)\s*$", line)
        if m and not BOT.search(m.group(1)) and "@" not in m.group(1) and m.group(1) not in names:
            names.append(m.group(1))
    return names[:top]


def main() -> None:
    args = sys.argv[1:]
    top = 3
    if "--top" in args:
        i = args.index("--top")
        top = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    if len(args) < 3:
        raise SystemExit(__doc__.split("Usage:")[1])
    print(json.dumps(authors(args[0], args[1], args[2:], top), ensure_ascii=False))


if __name__ == "__main__":
    main()
