# LLM Orchestration Strategy — Chitragupt

**Status:** Authoritative for Sprint 1 implementation
**Scope:** `services/ai-orchestration` — pipeline topology, framework choice, error handling, streaming
**Companion documents:**
- `LLM_UNIVERSE.md` — which model handles which function
- `LLM_DESIGN_PATTERNS.md` — session-scoped factory and lazy loading
- `LLM_DEGRADATION.md` — fallback triggers and degradation matrix

---

## The Core Problem

Every BA turn requires five LLM-backed operations to execute in sequence: classify intent, extract entities, retrieve context, analyze gaps, generate guidance. These operations are not independent — each one feeds the next. The orchestration layer must:

1. Wire the five operations into a reliable sequential pipeline.
2. Pass structured state between nodes without coupling node implementations.
3. Stream the final guidance tokens back to the Rust state machine as they arrive — not buffered.
4. Survive individual node failures without crashing the entire turn.
5. Stay within the latency budget (first token to the BA in under 2 seconds after the LLM begins).

The answer to all five requirements is **LangGraph** — the only Python-native framework that supports stateful, streaming, graph-based pipelines with first-class async support.

---

## Framework Decision: LangGraph (Direct SDK) — Not OpenRouter

Two approaches were evaluated for Sprint 1:

### Option A — LangGraph + Direct Provider SDKs (Chosen)

Each `LLMClient` in `LLMFactory` wraps the provider's own async SDK: `AsyncAnthropic`, `AsyncOpenAI`, `voyageai.Client`. Fallback switching is handled in Python code at the `SessionLLMContext.get()` call site.

**Why this is the right choice for Sprint 1:**
- Zero additional vendor. Every API key is already required (Anthropic, OpenAI for Whisper, Voyage for embedding). OpenRouter would be a fourth dependency.
- Direct SDK calls expose full provider-specific features: Anthropic prompt caching, streaming `tool_use`, Voyage batch embedding. OpenRouter proxies these but with occasional feature lag.
- The fallback logic is simple (two providers per function, budget-gated). It does not warrant a routing proxy.
- Latency: OpenRouter adds 30–80ms per call. Across a 5-node pipeline this compounds. At MVP scale with a 2-second first-token budget, this is significant.

### Option B — LangGraph + OpenRouter (Deferred to Sprint 3)

OpenRouter becomes valuable when:
- The number of providers per function exceeds two (cost arbitrage across five providers).
- Provider credit management needs centralisation (one API key, one billing dashboard).
- Dynamic routing based on real-time provider latency/cost is required.

None of these conditions apply in Sprint 1. OpenRouter is not a wrong choice — it is a premature one. Revisit when the fallback matrix in `LLM_DEGRADATION.md` grows beyond two levels.

---

## Pipeline Topology

The per-turn pipeline is a linear directed graph. There are no branches in the happy path. Branches appear only in error handling (see Section 5).

```
ProcessTurn (Rust gRPC call)
         │
         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │  LangGraph Pipeline (Python)                                    │
  │                                                                 │
  │  IntentClassifier  →  EntityExtractor  →  RAGRetrieval          │
  │                                                 │               │
  │                                         GapAnalyzer             │
  │                                                 │               │
  │                                       GuidanceGenerator  ──────►│──► stream tokens → Rust
  └─────────────────────────────────────────────────────────────────┘
         │
         ▼
  PipelineComplete (entities, ac_updates, intent) → Rust
```

### Node Responsibilities and Time Budgets

| Node | LLM | Max wall time | Output |
|---|---|---|---|
| `IntentClassifier` | Haiku (fast) | 200 ms | `intent: str` — one of 8 intent codes |
| `EntityExtractor` | Haiku (standard) | 500 ms | `extracted_entities: list[Entity]` |
| `RAGRetrieval` | Voyage (embedding) + pgvector | 300 ms | `retrieved_chunks: list[ChunkRef]` |
| `GapAnalyzer` | Sonnet | 800 ms | `gap_analysis: GapResult` — first unmet AC + suggested question |
| `GuidanceGenerator` | Opus/Sonnet | streaming | `guidance_tokens: list[str]` — streamed to Rust |

