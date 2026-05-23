"""Domain 8 — Context Awareness: Multi-turn Context Continuity stubs.

T-CTX-04: Entity from Turn N present in context dict passed to Turn N+1.
T-CTX-06: 50-turn session — no context_length_exceeded error.
T-CTX-07: Chunk indexed in Turn 1 is retrieved in Turn 10.

Requires: Full Docker Compose stack (Rust state + Python service + PostgreSQL).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Requires full Docker Compose stack. Run with: pytest -m integration")
async def test_ctx_04_entity_from_turn_n_present_in_turn_n_plus_1_context():
    """
    T-CTX-04: An entity (actor, requirement) captured in Turn N must appear in
    the session_state.actors / session_state.requirements dict passed to Turn N+1.
    """
    raise NotImplementedError("Integration test — requires full stack.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires full Docker Compose stack. Run with: pytest -m integration")
async def test_ctx_06_fifty_turn_session_no_context_exceeded_error():
    """
    T-CTX-06: Run 50 pipeline turns against a single session. No turn must raise
    a 'context_length_exceeded' error — the pipeline must truncate or summarise.
    """
    raise NotImplementedError("Integration test — requires full stack + 50 turns.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires PostgreSQL + pgvector. Run with: pytest -m integration")
async def test_ctx_07_chunk_indexed_in_turn_1_retrieved_in_turn_10():
    """
    T-CTX-07: A document chunk indexed during Turn 1 must still be retrievable
    via hybrid_search() during Turn 10 (TTL and active flag intact).
    """
    raise NotImplementedError("Integration test — requires PostgreSQL + pgvector.")
