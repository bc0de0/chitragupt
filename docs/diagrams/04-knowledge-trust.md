# 04 — How the System Decides What to Believe

Chitragupt reads documents, listens to conversations, and uses AI to fill in gaps. Not all of these sources are equally reliable. The system keeps track of exactly where every piece of information came from — and how confident it is.

---

## The Trust Ladder

Every fact in the session has a source. Sources are ranked. Higher rank always wins.

```mermaid
flowchart TD
    R1["🏛  Level 1 — BA's own words\nThe BA approved, edited, or confirmed it directly.\nNothing outranks this."]
    R2["📊  Level 2 — Structured systems\nJira fields, typed API contracts, database schemas.\nThe source system enforced the format — hard to be wrong."]
    R3["📄  Level 3 — Primary documents\nClient PDFs, signed Confluence pages, official emails.\nAuthored or approved by the client. Baseline trust."]
    R4["📝  Level 4 — Secondary documents\nMeeting notes, Slack threads, internal memos.\nInformal. May not reflect final decisions."]
    R5["🤖  Level 5 — AI inference\nThe model synthesised this from patterns and industry norms.\nAlways tagged. Always flagged for human review."]

    R1 --> R2 --> R3 --> R4 --> R5

    style R1 fill:#1B5E20,color:#fff,stroke:none
    style R2 fill:#2E7D32,color:#fff,stroke:none
    style R3 fill:#43A047,color:#fff,stroke:none
    style R4 fill:#81C784,color:#212121,stroke:none
    style R5 fill:#C8E6C9,color:#212121,stroke:none
```

**The critical rule:** An AI inference can never silently overwrite something a client document said. Level 5 does not beat Level 3.

---

## What the Confidence Score Means

Every requirement the system produces carries a score from 0 to 1. That score determines what tag — if any — appears next to it in the BRD.

```mermaid
flowchart LR
    SCORE{Confidence\nscore} -->|0.85 or above| HIGH["✅  No tag\nHigh confidence.\nReady for the BRD."]
    SCORE -->|0.65 – 0.84| MED["🔵  SYNTHESIZED\nLogically derived from sources.\nReview recommended before sign-off."]
    SCORE -->|0.40 – 0.64| LOW["🟡  INFERRED — VERIFY\nPattern-based. Needs client confirmation."]
    SCORE -->|Below 0.40| NONE["❌  Not included\nRaised as an open question for the BA."]
```

Anything extracted from a diagram or screenshot is capped at 0.80 regardless of score, and always carries `[VISUAL EXTRACTION — VERIFY]`. A diagram is an illustration, not a contract.

---

## When Two Sources Say Different Things

The system never picks a winner on its own. If two sources of the same level say different things, synthesis halts and the BA decides.

```mermaid
flowchart TD
    CONFLICT[Two sources address\nthe same topic differently]
    CONFLICT --> RANK{Are they the\nsame level?}
    RANK -->|No — different levels| WIN[Higher level wins.\nLower-level version discarded.\nNo BA action needed.]
    RANK -->|Yes — same level| HALT[CONFLICT DETECTED\nSynthesis paused for this topic.]
    HALT --> SHOW[System shows both versions\nside by side with full source citations]
    SHOW --> BA{BA decides}
    BA -->|Chooses Source A| GA[Source A locked\nas ground truth]
    BA -->|Chooses Source B| GB[Source B locked\nas ground truth]
    BA -->|Neither — I will clarify| GC[BA writes the correct version.\nBecomes Level 1.]
    GA --> RESUME([Synthesis resumes])
    GB --> RESUME
    GC --> RESUME

    style HALT fill:#B71C1C,color:#fff,stroke:none
    style RESUME fill:#1B5E20,color:#fff,stroke:none
```

The BA knows the client. The model does not. That is why the BA makes the call.
