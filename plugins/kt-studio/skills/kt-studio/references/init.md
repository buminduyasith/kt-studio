# init: set up a project for KT videos

**Contents:** 1. Check the computer · 2. What is there already · 3. Learn the project (no questions yet) · 4. Ask only what the files cannot tell · 5. Write the folder · 6. Install the recorder · 7. Prove it works, then say what is next

Run this for `/kt-studio:init` (or the request `init` / `setup`), or when the doctor reports an `[init]`
fix at the start of a run. It is safe to run again: it never changes existing settings without showing
the change and getting a yes.

The goal: after init, `/kt-studio:make <feature>` works with no setup questions, and nothing is ever
downloaded during a video. **Init is the only command that downloads** (the recorder, the voice, Chromium,
the Whisper model when `word_timing` is `whisper`); every other command refuses and points here.

Everything KT Studio keeps for a project is in one folder at the project root, `.kt-studio/`, next to
`.claude/` and `CLAUDE.md`. `python3 <skill>/scripts/project.py ${CLAUDE_PROJECT_DIR}` says where (in a
monorepo started from the top, ask once which part the videos are about when several folders have their
own `CLAUDE.md`). The settings and the answers in it are committed; the rest stays on the computer:

```
<root>/.kt-studio/
├── config.yml          repos and branches, docs to read first, voice, metadata
├── instructions.md     the project's rules, ## Services (what each one is for) and ## Addresses (where each runs)
├── learned.yml         the answers people picked for earlier videos (the first video writes it)
├── .gitignore          git keeps the settings, learned.yml and each feature.yml, nothing else
├── runtime/            the recorder (setup.sh)
└── features/           one folder per feature: its feature.yml and its videos (runs/)
```

## 1. Check the computer

```bash
bash <skill>/scripts/doctor.sh <root> --data <data>
```

- `[you]` fixes are tools the person installs (Node.js, Python, ffmpeg, git). playwright-cli is only
  needed when a page needs a login (it opens the window where the person logs in). Give the
  exact commands from the doctor, one per `bash` block, and wait. Install a system tool yourself only
  when the person asks you to.
- Leave `[init]` and `[setup]` fixes to the steps below.

## 2. What is there already

`python3 <skill>/scripts/project.py <root>` prints the layout:

- **`folder`** (`.kt-studio/config.yml` exists): the project is set up. Show both files in short, ask
  what to change (one question), change only that, then go to step 6. Nothing to change: go to step 6.
- **`none`**: a new project, steps 3 to 7.

## 3. Learn the project (no questions yet)

```bash
python3 <skill>/scripts/detect.py <root>
```

