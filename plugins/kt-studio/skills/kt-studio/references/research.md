# Researching a feature (any language, any stack)

**Contents:** The rule · 1. Frame the job · 2. Read what people wrote, as leads · 3. Find the footprint · 4. Map the layers · 5. Trace one flow end to end · 6. Prove it is live, and try to prove yourself wrong · 7. Run it when it is safe · 8. Map the system · 9. What a newcomer must know · 10. Grade every fact · 11. Write the brief · 12. Keep the scope a person can hold · Red flags

The goal is a brief a stranger could trust: what the feature is for, how people use it, the parts of
the system it crosses and how they talk, the rules it enforces, how it works end to end, why it is
built this way, what goes wrong, and how to change and test it.

## The rule

**The code at each repo's `ref` is the only source of truth.** Docs, READMEs, wiki pages, comments,
names, commit messages, tickets, diagrams and your own earlier notes are **leads**: they tell you where
to look, never what is true. Every fact the video says has evidence: a `repo:path:line` read at the
ref, or something you saw run.

Why so strict: comments and docs drift away from the code they describe. Studies of large open-source
projects found wrong comments in mature code, and docs that name code which no longer exists in about
three in ten popular projects. A video that repeats a stale doc teaches a wrong fact to every new
developer who watches it.

Work like a scientist: write down what you think is true, look for the code that confirms it, look
just as hard for the code that would prove it wrong, and keep only what survives.

## 1. Frame the job

- Say the feature in one sentence, in the user's words.
- Name the audience and what they must be able to do after watching (`references/kt-design.md`).
- List the request's limits: parts to skip, length, focus, depth words ("high level", "deep dive").
- **Write two or three hypotheses** before you read code, for example "the refund is sent to the
  payment provider straight away" and "the refund is queued and sent later". The research decides
  between them. A hypothesis you never test is not a fact.
- After step 5, size the footprint and pick the depth with `references/kt-design.md` (section 1b).

## 2. Read what people wrote, as leads

In this order, skimming for the feature's names, rules, numbers and the parts it talks to:

1. **The sources the person picked.** `python3 <skill>/scripts/sources.py <root> <feature-slug> --run <run>`
   lists them: the project's `knowledge:` list (skipped when this video is "code only") and the
   feature's own (`feature.yml`). Read every one, in that order:
   - `project`: files and folders in the project. Read the parts about the feature; cite them as `path`.
   - `outside`: a folder or file outside the project. Read only; never copy it into the run or the
     video; cite it by its path.
   - `link`: read it with the web fetch tool. Never log in. A page that asks for a login or shows
     nothing useful: skip it, say so in the brief, and ask the person to paste it or save it as a file.
   - `connector`: read it with a tool already connected in Claude Code (a wiki or a drive), read only.
     No such tool: skip it and say so; never ask the person to connect one in the middle of a run.
   - `NOT FOUND`: skip it and say so in the brief.
2. READMEs at each repo root and inside the feature's folders; `docs/`, ADRs, design notes, runbooks.
3. Contracts: OpenAPI or Swagger files, GraphQL schemas, `.proto` files, AsyncAPI, JSON schemas.
4. Words users see: translation files (`en.json`, `messages.properties`, `.po`, `.resx`, `strings.xml`).
5. Tests: their names list the behaviours ("rejects a refund larger than the order").
6. History: commits, merge requests and ticket keys that mention the feature.

Everything you take from these goes into the claims ledger (section 10) as `DOC-ONLY` until the
code confirms it. Signs that a doc or a comment is stale, so check it twice:

- A name it uses (function, class, endpoint, flag, environment variable, table, topic) no longer
  resolves at the ref: `git -C <repo> grep -n -w '<name>' <ref>` finds nothing.
- It last changed long before the code it describes. Compare
  `git -C <repo> log -1 --format=%cs <ref> -- <doc>` with the same command on the code's folder.
