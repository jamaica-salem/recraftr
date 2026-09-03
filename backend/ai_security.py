"""AI API Security, Rate Limiting, Circuit Breaking, Deduplication, and Cost Accounting module."""

import os
import time
import json
import uuid
import hashlib
import asyncio
import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone

logger = logging.getLogger("recraftr.ai_security")

# ---------------- Environment & Settings ----------------
DAILY_AI_BUDGET_USD = float(os.environ.get("DAILY_AI_BUDGET_USD", "5.00"))
AI_MAX_CONCURRENT_REQUESTS = int(os.environ.get("AI_MAX_CONCURRENT_REQUESTS", "5"))
GLOBAL_IP_LIMIT_PER_MIN = 15

# Operation Specific Configurations & Guardrails
OPERATION_CONFIGS = {
    "analyze": {
        "user_limit_min": 5,
        "user_limit_day": 20,
        "burst_10s": 5,
        "timeout_seconds": 30.0,
        "max_output_tokens": 1500,
    },
    "optimize": {
        "user_limit_min": 3,
        "user_limit_day": 10,
        "burst_10s": 3,
        "timeout_seconds": 45.0,
        "max_output_tokens": 2000,
    },
    "cover_letter": {
        "user_limit_min": 3,
        "user_limit_day": 10,
        "burst_10s": 3,
        "timeout_seconds": 30.0,
        "max_output_tokens": 1500,
    },
    "rewrite_bullet": {
        "user_limit_min": 10,
        "user_limit_day": 50,
        "burst_10s": 10,
        "timeout_seconds": 20.0,
        "max_output_tokens": 500,
    },
}

DEFAULT_OP_CONFIG = {
    "user_limit_min": 5,
    "user_limit_day": 20,
    "burst_10s": 3,
    "timeout_seconds": 30.0,
    "max_output_tokens": 1500,
}


# ---------------- Circuit Breaker ----------------
class CircuitBreaker:
    """In-process Circuit Breaker for AI Primary Provider (Gemini)."""

    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.consecutive_failures = 0
        self.last_state_change = time.time()

    def can_execute(self) -> bool:
        now = time.time()
        if self.state == "OPEN":
            if now - self.last_state_change > self.cooldown_seconds:
                self.state = "HALF_OPEN"
                self.last_state_change = now
                logger.info("Circuit Breaker transitioned OPEN -> HALF_OPEN (testing primary provider)")
                return True
            return False
        return True

    def record_success(self):
        if self.state != "CLOSED":
            logger.info("Circuit Breaker state reset HALF_OPEN/OPEN -> CLOSED")
        self.state = "CLOSED"
        self.consecutive_failures = 0

    def record_failure(self):
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            if self.state != "OPEN":
                logger.warning("Circuit Breaker OPENED! (%d consecutive failures). Cooldown: %.1fs", self.consecutive_failures, self.cooldown_seconds)
            self.state = "OPEN"
            self.last_state_change = time.time()


gemini_circuit_breaker = CircuitBreaker()


