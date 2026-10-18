#!/usr/bin/env python3
"""The questions a video asks, with the best answer first, and what the answers teach the next video.

Every feature has a folder, `.kt-studio/features/<feature>/`, and its answers in `feature.yml` there.
The project keeps `.kt-studio/learned.yml`: the answers people picked for earlier videos, newest last.
Both files are committed, so the whole team shares them, and both are written only by this script.

An answer is settled (no question) when, in this order:
  1. the request says it ("for testers", "on QA", "code only")              from: request
  2. the feature's feature.yml has it (an earlier video of this feature)    from: feature
  3. the instructions name it (the default environment under ## Before the run)  from: instructions
  4. there is only one choice (one environment in ## Addresses)             from: only one
     or none: ## Addresses has no address at all, so the video shows code     from: no app
  5. the same answer was picked 3 times in a row in learned.yml              from: learned
The environment is never settled by 2 or 5: where the app runs changes from video to video, so an earlier
answer only moves to the top of the question. The depth is never settled by 5: it follows each feature's
size, so another feature's answers say nothing about it.
Anything else becomes a question for AskUserQuestion, with the recommended answer first: the research's
suggestion, else this feature's last answer, else the answer picked most often in learned.yml, else
`defaults:` in config.yml, else the built-in default.

Usage:
  python3 choices.py ask <root> <feature> [--keys audience,show,environment] [--given '<json>'] [--suggest '<json>']
      Prints JSON: "use" (settled answers and where each came from), "ask" (the questions, at most 4,
      each option with its "value"), and "say" (one line telling the person what was settled).
      --given: what the request says, as values ({"audience": "qa"}). --suggest: the research's best
      guess, used only to order the options ({"depth": "deep-dive"}).
  python3 choices.py record <root> <feature> --answers '<json>' [--learn key,key] [--note '<text>']...
                            [--run <run-folder>] [--title '<title>']
      Saves the answers in feature.yml (and in the run's run.json `choices` with --run). Only the keys in
      --learn are added to learned.yml: the ones the person answered or the request said, never the
      ones settled from feature.yml or learned.yml. A --note is kept in feature.yml under `notes`.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import project  # noqa: E402
import services  # noqa: E402

SETTLE = 3     # the same answer this many times in a row: stop asking
HISTORY = 10   # answers kept per question in learned.yml
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Each option: (value, label, description). Labels are what the person sees; values are what is stored.
KEYS: dict[str, dict] = {
    "audience": {
        "header": "Audience",
        "question": "Who is this video for?",
        "default": "developer",
        "options": [
            ("developer", "Developer new to the area", "A short look at the screens, then most of the time on the code: how to change it safely"),
            ("qa", "QA or tester", "Every flow, rule and error message, with test data; very little code"),
            ("product", "Scrum master or product owner", "The flows and why they exist; one diagram at most, no code"),
            ("support", "Support or operations", "The flows, what failure looks like, and the logs and settings that help"),
        ],
    },
    "show": {
        "header": "Show",
        "question": "What should the video show?",
        "default": "screens-and-code",
        "options": [
            ("screens-and-code", "Screens and code", "Part A on the real app, then Part B, the code tour"),
            ("screens", "Screens only", "Only Part A: how to use the feature"),
            ("code", "Code only", "Only Part B: the code tour (terminal scenes for a project with no screens)"),
        ],
    },
    "environment": {
        "header": "Environment",
        "question": "Which environment should the screens come from?",
        "options": [],  # from ## Addresses
    },
    "depth": {
        "header": "Depth",
        "question": "How deep should the video go?",
        "default": "standard",
        "options": [
            ("overview", "Overview", "2 to 4 minutes: the main flow and the one rule that matters"),
            ("standard", "Standard", "5 to 10 minutes: the main flow step by step, each key rule where it lives"),
            ("deep-dive", "Deep dive", "8 to 12 minutes: every hop, the failure paths, the data and its states"),
        ],
    },
}
ROUND_ONE = ["audience", "show", "environment"]
WHY = {"request": "you asked for it", "feature": "this feature's last video", "instructions": "your instructions",
       "only one": "the only one", "no app": "no app in ## Addresses", "learned": f"picked {SETTLE} times in a row"}


# ---- the two files: flat "key: value" lines and "key:" with "  - item" lists, no YAML library needed

def read_yml(path: Path) -> dict:
    data: dict = {}
    current = None
    if not path.is_file():
        return data
    for line in path.read_text(errors="ignore").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s*(.*)$", line)
        if item and current is not None:
            data[current].append(unquote(item.group(1)))
            continue
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2)
        if not value.startswith('"'):
            value = re.sub(r"\s+#.*$", "", value).strip()
        if value == "":
            data[key], current = [], key
        else:
            data[key], current = unquote(value), None
    return data


def unquote(value: str) -> str:
    value = value.strip()
    if value.startswith('"'):
        try:
            return json.loads(value)
        except ValueError:
            return value.strip('"')
    return value.strip("'")


def quote(value) -> str:
    text = str(value)
    plain = re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.,/()+-]*", text) and not text.endswith(" ")
    return text if plain else json.dumps(text, ensure_ascii=False)


def write_yml(path: Path, header: str, data: dict) -> None:
    out = [header.rstrip()]
    for key, value in data.items():
        if isinstance(value, list):
            if value:
                out.append(f"{key}:")
                out += [f"  - {quote(v)}" for v in value]
        elif value not in (None, ""):
            out.append(f"{key}: {quote(value)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n")


FEATURE_HEADER = """# This feature's answers for KT Studio videos: who they are for, what they show, where the screens
# come from. Every video of this feature reads it and asks only what it does not say.
# Written by KT Studio (choices.py); edit a value freely. Commit it with the rest of .kt-studio/."""
LEARNED_HEADER = """# What KT Studio learned from the answers people picked for earlier videos, newest last.
# It recommends the answer picked most often, and stops asking once the same answer was picked
# 3 times in a row. Delete an answer to make it ask again. Written by KT Studio (choices.py)."""
FEATURE_ORDER = ["feature", "title", "audience", "show", "environment", "depth", "language"]


