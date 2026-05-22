# Model Selection & Graceful Degradation — Chitragupt

**Status:** Authoritative for Sprint 1 implementation
**Scope:** All LLM call sites in `services/ai-orchestration`
**Companion documents:**
- `LLM_UNIVERSE.md` — primary model assignments per function
- `LLM_ORCHESTRATION.md` — pipeline topology and retry policy
- `LLM_DESIGN_PATTERNS.md` — `SessionLLMContext`, `BudgetTracker`, `LLMFactory`

---

## Why This Document Exists

`LLM_UNIVERSE.md` defines which model handles which function. `LLM_DESIGN_PATTERNS.md` defines how models are injected at runtime. Neither document answers the operational question: **what actually happens when something goes wrong?**

A provider is rate-limited. A model's response time exceeds the turn budget. The session runs out of money mid-conversation. A fallback itself fails. This document defines the complete response to each of these scenarios — what degrades, to what, under what condition, and what the BA sees.

The guiding constraint is **budget-first degradation**. At MVP scale with a $5 per-session cap and a target of <$2 per average session, every degradation decision must either reduce cost or protect reliability, not both at the expense of the other.

---

## Degradation Trigger Types

There are three distinct triggers for model degradation. They are independent and may combine.

| Trigger | Condition | Response |
|---|---|---|
| **Budget** | Session spend ≥ threshold | Switch to cheaper model tier |
| **Provider error** | Rate limit, 5xx, timeout after retries exhausted | Switch to fallback provider |
| **Latency** | Node wall time ≥ budget for that node | Abandon and return safe default (intent/entity nodes only) |

---

## 1. Budget-Triggered Degradation

### Budget Thresholds

The $5.00 session hard limit is enforced in three stages. Each stage changes what models are available.

| Stage | Spend so far | Effect |
|---|---|---|
| **Normal** | < $3.00 | All models available as defined in `LLM_UNIVERSE.md` |
| **Caution** | $3.00 – $4.50 | Opus calls replaced by Sonnet. BA is notified once via a system message. |
| **Critical** | $4.50 – $5.00 | Sonnet calls replaced by Haiku. All generation is Haiku. BA notified again. |
| **Exhausted** | ≥ $5.00 | All LLM calls blocked. Pipeline returns a static "session budget reached" message. |

The `BudgetTracker` in `SessionLLMContext` exposes these stages:

```python
from enum import Enum

class BudgetStage(Enum):
    NORMAL   = "normal"
    CAUTION  = "caution"
    CRITICAL = "critical"
    EXHAUSTED = "exhausted"

class BudgetTracker:
    def stage(self) -> BudgetStage:
        if self._spent_usd >= self._limit_usd:
            return BudgetStage.EXHAUSTED
        if self._spent_usd >= 4.50:
            return BudgetStage.CRITICAL
        if self._spent_usd >= 3.00:
            return BudgetStage.CAUTION
        return BudgetStage.NORMAL
```

### Budget Degradation Matrix

| Function | Normal | Caution | Critical | Exhausted |
|---|---|---|---|---|
| Intent classification | `haiku-4-5` | `haiku-4-5` | `haiku-4-5` | blocked |
| Entity extraction | `haiku-4-5` | `haiku-4-5` | `haiku-4-5` | blocked |
| RAG synthesis | `haiku-4-5` | `haiku-4-5` | `haiku-4-5` | blocked |
| Gap analysis | `sonnet-4-6` | `sonnet-4-6` | `haiku-4-5` | blocked |
| Guidance generation | `opus-4-7` | `sonnet-4-6` | `haiku-4-5` | blocked |
| Requirement refinement | `sonnet-4-6` | `sonnet-4-6` | `haiku-4-5` | blocked |
| Visual understanding | `sonnet-4-6` | `sonnet-4-6` | `haiku-4-5` | skipped |
| BRD/SRS generation | `opus-4-7` | `sonnet-4-6` | `sonnet-4-6`* | blocked |
| Data transformation | `haiku-4-5` | `haiku-4-5` | `haiku-4-5` | blocked |
| Localization | `haiku-4-5` | `haiku-4-5` | `haiku-4-5` | blocked |
| Embedding | `voyage-large-2` | `voyage-large-2` | `voyage-large-2` | blocked |

*BRD generation is never degraded below Sonnet even at Critical. BRD quality is the primary deliverable — the BA has worked through 4–6 phases to get here. Using Haiku for the final output would undermine the product's value proposition. If the budget is exhausted before BRD generation begins, the BA is informed and offered the option to extend the session or export the accumulated requirements without AI generation.

### BA Notification

When a stage transition occurs, a system message is injected into the BA's response stream before the next guidance token:

- **Caution:** `"Note: this session is approaching its processing budget. The system has switched to a faster response model. Quality for complex tasks may be slightly reduced."`
- **Critical:** `"Note: this session is near its processing limit. The system is now using the most efficient model available. Consider saving your progress and resuming in a new session for complex requirements."`
- **Exhausted:** `"This session has reached its processing budget. No further AI analysis is available. Your captured requirements are saved and can be exported from this session."`

