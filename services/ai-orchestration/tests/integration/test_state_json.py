"""Domain 5 — Code Correctness: SessionState JSON Roundtrip stub.

T-CORR-10: Rust SessionState → JSON → Python dict parse → same field values.

Requires: Running Rust gRPC state machine (Docker Compose).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Rust gRPC state machine. Run with: pytest -m integration")
async def test_corr_10_session_state_json_roundtrip():
    """
    T-CORR-10: Serialise a known SessionState in Rust to JSON via GetSessionState,
    parse the JSON in Python, and verify all field values are identical.

    Catches: field name drift, encoding bugs, optional field handling differences.
    """
    raise NotImplementedError("Integration test — requires Rust gRPC state machine.")
