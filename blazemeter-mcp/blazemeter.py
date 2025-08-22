from typing import Any
from mcp.server.fastmcp import FastMCP

from services.blazemeter_api import (
    list_workspaces,
    list_projects,
    list_tests,
    run_test,
    get_results_summary,
    download_artifacts,
)

mcp = FastMCP("blazemeter")

@mcp.tool()
async def get_workspaces() -> str:
    """Return a list of available BlazeMeter workspaces."""
    return await list_workspaces()

@mcp.tool()
async def get_projects(workspace_id: str) -> str:
    """Return a list of projects for a workspace."""
    return await list_projects(workspace_id)

@mcp.tool()
async def get_tests(project_id: str) -> str:
    """Return a list of tests for the given project."""
    return await list_tests(project_id)

@mcp.tool()
async def start_test(test_id: str) -> str:
    """Start a BlazeMeter test and return run details."""
    return await run_test(test_id)

@mcp.tool()
async def get_run_results(run_id: str) -> str:
    """
    Get the summary, JTL, and logs for a test run.
    Artifacts are available in the `artifacts/` directory.
    """
    return await get_results_summary(run_id)  # You display summary, plus call download_artifacts internally

if __name__ == "__main__":
    mcp.run(transport='stdio')

