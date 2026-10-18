// Package httpapi exposes the loans service over JSON/HTTP. It only
// translates requests and errors; every business rule lives in package loans.
package httpapi

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"time"

	"example.com/library-loans/api/internal/loans"
)

// Handler wires HTTP routes to a loans.Service.
type Handler struct {
	svc *loans.Service
	log *slog.Logger
}

func NewHandler(svc *loans.Service, log *slog.Logger) *Handler {
	return &Handler{svc: svc, log: log}
}

// Routes registers every endpoint using Go 1.22 method+path patterns.
func (h *Handler) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /loans", h.borrow)
	mux.HandleFunc("POST /loans/{id}/return", h.loanAction(h.svc.Return))
	mux.HandleFunc("POST /loans/{id}/renew", h.loanAction(h.svc.Renew))
	mux.HandleFunc("GET /members/{id}/loans", h.memberLoans)
	mux.HandleFunc("POST /members/{id}/fines/payments", h.payFines)
	return mux
}

type loanResponse struct {
	ID         string     `json:"id"`
	MemberID   string     `json:"member_id"`
	ItemID     string     `json:"item_id"`
	Status     string     `json:"status"`
	BorrowedAt time.Time  `json:"borrowed_at"`
	DueAt      time.Time  `json:"due_at"`
	ReturnedAt *time.Time `json:"returned_at,omitempty"`
	Renewals   int        `json:"renewals"`
	FineCents  int64      `json:"fine_cents"`
}

func toLoanResponse(l loans.Loan) loanResponse {
	return loanResponse{
		ID: l.ID, MemberID: l.MemberID, ItemID: l.ItemID, Status: string(l.Status),
		BorrowedAt: l.BorrowedAt, DueAt: l.DueAt, ReturnedAt: l.ReturnedAt,
		Renewals: l.Renewals, FineCents: l.FineCents,
	}
}

// POST /loans {"member_id": "M-100", "item_id": "I-2001"}
func (h *Handler) borrow(w http.ResponseWriter, r *http.Request) {
	var req struct {
		MemberID string `json:"member_id"`
		ItemID   string `json:"item_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.MemberID == "" || req.ItemID == "" {
		writeJSON(w, http.StatusBadRequest, errorBody("member_id and item_id are required"))
		return
	}
	loan, err := h.svc.Borrow(req.MemberID, req.ItemID)
	if err != nil {
		h.writeError(w, err)
		return
	}
	writeJSON(w, http.StatusCreated, toLoanResponse(loan))
}

// loanAction adapts a service call on one loan (Return, Renew) to
// POST /loans/{id}/<action>.
func (h *Handler) loanAction(fn func(loanID string) (loans.Loan, error)) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		loan, err := fn(r.PathValue("id"))
		if err != nil {
			h.writeError(w, err)
			return
		}
		writeJSON(w, http.StatusOK, toLoanResponse(loan))
	}
}

// GET /members/{id}/loans
func (h *Handler) memberLoans(w http.ResponseWriter, r *http.Request) {
	list, err := h.svc.MemberLoans(r.PathValue("id"))
	if err != nil {
		h.writeError(w, err)
		return
	}
	out := make([]loanResponse, 0, len(list))
	for _, l := range list {
		out = append(out, toLoanResponse(l))
	}
	writeJSON(w, http.StatusOK, out)
}

// POST /members/{id}/fines/payments {"amount_cents": 500}
func (h *Handler) payFines(w http.ResponseWriter, r *http.Request) {
	var req struct {
		AmountCents int64 `json:"amount_cents"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, errorBody("amount_cents is required"))
		return
	}
	member, err := h.svc.PayFines(r.PathValue("id"), req.AmountCents)
	if err != nil {
		h.writeError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"member_id":          member.ID,
		"unpaid_fines_cents": member.UnpaidFinesCents,
	})
}

// writeError maps domain errors to HTTP status codes. Rule violations are
// 409 Conflict so the desk UI can show the message to staff verbatim.
func (h *Handler) writeError(w http.ResponseWriter, err error) {
	status := http.StatusInternalServerError
	switch {
	case errors.Is(err, loans.ErrNotFound):
		status = http.StatusNotFound
	case errors.Is(err, loans.ErrInvalidAmount):
		status = http.StatusUnprocessableEntity
	case errors.Is(err, loans.ErrLoanLimitReached),
		errors.Is(err, loans.ErrFinesOutstanding),
		errors.Is(err, loans.ErrItemUnavailable),
		errors.Is(err, loans.ErrItemReserved),
		errors.Is(err, loans.ErrRenewalLimit),
		errors.Is(err, loans.ErrLoanOverdue),
		errors.Is(err, loans.ErrInvalidTransition):
		status = http.StatusConflict
	}
	if status == http.StatusInternalServerError {
		h.log.Error("request failed", "err", err)
		writeJSON(w, status, errorBody("internal error"))
		return
	}
	writeJSON(w, status, errorBody(err.Error()))
}

func errorBody(msg string) map[string]string { return map[string]string{"error": msg} }

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}
