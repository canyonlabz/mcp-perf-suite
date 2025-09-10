# datadog.py
from typing import Optional, Dict, Any, List
import json
from fastmcp import FastMCP, Context    # ✅ FastMCP 2.x import
from services.datadog_api import (
    load_environment_json, 
    collect_host_metrics,
    collect_kubernetes_metrics
)

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
        start_time (str): Start timestamp in epoch or ISO8601 format.
        end_time (str): End timestamp in epoch or ISO8601 format.
        run_id (Optional[str]): Optional test run identifier for artifacts.
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
        start_time (str): Start timestamp in epoch or ISO8601 format.
        end_time (str): End timestamp in epoch or ISO8601 format.
        run_id (Optional[str]): Optional test run identifier for artifacts.
        ctx (Context, optional): Workflow context for chaining state/status/errors.

    Returns:
        dict: A dictionary containing list of CSV output files and high-level summary statistics.
    """
    return await collect_kubernetes_metrics(env_name, start_time, end_time, run_id, ctx)

if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down Datadog MCP…")
