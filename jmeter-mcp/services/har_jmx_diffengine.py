"""
services/har_jmx_diffengine.py

Diff engine that cross-compares a HAR file against an existing JMeter JMX
script to identify API changes requiring script updates.

This module is diagnostic only — it identifies what changed and produces a report.
It does NOT modify the JMX. Actual fixes are applied via the existing
edit_jmeter_component / add_jmeter_component HITL tools.

Phases:
  A — Parse & extract (HAR entries + JMX samplers)
  B — Multi-pass matching algorithm
  C — Difference analysis
  D — Report generation (JSON + Markdown)
"""

import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from services import network_capture
from services.jmx_editor import load_jmx, build_node_index, discover_jmx_file
from utils.config import load_config

logger = logging.getLogger(__name__)

CONFIG = load_config()
NETWORK_CAPTURE_CONFIG = CONFIG.get("network_capture", {})

_BINARY_MIME_PREFIXES = (
    "image/",
    "font/",
    "video/",
    "audio/",
    "application/octet-stream",
)

_MAX_HAR_FILE_SIZE_BYTES = 200 * 1024 * 1024
_WARN_HAR_FILE_SIZE_BYTES = 50 * 1024 * 1024


def _get_comparison_config() -> dict:
    """Load har_jmx_comparison config with safe defaults."""
    try:
        cfg = load_config()
        return cfg.get("har_jmx_comparison", {})
    except Exception:
        return {}


def _get_schema_depth() -> int:
    return _get_comparison_config().get("schema_comparison_depth", 3)


# ============================================================
# Phase A — HAR Extraction
# ============================================================

def load_and_validate_har(har_path: str) -> Dict[str, Any]:
    """
    Load and validate a HAR file, returning the parsed JSON dict.

    Replicates the same validation logic as har_adapter._load_har_file
    without importing the private function.

    Raises:
        FileNotFoundError: If HAR file does not exist.
        ValueError: If file exceeds size limit or is not valid HAR JSON.
    """
    if not os.path.isfile(har_path):
        raise FileNotFoundError(f"HAR file not found: {har_path}")

    file_size = os.path.getsize(har_path)

    if file_size > _MAX_HAR_FILE_SIZE_BYTES:
        raise ValueError(
            f"HAR file too large ({file_size / (1024 * 1024):.1f} MB). "
            f"Maximum supported size is {_MAX_HAR_FILE_SIZE_BYTES / (1024 * 1024):.0f} MB."
        )

    if file_size > _WARN_HAR_FILE_SIZE_BYTES:
        logger.warning(
            "Large HAR file: %.1f MB — parsing may take a moment",
            file_size / (1024 * 1024),
        )

    try:
        with open(har_path, "r", encoding="utf-8", errors="replace") as f:
            har_data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in HAR file: {exc}") from exc

    if not isinstance(har_data, dict) or "log" not in har_data:
        raise ValueError(
            "Invalid HAR structure: top-level object must contain a 'log' key"
        )

    log_obj = har_data["log"]
    if "entries" not in log_obj:
        raise ValueError(
            "Invalid HAR structure: 'log' object must contain an 'entries' array"
        )

    return har_data


def _should_include_har_entry(entry: Dict, config: Dict) -> bool:
    """
    Determine if a HAR entry should be included in the comparison.

    Applies the same filtering logic as har_adapter._should_include_entry:
    skip OPTIONS, non-HTTP, failed/aborted, binary MIME types, and
    config-driven domain/path exclusions.
    """
    request = entry.get("request", {})
    response = entry.get("response", {})

    method = (request.get("method") or "").upper()
    if method == "OPTIONS":
        return False

    url = request.get("url", "")
    if not url:
        return False

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False

    status = response.get("status", 0)
    if status in (0, -1):
        return False

    content = response.get("content", {})
    mime_type = (content.get("mimeType") or "").lower()
    for prefix in _BINARY_MIME_PREFIXES:
        if mime_type.startswith(prefix):
            return False

    try:
        if not network_capture.should_capture_url(url, config):
            return False
    except Exception:
        pass

    return True


