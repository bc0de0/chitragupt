# Key Decisions — Sprint 0

**Purpose:** Consolidated record of all foundational architectural and technology decisions. Replaces individual ADRs. Each decision tracks the question, meaningful options with tradeoffs, decision criteria, the decision made, and rationale.

**Status legend:** `OPEN` = unevaluated, `GUIDED` = BA/PM directional input received, `DECIDED` = engineering sign-off complete, `DEFERRED` = explicitly postponed.

**Sprint 0 closure status:** All decisions reached `DECIDED` or `DEFERRED` before Sprint 0 closed. No open questions remain that block Sprint 1 work.

---

## 1. Core Runtime

### D-001 — Application Language & Runtime

**Question:** What language and runtime underpins all backend services?

| Option | Tradeoff |
|---|---|
| Python 3.11+ | Best-in-class agentic/ML ecosystem (LangGraph, LangChain, HuggingFace). Slower raw throughput but rarely the bottleneck in LLM-bound workloads. |
| TypeScript (Node) | Strong async I/O; weaker ML ecosystem; interop with Python services adds complexity. |
| Go | Best performance; minimal ML library support; agentic patterns require significant custom work. |
| Rust | Deterministic, zero-GC, compile-time exhaustive state modeling; steep learning curve; no ML ecosystem. |

**Decision criteria:** Ecosystem maturity for LLM orchestration, HITL graph state management, and RAG pipeline tooling; correctness guarantees for state machine; connection concurrency for WebSocket API.

**Decision:** `DECIDED` — **Polyglot: Rust + Python + Go**

- **Rust** owns the session state machine (:50051 gRPC). Compile-time exhaustive state transition handling and zero-GC determinism are non-negotiable for AC evaluation.
- **Python 3.11+** owns all LLM/AI/RAG orchestration (:50052 gRPC). The entire ML ecosystem is Python-first; no other choice is viable.
- **Go 1.22+** owns the API gateway (:8080 HTTP/WS). Goroutines (2KB stack) handle 10K concurrent WebSocket sessions at ~20MB total overhead; a single binary deploys with no runtime dependencies.

Services communicate over **gRPC + protobuf** internally. HTTP/REST is exposed to clients by Go only. `.proto` files in `proto/` at repo root are the source of truth for all service contracts.

---

## 2. AI/ML Layer

### D-002 — LLM Model Selection & Tier Assignment

**Question:** Which LLM models are assigned to which reasoning tiers, and from which providers?

**Tier model:**

| Tier | Role | Candidate Models |
|---|---|---|
| Premium | Complex synthesis, BRD generation | Claude Opus, GPT-4o, Gemini Ultra |
| Standard | Requirement extraction, classification | Claude Sonnet, GPT-4o-mini, Gemini Pro |
| Fast | Routing, tagging, short extractions | Claude Haiku, GPT-4o-mini, Gemini Flash |
| Fallback | Cross-vendor failover | Must be different vendor from Primary |

**Decision criteria:** Structured output reliability, reasoning depth for requirements synthesis, context window (long documents), cost per 1M tokens, zero data-retention enterprise tier availability.

**Decision:** `DECIDED` — **Anthropic primary with Gemini fallback**

| Role | Model ID | Tier |
|---|---|---|
| BRD/HLD generation | `claude-opus-4-7` | Premium |
| Requirement extraction, gap analysis, refinement | `claude-sonnet-4-6` | Standard |
| Intent classification, routing | `claude-haiku-4-5-20251001` | Fast |
| Cross-vendor fallback | `gemini-2.0-flash` | Standard fallback |

Rationale: Anthropic delivers best structured output reliability for requirements synthesis; enterprise zero-data-retention tier is available; Gemini as fallback ensures provider diversity without adding a third SDK. All model IDs are pinned — no floating aliases permitted (INV-MODEL-03).

---

### D-003 — Embedding Model

**Question:** Which embedding model and vector dimension is used for all semantic search?

**Critical constraint:** This decision cannot be changed post-launch without a full re-embedding of all tenant data. Choose deliberately.

| Option | Dimension | Tradeoff |
|---|---|---|
| text-embedding-3-large (OpenAI) | 1536 or 3072 | Strong baseline; OpenAI vendor dependency |
| voyage-large-2 (Voyage AI) | 1536 | Top retrieval benchmarks on domain-specific text; smaller vendor |
| Cohere embed-v3 | 1024 | Good multilingual; cost-competitive |
| AWS Titan Embeddings | 1536 | AWS-native; simpler if deploying on AWS |

