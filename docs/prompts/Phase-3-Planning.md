# Phase 3 — Sprint Planning Prompts

**Purpose:** Translate architecture decisions and discovery outputs into an executable sprint plan — with epics, user stories, acceptance criteria, and a live Jira/Linear board.
**Tool access needed:** Jira or Linear (create epics, stories, sprints), Confluence (read design docs, save sprint docs).

---

## PH3-01 — Sprint 0 Document Generation

Use this to generate all seven Sprint 0 canonical documents in one go from the work done in Phases 1 and 2.

```
I need to generate the seven Sprint 0 canonical documents for [PRODUCT NAME].

Please read everything in Confluence space [SPACE_KEY] that we have produced so far — problem statement, stakeholder map, architecture decisions, tech stack, AI strategy, data architecture.

Then generate all seven Sprint 0 documents. For each, produce the full content and save it to Confluence as a new page under a space section called "Sprint 0 — Foundation":

1. BA_HITL_FLOW.md — The phase-by-phase BA conversation protocol for this product. Describe what happens in each phase, what checkpoints exist, and the exit criteria per phase. Use the Chitragupt 7-phase model as a template and adapt it for [PRODUCT NAME].

2. ARCHITECTURE.md — The trust model, confidence scoring rules (if AI is involved), conflict protocol, and engineering invariants. Extract these from our architecture decisions.

3. DECISIONS.md — All architectural decisions made so far in ADR format (question → choice → alternatives → rationale). Pull from the architecture decisions page.

4. TECH_STACK.md — Service design, library choices (pinned versions), gRPC interfaces if applicable, repo structure.

5. ONTOLOGY.md — Complete entity definitions for this product. What is a [key entity]? What are its fields? How does it relate to other entities?

6. DATABASE.md — Physical schema strategy, RLS policies, storage type per data class, migration approach.

7. Sprint 0 README — A summary of everything discovered and decided, the exit criteria, and a declaration of Sprint 0 status (CLOSED or IN PROGRESS).

For any document where you do not have enough information, list exactly what questions I need to answer to complete it.
```

**What Claude does:** Reads all existing work from Confluence and generates all seven Sprint 0 documents — fully formatted, saved to Confluence, with gaps flagged.

**Expected output:** Seven Confluence pages published under Sprint 0 + list of unanswered questions that must be resolved.

---

## PH3-02 — Epic Design from Architecture

Use this to translate architecture decisions into an epic structure that maps directly to the build sequence.

```
Based on the Sprint 0 architecture for [PRODUCT NAME], I need to design the epic structure.

Please:
1. Read the Sprint 0 documents in Confluence [SPACE_KEY], especially TECH_STACK.md and the BA_HITL_FLOW.md.
2. Design the epics for Sprint 1. For each epic:
   - Name (format: "Sprint 1: [Epic title]")
   - One-sentence description
   - Priority: P1 (must-have for Sprint 1 exit) / P2 (complete if P1 done) / P3 (stretch)
   - Dependencies: which epics must be done first
   - Key deliverable: what a "done" epic looks like in one sentence
   - Estimated complexity: S / M / L / XL

3. Create each epic in [Jira project PROJECT_KEY / Linear workspace WORKSPACE]:
   - Add the description
   - Set priority
   - Link dependencies
   - Label: sprint-1

4. Return a summary table: Epic Name | Priority | Complexity | Dependencies | Jira/Linear ID

The first epic must always be the core logic layer (state machine / workflow engine). Never start with the UI or integration layer.
```

**What Claude does:** Reads Sprint 0 docs, designs the epic structure with priorities, creates all epics directly in Jira/Linear, and returns a summary table with IDs.

**Expected output:** Epics created in Jira/Linear + summary table with IDs + dependency map.

---

## PH3-03 — User Story Generation with Acceptance Criteria

Use this to break an epic into implementation-ready user stories. Run once per epic.

```
I need to break down the epic "[EPIC NAME]" (Jira/Linear ID: [ID]) into user stories.

Please:
1. Read the epic in [Jira / Linear] and any linked Confluence pages.
2. Read the relevant section of BA_HITL_FLOW.md and TECH_STACK.md in Confluence [SPACE_KEY] to understand what this epic must implement.
3. Generate user stories in the format: "As a [role], I want [capability] so that [outcome]."
4. For each story, write acceptance criteria in this format:
   GIVEN [initial context]
   WHEN [action is taken]
   THEN [expected result]
   AND [additional condition if needed]
5. Flag any story where the acceptance criteria cannot be tested without a UI (these should wait until the API layer is complete).
6. Assign a story point estimate (Fibonacci: 1, 2, 3, 5, 8, 13).
7. Create each story in [Jira / Linear] as a child of the epic [ID], with AC in the description.

Return a table: Story | AC count | Points | Testable without UI?
```

