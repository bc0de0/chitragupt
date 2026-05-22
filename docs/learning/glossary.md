# Glossary — Chitragupt Technical Terms

**Purpose:** Every technical term used in the Chitragupt codebase, sprint documents, and playbooks — defined in plain language with cross-references to deeper topic files.

> Terms are alphabetical within each letter section. Cross-references use the format → *topic-file* or → *Other Term*.

---

## A

**Acceptance Criteria (AC)**
The specific, testable conditions that must be true for a user story to be considered done. Written in GIVEN/WHEN/THEN format. See also → *Definition of Done*, → *User Story*.

**ADR (Architecture Decision Record)**
A short document that captures one architectural decision — the question, the choice made, the alternatives considered, and the rationale. Chitragupt stores all ADRs in `docs/sprints/sprint0/DECISIONS.md`.

**Agent (AI)**
An AI system that can take actions in sequence to accomplish a goal — not just respond to a single prompt. Chitragupt is itself an agentic system: it asks questions, evaluates answers, and guides a multi-step workflow.

**Anthropic**
The AI safety company that created the Claude family of models. Chitragupt uses Claude models exclusively for generation and synthesis tasks. → See [01-llm-and-ai.md](01-llm-and-ai.md).

**API (Application Programming Interface)**
A defined contract for how two software components communicate. In Chitragupt: the Go service exposes a REST/WebSocket API to clients; Rust and Python communicate internally via gRPC APIs.

**Async / Await**
A pattern for writing non-blocking code — the program can do other work while waiting for a slow operation (database call, LLM response) to complete. Both Python (asyncio) and Rust (tokio) use this model. → See [02-ai-orchestration.md](02-ai-orchestration.md).

**asyncio.Queue**
A Python async-safe queue used to pass tokens from a background LLM streaming task to the HTTP response stream. The `PipelineExecutor` uses a Queue of max size 256, with `None` as a sentinel to signal stream completion. → See [02-ai-orchestration.md](02-ai-orchestration.md).

---

## B

**BA (Business Analyst)**
The primary user of Chitragupt. A BA facilitates requirements conversations between stakeholders and engineering, producing BRDs and HLDs. Chitragupt is designed to guide BAs through this process via the HITL conversation flow.

**BM25**
A classical information retrieval algorithm (Best Match 25) that ranks documents by keyword frequency and rarity. Used as the "sparse" component of Chitragupt's hybrid vector search — 30% weight alongside 70% dense (cosine) retrieval. → See [03-data-and-storage.md](03-data-and-storage.md).

**BRD (Business Requirements Document)**
The primary deliverable of the requirements phase. A structured document that captures functional requirements, non-functional requirements, scope, stakeholders, assumptions, and a traceability matrix linking requirements to their sources.

**Branch (git)**
An isolated line of development. Chitragupt convention: `feat/sprint-N-name`, `fix/id-name`, `chore/name`. Never commit directly to `main`.

**Budget Degradation**
The strategy of automatically downgrading to cheaper/faster AI models as per-session spend approaches the hard limit. Chitragupt has four stages: NORMAL → CAUTION ($3.00) → CRITICAL ($4.50) → EXHAUSTED ($5.00). → See [01-llm-and-ai.md](01-llm-and-ai.md).

---

## C

**Cache Hit / Cache Miss**
When a prompt (or part of a prompt) is served from Anthropic's prompt cache rather than being re-processed, it is a cache hit — much cheaper. A cache miss means the full prompt was processed fresh. Target: ≥80% cache hit rate. → See [01-llm-and-ai.md](01-llm-and-ai.md).

**CI/CD (Continuous Integration / Continuous Delivery)**
Automated pipelines that run tests, lint, build, and deploy code on every pull request or push. Chitragupt uses GitHub Actions with parallel jobs per language (Rust, Python, Go). → See [05-devops-and-ci.md](05-devops-and-ci.md).

**Circuit Breaker**
A pattern that stops calling a failing service after a threshold of failures, giving it time to recover. Chitragupt's `LLMFactory` marks a provider degraded for 60 seconds after 3 consecutive failures. → See [02-ai-orchestration.md](02-ai-orchestration.md).

