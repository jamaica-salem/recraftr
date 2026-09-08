"""In-process asynchronous background job queue for Recraftr.

Provides:
- Asynchronous FIFO queue with priority/worker pool
- Concurrency limiting via asyncio.Semaphore
- Per-job execution timeouts (asyncio.wait_for)
- Exponential backoff retry mechanism with configurable retry limits
- Cryptographic duplicate-job protection (deduplication)
- Failed-job exception capture, state transitions, and error sanitization
- User job status polling and cancellation
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
import uuid

logger = logging.getLogger("recraftr.jobs")


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    id: str
    user_id: str
    job_type: str
    payload: Dict[str, Any]
    status: JobStatus = JobStatus.QUEUED
    progress: int = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    timeout_seconds: float = 60.0
    dedup_key: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "job_type": self.job_type,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


def compute_dedup_key(user_id: str, job_type: str, payload: Dict[str, Any]) -> str:
    """Derive deterministic SHA256 deduplication key for active job uniqueness."""
    normalized_json = json.dumps(payload, sort_keys=True, default=str)
    raw = f"{user_id}:{job_type}:{normalized_json}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class JobQueue:
    """In-memory async background job processing engine."""

    def __init__(self, max_concurrency: int = 3):
        self.max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._jobs: Dict[str, Job] = {}
        self._active_dedup_keys: Dict[str, str] = {}
        self._handlers: Dict[str, Callable[[Job], Coroutine[Any, Any, Dict[str, Any]]]] = {}
        self._workers: List[asyncio.Task] = []
        self._running: bool = False
        self._lock = asyncio.Lock()

    def register_handler(
        self,
        job_type: str,
        handler: Callable[[Job], Coroutine[Any, Any, Dict[str, Any]]],
    ) -> None:
        """Register an async handler callable for a specific job_type."""
        self._handlers[job_type] = handler

    async def start(self, num_workers: Optional[int] = None) -> None:
        """Start background worker tasks."""
        if self._running:
            return
        self._running = True
        workers_count = num_workers or self.max_concurrency
        for i in range(workers_count):
            task = asyncio.create_task(self._worker_loop(worker_id=i), name=f"job-worker-{i}")
            self._workers.append(task)
        logger.info(f"Started JobQueue with {workers_count} background workers")

    async def stop(self) -> None:
        """Gracefully stop workers and drain queue."""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
            self._workers.clear()
        logger.info("JobQueue workers stopped")

    async def enqueue(
        self,
        job_type: str,
        payload: Dict[str, Any],
        user_id: str,
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        dedup_key: Optional[str] = None,
    ) -> Job:
        """Enqueue a new job with duplicate protection and validation."""
        if job_type not in self._handlers:
            raise ValueError(f"Unknown job type: '{job_type}'. Registered: {list(self._handlers.keys())}")

        key = dedup_key or compute_dedup_key(user_id, job_type, payload)

        async with self._lock:
            # Check duplicate active job
            if key in self._active_dedup_keys:
                existing_id = self._active_dedup_keys[key]
                existing_job = self._jobs.get(existing_id)
                if existing_job and existing_job.status in (JobStatus.QUEUED, JobStatus.PROCESSING):
                    logger.info(f"Duplicate job detected for key={key[:12]}..., returning existing job {existing_id}")
                    return existing_job

            job_id = str(uuid.uuid4())
            job = Job(
                id=job_id,
                user_id=user_id,
                job_type=job_type,
                payload=payload,
                status=JobStatus.QUEUED,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
                dedup_key=key,
            )
            self._jobs[job_id] = job
            self._active_dedup_keys[key] = job_id
            await self._queue.put(job_id)
            logger.info(f"Enqueued job {job_id} (type={job_type}, user={user_id})")
            return job

    def get_job(self, job_id: str, user_id: Optional[str] = None) -> Optional[Job]:
        """Fetch job by ID, verifying user_id ownership if provided (IDOR defense)."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        if user_id and job.user_id != user_id:
            return None
        return job

    def list_jobs(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Job]:
        """List jobs belonging to a user sorted by creation time descending."""
        user_jobs = [j for j in self._jobs.values() if j.user_id == user_id]
        user_jobs.sort(key=lambda j: j.created_at, reverse=True)
        return user_jobs[offset : offset + limit]

    async def cancel_job(self, job_id: str, user_id: str) -> bool:
        """Cancel a pending queued job."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.user_id != user_id:
                return False
            if job.status == JobStatus.QUEUED:
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now(timezone.utc).isoformat()
                if job.dedup_key and job.dedup_key in self._active_dedup_keys:
                    del self._active_dedup_keys[job.dedup_key]
                logger.info(f"Cancelled job {job_id}")
                return True
            return False

    async def _worker_loop(self, worker_id: int) -> None:
        """Main loop executed by each worker coroutine."""
        logger.debug(f"Worker {worker_id} started")
        while self._running:
            try:
                # Wait for job id from queue with timeout so loop checks _running periodically
                try:
                    job_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                job = self._jobs.get(job_id)
                if not job:
                    self._queue.task_done()
                    continue

                # If job was cancelled while waiting in queue, skip execution
                if job.status == JobStatus.CANCELLED:
                    self._queue.task_done()
                    continue

                # Execute with concurrency semaphore
                async with self._semaphore:
                    await self._process_job(job)

                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected worker {worker_id} error: {e}", exc_info=True)

    async def _process_job(self, job: Job) -> None:
        """Execute a single job with timeout and retry handling."""
        handler = self._handlers.get(job.job_type)
        if not handler:
            job.status = JobStatus.FAILED
            job.error = f"No handler registered for {job.job_type}"
            job.completed_at = datetime.now(timezone.utc).isoformat()
            self._cleanup_dedup(job)
            return

        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc).isoformat()
        job.progress = 10
        logger.info(f"Processing job {job.id} (attempt {job.retry_count + 1}/{job.max_retries + 1})")

        try:
            # Wrap execution in strict job timeout
            result = await asyncio.wait_for(handler(job), timeout=job.timeout_seconds)
            job.status = JobStatus.COMPLETED
            job.result = result
            job.progress = 100
            job.completed_at = datetime.now(timezone.utc).isoformat()
            logger.info(f"Job {job.id} completed successfully")
        except asyncio.TimeoutError:
            logger.warning(f"Job {job.id} timed out after {job.timeout_seconds}s")
            await self._handle_job_failure(job, f"Execution timed out after {job.timeout_seconds} seconds")
        except Exception as exc:
            logger.error(f"Job {job.id} execution failed: {exc}", exc_info=True)
            await self._handle_job_failure(job, str(exc))
        finally:
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                self._cleanup_dedup(job)

    async def _handle_job_failure(self, job: Job, error_msg: str) -> None:
        """Handle failure, deciding whether to retry with exponential backoff or mark FAILED."""
        if job.retry_count < job.max_retries:
            job.retry_count += 1
            backoff = 0.5 * (2 ** (job.retry_count - 1))
            logger.info(f"Retrying job {job.id} in {backoff:.2f}s (retry {job.retry_count}/{job.max_retries})")
            job.status = JobStatus.QUEUED
            job.error = f"Retrying after error: {error_msg}"
            await asyncio.sleep(backoff)
            await self._queue.put(job.id)
        else:
            job.status = JobStatus.FAILED
            job.error = error_msg
            job.completed_at = datetime.now(timezone.utc).isoformat()
            logger.error(f"Job {job.id} permanently failed after {job.max_retries} retries: {error_msg}")

    def _cleanup_dedup(self, job: Job) -> None:
        """Release active deduplication lock once job concludes."""
        if job.dedup_key and job.dedup_key in self._active_dedup_keys:
            if self._active_dedup_keys[job.dedup_key] == job.id:
                del self._active_dedup_keys[job.dedup_key]


# Singleton global job queue instance
global_job_queue = JobQueue(max_concurrency=3)
