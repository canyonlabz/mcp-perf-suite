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
    NONCE_COOKIE_KEYWORDS,
    OAUTH_PARAMS,
    OAUTH_TOKEN_FIELDS,
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
    """Extract ID-like values and OAuth tokens from JSON response body."""
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
    
    # Build set of OAuth token field names (lowercase for comparison)
    oauth_token_fields_lower = {f.lower() for f in OAUTH_TOKEN_FIELDS}
    
    # First, explicitly extract OAuth token fields from top-level JSON
    # (These may not match ID_KEY_PATTERNS used by walk_json)
    if isinstance(json_data, dict):
        for key_name, value in json_data.items():
            if key_name.lower() in oauth_token_fields_lower:
                value_str = str(value) if value is not None else ""
                if value_str:
                    suggested_var = _get_oauth_token_var_name(key_name)
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
                        "source_json_path": f"$.{key_name}",
                        "value": value_str,
                        "value_type": "oauth_token",
                        "candidate_type": "oauth_param",
                        "suggested_var_name": suggested_var,
                    })
    
    # Then walk JSON for ID-like values (using existing ID_KEY_PATTERNS)
    for json_path, value, key_name in walk_json(json_data):
        # Skip if already added as OAuth token
        if key_name.lower() in oauth_token_fields_lower:
            continue
            
        value_str = str(value) if value is not None else ""
        
        if is_id_like_value(value):
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


def _get_oauth_token_var_name(field_name: str) -> str:
    """Map OAuth token field names to suggested JMeter variable names."""
    field_lower = field_name.lower()
    
    # Map common OAuth token field names
    mapping = {
        "cdssotoken": "cdssotoken",
        "tokenid": "token_id",
        "access_token": "access_token",
        "accesstoken": "access_token",
        "id_token": "bearer_token",  # id_token is used as Bearer
        "idtoken": "bearer_token",
        "refresh_token": "refresh_token",
        "refreshtoken": "refresh_token",
    }
    
    return mapping.get(field_lower, field_lower)


