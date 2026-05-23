"""Domain 5 & 9 — Code Correctness and Budget tests.

T-CORR-14 (Redis key format), T-BUD-07 (float precision over 200 turns),
T-BUD-08 (load() returns last recorded value), T-BUD-09 (embedding cost tracked).

All tests run in the 'fast' CI mode — Redis is fully mocked.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_orchestration.llm.budget import BudgetTracker, _budget_key
from ai_orchestration.llm.features import BudgetStage


# ─────────────────────────────────────────────────────────────────────────────
# T-CORR-14: Redis key format — budget:{workspace_id}:{session_id}:total_usd
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_corr_14_budget_key_format_with_workspace():
    """
    T-CORR-14a: _budget_key() with both session_id and workspace_id must produce
    the canonical key format: budget:{workspace_id}:{session_id}:total_usd

    EXPECTED: PASS
    """
    key = _budget_key("sess-001", "ws-abc")
    assert key == "budget:ws-abc:sess-001:total_usd", (
        f"Unexpected key format: {key!r}"
    )


@pytest.mark.fast
def test_corr_14b_budget_key_format_without_workspace():
    """
    T-CORR-14b: _budget_key() without workspace_id falls back to:
    budget:{session_id}:total_usd

    EXPECTED: PASS
    """
    key = _budget_key("sess-001", None)
    assert key == "budget:sess-001:total_usd", (
        f"Unexpected fallback key format: {key!r}"
    )


@pytest.mark.fast
def test_corr_14c_budget_key_is_unique_per_session():
    """Different session_ids produce different keys."""
    key_a = _budget_key("sess-001", "ws-1")
    key_b = _budget_key("sess-002", "ws-1")
    assert key_a != key_b


@pytest.mark.fast
def test_corr_14d_budget_key_is_unique_per_workspace():
    """Different workspace_ids produce different keys for the same session."""
    key_a = _budget_key("sess-001", "ws-1")
    key_b = _budget_key("sess-001", "ws-2")
    assert key_a != key_b


# ─────────────────────────────────────────────────────────────────────────────
# T-BUD-07: 200 turns — no float overflow; precision ≤ 0.001 USD
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_bud_07_two_hundred_turns_no_overflow_and_precision():
    """
    T-BUD-07: Accumulating costs from 200 simulated turns must not overflow
    and the total must be accurate to within 0.001 USD.

    Each turn costs a fixed $0.0025 (typical Haiku + embedding cost).
    200 turns × $0.0025 = $0.50 expected total.

    EXPECTED: PASS
    """
    tracker = BudgetTracker(session_id="stress-sess", workspace_id="ws-stress")
    cost_per_turn = 0.0025
    turns = 200

    for _ in range(turns):
        await tracker.record(cost_per_turn)

    expected = cost_per_turn * turns  # 0.50
    assert abs(tracker.spent_usd - expected) <= 0.001, (
        f"Precision error after {turns} turns: "
        f"expected={expected:.6f}, got={tracker.spent_usd:.6f}"
    )


@pytest.mark.fast
async def test_bud_07b_stage_is_normal_at_zero_spend():
    """Fresh tracker reports NORMAL stage."""
    tracker = BudgetTracker(session_id="s", workspace_id="w")
    assert tracker.stage() == BudgetStage.NORMAL
    assert not tracker.is_exhausted()


@pytest.mark.fast
async def test_bud_07c_stage_transitions_at_thresholds():
    """Stage transitions: NORMAL → CAUTION at $3, CRITICAL at $4.50, EXHAUSTED at $5."""
    tracker = BudgetTracker(session_id="s", workspace_id="w")

    await tracker.record(2.99)
    assert tracker.stage() == BudgetStage.NORMAL

    await tracker.record(0.01)  # total = $3.00
    assert tracker.stage() == BudgetStage.CAUTION

    await tracker.record(1.50)  # total = $4.50
    assert tracker.stage() == BudgetStage.CRITICAL

    await tracker.record(0.50)  # total = $5.00
    assert tracker.stage() == BudgetStage.EXHAUSTED
    assert tracker.is_exhausted()


# ─────────────────────────────────────────────────────────────────────────────
# T-BUD-08: load() returns the last recorded value from Redis
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_bud_08_load_returns_value_from_redis():
    """
    T-BUD-08: BudgetTracker.load() must read the value from Redis and return
    a tracker whose spent_usd matches the stored value.

    EXPECTED: PASS
    """
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=b"2.3750")  # Redis returns bytes

    tracker = await BudgetTracker.load(
        session_id="sess-999",
        redis=mock_redis,
        workspace_id="ws-abc",
    )

    assert abs(tracker.spent_usd - 2.375) < 1e-9, (
        f"Expected spent_usd=2.375, got {tracker.spent_usd}"
    )
    mock_redis.get.assert_called_once_with("budget:ws-abc:sess-999:total_usd")


@pytest.mark.fast
async def test_bud_08b_load_returns_zero_when_key_missing():
    """load() returns 0.0 when the Redis key does not exist (returns None)."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    tracker = await BudgetTracker.load(
        session_id="new-sess",
        redis=mock_redis,
    )

    assert tracker.spent_usd == 0.0


