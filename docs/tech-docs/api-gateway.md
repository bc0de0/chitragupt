# API Gateway Service — Technical Reference

**Service:** `services/api-gateway` (Go)
**HTTP/WebSocket port:** `:8080`
**Role:** Public-facing entry point. Validates identity, routes requests to Rust and Python, and streams responses back to the browser. Contains no business logic.

> **Sprint status:** The Go API gateway is specified and designed. Implementation is scheduled for Sprint 1 parallel track. This document is the binding specification — all implementation must conform to it.

---

## 1. What Problem This Solves

The BA's browser needs to:

1. Send a message and receive a streaming AI response, word by word.
2. Upload documents during the session.
3. Receive a notification when a phase transition is ready.
4. Export the final BRD and HLD as a signed download link.

These are HTTP and WebSocket concerns. They do not belong in the Rust state machine (pure logic) or the Python AI service (pure LLM). Go handles them:

- **Goroutines** — each WebSocket session gets its own goroutine (2KB stack). 10,000 concurrent sessions cost ~20MB. The Python asyncio equivalent costs ~500MB.
- **Streaming** — Go's channel model is ideal for forwarding gRPC token streams to WebSocket without buffering. Tokens arrive at the browser as they leave the LLM.
- **Single binary** — `go build` produces a self-contained executable. No runtime, no virtual environment. `COPY api-gateway /usr/local/bin/` is the entire deployment.

---

## 2. Architecture Position

```
BA (Browser)
      │  WebSocket + REST
      ▼
Go API Gateway  (:8080)
      │  gRPC ProcessTurn (streaming)
      ├──────────────────────────────► Rust State Machine  (:50051)
      │  gRPC IngestDocument
      └──────────────────────────────► Python AI Orchestration  (:50052)
```

Go never touches the session state directly. It never evaluates acceptance criteria. It never calls an LLM. It translates between the external protocol (WebSocket/REST) and the internal protocol (gRPC), and validates identity.

**Invariant:** Every database query issued by Go must include `tenant_id`. A query that omits `tenant_id` is a security defect — RLS is the safety net, not a substitute for correct query construction.

---

## 3. Request Routing

```
WebSocket  /ws/sessions/{id}/chat          → Rust StateEngine.ProcessTurn (stream)
POST       /api/sessions                   → Rust StateEngine.CreateSession
GET        /api/sessions/{id}              → Rust StateEngine.GetSessionState
POST       /api/sessions/{id}/upload       → S3 upload → Python AIOrchestration.IngestDocument
                                              → Rust StateEngine.NotifyUploadComplete
GET        /api/sessions/{id}/export/{type} → Python (BRD/HLD generation) → presigned S3 URL
POST       /api/sign-off/{token}           → PostgreSQL token burn → Rust notify
GET        /health                         → 200 OK (liveness probe)
GET        /ready                          → gRPC ping Rust + Python (readiness probe)
```

All routes under `/api/*` and `/ws/*` require a valid JWT. `/health` and `/ready` are unauthenticated.

---

## 4. WebSocket Stream Handler

The chat WebSocket is the primary BA interface. Every message the BA sends travels down a streaming pipeline and returns tokens as they are generated.

```go
func (h *ChatHandler) ServeWS(w http.ResponseWriter, r *http.Request) {
    sessionID := chi.URLParam(r, "id")
    tenantID  := tenantFromContext(r.Context())  // extracted from JWT by middleware

    conn, err := h.upgrader.Upgrade(w, r, nil)
    if err != nil { return }
    defer conn.Close()

    for {
        // Read one BA message
        _, msg, err := conn.ReadMessage()
        if err != nil { return }

        // Open gRPC stream to Rust — one stream per turn
        stream, err := h.stateClient.ProcessTurn(r.Context(), &pb.TurnRequest{
            SessionId: sessionID,
            Message:   string(msg),
            TenantId:  tenantID,
        })
        if err != nil {
            conn.WriteJSON(errorEvent(err))
            continue
        }

        // Forward every gRPC event to WebSocket — zero buffering
        for {
            event, err := stream.Recv()
            if err == io.EOF { break }
            if err != nil { conn.WriteJSON(errorEvent(err)); break }
            conn.WriteJSON(toWSEvent(event))
        }
    }
}
```

`toWSEvent` maps `TurnEvent.oneof` variants to typed WebSocket JSON payloads:

