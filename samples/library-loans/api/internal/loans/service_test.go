package loans_test

import (
	"errors"
	"fmt"
	"testing"
	"time"

	"example.com/library-loans/api/internal/loans"
	"example.com/library-loans/api/internal/store"
)

// clock is a controllable time source for tests.
type clock struct{ t time.Time }

func (c *clock) Now() time.Time           { return c.t }
func (c *clock) advanceDays(n int)        { c.t = c.t.AddDate(0, 0, n) }
func newClock() *clock                    { return &clock{t: time.Date(2026, 9, 1, 10, 0, 0, 0, time.UTC)} }
func seedItem(r *store.Memory, id string) { r.AddItem(loans.Item{ID: id, Title: "Item " + id}) }

func setup(t *testing.T) (*loans.Service, *store.Memory, *clock) {
	t.Helper()
	repo := store.NewMemory()
	clk := newClock()
	_ = repo.SaveMember(loans.Member{ID: "M-1", Name: "Test Member"})
	return loans.NewService(repo, clk.Now), repo, clk
}

func TestBorrowSetsDueDateByItemType(t *testing.T) {
	svc, repo, clk := setup(t)
	seedItem(repo, "I-1")
	repo.AddItem(loans.Item{ID: "I-NEW", Title: "New release", NewRelease: true})

	std, err := svc.Borrow("M-1", "I-1")
	if err != nil {
		t.Fatal(err)
	}
	if want := clk.Now().AddDate(0, 0, 21); !std.DueAt.Equal(want) {
		t.Errorf("standard due = %v, want %v", std.DueAt, want)
	}
	nr, err := svc.Borrow("M-1", "I-NEW")
	if err != nil {
		t.Fatal(err)
	}
	if want := clk.Now().AddDate(0, 0, 7); !nr.DueAt.Equal(want) {
		t.Errorf("new release due = %v, want %v", nr.DueAt, want)
	}
	if std.Status != loans.StatusActive {
		t.Errorf("status = %s, want ACTIVE", std.Status)
	}
}

func TestBorrowRejectsSixthActiveLoan(t *testing.T) {
	svc, repo, _ := setup(t)
	for i := 1; i <= 6; i++ {
		seedItem(repo, fmt.Sprintf("I-%d", i))
	}
	for i := 1; i <= loans.MaxActiveLoans; i++ {
		if _, err := svc.Borrow("M-1", fmt.Sprintf("I-%d", i)); err != nil {
			t.Fatalf("loan %d: %v", i, err)
		}
	}
	if _, err := svc.Borrow("M-1", "I-6"); !errors.Is(err, loans.ErrLoanLimitReached) {
		t.Fatalf("6th loan err = %v, want ErrLoanLimitReached", err)
	}
}

func TestBorrowFineThresholdIsStrictlyGreaterThan(t *testing.T) {
	svc, repo, _ := setup(t)
	seedItem(repo, "I-1")
	seedItem(repo, "I-2")

	_ = repo.SaveMember(loans.Member{ID: "M-1", UnpaidFinesCents: 1000})
	if _, err := svc.Borrow("M-1", "I-1"); err != nil {
		t.Fatalf("owing exactly 10.00 should still borrow, got %v", err)
	}
	_ = repo.SaveMember(loans.Member{ID: "M-1", UnpaidFinesCents: 1001})
	if _, err := svc.Borrow("M-1", "I-2"); !errors.Is(err, loans.ErrFinesOutstanding) {
		t.Fatalf("owing 10.01 err = %v, want ErrFinesOutstanding", err)
	}
}

func TestReturnLateChargesFineToMember(t *testing.T) {
	svc, repo, clk := setup(t)
	seedItem(repo, "I-1")
	loan, _ := svc.Borrow("M-1", "I-1")

	clk.advanceDays(21 + 5) // 5 days late: 2 grace + 3 charged
	got, err := svc.Return(loan.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.Status != loans.StatusReturned || got.ReturnedAt == nil {
		t.Errorf("loan not closed: %+v", got)
	}
	if got.FineCents != 75 {
		t.Errorf("fine = %d, want 75", got.FineCents)
	}
	m, _ := repo.Member("M-1")
	if m.UnpaidFinesCents != 75 {
		t.Errorf("member balance = %d, want 75", m.UnpaidFinesCents)
	}
}

func TestReturnTwiceIsInvalidTransition(t *testing.T) {
	svc, repo, _ := setup(t)
	seedItem(repo, "I-1")
	loan, _ := svc.Borrow("M-1", "I-1")
	if _, err := svc.Return(loan.ID); err != nil {
		t.Fatal(err)
	}
	if _, err := svc.Return(loan.ID); !errors.Is(err, loans.ErrInvalidTransition) {
		t.Fatalf("err = %v, want ErrInvalidTransition", err)
	}
}

func TestRenewRules(t *testing.T) {
	svc, repo, clk := setup(t)
	seedItem(repo, "I-1")
	loan, _ := svc.Borrow("M-1", "I-1")

	for i := 1; i <= loans.MaxRenewals; i++ {
		clk.advanceDays(10)
		renewed, err := svc.Renew(loan.ID)
		if err != nil {
			t.Fatalf("renewal %d: %v", i, err)
		}
		if want := clk.Now().AddDate(0, 0, 21); !renewed.DueAt.Equal(want) {
			t.Errorf("renewal %d due = %v, want %v", i, renewed.DueAt, want)
		}
	}
	if _, err := svc.Renew(loan.ID); !errors.Is(err, loans.ErrRenewalLimit) {
		t.Fatalf("3rd renewal err = %v, want ErrRenewalLimit", err)
	}
}

func TestRenewBlockedByReservationOrLateness(t *testing.T) {
	svc, repo, clk := setup(t)
	seedItem(repo, "I-1")
	seedItem(repo, "I-2")
	reserved, _ := svc.Borrow("M-1", "I-1")
	late, _ := svc.Borrow("M-1", "I-2")

	repo.AddItem(loans.Item{ID: "I-1", ReservedBy: "M-9"})
	if _, err := svc.Renew(reserved.ID); !errors.Is(err, loans.ErrItemReserved) {
		t.Errorf("reserved renew err = %v, want ErrItemReserved", err)
	}
	clk.advanceDays(22)
	if _, err := svc.Renew(late.ID); !errors.Is(err, loans.ErrLoanOverdue) {
		t.Errorf("late renew err = %v, want ErrLoanOverdue", err)
	}
}

func TestPayFines(t *testing.T) {
	svc, repo, _ := setup(t)
	_ = repo.SaveMember(loans.Member{ID: "M-1", UnpaidFinesCents: 1250})

	m, err := svc.PayFines("M-1", 500)
	if err != nil || m.UnpaidFinesCents != 750 {
		t.Fatalf("after partial payment: balance=%d err=%v, want 750", m.UnpaidFinesCents, err)
	}
	for _, bad := range []int64{0, -100, 751} {
		if _, err := svc.PayFines("M-1", bad); !errors.Is(err, loans.ErrInvalidAmount) {
			t.Errorf("PayFines(%d) err = %v, want ErrInvalidAmount", bad, err)
		}
	}
}
