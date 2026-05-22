# Phase 1 — Discovery Prompts

**Purpose:** Define the problem, map stakeholders, surface unknowns, and produce the discovery documents that Sprint 0 depends on.
**Tool access needed:** Confluence (to save outputs), Jira/Linear (to cross-reference existing work).

---

## PH1-01 — Problem Statement Workshop

Run this before writing a single requirement. The problem statement is the foundation. If it is wrong, everything built on it is wrong.

```
I need to write a rigorous problem statement for [PRODUCT NAME].

Here is my current rough understanding:
[PASTE YOUR ROUGH NOTES — can be messy, that's fine]

Please do the following:
1. Read any existing problem statement, brief, or scope document in Confluence [SPACE_KEY]. Tell me what it says and whether it names a solution before defining the problem (this is a red flag — note it if so).
2. Challenge my rough understanding. For each claim I made, ask: is this the problem or is it a proposed solution? Is this a symptom or a root cause?
3. Help me write a problem statement in this format:
   - Context: [Who is affected, in what situation?]
   - Problem: [What is actually broken or painful — stated without naming a solution?]
   - Impact: [What does this cost in time, money, risk, or quality?]
   - Definition of success: [How will we know in 6 months that we solved this?]
4. After writing the draft, ask me the one question most likely to invalidate it.

Do not write requirements. Do not suggest features. Only define the problem.
```

**What Claude does:** Runs a Socratic challenge on your current thinking, pulls in existing docs for comparison, and produces a rigorous problem statement in a standardized format.

**Expected output:** A problem statement draft that separates problem from solution + one challenging question.

---

## PH1-02 — Stakeholder Interview Preparation

Use this before running any stakeholder interviews. Claude prepares questions tailored to each role.

```
I am about to interview stakeholders for [PRODUCT NAME].

Based on the stakeholder table we built in PH0-04 (or: here are the stakeholders I know about: [LIST]), please help me prepare.

For each stakeholder type below, generate 5-7 interview questions tailored to their role:
- [ROLE 1 — e.g. Product Owner]
- [ROLE 2 — e.g. End User]
- [ROLE 3 — e.g. IT / Technical Lead]
- [ROLE 4 — e.g. Compliance / Legal]

For each question, tell me:
- What I am trying to learn
- What answer would be a green flag (confirms our direction)
- What answer would be a red flag (signals a risk or misalignment)

Also:
- Which stakeholder should I interview first, and why?
- What is the one question I must not forget to ask any of them?

Cross-check Confluence [SPACE_KEY] for any existing interview notes or feedback from these roles and flag if we have already asked some of these questions.
```

**What Claude does:** Generates role-specific interview questions with signal interpretation, prioritizes interview order, and avoids duplicating questions already answered in existing docs.

**Expected output:** Interview question set per role + interview priority order + a "must-ask" question.

---

## PH1-03 — Unknowns and Assumptions Register

Run this after initial discovery conversations. Surfaces everything you are assuming without knowing.

```
We have completed initial discovery for [PRODUCT NAME].

Here is a summary of what we know so far:
[PASTE NOTES FROM PH1-01 AND ANY INTERVIEWS]

Please help me build a rigorous unknowns and assumptions register:

1. Read Confluence [SPACE_KEY] and Jira [PROJECT_KEY] for any references to: unknown, assumption, TBD, to be confirmed, pending, unclear, risk, open question.
2. From my notes above, identify every claim that is an assumption (something we are treating as true but have not confirmed).
3. For each assumption: state it, classify it (Technical / Business / Regulatory / Market), assess the risk if wrong (High / Medium / Low), and suggest how to validate it.
4. For each unknown: state what we do not know, who can answer it, and what we will assume in the meantime if we cannot wait for the answer.
5. Produce a register in this format and save it to a new Confluence page titled "[PRODUCT NAME] — Unknowns and Assumptions" in space [SPACE_KEY].

| ID | Item | Type | If wrong | How to validate | Owner | Due | Status |
```

**What Claude does:** Mines both tools for uncertainty signals, builds a register from your notes + tool content, and saves it directly to Confluence.

**Expected output:** Published Confluence page with the unknowns register + a count of High-risk assumptions that must be resolved before Sprint 1.

---

## PH1-04 — Scope Boundary Definition

Use this to draw the line between what is in and out of scope — before the team starts building the wrong things.

```
We need to define the scope boundary for [PRODUCT NAME] clearly.

Current understanding of what we are building:
[PASTE YOUR CURRENT SCOPE UNDERSTANDING]

Please do the following:
1. Search Jira [PROJECT_KEY] for any epics or issues that were ever discussed but then de-scoped, labelled "future", or moved to an icebox. List them.
2. Search Confluence [SPACE_KEY] for any scope documents, statement of work, or project charter.
3. Help me build a scope boundary document with three sections:
   - IN SCOPE: Features and capabilities we are committing to
   - OUT OF SCOPE (explicit): Things we have explicitly decided not to build in this phase
   - DEFERRED: Things that may be in scope in a future phase — named explicitly so they are not forgotten
4. For each item I mark OUT OF SCOPE, ask: is this out of scope because it is genuinely not needed, or because it is hard and we are avoiding it? Flag the latter.
5. Save this to Confluence as "[PRODUCT NAME] — Scope Boundary v1.0" in space [SPACE_KEY].

Be challenging. The most common scope failure is leaving things ambiguous rather than explicitly deciding.
```

**What Claude does:** Pulls deferred/iced items from Jira, merges with existing scope docs, challenges scope decisions, and produces a published Confluence page.

**Expected output:** Published scope boundary document with three explicit sections + flags on scope items that are "avoided" rather than genuinely excluded.

---

## PH1-05 — Discovery Synthesis and Sprint 0 Readiness

Run this at the end of discovery to assess whether you are ready to enter Sprint 0.

```
Discovery for [PRODUCT NAME] is nearing completion. Before we move to Sprint 0, I need to validate that we have done this correctly.

Please do the following:
1. Read everything we have produced so far in Confluence [SPACE_KEY] — the problem statement, stakeholder map, unknowns register, and scope boundary.
2. Cross-check against the Sprint 0 entry checklist:
   - Is the problem statement written without naming a solution?
   - Is at least one decision-maker identified by name and role?
   - Is success defined in measurable terms?
   - Are there ≥ 5 unknowns in the register, all with owners and due dates?
   - Is the scope boundary document present with explicit IN / OUT / DEFERRED sections?
3. For anything missing: tell me exactly what is missing and what I need to do to produce it.
4. For anything that is present but weak: tell me specifically what needs to be strengthened.
5. Give me a readiness verdict: READY TO START SPRINT 0 / NEEDS WORK — with a list of blockers if any.

Be honest. A weak discovery is worse than a slow discovery.
```

**What Claude does:** Reads all existing discovery outputs and scores them against the Sprint 0 entry checklist from PB-05, giving a clear go/no-go verdict.

**Expected output:** Sprint 0 readiness verdict with specific gaps listed + action items to close them.

---

> Chitragupt BA Prompt Library · Phase 1 Discovery · v0.1 · May 2026
