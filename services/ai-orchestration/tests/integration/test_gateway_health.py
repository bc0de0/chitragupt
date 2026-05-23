"""Domain 6 — Code Integration: Go Gateway Health Check stub.

T-INT-12: Go gateway /healthz returns 200 when both gRPC backends are up.

Requires: Go gateway + both gRPC backends (Docker Compose).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Go gateway + gRPC backends. Run with: pytest -m integration")
async def test_int_12_gateway_healthz_returns_200_when_backends_up():
    """
    T-INT-12: GET /healthz on the Go API gateway must return HTTP 200 (JSON ok)
    when both the Rust state machine and Python orchestration service are reachable.
    """
    raise NotImplementedError("Integration test — requires Go gateway + gRPC backends.")
