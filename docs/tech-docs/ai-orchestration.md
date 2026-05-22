# AI Orchestration Service — Technical Reference

**Service:** `services/ai-orchestration` (Python)
**gRPC port:** `:50052`
**Role:** Sole owner of all LLM interactions, RAG retrieval, entity extraction, and document ingestion. Receives a session state and a user message from Rust; returns a stream of guidance tokens plus structured extraction results.

---

## 1. What Problem This Solves

The per-turn conversation pipeline requires five sequential AI operations: classify intent, extract entities, retrieve context, analyze gaps, generate guidance. Each operation feeds the next. The orchestration layer must:

1. Wire the five operations into a reliable, sequential pipeline.
2. Thread structured state between nodes without coupling node implementations.
3. Stream guidance tokens back to Rust as they are generated — no internal buffering.
4. Survive individual node failures without aborting the turn.
5. Stay within a per-session cost budget and degrade gracefully when thresholds are breached.

The answer is **LangGraph** — a Python-native framework for stateful, streaming, graph-based pipelines with first-class async support.

---

## 2. Architecture Position

```
Go API Gateway  (:8080)
      │
      ▼ gRPC ProcessTurn
Rust State Machine  (:50051)
      │  (gates clear — Python is called)
      ▼ gRPC RunPipeline
Python AI Orchestration  (:50052)   ◄── owns all LLM + RAG
      │
      ▼ streams tokens back up the chain → Rust → Go → Browser
```

The Python service never makes state decisions. It does not know which phase is valid next. It receives a `SessionState` snapshot from Rust, runs the pipeline, and returns tokens + entities. What Rust does with those results is Rust's concern.

Document ingestion (`IngestDocument`) is a separate, fire-and-forget gRPC entry point. It runs an async worker independently of the per-turn pipeline.

---

## 3. Module Structure

```
services/ai-orchestration/
├── pyproject.toml                    uv-managed dependencies (PEP 517)
├── config/
│   └── orchestration.yaml            Master configuration — model IDs, budgets, timeouts, RAG params
└── src/ai_orchestration/
    ├── __init__.py
    ├── config.py                     OrchestrationConfig — typed Pydantic loader for orchestration.yaml
    ├── executor.py                   PipelineExecutor — process singleton; owns the compiled graph
    │
    ├── pipeline/
    │   ├── __init__.py
    │   └── state.py                  PipelineState TypedDict — the contract between nodes
    │
    ├── agents/
    │   ├── __init__.py
    │   ├── base.py                   PipelineNode ABC — all nodes implement __call__(state) → state
    │   ├── intent_classifier.py      Node 1 — fast LLM; 8 intent codes
    │   ├── entity_extractor.py       Node 2 — standard LLM; state-specific extraction
    │   ├── rag_retrieval.py          Node 3 — hybrid pgvector + BM25 search
    │   ├── gap_analyzer.py           Node 4 — standard LLM; AC gap identification
    │   └── guidance_generator.py     Node 5 — premium LLM; streaming response
    │
    ├── llm/
    │   ├── __init__.py
    │   ├── features.py               LLMFeature enum + BudgetStage enum
    │   ├── factory.py                LLMFactory — (feature, budget_stage) → LLMClient
    │   ├── budget.py                 BudgetTracker — per-session cost accumulation + threshold gates
    │   └── context.py                SessionLLMContext — per-turn factory facade + token sink
    │
    └── models/
        ├── __init__.py
        └── entities.py               Entity, ChunkRef, GapResult, AcUpdate, TurnResult Pydantic models
```

---

## 4. PipelineState — The Node Contract

`PipelineState` is a `TypedDict` threaded through every node. Nodes only read fields written by upstream nodes and write their own output field. No node imports another node directly — they communicate entirely through this shared state.

```python
class PipelineState(TypedDict):
    # Inputs — set at entry, never mutated by nodes
    session_state:       SessionStateProto   # from Rust gRPC; immutable
    user_message:        str
    llm_ctx:             SessionLLMContext   # lazy LLM factory + budget tracker + token sink

    # Node outputs — each node writes exactly one field
    intent:              Optional[str]                  # IntentClassifier
    extracted_entities:  list[Entity]                   # EntityExtractor
    retrieved_chunks:    list[ChunkRef]                 # RAGRetrieval
    gap_analysis:        Optional[GapResult]            # GapAnalyzer
    guidance_tokens:     list[str]                      # GuidanceGenerator
    ac_updates:          list[AcUpdate]                 # EntityExtractor / GapAnalyzer

    # Error tracking — any node can write here; pipeline continues unless aborted
    node_errors:         dict[str, str]                 # node_name → error message
    pipeline_aborted:    bool                           # True only on GuidanceGenerator failure
```

