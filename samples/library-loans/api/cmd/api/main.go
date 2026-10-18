// Command api runs the library loans HTTP service.
//
//	PORT=8080 go run ./cmd/api
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	httpapi "example.com/library-loans/api/internal/http"
	"example.com/library-loans/api/internal/loans"
	"example.com/library-loans/api/internal/store"
)

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	repo := store.NewMemory()
	seed(repo)

	svc := loans.NewService(repo, time.Now)
	srv := &http.Server{
		Addr:              ":" + envOr("PORT", "8080"),
		Handler:           httpapi.NewHandler(svc, log).Routes(),
		ReadHeaderTimeout: 5 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		log.Info("listening", "addr", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("server stopped", "err", err)
			os.Exit(1)
		}
	}()

	<-ctx.Done()
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = srv.Shutdown(shutdownCtx)
	log.Info("shut down")
}

// seed loads a few demo members and items so the API is usable locally.
func seed(repo *store.Memory) {
	_ = repo.SaveMember(loans.Member{ID: "M-100", Name: "Ada Okafor"})
	_ = repo.SaveMember(loans.Member{ID: "M-101", Name: "Ravi Perera", UnpaidFinesCents: 1250})
	repo.AddItem(loans.Item{ID: "I-2001", Title: "The Left Hand of Darkness"})
	repo.AddItem(loans.Item{ID: "I-2002", Title: "Braiding Sweetgrass"})
	repo.AddItem(loans.Item{ID: "I-3001", Title: "Tomorrow, and Tomorrow, and Tomorrow", NewRelease: true})
	repo.AddItem(loans.Item{ID: "I-3002", Title: "Intermezzo", NewRelease: true, ReservedBy: "M-101"})
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