Total to first guidance token: ~2 seconds (1 800 ms synchronous nodes + LLM time-to-first-token).

The `GuidanceGenerator` is the only streaming node. All upstream nodes complete synchronously before it fires, so the full context (intent, entities, retrieved chunks, gap) is available when it starts generating.

---

## PipelineState — The Shared Contract

`PipelineState` is the TypedDict threaded through every node. No node imports another node's class or calls it directly — they only read and write fields of this shared object.

```python
from typing import TypedDict, Optional
from uuid import UUID

class PipelineState(TypedDict):
    # Inputs (set by the pipeline entry point, never mutated by nodes)
    session_state:       SessionStateProto   # from Rust gRPC, immutable
    user_message:        str
    llm_ctx:             SessionLLMContext   # lazy LLM factory + budget tracker

    # Outputs (each node writes its own field; reads from upstream fields)
    intent:              Optional[str]                  # set by IntentClassifier
    extracted_entities:  list[Entity]                   # set by EntityExtractor
    retrieved_chunks:    list[ChunkRef]                 # set by RAGRetrieval
    gap_analysis:        Optional[GapResult]            # set by GapAnalyzer
    guidance_tokens:     list[str]                      # set by GuidanceGenerator

    # Error handling
    node_errors:         dict[str, str]                 # node_name → error message
    pipeline_aborted:    bool                           # True if unrecoverable error
```

Fields from upstream nodes are never modified by downstream nodes. `GuidanceGenerator` reads `extracted_entities` and `retrieved_chunks` but does not write to those fields. This makes the pipeline trivially testable — each node can be tested with a minimal `PipelineState`.

---

## LangGraph Graph Definition

```python
from langgraph.graph import StateGraph

def build_pipeline() -> CompiledGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("classify_intent",   IntentClassifierNode())
    graph.add_node("extract_entities",  EntityExtractorNode())
    graph.add_node("retrieve_context",  RAGRetrievalNode())
    graph.add_node("analyze_gaps",      GapAnalyzerNode())
    graph.add_node("generate_guidance", GuidanceGeneratorNode())

    # Linear edges — no branching in the happy path
    graph.add_edge("classify_intent",   "extract_entities")
    graph.add_edge("extract_entities",  "retrieve_context")
    graph.add_edge("retrieve_context",  "analyze_gaps")
    graph.add_edge("analyze_gaps",      "generate_guidance")

    graph.set_entry_point("classify_intent")
    graph.set_finish_point("generate_guidance")

    return graph.compile()

# Singleton — built once at service startup, reused for every turn
PIPELINE: CompiledGraph = build_pipeline()
```

The compiled graph is a process-level singleton. LangGraph's compiled graphs are stateless (all state is in `PipelineState`) and thread/task-safe — it can be shared across concurrent async pipeline invocations.

---

## Node Implementation Contract

Every node is a callable class with one `async __call__` method. This makes nodes independently testable and injectable as dependencies.

```python
from abc import ABC, abstractmethod

class PipelineNode(ABC):
    @abstractmethod
    async def __call__(self, state: PipelineState) -> PipelineState:
        """
        Receives full PipelineState. Returns updated PipelineState.
        Must not raise — all errors are caught and written to state["node_errors"].
        """
        ...
```

The no-raise contract is deliberate. LangGraph will propagate an unhandled exception as a pipeline abort. Nodes are instead responsible for writing errors to `state["node_errors"][self.__class__.__name__]` and returning the state with reasonable defaults so downstream nodes can degrade gracefully (see Section 5).

---

## Streaming Architecture

