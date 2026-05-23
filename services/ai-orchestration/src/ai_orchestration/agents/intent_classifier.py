"""IntentClassifierNode — classifies a BA turn into one of 9 intent codes.

Model: claude-haiku-4-5-20251001 (fast tier)
Timeout: 800ms
Output: state["intent"] — one of the 9 intent codes defined below
Fallback: "Clarification" (least disruptive default on failure)

Intent set:
  ProblemCapture | StakeholderProbe | RequirementCapture | ConstraintStatement
  ArchitectureComment | ReviewFeedback | UploadRequest | Clarification | REVISIT

REVISIT is detected as a post-processing step on Clarification intent when the
BA message contains revisit-indicator keywords. The LLM prompt covers 8 codes;
REVISIT is a keyword override applied after the LLM call.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..llm.features import LLMFeature
from ..pipeline.state import PipelineState
from .base import PipelineNode

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

VALID_INTENTS = frozenset({
    "ProblemCapture",
    "StakeholderProbe",
    "RequirementCapture",
    "ConstraintStatement",
    "ArchitectureComment",
    "ReviewFeedback",
    "UploadRequest",
    "Clarification",
    "REVISIT",
})

_DEFAULT_INTENT = "Clarification"

_REVISIT_KEYWORDS = frozenset({
    "back to",
    "go back",
    "revisit",
    "return to",
    "redo",
    "re-enter",
    "let's go back",
    "can we go back",
    "i need to change",
    "i want to change",
})


class IntentClassifierNode(PipelineNode):

    @property
    def timeout_ms(self) -> int:
        return self._config.orchestration.pipeline.timeout_ms.intent_classifier

    async def __call__(self, state: PipelineState) -> PipelineState:
        return await self._run_with_timeout(
            self._classify(state),
            state,
            default={**state, "intent": _DEFAULT_INTENT},
        )

    async def _classify(self, state: PipelineState) -> PipelineState:
        client = state["llm_ctx"].get(LLMFeature.INTENT_CLASSIFICATION)
        tier = self._config.models.function_map.intent_classification
        model = self._config.model_id(tier)
        system = _PROMPTS_DIR.joinpath("intent_classifier.txt").read_text(encoding="utf-8")

        response = await client.messages.create(
            model=model,
            system=system,
            messages=[{"role": "user", "content": state["user_message"]}],
            max_tokens=32,
        )

        raw = response.content[0].text.strip() if response.content else ""
        intent = _parse_intent(raw)
        intent = _maybe_revisit(intent, state["user_message"])

        logger.debug("IntentClassifier → %s", intent)
        return {**state, "intent": intent}


def _parse_intent(raw: str) -> str:
    try:
        data = json.loads(raw)
        code = data.get("intent", _DEFAULT_INTENT)
        return code if code in VALID_INTENTS else _DEFAULT_INTENT
    except (json.JSONDecodeError, TypeError, KeyError):
        return _DEFAULT_INTENT


def _maybe_revisit(intent: str, message: str) -> str:
    if intent == "Clarification":
        lower = message.lower()
        if any(kw in lower for kw in _REVISIT_KEYWORDS):
            return "REVISIT"
    return intent