def extract_from_html_form_post(
    response: str,
    response_headers: Dict[str, Any],
    entry_index: int,
    step_number: int,
    step_label: str,
    entry: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Extract OAuth tokens from HTML form_post response mode.
    
    OAuth 2.0 form_post response mode returns tokens in an HTML page with
    hidden form fields that auto-submit:
    
    <form method="post" action="...">
        <input type="hidden" name="id_token" value="eyJ0eXAi..."/>
        <input type="hidden" name="code" value="..."/>
        <input type="hidden" name="state" value="..."/>
    </form>
    
    Returns:
        List of candidate values for correlation (id_token, code, state).
    """
    import re
    candidates = []
    
    # Check content-type is HTML
    content_type = (response_headers or {}).get("content-type", "")
    if "html" not in content_type.lower():
        return candidates
    
    if not response or not response.strip():
        return candidates
    
    # Pattern to extract hidden input values: <input type="hidden" name="NAME" value="VALUE"/>
    # Handle various HTML quote styles and attribute orders
    hidden_input_pattern = re.compile(
        r'<input[^>]*type=["\']hidden["\'][^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\'][^>]*/?>',
        re.IGNORECASE
    )
    
    # Also handle reversed attribute order (name before type)
    hidden_input_pattern_alt = re.compile(
        r'<input[^>]*name=["\']([^"\']+)["\'][^>]*type=["\']hidden["\'][^>]*value=["\']([^"\']*)["\'][^>]*/?>',
        re.IGNORECASE
    )
    
    # Fields we care about in form_post responses
    oauth_form_fields = {"id_token", "code", "state", "access_token", "token_type"}
    
    for pattern in [hidden_input_pattern, hidden_input_pattern_alt]:
        for match in pattern.finditer(response):
            field_name = match.group(1)
            field_value = match.group(2)
            
            if field_name.lower() in oauth_form_fields and field_value:
                # Determine variable name suggestion
                var_name_map = {
                    "id_token": "bearer_token",
                    "code": "oauth_code",
                    "state": "oauth_state",
                    "access_token": "access_token",
                    "token_type": "token_type",
                }
                suggested_var = var_name_map.get(field_name.lower(), field_name.lower())
                
                candidates.append({
                    "entry_index": entry_index,
                    "step_number": step_number,
                    "step_label": step_label,
                    "request_id": entry.get("request_id"),
                    "request_method": entry.get("method", "GET"),
                    "request_url": entry.get("url", ""),
                    "response_status": entry.get("status"),
                    "source_location": "response_html_form",
                    "source_key": field_name,
                    "source_json_path": None,
                    "value": field_value,
                    "value_type": "oauth_token" if field_name.lower() in {"id_token", "access_token"} else "oauth_param",
                    "candidate_type": "oauth_param",
                    "suggested_var_name": suggested_var,
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
    Extract nonce values from Set-Cookie response headers.
    
    JMeter's Cookie Manager handles most cookies automatically, but some
    OAuth/SSO nonce values in cookies are used in subsequent request headers
    (like x-cdsso-nonce) and need to be correlated.
    
    Uses generic detection based on cookie names containing keywords like
    "nonce" or "csrf" (case-insensitive). Does NOT use company-specific patterns.
    
    Returns:
        List of candidate values for correlation.
    """
    import re
    candidates = []
    set_cookie = response_headers.get("set-cookie") if response_headers else None
    
    if not set_cookie:
        return candidates
    
    # Handle both string and list of cookies
    cookies = [set_cookie] if isinstance(set_cookie, str) else set_cookie
    
    for cookie_str in cookies:
        if not isinstance(cookie_str, str):
            continue
        
        # Parse cookie: NAME=VALUE; attribute; attribute...
        # Extract the name=value part (before first ;)
        cookie_parts = cookie_str.split(";")
        if not cookie_parts:
            continue
            
        name_value_part = cookie_parts[0].strip()
        if "=" not in name_value_part:
            continue
            
        cookie_name, cookie_value = name_value_part.split("=", 1)
        cookie_name = cookie_name.strip()
        cookie_value = cookie_value.strip()
        
        if not cookie_name or not cookie_value:
            continue
        
        # Check if cookie name contains any nonce keywords (generic detection)
        cookie_name_lower = cookie_name.lower()
        is_nonce_cookie = any(keyword in cookie_name_lower for keyword in NONCE_COOKIE_KEYWORDS)
        
        if is_nonce_cookie:
            # Generate a suggested variable name from the cookie name
            # Convert CamelCase/PascalCase to snake_case, remove company-specific prefixes
            suggested_var = _sanitize_cookie_name_to_var(cookie_name)
            
            candidates.append({
                "entry_index": entry_index,
                "step_number": step_number,
                "step_label": step_label,
                "request_id": entry.get("request_id"),
                "request_method": entry.get("method", "GET"),
                "request_url": entry.get("url", ""),
                "response_status": entry.get("status"),
                "source_location": "response_set_cookie",
                "source_key": cookie_name,
                "source_json_path": None,
                "value": cookie_value,
                "value_type": "oauth_nonce",
                "candidate_type": "oauth_param",
                "suggested_var_name": suggested_var,
            })
    
    return candidates


def _sanitize_cookie_name_to_var(cookie_name: str) -> str:
    """
    Convert a cookie name to a sanitized JMeter variable name.
    
    Examples:
    - "GlobalNonce" -> "global_nonce"
    - "SomeCompanyNonce" -> "nonce" 
    - "csrf_token" -> "csrf_token"
    - "NonceValue" -> "nonce_value"
    """
    import re
    
    # If it contains "nonce" (case-insensitive), extract just the relevant part
    name_lower = cookie_name.lower()
    
    if "nonce" in name_lower:
        # Simple: just use "nonce" or add context
        # Find where "nonce" appears and take surrounding context
        idx = name_lower.find("nonce")
        # Take from "nonce" onwards, remove environment suffixes
        suffix_patterns = ["_stg", "_stage", "_prod", "_dev", "_uat", "_qa"]
        result = cookie_name[idx:].lower()
        for suffix in suffix_patterns:
            if result.endswith(suffix):
                result = result[:-len(suffix)]
        # Convert to snake_case if needed
        result = re.sub(r'([a-z])([A-Z])', r'\1_\2', result).lower()
        return result if result else "nonce"
    
    if "csrf" in name_lower:
        return "csrf_token"
    
    # Fallback: convert the whole name to snake_case
    result = re.sub(r'([a-z])([A-Z])', r'\1_\2', cookie_name).lower()
    # Remove environment suffixes
    suffix_patterns = ["_stg", "_stage", "_prod", "_dev", "_uat", "_qa"]
    for suffix in suffix_patterns:
        if result.endswith(suffix):
            result = result[:-len(suffix)]
    return result


def extract_sources(
    entries: List[Tuple[int, int, str, Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    Phase 1: Extract all candidate source values from response data.
    
    Sources are extracted from:
    - Response headers (correlation IDs)
    - Redirect URLs (Location header params)
    - JSON response bodies (ID-like fields, OAuth tokens)
    - Set-Cookie headers (OAuth nonce values)
    - HTML form_post responses (OAuth tokens: id_token, code)
    
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
        
        # Extract from JSON body (includes OAuth token fields)
        all_candidates.extend(extract_from_json_body(
            response, response_headers, entry_index, step_number, step_label, entry
        ))
        
        # Extract OAuth nonce from Set-Cookie headers
        all_candidates.extend(extract_from_set_cookie(
            response_headers, entry_index, step_number, step_label, entry
        ))
        
        # Extract OAuth tokens from HTML form_post responses
        all_candidates.extend(extract_from_html_form_post(
            response, response_headers, entry_index, step_number, step_label, entry
        ))
    
    # Deduplicate by value - keep the FIRST occurrence (earliest source)
    seen_values: Dict[str, Dict[str, Any]] = {}
    for candidate in all_candidates:
        value_key = str(candidate.get("value", ""))
        if value_key not in seen_values:
            seen_values[value_key] = candidate
    
    return list(seen_values.values())
