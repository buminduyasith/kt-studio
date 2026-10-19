# Designing a KT video people understand

**Contents:** 0. How people learn from a video · 1. Who is watching · 1b. How deep to go · 2. The shape that works · 2b. The intro and the outro · 3. Principles · 3b. Motion: showing the system work · 4. Length · 5. Scene patterns · 6. Writing the voice lines · 7. Check the storyboard before the user sees it

A good knowledge-transfer video leaves the viewer able to **do** something: test the feature, change
it, explain it, or fix it. Decide that first; every scene must serve it. The bar: a developer who has
never seen the code understands the feature end to end from this one video, without reading anything
else first.

## 0. How people learn from a video

These come from research on learning from narrated video (Richard Mayer's multimedia principles,
cognitive load theory, and studies of how developers learn unfamiliar code). Each is a rule here.

| Rule | What it means in a KT video |
|---|---|
| **A map first** | Before any detail, show the parts involved and give each a one-line job. Knowing the parts frees the mind to follow how they interact. The map scenes do this |
| **One worked example** | Follow one real case (one order, one request) from the click to the database and back, in Part A and again in Part B. Name other branches; do not walk them all |
| **Picture and word together** | The thing moves or lights up while the voice names it, never seconds apart |
| **Labels, not sentences** | On screen: short labels and key terms beside the thing they name. Never the narration as text; the subtitles are a separate track the viewer turns on |
| **Point at it** | Light the part the voice is about and dim the rest. Say the structure aloud ("three steps") |
| **Small pieces** | One idea per scene. At most about four new names per scene. Chapters with verb-phrase titles ("Check the cart") |
| **Nothing extra** | No music, logo intros, jokes or side stories. Every scene serves the goal |
| **Talk to them** | "You" and "we", plain words, a normal pace, no filler |
| **Why, not only what** | Say why it is built this way. It is what newcomers miss most, and what only a coworker usually knows |
| **Skip what they know** | No general programming lessons ("a function is..."): help a beginner needs is noise to a developer |

## 1. Who is watching

| Audience | After the video they can | Part A (use it) | Part B (how it works) | Leave out |
|---|---|---|---|---|
| QA | Test it: every flow, rule, edge case and error message, with test data | Most of the video | Short: where each rule lives | Internal structure |
| Developer new to the area | Change it safely | Short: the main flow | Most: the path, rules, data, side effects, where to change things | Clicking through every screen |
| Scrum master, product owner | Explain it and plan around it | The flows and why they exist | One big-picture diagram at most | Code |
| Support, operations | Diagnose it | Flows and what failure looks like | Logs, settings, flags, retries | Code details that never fail |

