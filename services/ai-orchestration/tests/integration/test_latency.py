"""Domain 7 — Latency: Integration stubs.

T-LAT-01: IntentClassifier p95 ≤ 800 ms (real Haiku, temperature=0).
T-LAT-02: Full pipeline first-token p95 ≤ 3 000 ms (no RAG).
T-LAT-03: Full pipeline first-token p95 ≤ 4 500 ms (RAG, 1000 chunks).
T-LAT-04: RAG hybrid_search with 100k chunks p95 ≤ 500 ms.
T-LAT-05: Rust gRPC ApplyTurnResult round-trip p95 ≤ 10 ms.
T-LAT-07: 5 MB PDF fully indexed p95 ≤ 60 s.

Requires: Full Docker Compose stack + OPENROUTER_API_KEY.
Run with: pytest -m latency
"""
import pytest


@pytest.mark.latency
@pytest.mark.skip(reason="Requires live API keys + full stack. Run with: pytest -m latency")
async def test_lat_01_intent_classifier_p95_under_800ms():
    """T-LAT-01: p95 of 10 real IntentClassifier calls ≤ 800 ms."""
    raise NotImplementedError("Latency test — requires live API.")


@pytest.mark.latency
@pytest.mark.skip(reason="Requires live API keys + full stack. Run with: pytest -m latency")
async def test_lat_02_full_pipeline_first_token_no_rag_p95_under_3000ms():
    """T-LAT-02: p95 first-token latency ≤ 3 000 ms (no RAG, no indexed documents)."""
    raise NotImplementedError("Latency test — requires full stack.")


@pytest.mark.latency
@pytest.mark.skip(reason="Requires live API keys + 1000 chunks indexed. Run with: pytest -m latency")
async def test_lat_03_full_pipeline_first_token_with_rag_p95_under_4500ms():
    """T-LAT-03: p95 first-token latency ≤ 4 500 ms (RAG enabled, 1000 chunks)."""
    raise NotImplementedError("Latency test — requires full stack + indexed documents.")


@pytest.mark.latency
@pytest.mark.skip(reason="Requires PostgreSQL + 100k chunks. Run with: pytest -m latency")
async def test_lat_04_hybrid_search_100k_chunks_p95_under_500ms():
    """T-LAT-04: hybrid_search() with 100k chunks p95 ≤ 500 ms (10 trials)."""
    raise NotImplementedError("Latency test — requires PostgreSQL + 100k test chunks.")


@pytest.mark.latency
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m latency")
async def test_lat_05_rust_grpc_apply_turn_result_p95_under_10ms():
    """T-LAT-05: ApplyTurnResult round-trip (Go→Rust→Go) p95 ≤ 10 ms (50 trials)."""
    raise NotImplementedError("Latency test — requires Rust gRPC state machine.")


@pytest.mark.latency
@pytest.mark.skip(reason="Requires full stack + 5MB test PDF. Run with: pytest -m latency")
async def test_lat_07_5mb_pdf_indexing_p95_under_60s():
    """T-LAT-07: Full ingestion of a 5 MB PDF (extract→chunk→embed→store) p95 ≤ 60 s."""
    raise NotImplementedError("Latency test — requires full stack + 5MB test PDF.")
