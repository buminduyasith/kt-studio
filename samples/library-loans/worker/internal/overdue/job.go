// Package overdue implements the nightly overdue sweep: it marks late loans
// OVERDUE, refreshes their accrued fine and emails reminders.
//
// The job is safe to re-run: a RunLog entry per calendar day (UTC) makes a
// second run on the same day a no-op, and the store updates themselves are
// idempotent.
package overdue

import (
	"context"
	"fmt"
	"log/slog"
	"time"
)

// Fine rules. These mirror api/internal/loans/fines.go; the worker is built
// and deployed separately and does not import the api module.
const (
	FinePerDayCents     int64 = 25
	GraceDays                 = 2
	MaxFinePerItemCents int64 = 1500
)

const (
	StatusActive  = "ACTIVE"
	StatusOverdue = "OVERDUE"
)

// reminderDays lists the days-late on which a reminder is sent. Members
// asked for fewer emails, so we no longer send one every night.
var reminderDays = map[int]bool{1: true, 3: true, 7: true, 14: true, 30: true}

// Loan is the subset of loan data the job needs.
type Loan struct {
	ID        string
	MemberID  string
	ItemTitle string
	DueAt     time.Time
	Status    string
	FineCents int64
}

// LoanStore reads open loans and records overdue state.
type LoanStore interface {
	// OpenLoans returns loans in ACTIVE or OVERDUE status.
	OpenLoans(ctx context.Context) ([]Loan, error)
	// MarkOverdue sets status OVERDUE and stores the accrued fine estimate.
	MarkOverdue(ctx context.Context, loanID string, fineCents int64) error
}

// Reminder is the payload handed to the Notifier.
type Reminder struct {
	MemberID  string
	LoanID    string
	ItemTitle string
	DaysLate  int
	FineCents int64
}

// Notifier delivers a reminder to a member (email in production).
type Notifier interface {
	SendReminder(ctx context.Context, r Reminder) error
}

// RunLog remembers which days have already been processed.
type RunLog interface {
	Completed(ctx context.Context, day string) (bool, error)
	MarkCompleted(ctx context.Context, day string, s Summary) error
}

// Summary describes one run, and is stored in the RunLog.
type Summary struct {
	Day              string
	Skipped          bool
	Scanned          int
	MarkedOverdue    int
	RemindersSent    int
	ReminderFailures int
}

// Job is the nightly overdue sweep.
type Job struct {
	Store    LoanStore
	Notifier Notifier
	RunLog   RunLog
	Now      func() time.Time
	Log      *slog.Logger
}

// Run processes every open loan once per calendar day.
func (j *Job) Run(ctx context.Context) (Summary, error) {
	now := j.Now().UTC()
	s := Summary{Day: now.Format("2006-01-02")}

	done, err := j.RunLog.Completed(ctx, s.Day)
	if err != nil {
		return s, fmt.Errorf("read run log: %w", err)
	}
	if done {
		s.Skipped = true
		j.Log.Info("overdue run already completed today", "day", s.Day)
		return s, nil
	}

	open, err := j.Store.OpenLoans(ctx)
	if err != nil {
		return s, fmt.Errorf("load open loans: %w", err)
	}

	for _, l := range open {
		s.Scanned++
		late := daysLate(l.DueAt, now)
		if late == 0 {
			continue
		}
		fine := fineFor(l.DueAt, now)
		if l.Status != StatusOverdue || l.FineCents != fine {
			// A store failure aborts the run WITHOUT writing the run log,
			// so tomorrow's cron (or a manual re-run) picks it up again.
			if err := j.Store.MarkOverdue(ctx, l.ID, fine); err != nil {
				return s, fmt.Errorf("mark loan %s overdue: %w", l.ID, err)
			}
			if l.Status == StatusActive {
				s.MarkedOverdue++
			}
		}
		if !reminderDays[late] {
			continue
		}
		err := j.Notifier.SendReminder(ctx, Reminder{
			MemberID: l.MemberID, LoanID: l.ID, ItemTitle: l.ItemTitle,
			DaysLate: late, FineCents: fine,
		})
		if err != nil {
			// We prefer a missed reminder over a duplicate one, so a
			// notifier failure is logged and counted but does not
			// prevent the day from being marked complete.
			s.ReminderFailures++
			j.Log.Warn("reminder failed", "loan", l.ID, "err", err)
			continue
		}
		s.RemindersSent++
	}

	if err := j.RunLog.MarkCompleted(ctx, s.Day, s); err != nil {
		return s, fmt.Errorf("write run log: %w", err)
	}
	return s, nil
}

const day = 24 * time.Hour

func daysLate(due, asOf time.Time) int {
	dueDay, asOfDay := due.UTC().Truncate(day), asOf.UTC().Truncate(day)
	if !asOfDay.After(dueDay) {
		return 0
	}
	return int(asOfDay.Sub(dueDay) / day)
}

func fineFor(due, asOf time.Time) int64 {
	chargeable := daysLate(due, asOf) - GraceDays
	if chargeable <= 0 {
		return 0
	}
	return min(int64(chargeable)*FinePerDayCents, MaxFinePerItemCents)
}
