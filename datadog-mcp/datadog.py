from fastmcp import FastMCP, Context
from services.datadog_api import (
    load_environment_json, 
    get_kpi_metrics_for_hosts
)

mcp = FastMCP(name="datadog")

@mcp.tool
async def load_environment(env_name: str, ctx: Context) -> dict:
    """
    Loads the given environment's hosts from environments.json and puts them into context.

    Args:
        env_name: The environment to load (e.g., 'QA', 'DEV').
        ctx: The FastMCP workflow context.

    Returns:
        dict: Host info for the selected environment.
    """
    env_hosts = await load_environment_json(env_name)
    ctx.set_state("env_hosts", env_hosts)
    await ctx.info("Environment hosts loaded", env_hosts)
    return env_hosts

@mcp.tool
async def get_kpi_metrics(run_id: str, start_time: str, end_time: str, ctx: Context) -> str:
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
    env_hosts = ctx.get_state("env_hosts")
    csv_file = await get_kpi_metrics_for_hosts(
        run_id=run_id,
        hosts=env_hosts,
        start_time=start_time,
        end_time=end_time,
        ctx=ctx
    )
    await ctx.info("CSV file created", csv_file)
    return csv_file

if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down Datadog MCP…")
