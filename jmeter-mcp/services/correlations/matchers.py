"""
Phase 2 & 3: Usage detection and orphan ID detection.

Phase 2: Find usages of source values in subsequent requests
Phase 3: Detect orphan IDs (values in requests with no identifiable source)
"""

import json
from typing import Any, Dict, List, Set, Tuple
from urllib.parse import parse_qs, urlparse

from .classifiers import classify_value_type
from .constants import GUID_RE, NUMERIC_ID_RE, SKIP_HEADERS_USAGE, ID_KEY_PATTERNS
from .utils import value_matches, walk_json_all_values


# === Phase 2: Usage Detection ===

def find_usage_in_url(value_str: str, url: str) -> List[Dict[str, Any]]:
    """Find value in request URL (path and query params)."""
    usages = []
    
    if not value_matches(value_str, url):
        return usages
    
    try:
        parsed = urlparse(url)
        
        # Check path segments
        for segment in parsed.path.split("/"):
            if segment and value_matches(value_str, segment):
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
                if value_matches(value_str, val):
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


def find_usage_in_headers(value_str: str, headers: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find value in request headers (skips HTTP plumbing headers)."""
    usages = []
    
    for name, val in (headers or {}).items():
        if val is None:
            continue
        
        # Skip HTTP plumbing headers that aren't correlation targets
        if name.lower() in SKIP_HEADERS_USAGE:
            continue
        
        s_val = str(val)
        if value_matches(value_str, s_val):
            usages.append({
                "location_type": "request_header",
                "location_key": name,
                "location_json_path": None,
                "location_pattern": "{VALUE}",
                "request_example_fragment": f"{name}: {s_val}"[:200],
            })
    
    return usages


def find_usage_in_body(value_str: str, post_data: str) -> List[Dict[str, Any]]:
    """Find value in request body."""
    usages = []
    
    if not post_data or not value_str:
        return usages
    
    # Quick check: is value possibly in the body at all?
    if not value_matches(value_str, post_data):
        return usages
    
    # Try to parse as JSON for better location info
    try:
        json_data = json.loads(post_data)
        # Search ALL values in JSON, not just ID-like keys
        for json_path, value, key_name in walk_json_all_values(json_data):
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
    
    # Fallback: plain text match
    if value_matches(value_str, post_data):
        usages.append({
            "location_type": "request_body_text",
            "location_key": None,
            "location_json_path": None,
            "location_pattern": "{VALUE}",
            "request_example_fragment": post_data[:200],
        })
    
    return usages


def find_usages(
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
        local_usages.extend(find_usage_in_url(value_str, url))
        local_usages.extend(find_usage_in_headers(value_str, headers))
        local_usages.extend(find_usage_in_body(value_str, post_data))
        
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

def _is_id_like_param_name(param_name: str) -> bool:
    """
    Check if a query parameter name suggests it contains an ID value.
    
    Matches patterns like: appGuid, messagebusguid, userId, client_id, etc.
    Uses the same ID_KEY_PATTERNS as JSON extraction for consistency.
    """
    return bool(ID_KEY_PATTERNS.search(param_name))


def extract_ids_from_request_url(url: str) -> List[Dict[str, Any]]:
    """
    Extract ID-like values from a request URL.
    
    Detects IDs based on:
    1. Value format: numeric IDs or GUIDs (standard UUID format)
    2. Parameter name: if the parameter name suggests it's an ID field
       (e.g., appGuid, messagebusguid, userId, client_id)
    """
    ids = []
    
    try:
        parsed = urlparse(url)
        
        # Path segments - check by value format only
        for segment in parsed.path.split("/"):
            if segment and (NUMERIC_ID_RE.match(segment) or GUID_RE.match(segment)):
                ids.append({
                    "value": segment,
                    "location": "request_url_path",
                    "pattern": parsed.path.replace(segment, "{VALUE}", 1),
                })
        
        # Query params - check by value format OR parameter name pattern
        query_params = parse_qs(parsed.query)
        for param_name, values in query_params.items():
            for val in values:
                # Extract if value looks like an ID (numeric or GUID)
                value_is_id = NUMERIC_ID_RE.match(val) or GUID_RE.match(val)
                
                # Also extract if parameter name suggests it's an ID field
                # but only if value is non-trivial (has some length)
                name_suggests_id = _is_id_like_param_name(param_name) and len(val) >= 2
                
                if value_is_id or name_suggests_id:
                    ids.append({
                        "value": val,
                        "location": "request_query_param",
                        "location_key": param_name,
                        "pattern": f"{param_name}={{VALUE}}",
                    })
    except Exception:
        pass
    
    return ids


def detect_orphan_ids(
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
        url_ids = extract_ids_from_request_url(url)
        
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
                "value_type": classify_value_type(value),
                "candidate_type": "orphan_id",
                "location_pattern": id_info.get("pattern"),
            })
    
    return orphans