This structure makes every node independently testable. A test for `GapAnalyzerNode` constructs a `PipelineState` with `intent`, `extracted_entities`, and `retrieved_chunks` filled in and verifies the `gap_analysis` output — no LLM mocks needed for upstream fields.

---

## 5. Pipeline Topology

The per-turn pipeline is a linear directed graph. All five nodes run to completion before the response is fully assembled; only the final node streams.

```
classify_intent → extract_entities → retrieve_context → analyze_gaps → generate_guidance
```

```python
def build_pipeline(config: OrchestrationConfig) -> CompiledGraph:
    graph: StateGraph = StateGraph(PipelineState)

    graph.add_node("classify_intent",   IntentClassifierNode(config))
    graph.add_node("extract_entities",  EntityExtractorNode(config))
    graph.add_node("retrieve_context",  RAGRetrievalNode(config))
    graph.add_node("analyze_gaps",      GapAnalyzerNode(config))
    graph.add_node("generate_guidance", GuidanceGeneratorNode(config))

    graph.add_edge("classify_intent",  "extract_entities")
    graph.add_edge("extract_entities", "retrieve_context")
    graph.add_edge("retrieve_context", "analyze_gaps")
    graph.add_edge("analyze_gaps",     "generate_guidance")

    graph.set_entry_point("classify_intent")
    graph.set_finish_point("generate_guidance")

    return graph.compile()

# Process-level singleton — built once at startup, shared across all concurrent turns
PIPELINE: CompiledGraph = build_pipeline(config)
```

The compiled graph is stateless (all turn state lives in `PipelineState`) and safe to share across concurrent async invocations without locking.

### Node Time Budgets

| Node | LLM tier | Max wall time | Output |
|---|---|---|---|
| `IntentClassifier` | Fast (Haiku) | 800 ms | `intent` — one of 8 intent codes |
| `EntityExtractor` | Standard (Sonnet) | 1 500 ms | `extracted_entities` list |
| `RAGRetrieval` | Voyage (embedding) | 1 000 ms | `retrieved_chunks` list |
| `GapAnalyzer` | Standard (Sonnet) | 3 000 ms | `gap_analysis` with next question |
| `GuidanceGenerator` | Premium (Opus) | 20 000 ms | `guidance_tokens` — streamed |

---

## 6. Node Implementation Contract

Every node is a callable class that receives `PipelineState` and returns an updated `PipelineState`. The no-raise rule is fundamental: nodes must never propagate exceptions to LangGraph. A node failure writes to `node_errors` and returns safe defaults so downstream nodes can attempt execution.

```python
class PipelineNode(ABC):
    @abstractmethod
    async def __call__(self, state: PipelineState) -> PipelineState:
        """Must not raise. All errors written to state["node_errors"]."""
        ...
```

**Safe-default pattern for non-terminal nodes:**

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
                "intent": "Clarification",   # least-disruptive default; does not trigger extraction
                "node_errors": {**state["node_errors"], "IntentClassifierNode": str(e)},
            }
```

`GuidanceGeneratorNode` is the exception: if it fails, there is nothing to stream to the BA. It sets `pipeline_aborted = True`, which signals `PipelineExecutor` to raise `PipelineAbortedError`. The gRPC servicer catches this and sends a static fallback message.

---

## 7. PipelineExecutor

`PipelineExecutor` is the process-level singleton that owns the compiled graph and exposes the turn entry point to the gRPC servicer.

```python
class PipelineExecutor:
    def __init__(self, config: OrchestrationConfig) -> None:
        self._graph: CompiledGraph = build_pipeline(config)

    async def run(
        self,
        session_state: Any,
        user_message: str,
        llm_ctx: SessionLLMContext,
    ) -> AsyncGenerator[str, None]:
        """
        Execute one BA turn. Yields guidance tokens as they stream.
        After exhaustion, executor.last_result holds entities, AC updates, cost.
        Raises PipelineAbortedError if GuidanceGenerator fails.
        """