- Its paths, ports, topic names or environment names differ from the config.
- Its flow has fewer steps than the code, or it says "temporary", "old", "legacy", "v1" or "TODO".
- A later commit changed the code under a comment without touching the comment
  (`git -C <repo> log -L <start>,<end>:<file> <ref>` shows that range's history).

## 3. Find the footprint: search by every name

Collect every name the feature goes by: the user's words, labels on screen, URL paths, API paths,
table or collection names, ticket keys, feature flag names, and the names the code uses. Then search
all repos at their ref (not the working tree, which may be on another branch):

```bash
git -C <repo> grep -n -I -i -e 'refund' -e 'reimburse' <ref> -- ':!*lock*' ':!*.min.*' ':!*.svg'
git -C <repo> ls-tree -r --name-only <ref> | grep -i -E 'refund|reimburs'
git -C <repo> log <ref> --oneline -i -E --grep='refund|RF-[0-9]+' | head -40
git -C <repo> log <ref> --format='%h %ad %an %s' --date=short -- <folder> | head -40
git -C <repo> log <ref> --diff-filter=A --format='%h %ad %s' --date=short -- <folder>   # when files were born
git -C <repo> grep -n -w 'createRefund' <ref>                                           # who calls this
```

Always write `<ref>:./<path>` (with `./`): a repo entry may be a folder inside a bigger git repo (a
monorepo), and `./` reads the path from that folder, the same way `ls-tree` and `grep` above list it.
A bare `<ref>:<path>` reads from the top of the git repo and fails there.
With shell variables, always use braces and quotes: `git show "${REF}:./${FILE}"`. In zsh, `$REF:clinic/...`
reads `:c` as a modifier of the variable and the command fails.

Sort the hits into the layers below. A layer with no hits is a finding too ("no background job").

## 4. Map the layers

The same layers exist in almost every product. The clues differ by stack; look for the shape, not
for one framework.

| Layer | What to find | Typical clues |
|---|---|---|
| Screens | Pages, routes and components that show the feature's labels | Router config, `pages/`, `app/`, `views/`, `screens/`, templates (Jinja, ERB, Razor, Thymeleaf, Blade) |
| Client calls | Where the UI calls the server | `fetch`, axios, query hooks, generated API clients, GraphQL documents, gRPC stubs |
| Server entry | The route, controller, handler or resolver for that call | Express, Nest, Fastify, Spring `@RestController`, ASP.NET controllers, Django, Flask, FastAPI, Rails `routes.rb`, Go `http.Handle`/gin/chi, Laravel, Phoenix, GraphQL resolvers, gRPC services, CLI commands, message consumers |
| Rules | Validation, permissions, calculations, state changes | Services, use cases, domain models, policies, validators (zod, pydantic, Bean Validation, FluentValidation), guards and middleware |
| Data | What is stored and how | ORM models and entities, migrations, SQL, repositories, document schemas, cache keys |
| Side effects | What else happens | Events, queues and topics, emails, webhooks, calls to other services, scheduled jobs, audit logs |
| Settings | What changes behaviour per environment | Environment variables, config files, feature flags, roles and permissions, tenant settings |
| Tests | What is already proven | Unit, integration and end-to-end tests that name the feature |

When the trail goes through indirection (dependency injection, an event bus, reflection, generated
code, configuration), find where the link is made (the registration, the subscription, the generator
input) and say so in the brief. Do not guess the target by its name.

## 5. Trace one flow end to end

Pick the main flow and follow it hop by hop, reading each file at the ref:

1. The control the user touches (a button label you saw on screen) and its handler.
2. The call it makes: method and path, or message and topic.
3. The server entry that receives exactly that path or message.
4. The rules on the way: validation, permission, calculation. Note each limit with its number.
5. The write: what is stored, where, in which state.
6. The side effects: events, jobs, other services.
7. The answer back and what the screen shows.

Write each hop as a row: `repo:path:line`, symbol, the one idea it adds, and its evidence label. Keep
notes of dead ends too, so you do not search the same place twice. Then trace the second flow (another
role, the error path, the async part) the same way. Two well-traced flows beat ten skimmed ones.

## 6. Prove it is live, and try to prove yourself wrong

Code you can read is not always code that runs. For every hop in the story:

- **Find where it is wired.** The route table, the dependency injection registration, the message
  subscription, the scheduler entry, the CLI command, the event handler list. No registration found
  means "not proven live", whatever the name says.
- **Find one real caller** up to an entry point, with `git grep -n -w '<symbol>' <ref>` across all repos.
  A function nobody calls is dead code; leave it out of the video, or name it as a trap.
- **Find both ends of every hop between services.** The client call and the route that receives
  exactly that method and path; the producer of a topic and its consumer's subscription, with the
  topic name read from the config of the run's environment, never guessed; the writer and every
  reader of a table (search all repos for the table name: a shared database is a hidden link).
  Contracts (OpenAPI, protobuf, AsyncAPI) are maps; confirm the code matches them.
- **Read the flags and the settings for the run's environment**, including overrides. A path behind
  a flag that is off in that environment does not run there.
- **Look for what would prove you wrong**: other callers of the same function, middleware or filters
  on the route, async consumers, retries, dead-letter queues, scheduled jobs that write the same data,
  a newer `v2` beside the code you found. Try to disprove the three claims the video depends on most.
  Write down what you checked.

## 7. Run it when it is safe

Reading misses what is decided at run time: configuration, reflection, generated code, what a test
really asserts. When the project instructions allow it, and only on this computer:

- Run the unit or integration tests on the path, and confirm they ran (not skipped, not disabled, not
  filtered out). A passing test that covers a rule is the strongest evidence there is.
- Run the CLI, call the local API, or read the local app's logs while you walk the flow (the screenshot
  pass of `SKILL.md` step 3 is a good moment). Note what you saw: it becomes `RUN` evidence and often
  a `terminal` scene.
