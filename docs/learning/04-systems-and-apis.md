# 04 — Systems Programming: Rust, gRPC, and the Go API Gateway

**Why this matters for Chitragupt:** The state machine (Rust) and API gateway (Go) are not AI components — they are correctness and performance components. Understanding why these languages were chosen and how gRPC connects them helps you reason about the system boundaries and where to make changes safely.

---

## 1. Rust — The State Machine Kernel

### Why Rust?

Rust is a systems programming language that provides:
- **Memory safety without garbage collection** — no null pointer errors, no use-after-free bugs
- **Compile-time exhaustive matching** — the compiler forces you to handle every possible case
- **Zero-cost abstractions** — high-level code with low-level performance

For Chitragupt's state machine, the critical property is **exhaustive matching**. The BA conversation has 7 phases, and every possible transition must be handled. In most languages, forgetting to handle a case causes a runtime crash. In Rust, it causes a **compile error** — the bug is caught before the code ships.

```rust
// Rust forces you to handle every phase variant
match session.phase {
    SessionPhase::ProblemIntake      => handle_problem_intake(&mut session, input),
    SessionPhase::StakeholderMapping => handle_stakeholder_mapping(&mut session, input),
    SessionPhase::ScopeDefinition    => handle_scope_definition(&mut session, input),
    SessionPhase::RequirementCapture => handle_requirement_capture(&mut session, input),
    SessionPhase::AIStrategyDesign   => handle_ai_strategy_design(&mut session, input),
    SessionPhase::DataArchitecture   => handle_data_architecture(&mut session, input),
    SessionPhase::Validation         => handle_validation(&mut session, input),
    // If you forget any variant above, this code will NOT compile
}
```

### The SessionPhase enum

```rust
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SessionPhase {
    ProblemIntake,
    StakeholderMapping,
    ScopeDefinition,
    RequirementCapture,
    AIStrategyDesign,
    DataArchitecture,
    Validation,
}
```

An `enum` in Rust is a type that can be exactly one of its variants. Unlike an integer or string, the compiler tracks which variants exist and forces exhaustive handling.

### Transitions and the TransitionEngine

A transition from one phase to the next requires three conditions to be true:
1. All required AC criteria for the current phase are met
2. All HARD gates for the current phase are resolved
3. The BA has explicitly confirmed readiness

```rust
pub struct TransitionEngine;

impl TransitionEngine {
    pub fn can_advance(
        &self,
        session: &Session,
        ac_evaluator: &AcEvaluator,
        gate_checker: &GateChecker,
    ) -> TransitionResult {
        let criteria_met = ac_evaluator.all_required_met(session);
        let gates_clear = gate_checker.all_hard_gates_resolved(session);
        let confirmed = session.advance_confirmed;

        if criteria_met && gates_clear && confirmed {
            TransitionResult::Allowed(next_phase(session.phase))
        } else {
            TransitionResult::Blocked(blocking_reasons(session, criteria_met, gates_clear))
        }
    }
}
```

### Gate Types

| Type | Behaviour | Example |
|---|---|---|
| `HARD` | Session halts — cannot proceed until resolved | Client signature required before requirements are locked |
| `REQUIRED_PROMPT` | AI asks the BA for missing information | "You haven't named a decision-maker — who is it?" |
| `TRIGGERED` | Activates only when a condition is met | Upload gate triggers only if the BA mentioned a document |
| `RECOMMENDED` | Soft suggestion — BA can skip | "You may want to add compliance constraints before continuing" |

---

## 2. Async Rust with Tokio

Chitragupt's Rust service is asynchronous — it handles many gRPC requests concurrently without blocking.

**Tokio** is the async runtime for Rust — it provides the executor, timers, and I/O primitives.

```rust
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let service = StateEngineService::new();
    Server::builder()
        .add_service(StateEngineServer::new(service))
        .serve("[::1]:50051".parse()?)
        .await?;
    Ok(())
}
```

`async fn` functions return a `Future` — they don't block the thread while waiting. `await` suspends the current task and lets tokio run other tasks.

### Result and error handling

Rust has no exceptions. Fallible operations return `Result<T, E>` — either `Ok(value)` or `Err(error)`. You must handle both cases.

```rust
// Must handle success and failure explicitly
match evaluate_ac(session) {
    Ok(result)  => process_result(result),
    Err(e)      => log_error_and_return(e),
}
```

---

## 3. gRPC — Internal Service Communication

### What is gRPC?

gRPC is a Remote Procedure Call framework developed by Google. It allows one service to call functions on another service as if they were local — but over the network.

**Why gRPC instead of REST for internal calls?**

| | gRPC | REST |
|---|---|---|
| Protocol | HTTP/2 binary | HTTP/1.1 text (usually) |
| Performance | ~7x faster serialization | Slower (JSON parsing) |
| Streaming | Built-in bidirectional | Requires SSE/WebSocket |
| Type safety | Enforced via protobuf | Optional (OpenAPI) |
| Best for | Internal service calls | External client APIs |

Chitragupt uses gRPC for Go↔Rust and Rust↔Python because these are high-frequency internal calls where performance and type safety matter. External clients use REST/WebSocket via Go.

### Protocol Buffers (protobuf)

protobuf is the schema language for gRPC. It defines services (callable methods) and messages (data structures) in `.proto` files. These files are the source of truth for all service interfaces.

