// Package loans holds the circulation rules: who may borrow, for how long,
// renewals, returns and the fines that result from late returns.
package loans

import (
	"errors"
	"fmt"
	"sync"
	"time"
)

// Loan periods and limits agreed with the circulation desk.
const (
	StandardLoanDays   = 21
	NewReleaseLoanDays = 7
	MaxActiveLoans     = 5
	MaxRenewals        = 2
)

// Status is the lifecycle state of a loan.
//
//	ACTIVE -> RETURNED
//	ACTIVE -> OVERDUE -> RETURNED
//
// OVERDUE is normally set by the nightly worker, not by this service.
type Status string

const (
	StatusActive   Status = "ACTIVE"
	StatusOverdue  Status = "OVERDUE"
	StatusReturned Status = "RETURNED"
)

var allowedTransitions = map[Status][]Status{
	StatusActive:  {StatusOverdue, StatusReturned},
	StatusOverdue: {StatusReturned},
}

// CanTransition reports whether a loan may move from one status to another.
func CanTransition(from, to Status) bool {
	for _, s := range allowedTransitions[from] {
		if s == to {
			return true
		}
	}
	return false
}

var (
	ErrNotFound          = errors.New("not found")
	ErrLoanLimitReached  = errors.New("member already has the maximum number of active loans")
	ErrFinesOutstanding  = errors.New("member owes more than the borrowing threshold in fines")
	ErrItemUnavailable   = errors.New("item is already on loan")
	ErrItemReserved      = errors.New("item is reserved by another member")
	ErrRenewalLimit      = errors.New("loan has already been renewed the maximum number of times")
	ErrLoanOverdue       = errors.New("overdue loans cannot be renewed")
	ErrInvalidTransition = errors.New("invalid loan status transition")
	ErrInvalidAmount     = errors.New("payment amount must be positive and not exceed the balance")
)

// Member is a library card holder.
type Member struct {
	ID               string
	Name             string
	UnpaidFinesCents int64
}

// Item is a single physical copy that can be lent.
type Item struct {
	ID         string
	Title      string
	NewRelease bool
	// ReservedBy is the member ID holding a reservation, or "" if none.
	ReservedBy string
}

// Loan records one item lent to one member.
type Loan struct {
	ID         string
	MemberID   string
	ItemID     string
	BorrowedAt time.Time
	DueAt      time.Time
	ReturnedAt *time.Time
	Status     Status
	Renewals   int
	FineCents  int64
}

// Repository is the storage the service needs. internal/store provides an
// in-memory implementation; production uses Postgres behind the same shape.
type Repository interface {
	Member(id string) (Member, error)
	SaveMember(m Member) error
	Item(id string) (Item, error)
	Loan(id string) (Loan, error)
	CreateLoan(l Loan) (Loan, error)
	SaveLoan(l Loan) error
	LoansByMember(memberID string) ([]Loan, error)
	// OpenLoanForItem returns the ACTIVE or OVERDUE loan for an item, if any.
	OpenLoanForItem(itemID string) (Loan, bool, error)
}

// Service applies the circulation rules on top of a Repository.
type Service struct {
	repo Repository
	now  func() time.Time
	// mu serialises check-then-write sequences (e.g. loan limit checks).
	mu sync.Mutex
}

// NewService builds a Service. Pass time.Now in production; tests pass a
// fixed clock.
func NewService(repo Repository, now func() time.Time) *Service {
	return &Service{repo: repo, now: now}
}

// LoanPeriod returns how long an item may be borrowed for.
func LoanPeriod(it Item) time.Duration {
	if it.NewRelease {
		return NewReleaseLoanDays * day
	}
	return StandardLoanDays * day
}

