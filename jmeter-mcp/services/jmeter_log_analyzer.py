"""
jmeter_log_analyzer.py

Service module for deep analysis of JMeter/BlazeMeter log files.

Responsibilities:
- Orchestrate log file discovery, parsing, grouping, and output generation
- Parse multi-line error blocks (JSR223 Post-Processor, stack traces)
- Categorize and classify errors by type, severity, API, and response code
- Group similar errors with deduplication via normalized signatures
- Capture first-occurrence request/response details per error group
- Correlate with JTL data for response code enrichment
- Format and delegate output writing (CSV, JSON, Markdown) to file_utils

Output location: artifacts/<test_run_id>/analysis/

Note: This module delegates low-level extraction to utils/log_utils.py
and all file I/O to utils/file_utils.py.
"""

import csv
import os
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from utils.config import load_config
from utils.file_utils import (
    get_analysis_output_dir,
    get_source_artifacts_dir,
    discover_files_by_extension,
    save_csv_file,
    save_json_file,
    save_markdown_file,
)
from utils.log_utils import (
    is_new_log_entry,
    is_error_level,
    extract_timestamp,
    extract_log_level,
    extract_thread_name,
    extract_sampler_name,
    extract_api_endpoint,
    extract_response_code,
    extract_error_message,
    extract_request_details,
    extract_response_details,
    extract_stack_trace,
    normalize_error_message,
    generate_error_signature,
    truncate,
    sanitize_for_csv,
    RE_JSR223_ERROR,
    RE_LOG_ENTRY,
)

# === Configuration ===
CONFIG = load_config()
ARTIFACTS_PATH = CONFIG["artifacts"]["artifacts_path"]
LOG_CONFIG = CONFIG.get("jmeter_log", {})

MAX_DESCRIPTION_LENGTH = LOG_CONFIG.get("max_description_length", 200)
MAX_REQUEST_LENGTH = LOG_CONFIG.get("max_request_length", 500)
MAX_RESPONSE_LENGTH = LOG_CONFIG.get("max_response_length", 500)
MAX_STACK_TRACE_LINES = LOG_CONFIG.get("max_stack_trace_lines", 50)
ERROR_LEVELS = LOG_CONFIG.get("error_levels", ["ERROR", "FATAL"])

TOOL_VERSION = "1.0.0"


# ============================================================
# Error Category & Severity Constants
# ============================================================

# Severity levels ordered from most to least severe
SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2}

# Error categories with their detection keywords and default severity
ERROR_CATEGORIES = {
    "HTTP 5xx Error": {
        "severity": "Critical",
        "code_range": range(500, 600),
    },
    "HTTP 4xx Error": {
        "severity": "High",
        "code_range": range(400, 500),
    },
    "Script Execution Failure": {
        "severity": "Critical",
        "keywords": [
            "JSR223Sampler", "ScriptException", "MissingPropertyException",
            "CompilationFailedException", "GroovyRuntimeException",
        ],
    },
    "Connection Error": {
        "severity": "Critical",
        "keywords": [
            "Connection refused", "Connection reset", "ConnectException",
            "SocketException",
        ],
    },
    "Timeout Error": {
        "severity": "High",
        "keywords": [
            "timeout", "timed out", "SocketTimeoutException",
            "ReadTimeoutException",
        ],
    },
    "SSL/TLS Error": {
        "severity": "High",
        "keywords": [
            "SSLException", "SSLHandshakeException", "certificate",
        ],
    },
    "Thread/Concurrency Error": {
        "severity": "Critical",
        "keywords": [
            "OutOfMemoryError", "StackOverflowError",
        ],
    },
    "DNS Resolution Error": {
        "severity": "Critical",
        "keywords": [
            "UnknownHostException", "DNS resolution failed",
        ],
    },
    "Authentication Error": {
        "severity": "High",
        "keywords": [
            "401 Unauthorized", "403 Forbidden",
        ],
    },
}


# ============================================================
# Public API
# ============================================================

