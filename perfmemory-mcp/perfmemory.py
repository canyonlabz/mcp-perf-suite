# PerfMemory MCP Server
# Persistent memory and lessons learned layer for JMeter script debugging.
from fastmcp import FastMCP, Context
from typing import Optional, Dict, Any

mcp = FastMCP(
    name="perfmemory",
)


# =============================================================================
# Batch 1 — Core Tools
# =============================================================================

@mcp.tool()
async def store_debug_session(
    system_under_test: str,
    test_run_id: str,
    ctx: Context,
    script_name: Optional[str] = None,
    auth_flow_type: Optional[str] = None,
    environment: Optional[str] = None,
    created_by: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new debug session record in the memory store.

    Called at the start of a debug workflow to establish the session context.
    Returns a session_id used to link subsequent debug attempts.

    Args:
        system_under_test: What is being tested (portal, API, workflow, etc.)
        test_run_id: Links to the artifact structure (artifacts/{test_run_id}/)
        ctx: MCP context
        script_name: The JMX filename being debugged
        auth_flow_type: Authentication flow type (none, oauth_pkce, oauth_auth_code,
            saml, token_chain, custom_sso, entra_id, other)
        environment: Test environment (dev, qa, uat, staging, prod)
        created_by: PTE name or username
        notes: Freeform session notes

    Returns:
        dict with keys: status, session_id, message
    """
    _ = ctx
    return {"status": "NOT_IMPLEMENTED", "message": "store_debug_session is not yet implemented"}


@mcp.tool()
async def store_debug_attempt(
    session_id: str,
    iteration_number: int,
    symptom_text: str,
    outcome: str,
    ctx: Context,
    error_category: Optional[str] = None,
    severity: Optional[str] = None,
    response_code: Optional[str] = None,
    hostname: Optional[str] = None,
    sampler_name: Optional[str] = None,
    api_endpoint: Optional[str] = None,
    diagnosis: Optional[str] = None,
    fix_description: Optional[str] = None,
    fix_type: Optional[str] = None,
    component_type: Optional[str] = None,
    manifest_excerpt: Optional[str] = None,
    matched_attempt_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Embed a symptom and store a debug attempt linked to a session.

    Called after each debug iteration to record what was tried and the outcome.
    The symptom_text is embedded using the configured embedding provider and
    stored as a vector for future similarity search.

    If matched_attempt_id is provided (fix was based on a memory match),
    the confirmed_count on that matched attempt is incremented.

    Args:
        session_id: UUID of the parent debug session
        iteration_number: Attempt number within the session (1, 2, 3...)
        symptom_text: Structured symptom description (gets embedded as vector)
        outcome: Result of this attempt (resolved, failed, environment_issue,
            test_data_issue, authentication_issue, needs_investigation)
        ctx: MCP context
        error_category: From log analyzer (HTTP 4xx Error, Authentication Error, etc.)
        severity: Error severity (Critical, High, Medium)
        response_code: HTTP status code
        hostname: Host where the error occurred
        sampler_name: The failing JMeter sampler
        api_endpoint: The failing URL/endpoint
        diagnosis: Root cause determination (plain language)
        fix_description: What fix was attempted (plain language)
        fix_type: Categorized fix (add_extractor, move_extractor, edit_request_body,
            edit_header, edit_correlation, other)
        component_type: JMeter component type (json_extractor, regex_extractor, etc.)
        manifest_excerpt: Raw debug manifest iteration text for reference
        matched_attempt_id: UUID of a previously matched attempt whose fix was applied.
            If provided, that attempt's confirmed_count is incremented.

    Returns:
        dict with keys: status, attempt_id, embedding_model, message.
        If matched_attempt_id provided: also confirmed_match_id, new_confirmed_count.
    """
    _ = ctx
    return {"status": "NOT_IMPLEMENTED", "message": "store_debug_attempt is not yet implemented"}


@mcp.tool()
async def find_similar_attempts(
    symptom_text: str,
    ctx: Context,
    system_under_test: Optional[str] = None,
    error_category: Optional[str] = None,
    top_k: Optional[int] = None,
    threshold: Optional[float] = None,
) -> Dict[str, Any]:
    """Search the memory store for previously stored attempts similar to a symptom.

    Called before starting a debug loop to check if a similar issue has been
    encountered before. Returns matches ranked by cosine similarity with
    a recommendation on how to proceed.

    Args:
        symptom_text: The current error symptom to search for
        ctx: MCP context
        system_under_test: Filter by system (optional, narrows search)
        error_category: Filter by error category (optional, narrows search)
        top_k: Max number of results to return (defaults to config VECTOR_TOP_K)
        threshold: Minimum similarity score (defaults to config SIMILARITY_THRESHOLD)

    Returns:
        dict with keys: status, matches_found, matches, recommendation.
        Each match includes: attempt_id, session_id, symptom_text, diagnosis,
        fix_description, fix_type, outcome, similarity, confirmed_count, is_verified.
        recommendation is one of: apply_known_fix, review_suggestions, no_match.
    """
    _ = ctx
    return {
        "status": "NOT_IMPLEMENTED",
        "message": "find_similar_attempts is not yet implemented",
        "matches_found": 0,
        "matches": [],
        "recommendation": "no_match",
    }


# =============================================================================
# Batch 2 — Session Management Tools
# =============================================================================

@mcp.tool()
async def close_debug_session(
    session_id: str,
    final_outcome: str,
    ctx: Context,
    resolution_attempt_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Finalize a debug session with its outcome.

    Called when debugging is complete. Sets the final_outcome, completed_at
    timestamp, total_iterations count, and optionally links the resolving attempt.

    Args:
        session_id: UUID of the debug session to close
        final_outcome: Final result (resolved, unresolved, environment_issue,
            test_data_issue, authentication_issue, iteration_limit_reached,
            needs_investigation)
        ctx: MCP context
        resolution_attempt_id: UUID of the attempt that resolved the issue
        notes: Additional notes to append to the session

    Returns:
        dict with keys: status, message, total_iterations
    """
    _ = ctx
    return {"status": "NOT_IMPLEMENTED", "message": "close_debug_session is not yet implemented"}


@mcp.tool()
async def list_sessions(
    ctx: Context,
    system_under_test: Optional[str] = None,
    environment: Optional[str] = None,
    final_outcome: Optional[str] = None,
    limit: Optional[int] = 20,
) -> Dict[str, Any]:
    """Browse stored debug sessions with optional filters.

    Returns session metadata only (no attempts). Use get_session_detail
    to retrieve a full session with all its attempts.

    Args:
        ctx: MCP context
        system_under_test: Filter by system name
        environment: Filter by environment (dev, qa, uat, staging, prod)
        final_outcome: Filter by outcome (resolved, unresolved, etc.)
        limit: Maximum number of sessions to return (default 20)

    Returns:
        dict with keys: status, count, sessions (list of session metadata dicts)
    """
    _ = ctx
    return {
        "status": "NOT_IMPLEMENTED",
        "message": "list_sessions is not yet implemented",
        "count": 0,
        "sessions": [],
    }


@mcp.tool()
async def get_session_detail(
    session_id: str,
    ctx: Context,
) -> Dict[str, Any]:
    """Get a full debug session with all its attempts.

    Returns complete session metadata and all attempts ordered by
    iteration_number. Used during HITL review to inspect the full
    debug story.

    Args:
        session_id: UUID of the debug session
        ctx: MCP context

    Returns:
        dict with keys: status, session (dict), attempts (list ordered by
        iteration_number)
    """
    _ = ctx
    return {
        "status": "NOT_IMPLEMENTED",
        "message": "get_session_detail is not yet implemented",
        "session": {},
        "attempts": [],
    }


# =============================================================================
# Batch 3 — Maintenance Tools
# =============================================================================

@mcp.tool()
async def archive_attempt(
    attempt_id: str,
    ctx: Context,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Archive a debug attempt by setting is_active to FALSE.

    Used when a lesson becomes outdated (API changed, issue no longer occurs).
    The attempt remains in the database for audit trail but is excluded from
    future similarity searches.

    Args:
        attempt_id: UUID of the attempt to archive
        ctx: MCP context
        reason: Optional reason for archiving

    Returns:
        dict with keys: status, message
    """
    _ = ctx
    return {"status": "NOT_IMPLEMENTED", "message": "archive_attempt is not yet implemented"}


@mcp.tool()
async def verify_attempt(
    attempt_id: str,
    ctx: Context,
) -> Dict[str, Any]:
    """Mark a debug attempt as human-verified.

    Sets is_verified to TRUE. Used during HITL review when a human confirms
    that the lesson stored in this attempt is correct and reliable.

    Args:
        attempt_id: UUID of the attempt to verify
        ctx: MCP context

    Returns:
        dict with keys: status, message
    """
    _ = ctx
    return {"status": "NOT_IMPLEMENTED", "message": "verify_attempt is not yet implemented"}


@mcp.tool()
async def get_memory_stats(
    ctx: Context,
    system_under_test: Optional[str] = None,
) -> Dict[str, Any]:
    """Get overview statistics of the memory store.

    Returns counts of sessions and attempts, broken down by system,
    outcome, verification status, and active status.

    Args:
        ctx: MCP context
        system_under_test: Filter stats to a specific system (optional)

    Returns:
        dict with keys: status, total_sessions, total_attempts,
        by_system, by_outcome, verified_count, active_count
    """
    _ = ctx
    return {
        "status": "NOT_IMPLEMENTED",
        "message": "get_memory_stats is not yet implemented",
        "total_sessions": 0,
        "total_attempts": 0,
    }


# =============================================================================
# Server Startup
# =============================================================================

if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down PerfMemory MCP…")
