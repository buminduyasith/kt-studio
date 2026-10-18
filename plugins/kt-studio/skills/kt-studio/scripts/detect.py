#!/usr/bin/env python3
"""Looks around a project: a draft .kt-studio/config.yml and draft "## Services" and "## Addresses" tables
for `init`, or the app addresses a run could show.

Usage: python3 detect.py <project-root>           draft config.yml + draft tables for instructions.md
       python3 detect.py <project-root> --apps    candidate app addresses for one run, best first, with
                                                  the service, the environment, where each was found and
                                                  whether it answers right now

Finds, without running anything or reading secrets:
- git repos (the root and folders up to two levels down) with their default branch,
- docs to read first (README, docs folders, API contracts, architecture notes),
- app URLs in the project's own files (the ## Addresses table of the instructions, CLAUDE.md, README,
  package.json, compose files, launch configs, example env files, framework configs), with where each
  was found.

Language agnostic: it reads text, not a build system. Every guess is marked for the user to confirm.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import project  # noqa: E402
import services  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", "out", "target", "bin", "obj", ".venv",
             "venv", "__pycache__", ".next", ".nuxt", ".cache", "coverage", ".kt-studio", ".idea", ".gradle"}
# Files that often name the local URL or port. Real .env files are never read: they hold secrets.
URL_FILES = re.compile(r"^(readme.*|.*\.md|package\.json|docker-compose.*\.ya?ml|compose.*\.ya?ml|procfile|makefile|"
                       r"\.env\.(example|sample|template|dist)|launch(settings)?\.json|appsettings.*\.json|"
                       r"application.*\.(properties|ya?ml)|vite\.config\.[jt]s|angular\.json|nuxt\.config\.[jt]s|"
                       r"next\.config\.[jt]s|webpack.*\.js|.*\.toml|settings\.py|config\.exs|launch\.json)$", re.I)
EXAMPLE_ENV = re.compile(r"^\.env\.(example|sample|template|dist)$", re.I)
LOCAL_URL = re.compile(r"https?://(?:localhost|127\.0\.0\.1|\[::1\]|[a-z0-9-]+\.(?:localhost|test))(?::\d{2,5})?(?:/[^\s\"'<>)`\]]*)?", re.I)
PORT = re.compile(r"(?:^|[\s\"'])(?:PORT|SERVER_PORT|HTTP_PORT|APP_PORT)\s*[=:]\s*\"?(\d{2,5})", re.I | re.M)
COMPOSE_PORT = re.compile(r"^\s*-\s*[\"']?(\d{2,5}):\d{2,5}", re.M)
HOSTED_URL = re.compile(r"https?://[a-z0-9.-]*\b(?:dev|qa|test|uat|stage|staging|sandbox|preprod)\b[a-z0-9.-]*\.[a-z]{2,}(?:/[^\s\"'<>)`\]]*)?", re.I)
# A port the code listens on by default: app.listen(4100), PORT || 4100, getenv("PORT", "8000").
SOURCE_FILES = re.compile(r".*\.(js|mjs|cjs|ts|py|go|rb|php|java|kt|cs|rs|ex|exs)$", re.I)
SOURCE_PORT = re.compile(r"(?:\.listen\(\s*|PORT[\"']?\s*(?:\|\||\?\?|\bor\b|,)\s*[\"']?)(\d{4,5})\b")
PASSWORD_VAR = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*PASSWORD)\s*=", re.M)  # line start: a command or an env file
DOC_DIRS = ("docs", "doc", "documentation", "wiki", "adr", "adrs", "architecture", "design", "contracts", "schemas", "api-docs")
DOC_FILES = re.compile(r"^(readme|architecture|design|contributing|overview|glossary|domain)[^/]*\.(md|rst|adoc|txt)$|"
                       r"^(.*[.-])?(openapi|swagger|asyncapi)([.-][^/]*)?\.(ya?ml|json)$|.*\.(proto|graphql|gql|avsc)$", re.I)


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else ""


def walk(root: Path, depth: int):
    """Files and folders up to `depth` levels below root, skipping build and dependency folders."""
    stack = [(root, 0)]
    while stack:
        folder, level = stack.pop()
        try:
            entries = sorted(folder.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name in SKIP_DIRS or (entry.name.startswith(".") and entry.name not in (".vscode", ".claude")):
                    continue
                yield entry
                if level < depth:
                    stack.append((entry, level + 1))
            else:
                yield entry


def default_ref(path: Path) -> str:
    """origin's default branch, else origin/<current branch>, else the current branch, else HEAD."""
    default = git(path, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    branch = git(path, "branch", "--show-current")
    remote_branch = branch and git(path, "rev-parse", "--verify", "--quiet", f"origin/{branch}")
    return default or (f"origin/{branch}" if remote_branch else branch) or "HEAD"


def find_repos(root: Path) -> list[dict]:
    repos, seen = [], set()
    candidates = [root] + [p for p in walk(root, 1) if p.is_dir()]
    for path in candidates:
        top = git(path, "rev-parse", "--show-toplevel")
        if not top or top in seen or Path(top) != path.resolve():
            continue
        seen.add(top)
        ref = default_ref(path)
        rel = "." if path == root else "./" + path.relative_to(root).as_posix()
        key = re.sub(r"[^a-z0-9]+", "-", (root.name if path == root else path.name).lower()).strip("-") or "app"
        repos.append({"key": key, "path": rel, "ref": ref, "remote": bool(git(path, "remote"))})
    if not repos:
        repos = monorepo_parts(root)
    return repos


def monorepo_parts(root: Path) -> list[dict]:
    """The project is a folder inside a bigger git repo (a monorepo). Each app folder in it (one that holds
    source files) becomes a repo entry with the outer repo's ref, so the tour can label Frontend and Backend.
    git reads `<ref>:./<path>` relative to such a folder, so the paths stay short."""
    top = git(root, "rev-parse", "--show-toplevel")
    if not top:
        return []
    ref = default_ref(root)
    remote = bool(git(root, "remote"))
    parts = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir() and p.name not in SKIP_DIRS and not p.name.startswith(".")):
        if folder.name.lower() in DOC_DIRS:
            continue
        if any(SOURCE_FILES.match(f.name) for f in folder.rglob("*") if f.is_file() and not (set(f.relative_to(folder).parts) & SKIP_DIRS)):
            key = re.sub(r"[^a-z0-9]+", "-", folder.name.lower()).strip("-") or "app"
            parts.append({"key": key, "path": "./" + folder.name, "ref": ref, "remote": remote, "inside": top})
    if len(parts) < 2:  # one app folder, or code at the root: the project folder is the repo
        key = re.sub(r"[^a-z0-9]+", "-", root.name.lower()).strip("-") or "app"
        parts = [{"key": key, "path": ".", "ref": ref, "remote": remote, "inside": top}]
    return parts


