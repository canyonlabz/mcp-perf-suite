"""
Authentication orchestration for SharePoint MCP.

Three-layer token resolution:
  1. In-memory cache — fast path, no I/O
  2. Token cache file — re-read Bearer token from encrypted cache
  3. Browser login — launch Playwright, intercept Bearer token from network

All entry points are async and guarded by an asyncio.Lock to prevent
concurrent browser launches or token refresh races.

Key differences from msteams-mcp auth_manager:
  - Single token type (SharePoint Bearer) instead of four (Substrate, Skype, CSA, Auth)
  - Token captured via network request interception, not localStorage extraction
  - Tenant auto-detected from browser URL and stored alongside the token
  - SharePoint URL built dynamically from tenant (config or auto-detected)
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from . import session_store, token_extractor
from .browser_context import (
    _browser_lock,
    create_browser_context,
    close_browser,
    BrowserManager,
)
from .browser_auth import (
    ensure_authenticated,
    TokenInterceptor,
    extract_tenant_from_url,
)
from .errors import ErrorCode, Result, ok, err, create_error

from utils.config import load_config

logger = logging.getLogger("sharepoint-mcp.auth-manager")

TOKEN_REFRESH_THRESHOLD_SEC = 600  # 10 minutes


@dataclass
class AuthState:
    """Cached in-memory auth state — updated after each successful auth."""
    bearer_token: str | None = None
    bearer_expiry: float = 0
    tenant: str = ""
    user_name: str = "Unknown User"
    last_refresh: float = 0


_auth_state = AuthState()
_auth_lock = asyncio.Lock()


def _token_needs_refresh(expiry: float) -> bool:
    return expiry <= 0 or (expiry - time.time()) < TOKEN_REFRESH_THRESHOLD_SEC


def _get_configured_tenant() -> str:
    """Read the tenant from config.yaml, or return empty string."""
    try:
        cfg = load_config()
        return cfg.get("sharepoint", {}).get("tenant", "") or ""
    except Exception:
        return ""


def _get_sharepoint_url(tenant: str = "") -> str:
    """Build the SharePoint base URL from the tenant name.

    If no tenant is available, falls back to a generic SharePoint URL
    that will redirect through Entra ID and land on the user's tenant.
    """
    t = tenant or _get_configured_tenant() or _auth_state.tenant
    if t:
        return f"https://{t}.sharepoint.com"
    # No tenant known — navigate to Office portal which redirects to SP
    return "https://www.office.com/launch/sharepoint"


def _update_auth_state_from_cache() -> bool:
    """Try to populate _auth_state from the encrypted token cache.

    Returns True if a valid (non-expired) token was loaded.
    """
    info = token_extractor.get_valid_bearer_token()
    if not info:
        return False

    _auth_state.bearer_token = info.token
    _auth_state.bearer_expiry = info.expiry
    if info.tenant:
        _auth_state.tenant = info.tenant
    _auth_state.user_name = token_extractor.get_user_display_name(info.token)
    _auth_state.last_refresh = time.time()
    return True


def _update_auth_state_from_interceptor(
    interceptor: TokenInterceptor,
    tenant_from_auth: str | None = None,
) -> bool:
    """Update _auth_state from a TokenInterceptor after browser login.

    Saves the captured token to the encrypted cache and populates
    in-memory state. Returns True on success.
    """
    if not interceptor.has_token:
        return False

    tenant = (
        tenant_from_auth
        or interceptor.tenant
        or _get_configured_tenant()
        or _auth_state.tenant
    )

    info = token_extractor.save_bearer_token(interceptor.bearer_token, tenant)
    if not info:
        return False

    _auth_state.bearer_token = info.token
    _auth_state.bearer_expiry = info.expiry
    _auth_state.tenant = info.tenant
    _auth_state.user_name = token_extractor.get_user_display_name(info.token)
    _auth_state.last_refresh = time.time()
    return True


async def get_bearer_token() -> Result[str]:
    """Get a valid SharePoint Bearer token (cache -> file -> browser).

    This is the primary entry point for sharepoint_api.py to obtain
    a token for _api/ REST calls.
    """
    async with _auth_lock:
        # Layer 1: In-memory cache
        if (
            _auth_state.bearer_token
            and not _token_needs_refresh(_auth_state.bearer_expiry)
        ):
            return ok(_auth_state.bearer_token)

        # Layer 2: Encrypted token cache file
        if _update_auth_state_from_cache():
            if not _token_needs_refresh(_auth_state.bearer_expiry):
                return ok(_auth_state.bearer_token)

        # Layer 3: Headless browser refresh
        result = await _browser_login(headless=True)
        if result.ok and _auth_state.bearer_token:
            return ok(_auth_state.bearer_token)

        return err(create_error(
            ErrorCode.AUTH_REQUIRED,
            "No valid SharePoint Bearer token — call sharepoint_login first",
        ))


def get_tenant() -> str:
    """Return the current tenant name (from auth state, cache, or config)."""
    if _auth_state.tenant:
        return _auth_state.tenant

    info = token_extractor.get_valid_bearer_token()
    if info and info.tenant:
        _auth_state.tenant = info.tenant
        return info.tenant

    return _get_configured_tenant()


async def login(*, force: bool = False) -> Result[dict[str, Any]]:
    """Full login flow. If force=True, skip cache and go straight to browser.

    Returns a status dict on success.
    """
    async with _auth_lock:
        if not force:
            # Layer 1: In-memory cache
            if (
                _auth_state.bearer_token
                and not _token_needs_refresh(_auth_state.bearer_expiry)
            ):
                return ok({
                    "status": "already_authenticated",
                    "user": _auth_state.user_name,
                    "tenant": _auth_state.tenant,
                    "message": "Already authenticated with valid tokens",
                })

            # Layer 2: Token cache file
            if _update_auth_state_from_cache():
                if not _token_needs_refresh(_auth_state.bearer_expiry):
                    return ok({
                        "status": "restored_session",
                        "user": _auth_state.user_name,
                        "tenant": _auth_state.tenant,
                        "message": "Restored tokens from cached session",
                    })

        # Layer 3: Try headless first, fall back to visible
        result = await _browser_login(headless=True)
        if result.ok:
            return result

        return await _browser_login(headless=False)


async def _browser_login(*, headless: bool) -> Result[dict[str, Any]]:
    """Launch Playwright, navigate to SharePoint, authenticate.

    Creates a TokenInterceptor to capture Bearer tokens from network
    requests during navigation. The interceptor is attached to the page
    before navigating to SharePoint.
    """
    manager: BrowserManager | None = None
    auth_result: dict | None = None
    interceptor = TokenInterceptor()

    try:
        async with _browser_lock:
            manager = await create_browser_context(headless=headless)

            # Attach the network request interceptor before navigation
            manager.page.on("request", interceptor.on_request)

            sharepoint_url = _get_sharepoint_url()
            auth_result = await ensure_authenticated(
                manager.page,
                manager.context,
                interceptor,
                sharepoint_url,
                headless=headless,
            )

        if auth_result["success"]:
            tenant = auth_result.get("tenant") or interceptor.tenant
            _update_auth_state_from_interceptor(interceptor, tenant)

            # If we got cookies but no Bearer token from intercept,
            # try navigating to an _api endpoint to trigger a token
            if not _auth_state.bearer_token and manager:
                await _try_trigger_api_call(manager.page, interceptor)
                _update_auth_state_from_interceptor(interceptor, tenant)

            response: dict[str, Any] = {
                "status": "authenticated",
                "method": auth_result["method"],
                "user": _auth_state.user_name,
                "message": auth_result["message"],
            }

            if _auth_state.tenant:
                response["tenant"] = _auth_state.tenant
            else:
                response["warning"] = (
                    "Tenant could not be auto-detected. "
                    "Set 'sharepoint.tenant' in config.yaml or provide "
                    "the full site_url when calling upload tools."
                )

            return ok(response)

        if auth_result.get("method") == "needs_visible_login":
            return err(create_error(
                ErrorCode.AUTH_REQUIRED,
                "SSO failed — interactive login required",
            ))

        return err(create_error(
            ErrorCode.BROWSER_ERROR,
            auth_result.get("message", "Browser login failed"),
        ))

    except Exception as exc:
        logger.exception("Browser login error")
        return err(create_error(
            ErrorCode.BROWSER_ERROR,
            f"Browser error: {exc}",
        ))
    finally:
        if manager:
            try:
                save = bool(auth_result and auth_result.get("success"))
                await close_browser(manager, save_session=save)
            except Exception:
                pass


async def _try_trigger_api_call(page, interceptor: TokenInterceptor) -> None:
    """Navigate to a lightweight _api endpoint to trigger Bearer token emission.

    Some SSO flows may land on SharePoint with only cookies (FedAuth/rtFa)
    and no Bearer token in the initial page load. Hitting an _api endpoint
    forces the browser to attach a Bearer token to the request.
    """
    tenant = interceptor.tenant or _auth_state.tenant or _get_configured_tenant()
    if not tenant:
        return

    try:
        url = f"https://{tenant}.sharepoint.com/_api/web/currentuser"
        await page.goto(url, wait_until="domcontentloaded", timeout=10000)
        await asyncio.sleep(2)
    except Exception as exc:
        logger.debug("Trigger API call failed (non-fatal): %s", exc)


def get_status() -> dict[str, Any]:
    """Return a diagnostic snapshot of auth state (no network I/O)."""
    has_session = session_store.has_session_state()
    session_age = session_store.get_session_age_hours()

    return {
        "hasSession": has_session,
        "sessionAgeHours": round(session_age, 1) if session_age else None,
        "isSessionExpired": session_store.is_session_likely_expired(),
        "bearerToken": token_extractor.get_bearer_token_status(),
        "tenant": _auth_state.tenant or get_tenant(),
        "user": _auth_state.user_name,
        "lastRefresh": _auth_state.last_refresh,
    }
