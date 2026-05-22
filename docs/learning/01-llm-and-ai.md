# 01 — LLMs, Embeddings, RAG, and AI Fundamentals

**Why this matters for Chitragupt:** Every intelligent behaviour in the system — question generation, entity extraction, gap detection, BRD synthesis — is powered by an LLM. Understanding how these models work, what they cost, and how to control their behaviour is foundational to every architectural decision in Sprint 0.

---

## 1. What Is a Large Language Model?

An LLM is a neural network trained on enormous amounts of text. It learns statistical patterns about language — which words follow which, what concepts relate to others — and can generate coherent text, answer questions, summarise documents, and reason through problems.

**Key insight for BAs:** An LLM is not a database. It does not "look up" answers — it *predicts* what text should come next given the input. This means it can be confidently wrong. RAG (see below) is the primary technique for grounding LLM responses in actual facts.

### How an LLM processes your input

1. Your text is split into **tokens** (roughly 0.75 words each)
2. Tokens are converted to **embeddings** (numbers representing meaning)
3. The model processes all tokens together in its **context window** (max input size)
4. It generates output tokens one at a time via **inference**
5. Each output token is sampled from a probability distribution (**temperature** controls randomness)

---

## 2. Tokens and Context Windows

| Model | Context Window | Max Output | Cost (input/output per MTok) |
|---|---|---|---|
| claude-opus-4-7 | 1M tokens | 128k tokens | $5 / $25 |
| claude-sonnet-4-6 | 1M tokens | 64k tokens | $3 / $15 |
| claude-haiku-4-5-20251001 | 200k tokens | 64k tokens | $1 / $5 |
| gemini-2.0-flash (fallback) | 1M tokens | — | varies |

**Rule of thumb:** 1,000 tokens ≈ 750 words ≈ 1.5 pages of text.

**Why context window size matters:** Chitragupt can inject entire documents, conversation histories, and retrieved chunks into a single LLM call. The 1M token window means a very long BA session with many uploaded documents can still fit in one call — eliminating the need for complex chunking strategies on the input side.

---

## 3. Model Tiers — Chitragupt's Three-Tier Strategy

Chitragupt assigns every AI function to a tier based on its complexity and latency requirements:

| Tier | Model | Use Cases | Latency Target |
|---|---|---|---|
| **Fast** | claude-haiku-4-5-20251001 | Intent classification, routing decisions | < 500ms |
| **Standard** | claude-sonnet-4-6 | Entity extraction, gap analysis, question generation | < 2s |
| **Premium** | claude-opus-4-7 | Final BRD synthesis, complex reasoning | < 10s |
| **Embedding** | voyage-large-2 | Document and query embedding | < 1s |
| **Fallback** | gemini-2.0-flash | When Anthropic circuit breaks | same as tier |

### Budget degradation thresholds

```
$0.00 → $3.00  : NORMAL    — all tiers available
$3.00 → $4.50  : CAUTION   — premium → standard downgrade
$4.50 → $5.00  : CRITICAL  — standard → fast downgrade
$5.00+         : EXHAUSTED  — session halted
```

**Quality floor:** BRD generation always uses at minimum `standard` — it cannot be downgraded to `fast` regardless of budget state.

---

## 4. Embeddings

An embedding is a numerical representation of text — a list of floating-point numbers (a vector) that captures semantic meaning. Two pieces of text with similar meaning have similar vectors.

```
"requirements gathering"  → [0.23, -0.87, 0.41, ...]  (1536 numbers)
"collecting requirements"  → [0.24, -0.85, 0.39, ...]  (very similar)
"database migration"       → [0.91,  0.12, -0.63, ...] (very different)
```

Chitragupt uses **Voyage AI's `voyage-large-2`** model to embed:
- Uploaded documents (chunked into paragraphs)
- The BA's questions/statements
- Requirements extracted during conversation

All embeddings are 1536 dimensions and stored in PostgreSQL via pgvector.

### Why Voyage AI, not OpenAI embeddings?
Voyage `voyage-large-2` consistently outperforms OpenAI `text-embedding-3-large` on retrieval benchmarks, particularly for domain-specific technical content. Decision recorded in `docs/sprints/sprint0/DECISIONS.md`.

---

## 5. RAG — Retrieval-Augmented Generation

**Problem:** LLMs are trained on general text, not on your specific client's documents. If you ask "What are the compliance requirements for this client?" the LLM will guess — it cannot know.

