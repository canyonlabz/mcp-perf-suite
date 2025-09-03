# services/datadog_api.py

import os
import json
import aiohttp
import csv
from utils.config import load_config

# Load config at the top as in BlazeMeter
config = load_config()
artifacts_base = config["artifacts"]["artifacts_path"]
environments_json_path = config["datadog"]["environments_json_path"]

DD_API_KEY = os.getenv("DD_API_KEY")
DD_APP_KEY = os.getenv("DD_APP_KEY")
DATADOG_API_URL = "https://api.us3.datadoghq.com/api/v1/query"

async def load_environment_json(env_name: str) -> list:
    """
    Loads the hosts for a given environment from environments.json.
    Args:
        env_name (str): The environment name ("QA", "DEV", etc.)
    Returns:
        list[dict]: List of host entries for requested environment.
    """
    with open(environments_json_path, "r", encoding="utf-8") as f:
        envdata = json.load(f)
    hosts = envdata["environments"].get(env_name)
    if not hosts:
        raise ValueError(f"Environment '{env_name}' not found in environments.json")
    return hosts

async def get_kpi_metrics_for_hosts(run_id: str, hosts: list, start_time: str, end_time: str, ctx):
    """
    Pulls CPU and memory metrics for each host in the environment and writes them to a CSV.
    Args:
        run_id (str): Unique run identifier (BlazeMeter run_id)
        hosts (list): List of dicts from environments.json for one env.
        start_time/end_time: Epoch/int or '%Y-%m-%d %H:%M:%S' strings.
        ctx: FastMCP context (for info/error reporting)
    Returns:
        str: Path to output CSV file in artifacts/run_id/datadog/
    """

    # Decide output directory
    outdir = os.path.join(artifacts_base, str(run_id), "datadog")
    os.makedirs(outdir, exist_ok=True)
    outcsv = os.path.join(outdir, "kpi_metrics.csv")

    # Convert times if needed (assume epoch or ISO str)
    def to_epoch(ts):
        if isinstance(ts, (float, int)):
            return int(ts)
        try:
            # Try ISO format, fallback to original int string
            from datetime import datetime
            return int(datetime.fromisoformat(ts).timestamp())
        except Exception:
            return int(ts)

    start_epoch = to_epoch(start_time)
    end_epoch = to_epoch(end_time)

    # Metric queries: cpu (user), mem (used), mem (total)
    metric_query_template = (
        "avg:system.cpu.user{{host:{hostname}}}.rollup(avg,60),"
        "avg:system.mem.used{{host:{hostname}}}.rollup(avg,60),"
        "avg:system.mem.total{{host:{hostname}}}.rollup(avg,60)"
    )

    async with aiohttp.ClientSession() as session:
        with open(outcsv, "w", newline="") as fcsv:
            writer = csv.writer(fcsv)
            writer.writerow([
                "env", "hostname", "timestamp", "metric", "value"
            ])
            for host in hosts:
                hostname = host["hostname"]
                envtag = host.get("env", "")
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
                async with session.get(DATADOG_API_URL, params=params, headers=headers) as r:
                    if r.status != 200:
                        await ctx.error("Datadog API error", f"HTTP {r.status} for host {hostname}")
                        continue
                    resp = await r.json()
                    for series in resp.get("series", []):
                        metric_name = series.get("display_name", series.get("metric"))
                        for point in series.get("pointlist", []):
                            ts, val = point
                            # Datadog timestamps are ms; convert to ISO8601
                            from datetime import datetime
                            dt = datetime.utcfromtimestamp(ts / 1000).isoformat()
                            writer.writerow([envtag, hostname, dt, metric_name, val])
            await ctx.info("CSV file output", outcsv)
    return outcsv
