# Phase 4 — Delivery Output Prompts

**Purpose:** Generate the final deliverables — BRD, HLD, technical specifications, and Confluence documentation — grounded in everything captured throughout the engagement.
**Tool access needed:** Confluence (read session outputs, save deliverables), Jira/Linear (link requirements to stories).

---

## PH4-01 — Business Requirements Document (BRD) Generation

The BRD is the primary deliverable of the requirements phase. This prompt generates a fully traceable, client-ready BRD from everything captured in the session.

```
I need to generate the Business Requirements Document for [PRODUCT NAME].

Before writing anything, please:
1. Read the following Confluence pages in space [SPACE_KEY]:
   - Problem statement and scope boundary (from Phase 1)
   - Stakeholder map
   - Unknowns and assumptions register
   - BA_HITL_FLOW.md (Sprint 0)
   - ONTOLOGY.md (Sprint 0)
   - Any requirements or notes pages captured during the engagement

2. Read the Jira project [PROJECT_KEY] and extract all user stories that are DONE or IN REVIEW, as these represent confirmed requirements.

Now generate the BRD with the following sections:

---
# Business Requirements Document — [PRODUCT NAME]
Version: 1.0 | Date: [TODAY] | Status: DRAFT | BA: [YOUR NAME]

## 1. Executive Summary
[2-3 paragraph summary of the problem, solution, and expected outcomes]

## 2. Business Context
2.1 Problem Statement
2.2 Business Objectives (linked to success definition from discovery)
2.3 Scope (IN / OUT / DEFERRED)
2.4 Stakeholders (from stakeholder map)

## 3. Functional Requirements
[For each requirement:]
ID: FR-[NNN]
Description: [What the system must do]
Source: [Jira story ID / Confluence page / BA conversation]
Priority: Must Have / Should Have / Could Have
Acceptance Criteria: [GIVEN/WHEN/THEN]
Confidence: [HIGH / MEDIUM / LOW — based on whether there is a document source]

## 4. Non-Functional Requirements
[Performance, security, scalability, compliance — each with source and AC]

## 5. Assumptions and Constraints
[From the unknowns register — still-open items flagged]

## 6. Open Questions
[Requirements that are present but not yet confirmed — tagged INFERRED — VERIFY]

## 7. Traceability Matrix
[Requirement ID → Source → Jira Story ID]
---

Rules for this BRD:
- Every requirement must trace to a source (Jira story, Confluence page, or BA conversation).
- Any requirement with no source must be tagged [INFERRED — VERIFY] and added to Section 6.
- No requirements invented by Claude that were not discussed in the session.
- Conflicting information between sources must be flagged in Section 6, not silently resolved.

Save the completed BRD to Confluence as "[PRODUCT NAME] — BRD v1.0" in space [SPACE_KEY].
```

**What Claude does:** Reads all engagement outputs from both tools, generates a fully traceable BRD, flags all low-confidence items, and publishes to Confluence.

**Expected output:** Published BRD in Confluence with traceability matrix + list of INFERRED items requiring client confirmation.

---

## PH4-02 — High-Level Architecture Diagram (HLD)

Generates the architecture diagram that accompanies the BRD for client sign-off.

```
I need to generate the High-Level Architecture Diagram for [PRODUCT NAME].

Please:
1. Read the TECH_STACK.md and ARCHITECTURE.md (or equivalent pages) in Confluence [SPACE_KEY].
2. Read the data architecture page to understand storage layers.
3. Read the AI strategy page to understand the AI pipeline components.

Generate the following diagrams as Mermaid syntax. Each diagram should be small, focused, and understandable by a non-technical client:

Diagram 1: System Overview
- Show: all services, how they connect, what the user interacts with
- Labels in plain language (not "gRPC" — say "internal call")
- Include: data stores

Diagram 2: User Journey Flow
- Show: the phases of the user experience from start to signed-off
- Show: where uploads happen
- Show: where the AI does work
- Labels: what the USER experiences, not the technical operation

Diagram 3: Data Flow for One Request
- Show: what happens from the moment the user sends a message to when they get a response
- Keep it to 5-7 steps maximum
- Plain labels only

Diagram 4: Security and Tenancy Boundary
- Show: how data is isolated between clients
- Show: where authentication happens
- Simple boxes only

For each diagram: write 2-3 sentences of plain-language explanation above it.

Format as a Confluence page titled "[PRODUCT NAME] — High-Level Architecture" and save it to space [SPACE_KEY].
```

**What Claude does:** Reads the technical design docs and generates four focused, non-technical architecture diagrams with explanations — published to Confluence.