```protobuf
// StateEngine service — Go calls this on Rust
syntax = "proto3";
package chitragupt.state;

service StateEngine {
    rpc AdvancePhase(AdvancePhaseRequest) returns (AdvancePhaseResponse);
    rpc EvaluateAC(EvaluateACRequest) returns (EvaluateACResponse);
    rpc GetSessionState(GetSessionStateRequest) returns (SessionState);
}

message AdvancePhaseRequest {
    string session_id = 1;
    string tenant_id  = 2;
    bool   confirmed  = 3;
}

message AdvancePhaseResponse {
    bool    allowed       = 1;
    string  new_phase     = 2;
    repeated string blockers = 3;
}
```

From this `.proto` file, code generators (`protoc`) produce:
- Rust server code (via `tonic`)
- Python client code (via `grpcio-tools`)
- Go client code (via `protoc-gen-go`)

**The rule:** Never change the `.proto` file without updating all services that use it. A version mismatch will break the interface silently.

### Chitragupt's gRPC topology

```
Client browser
    ↕ WebSocket / REST
Go API Gateway (port 8080)
    ↕ gRPC (port 50051)
Rust State Machine
    ↕ gRPC (port 50052)
Python AI Orchestration
```

---

## 4. Go — The API Gateway

### Why Go for the gateway?

Go has excellent performance characteristics for network servers:
- **goroutines** — lightweight concurrent tasks (thousands of concurrent WebSocket connections with low memory)
- **Built-in HTTP/WebSocket support** — `net/http` and `gorilla/websocket` are battle-tested
- **Simple concurrency model** — goroutines + channels avoid the complexity of async/await

The gateway's job is purely I/O: receive requests, validate JWTs, route to backend services, stream responses. Go excels at this because it has minimal overhead per connection.

**Rule:** No business logic in Go. All decisions about session state, phase transitions, and requirement extraction happen in Rust or Python. The gateway is a router, not a brain.

### Goroutines and channels

```go
// Each WebSocket connection gets its own goroutine — very cheap
func handleWebSocket(conn *websocket.Conn, sessionID string) {
    // This goroutine reads from the connection and writes back
    // Thousands of these can run simultaneously on one server
    for {
        _, message, err := conn.ReadMessage()
        if err != nil { return }
        go processTurn(conn, sessionID, message)  // launch another goroutine
    }
}
```

### JWT middleware

```go
func JWTMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        token := extractBearerToken(r)
        claims, err := validateJWT(token)
        if err != nil {
            http.Error(w, "unauthorized", http.StatusUnauthorized)
            return
        }
        // Inject tenant_id into context — all downstream handlers can read it
        ctx := context.WithValue(r.Context(), "tenant_id", claims.TenantID)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}
```

---

## 5. Resources

### Rust

| Resource | URL | What to read |
|---|---|---|
| The Rust Book | [doc.rust-lang.org/book/](https://doc.rust-lang.org/book/) | Start here — enums (ch.6), pattern matching (ch.18), error handling (ch.9) |
| Rust async book | [rust-lang.github.io/async-book/](https://rust-lang.github.io/async-book/) | Futures, async/await, Tokio |
| Tokio docs | [docs.rs/tokio/latest/tokio/](https://docs.rs/tokio/latest/tokio/) | Runtime, tasks, channels, timers |
| tonic (gRPC for Rust) | [docs.rs/tonic/latest/tonic/](https://docs.rs/tonic/latest/tonic/) | Building gRPC servers and clients in Rust |

### gRPC and protobuf

| Resource | URL | What to read |
|---|---|---|
| gRPC introduction | [grpc.io/docs/what-is-grpc/introduction/](https://grpc.io/docs/what-is-grpc/introduction/) | Core concepts — services, messages, channels |
| Protocol Buffers language guide | [protobuf.dev/programming-guides/proto3/](https://protobuf.dev/programming-guides/proto3/) | How to write .proto files |
| gRPC Python quickstart | [grpc.io/docs/languages/python/quickstart/](https://grpc.io/docs/languages/python/quickstart/) | Running a Python gRPC client |
| gRPC Go quickstart | [grpc.io/docs/languages/go/quickstart/](https://grpc.io/docs/languages/go/quickstart/) | Running a Go gRPC server |

### Go

| Resource | URL | What to read |
|---|---|---|
| Official Go docs | [go.dev/doc/](https://go.dev/doc/) | Getting started, effective Go |
| Go tour | [go.dev/tour/welcome/1](https://go.dev/tour/welcome/1) | Interactive introduction — goroutines and channels are the key sections |
| Go HTTP server tutorial | [go.dev/doc/articles/wiki/](https://go.dev/doc/articles/wiki/) | Building a simple Go web server |

### Deep Dives

| Resource | What you will learn |
|---|---|
| [Why Rust for systems at Cloudflare](https://blog.cloudflare.com/tag/rust/) | Real-world rationale for choosing Rust in production |
| [State machine pattern in Rust](https://doc.rust-lang.org/book/ch06-00-enums.html) | Enums and match — the foundation of Chitragupt's phase system |
| [gRPC vs REST (Google Cloud)](https://cloud.google.com/blog/products/api-management/understanding-grpc-openapi-and-rest-and-when-to-use-them) | When gRPC is better than REST, with benchmarks |

---

> Chitragupt Learning Hub · 04 Systems and APIs · v0.1 · May 2026