| gRPC TurnEvent | WebSocket event type | BA browser action |
|---|---|---|
| `StreamToken` | `{ type: "token", text: "..." }` | Append text to response |
| `UploadGatePrompt` | `{ type: "gate", message: "...", doc_type: "..." }` | Show upload prompt |
| `TransitionOffer` | `{ type: "transition", summary: [...], next_phase: "..." }` | Show confirmation UI |
| `TurnComplete` | `{ type: "done", transition_ready: bool }` | Enable next-turn input |

---

## 5. JWT Middleware

All authenticated routes pass through the JWT middleware, which:

1. Extracts the `Authorization: Bearer <token>` header.
2. Validates the RS256 signature against the public key at `JWT_PUBLIC_KEY`.
3. Extracts `tenant_id`, `workspace_id`, and `user_id` from the token claims.
4. Stores these in `context.Context` for use by handlers and database queries.

```go
func JWTMiddleware(publicKey *rsa.PublicKey) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            claims, err := validateJWT(r.Header.Get("Authorization"), publicKey)
            if err != nil {
                http.Error(w, "Unauthorized", http.StatusUnauthorized)
                return
            }
            ctx := withClaims(r.Context(), claims)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}
```

The `tenant_id` stored in context is the only input to all multi-tenant query parameters. It is never sourced from the request body or URL parameters — those can be spoofed.

---

## 6. Document Upload Flow

Document uploads are a three-step operation involving all three services:

```
1. BA → Go: POST /api/sessions/{id}/upload (multipart/form-data)
2. Go: stream file to S3 → record document row in PostgreSQL with status='uploading'
3. Go → Python: gRPC IngestDocument(session_id, document_id, s3_key, tenant_id)
   Python returns IngestAck immediately (fire-and-forget)
4. Go → Rust: gRPC NotifyUploadComplete(session_id, document_id, checkpoint, tenant_id)
5. Python (background): ingest → embed → index → publish events:upload:complete
6. Rust (via Redis event): re-evaluate upload AC → may resolve a hard gate
```

Go responds to the BA with `{ "document_id": "...", "status": "ingesting" }` as soon as Python acknowledges. The BA is notified that indexing is complete via the next `TurnComplete` event (Rust reflects the resolved gate status).

```go
func (h *UploadHandler) Upload(w http.ResponseWriter, r *http.Request) {
    sessionID := chi.URLParam(r, "id")
    checkpoint := r.URL.Query().Get("checkpoint")  // "A", "B", "C", or "D"

    file, header, err := r.FormFile("document")
    if err != nil { http.Error(w, "bad request", 400); return }
    defer file.Close()

    s3Key    := fmt.Sprintf("%s/%s/%s", tenantID, sessionID, header.Filename)
    docID, _ := h.s3Client.Upload(r.Context(), s3Key, file)

    h.pythonClient.IngestDocument(r.Context(), &pb.IngestRequest{
        SessionId:  sessionID,
        DocumentId: docID,
        S3Key:      s3Key,
        TenantId:   tenantID,
    })

    h.stateClient.NotifyUploadComplete(r.Context(), &pb.UploadCompleteEvent{
        SessionId:  sessionID,
        DocumentId: docID,
        Checkpoint: checkpoint,
        TenantId:   tenantID,
    })

    json.NewEncoder(w).Encode(map[string]string{
        "document_id": docID,
        "status":      "ingesting",
    })
}
```

---

## 7. Sign-Off Token Flow

When the BA reaches `ReviewAndSignOff`, Rust generates a sign-off token and records it in PostgreSQL. The client receives the token via email (out of scope for the API gateway — handled by an email service). When the client clicks the sign-off link:

```
POST /api/sign-off/{token}
  → Go: look up token in PostgreSQL, verify it is unexpired and unused
  → Go: mark token as burned (atomic UPDATE with status check)
  → Go → Rust: gRPC NotifySignOff(session_id, token_id, tenant_id)
  → Rust: advance session to SIGNED_OFF phase
```

The sign-off endpoint is unauthenticated (the client does not have a BA JWT) but uses a cryptographically random token as a bearer credential. Tokens are single-use and expire after 30 days.

---

## 8. Rate Limiting

Rate limiting is applied per `tenant_id`, not per IP. This prevents a single tenant from consuming excessive LLM budget at the infrastructure layer, independently of the per-session cost caps enforced by the Python service.