# ---- what the project already says

def config_defaults(proj: project.Project) -> dict:
    """The `defaults:` block of config.yml, if the person wrote one (audience: qa, ...)."""
    text = proj.config.read_text(errors="ignore") if proj.config.is_file() else ""
    m = re.search(r"^defaults:[ \t]*\n((?:[ \t]+.*\n?)*)", text, re.M)
    if not m:
        return {}
    found = re.findall(r"^[ \t]+([A-Za-z0-9_-]+):[ \t]*([^#\n]*)", m.group(1), re.M)
    return {k: unquote(v) for k, v in found if v.strip()}


def environments(proj: project.Project) -> tuple[list[str], str, bool]:
    """(the environment columns of ## Addresses, the default the instructions name under ## Before the run,
    whether ## Addresses has any address at all)."""
    _, envs, addresses = services.read(proj.instructions)
    envs = [e for e in envs if e]
    has_app = any(addresses.values())
    text = proj.instructions.read_text(errors="ignore") if proj.instructions.is_file() else ""
    sec = re.search(r"^##[ \t]+Before the run\b[^\n]*\n(.*?)(?=^#{1,2}[ \t]|\Z)", text, re.M | re.S)
    default = ""
    for line in (sec.group(1) if sec else "").splitlines():
        low = line.lower()
        if re.search(r"\b(use|default)\b", low):
            hit = next((e for e in envs if re.search(rf"(?<![\w-]){re.escape(e.lower())}(?![\w-])", low)), "")
            if hit:
                default = hit
                break
    return envs, default, has_app


def streak(history: list[str]) -> str:
    """The answer picked SETTLE times in a row, most recently, or ''."""
    last = history[-SETTLE:]
    return last[0] if len(last) == SETTLE and len(set(last)) == 1 else ""


def most_picked(history: list[str]) -> str:
    if not history:
        return ""
    counts = Counter(history)
    best = max(counts.values())
    return next(v for v in reversed(history) if counts[v] == best)  # a tie goes to the newest


def options_for(key: str, envs: list[str]) -> list[tuple[str, str, str]]:
    if key == "environment":
        return [(e, e, f"The {e} column of ## Addresses") for e in envs]
    return KEYS[key]["options"]


def label_of(key: str, value: str, envs: list[str]) -> str:
    return next((label for v, label, _ in options_for(key, envs) if v == value), value)


def to_value(key: str, answer: str, envs: list[str]) -> str:
    """An answer may come back as a label ("QA or tester (Recommended)"); store its value ("qa")."""
    text = re.sub(r"\s*\(Recommended\)\s*$", "", str(answer)).strip()
    if key not in KEYS:
        return text
    for value, label, _ in options_for(key, envs):
        if text.lower() in (value.lower(), label.lower()):
            return value
    return text  # "Other": the person's own words, kept as they wrote them


# ---- ask and record

