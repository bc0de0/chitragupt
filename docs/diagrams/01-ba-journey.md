# 01 — The BA Journey

Chitragupt guides a Business Analyst from a raw problem description to a signed-off document — through conversation alone. No forms. No templates to fill in. Just questions and answers, one at a time.

---

## The Seven Phases

Every session moves through seven phases in order. Each phase has a clear goal. The system does not advance until that goal is met and the BA confirms it.

```mermaid
flowchart LR
    A([🏁 Problem\nIntake]) --> B([👥 Stakeholder\nDiscovery])
    B --> C([📋 Requirement\nElicitation])
    C --> D([🚧 Constraint\nCapture])
    D --> E([🏗 Architecture\nAlignment])
    E --> F([✍️ Review &\nSign-Off])
    F --> G([✅ Signed\nOff])

    style A fill:#1565C0,color:#fff,stroke:none
    style B fill:#1976D2,color:#fff,stroke:none
    style C fill:#1E88E5,color:#fff,stroke:none
    style D fill:#42A5F5,color:#212121,stroke:none
    style E fill:#64B5F6,color:#212121,stroke:none
    style F fill:#90CAF9,color:#212121,stroke:none
    style G fill:#1B5E20,color:#fff,stroke:none
```

> **Sprint 1** covers Phases 1–4. Architecture Alignment and Sign-Off are Sprint 2.

---

## What One Phase Looks Like

The session opens with the simplest possible question: *"What problem are you trying to solve?"* From there, the system leads — one question at a time — until four things are established. Then it asks the BA to confirm what it captured. Only then does it offer the next phase.

```mermaid
flowchart TD
    OPEN([Session starts]) --> Q1[System: What problem\nis the client solving?]
    Q1 --> A1[BA answers in own words]
    A1 --> Q2[System: What kind\nof business is this?]
    Q2 --> A2[BA answers]
    A2 --> Q3[System: Who is\nmost affected?]
    Q3 --> A3[BA answers]
    A3 --> Q4[System: What does\nsuccess look like?]
    Q4 --> A4[BA answers]
    A4 --> SUM[System: Here is what I captured.\nDoes this look right?]
    SUM -->|BA confirms| NEXT([Phase 2 begins])
    SUM -->|BA corrects| Q1
```

This same pattern repeats in every phase. The BA is never presented with a blank canvas.

---

## What Happens When the BA Uploads a Document

The BA can upload a document at any point — a brief, an org chart, meeting notes, a compliance policy. The system reads it immediately and adjusts what it knows. An uploaded document is evidence, not an attachment.

```mermaid
flowchart LR
    UP([BA uploads\na document]) --> READ[System reads\nand indexes it]
    READ --> COMPARE{Does it match\nwhat was said in chat?}
    COMPARE -->|Confirms| BOOST[Requirement confidence\ngoes up ✅]
    COMPARE -->|Contradicts| FLAG[Conflict surfaced\nBA resolves it]
    COMPARE -->|Adds new info| ADD[New fact added\nto the session]
```

A session without any uploaded documents can still produce a BRD. Requirements sourced only from conversation will carry a lower confidence score and a visible warning tag in the final document.
