# Learning Hub — Chitragupt Technical Reference

**Version:** v0.1
**Purpose:** A living reference library for BAs and engineers working on Chitragupt or any agentic product. Covers terminology, deep concepts, and curated resources.
**Maintained:** Add resources, fix broken links, expand glossary entries as the project evolves.

> All links in this directory were verified live as of May 2026. If a link is broken, update it rather than removing the entry.

---

## How This Is Organized

| File | What It Covers |
|---|---|
| [glossary.md](glossary.md) | A–Z definitions of every technical term used in this project |
| [01-llm-and-ai.md](01-llm-and-ai.md) | LLMs, tokens, embeddings, RAG, prompt caching, model selection |
| [02-ai-orchestration.md](02-ai-orchestration.md) | LangGraph, pipeline patterns, async streaming, state graphs |
| [03-data-and-storage.md](03-data-and-storage.md) | PostgreSQL, pgvector, Redis, vector search, RLS, hybrid search |
| [04-systems-and-apis.md](04-systems-and-apis.md) | Rust, gRPC, protobuf, Go API gateway, tokio, tonic |
| [05-devops-and-ci.md](05-devops-and-ci.md) | Docker, GitHub Actions, multi-stage builds, CI/CD for polyglot |

---

## How to Use This Hub

**If you are new to a concept:** Start with [glossary.md](glossary.md). Find the term, read the definition, then follow the cross-reference to the relevant topic file for deeper context.

**If you are making a technology decision:** Go to the relevant topic file. Each file has a "Why this matters for Chitragupt" section that anchors the concept to actual decisions made in this project.

**If you are onboarding a new team member:** Walk through the topic files in order. They build on each other — AI concepts before orchestration, storage before systems.

**If you hit a broken link:** Check the official home page of the project (e.g. docs.langchain.com for LangGraph) and update the URL here.

---

## What This Is Not

This is not a tutorial that walks you through building something from scratch. For that, follow the official "Getting Started" guides linked within each topic file. This hub is a *reference* — it gives you the vocabulary and the pointers you need to go deep on any concept that comes up during a sprint.

---

## Contributing

- Add a term to [glossary.md](glossary.md) if you encounter an unfamiliar word in the codebase or sprint docs.
- Add a resource link to a topic file if you find a genuinely useful article, video, or paper.
- Mark a resource `[OUTDATED]` rather than deleting it — someone may still find it useful for historical context.

---

> Chitragupt Learning Hub · v0.1 · May 2026
