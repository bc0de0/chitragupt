"""LLMFactory — maps LLMFeature + BudgetStage to a configured client.

Process-level singleton pattern: the underlying SDK instances (AsyncOpenAI,
voyageai.Client) are created once and reused. LLMClient wrapper objects are
lightweight and created per session feature.

IMPORTANT — OpenRouter is OpenAI-compatible only:
  OpenRouter exposes /api/v1/chat/completions (OpenAI format) and does NOT
  serve /messages (Anthropic format). All text-generation calls — including
  Anthropic, Google, and OpenAI models — are routed through OpenRouter using
  AsyncOpenAI pointed at OPENROUTER_BASE_URL.

  Agent code that calls client.messages.create() (Anthropic SDK style) must be
  migrated to client.chat.completions.create() (OpenAI SDK style). This is
  tracked as a Sprint 1 task.

  Voyage embeddings use the native Voyage API (VOYAGE_API_KEY) because Voyage
  is not available on OpenRouter.

See LLM_DESIGN_PATTERNS.md for the full pattern specification.
See LLM_DEGRADATION.md for the provider circuit-breaker logic.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from ..config import OrchestrationConfig
from .features import BudgetStage, LLMFeature

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Degradation budget matrix — (feature, stage) → tier override.
# None means "use the default tier from config.function_map".
# See LLM_DEGRADATION.md Section 1 (Budget Degradation Matrix).
# ---------------------------------------------------------------------------
_BUDGET_OVERRIDES: dict[tuple[LLMFeature, BudgetStage], str | None] = {
    # CAUTION: only premium-tier calls are downgraded
    (LLMFeature.BRD_GENERATION,         BudgetStage.CAUTION):  "standard",
    (LLMFeature.REQUIREMENT_REFINEMENT, BudgetStage.CAUTION):  None,  # stays standard
    # CRITICAL: standard → fast everywhere, except BRD stays at standard floor
    (LLMFeature.BRD_GENERATION,         BudgetStage.CRITICAL): "standard",  # quality floor
    (LLMFeature.REQUIREMENT_REFINEMENT, BudgetStage.CRITICAL): "fast",
    (LLMFeature.RAG_SYNTHESIS,          BudgetStage.CRITICAL): "fast",
    (LLMFeature.VISUAL_UNDERSTANDING,   BudgetStage.CRITICAL): "fast",
    (LLMFeature.IMAGE_OCR,              BudgetStage.CRITICAL): "fast",
}


class LLMFactory:
    """
    Stateless factory. Maps (feature, budget_stage) → LLMClient.

    SDK singletons are class-level to share connection pools across sessions.
    Call LLMFactory.create(feature, budget_stage, config) to get a client.
    """

    # Process-level SDK singletons — lazily initialised on first use
    _anthropic: Any = None
    _openai:    Any = None
    _voyage:    Any = None
    _google:    Any = None

    # Provider circuit-breaker state: provider_name → degraded_until (unix timestamp)
    _provider_degraded: dict[str, float] = {}

    @classmethod
    def _openrouter_client(cls) -> Any:
        """Shared OpenAI-SDK client pointed at OpenRouter for all text-generation calls.

        OpenRouter is OpenAI-compatible only (chat/completions endpoint).
        This single client handles all providers (Anthropic, Google, OpenAI) by
        passing the appropriate model ID prefix (e.g. "anthropic/claude-sonnet-4-6").
        """
        if cls._openai is None:
            from openai import AsyncOpenAI  # noqa: PLC0415
            cls._openai = AsyncOpenAI(
                base_url=os.environ["OPENROUTER_BASE_URL"],
                api_key=os.environ["OPENROUTER_API_KEY"],
                default_headers={
                    "HTTP-Referer": os.environ.get("OPENROUTER_SITE_URL", ""),
                    "X-Title": os.environ.get("OPENROUTER_SITE_NAME", "Chitragupt"),
                },
            )
        return cls._openai

    # Kept for backwards compatibility during agent migration to OpenAI SDK format.
    # Remove once all agent code uses client.chat.completions.create().
    @classmethod
    def _anthropic_client(cls) -> Any:
        return cls._openrouter_client()

    @classmethod
    def _openai_client(cls) -> Any:
        return cls._openrouter_client()

    @classmethod
    def _voyage_client(cls) -> Any:
        if cls._voyage is None:
            import voyageai  # noqa: PLC0415
            # Voyage is not on OpenRouter — uses native API with VOYAGE_API_KEY
            cls._voyage = voyageai.AsyncClient(
                api_key=os.environ["VOYAGE_API_KEY"],
            )
        return cls._voyage

    @classmethod
    def is_degraded(cls, provider: str) -> bool:
        return time.monotonic() < cls._provider_degraded.get(provider, 0.0)

    @classmethod
    def mark_degraded(cls, provider: str, duration_seconds: int = 60) -> None:
        cls._provider_degraded[provider] = time.monotonic() + duration_seconds
        logger.warning("Provider '%s' circuit-broken for %ds", provider, duration_seconds)

    @classmethod
    def create(
        cls,
        feature: LLMFeature,
        budget_stage: BudgetStage,
        config: OrchestrationConfig,
    ) -> Any:
        """
        Return a configured LLMClient for the given feature and budget stage.
        Applies budget degradation overrides and provider circuit-breaker.
        Returns a stub object if the provider is degraded and has a cross-vendor fallback.
        """
        if budget_stage == BudgetStage.EXHAUSTED:
            raise BudgetExhaustedError(f"Session budget exhausted — cannot call {feature}")

        # Resolve tier with budget override
        tier = cls._resolve_tier(feature, budget_stage, config)
        provider = cls._provider_for_tier(tier, feature)

        # Apply circuit-breaker: swap to fallback provider if primary is degraded
        if cls.is_degraded(provider):
            logger.info("Primary provider '%s' degraded — using fallback for %s", provider, feature)
            tier, provider = cls._fallback_tier_and_provider(feature, tier, config)

        return cls._build_client(provider, tier, feature, config)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _resolve_tier(
        cls,
        feature: LLMFeature,
        stage: BudgetStage,
        config: OrchestrationConfig,
    ) -> str:
        override = _BUDGET_OVERRIDES.get((feature, stage))
        if override is not None:
            return override
        return getattr(config.models.function_map, str(feature))

    @staticmethod
    def _provider_for_tier(tier: str, feature: LLMFeature) -> str:
        if tier == "embedding":
            return "voyage"
        if tier == "stt":
            return "openai"
        return "anthropic"

    @classmethod
    def _fallback_tier_and_provider(
        cls,
        feature: LLMFeature,
        current_tier: str,
        config: OrchestrationConfig,
    ) -> tuple[str, str]:
        if current_tier == "embedding":
            return "embedding_fallback", "openai"
        if current_tier == "stt":
            return "stt_fallback", "google"
        # Anthropic → Google fallback
        return current_tier + "_fallback", "google"

    @classmethod
    def _build_client(
        cls,
        provider: str,
        tier: str,
        feature: LLMFeature,
        config: OrchestrationConfig,
    ) -> Any:
        # TODO(sprint1): return real typed LLMClient wrappers.
        # For now returns the raw SDK client — nodes will be updated to use the wrapper API.
        if provider == "anthropic":
            return cls._anthropic_client()
        if provider == "voyage":
            return cls._voyage_client()
        if provider == "openai":
            return cls._openai_client()
        if provider == "google":
            # TODO: initialise google.generativeai client
            raise NotImplementedError("Google fallback client not yet wired")
        raise ValueError(f"Unknown provider: {provider}")


class BudgetExhaustedError(Exception):
    """Raised when the session budget is exhausted before an LLM call."""
