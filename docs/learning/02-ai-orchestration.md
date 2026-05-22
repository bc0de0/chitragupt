# 02 — AI Orchestration: LangGraph, Pipelines, and Async Patterns

**Why this matters for Chitragupt:** The Python AI orchestration service is the brain of the system. It receives every BA conversation turn and routes it through a 5-node LangGraph pipeline, managing LLM calls, document retrieval, and streaming output. Understanding how LangGraph works and why it was chosen is essential for anyone extending the AI service.

---

## 1. What Is AI Orchestration?

An LLM call is a single step. A real AI product needs *sequences* of steps: classify the intent, retrieve relevant documents, extract entities, detect gaps, generate a response. Orchestration frameworks manage these sequences as code rather than spaghetti logic.

**The problem without an orchestration framework:**
```python
# Without LangGraph — hard to test, hard to extend, no state management
def process_turn(user_input):
    intent = call_llm_for_intent(user_input)
    if intent == "requirement":
        docs = search_docs(user_input)
        entities = call_llm_for_extraction(user_input, docs)
        gaps = call_llm_for_gaps(entities)
        return call_llm_for_response(gaps)
    elif intent == ...
```

**The problem with LangGraph:**
- Each step is a typed, testable node
- State flows explicitly between nodes
- The graph can be visualised, inspected, and modified
- Streaming, retries, and observability are built in

---

## 2. LangGraph Core Concepts

LangGraph models a pipeline as a **directed graph**:

```
Node A → Node B → Node C
               ↘ Node D (conditional branch)
```

### State
The data that flows through the graph. In LangGraph, state is a typed dictionary (`TypedDict`) that every node can read and update.

```python
# Chitragupt's PipelineState
class PipelineState(TypedDict):
    session_id: str
    turn_id: str
    user_input: str
    intent: str                      # set by IntentClassifier
    entities: list[Entity]           # set by EntityExtractor
    retrieved_chunks: list[Chunk]    # set by RAGRetrieval
    gaps: list[Gap]                  # set by GapAnalyzer
    guidance: str                    # set by GuidanceGenerator
    token_stream: asyncio.Queue      # streaming output channel
    error: str | None
```

### Nodes
Python functions or classes that receive the state, do work, and return updated state. Every node has a defined input and output.

```python
# Every node follows the same ABC contract
class PipelineNode(ABC):
    @abstractmethod
    async def process(self, state: PipelineState) -> PipelineState:
        ...
```

### Edges
Define how nodes connect. Can be:
- **Unconditional:** always go from A to B
- **Conditional:** choose B or C based on state (e.g. route differently if intent = "question" vs "requirement")

### Compilation
The graph is compiled once at process startup — it becomes a callable that accepts state and returns state. Compilation validates the graph topology and type contracts.

```python
# Compiled once at startup — process-level singleton
pipeline = StateGraph(PipelineState)
pipeline.add_node("classify", IntentClassifier())
pipeline.add_node("extract", EntityExtractor())
pipeline.add_node("retrieve", RAGRetrieval())
pipeline.add_node("analyze", GapAnalyzer())
pipeline.add_node("generate", GuidanceGenerator())
pipeline.add_edge("classify", "extract")
pipeline.add_edge("extract", "retrieve")
pipeline.add_edge("retrieve", "analyze")
pipeline.add_edge("analyze", "generate")
compiled_pipeline = pipeline.compile()
```

---

## 3. Chitragupt's 5-Node Pipeline

```
IntentClassifier → EntityExtractor → RAGRetrieval → GapAnalyzer → GuidanceGenerator
```

| Node | Model Tier | Time Budget | What It Does |
|---|---|---|---|
| IntentClassifier | Fast (Haiku) | 300ms | Classifies the turn: requirement / question / approval / upload / off-topic |
| EntityExtractor | Standard (Sonnet) | 800ms | Extracts structured entities using tool use |
| RAGRetrieval | (no LLM) | 200ms | Vector search + hybrid retrieval, injects top-20 chunks into state |
| GapAnalyzer | Standard (Sonnet) | 600ms | Identifies missing required fields vs. phase AC criteria |
| GuidanceGenerator | Standard or Premium | 1200ms | Generates the BA's next question/response, streams tokens |

**Total budget per turn:** < 3.1 seconds end-to-end for standard tier.

---

## 4. The LLMFactory

The `LLMFactory` class manages LLM client lifecycle, budget enforcement, and fallback logic.

### Lazy initialization
SDK clients are not created at import time — they are created on first use. This means if Anthropic's SDK is temporarily unavailable at startup, the service still starts.

