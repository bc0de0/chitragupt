# 05 — DevOps and CI/CD: Docker, GitHub Actions, and Polyglot Pipelines

**Why this matters for Chitragupt:** A polyglot system (Rust + Python + Go) has a more complex CI/CD pipeline than a single-language project. Every language has its own build tool, test runner, and linter. Understanding how these are wired together helps you add new checks, debug failing pipelines, and understand why the Dockerfiles are structured the way they are.

---

## 1. What Is CI/CD?

**CI (Continuous Integration):** Every code change is automatically built and tested before it can be merged. If tests fail, the PR is blocked.

**CD (Continuous Delivery):** After CI passes, the software is automatically packaged and made ready to deploy.

**Why it matters:** Without CI, a developer can push code that breaks another developer's service and not discover it for days. CI catches breakage within minutes.

**Chitragupt's CI pipeline triggers on:** every pull request targeting `main`, and on every push to `main`.

---

## 2. GitHub Actions

GitHub Actions is a CI/CD platform built into GitHub. Pipelines are defined as YAML files in `.github/workflows/`.

### Anatomy of a workflow file

```yaml
name: CI                          # displayed in GitHub UI

on:                               # when this workflow runs
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:                             # parallel units of work
  rust:                           # job name
    runs-on: ubuntu-latest        # virtual machine type
    steps:                        # sequential commands within the job
      - uses: actions/checkout@v4 # clone the repo
      - name: Run tests
        run: cargo test --all
```

### Chitragupt's three parallel jobs

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  rust-ci    │   │  python-ci  │   │   go-ci     │
│             │   │             │   │             │
│ cargo fmt   │   │ black check │   │ gofmt -l    │
│ cargo clippy│   │ isort check │   │ go vet      │
│ cargo test  │   │ mypy --strict│   │ go test ./..│
│ docker build│   │ pytest      │   │ docker build│
└─────────────┘   │ docker build│   └─────────────┘
                  └─────────────┘
```

All three run in parallel — total CI time is the slowest job, not the sum of all jobs.

**Merge blocked if:** any job fails. A green CI = all three jobs passed.

---

## 3. Docker

Docker packages your application and all its dependencies into a **container** — a portable, isolated environment that runs the same everywhere.

### Why containers?

Without containers, "works on my machine" is a constant problem. Your dev machine has Rust 1.90, the server has Rust 1.82. The library versions differ. Docker eliminates this by packaging the exact runtime with the code.

### Multi-stage builds

Chitragupt uses multi-stage Dockerfiles to separate the build environment from the runtime environment:

1. **Builder stage:** has all build tools installed (compilers, dev dependencies)
2. **Runtime stage:** has only what's needed to run the compiled binary

This produces small, secure images — no compiler or build tools in production.

```dockerfile
# Rust — multi-stage build
FROM rust:1-slim AS builder
WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim AS runtime
COPY --from=builder /build/target/release/chitragupt-state /app/chitragupt-state
# No Rust compiler in the final image — much smaller and more secure
ENTRYPOINT ["/app/chitragupt-state"]
```

```dockerfile
# Python — uv for fast dependency installation
FROM python:3.11-slim AS builder
RUN pip install uv
WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev  # install deps without dev tools

FROM python:3.11-slim AS runtime
COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/src   /app/src
ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "chitragupt.orchestration.main"]
```

```dockerfile
# Go — scratch base = smallest possible image
FROM golang:1.23-alpine AS builder
WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o chitragupt-gateway ./cmd/gateway

