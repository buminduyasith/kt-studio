package overdue

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"
	"time"
)

var testNow = time.Date(2026, 10, 14, 2, 15, 0, 0, time.UTC)

type fakeStore struct {
	loans   map[string]Loan
	failOn  string
	updates int
}

func (f *fakeStore) OpenLoans(context.Context) ([]Loan, error) {
	var out []Loan
	for _, l := range f.loans {
		out = append(out, l)
	}
	return out, nil
}

func (f *fakeStore) MarkOverdue(_ context.Context, id string, fine int64) error {
	if id == f.failOn {
		return errors.New("db unavailable")
	}
	l := f.loans[id]
	l.Status, l.FineCents = StatusOverdue, fine
	f.loans[id] = l
	f.updates++
	return nil
}

type fakeNotifier struct {
	sent []Reminder
	err  error
}

func (f *fakeNotifier) SendReminder(_ context.Context, r Reminder) error {
	if f.err != nil {
		return f.err
	}
	f.sent = append(f.sent, r)
	return nil
}

type fakeRunLog struct{ days map[string]Summary }

func (f *fakeRunLog) Completed(_ context.Context, d string) (bool, error) {
	_, ok := f.days[d]
	return ok, nil
}

func (f *fakeRunLog) MarkCompleted(_ context.Context, d string, s Summary) error {
	f.days[d] = s
	return nil
}

func loanDue(id string, daysAgo int) Loan {
	return Loan{ID: id, MemberID: "M-1", ItemTitle: "Book " + id, DueAt: testNow.AddDate(0, 0, -daysAgo), Status: StatusActive}
}

func newJob(store *fakeStore, n *fakeNotifier) (*Job, *fakeRunLog) {
	rl := &fakeRunLog{days: map[string]Summary{}}
	return &Job{
		Store: store, Notifier: n, RunLog: rl,
		Now: func() time.Time { return testNow },
		Log: slog.New(slog.NewTextHandler(io.Discard, nil)),
	}, rl
}

func TestRunMarksOverdueAndComputesFine(t *testing.T) {
	store := &fakeStore{loans: map[string]Loan{
		"on-time": loanDue("on-time", -3),
		"late":    loanDue("late", 5),
		"capped":  loanDue("capped", 90),
	}}
	job, _ := newJob(store, &fakeNotifier{})

	s, err := job.Run(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if got := store.loans["on-time"].Status; got != StatusActive {
		t.Errorf("on-time loan status = %s, want ACTIVE", got)
	}
	if l := store.loans["late"]; l.Status != StatusOverdue || l.FineCents != 75 {
		t.Errorf("late loan = %s/%d, want OVERDUE/75", l.Status, l.FineCents)
	}
	if got := store.loans["capped"].FineCents; got != MaxFinePerItemCents {
		t.Errorf("capped fine = %d, want %d", got, MaxFinePerItemCents)
	}
	if s.MarkedOverdue != 2 || s.Scanned != 3 {
		t.Errorf("summary = %+v, want 3 scanned / 2 marked", s)
	}
}

func TestRunIsIdempotentPerDay(t *testing.T) {
	store := &fakeStore{loans: map[string]Loan{"late": loanDue("late", 3)}}
	n := &fakeNotifier{}
	job, _ := newJob(store, n)

	if _, err := job.Run(context.Background()); err != nil {
		t.Fatal(err)
	}
	second, err := job.Run(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if !second.Skipped {
		t.Error("second run on the same day should be skipped")
	}
	if len(n.sent) != 1 || store.updates != 1 {
		t.Errorf("reminders=%d updates=%d, want 1 and 1", len(n.sent), store.updates)
	}
}

func TestRemindersOnlyOnScheduledDays(t *testing.T) {
	store := &fakeStore{loans: map[string]Loan{
		"day3": loanDue("day3", 3),
		"day4": loanDue("day4", 4),
	}}
	n := &fakeNotifier{}
	job, _ := newJob(store, n)
	if _, err := job.Run(context.Background()); err != nil {
		t.Fatal(err)
	}
	if len(n.sent) != 1 || n.sent[0].LoanID != "day3" || n.sent[0].FineCents != 25 {
		t.Fatalf("sent = %+v, want one reminder for day3 with 25 cents", n.sent)
	}
}

func TestNotifierFailureStillCompletesDay(t *testing.T) {
	store := &fakeStore{loans: map[string]Loan{"late": loanDue("late", 1)}}
	job, rl := newJob(store, &fakeNotifier{err: errors.New("smtp timeout")})

	s, err := job.Run(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if s.ReminderFailures != 1 {
		t.Errorf("ReminderFailures = %d, want 1", s.ReminderFailures)
	}
	if _, ok := rl.days["2026-10-14"]; !ok {
		t.Error("day should be marked complete despite reminder failure")
	}
}

func TestStoreFailureLeavesDayOpenForRetry(t *testing.T) {
	store := &fakeStore{loans: map[string]Loan{"late": loanDue("late", 4)}, failOn: "late"}
	job, rl := newJob(store, &fakeNotifier{})

	if _, err := job.Run(context.Background()); err == nil {
		t.Fatal("expected an error")
	}
	if len(rl.days) != 0 {
		t.Error("run log must not be written when the store update fails")
	}
}
