"""
Chitragupt — Connection Probe
Tests: (1) OpenRouter model availability, (2) PostgreSQL connectivity, (3) pgvector extension.
Run: python scripts/test_connections.py
Writes a JSON result to stdout; human-readable table to stderr.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── load .env manually (no python-dotenv dependency required) ─────────────────

def _load_dotenv() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

_load_dotenv()


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class ProbeResult:
    name: str
    ok: bool
    latency_ms: float = 0.0
    detail: str = ""
    error: str = ""


@dataclass
class Report:
    results: list[ProbeResult] = field(default_factory=list)

    def add(self, r: ProbeResult) -> None:
        self.results.append(r)

    def print_table(self) -> None:
        width = 52
        print(f"\n{'─' * width}", file=sys.stderr)
        print(f"{'CHITRAGUPT CONNECTION PROBE':^{width}}", file=sys.stderr)
        print(f"{'─' * width}", file=sys.stderr)
        for r in self.results:
            status = "PASS" if r.ok else "FAIL"
            color = "\033[32m" if r.ok else "\033[31m"
            reset = "\033[0m"
            lat = f"{r.latency_ms:6.0f}ms" if r.latency_ms else "      "
            print(f"  {color}{status}{reset}  {r.name:<32} {lat}", file=sys.stderr)
            if r.detail:
                print(f"         {r.detail}", file=sys.stderr)
            if r.error:
                print(f"         \033[31mERR: {r.error[:80]}\033[0m", file=sys.stderr)
        print(f"{'─' * width}", file=sys.stderr)
        passed = sum(1 for r in self.results if r.ok)
        print(f"  {passed}/{len(self.results)} checks passed", file=sys.stderr)
        print(f"{'─' * width}\n", file=sys.stderr)

    def to_json(self) -> dict:
        return {
            "passed": sum(1 for r in self.results if r.ok),
            "total": len(self.results),
            "results": [
                {"name": r.name, "ok": r.ok, "latency_ms": r.latency_ms,
                 "detail": r.detail, "error": r.error}
                for r in self.results
            ],
        }


# ── OpenRouter probes ─────────────────────────────────────────────────────────

OPENROUTER_MODELS = [
    ("MODEL_FAST",              "Fast (Haiku)"),
    ("MODEL_STANDARD",          "Standard (Sonnet)"),
    ("MODEL_PREMIUM",           "Premium (Opus)"),
    ("MODEL_FALLBACK_ANTHROPIC","Fallback (Gemini)"),
    ("MODEL_FALLBACK_EMBEDDING","Fallback Embedding (OAI)"),
]

PROBE_PROMPT = "Reply with exactly the word: PONG"

# OpenRouter is OpenAI-compatible only (exposes /chat/completions, not Anthropic /messages).
# All LLM calls through OpenRouter must use the OpenAI SDK with model IDs prefixed
# by provider (e.g. "anthropic/claude-haiku-4-5-20251001").
# Text-only models are probed with chat.completions; embedding models use a
# separate Voyage probe (Voyage is not on OpenRouter).

EMBEDDING_ENV_KEYS = {"MODEL_EMBEDDING", "MODEL_FALLBACK_EMBEDDING"}


async def probe_openrouter_model(env_key: str, label: str) -> ProbeResult:
    model_id = os.environ.get(env_key, "")
    name = f"OpenRouter/{label}"
    if not model_id:
        return ProbeResult(name=name, ok=False, error=f"{env_key} not set in .env")

    # Skip Voyage embedding models — not on OpenRouter
    if model_id.startswith("voyage-"):
        return ProbeResult(name=name, ok=True,
                           detail=f"Skipped — Voyage model ({model_id}) uses native API")

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    if not api_key:
        return ProbeResult(name=name, ok=False, error="OPENROUTER_API_KEY not set")

    # For fallback embedding via OpenAI — text-embedding-3-small does not support
    # chat completions; skip the chat probe and confirm model availability via list.
    if env_key == "MODEL_FALLBACK_EMBEDDING":
        try:
            from openai import AsyncOpenAI  # type: ignore
            client = AsyncOpenAI(
                base_url=base_url,
                api_key=api_key,
                default_headers={
                    "HTTP-Referer": os.environ.get("OPENROUTER_SITE_URL", ""),
                    "X-Title": os.environ.get("OPENROUTER_SITE_NAME", "Chitragupt"),
                },
            )
            t0 = time.monotonic()
            resp = await client.embeddings.create(
                model=model_id,
                input="probe",
            )
            lat = (time.monotonic() - t0) * 1000
            dim = len(resp.data[0].embedding) if resp.data else 0
            return ProbeResult(name=name, ok=True, latency_ms=lat,
                               detail=f"model={model_id}  dim={dim}")
        except Exception as exc:
            return ProbeResult(name=name, ok=False, error=str(exc)[:120])

    try:
        from openai import AsyncOpenAI  # type: ignore
        client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            default_headers={
                "HTTP-Referer": os.environ.get("OPENROUTER_SITE_URL", ""),
                "X-Title": os.environ.get("OPENROUTER_SITE_NAME", "Chitragupt"),
            },
        )
        t0 = time.monotonic()
        resp = await client.chat.completions.create(
            model=model_id,
            max_tokens=8,
            temperature=0,
            messages=[{"role": "user", "content": PROBE_PROMPT}],
        )
        lat = (time.monotonic() - t0) * 1000
        reply = resp.choices[0].message.content.strip() if resp.choices else ""
        return ProbeResult(
            name=name, ok=True, latency_ms=lat,
            detail=f"model={model_id}  reply={reply!r}",
        )
    except Exception as exc:
        return ProbeResult(name=name, ok=False, error=str(exc)[:120])


# ── PostgreSQL + pgvector probe ───────────────────────────────────────────────

async def probe_postgres() -> list[ProbeResult]:
    results: list[ProbeResult] = []
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        results.append(ProbeResult(name="PostgreSQL/connect", ok=False, error="DATABASE_URL not set"))
        return results

    # asyncpg uses its own DSN format — strip the +asyncpg driver hint
    raw_dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")

    try:
        import asyncpg  # type: ignore
        t0 = time.monotonic()
        conn = await asyncpg.connect(dsn=raw_dsn)
        lat = (time.monotonic() - t0) * 1000
        pg_ver = await conn.fetchval("SELECT version()")
        results.append(ProbeResult(
            name="PostgreSQL/connect", ok=True, latency_ms=lat,
            detail=str(pg_ver)[:80],
        ))

        # pgvector extension check
        vec_installed = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"
        )
        if vec_installed:
            results.append(ProbeResult(name="PostgreSQL/pgvector", ok=True,
                                       detail="vector extension present"))
        else:
            results.append(ProbeResult(name="PostgreSQL/pgvector", ok=False,
                                       error="pgvector extension NOT installed — run: CREATE EXTENSION vector"))

        # schema check — do our tables exist?
        for table in ("documents", "document_chunks", "cost_log"):
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=$1)",
                table,
            )
            results.append(ProbeResult(
                name=f"PostgreSQL/table:{table}",
                ok=bool(exists),
                detail="exists" if exists else "",
                error="" if exists else f"Table '{table}' missing — run migrations",
            ))

        # hybrid_search function check
        fn_exists = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'hybrid_search')"
        )
        results.append(ProbeResult(
            name="PostgreSQL/hybrid_search()",
            ok=bool(fn_exists),
            detail="function present" if fn_exists else "",
            error="" if fn_exists else "hybrid_search() function missing — run migration 0005",
        ))

        await conn.close()
    except Exception as exc:
        results.append(ProbeResult(name="PostgreSQL/connect", ok=False, error=str(exc)[:120]))

    return results


# ── Voyage AI probe ───────────────────────────────────────────────────────────

async def probe_voyage() -> ProbeResult:
    api_key = os.environ.get("VOYAGE_API_KEY", "")
    if not api_key:
        return ProbeResult(name="Voyage/embed", ok=False, error="VOYAGE_API_KEY not set in .env")
    try:
        import voyageai  # type: ignore
        client = voyageai.AsyncClient(api_key=api_key)
        t0 = time.monotonic()
        result = await client.embed(["connectivity probe"], model="voyage-large-2")
        lat = (time.monotonic() - t0) * 1000
        dim = len(result.embeddings[0]) if result.embeddings else 0
        ok = dim == 1536
        return ProbeResult(
            name="Voyage/embed",
            ok=ok,
            latency_ms=lat,
            detail=f"dim={dim} (expected 1536)",
            error="" if ok else f"Unexpected embedding dimension: {dim}",
        )
    except Exception as exc:
        return ProbeResult(name="Voyage/embed", ok=False, error=str(exc)[:120])


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> int:
    report = Report()

    # OpenRouter models (run concurrently)
    or_tasks = [probe_openrouter_model(k, label) for k, label in OPENROUTER_MODELS]
    or_results = await asyncio.gather(*or_tasks)
    for r in or_results:
        report.add(r)

    # Voyage
    report.add(await probe_voyage())

    # PostgreSQL
    pg_results = await probe_postgres()
    for r in pg_results:
        report.add(r)

    report.print_table()
    print(json.dumps(report.to_json(), indent=2))

    return 0 if all(r.ok for r in report.results) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
