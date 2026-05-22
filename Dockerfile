# ── base: toolchain ───────────────────────────────────────────────────────────
FROM rust:1-slim AS base
WORKDIR /app
RUN rustup component add rustfmt clippy

# ── deps: fetch crates (cached until manifests or lock file change) ───────────
FROM base AS deps
COPY Cargo.toml Cargo.lock ./
COPY services/state-machine/Cargo.toml ./services/state-machine/Cargo.toml
RUN cargo fetch --locked

# ── tester: fmt · clippy · unit/integration tests ────────────────────────────
FROM deps AS tester
COPY services/state-machine/src      ./services/state-machine/src
COPY services/state-machine/tests    ./services/state-machine/tests
COPY services/state-machine/proto    ./services/state-machine/proto
RUN cargo fmt --check
RUN cargo clippy -p chitragupt-state-machine --all-targets -- -D warnings
RUN cargo test  -p chitragupt-state-machine

# ── builder: release binary ───────────────────────────────────────────────────
FROM tester AS builder
RUN cargo build --release -p chitragupt-state-machine

# ── runtime: minimal production image ────────────────────────────────────────
FROM debian:bookworm-slim AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/target/release/state-machine ./state-machine
ENTRYPOINT ["./state-machine"]