```

**Streaming concurrency model:**

```
asyncio.create_task(graph.ainvoke(initial_state))
                          ↓
             GuidanceGeneratorNode puts tokens on asyncio.Queue
                          ↓
     PipelineExecutor._drain_queue() yields tokens to the gRPC servicer
                          ↓
          gRPC servicer streams PipelineEvent.token to Rust
```

The graph runs as a background asyncio task. The executor reads from the token queue concurrently. A 25-second absolute timeout on the queue drain cancels the pipeline task if `GuidanceGeneratorNode` hangs. Individual node timeouts (from `orchestration.yaml`) are tighter.

`None` on the token queue is the stream-done sentinel, emitted by `GuidanceGeneratorNode` on success and by `_run_graph`'s `finally` block on any error path — ensuring `_drain_queue` always exits cleanly.

---

## 8. LLM Factory — Lazy Loading, Budget Degradation, Circuit Breaker

### LLMFeature and BudgetStage

```python
class LLMFeature(str, Enum):
    INTENT_CLASSIFICATION  = "intent_classification"
    REQUIREMENT_REFINEMENT = "requirement_refinement"
    RAG_SYNTHESIS          = "rag_synthesis"
    VISUAL_UNDERSTANDING   = "visual_understanding"
    BRD_GENERATION         = "brd_generation"
    EMBEDDING              = "embedding"
    # ... 6 additional features
```

```python
class BudgetStage(str, Enum):
    NORMAL    = "normal"     # < $3.00 — full tier
    CAUTION   = "caution"    # $3.00–$4.50 — premium → standard
    CRITICAL  = "critical"   # $4.50–$5.00 — standard → fast (BRD floor: standard)
    EXHAUSTED = "exhausted"  # > $5.00 — all LLM calls blocked
```

### LLMFactory.create()

```python
@classmethod
def create(cls, feature: LLMFeature, budget_stage: BudgetStage, config: OrchestrationConfig) -> Any:
    if budget_stage == BudgetStage.EXHAUSTED:
        raise BudgetExhaustedError(...)

    tier     = cls._resolve_tier(feature, budget_stage, config)  # applies budget overrides
    provider = cls._provider_for_tier(tier, feature)

    if cls.is_degraded(provider):                                 # circuit breaker
        tier, provider = cls._fallback_tier_and_provider(feature, tier, config)

    return cls._build_client(provider, tier, feature, config)    # lazy-init SDK singleton
```

**Budget override matrix** — the BRD quality floor (`brd_min_model: standard`) means `BRD_GENERATION` never degrades to Fast regardless of budget stage.

**Provider circuit breaker** — `mark_degraded(provider, duration_seconds=60)` is called after `failure_threshold` (default: 3) sustained provider errors. The degraded provider is bypassed for 60 seconds; calls route to the cross-vendor fallback (Anthropic → Google, Voyage → OpenAI text-embedding-3-small).

**Lazy SDK initialization** — SDK clients (`AsyncAnthropic`, `AsyncOpenAI`, `voyageai.AsyncClient`) are class-level singletons, created on first use. Connection pools are reused across all sessions and turns. A service that starts with no API calls loaded will initialize the first SDK client at the first request.

---

## 9. Streaming Architecture

`GuidanceGeneratorNode` streams tokens through an `asyncio.Queue` injected into `SessionLLMContext`:

```python
async with anthropic_client.messages.stream(
    model=model_id,
    system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
    messages=[{"role": "user", "content": user_content}],
) as stream:
    async for token in stream.text_stream:
        await state["llm_ctx"].token_sink.put(token)  # non-blocking up to maxsize=256

await state["llm_ctx"].token_sink.put(None)  # stream-done sentinel
```

The queue `maxsize=256` (configurable) provides ~1000 tokens of buffering at typical token sizes. If the downstream consumer (gRPC servicer) is slower than the LLM, the `put` will back-pressure the LLM stream. This is intentional — it prevents unbounded memory use during long BRD generations.

### Prompt Caching

All Anthropic calls place the static part of the prompt in `cache_control: ephemeral`. Only the variable part (retrieved chunks, user message) follows the cache break. Target: ≥ 80% of input tokens served from cache across a session.

```python
def build_cached_messages(system_prompt: str, retrieved_context: str, user_message: str):
    return [{"role": "user", "content": [
        {"type": "text", "text": system_prompt,
         "cache_control": {"type": "ephemeral"}},       # ← cached prefix
        {"type": "text", "text": f"Context:\n{retrieved_context}\n\nBA: {user_message}"},
    ]}]
