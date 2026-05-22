# PB-07 — CI/CD & Delivery

**Version:** v0.1
**The question:** How do we ship reliably — what does the CI pipeline check, how are polyglot services containerized, and what does "green" mean?
**When to use:** Sprint 0 (CI design), Sprint 1 (implementation). CI runs on every push. "It works on my machine" is not a standard.

---

## Why CI Is a Sprint 0 Decision

CI configuration is architecture. A CI pipeline that runs the wrong tests, on the wrong platform, with a non-pinned toolchain will give you green builds that hide real failures. The Chitragupt build learned this directly: a `rust:stable` Docker image resolved differently between local and CI; a `stable-x86_64-pc-windows-gnu` channel string caused a platform mismatch failure in CI.

Define your CI contract before writing production code. Fixing CI after Sprint 1 is much harder than configuring it before.

---

## Polyglot CI Architecture

A three-service polyglot system needs a CI pipeline that tests all three services independently, in parallel, without them needing to be running simultaneously.

```mermaid
flowchart TD
    PUSH([git push to main]) --> TRIGGER[GitHub Actions triggers\non push + PR]

    TRIGGER --> PAR1 & PAR2 & PAR3

    PAR1["🦀 Rust job\n1. cargo fmt --check\n2. cargo clippy -- -D warnings\n3. cargo build\n4. cargo test"]

    PAR2["🐍 Python job\n1. uv sync\n2. black --check\n3. isort --check\n4. mypy --strict src/\n5. pytest"]

    PAR3["🐹 Go job\n1. go build ./...\n2. go vet ./...\n3. staticcheck ./...\n4. go test ./..."]

    PAR1 --> PASS{All jobs green?}
    PAR2 --> PASS
    PAR3 --> PASS

    PASS -->|Yes| DOCKER[Build Docker images\nfor all three services\nDocker build only — no push on PR]
    PASS -->|No| BLOCK[Block merge\nBranch protection enforced]

    DOCKER --> DONE([PR may be merged])

    style DONE fill:#1B5E20,color:#fff,stroke:none
    style BLOCK fill:#B71C1C,color:#fff,stroke:none
```

---

## GitHub Actions Template

```yaml
# .github/workflows/ci.yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

env:
  CARGO_INCREMENTAL: 0
  CARGO_TERM_COLOR: always

jobs:
  # ── Rust ──────────────────────────────────────────────────────────────
  rust:
    name: Rust — state-machine
    runs-on: ubuntu-latest

    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: chitragupt
          POSTGRES_PASSWORD: chitragupt
          POSTGRES_DB: chitragupt_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      # Pin toolchain — never use 'stable' without a version
      # rust-toolchain.toml at repo root pins the version automatically
      - name: Install Rust toolchain
        uses: dtolnay/rust-toolchain@stable
        with:
          components: rustfmt, clippy

      - name: Cache Cargo dependencies
        uses: actions/cache@v4
        with:
          path: |
            ~/.cargo/registry
            ~/.cargo/git
            target/
          key: ${{ runner.os }}-cargo-${{ hashFiles('**/Cargo.lock') }}

      - name: Formatting check
        run: cargo fmt --check

      - name: Clippy (deny all warnings)
        run: cargo clippy -- -D warnings

      - name: Build
        run: cargo build --locked

      - name: Tests
        env:
          DATABASE_URL: postgres://chitragupt:chitragupt@localhost:5432/chitragupt_test
        run: cargo test

  # ── Python ────────────────────────────────────────────────────────────
  python:
    name: Python — ai-orchestration
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Install dependencies
        working-directory: services/ai-orchestration
        run: uv sync --dev

      - name: Formatting check (black)
        working-directory: services/ai-orchestration
        run: uv run black --check .

      - name: Import order check (isort)
        working-directory: services/ai-orchestration
        run: uv run isort --check .

      - name: Type checking (mypy --strict)
        working-directory: services/ai-orchestration
        run: uv run mypy --strict src/

      - name: Tests
        working-directory: services/ai-orchestration
        env:
          # Use test doubles — no real API keys in CI
          ANTHROPIC_API_KEY: test-key
          VOYAGE_API_KEY: test-key
        run: uv run pytest

  # ── Go ────────────────────────────────────────────────────────────────
  go:
    name: Go — api-gateway
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version-file: services/api-gateway/go.mod

      - name: Build
        working-directory: services/api-gateway
        run: go build ./...

      - name: Vet
        working-directory: services/api-gateway
        run: go vet ./...

      - name: Tests
        working-directory: services/api-gateway
        run: go test ./...

  # ── Docker smoke test ─────────────────────────────────────────────────
  docker:
    name: Docker build
    runs-on: ubuntu-latest
    needs: [rust, python, go]   # Only run if all service tests pass

    steps:
      - uses: actions/checkout@v4

      - name: Build state-machine image
        run: docker build -f services/state-machine/Dockerfile .

      - name: Build ai-orchestration image
        run: docker build -f services/ai-orchestration/Dockerfile .

      - name: Build api-gateway image
        run: docker build -f services/api-gateway/Dockerfile .
```

