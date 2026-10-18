// Package store provides an in-memory loans.Repository used for local runs
// and tests. It is safe for concurrent use.
package store

import (
	"fmt"
	"sort"
	"sync"

	"example.com/library-loans/api/internal/loans"
)

// Memory keeps members, items and loans in maps guarded by a mutex.
type Memory struct {
	mu       sync.RWMutex
	members  map[string]loans.Member
	items    map[string]loans.Item
	loanByID map[string]loans.Loan
	nextID   int
}

var _ loans.Repository = (*Memory)(nil)

// NewMemory returns an empty store.
func NewMemory() *Memory {
	return &Memory{
		members:  map[string]loans.Member{},
		items:    map[string]loans.Item{},
		loanByID: map[string]loans.Loan{},
	}
}

// AddItem seeds the catalogue. Items are managed by the cataloguing system
// in production, so there is no API endpoint for this.
func (m *Memory) AddItem(it loans.Item) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.items[it.ID] = it
}

func (m *Memory) Member(id string) (loans.Member, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	mem, ok := m.members[id]
	if !ok {
		return loans.Member{}, fmt.Errorf("member %q: %w", id, loans.ErrNotFound)
	}
	return mem, nil
}

func (m *Memory) SaveMember(mem loans.Member) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.members[mem.ID] = mem
	return nil
}

func (m *Memory) Item(id string) (loans.Item, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	it, ok := m.items[id]
	if !ok {
		return loans.Item{}, fmt.Errorf("item %q: %w", id, loans.ErrNotFound)
	}
	return it, nil
}

func (m *Memory) Loan(id string) (loans.Loan, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	l, ok := m.loanByID[id]
	if !ok {
		return loans.Loan{}, fmt.Errorf("loan %q: %w", id, loans.ErrNotFound)
	}
	return l, nil
}

// CreateLoan assigns the next sequential ID (L-0001, L-0002, ...).
func (m *Memory) CreateLoan(l loans.Loan) (loans.Loan, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.nextID++
	l.ID = fmt.Sprintf("L-%04d", m.nextID)
	m.loanByID[l.ID] = l
	return l, nil
}

func (m *Memory) SaveLoan(l loans.Loan) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.loanByID[l.ID] = l
	return nil
}

// LoansByMember returns the member's loans, newest first.
func (m *Memory) LoansByMember(memberID string) ([]loans.Loan, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	var out []loans.Loan
	for _, l := range m.loanByID {
		if l.MemberID == memberID {
			out = append(out, l)
		}
	}
	sort.Slice(out, func(i, j int) bool {
		if !out[i].BorrowedAt.Equal(out[j].BorrowedAt) {
			return out[i].BorrowedAt.After(out[j].BorrowedAt)
		}
		return out[i].ID > out[j].ID
	})
	return out, nil
}

func (m *Memory) OpenLoanForItem(itemID string) (loans.Loan, bool, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	for _, l := range m.loanByID {
		if l.ItemID == itemID && l.Status != loans.StatusReturned {
			return l, true, nil
		}
	}
	return loans.Loan{}, false, nil
}
