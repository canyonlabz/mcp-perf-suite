"""
Constants and patterns for correlation analysis.

Shared across all correlation analysis modules.
"""

import re
from typing import Dict, Set

# === Regex Patterns ===

# Numeric ID: one or more digits
NUMERIC_ID_RE = re.compile(r"^\d+$")

# GUID: standard UUID format
GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)

# JWT: three base64url segments separated by dots
JWT_RE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")

# JSON keys that likely contain IDs (for SOURCE extraction)
# Matches: id, _id, userId, user_id, prodId, prod_id, uuid, guid, etc.
ID_KEY_PATTERNS = re.compile(
    r"(^id$|_id$|Id$|ID$|^.*id$|^.*_id$|uuid|guid)", 
    re.IGNORECASE
)


# === Header Configuration ===

# Header suffixes that indicate correlation/transaction IDs
CORRELATION_HEADER_SUFFIXES = (
    "id", "_id", "uuid", "transactionid", "correlationid",
    "requestid", "traceid", "spanid",
)

# Headers to skip when looking for correlation IDs (source extraction)
SKIP_HEADERS_SOURCE: Set[str] = {
    "content-type", "content-length", "cache-control", "date", "expires",
    "etag", "accept", "accept-encoding", "accept-language", "connection",
    "host", "origin", "referer", "user-agent", "cookie", "set-cookie",
    "access-control-allow-origin", "access-control-allow-credentials",
    "vary", "server", "strict-transport-security", "x-content-type-options",
    "x-frame-options", "content-encoding", "content-security-policy",
}

# Headers to skip when looking for usages (request headers that are HTTP plumbing)
SKIP_HEADERS_USAGE: Set[str] = {
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


# === Value Configuration ===

# Minimum length for numeric IDs to avoid false positives (e.g., "1", "2")
MIN_NUMERIC_ID_LENGTH = 2

# Maximum depth for JSON traversal
MAX_JSON_DEPTH = 5


# === OAuth Configuration ===

# OAuth-related parameter names (for flagging, not extraction in Phase 1)
OAUTH_PARAMS: Set[str] = {
    "code", "state", "nonce", "id_token", "access_token", "refresh_token",
    "code_challenge", "code_verifier", "redirect_uri", "client_id",
}

# OAuth token field names in JSON responses (for extraction)
# These are extracted from authentication endpoint responses
OAUTH_TOKEN_FIELDS: Set[str] = {
    "cdssotoken", "cdssoToken",  # Cross-domain SSO token (generic)
    "ssotoken", "ssoToken",      # Generic SSO token
    "tokenid", "tokenId",        # ForgeRock/OpenAM token ID
    "access_token", "accessToken",
    "id_token", "idToken",
    "refresh_token", "refreshToken",
}

# Generic nonce cookie detection patterns (case-insensitive substrings)
# Used to detect nonce values in Set-Cookie headers for OAuth/SSO flows
# These are generic patterns, not company-specific
NONCE_COOKIE_KEYWORDS: tuple = (
    "nonce",      # Generic nonce cookie
    "csrftoken",  # CSRF tokens that may be used as nonce
)

# OAuth token query parameters to parameterize in URLs
# These tokens appear in URLs and need to be substituted with JMeter variables
OAUTH_TOKEN_URL_PARAMS: Set[str] = {
    "cdssotoken",
}


# === Request-Side OAuth Detection (Sprint A) ===

# OAuth parameter names to detect in request URLs.
# Used for request-side extraction when response sources are empty.
# Reference: https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce
OAUTH_URL_PARAMS: Set[str] = {
    # Standard OAuth 2.0 / OpenID Connect
    "client_id", "redirect_uri", "response_type", "scope", "state",
    "response_mode", "nonce",
    # PKCE (RFC 7636)
    "code_challenge", "code_challenge_method",
    # Tokens that may appear in URL query strings
    "code", "id_token", "access_token",
    # SSO tokens in URLs (cross-domain SSO flows)
    "cdssotoken", "ssotoken",
}

# Parameters whose values may contain nested URLs with more OAuth params.
# These are recursively URL-decoded and re-parsed to extract embedded params.
OAUTH_NESTED_URL_PARAMS: Set[str] = {
    "goto", "redirect_uri", "return_url", "returnurl",
    "redirect", "callback", "continue",
}

# Mapping from URL param name (lowercase) to value_type classification
OAUTH_PARAM_VALUE_TYPES: Dict[str, str] = {
    "client_id": "oauth_client_id",
    "redirect_uri": "oauth_redirect_uri",
    "response_type": "oauth_response_type",
    "scope": "oauth_scope",
    "state": "oauth_state",
    "response_mode": "oauth_response_mode",
    "nonce": "oauth_nonce",
    "code_challenge": "pkce_code_challenge",
    "code_challenge_method": "pkce_code_challenge_method",
    "code": "oauth_code",
    "id_token": "oauth_token",
    "access_token": "oauth_token",
    "cdssotoken": "sso_token",
    "ssotoken": "sso_token",
}

# PKCE-specific parameter names (subset of OAUTH_URL_PARAMS)
PKCE_PARAMS: Set[str] = {"code_challenge", "code_challenge_method", "code_verifier"}
