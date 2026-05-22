# Sprint 1 — The Conversation Engine

**Sprint 0 gave us the blueprint. Sprint 1 builds the engine that runs it.**

This sprint delivers the core of what makes Chitragupt useful: a system that can hold an intelligent, structured conversation with a BA, understand what they are saying, know what is still missing, and ask exactly the right question next.

By the end of Sprint 1, a BA should be able to sit down with a fresh session, describe a client problem in their own words, upload relevant documents at the right moments, and arrive at a confirmed, traceable requirements list — guided at every step by the system.

---

## What the System Does

Chitragupt does not ask the BA to fill in a form. It holds a conversation. But unlike an open-ended chat tool, it knows where the session is, what has already been captured, what is still missing, and what needs to be asked next.

Every time the BA sends a message, the system does five things in sequence — invisibly and immediately:

1. **Understands what the BA just said.** Not just the words, but the intent — is this new information, a confirmation, a correction, a request to revisit something, or a question directed at the system?
2. **Extracts what was captured.** If the BA described a stakeholder, the system adds that stakeholder to the session. If they named a constraint, the constraint is recorded. Nothing is lost.
3. **Searches for context.** If documents have been uploaded, the system searches them for anything relevant to what was just said. An org chart uploaded earlier might now be relevant to a new actor the BA just named.
4. **Identifies what is still missing.** The system knows what must be established before this phase can close. It identifies the most important gap remaining and determines the best question to ask.
5. **Responds with one clear action.** Acknowledge what was said. Show what was captured. Ask exactly one question, or offer to move to the next phase. Never both. Never more than one.

The BA should never have to wonder what to do next. If they ever do, that is a failure of the system, not the BA.

---

## The BA Journey in Sprint 1

Sprint 1 covers the first four phases of the seven-phase journey defined in Sprint 0. Each phase has a defined purpose, defined checkpoints, and a defined exit condition.

---

### Phase 1 — Problem Intake

**Purpose:** Establish what the client is actually trying to solve, in the BA's own words.

The session opens here. The system asks the BA to describe the client's problem in plain language — no template, no structure imposed. As the BA explains, the system extracts the core problem statement, identifies the business domain, and begins building a picture of who is affected.

Before this phase closes, the system must have a clear answer to four questions:

- What is the problem the client needs solved?
- What kind of business is this? (financial services, healthcare, logistics, etc.)
- Who are the people most affected by this problem?
- What does success look like for the client?

When those four questions have been answered to the system's satisfaction, it presents a summary back to the BA and asks: *"Does this capture the situation correctly?"* The BA confirms. Only then is the transition offered.

**Document checkpoint:** If the BA mentions that the client has provided a brief, a scope statement, or any prior discovery document, the system asks for it before moving on. That document becomes the primary evidence for the problem statement and elevates the reliability of everything extracted from it.

---

### Phase 2 — Stakeholder Discovery

**Purpose:** Map who has authority, who is affected, and what external systems or third parties are in play.

The system now asks the BA to walk through the people and organisations involved in this project. For each person, it captures their name, their role, and their decision-making authority. It also asks about external systems — partner platforms, APIs, legacy infrastructure — because these typically become integration requirements later.

Before this phase closes, the system must know:

- At least two actors have been identified.
- At least one actor has been confirmed as the decision-maker.
- Every actor has a name and a role.
- The BA has been asked about external systems — even if the answer is "there are none."

**Document checkpoint (Checkpoint A):** The system asks whether an org chart, RACI matrix, stakeholder map, or responsibility document exists. If one is provided, the system reads it to verify and supplement what the BA described. Actors identified only in conversation, with no supporting document, are flagged in the final BRD so the client can verify them.

---

### Phase 3 — Requirement Elicitation

**Purpose:** Draw out the specific functional needs and non-functional expectations the system must meet.

This is typically the longest phase. The BA works through each stakeholder group and describes what they need the system to do. The system captures these as draft requirements — both functional (what the system must do) and non-functional (how fast, how secure, how available).

For every requirement, the system tracks where it came from: a direct statement by the BA, or a passage in an uploaded document. This provenance is non-negotiable — it is what makes the final BRD auditable.

Before this phase closes:

- At least five requirements have been captured.
- At least one functional requirement and one non-functional requirement are present.
- Every stakeholder identified in Phase 2 is referenced by at least one requirement.
- Every requirement has a source — either a document passage or a direct statement from the BA.
- No more than two open questions remain unresolved.

