# services/correlation_analyzer.py
"""
Correlation Analyzer for JMeter MCP - Version 2.0

Analyzes Playwright-derived network captures to detect dynamic correlations
between HTTP responses and subsequent requests.

Phase 1 Implementation:
- Extract candidate values from response data (headers, JSON body, redirect URLs)
- Find usages of those values in subsequent requests (URL, headers, body)
- Detect orphan IDs in request URLs (values with no identifiable source)
- Classify parameterization strategy (extract_and_reuse, csv_dataset, udv)

Phase 2 (Future):
- OAuth/PKCE token handling via services/jmx/oauth2.py
- Cross-domain cookie extraction (edge cases)
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from fastmcp import Context

from utils.config import load_config, load_jmeter_config
from utils.file_utils import save_correlation_spec

# === Configuration ===
CONFIG = load_config()
ARTIFACTS_PATH = CONFIG["artifacts"]["artifacts_path"]
JMETER_CONFIG = load_jmeter_config()

# === Patterns ===
NUMERIC_ID_RE = re.compile(r"^\d+$")
GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)
JWT_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")

# Header suffixes that indicate correlation/transaction IDs
CORRELATION_HEADER_SUFFIXES = (
    "id", "_id", "uuid", "transactionid", "correlationid",
    "requestid", "traceid", "spanid",
)

# Headers to skip when looking for correlation IDs (source extraction)
SKIP_HEADERS_SOURCE = {
    "content-type", "content-length", "cache-control", "date", "expires",
    "etag", "accept", "accept-encoding", "accept-language", "connection",
    "host", "origin", "referer", "user-agent", "cookie", "set-cookie",
    "access-control-allow-origin", "access-control-allow-credentials",
    "vary", "server", "strict-transport-security", "x-content-type-options",
    "x-frame-options", "content-encoding", "content-security-policy",
}

# Headers to skip when looking for usages (request headers that are HTTP plumbing)
SKIP_HEADERS_USAGE = {
    "content-type", "content-length", "cache-control", "date", "expires",
    "accept", "accept-encoding", "accept-language", "connection",
    "host", "origin", "referer", "user-agent", "cookie",
    "priority", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
    "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site", "sec-fetch-user",
    "upgrade-insecure-requests", "if-none-match", "if-modified-since",
    "x-requested-with", "dnt", "pragma",
    # Pseudo-headers
    ":authority", ":method", ":path", ":scheme",
}

# Minimum length for numeric IDs to avoid false positives (e.g., "1", "2")
MIN_NUMERIC_ID_LENGTH = 2

# OAuth-related parameter names (for flagging, not extraction in Phase 1)
OAUTH_PARAMS = {
    "code", "state", "nonce", "id_token", "access_token", "refresh_token",
    "code_challenge", "code_verifier", "redirect_uri", "client_id",
}

# JSON keys that likely contain IDs (for SOURCE extraction)
# Matches: id, _id, userId, user_id, prodId, prod_id, uuid, guid, etc.
ID_KEY_PATTERNS = re.compile(
    r"(^id$|_id$|Id$|ID$|^.*id$|^.*_id$|uuid|guid)", 
    re.IGNORECASE
)

# Maximum depth for JSON traversal
MAX_JSON_DEPTH = 5


# === File Loading ===

def _get_network_capture_path(run_id: str) -> str:
    """Resolve path to network capture JSON for given run_id."""
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

    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[0]


def _load_network_data(path: str) -> Dict[str, Any]:
    """Load and parse network capture JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _iter_entries(network_data: Dict[str, Any]) -> List[Tuple[int, int, str, Dict[str, Any]]]:
    """
    Flatten step-grouped data into ordered list of (entry_index, step_number, step_label, entry).
    
    Returns entries in sequential order with global entry_index for forward-only searching.
    """
    flattened: List[Tuple[int, int, str, Dict[str, Any]]] = []
    global_index = 0
    
    for step_label, entries in network_data.items():
        for entry in entries:
            step_meta = entry.get("step") or {}
            step_number = step_meta.get("step_number")
            if step_number is None:
                match = re.match(r"Step\s+(\d+)", step_label)
                step_number = int(match.group(1)) if match else 0
            flattened.append((global_index, step_number, step_label, entry))
            global_index += 1

    # Sort by step_number, preserving order within steps
    flattened.sort(key=lambda x: (x[1], x[0]))
    
    # Re-index after sorting
    return [(i, sn, sl, e) for i, (_, sn, sl, e) in enumerate(flattened)]


