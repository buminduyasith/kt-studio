# Researching a feature (any language, any stack)

**Contents:** 1. Frame the job (5 minutes) · 2. Read what people wrote first · 3. Find the footprint: search by every name · 4. Map the layers · 5. Trace one flow end to end · 6. Pull out what a newcomer must know · 7. Verify every fact · 8. Write `<run>/1-research/brief.md` · Flows (Part A) · Rules and limits · Code path (Part B) · Data, side effects, settings · What goes wrong · Traps and history · How to test and debug · Writes a recording would do · Not covered (and why) · Open questions · 9. Keep the scope a person can hold

The goal is a brief that a stranger could trust: what the feature is for, how people use it, the rules
it enforces, how it works end to end, what goes wrong, and how to change and test it. Every fact is
read from the code at each repo's `ref` and cited as `repo:path:line`.

Work from the outside in: what people wrote, then what users see, then the code that runs. Never
start from guesses about the framework. Find the entry point the user touches and follow the calls.

## 1. Frame the job (5 minutes)

- Say the feature in one sentence, in the user's words.
- Name the audience and what they must be able to do after watching (see `references/kt-design.md`):
  QA tests it, a developer changes it, a scrum master explains it, support diagnoses it.
- List the request's limits: parts to skip, length, focus, and any depth words ("high level", "deep
  dive", "explain X in detail").
- After step 5, size the footprint and pick the depth with `references/kt-design.md` (section 1b). A
  deep dive traces more: every flow the request names, the async and failure paths, how each
  indirect link is wired, and the tests behind each rule. An overview stops at the main flow.

## 2. Read what people wrote first

In this order, skimming for the feature's names, rules and numbers:

1. The `knowledge` docs from the config (`.kt-studio/config.yml`).
2. READMEs at each repo root and inside the feature's folders; `docs/`, ADRs, design notes, runbooks.
3. Contracts: OpenAPI or Swagger files, GraphQL schemas, `.proto` files, AsyncAPI, JSON schemas.
4. Words users see: translation files (`en.json`, `messages.properties`, `.po`, `.resx`, `strings.xml`).
5. Tests: their names list the behaviours ("rejects a refund larger than the order").
6. History: commits, merge requests and ticket keys that mention the feature.

Docs are claims. Check each one in the code; when they disagree, the code wins and the gap becomes a
question in the brief.

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

Write each hop as a row: `repo:path:line`, symbol, and the one idea it adds. Then trace the second
flow (another role, the error path, the async part) the same way. Two well-traced flows beat ten
skimmed ones.

## 6. Pull out what a newcomer must know

- **Rules and limits** with their numbers ("at most 10 working days", "TTL 3600 s"), each with `file:line`.
- **States**: the status values and what moves a record from one to the next.
- **Who may do what**: roles and permission checks.
- **What goes wrong**: errors, their messages on screen, retries, timeouts, partial failures.
- **Settings** that change behaviour between environments.
- **Traps**: read bug-fix commits, `TODO`, `FIXME` and `HACK` comments near the feature, and tests
  named after bugs. These make the best "watch out" scenes.
- **How to test and debug it**: the tests to run, test data, logs or metrics the code writes.
- **Where to change common things**: "a new rule goes in X", "a new field needs A, B and C".

## 7. Verify every fact

- Read every cited file with line numbers at the ref: `git -C <repo> show <ref>:./<path> | cat -n`.
  Line ranges must come from the ref, never from the working tree.
- Cross-check each rule in a second place when there is one: a test, the error message on screen,
  the API contract.
- Run nothing against shared systems to learn the feature. Reading code, docs and git is enough;
  running tests or the app only when the project instructions allow it, and only locally.
- During the screenshot pass, compare labels, messages and step order with the code. The screen wins
  for what the user sees; the code wins for what happens.

## 8. Write `<run>/1-research/brief.md`

```markdown
# <Feature>: brief
**In one sentence:** ...
**Audience and goal:** QA, so they can test it end to end.

## Flows (Part A)
1. <Role> on <screen>: step, step, step. Result.

## Rules and limits
| Rule | Value | Where |
|---|---|---|

## Code path (Part B)
| # | Where (repo:path:line) | Symbol | The idea |
|---|---|---|---|

## Data, side effects, settings
## What goes wrong
## Traps and history
## How to test and debug
## Writes a recording would do
## Not covered (and why)
## Open questions
```

## 9. Keep the scope a person can hold

A KT video is a map, not an encyclopedia. Pick the three to five things the audience must leave
with; everything else goes to "Not covered" in the brief and the storyboard. A large feature becomes
several chapters, or several videos with one storyboard each.