**Decision criteria:** Retrieval quality on domain-specific (business requirements) text, vendor lock-in risk, dimension compatibility with chosen vector store.

**Decision:** `DECIDED` — **voyage-large-2, 1536 dimensions**

Voyage AI leads retrieval benchmarks on domain-specific and technical text — exactly the content profile of business requirement documents. The 1536-dimension output matches text-embedding-3-small's dimension, ensuring that if emergency cross-vendor fallback to OpenAI embeddings becomes necessary, the vector column schema does not need to change.

Emergency fallback: `text-embedding-3-small` (OpenAI, 1536 dim). Strict rule: no mixed embedding models within a single vector namespace. In the event of a Voyage AI provider failure, RAG retrieval is suspended for the affected session rather than mixing model outputs. Full re-embedding via `AIOrchestration.ReEmbed` is required to switch models.

---

### D-004 — Retrieval Strategy

**Question:** How are relevant chunks found for each query — dense, sparse, or hybrid?

| Option | Tradeoff |
|---|---|
| Dense only (vector similarity) | Simple; misses exact keyword matches; good for semantic intent |
| Sparse only (BM25 / keyword) | Good for exact terms, version numbers, named entities; misses paraphrase |
| Hybrid + re-ranking | Best recall; higher latency; requires a cross-encoder re-ranker model |

**Decision criteria:** Recall on business requirement documents (which mix semantic and exact-match content), acceptable latency budget, infrastructure complexity.

**Decision:** `DECIDED` — **Hybrid (dense + sparse) with cross-encoder re-ranking**

Business requirements documents contain a mix of semantic intent ("the system should be easy to use") and exact-match terms (regulation names, version numbers, actor names, system identifiers). Dense-only retrieval misses the latter class; sparse-only retrieval misses semantic paraphrase. Hybrid retrieval with Reciprocal Rank Fusion resolves both.

Implementation: pgvector cosine (dense, 70% weight) + BM25 via `rank-bm25` (sparse, 30% weight). Top-50 dense candidates are merged with BM25 scores in Python, fused with RRF, and the top-15 results are passed to a cross-encoder re-ranker. Final top-k (≤ 15) is returned to the GapAnalyzer and GuidanceGenerator nodes.

Latency budget: hybrid retrieval target p95 < 500ms, including re-ranking. HNSW index on the chunk table (m=16, ef_construction=64) is required to meet this target beyond 50k active rows.

---

## 3. Data Layer

### D-005 — Database Architecture

**Question:** Single PostgreSQL + pgvector instance or split relational and vector databases?

| Option | Tradeoff |
|---|---|
| PostgreSQL + pgvector | Unified ACID + vector search; single operational surface; RLS enforced in one place; simpler multi-tenancy |
| PostgreSQL + Pinecone/Weaviate | Best-in-class vector performance; two systems to operate, two RLS boundaries to maintain |
| PostgreSQL + Qdrant (self-hosted) | Open source vector DB; operational overhead; strong filtering support |

**Decision criteria:** Multi-tenancy enforcement at vector layer, operational complexity budget, query latency at scale (target: <500ms p95 semantic search).

**Decision:** `DECIDED` — **PostgreSQL 16 + pgvector (single instance)**

A single PostgreSQL instance extended with pgvector unifies ACID guarantees, RLS-based multi-tenancy, and vector similarity search under one operational surface. Key advantages: tenant isolation is written once (RLS policies) and applies to vector queries identically to relational queries; document ingestion and chunk insertion are a single transaction (no eventual consistency window); join capability between requirements and their supporting chunks requires no cross-service round trips.

pgvector's ANN performance with HNSW indexing meets the p95 <500ms retrieval target at MVP scale (estimated <10M chunks per deployment). Re-evaluation against dedicated vector infrastructure is deferred to Sprint 3.

Full schema: `DATABASE.md` Section 1.

---

### D-006 — Caching Layer

**Question:** What caching infrastructure handles session state, idempotency keys, and rate-limit counters?

| Option | Tradeoff |
|---|---|
| Redis (managed — Upstash, ElastiCache) | Industry standard; rich data structures; pub/sub for real-time events |
| DragonflyDB | Redis-compatible; better throughput; smaller ecosystem |
| In-process (no external cache) | Zero infra cost; not horizontally scalable |

**Decision criteria:** Horizontal scalability of API tier, session persistence across restarts, real-time notification support.

