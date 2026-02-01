"""
services/report_revision_generator.py
Report revision generator for AI-assisted report enhancement.

This module implements the revise_performance_test_report function that
assembles revised reports using AI-generated content from the revisions folder.

The approach reuses the report_generator infrastructure:
1. Read metadata to find which template was used for the original report
2. Create an AI template copy (ai_<template_name>) if it doesn't exist
3. In the AI template, replace original placeholders with AI placeholders
4. Load ALL source data files and build full context (same as create_performance_test_report)
5. Override AI placeholders with AI-generated content
6. Render using the AI template with full context
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from utils.config import load_config, load_revisable_sections_config, get_section_config
from utils.revision_utils import (
    validate_report_type,
    validate_section_id,
    get_reports_folder_path,
    get_revisions_folder_path,
    get_original_report_path,
    get_backup_report_path,
    get_revised_report_path,
    get_metadata_path,
    get_backup_metadata_path,
    get_revision_file_path,
    get_existing_revision_versions,
    get_latest_revision_version,
)
from utils.file_utils import (
    _load_json_safe,
    _load_text_safe,
    _load_text_file,
    _save_text_file,
)
from services.revision_context_manager import get_revision_content
# Import the context builder from report_generator
from services.report_generator import (
    _build_report_context,
    _render_template,
    _load_apm_trace_summary,
)


# Load configuration
CONFIG = load_config()
ARTIFACTS_CONFIG = CONFIG.get('artifacts', {})
REPORT_CONFIG = CONFIG.get('perf_report', {})
ARTIFACTS_PATH = Path(ARTIFACTS_CONFIG.get('artifacts_path', './artifacts'))
TEMPLATES_PATH = Path(REPORT_CONFIG.get('templates_path', './templates'))

# Server version info
SERVER_CONFIG = CONFIG.get('server', {})
MCP_VERSION = SERVER_CONFIG.get('version', 'unknown')


# -----------------------------------------------
# Main Report Revision Function
# -----------------------------------------------

async def revise_performance_test_report(
    run_id: str,
    report_type: str = "single_run",
    revision_version: Optional[int] = None
) -> Dict:
    """
    Assemble a revised performance test report using AI-generated content.
    
    This function reuses the report_generator infrastructure to ensure
    all data (tables, links, metrics) is populated correctly:
    1. Reads metadata to find which template was used for the original report
    2. Creates an AI template copy (ai_<template_name>) if it doesn't exist
    3. In the AI template, replaces original placeholders with AI placeholders
    4. Loads ALL source data files (same as create_performance_test_report)
    5. Builds full context using _build_report_context from report_generator
    6. Overrides AI placeholders with AI-generated content from revision files
    7. Renders the AI template with full context
    8. Backs up original report and saves the revised version
    
    Args:
        run_id: Test run ID (for single_run) or comparison_id (for comparison).
        report_type: "single_run" (default) or "comparison".
        revision_version: Specific version of revisions to use.
                         If None, uses the latest version for each section.
    
    Returns:
        dict containing:
            - run_id: The test run or comparison ID
            - report_type: Type of report
            - original_report_path: Path to the original report (now backed up)
            - revised_report_path: Path to the new revised report
            - backup_report_path: Path where original was backed up
            - ai_template_path: Path to the AI-enhanced template used
            - sections_revised: List of sections that were revised
            - revision_versions_used: Dict mapping section_id to version used
            - revised_at: ISO timestamp
            - mcp_version: PerfReport MCP version
            - status: "success" or "error"
            - error: Error message if status is "error"
            - warnings: List of non-fatal warnings
    """
    try:
        warnings = []
        missing_sections = []
        revised_timestamp = datetime.now().isoformat()
        
        # Validate report_type
        is_valid, error = validate_report_type(report_type)
        if not is_valid:
            return _error_response(run_id, report_type, error)
        
        # Get paths
        run_path = ARTIFACTS_PATH / run_id
        analysis_path = run_path / "analysis"
        reports_folder = get_reports_folder_path(run_id, report_type)
        revisions_folder = get_revisions_folder_path(run_id, report_type)
        
        # Validate paths exist
        if not run_path.exists():
            return _error_response(
                run_id, report_type,
                f"Run path not found: {run_path}"
            )
        
        if not analysis_path.exists():
            return _error_response(
                run_id, report_type,
                f"Analysis path not found: {analysis_path}"
            )
        
        if not reports_folder.exists():
            return _error_response(
                run_id, report_type,
                f"Reports folder not found: {reports_folder}"
            )
        
        # Get original report path
        original_report_path = get_original_report_path(run_id, report_type)
        
        if not original_report_path.exists():
            return _error_response(
                run_id, report_type,
                f"Original report not found: {original_report_path}"
            )
        
        # Get enabled sections
        enabled_sections = load_revisable_sections_config(report_type, enabled_only=True)
        
        if not enabled_sections:
            return _error_response(
                run_id, report_type,
                "No sections are enabled for revision. Enable sections in report_config.yaml first."
            )
        
        # Check if revisions folder has any content
        if not revisions_folder.exists() or not any(revisions_folder.iterdir()):
            return _error_response(
                run_id, report_type,
                f"No revision files found in {revisions_folder}. "
                "Run prepare_revision_context() for each section first."
            )
        
        # Step 1: Read metadata to find which template was used
        metadata_path = get_metadata_path(run_id, report_type)
        if not metadata_path.exists():
            return _error_response(
                run_id, report_type,
                f"Metadata file not found: {metadata_path}"
            )
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        original_template_name = metadata.get("template_used", "default_report_template.md")
        original_template_path = TEMPLATES_PATH / original_template_name
        
        if not original_template_path.exists():
            return _error_response(
                run_id, report_type,
                f"Original template not found: {original_template_path}"
            )
        
        # Step 2: Create or load AI template
        ai_template_name = f"ai_{original_template_name}"
        ai_template_path = TEMPLATES_PATH / ai_template_name
        
        ai_template_result = _ensure_ai_template_exists(
            original_template_path, ai_template_path, enabled_sections, warnings
        )
        
        if ai_template_result.get("status") == "error":
            return _error_response(
                run_id, report_type,
                f"Failed to create AI template: {ai_template_result.get('error')}",
                warnings=warnings
            )
        
        # Step 3: Load AI template content
        ai_template_content = await _load_text_file(ai_template_path)
        
        # Step 4: Collect revision content for AI sections
        sections_revised = []
        revision_versions_used = {}
        ai_context = {}
        
        for section_id, section_config in enabled_sections.items():
            # Check if revision exists for this section
            existing_versions = get_existing_revision_versions(run_id, section_id, report_type)
            
            if not existing_versions:
                warnings.append(
                    f"No revision found for enabled section '{section_id}'. Skipping."
                )
                continue
            
            # Determine which version to use
            if revision_version is not None:
                if revision_version in existing_versions:
                    version_to_use = revision_version
                else:
                    warnings.append(
                        f"Requested version {revision_version} not found for section "
                        f"'{section_id}'. Using latest (v{max(existing_versions)})."
                    )
                    version_to_use = max(existing_versions)
            else:
                version_to_use = max(existing_versions)
            
            # Read revision content
            revision_result = await get_revision_content(
                run_id, section_id, version_to_use, report_type
            )
            
            if revision_result.get("status") != "success":
                warnings.append(
                    f"Failed to read revision for section '{section_id}': "
                    f"{revision_result.get('error', 'Unknown error')}"
                )
                continue
            
            # Get the AI placeholder name
            ai_placeholder = section_config.get("ai_placeholder", "")
            
            if not ai_placeholder:
                warnings.append(
                    f"No AI placeholder defined for section '{section_id}'. Skipping."
                )
                continue
            
            # Add AI content to context
            revision_text = revision_result.get("content", "")
            ai_context[ai_placeholder] = revision_text
            
            sections_revised.append(section_id)
            revision_versions_used[section_id] = version_to_use
        
        if not sections_revised:
            return _error_response(
                run_id, report_type,
                "No sections were revised. Check warnings for details.",
                warnings=warnings
            )
        
        # Step 5: Load ALL source data files (same as create_performance_test_report)
        source_files = {}
        
        # Load analysis files
        perf_data = await _load_json_safe(
            analysis_path / "performance_analysis.json",
            "performance_analysis",
            source_files, warnings, missing_sections
        )
        
        infra_data = await _load_json_safe(
            analysis_path / "infrastructure_analysis.json",
            "infrastructure_analysis",
            source_files, warnings, missing_sections
        )
        
        corr_data = await _load_json_safe(
            analysis_path / "correlation_analysis.json",
            "correlation_analysis",
            source_files, warnings, missing_sections
        )
        
        # Determine environment type from correlation_analysis.json
        environment_type = None
        if corr_data:
            env_raw = corr_data.get("environment_type")
            if isinstance(env_raw, str):
                env_norm = env_raw.strip().lower()
                if env_norm in {"host", "kubernetes"}:
                    environment_type = env_norm
        
        if environment_type not in {"host", "kubernetes"}:
            return _error_response(
                run_id, report_type,
                "Environment type not detected in correlation_analysis.json. "
                "Expected 'host' or 'kubernetes' in field 'environment_type'."
            )
        
        # Load markdown summaries (optional)
        perf_summary_md = await _load_text_safe(
            analysis_path / "performance_summary.md",
            "performance_summary_md",
            source_files, warnings
        )
        
        infra_summary_md = await _load_text_safe(
            analysis_path / "infrastructure_summary.md",
            "infrastructure_summary_md",
            source_files, warnings
        )
        
        corr_summary_md = await _load_text_safe(
            analysis_path / "correlation_analysis.md",
            "correlation_analysis_md",
            source_files, warnings
        )
        
        # Load log analysis data (optional)
        log_data = await _load_json_safe(
            analysis_path / "log_analysis.json",
            "log_analysis",
            source_files, warnings, missing_sections
        )
        
        # Load APM trace data from datadog folder (optional)
        datadog_path = run_path / "datadog"
        apm_trace_summary = await _load_apm_trace_summary(datadog_path, source_files, warnings)
        
        # Load BlazeMeter test configuration (optional)
        blazemeter_path = run_path / "blazemeter"
        blazemeter_config = await _load_json_safe(
            blazemeter_path / "test_config.json",
            "blazemeter_test_config",
            source_files, warnings, []
        )
        
        # Load BlazeMeter public report URL (optional)
        blazemeter_public_report = await _load_json_safe(
            blazemeter_path / "public_report.json",
            "blazemeter_public_report",
            source_files, warnings, []
        )
        
        # Step 6: Build full context using report_generator's _build_report_context
        full_context = _build_report_context(
            run_id,
            environment_type,
            revised_timestamp,
            perf_data,
            infra_data,
            corr_data,
            perf_summary_md,
            infra_summary_md,
            corr_summary_md,
            log_data,
            apm_trace_summary,
            blazemeter_config
        )
        
        # Add BlazeMeter public report link
        if blazemeter_public_report and blazemeter_public_report.get("public_url"):
            public_url = blazemeter_public_report.get("public_url")
            full_context["BLAZEMETER_REPORT_LINK"] = f"[View Report]({public_url})"
        elif blazemeter_config and blazemeter_config.get("public_url"):
            public_url = blazemeter_config.get("public_url")
            full_context["BLAZEMETER_REPORT_LINK"] = f"[View Report]({public_url})"
        else:
            full_context["BLAZEMETER_REPORT_LINK"] = "Not available"
        
        # Add bug tracking placeholder
        full_context["BUG_TRACKING_ROWS"] = "{{BUG_TRACKING_ROWS}}"
        
        # Step 7: Override AI placeholders with AI-generated content
        full_context.update(ai_context)
        
        # Step 8: Render the AI template with full context
        revised_content = _render_template(ai_template_content, full_context)
        
        # Step 9: Backup original report and metadata
        backup_result = await _backup_original_files(run_id, report_type, warnings)
        
        if backup_result.get("status") == "error":
            return _error_response(
                run_id, report_type,
                f"Failed to backup original files: {backup_result.get('error')}",
                warnings=warnings
            )
        
        # Step 10: Add revision header and save
        revision_header = _build_revision_header(
            run_id, report_type, sections_revised, 
            revision_versions_used, revised_timestamp,
            ai_template_name
        )
        revised_content = _insert_revision_header(revised_content, revision_header)
        
        # Save revised report
        revised_report_path = get_revised_report_path(run_id, report_type)
        await _save_text_file(revised_report_path, revised_content)
        
        # Update metadata file with revision info
        await _update_metadata_with_revision(
            run_id, report_type, sections_revised,
            revision_versions_used, revised_timestamp, str(revised_report_path),
            ai_template_name
        )
        
        return {
            "run_id": run_id,
            "report_type": report_type,
            "original_report_path": str(original_report_path),
            "revised_report_path": str(revised_report_path),
            "backup_report_path": str(backup_result.get("backup_report_path", "")),
            "backup_metadata_path": str(backup_result.get("backup_metadata_path", "")),
            "ai_template_path": str(ai_template_path),
            "ai_template_created": ai_template_result.get("created", False),
            "sections_revised": sections_revised,
            "sections_revised_count": len(sections_revised),
            "revision_versions_used": revision_versions_used,
            "revision_version_requested": revision_version,
            "revised_at": revised_timestamp,
            "mcp_version": MCP_VERSION,
            "warnings": warnings,
            "status": "success"
        }
        
    except Exception as e:
        return _error_response(
            run_id, report_type,
            f"Report revision failed: {str(e)}"
        )


# -----------------------------------------------
# AI Template Functions
# -----------------------------------------------

def _ensure_ai_template_exists(
    original_template_path: Path,
    ai_template_path: Path,
    enabled_sections: Dict,
    warnings: List[str]
) -> Dict:
    """
    Ensure the AI-enhanced template exists.
    
    If it doesn't exist, creates it by copying the original template
    and replacing original placeholders with AI placeholders for enabled sections.
    
    Args:
        original_template_path: Path to the original template
        ai_template_path: Path where AI template should be
        enabled_sections: Dict of enabled sections with their config
        warnings: List to append warnings to
    
    Returns:
        dict with status and whether template was created
    """
    try:
        if ai_template_path.exists():
            # AI template already exists, verify it has the right placeholders
            return {"status": "success", "created": False}
        
        # Load original template
        original_content = original_template_path.read_text(encoding='utf-8')
        
        # Replace original placeholders with AI placeholders for enabled sections
        ai_content = original_content
        for section_id, section_config in enabled_sections.items():
            original_placeholder = "{{" + section_config.get("placeholder", "") + "}}"
            ai_placeholder = "{{" + section_config.get("ai_placeholder", "") + "}}"
            
            if original_placeholder in ai_content:
                ai_content = ai_content.replace(original_placeholder, ai_placeholder)
        
        # Save the AI template
        ai_template_path.write_text(ai_content, encoding='utf-8')
        
        return {"status": "success", "created": True}
        
    except Exception as e:
        return {"status": "error", "error": str(e)}


# -----------------------------------------------
# Backup Functions
# -----------------------------------------------

async def _backup_original_files(
    run_id: str,
    report_type: str,
    warnings: List[str]
) -> Dict:
    """
    Backup the original report and metadata files.
    
    Creates copies with _original suffix.
    """
    try:
        # Get paths
        original_report = get_original_report_path(run_id, report_type)
        backup_report = get_backup_report_path(run_id, report_type)
        metadata_file = get_metadata_path(run_id, report_type)
        backup_metadata = get_backup_metadata_path(run_id, report_type)
        
        # Backup report
        if original_report.exists():
            # Check if backup already exists (from previous revision)
            if backup_report.exists():
                warnings.append(
                    f"Backup report already exists: {backup_report.name}. "
                    "Keeping existing backup."
                )
            else:
                shutil.copy2(original_report, backup_report)
        
        # Backup metadata
        if metadata_file.exists():
            if backup_metadata.exists():
                warnings.append(
                    f"Backup metadata already exists: {backup_metadata.name}. "
                    "Keeping existing backup."
                )
            else:
                shutil.copy2(metadata_file, backup_metadata)
        else:
            warnings.append("Metadata file not found. Skipping metadata backup.")
        
        return {
            "status": "success",
            "backup_report_path": backup_report,
            "backup_metadata_path": backup_metadata
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


# -----------------------------------------------
# Header and Metadata Functions
# -----------------------------------------------

def _build_revision_header(
    run_id: str,
    report_type: str,
    sections_revised: List[str],
    revision_versions_used: Dict[str, int],
    timestamp: str,
    ai_template_name: str = ""
) -> str:
    """
    Build a revision header comment to insert into the report.
    """
    version_info = ", ".join([
        f"{s}=v{v}" for s, v in revision_versions_used.items()
    ])
    
    header = f"""<!--