### Model selection logic
```
request arrives
  → check current_budget_stage
  → if NORMAL: use assigned tier model
  → if CAUTION: downgrade premium → standard
  → if CRITICAL: downgrade standard → fast; apply quality floor if BRD
  → if EXHAUSTED: raise BudgetExhaustedException
```

### Provider circuit breaker
```
call Anthropic API
  → success: reset failure counter for provider
  → failure: increment failure counter
    → if counter >= 3: mark provider DEGRADED for 60 seconds
      → route to fallback (gemini-2.0-flash) for next 60s
      → after 60s: allow one test call; if success, restore provider
```

---

## 5. Streaming with asyncio.Queue

**The pattern:** Background task runs the LLM call and pushes tokens onto a queue. The main coroutine reads from the queue and yields tokens to the caller. `None` signals end of stream.

```python
# Simplified PipelineExecutor pattern
async def execute(self, state: PipelineState) -> AsyncGenerator[str, None]:
    queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=256)

    async def run_graph():
        async for chunk in self._graph.astream(state):
            token = extract_token(chunk)
            if token:
                await queue.put(token)
        await queue.put(None)  # sentinel — stream is done

    asyncio.create_task(run_graph())  # run in background

    while True:
        token = await queue.get()
        if token is None:
            break
        yield token
```

**Why Queue(maxsize=256)?** Back-pressure: if the consumer (gRPC stream, WebSocket) is slow, the producer (LLM streaming) blocks rather than filling unbounded memory.

---

## 6. Retry Strategy

Chitragupt uses `tenacity` for automatic retry with exponential backoff on transient LLM failures:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=2.0)
)
async def call_llm(self, prompt: str) -> str:
    ...
```

**Retry schedule:** 0.5s → 1.0s → 2.0s. After 3 failures, increment the circuit breaker counter.

---

## 7. Prompt Caching Strategy

LangGraph nodes that use large, stable system prompts mark them for caching:

- The system prompt (phase definition, AC criteria, entity schema) is marked `cache_control: ephemeral`
- The user's actual message is NOT cached — it changes every turn
- Shared context injected across multiple nodes (ONTOLOGY, session history) is cached separately

---

## 8. Resources

### Official Documentation

| Resource | URL | What to read |
|---|---|---|
| LangGraph overview | [docs.langchain.com/langgraph](https://docs.langchain.com/langgraph) | What LangGraph is, when to use it, core concepts |
| LangGraph Python API | [langchain-ai.github.io/langgraph/reference/](https://langchain-ai.github.io/langgraph/reference/) | StateGraph, nodes, edges, compilation |
| FastAPI docs | [fastapi.tiangolo.com](https://fastapi.tiangolo.com) | Building Python REST services with type safety |
| Python asyncio | [docs.python.org/3/library/asyncio.html](https://docs.python.org/3/library/asyncio.html) | Tasks, queues, async generators — the primitives under the hood |
| Pydantic v2 docs | [pydantic.dev/docs/validation/latest/get-started/](https://pydantic.dev/docs/validation/latest/get-started/) | Data validation, TypedDict, model schemas |
| tenacity (retry) | [tenacity.readthedocs.io/en/latest/](https://tenacity.readthedocs.io/en/latest/) | Retry decorators, exponential backoff |
| uv package manager | [docs.astral.sh/uv/](https://docs.astral.sh/uv/) | Fast Python deps — replaces pip/poetry in Chitragupt |

### Deep Dives

| Resource | What you will learn |
|---|---|
| [LangGraph conceptual guide — agents](https://langchain-ai.github.io/langgraph/concepts/) | How LangGraph handles checkpointing, persistence, multi-agent patterns |
| [Python async patterns (Real Python)](https://realpython.com/async-io-python/) | Practical async/await — asyncio.Queue, Tasks, Generators |
| [Streaming LLM responses — Anthropic cookbook](https://github.com/anthropics/anthropic-cookbook) | How to implement streaming correctly with back-pressure |

### When to Choose LangGraph vs Alternatives

| Framework | Best for | Not for |
|---|---|---|
| **LangGraph** | Stateful multi-step pipelines, BA conversation flow | Simple single-call pipelines |
| **LangChain** | Chains and agents without complex state | When state management is critical |
| **DSPy** | Optimising prompts automatically | Real-time conversational flows |
| **Raw API calls** | Simple single-step operations | Multi-step workflows |

**Chitragupt's choice:** LangGraph — the 5-node pipeline has complex state (conversation history, retrieved docs, extracted entities) that must flow correctly between steps. Decision in `docs/sprints/sprint0/DECISIONS.md` D-008.

---

> Chitragupt Learning Hub · 02 AI Orchestration · v0.1 · May 2026