- Never run anything against a shared system to learn the feature, and never change shared data.
  Use a scratch copy when the project rules say so.

## 8. Map the system

The video shows the big picture before the code (`references/kt-design.md`), so the brief needs it as
data, every part with evidence:

- **The parts** the feature crosses, at most about 9: each service, app, database, queue or topic,
  scheduled job and outside provider, with a one-line job in plain words ("takes and stores orders").
  Name them the way the team does (the `## Services` table of the instructions first).
- **How they talk:** for each connection, who calls whom, how (HTTP and the path, a topic and its name,
  SQL and the table), sync or async, and the evidence for both ends.
- **The journey:** the main flow as numbered steps on those parts, with the real data that travels
  (the fields that matter, from the code: `{ orderId, amount }`), and what is stored after each write.
- **States:** the status values of the main record and what moves it from one to the next, with the
  `file:line` of each move.
- **Boundaries:** what is inside the team's system and what is outside (a payment provider, an email
  service), and which parts run together.
- **The failure that matters:** a timeout, a retry, a duplicate, and where the code handles it.

## 9. What a newcomer must know

- **Rules and limits** with their numbers ("at most 10 working days", "TTL 3600 s"), each with `file:line`.
- **Who may do what**: roles and permission checks.
- **What goes wrong**: errors, their messages on screen, retries, timeouts, partial failures.
- **Settings** that change behaviour between environments.
- **Why it is built this way**: the decisions behind the shape (a queue instead of a direct call, a
  status instead of a delete), from ADRs, design notes, pull requests and commit messages. Newcomers
  name missing rationale as one of their biggest problems, and it is the part only a coworker usually
  knows. Label it with its source; when you cannot find a reason, say "not documented", never invent one.
- **Traps**: bug-fix commits, `TODO`, `FIXME` and `HACK` comments near the feature, tests named after
  bugs, and every stale doc you found (section 2). These make the best "watch out" scenes.
