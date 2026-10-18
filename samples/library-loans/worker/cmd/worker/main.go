// Command worker runs the nightly overdue sweep once and exits. In
// production cron starts it at 02:15 UTC against the shared loans database;
// locally it runs against a small in-memory data set.
package main

import (
	"context"
	"log/slog"
	"os"
	"time"

	"example.com/library-loans/worker/internal/overdue"
)

func main() {
	log := slog.New(slog.NewTextHandler(os.Stdout, nil))
	today := time.Now().UTC()

	job := &overdue.Job{
		Store: &memoryStore{loans: []overdue.Loan{
			{ID: "L-0001", MemberID: "M-100", ItemTitle: "Braiding Sweetgrass", DueAt: today.AddDate(0, 0, 4), Status: overdue.StatusActive},
			{ID: "L-0002", MemberID: "M-100", ItemTitle: "Intermezzo", DueAt: today.AddDate(0, 0, -1), Status: overdue.StatusActive},
			{ID: "L-0003", MemberID: "M-101", ItemTitle: "The Left Hand of Darkness", DueAt: today.AddDate(0, 0, -7), Status: overdue.StatusOverdue, FineCents: 100},
		}},
		Notifier: logNotifier{log: log},
		RunLog:   memoryRunLog{},
		Now:      time.Now,
		Log:      log,
	}

	summary, err := job.Run(context.Background())
	if err != nil {
		log.Error("overdue run failed", "err", err)
		os.Exit(1)
	}
	log.Info("overdue run finished", "summary", summary)
}

// memoryStore stands in for the shared loans database.
type memoryStore struct{ loans []overdue.Loan }

func (m *memoryStore) OpenLoans(context.Context) ([]overdue.Loan, error) {
	return append([]overdue.Loan(nil), m.loans...), nil
}

func (m *memoryStore) MarkOverdue(_ context.Context, id string, fine int64) error {
	for i := range m.loans {
		if m.loans[i].ID == id {
			m.loans[i].Status, m.loans[i].FineCents = overdue.StatusOverdue, fine
		}
	}
	return nil
}

// logNotifier prints reminders instead of emailing them.
type logNotifier struct{ log *slog.Logger }

func (n logNotifier) SendReminder(_ context.Context, r overdue.Reminder) error {
	n.log.Info("reminder", "member", r.MemberID, "item", r.ItemTitle, "days_late", r.DaysLate, "fine_cents", r.FineCents)
	return nil
}

// memoryRunLog forgets everything on exit; production uses the overdue_runs table.
type memoryRunLog map[string]overdue.Summary

func (r memoryRunLog) Completed(_ context.Context, day string) (bool, error) {
	_, ok := r[day]
	return ok, nil
}

func (r memoryRunLog) MarkCompleted(_ context.Context, day string, s overdue.Summary) error {
	r[day] = s
	return nil
}