These messages are factual, non-alarming, and actionable. They do not expose model names or cost figures.

---

## 2. Provider-Error-Triggered Degradation

### Fallback Provider Map

Each primary model has exactly one fallback provider. The fallback is always a different vendor — the point of a fallback is to survive provider-level outages, not just rate limits.

| Primary Model | Primary Vendor | Fallback Model | Fallback Vendor |
|---|---|---|---|
| `claude-haiku-4-5-20251001` | Anthropic | `gemini-2.0-flash` | Google |
| `claude-sonnet-4-6` | Anthropic | `gemini-2.0-flash` | Google |
| `claude-opus-4-7` | Anthropic | `claude-sonnet-4-6` | Anthropic* |
| `voyage-large-2` | Voyage AI | `text-embedding-3-small` | OpenAI |
| `whisper-1` | OpenAI | `gemini-2.0-flash` (audio) | Google |

*Opus's fallback is Sonnet, not a different vendor. The rationale: Opus is only used for BRD generation, which is a single call at the end of a session. An Anthropic-wide outage at that moment is low-probability. The quality step-down from Opus to Sonnet is smaller than the step-down from Opus to Gemini for long-form structured document generation. If Anthropic is fully down, the second fallback is Gemini — see Section 2.2.

### Error Classification

Not all errors trigger a fallback. The rule: **retry transient errors, fallback on sustained errors, fail fast on permanent errors.**

| Error Type | Examples | Response |
|---|---|---|
| **Transient** | `RateLimitError`, `APIStatusError` (5xx), network timeout | Retry up to 3 times with exponential backoff (0.5s → 1s → 2s) |
| **Sustained** | All retries exhausted on primary | Switch to fallback provider immediately; no retry on fallback |
| **Permanent** | `AuthenticationError` (401), `BadRequestError` (400), `InvalidRequestError` | Fail immediately; do not retry; do not fallback; write to `audit_log` |

Permanent errors indicate a configuration problem or a malformed prompt — retrying or switching providers will not fix them. They surface as pipeline errors so they can be investigated.

### Fallback Implementation

The fallback decision lives in `LLMFactory`, not in individual nodes. Nodes call `state["llm_ctx"].get(feature)` which returns the right client for the current budget stage and provider health.

```python
class LLMFactory:

    # Per-process provider health state — shared across all sessions
    _provider_degraded: dict[str, float] = {}   # provider → degraded_until (unix timestamp)

    @classmethod
    def _is_degraded(cls, provider: str) -> bool:
        until = cls._provider_degraded.get(provider, 0.0)
        return time.time() < until

    @classmethod
    def mark_degraded(cls, provider: str, duration_seconds: int = 60) -> None:
        """Called by LLMClient wrapper after sustained failures."""
        cls._provider_degraded[provider] = time.time() + duration_seconds
        logger.warning("Provider %s marked degraded for %ds", provider, duration_seconds)

    @classmethod
    def create(cls, feature: LLMFeature, budget_stage: BudgetStage) -> LLMClient:
        # 1. Determine target model given budget stage
        model = cls._model_for_budget(feature, budget_stage)
        provider = cls._provider_for_model(model)

        # 2. If primary provider is degraded, use fallback
        if cls._is_degraded(provider):
            model   = cls._fallback_model(feature)
            provider = cls._provider_for_model(model)
            logger.info("Using fallback model %s for %s (primary degraded)", model, feature)

        return cls._build_client(provider, model)
```

Provider degradation is a **process-level signal** with a 60-second expiry. After 60 seconds, the factory will attempt the primary provider again. This prevents a single intermittent error from permanently routing all traffic to the fallback, while also not retrying on every single call during an ongoing outage.

### Fallback Cost Accounting

When a fallback model is used, the cost is calculated using the fallback model's pricing, not the primary's. The `llm_call_log` records `fallback_used = true` and `model_id` of the actual model called. The `BudgetTracker` increments with the actual cost — the session budget reflects what was actually spent.

---

## 3. Latency-Triggered Degradation

Only the two fast nodes — `IntentClassifier` and `EntityExtractor` — have latency-triggered degradation. These nodes run synchronously before the streaming response begins; their latency is directly visible to the BA as time-to-first-token.

`GapAnalyzer` and `GuidanceGenerator` have softer latency expectations (the BA expects some thinking time before the response). `RAGRetrieval` is database-bound, not LLM-bound.

### Per-Node Timeout Budgets

| Node | Timeout | On timeout |
|---|---|---|
| `IntentClassifier` | 800 ms | Return `"Clarification"` default; mark `node_errors` |
| `EntityExtractor` | 1 500 ms | Return empty entity list; mark `node_errors` |
| `RAGRetrieval` | 1 000 ms | Return empty chunks; mark `node_errors` |
| `GapAnalyzer` | 3 000 ms | Return first unmet AC directly from `SessionState` (no LLM synthesis); mark `node_errors` |
| `GuidanceGenerator` | 20 000 ms | Abort pipeline; return generic "processing error" to BA |

