"""Domain 2 — Edge Cases tests.

T-EDGE-01 through T-EDGE-15.

Tests in this file verify that the system degrades gracefully for all inputs
outside the happy path. No panics, no data corruption, no silent failures.

Unit tests (T-EDGE-01..08, T-EDGE-10): run in the 'fast' CI mode.
Integration tests (T-EDGE-09, 11-15): marked @pytest.mark.integration and
    skipped by the test harness. They require Docker Compose with real services.

EXPECTED FINDINGS:
  T-EDGE-02: FAIL — No message truncation before LLM call (101K chars sent raw)
  T-EDGE-06: FAIL — DocumentProcessor does not reject binary files (no UNSUPPORTED_TYPE)
  T-EDGE-07: FAIL — DocumentProcessor does not reject zero-byte files (no EMPTY_FILE check)
  All other unit tests in this file: PASS
"""
from __future__ import annotations

import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import (
    make_state,
    mock_create_client,
    mock_create_raises,
    mock_create_sleeps,
    text_response,
    empty_response,
)

from ai_orchestration.agents.intent_classifier import IntentClassifierNode, VALID_INTENTS
from ai_orchestration.agents.entity_extractor import EntityExtractorNode
from ai_orchestration.agents.revisit_handler import RevisitHandlerNode
from ai_orchestration.config import OrchestrationConfig
from ai_orchestration.ingestion.document_processor import DocumentProcessor, RawPage


# ── Config fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def cfg() -> OrchestrationConfig:
    return OrchestrationConfig()


@pytest.fixture
def cfg_fast_timeout() -> OrchestrationConfig:
    """50 ms timeout so T-EDGE-04 finishes in under 1 s."""
    return OrchestrationConfig.model_validate({
        "orchestration": {
            "pipeline": {
                "timeout_ms": {
                    "intent_classifier": 50,
                    "entity_extractor": 50,
                }
            }
        }
    })


# ─────────────────────────────────────────────────────────────────────────────
# T-EDGE-01: Empty user message → intent returned, pipeline does not crash
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_edge_01_empty_message_pipeline_completes(cfg):
    """
    T-EDGE-01: An empty BA message must not crash the pipeline.
    The node must return a valid intent from VALID_INTENTS.

    EXPECTED: PASS
    """
    client = mock_create_client('{"intent": "Clarification"}')
    node = IntentClassifierNode(cfg)
    state = make_state(message="", client=client)

    result = await node(state)

    assert result is not None
    assert "intent" in result
    assert result["intent"] in VALID_INTENTS
    assert result["pipeline_aborted"] is False


@pytest.mark.fast
async def test_edge_01b_empty_message_with_llm_error_falls_back(cfg):
    """
    T-EDGE-01b: If the LLM raises an exception for an empty message,
    the node must still return Clarification (the safe default).

    EXPECTED: PASS
    """
    client = mock_create_raises(RuntimeError("API rejected empty input"))
    node = IntentClassifierNode(cfg)
    state = make_state(message="", client=client)

    result = await node(state)

    assert result["intent"] == "Clarification"
    assert "IntentClassifierNode" in result["node_errors"]


# ─────────────────────────────────────────────────────────────────────────────
# T-EDGE-02: Message > 100K chars → truncation check (reveals missing feature)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_edge_02_oversized_message_pipeline_completes(cfg):
    """
    T-EDGE-02a: A 101K-character message must not crash the pipeline.

    EXPECTED: PASS
    """
    long_message = "A" * 101_000
    client = mock_create_client('{"intent": "ProblemCapture"}')
    node = IntentClassifierNode(cfg)
    state = make_state(message=long_message, client=client)

    result = await node(state)

    assert result is not None
    assert result["intent"] in VALID_INTENTS


