# Phase 2 — Architecture & Design Prompts

**Purpose:** Make every architectural, AI strategy, and data design decision — with Claude as the opinionated technical co-designer, pulling context from your docs and challenging lazy choices.
**Tool access needed:** Confluence (read existing tech docs, save decisions), Jira/Linear (link decisions to epics).

---

## PH2-01 — Architecture Decision Workshop

Use this to design the system architecture from first principles. Claude will challenge every choice and record the rationale.

```
We are designing the architecture for [PRODUCT NAME].

Before recommending anything, please:
1. Read any existing architecture documents in Confluence [SPACE_KEY] — especially anything about infrastructure, services, or previous tech decisions.
2. Read any Jira epics labelled [infrastructure / backend / platform] in project [PROJECT_KEY] to understand what has already been built.

Now, based on our discovery outputs and the following product description:
[PASTE 2-3 SENTENCES DESCRIBING WHAT THE SYSTEM DOES]

Answer these decisions in order. For each: give me your recommendation, the reason, and the alternative you considered and rejected.

D-001: Monolith vs microservices vs polyglot — what is the right service structure for this product?
D-002: What are the service boundaries? Which concerns belong in which service?
D-003: How should services communicate? (gRPC / REST / message queue / event bus)
D-004: Where does session or workflow state live and who owns it?
D-005: What is the trust hierarchy for information sources in this system?
D-006: How is multi-tenancy enforced? What is the tenant isolation mechanism?

For each decision, use this format:
DECISION: [number and title]
We chose: [option]
Because: [1-3 plain-language reasons]
We considered: [alternative] but rejected it because [reason]
Revisit if: [condition that would make us reconsider]

Then save all six decisions to a new Confluence page titled "[PRODUCT NAME] — Architecture Decisions" in space [SPACE_KEY].
```

**What Claude does:** Researches existing architecture, makes opinionated recommendations for all 6 foundational decisions, records rationale, and publishes to Confluence.

**Expected output:** Six Architecture Decision Records published to Confluence + questions where Claude needs your input before deciding.

---

## PH2-02 — Technology Stack Selection

Use this after architecture decisions are made. Gets specific on languages, frameworks, and libraries.

```
We have decided on the architecture for [PRODUCT NAME] (see: [CONFLUENCE PAGE LINK or paste D-001 through D-006]).

Now help me select the technology stack.

For each service we identified:
1. Recommend the programming language and explain why it is the right fit for that service's computational profile.
2. Recommend the top 3 libraries or frameworks for that service (with version numbers if possible).
3. Flag any library that is a "mainstream vs niche" risk — where a popular choice exists and we are considering something less common.
4. Identify any technology decisions that are DEFERRED and must be resolved before Sprint 1.

Also:
- What is the recommended ORM or database client for each service?
- What is the recommended gRPC implementation for each language?
- What is the recommended logging library for each service?
- What is the recommended testing framework for each service?

Format as a table: Service | Language | Key Libraries | Rationale

Save as "[PRODUCT NAME] — Technology Stack" in Confluence [SPACE_KEY] and create a Jira epic "Sprint 0: Technology Stack Decision" in project [PROJECT_KEY] with this decision as a linked attachment.
```

**What Claude does:** Makes specific, versioned technology recommendations per service with rationale, creates a Jira epic for tracking, and publishes the stack doc to Confluence.

**Expected output:** Tech stack table in Confluence + Jira epic created + list of deferred tech decisions.

---

## PH2-03 — AI Function Inventory and Model Selection

Use this when the product involves LLM or AI capabilities.

```
[PRODUCT NAME] requires AI capabilities. Let us design the AI strategy.

Here is what the system needs to do from an AI perspective:
[DESCRIBE THE AI-DRIVEN FEATURES IN 2-4 SENTENCES]

Please:
1. Read any existing AI or LLM documentation in Confluence [SPACE_KEY].
2. Build a complete LLM function inventory for this product. For each function:
   - Name it
   - Describe what it does in one sentence
   - Classify it: Fast (classification/routing) / Standard (extraction/analysis) / Premium (generation/synthesis) / Embedding / Modal (audio/image)
   - Assign a primary model with a pinned model ID
   - Assign a fallback model (must be from a different vendor)
   - Estimate the max acceptable latency in ms

3. Design the budget strategy:
   - Estimate cost per function call (use published API pricing)
   - Estimate cost per complete user session
   - Recommend caution, critical, and hard-limit thresholds
   - Define the quality floor for final output (minimum model tier for deliverables)

4. Recommend an orchestration framework and justify the choice.

5. Save the result as "[PRODUCT NAME] — AI Strategy" in Confluence [SPACE_KEY].

Use only pinned model IDs — no floating aliases. If you recommend claude-sonnet, write the exact versioned ID.
```

