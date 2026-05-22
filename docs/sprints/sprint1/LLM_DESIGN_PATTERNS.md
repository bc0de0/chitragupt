# LLM Design Pattern Strategy — Chitragupt

**Status:** Authoritative for Sprint 1 Python service implementation
**Scope:** `services/ai-orchestration` — session lifecycle, LLM injection, lazy loading
**Companion:** `LLM_UNIVERSE.md` — which model to use per function

---

## Problem Statement

Ten LLM-backed functions must be available per session. Loading all ten eagerly wastes money (API clients initialised, connections kept warm) and adds startup latency. Not all functions fire every turn — visual understanding only fires when an image is uploaded; BRD generation only fires once per session. The system must inject the right LLMs at the right moment, scoped to the session, without the caller needing to know how to construct them.

Additionally, state (the Rust `SessionState`) and LLM clients must travel together through the pipeline — both are runtime artifacts, neither belongs in module-level singletons.

---

## Core Pattern: Session-Scoped LLM Factory

```
SessionLLMContextFactory          ← creates contexts; never instantiated per turn
        │
        ▼
SessionLLMContext                 ← one per active session turn; injected via DI
    ├── session_state: SessionStateProto   (from Rust gRPC)
    ├── budget_tracker: BudgetTracker      (reads/writes Redis)
    └── _lazy_clients: dict[Feature, Lazy[LLMClient]]
              │
              └── loaded on first .get(feature) call only
```

The factory creates a **context object** — not LLM connections. The context holds **lazy slots**: each slot knows how to build its LLM client but has not done so yet. The client is constructed the first time `.get(feature)` is called, and cached for the lifetime of that turn.

---

## Enum: LLMFeature

```python
from enum import StrEnum

class LLMFeature(StrEnum):
    INTENT_CLASSIFICATION   = "intent_classification"
    RAG_SYNTHESIS           = "rag_synthesis"
    VISUAL_UNDERSTANDING    = "visual_understanding"
    CHUNK_BOUNDARY          = "chunk_boundary"
    CHUNK_METADATA          = "chunk_metadata"
    EMBEDDING               = "embedding"
    BRD_GENERATION          = "brd_generation"
    DATA_TRANSFORMATION     = "data_transformation"
    REQUIREMENT_REFINEMENT  = "requirement_refinement"
    SPEECH_TO_TEXT          = "speech_to_text"
    IMAGE_OCR               = "image_ocr"
    LOCALIZATION            = "localization"
```

---

## LLMFactory

Stateless. Maps a `LLMFeature` to a fully configured client. All model IDs are constants — no string literals elsewhere in the codebase.

```python
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
import voyageai

# Pinned model constants — the only place these strings appear
_HAIKU   = "claude-haiku-4-5-20251001"
_SONNET  = "claude-sonnet-4-6"
_OPUS    = "claude-opus-4-7"
_GEMINI  = "gemini-2.0-flash"
_WHISPER = "whisper-1"
_VOYAGE  = "voyage-large-2"

class LLMFactory:
    _anthropic: AsyncAnthropic | None = None
    _openai: AsyncOpenAI | None = None
    _voyage: voyageai.Client | None = None

    @classmethod
    def _anthropic_client(cls) -> AsyncAnthropic:
        if cls._anthropic is None:
            cls._anthropic = AsyncAnthropic()   # reads ANTHROPIC_API_KEY from env
        return cls._anthropic

    @classmethod
    def create(cls, feature: LLMFeature) -> LLMClient:
        match feature:
            case LLMFeature.INTENT_CLASSIFICATION | LLMFeature.RAG_SYNTHESIS \
               | LLMFeature.CHUNK_BOUNDARY | LLMFeature.CHUNK_METADATA \
               | LLMFeature.DATA_TRANSFORMATION | LLMFeature.LOCALIZATION:
                return AnthropicClient(cls._anthropic_client(), model=_HAIKU)

            case LLMFeature.VISUAL_UNDERSTANDING | LLMFeature.IMAGE_OCR \
               | LLMFeature.REQUIREMENT_REFINEMENT:
                return AnthropicClient(cls._anthropic_client(), model=_SONNET)

            case LLMFeature.BRD_GENERATION:
                return AnthropicClient(cls._anthropic_client(), model=_OPUS)

            case LLMFeature.EMBEDDING:
                if cls._voyage is None:
                    cls._voyage = voyageai.Client()   # reads VOYAGE_API_KEY from env
                return VoyageClient(cls._voyage, model=_VOYAGE)

            case LLMFeature.SPEECH_TO_TEXT:
                if cls._openai is None:
                    cls._openai = AsyncOpenAI()       # reads OPENAI_API_KEY from env
                return WhisperClient(cls._openai, model=_WHISPER)
```

