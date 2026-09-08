"""Automated test suite for Phase 17 Background Processing.

Validates:
- Asynchronous job queue execution & state lifecycle
- Concurrency limiting via asyncio.Semaphore
- Execution timeouts (asyncio.wait_for)
- Retry limits and exponential backoff
- Duplicate-job protection (cryptographic deduplication)
- Cancellation of queued jobs
- API endpoints: POST /api/jobs/analyze, GET /api/jobs/{id}, DELETE /api/jobs/{id}, GET /api/jobs
- IDOR isolation between distinct users
"""
import asyncio
import time
import uuid
import pytest
import requests
from job_queue import JobQueue, Job, JobStatus, compute_dedup_key

BASE_URL = "http://localhost:8000"


# ============================================================================
# Unit Tests for JobQueue Engine
# ============================================================================

def test_job_queue_basic_lifecycle():
    """Verify job execution transitions from QUEUED -> PROCESSING -> COMPLETED."""
    async def _run():
        queue = JobQueue(max_concurrency=2)
        executed = False

        async def mock_handler(job: Job):
            nonlocal executed
            await asyncio.sleep(0.05)
            job.progress = 50
            executed = True
            return {"output": f"processed_{job.payload.get('data')}"}

        queue.register_handler("test_task", mock_handler)
        await queue.start(num_workers=2)

        try:
            job = await queue.enqueue(
                job_type="test_task",
                payload={"data": "abc"},
                user_id="user-123",
                timeout_seconds=5.0,
            )
            assert job.status in (JobStatus.QUEUED, JobStatus.PROCESSING)
            assert job.id in queue._jobs

            # Wait for completion
            for _ in range(20):
                if job.status == JobStatus.COMPLETED:
                    break
                await asyncio.sleep(0.05)

            assert job.status == JobStatus.COMPLETED
            assert job.progress == 100
            assert job.result == {"output": "processed_abc"}
            assert job.completed_at is not None
            assert executed is True
        finally:
            await queue.stop()

    asyncio.run(_run())


def test_job_queue_concurrency_limiting():
    """Verify max_concurrency semaphore prevents running more than N tasks at once."""
    async def _run():
        max_concurrency = 2
        queue = JobQueue(max_concurrency=max_concurrency)
        active_concurrent = 0
        max_observed_concurrent = 0
        lock = asyncio.Lock()

        async def slow_handler(job: Job):
            nonlocal active_concurrent, max_observed_concurrent
            async with lock:
                active_concurrent += 1
                if active_concurrent > max_observed_concurrent:
                    max_observed_concurrent = active_concurrent
            await asyncio.sleep(0.15)
            async with lock:
                active_concurrent -= 1
            return {"ok": True}

        queue.register_handler("slow_task", slow_handler)
        await queue.start(num_workers=max_concurrency)

        try:
            jobs = []
            for i in range(5):
                j = await queue.enqueue(
                    job_type="slow_task",
                    payload={"index": i},
                    user_id=f"user-{i}",
                    timeout_seconds=5.0,
                )
                jobs.append(j)

            # Wait for all jobs to complete
            for _ in range(40):
                if all(j.status == JobStatus.COMPLETED for j in jobs):
                    break
                await asyncio.sleep(0.05)

            assert all(j.status == JobStatus.COMPLETED for j in jobs)
            assert max_observed_concurrent <= max_concurrency, (
                f"Observed {max_observed_concurrent} concurrent jobs, exceeded max {max_concurrency}"
            )
        finally:
            await queue.stop()

    asyncio.run(_run())


def test_job_queue_timeout_enforcement():
    """Verify jobs taking longer than timeout_seconds fail cleanly with timeout error."""
    async def _run():
        queue = JobQueue(max_concurrency=2)

        async def infinite_handler(job: Job):
            await asyncio.sleep(5.0)
            return {"done": True}

        queue.register_handler("infinite_task", infinite_handler)
        await queue.start(num_workers=1)

        try:
            job = await queue.enqueue(
                job_type="infinite_task",
                payload={},
                user_id="user-timeout",
                timeout_seconds=0.2,
                max_retries=0,
            )

            for _ in range(25):
                if job.status == JobStatus.FAILED:
                    break
                await asyncio.sleep(0.05)

            assert job.status == JobStatus.FAILED
            assert "timed out" in (job.error or "").lower()
            assert job.completed_at is not None
        finally:
            await queue.stop()

    asyncio.run(_run())


def test_job_queue_retry_mechanism():
    """Verify transiently failing jobs are retried up to max_retries before failing."""
    async def _run():
        queue = JobQueue(max_concurrency=2)
        attempts = 0

        async def flaky_handler(job: Job):
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError(f"Transient network glitch attempt {attempts}")
            return {"recovered": True, "attempts": attempts}

        queue.register_handler("flaky_task", flaky_handler)
        await queue.start(num_workers=1)

        try:
            job = await queue.enqueue(
                job_type="flaky_task",
                payload={"test": "retry"},
                user_id="user-retry",
                timeout_seconds=5.0,
                max_retries=3,
            )

            for _ in range(40):
                if job.status == JobStatus.COMPLETED:
                    break
                await asyncio.sleep(0.1)

            assert job.status == JobStatus.COMPLETED
            assert job.retry_count == 2
            assert job.result == {"recovered": True, "attempts": 3}
        finally:
            await queue.stop()

    asyncio.run(_run())