@pytest.mark.fast
async def test_bud_08c_load_returns_zero_when_redis_unavailable():
    """load() falls back to 0.0 if Redis raises any exception."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis unreachable"))

    tracker = await BudgetTracker.load(
        session_id="sess-fail",
        redis=mock_redis,
    )

    assert tracker.spent_usd == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# T-BUD-09: Embedding cost tracked and included in turn total
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
async def test_bud_09_embedding_cost_recorded_via_tracker():
    """
    T-BUD-09: After a document embedding call, the embedding cost must be
    recorded in the BudgetTracker and reflected in spent_usd.

    Uses google/gemini-embedding-001 pricing: $0.15 / 1M tokens.
    A 512-token chunk costs $0.15 * 512 / 1_000_000 ≈ $0.0000768.

    EXPECTED: PASS
    """
    tracker = BudgetTracker(session_id="embed-sess", workspace_id="ws-embed")

    # Simulate embedding cost for 5 chunks of 512 tokens each
    tokens_per_chunk = 512
    chunk_count = 5
    price_per_million = 0.15
    cost_per_chunk = price_per_million * tokens_per_chunk / 1_000_000
    total_embedding_cost = cost_per_chunk * chunk_count

    await tracker.record(total_embedding_cost)

    expected = total_embedding_cost
    assert abs(tracker.spent_usd - expected) < 1e-9, (
        f"Embedding cost not recorded correctly: "
        f"expected={expected:.8f}, got={tracker.spent_usd:.8f}"
    )
    assert tracker.stage() == BudgetStage.NORMAL  # far below caution threshold


@pytest.mark.fast
async def test_bud_09b_record_persists_to_redis_when_available():
    """record() must call redis.incrbyfloat and redis.expire when Redis is provided."""
    mock_redis = AsyncMock()
    mock_redis.incrbyfloat = AsyncMock(return_value=0.0025)
    mock_redis.expire = AsyncMock()

    tracker = BudgetTracker(session_id="sess-r", workspace_id="ws-r")
    await tracker.record(0.0025, redis=mock_redis)

    mock_redis.incrbyfloat.assert_called_once()
    call_args = mock_redis.incrbyfloat.call_args
    assert call_args.args[0] == "budget:ws-r:sess-r:total_usd"
    assert abs(call_args.args[1] - 0.0025) < 1e-9

    # TTL set to 7 days
    mock_redis.expire.assert_called_once()
    ttl_args = mock_redis.expire.call_args.args
    assert ttl_args[1] == 7 * 24 * 3600


@pytest.mark.fast
async def test_bud_09c_record_completes_when_redis_unavailable():
    """record() must not raise when Redis is unavailable — in-memory counter still updates."""
    mock_redis = AsyncMock()
    mock_redis.incrbyfloat = AsyncMock(side_effect=ConnectionError("Redis down"))
    mock_redis.expire = AsyncMock()

    tracker = BudgetTracker(session_id="sess-fail", workspace_id="ws-fail")
    await tracker.record(0.005, redis=mock_redis)

    assert abs(tracker.spent_usd - 0.005) < 1e-9  # in-memory still updated