**Decision:** `DECIDED` — **Redis 7 (managed)**

Redis is the only option with both `INCRBYFLOAT` atomic operations (required for budget counters) and native pub/sub (required for upload-complete and sign-off events between services). Managed hosting: **Upstash** for MVP (serverless Redis, zero ops, generous free tier). **AWS ElastiCache** as the alternative if deployment is on AWS ECS Fargate and latency consistency is required.

Redis namespaces and eviction policy: `DATABASE.md` Section 2.

---

### D-007 — Object Storage

**Question:** Where are raw uploaded documents stored?

| Option | Tradeoff |
|---|---|
| AWS S3 | Mature; WORM support; strong egress cost at scale |
| Cloudflare R2 | S3-compatible; zero egress cost; newer |
| GCP Cloud Storage | Good EU residency options; GCP-native |
| Azure Blob Storage | Strong EU residency; better for enterprises already on Azure |

**Decision criteria:** Data residency compliance options (EU), egress cost, path-based tenant isolation, WORM compliance for regulated workspaces.

**Decision:** `DECIDED` — **Cloudflare R2 (primary); AWS S3 for regulated workspaces**

R2 is S3-compatible via boto3 `endpoint_url` override — zero application code changes to switch. Zero egress cost is the dominant factor: document uploads and BRD export downloads are the primary cost driver at scale, and R2 eliminates egress entirely.

Exception: workspaces with `compliance_flags` containing `HIPAA` or `SOC2` use AWS S3 with Object Lock (WORM) in Compliance mode. R2 Object Lock is available but newer and less validated in regulated audit contexts.

Path convention and access pattern: `DATABASE.md` Section 3.

---

## 4. Infrastructure

### D-008 — Deployment Platform

**Question:** Where do API servers and async ingestion workers run?

| Option | Tradeoff |
|---|---|
| AWS ECS Fargate | Managed containers; no cluster ops; good cold-start for API (<2s) |
| AWS Lambda | Cheapest for sporadic load; cold-start problematic for streaming responses |
| AWS EKS | Full control; significant ops overhead; right for >10 services |
| Google Cloud Run | Simpler than EKS; good EU regions; GCP lock-in |

**Decision criteria:** Cold-start latency for streaming API responses, worker isolation for long-running ingestion tasks, operational overhead budget for early stage.

**Decision:** `DECIDED` — **AWS ECS Fargate**

Fargate provides managed container execution with no cluster operations. Cold-start is <2s for the Go API gateway (single binary). Long-running document ingestion workers run as separate Fargate tasks, isolated from the API tier. No Kubernetes overhead at this scale.

Local development uses Docker Compose (already implemented in `docker-compose.yml`). All three services + PostgreSQL + Redis are wired and runnable with `docker compose up`.

---

### D-009 — Observability Stack

**Question:** How are LLM costs, traces, and quality metrics tracked?

| Option | Tradeoff |
|---|---|
| Langfuse (self-hosted or cloud) | Open source; LLM-native cost attribution; GDPR-friendly self-host option |
| LangSmith | LangChain-native; good tracing; vendor lock-in |
| Helicone | Simple proxy; lightweight; less agentic tracing depth |
| Custom (OpenTelemetry + Grafana) | Full control; significant build effort |

**Decision criteria:** LLM-native cost attribution per project/agent, budget alerting integration, data residency options.

**Decision:** `DECIDED` — **OpenTelemetry (Sprint 1) → Langfuse (Sprint 2)**

Sprint 1: OpenTelemetry structured traces written to stdout. Rust uses `tracing-subscriber`; Python uses `tracing-opentelemetry`. Zero new infrastructure required; traces are captured in CI and can be inspected locally. This is sufficient to debug the pipeline during Sprint 1.

Sprint 2: Langfuse cloud (or self-hosted for GDPR workspaces). LLM-native cost attribution per project, per agent, and per model tier; budget threshold alerting; conversation replay. The switch from stdout to Langfuse exporter is a single-line config change — no pipeline refactoring needed.

---

### D-010 — CI/CD Pipeline

**Question:** What pipeline runs tests, builds containers, and deploys?

| Option | Tradeoff |
|---|---|
| GitHub Actions | Native GitHub integration; generous free tier; sufficient for most workloads |
| GitLab CI | Better built-in container registry; requires self-hosted or GitLab SaaS |
| CircleCI | Mature; good parallelism; additional vendor |

