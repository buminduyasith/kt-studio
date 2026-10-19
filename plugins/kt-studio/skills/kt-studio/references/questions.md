# Questions: ask few, recommend well, remember the answers

**Contents:** 1. The idea · 2. Round 1, before the research · 3. Round 2, after the research · 4. Saving the answers · 5. What the next video learns

## 1. The idea

Every project is different, and every feature in it too: who watches, what to show, how deep. So each
video asks, but it asks little, and every question comes with the best answer first. The first video in
a project knows nothing and asks the most. Later videos know the feature (`feature.yml`) and what people
picked before (`learned.yml`), and ask less.

- **Never ask what the request, the code or the files already say.** "For testers, on QA" answers two
  questions.
- **One AskUserQuestion call per round**, at most 4 questions, 2 to 4 answers each. The recommended
  answer is first and its label ends with "(Recommended)". The person can always pick "Other" and type.
- **Plain words.** Labels of 1 to 5 words; the description says what the answer changes in the video.
- No AskUserQuestion tool (for example a background session): ask the same questions as one short
  numbered list in the chat, with the recommended answer named, and wait.

## 2. Round 1, before the research

```bash
python3 <skill>/scripts/choices.py ask <root> <feature-slug> --given '{"audience": "qa", "environment": "qa"}'
```

`--given` holds only what the request says, as values: `audience` (`developer`, `qa`, `product`,
`support`), `show` (`screens-and-code`, `screens`, `code`), `environment` (a column of `## Addresses`),
`sources` (`project`, or `code-only` for "code only, skip the docs"), and `language` when the request
names one. Leave out what it does not say.

**The sources question** asks what the research reads besides the code: the project's `knowledge:` list
(its answer lists them) or code only. When the request or the "Other" answer names extra places (a spec,
a folder, a ticket link), keep `sources: project` (or `code-only` when the person said so) and save each
place with `--knowledge` (section 4): they are read for this feature only, after the project's list.

It prints JSON:

| Field | What to do |
|---|---|
| `use` | Answers already settled, and where each came from. Do not ask them again |
| `say` | One line for the person, for example "Using audience: QA or tester (picked 3 times in a row). Say if you want something else." Say it as it is |
| `ask` | The questions. Pass `question`, `header`, `multiSelect` and each option's `label` and `description` to AskUserQuestion, in the same order. Keep each option's `value`: it is what you save |

An answer is settled, in this order, by: the request; this feature's `feature.yml` (an earlier video of
the same feature); the instructions (the default environment under `## Before the run`); the only
choice there is (one environment, or no app at all, which means code only); or `learned.yml`, when
the same answer was picked 3 times in a row. **The environment is never settled by `feature.yml` or
`learned.yml`**: where the app runs changes from video to video, so an earlier answer only goes first.
**The depth is never settled by `learned.yml`**: it follows each feature's size.

The environment question is left out when the video shows code only, or `## Addresses` is empty (step
3 of `SKILL.md` then finds the apps).

## 3. Round 2, after the research

Now you know the feature. Ask only what the person must decide and the code cannot: these questions
are specific to this feature, and their answers come from the brief.

1. **Depth, who built it, and where to ask**, in one call, unless settled:

   ```bash
   python3 <skill>/scripts/authors.py <repo-path> <ref> <file or folder>...      # once per repo on the code path
   python3 <skill>/scripts/choices.py ask <root> <feature-slug> --keys depth,built_by,contact \
     --suggest '{"depth": "<pick>"}' --offer '{"built_by": [<names from authors.py>], "contact": [<the first of them>]}'
   ```

   - **Depth**: your pick follows `references/kt-design.md` ("How deep to go"). Put the reason in the
     description of the recommended answer, for example "3 services and 2 async hops".
   - **Who built it** (`built_by`, several answers allowed) names the people or the team on the intro and
     the outro. `authors.py` gives the names with the most commits on the feature's files (from the
     brief's code path), names only: never an email, never a bot. Merge the repos' lists, most commits
     first, at most three. The person can pick them, type a team name under "Other", or pick "Show no
     names". Names are personal: show only what the person picked.
   - **Where to ask** (`contact`) goes on the outro: a team, a channel or a person, or "Leave it out".
   - Both belong to the feature: the next video of the same feature asks neither. A contact picked three
     times in a row stops being asked for other features too.
2. One more of your own in the same call (AskUserQuestion takes four), only when the brief shows a real
   choice. Settled answers leave room for more. When the feature truly needs more choices, one second
   call of at most three. Examples:
   - "I found three flows: full refund, part refund, refund failed. Which should the video show?"
     (`multiSelect: true`, the flows most people use first).
   - "Which example should the video follow from start to end?" (two or three real records or
     inputs from the code or the test data).
   - "The code tour can show the Shop and the Orders API. Which should it show?" (`multiSelect: true`).

   Do not ask about anything with only one sensible answer. Do not ask about wording or scene order:
   that is what the storyboard review is for.

## 4. Saving the answers

After each round, save what is now known, as values:

```bash
python3 <skill>/scripts/choices.py record <root> <feature-slug> --run <run> \
  --answers '{"audience": "qa", "show": "screens-and-code", "environment": "qa"}' \
  --learn audience,show,environment --title "Order refunds" \
  --note "Flows: full refund, part refund" --note "Example: order 1042, paid by card"
```

- `--answers`: every answer of the round, settled ones included, so `run.json` `choices` has them all.
  `built_by` is a list (`["Orders API team"]`, or `["none"]` for no names); put the same names in the
  storyboard's `intro.builtBy` (`[]` for no names) and the contact in `outro.ask`.
  A label from AskUserQuestion is turned into its value; an "Other" answer is kept in the person's words.
- `--learn`: only the keys the person answered in this round or the request said. Never the ones settled
  by `feature.yml`, `learned.yml` or the instructions: counting them again would teach nothing.
- `--knowledge`: a place to read for this feature only, one per flag: a folder or file in the project,
  one outside it (`~/notes/refunds/`), a web link, or `connector: <what>` for a tool connected in Claude
  Code. It is kept in `feature.yml` under `knowledge` and read by every later video of this feature.
- `--note`: round 2 answers that are not one of the fixed questions. They are kept in `feature.yml`,
  so the next video of this feature (and `/kt-studio:update`) knows them.
- `--title`: the feature's name in plain words, the first time.

It writes `<feature>/feature.yml`, `learned.yml` and `run.json` `choices`. The two `.yml` files are
committed with the rest of `.kt-studio/`, so the whole team shares them. Tell the person in one line
when `feature.yml` is new: "Saved this feature's answers in .kt-studio/features/<feature>/feature.yml."

## 5. What the next video learns

- **The same feature again** (a new video, or `/kt-studio:update`): `feature.yml` settles audience,
  what to show, the sources and depth, and its notes say which flows and example were chosen. Round 1 is usually one
  line; round 2 asks only what the new request changes.
- **Another feature in the same project:** the recommended answer is the one picked most often, and a
  question stops once the same answer was picked 3 times in a row (not the environment or the depth).
- **Never learned:** passwords, tokens, accounts or anything about logging in (that is the `## Logging in`
  table, written by people), and anything the person did not choose.
- To make it ask again, the person deletes the answers from `learned.yml` or a line from `feature.yml`,
  or simply says so in the request.