def analyze_logs(
    test_run_id: str,
    log_source: str = "blazemeter",
) -> dict:
    """
    Main entry point. Discovers, parses, groups, correlates, and outputs
    analysis for all .log files under the specified source folder.

    Orchestration flow:
      1. Validate inputs (test_run_id, log_source)
      2. Discover log files → if none found, return { status: "NO_LOGS" }
      3. Discover JTL file (optional, single file)
      4. For each log file:
         a. Parse log file → list of error entries
         b. Collect file metadata (size, line counts)
      5. Merge all error entries across log files
      6. Categorize each error entry
      7. Group errors by signature
      8. If JTL file found:
         a. Parse JTL file
         b. Correlate with error groups
         c. Identify JTL-only failures
      9. Format and write CSV output (via file_utils)
     10. Format and write JSON output (via file_utils)
     11. Format and write Markdown output (via file_utils)
     12. Return result dict with status, paths, and summary

    Args:
        test_run_id: Unique test run identifier.
        log_source: "jmeter" or "blazemeter".

    Returns:
        dict with:
          - test_run_id: The test run identifier
          - log_source: Which source was analyzed
          - status: "OK", "NO_LOGS", or "ERROR"
          - log_files_analyzed: List of log file names processed
          - total_issues: Total unique issues found
          - total_occurrences: Sum of all error occurrences
          - issues_by_severity: Breakdown by severity level
          - output_files: Dict with paths to CSV, JSON, and Markdown outputs
          - message: Human-readable summary
    """
    pass


# ============================================================
# Log Parsing (high-level)
# ============================================================

def _parse_log_file(file_path: str) -> Tuple[List[dict], dict]:
    """
    Parse a single log file and return a list of structured error entries
    along with file metadata.

    Handles multi-line error blocks and stack traces by:
      1. Reading line-by-line (streaming, not loading full file into memory)
      2. Using is_new_log_entry() to detect block boundaries
      3. Accumulating continuation lines into the current block
      4. Parsing completed blocks via _parse_error_block()

    Args:
        file_path: Absolute path to the .log file.

    Returns:
        Tuple of:
          - List of structured error entry dicts
          - File metadata dict with: filename, path, size_bytes,
            total_lines, error_lines
    """
    error_entries = []
    total_lines = 0
    error_block_count = 0

    # Current block being accumulated
    current_block_lines: List[str] = []
    current_block_start_line = 0
    current_block_is_error = False

    def _finalize_block():
        """Process the accumulated block if it's an error block."""
        nonlocal error_block_count
        if current_block_lines and current_block_is_error:
            entry = _parse_error_block(
                current_block_lines,
                current_block_start_line,
                file_path,
            )
            if entry:
                error_entries.append(entry)
                error_block_count += 1

    file_size = os.path.getsize(file_path)

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line_num, raw_line in enumerate(f, start=1):
            total_lines += 1
            line = raw_line.rstrip("\n\r")

            if is_new_log_entry(line):
                # Finalize previous block before starting new one
                _finalize_block()

                # Start a new block
                current_block_lines = [line]
                current_block_start_line = line_num

                # Determine if this block qualifies as an error:
                # - JMeter log level is ERROR or FATAL, OR
                # - Content contains [ERROR]: (JSR223 Post-Processor marker)
                log_level = extract_log_level(line)
                level_is_error = (
                    log_level is not None
                    and is_error_level(log_level, ERROR_LEVELS)
                )
                has_jsr223_error = "[ERROR]:" in line

                current_block_is_error = level_is_error or has_jsr223_error
            else:
                # Continuation line — append to current block
                if current_block_lines:
                    current_block_lines.append(line)
                    # A continuation line with [ERROR]: also marks block as error
                    if not current_block_is_error and "[ERROR]:" in line:
                        current_block_is_error = True

    # Finalize the last block in the file
    _finalize_block()

    metadata = {
        "filename": os.path.basename(file_path),
        "path": file_path,
        "size_bytes": file_size,
        "total_lines": total_lines,
        "error_lines": error_block_count,
    }

    return error_entries, metadata


