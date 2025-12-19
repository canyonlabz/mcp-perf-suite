"""
Constants and patterns for correlation analysis.

Shared across all correlation analysis modules.
"""

import re
from typing import Set

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

