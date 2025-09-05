# datadog.py
import json
from fastmcp import FastMCP, Context    # ✅ FastMCP 2.x import
from services.datadog_api import (
    load_environment_json, 
    get_metrics_for_hosts,
    get_kubernetes_metrics_for_services
)

mcp = FastMCP(name="datadog")

@mcp.tool()
async def load_environment(env_name: str, ctx: Context) -> dict:
    """
    Loads the complete environment configuration from environments.json and puts it into context.

    Args:
        env_name: The environment short name to load (e.g., 'QA', 'UAT', etc.).
        ctx: The FastMCP workflow context.

    Returns:
        dict: Complete environment configuration for the selected environment.
    """
    return await load_environment_json(env_name, ctx)

@mcp.tool()
async def get_host_metrics(run_id: str, start_time: str, end_time: str, ctx: Context) -> str:
    """
    Retrieves Datadog CPU/memory metrics for all hosts in the current context.
    Outputs a CSV artifact in the artifacts directory for the given run_id.

    Args:
        run_id: BlazeMeter test run ID.
        start_time: Start timestamp for metrics window.
        end_time: End timestamp for metrics window.
        ctx: The FastMCP workflow context.

    Returns:
        str: The output path to the CSV file.
    """
    raw_config = ctx.get_state("env_config")
    if not raw_config:
        await ctx.error("No environment config found in context. Please run load_environment first.")
        return "Error: No environment configuration loaded"
    
    env_config = json.loads(raw_config)
    
    # Validate that hosts exist in the config
    hosts = env_config.get("hosts", [])
    if not hosts:
        await ctx.error("No hosts found in environment configuration")
        return "Error: No hosts configured for this environment"
    
    csv_file = await get_metrics_for_hosts(
        run_id=run_id,
        env_config=env_config,
        start_time=start_time,
        end_time=end_time,
        ctx=ctx
    )
    
    env_name = env_config.get("environment_name", "unknown")
    host_count = len(hosts)
    await ctx.info(f"Host metrics CSV created for {env_name} environment ({host_count} hosts): {csv_file}")
    
    return csv_file

@mcp.tool()
async def get_kubernetes_metrics(run_id: str, start_time: str, end_time: str, env_config: dict, ctx: Context) -> str:
    """
    Retrieves Kubernetes CPU metrics for all services in the specified environment.
    Outputs a CSV artifact in the artifacts directory for the given run_id.

    Args:
        run_id: BlazeMeter test run ID.
        start_time: Start timestamp for metrics window.
        end_time: End timestamp for metrics window.
        env_config: The environment configuration dictionary.
        ctx: The FastMCP workflow context.

    Returns:
        str: The output path to the CSV file.
    """
    if not env_config:
        await ctx.error("No environment configuration provided.")
        return "ERROR: No environment configuration provided"
    
    # Validate that Kubernetes config exists
    k8s_config = env_config.get("kubernetes", {})
    if not k8s_config:
        await ctx.error("No Kubernetes configuration found in environment")
        return "ERROR: No Kubernetes configuration for this environment"
    
    # Validate that services exist in the Kubernetes config
    services = k8s_config.get("services", [])
    if not services:
        await ctx.error("No Kubernetes services found in environment configuration")
        return "ERROR: No Kubernetes services configured for this environment"
    
    csv_file = await get_kubernetes_metrics_for_services(
        run_id=run_id,
        env_config=env_config,
        start_time=start_time,
        end_time=end_time,
        ctx=ctx
    )
    
    env_name = env_config.get("environment_name", "unknown")
    service_count = len(services)
    await ctx.info(f"Kubernetes metrics CSV created for {env_name} environment ({service_count} services): {csv_file}")
    
    return csv_file

if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down Datadog MCP…")
