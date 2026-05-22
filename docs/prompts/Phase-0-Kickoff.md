# Phase 0 — Project Kickoff Prompts

**Purpose:** Orient Claude to your project using live context from your tools. Run these before anything else.
**Tool access needed:** Jira or Linear (for existing work), Confluence or GitBook (for existing docs).

---

## PH0-01 — Cold Start: Load Everything Claude Needs to Know

Use this when Claude has zero context about the project. It tells Claude to go find context rather than asking you to paste it in.

```
I am starting a new product called [PRODUCT NAME].

Here is what I know so far:
- Problem: [ONE SENTENCE — what pain does this solve?]
- Client / company: [WHO is this for?]
- Approximate scope: [SMALL / MEDIUM / LARGE — your gut feel]

I want you to help me design this product from scratch.

Before we begin, please:
1. Search Confluence space [SPACE_KEY] for any existing pages related to [PRODUCT NAME] or [RELATED TOPIC]. List what you find with page titles and last-modified dates.
2. Search the Jira project [PROJECT_KEY] for any existing epics or issues related to [PRODUCT NAME]. List them with their status.
3. Tell me: based on what you found, what do we already know, and what is the most important thing we need to establish first?

Then ask me the one most important question you need answered to start the discovery phase.
```

**What Claude does:** Searches both tools, synthesises what already exists, identifies the first gap, and asks one focused question.

**Expected output:** A summary of existing context + one clarifying question. If nothing exists, Claude will say so and propose starting from scratch.

---

## PH0-02 — Orient to an Existing Project

Use this when picking up a project mid-stream or joining an existing team.

```
I am joining an existing project called [PRODUCT NAME] as the BA.

Please do the following to orient me:

1. Read the Confluence space [SPACE_KEY] and list:
   - All pages in the space with their titles and last-modified dates
   - Any architecture decision pages or ADRs
   - Any existing requirements, BRDs, or specification documents

2. Read the Jira project [PROJECT_KEY] and tell me:
   - How many open epics exist and what are their names?
   - What are the current sprint's stories? Which are blocked?
   - What was completed in the last two sprints?

3. Based on everything you found, give me:
   - A 5-bullet summary of where this project is today
   - The 3 biggest open risks or questions you can see from the docs and issues
   - What the BA before me appears to have left unfinished

Do not summarise what I already told you. Only report what you found in the tools.
```

**What Claude does:** Deep-reads your tools and gives you an honest orientation — including what looks incomplete or risky.

**Expected output:** Project orientation brief with risk flags. Treat this like a handover document generated from live data.

---

## PH0-03 — Technology Context Load

Use this before any architecture or AI strategy work. Gets Claude up to speed on what's already been decided technically.

```
Before we design the technical architecture for [PRODUCT NAME], I need you to understand what already exists.

Please:
1. Read any pages in Confluence [SPACE_KEY] with titles containing words like: architecture, tech stack, decisions, ADR, infrastructure, deployment, database, API.
2. Read any Jira epics labelled [infrastructure / platform / backend / architecture] in project [PROJECT_KEY].
3. List the existing technology choices you found (languages, frameworks, databases, cloud provider, CI/CD tools).
4. Flag any decisions that look inconsistent, outdated, or incomplete.
5. Tell me: what do we know about the technical stack, and what must we still decide before we can design the new product?
```

**What Claude does:** Builds a technology inventory from live documents and surfaces gaps and inconsistencies before new decisions layer on top of old ones.

**Expected output:** Technology inventory table + list of open decisions + questions that must be resolved.

---

## PH0-04 — Stakeholder Context Load

Use this at the start of any new engagement to understand who is involved before conducting interviews.

```
I am about to start stakeholder discovery for [PRODUCT NAME].

Before I run any interviews, help me understand who is already known:

1. Search Confluence [SPACE_KEY] for any pages mentioning: stakeholders, RACI, org chart, decision-makers, sponsors, product owner, client contacts.
2. Search Jira [PROJECT_KEY] for: who has been assigned to epics, who has commented most, who raised the most issues.
3. Based on what you find, create a preliminary stakeholder table with columns: Name/Role, Type (internal/external), Known authority level, Source of this information.
4. Identify any roles that appear in the work but have no named person attached.
5. Tell me: who must I talk to before I can complete discovery, and who seems most important but is most absent from the current records?
```

**What Claude does:** Cross-references two tools to infer a stakeholder map from actual activity, not just from what was formally documented.

**Expected output:** Preliminary stakeholder table with source citations + list of unknown or absent roles.

---

## PH0-05 — Constraint and Risk Inventory

Use this early to surface constraints before they become blockers mid-sprint.

```
Help me build a constraint and risk inventory for [PRODUCT NAME] before we go too far.

1. Search Confluence [SPACE_KEY] for pages containing: compliance, GDPR, HIPAA, security, audit, legal, data residency, budget, timeline, deadline, constraint, blocker.
2. Search Jira [PROJECT_KEY] for issues labelled: risk, blocker, dependency, compliance, security.
3. For each constraint or risk you find, record: Description, Source (page or issue), Severity (High/Medium/Low), Whether it is already resolved or still open.
4. Identify constraints that appear in Jira but not in Confluence (not yet documented) and vice versa.
5. Tell me: what is the constraint most likely to derail this project if we do not address it in Sprint 0?
```

**What Claude does:** Mines both tools for constraint signals and builds a consolidated register, flagging unresolved items and mismatches between tools.

**Expected output:** Constraint and risk register with severity flags + one critical constraint to address in Sprint 0.

---

> Chitragupt BA Prompt Library · Phase 0 Kickoff · v0.1 · May 2026
