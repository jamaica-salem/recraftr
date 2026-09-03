"""Advanced AI Security, Circuit Breaker, Rate Limiter & Accounting Test Suite."""

import pytest
import time
import asyncio
from ai_security import (
    CircuitBreaker,
    AIRateLimiter,
    InFlightDeduplicator,
    estimate_tokens,
    calculate_cost_usd,
    record_ai_telemetry,
)


def test_circuit_breaker_state_transitions():
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=0.2)
    assert cb.state == "CLOSED"
    assert cb.can_execute() is True

    # 2 failures -> remains CLOSED
    cb.record_failure()
    cb.record_failure()
    assert cb.state == "CLOSED"
    assert cb.can_execute() is True

    # 3rd failure -> OPENS
    cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.can_execute() is False

    # Wait for cooldown
    time.sleep(0.25)
    assert cb.can_execute() is True
    assert cb.state == "HALF_OPEN"

    # Success resets to CLOSED
    cb.record_success()
    assert cb.state == "CLOSED"
    assert cb.consecutive_failures == 0


@pytest.mark.anyio
async def test_operation_specific_rate_limits():
    limiter = AIRateLimiter()
    user_id = "test_user_op_rate"
    ip = "192.168.1.50"

    # Analyze operation limit is 5 req/min
    for i in range(5):
        ok, msg = await limiter.check_rate_limits(user_id, ip, "analyze", db=None)
        assert ok is True, f"Request {i+1} failed: {msg}"

    # 6th analyze request exceeds limit
    ok, msg = await limiter.check_rate_limits(user_id, ip, "analyze", db=None)
    assert ok is False
    assert "Rate limit for 'analyze' exceeded" in msg


@pytest.mark.anyio
async def test_short_window_burst_protection():
    limiter = AIRateLimiter()
    user_id = "test_user_burst"
    ip = "10.0.0.1"

    # Temporarily set burst_10s to 2 for testing
    from ai_security import OPERATION_CONFIGS
    orig_burst = OPERATION_CONFIGS["analyze"]["burst_10s"]
    OPERATION_CONFIGS["analyze"]["burst_10s"] = 2
    try:
        ok1, _ = await limiter.check_rate_limits(user_id, ip, "analyze", db=None)
        ok2, _ = await limiter.check_rate_limits(user_id, ip, "analyze", db=None)
        assert ok1 is True and ok2 is True

        # 3rd rapid request triggers burst limit
        ok3, msg3 = await limiter.check_rate_limits(user_id, ip, "analyze", db=None)
        assert ok3 is False
        assert "Burst rate limit" in msg3
    finally:
        OPERATION_CONFIGS["analyze"]["burst_10s"] = orig_burst


def test_token_accounting_and_cost_estimation():
    text = "A" * 400  # ~100 tokens
    assert estimate_tokens(text) == 100

    # Gemini cost calculation
    cost_gemini = calculate_cost_usd("gemini", prompt_tokens=1000, completion_tokens=1000)
    assert cost_gemini == pytest.approx(0.000375, rel=1e-3)

    # Groq cost calculation
    cost_groq = calculate_cost_usd("groq", prompt_tokens=1000, completion_tokens=1000)
    assert cost_groq == pytest.approx(0.0005, rel=1e-3)


def test_in_flight_deduplication():
    dedup = InFlightDeduplicator()
    key1 = dedup.get_key("user_123", "optimize", "sample resume payload text")
    key2 = dedup.get_key("user_123", "optimize", "sample resume payload text")
    key3 = dedup.get_key("user_123", "optimize", "different payload text")

    assert key1 == key2
    assert key1 != key3
