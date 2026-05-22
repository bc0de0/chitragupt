# 05 — The Three Services

Chitragupt is three separate programs, each written in a different language. They never share code. They pass messages to each other over a well-defined channel. Each one is responsible for exactly one domain — and has no authority over the others.

---

## One Job Each

```mermaid
flowchart TB
    BA([🧑‍💼 Business Analyst\nin a browser]) -->|sends a message| GO

    subgraph GO["🐹 Go — The Front Door\n:8080"]
        G1[Accepts connections]
        G2[Checks identity — JWT auth]
        G3[Routes to the right service]
        G4[Streams words back to the browser]
    end

    GO -->|hands off to| RUST

    subgraph RUST["🦀 Rust — The Brain\n:50051"]
        R1[Tracks which phase the session is in]
        R2[Evaluates acceptance criteria]
        R3[Checks all gates and blocks if needed]
        R4[Decides when to advance to the next phase]
    end

    RUST -->|requests AI work| PYTHON

    subgraph PYTHON["🐍 Python — The Intelligence\n:50052"]
        P1[Classifies what the BA meant]
        P2[Extracts structured facts]
        P3[Searches uploaded documents]
        P4[Identifies the best next question]
        P5[Writes and streams the response]
    end

    PYTHON -->|streams words| RUST
    RUST -->|streams words| GO
    GO -->|streams words| BA
```

The BA types a message. It flows in: Go → Rust → Python. The response streams back: Python → Rust → Go → Browser. The BA sees words appearing in real time.

---

## Why These Three Languages

Each language was chosen because it is genuinely the best fit for that specific job.

```mermaid
flowchart LR
    subgraph WHY_RUST["🦀 Why Rust for the state machine"]
        RS["Rules are the whole job:\nif this condition, then that outcome.\n\nRust's compiler checks every\npossible combination at build time.\nAn impossible state is a build error —\nnot a production incident at 2am."]
    end

    subgraph WHY_PY["🐍 Why Python for AI"]
        PY["Every LLM SDK, embedding library,\nand document parser is Python-first.\n\nLLM calls take 1–5 seconds.\nPython overhead is 10ms.\nThe performance concern does not apply here."]
    end

    subgraph WHY_GO["🐹 Why Go for the API"]
        GO["Each active BA session holds\na WebSocket connection open.\n\nGo handles 10,000 open connections\nat around 20MB total memory.\nThe same load in Python costs ~500MB."]
    end
```

---

## What Each Service Owns

A key design principle: each service has authority over exactly one domain. It cannot reach into another service's territory.

| | Go | Rust | Python |
|---|---|---|---|
| **Responsible for** | Auth, routing, WebSocket, streaming | Session state, phases, AC, gates | LLMs, RAG, extraction, generation |
| **Not allowed to** | Evaluate criteria or call LLMs | Parse documents or call LLM APIs | Make gate decisions or change session state |
| **Owns in the database** | Nothing (reads session for auth only) | `session` table | `document`, `chunk`, `requirement` tables |
| **If it goes down** | No new connections accepted | Sessions freeze mid-turn | AI responses stop; state machine waits |

This separation means a faster AI model in Python does not require touching Go or Rust. A new gate rule in Rust does not require changing any Python prompt.
