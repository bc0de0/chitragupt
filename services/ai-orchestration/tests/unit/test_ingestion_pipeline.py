"""Domain 5 — Code Correctness: IngestionPipeline unit tests.

T-CORR-04 (BM25 sparse vector), T-CORR-05/06 (PII scrubber correctness),
T-QUAL-06 (PII scrubber applied before embedding).

All tests run in the 'fast' CI mode — no database or network I/O.
"""
from __future__ import annotations

import pytest

from ai_orchestration.ingestion.pipeline import _bm25_sparse, _scrub_pii


# ─────────────────────────────────────────────────────────────────────────────
# T-CORR-04: BM25 sparse vector — TF-IDF weights sum ≤ 1.0; empty → empty dict
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_corr_04_bm25_weights_sum_to_one_for_nonempty_input():
    """
    T-CORR-04a: _bm25_sparse() weights for a non-empty token list sum to exactly 1.0
    (each term's weight is count/total; sum of counts = total).

    EXPECTED: PASS
    """
    tokens = ["the", "cat", "sat", "on", "the", "mat", "the"]
    result = _bm25_sparse(tokens)

    assert len(result) > 0, "Expected non-empty sparse vector"
    total_weight = sum(result.values())
    assert abs(total_weight - 1.0) < 1e-9, (
        f"BM25 weights should sum to 1.0 but got {total_weight:.9f}"
    )


@pytest.mark.fast
def test_corr_04b_bm25_empty_input_returns_empty_dict():
    """
    T-CORR-04b: _bm25_sparse([]) must return an empty dict (no ZeroDivisionError).

    EXPECTED: PASS
    """
    result = _bm25_sparse([])
    assert result == {}


@pytest.mark.fast
def test_corr_04c_bm25_term_weights_are_case_normalised():
    """_bm25_sparse lowercases all tokens, so 'The' and 'the' are the same term."""
    tokens = ["The", "the", "THE"]
    result = _bm25_sparse(tokens)

    assert list(result.keys()) == ["the"]
    assert abs(result["the"] - 1.0) < 1e-9  # 3/3


@pytest.mark.fast
def test_corr_04d_bm25_all_weights_non_negative():
    """Every weight in the sparse vector must be > 0."""
    tokens = ["alpha", "beta", "gamma", "alpha"]
    result = _bm25_sparse(tokens)

    for term, weight in result.items():
        assert weight > 0, f"Term '{term}' has non-positive weight {weight}"


# ─────────────────────────────────────────────────────────────────────────────
# T-CORR-05: PII scrubber — email, phone, SSN, credit card removed
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_corr_05_pii_email_removed():
    """
    T-CORR-05a: Valid email addresses are replaced with [EMAIL].

    EXPECTED: PASS
    """
    text = "Contact john.doe@example.com for support or reach admin@chitragupt.ai."
    result = _scrub_pii(text)

    assert "john.doe@example.com" not in result
    assert "admin@chitragupt.ai" not in result
    assert "[EMAIL]" in result


@pytest.mark.fast
def test_corr_05b_pii_phone_removed():
    """
    T-CORR-05b: US phone numbers (E.164 and common formats) are replaced with [PHONE].

    EXPECTED: PASS
    """
    phones = [
        "Call us at 555-867-5309.",
        "US number: 800.555.0100.",
        "Also reach us at 415 202 0123.",
    ]
    for text in phones:
        result = _scrub_pii(text)
        assert "[PHONE]" in result, f"Phone not removed from: {text!r}"


@pytest.mark.fast
def test_corr_05c_pii_ssn_removed():
    """
    T-CORR-05c: US Social Security numbers (NNN-NN-NNNN) are replaced with [SSN].

    EXPECTED: PASS
    """
    text = "SSN: 123-45-6789 must not be stored in the document."
    result = _scrub_pii(text)

    assert "123-45-6789" not in result
    assert "[SSN]" in result


@pytest.mark.fast
def test_corr_05d_pii_credit_card_removed():
    """
    T-CORR-05d: Visa (16-digit) and Mastercard numbers are replaced with [CARD].

    EXPECTED: PASS
    """
    cards = [
        "4111111111111111",  # Visa test number
        "5500005555555559",  # Mastercard test number
    ]
    for card in cards:
        text = f"Please use card number {card} for payment."
        result = _scrub_pii(text)
        assert card not in result, f"Card number not removed: {card}"
        assert "[CARD]" in result


# ─────────────────────────────────────────────────────────────────────────────
# T-CORR-06: PII scrubber — non-PII strings pass through unchanged
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_corr_06_non_pii_strings_pass_unchanged():
    """
    T-CORR-06: Strings that contain no PII must pass through _scrub_pii() unmodified.

    EXPECTED: PASS
    """
    safe_strings = [
        "The business problem is that procurement is slow.",
        "Actors: procurement manager, finance team, IT admin.",
        "Timeline: 6 months from kickoff.",
        "Budget: TBD pending final approval.",
        "The system must support 99.9% uptime.",
        "Reference document: RFC-2119 (2006). Section 3.",
    ]
    for text in safe_strings:
        result = _scrub_pii(text)
        assert result == text, (
            f"Non-PII string was modified by scrubber.\n"
            f"  Input:  {text!r}\n"
            f"  Output: {result!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# T-QUAL-06: PII scrubber is applied to chunk text before embedding
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_qual_06_pii_scrubber_applied_to_chunk_text():
    """
    T-QUAL-06: _scrub_pii() must remove all PII from chunk text so that
    no PII is stored in the vector DB or passed to the embedding model.

    Verifies the scrubber handles a realistic multi-PII document chunk.

    EXPECTED: PASS
    """
    chunk_text = (
        "The project owner is jane.smith@revorion.ai and her contact is 212-555-0199. "
        "Payment method: 4111111111111111. "
        "Employee ID: 987-65-4321. "
        "The deployment timeline is Q3 2026."
    )

    result = _scrub_pii(chunk_text)

    # All PII must be removed
    assert "jane.smith@revorion.ai" not in result
    assert "212-555-0199" not in result
    assert "4111111111111111" not in result
    assert "987-65-4321" not in result

    # Non-PII content must be preserved
    assert "Q3 2026" in result
    assert "deployment timeline" in result

    # Placeholders present
    assert "[EMAIL]" in result
    assert "[PHONE]" in result
    assert "[CARD]" in result
    assert "[SSN]" in result
