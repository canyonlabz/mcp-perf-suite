# blazemeter.py
from fastmcp import FastMCP, Context  # ✅ FastMCP 2.x import
from typing import Optional, Dict, Any
from utils.config import load_config

from services.blazemeter_api import (
    list_workspaces,
    list_projects,
    list_tests,
    run_test,
    get_test_status,
    get_results_summary,
    list_test_runs,
    get_session_artifacts,
    download_artifact_zip_file,
    extract_artifact_zip_file,
    process_extracted_artifact_files,
    get_public_report_url,
    fetch_aggregate_report,
)

mcp = FastMCP(
    name="blazemeter",
)

@mcp.tool
async def get_workspaces() -> str:
    """
    List BlazeMeter workspaces for the configured account.

    Returns:
        A human-readable string summary (or JSON string) of available workspaces.
    """
    return await list_workspaces()

@mcp.tool
async def get_projects(workspace_id: str, project_name: Optional[str] = None) -> str:
    """
    List projects inside a given BlazeMeter workspace.

    Args:
        workspace_id: The BlazeMeter workspace ID.
        project_name: Optional project name to filter results. If provided, only projects matching this name will be returned.
    Returns:
        String (JSON or formatted text) listing projects.
    """
    return await list_projects(workspace_id, project_name)

@mcp.tool
async def get_tests(project_id: str) -> str:
    """
    List tests for a given BlazeMeter project.

    Args:
        project_id: The BlazeMeter project ID.
    Returns:
        String (JSON or formatted text) listing tests.
    """
    return await list_tests(project_id)

@mcp.tool
async def start_test(test_id: str, ctx: Context) -> str:
    """
    Starts a BlazeMeter test run.

    Args:
        test_id: The BlazeMeter test ID.
        ctx (Context, optional): FastMCP workflow context to store run_id for chaining.
    Returns:
        String (JSON or formatted text) with the created run ID and status.
    """
    return await run_test(test_id, ctx)

@mcp.tool()
async def check_test_status(run_id: str, ctx: Context) -> dict:
    """
    Checks the status of a BlazeMeter test run by run_id.

    Args:
        run_id (str): BlazeMeter master/run ID.
        ctx (Context, optional): Workflow context for chaining state/status/errors.

    Returns:
        A dictionary containing:
            - run_id: The provided run ID.
            - status: Main BlazeMeter run status (examples: 'STARTING', 'RUNNING', 'ENDED').
            - statuses: Percentage breakdown of sub-statuses (pending, booting, ready, ended, etc.).
            - error: Null, string, or object if an error is present in BlazeMeter response.
            - has_error: True if an error was detected or test failed, otherwise False.
            - ctx: Also updates context with latest status info for advanced workflows.

    Usage:
        Use to monitor if a test started, is running, or has finished. Useful for polling during test execution.
    """
    return await get_test_status(run_id, ctx)

@mcp.tool
async def get_run_results(run_id: str, ctx: Context) -> str:
    """
    Get the latest summary for a given run.

    Args:
        run_id: The BlazeMeter test run ID.
        ctx (Context, optional): FastMCP context to record, reuse, or cache summary info.
    Returns:
        String (JSON or formatted text) summary of run status and KPIs; context updated with summary fields for workflow chaining.
    """
    return await get_results_summary(run_id, ctx)

@mcp.tool()
def get_artifacts_path() -> str:
    """
    Returns the configured artifacts base path from config.yaml.
    """
    config = load_config()
    artifacts_path = config.get("artifacts", {}).get("artifacts_path", "")
    return artifacts_path or "No artifacts_path found in config."

@mcp.tool()
async def get_test_runs(test_id: str, start_time: str, end_time: str, ctx: Context) -> list:
    """
    Lists past BlazeMeter test runs (masters) for the specified test within the given date range.
    Dates should be supplied in human-readable format: 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD'

    Args:
        test_id (str): The BlazeMeter test ID.
        start_time (str): The start time for the date range.
        end_time (str): The end time for the date range.
        ctx (Context, optional): FastMCP context for chaining or caching results.
    Returns:
        List of test run summaries.
    """
    return await list_test_runs(test_id, start_time, end_time, ctx)

