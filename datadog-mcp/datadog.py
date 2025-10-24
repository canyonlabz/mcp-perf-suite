# datadog.py
from typing import Optional, Dict, Any, List
import json
from fastmcp import FastMCP, Context    # ✅ FastMCP 2.x import
from services.datadog_api import (
    load_environment_json, 
    collect_host_metrics,
    collect_kubernetes_metrics
)
from services.datadog_logs import collect_logs

mcp = FastMCP(name="datadog")

@mcp.tool()
async def load_environment(env_name: str, ctx: Context) -> Dict[str, Any]:
    """
    Loads the complete environment configuration from environments.json and stores it in context.

    Args:
        env_name (str): The environment short name to load (e.g., 'QA', 'UAT', etc.).
        ctx (Context, optional): Workflow context for chaining state/status/errors.

    Returns:
        dict: Complete environment configuration for the selected environment.
    """
    return await load_environment_json(env_name, ctx)

@mcp.tool()
async def get_host_metrics(env_name: str, start_time: str, end_time: str, run_id: Optional[str], ctx: Context) -> Dict[str, Any]:
    """
    Retrieves CPU and memory metrics for all Hosts in the specified environment.
    
    Args:
        env_name (str): The environment short name to load (e.g., 'QA', 'UAT', etc.).
        start_time (str): Start timestamp in format "YYYY-MM-DD HH:MM:SS" (e.g., "2025-10-21 22:10:00").
        end_time (str): End timestamp in format "YYYY-MM-DD HH:MM:SS" (e.g., "2025-10-21 22:10:00").
        run_id (Optional[str]): Optional test run identifier for artifacts (e.g., BlazeMeter run_id or timestamp '2023-01-01T00:00:00Z').
        ctx (Context, optional): Workflow context for chaining state/status/errors.

    Returns:
        dict: A dictionary containing list of CSV output files and high-level summary statistics.
    """
    return await collect_host_metrics(env_name, start_time, end_time, run_id, ctx)

@mcp.tool()
async def get_kubernetes_metrics(env_name: str, start_time: str, end_time: str, run_id: Optional[str], ctx: Context) -> Dict[str, Any]:
    """
    Retrieves CPU and memory metrics for all Kubernetes services in the specified environment.

    Args:
        env_name (str): The environment short name to load (e.g., 'QA', 'UAT', etc.).
        start_time (str): Start timestamp in format "YYYY-MM-DD HH:MM:SS" (e.g., "2025-10-21 22:10:00").
        end_time (str): End timestamp in format "YYYY-MM-DD HH:MM:SS" (e.g., "2025-10-21 22:10:00").
        run_id (Optional[str]): Optional test run identifier for artifacts (e.g., BlazeMeter run_id or timestamp '2023-01-01T00:00:00Z').
        ctx (Context, optional): Workflow context for chaining state/status/errors.

    Returns:
        dict: A dictionary containing list of CSV output files and high-level summary statistics.
    """
    return await collect_kubernetes_metrics(env_name, start_time, end_time, run_id, ctx)

@mcp.tool()
async def get_logs(env_name: str, start_time: str, end_time: str, query_type: str, run_id: Optional[str], ctx: Context, custom_query: Optional[str] = None) -> dict:
    """
    Retrieve logs from Datadog for a specific environment and time range.
    
    Args:
        env_name: Environment name from environments.json
        start_time: Start time (ISO 8601 format or epoch timestamp)
        end_time: End time (ISO 8601 format or epoch timestamp)
        query_type: Template types ("all_errors", "warnings", "http_errors", "api_errors", "service_errors", "host_errors", "kubernetes_errors", "custom")
        run_id: Optional run ID for organizing artifacts
        ctx: Workflow context for chaining state/status/errors
        custom_query: Custom Datadog query (required if query_type="custom")
        
    Returns:
        dict: Dictionary with keys 'files' (list of CSV file paths) and 'summary' (summary statistics)
    """
    return await collect_logs(env_name, start_time, end_time, query_type, run_id, ctx, custom_query)

if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down Datadog MCP…")