FROM scratch AS runtime           # scratch = literally empty image
COPY --from=builder /build/chitragupt-gateway /chitragupt-gateway
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
ENTRYPOINT ["/chitragupt-gateway"]
```

**Why `scratch` for Go?** The Go binary is statically compiled — it has no dependencies. No base OS needed, no attack surface, smallest possible image.

---

## 4. Language-Specific Tools

### Rust toolchain

| Tool | Command | Purpose |
|---|---|---|
| `cargo fmt` | `cargo fmt --check` | Code formatting (enforced in CI) |
| `cargo clippy` | `cargo clippy -- -D warnings` | Linter — catches common mistakes |
| `cargo test` | `cargo test --all` | Run all unit and integration tests |
| `cargo build --release` | | Optimised production binary |

### Python toolchain

| Tool | Command | Purpose |
|---|---|---|
| `black` | `black --check src/` | Code formatter (enforced in CI) |
| `isort` | `isort --check-only src/` | Import sorting |
| `mypy` | `mypy --strict src/` | Type checking |
| `pytest` | `pytest tests/` | Test runner |
| `uv` | `uv sync --frozen` | Dependency management |

### Go toolchain

| Tool | Command | Purpose |
|---|---|---|
| `gofmt` | `gofmt -l .` | Code formatting (built into Go) |
| `go vet` | `go vet ./...` | Static analysis |
| `go test` | `go test ./...` | Run all tests |
| `go build` | `CGO_ENABLED=0 go build` | Compile |

---

## 5. The Proto Change Protocol

`.proto` files define the contracts between services. Changing them carelessly breaks services.

**Safe proto change process:**
1. Make the change in the `.proto` file
2. Re-run `protoc` to regenerate code for all services (Rust, Python, Go)
3. Update all services to use the new generated code
4. All services must be updated *before* the change is deployed to any environment
5. PR must show updated generated code in all three services

**Backward-compatible changes (safe):**
- Adding a new field (old services ignore unknown fields)
- Adding a new RPC method (old services don't call it)

**Breaking changes (require coordinated deploy):**
- Renaming or removing a field
- Changing a field's type
- Removing an RPC method

---

## 6. Conventional Commits and Branch Naming

### Commit format

```
<type>(<scope>): <short description>

Types: feat | fix | docs | chore | refactor | test | ci | perf
```

Examples:
```
feat(state-machine): add AIStrategyDesign phase AC evaluators
fix(go-gateway): handle WebSocket disconnect during streaming
docs(sprint1): update epic priorities to reflect P1 completion
chore(deps): bump tokio to 1.52.3
```

**Why this matters:** Conventional Commits enable automated changelog generation and make `git log` readable for new team members. CI will fail a PR with a non-conformant commit message.

### Branch naming

```
feat/sprint-1-state-machine-core
fix/CHT-42-websocket-reconnect
chore/bump-tokio-1-52
docs/add-api-gateway-tech-doc
```

---

## 7. Definition of Done (Engineering)

A user story is not done until all of these are true:

```
[ ] Code written and compiles without warnings
[ ] Unit tests cover the happy path and at least one failure case
[ ] CI passes (fmt + lint + type check + tests + Docker build)
[ ] PR reviewed and approved by at least one other engineer
[ ] PR description links to the Jira/Linear story
[ ] Merged to main — not just "ready to merge"
```

An epic is not done until all its child stories are done AND a manual smoke test confirms the feature works end-to-end.

---

## 8. Resources

### Official Documentation

| Resource | URL | What to read |
|---|---|---|
| GitHub Actions quickstart | [docs.github.com/en/actions/writing-workflows/quickstart](https://docs.github.com/en/actions/writing-workflows/quickstart) | Your first workflow file |
| GitHub Actions reference | [docs.github.com/en/actions](https://docs.github.com/en/actions) | Triggers, jobs, steps, secrets |
| Docker get started | [docs.docker.com/get-started/](https://docs.docker.com/get-started/) | Containers, images, multi-stage builds |
| Docker multi-stage builds | [docs.docker.com/build/building/multi-stage/](https://docs.docker.com/build/building/multi-stage/) | How to separate build and runtime stages |
| uv documentation | [docs.astral.sh/uv/](https://docs.astral.sh/uv/) | Python dependency management with uv |

### Deep Dives

| Resource | What you will learn |
|---|---|
| [Conventional Commits specification](https://www.conventionalcommits.org/en/v1.0.0/) | The full commit format — all types and their meaning |
| [Docker best practices for Python](https://docs.docker.com/language/python/containerize/) | Exactly the patterns used in Chitragupt's Python Dockerfile |
| [GitHub Actions: caching dependencies](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflows-do/caching-dependencies-to-speed-up-workflows) | How to cache `cargo`, pip, and Go module downloads in CI |
| [Rust CI with GitHub Actions](https://doc.rust-lang.org/book/appendix-07-nightly-rust.html) | Configuring the Rust toolchain in GitHub Actions |

### Debugging a failing CI job

```
1. Click the failing job in the GitHub PR checks
2. Find the failing step (red ✗)
3. Read the last 20 lines of output — the error is almost always there
4. Common issues:
   - "fmt" failure → run `cargo fmt` / `black` / `gofmt` locally
   - "clippy" failure → read the lint message and fix the code pattern
   - "mypy" failure → add a type annotation the checker flagged
   - "docker build" failure → run `docker build` locally to reproduce
   - "tests failed" → run the test locally to get a full stack trace
```

---

> Chitragupt Learning Hub · 05 DevOps and CI · v0.1 · May 2026