```

At 80% cache hit rate on `GapAnalyzer` and `GuidanceGenerator` (the nodes with the largest system prompts), prompt caching reduces per-turn cost by an estimated 30–40%.

---

## 10. RAG Retrieval Parameters

Configured in `config/orchestration.yaml` under the `rag:` key:

| Parameter | Default | Meaning |
|---|---|---|
| `top_k` | 20 | Final chunks returned to GapAnalyzer after all stages |
| `candidate_pool` | 50 | ANN candidate pool before re-ranking |
| `rerank_top_k` | 10 | Top-k after cross-encoder re-rank |
| `bm25_weight` | 0.3 | Weight for sparse BM25 score in hybrid fusion |
| `dense_weight` | 0.7 | Weight for dense cosine similarity score |

Hybrid retrieval fuses BM25 (keyword match) and vector similarity (Voyage embedding) using Reciprocal Rank Fusion before the cross-encoder re-rank pass. Chunks are namespaced per `(tenant_id, project_id)` in pgvector — no cross-tenant retrieval is possible.

---

## 11. Ingestion Pipeline

Document ingestion is asynchronous, triggered by `AIOrchestration.IngestDocument`. It is independent of the per-turn LangGraph pipeline.

```
IngestDocument (gRPC from Go)
       │
       ▼ returns IngestAck immediately
DocumentParser         (pypdf / python-docx / openpyxl — rule-based)
       │
       ▼
PIIScrubber            (presidio-analyzer — before any embedding)
       │
       ▼
ChunkBoundaryDetector  (Haiku for ambiguous splits; rule-based otherwise)
       │
       ▼
ChunkMetadataSummariser (Haiku — section title, entity hints per chunk)
       │
       ▼
EmbeddingBatcher       (voyage-large-2 — up to 128 chunks per API call)
       │
       ▼
ChunkWriter            (asyncpg bulk INSERT into chunk + vector tables)
       │
       ▼
DocumentStatusUpdater  (UPDATE document SET status = 'indexed')
       │
       ▼
EventPublisher         (PUBLISH events:upload:complete → Redis)
```

Rust subscribes to `events:upload:complete` and calls `NotifyUploadComplete` on itself to re-evaluate upload AC — this is what resolves a blocking hard gate after a document arrives mid-session.

Failures set `document.status = 'failed'` and write to `audit_log`. The BA is notified by Rust on the next turn when it reads the `failed` status.

---

## 12. gRPC Interface (Python exposes)

```protobuf
service AIOrchestration {
  // Primary per-turn pipeline. Returns a stream of tokens + entity/AC events.
  rpc RunPipeline(PipelineRequest) returns (stream PipelineEvent);

  // Async document ingestion — returns IngestAck immediately; fires Redis event on completion.
  rpc IngestDocument(IngestRequest) returns (IngestAck);

  // Batch re-embedding (used after embedding model upgrades — full reindex).
  rpc ReEmbed(ReEmbedRequest) returns (stream ReEmbedProgress);
}

message PipelineEvent {
  oneof payload {
    StreamToken      token    = 1;   // guidance text token — relay to browser
    EntityUpdate     entity   = 2;   // extracted entity (arrives mid-stream)
    AcUpdate         ac       = 3;   // AC status change
    PipelineComplete complete = 4;   // turn done; includes cost_usd
  }
}
```

`PipelineComplete` carries `cost_usd` — Rust adds this to `SessionState.session_cost_usd`, which is what triggers `BudgetStage` upgrades on subsequent turns.

---

## 13. Error Handling and Retry Policy

### Retry (all LLM API calls)

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIStatusError)),
    reraise=True,
)
async def _call_with_retry(self, ...): ...
```

Three attempts; 0.5 s → 1 s → 2 s waits. `RateLimitError` and 5xx errors are retried. `401` and `400` are permanent failures — retrying will not help.

After the third attempt fails, `LLMFactory.mark_degraded(provider)` is called if the failure was a server error (5xx), engaging the circuit breaker for 60 seconds.

### Node failure hierarchy