def ask(proj: project.Project, feature: str, keys: list[str], given: dict, suggest: dict) -> dict:
    saved = read_yml(proj.feature(feature) / "feature.yml")
    learned = read_yml(proj.learned)
    defaults = config_defaults(proj)
    envs, env_default, has_app = environments(proj)
    use: dict[str, dict] = {}
    questions = []

    def settle(key: str, value: str, source: str) -> None:
        use[key] = {"value": value, "label": label_of(key, value, envs), "from": source}

    for key in keys:
        if key not in KEYS:
            raise SystemExit(f"unknown question: {key} (known: {', '.join(KEYS)})")
        history = learned.get(key) if isinstance(learned.get(key), list) else []
        if key in given and str(given[key]).strip():
            settle(key, to_value(key, given[key], envs), "request")
            continue
        last = saved.get(key) if isinstance(saved.get(key), str) else ""
        if last and key != "environment":
            settle(key, last, "feature")
            continue
        if key == "show" and not has_app:
            settle(key, "code", "no app")
            continue
        if key == "environment":
            show = use.get("show", {}).get("value") or (saved.get("show") if isinstance(saved.get("show"), str) else "")
            if show == "code" or not has_app:
                continue  # no screens, or no ## Addresses yet: step 3 of the skill finds the apps
            if env_default:
                settle(key, env_default, "instructions")
                continue
            if len(envs) == 1:
                settle(key, envs[0], "only one")
                continue
        if streak(history) and key not in ("environment", "depth"):
            settle(key, streak(history), "learned")
            continue
        opts = options_for(key, envs)
        values = [v for v, _, _ in opts]
        builtin = KEYS[key].get("default", "")
        pick = next((v for v in [suggest.get(key), last, most_picked(history), defaults.get(key), builtin]
                     if v and v in values), values[0] if values else "")
        ordered = sorted(opts, key=lambda o: o[0] != pick)[:4]
        questions.append({
            "key": key,
            "question": KEYS[key]["question"],
            "header": KEYS[key]["header"],
            "multiSelect": False,
            "options": [{"label": label + (" (Recommended)" if value == pick else ""), "value": value,
                         "description": desc} for value, label, desc in ordered],
        })

    say = ""
    if use:
        parts = [f"{KEYS[k]['header'].lower()}: {u['label']} ({WHY[u['from']]})" for k, u in use.items()]
        say = "Using " + "; ".join(parts) + ". Say if you want something else."
    return {"feature": feature, "use": use, "ask": questions[:4], "say": say}


def record(proj: project.Project, feature: str, answers: dict, learn: list[str], notes: list[str],
           run: Path | None, title: str) -> list[str]:
    envs = environments(proj)[0]
    folder = proj.feature(feature)
    path = folder / "feature.yml"
    data = read_yml(path)
    clean = {k: to_value(k, v, envs) for k, v in answers.items() if str(v).strip()}
    data["feature"] = feature
    if title:
        data["title"] = title
    data.update(clean)
    note_list = data.get("notes") if isinstance(data.get("notes"), list) else []
    note_list += [n for n in notes if n and n not in note_list]
    data["notes"] = note_list
    runs = data.get("runs") if isinstance(data.get("runs"), list) else []
    if run and run.name not in runs:
        runs.append(run.name)
    data["runs"] = runs
    data["updated"] = date.today().isoformat()
    ordered = {k: data[k] for k in FEATURE_ORDER if k in data}
    ordered.update({k: v for k, v in data.items() if k not in ordered and k not in ("notes", "runs", "updated")})
    ordered.update({"notes": data["notes"], "runs": data["runs"], "updated": data["updated"]})
    write_yml(path, FEATURE_HEADER, ordered)
    done = [f"saved {proj.rel(path)}: " + ", ".join(f"{k} {v}" for k, v in clean.items())]

    taught = {k: clean[k] for k in learn if k in clean}
    if taught:
        learned = read_yml(proj.learned)
        for k, v in taught.items():
            history = learned.get(k) if isinstance(learned.get(k), list) else []
            learned[k] = (history + [v])[-HISTORY:]
        write_yml(proj.learned, LEARNED_HEADER, learned)
        done.append(f"learned {proj.rel(proj.learned)}: " + ", ".join(f"{k} {v}" for k, v in taught.items()))

    if run:
        run_json = run / "run.json"
        info = json.loads(run_json.read_text()) if run_json.is_file() else {}
        info["choices"] = {**info.get("choices", {}), **clean, **({"notes": note_list} if note_list else {})}
        run_json.write_text(json.dumps(info, indent=2) + "\n")
        done.append(f"run.json choices: {', '.join(sorted(k for k in info['choices'] if k != 'notes'))}")
    project.write_gitignore(proj.out)
    return done


def option(args: list[str], name: str, many: bool = False):
    found = [args[i + 1] for i, a in enumerate(args[:-1]) if a == name]
    return found if many else (found[-1] if found else "")


def as_json(text: str, name: str) -> dict:
    if not text:
        return {}
    try:
        value = json.loads(text)
    except ValueError as e:
        raise SystemExit(f"{name} is not valid JSON: {e}")
    if not isinstance(value, dict):
        raise SystemExit(f"{name} must be a JSON object, for example {{\"audience\": \"qa\"}}")
    return value


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 3 or args[0] not in ("ask", "record"):
        raise SystemExit(__doc__.split("Usage:")[1])
    command, root, feature = args[0], args[1], args[2]
    if not SLUG.match(feature):
        raise SystemExit(f"feature must be lowercase letters, digits and dashes, for example order-refunds (got: {feature})")
    proj = project.find(root)
    rest = args[3:]
    if command == "ask":
        keys = [k.strip() for k in (option(rest, "--keys") or ",".join(ROUND_ONE)).split(",") if k.strip()]
        result = ask(proj, feature, keys, as_json(option(rest, "--given"), "--given"),
                     as_json(option(rest, "--suggest"), "--suggest"))
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        run = option(rest, "--run")
        learn = [k.strip() for k in option(rest, "--learn").split(",") if k.strip()]
        lines = record(proj, feature, as_json(option(rest, "--answers"), "--answers"), learn,
                       option(rest, "--note", many=True), Path(run) if run else None, option(rest, "--title"))
        print("\n".join(lines))


if __name__ == "__main__":
    main()
