package loans

import "time"

// Fine rules. All money is held in integer cents so we never round floats.
//
// The overdue worker keeps its own copy of these numbers in
// worker/internal/overdue/job.go. Change both places together.
const (
	// FinePerDayCents is charged for every late day after the grace period.
	FinePerDayCents int64 = 25

	// GraceDays is how many late days are forgiven before fines start.
	GraceDays = 2

	// MaxFinePerItemCents caps the fine charged for a single loan.
	// FIXME(LIB-412): circulation asked us to re-check this cap against the
	// published fines policy before the next term starts.
	MaxFinePerItemCents int64 = 1500

	// BorrowBlockThresholdCents: a member who owes MORE than this amount
	// cannot borrow until they pay down their balance.
	BorrowBlockThresholdCents int64 = 1000
)

const day = 24 * time.Hour

// DaysLate returns the number of whole calendar days (UTC) between the due
// date and asOf. Returning an item any time on its due date is not late.
func DaysLate(due, asOf time.Time) int {
	dueDay := due.UTC().Truncate(day)
	asOfDay := asOf.UTC().Truncate(day)
	if !asOfDay.After(dueDay) {
		return 0
	}
	return int(asOfDay.Sub(dueDay) / day)
}

// FineFor returns the fine in cents for a loan due at due and returned (or
// assessed) at asOf: 25 cents per day after a 2-day grace period, capped at
// MaxFinePerItemCents.
func FineFor(due, asOf time.Time) int64 {
	chargeable := DaysLate(due, asOf) - GraceDays
	if chargeable <= 0 {
		return 0
	}
	fine := int64(chargeable) * FinePerDayCents
	if fine > MaxFinePerItemCents {
		return MaxFinePerItemCents
	}
	return fine
}
