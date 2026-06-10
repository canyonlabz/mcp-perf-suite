"""Background task runner for the A2A server (V2 doc Section 14).

Owns the lifecycle of an `agent_tasks` row from `pending` through one of the
terminal states (`completed`, `failed`, `cancelled`). Three things are
implemented here:

  1. **State-transition publication.** While a task runs, every status change
     is broadcast to in-process subscribers (`subscribe()` / `unsubscribe()`)
     so the SSE endpoint can stream events to the caller without polling
     the database.

  2. **Webhook delivery.** When a task reaches a terminal state, every URL
     in `agent_tasks.subscriber_endpoints` receives a `POST` of the final
     status payload. Three retries with exponential backoff (per V2
     Section 14.2). Webhook failures are logged but do not change the task
     status - the task is still authoritatively `completed` in the DB.

  3. **Stub agent execution.** Until F3.7+ wires real AG2 agents behind
     these endpoints, the executor runs a small simulated workflow:
     `pending -> running -> completed` with a 3-second total runtime and a
     deterministic `{"echo": payload, "stub": true, ...}` result. This is
     enough to exercise all three callback patterns end-to-end and let
     external A2A clients integrate against a real wire shape early.

When F3.7 lands, the `_run_stub_agent()` function is replaced with a real
dispatch into AG2's `ConversableAgent`, but everything else (DB writes,
SSE broadcast, webhook delivery, retry policy) stays the same.

Heavy imports (`httpx`, `asyncpg` via task_store) are reached only inside
the dispatch coroutine so this module imports cleanly in environments
without those packages.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from . import task_store

log = logging.getLogger(__name__)

WEBHOOK_RETRY_ATTEMPTS = 3
WEBHOOK_BACKOFF_BASE_SECONDS = 1.0
WEBHOOK_TIMEOUT_SECONDS = 15.0
STUB_TOTAL_RUNTIME_SECONDS = 3.0


@dataclass
class TaskEvent:
    """One state-transition snapshot delivered to in-process subscribers.

    Mirrors the shape we will send over SSE in the A2A
    `tasks/sendSubscribe` endpoint. Includes both IDs from V2 Section 4.3
    so SSE consumers can correlate to the broader session.
    """

    task_id: str
    session_id: Optional[str]
    external_session_id: Optional[str]
    agent_name: str
    status: str
    progress: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[dict] = None
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_sse_data(self) -> str:
        """Render a JSON line suitable for an SSE `data:` field."""
        return json.dumps(asdict(self))


# =============================================================================
# Subscription bus (in-process)
# =============================================================================
# Each task_id maps to a list of asyncio.Queue subscribers. SSE consumers
# subscribe before submitting the task (or right after) and unsubscribe on
# disconnect. This is intentionally in-process - cross-process pub/sub is an
# Epic 4 concern (Redis / Postgres LISTEN / etc.).

_subscribers: dict[UUID, list[asyncio.Queue]] = {}
_subscribers_lock = asyncio.Lock()


async def subscribe(task_id: UUID) -> asyncio.Queue:
    """Register a queue for state events on `task_id`. Returns the queue."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    async with _subscribers_lock:
        _subscribers.setdefault(task_id, []).append(queue)
    return queue


async def unsubscribe(task_id: UUID, queue: asyncio.Queue) -> None:
    """Remove a queue from the subscriber list. Safe to call twice."""
    async with _subscribers_lock:
        queues = _subscribers.get(task_id)
        if queues and queue in queues:
            queues.remove(queue)
        if queues is not None and not queues:
            _subscribers.pop(task_id, None)


async def _broadcast(task_id: UUID, event: TaskEvent) -> None:
    """Push `event` to every queue subscribed to `task_id`. Drops on full queue."""
    async with _subscribers_lock:
        queues = list(_subscribers.get(task_id, ()))
    for queue in queues:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            log.warning("Dropping SSE event for task %s; subscriber queue full", task_id)


# =============================================================================
# Public API
# =============================================================================

