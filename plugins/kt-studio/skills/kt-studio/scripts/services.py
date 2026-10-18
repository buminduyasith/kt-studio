#!/usr/bin/env python3
"""Reads and updates the two tables in a project's instructions.md that say what the services are and
where they run.

    ## Services                      what each service is for, at idea level (no code)
    | Service | What it is for | Talks to | Login |

    ## Addresses                     where each service runs: one column per environment
    | Service | local | dev | qa |

A project can have many services, and each one can run in several environments (or only some of
them): a cell is empty where a service does not run. The person writes these tables; a run adds what
it learns (a new service, a new environment, an address for an empty cell) and never changes or
deletes what is there.

Usage: python3 services.py <instructions.md>     prints the services and their addresses
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SERVICES_HEADER = ["Service", "What it is for", "Talks to", "Login"]
NEW_FILE = """# KT Studio: project instructions

## Services

What each service is for and what it talks to, in plain words (no code).

| Service | What it is for | Talks to | Login |
| --- | --- | --- | --- |

## Addresses

Where each service runs. One column per environment; leave a cell empty where a service does not run.

| Service |
| --- |

## Logging in

How people log in to each service in each environment: none, window (KT Studio opens a browser window
and you log in your usual way) or script (your team's own login command: you run it, KT Studio uses the
session file it saves). KT Studio never logs in for you.

| Service | Environment | How | The person runs | Session file |
| --- | --- | --- | --- | --- |
"""


def cell(text) -> str:
    return " ".join(str(text or "").split()).replace("|", "/")


def norm(text: str) -> str:
    return " ".join(str(text or "").split()).lower().rstrip("/")


def same_service(a: str, b: str) -> bool:
    """Service names match without case, backticks or a note in brackets: "Loans API (`api/`)" = "loans api"."""
    key = lambda t: norm(re.sub(r"\([^)]*\)|`", "", t or ""))
    return key(a) == key(b)


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c) and any(cells)


class Table:
    """The first Markdown table of one `## <title>` section, kept with its place in the text."""

    def __init__(self, text: str, title: str):
        self.title = title
        sec = re.search(rf"^##[ \t]+{title}\b[^\n]*\n", text, re.M | re.I)
        self.found = bool(sec)
        self.header: list[str] = []
        self.rows: list[list[str]] = []
        self.span = (0, 0)  # where the table's text is (start, end), or the end of the heading
        if not sec:
            return
        nxt = re.search(r"^#{1,2}[ \t]", text[sec.end():], re.M)
        end = sec.end() + (nxt.start() if nxt else len(text) - sec.end())
        lines = text[sec.end():end].split("\n")
        pos = sec.end()
        start = None
        for line in lines:
            if line.strip().startswith("|"):
                if start is None:
                    start = pos
                cells = split_row(line)
                if not self.header:
                    self.header = cells
                elif not is_separator(cells):
                    self.rows.append(cells + [""] * (len(self.header) - len(cells)))
                self.span = (start, pos + len(line))
            elif start is not None:
                break
            pos += len(line) + 1
        if start is None:
            self.span = (sec.end(), sec.end())

    def render(self) -> str:
        out = ["| " + " | ".join(self.header) + " |", "| " + " | ".join("---" for _ in self.header) + " |"]
        out += ["| " + " | ".join((r + [""] * len(self.header))[: len(self.header)]) + " |" for r in self.rows]
        return "\n".join(out)

    def row(self, service: str) -> list[str] | None:
        return next((r for r in self.rows if same_service(r[0], service)), None)


def read(path: Path) -> tuple[list[dict], list[str], dict[str, dict[str, str]]]:
    """(services, environments, addresses[service][environment] = url) from the instructions file."""
    text = path.read_text(errors="ignore") if path.is_file() else ""
    services = []
    t = Table(text, "Services")
    for r in t.rows:
        if r and r[0]:
            services.append(dict(zip(["name", "for", "talks", "login"], r + [""] * 4)))
    a = Table(text, "Addresses")
    envs = a.header[1:]
    addresses: dict[str, dict[str, str]] = {}
    for r in a.rows:
        if r and r[0]:
            addresses[r[0]] = {env: url for env, url in zip(envs, r[1:]) if re.match(r"https?://", url)}
    return services, envs, addresses


LOGIN_HOWS = ("none", "window", "script")


def logins(path: Path) -> list[dict]:
    """Rows of the "## Logging in" table: how people log in to each service in each environment.

        | Service | Environment | How | The person runs | Session file |
        | Shop | dev, qa | script | `node tools/login.mjs {env}` | .auth-team/{env}.json |
        | Help center | dev | window | | |

    How: none (no login), window (KT Studio opens a browser window and the person logs in there) or
    script (the person runs the team's own command, which saves a session file; KT Studio uses that file
    and never runs the command). Service: one or more, comma-separated, or * for all. Environment: a
    list, or empty / all / * for every environment. {env}
    in the command or the file is replaced with the run's environment."""
    text = path.read_text(errors="ignore") if path.is_file() else ""
    t = Table(text, "Logging in")
    head = [norm(h) for h in t.header]

    def col(*words):
        return next((i for i, h in enumerate(head) if any(w in h for w in words)), None)

    i_srv, i_env, i_how = col("service"), col("environment", "env"), col("how")
    i_run, i_ses = col("runs", "command", "script"), col("session")
    if i_srv is None or i_how is None:
        return []
    rows = []
    for r in t.rows:
        get = lambda i: r[i].strip().strip("`").strip() if i is not None and i < len(r) else ""
        how = get(i_how).lower()
        if not get(i_srv) or how not in LOGIN_HOWS:
            continue
        envs = [e.strip().lower() for e in re.split(r"[,/]", get(i_env)) if e.strip()]
        rows.append({"service": get(i_srv), "envs": [] if not envs or envs[0] in ("all", "*", "any") else envs,
                     "how": how, "run": get(i_run), "session": get(i_ses)})
    return rows


