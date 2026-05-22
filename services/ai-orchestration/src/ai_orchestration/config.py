"""Config loader — reads orchestration.yaml into typed Pydantic models.

Usage:
    config = OrchestrationConfig.default()          # loads config/orchestration.yaml
    config = OrchestrationConfig.from_yaml(path)    # explicit path
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Orchestration section
# ---------------------------------------------------------------------------

class PipelineTimeouts(BaseModel):
    intent_classifier:  int = 800
    entity_extractor:   int = 1500
    rag_retrieval:      int = 1000
    gap_analyzer:       int = 3000
    guidance_generator: int = 20000


class RetryConfig(BaseModel):
    max_attempts:     int   = 3
    wait_min_seconds: float = 0.5
    wait_max_seconds: float = 4.0
    multiplier:       float = 0.5


class StreamingConfig(BaseModel):
    token_queue_maxsize: int = 256


class PromptCacheConfig(BaseModel):
    target_cache_ratio: float = 0.80


class PipelineConfig(BaseModel):
    timeout_ms: PipelineTimeouts = Field(default_factory=PipelineTimeouts)
    streaming:  StreamingConfig  = Field(default_factory=StreamingConfig)


class OrchestrationSection(BaseModel):
    pipeline:     PipelineConfig    = Field(default_factory=PipelineConfig)
    retry:        RetryConfig       = Field(default_factory=RetryConfig)
    prompt_cache: PromptCacheConfig = Field(default_factory=PromptCacheConfig)


# ---------------------------------------------------------------------------
# Models section
# ---------------------------------------------------------------------------

class PrimaryModels(BaseModel):
    fast:      str = "claude-haiku-4-5-20251001"
    standard:  str = "claude-sonnet-4-6"
    premium:   str = "claude-opus-4-7"
    embedding: str = "voyage-large-2"
    stt:       str = "whisper-1"


class FallbackModels(BaseModel):
    anthropic:  str = "gemini-2.0-flash"
    voyage:     str = "text-embedding-3-small"
    openai_stt: str = "gemini-2.0-flash"


class EmbeddingConfig(BaseModel):
    dimension:  int = 1536
    batch_size: int = 128


class FunctionModelMap(BaseModel):
    intent_classification:  str = "fast"
    rag_synthesis:          str = "fast"
    visual_understanding:   str = "standard"
    chunk_boundary:         str = "fast"
    chunk_metadata:         str = "fast"
    embedding:              str = "embedding"
    brd_generation:         str = "premium"
    data_transformation:    str = "fast"
    requirement_refinement: str = "standard"
    speech_to_text:         str = "stt"
    image_ocr:              str = "standard"
    localization:           str = "fast"


class ModelsSection(BaseModel):
    primary:      PrimaryModels  = Field(default_factory=PrimaryModels)
    fallback:     FallbackModels = Field(default_factory=FallbackModels)
    embedding:    EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    function_map: FunctionModelMap = Field(default_factory=FunctionModelMap)


# ---------------------------------------------------------------------------
# Budget section
# ---------------------------------------------------------------------------

class BudgetConfig(BaseModel):
    session_limit_usd:       float = 5.00
    caution_threshold_usd:   float = 3.00
    critical_threshold_usd:  float = 4.50
    brd_min_model:           str   = "standard"


# ---------------------------------------------------------------------------
# Degradation section
# ---------------------------------------------------------------------------

class DegradationConfig(BaseModel):
    failure_threshold:                       int = 3
    provider_circuit_breaker_seconds:        int = 60
    provider_health_check_interval_seconds:  int = 60


# ---------------------------------------------------------------------------
# RAG section
# ---------------------------------------------------------------------------

class RAGConfig(BaseModel):
    top_k:          int   = 20
    bm25_weight:    float = 0.3
    dense_weight:   float = 0.7
    candidate_pool: int   = 50
    rerank_top_k:   int   = 10


# ---------------------------------------------------------------------------
# Ingestion section
# ---------------------------------------------------------------------------

class IngestionConfig(BaseModel):
    chunk_size_tokens:    int  = 512
    chunk_overlap_tokens: int  = 64
    min_chunk_tokens:     int  = 50
    pii_scrub_enabled:    bool = True
    embedding_batch_size: int  = 128


# ---------------------------------------------------------------------------
# Root config
# ---------------------------------------------------------------------------

class OrchestrationConfig(BaseModel):
    orchestration: OrchestrationSection = Field(default_factory=OrchestrationSection)
    models:        ModelsSection        = Field(default_factory=ModelsSection)
    budget:        BudgetConfig         = Field(default_factory=BudgetConfig)
    degradation:   DegradationConfig    = Field(default_factory=DegradationConfig)
    rag:           RAGConfig            = Field(default_factory=RAGConfig)
    ingestion:     IngestionConfig      = Field(default_factory=IngestionConfig)

    @classmethod
    def from_yaml(cls, path: Path | str) -> "OrchestrationConfig":
        with open(path) as fh:
            data = yaml.safe_load(fh)
        return cls.model_validate(data or {})

    @classmethod
    def default(cls) -> "OrchestrationConfig":
        """Load from config/orchestration.yaml relative to the package root."""
        config_path = (
            Path(__file__).parent.parent.parent  # src/ai_orchestration → services/ai-orchestration
            / "config"
            / "orchestration.yaml"
        )
        return cls.from_yaml(config_path)

    def model_id(self, tier: str) -> str:
        """Resolve a tier name ('fast', 'standard', 'premium', etc.) to a pinned model ID."""
        return getattr(self.models.primary, tier)

    def fallback_model_id(self, provider: str) -> str:
        """Resolve a provider name to its fallback model ID."""
        return getattr(self.models.fallback, provider)