**Expected output:** Four Mermaid diagrams published to Confluence + plain-language explanations for each.

---

## PH4-03 — Sprint Review and Demo Preparation

Use this before every sprint demo to prepare a client-facing summary.

```
Sprint [N] for [PRODUCT NAME] is ending. I need to prepare for the sprint review.

Please:
1. Read the sprint in [Jira / Linear] — list all stories that were completed this sprint (status: Done) and their descriptions.
2. List stories that were in the sprint but NOT completed — and why they were not done (if notes exist in the issues).
3. Read the sprint goals from the sprint description.

Generate:
A. Sprint Review Summary (for the client — non-technical):
   - What we set out to do
   - What we completed (in plain language — no jargon)
   - What we did not complete and why
   - What this means for the next sprint
   - Any decisions the client needs to make before we continue

B. Velocity Report:
   - Points committed vs points delivered
   - Percentage of sprint goal achieved
   - Trend vs previous sprint (if I give you last sprint's velocity: [N] points)

C. Next Sprint Proposal:
   - Based on this sprint's velocity, how many points should we commit to next sprint?
   - Which epics should be in scope?
   - What risks exist for next sprint?

Save the Sprint Review Summary to Confluence as "Sprint [N] Review — [PRODUCT NAME]" in space [SPACE_KEY].
Update the Jira/Linear sprint status to COMPLETED.
```

**What Claude does:** Reads the sprint board state, generates client-facing and technical summaries, calculates velocity, proposes next sprint scope, and publishes the review.

**Expected output:** Sprint review published to Confluence + sprint status updated in Jira/Linear + next sprint capacity recommendation.

---

## PH4-04 — Requirement Change Impact Analysis

Use this when a client requests a change to an existing requirement mid-sprint.

```
The client has requested a change to [PRODUCT NAME]:

Change request: [DESCRIBE THE CHANGE IN 2-3 SENTENCES]

Before I agree to anything, please do an impact analysis:

1. Read the BRD in Confluence [SPACE_KEY] — find all requirements that this change would affect and list them with their IDs.
2. Read the Jira/Linear project [PROJECT_KEY / WORKSPACE] — find all stories that implement the affected requirements. What is their current status (To Do / In Progress / Done)?
3. For stories that are DONE: this change means rework. Estimate the impact.
4. For stories that are IN PROGRESS: how disruptive is the change to the current work?
5. Check the unknowns register in Confluence — was this change mentioned as a risk or assumption?

Produce a Change Impact Report:
- What changes (requirements affected, stories affected)
- What it costs (stories to redo, estimated points)
- What the risk is (what else could break if we make this change)
- Recommendation: Accept / Defer to next sprint / Reject with explanation

Do not accept or reject the change yourself — present the analysis and let me make the decision.
```

**What Claude does:** Cross-references BRD requirements with live Jira/Linear stories, quantifies the cost of the change, checks against the unknowns register, and presents a structured impact report.

**Expected output:** Change impact report with cost estimate + recommendation for BA to decide on.

---

## PH4-05 — Sign-Off Package Assembly

Use this at the end of the engagement to assemble the complete client sign-off package.

```
[PRODUCT NAME] is ready for client sign-off. Help me assemble the sign-off package.

Please:
1. Read Confluence space [SPACE_KEY] and list every document that exists.
2. Identify which of these are client-facing deliverables vs internal working documents.
3. Check that the following mandatory deliverables exist and are at version 1.0 or higher:
   - Business Requirements Document (BRD)
   - High-Level Architecture Diagram
   - Stakeholder-reviewed requirements (all requirements have been reviewed — flag any that have not)
   - Open questions register (all HIGH items resolved or explicitly deferred with client approval)

4. For any missing or incomplete deliverable: tell me exactly what needs to be finished.

5. Generate a Sign-Off Cover Page with:
   - Project name and version
   - List of deliverables included
   - Summary of what is being approved (in plain language)
   - What changes after sign-off (frozen scope, version-controlled changes)
   - Space for client signature / approval date

6. Save the Cover Page to Confluence as "[PRODUCT NAME] — Sign-Off Package Cover" in space [SPACE_KEY].

7. Create a Jira/Linear issue "Client Sign-Off" in project [PROJECT_KEY] with links to all deliverables and status AWAITING APPROVAL.
```

**What Claude does:** Audits all Confluence pages, checks mandatory deliverables are complete, generates the sign-off cover page, and creates the sign-off tracking issue.

**Expected output:** Sign-off package cover page in Confluence + sign-off tracking issue in Jira/Linear + gap list if anything is missing.

---

> Chitragupt BA Prompt Library · Phase 4 Delivery · v0.1 · May 2026
