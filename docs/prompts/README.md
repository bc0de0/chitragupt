# BA Prompt Library — Agentic Product Design with Claude

**Version:** v0.1 · May 2026
**Purpose:** A curated, copy-paste prompt library for Business Analysts using Claude with live access to Jira, Linear, Confluence, or GitBook — to take a product from zero context to a production-grade design, end to end.

---

## What This Is

These are not generic "ask Claude" prompts. They are sequenced, context-building prompts modeled on the exact prompt trail used to design and build Chitragupt — refined for any agentic product build.

Each prompt assumes Claude has MCP (Model Context Protocol) tool access to at least one of:
- **Jira** — issue management, epics, sprints, story creation
- **Linear** — issue management, cycles, projects, milestones
- **Confluence** — knowledge base, architecture docs, decisions, meeting notes
- **GitBook** — technical documentation, guides, API specs

With this access, Claude can pull live context from your tools rather than relying on what you paste in — dramatically improving the quality of output.

---

## How to Use This Library

**If you are starting fresh with a new project:**
Run the prompts in order, Phase 0 → Phase 4. Each prompt picks up context from the previous one.

**If you are mid-project:**
Jump to the phase matching your current stage. The prompts are designed to be usable independently if you give Claude enough context in the first prompt.

**If you need one specific output right now:**
Go to [Power Prompts](Power-Prompts.md) — high-leverage single prompts for BRD generation, user story creation, architecture diagrams, and sprint design.

---

## The Six Prompt Sets

| File | Phase | What it does | Tool access needed |
|---|---|---|---|
| [Phase-0-Kickoff.md](Phase-0-Kickoff.md) | Project start | Load context from existing tools, orient Claude to the project | Jira/Linear + Confluence |
| [Phase-1-Discovery.md](Phase-1-Discovery.md) | Discovery | Problem definition, stakeholder mapping, unknowns, assumptions | Confluence + optional Jira |
| [Phase-2-Design.md](Phase-2-Design.md) | Architecture & AI design | Service boundaries, model selection, data strategy | Confluence |
| [Phase-3-Planning.md](Phase-3-Planning.md) | Sprint planning | Sprint docs, epics, user stories with AC, board creation | Jira/Linear + Confluence |
| [Phase-4-Delivery.md](Phase-4-Delivery.md) | Output generation | BRD, HLD, tech specs, Confluence pages | Confluence + optional Jira |
| [Power-Prompts.md](Power-Prompts.md) | Any phase | Single-shot high-value prompts for common BA moments | Varies |

---

## Claude Setup Assumptions

These prompts work best when Claude has been given the following context before the first prompt:

```
CLAUDE CONTEXT SETUP
---------------------
You are working with [BA name] on a new product called [Product name].

Tool access you have:
- Jira project: [PROJECT_KEY] at [company.atlassian.net]
  OR Linear workspace: [workspace-slug]
- Confluence space: [SPACE_KEY] at [company.atlassian.net]
  OR GitBook: [gitbook-space-url]

Your role: You are a senior BA and solution architect collaborating with me.
You are opinionated — when I ask you to recommend something, give me your
best recommendation with a rationale, not a list of options without guidance.

When you read from my tools, always cite the source (page title, issue ID, etc.)
so I can verify. When you write to my tools, ask me to confirm before saving.
```

---

## Prompt Numbering Convention

Prompts are numbered `PH[N]-[NN]` where:
- `PH[N]` is the phase number (0–4 + PW for Power)
- `[NN]` is the sequence within the phase

Example: `PH1-03` = Phase 1, third prompt.

You can reference these numbers in conversations with Claude: "Run PH2-01 now" — Claude will understand if it has this library loaded as context.

---

## The Prompt Trail Philosophy

The prompts are structured like the Chitragupt prompt trail — sequential, each one building on what came before. The BA drives. Claude documents, reasons, and challenges. The output of every prompt is a decision, a document, or a Jira/Linear/Confluence artifact.

> The BA asks the right question. Claude does the synthesis. The BA approves.

---

> Chitragupt BA Prompt Library · v0.1 · May 2026