**Document checkpoint (Checkpoint B):** The system asks for wireframes, process diagrams, meeting notes, workshop outputs, or any feature lists the client provided. Where a requirement references a workflow, UI, or system integration, the system specifically prompts for a diagram or mockup. If none is provided, that requirement is noted as conversation-only in the BRD.

---

### Phase 4 — Constraint Capture

**Purpose:** Pin down the real-world limits the solution must operate within.

Requirements describe what the system should do. Constraints describe what it cannot do, or what it must do regardless of cost. Timeline, budget, regulatory requirements, data residency rules, and security standards all belong here.

The system asks about each constraint type explicitly. It does not assume the BA will think to volunteer this information unprompted.

Before this phase closes:

- At least one constraint has been captured.
- The timeline has been addressed — either a date or an explicit "no fixed deadline."
- The budget range has been addressed — even approximately.
- The BA has been asked about regulatory or compliance requirements and has responded.
- The BA has been asked about data residency or data handling rules.

**Document checkpoint (Checkpoint C):** The system asks for compliance policies, security requirements documents, data classification policies, vendor contracts, or infrastructure specifications. For sessions in regulated industries — financial services, healthcare, government — at least one supporting document must be uploaded or the BA must explicitly confirm they are working from memory. This is not optional in regulated domains; it is surfaced as a required step before the phase closes.

---

## How the System Handles Edge Cases

**The BA wants to go back.** If the BA says "actually I need to change the stakeholders" or "can we revisit the problem statement," the system re-enters that phase, shows the BA what was captured there, and resumes from the last unanswered question. Nothing already captured is lost.

**The BA wants to skip something.** If the BA does not know the answer to something — "I'll need to check with the client on the timeline" — the system records it as an open question and moves on. Open questions are surfaced in the final BRD so nothing falls through the cracks.

**The BA wants to move on before everything is answered.** The system surfaces specifically what is still missing: *"We do not yet have a decision-maker identified and we have not been asked about external systems. Do you want to continue anyway?"* The BA can choose to proceed — their choice is recorded — but the system does not silently let gaps pass unacknowledged.

**A document is uploaded mid-conversation.** The system processes it in the background, indexes it, and immediately re-evaluates what it now knows. A document uploaded in Phase 3 might resolve a question from Phase 2. The BA is notified.

---

## What Sprint 1 Does Not Cover

Architecture Alignment, Review and Sign-Off, and the generation of the BRD and High-Level Architecture Diagram are Sprint 2 work. These phases depend on everything established in Phases 1–4, so they are a natural second sprint.

Sprint 1 also does not include:
- Voice and audio input (a later sprint once the text pipeline is proven)
- Multi-user or collaborative sessions
- Downstream connector push to Jira, Confluence, or similar tools
- Client-facing UI — the API is built first; the interface comes after

---

## Engineering Companion Documents

The following documents contain the technical design decisions that implement the BA experience described above. They are not BA-facing content — they are reference material for the engineering team building Sprint 1.

| Document | What it covers |
|---|---|
| [LLM_UNIVERSE.md](LLM_UNIVERSE.md) | Which AI models are used for which tasks, why, and at what cost — with fallback and budget rules |
| [LLM_DESIGN_PATTERNS.md](LLM_DESIGN_PATTERNS.md) | How AI capabilities are loaded and injected into the session at runtime — the factory and lazy-loading architecture |

The Rust state machine kernel built in Sprint 1 is documented at [docs/tech-docs/state-machine.md](../../tech-docs/state-machine.md).

---

## Sprint 1 Exit Criteria

Sprint 1 closes when:

- A new BA session can move from Problem Intake all the way to a confirmed requirements list through conversation alone — no manual state manipulation required.
- The system surfaces exactly one next question or transition offer at the end of every turn, without exception.
- A document uploaded at Checkpoint B is indexed and retrievable within the same session, and requirements sourced from it carry traceable provenance.
- A session in a regulated domain (financial services, healthcare, government) cannot close Phase 3 without at least one uploaded document or an explicit BA waiver.
- The system correctly handles REVISIT requests — re-entering a prior phase without losing any captured data.

---

> Chitragupt · Sprint 1 · The Conversation Engine · May 2026
