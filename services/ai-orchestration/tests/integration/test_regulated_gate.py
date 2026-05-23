"""Domain 4 — Regulated Domain Gate: Integration stubs.

T-STATE-07: Regulated domain, no documents → Phase 3→4 blocked.
T-STATE-08: Regulated domain, one document indexed → Phase 3→4 allowed.
T-STATE-09: Regulated domain, AC-S3-U1 waived → Phase 3→4 allowed.

Requires: Rust gRPC state machine + PostgreSQL (Docker Compose).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_state_07_regulated_domain_blocks_transition_without_documents():
    """
    T-STATE-07: For a regulated domain session, documents_indexed must be non-empty
    before Phase 3→4 is allowed. An empty documents list must block the transition.
    """
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_state_08_regulated_domain_allows_transition_with_one_document():
    """
    T-STATE-08: With at least one document indexed, the regulated gate must pass
    and Phase 3→4 transition must be approved.
    """
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_state_09_waived_ac_allows_transition_despite_no_documents():
    """
    T-STATE-09: If AC-S3-U1 (document requirement) is waived, Phase 3→4 must be
    approved even with documents_indexed=[] (waiver bypasses the gate).
    """
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")
