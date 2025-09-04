# datadog.py
import json
from fastmcp import FastMCP, Context
from services.datadog_api import (
    load_environment_json, 
    get_metrics_for_hosts
)

mcp = FastMCP(name="datadog")

@mcp.tool
async def load_environment(env_name: str, ctx: Context) -> dict:
    """
    Loads the complete environment configuration from environments.json and puts it into context.

    Args:
        env_name: The environment short name to load (e.g., 'QA', 'UAT', etc.).
        ctx: The FastMCP workflow context.

    Returns:
        dict: Complete environment configuration for the selected environment.
    """
    env_config = await load_environment_json(env_name)
    serialized_config = json.dumps(env_config)
    ctx.set_state("env_config", serialized_config)
    
    # Extract key info for the log message
    env_tag = env_config.get("env_tag", "unknown")
    host_count = len(env_config.get("hosts", []))
    k8s_services = len(env_config.get("kubernetes", {}).get("services", []))
    
    await ctx.info(f"Environment '{env_name}' loaded with env_tag: {env_tag}, {host_count} hosts, {k8s_services} k8s services")
    return env_config

@mcp.tool
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

if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down Datadog MCP…")