**What Claude does:** Builds the full AI function inventory with real model IDs and pricing estimates, designs the budget strategy, and publishes the AI strategy doc to Confluence.

**Expected output:** AI strategy document in Confluence with function-to-model mapping, cost estimates, and budget thresholds.

---

## PH2-04 — Data Architecture Design

Use this to design the full data layer before any schema is written in code.

```
We need to design the data architecture for [PRODUCT NAME].

Product context: [2-3 sentences on what data the system handles]
Users: [approximate number of tenants / users]
Compliance flags (check all that apply): [ ] GDPR  [ ] HIPAA  [ ] SOC2  [ ] PCI  [ ] None

Please:
1. Read any existing database documentation or schema in Confluence [SPACE_KEY].
2. For each data type in this system, recommend a storage mechanism:
   - Structured business data (sessions, users, decisions) → [your recommendation]
   - Semantic content (documents, chunks, embeddings) → [your recommendation]
   - Active session cache → [your recommendation]
   - File storage (PDFs, images, audio) → [your recommendation]
   - Audit trail → [your recommendation]
   - Cost/usage telemetry → [your recommendation]

3. Design the multi-tenancy enforcement strategy:
   - How is tenant_id propagated from JWT to database queries?
   - Which tables require Row Level Security?
   - What does the RLS policy look like?

4. If this system uses vector search:
   - Recommend the embedding model with pinned version and output dimension
   - Design the hybrid search strategy (dense + sparse weights)
   - Specify the vector index type (HNSW vs IVFFlat) and configuration

5. Write the migration strategy rules (how schema changes are applied).

6. Save as "[PRODUCT NAME] — Data Architecture" in Confluence [SPACE_KEY].
```

**What Claude does:** Designs the full data layer with specific technology recommendations, RLS strategy, vector index config, and migration rules — published to Confluence.

**Expected output:** Data architecture document in Confluence + specific SQL patterns for RLS and vector indexing.

---

## PH2-05 — Architecture Review and Sprint 0 Closure

Run this to formally close Sprint 0 architecture work and validate completeness before Sprint 1 begins.

```
We have completed the architecture design for [PRODUCT NAME]. Before closing Sprint 0, please validate.

Read the following Confluence pages in space [SPACE_KEY]:
- [PRODUCT NAME] — Architecture Decisions
- [PRODUCT NAME] — Technology Stack
- [PRODUCT NAME] — AI Strategy (if applicable)
- [PRODUCT NAME] — Data Architecture
- Any other architecture pages you find

Check each against the Sprint 0 Architecture Completeness Checklist:
[ ] Every service has exactly one stated responsibility
[ ] Every piece of data has exactly one owning service
[ ] Communication protocol decided for every inter-service call
[ ] Multi-tenancy invariant documented and enforcement mechanism described
[ ] Trust hierarchy defined for all information sources
[ ] All architectural decisions recorded with: question, choice, alternative, rationale
[ ] All model IDs pinned (no floating aliases anywhere)
[ ] Budget strategy designed with three threshold levels
[ ] Migration strategy documented

For any item that is missing or incomplete: tell me exactly what is missing.
Give me a final verdict: SPRINT 0 CLOSED / SPRINT 0 INCOMPLETE.
If incomplete, create Jira issues in [PROJECT_KEY] for each gap found.
```

**What Claude does:** Reads all architecture documents, checks against the completeness list, and creates Jira issues for any gaps — giving a clear go/no-go for Sprint 1.

**Expected output:** Architecture review verdict + Jira issues created for any gaps.

---

> Chitragupt BA Prompt Library · Phase 2 Design · v0.1 · May 2026