@mcp.tool()
async def get_artifact_file_list(session_id: str, ctx: Context) -> dict:
    """
    Returns a dict of downloadable artifact/log files for a given BlazeMeter session.
    Keys are filenames, values are their URLs.

    Args:
        session_id (str): BlazeMeter session ID.
        ctx (Context, optional): FastMCP context for chaining file URLs.

    Returns:
        Dict of filename -> URL. Context updated with file list.
    """
    return await get_session_artifacts(session_id, ctx)

@mcp.tool()
async def download_artifacts_zip(artifact_zip_url: str, run_id: str, ctx: Context) -> str:
    """
    Downloads the artifacts.zip for a given BlazeMeter run to the proper artifacts path.

    Args:
        artifact_zip_url (str): S3 URL to artifacts.zip.
        run_id (str): BlazeMeter run/master ID.
        ctx (Context, optional): Workflow context to save file path.

    Returns:
        Local file path (string). Updates context with path for downstream workflow steps.

    Note:
        If download fails with 500 errors, try:
        1. Re-fetch test run results: get_run_results(run_id)
        2. Re-fetch artifact file list: get_artifact_file_list(session_id)
        3. Retry download with updated URL
        
        Common issues:
        - 500 Internal Server Error: Usually indicates expired session/URL
        - Solution: Re-fetch run details and artifact list before retrying
    """
    return await download_artifact_zip_file(artifact_zip_url, run_id, ctx)

@mcp.tool()
async def extract_artifact_zip(local_zip_path: str, run_id: str, ctx: Context) -> list:
    """
    Extracts a downloaded artifacts.zip file for a BlazeMeter run.

    Args:
        local_zip_path (str): Path to artifacts.zip.
        run_id (str): BlazeMeter run ID.
        ctx (Context, optional): Workflow context to add list of extracted files.

    Returns:
        List of extracted file paths. Updates context for downstream tools.
    """
    return await extract_artifact_zip_file(local_zip_path, run_id, ctx)

@mcp.tool()
def process_extracted_files(run_id: str, extracted_files: list, ctx: Context) -> dict:
    """
    Processes BlazeMeter run artifacts (kpi.jtl, jmeter.log).

    Args:
        run_id (str): BlazeMeter run ID.
        extracted_files (list): Paths to files from ZIP extraction.
        ctx (Context, optional): Workflow context for chaining file paths and errors.

    Returns:
        Dict of output file paths and errors. Updates context for downstream steps and error handling.
    """
    return process_extracted_artifact_files(run_id, extracted_files, ctx)

@mcp.tool()
async def get_public_report(run_id: str, ctx: Context) -> dict:
    """
    Generates or retrieves a public BlazeMeter report URL for the given test run.

    Args:
        run_id (str): The BlazeMeter run/master ID.
        ctx (Context, optional): Workflow context to chain report URL/token for downstream analysis/sharing.

    Returns:
        Dictionary including:
            - run_id: Test run ID associated with the URL.
            - public_url: Public, shareable BlazeMeter report link.
            - public_token: The underlying token (for debugging or manual URL re-creation).
            - is_new: True if the token was just created; False if it existed already.
            - error: An error message if something went wrong.
        Updates context for workflow orchestration.

    Usage:
        Use to quickly generate a shareable report URL for stakeholders after a test completes.
    """
    return await get_public_report_url(run_id, ctx)

@mcp.tool()
async def get_aggregate_report(run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Get BlazeMeter aggregate performance report for a test run
    
    Args:
        run_id: The BlazeMeter run/master ID
        ctx: FastMCP workflow context for chaining
        
    Returns:
        Dictionary containing aggregate performance statistics and CSV file path
    """
    return await fetch_aggregate_report(run_id, ctx)

# -----------------------------
# BlazeMeter MCP entry point
# -----------------------------
if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down BlazeMeter MCP…")