| Node | Failure behaviour | Default value |
|---|---|---|
| `IntentClassifier` | Log warning; continue | `"Clarification"` intent |
| `EntityExtractor` | Log warning; continue | empty entity list |
| `RAGRetrieval` | Log warning; continue | empty chunk list |
| `GapAnalyzer` | Log warning; continue | `None` gap (generator falls back to generic prompt) |
| `GuidanceGenerator` | Log error; set `pipeline_aborted = True` | — |

---

## 14. Key Libraries

| Package | Purpose |
|---|---|
| `langgraph` | Per-turn pipeline graph — stateful, async, streaming |
| `anthropic` | Primary LLM SDK — Claude Opus / Sonnet / Haiku; prompt caching; streaming |
| `openai` | Fallback LLM + Whisper STT |
| `voyageai` | Embedding model (voyage-large-2, 1536-dim); batch API |
| `asyncpg` | Async PostgreSQL; pgvector hybrid search queries |
| `grpcio` + `grpcio-tools` | gRPC server (exposes service to Rust) |
| `redis.asyncio` | Async Redis — publish `events:upload:complete` |
| `pypdf` + `python-docx` + `openpyxl` | Document parsing |
| `rank-bm25` | BM25 sparse vector generation |
| `boto3` | S3 document storage |
| `pydantic` | All LLM structured output schemas; entity models |
| `tenacity` | Retry with exponential backoff on every LLM API call |
| `presidio-analyzer` | PII detection before embedding |
| `uv` | Dependency management (replaces pip/poetry) |

---

## 15. Configuration Reference

All operational parameters live in `config/orchestration.yaml`. The file is loaded once at startup into `OrchestrationConfig` (Pydantic). Nodes read config via constructor injection — never via global state or environment variables (except API keys, which are environment-only for security).

Key sections:

| YAML key | What it controls |
|---|---|
| `orchestration.pipeline.timeout_ms.*` | Per-node wall-time limits |
| `orchestration.retry.*` | tenacity retry policy for all LLM calls |
| `orchestration.streaming.token_queue_maxsize` | asyncio.Queue size for token pipe |
| `models.primary.*` | Pinned model IDs for each tier |
| `models.fallback.*` | Cross-vendor fallback model IDs |
| `models.function_map.*` | Maps each LLMFeature to a tier |
| `budget.session_limit_usd` | Hard cap — all LLM blocked at exhaustion |
| `budget.caution_threshold_usd` | Premium → Standard downgrade threshold |
| `budget.critical_threshold_usd` | Standard → Fast downgrade threshold |
| `rag.top_k` / `rag.bm25_weight` / etc. | Retrieval hyperparameters |
| `ingestion.chunk_size_tokens` | Chunking parameters |

**Model ID changes are deployment events**, not code changes. Update `models.primary.*` in the YAML, test against the evaluation dataset, promote to production.

---

## 16. Local Development

```bash
cd services/ai-orchestration

# Install dependencies (uv resolves from pyproject.toml)
uv sync

# Run the service (gRPC server — once servicer is wired in a later sprint)
uv run python -m ai_orchestration.server

# Run tests
uv run pytest

# Type checking (must pass before any PR)
uv run mypy --strict src/

# Format and import sort
uv run black . && uv run isort .
```

Required environment variables (copy `.env.example` to `.env`):

```bash
ANTHROPIC_API_KEY=sk-ant-...
VOYAGE_API_KEY=pa-...
OPENAI_API_KEY=sk-...            # needed for Whisper STT fallback
DATABASE_URL=postgres://chitragupt:chitragupt@localhost:5432/chitragupt
REDIS_URL=redis://localhost:6379
STATE_MACHINE_ADDR=localhost:50051
```

### Testing a pipeline turn without the gRPC server

```python
from ai_orchestration.config import OrchestrationConfig
from ai_orchestration.executor import PipelineExecutor
from ai_orchestration.llm.context import SessionLLMContextFactory

config   = OrchestrationConfig.default()
factory  = SessionLLMContextFactory(config)
executor = PipelineExecutor(config)

session  = {"session_id": "...", "current_phase": "ProblemIntake", ...}
llm_ctx  = await factory.for_turn(session)

async for token in executor.run(session, "The client wants to automate invoicing", llm_ctx):
    print(token, end="", flush=True)

result = executor.last_result  # TurnResult with entities, AC updates, cost_usd
```

---

> Chitragupt AI Orchestration Service · Technical Reference · Sprint 1 · May 2026