def _parse_error_block(
    lines: List[str],
    start_line_num: int,
    file_path: str,
) -> Optional[dict]:
    """
    Parse a multi-line error block into a structured entry.

    Delegates field extraction to log_utils functions.

    Args:
        lines: List of lines comprising the error block.
        start_line_num: Line number where the block starts in the file.
        file_path: Source log file path (for metadata).

    Returns:
        dict with: timestamp, log_level, thread_name, sampler_name,
        api_endpoint, response_code, error_message, request_details,
        response_details, stack_trace, line_number, log_file, raw_block.
        Returns None if block cannot be parsed.
    """
    if not lines:
        return None

    raw_block = "\n".join(lines)
    first_line = lines[0]

    # Extract base fields from the first (timestamped) line
    timestamp = extract_timestamp(first_line)
    log_level = extract_log_level(first_line) or "ERROR"

    # Check if this is a JSR223 Post-Processor error block
    # These have [ERROR]:[ThreadName]: SamplerName: pattern
    is_jsr223 = "[ERROR]:" in raw_block

    if is_jsr223:
        # Delegate to JSR223-specific parser
        jsr223_data = _extract_jsr223_error_block(lines)
        thread_name = jsr223_data.get("thread_name")
        sampler_name = jsr223_data.get("sampler_name")
        error_message = jsr223_data.get("error_message", "")
        request_details = jsr223_data.get("request_details")
        response_details = jsr223_data.get("response_details")
    else:
        # Standard error — extract from full block text
        thread_name = extract_thread_name(raw_block)
        sampler_name = extract_sampler_name(first_line)
        error_message = extract_error_message(raw_block)
        request_details = extract_request_details(raw_block)
        response_details = extract_response_details(raw_block)

    # Fields common to both JSR223 and standard errors
    api_endpoint = extract_api_endpoint(raw_block)
    response_code = extract_response_code(raw_block)
    stack_trace = extract_stack_trace(lines, MAX_STACK_TRACE_LINES)

    return {
        "timestamp": timestamp,
        "log_level": log_level,
        "thread_name": thread_name,
        "sampler_name": sampler_name,
        "api_endpoint": api_endpoint or "N/A",
        "response_code": response_code or "N/A",
        "error_message": error_message,
        "request_details": request_details,
        "response_details": response_details,
        "stack_trace": stack_trace,
        "line_number": start_line_num,
        "log_file": os.path.basename(file_path),
        "raw_block": raw_block,
        # Category and severity are populated later by _categorize_error()
        "error_category": None,
        "severity": None,
    }


def _extract_jsr223_error_block(lines: List[str]) -> dict:
    """
    Extract structured data from a JSR223 Post-Processor error block.

    Uses Request=[...] and Response=[...] as reliable boundaries.
    Custom lines between error message and Request= are captured
    as part of the error context/description.

    Args:
        lines: List of lines from the JSR223 error block.

    Returns:
        dict with: thread_name, sampler_name, error_message,
        request_details, response_details, context_lines
    """
    thread_name = None
    sampler_name = None
    error_message = ""
    context_lines = []
    request_lines = []
    response_lines = []

    # Parse state: "message" → "context" → "request" → "response"
    state = "message"
    in_request = False
    in_response = False

    for line in lines:
        # Check for JSR223 error marker to extract thread/sampler from first match
        match = RE_JSR223_ERROR.search(line)

        if in_response:
            # Accumulate response continuation lines
            response_lines.append(line)
            # Check if response block closes on this line
            stripped = line.rstrip()
            if stripped.endswith("]") and "Response=[" not in line:
                in_response = False
            continue

        if in_request:
            # Check if request block closes and response starts
            stripped = line.rstrip()
            if "Response=[" in line:
                # Request block ended, response block starts
                in_request = False
                in_response = True
                response_lines.append(line)
                # Check for single-line response: Response=[...]
                if stripped.endswith("]"):
                    in_response = False
            elif stripped.endswith("]") and "Request=[" not in line:
                # Request block closes
                in_request = False
                request_lines.append(line)
            else:
                request_lines.append(line)
            continue

        # Check for Request=[...] boundary
        if "Request=[" in line:
            state = "request"
            in_request = True
            request_lines.append(line)
            # Check for single-line request: Request=[...] on one line
            stripped = line.rstrip()
            if stripped.endswith("]") and stripped.count("[") == stripped.count("]"):
                in_request = False
            continue

        # Check for Response=[...] boundary (may appear without Request=)
        if "Response=[" in line:
            state = "response"
            in_response = True
            response_lines.append(line)
            stripped = line.rstrip()
            if stripped.endswith("]") and "Response=[" in line:
                # Single-line response like Response=[] or Response=[content]
                # Count brackets to see if it closes
                after_marker = line[line.index("Response=[") + len("Response=["):]
                if "]" in after_marker:
                    in_response = False
            continue

        # Extract thread_name and sampler_name from first [ERROR]: match
        if match and thread_name is None:
            thread_name = match.group(1).strip()
            sampler_name = match.group(2).strip()
            error_message = match.group(3).strip()
            state = "context"
            continue

        if match and state == "context":
            # Additional [ERROR]: lines before Request= are context
            context_content = match.group(3).strip()
            context_lines.append(context_content)
            continue

        # Non-[ERROR]: lines in context are also captured
        if state == "context":
            context_lines.append(line.strip())

    # Build request_details from collected lines
    request_details = None
    if request_lines:
        request_text = "\n".join(request_lines)
        request_details = extract_request_details(request_text)

    # Build response_details from collected lines
    response_details = None
    if response_lines:
        response_text = "\n".join(response_lines)
        response_details = extract_response_details(response_text)
    else:
        response_details = "[not available]"

    return {
        "thread_name": thread_name,
        "sampler_name": sampler_name,
        "error_message": error_message,
        "request_details": request_details,
        "response_details": response_details,
        "context_lines": context_lines,
    }


