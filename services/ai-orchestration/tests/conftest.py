"""Shared pytest fixtures and factories for ai-orchestration unit tests.

Helper functions (make_state, text_response, etc.) are defined at module level
and imported by test modules. Pytest fixtures are decorated with @pytest.fixture.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_orchestration.config import OrchestrationConfig
from ai_orchestration.llm.budget import BudgetTracker
from ai_orchestration.llm.features import LLMFeature
from ai_orchestration.models.entities import AcUpdate, Entity, GapResult


# ── Config fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def cfg() -> OrchestrationConfig:
    """Default OrchestrationConfig — no YAML file required."""
    return OrchestrationConfig()


@pytest.fixture
def cfg_fast_timeout() -> OrchestrationConfig:
    """Config with 50 ms node timeouts so timeout tests complete quickly."""
    return OrchestrationConfig.model_validate({
        "orchestration": {
            "pipeline": {
                "timeout_ms": {
                    "intent_classifier": 50,
                    "entity_extractor": 50,
                    "gap_analyzer": 50,
                    "guidance_generator": 50,
                }
            }
        }
    })


# ── Session state ─────────────────────────────────────────────────────────────

@pytest.fixture
def base_session() -> dict:
    """Minimal session-state dict for a fresh ProblemIntake session."""
    return _fresh_session()


def _fresh_session(phase: str = "ProblemIntake") -> dict:
    return {
        "session_id": "test-session-001",
        "workspace_id": "test-workspace-001",
        "current_phase": phase,
        "ac_met": [],
        "ac_waived": [],
        "actors": [],
        "requirements": [],
        "constraints": [],
        "assumptions": [],
        "open_questions": [],
        "documents_indexed": [],
        "problem_statement": None,
        "business_domain": None,
        "success_definition": None,
        "regulatory_context": None,
        "architecture_approach": None,
        "deployment_environment": None,
    }


# ── Mock LLM response builders ────────────────────────────────────────────────

def text_response(text: str) -> MagicMock:
    """Mock Anthropic response with one text content block."""
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


def empty_response() -> MagicMock:
    """Mock Anthropic response with no content blocks."""
    resp = MagicMock()
    resp.content = []
    return resp


class FakeStream:
    """
    Async context manager that yields a fixed list of token strings.
    Stands in for anthropic's streaming context manager.
    """

    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens

    async def __aenter__(self) -> "FakeStream":
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    @property
    def text_stream(self) -> Any:
        return self._gen()

    async def _gen(self):
        for tok in self._tokens:
            yield tok


# ── Mock client factories ─────────────────────────────────────────────────────

def mock_create_client(response_text: str) -> MagicMock:
    """Synchronous-style mock: messages.create returns a fixed text response."""
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=text_response(response_text))
    return client


def mock_stream_client(tokens: list[str]) -> MagicMock:
    """Streaming mock: messages.stream returns a FakeStream of tokens."""
    client = MagicMock()
    client.messages.stream = MagicMock(return_value=FakeStream(tokens))
    return client


def mock_create_empty(client: MagicMock | None = None) -> MagicMock:
    """messages.create returns a response with no content blocks."""
    c = client or MagicMock()
    c.messages.create = AsyncMock(return_value=empty_response())
    return c


def mock_create_raises(exc: Exception) -> MagicMock:
    """messages.create raises the given exception."""
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=exc)
    return client


def mock_create_sleeps(seconds: float) -> MagicMock:
    """messages.create hangs for `seconds` — simulates a network timeout."""

    async def _hang(*args: Any, **kwargs: Any) -> MagicMock:
        await asyncio.sleep(seconds)
        return text_response('{"intent": "Clarification"}')

    client = MagicMock()
    client.messages.create = _hang
    return client


# ── LLM context factory ───────────────────────────────────────────────────────

def make_llm_ctx(
    phase: str = "ProblemIntake",
    session_id: str = "test-session-001",
    client: Any = None,
    token_sink: "asyncio.Queue[str | None] | None" = None,
) -> MagicMock:
    """Build a mock SessionLLMContext with a swappable LLM client."""
    if client is None:
        client = mock_create_client('{"intent": "Clarification"}')
    ctx = MagicMock()
    ctx.current_phase = phase
    ctx.session_id = session_id
    ctx.token_sink = token_sink
    ctx.budget = BudgetTracker(session_id=session_id)
    ctx.get.return_value = client
    return ctx


# ── PipelineState dict factory ────────────────────────────────────────────────

def make_state(
    message: str = "Tell me about the project",
    phase: str = "ProblemIntake",
    session_state: dict | None = None,
    client: Any = None,
    gap_analysis: GapResult | None = None,
    extracted_entities: list[Entity] | None = None,
    token_sink: "asyncio.Queue[str | None] | None" = None,
) -> dict:
    """
    Build a PipelineState dict suitable for passing directly to any node.
    PipelineState is a TypedDict at type-check time but a plain dict at runtime.
    """
    ss = session_state if session_state is not None else _fresh_session(phase)
    return {
        "session_state": ss,
        "user_message": message,
        "llm_ctx": make_llm_ctx(phase=phase, client=client, token_sink=token_sink),
        "intent": None,
        "extracted_entities": extracted_entities or [],
        "retrieved_chunks": [],
        "gap_analysis": gap_analysis,
        "guidance_tokens": [],
        "ac_updates": [],
        "node_errors": {},
        "pipeline_aborted": False,
    }


# ── Pytest factory fixtures ───────────────────────────────────────────────────

@pytest.fixture
def state_factory():
    """Returns `make_state` so tests can build PipelineState dicts inline."""
    return make_state


@pytest.fixture
def llm_ctx_factory():
    """Returns `make_llm_ctx` for tests that need a standalone LLM context."""
    return make_llm_ctx
