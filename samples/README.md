# Samples

Small but realistic projects to try KT Studio on, and to test the plugin end to end before a release.
Each one stresses a different part of the skill: a web app with screens, services with no UI, a deep
dive, a short overview, several languages, and projects that are folders inside a bigger git repo.

| Sample | Stack | Folders | No UI? | What it tests |
|---|---|---|---|---|
| [`dental-clinic/`](dental-clinic/) | Plain JavaScript frontend, Python standard-library backend, SQLite | `frontend/`, `backend/`, `docs/` | Has a web UI with a local login | The full video: real screens (Part A), logged in by you in the window KT Studio opens, then a code tour (Part B) across two folders. Booking rules with numbers, a write at gate 2 |
| [`shop-checkout/`](shop-checkout/) | Java 17 Spring Boot, TypeScript Node, Kafka, Redis, Postgres | `order-service/`, `payment-gateway/`, `contracts/`, `docs/` | No UI | A deep dive: events, a webhook, retries, three layers of idempotency, a scheduled job, tickets in the code, doc/code gaps |
| [`library-loans/`](library-loans/) | Go 1.22, standard library | `api/`, `worker/`, `docs/` | No UI (HTTP API and a nightly job) | Two Go modules with duplicated rules, and a policy doc that disagrees with the code on purpose (the fine cap) |
| [`tiny-notes/`](tiny-notes/) | Rust, standard library | `src/` | No UI (a CLI) | A small codebase: the skill should keep the video short and high level, and show the tool in use with terminal scenes |

`dental-clinic`, `shop-checkout` and `tiny-notes` have the `.kt-studio/` folder (`config.yml` and
`instructions.md`) that `/kt-studio:init` wrote for them. `library-loans` has none, so you can try
`/kt-studio:init` from scratch.

## Try one

Open Claude Code in a sample folder (not the repo root), then:

```
/kt-studio:init
/kt-studio:make appointment-booking "developer new to the team"            # dental-clinic (start the app first: see its README)
/kt-studio:make payment-confirmation "deep dive for on-call, no screens"   # shop-checkout
/kt-studio:make notes-cli "quick high-level overview, keep it short"       # tiny-notes
/kt-studio:make overdue-fines "QA audience: every rule with its number"    # library-loans
```

Everything the plugin writes goes into the sample's `.kt-studio/` folder; git keeps only the
settings files and the answers (`learned.yml` and each feature's `feature.yml`) there. Delete those two
kinds of files after a test run, so the next test starts with no answers.

## Test the plugin before a release

Run at least the dental-clinic sample end to end (both parts, one joined file), and one sample with no
UI. A release is good when, for each run:

- `doctor: ready`, and setup ends with `npm audit: clean`
- the storyboard builds and its own snapshots (`tools/snap.mjs`) show no page errors
- `check_video.py` prints `PASS: no blinks` for every video
- `check_sync.py` prints `PASS: voice and picture in sync` (every action within 0.4 s of its word)
- the contact sheets match the storyboard scene by scene
- `cleanup.sh` prints `nothing running`

Record one project at a time on a computer: two takes at once share the CPU and slip out of sync.