@pytest.mark.fast
async def test_edge_02b_oversized_message_is_truncated_before_llm_call(cfg):
    """
    T-EDGE-02b: A 101K-character message must be truncated before being sent
    to the LLM. The LLM call must receive ≤ 100,000 characters.

    EXPECTED: FAIL
    FINDING:  No truncation logic exists in IntentClassifierNode._classify().
              The full 101,000-character message is forwarded to the LLM.
    FIX:      Add message truncation (e.g. to 100,000 chars) in _classify()
              before building the messages list.
    """
    long_message = "A" * 101_000
    captured_content: list[str] = []

    async def capture_create(*args, **kwargs):
        msgs = kwargs.get("messages", [])
        if msgs:
            captured_content.append(msgs[0].get("content", ""))
        return text_response('{"intent": "ProblemCapture"}')

    client = MagicMock()
    client.messages.create = capture_create

    node = IntentClassifierNode(cfg)
    state = make_state(message=long_message, client=client)
    await node(state)

    assert len(captured_content) == 1
    sent_length = len(captured_content[0])
    assert sent_length <= 100_000, (
        f"FINDING: Message was NOT truncated before LLM call. "
        f"LLM received {sent_length:,} characters. "
        f"No truncation logic found in intent_classifier.py."
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-EDGE-03: LLM returns malformed JSON → Clarification fallback
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_edge_03_malformed_json_falls_back_to_clarification(cfg):
    """
    T-EDGE-03: When the LLM returns text that cannot be parsed as JSON,
    IntentClassifierNode must return 'Clarification' — not crash.

    EXPECTED: PASS
    """
    bad_responses = [
        "not json at all",
        "{ intent: ProblemCapture }",  # unquoted keys
        "<xml>intent</xml>",
        "I think this is a requirement capture.",  # natural language
        "",
        "null",
        "[]",
    ]

    node = IntentClassifierNode(cfg)

    for bad_text in bad_responses:
        client = mock_create_client(bad_text)
        state = make_state(message="We need a login page.", client=client)
        result = await node(state)

        assert result["intent"] == "Clarification", (
            f"Expected Clarification for malformed JSON {bad_text!r}, "
            f"got {result['intent']!r}"
        )
        assert result["pipeline_aborted"] is False


# ─────────────────────────────────────────────────────────────────────────────
# T-EDGE-04: LLM call times out → Clarification + node_errors populated
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_edge_04_timeout_falls_back_to_clarification(cfg_fast_timeout):
    """
    T-EDGE-04: When the LLM call exceeds the node timeout (50 ms in this test),
    the node must return Clarification and record the timeout in node_errors.

    EXPECTED: PASS
    """
    hanging_client = mock_create_sleeps(10.0)  # 10s — much longer than 50ms timeout

    node = IntentClassifierNode(cfg_fast_timeout)
    state = make_state(message="What are the main stakeholders?", client=hanging_client)

    result = await node(state)

    assert result["intent"] == "Clarification", (
        f"Expected Clarification on timeout, got {result['intent']!r}"
    )
    assert "IntentClassifierNode" in result["node_errors"], (
        "Timeout was not recorded in node_errors"
    )
    assert "timeout" in result["node_errors"]["IntentClassifierNode"].lower(), (
        f"node_errors entry does not mention timeout: "
        f"{result['node_errors']['IntentClassifierNode']!r}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-EDGE-05: LLM returns empty content list → empty entity list, no crash
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_edge_05_empty_llm_content_returns_empty_entity_list(cfg):
    """
    T-EDGE-05: When the LLM response has no content blocks, EntityExtractorNode
    must return an empty entity list and must not crash.

    EXPECTED: PASS
    """
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=empty_response())

    node = EntityExtractorNode(cfg)
    state = make_state(
        message="There are no stakeholders in this project.",
        phase="StakeholderDiscovery",
        client=client,
    )

    result = await node(state)

    assert result["extracted_entities"] == []
    assert result["ac_updates"] == []
    assert result["pipeline_aborted"] is False


@pytest.mark.fast
async def test_edge_05b_empty_string_from_llm_returns_empty_entity_list(cfg):
    """
    T-EDGE-05b: When the LLM returns an empty string, EntityExtractorNode
    must return an empty entity list.

    EXPECTED: PASS
    """
    client = mock_create_client("")  # Empty text, non-empty content list

    node = EntityExtractorNode(cfg)
    state = make_state(message="(silence)", phase="RequirementElicitation", client=client)

    result = await node(state)

    assert result["extracted_entities"] == []
    assert result["pipeline_aborted"] is False


# ─────────────────────────────────────────────────────────────────────────────
# T-EDGE-06: Binary file → rejected with UNSUPPORTED_TYPE (reveals missing check)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_edge_06_binary_file_is_rejected():
    """
    T-EDGE-06: DocumentProcessor must reject non-text binary files with a
    ValueError indicating UNSUPPORTED_TYPE.

    EXPECTED: FAIL
    FINDING:  DocumentProcessor.process() has no binary file validation.
              Binary content with an unrecognised extension is silently decoded
              as UTF-8 (with replacement characters) instead of being rejected.
    FIX:      Add file-type validation in DocumentProcessor.process().
              Reject files with non-text/non-document content types.
    """
    processor = DocumentProcessor()
    binary_content = bytes(range(256))  # full byte range — clearly binary

    with pytest.raises(ValueError, match="UNSUPPORTED_TYPE"):
        processor.process(binary_content, "data.bin")


@pytest.mark.fast
def test_edge_06b_binary_content_with_text_extension_is_rejected():
    """
    T-EDGE-06b: A binary payload disguised with a .txt extension must also
    be rejected or produce a detectable warning.

    EXPECTED: FAIL
    FINDING:  No content-type sniffing is implemented. The binary payload is
              decoded as UTF-8 with replacement characters and returned as text.
    """
    processor = DocumentProcessor()
    binary_content = bytes(range(256))

    # The current code returns a page with garbled text — no rejection
    with pytest.raises(ValueError, match="UNSUPPORTED_TYPE"):
        processor.process(binary_content, "looks_like_text.txt")


# ─────────────────────────────────────────────────────────────────────────────
# T-EDGE-07: Zero-byte file → rejected with EMPTY_FILE (reveals missing check)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_edge_07_zero_byte_file_is_rejected():
    """
    T-EDGE-07: DocumentProcessor must reject zero-byte files with a ValueError
    indicating EMPTY_FILE.

    EXPECTED: FAIL
    FINDING:  DocumentProcessor.process(b"", "doc.txt") succeeds and returns
              a RawPage with empty text instead of raising. There is no empty-file
              guard at any layer (DocumentProcessor, IngestionPipeline, or gRPC servicer).
    FIX:      Add `if not content: raise ValueError("EMPTY_FILE")` early in
              DocumentProcessor.process() and/or the gRPC IngestDocument servicer.
    """
    processor = DocumentProcessor()

    with pytest.raises(ValueError, match="EMPTY_FILE"):
        processor.process(b"", "document.pdf")


# ─────────────────────────────────────────────────────────────────────────────
# T-EDGE-08: Image-only PDF (no extractable text) → graceful handling
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_edge_08_image_only_pdf_returns_pages_without_crashing(monkeypatch):
    """
    T-EDGE-08: When a PDF contains only images (no extractable text), pypdf
    returns empty text per page. DocumentProcessor must handle this gracefully,
    returning at least one RawPage without crashing.

    EXPECTED: PASS
    """
    from ai_orchestration.ingestion import document_processor as dp_module

    def mock_extract_pdf(self, content: bytes) -> list[RawPage]:
        # Simulate pypdf finding pages but extracting no text
        return [RawPage(text="", page_number=1)]

    monkeypatch.setattr(dp_module.DocumentProcessor, "_extract_pdf", mock_extract_pdf)

    processor = dp_module.DocumentProcessor()
    pages = processor.process(b"%PDF-1.4 (simulated)", "scanned_doc.pdf")

    assert len(pages) >= 1, "Expected at least one RawPage even for image-only PDF"
    assert all(isinstance(p, RawPage) for p in pages)
    # Text will be empty — that is acceptable; no crash is the key invariant
    assert all(p.text == "" or isinstance(p.text, str) for p in pages)


@pytest.mark.fast
def test_edge_08b_all_empty_pdf_pages_return_single_placeholder_page(monkeypatch):
    """
    T-EDGE-08b: The internal _extract_pdf implementation returns a single
    empty placeholder page when all PDF pages yield no text.

    EXPECTED: PASS
    """
    import io

    # Build a minimal mock pypdf that returns two pages with no text
    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""

    mock_reader = MagicMock()
    mock_reader.pages = [mock_page, mock_page]

    mock_pypdf = MagicMock()
    mock_pypdf.PdfReader.return_value = mock_reader

    from ai_orchestration.ingestion import document_processor as dp_module

    with patch.dict("sys.modules", {"pypdf": mock_pypdf}):
        processor = dp_module.DocumentProcessor()
        pages = processor._extract_pdf(b"%PDF-1.4 mock")

    # Code returns [RawPage(text="", page_number=1)] when all pages are empty
    assert len(pages) == 1
    assert pages[0].text == ""
    assert pages[0].page_number == 1


# ─────────────────────────────────────────────────────────────────────────────
# T-EDGE-09: Duplicate document upload → hash dedup  (INTEGRATION — skip)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.skip(reason="Requires Docker Compose (PostgreSQL + asyncpg). Run with: pytest -m integration")
async def test_edge_09_duplicate_document_upload_is_deduplicated():
    """
    T-EDGE-09: Uploading the same document twice (identical content hash)
    must return the existing document_id on the second call.

    Requires: PostgreSQL + asyncpg pool (Docker Compose test profile).
    """
    raise NotImplementedError("Integration test — see tests/integration/test_ingestion.py")


# ─────────────────────────────────────────────────────────────────────────────
# T-EDGE-10: REVISIT message with no recognisable target phase → clarification gap
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_edge_10_revisit_with_unknown_target_returns_clarification_gap(cfg):
    """
    T-EDGE-10: A REVISIT message that contains no recognisable phase keyword
    must return a gap with criterion_id='REVISIT-UNKNOWN' and a clarification
    question asking the BA to specify the target phase.

    EXPECTED: PASS
    """
    node = RevisitHandlerNode(cfg)
    state = make_state(
        message="I want to go back to something we discussed earlier",
        # No phase keyword (problem, stakeholder, requirement, etc.)
    )

    result = await node(state)

    assert result["gap_analysis"] is not None
    gap = result["gap_analysis"]
    assert gap.criterion_id == "REVISIT-UNKNOWN", (
        f"Expected REVISIT-UNKNOWN, got {gap.criterion_id!r}"
    )
    assert gap.is_terminal is False
    assert gap.suggested_question != "", "Clarification question must not be empty"
    assert "phase" in gap.suggested_question.lower() or "back" in gap.suggested_question.lower(), (
        f"Clarification question should reference phases: {gap.suggested_question!r}"
    )


@pytest.mark.fast
async def test_edge_10b_revisit_with_valid_phase_keyword_resolves_correctly(cfg):
    """
    T-EDGE-10b: A REVISIT message containing a valid phase keyword must resolve
    to that phase and return the first unmet criterion for it.

    EXPECTED: PASS
    """
    node = RevisitHandlerNode(cfg)
    state = make_state(
        message="I want to go back to the requirements we discussed",
    )

    result = await node(state)

    gap = result["gap_analysis"]
    assert gap.criterion_id != "REVISIT-UNKNOWN", (
        "A recognisable phase keyword ('requirements') should have resolved the target."
    )
    assert "RequirementElicitation" in result["intent"], (
        f"Intent should contain resolved phase. Got: {result['intent']!r}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-EDGE-11: REVISIT to current phase → no-op  (INTEGRATION — skip)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.skip(reason="Requires running Rust gRPC state machine. Run with: pytest -m integration")
async def test_edge_11_revisit_to_current_phase_is_noop():
    """
    T-EDGE-11: When the BA revisits the current phase, current_phase must remain
    unchanged. Requires Rust gRPC service for state validation.
    """
    raise NotImplementedError("Integration test — see tests/integration/test_revisit.py")


# ─────────────────────────────────────────────────────────────────────────────
# T-EDGE-12: Concurrent document upload + turn → no race  (INTEGRATION — skip)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.skip(reason="Requires full Docker Compose stack. Run with: pytest -m integration")
async def test_edge_12_concurrent_upload_and_turn_no_race():
    """
    T-EDGE-12: A simultaneous document upload and BA turn in the same session
    must both complete successfully without corrupting session state.
    """
    raise NotImplementedError("Integration test — see tests/integration/test_concurrency.py")


# ─────────────────────────────────────────────────────────────────────────────
# T-EDGE-13..15: Go gateway error handling  (INTEGRATION — skip)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.skip(reason="Requires running Go API gateway. Run with: pytest -m integration")
async def test_edge_13_nonexistent_session_returns_404():
    raise NotImplementedError("Integration test — see tests/integration/test_gateway_errors.py")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires running Go API gateway with Rust service stopped.")
async def test_edge_14_rust_grpc_unreachable_returns_503():
    raise NotImplementedError("Integration test — see tests/integration/test_gateway_errors.py")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires running Go API gateway with Python service stopped.")
async def test_edge_15_python_grpc_unreachable_returns_503():
    raise NotImplementedError("Integration test — see tests/integration/test_gateway_errors.py")


# ─────────────────────────────────────────────────────────────────────────────
# Supplementary edge cases for LLM response parsing robustness
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_edge_parse_entities_handles_non_list_json(cfg):
    """
    _parse_entities must return [] when the LLM returns valid JSON that is
    not a list (e.g. an object or a string).
    """
    from ai_orchestration.agents.entity_extractor import _parse_entities

    non_list_inputs = [
        '{"entity_type": "actor", "value": "CFO"}',  # object, not list
        '"just a string"',
        "42",
        "true",
    ]
    for raw in non_list_inputs:
        result = _parse_entities(raw, "ProblemIntake")
        assert result == [], f"Expected [] for non-list JSON {raw!r}, got {result!r}"


@pytest.mark.fast
def test_edge_parse_entities_skips_items_missing_required_fields(cfg):
    """
    _parse_entities must skip array items that are missing entity_type or value.
    """
    from ai_orchestration.agents.entity_extractor import _parse_entities

    raw = '[{"entity_type": "actor"}, {"value": "CFO"}, {"entity_type": "requirement", "value": "login"}]'
    result = _parse_entities(raw, "RequirementElicitation")

    assert len(result) == 1
    assert result[0].entity_type == "requirement"
    assert result[0].value == "login"


@pytest.mark.fast
async def test_edge_entity_extractor_on_llm_exception_returns_empty_list(cfg):
    """
    If the LLM call raises any exception, EntityExtractorNode must return
    an empty entity list (not crash, not propagate the exception).
    """
    client = mock_create_raises(ConnectionError("gRPC channel lost"))
    node = EntityExtractorNode(cfg)
    state = make_state(message="The CTO will own this project.", client=client)

    result = await node(state)

    assert result["extracted_entities"] == []
    assert result["ac_updates"] == []
    assert "EntityExtractorNode" in result["node_errors"]