# ---------------- Rate Limiter & Rate State ----------------
class AIRateLimiter:
    def __init__(self):
        self._ip_history: Dict[str, list] = {}
        self._user_min_history: Dict[str, list] = {}
        self._user_burst_history: Dict[str, list] = {}

    def _clean_window(self, timestamps: list, window_seconds: float) -> list:
        now = time.time()
        return [t for t in timestamps if now - t < window_seconds]

    async def check_rate_limits(
        self, user_id: str, client_ip: str, operation: str, db
    ) -> Tuple[bool, str]:
        now = time.time()
        op_cfg = OPERATION_CONFIGS.get(operation, DEFAULT_OP_CONFIG)

        # 1. Global IP Rate Limit (15 req/min)
        if client_ip:
            ip_times = self._clean_window(self._ip_history.get(client_ip, []), 60.0)
            if len(ip_times) >= GLOBAL_IP_LIMIT_PER_MIN:
                return False, f"IP rate limit exceeded ({GLOBAL_IP_LIMIT_PER_MIN} req/min). Please try again shortly."
            ip_times.append(now)
            self._ip_history[client_ip] = ip_times

        # 2. Per-User Per-Operation Minute Limit
        user_op_key = f"{user_id}:{operation}"
        user_times = self._clean_window(self._user_min_history.get(user_op_key, []), 60.0)
        if len(user_times) >= op_cfg["user_limit_min"]:
            return False, f"Rate limit for '{operation}' exceeded ({op_cfg['user_limit_min']} req/min). Please wait a moment."
        user_times.append(now)
        self._user_min_history[user_op_key] = user_times

        # 3. Short-window Burst Limit (3 req / 10s)
        burst_times = self._clean_window(self._user_burst_history.get(user_op_key, []), 10.0)
        if len(burst_times) >= op_cfg["burst_10s"]:
            return False, f"Burst rate limit exceeded for '{operation}' ({op_cfg['burst_10s']} req / 10s). Please slow down."
        burst_times.append(now)
        self._user_burst_history[user_op_key] = burst_times

        # 4. Daily Operation Count in DB
        if db is not None:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            daily_key = f"daily_ai_{user_id}_{today_str}_{operation}"
            daily_doc = await db.ai_usage_counters.find_one({"id": daily_key})
            count = daily_doc.get("count", 0) if daily_doc else 0
            if count >= op_cfg["user_limit_day"]:
                return False, f"Daily limit reached for '{operation}' ({op_cfg['user_limit_day']} req/day)."

            # 5. Global Daily Spend USD Budget Check
            budget_doc = await db.ai_usage_counters.find_one({"id": f"global_spend_{today_str}"})
            total_spend = budget_doc.get("total_spend_usd", 0.0) if budget_doc else 0.0
            if total_spend >= DAILY_AI_BUDGET_USD:
                return False, "Global daily AI budget reached for today. Operations will resume tomorrow."

        return True, "Allowed"

    async def increment_daily_usage(self, user_id: str, operation: str, estimated_cost_usd: float, db):
        if db is None:
            return
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_key = f"daily_ai_{user_id}_{today_str}_{operation}"
        await db.ai_usage_counters.update_one(
            {"id": daily_key},
            {"$inc": {"count": 1}, "$set": {"user_id": user_id, "date": today_str, "operation": operation}},
            upsert=True,
        )
        if estimated_cost_usd > 0:
            await db.ai_usage_counters.update_one(
                {"id": f"global_spend_{today_str}"},
                {"$inc": {"total_spend_usd": estimated_cost_usd}, "$set": {"date": today_str}},
                upsert=True,
            )


ai_rate_limiter = AIRateLimiter()


# ---------------- In-Flight Request Deduplicator ----------------
class InFlightDeduplicator:
    def __init__(self):
        self._in_flight: Dict[str, asyncio.Task] = {}

    def get_key(self, user_id: str, operation: str, input_payload: str) -> str:
        h = hashlib.sha256(input_payload.encode("utf-8")).hexdigest()[:16]
        return f"{user_id}:{operation}:{h}"

    def is_in_flight(self, key: str) -> bool:
        return key in self._in_flight and not self._in_flight[key].done()

    def set_task(self, key: str, task: asyncio.Task):
        self._in_flight[key] = task
        def _clear(_):
            self._in_flight.pop(key, None)
        task.add_done_callback(_clear)


ai_deduplicator = InFlightDeduplicator()


# ---------------- Token Accounting & Telemetry ----------------
def estimate_tokens(text: str) -> int:
    """Estimate token count (approx 4 chars per token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def calculate_cost_usd(provider: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate estimated API cost in USD based on provider pricing."""
    p_lower = (provider or "").lower()
    if "gemini" in p_lower:
        # Gemini Flash pricing: ~$0.000075 / 1K prompt tokens, $0.0003 / 1K completion tokens
        return (prompt_tokens * 0.000075 / 1000) + (completion_tokens * 0.0003 / 1000)
    elif "groq" in p_lower:
        # Groq Llama/GPT OSS pricing: ~$0.0001 / 1K prompt tokens, $0.0004 / 1K completion tokens
        return (prompt_tokens * 0.0001 / 1000) + (completion_tokens * 0.0004 / 1000)
    return 0.0001  # Default fallback cost estimate


async def record_ai_telemetry(
    db,
    user_id: str,
    operation: str,
    provider: str,
    model: str,
    prompt_text: str,
    output_text: str,
    latency_ms: float,
    status: str = "success",
    error_type: Optional[str] = None,
    request_id: Optional[str] = None,
):
    if not request_id:
        request_id = f"ai_req_{uuid.uuid4().hex[:12]}"

    prompt_tokens = estimate_tokens(prompt_text)
    output_tokens = estimate_tokens(output_text)
    total_tokens = prompt_tokens + output_tokens
    cost_usd = calculate_cost_usd(provider, prompt_tokens, output_tokens)

    log_entry = {
        "request_id": request_id,
        "user_id": user_id,
        "operation": operation,
        "provider": provider,
        "model": model,
        "input_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(cost_usd, 6),
        "latency_ms": round(latency_ms, 2),
        "status": status,
        "error_type": error_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if db is not None:
        try:
            await db.ai_usage_logs.insert_one(log_entry)
            await ai_rate_limiter.increment_daily_usage(user_id, operation, cost_usd, db)
        except Exception as e:
            logger.error("Failed to persist AI telemetry log: %s", e)

    return log_entry
