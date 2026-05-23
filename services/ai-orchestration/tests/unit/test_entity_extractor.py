"""Domain 8 — Context Awareness: EntityExtractorNode tests.

T-CTX-01 (Phase 2 / StakeholderDiscovery system prompt variant),
T-CTX-02 (Phase 3 / RequirementElicitation system prompt variant).

Note: T-DET-03 (prompt determinism) is covered in test_determinism.py.
      T-EDGE-05 (empty LLM response) is covered in test_edge_cases.py.

All tests run in the 'fast' CI mode.
"""
from __future__ import annotations

import sys
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from conftest import make_state, text_response

from ai_orchestration.agents.entity_extractor import EntityExtractorNode
from ai_orchestration.config import OrchestrationConfig


@pytest.fixture
def cfg() -> OrchestrationConfig:
    return OrchestrationConfig()


def _capture_system_client(response_text: str) -> tuple[MagicMock, list[str]]:
    """Build a mock client that captures the `system` kwarg from messages.create."""
    captured: list[str] = []

    async def capture_create(*args, **kwargs):
        captured.append(kwargs.get("system", ""))
        return text_response(response_text)

    client = MagicMock()
    client.messages.create = capture_create
    return client, captured


# ─────────────────────────────────────────────────────────────────────────────
# T-CTX-01: EntityExtractor uses Phase 2 system prompt when phase = StakeholderDiscovery
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_ctx_01_entity_extractor_uses_phase_2_prompt_for_stakeholder_discovery(cfg):
    """
    T-CTX-01: When current_phase is 'StakeholderDiscovery', EntityExtractorNode must
    inject that phase into the system prompt via the {{PHASE}} placeholder.

    The entity_extractor.txt template contains {{PHASE}}, which is replaced with
    the current phase name before sending to the LLM.

    EXPECTED: PASS
    """
    client, captured = _capture_system_client(
        '[{"entity_type":"actor","value":"CTO","confidence":0.9}]'
    )
    node = EntityExtractorNode(cfg)
    state = make_state(
        message="The CTO and CFO are the primary stakeholders.",
        phase="StakeholderDiscovery",
        client=client,
    )

    await node(state)

    assert len(captured) == 1, "messages.create was not called"
    system_prompt = captured[0]
    assert "StakeholderDiscovery" in system_prompt, (
        "FINDING: Phase 'StakeholderDiscovery' was not injected into the entity "
        f"extractor system prompt.\nPrompt snippet: {system_prompt[:300]!r}"
    )


@pytest.mark.fast
async def test_ctx_01b_phase_2_prompt_differs_from_phase_1_prompt(cfg):
    """
    T-CTX-01b: The system prompt for StakeholderDiscovery must differ from the
    system prompt for ProblemIntake, proving phase injection is working.

    EXPECTED: PASS
    """
    captured: dict[str, str] = {}

    for phase in ("ProblemIntake", "StakeholderDiscovery"):
        sys_calls: list[str] = []

        async def cap(*args, _calls=sys_calls, **kwargs):
            _calls.append(kwargs.get("system", ""))
            return text_response("[]")

        c = MagicMock()
        c.messages.create = cap
        node = EntityExtractorNode(cfg)
        state = make_state(message="Hello.", phase=phase, client=c)
        await node(state)
        captured[phase] = sys_calls[0] if sys_calls else ""

    assert captured["ProblemIntake"] != captured["StakeholderDiscovery"], (
        "System prompts for ProblemIntake and StakeholderDiscovery are identical — "
        "phase injection may not be working."
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-CTX-02: EntityExtractor uses Phase 3 system prompt when phase = RequirementElicitation
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_ctx_02_entity_extractor_uses_phase_3_prompt_for_requirement_elicitation(cfg):
    """
    T-CTX-02: When current_phase is 'RequirementElicitation', EntityExtractorNode must
    inject 'RequirementElicitation' into the system prompt via {{PHASE}}.

    EXPECTED: PASS
    """
    client, captured = _capture_system_client(
        '[{"entity_type":"requirement","value":"SSO login","confidence":0.95}]'
    )
    node = EntityExtractorNode(cfg)
    state = make_state(
        message="The system must support single sign-on and role-based access.",
        phase="RequirementElicitation",
        client=client,
    )

    await node(state)

    assert len(captured) == 1, "messages.create was not called"
    system_prompt = captured[0]
    assert "RequirementElicitation" in system_prompt, (
        "FINDING: Phase 'RequirementElicitation' was not injected into the entity "
        f"extractor system prompt.\nPrompt snippet: {system_prompt[:300]!r}"
    )


@pytest.mark.fast
async def test_ctx_02b_requirement_elicitation_extracts_requirements_and_updates_ac(cfg):
    """
    T-CTX-02b: In RequirementElicitation phase, if ≥5 requirements are present
    (existing + this turn), EntityExtractorNode should emit an AcUpdate for AC-S3-01.

    EXPECTED: PASS (if derive_ac_updates works correctly)
    """
    # Build a session that already has 4 requirements; this turn adds the 5th
    session = {
        "session_id": "s",
        "workspace_id": "w",
        "current_phase": "RequirementElicitation",
        "ac_met": [],
        "ac_waived": [],
        "actors": [],
        "requirements": ["R1", "R2", "R3", "R4"],  # 4 existing
        "constraints": [], "assumptions": [], "open_questions": [],
        "documents_indexed": [], "problem_statement": None,
        "business_domain": None, "success_definition": None,
        "regulatory_context": None, "architecture_approach": None,
        "deployment_environment": None,
    }

    client, _ = _capture_system_client(
        '[{"entity_type":"requirement","value":"SSO support","confidence":0.9}]'
    )
    node = EntityExtractorNode(cfg)
    state = make_state(
        message="The system must support SSO.",
        phase="RequirementElicitation",
        session_state=session,
        client=client,
    )

    result = await node(state)

    # Should have emitted AC-S3-01 update (≥5 requirements)
    ac_updates = result["ac_updates"]
    criterion_ids = [u.criterion_id for u in ac_updates]
    assert "AC-S3-01" in criterion_ids, (
        f"Expected AC-S3-01 update when ≥5 requirements present. Got: {criterion_ids}"
    )


@pytest.mark.fast
async def test_ctx_02c_stakeholder_discovery_extracts_actors(cfg):
    """
    T-CTX-01c: In StakeholderDiscovery phase with ≥2 actors, AC-S2-01 should be signalled.

    EXPECTED: PASS
    """
    client, _ = _capture_system_client(
        '[{"entity_type":"actor","value":"Product Manager","confidence":0.9},'
        '{"entity_type":"actor","value":"IT Admin","confidence":0.85}]'
    )
    node = EntityExtractorNode(cfg)
    state = make_state(
        message="The product manager and IT admin are main users.",
        phase="StakeholderDiscovery",
        client=client,
    )

    result = await node(state)

    extracted = result["extracted_entities"]
    assert len(extracted) == 2
    assert all(e.entity_type == "actor" for e in extracted)
    assert all(e.phase == "StakeholderDiscovery" for e in extracted)

    criterion_ids = [u.criterion_id for u in result["ac_updates"]]
    assert "AC-S2-01" in criterion_ids, (
        f"Expected AC-S2-01 (≥2 actors). AC updates: {criterion_ids}"
    )