def login_for(path: Path, service: str, env: str) -> dict | None:
    """The ## Logging in row for this service in this environment, or None."""
    for row in logins(path):
        names = [n.strip() for n in row["service"].split(",") if n.strip()]
        if (any(same_service(n, service) for n in names) or row["service"].lower() in ("*", "all")) \
                and (not row["envs"] or norm(env) in row["envs"]):
            return row
    return None


def update(path: Path, apps: list[dict], label: str) -> list[str]:
    """Adds what these apps teach: a Services row per new service, an Addresses column per new
    environment, an address per empty cell. Returns one line per change (and per address it kept)."""
    said = []
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(NEW_FILE)
        said.append(f"created {label} with ## Services and ## Addresses")
    text = path.read_text()
    for title, header in (("Services", SERVICES_HEADER), ("Addresses", ["Service"])):
        if not Table(text, title).found:
            block = f"## {title}\n\n| " + " | ".join(header) + " |\n| " + " | ".join("---" for _ in header) + " |\n\n"
            if title == "Addresses" and Table(text, "Services").found:
                sec = re.search(r"^##[ \t]+Services\b[^\n]*\n", text, re.M | re.I)
                nxt = re.search(r"^#{1,2}[ \t]", text[sec.end():], re.M)
                at = sec.end() + nxt.start() if nxt else len(text)
                text = text[:at].rstrip("\n") + "\n\n" + block + text[at:]
            else:
                title_line = re.search(r"^# .*\n", text, re.M)
                at = title_line.end() if title_line else 0
                text = text[:at] + "\n" + block + text[at:].lstrip("\n")
            said.append(f"added a ## {title} section to {label}")

    services = Table(text, "Services")
    if not services.header:
        services.header = list(SERVICES_HEADER)
    added = False
    for app in apps:
        if services.row(app["name"]) is None:
            added = True
            login = app.get("login_note") or ("Log in in the window KT Studio opens" if app.get("login") else "None")
            services.rows.append([cell(app["name"]), cell(app.get("for")) or "TODO: what it is for",
                                  cell(app.get("talks")), cell(login)][: max(len(services.header), 4)])
            said.append(f"added to ## Services in {label}: {app['name']}")
    if added:
        text = replace(text, services)

    addresses = Table(text, "Addresses")
    if not addresses.header:
        addresses.header = ["Service"]
    changed = False
    for app in apps:
        url, env = (app.get("url") or "").strip(), cell(app.get("env"))
        if not url or not env:
            continue
        envs = [norm(h) for h in addresses.header]
        if norm(env) not in envs:
            addresses.header.append(env)
            for r in addresses.rows:
                r.append("")
            envs.append(norm(env))
            said.append(f"added the environment {env} to ## Addresses in {label}")
            changed = True
        col = envs.index(norm(env))
        r = addresses.row(app["name"])
        if r is None:
            r = [cell(app["name"])] + [""] * (len(addresses.header) - 1)
            addresses.rows.append(r)
        r += [""] * (len(addresses.header) - len(r))
        if not r[col]:
            r[col] = url
            said.append(f"added to ## Addresses in {label}: {app['name']} ({env}) {url}")
            changed = True
        elif norm(r[col]) != norm(url):
            said.append(f"kept: ## Addresses says {r[col]} for {app['name']} ({env}); this run uses {url}. "
                        "Ask the person whether to change the table")
        else:
            said.append(f"already listed: {app['name']} ({env}) {url}")
    if changed:
        text = replace(text, addresses)
    path.write_text(text)
    return said


def replace(text: str, table: Table) -> str:
    start, end = table.span
    if start == end:  # a section with no table yet: put it right under the heading
        return text[:start] + "\n" + table.render() + "\n" + text[start:]
    return text[:start] + table.render() + text[end:]


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python3 services.py <instructions.md>")
    services, envs, addresses = read(Path(sys.argv[1]))
    for s in services:
        mine = next((v for k, v in addresses.items() if same_service(k, s["name"])), {})
        where = ", ".join(f"{env} {url}" for env, url in mine.items()) or "no address"
        print(f"{s['name']}: {s['for']} | talks to: {s['talks'] or '-'} | login: {s['login'] or '-'} | {where}")
    for name in addresses:
        if not any(same_service(s["name"], name) for s in services):
            print(f"{name}: (not in ## Services) | " + ", ".join(f"{e} {u}" for e, u in addresses[name].items()))
    print("environments: " + (", ".join(envs) or "none yet"))


if __name__ == "__main__":
    main()
