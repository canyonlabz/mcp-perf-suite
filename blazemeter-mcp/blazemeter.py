# blazemeter.py
from fastmcp import FastMCP  # ✅ FastMCP 2.x import
from typing import Optional

from services.blazemeter_api import (
    list_workspaces,
    list_projects,
    list_tests,
    run_test,
    get_results_summary,
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
async def get_projects(workspace_id: str) -> str:
    """
    List projects inside a given BlazeMeter workspace.

    Args:
        workspace_id: The BlazeMeter workspace ID.
    Returns:
        String (JSON or formatted text) listing projects.
    """
    return await list_projects(workspace_id)

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
async def get_run_results(run_id: str, include_artifacts: Optional[bool] = False) -> str:
    """
    Get the latest summary for a given run, optionally downloading artifacts.

    Args:
        run_id: The BlazeMeter test run ID.
        include_artifacts: If True, also download JTL/logs to an ./artifacts folder.
    Returns:
        String (JSON or formatted text) summary of run status and KPIs.
    """
    return await get_results_summary(run_id, include_artifacts=include_artifacts)

if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down BlazeMeter MCP…")
