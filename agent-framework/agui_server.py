"""AG-UI / CopilotKit bridge for PerfPilot Agents (V2 doc Section 10, port 8002).

A separate FastAPI ASGI app from the A2A surface (port 8001). It exists to
support the human-driven HITL experience through a browser-based React UI
built on CopilotKit. The two surfaces deliberately stay in different
processes so:

  - The A2A surface stays minimal and protocol-pure (no UI concerns).
  - The AG-UI surface can carry conversation, session, run, and HITL
    affordances that browsers need (cookies, SSE, CORS).

URL conventions:

  /copilotkit/                - AG-UI / CopilotKit endpoint, served by AG2's
                                 native `AGUIStream(agent).build_asgi()`.
                                 The Next.js CopilotKit React frontend points
                                 its `runtimeUrl` here. AG2 speaks AG-UI
                                 natively, so no CopilotKit Python SDK is
                                 needed in the middle. NOTE: the trailing
                                 slash is canonical (Starlette `Mount` 307s
                                 from `/copilotkit` -> `/copilotkit/`).
  /api/sessions[/{id}]        - Session info
  /api/runs[/{test_run_id}]   - Test-run grouping over agent_tasks
  /api/hitl/{approve,reject}  - HITL CRUD over hitl_approvals
  /api/events                 - AG-UI SSE event stream from task_executor
  /health                     - Liveness probe

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

from utils import (
    agents_config,
    auth,
    db,
    hitl_store,
    session_store,
    task_executor,
    task_store,
)
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

    # Session middleware after CORS so preflight requests are not minted as
    # sessions. Cookie tunables come from `agents.yaml -> web_ui.session_cookie`
    # via `utils.agents_config.get_session_cookie_config()`, which always
    # returns a populated config (defaults fill in any missing keys).
    cookie_cfg = agents_config.get_session_cookie_config(FRAMEWORK_DIR)
    log.info(
        "AG-UI session-cookie config: max_age_days=%d secure=%s samesite=%s",
        cookie_cfg.max_age_days, cookie_cfg.secure, cookie_cfg.samesite,
    )
    app.add_middleware(
        SessionMiddleware,
        default_source="web_ui",
        cookie_secure=cookie_cfg.secure,
        cookie_samesite=cookie_cfg.samesite,
        cookie_max_age_days=cookie_cfg.max_age_days,
    )

    _register_routes(app)
    _mount_copilotkit(app)
    return app


def _mount_copilotkit(app: FastAPI) -> None:
    """Mount the AG-UI / CopilotKit endpoint at /copilotkit (PBI 3.6.3).

    Uses AG2's built-in `AGUIStream(agent).build_asgi()` so CopilotKit React
    (F3.6.7) can talk to us directly via the AG-UI protocol. No CopilotKit
    Python SDK is involved - AG2 ships AG-UI support natively.

    Mount is best-effort: if the agent or AG2 import fails, the rest of
    the server still boots and the other endpoints (`/api/sessions`,
    `/api/runs`, `/api/hitl/*`, `/api/events`, `/health`) keep working.
    A subsequent boot attempt with a valid LLM config will mount cleanly.
    """
    try:
        from autogen.ag_ui import AGUIStream  # noqa: WPS433
        from utils.copilotkit_stub import build_stub_orchestrator  # noqa: WPS433
    except Exception:
        log.exception(
            "Could not import AG2 / AGUIStream; /copilotkit will be unavailable. "
            "Install with: pip install \"ag2[ag-ui]==0.13.3\""
        )
        return

    try:
        agent = build_stub_orchestrator()
    except Exception:
        log.exception(
            "Failed to build the stub orchestrator (likely missing/invalid LLM "
            "credentials in agent-framework/.env); /copilotkit will be unavailable."
        )
        return

    try:
        stream = AGUIStream(agent)
        app.mount("/copilotkit", stream.build_asgi())
        log.info("Mounted AG-UI endpoint at /copilotkit (stub orchestrator)")
    except Exception:
        log.exception("Could not mount /copilotkit; AG-UI endpoint will be unavailable")


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

        # PBI 3.7.0b owner-filtering: only the task's owner can subscribe to
        # its event stream. A subscriber that doesn't own the task would
        # otherwise see the task's payload + result via the snapshot event,
        # which is the same data the /api/runs/{id} endpoint protects.
        owner = await auth.owner_of_session(existing.session_id)
        auth.requires_owner(
            resource_owner=owner,
            requesting_user=getattr(request.state, "user_id", None),
            resource_kind="task event stream",
        )

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

    # -- Sessions (PBI 3.6.4 + PBI 3.7.0b owner-filtering) ------------------------
    @app.get("/api/sessions", tags=["sessions"])
    async def list_sessions_route(
        request: Request,
        limit: int = 50,
        offset: int = 0,
        source: Optional[str] = None,
        include_ended: bool = False,
    ) -> dict:
        """Return recent sessions owned by the requesting user.

        Owner-filtered in PBI 3.7.0b: only sessions whose `user_id` matches
        `request.state.user_id` are returned. The Web UI session picker is
        per-user; Alice never sees Bob's sessions.
        """
        requesting_user = getattr(request.state, "user_id", None)
        sessions = await session_store.list_sessions(
            limit=limit,
            offset=offset,
            source=source,
            include_ended=include_ended,
            user_id=requesting_user,
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

        Not owner-filtered: by definition the session is the requesting
        user's own (the middleware either created it for them or matched
        their own X-Session-Id). The middleware re-uses an existing
        session row when its `session_id` arrives via header -- and we
        still 403 if that row turns out to belong to another user, so a
        client can't hijack someone else's session by spoofing its ID.
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
        auth.requires_owner(
            resource_owner=session.user_id,
            requesting_user=getattr(request.state, "user_id", None),
            resource_kind="session",
        )
        return _session_to_dict(session)

    @app.get("/api/sessions/{session_id}", tags=["sessions"])
    async def get_session_route(session_id: str, request: Request) -> dict:
        try:
            uuid_value = UUID(session_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Malformed session_id") from exc
        session = await session_store.get_session(uuid_value)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        auth.requires_owner(
            resource_owner=session.user_id,
            requesting_user=getattr(request.state, "user_id", None),
            resource_kind="session",
        )
        return _session_to_dict(session)

    # -- Test runs (PBI 3.6.6 + PBI 3.7.0b owner-filtering) -----------------------
    @app.get("/api/runs", tags=["runs"])
    async def list_runs_route(request: Request, limit: int = 50, offset: int = 0) -> dict:
        """Return recent test runs owned by the requesting user.

        Owner-filtered in PBI 3.7.0b: a run "belongs to" a user when at
        least one of its tasks lives in a session owned by that user.
        Implemented in `task_store.list_runs(user_id=...)` via a JOIN.
        """
        requesting_user = getattr(request.state, "user_id", None)
        runs = await task_store.list_runs(
            limit=limit,
            offset=offset,
            user_id=requesting_user,
        )
        return {
            "runs": [_run_summary_to_dict(r) for r in runs],
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/runs/{test_run_id}", tags=["runs"])
    async def get_run_route(test_run_id: str, request: Request) -> dict:
        """Return every task associated with a single `test_run_id`.

        Owner-filtered: 404 when the user has no tasks under this run,
        which is indistinguishable from "this run does not exist." We
        deliberately avoid 403 here so callers cannot probe for the
        existence of other users' runs by trying random test_run_ids.
        """
        requesting_user = getattr(request.state, "user_id", None)
        tasks = await task_store.list_tasks_for_run(
            test_run_id,
            user_id=requesting_user,
        )
        if not tasks:
            raise HTTPException(status_code=404, detail="No tasks found for this test_run_id")
        return {
            "test_run_id": test_run_id,
            "task_count": len(tasks),
            "tasks": [_task_to_snapshot_payload(t) for t in tasks],
        }

    # -- HITL approvals (PBI 3.6.5 + PBI 3.7.0b owner-filtering) -----------------
    @app.post("/api/hitl/prompts", tags=["hitl"], status_code=201)
    async def create_hitl_prompt(body: HitlPromptCreate) -> dict:
        """Open a new HITL prompt for a task.

        Typically called by an agent (server-side trusted code path) rather
        than the browser. Exposed here for symmetry and so the smoke test
        can exercise the full lifecycle without an agent in the loop.

        Owner-filtering: EXEMPT in PBI 3.7.0b. The agent is server-side
        trusted code creating a prompt on behalf of a task it is already
        running. Validating ownership here would require resolving the
        task's session and matching against the requesting user, which is
        not appropriate for server-side callers that don't have a user_id.

        Future hardening (housekeeping item H5 in the status doc): swap
        this exemption for service-principal-only auth in Epic 4, so
        end-users cannot self-create approval requests under forged
        identities. The /approve and /reject endpoints below already
        protect the *decision* side via `requires_owner` (the security
        boundary that actually matters: forging an approval).
        """
        try:
            task_uuid = UUID(body.task_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Malformed task_id") from exc
        approval = await hitl_store.create_prompt(task_uuid, body.prompt)
        return _approval_to_dict(approval)

    @app.get("/api/hitl/tasks/{task_id}", tags=["hitl"])
    async def list_hitl_for_task(task_id: str, request: Request) -> dict:
        """List HITL approvals for a task, restricted to the task's owner.

        Owner-filtered: the requesting user must own the underlying task's
        session. Otherwise 403 -- same answer they'd get for any other
        user's task, so the read surface doesn't leak existence.
        """
        try:
            task_uuid = UUID(task_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Malformed task_id") from exc

        task_owner = await auth.owner_of_task(task_uuid)
        if task_owner is None:
            # Distinguish "no such task" from "task exists but not yours"
            # at the *load* layer: if the task doesn't exist at all, return
            # 404 instead of leaking via 403.
            existing_task = await task_store.get_task(task_uuid)
            if existing_task is None:
                raise HTTPException(status_code=404, detail="Task not found")
        auth.requires_owner(
            resource_owner=task_owner,
            requesting_user=getattr(request.state, "user_id", None),
            resource_kind="HITL task",
        )

        approvals = await hitl_store.list_for_task(task_uuid)
        return {
            "task_id": task_id,
            "approvals": [_approval_to_dict(a) for a in approvals],
        }

    @app.post("/api/hitl/approve", tags=["hitl"])
    async def approve_hitl(body: HitlDecision, request: Request) -> dict:
        """Approve a pending HITL prompt. Owner-filtered."""
        await _enforce_hitl_owner(body.approval_id, request)
        return _serialize_decision_response(
            await hitl_store.record_decision(
                body.approval_id,
                decision="approved",
                decided_by=_resolve_decider(request, body.decided_by),
            )
        )

    @app.post("/api/hitl/reject", tags=["hitl"])
    async def reject_hitl(body: HitlDecision, request: Request) -> dict:
        """Reject a pending HITL prompt with optional feedback. Owner-filtered."""
        await _enforce_hitl_owner(body.approval_id, request)
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
        "user_id": session.user_id,
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

    Precedence: explicit body field > middleware-resolved `user_id`
    (which itself follows the four-step chain in `utils.user_identity`).
    """
    if body_value:
        return body_value
    state_user = getattr(request.state, "user_id", None)
    if state_user:
        return state_user
    return None


async def _enforce_hitl_owner(approval_id: int, request: Request) -> None:
    """Raise 403/404 unless the requesting user owns the HITL approval.

    "Owns" walks `hitl_approvals -> agent_tasks -> agent_sessions ->
    user_id`. The flow:

      1. Look up the approval row; 404 if absent (no ownership leak --
         a wrong approval_id and an unowned approval_id both 404 if you
         don't already know which is which).
      2. Resolve the owner of the approval's task.
      3. `auth.requires_owner` enforces equality with `request.state.user_id`.

    Called by both /approve and /reject so the security check is identical.
    """
    approval = await hitl_store.get_approval(approval_id)
    if approval is None:
        # Don't leak "this approval id has been decided by someone else"
        # via a 403. 404 covers both "never existed" and "already terminal."
        raise HTTPException(
            status_code=404,
            detail="No pending HITL approval found for that id (already decided or absent).",
        )
    owner = await auth.owner_of_task(approval.task_id)
    auth.requires_owner(
        resource_owner=owner,
        requesting_user=getattr(request.state, "user_id", None),
        resource_kind="HITL approval",
    )


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
