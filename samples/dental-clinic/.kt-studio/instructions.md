# KT Studio: project instructions

## Services

| Service | What it is for | Talks to | Login |
| --- | --- | --- | --- |
| Front desk app | Where receptionists see the day schedule and book visits | Clinic backend (same address, `/api`) | Staff user `reception@smile.test` |
| Clinic backend | Checks every booking rule, saves visits, queues reminder messages | SQLite file (`CLINIC_DB`) | Through the front desk app's login |

## Addresses

| Service | local |
| --- | --- |
| Front desk app | http://localhost:8040 |

## Logging in

| Service | Environment | How | The person runs | Session file |
| --- | --- | --- | --- | --- |
| Front desk app | local | window | | |

- Log in as `reception@smile.test` with the test password you set in `CLINIC_TEST_PASSWORD`. You type it
  in the window KT Studio opens; it never types or stores it.
- Signed-in text: `Log out` (set `KT_LOGGED_IN_TEXT=Log out` for `login.sh`).

## Before the run

- Use the local environment (the only one). If http://localhost:8040 does not answer, start
  it in the background with the clinic clock pinned to Monday 19 October 2026 08:00, so demos are
  repeatable (the person exports `CLINIC_TEST_PASSWORD` in their shell first):

  ```bash
  cd <root>/backend && CLINIC_NOW=2026-10-19T08:00 CLINIC_DB=<root>/.kt-studio/demo-clinic.db python3 server.py
  ```

  Wait until http://localhost:8040 answers.

## Before each take

- Start from a fresh demo database: stop the app, delete `.kt-studio/demo-clinic.db`, start the app
  again as above. The seeded staff user, dentists and patients come back on start.
- The app keeps logins in memory, so a restart logs everyone out: ask me to log in again in the window
  (see Logging in) before preflight.

## After the run

- Stop the app if this run started it.
