"""AG-UI / CopilotKit bridge for PerfPilot Agents (V2 doc Section 10, port 8002).

A separate FastAPI ASGI app from the A2A surface (port 8001). It exists to
support the human-driven HITL experience through a browser-based React UI
built on CopilotKit. The two surfaces deliberately stay in different
processes so:

  - The A2A surface stays minimal and protocol-pure (no UI concerns).
  - The AG-UI surface can carry conversation, session, run, and HITL
    affordances that browsers need (cookies, SSE, CORS).

URL conventions:

  /copilotkit                 - Mounted by the CopilotKit Python SDK in
                                 PBI 3.6.3 (handles chat / runtime forwarding
                                 from the Next.js CopilotKit runtime).
  /api/sessions[/{id}]        - Session info (PBI 3.6.4)
  /api/runs[/{test_run_id}]   - Test-run grouping over agent_tasks (PBI 3.6.6)
  /api/hitl/{approve,reject}  - HITL CRUD over hitl_approvals (PBI 3.6.5)
  /api/events                 - AG-UI SSE event stream from task_executor (PBI 3.6.2)
  /health                     - Liveness probe (this PBI)

Deliberately NOT prefixed with `/api/perfpilot/*`. The shorter `/api/*`
prefix matches industry convention; the brand stays in the front-end
(CopilotKit page title, manifest, etc.), not in the URL.

Run locally:

    cd agent-framework
    python agui_server.py

Or via uvicorn from the agent-framework folder:

    uvicorn agui_server:app --host 0.0.0.0 --port 8002
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from uuid import UUID

if __package__ is None:
    # Allow `python agui_server.py` from inside agent-framework/.
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import asyncio
import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from pydantic import BaseModel, Field

from utils import db, hitl_store, session_store, task_executor, task_store
from utils.session_middleware import SessionMiddleware

log = logging.getLogger(__name__)

FRAMEWORK_DIR = Path(__file__).resolve().parent
SERVER_VERSION = "0.1.0"
SERVER_TITLE = "PerfPilot Agents - AG-UI Bridge"


# =============================================================================
# App lifespan
# =============================================================================

@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Warm the asyncpg pool on startup so the first browser request is fast."""
    log.info("AG-UI bridge starting; warming asyncpg pool")
    try:
        await db.get_pool()
        log.info("AG-UI bridge ready (port=%s)", os.environ.get("AGUI_PORT", "8002"))
    except Exception:
        log.exception(
            "Failed to warm asyncpg pool at startup; routes will retry per request"
        )
    try:
        yield
    finally:
        log.info("AG-UI bridge shutting down; closing asyncpg pool")
        await db.close_pool()


# =============================================================================
# CORS configuration
# =============================================================================
# CORS is permissive by default for local dev. Operators tighten via env
# vars. Epic 4 will move this to `config/agents.yaml -> cors:` and pin a
# strict origin list when running on Azure Container Apps. The Next.js
# frontend in F3.6.7 runs on its own port (3000 by default) so it MUST
# come from a different origin than this server.

def _resolve_cors_origins() -> list[str]:
    raw = os.environ.get("AGUI_CORS_ORIGINS", "").strip()
    if not raw:
        # Common local-dev defaults: Next.js dev server on 3000, Vite on 5173,
        # CRA on 3000, and the bridge itself in case anyone hits it directly.
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    if raw == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


# =============================================================================
# App factory
# =============================================================================

def create_app() -> FastAPI:
    """Build the FastAPI app. Factored out so tests can mount it in-process."""
    app = FastAPI(
        title=SERVER_TITLE,
        version=SERVER_VERSION,
        description="Human-facing surface for PerfPilot Agents (CopilotKit + AG-UI). See V2 doc Section 10.",
        lifespan=_lifespan,
    )

    # CORS first so OPTIONS preflights short-circuit before any session work.
    cors_origins = _resolve_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Session-Id", "X-External-Session-Id"],
    )

    # Session middleware after CORS so preflight requests are not minted as sessions.
    app.add_middleware(SessionMiddleware, default_source="web_ui")

    _register_routes(app)
    return app


# =============================================================================
# Pydantic request shapes (used by route signatures below)
# =============================================================================

class HitlPromptCreate(BaseModel):
    task_id: str
    prompt: dict = Field(default_factory=dict)


class HitlDecision(BaseModel):
    approval_id: int
    feedback: Optional[str] = None
    decided_by: Optional[str] = None


# =============================================================================
# Route registration
# =============================================================================