def _extract_json_schema(data: Any, max_depth: int, current_depth: int = 0) -> Any:
    """
    Extract the key structure of a JSON value up to max_depth levels.

    Returns a schema-like representation:
    - dict  -> {key: <nested schema>, ...}
    - list  -> [<schema of first element>] (or [] for empty lists)
    - str/int/float/bool/None -> the type name as a string
    """
    if current_depth >= max_depth:
        return "..."

    if isinstance(data, dict):
        return {
            k: _extract_json_schema(v, max_depth, current_depth + 1)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        if data:
            return [_extract_json_schema(data[0], max_depth, current_depth + 1)]
        return []
    elif isinstance(data, bool):
        return "bool"
    elif isinstance(data, int):
        return "int"
    elif isinstance(data, float):
        return "float"
    elif isinstance(data, str):
        return "string"
    elif data is None:
        return "null"
    return "unknown"


def _parse_body_schema(
    body_text: Optional[str],
    content_type: str,
    max_depth: int,
) -> Any:
    """
    Parse a request or response body into a schema representation.

    Returns:
    - JSON key schema (dict) if Content-Type is JSON and body parses
    - "form-encoded" if Content-Type indicates form data
    - "raw" for everything else or if parsing fails
    - None if body is empty
    """
    if not body_text or not body_text.strip():
        return None

    ct_lower = content_type.lower()

    if "application/json" in ct_lower or "+json" in ct_lower:
        try:
            parsed = json.loads(body_text)
            return _extract_json_schema(parsed, max_depth)
        except (json.JSONDecodeError, TypeError):
            return "raw"

    if "application/x-www-form-urlencoded" in ct_lower:
        return "form-encoded"

    if "multipart/form-data" in ct_lower:
        return "form-encoded"

    return "raw"


def extract_har_entries(har_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Parse a HAR file and extract comparison-relevant fields from each entry.

    Returns:
        Tuple of (entries, metadata) where:
        - entries: list of normalized entry dicts
        - metadata: dict with har_file, entries_total, entries_after_filter
    """
    har_data = load_and_validate_har(har_path)
    raw_entries = har_data["log"].get("entries", [])
    entries_total = len(raw_entries)

    capture_config = dict(NETWORK_CAPTURE_CONFIG)
    schema_depth = _get_schema_depth()

    extracted: List[Dict[str, Any]] = []

    for idx, entry in enumerate(raw_entries):
        if not _should_include_har_entry(entry, capture_config):
            continue

        request = entry.get("request", {})
        response = entry.get("response", {})

        url = request.get("url", "")
        parsed_url = urlparse(url)
        url_path = parsed_url.path.rstrip("/").lower() or "/"

        method = (request.get("method") or "GET").upper()

        query_params = sorted(set(
            p.get("name", "") for p in request.get("queryString", [])
            if p.get("name")
        ))

        req_headers = {}
        for h in request.get("headers", []):
            name = (h.get("name") or "").lower()
            if name in ("content-type", "authorization", "accept"):
                req_headers[name] = h.get("value", "")

        request_content_type = req_headers.get("content-type", "")
        post_data_text = request.get("postData", {}).get("text", "")
        request_body_schema = _parse_body_schema(
            post_data_text, request_content_type, schema_depth,
        )

        response_status = response.get("status", 0)

        resp_content = response.get("content", {})
        resp_content_type = (resp_content.get("mimeType") or "").lower()
        resp_body_text = resp_content.get("text", "")
        response_body_schema = _parse_body_schema(
            resp_body_text, resp_content_type, schema_depth,
        )

        extracted.append({
            "method": method,
            "url": url,
            "url_path": url_path,
            "query_params": query_params,
            "request_headers": req_headers,
            "request_body_schema": request_body_schema,
            "response_status": response_status,
            "response_body_schema": response_body_schema,
            "har_entry_index": idx,
        })

    metadata = {
        "har_file": os.path.basename(har_path),
        "har_entries_total": entries_total,
        "har_entries_after_filter": len(extracted),
    }

    logger.info(
        "HAR extraction: %d total entries, %d after filtering",
        entries_total, len(extracted),
    )

    return extracted, metadata


# ============================================================
# Phase A — JMX Extraction
# ============================================================

_EXTRACTOR_TYPES = {
    "JSONPostProcessor",
    "RegexExtractor",
    "BoundaryExtractor",
    "XPathExtractor",
    "XPath2Extractor",
    "HtmlExtractor",
}

_ASSERTION_TYPES = {
    "ResponseAssertion",
    "JSONPathAssertion",
    "DurationAssertion",
    "SizeAssertion",
}

_VAR_PLACEHOLDER_RE = re.compile(r'\$\{([^}]+)\}')
_NAME_PLACEHOLDER_RE = re.compile(r'\{([^}]+)\}|\{\{([^}]+)\}\}')


def _extract_request_body(elem: ET.Element) -> Optional[str]:
    """
    Extract the raw request body from an HTTPSamplerProxy XML element.

    JMeter stores the body under:
      elementProp[name='HTTPsampler.Arguments'] >
        collectionProp > elementProp > stringProp[name='Argument.value']
    """
    args_prop = None
    for child in elem:
        if child.tag == "elementProp" and child.get("name") in (
            "HTTPsampler.Arguments", "HTTPSampler.Arguments",
        ):
            args_prop = child
            break

    if args_prop is None:
        return None

    for coll in args_prop.iter("collectionProp"):
        for arg_elem in coll.iter("elementProp"):
            for sp in arg_elem:
                if sp.tag == "stringProp" and sp.get("name") == "Argument.value":
                    return sp.text or ""

    return None


def _extract_child_extractors(
    children: list,
    node_index: Dict[str, dict],
) -> List[Dict[str, Any]]:
    """
    Collect extractors from the hierarchy children of an HTTP sampler.

    Returns a list of dicts with extractor metadata.
    """
    extractors: List[Dict[str, Any]] = []
    for child in children:
        if child["type"] in _EXTRACTOR_TYPES:
            nid = child["node_id"]
            info = node_index.get(nid, {})
            props = info.get("props", {})
            extractors.append({
                "node_id": nid,
                "type": child["type"],
                "testname": child["testname"],
                "json_path": props.get("jsonpath", ""),
                "regex": props.get("regex", ""),
                "refname": props.get("refname", ""),
            })
    return extractors


def _extract_child_assertions(
    children: list,
    node_index: Dict[str, dict],
) -> List[Dict[str, Any]]:
    """
    Collect assertions from the hierarchy children of an HTTP sampler.

    Returns a list of dicts with assertion metadata.
    """
    assertions: List[Dict[str, Any]] = []
    for child in children:
        if child["type"] in _ASSERTION_TYPES:
            nid = child["node_id"]
            info = node_index.get(nid, {})
            props = info.get("props", {})
            assertions.append({
                "node_id": nid,
                "type": child["type"],
                "testname": child["testname"],
                "props": props,
            })
    return assertions


def _extract_url_path_from_name(testname: str) -> Optional[str]:
    """
    Extract the URL path fragment from a sampler testname.

    Sampler names typically follow patterns like:
      TC01_TS02_POST_/api/v1/shoppingcart
      TC01_TS02_/api/v1/customer/{customerId}

    Returns the path portion (starting with /) or None if not found.
    """
    match = re.search(r'(/[^\s]+)', testname)
    if match:
        return match.group(1).lower().rstrip("/") or "/"
    return None


def _build_url_regex_from_pattern(url_pattern: str) -> Optional[str]:
    """
    Convert a JMX URL pattern with ${...} placeholders into a regex.

    Example: /api/v1/customer/${customerId} -> ^/api/v1/customer/[^/]+$
    """
    if "${" not in url_pattern:
        return None

    regex_parts = []
    last_end = 0
    for m in _VAR_PLACEHOLDER_RE.finditer(url_pattern):
        regex_parts.append(re.escape(url_pattern[last_end:m.start()]))
        regex_parts.append("[^/]+")
        last_end = m.end()
    regex_parts.append(re.escape(url_pattern[last_end:]))

    return "^" + "".join(regex_parts) + "$"


def _build_url_regex_from_name(url_from_name: str) -> Optional[str]:
    """
    Convert a URL path from sampler name with {param} or {{param}} into a regex.

    Example: /api/v1/customer/{customerId} -> ^/api/v1/customer/[^/]+$
    """
    if "{" not in url_from_name:
        return None

    regex_parts = []
    last_end = 0
    for m in _NAME_PLACEHOLDER_RE.finditer(url_from_name):
        regex_parts.append(re.escape(url_from_name[last_end:m.start()]))
        regex_parts.append("[^/]+")
        last_end = m.end()
    regex_parts.append(re.escape(url_from_name[last_end:]))

    return "^" + "".join(regex_parts) + "$"


def _walk_hierarchy_for_samplers(
    hierarchy: list,
    node_index: Dict[str, dict],
    root: ET.Element,
    parent_controller: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Recursively walk the hierarchy to extract HTTP sampler details.

    Collects sampler metadata including URL patterns, bodies, child
    extractors/assertions, and parent controller context.
    """
    samplers: List[Dict[str, Any]] = []

    for node in hierarchy:
        ntype = node["type"]
        nid = node["node_id"]
        info = node_index.get(nid, {})
        props = info.get("props", {})

        current_controller = parent_controller
        if ntype in ("TransactionController", "GenericController", "LoopController"):
            current_controller = node["testname"]

        if ntype == "HTTPSamplerProxy":
            testname = node["testname"]
            method = props.get("method", "GET").upper()
            url_pattern = props.get("path", "")
            domain = props.get("domain", "")
            url_path_from_name = _extract_url_path_from_name(testname)

            url_regex = _build_url_regex_from_pattern(url_pattern)
            name_regex = _build_url_regex_from_name(
                url_path_from_name
            ) if url_path_from_name else None

            body = None
            elem_result = _find_element_by_node_id_lightweight(root, nid, node_index)
            if elem_result is not None:
                body = _extract_request_body(elem_result)

            children = node.get("children", [])
            extractors = _extract_child_extractors(children, node_index)
            assertions = _extract_child_assertions(children, node_index)

            samplers.append({
                "node_id": nid,
                "testname": testname,
                "enabled": node.get("enabled", True),
                "method": method,
                "url_pattern": url_pattern,
                "url_pattern_normalized": url_pattern.rstrip("/").lower() or "/",
                "url_path_from_name": url_path_from_name,
                "url_regex": url_regex,
                "name_regex": name_regex,
                "domain": domain,
                "request_body": body,
                "parent_controller": current_controller,
                "child_extractors": extractors,
                "child_assertions": assertions,
            })

        if node.get("children"):
            samplers.extend(_walk_hierarchy_for_samplers(
                node["children"], node_index, root, current_controller,
            ))

    return samplers


def _find_element_by_node_id_lightweight(
    root: ET.Element,
    target_node_id: str,
    node_index: Dict[str, dict],
) -> Optional[ET.Element]:
    """
    Lightweight element lookup that returns just the XML element (not the full
    triple) for body extraction. Uses the same walking logic as
    jmx_editor.find_element_by_node_id but only returns the element itself.
    """
    from services.jmx_editor import find_element_by_node_id

    result = find_element_by_node_id(root, target_node_id, node_index)
    if result is not None:
        return result[0]
    return None


def extract_jmx_samplers(
    jmx_path: str,
    jmx_structure_file: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Parse a JMX file and extract HTTP sampler details for comparison.

    If jmx_structure_file is provided and its jmx_last_modified matches the
    JMX file's current mtime, the pre-parsed node_index from the structure
    file is used. Otherwise, the JMX is parsed from scratch.

    Args:
        jmx_path: Absolute path to the JMX file.
        jmx_structure_file: Optional path to a jmx_structure_*.json file.

    Returns:
        Tuple of (samplers, metadata) where:
        - samplers: list of sampler dicts with full comparison context
        - metadata: dict with jmx_file, jmx_samplers_total
    """
    tree, root = load_jmx(jmx_path)

    use_structure_file = False
    if jmx_structure_file and os.path.isfile(jmx_structure_file):
        try:
            with open(jmx_structure_file, "r", encoding="utf-8") as f:
                structure_data = json.load(f)
            jmx_mtime = os.path.getmtime(jmx_path)
            recorded_mtime = structure_data.get("jmx_last_modified", "")
            current_mtime_str = datetime.utcfromtimestamp(jmx_mtime).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            if recorded_mtime == current_mtime_str:
                use_structure_file = True
                logger.info("Using pre-parsed structure file: %s", jmx_structure_file)
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to read structure file, parsing JMX from scratch")

    node_index, hierarchy = build_node_index(root)

    # Even when using structure file, we rebuild from raw XML to get full
    # props (including body extraction which requires XML element access)
    samplers = _walk_hierarchy_for_samplers(hierarchy, node_index, root)

    metadata = {
        "jmx_file": os.path.basename(jmx_path),
        "jmx_samplers_total": len(samplers),
        "used_structure_file": use_structure_file,
    }

    logger.info(
        "JMX extraction: %d HTTP samplers found in %s",
        len(samplers), os.path.basename(jmx_path),
    )

    return samplers, metadata