# === Value Classification ===

def _classify_value_type(value: Any) -> str:
    """Classify value into type category."""
    if isinstance(value, int):
        return "business_id_numeric"
    if isinstance(value, str):
        if NUMERIC_ID_RE.match(value):
            return "business_id_numeric"
        if GUID_RE.match(value):
            return "business_id_guid"
        if JWT_RE.match(value):
            return "oauth_token"  # Flag for Phase 2
        if len(value) > 20 and value.isalnum():
            return "opaque_id"
        return "string_id"
    return "unknown"


def _is_id_like_value(value: Any) -> bool:
    """Check if value looks like an ID that should be correlated."""
    if isinstance(value, int):
        # Skip very small numbers (likely not meaningful IDs)
        return value >= 10 ** (MIN_NUMERIC_ID_LENGTH - 1)  # e.g., >= 10 for length 2
    if isinstance(value, str):
        # Numeric string - must meet minimum length
        if NUMERIC_ID_RE.match(value):
            return len(value) >= MIN_NUMERIC_ID_LENGTH
        # GUID - always valid
        if GUID_RE.match(value):
            return True
        # Opaque ID (long alphanumeric)
        if len(value) >= 8 and len(value) <= 128 and re.match(r"^[A-Za-z0-9_-]+$", value):
            return True
    return False


# === URL Normalization ===

def _normalize_for_comparison(value: str) -> Set[str]:
    """Return set of normalized forms for comparison (handles URL encoding)."""
    forms = {value}
    try:
        decoded = unquote(value)
        forms.add(decoded)
    except Exception:
        pass
    return forms


def _value_matches(needle: str, haystack: str, exact: bool = False) -> bool:
    """
    Check if needle appears in haystack, considering URL encoding.
    
    Args:
        needle: The value to search for
        haystack: The string to search in
        exact: If True, require exact match. If False, use word boundary matching
               for short values to avoid false positives (e.g., "11" in UUID).
    """
    if not needle or not haystack:
        return False
    
    needle_forms = _normalize_for_comparison(needle)
    haystack_forms = _normalize_for_comparison(haystack)
    
    for n in needle_forms:
        for h in haystack_forms:
            if exact:
                # Exact match
                if n == h:
                    return True
            elif len(n) <= 4:
                # Short values: use word boundary to avoid false positives
                # Match if surrounded by non-alphanumeric or at string boundaries
                pattern = r'(?<![a-zA-Z0-9])' + re.escape(n) + r'(?![a-zA-Z0-9])'
                if re.search(pattern, h):
                    return True
            else:
                # Longer values: substring match is safe
                if n in h:
                    return True
    return False


# === Phase 1: Source Extraction ===

