# Power Prompts — High-Leverage Single-Shot Prompts

**Version:** v0.1
**Purpose:** Prompts for specific high-value moments that do not fit neatly into a phase — or that you need to run quickly without running the full sequence.
**Tool access needed:** Varies per prompt — listed for each.

---

## PP-01 — "What Are We Missing?" (The Gap Detector)

*Run this at any point in the project to find what has been overlooked.*
**Tool access:** Confluence + Jira/Linear

```
I need you to be a devil's advocate for [PRODUCT NAME].

Read everything in Confluence space [SPACE_KEY] and the Jira project [PROJECT_KEY].

Then answer:
1. What important topic has been discussed in Jira issues but never documented in Confluence? (These are decisions made in passing that may be forgotten.)
2. What important topic appears in Confluence documents but has no Jira epic or story tracking it? (These are decisions that were planned but may never get built.)
3. What requirement appears in the BRD but has no corresponding user story in Jira? (These are requirements at risk of falling through.)
4. What user story in Jira cannot be traced back to a requirement in the BRD? (These are stories that should not exist or whose BRD entry is missing.)
5. What architectural decision is referenced in the tech stack but has no ADR explaining the rationale? (These are latent risks — the decision exists but if challenged, there is no record of why.)

Give me a prioritised list. For each gap, tell me: is this a critical risk, a documentation debt, or a nice-to-have cleanup?
```

---

## PP-02 — "Is This Decision Right?" (The Challenger)

*Use before finalizing any major architectural or strategic decision.*
**Tool access:** Confluence

```
We are about to make a final decision on [DECISION TOPIC] for [PRODUCT NAME].

Our current plan is: [DESCRIBE YOUR CURRENT PLAN IN 2-3 SENTENCES]

Play the role of a skeptical senior architect who has seen this kind of decision go wrong before.

1. What are the 3 most likely ways this decision fails in production?
2. What assumption are we making that we have not validated?
3. What is the strongest argument for the alternative we are NOT choosing?
4. Is there a third option we have not considered that would be better than both?
5. If this decision turns out to be wrong 6 months from now, what would be the fastest way to reverse it?

Do not tell me to "consider both options." Give me your honest assessment of whether our current plan is the right one. If it is not, say so directly.

Read the architecture decisions page in Confluence [SPACE_KEY] first so you understand the full context.
```

---

## PP-03 — "Write My User Story" (The Story Generator)

*Use when you know what a feature should do but need it structured correctly.*
**Tool access:** Jira/Linear

```
I need to write a user story for this feature in [PRODUCT NAME]:

Feature description: [DESCRIBE THE FEATURE IN 2-4 SENTENCES]
User role affected: [WHO USES THIS]
Epic it belongs to: [EPIC NAME / ID]

Please:
1. Write the story in format: "As a [role], I want [capability] so that [outcome]."
2. Write 3-5 acceptance criteria in GIVEN/WHEN/THEN format. For each:
   - One happy path
   - One failure/edge case
   - One non-functional requirement if applicable (performance, security, accessibility)
3. Suggest a story point estimate with reasoning.
4. Flag any technical dependency this story has on another story not yet created.
5. Create the story in [Jira / Linear] under epic [EPIC ID] with the full AC in the description.

If the feature description is ambiguous or could be interpreted multiple ways, ask me to clarify before writing the story.
```

---

## PP-04 — "Explain This to My Client" (The Translator)

*Use when you need to explain a technical decision to a non-technical stakeholder.*
**Tool access:** Confluence (optional — to read source material)

```
I need to explain [TECHNICAL CONCEPT OR DECISION] to a client who has no technical background.

The concept is: [DESCRIBE IT TECHNICALLY — e.g. "we are using a state machine in Rust to enforce phase transitions because the compiler gives us exhaustive matching"]

Please:
1. Explain this in plain language — maximum 3 sentences. Assume the client understands business problems but not engineering.
2. Give one analogy from everyday business life that captures the key benefit.
3. Explain what the alternative would be and why it is worse — in language the client can appreciate ("it would be like... instead of...").
4. Anticipate the one question they will most likely ask and answer it.
5. Write a one-paragraph version I could put in a client email or Confluence page.

Do not use: API, gRPC, enum, compile-time, runtime, state machine, microservice. Use plain equivalents.
```

---

## PP-05 — "Review My Requirements" (The QA Reviewer)

*Use before sending requirements to engineering to catch problems before they become bugs.*
**Tool access:** Confluence + Jira/Linear

```
Before I send these requirements to the engineering team, I need you to review them.

Please read the requirements section of the BRD in Confluence [SPACE_KEY] (or: here are the requirements: [PASTE]).

Review each requirement against these quality criteria:
1. CLEAR: Is the requirement stated unambiguously? Could two engineers read it and implement different things?
2. COMPLETE: Does it have acceptance criteria? Is there a definition of "done" for this requirement?
3. TRACEABLE: Does it have a source? Is it linked to a Jira story?
4. TESTABLE: Can this be verified with an automated test or a specific manual test step?
5. CONFLICT-FREE: Does it contradict any other requirement in the BRD?

For each requirement that fails any of these criteria: tell me specifically what is wrong and give me a rewritten version.

Also flag:
- Any requirement that is actually a solution disguised as a requirement ("the system shall use React" — this is a technology choice, not a requirement)
- Any requirement that is so vague it could never be tested ("the system shall be fast")
- Any requirement that sounds like two requirements merged into one
```

---

## PP-06 — "Create the Sprint 0 in One Shot" (The Speed Sprint)

*Use when you need Sprint 0 documents fast and have reasonable clarity on the product.*
**Tool access:** Confluence (to save), Jira/Linear (to create epics)

