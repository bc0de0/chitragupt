"""asyncpg connection pool — process-level singleton.

Initialised once at service startup via init_pool() and shared across all
concurrent requests. The pool applies the app.tenant_id GUC for RLS on
every acquired connection — callers set it per-query with SET LOCAL.
"""
from __future__ import annotations

import logging
import os

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool(dsn: str | None = None, min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    """Initialise the global pool. Call once at service startup."""
    global _pool
    if _pool is not None:
        return _pool
    dsn = dsn or os.environ["DATABASE_URL"]
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=10.0,
        server_settings={"application_name": "chitragupt-orchestration"},
    )
    logger.info("asyncpg pool ready (min=%d max=%d)", min_size, max_size)
    return _pool


async def get_pool() -> asyncpg.Pool:
    """Return the global pool, initialising it from DATABASE_URL if needed."""
    global _pool
    if _pool is None:
        await init_pool()
    return _pool  # type: ignore[return-value]


async def close_pool() -> None:
    """Gracefully close the pool. Call at service shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("asyncpg pool closed")