`GuidanceGenerator` is the only node that streams. Streaming is implemented as a generator that yields tokens as they arrive from the Anthropic SDK:

```python
class GuidanceGeneratorNode(PipelineNode):

    async def __call__(self, state: PipelineState) -> PipelineState:
        client = state["llm_ctx"].get(LLMFeature.BRD_GENERATION
                                      if state["session_state"].current_phase == "ReviewAndSignOff"
                                      else LLMFeature.REQUIREMENT_REFINEMENT)
        tokens = []

        async with client.stream(
            system=self._build_system_prompt(state),
            user=self._build_user_prompt(state),
        ) as stream:
            async for token in stream:
                tokens.append(token)
                # Yield token to the gRPC streaming response — not buffered
                await state["llm_ctx"].token_sink.send(token)

        return {**state, "guidance_tokens": tokens}
```

`token_sink` is an `asyncio.Queue` injected into `SessionLLMContext` by `SessionLLMContextFactory`. The gRPC servicer reads from this queue and streams `PipelineEvent.token` messages to Rust, which forwards them to Go, which forwards them to the browser.

This means the BA sees the first word of the response approximately `(IntentClassifier + EntityExtractor + RAGRetrieval + GapAnalyzer) + LLM time-to-first-token` after sending a message — around 2 seconds for a warm pipeline. The pipeline nodes upstream of `GuidanceGenerator` must complete before tokens begin flowing.

---

## Prompt Caching Strategy

All Anthropic calls use the prompt cache. The static part of the prompt (system context, phase instructions, output schema, AC gap) is placed in the `cache_control: ephemeral` block. Only the variable part (user message, retrieved chunk content) follows the cached prefix.

```python
def build_cached_messages(
    system_prompt: str,         # static: phase instructions + output schema
    retrieved_context: str,     # variable: chunk content changes per turn
    user_message: str,          # variable: what the BA just said
) -> list[dict]:
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},  # ← cached prefix
                },
                {
                    "type": "text",
                    "text": f"Context:\n{retrieved_context}\n\nBA: {user_message}",
                    # ↑ not cached — variable per turn
                },
            ],
        }
    ]
```

**Target:** ≥ 80% of input tokens served from cache across a session. The system prompt and AC instructions do not change within a phase — they are fully cacheable. Only retrieved chunks and the BA's message are variable.

**Effect on cost:** Cached tokens are billed at approximately 10% of the base input price for Anthropic models. Hitting this target on the `GapAnalyzer` and `GuidanceGenerator` nodes (which have the largest system prompts) reduces the per-turn cost by an estimated 30–40%.

---

## Ingestion Pipeline (Asynchronous, Separate from Per-Turn)

Document ingestion runs in a separate async worker, triggered by `Python.IngestDocument`. It is not part of the per-turn LangGraph pipeline.

```
IngestDocument (gRPC call from Go)
         │
         ▼
  DocumentParser        (pypdf / python-docx / openpyxl — rule-based, no LLM)
         │
         ▼
  PIIScrubber           (presidio-analyzer — rule-based, no LLM)
         │
         ▼
  ChunkBoundaryDetector (Haiku for ambiguous splits; rule-based for most)
         │
         ▼
  ChunkMetadataSummariser (Haiku — section title, entity hints)
         │
         ▼
  EmbeddingBatcher      (voyage-large-2 — up to 128 chunks per API call)
         │
         ▼
  ChunkWriter           (asyncpg bulk INSERT into chunk table)
         │
         ▼
  DocumentStatusUpdater (UPDATE document SET status = 'indexed')
         │
         ▼
  EventPublisher        (PUBLISH events:upload:complete → Redis)
```

This pipeline is fire-and-forget from the gRPC caller's perspective. `IngestDocument` returns `IngestAck` immediately. The ingestion worker runs to completion in the background. Failures are written to `document.status = 'failed'` and surfaced via the `audit_log`.

---

## Error Handling