def find_docs(root: Path) -> list[str]:
    docs = []
    for path in walk(root, 2):
        rel = path.relative_to(root).as_posix()
        if path.is_dir() and path.name.lower() in DOC_DIRS:
            docs.append(rel + "/")
        elif path.is_file() and DOC_FILES.match(path.name) and rel.count("/") <= 2:
            if not any(rel.startswith(d) for d in docs):
                docs.append(rel)
    readme_first = sorted(docs, key=lambda d: (not d.lower().startswith("readme"), d.count("/"), d))
    return readme_first[:12]


def read(path: Path) -> str:
    try:
        return path.read_text(errors="ignore")[:200_000] if path.stat().st_size < 2_000_000 else ""
    except OSError:
        return ""


def find_urls(root: Path):
    local, hosted, sources, secrets = Counter(), Counter(), defaultdict(set), set()
    for path in walk(root, 3):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if SOURCE_FILES.match(path.name) and "test" not in rel.lower():
            for port in SOURCE_PORT.findall(read(path)):
                base = f"http://localhost:{port}"
                local[base] += 1
                sources[base].add(rel)
            continue
        if not URL_FILES.match(path.name):
            continue
        text = read(path)
        for url in LOCAL_URL.findall(text):
            base = re.match(r"https?://[^/]+", url).group(0).replace("0.0.0.0", "localhost")
            local[base] += 1
            sources[base].add(rel)
        ports = PORT.findall(text) + (COMPOSE_PORT.findall(text) if "compose" in path.name.lower() else [])
        for port in ports:
            if 80 <= int(port) <= 65535:
                base = f"http://localhost:{port}"
                local[base] += 1
                sources[base].add(rel)
        for url in HOSTED_URL.findall(text):
            base = re.match(r"https?://[^/]+", url).group(0)
            hosted[base] += 1
            sources[base].add(rel)
        if EXAMPLE_ENV.match(path.name) or path.suffix.lower() == ".md" or path.name.lower().startswith("readme"):
            secrets.update(PASSWORD_VAR.findall(text))
    # localhost:4200 and 127.0.0.1:4200 are the same app: keep the spelling the project uses most.
    merged, merged_sources = Counter(), defaultdict(set)
    by_port = defaultdict(list)
    for base, count in local.items():
        by_port[re.sub(r"^https?://(localhost|127\.0\.0\.1|\[::1\])", "", base)].append((count, base))
    for spellings in by_port.values():
        best = max(spellings)[1]
        merged[best] = sum(c for c, _ in spellings)
        for _, base in spellings:
            merged_sources[best] |= sources[base]
    sources.update(merged_sources)
    return merged, hosted, sources, sorted(secrets)


