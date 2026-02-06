"""
log_utils.py

Utility module for JMeter/BlazeMeter log parsing.

Contains:
- Compiled regex patterns for log line detection and field extraction
- Functions for extracting timestamps, log levels, thread names, etc.
- Error message normalization and signature generation for deduplication
- Text utilities (truncation, CSV sanitization)

This module is stateless and has no side effects — it only parses and
transforms text. All file I/O is handled by file_utils.py.
"""

import hashlib
import re
from typing import List, Optional


# ============================================================
# Compiled Regex Patterns
# ============================================================

# New timestamped log entry (matches the start of any JMeter log line)
# Example: "2025-12-16 10:57:01,930 INFO o.a.j.e.J.JSR223 ..."
RE_LOG_ENTRY = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+"
    r"(INFO|ERROR|FATAL|WARN|DEBUG)\s+"
    r"(.+)"
)

# JSR223 error marker within log content
# Example: "[ERROR]:[TC02_AuthProxy - v0.7-ThreadStarter 1-21]: TC02_TS03_..."
RE_JSR223_ERROR = re.compile(
    r"\[ERROR\]:\[([^\]]+)\]:\s*([^:]+):\s*(.*)"
)

# HTTP response code extraction — multiple patterns
# Pattern 1: "Expected [200] but instead received [401]"
# Pattern 2: "Response code: 500"
# Pattern 3: "HTTP/1.1 500"
RE_RESPONSE_CODE = re.compile(
    r"(?:Expected.*?\[(\d{3})\].*?received\s+\[(\d{3})\])"
    r"|(?:Response\s+code[:\s]+(\d{3}))"
    r"|(?:HTTP.*?(\d{3}))",
    re.IGNORECASE,
)

# Request block boundary: Request=[...]
# The Request= line is a reliable boundary in JSR223 error blocks.
RE_REQUEST_BLOCK = re.compile(
    r"Request=\[(.+?)(?:\]$|\]\s*$)",
    re.DOTALL,
)

# Response block boundary: Response=[...]
# The Response= line is the last line in a JSR223 error block.
RE_RESPONSE_BLOCK = re.compile(
    r"Response=\[(.*)(?:\]$|\]\s*$)",
    re.DOTALL,
)

# API endpoint from URL (HTTP method + full URL)
RE_URL_PATTERN = re.compile(
    r"(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(https?://[^\s]+)",
    re.IGNORECASE,
)

# Stack trace lines
RE_STACK_TRACE = re.compile(
    r"^\s+at\s+|^Caused\s+by:|^\s+\.\.\.\s+\d+\s+more"
)

# Standard JMeter error (non-JSR223) — lines starting with timestamp + ERROR/FATAL
RE_STANDARD_ERROR = re.compile(
    r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2},\d{3})\s+"
    r"(ERROR|FATAL)\s+"
    r"(.+)",
    re.IGNORECASE,
)

# --- Normalization patterns (for deduplication hashing) ---

RE_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
RE_EMAIL = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
)
RE_IP_ADDRESS = re.compile(
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
)
RE_NUMERIC_ID = re.compile(
    r"\b\d{5,}\b"  # 5+ digit numbers likely to be IDs
)
RE_TIMESTAMP_IN_MSG = re.compile(
    r"\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}"
)


# ============================================================
# Log Line Detection
# ============================================================

def is_new_log_entry(line: str) -> bool:
    """
    Check if a line starts a new timestamped JMeter log entry.

    A new entry begins with a timestamp in the format:
      YYYY-MM-DD HH:MM:SS,mmm LEVEL ...

    Args:
        line: A single line from a JMeter log file.

    Returns:
        True if the line starts a new timestamped log entry.
    """
    pass


def is_error_level(log_level: str, error_levels: List[str]) -> bool:
    """
    Check if the log level qualifies as an error per configured levels.

    Args:
        log_level: The log level string (e.g., "ERROR", "FATAL", "WARN").
        error_levels: List of log levels that qualify as errors
                      (e.g., ["ERROR", "FATAL"]).

    Returns:
        True if log_level is in the error_levels list (case-insensitive).
    """
    pass


# ============================================================
# Error Field Extraction
# ============================================================

def extract_timestamp(line: str) -> Optional[str]:
    """
    Extract timestamp from a JMeter log line.

    Expected format: "YYYY-MM-DD HH:MM:SS,mmm"

    Args:
        line: A JMeter log line starting with a timestamp.

    Returns:
        Timestamp string, or None if not found.
    """
    pass


def extract_log_level(line: str) -> Optional[str]:
    """
    Extract the log level from a JMeter log line.

    Args:
        line: A JMeter log line (e.g., "2025-12-16 10:57:01,930 ERROR ...").

    Returns:
        Log level string (e.g., "ERROR", "FATAL"), or None if not found.
    """
    pass


