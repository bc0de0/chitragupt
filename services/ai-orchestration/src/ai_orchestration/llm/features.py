"""LLMFeature enum and BudgetStage enum.

These are the only two enums that control model selection and degradation.
Every LLM call site in the service uses LLMFeature — never raw model ID strings.
"""
from __future__ import annotations

from enum import StrEnum


class LLMFeature(StrEnum):
    INTENT_CLASSIFICATION  = "intent_classification"
    RAG_SYNTHESIS          = "rag_synthesis"
    VISUAL_UNDERSTANDING   = "visual_understanding"
    CHUNK_BOUNDARY         = "chunk_boundary"
    CHUNK_METADATA         = "chunk_metadata"
    EMBEDDING              = "embedding"
    BRD_GENERATION         = "brd_generation"
    DATA_TRANSFORMATION    = "data_transformation"
    REQUIREMENT_REFINEMENT = "requirement_refinement"
    SPEECH_TO_TEXT         = "speech_to_text"
    IMAGE_OCR              = "image_ocr"
    LOCALIZATION           = "localization"


class BudgetStage(StrEnum):
    """Per-session spend stage. Controls which model tier is available."""
    NORMAL    = "normal"     # < $3.00  — all tiers available
    CAUTION   = "caution"    # $3–4.50  — Opus → Sonnet; BA notified once
    CRITICAL  = "critical"   # $4.50–5  — Sonnet → Haiku (except BRD); BA notified again
    EXHAUSTED = "exhausted"  # ≥ $5.00  — all LLM calls blocked
