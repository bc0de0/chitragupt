"""EntityExtractorNode — extracts structured entities from the BA turn.

Model: claude-haiku-4-5-20251001 (fast tier)
Timeout: 1500ms
Output: state["extracted_entities"] — list[Entity]
        state["ac_updates"]         — list[AcUpdate] derived from entity counts

Entity types: actor, requirement, constraint, assumption, gap
Extraction is phase-specific — the system prompt is scoped to what matters in the current phase.

source_chunk_ids on each Entity are intentionally empty at this stage: this node runs
before RAG retrieval. Provenance linkage (chunk → entity) is added downstream.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..llm.features import LLMFeature
from ..models.entities import AcUpdate, Entity
from ..pipeline.state import PipelineState
from .base import PipelineNode

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class EntityExtractorNode(PipelineNode):

    @property
    def timeout_ms(self) -> int:
        return self._config.orchestration.pipeline.timeout_ms.entity_extractor

    async def __call__(self, state: PipelineState) -> PipelineState:
        return await self._run_with_timeout(
            self._extract(state),
            state,
            default={**state, "extracted_entities": [], "ac_updates": []},
        )

    async def _extract(self, state: PipelineState) -> PipelineState:
        phase = state["llm_ctx"].current_phase
        client = state["llm_ctx"].get(LLMFeature.DATA_TRANSFORMATION)
        tier = self._config.models.function_map.data_transformation
        model = self._config.model_id(tier)

        template = _PROMPTS_DIR.joinpath("entity_extractor.txt").read_text(encoding="utf-8")
        system = template.replace("{{PHASE}}", phase)

        response = await client.messages.create(
            model=model,
            system=system,
            messages=[{"role": "user", "content": state["user_message"]}],
            max_tokens=1024,
        )

        raw = response.content[0].text.strip() if response.content else "[]"
        entities = _parse_entities(raw, phase)
        ac_updates = _derive_ac_updates(entities, state["session_state"], phase)

        logger.debug("EntityExtractor → %d entities, %d AC updates", len(entities), len(ac_updates))
        return {**state, "extracted_entities": entities, "ac_updates": ac_updates}


def _parse_entities(raw: str, phase: str) -> list[Entity]:
    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            return []
        result = []
        for item in items:
            if not isinstance(item, dict):
                continue
            entity_type = item.get("entity_type", "")
            value = item.get("value", "")
            if not entity_type or not value:
                continue
            result.append(Entity(
                entity_type=entity_type,
                value=value,
                confidence=float(item.get("confidence", 1.0)),
                source=item.get("source", "conversation"),
                phase=phase,
                source_chunk_ids=[],
            ))
        return result
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def _derive_ac_updates(
    entities: list[Entity],
    session_state: object,
    phase: str,
) -> list[AcUpdate]:
    """Derive AcUpdate events from what was extracted this turn.

    These are optimistic updates: if we extracted enough entities of a type,
    we signal the criterion as met. The Rust state machine is the authoritative
    source — these signals are merged, not overriding.
    """
    updates: list[AcUpdate] = []

    if not entities:
        return updates

    def get_field(name: str, default):
        if isinstance(session_state, dict):
            return session_state.get(name, default)
        return getattr(session_state, name, default)

    actor_count = len(get_field("actors", [])) + sum(1 for e in entities if e.entity_type == "actor")
    req_count = len(get_field("requirements", [])) + sum(1 for e in entities if e.entity_type == "requirement")
    constraint_count = len(get_field("constraints", [])) + sum(1 for e in entities if e.entity_type == "constraint")

    # Phase 1 signals
    if phase == "ProblemIntake":
        if any(e.entity_type == "gap" for e in entities):
            pass  # gaps don't signal AC met

    # Phase 2 signals
    if phase == "StakeholderDiscovery":
        if actor_count >= 2:
            updates.append(AcUpdate("AC-S2-01", True, f"≥2 actors present ({actor_count} total)"))
        new_actors = [e for e in entities if e.entity_type == "actor"]
        if any("decision maker" in e.value.lower() or "final approver" in e.value.lower()
               or "decision_maker" in e.value.lower() for e in new_actors):
            updates.append(AcUpdate("AC-S2-02", True, "Decision-maker identified this turn"))

    # Phase 3 signals
    if phase == "RequirementElicitation":
        functional = req_count  # rough proxy; Rust will count precisely
        if functional >= 5:
            updates.append(AcUpdate("AC-S3-01", True, f"≥5 requirements present ({req_count} total)"))

    # Phase 4 signals
    if phase == "ConstraintCapture":
        if constraint_count >= 1:
            pass  # individual constraint types are checked by Rust field evaluator

    return updates
