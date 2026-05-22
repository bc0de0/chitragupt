# Playbooks — Agentic Product Build System

**Version:** v0.1 · Living document · May 2026
**Purpose:** Take any agentic product from a raw idea to production — with every decision, template, and diagram a BA needs to reason through the build without needing an engineer in the room.

---

## What These Playbooks Are

These are not methodology summaries. They are decision engines.

Every playbook answers a specific question a BA or product team faces during a build. Each one gives you: a decision framework, a fill-in template, one or two diagrams you can actually understand, and a cheat sheet you can use in a client meeting.

They were written by reverse-engineering the Chitragupt build — an agentic Business Requirement Analyzer built from zero to production using exactly the approach described here. Every decision in these playbooks was made for real, under real constraints. The examples are not hypothetical.

---

## The Eight Playbooks

| # | Playbook | The question it answers | When to use it |
|---|---|---|---|
| [PB-01](PB-01-discovery.md) | Problem Discovery | What are we actually building and why? | Day 1 of any engagement |
| [PB-02](PB-02-architecture.md) | System Architecture | How should the system be structured? | After discovery, before Sprint 0 |
| [PB-03](PB-03-ai-strategy.md) | AI & LLM Strategy | Which AI capabilities do we need and how do we pay for them? | Sprint 0 |
| [PB-04](PB-04-data-strategy.md) | Data Architecture | Where does data live and how is it kept safe? | Sprint 0 |
| [PB-05](PB-05-sprint-design.md) | Sprint Design | How do we sequence the build? | Sprint 0 planning |
| [PB-06](PB-06-state-machine.md) | State Machine & HITL | How do we model the user's journey with hard guarantees? | Sprint 1 design |
| [PB-07](PB-07-delivery.md) | CI/CD & Delivery | How do we ship reliably, every time? | Sprint 1 parallel track |
| [PB-08](PB-08-cheatsheets.md) | Master Cheat Sheet | What is the fastest answer to the question in front of me right now? | Anytime |

---

## How to Use These Playbooks

**If you are starting a new project:** Begin at PB-01 and work forward. Each playbook outputs a document or decision that the next one depends on.

**If you are in the middle of a project:** Find the playbook that matches the decision in front of you. They are designed to be used out of order.

**If you are in a client meeting:** Open PB-08. The master cheat sheet has every key decision tree on a single page.

**If you are debugging a failing architecture:** Read the "What goes wrong without this" section in the relevant playbook. Most common failure modes are catalogued there.

---

## The Underlying Philosophy

These playbooks are built on five principles that the Chitragupt build proved out:

**1. Sprint 0 is not optional.** The most expensive bugs are architectural. Sprint 0 spends time deciding before code is written. Every hour of Sprint 0 saves ten hours of refactoring.

**2. BA language first, engineering language later.** A BA who cannot explain an architectural decision to a client should not be making it. If the reasoning cannot be stated plainly, the decision has not been made — it has been deferred.

**3. Every decision has a rationale and a recorded alternative.** "We chose X" is not a decision. "We chose X because of Y, and we considered Z but ruled it out because of W" is a decision. Playbook templates enforce this format.

**4. The system leads, the BA approves.** In agentic systems, the AI does the synthesis. The BA does the judgment. The playbooks are built around this division.

**5. Gaps are surfaced, not swallowed.** An unknown that is documented and assigned is managed. An unknown that is ignored becomes a production incident.

---

## Version History

| Version | What changed |
|---|---|
| v0.1 | Initial release — all eight playbooks, grounded in Chitragupt build |

---

## The Living Example

Every playbook references **Chitragupt** as the living example. All documents produced during that build are in `docs/sprints/` and `docs/tech-docs/`. Where a playbook says *"Chitragupt decision:"*, you can read the original reasoning in the referenced document.

---

> Chitragupt Playbooks · v0.1 · May 2026