def _register_routes(app: FastAPI) -> None:
    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "service": "agui", "version": SERVER_VERSION}

    # -- AG-UI SSE event stream (PBI 3.6.2) --------------------------------------
    # Browser clients (typically CopilotKit's React UI) follow a task they
    # already started elsewhere by subscribing to this endpoint with the
    # `task_id`. The same `task_executor` broadcast bus that powers the
    # A2A server's `tasks/sendSubscribe` is reused here - we just translate
    # to the AG-UI envelope and add CORS-friendly heartbeats.
    @app.get("/api/events", tags=["agui"])
    async def stream_events(request: Request, task_id: str) -> EventSourceResponse:
        try:
            task_uuid = UUID(task_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Malformed task_id") from exc

        existing = await task_store.get_task(task_uuid)
        if existing is None:
            raise HTTPException(status_code=404, detail="Task not found")

        async def _stream():
            yield {
                "event": "snapshot",
                "data": json.dumps(_task_to_snapshot_payload(existing)),
            }
            if existing.status in task_store.TERMINAL_STATUSES:
                # Already terminal - one snapshot then close. No need to subscribe.
                return
            queue = await task_executor.subscribe(task_uuid)
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        yield {"event": "ping", "data": "{}"}
                        continue
                    yield {"event": "state", "data": event.to_sse_data()}
                    if event.status in task_store.TERMINAL_STATUSES:
                        break
            finally:
                await task_executor.unsubscribe(task_uuid, queue)

        return EventSourceResponse(_stream())

    # -- Sessions (PBI 3.6.4) ----------------------------------------------------
    @app.get("/api/sessions", tags=["sessions"])
    async def list_sessions_route(
        limit: int = 50,
        offset: int = 0,
        source: Optional[str] = None,
        include_ended: bool = False,
    ) -> dict:
        """Return recent sessions for the browser session picker."""
        sessions = await session_store.list_sessions(
            limit=limit,
            offset=offset,
            source=source,
            include_ended=include_ended,
        )
        return {
            "sessions": [_session_to_dict(s) for s in sessions],
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/sessions/me", tags=["sessions"])
    async def my_session_route(request: Request) -> dict:
        """Return the session attached to the current request by middleware.

        Browsers hit this on first page load to learn their `session_id`
        without needing to send a header. Combined with the `X-Session-Id`
        echo on the response, this is how the React UI bootstraps.
        """
        session_id = getattr(request.state, "session_id", None)
        if session_id is None:
            raise HTTPException(
                status_code=503,
                detail="Session could not be established (perfagent_state unavailable).",
            )
        session = await session_store.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return _session_to_dict(session)

    @app.get("/api/sessions/{session_id}", tags=["sessions"])
    async def get_session_route(session_id: str) -> dict:
        try:
            uuid_value = UUID(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Malformed session_id") from exc
        session = await session_store.get_session(uuid_value)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return _session_to_dict(session)

    # -- Test runs (PBI 3.6.6) ---------------------------------------------------
    @app.get("/api/runs", tags=["runs"])
    async def list_runs_route(limit: int = 50, offset: int = 0) -> dict:
        """Return recent test runs grouped by `test_run_id`."""
        runs = await task_store.list_runs(limit=limit, offset=offset)
        return {
            "runs": [_run_summary_to_dict(r) for r in runs],
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/runs/{test_run_id}", tags=["runs"])
    async def get_run_route(test_run_id: str) -> dict:
        """Return every task associated with a single `test_run_id`."""
        tasks = await task_store.list_tasks_for_run(test_run_id)
        if not tasks:
            raise HTTPException(status_code=404, detail="No tasks found for this test_run_id")
        return {
            "test_run_id": test_run_id,
            "task_count": len(tasks),
            "tasks": [_task_to_snapshot_payload(t) for t in tasks],
        }

    # -- HITL approvals (PBI 3.6.5) ----------------------------------------------
    @app.post("/api/hitl/prompts", tags=["hitl"], status_code=201)
    async def create_hitl_prompt(body: HitlPromptCreate) -> dict:
        """Open a new HITL prompt for a task.

        Typically called by an agent (server-side) rather than the browser,
        but exposed here for symmetry and so the smoke test can exercise
        the full lifecycle without an agent in the loop.
        """
        try:
            task_uuid = UUID(body.task_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Malformed task_id") from exc
        approval = await hitl_store.create_prompt(task_uuid, body.prompt)
        return _approval_to_dict(approval)

    @app.get("/api/hitl/tasks/{task_id}", tags=["hitl"])
    async def list_hitl_for_task(task_id: str) -> dict:
        try:
            task_uuid = UUID(task_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Malformed task_id") from exc
        approvals = await hitl_store.list_for_task(task_uuid)
        return {
            "task_id": task_id,
            "approvals": [_approval_to_dict(a) for a in approvals],
        }

    @app.post("/api/hitl/approve", tags=["hitl"])
    async def approve_hitl(body: HitlDecision, request: Request) -> dict:
        return _serialize_decision_response(
            await hitl_store.record_decision(
                body.approval_id,
                decision="approved",
                decided_by=_resolve_decider(request, body.decided_by),
            )
        )

    @app.post("/api/hitl/reject", tags=["hitl"])
    async def reject_hitl(body: HitlDecision, request: Request) -> dict:
        return _serialize_decision_response(
            await hitl_store.record_decision(
                body.approval_id,
                decision="rejected",
                feedback=body.feedback,
                decided_by=_resolve_decider(request, body.decided_by),
            )
        )

    # Subsequent PBIs (3.6.3) plug additional routers in here.


def _task_to_snapshot_payload(task: task_store.AgentTask) -> dict:
    """Browser-friendly snapshot of an `agent_tasks` row for AG-UI consumers."""
    return {
        "task_id": str(task.task_id),
        "session_id": str(task.session_id) if task.session_id else None,
        "external_session_id": task.external_session_id,
        "agent_name": task.agent_name,
        "status": task.status,
        "test_run_id": task.test_run_id,
        "result": task.result,
        "error": task.error,
        "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def _session_to_dict(session: session_store.AgentSession) -> dict:
    """Browser-friendly view of an `agent_sessions` row."""
    return {
        "session_id": str(session.session_id),
        "external_session_id": session.external_session_id,
        "source": session.source,
        "user_identity": session.user_identity,
        "metadata": session.metadata,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else None,
    }


def _run_summary_to_dict(run: task_store.RunSummary) -> dict:
    """Browser-friendly view of a `RunSummary` (PBI 3.6.6)."""
    return {
        "test_run_id": run.test_run_id,
        "task_count": run.task_count,
        "completed_count": run.completed_count,
        "failed_count": run.failed_count,
        "active_count": run.active_count,
        "cancelled_count": run.cancelled_count,
        "agent_names": run.agent_names,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "last_activity_at": run.last_activity_at.isoformat() if run.last_activity_at else None,
    }


def _approval_to_dict(approval: hitl_store.HitlApproval) -> dict:
    """Browser-friendly view of a `hitl_approvals` row (PBI 3.6.5)."""
    return {
        "id": approval.id,
        "task_id": str(approval.task_id),
        "prompt": approval.prompt,
        "decision": approval.decision,
        "feedback": approval.feedback,
        "decided_by": approval.decided_by,
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
    }


def _serialize_decision_response(approval: Optional[hitl_store.HitlApproval]) -> dict:
    """Either return the updated row or 404 if it was missing/already terminal."""
    if approval is None:
        raise HTTPException(
            status_code=404,
            detail="No pending HITL approval found for that id (already decided or absent).",
        )
    return _approval_to_dict(approval)


def _resolve_decider(request: Request, body_value: Optional[str]) -> Optional[str]:
    """Decide who recorded a HITL decision.

    Precedence: explicit body field > `X-User-Identity` request header >
    session middleware's `user_identity` (Epic 4 EntraID slot).
    """
    if body_value:
        return body_value
    header = request.headers.get("X-User-Identity")
    if header and header.strip():
        return header.strip()
    return None


# =============================================================================
# ASGI entrypoint
# =============================================================================

app = create_app()


def _resolve_port() -> int:
    raw = os.environ.get("AGUI_PORT", "8002")
    try:
        return int(raw)
    except ValueError:
        log.warning("AGUI_PORT=%r is not an int; falling back to 8002", raw)
        return 8002


def main() -> None:
    """`python agui_server.py` entrypoint. Loads .env and runs uvicorn."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        from dotenv import load_dotenv
        load_dotenv(FRAMEWORK_DIR / ".env", override=False)
    except ImportError:
        log.debug("python-dotenv not installed; relying on shell env only")

    import uvicorn
    uvicorn.run(
        "agui_server:app",
        host=os.environ.get("AGUI_HOST", "0.0.0.0"),
        port=_resolve_port(),
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
