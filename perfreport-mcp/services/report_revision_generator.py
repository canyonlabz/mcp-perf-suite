"""
services/report_revision_generator.py
Report revision generator for AI-assisted report enhancement.

This module implements the revise_performance_test_report function that
assembles revised reports using AI-generated content from the revisions folder.
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
from services.revision_context_manager import get_revision_content


# Load configuration
CONFIG = load_config()
ARTIFACTS_CONFIG = CONFIG.get('artifacts', {})
ARTIFACTS_PATH = Path(ARTIFACTS_CONFIG.get('artifacts_path', './artifacts'))

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
    
    This function:
    1. Loads the original report and its metadata
    2. Backs up the original report and metadata (with _original suffix)
    3. Reads AI-generated revision content for enabled sections
    4. Replaces original placeholders with AI-revised content
    5. Saves the new revised report (with _revised suffix)
    
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
        revised_timestamp = datetime.now().isoformat()
        
        # Validate report_type
        is_valid, error = validate_report_type(report_type)
        if not is_valid:
            return _error_response(run_id, report_type, error)
        
        # Get paths
        reports_folder = get_reports_folder_path(run_id, report_type)
        revisions_folder = get_revisions_folder_path(run_id, report_type)
        
        # Validate reports folder exists
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
        
        # Load original report content
        original_content = original_report_path.read_text(encoding='utf-8')
        
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
        
        # Collect revision content for each enabled section
        sections_revised = []
        revision_versions_used = {}
        revised_content = original_content
        
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
            
            # Get the placeholder to replace
            placeholder = section_config.get("placeholder", "")
            ai_placeholder = section_config.get("ai_placeholder", "")
            
            if not placeholder:
                warnings.append(
                    f"No placeholder defined for section '{section_id}'. Skipping."
                )
                continue
            
            # Replace the placeholder with AI content
            revision_text = revision_result.get("content", "")
            
            # Try replacing the original placeholder pattern {{PLACEHOLDER}}
            original_placeholder = "{{" + placeholder + "}}"
            if original_placeholder in revised_content:
                revised_content = revised_content.replace(
                    original_placeholder, 
                    revision_text
                )
                sections_revised.append(section_id)
                revision_versions_used[section_id] = version_to_use
            else:
                # Check if already revised (AI placeholder present)
                ai_placeholder_pattern = "{{" + ai_placeholder + "}}"
                if ai_placeholder_pattern in revised_content:
                    revised_content = revised_content.replace(
                        ai_placeholder_pattern,
                        revision_text
                    )
                    sections_revised.append(section_id)
                    revision_versions_used[section_id] = version_to_use
                else:
                    warnings.append(
                        f"Placeholder '{original_placeholder}' not found in report. "
                        f"Section '{section_id}' may already be revised or placeholder is missing."
                    )
        
        if not sections_revised:
            return _error_response(
                run_id, report_type,
                "No sections were revised. Check warnings for details.",
                warnings=warnings
            )
        
        # Backup original report and metadata
        backup_result = await _backup_original_files(run_id, report_type, warnings)
        
        if backup_result.get("status") == "error":
            return _error_response(
                run_id, report_type,
                f"Failed to backup original files: {backup_result.get('error')}",
                warnings=warnings
            )
        
        # Add revision metadata to the report content
        revision_header = _build_revision_header(
            run_id, report_type, sections_revised, 
            revision_versions_used, revised_timestamp
        )
        revised_content = _insert_revision_header(revised_content, revision_header)
        
        # Save revised report
        revised_report_path = get_revised_report_path(run_id, report_type)
        revised_report_path.write_text(revised_content, encoding='utf-8')
        
        # Update metadata file with revision info
        await _update_metadata_with_revision(
            run_id, report_type, sections_revised,
            revision_versions_used, revised_timestamp, str(revised_report_path)
        )
        
        return {
            "run_id": run_id,
            "report_type": report_type,
            "original_report_path": str(original_report_path),
            "revised_report_path": str(revised_report_path),
            "backup_report_path": str(backup_result.get("backup_report_path", "")),
            "backup_metadata_path": str(backup_result.get("backup_metadata_path", "")),
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
    timestamp: str
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
    revised_report_path: str
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
