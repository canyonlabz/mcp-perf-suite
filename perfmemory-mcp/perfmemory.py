# PerfMemory MCP Server
# Persistent memory and lessons learned layer for JMeter script debugging.
import asyncio
import atexit
import logging

from fastmcp import FastMCP, Context
from typing import Optional, Dict, Any

from services.embeddings import EmbeddingProvider
from services import session_manager as sm
from services import graph_manager as gm
from utils.config import load_config

log = logging.getLogger(__name__)

mcp = FastMCP(
    name="perfmemory",
)

_config = load_config()
_embedder = EmbeddingProvider(_config["embedding"])


def _graph_enabled() -> bool:
    return _config.get("graph", {}).get("enabled", False)


def _shutdown():
    """Release database connections and HTTP clients on exit."""
    log.info("PerfMemory shutdown — releasing resources")
    sm.close_pool()
    if _graph_enabled():
        gm.close_pool()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_embedder.close())
        else:
            loop.run_until_complete(_embedder.close())
    except RuntimeError:
        pass

atexit.register(_shutdown)


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
    try:
        session_id = sm.create_session(
            _config["database"],
            system_under_test=system_under_test,
            test_run_id=test_run_id,
            script_name=script_name,
            auth_flow_type=auth_flow_type,
            environment=environment,
            created_by=created_by,
            notes=notes,
        )
        return {
            "status": "OK",
            "session_id": session_id,
            "message": f"Debug session created (id={session_id})",
        }
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


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
    try:
        embedding = await _embedder.embed(symptom_text)
        model_name = _embedder.get_model_name()

        attempt_id = sm.create_attempt(
            _config["database"],
            session_id=session_id,
            iteration_number=iteration_number,
            symptom_text=symptom_text,
            outcome=outcome,
            embedding=embedding,
            embedding_model=model_name,
            error_category=error_category,
            severity=severity,
            response_code=response_code,
            hostname=hostname,
            sampler_name=sampler_name,
            api_endpoint=api_endpoint,
            diagnosis=diagnosis,
            fix_description=fix_description,
            fix_type=fix_type,
            component_type=component_type,
            manifest_excerpt=manifest_excerpt,
        )

        result: Dict[str, Any] = {
            "status": "OK",
            "attempt_id": attempt_id,
            "embedding_model": model_name,
            "message": f"Debug attempt stored (id={attempt_id})",
        }

        if matched_attempt_id:
            new_count = sm.increment_confirmed(_config["database"], matched_attempt_id)
            result["confirmed_match_id"] = matched_attempt_id
            result["new_confirmed_count"] = new_count

        # Graph layer: create nodes and deterministic edges
        if _graph_enabled():
            graph_cfg = _config["graph"]
            graph_name = graph_cfg["graph_name"]

            session_data = sm.get_session(_config["database"], session_id)
            project = session_data["session"]["system_under_test"] if session_data else "unknown"

            graph_ok = gm.create_attempt_node(
                _config["database"],
                graph_name=graph_name,
                attempt_id=attempt_id,
                project=project,
                error_category=error_category,
                fix_type=fix_type,
                outcome=outcome,
                response_code=response_code,
                component_type=component_type,
            )
            result["graph_node_created"] = graph_ok

            if graph_ok and error_category:
                edge_count = gm.create_cross_project_edges(
                    _config["database"],
                    graph_name=graph_name,
                    attempt_id=attempt_id,
                    error_category=error_category,
                    response_code=response_code,
                    project=project,
                )
                result["graph_cross_project_edges"] = edge_count

            if graph_ok:
                similar_for_edges = sm.find_similar(
                    _config["database"],
                    embedding=embedding,
                    threshold=graph_cfg["embedding_edge_threshold"],
                    top_k=graph_cfg["max_embedding_edges"],
                )
                edge_candidates = [
                    {
                        "attempt_id": m["attempt_id"],
                        "similarity": m["similarity"],
                        "cross_project": m.get("system_under_test", "") != project,
                    }
                    for m in similar_for_edges
                    if m["attempt_id"] != attempt_id
                ]
                if edge_candidates:
                    emb_edges = gm.create_embedding_edges(
                        _config["database"],
                        graph_name=graph_name,
                        attempt_id=attempt_id,
                        similar_attempt_ids=edge_candidates,
                    )
                    result["graph_embedding_edges"] = emb_edges

        return result
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


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
    try:
        search_config = _config["search"]
        effective_top_k = top_k if top_k is not None else search_config["top_k"]
        effective_threshold = threshold if threshold is not None else search_config["threshold"]

        embedding = await _embedder.embed(symptom_text)

        vector_matches = sm.find_similar(
            _config["database"],
            embedding=embedding,
            system_under_test=system_under_test,
            error_category=error_category,
            threshold=effective_threshold,
            top_k=effective_top_k,
        )
        for m in vector_matches:
            m["source"] = "vector"

        graph_matches = []
        if _graph_enabled() and (error_category or system_under_test):
            graph_cfg = _config["graph"]
            graph_results = gm.find_graph_related(
                _config["database"],
                graph_name=graph_cfg["graph_name"],
                error_category=error_category,
                current_project=system_under_test,
                limit=effective_top_k,
            )
            for gr in graph_results:
                graph_matches.append(gr)

        # Merge: deduplicate by attempt_id, mark "both" if found in both
        merged = {}
        vw = _config.get("graph", {}).get("vector_weight", 0.6)
        gw = _config.get("graph", {}).get("graph_weight", 0.4)

        for m in vector_matches:
            aid = m["attempt_id"]
            m["combined_score"] = round(m.get("similarity", 0) * vw, 4)
            merged[aid] = m

        for gm_match in graph_matches:
            aid = gm_match["attempt_id"]
            if aid in merged:
                merged[aid]["source"] = "both"
                merged[aid]["combined_score"] = round(
                    merged[aid].get("similarity", 0) * vw + 1.0 * gw, 4
                )
                merged[aid]["graph_path"] = gm_match.get("graph_path", "")
            else:
                gm_match["combined_score"] = round(1.0 * gw, 4)
                merged[aid] = gm_match

        matches = sorted(merged.values(), key=lambda x: x.get("combined_score", 0), reverse=True)
        matches = matches[:effective_top_k]

        if matches:
            top = matches[0]
            top_sim = top.get("similarity", top.get("combined_score", 0))
            if top_sim > 0.85 or top.get("source") == "both":
                recommendation = "apply_known_fix"
            elif top_sim > 0.60:
                recommendation = "review_suggestions"
            else:
                recommendation = "no_match"
        else:
            recommendation = "no_match"

        return {
            "status": "OK",
            "matches_found": len(matches),
            "matches": matches,
            "recommendation": recommendation,
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "message": str(e),
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
    try:
        total_iterations = sm.close_session(
            _config["database"],
            session_id=session_id,
            final_outcome=final_outcome,
            resolution_attempt_id=resolution_attempt_id,
            notes=notes,
        )
        return {
            "status": "OK",
            "message": f"Session closed with outcome: {final_outcome}",
            "total_iterations": total_iterations,
        }
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


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
    try:
        sessions = sm.list_sessions_filtered(
            _config["database"],
            system_under_test=system_under_test,
            environment=environment,
            final_outcome=final_outcome,
            limit=limit or 20,
        )
        return {
            "status": "OK",
            "count": len(sessions),
            "sessions": sessions,
        }
    except Exception as e:
        return {"status": "ERROR", "message": str(e), "count": 0, "sessions": []}


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
    try:
        result = sm.get_session(_config["database"], session_id)
        if not result:
            return {
                "status": "ERROR",
                "message": f"Session not found: {session_id}",
                "session": {},
                "attempts": [],
            }
        return {
            "status": "OK",
            "session": result["session"],
            "attempts": result["attempts"],
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "message": str(e),
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
    try:
        found = sm.archive_attempt_by_id(_config["database"], attempt_id)
        if not found:
            return {"status": "ERROR", "message": f"Attempt not found: {attempt_id}"}
        msg = f"Attempt archived (id={attempt_id})"
        if reason:
            msg += f" — reason: {reason}"
        return {"status": "OK", "message": msg}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


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
    try:
        found = sm.verify_attempt_by_id(_config["database"], attempt_id)
        if not found:
            return {"status": "ERROR", "message": f"Attempt not found: {attempt_id}"}
        return {"status": "OK", "message": f"Attempt verified (id={attempt_id})"}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


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
    try:
        stats = sm.get_stats(_config["database"], system_under_test)
        return {"status": "OK", **stats}
    except Exception as e:
        return {
            "status": "ERROR",
            "message": str(e),
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
