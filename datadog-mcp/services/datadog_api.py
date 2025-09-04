# services/datadog_api.py
import os
import json
import httpx
import csv
from datetime import datetime
from utils.config import load_config

# Load config at the top as in BlazeMeter
config = load_config()
artifacts_base = config["artifacts"]["artifacts_path"]
environments_json_path = config["datadog"]["environments_json_path"]

DD_API_KEY = os.getenv("DD_API_KEY")
DD_APP_KEY = os.getenv("DD_APP_KEY")
DATADOG_API_URL = "https://api.us3.datadoghq.com/api/v1/query"

async def load_environment_json(env_name: str) -> dict:
    """
    Loads the complete environment configuration for a given environment from environments.json.
    Args:
        env_name (str): The environment name ("QA", "UAT", etc.)
    Returns:
        dict: Complete environment configuration including env_tag, metadata, tags, services, hosts, and kubernetes sections.
    """
    with open(environments_json_path, "r", encoding="utf-8") as f:
        envdata = json.load(f)
    
    env_config = envdata["environments"].get(env_name)
    if not env_config:
        raise ValueError(f"Environment '{env_name}' not found in environments.json")
    
    # Add the environment name to the config for reference
    env_config["environment_name"] = env_name
    
    return env_config

async def get_metrics_for_hosts(run_id: str, env_config: dict, start_time: str, end_time: str, ctx):
    """
    Pulls CPU and memory metrics for each host in the environment and writes them to a CSV.
    Args:
        run_id (str): Unique run identifier (BlazeMeter run_id)
        env_config (dict): Complete environment configuration from environments.json
        start_time/end_time: Epoch/int or '%Y-%m-%d %H:%M:%S' strings.
        ctx: FastMCP context (for info/error reporting)
    Returns:
        str: Path to output CSV file in artifacts/run_id/datadog/
    """

    # Decide output directory
    outdir = os.path.join(artifacts_base, str(run_id), "datadog")
    os.makedirs(outdir, exist_ok=True)
    outcsv = os.path.join(outdir, "host_metrics.csv")

    # Convert times if needed (assume epoch or ISO str)
    def to_epoch(ts):
        if isinstance(ts, (float, int)):
            return int(ts)
        try:
            # Try ISO format, fallback to original int string
            return int(datetime.fromisoformat(ts).timestamp())
        except Exception:
            return int(ts)

    start_epoch = to_epoch(start_time)
    end_epoch = to_epoch(end_time)

    # Extract environment info from config
    env_tag = env_config.get("env_tag", "unknown")
    hosts = env_config.get("hosts", [])
    env_name = env_config.get("environment_name", "unknown")

    # Metric queries: cpu (user), mem (used), mem (total)
    metric_query_template = (
        "avg:system.cpu.user{{host:{hostname}}}.rollup(avg,60),"
        "avg:system.mem.used{{host:{hostname}}}.rollup(avg,60),"
        "avg:system.mem.total{{host:{hostname}}}.rollup(avg,60)"
    )

    async with httpx.AsyncClient() as client:
        with open(outcsv, "w", newline="") as fcsv:
            writer = csv.writer(fcsv)
            writer.writerow([
                "env_name", "env_tag", "hostname", "timestamp", "metric", "value"
            ])
            
            for host in hosts:
                hostname = host["hostname"]
                query_str = metric_query_template.format(hostname=hostname)
                params = {
                    "from": start_epoch,
                    "to": end_epoch,
                    "query": query_str
                }
                headers = {
                    "DD-API-KEY": DD_API_KEY,
                    "DD-APPLICATION-KEY": DD_APP_KEY
                }
                
                try:
                    resp = await client.get(DATADOG_API_URL, params=params, headers=headers)
                    resp.raise_for_status()  # Raises exception for bad status codes
                    
                    resp_json = resp.json()
                    for series in resp_json.get("series", []):
                        metric_name = series.get("display_name", series.get("metric"))
                        for point in series.get("pointlist", []):
                            ts, val = point
                            # Datadog timestamps are ms; convert to ISO8601
                            dt = datetime.utcfromtimestamp(ts / 1000).isoformat()
                            writer.writerow([env_name, env_tag, hostname, dt, metric_name, val])
                            
                except httpx.HTTPStatusError as e:
                    await ctx.error(f"Datadog API error: HTTP {e.response.status_code} for host {hostname}")
                    continue
                except Exception as e:
                    await ctx.error(f"Error fetching metrics for host {hostname}: {str(e)}")
                    continue
            
            await ctx.info(f"Host metrics CSV created: {outcsv}")
    
    return outcsv