The audience is the round 1 answer (`run.json` `choices.audience`: `developer`, `qa`, `product`,
`support`, or the person's own words). None given: assume a developer joining the team and say so in
`brief.readAs`.

## 1b. How deep to go

Decide the depth after the research, from what you found, not from the size of the repo, and offer
your pick as the recommended answer of round 2 (`references/questions.md`): the person's answer wins. Count the
feature's footprint: files on the main path, repos or services it crosses, hops in the main trace,
async boundaries (queues, events, jobs, webhooks), and rules with numbers.

| Depth | Pick it when | Part B looks like | Length |
|---|---|---|---|
| **Overview** | A small footprint (about 5 files or fewer, one repo, 4 hops or fewer, no async), or an audience without code, or the user asks for "high level", "quick", "short", "an intro" | The map and the journey in motion, then 3 to 6 code scenes on the ideas that matter: where it starts, the one rule, where data lands | 2 to 4 min |
| **Standard** (default) | Anything in between | The map, the journey in motion, the main flow hop by hop in code, each key rule where it lives, the failure that matters, one change-and-test scene | 5 to 10 min |
| **Deep dive** | A large footprint (several services, async hops, indirection such as events, dependency injection or schedulers), or the user asks for "deep dive", "in depth", "in detail", "thoroughly", "explain X deeply" | The map, then one chapter per service or stage, each opened by zooming into its part of the map; every hop, including the async ones and how each link is wired; the failure paths (retries, timeouts, duplicates, expiry); concurrency and idempotency; the data and its states; settings; the tests that prove each rule | 8 to 12 min per video; more than that becomes several videos, one per stage or service |

- **The user's words win.** "Explain the webhook deeply" means a deep dive on the webhook and an
  overview of the rest, even in a small project. "High level only" means overview, even in a large one.
- A small codebase never gets padded: an overview with five good scenes beats a standard video that
  repeats itself. A large one never gets squeezed: cut scope (one flow, one service), not depth.
- Say the depth and why in `brief.readAs`, for example "Depth: deep dive on payment confirmation
  (3 services, 2 async hops, you asked for detail); overview of order creation". A wrong guess is
  then caught in review, before anything is recorded.
- Deep dive does not mean reading code line by line. It means more hops, more failure paths and
  more "why", each still one idea per scene.

## 2. The shape that works

No screens to show (a CLI, a library, a worker, an API with no UI), or the user skips them: there is
no Part A. Part B opens with the intro, then a short "Try it" chapter of `terminal` scenes (run it, see
the answer, see a rule refuse), then goes on as below. Number its chapters B1, B2, ... as usual.

Part A (the app):

1. **The intro** (one `intro` scene, the first of the video, 15 to 30 s): the card says what the
   feature is and why it exists, what you will learn, the chapters, who built it and which version of
   the code; the voice says why it matters and what the viewer will be able to do (section 2b).
2. **Use it**: the main flow first, happy path, with realistic data. Then the rule that trips people
   up, shown failing on screen. Then the other role (the approver, the admin).

Part B (how it works), from the outside in, the way a map zooms in:

3. **The map** (20 to 45 s, `map` scenes): the parts this feature crosses build up one by one, each
   named with its job, inside their boundaries ("everything in the Acme box is ours; the payment
   provider is outside"). End on the still overview: this is the high-level design picture.
4. **The journey in motion** (`map` scenes): the same example as Part A travels across the map, step
   by step: what is sent, sync or async, what is saved and in which state. Bridge to Part A in words
   ("this is what ran when you clicked Refund").
5. **The states** (one `map` scene, when the main record has a status): the states light up in order
   with the event that moves each one.
6. **How it works in code**: zoom into the first part, then the code, in the order it runs, one idea
   per scene, with the small map in the corner saying where we are. Each scene says the purpose of the
   code first, then lights one to three key lines. Show each rule from Part A where it lives ("this is
   the blue banner, in code"). Crossing to another service: back to the map for one step, then zoom in.
7. **When it goes wrong** (a `map` scene, then code): the failure that matters (a timeout, a retry, a
   duplicate) shown on the map, then where the code handles it.
8. **Why it is built this way** (one or two scenes): the decisions behind the shape, with their source.
9. **Change, test, debug** (one to three scenes, for developer and QA audiences): where a new rule
   goes, the tests that cover it (run, with their real output), what the logs say when it fails.
10. **Recap and outro**: the journey replays once, quickly, on the full map; then the `outro` scene,
    the last of the video: three things to remember, the next steps, where to ask (section 2b).

For an audience without code, Part B can be chapters 3 to 5, 7 and 8 alone, still with the intro and
the outro.

## 2b. The intro and the outro

Every video opens with an intro and closes with an outro: a full screen card (`lib/cards.ts`), the
same in Part A and Part B, whose parts come in one by one with the voice. The intro fades away into the
first screen; the outro stays to the end. They are the "map first" and the "what now" of the video.

| | The card shows (storyboard `intro` / `outro`) | The voice says |
|---|---|---|
| **Intro** | The feature's name, one line on what it is and why it exists (`tagline`), what you will learn (`learn`, 3 items), the chapters (filled in from the storyboard), the length, who built it (`builtBy`) and the code version (filled in from `meta.sources`) | Why it matters and what the viewer will be able to do after watching, in two or three sentences. It names who built it ("Built by the Orders API team"), never reads the card aloud |
| **Outro** | Three things to remember (`remember`), the next steps (`next`: a real test command, the file where a new rule goes, the doc to read), where to ask (`ask`), who built it | The three things, in other words than the card, then where to go with questions. It ends on a short, friendly line, not "thanks for watching" |

- Who built it and where to ask come from round 2 (`references/questions.md`): the person picks the
  names, a team, or no names. Never show an email address or anything else personal.
- The intro's `learn` items match the video's goal (`brief.readAs`); the outro's `remember` items are
  the key rules and ideas, and each one was shown in the video.
- Keep each under about 30 s. No music, no logo animation, no long thanks.
- The project's brand (`branding` in config.yml, `references/config.md`) puts its logo on both cards
  and its colour on the cards, the map and the code highlight. Nothing else changes: the layout stays
  the same, so every KT video reads the same way.

## 3. Principles

- **One idea per scene.** If a line needs "and also", it is two scenes.
- **One example all the way through.** The same request, order or user in Part A and Part B, so the
  code tour talks about something the viewer has already seen.
- **The screen's words.** Name things as the UI does. When the code uses another name, say both once
  ("the screen says Refund; the code calls it a reversal").
- **Show, then tell.** The picture changes, the voice names it, the action lands on its word.
- **Rules three times.** The key rules appear on screen, in the code, and in the recap.
- **Numbers, not adjectives.** "At most ten working days", not "a limited number of days".
- **Say why, not only what.** "The days leave the balance only at approval, so a rejected request
  costs nothing."
- **Signpost.** Chapter titles, and a short "Next, ..." when the story moves to a new place.
- **Only proven facts.** Every fact in the voice is labelled `CODE` or `RUN` in the brief
  (`references/research.md`, section 10). A stale doc is never repeated as truth; it can be a trap.

Avoid: reading code line by line, unexplained acronyms, more than five rules, scenes longer than
about 20 s, long silent navigation, showing secrets or personal data, and anything the viewer must
pause to read.

## 3b. Motion: showing the system work

The map scenes (`map`, drawn by `assets/studio/ide/map.js`) show the parts of the system and a request
moving between them before any code. The best technical explainers do the same: build the diagram
piece by piece with the voice, move one thing at a time, light the active path and dim the rest, and
zoom from the big picture into one part.

**Layout.** The map is a small grid. Left to right is the direction of the main flow: the person on
the left, then the app, the services, and outside providers on the right; data stores below the
service that owns them; queues and topics between the services they join. A boundary (`groups`) is
drawn around what runs together or belongs to the team. At most about 9 parts on one map: split a
bigger system into a map per stage. **Use one map for the whole video**: a part keeps its place and
colour from the first scene to the recap, and the corner map during the code is the same map, small.

**Grammar.** Each kind of message has one look, every time:

| Step kind | Looks like | Use it for |
|---|---|---|
| `call` | A yellow message travels along a solid arrow | A request that waits for its answer (HTTP, gRPC, a function call across a boundary) |
| `reply` | A blue message travels back beside the call | The answer, when it matters (`202 Accepted`) |
| `event` | A purple message on a dashed arrow; with `to` as a list, one copy flies to each consumer | Async: a message published to a queue or topic, a webhook, a job picked up later |
| `write`, `read` | A teal message into or out of a database, cache or file; `state` shows what is stored | Saving and loading, and what the record looks like after |
| `fail` | A red message stops halfway and shows ✕ | A timeout, a refusal, a crash: the failure that matters |

**Motion rules.**

- One movement at a time, and the voice names it as it moves ("the shop **sends** the refund to the
  Orders API"). The effect starts only when the message lands.
- A part comes in when the voice first names it, with its one-line job in the same breath.
- The travelling text is the real data, short (at most about 36 characters): `{ order: 1042, amount: 20 }`,
  `refund 77`, `POST /refunds`.
- After each step, hold: the scene's 1.5 s pause is the hold. Three or four steps per scene at most.
- Zoom into a part right before its code opens ("inside the Orders API..."), and show the corner map
  (`where` on the code scene) for every code scene of that part.
- Colour is never the only signal: the dashed line, the ✕ and the label carry the meaning too.

**The diagram kinds.** Pick the picture that answers the viewer's question:

| The question | Picture |
|---|---|
| What are the parts and how are they connected? (the high-level design) | `map` with `overview` |
| What happens, in order, when I click? | `map` with `steps` (the journey) |
| Who calls whom, exactly, and in what order, inside one exchange? | `diagram` (sequence) |
| What states does the record go through? | `map` whose nodes are `state` |

## 4. Length

| Audience | Target |
|---|---|
| QA, scrum master, product owner | 3 to 6 minutes |
| Developer | 6 to 12 minutes |

Keep each chapter under about 6 minutes: people stop watching around there, whatever the total, and
chapters let them jump. Over 12 minutes, split into several videos (one per flow or per service). The scene estimate in the
storyboard (words / 2.4 + 2 s at speed 0.9) adds up to the length; cut scenes, not pace.

## 5. Scene patterns

| Pattern | Kind | Use it for |
|---|---|---|
| Intro | `intro` | The first scene: what it is, why it exists, what you will learn, the chapters, who built it |
| Outro | `outro` | The last scene: three things to remember, next steps, where to ask |
| Title card | `title` | Chapter openers |
| Map build-up | `map` (`reveal`) | The parts this feature crosses, each named with its job, coming in as the voice names them |
| High-level design | `map` (`overview`) | Every part and connection, still, inside its boundaries |
| Journey | `map` (`steps`) | The worked example travelling across the parts, one step per sentence |
| Async fan-out | `map` (an `event` step with several `to`) | One event reaching several consumers |
| Failure and retry | `map` (a `fail` step) | The failure that matters, before the code that handles it |
| States | `map` with `state` nodes | The status of the main record and what moves it |
| Zoom in | `map` (`zoom`) | Going from the map into one part, right before its code |
| Recap replay | `map` (`replay`) | The whole journey again, quickly, before the last title |
| Sequence diagram | `diagram` | Who calls whom, in order, inside one exchange, one arrow lit per step |
| Screen walk | `ui` | A flow on the real app; actions land on their words |
| The trap | `ui` | A rule shown failing, with the message zoomed |
| Folder walk | `nav` | Where a part lives, narrated ("open src, then routes") |
| Code idea | `code` (with `where`) | One range of at most 25 lines, one note with the idea, the corner map lit on its part |
| Try it | `terminal` | Use it without a browser: a CLI command, a `curl` to the API, a test run, with its real output. The "use it" part for a CLI, a library or a backend with no screens |
| Follow the call | `code` | A jump from a call to its target, possibly in another repo |

## 6. Writing the voice lines

- Simple English, present tense, active voice, "you" for the viewer. At most about 15 words per sentence.
- Speak numbers and names the way a person says them; put odd product words in `voice.pronounce`.
- Name a file by what it is in the voice ("the store file", "main"), and show the real name on screen
  (note, heading, terminal). "main dot r s" and "dash dash tag" are hard to listen to. A pronounce entry
  changes every place the word appears, so read every line it touches again.
- Define an acronym the first time ("the T T L, the time to live, is one hour").
- UI lines carry their actions: name the button or field as it is used, say a typed value as it is
  typed, and leave about 1 s of voice per click. The recording clicks on those words.
- Code lines say what the code means for the viewer, not what the syntax does.
- The last line of a chapter can bridge to the next ("Now let's see where that rule lives").

## 7. Check the storyboard before the user sees it

- [ ] The video opens with the `intro` and closes with the `outro`; the intro's `learn` matches the goal.
- [ ] Every scene serves the audience goal in `brief.readAs`.
- [ ] Part B opens with the map: every part named with its one-line job, before any code.
- [ ] One example runs through Part A, the journey on the map, and the code.
- [ ] The failure that matters is shown, on the map and in the code.
- [ ] There is a "why it is built this way" scene, with its source, or the brief says it is not documented.
- [ ] Each key rule appears on screen, in code, and in the recap.
- [ ] Every code scene of a service has `where`, and the code tour follows the map's order.
- [ ] No scene over about 20 s, no chapter over about 6 minutes, total within the target length.
- [ ] At most about four new names per scene; on-screen text is labels, not sentences.
- [ ] Every fact in the voice is `CODE` or `RUN` in the brief, with a `file:line` read at the ref.
- [ ] Every UI action has its word in the line; a server result is spoken in the scene after it shows.
- [ ] Every write is in `overview.writes` and flagged on its scene.
- [ ] Nothing secret or personal on screen or in the voice.