AI-REVISED REPORT
=================
Run ID: {run_id}
Report Type: {report_type}
Revised At: {timestamp}
Sections Revised: {', '.join(sections_revised)}
Revision Versions: {version_info}
AI Template: {ai_template_name}
MCP Version: {MCP_VERSION}
-->

"""
    return header


def _insert_revision_header(content: str, header: str) -> str:
    """
    Insert the revision header at the beginning of the report.
    
    If the report already has a revision header, replace it.
    """
    # Check if there's already a revision header
    if "AI-REVISED REPORT" in content:
        # Find and replace existing header
        start = content.find("<!--\nAI-REVISED REPORT")
        if start != -1:
            end = content.find("-->", start)
            if end != -1:
                # Replace existing header
                return header + content[end + 4:].lstrip('\n')
    
    # Insert at beginning
    return header + content


async def _update_metadata_with_revision(
    run_id: str,
    report_type: str,
    sections_revised: List[str],
    revision_versions_used: Dict[str, int],
    timestamp: str,
    revised_report_path: str,
    ai_template_name: str = ""
) -> None:
    """
    Update the metadata JSON file with revision information.
    """
    metadata_path = get_metadata_path(run_id, report_type)
    
    if not metadata_path.exists():
        return
    
    try:
        # Load existing metadata
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Add revision information
        metadata["revision_info"] = {
            "is_revised": True,
            "revised_at": timestamp,
            "sections_revised": sections_revised,
            "revision_versions_used": revision_versions_used,
            "revised_report_path": revised_report_path,
            "ai_template_used": ai_template_name,
            "original_report_backed_up": True
        }
        
        # Update report_path to point to revised version
        metadata["report_path"] = revised_report_path
        metadata["report_name"] = Path(revised_report_path).name
        
        # Save updated metadata
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
            
    except Exception:
        # Non-fatal - metadata update is optional
        pass


# -----------------------------------------------
# Header-Based Section Replacement Functions
# -----------------------------------------------

def _get_section_header_pattern(section_id: str) -> Optional[str]:
    """
    Get the markdown header pattern for a section.
    
    Maps section_id to the expected header in the report.
    """
    header_patterns = {
        "executive_summary": "## ✨ 1.0 Executive Summary",
        "key_observations": "## 🔎 2.0 Key Observations",
        "issues_table": "### 2.1 Issues Observed",
    }
    
    # Also try without emojis as fallback
    fallback_patterns = {
        "executive_summary": "## 1.0 Executive Summary",
        "key_observations": "## 2.0 Key Observations",
        "issues_table": "### 2.1 Issues Observed",
    }
    
    return header_patterns.get(section_id) or fallback_patterns.get(section_id)


def _get_section_end_pattern(section_id: str) -> Optional[str]:
    """
    Get the pattern that marks the end of a section.
    
    Returns the header of the next section or a delimiter.
    """
    end_patterns = {
        "executive_summary": "### ⚙️ 1.1 Test Configuration",
        "key_observations": "### 2.1 Issues Observed",
        "issues_table": "### 2.2 SLA Compliance",
    }
    
    # Fallbacks without emojis
    fallback_end_patterns = {
        "executive_summary": "### 1.1 Test Configuration",
        "key_observations": "### 2.1 Issues Observed",
        "issues_table": "### 2.2 SLA Compliance",
    }
    
    return end_patterns.get(section_id) or fallback_end_patterns.get(section_id)


def _replace_section_by_header(
    content: str,
    header_pattern: str,
    end_pattern: Optional[str],
    new_content: str
) -> Optional[str]:
    """
    Replace section content identified by header pattern.
    
    Finds the section header and replaces content up to the end pattern
    or next section header.
    
    Args:
        content: Full report content
        header_pattern: Section header to find
        end_pattern: Pattern marking end of section (next header)
        new_content: New content to insert
    
    Returns:
        Modified content string, or None if header not found
    """
    import re
    
    # Try to find the header pattern (with or without emoji)
    header_pos = content.find(header_pattern)
    
    # If not found, try without emoji prefix
    if header_pos == -1:
        # Remove emoji from pattern and try again
        clean_pattern = re.sub(r'[✨🔎📊🏗️⚙️]\s*', '', header_pattern)
        header_pos = content.find(clean_pattern)
        if header_pos != -1:
            header_pattern = clean_pattern
    
    if header_pos == -1:
        return None
    
    # Find where the section content starts (after header line)
    content_start = content.find('\n', header_pos)
    if content_start == -1:
        return None
    content_start += 1  # Skip the newline
    
    # Skip any additional newlines after header
    while content_start < len(content) and content[content_start] == '\n':
        content_start += 1
    
    # Find where the section ends
    if end_pattern:
        # Try with emoji first
        end_pos = content.find(end_pattern, content_start)
        
        # If not found, try without emoji
        if end_pos == -1:
            clean_end_pattern = re.sub(r'[✨🔎📊🏗️⚙️]\s*', '', end_pattern)
            end_pos = content.find(clean_end_pattern, content_start)
        
        if end_pos == -1:
            # If end pattern not found, look for next ## or ### header
            next_section = re.search(r'\n(##[#]?\s+\d+\.)', content[content_start:])
            if next_section:
                end_pos = content_start + next_section.start()
            else:
                end_pos = len(content)
    else:
        # Look for next section header
        next_section = re.search(r'\n(##[#]?\s+\d+\.)', content[content_start:])
        if next_section:
            end_pos = content_start + next_section.start()
        else:
            end_pos = len(content)
    
    # Build the new content
    # Keep the header, replace the content, keep everything after end_pos
    result = content[:content_start] + '\n' + new_content + '\n\n' + content[end_pos:]
    
    return result


# -----------------------------------------------
# Helper Functions
# -----------------------------------------------

def _error_response(
    run_id: str,
    report_type: str,
    error_message: str,
    warnings: Optional[List[str]] = None
) -> Dict:
    """Build a standardized error response."""
    response = {
        "run_id": run_id,
        "report_type": report_type,
        "status": "error",
        "error": error_message
    }
    if warnings:
        response["warnings"] = warnings
    return response


# -----------------------------------------------
# Comparison Report Revision (Stub)
# -----------------------------------------------

async def revise_comparison_report(
    comparison_id: str,
    revision_version: Optional[int] = None
) -> Dict:
    """
    Assemble a revised comparison report using AI-generated content.
    
    NOTE: This is a stub for future implementation.
    
    Args:
        comparison_id: Comparison identifier.
        revision_version: Specific version of revisions to use.
    
    Returns:
        dict with error indicating not yet implemented.
    """
    return {
        "comparison_id": comparison_id,
        "report_type": "comparison",
        "status": "error",
        "error": "Comparison report revision is not yet implemented. "
                "Use revise_performance_test_report with report_type='comparison' "
                "when this feature is available."
    }
