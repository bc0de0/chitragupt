# Contributing to Chitragupt

Chitragupt is a polyglot monorepo — Rust for the state machine kernel, Python for AI orchestration, and Go for the API gateway. This guide covers how to get each service running, conventions for all three, and project-specific rules that are easy to miss.

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Rust | See `rust-toolchain.toml` | State machine service |
| Python | 3.11+ | AI orchestration service |
| Go | 1.22+ | API gateway service |
| `protoc` | 3.21+ | Protobuf compilation |
| Docker + Compose | v2+ | Local infrastructure (PostgreSQL, Redis) |
| `uv` | Latest | Python dependency management |

---

## Repository Layout

```
chitragupt/
├── services/
│   ├── state-machine/    Rust — gRPC state engine (:50051)
│   ├── ai-orchestration/ Python — LangGraph pipeline (:50052)
│   └── api-gateway/      Go — WebSocket + REST gateway (:8080)
├── proto/                Protobuf definitions (source of truth)
├── docs/                 Project documentation
│   ├── sprints/          Sprint planning
│   └── architecture/     Technical reference
└── tech-docs/            Deep-dive technical documentation
```

---

## Getting Started

### 1. Start Infrastructure

```bash
docker compose up -d postgres redis
```

PostgreSQL runs on `:5432`, Redis on `:6379`. Migrations run automatically on first start.

### 2. Rust — State Machine

```bash
cd services/state-machine
cargo build
cargo run

# Run tests
cargo test

# With structured logging
RUST_LOG=debug cargo run
```

The `rust-toolchain.toml` at the repo root pins the Rust toolchain version. `rustup` picks it up automatically.

### 3. Python — AI Orchestration

```bash
cd services/ai-orchestration
uv sync
uv run python -m chitragupt.server

# Run tests
uv run pytest

# Type check
uv run mypy --strict src/
```

Required environment variables (copy `.env.example` to `.env`):

```
ANTHROPIC_API_KEY=...
VOYAGE_API_KEY=...
DATABASE_URL=postgres://chitragupt:chitragupt@localhost:5432/chitragupt
REDIS_URL=redis://localhost:6379
STATE_MACHINE_ADDR=localhost:50051
```

### 4. Go — API Gateway

```bash
cd services/api-gateway
go build ./...
go run ./cmd/server

# Run tests
go test ./...
```

Required environment variables:

```
STATE_MACHINE_ADDR=localhost:50051
AI_ORCHESTRATION_ADDR=localhost:50052
DATABASE_URL=postgres://chitragupt:chitragupt@localhost:5432/chitragupt
REDIS_URL=redis://localhost:6379
JWT_PUBLIC_KEY=<RS256 public key>
```

---

## Development Conventions

### Git

**Branch naming:**

```
feat/sprint-N-short-description
fix/issue-id-short-description
chore/short-description
docs/short-description
```

**Commit format** (Conventional Commits):

```
<type>(<scope>): <description>

Types: feat | fix | docs | style | refactor | perf | test | chore
```

Examples:
```
feat(state-machine): add AC evaluator for CONSTRAINT_CAPTURE phase
fix(ai-orchestration): retry LLM call on rate limit with exponential backoff
docs(tech-docs): add gate system section to state machine reference
```

Breaking changes: append `!` to the type, e.g. `feat(proto)!: rename TurnRequest field`.

---

### Rust Conventions

- **No `unwrap()` or `expect()` in library code.** Use `?` and typed errors (`thiserror`).
- **All public functions have typed errors.** Return `Result<T, StateError>`, not `Result<T, Box<dyn Error>>`.
- **No `println!` in production paths.** Use `tracing::info!`, `tracing::warn!`, `tracing::error!`.
- **`cargo clippy` must pass.** Run before every commit: `cargo clippy -- -D warnings`.
- **`cargo fmt` enforced.** Format is non-negotiable: `cargo fmt --check` runs in CI.

---

### Python Conventions

- **Formatter:** `black` (line length 88, default config). Run `black .` before committing.
- **Import ordering:** `isort` with `--profile black`. Run `isort .` before committing.
- **Type hints mandatory** on all function signatures. `mypy --strict` must pass on the `src/` directory.
- **All LLM calls use pinned model versions.** No floating aliases like `claude-sonnet-latest`. See `docs/sprints/sprint0/TECH_STACK.md` for the current pinned model IDs.
- **Pydantic schemas for all LLM structured output.** No `json.loads` on raw LLM strings.
- **Retry all LLM calls** with `tenacity` — exponential backoff, max 3 retries, different vendor on fallback.

---

### Go Conventions

- **`go vet` and `staticcheck` must pass** before merging.
- **No business logic in handlers.** Handlers translate HTTP ↔ gRPC and nothing else. AC evaluation, session logic, and LLM decisions live in Rust and Python respectively.
- **Structured logging with `zap`.** No `fmt.Println` in production paths.
- **All context values carry `tenant_id`.** Middleware extracts it from JWT and stores it in `context.Context`. Any database query that omits `tenant_id` is a security defect.

---

## Protobuf Changes

The `.proto` files in `proto/` are the contract between all three services. Changes require coordination:

1. Update the `.proto` file.
2. Regenerate stubs for all three services (see `tech-docs/state-machine.md` Section 12).
3. Commit the `.proto` change and all three generated stub files in a single commit.
4. Never remove or renumber an existing field — add new fields with new numbers instead.

---

## Adding AC Criteria

Acceptance criteria live in `services/state-machine/src/ac/`. Each phase has its own file (`s1.rs` through `s6.rs`).

1. Open the relevant `s{N}.rs` file.
2. Add a `check(id, description, condition, suggested_question)` call.
3. Run `cargo test`.
4. Add the criterion to the AC table in `docs/sprints/sprint1/README.md` for the relevant transition.

The criterion ID format is `AC-S{phase}-{number}` for conversational criteria and `AC-S{phase}-U{number}` for upload-related criteria.

---

## Adding a Hard Gate

Hard gates live in `services/state-machine/src/gates/manager.rs`.

1. Add an `UploadGate` entry in `all_gates_for_session`.
2. Document the gate in `tech-docs/state-machine.md` Section 6.
3. Write an integration test that confirms the gate fires and `TransitionEngine::attempt` returns `Err(StateError::HardGateBlocking { ... })`.

---

## Pull Request Checklist

Before opening a PR:

- [ ] Branch name follows `feat/fix/chore/docs` convention
- [ ] Commit messages follow Conventional Commits format
- [ ] For Rust: `cargo clippy`, `cargo fmt --check`, `cargo test` all pass
- [ ] For Python: `black --check .`, `isort --check .`, `mypy --strict src/`, `pytest` all pass
- [ ] For Go: `go vet ./...`, `go test ./...` pass
- [ ] Proto changes include all three generated stub files committed together
- [ ] New AC criteria are documented in `docs/sprints/sprint1/README.md`
- [ ] New hard gates are documented in `tech-docs/state-machine.md`
- [ ] No pinned model IDs changed without updating `docs/sprints/sprint0/TECH_STACK.md`

---

## Questions and Support

For questions about the system architecture, see:

- `docs/sprints/sprint0/TECH_STACK.md` — service design, data flow, library choices
- `tech-docs/state-machine.md` — state machine kernel deep-dive
- `docs/sprints/sprint0/ARCHITECTURE.md` — trust hierarchy, invariants, engineering conventions
- `docs/sprints/sprint1/README.md` — Sprint 1 priorities and epic breakdown

For anything else, open an issue or reach out to the engineering lead.

---

> Chitragupt · Contributing Guide · May 2026