STAGES = re.compile(r"\b(dev|develop|qa|test|uat|stage|staging|sandbox|preprod|prod)\b", re.I)


def guess_env(url: str) -> str:
    """local for this computer, else the stage word in the host name (dev, qa, staging ...)."""
    if LOCAL_URL.match(url):
        return "local"
    m = STAGES.search(re.sub(r"^https?://", "", url).split("/")[0])
    return m.group(1).lower() if m else "CONFIRM"


def addresses_table(root: Path) -> list[tuple[str, str, str]]:
    """(service, environment, url) from the ## Addresses table of the instructions file."""
    proj = project.find(root)
    _, _, addresses = services.read(proj.instructions)
    return [(name, env, url) for name, by_env in addresses.items() for env, url in by_env.items()]


def answers(url: str) -> bool:
    import urllib.request
    try:
        urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=3)
        return True
    except Exception as err:  # an HTTP error page still means something answers there
        return hasattr(err, "code")


def candidate_apps(root: Path) -> None:
    """Best first: the ## Addresses table, then other docs (CLAUDE.md, README, ...); each with its service
    and environment, where it was found and whether it answers."""
    proj = project.find(root)
    seen, out = set(), []
    for name, env, url in addresses_table(root):
        out.append((url, name, env, f"{proj.rel(proj.instructions)} ## Addresses"))
    local, hosted, sources, _ = find_urls(root)
    for url, _ in hosted.most_common(5) + local.most_common(5):
        out.append((url, "", guess_env(url) + "?", ", ".join(sorted(sources[url])[:3])))
    print("# Candidate app addresses for this run, best first: url, service, environment (? = a guess),")
    print("# state, where found. Ask the user only when the request and these do not settle it.")
    if not out:
        print("# none found: ask the user, or make a video with no app (code and terminal scenes only)")
    for url, name, env, where in out:
        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        state = "answers now" if answers(url) else "not answering"
        print(f"{url}\t{name or '-'}\t{env}\t{state}\tfound in: {where}")


