// Chitragupt API Gateway — HTTP ↔ gRPC bridge.
//
// Exposes a REST/SSE API consumed by the frontend, and proxies requests to:
//   - Rust state machine (StateEngine gRPC, default :50051)
//   - Python AI orchestration (AiOrchestration gRPC, default :50052)
//
// Environment variables:
//
//	PORT               — HTTP listen port (default: 8080)
//	STATE_MACHINE_ADDR — Rust gRPC address  (default: localhost:50051)
//	ORCHESTRATION_ADDR — Python gRPC address (default: localhost:50052)
package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"

	"github.com/bc0de0/chitragupt/services/api-gateway/internal/gateway"
	"github.com/bc0de0/chitragupt/services/api-gateway/internal/orchestration"
	"github.com/bc0de0/chitragupt/services/api-gateway/internal/statemc"
)

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(log)

	// ── gRPC clients ──────────────────────────────────────────────────────────
	stateMachineAddr := env("STATE_MACHINE_ADDR", "localhost:50051")
	orchestrationAddr := env("ORCHESTRATION_ADDR", "localhost:50052")

	stateClient, err := statemc.NewClient(stateMachineAddr)
	if err != nil {
		slog.Error("failed to connect to state machine", "addr", stateMachineAddr, "err", err)
		os.Exit(1)
	}
	defer stateClient.Close()

	orchClient, err := orchestration.NewClient(orchestrationAddr)
	if err != nil {
		slog.Error("failed to connect to orchestration service", "addr", orchestrationAddr, "err", err)
		os.Exit(1)
	}
	defer orchClient.Close()

	// ── HTTP router ───────────────────────────────────────────────────────────
	h := gateway.NewHandler(stateClient, orchClient, log)

	r := chi.NewRouter()
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Recoverer)
	r.Use(middleware.Timeout(30 * time.Second))

	// Session lifecycle
	r.Post("/api/sessions", h.CreateSession)
	r.Get("/api/sessions/{sessionID}", h.GetSession)

	// BA turn — SSE streaming
	r.Post("/api/sessions/{sessionID}/turns", h.ProcessTurn)

	// Phase transitions
	r.Post("/api/sessions/{sessionID}/transition", h.RequestTransition)
	r.Post("/api/sessions/{sessionID}/revisit",    h.RevisitPhase)

	// Document upload
	r.Post("/api/sessions/{sessionID}/documents", h.UploadDocument)

	// Health
	r.Get("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	})

	port := env("PORT", "8080")
	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      r,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 35 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// ── Graceful shutdown ─────────────────────────────────────────────────────
	go func() {
		slog.Info("API gateway listening", "port", port)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("server error", "err", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	slog.Info("Shutting down...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		slog.Error("graceful shutdown failed", "err", err)
	}
}

func env(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
