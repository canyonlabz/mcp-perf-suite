"""A2A FastAPI server for PerfPilot Agents (V2 doc Section 9, port 8001).

One ASGI app exposing all seven agents through path-based routing under
`/agents/{name}/...`. Endpoints follow the A2A protocol exactly (no
PerfPilot branding) so off-the-shelf A2A clients integrate without
adapters. Branding lives only on port 8002 (the AG-UI bridge, F3.6).

Endpoints (matches V2 Section 9.2):

    GET  /health                                            - liveness probe
    GET  /agents                                            - list discoverable agents
    GET  /agents/{name}/.well-known/agent.json              - agent card (RFC 8615)
    POST /agents/{name}/tasks/send                          - submit task (poll/webhook)
    POST /agents/{name}/tasks/sendSubscribe                 - submit task + SSE stream
    GET  /agents/{name}/tasks/{task_id}                     - poll task state
    POST /agents/{name}/tasks/{task_id}/cancel              - cancel a running task

Long-running task model (V2 Section 14):

    Pattern 1 - Polling: caller submits via tasks/send, polls GET tasks/{id}.
    Pattern 2 - SSE:     caller submits via tasks/sendSubscribe, holds open
                         the SSE stream until the task reaches terminal state.
    Pattern 3 - Webhook: caller submits with `subscriber_endpoints`; server
                         POSTs the final body to each URL on completion.

Run locally:

    cd agent-framework
    python a2a_server.py

Or via uvicorn from the agent-framework folder:

    uvicorn a2a_server:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

if __package__ is None:
    # Allow `python a2a_server.py` from inside agent-framework/.
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from utils import agents_config, db, task_executor, task_store
from utils.session_middleware import SessionMiddleware

log = logging.getLogger(__name__)

FRAMEWORK_DIR = Path(__file__).resolve().parent
AGENTS_DIR = FRAMEWORK_DIR / "agents"
SERVER_VERSION = "0.1.0"
SERVER_TITLE = "PerfPilot Agents - A2A Surface"


# =============================================================================
# App lifespan
# =============================================================================

@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Open the asyncpg pool eagerly so the first request is fast."""
    log.info("A2A server starting; warming asyncpg pool")
    try:
        await db.get_pool()
        log.info("A2A server ready (port=%s)", os.environ.get("A2A_PORT", "8001"))
    except Exception:
        log.exception("Failed to warm asyncpg pool at startup; routes will retry per request")
    try:
        yield
    finally:
        log.info("A2A server shutting down; closing asyncpg pool")
        await db.close_pool()


def create_app() -> FastAPI:
    """Build the FastAPI app. Factored out so tests can mount it in-process."""
    app = FastAPI(
        title=SERVER_TITLE,
        version=SERVER_VERSION,
        description="A2A protocol surface for PerfPilot Agents. See V2 doc Section 9.",
        lifespan=_lifespan,
    )
    app.add_middleware(SessionMiddleware, default_source="a2a_external")

    _register_routes(app)
    return app


# =============================================================================
# Route registration
# =============================================================================