def extract_thread_name(text: str) -> Optional[str]:
    """
    Extract thread group name from error text.

    Looks for patterns like:
      - [ERROR]:[ThreadName]: ...
      - Thread Group 1-1

    Args:
        text: Error block text content.

    Returns:
        Thread name string, or None if not found.
    """
    pass


def extract_sampler_name(text: str) -> Optional[str]:
    """
    Extract HTTP sampler or transaction name from error text.

    Looks for patterns like:
      - JSR223 PostProcessor (SamplerName):
      - [ERROR]:[ThreadName]: SamplerName: ...

    Args:
        text: Error block text content.

    Returns:
        Sampler name string, or None if not found.
    """
    pass


def extract_api_endpoint(text: str) -> Optional[str]:
    """
    Extract API URL/path from error context.

    Looks for patterns like:
      - GET https://host/api/path
      - POST https://host/api/path
      - URL in Request=[...] block

    Args:
        text: Error block text content.

    Returns:
        API endpoint URL or path, or None if not found.
    """
    pass


def extract_response_code(text: str) -> Optional[str]:
    """
    Extract HTTP response code from error text.

    Looks for patterns like:
      - "Expected [200] but instead received [401]" → returns "401"
      - "Response code: 500" → returns "500"

    Args:
        text: Error block text content.

    Returns:
        HTTP response code as string (e.g., "500"), or None if not found.
    """
    pass


def extract_error_message(text: str) -> str:
    """
    Extract the primary error message from error text.

    For JSR223 blocks, this is the first line's message content
    (e.g., "Expected <response code> [200] but instead received [401]").
    For standard errors, this is the message after the log level and class.

    Args:
        text: Error block text content.

    Returns:
        The primary error message string. Returns the full text
        if no specific message pattern is matched.
    """
    pass


def extract_request_details(text: str) -> Optional[str]:
    """
    Extract request URL, method, and body from a Request=[...] block.

    The Request=[...] line is a reliable boundary in JSR223 error blocks.
    Content between Request=[ and the closing ] is captured.

    Args:
        text: Error block text content (may be multi-line).

    Returns:
        Request details string, or None if no Request block found.
    """
    pass


def extract_response_details(text: str) -> Optional[str]:
    """
    Extract response content from a Response=[...] block.

    The Response=[...] line is the last line in a JSR223 error block.

    Args:
        text: Error block text content (may be multi-line).

    Returns:
        Response details string.
        Returns "[empty]" if Response=[] contains no content.
        Returns "[not available]" if no Response block found.
    """
    pass


def extract_stack_trace(lines: List[str], max_lines: int = 50) -> Optional[str]:
    """
    Extract Java/Groovy stack trace from error block lines.

    Collects lines that match stack trace patterns:
      - Lines starting with whitespace + "at "
      - "Caused by:" lines
      - "... N more" lines

    Args:
        lines: List of lines from the error block.
        max_lines: Maximum number of stack trace lines to capture.

    Returns:
        Stack trace as a single string (lines joined by newline),
        or None if no stack trace lines found.
    """
    pass


# ============================================================
# Normalization & Hashing
# ============================================================

def normalize_error_message(message: str) -> str:
    """
    Normalize error message for signature generation.

    Replaces variable data with placeholders to ensure the same
    logical error with different variable data groups together:
      - UUIDs → {UUID}
      - Email addresses → {EMAIL}
      - IP addresses → {IP}
      - Numeric IDs (5+ digits) → {ID}
      - Timestamps → {TIMESTAMP}
      - Strip leading/trailing whitespace
      - Lowercase

    Args:
        message: Raw error message string.

    Returns:
        Normalized message string.
    """
    pass


def generate_error_signature(
    error_category: str,
    response_code: str,
    api_endpoint: str,
    error_message: str,
) -> str:
    """
    Create a unique composite hash for error grouping.

    Signature = SHA-256 hash of:
      (error_category, response_code, api_endpoint, normalized_message_prefix)

    The error_message is normalized first (via normalize_error_message),
    then truncated to the first ~100 characters before hashing.

    Args:
        error_category: Error classification (e.g., "HTTP 5xx Error").
        response_code: HTTP response code (e.g., "500") or "N/A".
        api_endpoint: Affected API endpoint or "N/A".
        error_message: Raw error message (will be normalized internally).

    Returns:
        Hex digest string of the composite hash.
    """
    pass


# ============================================================
# Text Utilities
# ============================================================

def truncate(text: str, max_length: int) -> str:
    """
    Truncate string to max_length, appending '...' if truncated.

    Args:
        text: Input string.
        max_length: Maximum allowed length (including the '...' suffix).

    Returns:
        Original string if within limit, otherwise truncated with '...'.
    """
    pass


def sanitize_for_csv(text: str) -> str:
    """
    Clean string for safe CSV output.

    Replaces newlines with spaces and strips excessive whitespace.
    This ensures multi-line error messages don't break CSV row structure.

    Args:
        text: Input string (may contain newlines).

    Returns:
        Sanitized single-line string.
    """
    pass