| Endpoint | Limit | Window |
|---|---|---|
| WebSocket messages | 60 messages | per minute per session |
| Document uploads | 20 uploads | per hour per session |
| Session creation | 10 sessions | per hour per tenant |
| All other `/api/*` | 200 requests | per minute per tenant |

Rate limit state is kept in Redis (`rate:{tenant_id}:{endpoint}` with TTL = window). Exceeding the limit returns `429 Too Many Requests`.

---

## 9. Redis Events (Subscriptions)

Go subscribes to Redis channels to handle async events that require an action in the browser layer:

| Channel | Published by | Go action |
|---|---|---|
| `events:budget:threshold` | Rust (after cost rollup) | Send budget warning via the active WebSocket if session is connected |
| `events:signoff:received` | Go itself (after burning token) | Notify the BA's WebSocket that the client has signed |

---

## 10. Key Libraries

| Library | Purpose |
|---|---|
| `chi` | Lightweight HTTP router; middleware composition |
| `gorilla/websocket` | WebSocket upgrade and read/write loop |
| `google.golang.org/grpc` | gRPC clients for Rust state machine and Python AI service |
| `golang-jwt/jwt/v5` | RS256 JWT validation |
| `pgx/v5` | PostgreSQL driver — session lookup, sign-off token operations |
| `go-redis/v9` | Redis client — rate limiting, event subscriptions |
| `uber-go/zap` | Structured, leveled production logging |
| `prometheus/client_golang` | Metrics — request count, latency histograms, active WebSocket sessions |
| `aws-sdk-go-v2/s3` | S3 document upload, presigned download URLs |
| `rs/cors` | CORS middleware |

---

## 11. Module Structure

```
services/api-gateway/
├── go.mod
├── go.sum
├── cmd/
│   └── server/
│       └── main.go              Entry point — router setup, gRPC client init, server start
└── internal/
    ├── handler/
    │   ├── chat.go              WebSocket stream handler — forwards gRPC events to browser
    │   ├── session.go           REST handlers — create session, get session state
    │   ├── upload.go            Multipart upload → S3 → IngestDocument + NotifyUploadComplete
    │   ├── export.go            BRD/HLD export → presigned S3 URL
    │   └── signoff.go           Sign-off token burn + Rust notification
    ├── middleware/
    │   ├── auth.go              JWT validation; injects tenant_id, user_id into context
    │   ├── ratelimit.go         Per-tenant rate limiting via Redis
    │   └── logging.go           Request/response structured logging with zap
    ├── grpcclient/
    │   ├── state.go             Rust StateEngine gRPC client wrapper
    │   └── ai.go                Python AIOrchestration gRPC client wrapper
    └── events/
        └── redis_sub.go         Redis subscriber — budget.threshold, signoff.received
```

---

## 12. Local Development

The service is not yet built. When scaffolded:

```bash
cd services/api-gateway

# Build
go build ./...

# Run (requires Rust and Python services running first)
go run ./cmd/server

# Tests
go test ./...

# Vet and staticcheck (must pass before any PR)
go vet ./...
staticcheck ./...
```

Required environment variables:

```bash
STATE_MACHINE_ADDR=localhost:50051
AI_ORCHESTRATION_ADDR=localhost:50052
DATABASE_URL=postgres://chitragupt:chitragupt@localhost:5432/chitragupt
REDIS_URL=redis://localhost:6379
JWT_PUBLIC_KEY=<RS256 public key — PEM format>
S3_BUCKET=chitragupt-documents
AWS_REGION=ap-southeast-1
```

For local development, `docker compose up -d postgres redis` starts the shared infrastructure. All three services can then be started independently.

---

## 13. Why No Business Logic in Go

This is the most important constraint on Go contributions. If you find yourself writing anything that:

- Evaluates whether a session can advance to the next phase → belongs in Rust
- Decides which LLM to use or how to construct a prompt → belongs in Python
- Reads `session.current_phase` to change the response → belongs in Rust

...it is in the wrong service. Go's only jobs are: authenticate, route, translate between WebSocket/REST and gRPC, and stream. The moment Go accumulates business logic, the three-service boundary breaks down and the clean separation between state ownership (Rust), intelligence (Python), and connectivity (Go) is lost.

---

> Chitragupt API Gateway Service · Technical Reference · Sprint 1 · May 2026