# ============================================================
# Error Categorization
# ============================================================

def _categorize_error(entry: dict) -> Tuple[str, str]:
    """
    Determine error category and severity for a parsed error entry.

    Classification priority:
      1. FATAL log level → "Fatal JMeter Error" (Critical)
      2. HTTP response code → "HTTP 5xx Error" or "HTTP 4xx Error"
      3. Keyword matching against ERROR_CATEGORIES
      4. JSR223 [ERROR]: marker → "Custom Logic Error" (High)
      5. Fallback → "General Error" (Medium)

    Args:
        entry: Parsed error entry dict (must contain at minimum:
               log_level, response_code, error_message, raw_block).

    Returns:
        Tuple of (error_category, severity).
    """
    log_level = (entry.get("log_level") or "").upper()
    response_code = entry.get("response_code", "N/A")
    error_message = entry.get("error_message", "")
    raw_block = entry.get("raw_block", "")
    search_text = f"{error_message} {raw_block}"

    # 1. FATAL log level
    if log_level == "FATAL":
        return ("Fatal JMeter Error", "Critical")

    # 2. HTTP response code classification
    if response_code != "N/A":
        try:
            code_int = int(response_code)
            for category_name, category_def in ERROR_CATEGORIES.items():
                if "code_range" in category_def and code_int in category_def["code_range"]:
                    return (category_name, category_def["severity"])
        except (ValueError, TypeError):
            pass

    # 3. Keyword matching against ERROR_CATEGORIES (non-HTTP-code categories)
    for category_name, category_def in ERROR_CATEGORIES.items():
        if "keywords" not in category_def:
            continue
        for keyword in category_def["keywords"]:
            if keyword.lower() in search_text.lower():
                return (category_name, category_def["severity"])

    # 4. JSR223 [ERROR]: marker → Custom Logic Error
    if "[ERROR]:" in raw_block:
        return ("Custom Logic Error", "High")

    # 5. Fallback
    return ("General Error", "Medium")


# ============================================================
# Grouping & Deduplication
# ============================================================