def _extract_from_response_headers(
    response_headers: Dict[str, Any],
    entry_index: int,
    step_number: int,
    step_label: str,
    entry: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Extract correlation IDs from response headers."""
    candidates = []
    
    for raw_key, value in (response_headers or {}).items():
        if raw_key is None or value is None:
            continue
        key = str(raw_key).lower()
        
        # Skip known non-ID headers
        if key in SKIP_HEADERS_SOURCE:
            continue
        
        # Check if header name suggests a correlation ID
        if any(key.endswith(suffix) for suffix in CORRELATION_HEADER_SUFFIXES):
            value_str = str(value)
            if value_str and len(value_str) > 0:
                candidates.append({
                    "entry_index": entry_index,
                    "step_number": step_number,
                    "step_label": step_label,
                    "request_id": entry.get("request_id"),
                    "request_method": entry.get("method", "GET"),
                    "request_url": entry.get("url", ""),
                    "response_status": entry.get("status"),
                    "source_location": "response_header",
                    "source_key": raw_key,
                    "source_json_path": None,
                    "value": value_str,
                    "value_type": _classify_value_type(value_str),
                    "candidate_type": "correlation_id",
                })
    
    return candidates


def _extract_from_redirect_url(
    response_headers: Dict[str, Any],
    entry_index: int,
    step_number: int,
    step_label: str,
    entry: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Extract values from Location header redirect URL."""
    candidates = []
    location = response_headers.get("location") if response_headers else None
    
    if not location:
        return candidates
    
    try:
        parsed = urlparse(location)
        query_params = parse_qs(parsed.query)
        
        for param_name, values in query_params.items():
            for val in values:
                # Check if it's an OAuth param (flag for Phase 2)
                is_oauth = param_name.lower() in OAUTH_PARAMS
                
                if _is_id_like_value(val) or is_oauth:
                    candidates.append({
                        "entry_index": entry_index,
                        "step_number": step_number,
                        "step_label": step_label,
                        "request_id": entry.get("request_id"),
                        "request_method": entry.get("method", "GET"),
                        "request_url": entry.get("url", ""),
                        "response_status": entry.get("status"),
                        "source_location": "response_redirect_url",
                        "source_key": param_name,
                        "source_json_path": None,
                        "value": val,
                        "value_type": "oauth_state" if is_oauth else _classify_value_type(val),
                        "candidate_type": "oauth_param" if is_oauth else "business_id",
                    })
    except Exception:
        pass  # Skip malformed URLs
    
    return candidates


def _walk_json(obj: Any, path: str = "$", depth: int = 0) -> List[Tuple[str, Any, str]]:
    """
    Recursively walk JSON object, yielding (json_path, value, key_name) tuples.
    
    Respects MAX_JSON_DEPTH to avoid overly deep traversal.
    """
    results = []
    
    if depth > MAX_JSON_DEPTH:
        return results
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_path = f"{path}.{key}"
            # Check if key looks like an ID field
            if ID_KEY_PATTERNS.search(key):
                # Only add if value is a primitive (not nested object/array)
                if isinstance(value, (str, int, float, bool)) or value is None:
                    results.append((new_path, value, key))
            # Recurse into nested objects
            if isinstance(value, (dict, list)):
                results.extend(_walk_json(value, new_path, depth + 1))
    
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            new_path = f"{path}[{i}]"
            results.extend(_walk_json(item, new_path, depth + 1))
    
    return results


def _extract_from_json_body(
    response: str,
    response_headers: Dict[str, Any],
    entry_index: int,
    step_number: int,
    step_label: str,
    entry: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Extract ID-like values from JSON response body."""
    candidates = []
    
    # Check content-type
    content_type = (response_headers or {}).get("content-type", "")
    if "json" not in content_type.lower():
        return candidates
    
    if not response or not response.strip():
        return candidates
    
    try:
        json_data = json.loads(response)
    except (json.JSONDecodeError, TypeError):
        return candidates
    
    # Walk JSON and extract ID-like values
    for json_path, value, key_name in _walk_json(json_data):
        if _is_id_like_value(value):
            value_str = str(value)
            candidates.append({
                "entry_index": entry_index,
                "step_number": step_number,
                "step_label": step_label,
                "request_id": entry.get("request_id"),
                "request_method": entry.get("method", "GET"),
                "request_url": entry.get("url", ""),
                "response_status": entry.get("status"),
                "source_location": "response_json",
                "source_key": key_name,
                "source_json_path": json_path,
                "value": value_str,
                "value_type": _classify_value_type(value),
                "candidate_type": "business_id",
            })
    
    return candidates


def _extract_from_set_cookie(
    response_headers: Dict[str, Any],
    entry_index: int,
    step_number: int,
    step_label: str,
    entry: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    STUB: Cookie extraction for cross-domain SSO edge cases.
    
    JMeter's Cookie Manager handles most cookies automatically.
    This function is reserved for future implementation of 
    cross-domain cookie pattern detection.
    
    Returns empty list - Cookie Manager handles standard cases.
    """
    # TODO: Phase 2 - Implement cross-domain cookie pattern detection
    # For now, return empty - this is an edge case
    return []


def _extract_sources(entries: List[Tuple[int, int, str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """
    Phase 1: Extract all candidate source values from response data.
    
    Sources are extracted from:
    - Response headers (correlation IDs)
    - Redirect URLs (Location header params)
    - JSON response bodies (ID-like fields)
    
    Deduplicates by value, keeping the LAST occurrence (closest to potential usage).
    """
    all_candidates = []
    
    for entry_index, step_number, step_label, entry in entries:
        response_headers = entry.get("response_headers") or {}
        response = entry.get("response", "")
        
        # Extract from response headers
        all_candidates.extend(_extract_from_response_headers(
            response_headers, entry_index, step_number, step_label, entry
        ))
        
        # Extract from redirect URL
        all_candidates.extend(_extract_from_redirect_url(
            response_headers, entry_index, step_number, step_label, entry
        ))
        
        # Extract from JSON body
        all_candidates.extend(_extract_from_json_body(
            response, response_headers, entry_index, step_number, step_label, entry
        ))
        
        # Stub for cookie extraction (edge cases)
        all_candidates.extend(_extract_from_set_cookie(
            response_headers, entry_index, step_number, step_label, entry
        ))
    
    # Deduplicate by value - keep the FIRST occurrence (earliest source)
    # This ensures we find sources BEFORE their usages in subsequent requests
    seen_values: Dict[str, Dict[str, Any]] = {}
    for candidate in all_candidates:
        value_key = str(candidate.get("value", ""))
        # Only add if not already seen (keep first occurrence)
        if value_key not in seen_values:
            seen_values[value_key] = candidate
    
    return list(seen_values.values())


# === Phase 2: Usage Detection ===

def _find_usage_in_url(value_str: str, url: str) -> List[Dict[str, Any]]:
    """Find value in request URL (path and query params)."""
    usages = []
    
    if not _value_matches(value_str, url):
        return usages
    
    try:
        parsed = urlparse(url)
        
        # Check path segments
        for segment in parsed.path.split("/"):
            if segment and _value_matches(value_str, segment):
                usages.append({
                    "location_type": "request_url_path",
                    "location_key": None,
                    "location_json_path": None,
                    "location_pattern": parsed.path.replace(segment, "{VALUE}", 1),
                    "request_example_fragment": url[:200],
                })
                break  # One match per URL
        
        # Check query params
        query_params = parse_qs(parsed.query)
        for param_name, values in query_params.items():
            for val in values:
                if _value_matches(value_str, val):
                    usages.append({
                        "location_type": "request_query_param",
                        "location_key": param_name,
                        "location_json_path": None,
                        "location_pattern": f"{param_name}={{VALUE}}",
                        "request_example_fragment": f"?{param_name}={val}"[:200],
                    })
    except Exception:
        # Fallback: simple substring match
        if value_str in url:
            usages.append({
                "location_type": "request_url_path",
                "location_key": None,
                "location_json_path": None,
                "location_pattern": "{VALUE}",
                "request_example_fragment": url[:200],
            })
    
    return usages


def _find_usage_in_headers(value_str: str, headers: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find value in request headers (skips HTTP plumbing headers)."""
    usages = []
    
    for name, val in (headers or {}).items():
        if val is None:
            continue
        
        # Skip HTTP plumbing headers that aren't correlation targets
        if name.lower() in SKIP_HEADERS_USAGE:
            continue
        
        s_val = str(val)
        if _value_matches(value_str, s_val):
            usages.append({
                "location_type": "request_header",
                "location_key": name,
                "location_json_path": None,
                "location_pattern": "{VALUE}",
                "request_example_fragment": f"{name}: {s_val}"[:200],
            })
    
    return usages


def _walk_json_all_values(
    obj: Any, 
    path: str = "$", 
    depth: int = 0
) -> List[Tuple[str, Any, str]]:
    """
    Walk JSON and extract ALL primitive values (for usage detection).
    
    Unlike _walk_json which only extracts ID-like keys, this extracts
    all values so we can find where known values are being used.
    
    Returns list of (json_path, value, key_name).
    """
    results = []
    
    if depth > MAX_JSON_DEPTH:
        return results
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_path = f"{path}.{key}"
            # Add all primitive values
            if isinstance(value, (str, int, float, bool)) or value is None:
                results.append((new_path, value, key))
            # Recurse into nested objects
            if isinstance(value, (dict, list)):
                results.extend(_walk_json_all_values(value, new_path, depth + 1))
    
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            new_path = f"{path}[{i}]"
            if isinstance(item, (str, int, float, bool)) or item is None:
                results.append((new_path, item, f"[{i}]"))
            if isinstance(item, (dict, list)):
                results.extend(_walk_json_all_values(item, new_path, depth + 1))
    
    return results


def _find_usage_in_body(value_str: str, post_data: str) -> List[Dict[str, Any]]:
    """Find value in request body."""
    usages = []
    
    if not post_data or not value_str:
        return usages
    
    # Quick check: is value possibly in the body at all?
    if not _value_matches(value_str, post_data):
        return usages
    
    # Try to parse as JSON for better location info
    try:
        json_data = json.loads(post_data)
        # Search ALL values in JSON, not just ID-like keys
        for json_path, value, key_name in _walk_json_all_values(json_data):
            str_value = str(value)
            # Use EXACT match for JSON values to avoid false positives
            if str_value == value_str:
                usages.append({
                    "location_type": "request_body_json",
                    "location_key": key_name,
                    "location_json_path": json_path,
                    "location_pattern": f"{key_name}={{VALUE}}",
                    "request_example_fragment": post_data[:200],
                })
                return usages  # One match is enough
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Fallback: plain text match (use word boundary matching for safety)
    if _value_matches(value_str, post_data):
        usages.append({
            "location_type": "request_body_text",
            "location_key": None,
            "location_json_path": None,
            "location_pattern": "{VALUE}",
            "request_example_fragment": post_data[:200],
        })
    
    return usages


def _find_usages(
    candidate: Dict[str, Any],
    entries: List[Tuple[int, int, str, Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    Phase 2: Find all usages of a candidate value in SUBSEQUENT requests.
    
    Only searches entries with index > candidate's entry_index (forward-only).
    """
    usages = []
    value_str = str(candidate.get("value", ""))
    source_entry_index = candidate.get("entry_index", -1)
    
    if not value_str:
        return usages
    
    usage_number = 0
    for entry_index, step_number, step_label, entry in entries:
        # Forward-only: only search entries AFTER the source
        if entry_index <= source_entry_index:
            continue
        
        url = entry.get("url", "")
        headers = entry.get("headers") or {}
        post_data = entry.get("post_data") or ""
        
        local_usages = []
        local_usages.extend(_find_usage_in_url(value_str, url))
        local_usages.extend(_find_usage_in_headers(value_str, headers))
        local_usages.extend(_find_usage_in_body(value_str, post_data))
        
        for u in local_usages:
            usage_number += 1
            u.update({
                "usage_number": usage_number,
                "entry_index": entry_index,
                "step_number": step_number,
                "step_label": step_label,
                "request_id": entry.get("request_id"),
                "request_method": entry.get("method", "GET"),
                "request_url": url,
            })
            usages.append(u)
    
    return usages


# === Phase 3: Orphan ID Detection ===

def _extract_ids_from_request_url(url: str) -> List[Dict[str, Any]]:
    """Extract ID-like values from a request URL."""
    ids = []
    
    try:
        parsed = urlparse(url)
        
        # Path segments
        for segment in parsed.path.split("/"):
            if segment and (NUMERIC_ID_RE.match(segment) or GUID_RE.match(segment)):
                ids.append({
                    "value": segment,
                    "location": "request_url_path",
                    "pattern": parsed.path.replace(segment, "{VALUE}", 1),
                })
        
        # Query params
        query_params = parse_qs(parsed.query)
        for param_name, values in query_params.items():
            for val in values:
                if NUMERIC_ID_RE.match(val) or GUID_RE.match(val):
                    ids.append({
                        "value": val,
                        "location": "request_query_param",
                        "location_key": param_name,
                        "pattern": f"{param_name}={{VALUE}}",
                    })
    except Exception:
        pass
    
    return ids


def _detect_orphan_ids(
    entries: List[Tuple[int, int, str, Dict[str, Any]]],
    known_source_values: Set[str]
) -> List[Dict[str, Any]]:
    """
    Phase 3: Detect ID-like values in request URLs that have no source.
    
    These are flagged as low-confidence correlations requiring parameterization.
    """
    orphans = []
    seen_values: Set[str] = set()  # Avoid duplicates
    
    for entry_index, step_number, step_label, entry in entries:
        url = entry.get("url", "")
        url_ids = _extract_ids_from_request_url(url)
        
        for id_info in url_ids:
            value = id_info["value"]
            
            # Skip if we've seen this value before
            if value in seen_values:
                continue
            seen_values.add(value)
            
            # Skip if this value has a known source
            if value in known_source_values:
                continue
            
            orphans.append({
                "entry_index": entry_index,
                "step_number": step_number,
                "step_label": step_label,
                "request_id": entry.get("request_id"),
                "request_method": entry.get("method", "GET"),
                "request_url": url,
                "response_status": None,
                "source_location": id_info["location"],
                "source_key": id_info.get("location_key"),
                "source_json_path": None,
                "value": value,
                "value_type": _classify_value_type(value),
                "candidate_type": "orphan_id",
                "location_pattern": id_info.get("pattern"),
            })
    
    return orphans


# === Phase 1.5: Parameterization Strategy ===

def _classify_parameterization_strategy(
    correlation_found: bool,
    usage_count: int
) -> Dict[str, Any]:
    """
    Classify parameterization strategy based on correlation status and usage count.
    
    Rules:
    - Has source → extract_and_reuse (needs JSON/Regex Extractor)
    - No source, ≥3 occurrences → csv_dataset
    - No source, 1-2 occurrences → user_defined_variable
    """
    if correlation_found:
        return {
            "strategy": "extract_and_reuse",
            "extractor_type": "regex",  # Could be json_extractor based on source
            "reason": "Value found in prior response",
        }
    
    if usage_count >= 3:
        return {
            "strategy": "csv_dataset",
            "reason": f"Value appears {usage_count} times, no source found",
        }
    
    return {
        "strategy": "user_defined_variable",
        "reason": f"Value appears {usage_count} time(s), no source found",
    }


# === Main Correlation Logic ===

def _find_correlations(network_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Main correlation detection driver.
    
    Returns:
        Tuple of (correlations list, summary dict)
    """
    entries = _iter_entries(network_data)
    if not entries:
        return [], {}
    
    # Phase 1: Extract sources from responses
    source_candidates = _extract_sources(entries)
    
    # Track known source values for orphan detection
    known_source_values: Set[str] = {str(c["value"]) for c in source_candidates}
    
    correlations: List[Dict[str, Any]] = []
    correlation_counter = 0
    
    # Phase 2: Find usages for each source candidate
    for candidate in source_candidates:
        usages = _find_usages(candidate, entries)
        
        # Only emit correlations where value flows forward at least once
        if not usages:
            continue
        
        correlation_counter += 1
        correlation_id = f"corr_{correlation_counter}"
        
        # Determine extractor type based on source location
        extractor_type = "regex"
        if candidate.get("source_location") == "response_json":
            extractor_type = "json"
        
        param_hint = _classify_parameterization_strategy(True, len(usages))
        param_hint["extractor_type"] = extractor_type
        
        correlation = {
            "correlation_id": correlation_id,
            "type": candidate.get("candidate_type", "unknown"),
            "value_type": candidate.get("value_type", "unknown"),
            "confidence": "high",
            "correlation_found": True,
            "source": {
                "step_number": candidate.get("step_number"),
                "step_label": candidate.get("step_label"),
                "entry_index": candidate.get("entry_index"),
                "request_id": candidate.get("request_id"),
                "request_method": candidate.get("request_method"),
                "request_url": candidate.get("request_url"),
                "response_status": candidate.get("response_status"),
                "source_location": candidate.get("source_location"),
                "source_key": candidate.get("source_key"),
                "source_json_path": candidate.get("source_json_path"),
                "response_example_value": candidate.get("value"),
            },
            "usages": usages,
            "parameterization_hint": param_hint,
        }
        
        correlations.append(correlation)
    
    # Phase 3: Detect orphan IDs
    orphan_candidates = _detect_orphan_ids(entries, known_source_values)
    
    for orphan in orphan_candidates:
        # Count occurrences of this value across all entries
        value_str = str(orphan["value"])
        occurrence_count = 1
        for _, _, _, entry in entries:
            url = entry.get("url", "")
            post_data = entry.get("post_data") or ""
            if value_str in url or value_str in post_data:
                occurrence_count += 1
        
        correlation_counter += 1
        correlation_id = f"corr_{correlation_counter}"
        
        param_hint = _classify_parameterization_strategy(False, occurrence_count)
        
        correlation = {
            "correlation_id": correlation_id,
            "type": "orphan_id",
            "value_type": orphan.get("value_type", "unknown"),
            "confidence": "low",
            "correlation_found": False,
            "source": {
                "step_number": orphan.get("step_number"),
                "step_label": orphan.get("step_label"),
                "entry_index": orphan.get("entry_index"),
                "request_id": orphan.get("request_id"),
                "request_method": orphan.get("request_method"),
                "request_url": orphan.get("request_url"),
                "response_status": None,
                "source_location": orphan.get("source_location"),
                "source_key": orphan.get("source_key"),
                "source_json_path": None,
                "response_example_value": orphan.get("value"),
            },
            "usages": [],
            "parameterization_hint": param_hint,
            "notes": "Value found in request URL but not in any prior response. "
                     "Recommend parameterization via CSV Data Set or User Defined Variables.",
        }
        
        correlations.append(correlation)
    
    # Build summary
    summary = {
        "total_correlations": len(correlations),
        "business_ids": sum(1 for c in correlations if c.get("type") == "business_id"),
        "correlation_ids": sum(1 for c in correlations if c.get("type") == "correlation_id"),
        "oauth_params": sum(1 for c in correlations if c.get("type") == "oauth_param"),
        "orphan_ids": sum(1 for c in correlations if c.get("type") == "orphan_id"),
        "high_confidence": sum(1 for c in correlations if c.get("confidence") == "high"),
        "low_confidence": sum(1 for c in correlations if c.get("confidence") == "low"),
    }
    
    return correlations, summary


# === Public API ===

async def analyze_traffic(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Main entry point for the analyze_network_traffic MCP tool.
    
    Analyzes network capture for correlations and writes correlation_spec.json.
    
    Args:
        test_run_id: Unique identifier for the test run.
        ctx: FastMCP context for logging.
    
    Returns:
        dict with status, message, correlation_spec_path, count, and summary.
    """
    try:
        capture_path = _get_network_capture_path(test_run_id)
    except FileNotFoundError as e:
        msg = str(e)
        await ctx.error(msg)
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
        await ctx.info(f"✅ Loaded network capture: {capture_path}")

        correlations, summary = _find_correlations(network_data)

        correlation_spec = {
            "capture_file": os.path.basename(capture_path),
            "application": JMETER_CONFIG.get("application_name", "unknown"),
            "spec_version": "2.0",
            "analyzer_version": "2.0.0",
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "total_steps": len(network_data),
            "total_entries": sum(len(v) for v in network_data.values()),
            "correlations": correlations,
            "summary": summary,
        }

        output_path = save_correlation_spec(test_run_id, correlation_spec)
        msg = f"Correlation analysis complete: {len(correlations)} correlations found"
        await ctx.info(f"✅ {msg}: {output_path}")

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
        await ctx.error(msg)
        return {
            "status": "ERROR",
            "message": msg,
            "test_run_id": test_run_id,
            "correlation_spec_path": None,
            "count": 0,
            "summary": {},
        }
