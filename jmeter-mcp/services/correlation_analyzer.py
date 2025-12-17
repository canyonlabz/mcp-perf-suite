# services/correlation_analyzer.py
"""
correlation_analyzer.py

Phase 1 implementation of the correlation analyzer for JMeter MCP.

Responsibilities:
- Load the step-aware network capture JSON produced by playwright_adapter.py.
- Identify candidate values that may require correlation/parameterization:
  - Business IDs / GUIDs in URLs.
  - Correlation/transaction IDs in response headers.
  - (Placeholder) OAuth-related tokens for future handling.
- Detect value flows (response -> later request) in a conservative, heuristic way.
- Emit correlation_spec.json under:
    artifacts/<run_id>/jmeter/correlation_spec.json

NOTE:
This is a FIRST DRAFT focused on core correlations (IDs and correlation IDs).
OAuth 2.0 / PKCE-specific logic will be added later, likely via a dedicated
services/jmx/oauth2.py module. All such logic is explicitly marked with TODOs.
"""
import json
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from fastmcp import Context
from utils.config import load_config, load_jmeter_config
from utils.file_utils import save_correlation_spec

# === Global configuration ===
CONFIG = load_config()
ARTIFACTS_PATH = CONFIG["artifacts"]["artifacts_path"]
JMETER_CONFIG = load_jmeter_config()

# Simple regexes for numeric IDs and GUIDs
NUMERIC_ID_RE = re.compile(r"^\d+$")
GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)

# Header name patterns that often carry correlation IDs
CORRELATION_KEY_SUFFIXES = (
    "id",
    "_id",
    "uuid",
    "transactionid",
    "correlationid",
    "requestid",
    "traceid",
    "spanid",
)

# Explicit auth token keys we care about (Phase 2: OAuth module)
OAUTH_TOKEN_KEYS = {
    "access_token",
    "id_token",
    "refresh_token",
    "session_token",
    "auth_token",
    # NOTE: OAuth_Refresh_Token and similar env-specific cookies are intentionally excluded.
}

def _get_network_capture_path(run_id: str) -> str:
    """
    Resolve the path to the network capture JSON for a given run_id.

    Layout (per playwright_adapter.write_step_network_capture):
        artifacts/<run_id>/jmeter/network-capture/network_capture_<timestamp>.json
    """
    base_dir = os.path.join(ARTIFACTS_PATH, str(run_id), "jmeter", "network-capture")
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"Network capture directory not found: {base_dir}")

    candidates: List[str] = [
        os.path.join(base_dir, f)
        for f in os.listdir(base_dir)
        if f.lower().endswith(".json")
    ]
    if not candidates:
        raise FileNotFoundError(f"No network capture JSON files found in: {base_dir}")

    # For now, pick the most recently modified capture file
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]


