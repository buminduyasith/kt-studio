# The storyboard

**Contents:** Shape · Pictures · Writing rules

The storyboard is the contract. The user reviews it as a Claude artifact, comments on it, and
approves it. Only then is anything recorded. Recording is slow; changing a storyboard is cheap.

Plan it with `references/kt-design.md` (audience, story shape, scene patterns) from the brief made
with `references/research.md`. Your only creative output is `<run>/2-storyboard/storyboard.json`. The layout is fixed in
`assets/storyboard-template.html`; never edit it per feature. Build with:

```bash
python3 <skill>/scripts/build_storyboard.py <run>/2-storyboard
```

The build checks required fields and stops with a list of problems.

## Shape

```json
{
  "meta": {
    "feature": "Order Refunds", "short": "Refunds", "round": 1, "status": "Draft for review",
    "date": "2026-10-13", "environment": "dev", "shotsFrom": "https://dev.acme.example",
    "voice": "Kokoro af_heart, speed 0.9", "format": "1920x1080 MP4, chapters, subtitles (.srt)",
    "review": "artifact",
    "sources": [{ "repo": "api", "ref": "origin/main", "sha": "1a2b3c4d" }]
  },
  "brief": {
    "request": "The user's words, cleaned up into one or two sentences.",
    "readAs": ["How you understood each instruction, one line each."]
  },
  "overview": {
    "tldr": "Two sentences: what the feature does and why it matters.",
    "what": ["Plain paragraphs that explain the feature to a newcomer."],
    "explain": [{ "title": "How to ...", "detail": "What the viewer will learn." }],
    "repos": [{ "name": "acme-api", "label": "Backend", "role": "What this repo does in the feature.",
                "ref": "origin/main", "sha": "1a2b3c4d", "files": ["src/refunds/refund.service.ts"] }],
    "notCovered": ["What the video leaves out on purpose."],
    "set": [{ "k": "Environment", "v": "dev" }, { "k": "Demo data", "v": "order #1042" }],
    "writes": ["Every save, push, create or delete the recording will do, and where."],
    "questions": ["Decisions you need from the user."]
  },
  "parts": [
    { "id": "A", "title": "Use it", "subtitle": "Real screens on dev", "chapters": [
      { "id": "A1", "title": "Refund an order", "scenes": [ /* scenes */ ] } ] },
    { "id": "B", "title": "How it works", "subtitle": "Code tour, real code from origin/main", "chapters": [] }
  ],
  "diagrams": {
    "refund": { "title": "Refund", "actors": ["Agent", { "name": "Web", "sub": "web app" }, "API", "Payments"],
                "steps": [{ "from": "Agent", "to": "Web", "label": "clicks Refund" },
                          { "from": "Web", "to": "API", "label": "POST /refunds" },
                          { "from": "API", "to": "Payments", "label": "refund(charge)" },
                          { "from": "API", "to": "Web", "label": "201 Created", "reply": true }] }
  },
  "intro": {
    "tagline": "How a support agent refunds an order, and what happens behind the button.",
    "learn": ["How to refund an order", "How the refund travels to the payment provider", "Where to change the refund rules"],
    "builtBy": ["Orders API team"],
    "audience": "New developers"
  },
  "outro": {
    "remember": ["A refund is saved first and sent later", "The provider can time out: the job tries again", "The rules live in refund-rules.ts"],
    "next": [{ "label": "Run the refund tests", "detail": "npm test -- refunds" },
             { "label": "Add a refund rule", "detail": "api/src/refunds/refund-rules.ts" }],
    "ask": "The Orders API team"
  },
  "maps": {
    "refund": {
      "title": "How a refund travels",
      "nodes": [
        { "id": "agent", "label": "Support agent", "kind": "person", "col": 0, "row": 1 },
        { "id": "shop", "label": "Shop", "sub": "web app", "kind": "app", "col": 1, "row": 1 },
        { "id": "api", "label": "Orders API", "kind": "service", "col": 2, "row": 1 },
        { "id": "db", "label": "Postgres", "sub": "orders, refunds", "kind": "database", "col": 2, "row": 2 },
        { "id": "topic", "label": "refund.created", "kind": "queue", "col": 3, "row": 0 },
        { "id": "pay", "label": "Payment provider", "kind": "external", "col": 4, "row": 1 }
      ],
      "groups": [{ "label": "Acme", "nodes": ["shop", "api", "db", "topic"] }],
      "steps": [
        { "from": "agent", "to": "shop", "label": "clicks Refund" },
        { "from": "shop", "to": "api", "label": "POST /refunds", "payload": "{ order: 1042, amount: 20 }" },
        { "from": "api", "to": "db", "label": "saves the refund", "kind": "write", "state": { "node": "db", "text": "refund 77: PENDING" } },
        { "from": "api", "to": "shop", "label": "202 Accepted", "kind": "reply" },
        { "from": "api", "to": "topic", "label": "refund.created", "kind": "event", "payload": "refund 77" },
        { "from": "topic", "to": "pay", "label": "refund(charge)", "kind": "event" },
        { "from": "pay", "to": "api", "label": "timeout after 10 s", "kind": "fail" }
      ]
    }
  },
  "production": {
    "pace": ["Voice speed 0.9", "1.5 s pause after each point", "No fades between scenes"],
    "pronounce": [["AcmePay", "Acme Pay"]],   // start from voice.pronounce in the config, add new ones
    "deliver": ["refunds-ui.mp4", "refunds-code.mp4", "Subtitles .srt and .vtt", "Chapters inside each MP4"]
  },
  "review": ["Questions the reviewer should answer before approving."]
}
```

