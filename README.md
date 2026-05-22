# Chitragupt

**Agentic Business Requirement Analyzer** — from raw stakeholder input to a signed-off BRD, in hours not weeks.

![Status](https://img.shields.io/badge/status-sprint__1__in__progress-blue)
![License](https://img.shields.io/badge/license-proprietary-lightgrey)
![Rust](https://img.shields.io/badge/rust-1.78%2B-orange)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Go](https://img.shields.io/badge/go-1.22%2B-00aed8)

---

## What It Does

Chitragupt ingests multi-modal business inputs — PDFs, Jira epics, Confluence pages, audio recordings, architecture diagrams — and routes them through a retrieval-augmented generation pipeline to produce fully traceable, structured Business Requirements Documents. A Business Analyst drives the session through active conversation; the system never asks them to fill out a form.

Every requirement is grounded in a source chunk. Every inference is tagged with a confidence score. Every conflict between sources is escalated to a human. The BA leads, the system documents.

---

## Key Capabilities

| Capability | Detail |
|---|---|
| Multi-modal ingestion | PDF · DOCX · XLSX · Audio · Images · Video · URLs · Jira · Confluence · Notion · GitHub · Linear |
| BA-led HITL conversation | 7-phase protocol from problem intake to client sign-off — chat-first, not form-first |
| Grounded synthesis | Every requirement traces to source chunks; orphan knowledge is prohibited |
| Confidence scoring | Calibrated 0–1 score with mandatory tier tags: `[SYNTHESIZED]` `[INFERRED — VERIFY]` |
| Conflict resolution | Equal-tier source contradictions halt synthesis and escalate to human review |
| BRD generation | Templated DOCX/PDF with traceability matrix, domain glossary, and acceptance criteria |
| HLD generation | Mermaid · PNG · SVG high-level architecture diagrams signed off by the client |
| Multi-tenancy | RLS on every table; separate vector namespaces per tenant; zero cross-tenant data leakage |
| Budget control | Project and workspace-level LLM cost caps with hard circuit breakers |

---

## System Architecture

Chitragupt is a **three-service polyglot system**, each language chosen for its computational profile:

| Service | Language | Why |
|---|---|---|
| State Machine | **Rust** | Compile-time exhaustive state modeling, zero-GC, deterministic AC evaluation |
| AI Orchestration / RAG | **Python** | LLM/ML ecosystem is Python-first; LLM latency dominates all other costs |
| API Gateway | **Go** | High-throughput concurrent WebSocket connections; cheap goroutines; single binary |

Services communicate over **gRPC** with protobuf. They share PostgreSQL and Redis. No service touches another service's database directly.

```mermaid
graph TB
    subgraph Clients["Clients"]
        BA[Business Analyst\nBrowser / App]
        WEBHOOK[Upstream Webhooks\nJira · Confluence]
    end

    subgraph Go["Go — API Gateway · :8080"]
        GW[Router + Middleware\nJWT Auth · Rate Limit]
        WSH[WebSocket Handler\nStreaming response]
        REST[REST Handlers\nSession · Upload · Export]
    end

    subgraph Rust["Rust — State Machine · :50051"]
        SM[Session State Machine\nPhase enum · AC evaluation]
        GATE[Upload Gate Manager\nHard · Required · Triggered]
        TRANS[Transition Handler\nConfirmation flow]
    end

    subgraph Python["Python — AI Orchestration · :50052"]
        LG[LangGraph Pipeline\nPer-turn agent graph]
        IC[IntentClassifier · Fast LLM]
        EE[EntityExtractor · Standard LLM]
        RAG[RAGRetrieval · Hybrid search]
        GA[GapAnalyzer · Standard LLM]
        GG[GuidanceGenerator · Premium LLM]
        ING[Ingestion Worker\nChunk · Embed · Index]
    end

    subgraph Data["Shared Data Layer"]
        PG[(PostgreSQL 16 + pgvector)]
        REDIS[(Redis\nSession cache · Events)]
        S3[(S3\nRaw documents)]
    end

    BA -->|WebSocket| WSH
    BA -->|REST| REST
    WEBHOOK --> REST
    WSH --> GW
    REST --> GW
    GW -->|gRPC ProcessTurn| SM
    GW -->|gRPC IngestDocument| ING
    SM --> GATE
    SM --> TRANS
    SM -->|gRPC RunPipeline| LG
    LG --> IC --> EE --> RAG --> GA --> GG
    GG -->|stream tokens| SM
    SM -->|stream tokens| GW
    GW -->|stream tokens| BA
    SM --- PG
    SM --- REDIS
    LG --- PG
    ING --- PG
    ING --- S3
```

---

## BA HITL Flow

The BA drives the entire session through structured conversation. The system leads — one question at a time — from problem statement to locked artifacts.

```mermaid
stateDiagram-v2
    direction LR

    [*] --> PROBLEM_INTAKE

    PROBLEM_INTAKE --> STAKEHOLDER_DISCOVERY : AC-S1 met + BA confirms

    STAKEHOLDER_DISCOVERY --> REQUIREMENT_ELICITATION : AC-S2 met + BA confirms

    state STAKEHOLDER_DISCOVERY {
        [*] --> Chat
        Chat --> CheckpointA : optional
        note right of CheckpointA
            Upload: org charts, RACI
        end note
        CheckpointA --> [*]
    }

    REQUIREMENT_ELICITATION --> CONSTRAINT_CAPTURE : AC-S3 met + BA confirms

    state REQUIREMENT_ELICITATION {
        [*] --> QandA
        QandA --> CheckpointB : optional
        note right of CheckpointB
            Upload: wireframes, process docs
        end note
        CheckpointB --> [*]
    }

    CONSTRAINT_CAPTURE --> ARCHITECTURE_ALIGNMENT : AC-S4 met + BA confirms

    state CONSTRAINT_CAPTURE {
        [*] --> Elicit
        Elicit --> CheckpointC : optional
        note right of CheckpointC
            Upload: compliance docs, infra specs
        end note
        CheckpointC --> [*]
    }

    ARCHITECTURE_ALIGNMENT --> REVIEW_AND_SIGN_OFF : AC-S5 met + BA confirms

    REVIEW_AND_SIGN_OFF --> REQUIREMENT_ELICITATION : Revision requested
    REVIEW_AND_SIGN_OFF --> SIGNED_OFF : AC-S6 met + BA approves

    state REVIEW_AND_SIGN_OFF {
        [*] --> DraftBRD
        DraftBRD --> CheckpointD : optional
        note right of CheckpointD
            Upload: client comments
        end note
        CheckpointD --> [*]
    }

    SIGNED_OFF --> [*]
```

---

## Per-Turn Data Flow

On every BA message, the system evaluates state gates synchronously before calling any LLM:

```mermaid
sequenceDiagram
    participant BA as BA (Browser)
    participant Go as Go API Gateway
    participant Rust as Rust State Machine
    participant Python as Python AI Orchestration
    participant DB as PostgreSQL
    participant Cache as Redis

    BA->>Go: WebSocket message
    Go->>Go: Validate JWT, extract tenant_id
    Go->>Rust: gRPC ProcessTurn

    Rust->>Cache: Load SessionState (cache-first)
    Rust->>Rust: Evaluate upload gates (no LLM)
    alt Hard gate open
        Rust-->>Go: UploadGatePrompt
        Go-->>BA: Stream checkpoint prompt
    else All gates clear
        Rust->>Python: gRPC RunPipeline(SessionState, message)
        Python->>Python: IntentClassifier → EntityExtractor → RAGRetrieval → GapAnalyzer → GuidanceGenerator
        loop Stream tokens
            Python-->>Rust: PipelineToken
            Rust-->>Go: TurnToken
            Go-->>BA: WebSocket token
        end
        Python-->>Rust: PipelineComplete
    end

    Rust->>Rust: Apply entity updates · Evaluate AC · Check transition readiness
    Rust->>DB: Persist updated SessionState
    Rust->>Cache: Update session cache
    Rust-->>Go: TurnComplete
    Go-->>BA: TurnComplete event
```

---

## Current Status

**Sprint 1 — Core Engine in progress.**

| Component | Status |
|---|---|
| Rust state machine kernel | **Built** — `SessionPhase` enum, `SessionState`, AC evaluators, gate manager, `cargo build` ✓ |
| Proto definition (`state_engine.proto`) | **Built** — gRPC service interface defined |
| LangGraph pipeline (Python) | Todo — Sprint 1 P1 |
| Intent classifier | Todo — Sprint 1 P1 |
| Entity extractors | Todo — Sprint 1 P1 |
| RAG retrieval | Todo — Sprint 1 P1 |
| Document ingestion | Todo — Sprint 1 P2 |
| Go API gateway | Todo — Sprint 1 parallel track |
| BRD generator | Todo — Sprint 1 P3 / Sprint 2 |
| HLD generator | Todo — Sprint 1 P3 / Sprint 2 |

See [`docs/sprints/sprint1/README.md`](docs/sprints/sprint1/README.md) for the full priority ladder and epic breakdown.

---

## Repository Structure

```
chitragupt/
│
├── CLAUDE.md                       Claude Code instructions + prompt logging rule
├── CONTRIBUTING.md                 How to build, run, and contribute
├── LICENSE.md                      Proprietary — All Rights Reserved, Revorion AI
├── README.md                       This file
│
├── Cargo.toml                      Rust workspace manifest
├── Cargo.lock
├── rust-toolchain.toml             Pinned Rust toolchain version
│
├── services/
│   └── state-machine/              Rust — session state machine (:50051 gRPC)
│       ├── Cargo.toml
│       ├── proto/
│       │   └── state_engine.proto  gRPC service definition
│       └── src/
│           ├── main.rs
│           ├── state/              SessionPhase enum, SessionState, TransitionEngine
│           ├── ac/                 Acceptance criteria evaluators (s1.rs – s6.rs)
│           ├── gates/              Upload gate manager (Hard / Required / Triggered)
│           └── error.rs
│
├── docs/
│   ├── sprints/
│   │   ├── sprint0/                Foundation — all 7 canonical docs (Sprint 0 CLOSED)
│   │   │   ├── README.md           Sprint 0 overview and exit criteria (COMPLETE)
│   │   │   ├── BA_HITL_FLOW.md     7-phase BA conversation protocol
│   │   │   ├── ARCHITECTURE.md     Trust hierarchy, confidence scoring, invariants, conventions
│   │   │   ├── DECISIONS.md        14 decisions — all DECIDED or DEFERRED
│   │   │   ├── TECH_STACK.md       Service design, libraries, model versions (authoritative)
│   │   │   ├── ONTOLOGY.md         Complete data model — entity schemas, relationships
│   │   │   └── DATABASE.md         Schema, RLS, pgvector, Redis, R2, migration strategy
│   │   └── sprint1/
│   │       └── README.md           Core engine: state machine + RAG pipeline
│   ├── diagrams/                   Mermaid concept diagrams (state machine, trust, pipeline)
│   └── logs/
│       └── prompt_trail.md         Append-only prompt registry (P-001 → current)
│
    └── tech-docs/
        └── state-machine.md        Deep-dive: SessionPhase enum, AC system, gate types,
                                    TransitionEngine, gRPC interface, module structure
```

---

## Documentation Map

### Technical Reference

| Document | Service | Purpose |
|---|---|---|
| [docs/tech-docs/state-machine.md](docs/tech-docs/state-machine.md) | Rust | `SessionPhase` enum, AC system, gate types, `TransitionEngine`, gRPC interface |
| [docs/tech-docs/ai-orchestration.md](docs/tech-docs/ai-orchestration.md) | Python | LangGraph pipeline, `PipelineExecutor`, `LLMFactory`, streaming, RAG, ingestion |
| [docs/tech-docs/api-gateway.md](docs/tech-docs/api-gateway.md) | Go | Route table, WebSocket handler, JWT middleware, upload flow, sign-off flow |

### Architecture & Strategy

| Document | Audience | Purpose |
|---|---|---|
| [docs/sprints/sprint0/TECH_STACK.md](docs/sprints/sprint0/TECH_STACK.md) | Engineering · Architecture | Service design, library choices, model versions, gRPC interfaces |
| [docs/sprints/sprint0/BA_HITL_FLOW.md](docs/sprints/sprint0/BA_HITL_FLOW.md) | BA · PM | How BAs interact with the system phase by phase |
| [docs/sprints/sprint0/DECISIONS.md](docs/sprints/sprint0/DECISIONS.md) | Engineering · Architecture | 14 architectural decisions — all DECIDED or DEFERRED (Sprint 0 closed) |
| [docs/sprints/sprint0/ARCHITECTURE.md](docs/sprints/sprint0/ARCHITECTURE.md) | Engineering · AI/ML | Trust rules, confidence scoring, conflict protocol, invariants, conventions |
| [docs/sprints/sprint0/ONTOLOGY.md](docs/sprints/sprint0/ONTOLOGY.md) | Engineering · Architecture | Complete entity schemas, relationships, and JSON contracts |
| [docs/sprints/sprint0/DATABASE.md](docs/sprints/sprint0/DATABASE.md) | Engineering · DBA | Schema, RLS, pgvector indexing, Redis, R2, migration, data residency |
| [docs/sprints/sprint1/README.md](docs/sprints/sprint1/README.md) | Engineering | Sprint 1 priorities, epics, acceptance criteria, definition of done |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Engineering | Build, run, contribute — per-service setup and conventions |

---

## Quick Start

```bash
# Infrastructure
docker compose up -d postgres redis

# Rust state machine
cargo build && cargo run

# Python AI orchestration (once ai-orchestration service is scaffolded)
cd services/ai-orchestration && uv sync && uv run python -m chitragupt.server

# Go API gateway (once api-gateway service is scaffolded)
cd services/api-gateway && go run ./cmd/server
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full setup instructions, environment variables, and development conventions.

---

## License

Proprietary — Copyright © 2026 Revorion AI. All Rights Reserved.
See [LICENSE.md](LICENSE.md) for full terms.

---

*Chitragupt · Revorion AI · May 2026*