def test_job_queue_duplicate_protection():
    """Verify duplicate active jobs return the existing job reference instead of duplicating."""
    async def _run():
        queue = JobQueue(max_concurrency=1)

        async def long_handler(job: Job):
            await asyncio.sleep(0.5)
            return {"res": "ok"}

        queue.register_handler("dedup_task", long_handler)
        await queue.start(num_workers=1)

        try:
            user_id = "user-dedup"
            payload = {"param": "value", "id": 42}

            job1 = await queue.enqueue(job_type="dedup_task", payload=payload, user_id=user_id)
            job2 = await queue.enqueue(job_type="dedup_task", payload=payload, user_id=user_id)

            # Must return identical job instance/id
            assert job1.id == job2.id
            assert len([j for j in queue._jobs.values() if j.user_id == user_id]) == 1

            # Different payload should create a distinct job
            job3 = await queue.enqueue(job_type="dedup_task", payload={"param": "other"}, user_id=user_id)
            assert job3.id != job1.id
        finally:
            await queue.stop()

    asyncio.run(_run())


def test_job_queue_cancellation():
    """Verify queued jobs can be cancelled before execution."""
    async def _run():
        queue = JobQueue(max_concurrency=1)

        async def blocker_handler(job: Job):
            await asyncio.sleep(0.4)
            return {"done": True}

        queue.register_handler("blocker", blocker_handler)
        await queue.start(num_workers=1)

        try:
            # Fill the worker with job 1
            job1 = await queue.enqueue(job_type="blocker", payload={"n": 1}, user_id="u1")
            # Job 2 is queued waiting for worker
            job2 = await queue.enqueue(job_type="blocker", payload={"n": 2}, user_id="u1")

            # Cancel job 2
            cancelled = await queue.cancel_job(job2.id, user_id="u1")
            assert cancelled is True
            assert job2.status == JobStatus.CANCELLED

            # Cannot cancel from another user
            job3 = await queue.enqueue(job_type="blocker", payload={"n": 3}, user_id="u1")
            wrong_user_cancel = await queue.cancel_job(job3.id, user_id="u_attacker")
            assert wrong_user_cancel is False
        finally:
            await queue.stop()

    asyncio.run(_run())


# ============================================================================
# API Endpoint Integration Tests
# ============================================================================

def _register_user(email_prefix: str, password: str = "TestPassword123!") -> str:
    email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com"
    resp = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": email, "password": password, "name": "Test User"},
        timeout=10,
    )
    if resp.status_code == 200:
        return resp.json()["token"]
    login = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    return login.json()["token"]


def test_api_jobs_enqueue_poll_and_idor():
    """Test POST /api/jobs/analyze, GET /api/jobs/{id}, list, and IDOR protection."""
    token_a = _register_user("job_user_a")
    token_b = _register_user("job_user_b")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    sample_resume = (
        "John Doe - Senior Software Engineer\n"
        "Experience: 8 years Python, FastAPI, PostgreSQL, Kubernetes, AWS.\n"
        "Skills: Distributed Systems, Asynchronous Queues, System Architecture."
    )
    sample_jd = (
        "We are looking for a Senior Software Engineer with deep expertise in Python, "
        "FastAPI, async architectures, and distributed systems. 5+ years experience required."
    )

    # 1. Enqueue job as User A
    enqueue_resp = requests.post(
        f"{BASE_URL}/api/jobs/analyze",
        headers=headers_a,
        json={
            "resume_text": sample_resume,
            "job_title": "Senior Software Engineer",
            "job_description": sample_jd,
        },
        timeout=10,
    )
    assert enqueue_resp.status_code == 200
    job_data = enqueue_resp.json()
    job_id = job_data["id"]
    assert job_data["status"] in ("queued", "processing", "completed")
    assert job_data["job_type"] == "analyze_resume"

    # 2. Poll job status as User A
    poll_resp = requests.get(f"{BASE_URL}/api/jobs/{job_id}", headers=headers_a, timeout=10)
    assert poll_resp.status_code == 200
    poll_data = poll_resp.json()
    assert poll_data["id"] == job_id
    assert "status" in poll_data

    # 3. IDOR Defense: User B MUST NOT be able to view User A's job
    idor_poll = requests.get(f"{BASE_URL}/api/jobs/{job_id}", headers=headers_b, timeout=10)
    assert idor_poll.status_code == 404, "User B accessed User A's background job (IDOR violation)"

    # 4. IDOR Defense: User B MUST NOT be able to cancel User A's job
    idor_cancel = requests.delete(f"{BASE_URL}/api/jobs/{job_id}", headers=headers_b, timeout=10)
    assert idor_cancel.status_code == 404, "User B cancelled User A's background job (IDOR violation)"

    # 5. List jobs for User A
    list_resp = requests.get(f"{BASE_URL}/api/jobs", headers=headers_a, timeout=10)
    assert list_resp.status_code == 200
    user_jobs = list_resp.json()["jobs"]
    assert any(j["id"] == job_id for j in user_jobs)

    # 6. User B's list should not include User A's jobs
    list_b_resp = requests.get(f"{BASE_URL}/api/jobs", headers=headers_b, timeout=10)
    assert list_b_resp.status_code == 200
    assert not any(j["id"] == job_id for j in list_b_resp.json()["jobs"])