**Context Window**
The maximum number of tokens an LLM can process in a single call (input + output combined). Claude Opus 4.7 and Sonnet 4.6 have 1M token context windows. Haiku 4.5 has 200k. → See [01-llm-and-ai.md](01-llm-and-ai.md).

**Conventional Commits**
A commit message format standard: `<type>(<scope>): <description>`. Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`. Required for all Chitragupt commits.

**Cosine Similarity**
A measure of how similar two vectors are based on the angle between them (not magnitude). Used as the distance metric for dense vector search in pgvector. Range: –1 to 1, where 1 = identical direction. → See [03-data-and-storage.md](03-data-and-storage.md).

---

## D

**Dense Retrieval**
Vector search using embedding representations — finding semantically similar content even when exact keywords don't match. Chitragupt uses `voyage-large-2` embeddings at 1536 dimensions. 70% weight in hybrid search. → See [01-llm-and-ai.md](01-llm-and-ai.md) and [03-data-and-storage.md](03-data-and-storage.md).

**Definition of Done (DoD)**
The agreed checklist that must be satisfied before a story or epic is marked complete. Typically: code written, tests pass, CI green, PR reviewed and merged.

**Docker**
A platform for packaging software and its dependencies into portable containers. Chitragupt uses multi-stage Docker builds — a builder image compiles/installs, a minimal runtime image ships. → See [05-devops-and-ci.md](05-devops-and-ci.md).

---

## E

**Embedding**
A numerical representation (vector) of a piece of text that captures its semantic meaning. Similar texts have similar embeddings. Chitragupt uses Voyage AI's `voyage-large-2` model to embed documents and queries for vector search. → See [01-llm-and-ai.md](01-llm-and-ai.md).

**Enum**
A type that represents a fixed set of named values. In Rust, `SessionPhase` is an enum with variants for each phase of the BA conversation (e.g. `ProblemIntake`, `StakeholderMapping`). → See [04-systems-and-apis.md](04-systems-and-apis.md).

**Epic**
A large unit of work in Jira/Linear that groups related user stories. Epics map to major product capabilities (e.g. "Sprint 1: State Machine Kernel"). P1 = must complete in sprint; P2 = complete if P1 done; P3 = stretch.

---

## F

**Fallback Model**
A secondary LLM from a different vendor, used when the primary fails. Chitragupt falls back from Anthropic Claude to Google Gemini (`gemini-2.0-flash`). → See [01-llm-and-ai.md](01-llm-and-ai.md).

**FastAPI**
A Python web framework for building REST APIs with automatic OpenAPI documentation. Used in Chitragupt's Python AI orchestration service to expose internal endpoints. → See [02-ai-orchestration.md](02-ai-orchestration.md).

**Fibonacci (story points)**
The point scale used for story estimation: 1, 2, 3, 5, 8, 13. Non-linear to reflect that larger work is harder to estimate precisely.

**Function Calling (Tool Use)**
The ability of an LLM to invoke structured functions/tools rather than just generating text. Chitragupt's AI pipeline uses tool use to extract structured requirements and entities from conversation.

---

## G

**Gate (workflow)**
A checkpoint that must be satisfied before a BA session can advance to the next phase. Four types: `HARD` (session halts), `REQUIRED_PROMPT` (AI prompts for missing info), `TRIGGERED` (context-dependent), `RECOMMENDED` (soft suggestion). → See [04-systems-and-apis.md](04-systems-and-apis.md).

**GitHub Actions**
A CI/CD automation platform built into GitHub. Chitragupt uses workflow YAML files in `.github/workflows/` to run tests on every PR. → See [05-devops-and-ci.md](05-devops-and-ci.md).

**Go (Golang)**
A statically typed, compiled language from Google. Used for Chitragupt's API gateway because of its excellent HTTP/WebSocket performance and lightweight concurrency (goroutines). → See [04-systems-and-apis.md](04-systems-and-apis.md).

**goroutine**
A lightweight concurrent unit in Go — much cheaper than a thread. The Go API gateway uses goroutines to handle thousands of concurrent WebSocket connections. → See [04-systems-and-apis.md](04-systems-and-apis.md).

**gRPC**
A high-performance RPC framework using HTTP/2 and Protocol Buffers. Used for internal service-to-service communication in Chitragupt: Go↔Rust and Rust↔Python. → See [04-systems-and-apis.md](04-systems-and-apis.md).

---

## H

**Hard Gate**
A `HARD` type gate in Chitragupt's state machine — the session halts and cannot advance until the condition is satisfied (e.g. a signed document must be uploaded before requirements are approved). → See → *Gate*.

**HLD (High-Level Design / Architecture Diagram)**
A set of diagrams showing the system's services, data flows, and interactions — designed for client sign-off. Typically includes System Overview, User Journey, Data Flow, and Security/Tenancy diagrams.

**HITL (Human in the Loop)**
A design pattern where a human provides input or approval at key decision points in an AI pipeline — rather than the AI operating fully autonomously. Chitragupt is HITL by design: every phase requires BA confirmation before progressing.

**HNSW (Hierarchical Navigable Small World)**
A graph-based approximate nearest neighbour index algorithm for vector search. Fast at query time. Chitragupt uses HNSW in pgvector with `m=16`, `ef_construction=64` on `vector(1536)` columns. → See [03-data-and-storage.md](03-data-and-storage.md).

**Hybrid Search**
Combining dense (semantic) and sparse (keyword) retrieval, then fusing results. Chitragupt: 70% cosine + 30% BM25 weight, top-50 candidates re-ranked to top-20. → See [03-data-and-storage.md](03-data-and-storage.md).

---

## I

**Inference**
The act of running an LLM on an input to generate an output. "Inference cost" = the cost per API call in dollars.

**IVFFlat**
An older pgvector index type (Inverted File Flat) — faster to build than HNSW but slower at query time for large datasets. Chitragupt uses HNSW. → See [03-data-and-storage.md](03-data-and-storage.md).

---

## J

**JWT (JSON Web Token)**
A compact, signed token used to authenticate API requests. Chitragupt's Go gateway validates JWTs on every request and extracts `tenant_id` from the claims to enforce multi-tenancy. → See [04-systems-and-apis.md](04-systems-and-apis.md).

---

## K

**k-NN (k-Nearest Neighbour)**
Finding the `k` most similar vectors to a query vector. The foundation of all vector search. pgvector implements exact k-NN and approximate k-NN (via HNSW/IVFFlat). → See [03-data-and-storage.md](03-data-and-storage.md).

---

## L

**LangGraph**
A Python framework for building stateful, multi-step AI pipelines as directed graphs. Each node is a processing step; edges define the flow. Chitragupt's AI orchestration service is built as a LangGraph pipeline. → See [02-ai-orchestration.md](02-ai-orchestration.md).

**Latency**
The time from request sent to first response received. A critical design constraint for interactive BA sessions — target <2s for most LLM calls, <500ms for routing decisions.

**Linear**
A project management tool (alternative to Jira) used for issue tracking, sprint planning, and backlog management. Referenced throughout the playbooks and prompt library.

**LLM (Large Language Model)**
A neural network trained on massive text datasets that can generate, summarise, classify, and reason about text. GPT-4, Claude, and Gemini are all LLMs. Chitragupt uses Claude as its primary LLM provider. → See [01-llm-and-ai.md](01-llm-and-ai.md).

**LLMFactory**
Chitragupt's Python class that manages LLM client initialization, budget-based model selection, and provider circuit breaking. Lazily initializes SDK clients. → See [02-ai-orchestration.md](02-ai-orchestration.md).

---

## M

**MCP (Model Context Protocol)**
A standard protocol that allows Claude (and other LLMs) to use external tools — Jira, Linear, Confluence, GitHub — via structured tool calls. Chitragupt's prompt library is designed for use when Claude has MCP access.

**Migration (database)**
A versioned, repeatable script that modifies a database schema in a controlled way. Chitragupt uses append-only migrations: never modify a migration after it is merged.

**Model ID (pinned)**
A specific, immutable identifier for an LLM version (e.g. `claude-sonnet-4-6`). Chitragupt policy: always use pinned model IDs, never floating aliases. This prevents silent model upgrades from changing behaviour.

**Monolith vs Polyglot**
Monolith = one codebase in one language. Polyglot = multiple services in multiple languages, each chosen for its strengths. Chitragupt is polyglot: Rust for correctness, Python for AI, Go for HTTP performance.

**mypy**
A static type checker for Python. Chitragupt runs mypy with `--strict` flag in CI. → See [05-devops-and-ci.md](05-devops-and-ci.md).

---

## N

**NFR (Non-Functional Requirement)**
Requirements about *how* a system behaves rather than *what* it does — performance, security, scalability, availability, compliance. Must be as testable as functional requirements.

**Node (LangGraph)**
A single processing step in a LangGraph pipeline — a Python function or class that receives state, does work, and returns updated state. Chitragupt's pipeline has 5 nodes: IntentClassifier → EntityExtractor → RAGRetrieval → GapAnalyzer → GuidanceGenerator. → See [02-ai-orchestration.md](02-ai-orchestration.md).

---

## O

**ONTOLOGY**
A formal definition of the entities in a system, their attributes, and relationships. `docs/sprints/sprint0/ONTOLOGY.md` defines what a `Session`, `Requirement`, `Stakeholder`, `Document`, and other entities are in Chitragupt.

**Orchestration**
The coordination of multiple AI model calls, tool invocations, and data retrievals into a coherent pipeline. LangGraph is Chitragupt's orchestration framework. → See [02-ai-orchestration.md](02-ai-orchestration.md).

---

## P

**pgvector**
A PostgreSQL extension that adds vector storage and similarity search. Chitragupt uses pgvector with HNSW indexing for semantic document retrieval. → See [03-data-and-storage.md](03-data-and-storage.md).

**Pipeline**
A sequence of processing steps where the output of one step feeds the input of the next. Chitragupt's AI pipeline processes each BA conversation turn through 5 nodes. → See [02-ai-orchestration.md](02-ai-orchestration.md).

**Polyglot Architecture**
See → *Monolith vs Polyglot*.

**Prompt Caching**
An Anthropic feature that stores the processed representation of a prompt prefix in the API, so repeated calls with the same prefix are cheaper and faster. Chitragupt targets ≥80% cache hit rate. → See [01-llm-and-ai.md](01-llm-and-ai.md).

**Protobuf (Protocol Buffers)**
A language-neutral format for serialising structured data, developed by Google. Used to define gRPC service contracts. `.proto` files are the source of truth for all service interfaces. → See [04-systems-and-apis.md](04-systems-and-apis.md).

**Pydantic**
A Python library for data validation using type annotations. Chitragupt uses Pydantic for all request/response models and the `PipelineState` TypedDict. → See [02-ai-orchestration.md](02-ai-orchestration.md).

---

## Q

**Quality Floor**
The minimum acceptable model tier for a given output. Chitragupt's quality floor for BRD generation = `standard` (Sonnet) — even when budget is constrained, final deliverables cannot use the `fast` (Haiku) tier.

---

## R

**RAG (Retrieval-Augmented Generation)**
A technique where relevant documents are retrieved from a knowledge base and injected into the LLM's context before generation. Improves accuracy by grounding the LLM in factual content. Chitragupt's RAGRetrieval node does this. → See [01-llm-and-ai.md](01-llm-and-ai.md) and [03-data-and-storage.md](03-data-and-storage.md).

**Redis**
An in-memory data store used for caching, session state, and pub/sub messaging. Chitragupt uses Redis for active session state and Go→Python event subscriptions. → See [03-data-and-storage.md](03-data-and-storage.md).

**Re-ranking**
A second-stage retrieval step that re-orders search results using a more expensive but more accurate model. Chitragupt retrieves top-50 candidates then re-ranks to top-20.

**RLS (Row Level Security)**
A PostgreSQL feature that enforces per-row access control at the database level — each query automatically filters to the current tenant's rows. Prevents data leakage between tenants. → See [03-data-and-storage.md](03-data-and-storage.md).

**REST**
A style for designing HTTP APIs using standard methods (GET, POST, PUT, DELETE) and URL structure. Chitragupt's Go gateway exposes REST endpoints for external clients.

**Rust**
A systems programming language that guarantees memory safety without a garbage collector. Used for Chitragupt's state machine kernel because the compiler enforces exhaustive pattern matching on all phase transitions. → See [04-systems-and-apis.md](04-systems-and-apis.md).

---

## S

**Schema**
The definition of a database's tables, columns, types, and constraints. In Chitragupt, schemas are defined in SQL migration files and must follow append-only migration rules.

**Singleton**
A pattern where only one instance of an object exists in the process. Chitragupt's compiled LangGraph pipeline is a process-level singleton — built once at startup, shared across all requests.

**Sparse Retrieval**
Keyword-based document retrieval (e.g. BM25). Finds documents that contain specific words. Combined with → *Dense Retrieval* in hybrid search.

**Sprint**
A time-boxed iteration of development work (typically 2 weeks). Sprint 0 = foundation documents only; Sprint 1 = core engine. Chitragupt uses a 7-phase sprint model.

**Stakeholder**
Any person who has an interest in the product — users, buyers, compliance officers, engineers. Identifying and mapping stakeholders is Phase 0 of the Chitragupt HITL flow.

**State Machine**
A design pattern where a system can only be in one defined state at a time, and transitions between states follow explicit rules. Chitragupt's `SessionPhase` state machine (in Rust) enforces the BA conversation flow. → See [04-systems-and-apis.md](04-systems-and-apis.md).

**Streaming (LLM)**
Delivering LLM output token-by-token as it is generated rather than waiting for the full response. Improves perceived responsiveness. Chitragupt streams via `asyncio.Queue` and Server-Sent Events. → See [02-ai-orchestration.md](02-ai-orchestration.md).

---

## T

**Tenant**
A customer organization in a multi-tenant system. All data in Chitragupt is scoped to a `tenant_id` — one tenant cannot see another's sessions, documents, or requirements.

**Token**
The basic unit of text an LLM processes — roughly 0.75 words. LLM pricing is per million tokens (MTok). Context windows are measured in tokens.

**tokio**
The async runtime for Rust — provides the executor, timers, and I/O primitives that make async Rust work. Chitragupt's state machine service uses tokio. → See [04-systems-and-apis.md](04-systems-and-apis.md).

**tonic**
A Rust library for building gRPC services. Chitragupt's Rust service uses tonic to implement the StateEngine gRPC interface. → See [04-systems-and-apis.md](04-systems-and-apis.md).

**TypedDict**
A Python type that defines a dictionary with specific key-value types. Chitragupt's `PipelineState` is a TypedDict — it defines exactly what fields flow through the LangGraph pipeline. → See [02-ai-orchestration.md](02-ai-orchestration.md).

**Traceability Matrix**
A table in the BRD that links each requirement to its source (Jira story, interview, document) and to its implementation. Makes scope changes visible and auditable.

---

## U

**User Story**
A unit of work written from the user's perspective: "As a [role], I want [capability] so that [outcome]." Must have GIVEN/WHEN/THEN acceptance criteria and a story point estimate.

**uv**
A fast Python package manager and virtual environment tool written in Rust. Chitragupt uses uv for dependency management and Docker builds in the Python service. → See [05-devops-and-ci.md](05-devops-and-ci.md).

---

## V

**Vector**
A list of numbers (floating-point) that represents a piece of data in a high-dimensional space. In AI, text is converted to vectors (→ *Embedding*) to enable semantic similarity comparisons.

**Vector Database**
A database optimised for storing and searching vectors by similarity. pgvector adds this capability to PostgreSQL. → See [03-data-and-storage.md](03-data-and-storage.md).

**Velocity (sprint)**
The number of story points a team completes per sprint. Used to forecast future sprint capacity and measure team throughput trend.

---

## W

**WebSocket**
A bidirectional, persistent communication channel between client and server over a single TCP connection. Used by Chitragupt's Go gateway to stream AI responses to the BA's browser in real time.

---

> Chitragupt Learning Hub · Glossary · v0.1 · May 2026
