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

    Expected layout (based on your description):
        artifacts/<run_id>/jmeter/network-capture/*.json

    For now, we pick the first .json file in that folder.
    """
    base_dir = os.path.join(ARTIFACTS_PATH, str(run_id), "jmeter", "network-capture")
    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"Network capture directory not found: {base_dir}")

    candidates = [
        os.path.join(base_dir, f)
        for f in os.listdir(base_dir)
        if f.lower().endswith(".json")
    ]
    if not candidates:
        raise FileNotFoundError(f"No network capture JSON files found in: {base_dir}")

    # You can later add logic to pick the latest, or a specific pattern.
    return candidates[0]


def _load_network_data(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _classify_value_type(value: Any) -> str:
    """
    Very simple placeholder classifier for correlation candidate types.
    You can refine with regexes for GUID, JWT, etc.
    """
    if isinstance(value, int):
        return "numeric_id"
    if isinstance(value, str):
        # TODO: add GUID / JWT / etc. detection heuristics
        if len(value) > 30 and "." in value:
            return "jwt_or_token"
        # more heuristics here
        return "string"
    return "unknown"


def _iter_requests(network_data: Dict[str, Any]):
    """
    Iterate over your step-grouped capture structure.

    network_data structure (from your example):
        {
          "Step 1: Navigate to ...": [
             { "request_id": "...", "method": "GET", "url": "...", "headers": {...}, "post_data": "...", "step": {...}, "response": {...} },
             ...
          ],
          ...
        }
    """
    for step_name, entries in network_data.items():
        for entry in entries:
            yield step_name, entry


def _find_correlations(network_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Core heuristic engine:
    - Scan responses for candidate values.
    - Look for the same literal values in subsequent requests.
    - Build correlation entries with source + usages (no variable names).
    """
    correlations: List[Dict[str, Any]] = []

    # Simple approach: collect all response values of interest into a map,
    # then scan later requests for exact string matches.
    # You can optimize and refine this later.

    response_candidates: List[Dict[str, Any]] = []

    # 1) Collect response fields to consider as potential correlation sources
    for step_name, entry in _iter_requests(network_data):
        response = entry.get("response") or {}
        body_json = response.get("json")  # assuming you store parsed JSON here
        if not isinstance(body_json, dict):
            continue

        # Traverse JSON fields (shallow or deep) for now as a simple heuristic
        # You can later implement a proper recursive walker that yields json_path, value.
        for key, value in body_json.items():
            value_type = _classify_value_type(value)
            if value_type == "unknown":
                continue

            response_candidates.append(
                {
                    "step_name": step_name,
                    "entry": entry,
                    "key": key,
                    "json_path": f"$.{key}",
                    "value": value,
                    "value_type": value_type,
                }
            )

    # 2) For each candidate value, search for usages in subsequent requests
    for idx, candidate in enumerate(response_candidates):
        value = candidate["value"]
        if value is None:
            continue

        value_str = str(value)
        usages: List[Dict[str, Any]] = []

        # Only search in entries AFTER this response's entry in the sequential list
        # For now, we simply scan all entries; you can later add stricter ordering
        for step_name, entry in _iter_requests(network_data):
            req_url = entry.get("url", "")
            req_method = entry.get("method", "GET")
            headers = entry.get("headers") or {}
            post_data = entry.get("post_data") or ""

            # URL / query / path usage
            if value_str in req_url:
                usages.append(
                    {
                        "step_label": step_name,
                        "request_method": req_method,
                        "request_url": req_url,
                        "location_type": "url",
                        "location_key": None,
                        "location_pattern": "{VALUE}",
                        "request_example_fragment": req_url,
                    }
                )

            # Header usage
            for h_name, h_val in headers.items():
                if value_str in str(h_val):
                    usages.append(
                        {
                            "step_label": step_name,
                            "request_method": req_method,
                            "request_url": req_url,
                            "location_type": "header",
                            "location_key": h_name,
                            "location_pattern": "{VALUE}",
                            "request_example_fragment": f"{h_name}: {h_val}",
                        }
                    )

            # Body usage
            if isinstance(post_data, str) and value_str in post_data:
                usages.append(
                    {
                        "step_label": step_name,
                        "request_method": req_method,
                        "request_url": req_url,
                        "location_type": "raw_body_fragment",
                        "location_key": None,
                        "location_pattern": "{VALUE}",
                        "request_example_fragment": post_data[:200],
                    }
                )

        if not usages:
            continue

        corr_id = f"corr_{idx+1}"

        entry = candidate["entry"]
        response = entry.get("response") or {}
        content_type = response.get("content_type", "")

        correlations.append(
            {
                "correlation_id": corr_id,
                "type": candidate["value_type"],
                "source": {
                    "step_label": candidate["step_name"],
                    "request_method": entry.get("method", "GET"),
                    "request_url": entry.get("url", ""),
                    "response_content_type": content_type,
                    "response_json_path": candidate["json_path"],
                    "response_example_value": candidate["value"],
                },
                "usages": usages,
            }
        )

    return correlations


async def analyze_traffic(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Main underlying function for the analyze_network_traffic MCP tool.

    - Loads the network capture JSON for the given test_run_id.
    - Identifies correlation candidates and usages.
    - Writes correlation_spec.json into:
        artifacts/<test_run_id>/jmeter/correlation_spec.json

    Returns:
        dict with status, message, and correlation_spec_path.
    """
    try:
        capture_path = _get_network_capture_path(test_run_id)
    except FileNotFoundError as e:
        ctx.error(str(e))
        return {
            "status": "ERROR",
            "message": str(e),
            "test_run_id": test_run_id,
            "correlation_spec_path": None,
            "count": 0,
        }

    try:
        network_data = _load_network_data(capture_path)
        ctx.info(f"✅ Loaded network capture for correlation analysis: {capture_path}")

        correlations = _find_correlations(network_data)
        correlation_spec = {
            "capture_file": os.path.basename(capture_path),
            "application": JMETER_CONFIG.get("application_name", "unknown"),
            "spec_version": "1.0",
            "correlations": correlations,
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
        }