// Borrow lends an item to a member if every circulation rule allows it.
func (s *Service) Borrow(memberID, itemID string) (Loan, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	member, err := s.repo.Member(memberID)
	if err != nil {
		return Loan{}, err
	}
	if member.UnpaidFinesCents > BorrowBlockThresholdCents {
		return Loan{}, ErrFinesOutstanding
	}

	history, err := s.repo.LoansByMember(memberID)
	if err != nil {
		return Loan{}, err
	}
	open := 0
	for _, l := range history {
		if l.Status != StatusReturned {
			open++ // overdue loans count towards the limit too
		}
	}
	if open >= MaxActiveLoans {
		return Loan{}, ErrLoanLimitReached
	}

	item, err := s.repo.Item(itemID)
	if err != nil {
		return Loan{}, err
	}
	if item.ReservedBy != "" && item.ReservedBy != memberID {
		return Loan{}, ErrItemReserved
	}
	if _, onLoan, err := s.repo.OpenLoanForItem(itemID); err != nil {
		return Loan{}, err
	} else if onLoan {
		return Loan{}, ErrItemUnavailable
	}

	now := s.now()
	return s.repo.CreateLoan(Loan{
		MemberID:   memberID,
		ItemID:     itemID,
		BorrowedAt: now,
		DueAt:      now.Add(LoanPeriod(item)),
		Status:     StatusActive,
	})
}

// Renew extends a loan by a fresh loan period counted from today. A loan can
// be renewed MaxRenewals times, never once it is late, and never while
// another member has the item reserved.
func (s *Service) Renew(loanID string) (Loan, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	l, err := s.repo.Loan(loanID)
	if err != nil {
		return Loan{}, err
	}
	now := s.now()
	switch {
	case l.Status == StatusReturned:
		return Loan{}, ErrInvalidTransition
	case l.Status == StatusOverdue || DaysLate(l.DueAt, now) > 0:
		return Loan{}, ErrLoanOverdue
	case l.Renewals >= MaxRenewals:
		return Loan{}, ErrRenewalLimit
	}
	item, err := s.repo.Item(l.ItemID)
	if err != nil {
		return Loan{}, err
	}
	if item.ReservedBy != "" && item.ReservedBy != l.MemberID {
		return Loan{}, ErrItemReserved
	}

	l.Renewals++
	l.DueAt = now.Add(LoanPeriod(item))
	return l, s.repo.SaveLoan(l)
}

// Return closes a loan and charges any fine to the member's balance.
func (s *Service) Return(loanID string) (Loan, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	l, err := s.repo.Loan(loanID)
	if err != nil {
		return Loan{}, err
	}
	if !CanTransition(l.Status, StatusReturned) {
		return Loan{}, fmt.Errorf("%w: %s -> %s", ErrInvalidTransition, l.Status, StatusReturned)
	}
	member, err := s.repo.Member(l.MemberID)
	if err != nil {
		return Loan{}, err
	}

	now := s.now()
	l.ReturnedAt = &now
	l.Status = StatusReturned
	// The worker may have stored a running estimate; the final fine is
	// always recomputed from the actual return time.
	l.FineCents = FineFor(l.DueAt, now)
	if err := s.repo.SaveLoan(l); err != nil {
		return Loan{}, err
	}
	if l.FineCents > 0 {
		member.UnpaidFinesCents += l.FineCents
		if err := s.repo.SaveMember(member); err != nil {
			return Loan{}, err
		}
	}
	return l, nil
}

// MemberLoans lists every loan a member has had, newest first.
func (s *Service) MemberLoans(memberID string) ([]Loan, error) {
	if _, err := s.repo.Member(memberID); err != nil {
		return nil, err
	}
	return s.repo.LoansByMember(memberID)
}

// PayFines records a payment against a member's fine balance. Partial
// payments are allowed; overpayments are rejected.
func (s *Service) PayFines(memberID string, amountCents int64) (Member, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	member, err := s.repo.Member(memberID)
	if err != nil {
		return Member{}, err
	}
	if amountCents <= 0 || amountCents > member.UnpaidFinesCents {
		return Member{}, ErrInvalidAmount
	}
	member.UnpaidFinesCents -= amountCents
	return member, s.repo.SaveMember(member)
}
