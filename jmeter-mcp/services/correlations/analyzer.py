"""
Main correlation analysis orchestrator.

Coordinates the three phases of correlation analysis:
- Phase 1: Source extraction (extractors.py)
- Phase 2: Usage detection (matchers.py)
- Phase 3: Orphan ID detection (matchers.py)
- Phase 1.5: Parameterization strategy (classifiers.py)
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Set, Tuple

from fastmcp import Context

from utils.config import load_config, load_jmeter_config
from utils.file_utils import save_correlation_spec

from .classifiers import classify_parameterization_strategy
from .extractors import extract_sources
from .matchers import detect_orphan_ids, find_usages
from .utils import init_exclude_domains, is_excluded_url


# === Configuration ===
CONFIG = load_config()
ARTIFACTS_PATH = CONFIG["artifacts"]["artifacts_path"]
JMETER_CONFIG = load_jmeter_config()

# Initialize domain exclusion from config
init_exclude_domains(CONFIG)


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


def _iter_entries(
    network_data: Dict[str, Any],
    exclude_domains: bool = True
) -> List[Tuple[int, int, str, Dict[str, Any]]]:
    """
    Flatten step-grouped data into ordered list of (entry_index, step_number, step_label, entry).
    
    Args:
        network_data: The loaded network capture data
        exclude_domains: If True, filter out entries matching excluded domains (APM, analytics, etc.)
    
    Returns entries in sequential order with global entry_index for forward-only searching.
    """
    flattened: List[Tuple[int, int, str, Dict[str, Any]]] = []
    excluded_count = 0
    global_index = 0
    
    for step_label, entries in network_data.items():
        for entry in entries:
            # Filter out excluded domains (APM, analytics, etc.)
            if exclude_domains:
                url = entry.get("url", "")
                if is_excluded_url(url):
                    excluded_count += 1
                    continue
            
            step_meta = entry.get("step") or {}
            step_number = step_meta.get("step_number")
            if step_number is None:
                match = re.match(r"Step\s+(\d+)", step_label)
                step_number = int(match.group(1)) if match else 0
            flattened.append((global_index, step_number, step_label, entry))
            global_index += 1
    
    if excluded_count > 0:
        print(f"[INFO] Excluded {excluded_count} entries from non-essential domains (APM, analytics, etc.)")

    # Sort by step_number, preserving order within steps
    flattened.sort(key=lambda x: (x[1], x[0]))
    
    # Re-index after sorting
    return [(i, sn, sl, e) for i, (_, sn, sl, e) in enumerate(flattened)]


# === Main Correlation Logic ===

def _find_correlations(network_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Main correlation detection driver.
    
    Orchestrates:
    1. Phase 1: Extract sources from responses
    2. Phase 2: Find usages for each source
    3. Phase 3: Detect orphan IDs
    4. Phase 1.5: Classify parameterization strategies
    
    Returns:
        Tuple of (correlations list, summary dict)
    """
    entries = _iter_entries(network_data)
    if not entries:
        return [], {}
    
    # Phase 1: Extract sources from responses
    source_candidates = extract_sources(entries)
    
    # Track known source values for orphan detection
    known_source_values: Set[str] = {str(c["value"]) for c in source_candidates}
    
    correlations: List[Dict[str, Any]] = []
    correlation_counter = 0
    
    # Phase 2: Find usages for each source candidate
    for candidate in source_candidates:
        usages = find_usages(candidate, entries)
        
        # Only emit correlations where value flows forward at least once
        if not usages:
            continue
        
        correlation_counter += 1
        correlation_id = f"corr_{correlation_counter}"
        
        # Determine extractor type based on source location
        extractor_type = "regex"
        if candidate.get("source_location") == "response_json":
            extractor_type = "json"
        
        param_hint = classify_parameterization_strategy(True, len(usages))
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
    orphan_candidates = detect_orphan_ids(entries, known_source_values)
    
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
        
        param_hint = classify_parameterization_strategy(False, occurrence_count)
        
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
        await ctx.info(f"Loaded network capture: {capture_path}")

        correlations, summary = _find_correlations(network_data)

        correlation_spec = {
            "capture_file": os.path.basename(capture_path),
            "application": JMETER_CONFIG.get("application_name", "unknown"),
            "spec_version": "2.0",
            "analyzer_version": "0.2.0",
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "total_steps": len(network_data),
            "total_entries": sum(len(v) for v in network_data.values()),
            "correlations": correlations,
            "summary": summary,
        }

        output_path = save_correlation_spec(test_run_id, correlation_spec)
        msg = f"Correlation analysis complete: {len(correlations)} correlations found"
        await ctx.info(f"{msg}: {output_path}")

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