def _group_errors(entries: List[dict]) -> List[dict]:
    """
    Group error entries by signature and aggregate statistics.

    For each unique signature (via log_utils.generate_error_signature):
      - Count occurrences
      - Collect distinct thread names
      - Track first and last occurrence timestamps
      - Select first occurrence details (description, request, response)
      - Collect sample line numbers (first 10)

    Groups are sorted by severity (Critical → Medium), then by
    error_count (descending).

    Error IDs are assigned sequentially: ERR-001, ERR-002, etc.

    Args:
        entries: List of categorized error entry dicts.

    Returns:
        List of grouped error dicts, each containing:
          error_id, error_category, severity, response_code,
          api_endpoint, error_count, affected_threads,
          first_occurrence, last_occurrence,
          first_occurrence_description, first_occurrence_request,
          first_occurrence_response, log_file, sample_line_numbers
    """
    if not entries:
        return []

    # Group entries by signature
    signature_groups: Dict[str, List[dict]] = defaultdict(list)
    for entry in entries:
        sig = generate_error_signature(
            entry.get("error_category", "General Error"),
            entry.get("response_code", "N/A"),
            entry.get("api_endpoint", "N/A"),
            entry.get("error_message", ""),
        )
        signature_groups[sig].append(entry)

    # Build grouped results
    grouped = []
    for sig, group_entries in signature_groups.items():
        # Sort entries by timestamp (earliest first) for consistent ordering
        group_entries.sort(key=lambda e: e.get("timestamp") or "")

        # Use first entry for category/severity/endpoint metadata
        first = group_entries[0]

        # Collect distinct thread names
        threads = set()
        for e in group_entries:
            if e.get("thread_name"):
                threads.add(e["thread_name"])

        # Collect line numbers (first 10)
        line_numbers = [
            e["line_number"] for e in group_entries[:10]
            if e.get("line_number")
        ]

        # Collect log files (could span multiple if multiple .log files)
        log_files = set()
        for e in group_entries:
            if e.get("log_file"):
                log_files.add(e["log_file"])

        # Get first and last timestamps
        timestamps = [
            e["timestamp"] for e in group_entries
            if e.get("timestamp")
        ]
        first_occurrence = timestamps[0] if timestamps else None
        last_occurrence = timestamps[-1] if timestamps else None

        # Get first occurrence details (description, request, response)
        first_details = _select_first_occurrence_details(group_entries)

        grouped.append({
            "error_id": None,  # Assigned after sorting
            "error_category": first.get("error_category", "General Error"),
            "severity": first.get("severity", "Medium"),
            "response_code": first.get("response_code", "N/A"),
            "api_endpoint": first.get("api_endpoint", "N/A"),
            "error_count": len(group_entries),
            "affected_threads": sorted(threads),
            "first_occurrence": first_occurrence,
            "last_occurrence": last_occurrence,
            "first_occurrence_description": first_details["first_occurrence_description"],
            "first_occurrence_request": first_details["first_occurrence_request"],
            "first_occurrence_response": first_details["first_occurrence_response"],
            "first_occurrence_thread": first_details["first_occurrence_thread"],
            "log_file": "; ".join(sorted(log_files)),
            "sample_line_numbers": line_numbers,
        })

    # Sort by severity (Critical → Medium), then by error_count (descending)
    grouped.sort(
        key=lambda g: (
            SEVERITY_ORDER.get(g["severity"], 99),
            -g["error_count"],
        )
    )

    # Assign sequential error IDs
    for idx, group in enumerate(grouped, start=1):
        group["error_id"] = f"ERR-{idx:03d}"

    return grouped


def _select_first_occurrence_details(entries: List[dict]) -> dict:
    """
    Select the first occurrence from a list of same-signature entries
    and extract its description, request, and response details.

    Description, request, and response are truncated per config limits.

    Args:
        entries: List of error entries sharing the same signature,
                 sorted by timestamp (earliest first).

    Returns:
        dict with: first_occurrence_description, first_occurrence_request,
        first_occurrence_response, first_occurrence_thread
    """
    if not entries:
        return {
            "first_occurrence_description": "",
            "first_occurrence_request": "[not available]",
            "first_occurrence_response": "[not available]",
            "first_occurrence_thread": None,
        }

    first = entries[0]

    # Build description from error message
    description = first.get("error_message", "")
    description = truncate(description, MAX_DESCRIPTION_LENGTH)

    # Request details — truncated
    request = first.get("request_details")
    if request:
        request = truncate(request, MAX_REQUEST_LENGTH)
    else:
        request = "[not available]"

    # Response details — truncated
    response = first.get("response_details")
    if response:
        response = truncate(response, MAX_RESPONSE_LENGTH)
    else:
        response = "[not available]"

    return {
        "first_occurrence_description": description,
        "first_occurrence_request": request,
        "first_occurrence_response": response,
        "first_occurrence_thread": first.get("thread_name"),
    }


# ============================================================
# JTL Correlation
# ============================================================

def _discover_jtl_file(test_run_id: str, log_source: str) -> Optional[str]:
    """
    Find the single JTL/CSV result file for correlation.

    Discovery order (stop at first match):
      1. test-results.csv (BlazeMeter convention)
      2. <test_run_id>.jtl (JMeter convention)
      3. Any single *.jtl file (fallback)

    Args:
        test_run_id: Test run identifier.
        log_source: Source folder ("jmeter" or "blazemeter").

    Returns:
        Absolute file path, or None if no JTL file found.
    """
    source_dir = get_source_artifacts_dir(test_run_id, log_source)

    if not os.path.isdir(source_dir):
        return None

    # 1. Check for BlazeMeter convention: test-results.csv
    csv_path = os.path.join(source_dir, "test-results.csv")
    if os.path.isfile(csv_path):
        return csv_path

    # 2. Check for JMeter convention: <test_run_id>.jtl
    jtl_path = os.path.join(source_dir, f"{test_run_id}.jtl")
    if os.path.isfile(jtl_path):
        return jtl_path

    # 3. Fallback: any single .jtl file
    jtl_files = discover_files_by_extension(source_dir, ".jtl")
    if jtl_files:
        return jtl_files[0]

    return None


