import os
from pathlib import Path
from typing import Optional, List, Dict
from fastmcp import Context
from utils.config import load_config

# Load config
config = load_config()
ARTIFACTS_PATH = config['artifacts']['artifacts_path']

async def list_available_reports(test_run_id: Optional[str] = None, ctx: Context = None) -> List[Dict]:
    """
    Lists available Markdown performance reports from artifacts directory.
    
    Args:
        test_run_id: If provided, lists single-run reports for that run_id.
                     If None, lists comparison reports from 'comparisons/' folder.
        ctx: FastMCP context for logging.
    
    Returns:
        List of report metadata dicts with:
        - filename
        - filepath
        - report_type ("single" or "comparison")
        - test_run_ids (list)
        - display_name (parsed title or filename)
    """
    reports = []
    
    if test_run_id:
        # Single test run reports: artifacts/<test_run_id>/reports/
        report_dir = Path(ARTIFACTS_PATH) / test_run_id / "reports"
        report_type = "single"
    else:
        # Comparison reports: artifacts/comparisons/
        report_dir = Path(ARTIFACTS_PATH) / "comparisons"
        report_type = "comparison"
    
    if not report_dir.exists():
        warning_msg = f"Report directory not found: {report_dir}"
        if ctx:
            await ctx.warning(warning_msg)
        return {"warning": warning_msg}
    
    for file in report_dir.glob("*.md"):
        filename = file.name
        
        # Parse test run IDs from filename
        # Examples: performance_report_80014829.md, comparison_report_79973739_80014829.md
        test_run_ids = []
        if report_type == "single":
            # Extract from pattern: performance_report_<run_id>.md
            parts = filename.replace(".md", "").split("_")
            if len(parts) >= 3:
                test_run_ids = [parts[-1]]
        else:
            # Extract from pattern: comparison_report_<id1>_<id2>.md
            parts = filename.replace(".md", "").split("_")
            if len(parts) >= 4:
                test_run_ids = parts[2:]  # All IDs after "comparison_report"
        
        # Extract display name from first line of file
        display_name = filename
        try:
            with open(file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line.startswith('#'):
                    display_name = first_line.lstrip('#').strip()
        except Exception as e:
            if ctx:
                await ctx.warning(f"Could not parse title from {filename}: {e}")
                return {"warning": f"Error reading {filename}: {e}"}
        
        reports.append({
            "filename": filename,
            "filepath": str(file.absolute()),
            "report_type": report_type,
            "test_run_ids": test_run_ids,
            "display_name": display_name
        })

    if not reports:
        error_msg = f"No markdown report files found in {report_dir}"
        if ctx:
            await ctx.error(error_msg)
        return {"error": error_msg}

    if ctx:
        await ctx.info(f"Found {len(reports)} {report_type} reports.")
    
    return reports


async def list_available_charts(test_run_id: Optional[str] = None, ctx: Context = None) -> List[Dict]:
    """
    Lists available PNG chart images from artifacts directory.
    
    Args:
        test_run_id: If provided, lists charts for that single run.
                     If None, lists comparison charts from 'comparisons/' folder.
        ctx: FastMCP context for logging.
    
    Returns:
        List of chart metadata dicts with:
        - filename
        - filepath
        - chart_type (inferred from filename if possible)
        - description
    """
    charts = []
    
    if test_run_id:
        # Single test run charts: artifacts/<test_run_id>/charts/
        chart_dir = Path(ARTIFACTS_PATH) / test_run_id / "charts"
    else:
        # Comparison charts: artifacts/comparisons/charts/ (if they exist in future)
        chart_dir = Path(ARTIFACTS_PATH) / "comparisons" / "charts"
    
    if not chart_dir.exists():
        warning_msg = f"Chart directory not found: {chart_dir}"
        if ctx:
            await ctx.warning(warning_msg)
        return {"warning": warning_msg}
    
    for file in chart_dir.glob("*.png"):
        filename = file.name
        
        # Parse chart filename pattern: <metric_type>_metric_<host_or_service>.png
        # Example: memory_metric_nga-ai-skills-ap.png
        metric_type = "unknown"
        host_or_service = "unknown"
        
        # Remove .png extension
        name_without_ext = filename.replace(".png", "")
        
        # Split by underscore
        parts = name_without_ext.split("_")
        
        if len(parts) >= 3 and parts[1] == "metric":
            metric_type = parts[0]  # First part is metric type (cpu, memory, etc.)
            host_or_service = "_".join(parts[2:])  # Everything after "metric" is host/service
        
        # Create human-readable description
        description = f"{metric_type.upper()} metrics for {host_or_service}"
        
        charts.append({
            "filename": filename,
            "filepath": str(file.absolute()),
            "metric_type": metric_type,
            "host_or_service": host_or_service,
            "description": description
        })
    
    if not charts:
        error_msg = f"No PNG chart files found in {chart_dir}"
        if ctx:
            await ctx.error(error_msg)
        return {"error": error_msg}
    
    if ctx:
        await ctx.info(f"Found {len(charts)} charts.")
    
    return charts
