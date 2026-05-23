"""Domain 9 — Budget & Commercial: Integration stubs.

T-BUD-01: IntentClassifier cost recorded in Redis after turn.
T-BUD-02: Costs from 5 turns accumulate via INCRBYFLOAT.
T-BUD-03: Budget Redis key TTL is exactly 7 days after last write.
T-BUD-04: Redis unavailable → pipeline completes; cost recorded as 0.0.
T-BUD-05: cost_usd in SSE complete event matches sum of all LLM calls in turn.
T-INT-10: Python → Redis: BudgetTracker.record() increments key; TTL is 7 days.

Requires: Redis + Python service (Docker Compose).
Run with: pytest -m integration
"""
import pytest


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Redis + running services. Run with: pytest -m integration")
async def test_bud_01_intent_classifier_cost_recorded_in_redis_after_turn():
    """
    T-BUD-01: After a full pipeline turn, the LLM cost for the intent classifier
    call must be recorded in Redis under the session budget key.
    """
    raise NotImplementedError("Integration test — requires Redis + Python service.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Redis + running services. Run with: pytest -m integration")
async def test_bud_02_costs_from_five_turns_accumulate_correctly():
    """
    T-BUD-02: Running 5 turns, each with a known LLM cost, the Redis budget key
    must accumulate to the sum of all 5 turn costs (INCRBYFLOAT precision).
    """
    raise NotImplementedError("Integration test — requires Redis.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Redis + running services. Run with: pytest -m integration")
async def test_bud_03_budget_redis_key_ttl_is_seven_days():
    """
    T-BUD-03: After the last BudgetTracker.record() call, the Redis key TTL
    must be exactly 7 days (604 800 seconds ± 2 s tolerance for test timing).
    """
    raise NotImplementedError("Integration test — requires Redis.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Redis + running services. Run with: pytest -m integration")
async def test_bud_04_pipeline_completes_when_redis_unavailable():
    """
    T-BUD-04: When Redis is unreachable, the pipeline must still complete
    successfully. The TurnComplete SSE event cost_usd field must be 0.0.
    """
    raise NotImplementedError("Integration test — requires Redis unavailable scenario.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires full stack + SSE client. Run with: pytest -m integration")
async def test_bud_05_sse_complete_cost_matches_sum_of_llm_calls():
    """
    T-BUD-05: The cost_usd field in the SSE 'complete' event must equal the sum
    of all individual LLM call costs recorded during that turn.
    """
    raise NotImplementedError("Integration test — requires full stack + SSE parsing.")


@pytest.mark.integration
@pytest.mark.skip(reason="Requires Redis. Run with: pytest -m integration")
async def test_int_10_budget_tracker_record_increments_redis_key_with_ttl():
    """
    T-INT-10: BudgetTracker.record() against a real Redis instance must atomically
    increment the budget key using INCRBYFLOAT and set TTL to 7 days.
    """
    raise NotImplementedError("Integration test — requires real Redis instance.")