**Key design decisions:**
- SDK instances (`AsyncAnthropic`, `AsyncOpenAI`, `voyageai.Client`) are process-level singletons. They manage connection pools internally. Creating one per session would be wasteful.
- `LLMClient` wrapper objects (thin adapters over the SDK) are created per session feature. They are lightweight — they hold a reference to the SDK instance plus the model ID and retry config.
- The `match` is exhaustive — adding a new `LLMFeature` variant without updating this factory is a runtime error at first use. (A future sprint can add a `@staticmethod` validation at startup.)

---

## SessionLLMContext

Injected at the start of every turn. Holds state + lazy LLM slots.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class SessionLLMContext:
    session_state: SessionStateProto      # from Rust gRPC — immutable for this turn
    budget: BudgetTracker                 # reads/writes Redis
    _slots: dict[LLMFeature, Any] = field(default_factory=dict, init=False, repr=False)

    def get(self, feature: LLMFeature) -> LLMClient:
        """Return the LLM client for this feature, constructing it on first access."""
        if feature not in self._slots:
            client = LLMFactory.create(feature)
            # Budget check for premium tier — degrade to Sonnet if exhausted
            if feature == LLMFeature.BRD_GENERATION and self.budget.is_exhausted():
                client = LLMFactory.create_with_model(LLMFeature.BRD_GENERATION, fallback=True)
            self._slots[feature] = client
        return self._slots[feature]

    @property
    def phase(self) -> str:
        return self.session_state.current_phase

    @property
    def session_id(self) -> str:
        return self.session_state.session_id
```

**Why not `functools.cached_property`:** `cached_property` requires attribute names at class definition time. We need dynamic feature keys — dict-based lazy cache is the right structure here.

---

## SessionLLMContextFactory

Creates a `SessionLLMContext` for a given turn. Reads session state from the gRPC call; reads budget from Redis. Does **not** create any LLM clients — that happens lazily.

```python
class SessionLLMContextFactory:

    def __init__(self, redis_client: Redis):
        self._redis = redis_client

    async def for_turn(
        self,
        session_state: SessionStateProto,
    ) -> SessionLLMContext:
        budget = await BudgetTracker.load(
            session_id=session_state.session_id,
            redis=self._redis,
        )
        return SessionLLMContext(
            session_state=session_state,
            budget=budget,
        )
```

The factory is injected once at service startup (not per session). The context is created per turn and garbage-collected after the turn completes — no long-lived session objects holding open LLM connections.

---

## Injection into the LangGraph Pipeline

The `SessionLLMContext` is added to the `PipelineState` TypedDict so every node in the graph can access it without importing singletons:

```python
class PipelineState(TypedDict):
    session_state:  SessionStateProto
    llm_ctx:        SessionLLMContext      # ← injected here
    user_message:   str
    intent:         str | None
    extracted_entities: list[Entity]
    retrieved_chunks:   list[ChunkRef]
    gap_analysis:   GapResult | None
    guidance_tokens: list[str]
```

Each node receives the full `PipelineState` and calls `state["llm_ctx"].get(LLMFeature.X)` to obtain its client. No node imports `LLMFactory` or holds a reference to an LLM client as an instance variable.

```python
class IntentClassifierNode:
    async def __call__(self, state: PipelineState) -> PipelineState:
        client = state["llm_ctx"].get(LLMFeature.INTENT_CLASSIFICATION)
        intent = await client.classify(state["user_message"], state["session_state"])
        return {**state, "intent": intent}
