"""E2E Suite — Latency (End-to-End).

T-LAT-06: Go gateway SSE: time from POST to first 'event: token' p95 ≤ 5 000 ms.
T-LAT-08: Streaming throughput: sustained token rate ≥ 10 tok/s after first token.

Requires: Full Docker Compose stack + OPENROUTER_API_KEY.
Run with: pytest -m latency
"""
import pytest


@pytest.mark.latency
@pytest.mark.skip(reason="Requires full Docker Compose stack + API keys. Run with: pytest -m latency")
async def test_lat_06_gateway_sse_first_token_p95_under_5000ms():
    """
    T-LAT-06: POST /turn to the Go gateway; measure time from request send to
    first 'event: token' SSE line. p95 of 10 trials must be ≤ 5 000 ms.

    Includes: Go routing latency + Rust gRPC + Python pipeline first-token.
    """
    raise NotImplementedError("Latency E2E test — requires full Docker Compose stack.")


@pytest.mark.latency
@pytest.mark.skip(reason="Requires full Docker Compose stack + API keys. Run with: pytest -m latency")
async def test_lat_08_streaming_throughput_at_least_10_tokens_per_second():
    """
    T-LAT-08: After the first token arrives, the sustained token rate over 5 trials
    must be ≥ 10 tokens per second (measured as total_tokens / streaming_duration).
    """
    raise NotImplementedError("Latency E2E test — requires full Docker Compose stack.")
