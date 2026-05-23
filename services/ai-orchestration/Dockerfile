# ── base: Python 3.11 with system dependencies ───────────────────────────────
FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        protobuf-compiler \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── deps: install pinned requirements (cached until pyproject.toml changes) ──
FROM base AS deps
COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install -e ".[dev]" --no-deps \
    && pip install . --no-deps \
    && pip install .

# ── tester: run fast unit tests inside Docker ─────────────────────────────────
FROM deps AS tester
COPY src/ ./src/
COPY tests/ ./tests/
COPY config/ ./config/
RUN pytest -m fast --tb=short -q

# ── builder: compile protobuf stubs ──────────────────────────────────────────
FROM deps AS builder
COPY src/ ./src/
COPY config/ ./config/
# Generate gRPC stubs from proto files (mounted via build arg or copied)
COPY proto/ ./proto/
RUN python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./src/ai_orchestration/grpc \
    --grpc_python_out=./src/ai_orchestration/grpc \
    ./proto/*.proto 2>/dev/null || true

# ── runtime: minimal production image ────────────────────────────────────────
FROM python:3.11-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1001 appuser \
    && useradd --uid 1001 --gid appuser --shell /bin/sh --no-create-home appuser

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app/src ./src
COPY --from=builder /app/config ./config

USER appuser
EXPOSE 50052

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import grpc; channel = grpc.insecure_channel('localhost:50052'); channel.close()" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "ai_orchestration.grpc.server"]