def _register_routes(app: FastAPI) -> None:

    # -- Liveness ----------------------------------------------------------------
    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "service": "a2a", "version": SERVER_VERSION}

    # -- Discovery ---------------------------------------------------------------
    @app.get("/agents", tags=["discovery"])
    async def list_agents() -> dict:
        """Return the list of agents that are currently enabled.

        Mirrors V2 Section 9.5: only enabled agents appear in discovery.
        Disabled agents return 404 on their well-known card path.
        """
        names = agents_config.list_enabled_agents(FRAMEWORK_DIR)
        return {
            "agents": [
                {
                    "name": name,
                    "agent_card_url": f"/agents/{name}/.well-known/agent.json",
                    "tasks_send_url": f"/agents/{name}/tasks/send",
                }
                for name in names
            ],
            "known_agents": list(agents_config.KNOWN_AGENTS),
        }

    @app.get("/agents/{agent_name}/.well-known/agent.json", tags=["discovery"])
    async def agent_card(agent_name: str) -> JSONResponse:
        if not agents_config.is_agent_enabled(agent_name, FRAMEWORK_DIR):
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' is not enabled or unknown.")

        card_path = AGENTS_DIR / agent_name / "agent_card.json"
        if card_path.exists():
            with open(card_path, "r", encoding="utf-8") as f:
                card = json.load(f)
        else:
            # F3.7+ ships real cards; until then synthesize a truthful stub
            # card per V2 Section 7.4 / 9.5 ("skills:[] + status:'stub'").
            card = _synthesize_stub_card(agent_name)
        return JSONResponse(card)

    # -- Task endpoints ----------------------------------------------------------
    @app.post("/agents/{agent_name}/tasks/send", status_code=202, tags=["tasks"])
    async def tasks_send(agent_name: str, request: Request) -> dict:
        await _require_enabled_agent(agent_name)
        session_id = _require_session(request)
        body = await _read_json_body(request)

        task = await task_store.create_task(
            session_id=session_id,
            external_session_id=getattr(request.state, "external_session_id", None),
            agent_name=agent_name,
            payload=body,
            test_run_id=body.get("test_run_id"),
            subscriber_endpoints=_extract_subscriber_endpoints(body),
        )
        # Fire-and-forget background execution.
        asyncio.create_task(task_executor.execute_task(task.task_id))

        return {
            "task_id": str(task.task_id),
            "session_id": str(task.session_id),
            "agent_name": task.agent_name,
            "status": task.status,
            "submitted_at": task.submitted_at.isoformat(),
        }

    @app.post("/agents/{agent_name}/tasks/sendSubscribe", tags=["tasks"])
    async def tasks_send_subscribe(agent_name: str, request: Request) -> EventSourceResponse:
        await _require_enabled_agent(agent_name)
        session_id = _require_session(request)
        body = await _read_json_body(request)

        task = await task_store.create_task(
            session_id=session_id,
            external_session_id=getattr(request.state, "external_session_id", None),
            agent_name=agent_name,
            payload=body,
            test_run_id=body.get("test_run_id"),
            subscriber_endpoints=_extract_subscriber_endpoints(body),
        )
        queue = await task_executor.subscribe(task.task_id)
        asyncio.create_task(task_executor.execute_task(task.task_id))

        async def _stream():
            # Emit an initial snapshot so consumers immediately know the task_id.
            yield {
                "event": "snapshot",
                "data": json.dumps({
                    "task_id": str(task.task_id),
                    "session_id": str(task.session_id),
                    "agent_name": task.agent_name,
                    "status": task.status,
                    "submitted_at": task.submitted_at.isoformat(),
                }),
            }
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        # Heartbeat keeps proxies from killing the connection.
                        yield {"event": "ping", "data": "{}"}
                        continue
                    yield {"event": "state", "data": event.to_sse_data()}
                    if event.status in task_store.TERMINAL_STATUSES:
                        break
            finally:
                await task_executor.unsubscribe(task.task_id, queue)

        return EventSourceResponse(_stream())

    @app.get("/agents/{agent_name}/tasks/{task_id}", tags=["tasks"])
    async def tasks_get(agent_name: str, task_id: str, request: Request) -> dict:
        await _require_enabled_agent(agent_name)
        try:
            task_uuid = UUID(task_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Malformed task_id") from exc

        task = await task_store.get_task(task_uuid)
        if task is None or task.agent_name != agent_name:
            raise HTTPException(status_code=404, detail="Task not found for this agent")

        return _task_to_dict(task)

    @app.post("/agents/{agent_name}/tasks/{task_id}/cancel", tags=["tasks"])
    async def tasks_cancel(agent_name: str, task_id: str) -> dict:
        await _require_enabled_agent(agent_name)
        try:
            task_uuid = UUID(task_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Malformed task_id") from exc

        task = await task_store.get_task(task_uuid)
        if task is None or task.agent_name != agent_name:
            raise HTTPException(status_code=404, detail="Task not found for this agent")

        changed = await task_store.mark_cancelled(task_uuid, reason="cancelled via A2A")
        return {"task_id": task_id, "cancelled": changed, "previous_status": task.status}


# =============================================================================
# Helpers
# =============================================================================

async def _require_enabled_agent(agent_name: str) -> None:
    if not agents_config.is_agent_enabled(agent_name, FRAMEWORK_DIR):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' is not enabled or unknown.")


def _require_session(request: Request) -> UUID:
    session_id = getattr(request.state, "session_id", None)
    if session_id is None:
        # SessionMiddleware should always provide one; if it could not (DB
        # outage), refuse to mint tasks rather than orphan them.
        raise HTTPException(
            status_code=503,
            detail="Session could not be established (perfagent_state unavailable).",
        )
    return session_id


async def _read_json_body(request: Request) -> dict:
    raw = await request.body()
    if not raw:
        return {}
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object.")
    return body


def _extract_subscriber_endpoints(body: dict) -> list[str]:
    """Locate `subscriber_endpoints` in either the top-level body or a `callbacks` block."""
    callbacks = body.get("callbacks") or {}
    raw = body.get("subscriber_endpoints") or callbacks.get("subscriber_endpoints") or []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for entry in raw:
        if isinstance(entry, str) and entry.strip():
            out.append(entry.strip())
    # Also accept the singular `webhook_url` from the V2 doc example payload.
    webhook = callbacks.get("webhook_url") or body.get("webhook_url")
    if isinstance(webhook, str) and webhook.strip() and webhook.strip() not in out:
        out.append(webhook.strip())
    return out


def _task_to_dict(task: task_store.AgentTask) -> dict:
    return {
        "task_id": str(task.task_id),
        "session_id": str(task.session_id) if task.session_id else None,
        "external_session_id": task.external_session_id,
        "agent_name": task.agent_name,
        "status": task.status,
        "test_run_id": task.test_run_id,
        "result": task.result,
        "error": task.error,
        "subscriber_endpoints": task.subscriber_endpoints,
        "submitted_at": task.submitted_at.isoformat() if task.submitted_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


def _synthesize_stub_card(agent_name: str) -> dict:
    """Return a truthful stub `agent_card.json` for an agent with no on-disk card.

    Section 7.4 of the V2 doc requires stub cards to advertise empty skills
    and a clear status field rather than promising capabilities the agent
    does not yet have.
    """
    return {
        "name": agent_name,
        "description": (
            f"PerfPilot {agent_name} (Epic 3 stub). Real capabilities ship in a later "
            "Feature; this card is published only so external A2A clients can discover "
            "the agent today."
        ),
        "url": f"/agents/{agent_name}",
        "version": SERVER_VERSION,
        "status": "stub",
        "skills": [],
        "tags": ["stub", "epic-3"],
        "capabilities": {
            "streaming": True,
            "long_running_tasks": True,
            "webhook_subscribers": True,
        },
    }


# =============================================================================
# ASGI entrypoint
# =============================================================================

app = create_app()


def _resolve_port() -> int:
    raw = os.environ.get("A2A_PORT", "8001")
    try:
        return int(raw)
    except ValueError:
        log.warning("A2A_PORT=%r is not an int; falling back to 8001", raw)
        return 8001


def main() -> None:
    """`python a2a_server.py` entrypoint. Loads .env and runs uvicorn."""
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
        "a2a_server:app",
        host=os.environ.get("A2A_HOST", "0.0.0.0"),
        port=_resolve_port(),
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