**Decision criteria:** Container build support, parallel test execution, cost within startup budget.

**Decision:** `DECIDED` — **GitHub Actions**

Already implemented: `.github/workflows/ci.yaml` runs Rust unit tests in Docker on every push. Pipeline runs three parallel jobs: Rust (`cargo test` in Docker), Python (`pytest`), Go (`go test`). Container builds added in Sprint 2 after all three services have test coverage. Free tier is sufficient at current team size.

---

## 5. Identity & Integrations

### D-011 — Authentication Provider

**Question:** How are users authenticated and how are API keys managed?

| Option | Tradeoff |
|---|---|
| Auth0 | Feature-rich; SAML + OIDC + MFA; enterprise pricing at scale |
| AWS Cognito | Cost-effective; tighter AWS integration; complex configuration |
| Clerk | Modern DX; good social + enterprise auth; US-only data by default |
| Self-built (FastAPI + JWT) | Full control; significant security implementation burden |

**Decision criteria:** SAML 2.0 support (enterprise clients), custom JWT claims (tenant_id, plan), API key management, EU data residency option.

**Decision:** `DECIDED` — **Auth0**

Auth0 is the only option that delivers all decision criteria out of the box: SAML 2.0 for enterprise SSO, custom JWT claims for `tenant_id` / `plan` / `role`, machine-to-machine tokens for API key flows, and EU data residency via the EU tenant option. JWT tokens are validated by the Go API gateway using RS256 with Auth0's public JWKS endpoint — no shared secret.

---

### D-012 — Connector Integrations (MVP Set)

**Question:** Which inbound and outbound connector platforms are in scope for MVP?

**Inbound candidates:** Jira, Confluence, Notion, Google Docs/Drive, GitHub, Linear, SharePoint, Slack

**Outbound candidates:** Jira (story creation), Confluence (spec publish), Notion, GitHub Issues, Linear, file export (DOCX/PDF/Markdown)

**Decision criteria:** Client demand, OAuth complexity, rate limit risk, BA team's existing tooling.

**Decision:** `DECIDED`

**Inbound MVP:**
- File upload (PDF, DOCX, XLSX) — the primary path; covers 80% of BA workflows with zero OAuth complexity
- Confluence (read-only) — most common enterprise spec source; OAuth 2.0
- Google Docs/Drive (read-only) — second most common; OAuth 2.0

**Outbound MVP:**
- File export (DOCX, PDF, Markdown) — zero external dependency; BA downloads and distributes
- Jira story creation — deferred to Sprint 3; depends on locked spec + Sign-Off completing first

All other connectors (Notion, GitHub Issues, Linear, SharePoint, Slack) are post-MVP and require a separate integration sprint.

---

### D-013 — Email Delivery

**Question:** What service sends budget alerts, notifications, and sign-off requests?

| Option | Tradeoff |
|---|---|
| AWS SES | Cheapest at volume; requires domain setup; deliverability work needed |
| SendGrid | Good deliverability; generous free tier; straightforward API |
| Postmark | Excellent deliverability; transactional-only focus |

**Decision criteria:** Budget cap alert delivery reliability, EU data residency, developer setup simplicity.

**Decision:** `DECIDED` — **SendGrid**

SendGrid matches all decision criteria: 100 emails/day free tier covers MVP volume; EU data residency available; excellent deliverability without DNS warmup work; Python and Go SDKs are both mature. Use cases: sign-off token dispatch (time-sensitive — reliable delivery essential), budget cap alerts, session summary emails.

---

### D-014 — Speech-to-Text (Deferred)

**Question:** Which STT service handles stakeholder voice recordings uploaded at elicitation checkpoints?

**Status:** `DEFERRED` — Not required for MVP. Re-evaluate at Sprint 2.

Candidates for future evaluation: AssemblyAI (best diarisation), Deepgram (fast + cost), AWS Transcribe (AWS-native).

---

## Decision Governance

- Decisions move from `OPEN` → `GUIDED` when the BA/PM session (Phase 5 of BA HITL Flow) yields a directional answer.
- Decisions move from `GUIDED` → `DECIDED` when engineering validates the choice against performance and cost criteria.
- Once `DECIDED`, a decision is locked. Changes require creating a new decision entry (D-XXX supersedes D-YYY) rather than editing this record.
- `DEFERRED` decisions are reviewed at the sprint named in their entry and may be decided, deferred again, or dropped.

---

> Chitragupt Key Decisions • Sprint 0 • CLOSED • May 2026