def _load_network_data(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _iter_entries(network_data: Dict[str, Any]) -> List[Tuple[int, str, Dict[str, Any]]]:
    """
    Flatten the step-aware mapping into a list of (step_number, step_label, entry),
    preserving the natural order of steps as they appear in the JSON.

    Each entry is expected to have:
        entry["step"] = {"step_number": int, "instructions": str, "timestamp": str}
    """
    flattened: List[Tuple[int, str, Dict[str, Any]]] = []
    for step_label, entries in network_data.items():
        for entry in entries:
            step_meta = entry.get("step") or {}
            step_number = step_meta.get("step_number")
            if step_number is None:
                # Fallback: try to infer from label like "Step 1: ..."
                match = re.match(r"Step\s+(\d+)", step_label)
                if match:
                    step_number = int(match.group(1))
                else:
                    step_number = 0
            flattened.append((step_number, step_label, entry))

    # Sort by step_number, but keep relative order for identical step_numbers
    flattened.sort(key=lambda x: x[0])
    return flattened


def _classify_value(value: Any) -> str:
    """
    Basic value classification for Phase 1.
    This intentionally does NOT parse JWTs or do deep entropy analysis yet.

    Returns a coarse type: "numeric_id", "guid_id", "string_id", or "unknown".
    """
    if isinstance(value, int):
        return "numeric_id"
    if isinstance(value, str):
        if NUMERIC_ID_RE.match(value):
            return "numeric_id"
        if GUID_RE.match(value):
            return "guid_id"
        # Additional heuristics for opaque IDs can be added here.
        return "string_id"
    return "unknown"


def _extract_ids_from_url(url: str) -> List[Dict[str, Any]]:
    """
    Extract candidate business IDs from a URL's path and query components.

    - Path segments that are numeric or GUID-shaped.
    - Query parameter values that are numeric or GUID-shaped.

    Returns a list of:
        {
            "source_location": "url_path" | "url_query",
            "source_key": <param_name or None>,
            "value": <value>,
            "location_pattern": <descriptive pattern, e.g. "/claims/{VALUE}">
        }
    """
    from urllib.parse import urlparse, parse_qs

    candidates: List[Dict[str, Any]] = []
    parsed = urlparse(url)

    # Path segments
    path_segments = [seg for seg in parsed.path.split("/") if seg]
    for seg in path_segments:
        if NUMERIC_ID_RE.match(seg) or GUID_RE.match(seg):
            candidates.append(
                {
                    "source_location": "url_path",
                    "source_key": None,
                    "value": seg,
                    "location_pattern": parsed.path.replace(seg, "{VALUE}", 1),
                }
            )

    # Query params
    query_params = parse_qs(parsed.query)
    for key, vals in query_params.items():
        for val in vals:
            if NUMERIC_ID_RE.match(val) or GUID_RE.match(val):
                candidates.append(
                    {
                        "source_location": "url_query",
                        "source_key": key,
                        "value": val,
                        "location_pattern": f"{key}={{VALUE}}",
                    }
                )

    return candidates


def _extract_header_id_candidates(headers: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Find candidate correlation/transaction IDs in headers based on key suffix patterns.

    This is used primarily on response_headers, but can also be used on request headers.

    Returns a list of:
        {
            "source_location": "response_header" or "request_header",
            "source_key": <header_name>,
            "value": <header_value>,
        }
    """
    candidates: List[Dict[str, Any]] = []
    for raw_key, value in (headers or {}).items():
        if raw_key is None:
            continue
        key = str(raw_key).lower()
        # Ignore well-known non-id headers
        if key in ("content-type", "content-length", "cache-control", "accept", "accept-encoding"):
            continue

        if any(key.endswith(suffix) for suffix in CORRELATION_KEY_SUFFIXES):
            if value:
                candidates.append(
                    {
                        "source_location": "response_header",  # caller may override
                        "source_key": raw_key,
                        "value": str(value),
                    }
                )
    return candidates


def _extract_response_candidates(
    entries: List[Tuple[int, str, Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    Phase 1: extract candidate correlation sources from responses and URLs.

    For each entry:
    - Extract URL-based IDs (business IDs).
    - Extract correlation/transaction IDs from response headers.

    NOTE: OAuth-specific extraction is deferred to a future phase; here we only
    capture generic ID-like patterns.
    """
    candidates: List[Dict[str, Any]] = []

    for step_number, step_label, entry in entries:
        request_id = entry.get("request_id")
        method = entry.get("method", "GET")
        url = entry.get("url", "")
        status = entry.get("status")
        response_headers = entry.get("response_headers") or {}

        # 1) Business IDs from URL
        url_id_candidates = _extract_ids_from_url(url)
        for c in url_id_candidates:
            value = c["value"]
            value_type = _classify_value(value)
            candidates.append(
                {
                    "candidate_type": "business_id",
                    "step_number": step_number,
                    "step_label": step_label,
                    "request_id": request_id,
                    "request_method": method,
                    "request_url": url,
                    "response_status": status,
                    "source_location": c["source_location"],
                    "source_key": c["source_key"],
                    "source_header_name": None,
                    "source_json_path": None,
                    "value": value,
                    "value_type": value_type,
                    "location_pattern": c["location_pattern"],
                }
            )

        # 2) Correlation/transaction IDs from response headers
        header_candidates = _extract_header_id_candidates(response_headers)
        for hc in header_candidates:
            value = hc["value"]
            value_type = _classify_value(value)
            candidates.append(
                {
                    "candidate_type": "correlation_id",
                    "step_number": step_number,
                    "step_label": step_label,
                    "request_id": request_id,
                    "request_method": method,
                    "request_url": url,
                    "response_status": status,
                    "source_location": "response_header",
                    "source_key": hc["source_key"],
                    "source_header_name": hc["source_key"],
                    "source_json_path": None,
                    "value": value,
                    "value_type": value_type,
                    "location_pattern": None,
                }
            )

        # TODO Phase 2: OAuth token extraction from response headers/body/cookies

    return candidates


def _usage_in_headers(value_str: str, headers: Dict[str, Any]) -> List[Dict[str, Any]]:
    usages: List[Dict[str, Any]] = []
    for name, val in (headers or {}).items():
        if val is None:
            continue
        s_val = str(val)
        if value_str and value_str in s_val:
            usages.append(
                {
                    "location_type": "header",
                    "location_key": name,
                    "location_json_path": None,
                    "location_pattern": "{VALUE}",
                    "request_example_fragment": f"{name}: {s_val}"[:200],
                }
            )
    return usages


def _usage_in_url(value_str: str, url: str) -> List[Dict[str, Any]]:
    usages: List[Dict[str, Any]] = []
    if value_str and value_str in (url or ""):
        usages.append(
            {
                "location_type": "url",
                "location_key": None,
                "location_json_path": None,
                "location_pattern": "{VALUE}",
                "request_example_fragment": url[:200],
            }
        )
    return usages


def _usage_in_body(value_str: str, body: str) -> List[Dict[str, Any]]:
    usages: List[Dict[str, Any]] = []
    if not value_str:
        return usages
    if not body:
        return usages

    body_str = str(body)
    if value_str in body_str:
        usages.append(
            {
                "location_type": "request_body_fragment",
                "location_key": None,
                "location_json_path": None,
                "location_pattern": "{VALUE}",
                "request_example_fragment": body_str[:200],
            }
        )
    # TODO Phase 2: if body is JSON, derive location_json_path
    return usages


def _find_usages_for_candidate(
    candidate_index: int,
    candidate: Dict[str, Any],
    entries: List[Tuple[int, str, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    For a given candidate value, search all SUBSEQUENT entries for occurrences
    in request headers, URL, and body.

    This uses a simple value_str substring search; Phase 2 may add more robust
    normalization (e.g., URL decoding).
    """
    usages: List[Dict[str, Any]] = []
    value = candidate.get("value")
    if value is None:
        return usages

    value_str = str(value)
    # Treat candidate_index as flattened index into entries
    # We'll search entries with index > candidate_index
    for idx in range(candidate_index + 1, len(entries)):
        step_number, step_label, entry = entries[idx]
        req_headers = entry.get("headers") or {}
        url = entry.get("url", "")
        body = entry.get("post_data") or ""

        local_usages: List[Dict[str, Any]] = []
        local_usages.extend(_usage_in_headers(value_str, req_headers))
        local_usages.extend(_usage_in_url(value_str, url))
        local_usages.extend(_usage_in_body(value_str, body))

        if local_usages:
            for u in local_usages:
                u.update(
                    {
                        "step_number": step_number,
                        "step_label": step_label,
                        "request_id": entry.get("request_id"),
                        "request_method": entry.get("method", "GET"),
                        "request_url": url,
                        "is_same_value": True,
                    }
                )
            usages.extend(local_usages)

    return usages


def _find_correlations(network_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    High-level driver:
    - Flatten entries.
    - Extract response/URL candidates.
    - For each candidate, search for usages in subsequent entries.
    - Build correlation records for candidates with at least one usage.

    This function is intentionally conservative. It is expected that
    smoke testing will reveal where heuristics need tightening or loosening.
    """
    entries = _iter_entries(network_data)
    if not entries:
        return []

    candidates = _extract_response_candidates(entries)
    correlations: List[Dict[str, Any]] = []

    for idx, cand in enumerate(candidates):
        usages = _find_usages_for_candidate(idx, cand, entries)
        if not usages:
            # We only emit correlations where the value flows forward at least once.
            continue

        correlation_id = f"corr_{len(correlations) + 1}"
        cand_type = cand.get("candidate_type", "unknown")
        value_type = cand.get("value_type", "unknown")

        # Confidence: high if candidate comes from a response and flows into later requests
        confidence = "high"

        source = {
            "step_number": cand.get("step_number"),
            "step_label": cand.get("step_label"),
            "request_id": cand.get("request_id"),
            "request_method": cand.get("request_method"),
            "request_url": cand.get("request_url"),
            "response_status": cand.get("response_status"),
            "response_content_type": (cand.get("response_headers") or {}).get("content-type")
            if cand.get("response_headers")
            else None,
            "source_location": cand.get("source_location"),
            "source_key": cand.get("source_key"),
            "source_json_path": cand.get("source_json_path"),
            "source_header_name": cand.get("source_header_name"),
            "response_example_value": cand.get("value"),
            "response_example_excerpt": None,  # Placeholder, can be enriched later
        }

        correlation = {
            "correlation_id": correlation_id,
            "type": cand_type if cand_type != "unknown" else value_type,
            "value_type": value_type,
            "confidence": confidence,
            "correlation_found": True,
            "source": source,
            "usages": usages,
        }

        correlations.append(correlation)

    return correlations


async def analyze_traffic(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Main underlying function for the analyze_network_traffic MCP tool.

    - Loads the network capture JSON for the given test_run_id.
    - Identifies correlation candidates and their usages.
    - Writes correlation_spec.json into:
        artifacts/<test_run_id>/jmeter/correlation_spec.json

    Returns:
        dict: status + metadata about the analysis.
    """
    try:
        capture_path = _get_network_capture_path(test_run_id)
    except FileNotFoundError as e:
        msg = str(e)
        ctx.error(msg)
        return {
            "status": "ERROR",
            "message": msg,
            "test_run_id": test_run_id,
            "correlation_spec_path": None,
            "count": 0,
            "summary": {},
        }

    try:
        network_data = _load_network_data(capture_path)
        ctx.info(f"✅ Loaded network capture for correlation analysis: {capture_path}")

        correlations = _find_correlations(network_data)

        summary = {
            "total_correlations": len(correlations),
            "oauth_tokens": 0,      # TODO Phase 2: populate
            "business_ids": sum(1 for c in correlations if c.get("type") == "business_id"),
            "correlation_ids": sum(1 for c in correlations if c.get("type") == "correlation_id"),
            "high_confidence": sum(1 for c in correlations if c.get("confidence") == "high"),
            "low_confidence": sum(1 for c in correlations if c.get("confidence") == "low"),
            "unmatched_candidates": 0,  # TODO: Phase 2 for URL IDs without sources
        }

        correlation_spec = {
            "capture_file": os.path.basename(capture_path),
            "application": JMETER_CONFIG.get("application_name", "unknown"),
            "spec_version": "1.0",
            "analyzer_version": "1.0.0",
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "total_steps": len(network_data),
            "total_entries": sum(len(v) for v in network_data.values()),
            "correlations": correlations,
            "summary": summary,
        }

        output_path = save_correlation_spec(test_run_id, correlation_spec)
        msg = f"Correlation spec generated with {len(correlations)} entries: {output_path}"
        ctx.info(msg)

        return {
            "status": "OK",
            "message": msg,
            "test_run_id": test_run_id,
            "correlation_spec_path": output_path,
            "count": len(correlations),
            "summary": summary,
        }

    except Exception as e:
        msg = f"Error during correlation analysis: {e}"
        ctx.error(msg)
        return {
            "status": "ERROR",
            "message": msg,
            "test_run_id": test_run_id,
            "correlation_spec_path": None,
            "count": 0,
            "summary": {},
        }
