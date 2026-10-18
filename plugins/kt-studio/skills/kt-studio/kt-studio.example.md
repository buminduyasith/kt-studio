# KT Studio: project instructions

<!--
.kt-studio/instructions.md: your own rules for KT Studio, your services and where each one runs.
/kt-studio:init writes it for you; edit it freely. Change this file, not the plugin.

How KT Studio uses it:
- It reads this file, and the `metadata` block of config.yml, at the start of every run.
- It looks up where your apps run in "## Addresses" first (then CLAUDE.md, the README and your docs). When
  it learns a new service, environment or address, it adds it here, so the next run does not have to ask.
  It never changes or deletes what you wrote.
- It runs "Before the run" first and "After the run" last, and follows every other section at the
  matching step. Your rules win over the plugin's defaults.
- They never relax the plugin's safety rules: it never logs in for you or types a password, it records
  nothing before the storyboard is approved, it asks before every recording that writes, and it always
  cleans up.
Delete a section you do not need. Keep each rule short.
-->

## Services

<!-- One row per service, in plain words: what it is for and what it talks to, not code. -->

| Service | What it is for | Talks to | Login |
| --- | --- | --- | --- |
| Shop | Where customers browse, pay and see their orders | Orders API | Company SSO |
| Admin | Where staff refund and cancel orders | Orders API | Company SSO, admin role |
| Orders API | Takes and stores orders, sends refunds to the payment provider | Postgres, payment provider | No screens |

## Addresses

<!-- Where each service runs: one column per environment (any names). Leave a cell empty where a
service does not run. Services with no screens can be left out. -->

| Service | local | dev | qa |
| --- | --- | --- | --- |
| Shop | http://localhost:3000 | https://dev.acme.example | https://qa.acme.example |
| Admin | http://localhost:3000/admin | https://dev.acme.example/admin | https://qa.acme.example/admin |

## Logging in

<!-- How people log in to each service in each environment. How: none, window (KT Studio opens a
browser window and you log in your usual way: SSO, 2FA, anything), or script (your team's own login
command: you run it, it saves a session file, KT Studio uses that file and never runs the command).
{env} is replaced with the environment. KT Studio follows this table exactly and never logs in for you. -->

| Service | Environment | How | The person runs | Session file |
| --- | --- | --- | --- | --- |
| Shop, Admin | local | none | | |
| Shop, Admin | dev, qa | script | `node tools/login.mjs {env}` | .auth-team/{env}.json |

- Use the QA test account, not your own (ask the team for it).

## Before the run

- When the request names no environment, use qa.
- Check that the site answers before starting.

## Before each take

- Reset the demo data so every take starts the same way.

## Screens and recording

- Use test records only; never show real customer data.

## After the run

- Deliver the video files with a one-line summary per part.