### Scene

| Field | Meaning |
|---|---|
| `id` | `A1-03` = part A, chapter 1, scene 3. Stable across rounds (comments refer to it) |
| `kind` | `intro` (the first scene of the video), `outro` (the last scene), `ui` (a real screen), `code` (a file and method), `nav` (walking the folders), `title` (a chapter opener card), `diagram` (a sequence diagram, Part B), `map` (the system map in motion, Part B), `terminal` (a real command and its real output, Part B) |
| `status` | `ready` (picture captured or drawn), `planned` (screen not captured yet), `after-write` (the screen only exists after a save or push, so it is captured during recording) |
| `title` | Short scene name |
| `heading` | Slug line, for example `SCREEN · Refund drawer · dev` or `CODE · api · refund.service.ts:40-58` |
| `voice` | The exact words the narrator says, with real spelling (the pronounce map is applied only for the voice) |
| `seconds` | Optional. The build fills it from the spoken words (pronounce map applied, numbers as said) ÷ 2.4 + 2 at speed 0.9, and notes a hand-set value that is far off. The + 2 s is the clip's lead-in and the 1.5 s pause after the point, so the scenes add up to the video's length |
| `screen` | `ui` scenes: what is on screen. `title` scenes: the subtitle |
| `action` | What the cursor or the page does, as a list |
| `note` | Optional text shown on screen (caption or code note). The same text is used in the video. Markup: `<b>` and `<code>` only; for a placeholder write `order-{id}`, never angle brackets (the same holds for a title scene's `screen`, which the video shows as the title's subtitle) |
| `shot` | `ui` scenes: `shots/A1-03.png` (relative to `2-storyboard/`), a real screenshot |
| `sketch` | `ui` scenes without a shot: `list`, `drawer`, `form`, `success` or `editor` (a drawn placeholder) |
| `code` | `code` and `nav` scenes: `{ "repo": "api", "file": "src/refunds/refund.service.ts", "symbol": "RefundService.refund()", "lines": "40-58" }`. For `nav`, `file` is the folder path walked |
| `flags` | `["writes"]` when the scene saves, pushes, creates or deletes something |
| `terminal` | `terminal` scenes: `{ "cwd": "api", "cmd": "curl -s -X POST localhost:8080/loans -d '{...}'", "output": "<what it really printed>", "marks": ["409", "fine limit"] }`. `cwd` is the folder shown in the prompt (the repo key or a short path, where the command was run); `output` is copied from running the command before the storyboard (at most 14 lines; trim with `head` or `jq`); `marks` are the bits the voice names, lit on screen |
| `diagram` | `diagram` scenes: `{ "use": "refund", "steps": [2, 3] }`: which diagram from the top-level `diagrams`, and the steps this scene lights (earlier steps stay visible, later ones are hidden) |
| `map` | `map` scenes: which map from the top-level `maps`, and what the scene does, one or more of: `"reveal": ["shop", "api"]` (bring these parts in, in this order), `"overview": true` (every part and link, still: the high-level design), `"steps": [2, 4]` (play steps 2 to 4 of the journey), `"zoom": "api"` (zoom into a part, right before its code), `"replay": true` (the whole journey again, quickly, for the recap). Parts and links shown in earlier scenes stay |
| `where` | Optional, `code` and `nav` scenes: `{ "map": "refund", "node": "api" }`: the small map in the corner of the code, with this part lit ("you are here") |

## Pictures

