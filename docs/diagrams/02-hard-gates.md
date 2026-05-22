# 02 — Checkpoints and Gates

The system enforces checkpoints. Some are questions it must ask before the session can move forward. Some are documents that must exist. One is a client signature. These are called **gates** — and not all gates are equal.

---

## The Four Gate Types

```mermaid
flowchart TD
    HARD["🔴  HARD GATE\nCannot proceed. Full stop.\nMust be resolved before anything else."]
    REQ["🟠  REQUIRED PROMPT\nThe system must ask this question\nbefore offering to advance.\nThe BA can still answer no or skip."]
    TRIG["🟡  TRIGGERED\nThe BA mentioned something that suggests\na relevant document exists.\nSystem asks once. BA can decline."]
    REC["🟢  RECOMMENDED\nSystem suggests once.\nBA can ignore it entirely. No consequence."]

    HARD --- REQ --- TRIG --- REC
```

| Gate type | Can the BA skip it? | What happens if they do |
|---|---|---|
| HARD GATE | No | Session cannot advance — period |
| REQUIRED PROMPT | Yes, after the question is asked | The decline is recorded |
| TRIGGERED | Yes | Confidence on related requirements drops |
| RECOMMENDED | Yes | No impact |

---

## What the BA Sees When Trying to Advance

When the BA says "let's move on," the system runs a silent checklist. From the BA's perspective, they just see the system's next message.

```mermaid
flowchart TD
    TRY([BA: let's move to the next phase]) --> HG{Hard gate open?}
    HG -->|Yes| BLOCK[System explains the one thing\nthat needs to be resolved and how]
    BLOCK --> TRY
    HG -->|No| RQ{Required question\nnot yet asked?}
    RQ -->|Yes| ASK[System asks the\nrequired question]
    ASK --> TRY
    RQ -->|No| GAP{Essential gaps still open?}
    GAP -->|Yes| PROBE[System asks\nthe missing question]
    PROBE --> TRY
    GAP -->|No| CONFIRM[System: Here is what we captured.\nReady to move on?]
    CONFIRM -->|BA says yes| NEXT([Next phase])
    CONFIRM -->|BA says no| PROBE
```

The BA never sees an error message. They see one clear next step.

---

## The One Gate With No Workaround: Client Signature

The final transition — from Review to Signed Off — requires a recorded client signature. No BA confirmation substitutes for it. A BRD without a client signature is a draft, not a deliverable.

```mermaid
flowchart LR
    REVIEW([Review &\nSign-Off phase]) --> GEN{BRD and HLD\nexist?}
    GEN -->|No| AUTO[System generates\nthem automatically]
    AUTO --> GEN
    GEN -->|Yes| SEND[Sign-off token dispatched\nto client email]
    SEND --> WAIT{Client signs?}
    WAIT -->|Signed| LOCK([SIGNED OFF\nDeliverables locked\nSession closed])
    WAIT -->|Not yet| STATUS[System shows:\nAwaiting signature\nfrom client@company.com]
    STATUS --> WAIT

    style LOCK fill:#1B5E20,color:#fff,stroke:none
```
