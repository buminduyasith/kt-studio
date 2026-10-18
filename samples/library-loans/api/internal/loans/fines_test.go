package loans

import (
	"testing"
	"time"
)

func TestFineFor(t *testing.T) {
	due := time.Date(2026, 3, 10, 17, 0, 0, 0, time.UTC)
	after := func(days int) time.Time { return due.AddDate(0, 0, days) }

	tests := []struct {
		name string
		at   time.Time
		want int64
	}{
		{"returned early", after(-3), 0},
		{"returned late on the due date", due.Add(6 * time.Hour), 0},
		{"1 day late (next calendar day) is within grace", due.Add(8 * time.Hour), 0},
		{"2 days late is within grace", after(2), 0},
		{"3 days late charges one day", after(3), 25},
		{"10 days late", after(10), 200},
		{"cap reached at 62 days", after(62), 1500},
		{"never more than the cap", after(200), 1500},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := FineFor(due, tt.at); got != tt.want {
				t.Errorf("FineFor = %d cents, want %d", got, tt.want)
			}
		})
	}
}

func TestCanTransition(t *testing.T) {
	allowed := [][2]Status{{StatusActive, StatusOverdue}, {StatusActive, StatusReturned}, {StatusOverdue, StatusReturned}}
	denied := [][2]Status{{StatusOverdue, StatusActive}, {StatusReturned, StatusActive}, {StatusReturned, StatusReturned}}
	for _, p := range allowed {
		if !CanTransition(p[0], p[1]) {
			t.Errorf("%s -> %s should be allowed", p[0], p[1])
		}
	}
	for _, p := range denied {
		if CanTransition(p[0], p[1]) {
			t.Errorf("%s -> %s should be rejected", p[0], p[1])
		}
	}
}