Timeouts are enforced with `asyncio.wait_for`. The `GuidanceGenerator` timeout is generous (20s) because streaming response time is dominated by total tokens generated, not time-to-first-token — a 20-second stream is acceptable for a long BRD section.

```python
async def __call__(self, state: PipelineState) -> PipelineState:
    try:
        result = await asyncio.wait_for(
            self._classify(state),
            timeout=0.8,  # 800ms
        )
        return {**state, "intent": result}
    except asyncio.TimeoutError:
        logger.warning("IntentClassifier timed out after 800ms")
        return {**state, "intent": "Clarification",
                "node_errors": {**state["node_errors"], "IntentClassifierNode": "timeout"}}
```

---

## 4. Embedding Fallback

The embedding fallback (`text-embedding-3-small` from OpenAI) requires special handling because the embedding dimension is the same (1536) but the vector space is different. A query embedded with `text-embedding-3-small` cannot be reliably compared against documents embedded with `voyage-large-2`.

### Sprint 1 Policy: No Mixed-Model Retrieval

If `voyage-large-2` is unavailable during a retrieval call:
- **Ingestion** (background): pause and retry every 30 seconds for up to 10 minutes. Log the failure. Do not switch to `text-embedding-3-small` for new chunk embeddings.
- **Retrieval** (per-turn): skip RAG retrieval entirely for this turn. The pipeline proceeds with an empty `retrieved_chunks` list. The `GapAnalyzer` falls back to using only `SessionState` for gap identification.

The reason for this conservative policy: mixed-model embeddings in the same chunk table would corrupt retrieval quality in ways that are hard to detect and reverse. The right fix for an embedding provider outage is to wait, not to embed with a different model.

The `text-embedding-3-small` fallback is reserved for a future sprint when Chitragupt supports a re-embedding workflow that allows bulk migration of an existing tenant's chunks to a new model.

---

## 5. The Complete Degradation Decision Tree

Every `LLMClient.call()` passes through this sequence before dispatching to the API:

```
1. CHECK budget stage
   ├─ EXHAUSTED → raise BudgetExhaustedError (pipeline handles static response)
   ├─ CRITICAL  → swap model to cheaper tier (see budget matrix)
   ├─ CAUTION   → swap model for Opus-tier calls only
   └─ NORMAL    → use primary model

2. CHECK provider health
   ├─ primary provider degraded → use fallback model
   └─ primary available         → use primary model

3. CALL API with retry policy (tenacity: 3 attempts, exponential backoff)
   ├─ SUCCESS          → record cost; return response
   ├─ TRANSIENT error  → retry (up to 3 attempts)
   ├─ SUSTAINED error  → mark provider degraded (60s); raise to node
   └─ PERMANENT error  → raise to node immediately (no retry)

4. NODE catches exception (PipelineNode.except block)
   ├─ Intent/Entity/RAG/Gap node → write default; continue pipeline
   └─ Guidance node              → set pipeline_aborted = True

5. PIPELINE servicer checks pipeline_aborted
   ├─ True  → send error message to BA; log to audit_log
   └─ False → send guidance tokens; return PipelineComplete to Rust
```

---

## 6. Cost Guardrails Summary

These guardrails are always active. They are not optional and cannot be disabled per session.

| Guardrail | Threshold | Mechanism |
|---|---|---|
| Session hard limit | $5.00 | `BudgetTracker.stage() == EXHAUSTED` → all LLM calls blocked |
| Opus guard | $3.00 | Automatic downgrade to Sonnet; BA notified once |
| BRD quality floor | — | BRD generation never degrades below Sonnet regardless of budget stage |
| Embedding consistency | — | No mixed-model embeddings within a project's chunk table |
| Provider circuit breaker | 3 sustained failures | Primary provider marked degraded for 60 seconds |
| Per-node timeout | See table above | `asyncio.wait_for`; safe defaults returned on timeout |

---

## 7. What Degrades Invisibly vs. What the BA Sees

Not all degradation needs to be surfaced. The BA should know when their experience changes meaningfully; they should not be burdened with operational detail.

| Event | BA sees | Logged internally |
|---|---|---|
| Haiku used instead of Sonnet for gap analysis (Critical stage) | System message (once) | `llm_call_log.model_id`, `llm_call_log.fallback_used` |
| Fallback provider used (Gemini instead of Anthropic) | Nothing | `llm_call_log.fallback_used = true` |
| IntentClassifier timed out; default intent used | Nothing | `node_errors.IntentClassifierNode = "timeout"` |
| EntityExtractor failed; empty entities | Nothing (next turn will re-extract) | `node_errors.EntityExtractorNode` |
| RAG retrieval skipped (embedding provider down) | Nothing | `node_errors.RAGRetrievalNode` |
| Budget exhausted | Static message; no more AI responses | `audit_log` event `session.budget_exhausted` |
| Pipeline aborted (GuidanceGenerator unrecoverable) | "Something went wrong. Please try again." | `audit_log` event `pipeline.aborted` |

The principle: **degrade silently when the BA's next message will give the system a chance to recover; notify when the BA's ability to complete the session is affected.**

---

> Model Selection & Graceful Degradation · Chitragupt · Sprint 1 · May 2026
