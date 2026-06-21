"""In-process async job queue.

Caller hits an endpoint with `async_job=true` (or omits both
`output_path`/`output_url`) → server schedules the work in a background
asyncio task and returns 202 + job_id immediately. Caller polls
`GET /v1/jobs/{job_id}` for status + result.

This is the minimal v0.2.0 surface. For production scale, front the API
with `psyb0t/docker-proxq` (Redis-backed job queue) — proxq wraps the
sync route and gives the same job-id semantics from outside, without
this in-process queue. See `~/.claude/rule-details/designing-an-api.md`.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal


_log = logging.getLogger("flickies.jobs")


JobStatus = Literal["pending", "running", "complete", "failed", "cancelled"]


@dataclass
class Job:
    job_id: str
    status: JobStatus = "pending"
    result: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    task: asyncio.Task[None] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }


class JobQueue:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def submit(
        self,
        coro_factory: Callable[[], Awaitable[dict[str, Any]]],
        *,
        webhook_url: str | None = None,
    ) -> Job:
        """Schedule coro_factory() as a background task. Returns the Job stub.

        If webhook_url is set, fires a signed POST with the final job state
        (status + result + error) after the coro completes — see webhooks.py.
        """
        job = Job(job_id=str(uuid.uuid4()))
        async with self._lock:
            self._jobs[job.job_id] = job

        async def _runner() -> None:
            job.started_at = time.time()
            job.status = "running"
            try:
                result = await coro_factory()
            except Exception as e:  # noqa: BLE001
                job.error = {"code": "JOB_FAILED", "message": str(e)}
                job.status = "failed"
                job.finished_at = time.time()
                _log.exception("job failed", extra={"job_id": job.job_id})
            else:
                job.result = result
                job.status = "complete"
                job.finished_at = time.time()
                _log.info(
                    "job complete",
                    extra={
                        "job_id": job.job_id,
                        "wall_secs": (job.finished_at - (job.started_at or job.finished_at)),
                    },
                )
            if webhook_url:
                # Lazy import to avoid pulling httpx into jobs.py at module load.
                from flickies.webhooks import deliver
                asyncio.create_task(deliver(webhook_url, job.to_dict()))

        job.task = asyncio.create_task(_runner())
        return job

    async def get(self, job_id: str) -> Job | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def cancel(self, job_id: str) -> bool:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.task is None:
                return False
            if job.status in ("complete", "failed", "cancelled"):
                return False
            job.task.cancel()
            job.status = "cancelled"
            job.finished_at = time.time()
            return True
