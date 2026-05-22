# CLAUDE.md — Chitragupt Project Instructions

## Prompt Registry

**Every user prompt in this project must be logged to `docs/logs/prompt_trail.md`.**

Before responding to any user request, append a new entry to the prompt trail using the established format:

```
**P-NNN**
> [exact user prompt verbatim]
```

Where NNN is the next sequential number after the last logged entry. Do not paraphrase or clean up the prompt — log it exactly as the user typed it. If a prompt was clearly inferred from context (no verbatim text), mark it `[INFERRED]` and summarize it in one sentence.

Add new entries under the appropriate phase section heading. If a prompt doesn't fit an existing phase, create a new `## Phase Name` heading.

This rule applies to all sessions in this project, without exception.

---

## Project Overview

**Chitragupt** is an agentic Business Requirement Analyzer. It ingests multi-modal documents and stakeholder conversations, extracts structured requirements, and produces client-ready BRDs and High-Level Architecture Diagrams.

**Primary user:** Business Analysts (BAs) who are guided through a structured HITL conversation flow — not document editors.

---

## Key Documents

| Document | Purpose |
|---|---|
| `docs/sprints/sprint0/BA_HITL_FLOW.md` | BA onboarding protocol (7-phase HITL state machine) |
| `docs/sprints/sprint0/DECISIONS.md` | All architectural decisions — all DECIDED or DEFERRED (Sprint 0 CLOSED) |
| `docs/sprints/sprint0/ARCHITECTURE.md` | Trust hierarchy, confidence scoring, conflict protocol, invariants, engineering conventions |
| `docs/sprints/sprint0/TECH_STACK.md` | Authoritative tech stack — Rust/Python/Go, libraries, model versions, gRPC contracts |
| `docs/sprints/sprint0/ONTOLOGY.md` | Complete data model and entity schemas |
| `docs/sprints/sprint0/DATABASE.md` | Database strategy — PostgreSQL + pgvector + Redis + R2, schemas, RLS, hybrid search |
| `docs/sprints/sprint1/README.md` | Sprint 1 priorities, epics, AC definitions |
| `docs/logs/prompt_trail.md` | Prompt registry (append-only) |
| `docs/tech-docs/state-machine.md` | Deep-dive technical reference for the Rust state machine kernel |

---

## Engineering Conventions (Summary)

- Python 3.11+, `black` formatter, `isort`, `mypy --strict`
- Commit format: `<type>(<scope>): <description>` (Conventional Commits)
- Branch naming: `feat/sprint-N-name`, `fix/id-name`, `chore/name`
- Every LLM call must use pinned model versions — no floating aliases
- RLS enforced on every database table with tenant-specific data
- No code unless a Sprint 0 decision is DECIDED for the relevant technology

---

## What NOT to do

- Do not create new documentation files unless the user explicitly asks for one.
- All decisions in `docs/sprints/sprint0/DECISIONS.md` are now DECIDED or DEFERRED — Sprint 0 is closed. Code may proceed for any component whose decision is DECIDED.
- Do not introduce new ADR files — use `docs/sprints/sprint0/DECISIONS.md` as the single decisions document.
- Do not introduce new ADR files — use `docs/sprints/sprint0/DECISIONS.md` as the single decisions document.