### Node-Level: Catch, Record, Continue

Every node wraps its core logic in a try/except. On failure, it writes the error to `state["node_errors"]` and returns the state with safe defaults so downstream nodes can still attempt execution.

```python
class IntentClassifierNode(PipelineNode):
    async def __call__(self, state: PipelineState) -> PipelineState:
        try:
            client = state["llm_ctx"].get(LLMFeature.INTENT_CLASSIFICATION)
            intent = await client.classify(state["user_message"], state["session_state"])
            return {**state, "intent": intent}
        except Exception as e:
            logger.warning("IntentClassifier failed: %s", e)
            return {
                **state,
                "intent": "Clarification",          # safe default — least disruptive intent
                "node_errors": {**state["node_errors"], "IntentClassifierNode": str(e)},
            }
```

The default intent `Clarification` is chosen because it does not trigger entity extraction for any specific phase and does not advance AC — it simply asks the BA to clarify. This is the least harmful default when intent classification fails.

### Pipeline-Level: Abort on GuidanceGenerator Failure

`GuidanceGenerator` failure is not recoverable with a default. If it fails, there is nothing to stream to the BA. The pipeline sets `pipeline_aborted = True`, which signals the gRPC servicer to send a fallback error message to the BA and log the failure.

```python
class GuidanceGeneratorNode(PipelineNode):
    async def __call__(self, state: PipelineState) -> PipelineState:
        try:
            # ... generation logic ...
        except BudgetExhaustedError:
            # Degrade to fallback model — see LLM_DEGRADATION.md
            return await self._run_with_fallback(state)
        except Exception as e:
            logger.error("GuidanceGenerator failed unrecoverably: %s", e)
            return {**state, "pipeline_aborted": True,
                    "node_errors": {**state["node_errors"], "GuidanceGeneratorNode": str(e)}}
```

### Retry Policy

All LLM API calls use `tenacity` with exponential backoff. The policy is set at the `LLMClient` wrapper level so every node inherits it automatically.

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIStatusError)),
    reraise=True,   # final attempt failure is re-raised to the node's except block
)
async def _call_with_retry(self, *args, **kwargs):
    return await self._client.messages.create(*args, **kwargs)
```

Three attempts, 0.5s → 1s → 2s wait. Rate limit and server errors (5xx) are retried. Authentication errors (401) and invalid request errors (400) are not — they are permanent failures that retrying will not fix.

---

## Observability

Every pipeline invocation produces a structured trace. Trace spans are emitted via `tracing-opentelemetry` (Python equivalent: `opentelemetry-sdk`) and forwarded to the observability backend (D-009 in DECISIONS.md — not yet decided; traces are emitted to stdout in Sprint 1).

Each node emits:
- `node.start` — session_id, phase, node_name, timestamp
- `node.complete` — node_name, duration_ms, success, model_id (if LLM was called)
- `node.error` — node_name, error_type, error_message (if failed)

The `llm_call_log` PostgreSQL table is the authoritative cost record — see `DATABASE.md` Section 1.4.

---

## What This Document Does Not Cover

- **OpenRouter integration** — deferred to Sprint 3. Current design assumes direct SDK calls.
- **Parallel node execution** — all nodes run sequentially in Sprint 1. RAGRetrieval could theoretically run in parallel with EntityExtractor but the dependency (entity hints improve retrieval quality) justifies sequential ordering.
- **LangGraph persistence / checkpointing** — not used in Sprint 1. `PipelineState` is ephemeral per turn. Session state persistence is handled by Rust (PostgreSQL + Redis), not LangGraph.
- **Multi-agent subgraphs** — Sprint 1 uses a flat linear pipeline. Subgraphs for specialised elicitation agents (e.g., a dedicated compliance agent for regulated domains) are a Sprint 2 concern.

---

> LLM Orchestration Strategy · Chitragupt · Sprint 1 · May 2026