It prints a draft `config.yml` (the git repos with their default branches, the docs to read first, and
links to wikis and shared docs that the project's files mention, as comments) and
draft `## Services` and `## Addresses` tables: the app addresses found in the project's own files
(CLAUDE.md, README, compose files, launch configs, example env files), the environment each looks like
(`local`, or `dev` / `qa` from the host name) and where each was found. It never reads a real `.env`
file. Every guess is marked `CONFIRM`.

Also read CLAUDE.md, the README and the docs for the services: what each is for, what it talks to, how
it is started, and the addresses of shared environments (dev, QA, staging) if the docs name them. Fill
the tables from that, at idea level (one line each, no code).

## 4. Ask only what the files cannot tell

One short round of questions (use the AskUserQuestion tool when it is available), each with the draft's
guess as the first option:

1. **Services and where they run:** show the two drafted tables. A project often has several services,
   and each can run in several environments (local, dev, qa, ...), or only some of them. Anything wrong
   or missing? Which environment should a video use when the request does not say (the default)? No
   app to show (a CLI, a library, a worker): videos show the code and real terminal commands instead.
2. **The code tour:** which repos it may show, and the default branch for each.
3. **Where research reads, besides the code** (`knowledge:` in config.yml). Run
   `python3 <skill>/scripts/detect.py <root> --knowledge`: it lists the docs in the project and the
   links to wikis and shared docs that README, CLAUDE.md and the docs mention. Ask one question with
   `multiSelect: true`, at most 4 answers: the docs it found (one answer, recommended, naming them),
   the links it found (one answer per link, or one for all of them), and **Code only**. Say in the
   question that "Other" takes anything else, one per line:
   - a folder or file in the project (`docs/refunds/`, `specs/`);
   - a folder or file outside it (`~/notes/shop/`): it works only on computers that have it, and the
     doctor shows a tip where it is missing, so suggest copying it into the project when the team needs it;
   - a web link: research reads it with the web fetch tool and never logs in. A page that needs a login
     is skipped, so suggest saving it as a file in the project;
   - a wiki or drive the person reads through a tool connected in Claude Code: `connector: <what to read>`,
     written in quotes in config.yml, for example `- "connector: Help center space, Refunds pages"`.

   Write the picks under `knowledge:`, in the order they should be read; **Code only** is `knowledge: []`.
   Each video can still change this for itself (`references/questions.md`, the sources question).
4. **Voice:** `af_heart` (US female, default), `am_michael` (US male), `bf_emma` (UK female); speed 0.9.
5. **Anything the project needs every run** (which data or account to use, who to tell, how to deliver).
   This goes in `instructions.md`.

6. **Logging in**, only for services with screens: how do people log in, per environment? Draft the
   `## Logging in` table (`references/config.md`) from the docs: `none`, `window` (the default: KT Studio
   opens a window and the person logs in their own way), or `script` when the team has its own login
   command (the CLAUDE.md, a test guide or older instructions often name it), with the command the person
   runs and the session file it writes. KT Studio never logs in for the person and never runs that
   command. Never ask for a password, token or key, and never write one into a file.

## 5. Write the folder

- `<root>/.kt-studio/config.yml`: the draft plus the answers, in the format of
  `<skill>/kt-studio.example.yml` (every field is described in `references/config.md`). Drop the
  `CONFIRM` comments. No `output_dir` and no `instructions` (the defaults are right).
- `<root>/.kt-studio/instructions.md`: start from `<skill>/kt-studio.example.md`. Replace its example
  `## Services` and `## Addresses` with the confirmed ones (or one line saying there is no app; a
  service has exactly the same name in both tables, with no folder or note added to it), write
  the default environment under `## Before the run`, write the `## Logging in` table (with notes on
  which account to use below it), and fill the other sections
  with what the person said. Delete sections that stay empty.
- `python3 <skill>/scripts/project.py --gitignore <root>/.kt-studio` writes the `.gitignore`.
- Show both files. Suggest committing them (they hold no secrets).

## 6. Install the recorder

Skip when the doctor shows no `[init]` or `[setup]` fix about the recorder. Otherwise tell the person
first: the first install on a computer downloads up to 1 GB (about 500 MB of pinned packages and the
offline voice model, plus Chromium when this computer does not have it yet, plus about 150 MB for the
Whisper model when `voice.word_timing` is `whisper`) and takes 2 to 5 minutes. All of it is shared by
every project on this computer, so the next project takes seconds.

```bash
bash <skill>/scripts/setup.sh <out> <data>
```

`<data>` is the plugin's data folder (`SKILL.md`, "Names used below"). Setup links the project's
`.kt-studio/runtime/node_modules` to the copy there; a project that has its own copy (about 500 MB)
gets it deleted and linked too.

Use a 10-minute timeout and wait for `ready:` before going on; do not end the turn while it runs
(an install cut off halfway is caught by the doctor, and running setup again finishes it). This is the
only place `setup.sh` runs without `--no-download`.

## 7. Prove it works, then say what is next

```bash
bash <skill>/scripts/doctor.sh <root> --deep --data <data>
```

It starts Chromium and speaks a test sentence. It must end with `doctor: ready`. Then, for each address
in `## Addresses`: `curl -s -o /dev/null -w '%{http_code}\n' <url>`. Not reachable is fine for now (the
app may be stopped); say so. Do not log in now: logins are made per run and deleted when it ends.

A short summary in simple English:

| Item | What to say |
|---|---|
| Found | Repos and branches, docs, services and the environments each runs in |
| Written | `.kt-studio/config.yml` and `.kt-studio/instructions.md` (suggest committing both) |
| Installed | The recorder in `.kt-studio/runtime` (not committed), Chromium, the voice model |
| Next | `/kt-studio:make <feature> [instructions]`, for example `/kt-studio:make order-refunds "on QA, for testers, max 5 min"` |

Init makes no feature folder and asks nothing about videos: the first `/kt-studio:make <feature>` does,
and asks who the video is for, what to show and how deep (`references/questions.md`).
