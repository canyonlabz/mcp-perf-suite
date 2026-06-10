"""CRUD over the `agent_tasks` table.

Tasks are the per-A2A-call records that back the three long-running task
patterns from V2 doc Section 14 (poll, SSE, webhook). One row per
`tasks/send` invocation, lifecycle states `pending -> running -> completed
| failed | cancelled`.

Mirrors the shape and lazy-import philosophy of `session_store.py`. Heavier
helpers (cancel, list-by-session, retention sweeps) are added as later
Features need them.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from . import db

log = logging.getLogger(__name__)

VALID_STATUSES = ("pending", "running", "completed", "failed", "cancelled")
TERMINAL_STATUSES = ("completed", "failed", "cancelled")


@dataclass
class AgentTask:
    """Materialized view of a row in `agent_tasks`."""

    task_id: UUID
    session_id: UUID
    agent_name: str
    status: str
    payload: dict
    submitted_at: datetime
    updated_at: datetime
    external_session_id: Optional[str] = None
    test_run_id: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[dict] = None
    subscriber_endpoints: list = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


def _coerce_jsonb(value: Any) -> Any:
    """asyncpg returns JSONB as either str (default) or already-decoded dict."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _row_to_task(row: Any) -> AgentTask:
    return AgentTask(
        task_id=row["task_id"],
        session_id=row["session_id"],
        external_session_id=row["external_session_id"],
        agent_name=row["agent_name"],
        status=row["status"],
        test_run_id=row["test_run_id"],
        payload=_coerce_jsonb(row["payload"]) or {},
        result=_coerce_jsonb(row["result"]),
        error=_coerce_jsonb(row["error"]),
        subscriber_endpoints=_coerce_jsonb(row["subscriber_endpoints"]) or [],
        submitted_at=row["submitted_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        updated_at=row["updated_at"],
    )


async def create_task(
    *,
    session_id: UUID,
    agent_name: str,
    payload: dict,
    external_session_id: Optional[str] = None,
    test_run_id: Optional[str] = None,
    subscriber_endpoints: Optional[list[str]] = None,
) -> AgentTask:
    """Insert a new `agent_tasks` row in `pending` state and return it."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO agent_tasks (
                session_id, external_session_id, agent_name, status,
                test_run_id, payload, subscriber_endpoints
            )
            VALUES ($1, $2, $3, 'pending', $4, $5::jsonb, $6::jsonb)
            RETURNING task_id, session_id, external_session_id, agent_name, status,
                      test_run_id, payload, result, error, subscriber_endpoints,
                      submitted_at, started_at, completed_at, updated_at
            """,
            session_id,
            external_session_id,
            agent_name,
            test_run_id,
            json.dumps(payload or {}),
            json.dumps(subscriber_endpoints or []),
        )
    return _row_to_task(row)


async def get_task(task_id: UUID) -> Optional[AgentTask]:
    """Fetch a task by id. Returns None when the row is absent."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT task_id, session_id, external_session_id, agent_name, status,
                   test_run_id, payload, result, error, subscriber_endpoints,
                   submitted_at, started_at, completed_at, updated_at
            FROM agent_tasks
            WHERE task_id = $1
            """,
            task_id,
        )
    return _row_to_task(row) if row is not None else None


async def mark_running(task_id: UUID) -> None:
    """Transition `pending -> running` and stamp `started_at = NOW()`."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE agent_tasks
            SET status = 'running',
                started_at = COALESCE(started_at, NOW()),
                updated_at = NOW()
            WHERE task_id = $1
              AND status = 'pending'
            """,
            task_id,
        )


async def mark_completed(task_id: UUID, result: dict) -> None:
    """Transition any non-terminal task to `completed` with a result body."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE agent_tasks
            SET status = 'completed',
                result = $2::jsonb,
                completed_at = NOW(),
                updated_at = NOW()
            WHERE task_id = $1
              AND status NOT IN ('completed', 'failed', 'cancelled')
            """,
            task_id,
            json.dumps(result or {}),
        )


async def mark_failed(task_id: UUID, error: dict) -> None:
    """Transition any non-terminal task to `failed` with an error body."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE agent_tasks
            SET status = 'failed',
                error = $2::jsonb,
                completed_at = NOW(),
                updated_at = NOW()
            WHERE task_id = $1
              AND status NOT IN ('completed', 'failed', 'cancelled')
            """,
            task_id,
            json.dumps(error or {}),
        )


async def mark_cancelled(task_id: UUID, reason: Optional[str] = None) -> bool:
    """Transition any non-terminal task to `cancelled`. Returns True if changed."""
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE agent_tasks
            SET status = 'cancelled',
                error = $2::jsonb,
                completed_at = NOW(),
                updated_at = NOW()
            WHERE task_id = $1
              AND status NOT IN ('completed', 'failed', 'cancelled')
            """,
            task_id,
            json.dumps({"reason": reason or "cancelled by client"}),
        )
    return result.endswith(" 1")


async def delete_task(task_id: UUID) -> bool:
    """Delete a task row. Returns True when a row was removed.

    Intended for tests and operator clean-up only.
    """
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM agent_tasks WHERE task_id = $1", task_id)
    return result.endswith(" 1")