async def execute_task(task_id: UUID) -> None:
    """Run the task end-to-end. Schedule with `asyncio.create_task(...)`."""
    task = await task_store.get_task(task_id)
    if task is None:
        log.error("execute_task: task %s not found", task_id)
        return

    if task.status in task_store.TERMINAL_STATUSES:
        log.info("execute_task: task %s already terminal (%s); nothing to do", task_id, task.status)
        return

    common = dict(
        task_id=str(task.task_id),
        session_id=str(task.session_id) if task.session_id else None,
        external_session_id=task.external_session_id,
        agent_name=task.agent_name,
    )

    try:
        await task_store.mark_running(task.task_id)
        await _broadcast(task.task_id, TaskEvent(status="running", progress="started", **common))
        result = await _run_stub_agent(task, common)
        await task_store.mark_completed(task.task_id, result)
        await _broadcast(task.task_id, TaskEvent(status="completed", result=result, **common))
    except asyncio.CancelledError:
        await task_store.mark_cancelled(task.task_id, reason="execution cancelled")
        await _broadcast(
            task.task_id,
            TaskEvent(status="cancelled", error={"reason": "execution cancelled"}, **common),
        )
        raise
    except Exception as exc:
        log.exception("execute_task: task %s failed", task_id)
        error = {"type": type(exc).__name__, "message": str(exc)}
        await task_store.mark_failed(task.task_id, error)
        await _broadcast(task.task_id, TaskEvent(status="failed", error=error, **common))

    # Reload to get the final terminal row (DB is source of truth) and fan out webhooks.
    final = await task_store.get_task(task.task_id)
    if final is not None and final.subscriber_endpoints:
        await _deliver_webhooks(final)


# =============================================================================
# Stub agent (replaced in F3.7+)
# =============================================================================

async def _run_stub_agent(task: task_store.AgentTask, common: dict) -> dict:
    """Simulate an agent doing work in three phases.

    Replaced in F3.7 by a real AG2 dispatch. The shape of the returned dict
    is the contract that survives the swap.
    """
    phases = (
        ("planning", 1.0),
        ("executing", 1.5),
        ("finalizing", 0.5),
    )
    for phase, delay in phases:
        await asyncio.sleep(delay)
        await _broadcast(task.task_id, TaskEvent(status="running", progress=phase, **common))
    return {
        "stub": True,
        "agent": task.agent_name,
        "echo": task.payload,
        "note": "F3.5 stub executor; replaced by real AG2 dispatch in F3.7+",
    }


# =============================================================================
# Webhook delivery (Pattern 3 from V2 Section 14.2)
# =============================================================================

async def _deliver_webhooks(task: task_store.AgentTask) -> None:
    """POST the final task body to each subscriber URL with retry/backoff."""
    import httpx

    body = {
        "task_id": str(task.task_id),
        "session_id": str(task.session_id) if task.session_id else None,
        "external_session_id": task.external_session_id,
        "agent_name": task.agent_name,
        "status": task.status,
        "result": task.result,
        "error": task.error,
        "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }

    async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_SECONDS) as client:
        for url in task.subscriber_endpoints or []:
            await _post_with_retry(client, url, body, task.task_id)


async def _post_with_retry(client: Any, url: str, body: dict, task_id: UUID) -> None:
    delay = WEBHOOK_BACKOFF_BASE_SECONDS
    for attempt in range(1, WEBHOOK_RETRY_ATTEMPTS + 1):
        try:
            response = await client.post(url, json=body, headers={"X-Task-Id": str(task_id)})
            if response.status_code < 500:
                # 2xx = success; 4xx = caller's mistake, no point retrying.
                if response.status_code >= 400:
                    log.warning(
                        "Webhook %s returned %d for task %s; not retrying (4xx).",
                        url, response.status_code, task_id,
                    )
                else:
                    log.info("Webhook %s delivered task %s (%d).", url, task_id, response.status_code)
                return
            log.warning(
                "Webhook %s returned %d for task %s (attempt %d/%d).",
                url, response.status_code, task_id, attempt, WEBHOOK_RETRY_ATTEMPTS,
            )
        except Exception as exc:
            log.warning(
                "Webhook %s raised %s for task %s (attempt %d/%d): %s",
                url, type(exc).__name__, task_id, attempt, WEBHOOK_RETRY_ATTEMPTS, exc,
            )
        if attempt < WEBHOOK_RETRY_ATTEMPTS:
            await asyncio.sleep(delay)
            delay *= 2  # exponential backoff
    log.error("Webhook %s exhausted %d attempts for task %s.", url, WEBHOOK_RETRY_ATTEMPTS, task_id)