def _parse_jtl_file(file_path: str) -> Tuple[List[dict], dict]:
    """
    Parse a JTL/CSV result file into a list of result dicts
    and file metadata.

    Both .jtl and .csv files are CSV format — Python's csv module
    handles both identically.

    Expected headers:
      timeStamp, elapsed, label, responseCode, responseMessage,
      threadName, success, bytes, ...

    Args:
        file_path: Absolute path to the JTL/CSV file.

    Returns:
        Tuple of:
          - List of result dicts (one per sampler row)
          - File metadata dict with: filename, path,
            total_samples, failed_samples
    """
    pass


def _correlate_with_jtl(
    error_groups: List[dict],
    jtl_data: List[dict],
) -> Tuple[List[dict], List[dict], dict]:
    """
    Enrich grouped errors with JTL data and identify JTL-only failures.

    Matching strategy:
      - Match by sampler label + thread name + time window (±2 seconds)
      - Enrich matched groups with: jtl_response_code, jtl_response_message,
        jtl_elapsed_ms
      - Identify JTL rows with success=false not matched to any log error

    Args:
        error_groups: List of grouped error dicts.
        jtl_data: List of parsed JTL result dicts.

    Returns:
        Tuple of:
          - Enriched error groups (with JTL fields added)
          - JTL-only failures (list of dicts)
          - Correlation stats dict with: log_errors_matched_to_jtl,
            jtl_only_failures, unmatched_log_errors
    """
    pass


# ============================================================
# Output Formatting
# ============================================================

def _format_csv_rows(
    grouped_errors: List[dict],
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Build CSV fieldnames and row dicts from grouped errors.

    Values are sanitized for CSV safety (newlines replaced, etc.)
    via log_utils.sanitize_for_csv().

    Actual file write is performed by file_utils.save_csv_file().

    Args:
        grouped_errors: List of grouped error dicts.

    Returns:
        Tuple of (fieldnames list, rows list of dicts).
    """
    pass


def _format_json_output(
    test_run_id: str,
    log_source: str,
    grouped_errors: List[dict],
    log_file_metadata: List[dict],
    jtl_file_metadata: Optional[dict],
    jtl_only_failures: List[dict],
    jtl_correlation_stats: dict,
) -> dict:
    """
    Build complete JSON output dict with metadata, summary, and issues.

    Actual file write is performed by file_utils.save_json_file().

    Args:
        test_run_id: Test run identifier.
        log_source: Source analyzed ("jmeter" or "blazemeter").
        grouped_errors: List of grouped error dicts.
        log_file_metadata: List of metadata dicts for each log file.
        jtl_file_metadata: Metadata dict for the JTL file, or None.
        jtl_only_failures: List of JTL-only failure dicts.
        jtl_correlation_stats: Correlation statistics dict.

    Returns:
        Complete JSON-serializable dict matching the output schema.
    """
    pass


def _format_markdown_output(
    test_run_id: str,
    log_source: str,
    grouped_errors: List[dict],
    log_file_metadata: List[dict],
    jtl_file_metadata: Optional[dict],
    jtl_only_failures: List[dict],
    jtl_correlation_stats: dict,
) -> str:
    """
    Build complete Markdown report string.

    Sections:
      1. Header (test run ID, log source, date, files analyzed)
      2. Executive Summary (totals, severity breakdown, time window)
      3. Issues by Severity (tables for Critical, High, Medium)
      4. Top Affected APIs
      5. Error Category Breakdown
      6. First Occurrence Details (per issue with request/response)
      7. JTL Correlation Summary
      8. Log Files Analyzed

    Actual file write is performed by file_utils.save_markdown_file().

    Args:
        test_run_id: Test run identifier.
        log_source: Source analyzed ("jmeter" or "blazemeter").
        grouped_errors: List of grouped error dicts.
        log_file_metadata: List of metadata dicts for each log file.
        jtl_file_metadata: Metadata dict for the JTL file, or None.
        jtl_only_failures: List of JTL-only failure dicts.
        jtl_correlation_stats: Correlation statistics dict.

    Returns:
        Complete Markdown report as a string.
    """
    pass