**Solution — RAG:**
1. When a BA asks a question, embed the question into a vector
2. Search the vector database for the most similar document chunks
3. Inject those chunks into the LLM's context as grounding material
4. The LLM generates its answer based on the actual client documents

```
User question → embed → vector search → top-20 relevant chunks
                                              ↓
                              LLM (with chunks in context) → answer
```

### Chitragupt's RAG parameters
- **Retrieval:** Top-50 candidates via hybrid search (70% cosine + 30% BM25)
- **Re-ranking:** Top-50 → top-20 using a re-ranker model
- **Chunk size:** ~512 tokens per chunk with 64-token overlap
- **Injected into:** `RAGRetrieval` node, which passes chunks to `GapAnalyzer` and `GuidanceGenerator`

---

## 6. Prompt Caching

**Problem:** Chitragupt's system prompts are long (phase definitions, entity schemas, AC templates). Sending them on every turn is expensive.

**Solution:** Anthropic's prompt caching stores the processed representation of a prompt prefix in their API for 5 minutes. Repeated calls with the same prefix are ~90% cheaper.

```python
# Chitragupt pattern: mark the stable system prompt for caching
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "... long system prompt ...",
      "cache_control": {"type": "ephemeral"}
    },
    {
      "type": "text",
      "text": "User's actual question"  # not cached — changes every turn
    }
  ]
}
```

**Target:** ≥80% cache hit rate per session. This reduces cost by 30-40% for a typical BA session.

---

## 7. Streaming

LLMs generate output one token at a time. By default, APIs wait until the full response is ready before sending it. Streaming sends each token as it is generated, giving users the feel of watching the AI "type" in real time.

**Why it matters:** BA sessions are conversational. A 3-second blank screen is jarring; a stream of tokens appearing within 200ms feels natural.

**Chitragupt's streaming chain:**
```
Anthropic API → streamed tokens
              → Python asyncio.Queue (buffer, maxsize=256)
              → PipelineExecutor async generator
              → gRPC stream to Go gateway
              → WebSocket stream to browser
```

---

## 8. Function Calling / Tool Use

Instead of just generating text, LLMs can be asked to call functions with structured arguments. This allows controlled extraction of structured data.

```python
# LLM is given a tool definition:
extract_requirement = {
  "name": "extract_requirement",
  "description": "Extract a structured requirement from conversation",
  "input_schema": {
    "type": "object",
    "properties": {
      "id": {"type": "string"},
      "description": {"type": "string"},
      "priority": {"enum": ["must-have", "should-have", "could-have"]},
      "source": {"type": "string"}
    }
  }
}

# LLM returns a structured call, not free text
# Result: {"id": "FR-001", "description": "...", "priority": "must-have", ...}
```

Chitragupt's `EntityExtractor` node uses tool use to extract requirements with guaranteed JSON structure.

---

## 9. Resources

### Official Documentation

| Resource | URL | What to read |
|---|---|---|
| Anthropic models overview | [platform.claude.com/docs/en/docs/about-claude/models/overview](https://platform.claude.com/docs/en/docs/about-claude/models/overview) | All current model IDs, context windows, pricing |
| Anthropic prompt engineering | [platform.claude.com/docs/en/build-with-claude/prompt-engineering](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering) | Best practices for writing effective prompts |
| Anthropic tool use guide | [platform.claude.com/docs/en/build-with-claude/tool-use/overview](https://platform.claude.com/docs/en/build-with-claude/tool-use/overview) | How function calling works with Claude |
| Anthropic prompt caching | [platform.claude.com/docs/en/build-with-claude/prompt-caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) | Cache control syntax and TTL rules |
| Voyage AI embeddings | [docs.voyageai.com/docs/embeddings](https://docs.voyageai.com/docs/embeddings) | voyage-large-2 specs, API usage, dimensions |

### Deep Dives

| Resource | What you will learn |
|---|---|
| [Attention Is All You Need (original transformer paper)](https://arxiv.org/abs/1706.03762) | How LLMs work at the architecture level |
| [RAG Survey — arXiv 2312.10997](https://arxiv.org/abs/2312.10997) | Comprehensive survey of RAG techniques and trade-offs |
| [Anthropic's Claude character and safety research](https://www.anthropic.com/research) | Why Claude behaves differently from other models |
| [Voyage AI blog: embedding benchmarks](https://blog.voyageai.com) | Why voyage-large-2 was chosen |

---

> Chitragupt Learning Hub · 01 LLM and AI · v0.1 · May 2026