```

---

## Phase → Feature Activation Map

Not all features are active in all phases. This table controls which lazy slots are **allowed** to be created in a given phase. Attempting to use a feature outside its allowed phases raises `FeatureNotActiveError` (fail-fast, not silent).

| Phase | Active Features |
|---|---|
| `ProblemIntake` | `INTENT_CLASSIFICATION`, `RAG_SYNTHESIS`, `EMBEDDING`, `SPEECH_TO_TEXT`, `IMAGE_OCR` |
| `StakeholderDiscovery` | + `VISUAL_UNDERSTANDING` |
| `RequirementElicitation` | + `DATA_TRANSFORMATION`, `CHUNK_BOUNDARY`, `CHUNK_METADATA` |
| `ConstraintCapture` | + `REQUIREMENT_REFINEMENT` |
| `ArchitectureAlignment` | + `VISUAL_UNDERSTANDING` |
| `ReviewAndSignOff` | + `BRD_GENERATION`, `LOCALIZATION` |
| `SignedOff` | `BRD_GENERATION` (export only), `LOCALIZATION` |

Ingestion pipeline features (`EMBEDDING`, `CHUNK_BOUNDARY`, `CHUNK_METADATA`) are always available because document upload can happen at any phase.

---

## Budget Tracker

Enforces the $5.00 per-session hard limit. Tracked in Redis at `budget:session:{session_id}`.

```python
@dataclass
class BudgetTracker:
    session_id: str
    _spent_usd: float          # loaded from Redis on creation
    _limit_usd: float = 5.00
    _redis: Redis = field(repr=False)

    @classmethod
    async def load(cls, session_id: str, redis: Redis) -> BudgetTracker:
        raw = await redis.get(f"budget:session:{session_id}")
        spent = float(raw or 0.0)
        return cls(session_id=session_id, _spent_usd=spent, _redis=redis)

    def is_exhausted(self) -> bool:
        return self._spent_usd >= self._limit_usd

    async def record(self, cost_usd: float) -> None:
        self._spent_usd += cost_usd
        await self._redis.incrbyfloat(f"budget:session:{self._session_id}", cost_usd)
```

Every `LLMClient` wrapper calls `budget.record(cost)` after each successful API call, using the usage tokens from the API response and the tier pricing from `LLM_UNIVERSE.md`.

---

## Startup Wiring (gRPC Service Entry Point)

```python
async def serve():
    redis  = await create_redis_pool(settings.REDIS_URL)
    factory = SessionLLMContextFactory(redis_client=redis)

    server = grpc.aio.server()
    ai_orchestration_pb2_grpc.add_AIOrchestrationServicer_to_server(
        AIOrchestrationServicer(llm_context_factory=factory),
        server,
    )
    await server.start()
    await server.wait_for_termination()
```

`LLMFactory` SDK instances are lazily initialised on the first call that needs them — not at startup. This means the service starts in ~50ms even if an LLM API key is misconfigured; the error surfaces on the first actual LLM call.

---

## Anti-Patterns to Avoid

| Anti-pattern | Why it's wrong | Correct approach |
|---|---|---|
| Module-level `anthropic_client = AsyncAnthropic()` | Ties client lifetime to process lifetime; prevents test injection | Use `LLMFactory` class-level laziness |
| Passing model ID strings as function arguments | Spreads pinned constants across the codebase | Only `LLMFactory` knows model IDs |
| Creating a new `AsyncAnthropic()` per turn | Destroys connection pool; rate-limit state lost | Process-level SDK singleton in `LLMFactory` |
| Calling `LLMFactory.create()` directly in a node | Bypasses budget and phase-activation checks | Always use `state["llm_ctx"].get(feature)` |
| Storing `SessionLLMContext` in Redis or a database | Contexts are turn-scoped; they hold live connections | Create fresh context per turn, discard after |

---

## What Is Not Decided Here

- The `SessionUser` or `SessionObject` that the user mentioned — this is deferred to a later sprint when the user/session data model is formalised. The `SessionLLMContext` is designed to be attached to that object as a field once it exists.
- Authentication / API key rotation — keys come from environment variables for Sprint 1. Secret management (Vault, AWS Secrets Manager) is a Phase 2 concern.
- Multi-tenancy budget isolation — the $5.00 limit is per session. Per-tenant aggregate limits require a separate ledger and are deferred.

---

> LLM Design Patterns · Chitragupt · Sprint 1 · May 2026
