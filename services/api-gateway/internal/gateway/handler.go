// Package gateway implements the HTTP handlers for the Chitragupt API gateway.
//
// Turn flow (ProcessTurn):
//  1. Load session state from Rust (GetSessionState).
//  2. Call Python RunPipeline — stream tokens to client via SSE.
//  3. Send TurnComplete details from Python to Rust (ApplyTurnResult).
//  4. Return final JSON event with transition/AC metadata.
package gateway

import (
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"

	"github.com/go-chi/chi/v5"

	commonpb "github.com/bc0de0/chitragupt/services/api-gateway/proto/common"
	orchpb "github.com/bc0de0/chitragupt/services/api-gateway/proto/orchestration"

	"github.com/bc0de0/chitragupt/services/api-gateway/internal/orchestration"
	"github.com/bc0de0/chitragupt/services/api-gateway/internal/statemc"
)

// Handler holds injected dependencies for all HTTP handlers.
type Handler struct {
	state *statemc.Client
	orch  *orchestration.Client
	log   *slog.Logger
}

// NewHandler constructs a Handler.
func NewHandler(state *statemc.Client, orch *orchestration.Client, log *slog.Logger) *Handler {
	return &Handler{state: state, orch: orch, log: log}
}

// ── CreateSession ─────────────────────────────────────────────────────────────

type createSessionReq struct {
	WorkspaceID string `json:"workspace_id"`
	ProjectID   string `json:"project_id"`
}

func (h *Handler) CreateSession(w http.ResponseWriter, r *http.Request) {
	var req createSessionReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		jsonError(w, "invalid request body", http.StatusBadRequest)
		return
	}
	if req.WorkspaceID == "" || req.ProjectID == "" {
		jsonError(w, "workspace_id and project_id are required", http.StatusBadRequest)
		return
	}

	resp, err := h.state.CreateSession(r.Context(), req.WorkspaceID, req.ProjectID)
	if err != nil {
		h.log.Error("CreateSession failed", "err", err)
		jsonError(w, "failed to create session", http.StatusInternalServerError)
		return
	}

	jsonOK(w, map[string]any{
		"session_id":    resp.SessionId,
		"current_phase": resp.CurrentPhase,
	})
}

// ── GetSession ───────────────────────────────────────────────────────────────

func (h *Handler) GetSession(w http.ResponseWriter, r *http.Request) {
	sessionID   := chi.URLParam(r, "sessionID")
	workspaceID := r.URL.Query().Get("workspace_id")

	state, err := h.state.GetSessionState(r.Context(), sessionID, workspaceID)
	if err != nil {
		h.log.Error("GetSessionState failed", "session", sessionID, "err", err)
		jsonError(w, "session not found", http.StatusNotFound)
		return
	}

	jsonOK(w, sessionStateJSON(state))
}

// ── ProcessTurn ──────────────────────────────────────────────────────────────

type turnReq struct {
	Message     string `json:"message"`
	WorkspaceID string `json:"workspace_id"`
}

func (h *Handler) ProcessTurn(w http.ResponseWriter, r *http.Request) {
	sessionID := chi.URLParam(r, "sessionID")

	var req turnReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Message == "" {
		jsonError(w, "message is required", http.StatusBadRequest)
		return
	}

	// 1. Load session state from Rust.
	sessionState, err := h.state.GetSessionState(r.Context(), sessionID, req.WorkspaceID)
	if err != nil {
		h.log.Error("GetSessionState failed", "session", sessionID, "err", err)
		jsonError(w, "session not found", http.StatusNotFound)
		return
	}

	// 2. Open SSE stream.
	sseHeaders(w)
	flusher, ok := w.(http.Flusher)
	if !ok {
		jsonError(w, "streaming not supported", http.StatusInternalServerError)
		return
	}

	// 3. Run Python pipeline — stream tokens as SSE events.
	result, err := h.orch.RunPipeline(
		r.Context(),
		sessionState,
		req.Message,
		func(token string) {
			fmt.Fprintf(w, "event: token\ndata: %s\n\n", jsonString(token))
			flusher.Flush()
		},
	)
	if err != nil {
		h.log.Error("RunPipeline failed", "session", sessionID, "err", err)
		fmt.Fprintf(w, "event: error\ndata: %s\n\n", jsonString(err.Error()))
		flusher.Flush()
		return
	}

	// 4. Apply pipeline result to Rust session state.
	var entities  []*commonpb.EntityProto
	var acUpdates []*commonpb.AcUpdateProto
	var costUSD   float64

	if c := result.Complete; c != nil {
		entities  = c.Entities
		acUpdates = c.AcUpdates
		costUSD   = float64(c.CostUsd)
	}

	turnResp, err := h.state.ApplyTurnResult(r.Context(), sessionID, entities, acUpdates, costUSD)
	if err != nil {
		h.log.Warn("ApplyTurnResult failed", "session", sessionID, "err", err)
	}

	// 5. Send completion event.
	completion := map[string]any{
		"type": "complete",
	}
	if result.Complete != nil {
		completion["intent"]             = result.Complete.Intent
		completion["transition_ready"]   = result.Complete.TransitionReady
		completion["gap_criterion_id"]   = result.Complete.GapCriterionId
		completion["suggested_question"] = result.Complete.SuggestedQuestion
		completion["cost_usd"]           = result.Complete.CostUsd
		completion["aborted"]            = result.Complete.Aborted
	}
	if turnResp != nil {
		completion["current_phase"]  = turnResp.CurrentPhase
		completion["unmet_ac_count"] = turnResp.UnmetAcCount
	}

	completionBytes, _ := json.Marshal(completion)
	fmt.Fprintf(w, "event: complete\ndata: %s\n\n", string(completionBytes))
	flusher.Flush()
}