- **UI scenes get real screenshots.** Use the apps settled at step 3 (`run.json` `apps`: the request's
  addresses, else `## Addresses` in the instructions for the run's environment, else the docs, else a local app found running). Walk the planned steps at 1920x1080 with the saved
  session (a short Node script with Playwright, as in `SKILL.md` step 3), stop before every save, push or
  delete, and save `shots/<scene-id>.png`. A screen that only
  exists after a write gets `status: "after-write"` and a `sketch`. Its voice line cannot be checked on
  a screenshot, so work out every claim in it from the code (which times are free after the booking,
  which status shows) and cite the rule in `screen`. Keep full 1920x1080 resolution:
  reviewers click a picture to open it full size, and arrow keys move through every screenshot.
- **Terminal scenes show real output.** Run the command yourself first, on this computer, against the
  local app or the code (a CLI, `curl` to a local API, a test run, a script), and paste what it printed.
  Never write output by hand, and never run a command that writes to a shared system to get it. A
  command that would change shared data is described in a `code` scene instead.
  - Run every terminal scene of the video in order, from a clean state (an empty data file, a fresh
    local database), in one go, so the outputs agree with each other (ids, counts, timestamps).
    Re-run the whole sequence after any change.
  - Show the command the way the team types it (`cargo run -- add ...`, `npm run ...`, `./bin/tool`),
    or the installed name when the README says to install it. One command per scene, no `&&` chains.
  - Keep a command under about 80 characters (it is typed on screen). The terminal panel in the video
    shows about 130 characters per line; longer lines wrap, which is fine. The 14-line limit counts
    output lines. Narrowing output with a pipe (`| grep`, `| head`, `| jq`) or a quiet flag is fine and
    stays in the command, so the viewer sees exactly what was run. Drop blank lines a tool prints first.
  - Run a project's tests or build in a scratch copy when the project's rules say so, and point package
    caches there too (`npm --cache`, `-Dmaven.repo.local`), so nothing lands in the home folder. Name
    the copy's folder like the project folder (`/tmp/.../payment-gateway`), because tools print their
    working folder and the prompt on screen shows the project's.
  - `marks` light every place the text appears in the output: pick a phrase that appears once
    (`limit is 280`, not `280`).
- **Code, nav and title scenes are drawn** from the data. File, method and lines are enough to
  review them. No screenshot.
- **The intro and the outro are drawn** from the top-level `intro` and `outro` (`references/kt-design.md`
  section 2b). One `intro` scene, the first scene of the video, and one `outro` scene, the last; the
  build checks both. `intro`: `tagline` (one line, about 140 characters at most), `learn` (1 to 4 items,
  three is best), `builtBy` (the names or team the person picked in round 2; `[]` shows no names),
  `audience` (shown as "for new developers"); optional `title` (else `meta.feature`), `agenda` and
  `length` (else filled in from the chapters and the scene lengths) and `code` (else the first source's
  repo, ref, sha and the date). `outro`: `remember` (1 to 4 items, three is best), `next` (each
  `{ label, detail }`: a real command, a file, a doc), `ask` (where to go with questions, from round 2;
  `"none"` leaves it out), optional `builtBy` (else the intro's) and `title`. Never an email address.
- **Map scenes are drawn** from `maps` (the storyboard shows each one small, with its steps lit; the
  video animates them, `references/kt-design.md` section 3b). A map is the system as the research found
  it (`references/research.md` section 8), every part and link with evidence in the brief:
  - `nodes`: `id`, `label` (the team's name for it), optional `sub` (a few words), `kind` (`person`,
    `app`, `service`, `job`, `database`, `cache`, `queue`, `external`, `state`), and `col`, `row` on a
    small grid (0-based). Left to right follows the main flow; data stores go under their service.
    At most 9 nodes; no two on the same cell.
  - `groups`: boundaries, `{ label, nodes }`, drawn around their nodes. The box spans from the first to
    the last column and row of its nodes, so no other node may sit inside that range (the build checks).
  - `steps`: the journey, in order: `from`, `to` (a list for an event that reaches several consumers),
    `label` (what the step means or its real call), optional `kind` (`call`, `reply`, `event`, `write`,
    `read`, `fail`), `payload` (the real data that travels, at most about 36 characters) and `state`
    (`{ node, text }`: what is stored after this step).
  - A map with only `state` nodes is a state diagram: its steps are the moves, labelled with the event.
- **Diagram scenes are drawn** from `diagrams`: actors across the top, one arrow per step, in order.
  Use one for the big picture before the code (who calls whom), and light it step by step over a few
  scenes. Keep it to at most 6 actors and 10 steps; labels are what the step means or its real call
  (`POST /refunds`). A non-developer audience can have a Part B that is only a diagram chapter.

`production.pronounce` is the only list the voice uses (`make_scenes.py` reads it). Copy every entry of
`voice.pronounce` from the config (`.kt-studio/config.yml`) into it first, then add the feature's own words.

## Writing rules

- Simple English. Short sentences, active voice, one idea per sentence, one or two sentences per scene.
- Say what the viewer should understand, not what the code literally does line by line.
- UI lines carry their actions: name the button or field as it is used ("click Send request"), say a
  typed value as it is typed ("Monday the second of November"). The recording clicks on those words.
  Leave about one second of voice per click and 0.1 s per typed character; when a scene has more
  actions than its line can carry, split it. Say a server result in the next scene, after it shows.
- Every code fact must come from the file at its repo's ref. Read it with
  `git -C <repo> show <ref>:./<path>` and put the real line range in `code.lines`.
- Narrate only facts the brief labels `CODE` or `RUN`. A `DOC-ONLY` claim stays in `overview.questions`;
  a `CONFLICT` (a stale doc) can be a trap scene, never a fact.
- On screen, labels and key terms only: the voice carries the sentences.
- Put the rule that trips people up in the UI part first, then show where it lives in the code.
- Name every write in `overview.writes` and flag its scene.
- Fill `brief.readAs` with how you understood each user instruction, so a misreading is caught in review.
- Order: Part A (use it) before Part B (how it works). Skip a part when the user asks.