---

## Docker Strategy for Polyglot Services

Every service needs a Dockerfile. Multi-stage builds are non-negotiable for production images — the builder stage has compilers and toolchains; the runtime stage has only the binary.

### Rust Dockerfile Pattern

```dockerfile
# services/state-machine/Dockerfile

# Stage 1: Build
FROM rust:1-slim AS builder
WORKDIR /app

# Install protoc (required for prost code generation)
RUN apt-get update && apt-get install -y protobuf-compiler && rm -rf /var/lib/apt/lists/*

# Cache dependencies separately (only rebuilt when Cargo.lock changes)
COPY Cargo.toml Cargo.lock ./
COPY services/state-machine/Cargo.toml services/state-machine/
RUN mkdir -p services/state-machine/src && echo "fn main(){}" > services/state-machine/src/main.rs
RUN cargo build --release -p state-machine
RUN rm services/state-machine/src/main.rs

# Copy actual source and build
COPY services/state-machine/ services/state-machine/
RUN cargo build --release -p state-machine

# Stage 2: Runtime (minimal image)
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/target/release/state-machine /usr/local/bin/state-machine
EXPOSE 50051
CMD ["state-machine"]
```

### Python Dockerfile Pattern

```dockerfile
# services/ai-orchestration/Dockerfile

# Stage 1: Build (install dependencies)
FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install uv
COPY services/ai-orchestration/pyproject.toml services/ai-orchestration/uv.lock ./
RUN uv sync --no-dev --frozen

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY services/ai-orchestration/src/ ./src/
COPY services/ai-orchestration/config/ ./config/
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 50052
CMD ["python", "-m", "ai_orchestration.server"]
```

### Go Dockerfile Pattern

```dockerfile
# services/api-gateway/Dockerfile

# Stage 1: Build
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY services/api-gateway/go.mod services/api-gateway/go.sum ./
RUN go mod download
COPY services/api-gateway/ ./
RUN CGO_ENABLED=0 GOOS=linux go build -o api-gateway ./cmd/server

# Stage 2: Runtime (scratch — smallest possible image)
FROM scratch
COPY --from=builder /app/api-gateway /api-gateway
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
EXPOSE 8080
CMD ["/api-gateway"]
```

---

## Test Strategy Matrix

Different types of tests belong at different levels. This table tells you what to write for each service.

| Test type | Rust | Python | Go | What it proves |
|---|---|---|---|---|
| **Unit** | AC evaluators, gate logic, transition guards | Node logic with mock LLM clients | Handler logic with mock gRPC clients | Individual functions work correctly |
| **Integration** | State transitions with real PostgreSQL | Pipeline end-to-end with real DB (no live LLM) | WebSocket + REST with real gRPC server (test stubs) | Components work together |
| **E2E** | Full session from Phase 1 to Phase 4 | LLM pipeline with live provider (staging only) | Full request through all three services | System works end to end |
| **Contract** | Proto schema validation | Proto message serialization | Proto client compatibility | Service interfaces are compatible |