**What Claude does:** Reads the epic and design docs, generates stories with GIVEN/WHEN/THEN ACs, creates them in Jira/Linear as child issues, and flags untestable stories.

**Expected output:** User stories created in Jira/Linear + summary table + untestable story flags.

---

## PH3-04 — State Machine Phase and AC Definition

Use this specifically when the product has a conversational or workflow phase system (like Chitragupt). This generates the full phase and AC design.

```
[PRODUCT NAME] uses a [state machine / workflow engine] to manage the user journey.

Based on the BA_HITL_FLOW.md in Confluence [SPACE_KEY], help me define the complete phase and acceptance criteria system:

For each phase in the user journey:

1. Phase definition:
   - Phase name (as an enum value, e.g. ProblemIntake)
   - Plain-language description: what is the BA/user doing here?
   - What must be captured before this phase can close?
   - What transition(s) are allowed from this phase?

2. Acceptance criteria (for each phase, generate 4-6):
   - ID: AC-S[N]-[NN]
   - Description: plain language
   - Condition: a specific programmatic check on the session/workflow state
   - Suggested question: the exact question the system should ask if this criterion is unmet
   - Optional or required?

3. Gate inventory (for each phase, identify any upload or external-approval gates):
   - Gate ID
   - Gate type: HARD / REQUIRED_PROMPT / TRIGGERED / RECOMMENDED
   - Trigger condition
   - How to resolve

Format as a document and save to Confluence as "[PRODUCT NAME] — State Machine AC Register" in space [SPACE_KEY].
Then create one Jira story per phase in epic [EPIC_ID]: "Implement AC evaluator for [Phase name]".
```

**What Claude does:** Reads the HITL flow doc and generates a complete phase/AC/gate system — published to Confluence + Jira stories created per phase.

**Expected output:** AC register in Confluence + one Jira story per phase evaluator.

---

## PH3-05 — Sprint Planning Board Setup

Use this to set up the sprint board with the correct structure before sprint kickoff.

```
Sprint 1 for [PRODUCT NAME] is about to begin. Please help me set up the sprint board correctly.

1. Read all epics in [Jira project PROJECT_KEY / Linear workspace WORKSPACE] labelled sprint-1. List them with their current child stories and point totals.

2. Verify the priority ordering:
   - P1 epics must be assigned to Sprint 1 and have stories with points
   - P2 epics may be in Sprint 1 backlog
   - P3 epics must not be in Sprint 1

3. Check for missing stories: are there any epics with no child stories? Flag them.

4. Check dependencies: are there any stories in Sprint 1 that depend on stories not yet in Sprint 1? Flag them.

5. In [Jira / Linear]:
   - Create a sprint named "Sprint 1 — [PRODUCT NAME] Core Engine"
   - Add all P1 stories to the sprint
   - Leave P2 in the backlog with a "sprint-1-stretch" label
   - Move P3 to a future sprint

6. Return: Sprint 1 story count, total points, team capacity check (if I give you the team size and sprint length, calculate if this is realistic).

Team size: [N] engineers + [N] BAs
Sprint length: [2 weeks / 3 weeks]
Average velocity assumption: [N] points per engineer per sprint
```

**What Claude does:** Reads the board state, validates priority ordering, creates the sprint, assigns stories, and does a capacity check.

**Expected output:** Sprint 1 board configured in Jira/Linear + capacity analysis with green/amber/red verdict.

---

## PH3-06 — Definition of Done and Convention Setup

Use this once at the start of Sprint 1 to lock conventions and the definition of done.

```
Before Sprint 1 begins for [PRODUCT NAME], I need to lock the Definition of Done and development conventions.

1. Read any existing conventions or engineering standards in Confluence [SPACE_KEY] — look for pages about code style, commit format, PR process, testing standards.

2. Based on the tech stack ([Rust / Python / Go] from TECH_STACK.md), generate:
   - Commit message format (Conventional Commits)
   - Branch naming convention
   - PR checklist (lint, format, type check, test requirements per language)
   - Definition of Done for a user story
   - Definition of Done for an epic

3. Flag any inconsistency with existing conventions found in Confluence.

4. Save to Confluence as "[PRODUCT NAME] — Development Conventions" in space [SPACE_KEY].

5. Create a Jira story "Sprint 1: Set up CI pipeline" in epic [EPIC_ID] with the following AC:
   GIVEN a PR is opened against main
   WHEN CI runs
   THEN [formatting check] passes
   AND [linting/type check] passes
   AND [all tests] pass
   AND [Docker build] succeeds
   AND merge is blocked if any check fails
```

**What Claude does:** Reads existing conventions (to avoid contradicting them), generates a complete conventions + DoD document, saves to Confluence, and creates the CI setup story.

**Expected output:** Conventions document in Confluence + CI setup story in Jira/Linear.

---

> Chitragupt BA Prompt Library · Phase 3 Planning · v0.1 · May 2026