// ── RequestTransition ────────────────────────────────────────────────────────

type transitionReq struct {
	TargetPhase string `json:"target_phase"`
}

func (h *Handler) RequestTransition(w http.ResponseWriter, r *http.Request) {
	sessionID := chi.URLParam(r, "sessionID")

	var req transitionReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.TargetPhase == "" {
		jsonError(w, "target_phase is required", http.StatusBadRequest)
		return
	}

	resp, err := h.state.RequestTransition(r.Context(), sessionID, req.TargetPhase)
	if err != nil {
		h.log.Error("RequestTransition RPC failed", "session", sessionID, "err", err)
		jsonError(w, "transition request failed", http.StatusInternalServerError)
		return
	}

	status := http.StatusOK
	if !resp.Approved {
		status = http.StatusConflict
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]any{
		"approved":      resp.Approved,
		"current_phase": resp.CurrentPhase,
		"error":         resp.ErrorMessage,
	})
}

// ── RevisitPhase ─────────────────────────────────────────────────────────────

type revisitReq struct {
	TargetPhase string `json:"target_phase"`
}

func (h *Handler) RevisitPhase(w http.ResponseWriter, r *http.Request) {
	sessionID := chi.URLParam(r, "sessionID")

	var req revisitReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.TargetPhase == "" {
		jsonError(w, "target_phase is required", http.StatusBadRequest)
		return
	}

	resp, err := h.state.RevisitPhase(r.Context(), sessionID, req.TargetPhase)
	if err != nil {
		h.log.Error("RevisitPhase RPC failed", "session", sessionID, "err", err)
		jsonError(w, "revisit failed", http.StatusInternalServerError)
		return
	}

	status := http.StatusOK
	if !resp.Ok {
		status = http.StatusConflict
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]any{
		"ok":            resp.Ok,
		"current_phase": resp.CurrentPhase,
		"error":         resp.ErrorMessage,
	})
}

// ── UploadDocument ───────────────────────────────────────────────────────────

func (h *Handler) UploadDocument(w http.ResponseWriter, r *http.Request) {
	sessionID := chi.URLParam(r, "sessionID")

	if err := r.ParseMultipartForm(32 << 20); err != nil { // 32 MB limit
		jsonError(w, "failed to parse multipart form", http.StatusBadRequest)
		return
	}

	file, header, err := r.FormFile("file")
	if err != nil {
		jsonError(w, "file field is required", http.StatusBadRequest)
		return
	}
	defer file.Close()

	content, err := io.ReadAll(file)
	if err != nil {
		jsonError(w, "failed to read file", http.StatusInternalServerError)
		return
	}

	workspaceID := r.FormValue("workspace_id")
	projectID   := r.FormValue("project_id")
	documentID  := r.FormValue("document_id") // client supplies pre-generated UUID

	resp, err := h.orch.IngestDocument(r.Context(), &orchpb.IngestRequest{
		DocumentId:  documentID,
		WorkspaceId: workspaceID,
		ProjectId:   projectID,
		SessionId:   sessionID,
		Filename:    header.Filename,
		Content:     content,
	})
	if err != nil {
		h.log.Error("IngestDocument failed", "session", sessionID, "err", err)
		jsonError(w, "ingestion failed", http.StatusInternalServerError)
		return
	}

	h.log.Info("document ingestion accepted",
		"session", sessionID,
		"document", resp.DocumentId,
		"status", resp.Status,
	)

	jsonOK(w, map[string]any{
		"document_id": resp.DocumentId,
		"status":      resp.Status,
	})
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func sseHeaders(w http.ResponseWriter) {
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")
}

func jsonOK(w http.ResponseWriter, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(body)
}

func jsonError(w http.ResponseWriter, msg string, status int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

func jsonString(s string) string {
	b, _ := json.Marshal(s)
	return string(b)
}

func sessionStateJSON(s *commonpb.SessionStateProto) map[string]any {
	return map[string]any{
		"session_id":         s.SessionId,
		"workspace_id":       s.WorkspaceId,
		"project_id":         s.ProjectId,
		"current_phase":      s.CurrentPhase,
		"turn_count":         s.TurnCount,
		"total_cost_usd":     s.TotalCostUsd,
		"ac_met":             s.AcMet,
		"ac_waived":          s.AcWaived,
		"documents_indexed":  s.DocumentsIndexed,
	}
}
