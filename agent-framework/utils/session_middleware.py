"""Starlette/FastAPI middleware that materializes the three-ID model.

Implements V2 doc Section 4.3:

    external_session_id  (optional)  inbound from upstream SDLC, opaque
    session_id           (required)  one UI tab / Cursor connection / A2A peer
    task_id              (required)  one A2A `tasks/send` call

For every inbound request to the A2A server (port 8001) and the AG-UI bridge
(port 8002), this middleware:

  1. Reads `X-Session-Id` and `X-External-Session-Id` headers if present.
  2. Resolves or creates the matching `agent_sessions` row.
  3. Writes both IDs into `request.state` so downstream route handlers can
     read them without re-doing the work.
  4. Bumps `last_activity_at` on existing sessions.

`task_id` is NOT created here. Tasks are minted when route handlers call
`task_store.create_task()`. The middleware only owns the session layer.

Heavy imports (`asyncpg` via `utils.session_store`) are reached only inside
the dispatch coroutine, so importing this module does not require a running
database.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from . import session_store

log = logging.getLogger(__name__)

HEADER_SESSION_ID = "X-Session-Id"
HEADER_EXTERNAL_SESSION_ID = "X-External-Session-Id"
HEADER_USER_ID = "X-User-Id"
HEADER_SOURCE = "X-Session-Source"

# Paths for which the middleware skips DB work entirely. Liveness probes
# should be a single SELECT-free round-trip.
SKIP_PATHS = ("/health", "/healthz", "/livez", "/readyz")

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _parse_uuid_header(value: Optional[str]) -> Optional[UUID]:
    """Best-effort UUID parse. Returns None on missing or malformed values."""
    if not value:
        return None
    value = value.strip()
    if not UUID_RE.match(value):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


class SessionMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that resolves and persists `session_id`.

    Args:
        default_source: Source tag stored on `agent_sessions.source` when the
            client does not send `X-Session-Source`. Servers pick the value
            that best identifies their inbound surface (`a2a_external` for
            port 8001, `web_ui` for port 8002).
        echo_session_id_header: If True, the resolved `session_id` is echoed
            back in the response under `HEADER_SESSION_ID`. This is what
            lets a fresh client (no header) learn its own session ID after
            the first request.
    """

    def __init__(self, app, *, default_source: str, echo_session_id_header: bool = True):
        super().__init__(app)
        self.default_source = default_source
        self.echo_session_id_header = echo_session_id_header

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if any(path == p or path.startswith(p + "/") for p in SKIP_PATHS):
            request.state.session_id = None
            request.state.external_session_id = None
            return await call_next(request)

        session_id_in = _parse_uuid_header(request.headers.get(HEADER_SESSION_ID))
        external_session_id = (request.headers.get(HEADER_EXTERNAL_SESSION_ID) or "").strip() or None
        user_id = (request.headers.get(HEADER_USER_ID) or "").strip() or None
        source = (request.headers.get(HEADER_SOURCE) or "").strip() or self.default_source

        try:
            session = await self._resolve_session(
                session_id=session_id_in,
                external_session_id=external_session_id,
                user_id=user_id,
                source=source,
            )
        except Exception:
            # DB unavailable, schema not provisioned, etc. Don't kill the
            # request - log and continue with no session attached. Route
            # handlers that absolutely require a session can guard on
            # request.state.session_id is None.
            log.exception(
                "SessionMiddleware: failed to resolve session (path=%s, in_session_id=%s). "
                "Continuing without session context.",
                path,
                session_id_in,
            )
            request.state.session_id = None
            request.state.external_session_id = external_session_id
            return await call_next(request)

        request.state.session_id = session.session_id
        request.state.external_session_id = session.external_session_id

        response = await call_next(request)

        if self.echo_session_id_header:
            response.headers[HEADER_SESSION_ID] = str(session.session_id)
            if session.external_session_id:
                response.headers[HEADER_EXTERNAL_SESSION_ID] = session.external_session_id
        return response

    async def _resolve_session(
        self,
        *,
        session_id: Optional[UUID],
        external_session_id: Optional[str],
        user_id: Optional[str],
        source: str,
    ) -> session_store.AgentSession:
        """Return an existing session (touched) or a freshly created one."""
        if session_id is not None:
            existing = await session_store.get_session(session_id)
            if existing is not None:
                await session_store.touch_session(existing.session_id)
                return existing
            # Header named a session_id we do not recognize. Fall through and
            # create a new session; we deliberately do not honor caller-supplied
            # IDs to avoid letting an external party squat on session UUIDs.
            log.info(
                "SessionMiddleware: ignoring unknown X-Session-Id %s; minting a new session",
                session_id,
            )

        return await session_store.create_session(
            source=source,
            external_session_id=external_session_id,
            user_id=user_id,
        )
