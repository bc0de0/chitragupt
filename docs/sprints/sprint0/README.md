# Sprint 0 — Discovery & Foundation

**What this sprint is about:** Before a single line of code is written, the team must understand the problem deeply enough to build the right thing. Sprint 0 is entirely devoted to that understanding. It produces knowledge, not software.

---

## The Problem We Are Solving

Business Analysts spend a disproportionate amount of their time on logistics — chasing stakeholders for answers, reformatting notes from workshops, reconciling conflicting versions of requirements, and assembling BRD drafts from scattered documents and memory. The actual thinking — understanding the client's intent, surfacing hidden assumptions, spotting contradictions early — gets compressed or skipped entirely under deadline pressure.

Chitragupt's purpose is to give that time back. It acts as a structured conversation partner that walks the BA through every phase of discovery in the right order, at the right depth, and does not allow the session to move forward until the right questions have been answered.

Before we could build that system, we had to answer a prior question: what *is* the right order, the right depth, and the right set of questions? That is what Sprint 0 established.

---

## What Sprint 0 Discovered

### The seven-phase BA journey

Discovery work confirmed that a structured requirements engagement always passes through seven identifiable phases, in sequence. Each phase has a clear purpose, a clear set of things that must be known before moving on, and a clear hand-off to the next phase.

| Phase | What the BA is doing |
|---|---|
| Problem Intake | Establishing what the client is actually trying to solve — not what they think they want built |
| Stakeholder Discovery | Identifying who has authority, who is affected, and what external systems are in play |
| Requirement Elicitation | Drawing out functional needs and non-functional constraints from people and documents |
| Constraint Capture | Pinning down the real-world limits — budget, timeline, compliance, data handling |
| Architecture Alignment | Connecting business decisions to the technology directions they imply |
| Review and Sign-Off | Walking the client through the full picture and getting a formal, recorded approval |
| Signed Off | Session complete; deliverables locked; BRD and HLD in the client's hands |

These phases are not optional and they are not reorderable. A BA cannot meaningfully elicit requirements before knowing who the stakeholders are. The system enforces this sequence.

### Documents are evidence, not decoration

A key insight from discovery: uploaded documents should not be treated as attachments to a conversation. They are the most reliable evidence available about client intent, stakeholder authority, and system constraints. When a BA uploads an org chart, that org chart should resolve ambiguity in who the decision-maker is. When a compliance policy is uploaded, that policy should shape which constraints the system probes for.

This meant the system needed a concept of *document checkpoints* — defined moments in the conversation where the BA is expected to provide supporting material, and where the system actively uses that material to inform its questions.

### Transitions must be confirmed, not assumed

The system must never silently advance from one phase to the next. Two things must happen: the system presents a summary of what was captured in the current phase, and the BA explicitly confirms that summary before the transition is offered. If the BA does not confirm — or if essential information is still missing — the system stays in the current phase and continues probing.

This is not a UX preference. It is the mechanism that prevents an incomplete discovery from being mistaken for a complete one.

### Sign-off is a formal event, not a chat message

The final transition — from Review to Signed Off — requires a recorded client approval, not just a "looks good" in chat. Sprint 0 established that this means a sign-off token is generated, dispatched, and must be returned with status *signed* before the session closes. There is no workaround for this gate.

---

## Decisions Made in Sprint 0

Sprint 0 produced a set of architectural decisions that govern everything built in Sprint 1 and beyond. The full register is in [DECISIONS.md](DECISIONS.md). The decisions that have the most direct impact on the BA experience are:

- **The system leads the conversation.** The BA answers; the system asks. The system never presents a blank prompt or an open-ended "what else?"
- **One question per turn.** Every system response ends with exactly one clear action for the BA — a question, a confirmation request, or a transition offer. Never a list of questions. Never silence.
- **Gaps are surfaced, not swallowed.** If the system detects that something essential is missing — an actor without a named authority, a requirement with no identified source — it asks about it explicitly before moving on.
- **Trust levels are tracked.** Information extracted from uploaded documents is treated as more reliable than information stated only in chat. The system tracks this distinction and surfaces it in the final BRD.

---

## What Sprint 0 Produced

| Document | What it contains |
|---|---|
| [BA_HITL_FLOW.md](BA_HITL_FLOW.md) | The definitive description of the seven-phase conversation — what happens in each phase, what checkpoints exist, and how the BA is guided through each transition |
| [ARCHITECTURE.md](ARCHITECTURE.md) | The trust model, data confidence tiers, and engineering invariants that underpin every system decision |
| [DECISIONS.md](DECISIONS.md) | Every architectural decision made during discovery, with status (decided or still open), the question being answered, and the rationale |

The data model — the full schema of every entity the system captures — is maintained separately at [docs/architecture/ontology.md](../../architecture/ontology.md), because it evolves as implementation proceeds and should not be locked inside a sprint document.

---

## How Sprint 0 Connects to Sprint 1

Sprint 0 is the specification. Sprint 1 is the first implementation of it.

Everything built in Sprint 1 — the conversation engine, the phase transitions, the document checkpoints, the guidance logic — is a direct translation of the decisions made here. Where Sprint 0 says "the system must confirm with the BA before transitioning," Sprint 1 builds the confirmation flow. Where Sprint 0 says "documents at Checkpoint A should inform stakeholder extraction," Sprint 1 builds the ingestion and retrieval pipeline that makes that possible.

Sprint 1 covers the first four phases: Problem Intake through Constraint Capture. Architecture Alignment, Review, and Sign-Off are Sprint 2.

---

## Sprint 0 Exit Criteria

Sprint 0 is complete when the following are true:

- All decisions in DECISIONS.md have reached a guided or decided state — no open questions that block Sprint 1 work
- BA_HITL_FLOW.md has been reviewed and confirmed by the BA team lead
- ARCHITECTURE.md has been ratified by the engineering lead
- The data model in ontology.md has been validated against the outputs defined in BA_HITL_FLOW.md

Sprint 1 begins immediately after all four criteria are met.

---

> Chitragupt · Sprint 0 · Discovery & Foundation · May 2026
