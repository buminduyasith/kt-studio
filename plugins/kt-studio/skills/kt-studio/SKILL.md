---
name: make
description: "Makes a narrated knowledge-transfer (KT) video of one feature from the real code and the running app: researches the feature, writes a storyboard the user reviews and approves, then records real screens and a VS Code style code tour with an offline voice, subtitles and chapters. Use when the user asks for a KT, handover or onboarding video, a feature walkthrough for QA or a scrum master, a code tour video or a storyboard for one, or wants to set KT Studio up, check it, or change a delivered video. Reads the project's .kt-studio/ folder: config.yml (repos, branches, voice), instructions.md (the project's rules, its services and their addresses in each environment) and one folder per feature with its answers, asking only what they do not say. Commands: /kt-studio:make <feature> [instructions], /kt-studio:init, /kt-studio:update, /kt-studio:doctor."
argument-hint: "<feature> [instructions, e.g. 'on QA, for testers, skip frontend code, max 4 min']"
allowed-tools: Bash(bash ${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# KT Studio

Make a knowledge-transfer video for one feature: **Part A** shows how to use it on real screens,
**Part B** walks the code at idea level in a VS Code style view. A storyboard is reviewed and
approved first, because changing a storyboard is cheap and re-recording a video is not.

**Request:** $ARGUMENTS

## Start here

Look at the first word of the request:

| Request | Do |
|---|---|
| `init` or `setup` (the same as `/kt-studio:init`) | Set this project up for KT videos: follow `references/init.md`, then stop |
| `doctor` or `check` (the same as `/kt-studio:doctor`) | Run `bash <skill>/scripts/doctor.sh <root> --data <data>`, explain each problem and its fix in simple English, then stop |
| `update <feature> [change]` (the same as `/kt-studio:update`) | Change a delivered video by recording only the changed scenes: follow `references/update.md` |
| Empty | Say what the skill does in two lines and the commands below, then ask which feature (and run `init` first when the project has no `.kt-studio/config.yml`) |
| Anything else | A feature, with optional instructions: make the video, steps 0 to 10 below. When that feature already has delivered videos (a run in `<out>/features/<feature-slug>/runs/` with `5-videos/`), ask first: update them (`references/update.md`) or make a new one |

The commands people type: `/kt-studio:make <feature> [instructions]` makes a video, `/kt-studio:init` sets the
project up, `/kt-studio:update <feature> [change]` changes a video, `/kt-studio:doctor` checks everything.

## Names used below

| Name | Meaning |
|---|---|
| `<skill>` | This skill's folder: `${CLAUDE_SKILL_DIR}` (if that shows unexpanded, the folder of this SKILL.md) |
| `<root>` | The project root: the folder that holds `.kt-studio/`, next to `.claude/` and `CLAUDE.md`. `python3 <skill>/scripts/project.py ${CLAUDE_PROJECT_DIR}` prints it and the paths below (if that shows unexpanded, leave the folder out: it starts from the current one) |
| `<config>` | `<root>/.kt-studio/config.yml`, the settings |
| `<instructions>` | `<root>/.kt-studio/instructions.md`, the project's rules, services and addresses (`instructions:` in the config can name another file) |
| `<out>` | `<root>/.kt-studio` (or `output_dir` in the config). Everything the skill writes goes here |
| `<rt>` | `<out>/runtime`: the recorder, reused by every run. Its `node_modules` (packages and the voice model) is a link to `<data>` |
| `<data>` | `${CLAUDE_PLUGIN_DATA}`: the plugin's data folder, where `setup.sh` installs the recorder's packages and voice model once for every project (Claude Code keeps it across updates and deletes it on uninstall) |
| `<feature>` | `<out>/features/<feature-slug>`: everything about one feature. Its `feature.yml` holds the answers for this feature (committed) |
| `<run>` | `<feature>/runs/<date>-<feature-slug>`: this request's folder |

```
<root>/.kt-studio/
├── config.yml               settings (committed)
├── instructions.md          the project's rules, ## Services and ## Addresses (committed)
├── learned.yml              the answers people picked for earlier videos (committed, choices.py writes it)
├── .gitignore               git keeps the files marked committed and nothing else
├── runtime/                 shared: pinned packages, offline voice, recorder, helpers, .auth/ (this run's logins)
└── features/<feature>/      one folder per feature
    ├── feature.yml          this feature's answers: audience, what to show, depth, notes (committed)
    └── runs/<date>-<feature>/   one request, reused for the whole session
        ├── run.json         request, choices, apps (key, service, environment, url, login), storyboard link, step status
        ├── 1-research/      brief.md
        ├── 2-storyboard/    storyboard.json, storyboard.html, shots/
        ├── 3-scripts/       ui.demo.ts, ui.scenes.json, code.demo.ts, code.scenes.json, tour.json
        ├── 4-checks/        contact sheets, scene reports
        └── 5-videos/        finished videos + subtitles
```

## Rules that always apply

1. **Simple English** in the storyboard, the narration and every message. Short sentences.
2. **Never log in for the person.** When a page needs a login, open a window and the person logs in
   their own way; never type into a login form or ask for a password. Logins last only for the run
   and are deleted at the end (`references/config.md`).
3. **Gate 1:** nothing is recorded until the user approves the storyboard.
4. **Gate 2:** before any recording that saves, pushes, creates or deletes something, list those
   writes and get a yes for this run. Never write where the project instructions forbid it.
5. **Facts come from the code** at each repo's `ref`, with `file:line`. Never from memory.
6. **Pace a person can follow**, no blinking scene changes (`references/quality.md`).
7. **One folder per feature.** The first `/kt-studio:make` call for a feature creates `<feature>` and a
   run in it; later calls about the same feature, in this session or the next, reuse that run (pass its
   run id to `new_run.sh`, which otherwise starts a new run on a new date). A different feature gets
   its own folder.
   Write nothing outside `<out>`, except the build output the project's own build makes (for example
   `target/` or `bin/`, ignored by git) when a terminal scene needs the program built.
8. **Always clean up**, also after a failure: `bash <skill>/scripts/cleanup.sh <out>`.
9. **Project instructions.** `<instructions>` and the `metadata` block of `<config>` are the
   project's own rules. Follow them at every step; they win over this skill's defaults, never over
   rules 2, 3, 4 and 8. Details: `references/config.md`.

## 0. Check, brief and run folder

- Check first, every run (under a second): `bash <skill>/scripts/doctor.sh <root> --quiet --data <data>`.
  On `doctor: ready`, go on. Otherwise do its numbered fixes in order: `[you]` goes to the user with
  the exact command, and the run waits; `[init]` stops the run: tell the user to run `/kt-studio:init`
  (the only command that downloads: up to 1 GB the first time on a computer) and then this request
  again; `[setup]` is step 1 below. Then run the doctor again until it prints `doctor: ready`. A `TIP`
  line does not stop the run: mention it to the user in one line at the end.
- Read `<instructions>` and the `metadata` of `<config>`. Do their "Before the run" section now.
- Note any app addresses, environments ("on QA") and branches the request names: they win for this run
  (a branch overrides the repo's `ref`). Which apps the video shows is settled at step 3, once the
  research knows which services the feature touches.
- Turn the user's instructions into constraints: audience, parts to include or skip, focus areas,
  length, language, one file or one per part.
- Run folder: for a feature this session (or an earlier one) already started, reuse its run.
  Otherwise: `bash <skill>/scripts/new_run.sh <out> <feature-slug>` (the slug is lowercase letters,
  digits and dashes; it prints the path; pass the run id as the third argument to continue an older run). Fill `request` and
  `instructions` in `<run>/run.json`, and update `steps` as each step finishes.
- **Ask, round 1** (`references/questions.md`): `python3 <skill>/scripts/choices.py ask <root> <feature-slug>
  --given '<what the request says>'`. Say its `say` line; put its `ask` questions (at most 4) to the
  person in one AskUserQuestion call, the recommended answer first; then save every answer with
  `choices.py record ... --run <run>` (extra places to read for this feature: `--knowledge`). Nothing
  to ask: say the line and go on. The answers (audience, what to show, environment, what the research
  reads besides the code) hold for the whole run.

## 1. Refresh the runtime (only when the doctor asks)

**Only `/kt-studio:init` downloads.** A video run never does: it only refreshes the recorder's small
files, in seconds, after a plugin update or in a new project on a computer that already has the
recorder. Run the exact `[setup]` command the doctor printed, which is:

```bash
bash <skill>/scripts/setup.sh <out> <data> --no-download
```

When it prints `needs a download (...)` (exit 3), it changed nothing: stop and tell the user to run
`/kt-studio:init`, then this request again. Never run `setup.sh` without `--no-download` here.

## 2. Research the feature

Follow `references/research.md`. It works for any language and stack:

- Read what people wrote first: the sources the person picked (`python3 <skill>/scripts/sources.py <root>
  <feature-slug> --run <run>` lists them: folders, links, connected tools), then READMEs, API contracts,
  tests and history. Then
  search every repo at its ref by every name the feature goes by.
- Map the layers (screens, client calls, server entry, rules, data, side effects, settings, tests)
  and trace the main flow hop by hop from the button the user clicks to what is stored and back.
- Pull out the rules with their numbers, the states, who may do what, what goes wrong, the traps.
- Read every file you will cite at its repo's ref: `git -C <repo> show <ref>:./<path> | cat -n`.
- Write `<run>/1-research/brief.md` with the template in `references/research.md`.
- **Ask, round 2** (`references/questions.md`): now the research knows the feature, ask what only the
  person can decide, with answers taken from the code: the depth (`choices.py ask ... --keys depth
  --suggest '{"depth": "<your pick from references/kt-design.md>"}'`), which flows to show, which example to
  follow, which repos the code tour shows. At most 4 questions, one AskUserQuestion call; save them with
  `choices.py record` (flows and examples as `--note`).

## 3. Capture the UI screens

No screens in this video (a CLI, a library, a backend with no UI, or the user said to skip them):
skip this step and Part A. Instead run the "Try it" commands for the `terminal` scenes now, locally,
and keep their real output for the storyboard (`references/storyboard.md`).

- **Settle the apps** (`references/config.md`, "Finding the apps for a run"), every run, also when the
  request names them. A project has services, and each service can run in several environments
  (local, dev, qa, ...): `## Services` in `<instructions>` says what each one is for, `## Addresses` where
  it runs, one column per environment. `python3 <skill>/scripts/detect.py <root> --apps` lists every
  candidate address with its service and environment (the `## Addresses` table first, then CLAUDE.md and
  the docs, local apps) and whether it answers now.
  - **Which services:** the ones this feature's screens are on (from the research).
  - **Which environment:** `environment` in `run.json` `choices` (round 1); else the one the request
    names; else the default the instructions name; else the only environment that has an address for
    every service needed. Otherwise ask one question
    (AskUserQuestion when available) with the environments as options, the instructions' default first.
    One take can mix environments only when the request or the instructions say so.
  - Ask also when a needed service has no address in that environment, or the address does not answer.
- **Record them, always with this script:** `python3 <skill>/scripts/apps.py <root> <run> '<json>'`, one
  object per app: `name` (the service, as `## Services` names it), `env`, `url`, `from`, and for a new
  service `for` and `talks` (what it is for and what it talks to, one idea-level line each, from the
  research) and `login_note`. It checks each address in a fresh browser (`probe ...: login needed` or
  `no login needed`), gives each app a `key` (for example `shop-qa`) and writes `run.json` `apps`.
  It adds what the run learned to `<instructions>`: a new service, a new environment column, an address
  for an empty cell; it never changes what is there (a `kept:` line means the table says another address:
  ask the user whether to change it). Tell the user each `added` line in one sentence. No app: `'[]'`.
- **Log in: do exactly what `apps.py` printed under `NEXT`**, nothing else. It read the `## Logging in`
  table of `<instructions>` (how people log in to each service in each environment: `none`, `window`, or
  `script`, the team's own login command) and wrote each app's method and session file into
  `run.json`. A `window` app: open the window, tell the person to log in there their own way (add the
  table's notes on which account), and wait in the background. A `script` app: check the saved session
  first; when it is missing or expired, give the person the exact command to run themselves and wait
  until they say it is done. Never run a login command, never type into a login form. No login needed:
  nothing to do. `take.sh` and `preflight.sh` read the logins from `run.json` too, and refuse to record
  an app that needs a login without a valid session.
- Walk each planned UI scene with the saved session at 1920x1080 and save
  `<run>/2-storyboard/shots/<scene-id>.png`, with a short Node script kept in the run
  (`<run>/2-storyboard/capture.mjs`, run with `cd <rt> && node <run>/2-storyboard/capture.mjs`):
  `createRequire('<rt>/package.json')('playwright')`, a context with `storageState` set to the run's session (`<rt>/.auth/kt-<key>.json`, or the project's own file; only when it logged in)
  (`playwright-cli state-load` does not apply saved login cookies). Note the locators that worked; the
  recording script reuses them.
- **Stop before every write.** A screen that only exists after a write gets `status: "after-write"`
  and a `sketch` in the storyboard.
- Code, folder and title scenes need no screenshot.

## 4. Storyboard and review (gate 1)

- Plan the video for its audience with `references/kt-design.md`: the story shape, one example all
  the way through, a sequence diagram for the big picture, one idea per scene.
- Write `<run>/2-storyboard/storyboard.json` exactly as in `references/storyboard.md`, then go
  through the checklist at the end of `references/kt-design.md` before the user sees it.
- Build: `python3 <skill>/scripts/build_storyboard.py <run>/2-storyboard`, then look at it yourself:
  `cd <rt> && node tools/snap.mjs <run>/2-storyboard/storyboard.html <run>/4-checks/storyboard-snaps`.
- Run the review loop in `references/review-loop.md` until the user approves: a Claude artifact by
  default, or **local review** (no artifact: the user opens the HTML file and comments in the chat)
  when the user or the project asks for it, or the Artifact tool is not available. Save the mode,
  link and round in `run.json`.

## 5. Write the recording scripts

From the approved storyboard, without adding or dropping scenes, into `<run>/3-scripts/`:

- Voice files first: `python3 <skill>/scripts/make_scenes.py <run>` writes `ui.scenes.json` and
  `code.scenes.json` from the storyboard voice lines (`voice.pronounce` applied to the spoken text only,
  the real spelling kept as `caption`).
- Part A: `ui.demo.ts` (`references/ui-recording.md`). Part B: `tour.json` and `code.demo.ts`
  (`references/code-tour.md`). Scene names = storyboard ids.
- **Every action waits for the word that describes it** (`lib/sync.ts`: `sync.say(id)`, then
  `s.click(target, 'word')`, `s.type(...)`, `s.end()`). Pick cue words from the spoken `text`.

Pin the code to what was approved: in `tour.json`, give each repo the `sha` from the storyboard's
`meta.sources` as its `ref`, not the branch. A branch that moves after approval then cannot change
the code or the line numbers on screen.

Then stage them into the runtime (copies named `<run-id>-ui` / `<run-id>-code`, tour built):

```bash
bash <skill>/scripts/stage.sh <out> <run>
```

Re-stage after every script change. The files in `<run>/3-scripts/` are the source of truth.

## 6. Rehearse

The simple way, which runs every step below in order with the right names and always stops the tour
server: `bash <skill>/scripts/take.sh rehearse <out> <run> <ui|code>`. A part longer than about 3
minutes takes more than a 10-minute command limit to rehearse: run it in the background, like a take,
and wait for it to finish. A rehearsal or take that was cut off leaves its recorder running; `take.sh`
then refuses to start and says to run `cleanup.sh` first. To retry only the scenes you just
fixed, add `--patch <first> <last>`: the scenes before them run fast, so a retry takes a minute instead
of a whole rehearsal. The steps it runs:

- Set for every Argo command, run inside `<rt>`: `KT_BASE_URL`, `KT_STATE` (the session file `run.json`
  names for the app, or the merged one; Part A only, and only when the app needed a login; `take.sh` fills both from `run.json` `apps` and stops early
  when the app does not answer, but a direct `npx argo` call falls back to localhost:3000), and `KT_TRANSCRIBE=1` when `voice.word_timing` is `whisper`, for `tools/beats.mjs` too. The voice
  and speed come from `<config>` (`KT_VOICE` and `KT_SPEED` override them).
- `npx argo tts generate demos/<run-id>-ui.scenes.json`, then `node tools/beats.mjs <run-id>-ui`
  (word timings for the cues and captions; and the same for `-code`). Again after any voice change.
- Part A: `KT_DRY=1 npx argo record <run-id>-ui`. In a rehearsal `createSync()` blocks every request that
  could change data, so it stops at the first write (end the script there with `if (DRY) return`).
  Fix locators and waits in `3-scripts/`, re-stage, repeat until it passes. When every write goes to
  local demo data the user said yes to at gate 2 (and "Before each take" resets it), rehearse once
  more without `KT_DRY`, so the scenes after the write run before the real take too. Then
  `python3 <skill>/scripts/check_sync.py <rt>/.argo/<run-id>-ui`: a late cue means the line has no
  room for its actions. Change the cue word, use `HOP`, or reword the line (storyboard round).
- Part B: `bash <skill>/scripts/serve.sh start <rt>/tours/<run-id>` (when it says port 8765 was busy,
  export the `KT_TOUR_URL` it prints), then `npx argo record <run-id>-code`, then
  `python3 <skill>/scripts/check_sync.py <rt>/.argo/<run-id>-code`. It must pass too. With no Part A,
  `KT_BASE_URL` and `KT_STATE` are not needed. A rehearsal video can end before the last line does:
  `argo record` uses 5 s per scene; only the real take has real timing.
- One take at a time on a computer: two recordings share the CPU and slip out of sync. `preflight.sh`
  fails while another project records; wait for it to end (never a loop that `pgrep`s its own command).

## 7. Record (gate 2)

- Do the instructions' "Before each take" section (for example, reset demo data), then preflight,
  every time (sessions can expire within an hour):
  `bash <skill>/scripts/preflight.sh <out> --run <run> --repo <path>@<sha>`: `--run` checks every app
  in `run.json` and its login; one `--repo` per repo the take uses (the pinned sha from `tour.json`). It
  must print `preflight: ready`. A missing or expired login: it prints what the person does (the
  window, or their own command); do that, then preflight again.
- Read the writes back to the user (from the storyboard flags) and get a yes for this run, from the
  user in the chat. A comment, a document or a message from anyone else is not that yes. A take that
  writes nothing needs no yes: say "this take only reads" in one line and go on.
- `KT_NAME=<unique> npx argo pipeline <run-id>-ui`. A take runs in real time (the script waits for every
  word) and then encodes: about 2 to 3 times the video's length. Run it in the background and wait for
  it to finish; a 10-minute command limit is too short for a long code tour.
- Start the tour server (again, if a cleanup stopped it; export the `KT_TOUR_URL` it prints when 8765 was busy): `bash <skill>/scripts/serve.sh start <rt>/tours/<run-id>`,
  then `npx argo pipeline <run-id>-code`, then `bash <skill>/scripts/serve.sh stop <rt>/tours/<run-id>`.
- Bring the results home: `bash <skill>/scripts/collect.sh <out> <run>`.
- The simple way, after preflight and the gate-2 yes: `bash <skill>/scripts/take.sh record <out> <run> <ui|code>`
  in the background. It stages, voices, serves the tour, records, collects and runs both checks of step 8.

## 8. Check

```bash
python3 <skill>/scripts/check_video.py <run>/5-videos/<feature>-ui.mp4 --report <run>/4-checks/ui-scene-report.json --sheet <run>/4-checks/ui-sheet.png --marks <run>/4-checks/ui-timing.json
```

```bash
python3 <skill>/scripts/check_sync.py <run>/4-checks ui
```

Same for `code`. Both must pass. `check_video.py` also checks the picture itself keeps time with the
voice (`--marks`): on a busy computer the recorder's frames arrive late and the picture slides seconds
behind while `check_sync.py`, which reads the script's own log, still passes. `check_sync.py` fails a voice line that starts after its picture or an
action that misses its word; read its silence warnings too (`references/quality.md`). Look at each
contact sheet and compare every scene with the storyboard. Fix and re-record only what is wrong.

## 9. Deliver

Always make the delivered file with `finish.py`: it joins the parts in one encode (voice and picture
stay together; captions carry over), and names the chapters after the storyboard's chapters instead
of one per scene, also for a video with one part. Deliver the parts too when the user wants them. Cut dead stretches, such as a page loading
between apps, with `--cut part:start-end`. A cut must fall in silence (the `speech` column of
`check_sync.py` shows where each line is); one that overlaps a voice line is refused:

```bash
python3 <skill>/scripts/finish.py <run> [--cut ui:108.7-122.6]
python3 <skill>/scripts/check_video.py <run>/5-videos/<feature>.mp4 --marks <run>/4-checks/joined-timing.json
```

Send `<run>/5-videos/<feature>.mp4` (with its `.srt` and `.vtt`) to the user with a short table. The part
files (`<feature>-ui.mp4`, `<feature>-code.mp4`) stay as working copies: `patch.py` updates them later. part, length, scenes, anything
that differs from the storyboard. Mention what was written to shared systems during recording.
Do the instructions' "After the run" section. Set every step in `run.json` to `done`.

## 10. Clean up

```bash
bash <skill>/scripts/cleanup.sh <out>
```

It must print `nothing running`. It stops only what the skill's own scripts started. Then delete the
run's logins (they are never kept between runs): `bash <skill>/scripts/login.sh forget <out>`. It
deletes only the files KT Studio made (`kt-*`), never sessions the project keeps itself. Also stop every
process you started yourself for this run (an app server from "Before the run": note its pid in
`run.json` under `started` when you start it), unless the instructions say to leave it running.

## References

| File | Read it when |
|---|---|
| `references/init.md` | The request is `init`, or the doctor finds no settings, or settings to move into `.kt-studio/` |
| `references/config.md` | Reading `<config>` or `<instructions>`, finding the apps for a run, services and addresses, logging in |
| `references/questions.md` | Asking the two rounds of questions, saving the answers, and what the answers teach the next video |
| `references/research.md` | Researching the feature in any codebase, and writing the brief |
| `references/kt-design.md` | Planning the video for its audience: story shape, scene patterns, voice lines |
| `references/storyboard.md` | Writing `storyboard.json` |
| `references/review-loop.md` | Publishing the storyboard and handling comments |
| `references/ui-recording.md` | Writing the Part A script |
| `references/code-tour.md` | Writing the Part B tour and script |
| `references/quality.md` | Pace, voice and picture sync, and checking a video |
| `references/update.md` | A delivered video needs a change: record only the changed scenes and splice them in |
| `references/lessons.md` | Something behaves oddly; most traps are already listed |
