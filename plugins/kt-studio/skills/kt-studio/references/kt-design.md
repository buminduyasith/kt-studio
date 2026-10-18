# Designing a KT video people understand

**Contents:** 1. Who is watching · 1b. How deep to go · 2. The shape that works · 3. Principles · 4. Length · 5. Scene patterns · 6. Writing the voice lines · 7. Check the storyboard before the user sees it

A good knowledge-transfer video leaves the viewer able to **do** something: test the feature, change
it, explain it, or fix it. Decide that first; every scene must serve it.

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
| **Overview** | A small footprint (about 5 files or fewer, one repo, 4 hops or fewer, no async), or an audience without code, or the user asks for "high level", "quick", "short", "an intro" | One diagram, then 3 to 6 code scenes on the ideas that matter: where it starts, the one rule, where data lands | 2 to 4 min |
| **Standard** (default) | Anything in between | The diagram, the main flow hop by hop, each key rule where it lives, one change-and-test scene | 5 to 10 min |
| **Deep dive** | A large footprint (several services, async hops, indirection such as events, dependency injection or schedulers), or the user asks for "deep dive", "in depth", "in detail", "thoroughly", "explain X deeply" | One chapter per service or stage; every hop, including the async ones and how each link is wired; the failure paths (retries, timeouts, duplicates, expiry); concurrency and idempotency; the data and its states; settings; the tests that prove each rule | 8 to 12 min per video; more than that becomes several videos, one per stage or service |

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
no Part A. Part B opens with a short "Try it" chapter of `terminal` scenes (run it, see the answer,
see a rule refuse), then goes on as below. Number its chapters B1, B2, ... as usual.

Part A (the app):

1. **Why it exists** (one title scene, 10 to 20 s, a card over the first screen): the problem, who
   has it, what you will learn.
2. **Use it**: the main flow first, happy path, with realistic data. Then the rule that trips people
   up, shown failing on screen. Then the other role (the approver, the admin).

Part B (the code tour):

3. **The big picture** (a diagram scene or two): the parts involved and the flow, step by step. For an
   audience without code, Part B can be this chapter alone.
4. **How it works**: the same flow through the code, in the order it runs, one idea per scene. Show
   each rule from Part A where it lives ("this is the blue banner, in code").
5. **Change, test, debug** (one to three scenes, for developer and QA audiences): where a new rule
   goes, the tests that cover it, what the logs say when it fails.
6. **Recap** (one title scene at the end of the last part): the three things to remember.

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

Avoid: reading code line by line, unexplained acronyms, more than five rules, scenes longer than
about 20 s, long silent navigation, showing secrets or personal data, and anything the viewer must
pause to read.

## 4. Length

| Audience | Target |
|---|---|
| QA, scrum master, product owner | 3 to 6 minutes |
| Developer | 6 to 12 minutes |

Over 12 minutes, split into several videos (one per flow or per service). The scene estimate in the
storyboard (words / 2.4 + 2 s at speed 0.9) adds up to the length; cut scenes, not pace.

## 5. Scene patterns

| Pattern | Kind | Use it for |
|---|---|---|
| Title card | `title` | Why it exists, chapter openers, the recap |
| Sequence diagram | `diagram` | The big picture: who calls whom, in order, one arrow lit per step |
| Screen walk | `ui` | A flow on the real app; actions land on their words |
| The trap | `ui` | A rule shown failing, with the message zoomed |
| Folder walk | `nav` | Where a part lives, narrated ("open src, then routes") |
| Code idea | `code` | One range of at most 25 lines, one note with the idea |
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

- [ ] Every scene serves the audience goal in `brief.readAs`.
- [ ] One example runs through Part A and Part B.
- [ ] Each key rule appears on screen, in code, and in the recap.
- [ ] No scene over about 20 s, total within the target length.
- [ ] Every code fact has a `file:line` read at the ref.
- [ ] Every UI action has its word in the line; a server result is spoken in the scene after it shows.
- [ ] Every write is in `overview.writes` and flagged on its scene.
- [ ] Nothing secret or personal on screen or in the voice.
