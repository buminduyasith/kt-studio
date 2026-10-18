# Smile Dental: front desk app (sample)

A small dental clinic system used to test KT Studio on a project with a **frontend and a backend in
two folders**. Receptionists log in, book appointments, check patients in and cancel visits.

| Folder | What it is | Stack |
|---|---|---|
| `frontend/` | The front desk web app: login, day schedule, new appointment form | Plain HTML, CSS and JavaScript modules, no build step |
| `backend/` | JSON API under `/api`, booking rules, SQLite storage, SMS outbox; also serves `frontend/` | Python 3.9+ standard library only |
| `docs/` | Booking rules as the clinic manager wrote them | Markdown |

## Run it

```bash
export CLINIC_TEST_PASSWORD=smile-demo   # in your own shell, before starting Claude Code
cd backend && python3 server.py
```

Open http://localhost:8040 and log in as `reception@smile.test` with the password you set.
`CLINIC_NOW=2026-10-19T08:00` pins the clinic clock (handy for demos and tests); `CLINIC_DB` sets the
database file (default `backend/clinic.db`, delete it to start fresh).

## Test it

```bash
cd backend && python3 -m unittest discover -s tests -v
```

## Make a KT video of it

The `.kt-studio/` folder here (`config.yml` and `instructions.md`) is ready for `/kt-studio:make`. Start the app, then:

```
/kt-studio:make appointment-booking
/kt-studio:make appointment-booking "QA audience, focus on the booking rules, max 5 minutes"
```