```
I need to run a fast Sprint 0 for [PRODUCT NAME].

Here is everything I know:
- Problem: [2-3 SENTENCES]
- Users: [WHO USES THIS]
- Key features: [LIST 4-6 FEATURES]
- Tech context: [LANGUAGE PREFERENCES, EXISTING INFRASTRUCTURE]
- Compliance: [GDPR / HIPAA / none]
- Budget sensitivity: [HIGH — cost per request matters / MEDIUM / LOW]
- Timeline: [HARD DEADLINE OR FLEXIBLE]

Please produce all Sprint 0 decisions and documents in one response:

1. Problem statement (50+ words, solution-free)
2. Recommended architecture (monolith / polyglot — with 2-sentence rationale)
3. Technology stack (per service, with pinned library versions)
4. AI strategy (if applicable — function inventory, tier assignments, budget thresholds)
5. Data architecture (storage type per data class, RLS strategy)
6. The 5 most important architectural decisions (ADR format)
7. Sprint 1 epic list with priorities (P1/P2/P3)
8. The 3 biggest risks entering Sprint 1

Save each section as a separate Confluence page in space [SPACE_KEY].
Create P1 epics in [Jira / Linear] project [PROJECT_KEY / WORKSPACE].

Be opinionated. Give me decisions, not options.
```

---

## PP-07 — "Retrospective Analysis" (The Honest Look Back)

*Use at the end of any sprint to get an unvarnished view of what happened.*
**Tool access:** Jira/Linear

```
Sprint [N] for [PRODUCT NAME] is complete. I need an honest retrospective.

Please read the completed sprint in [Jira / Linear]:
- What stories were committed? What was done? What was not done?
- What stories were added mid-sprint (scope creep indicators)?
- What stories were blocked and for how long?
- What is the velocity trend across the last [2-3] sprints if you can see them?

Now answer:
1. Did we achieve the sprint goal? Yes / Partially / No — with evidence.
2. What was the single biggest cause of incomplete work? (Underestimation / Scope added / Blocked / Technical complexity / Other)
3. Which story caused the most pain and why?
4. Was there any work done that was not in the sprint plan? If so, was it justified?
5. What one change to our planning process would most improve Sprint [N+1]?

Be direct. Do not write a balanced "here is what went well / here is what could improve" format. Tell me what actually went wrong and what I should do about it.
```

---

## PP-08 — "Research This Technology" (The Deep Dive)

*Use when you need to make a technology decision and want Claude to research it for you.*
**Tool access:** None required (but Confluence to save output)

```
I need to make a decision about [TECHNOLOGY / FRAMEWORK / LIBRARY] for [PRODUCT NAME].

Context: We are building [BRIEF DESCRIPTION]. We need this technology to [SOLVE PROBLEM].

Please research this thoroughly and answer:
1. What exactly does [TECHNOLOGY] do and what problem does it solve best?
2. What are the top 3 production use cases for this technology — what kinds of companies use it and for what?
3. What are the known failure modes and limitations? (Do not just list cons from the marketing page — tell me about real failure modes that teams have hit.)
4. What is the current version and is it stable for production? What is the release cadence?
5. What does the migration path look like if we choose this and later need to change? (Lock-in assessment)
6. What would a senior engineer who has worked with this say are the things they wish they knew before choosing it?
7. On a scale of 1-10: how confident are you that this is the right choice for our specific use case? Why?

Then: give me your recommendation — use it / do not use it / use it with these conditions.
```

---

## PP-09 — "Write This ADR" (The Decision Recorder)

*Use immediately after making any significant architectural decision — captures it before context is lost.*
**Tool access:** Confluence

```
We just made a decision for [PRODUCT NAME]. I need to record it before we move on.

The decision we made: [DESCRIBE IN 1-2 SENTENCES]

Please write an Architecture Decision Record in this format:

---
DECISION: D-[NEXT NUMBER]
Title: [Short descriptive title]
Date: [TODAY]
Status: DECIDED
Author: [YOUR NAME]

QUESTION
[What architectural question does this answer?]

CONTEXT
[Why did this need to be decided? What constraints drove it?]

DECISION
We chose: [option]
Because: [1-3 clear reasons in plain language]

ALTERNATIVES CONSIDERED
Option A — [Name]: [Brief description]. Rejected because: [Reason].
Option B — [Name]: [Brief description]. Rejected because: [Reason].

CONSEQUENCES
What does this make easier?
What does this make harder or more expensive?

REVISIT CONDITION
Under what circumstances should we reconsider this?
---

Save this to the "Architecture Decisions" page in Confluence [SPACE_KEY] — append it to the existing list of decisions.
Update the decision number to be the next in sequence after the last decision on that page.
```

---

## PP-10 — "The BA Standup Brief" (Daily Context Builder)

*Use at the start of each working day to get oriented before meetings.*
**Tool access:** Jira/Linear + Confluence

```
Good morning. I am about to start my BA day on [PRODUCT NAME].

Give me a 2-minute brief:
1. What changed in [Jira / Linear] project [PROJECT_KEY] since [YESTERDAY / LAST FRIDAY]?
   - New issues created
   - Issues that moved to Done
   - Issues that are newly Blocked
   - Comments that mention a decision or a risk

2. What is happening in the current sprint?
   - How many points completed vs total committed?
   - How many days left in the sprint?
   - Are we on track? (Simple: yes / at risk / no)

3. What is the one thing I must not forget to do today based on what I see in the board?

Keep this to bullet points. No paragraphs. I am about to start a meeting.
```

---

> Chitragupt BA Prompt Library · Power Prompts · v0.1 · May 2026