def project_name(root: Path) -> str:
    for readme in sorted(root.glob("[Rr][Ee][Aa][Dd][Mm][Ee]*")):
        heading = re.search(r"^#\s+(.{3,60}?)\s*#*$", read(readme), re.M)
        if heading:
            return re.sub(r"[`*_\[\]]", "", heading.group(1)).strip()
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            name = json.loads(read(pkg)).get("name", "")
            if name and not name.startswith("@"):
                return name.replace("-", " ").title()
        except ValueError:
            pass
    return root.resolve().name.replace("-", " ").replace("_", " ").title()


def line(text: str, comment: str = "") -> None:
    print(f"{text:<37} # {comment}" if comment else text)


def scalar(value: str) -> str:
    """A YAML value: quoted when a colon, a hash or a leading symbol would change its meaning."""
    return json.dumps(value) if re.search(r":\s|\s#|^[\W_]", value) else value


def main() -> None:
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != "--apps"):
        sys.exit("usage: python3 detect.py <project-root> [--apps]")
    root = Path(sys.argv[1]).resolve()
    if not root.is_dir():
        sys.exit(f"no such folder: {root}")
    if len(sys.argv) == 3:
        candidate_apps(root)
        return
    repos, docs = find_repos(root), find_docs(root)
    local, hosted, sources, secrets = find_urls(root)

    print("# Draft .kt-studio/config.yml from detect.py. Lines marked CONFIRM are guesses: ask the user.")
    line(f"project: {scalar(project_name(root))}", "CONFIRM the name shown on title screens")
    print()
    print("metadata: {}")
    print()
    print("repos:")
    if not repos:
        line("  []", "CONFIRM: no git repo found; the code tour needs one")
    for repo in repos:
        note = "" if repo["remote"] else "  (no remote: a local branch)"
        if repo.get("inside"):
            note += f"  (a folder of the git repo at {repo['inside']})"
        print(f"  - key: {repo['key']}")
        print(f"    path: {repo['path']}")
        print(f"    label: {repo['key'].replace('-', ' ').title()}")
        line(f"    ref: {repo['ref']}", f"CONFIRM the branch the tour reads{note}")
    print()
    print("knowledge:")
    print("\n".join(f"  - {d}" for d in docs) if docs else "  []")
    print()
    print("voice:")
    print("  engine: kokoro")
    line("  name: af_heart", "CONFIRM: af_heart (US female), am_michael (US male), bf_emma (UK female)")
    print("  speed: 0.9")
    print("  word_timing: estimate")
    print("  pronounce: {}")
    print()
    line("review: artifact", "CONFIRM: artifact (comment on a Claude artifact) or local (open the HTML file, comment in the chat)")
    print()
    print("language: simple English")
    # The services and where they run go in instructions.md, where the person keeps them up to date and
    # each run reads them first.
    print()
    print('# ---- Draft tables for .kt-studio/instructions.md. CONFIRM each row with the user; fill the blanks from the docs ----')
    print("## Services")
    print()
    print("| Service | What it is for | Talks to | Login |")
    print("| --- | --- | --- | --- |")
    apps = [u for u, _ in local.most_common(3)] + [u for u, _ in hosted.most_common(3)]
    if not apps:
        print("| (none found: a CLI, a library or a worker has no app to show) | | | |")
    for url in apps:
        print(f"| CONFIRM name of the app at {url} | CONFIRM | CONFIRM | CONFIRM: none, or how people log in |")
    print()
    print("## Addresses")
    print()
    envs = list(dict.fromkeys(guess_env(u) for u in apps))
    print("| Service | " + " | ".join(envs) + " |" if envs else "| Service |")
    print("| --- | " + " | ".join("---" for _ in envs) + " |" if envs else "| --- |")
    for url in apps:
        where = ", ".join(sorted(sources[url])[:2])
        cells = [url if guess_env(url) == env else "" for env in envs]
        print(f"| CONFIRM name (found in {where}) | " + " | ".join(cells) + " |")

if __name__ == "__main__":
    main()
