# Library Loans

Circulation backend for a small public library: lending items to members,
renewals, returns, overdue tracking and fines.

The system is two independently deployed Go services that share one loans
database (in this sample each uses an in-memory store instead).

| Folder    | What it is |
|-----------|------------|
| `api/`    | HTTP service used by the circulation desk and the member web app. Owns the borrowing, renewal, return and fine-payment rules. |
| `worker/` | Nightly overdue job (cron, 02:15 UTC). Marks late loans `OVERDUE`, refreshes the accrued fine and emails reminders. Safe to re-run: it records one run per day. |
| `docs/`   | `fines-policy.md`, the policy as written by Circulation Services. |

Both are standard-library-only Go modules (Go 1.22+).

## Business rules at a glance

| Rule | Value | Where in code |
|------|-------|---------------|
| Loan period | 21 days, 7 for new releases | `api/internal/loans/service.go` |
| Active loans per member | 5 | `api/internal/loans/service.go` |
| Renewals | 2, not if reserved by someone else, not once late | `api/internal/loans/service.go` |
| Borrowing blocked | unpaid fines over $10.00 | `api/internal/loans/fines.go` |
| Fine | $0.25/day after a 2-day grace period | `api/internal/loans/fines.go`, `worker/internal/overdue/job.go` |
| Fine cap | per item, see `MaxFinePerItemCents` | same as above |

All money is stored as integer cents. Loan states:

```
ACTIVE -> RETURNED
ACTIVE -> OVERDUE -> RETURNED
```

The fine rules exist twice (api and worker) because the modules do not share
code. The API always recomputes the final fine at return time; the worker's
figure is only a running estimate shown to members.

## Running

```sh
# API on :8080 (override with PORT)
cd api
go run ./cmd/api
go test ./...

curl -XPOST localhost:8080/loans -d '{"member_id":"M-100","item_id":"I-2001"}'
curl localhost:8080/members/M-100/loans
curl -XPOST localhost:8080/loans/L-0001/renew
curl -XPOST localhost:8080/loans/L-0001/return
curl -XPOST localhost:8080/members/M-101/fines/payments -d '{"amount_cents":500}'

# Overdue job, one run against demo data
cd ../worker
go run ./cmd/worker
go test ./...
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/loans` | Borrow an item |
| POST | `/loans/{id}/renew` | Renew a loan |
| POST | `/loans/{id}/return` | Return an item; charges any fine |
| GET  | `/members/{id}/loans` | A member's loans, newest first |
| POST | `/members/{id}/fines/payments` | Pay part or all of a fine balance |

Rule violations return `409 Conflict` with an `error` message; unknown IDs
return `404`.
