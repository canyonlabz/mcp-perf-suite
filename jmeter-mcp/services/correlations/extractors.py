"""
Phase 1: Source extraction from response data.

Extracts candidate values from:
- Response headers (correlation IDs)
- Redirect URLs (Location header params)
- JSON response bodies (ID-like fields)
- Set-Cookie headers (edge cases - stub)
"""

import json
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

from .classifiers import classify_value_type, is_id_like_value
from .constants import (
    CORRELATION_HEADER_SUFFIXES,
    OAUTH_PARAMS,
    SKIP_HEADERS_SOURCE,
)
from .utils import walk_json


def extract_from_response_headers(
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
                    "value_type": classify_value_type(value_str),
                    "candidate_type": "correlation_id",
                })
    
    return candidates


def extract_from_redirect_url(
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
                
                if is_id_like_value(val) or is_oauth:
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
                        "value_type": "oauth_state" if is_oauth else classify_value_type(val),
                        "candidate_type": "oauth_param" if is_oauth else "business_id",
                    })
    except Exception:
        pass  # Skip malformed URLs
    
    return candidates


def extract_from_json_body(
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
    for json_path, value, key_name in walk_json(json_data):
        if is_id_like_value(value):
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
                "value_type": classify_value_type(value),
                "candidate_type": "business_id",
            })
    
    return candidates


def extract_from_set_cookie(
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
    return []


def extract_sources(
    entries: List[Tuple[int, int, str, Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    Phase 1: Extract all candidate source values from response data.
    
    Sources are extracted from:
    - Response headers (correlation IDs)
    - Redirect URLs (Location header params)
    - JSON response bodies (ID-like fields)
    
    Deduplicates by value, keeping the FIRST occurrence (earliest source).
    """
    all_candidates = []
    
    for entry_index, step_number, step_label, entry in entries:
        response_headers = entry.get("response_headers") or {}
        response = entry.get("response", "")
        
        # Extract from response headers
        all_candidates.extend(extract_from_response_headers(
            response_headers, entry_index, step_number, step_label, entry
        ))
        
        # Extract from redirect URL
        all_candidates.extend(extract_from_redirect_url(
            response_headers, entry_index, step_number, step_label, entry
        ))
        
        # Extract from JSON body
        all_candidates.extend(extract_from_json_body(
            response, response_headers, entry_index, step_number, step_label, entry
        ))
        
        # Stub for cookie extraction (edge cases)
        all_candidates.extend(extract_from_set_cookie(
            response_headers, entry_index, step_number, step_label, entry
        ))
    
    # Deduplicate by value - keep the FIRST occurrence (earliest source)
    seen_values: Dict[str, Dict[str, Any]] = {}
    for candidate in all_candidates:
        value_key = str(candidate.get("value", ""))
        if value_key not in seen_values:
            seen_values[value_key] = candidate
    
    return list(seen_values.values())