- **How to test and debug it**: the tests to run, test data, logs or metrics the code writes.
- **Where to change common things**: "a new rule goes in X", "a new field needs A, B and C".

## 10. Grade every fact

Keep a claims ledger in the brief. Every fact gets one label:

| Label | Means | In the video |
|---|---|---|
| `RUN` | Seen while running: a test that passed, a command's output, a log line | Say it as fact |
| `CODE` | Read in the code at the ref, with where it is wired and one caller found | Say it as fact |
| `DOC-ONLY` | Only in docs, comments, names, commit messages or tickets | Never as fact. Put it in Open questions, or say "the design note says ... but the code does not show it" |
| `CONFLICT` | The code or a run says something else than a doc | Teach the code. Name the stale doc in Traps; it can be a "watch out" scene |
| `UNKNOWN` | Not checked yet | Never in the video |

- Rate the source and the claim apart: a trusted wiki can still carry a claim nobody confirmed.
- **Your own notes and summaries are claims too.** Before a fact goes into the storyboard, read its
  `file:line` again at the ref (`git -C <repo> show <ref>:./<path> | cat -n`). Line ranges come from
  the ref, never from the working tree.
- Cross-check each key rule in a second place when there is one: a test, the error message on screen,
  the contract. During the screenshot pass, compare labels, messages and step order with the code. The
  screen wins for what the user sees; the code wins for what happens.

## 11. Write `<run>/1-research/brief.md`

```markdown
# <Feature>: brief
**In one sentence:** ...
**Audience and goal:** QA, so they can test it end to end.
**Read first:** docs/refunds/ (the refund rules), https://wiki.acme.example/refunds (skipped: needs a
login). Code only: no.
**Hypotheses:** H1 the refund is sent at once (rejected: queued, see step 5). H2 ... (confirmed).

## Flows (Part A)
1. <Role> on <screen>: step, step, step. Result.

## The system (for the map scenes)
| Part | Kind | Its job, in plain words | Evidence |
|---|---|---|---|
| Orders API | service | Takes and stores orders, sends refunds | api:src/main.ts:12 (routes) |

| # | From | To | How | Sync? | What travels | Evidence (both ends) |
|---|---|---|---|---|---|---|
| 2 | Shop | Orders API | POST /refunds | sync | { orderId, amount } | web:src/api.ts:40, api:src/refunds/routes.ts:8 |

States: PENDING -> SENT -> DONE, or FAILED (api:src/refunds/refund.ts:30-61).
Boundaries: inside Acme: Shop, Orders API, Postgres, the refund topic. Outside: the payment provider.

## Rules and limits
| Rule | Value | Where | Label |
|---|---|---|---|

## Code path (Part B)
| # | Where (repo:path:line) | Symbol | The idea | Wired at | Label |
|---|---|---|---|---|---|

## Why it is built this way
## Data, side effects, settings
## What goes wrong
## Traps and history (stale docs found go here)
## How to test and debug
## Writes a recording would do
## Claims checked against being wrong
## Not covered (and why)
## Open questions (every DOC-ONLY and UNKNOWN fact)
```

## 12. Keep the scope a person can hold

A KT video is a map, not an encyclopedia. Pick the three to five things the audience must leave
with; everything else goes to "Not covered" in the brief and the storyboard. A large feature becomes
several chapters, or several videos with one storyboard each.

## Red flags: the fact is not verified yet

- Its only source is a comment, a doc, a diagram, a commit message or your own earlier note.
- No registration and no caller were found.
- It sits behind a flag or a setting you have not read for the run's environment.
- Only one side of a call, a topic or a table was found.
- The doc is older than its code, or a name in it no longer resolves.
- The test that "proves" it is skipped, disabled or never runs.
- A name says "old", "legacy", "v1", "deprecated" or "temporary".