### Test Naming Convention

```
# Rust
#[test]
fn test_ac_s1_rejects_empty_problem_statement() { ... }
fn test_hard_gate_blocks_transition_when_no_brd() { ... }

# Python
def test_intent_classifier_returns_answer_for_factual_message(): ...
def test_guidance_generator_falls_back_on_budget_exhaustion(): ...

# Go
func TestChatHandler_ForwardsTokensToWebSocket(t *testing.T) { ... }
func TestJWTMiddleware_RejectsExpiredToken(t *testing.T) { ... }
```

---

## Protobuf Change Protocol

Proto changes affect all three services simultaneously. This is the most dangerous type of change in a polyglot system.

```
PROTO CHANGE PROTOCOL
----------------------

1. Change the .proto file ONLY.
   Do not change any generated stub files by hand.

2. Regenerate stubs for all three languages:
   # Rust (via prost — runs automatically on cargo build)
   cargo build

   # Go stubs
   protoc --go_out=. --go-grpc_out=. proto/state_engine.proto

   # Python stubs
   python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. proto/state_engine.proto

3. Commit the .proto change AND all three generated stub files in ONE commit.
   Never commit a .proto change without updating all stubs.
   Never commit stub changes without the .proto change.

4. NEVER remove or renumber an existing field.
   - Removing field 3 makes existing serialized data that uses field 3 unreadable.
   - Adding a new field: use the next available field number.
   - Deprecating a field: mark with [deprecated = true]; do not remove.

5. Test proto changes in all three services before merging.
   A proto change that compiles in Rust but breaks the Python servicer is a broken change.
```

---

## CI Completeness Checklist

```
CI/CD SIGN-OFF
---------------

[ ] GitHub Actions workflow exists at .github/workflows/ci.yaml
[ ] CI runs on push to main AND on PRs targeting main
[ ] Rust job: cargo fmt --check + cargo clippy -D warnings + cargo test
[ ] Python job: black + isort + mypy --strict + pytest
[ ] Go job: go vet + staticcheck + go test
[ ] Docker build job runs after all service jobs pass
[ ] Rust toolchain is pinned in rust-toolchain.toml (no "stable" channel string)
[ ] Branch protection enabled: merge requires green CI
[ ] No API keys in CI environment — use test doubles or mock servers
[ ] Dependency caching configured (Cargo + uv + Go module cache)
[ ] Test database wired up for integration tests (PostgreSQL service container)
[ ] Proto change protocol documented and linked from CONTRIBUTING.md
```

---

## What Goes Wrong Without This

| Skipped step | Typical consequence | When it surfaces |
|---|---|---|
| No pinned toolchain | `cargo fmt` on CI uses different version than local; formatting check fails intermittently | First PR |
| mypy not in CI | Python type errors accumulate; refactoring breaks in unexpected places | Sprint 2 |
| No Docker build in CI | Docker image builds locally but not in CI (missing build arg, wrong base image) | First staging deploy |
| Proto stubs not committed together | Go and Python use incompatible versions of the same proto message | Integration test |
| No branch protection | Broken code merged to main; unblocks team for hours | Sprint 1 |

---

## Chitragupt Decision

> **How we set up Chitragupt's CI:**
> GitHub Actions, three parallel jobs (Rust / Python / Go). Rust toolchain pinned in `rust-toolchain.toml` — this fixed a CI failure caused by `stable-x86_64-pc-windows-gnu` channel string. Docker used to isolate the build environment after a `GateManager::default()` dependency issue broke local tests. Proto stubs committed alongside the .proto file. `cargo fmt --check` and `cargo clippy -D warnings` are hard gates — CI rejects any PR that fails them.
> Reference: `.github/workflows/ci.yaml`, `rust-toolchain.toml`, `CONTRIBUTING.md`.

---

> Chitragupt Playbooks · PB-07 CI/CD & Delivery · v0.1 · May 2026
