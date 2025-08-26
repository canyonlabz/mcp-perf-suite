# blazemeter.py
from fastmcp import FastMCP  # ✅ FastMCP 2.x import
from typing import Optional
from utils.config import load_config

from services.blazemeter_api import (
    list_workspaces,
    list_projects,
    list_tests,
    run_test,
    get_results_summary,
    list_test_runs,
    get_session_artifacts,
    download_artifact_zip_file,
    extract_artifact_zip_file,
    process_extracted_artifact_files
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
async def start_test(test_id: str) -> str:
    """
    Start a BlazeMeter test run.

    Args:
        test_id: The BlazeMeter test ID.
    Returns:
        String (JSON or formatted text) with the created run ID and status.
    """
    return await run_test(test_id)

@mcp.tool
async def get_run_results(run_id: str) -> str:
    """
    Get the latest summary for a given run.

    Args:
        run_id: The BlazeMeter test run ID.
    Returns:
        String (JSON or formatted text) summary of run status and KPIs.
    """
    return await get_results_summary(run_id)

@mcp.tool()
def get_artifacts_path() -> str:
    """
    Returns the configured artifacts base path from config.yaml.
    """
    config = load_config()
    artifacts_path = config.get("artifacts", {}).get("artifacts_path", "")
    return artifacts_path or "No artifacts_path found in config."

@mcp.tool()
async def get_test_runs(test_id: str, start_time: str, end_time: str) -> list:
    """
    Lists past BlazeMeter test runs (masters) for the specified test within the given date range.
    Dates should be supplied in human-readable format: 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD'
    """
    return await list_test_runs(test_id, start_time, end_time)

@mcp.tool()
async def get_artifact_file_list(session_id: str) -> dict:
    """
    Returns a dict of downloadable artifact/log files for a given BlazeMeter session.
    Keys are filenames, values are their URLs.
    """
    return await get_session_artifacts(session_id)

@mcp.tool()
async def download_artifacts_zip(artifact_zip_url: str, run_id: str) -> str:
    """
    Downloads the artifacts.zip for a given BlazeMeter run to the proper artifacts path.
    Returns the local file path.
    """
    return await download_artifact_zip_file(artifact_zip_url, run_id)

@mcp.tool()
def extract_artifact_zip(local_zip_path: str, run_id: str) -> list:
    """
    Extracts a downloaded artifacts.zip file for a BlazeMeter run.
    - local_zip_path: The full local filesystem path to artifacts.zip.
    - run_id: The run ID (used to determine artifact destination folder).
    Returns list of extracted file paths.
    """
    return extract_artifact_zip_file(local_zip_path, run_id)

@mcp.tool()
def process_extracted_files(run_id: str, extracted_files: list) -> dict:
    """
    Processes BlazeMeter run artifacts:
    - Uses only kpi.jtl for metrics, renames to test-results.csv in destination folder
    - Moves jmeter.log for diagnostics
    - Ignores other .jtl files and extraneous files
    Returns processed file paths and any errors encountered.
    Use for final step before test result analysis.
    """
    return process_extracted_artifact_files(run_id, extracted_files)

# -----------------------------
# BlazeMeter MCP entry point
# -----------------------------
if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down BlazeMeter MCP…")