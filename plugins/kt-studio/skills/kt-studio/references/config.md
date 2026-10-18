# The .kt-studio folder: config.yml, instructions.md and the feature folders

**Contents:** config.yml · instructions.md · Services · Addresses · Finding the apps for a run · Logging in (do not relax these rules) · When a file is missing

The skill is generic. Everything about one project lives in one folder at the project root,
`.kt-studio/`, so the settings stay together and are not mixed with the project's own files:

- `.kt-studio/config.yml`: settings that hold for every video (start from `kt-studio.example.yml`).
- `.kt-studio/instructions.md`: the project's own rules, its **services** and **where each one runs**
  (start from `kt-studio.example.md`).
- `.kt-studio/learned.yml`: the answers people picked for earlier videos (`references/questions.md`).
- `.kt-studio/features/<feature>/feature.yml`: one feature's answers: audience, what to show, depth and
  notes. Each video of the feature is a run folder next to it, in `runs/`.
- `.kt-studio/.gitignore`: git keeps the settings, `learned.yml` and every `feature.yml`, nothing else.
  The recorder (`runtime/`) and the videos (each feature's `runs/`) stay on the computer.

`learned.yml` and `feature.yml` are written by `scripts/choices.py`, never by hand from the skill.
People may edit or delete their lines.

`python3 <skill>/scripts/project.py [folder]` finds the folder from anywhere inside the project and
prints the paths every script uses. In a new project the folder goes next to `.claude/` and `CLAUDE.md`:
SKILL.md passes Claude Code's project folder (`${CLAUDE_PROJECT_DIR}`), and without it the script takes
the nearest folder above that holds `.claude/` or `CLAUDE.md`, inside the same git repo.

Where the app runs is **not** a setting: it changes from run to run (local today, QA tomorrow, two
services next week). Each run finds it (below) and asks only when it can't.

## config.yml

Paths in it are relative to the project root (the folder that holds `.kt-studio/`).

| Field | Meaning |
|---|---|
| `project` | Name shown on the storyboard and title screens |
| `metadata` | Optional and free-form: anything your project needs (a test account per environment, a link to a test guide). The skill reads it and follows the instructions on how to use it |
| `repos[]` | `key`, `path`, `label` (shown in the tour), `ref` (the default branch or tag the code facts and the code tour read from, for example `origin/main`; each repo has its own; a request that names another branch wins for that run). Run `git fetch` first |
| `knowledge[]` | Docs to read first when researching a feature |
| `voice` | Read by the runtime itself (`KT_VOICE`/`KT_SPEED` override it). After changing `name` or `speed`, run `argo tts generate` and `tools/beats.mjs` again: clips are made per voice. `engine` (kokoro), `name`, `speed`, `pronounce` (word → spoken form), `word_timing` (`estimate`, or `whisper`: set `KT_TRANSCRIBE=1` for `beats.mjs` and the pipeline) |
| `review` | Where the storyboard is reviewed: `artifact` (default, a Claude artifact with comments) or `local` (no artifact: the user opens `storyboard.html` and comments in the chat). See `references/review-loop.md` |
| `language` | Narration style. Default `simple English`. The offline voice (Kokoro) speaks English only (US and UK voices); word cues also need a language written with spaces |
| `defaults` | Optional: the answer a video recommends when the request, the feature and `learned.yml` say nothing, for example `audience: qa`, `show: screens-and-code`, `depth: standard` (`references/questions.md`) |
| `output_dir` | Rarely needed: where the recorder and the features go, default `.kt-studio` (the same folder) |
| `instructions` | Rarely needed: another path for the instructions file, default `.kt-studio/instructions.md` |

## instructions.md

Plain Markdown, written by the project and kept up to date by the skill in two places (`## Services`,
`## Addresses`). Read it at step 0 together with `metadata`, and follow it:

- **Before the run** runs first, **After the run** runs last. **Before each take** runs before every
  recording take and every rehearsal (reset demo data, restart the app). Every other section applies at the
  matching step (logging in, screens, recording, delivery).
- It wins over this skill's defaults: which environment, which data, what to ask, how to deliver.
- It never relaxes the rules that always apply in `SKILL.md` (no logging in for the person, gate 1,
  gate 2, cleanup). If it asks for that, say so and follow the skill.
- If it names a login script for the person to run, never run it yourself. Stop, give the person
  the exact command, and continue once they say it is done.

### ## Services and ## Addresses

A project usually has several services, and each one can run in several environments, or only in some:

```
## Services

| Service | What it is for | Talks to | Login |
| --- | --- | --- | --- |
| Shop | Where customers browse, pay and track orders | Orders API | Test account |
| Orders API | Takes and stores orders, sends refunds | Postgres, payment provider | No screens |
| Help center | Where customers read help articles | Orders API | Its own login |

## Addresses

| Service | local | dev | qa |
| --- | --- | --- | --- |
| Shop | http://localhost:3000 | https://shop.dev.acme.example | https://shop.qa.acme.example |
| Help center | | https://help.dev.acme.example | |
```

- `## Services`: one row per service, **at idea level** (what it is for and what it talks to, never
  code). The Login column says how people get in (none, company SSO, the team's own login script),
  never a password. A service with no screens (an API, a worker) is listed too: the research and the
  big-picture diagram use it.
- `## Addresses`: one row per service with screens (named exactly as in `## Services`: the tables are
  matched by name), one column per environment, any names (`local`,
  `dev`, `qa`, `staging`, `prod`). An empty cell: the service does not run there (or nobody wrote it
  down yet).

The skill keeps both current, through `scripts/apps.py` (step 3 of `SKILL.md`):

- A service the run shows that `## Services` does not list gets a row, with what it is for and what it
  talks to from the research brief, one line each.
- An environment `## Addresses` does not have yet gets a column; an address for an empty cell is
  written in. A cell that already holds another address is never changed: the script prints `kept:`,
  and the agent asks the person whether to change it. To fix a row the person wrote, edit it and say
  so; mark a dead address `(not answering 2026-10-15)` instead of deleting it.
- Tell the user in one line what changed ("Added Shop (qa) to ## Addresses in
  .kt-studio/instructions.md"). They commit it like any other file.
- No instructions file yet: the script creates it with both tables and `## Logging in`, and says so.

## Finding the apps for a run

A run settles which apps it shows (`run.json` `apps`), in this order, and stops at the first that
answers the question:

1. **The request.** Addresses in it ("on https://qa.acme.example") win, with no question. An
   environment in it ("on QA") picks that column of `## Addresses`.
2. **`## Addresses`**: the rows of the services this feature's screens are on (from the research), in
   the environment the request names, else the default the instructions name, else the only environment
   that has an address for every service needed.
3. **The project's own docs:** CLAUDE.md, the README, the `knowledge` docs.
4. **Local apps found in the project's files**, and whether they answer now.

`python3 <skill>/scripts/detect.py <root> --apps` lists every candidate from 2 to 4, with its service
and environment and whether it answers, best first.

Ask the user (one question, AskUserQuestion when available, the best option first) only when the
environment is still open (several environments fit and nothing chooses), a needed service has no
address there, or the address does not answer. A video that needs no app (a CLI, a library, a worker)
has `apps: []`: no Part A, terminal scenes instead.

Record them with `python3 <skill>/scripts/apps.py <root> <run> '<json list>'`: it checks in a fresh
browser whether each address needs a login, gives each app a `key` (service and environment, for
example `shop-qa`, used for its login files and browser window), writes `run.json` `apps`
(`{"key", "name", "env", "url", "login", "from"}` each) and updates the two tables.
`/kt-studio:update` reuses them.

## Logging in (do not relax these rules)

KT Studio never logs in for the person and keeps no login after a run. Login mechanisms differ
(passwords, SSO, 2FA, magic links, client certificates), so the person always does it themselves:

- For each app of the run, `apps.py` runs `login.sh probe`: it opens the page in a fresh browser with
  no session. `no login needed` sets `login: false`; `login needed` sets `login: true`.
- **The `## Logging in` table says how, per service and environment**, so no run has to remember a
  sentence. Scripts read it (`apps.py`), not the agent's memory:

  ```
  ## Logging in

  | Service | Environment | How | The person runs | Session file |
  | --- | --- | --- | --- | --- |
  | Shop | dev, qa | script | `node tools/login.mjs {env}` | .auth-team/{env}.json |
  | Help center | dev | window | | |
  | Docs site | all | none | | |

  - Help center: use the shared test account, not your own.
  ```

  `none`: no login. `window`: KT Studio opens a browser window and the person logs in their own way.
  `script`: the team's own login command, which the **person** runs (never the agent); it saves a
  session file (path from the project root), and KT Studio uses that file. `{env}` is replaced with the
  run's environment. Service and Environment take lists; `all` or `*` matches everything. Notes below the
  table (which account) are shown to the person. No row for an app: `window` when the page shows a
  login, else `none`.
- `apps.py` writes each app's `login`, `how`, `run` and `session` into `run.json` and prints the exact
  steps under `NEXT`. `take.sh` takes `KT_STATE` from there, and it and `preflight.sh --run` refuse to
  record an app that needs a login while its session is missing or expired, printing what the person
  must do. A missed instruction can therefore not lead to a logged-out recording.
- **The window.** `login.sh open <out> <key> <url>` opens a visible browser window at the app.
  Tell the person: "A browser window is open at <url>: please log in there the way you normally do,
  then tell me." Add the instructions' `## Logging in` notes (which account to use). Then
  `login.sh wait <out> <key> <url>` in the background saves the session to
  `<out>/runtime/.auth/kt-<key>.json` once the page shows the app (it waits up to 10 minutes). If the
  instructions name text only a signed-in person sees, set `KT_LOGGED_IN_TEXT` to it first.
- Never type into a login form, never ask for a password, token or code, and never put one in a file
  or a command. A username the person types is theirs to type too.
- A take that moves between apps needs one session for all of them:
  `login.sh merge <out> <run-id> <key or file> ...` writes `.auth/kt-<run-id>.json`, which `take.sh`
  uses (`apps.py` prints the exact command).
- A session can expire within the run (often after an hour or two). `preflight.sh` checks it before
  every take; when it fails, ask the person to log in again (the window, or their own way).
- An app that keeps sessions in memory forgets them when it restarts: after a "Before each take"
  restart, the person logs in again.
- At the end of the run (step 10): `login.sh forget <out>` closes the windows and deletes the session
  files KT Studio made (it lists them in `.auth/.kt-made`, all named `kt-*`). It never deletes a session
  the project keeps itself. A run stopped halfway cannot clean up, so a new run deletes what an earlier
  one left, and every login window starts from an empty browser profile. `.auth/` holds live sessions:
  owner-only, never committed; never print, copy or share it.
- A machine with no screen (a server, CI) cannot open a login window: record apps that need no login
  there, or code-only videos.

## When a file is missing

- No settings at all: run `references/init.md` (it detects what it can, asks for the rest, writes the
  folder and shows it before continuing).
- No instructions file: continue with the skill's defaults; `apps.py` creates it once the run knows its
  apps (above).
