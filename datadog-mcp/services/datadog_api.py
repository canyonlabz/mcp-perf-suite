# services/datadog_api.py
import os
import json
import httpx
import csv
from datetime import datetime
from dotenv import load_dotenv
from fastmcp import FastMCP, Context    # ✅ FastMCP 2.x import
from utils.config import load_config

# Load environment variables from .env file such as API keys and secrets
load_dotenv()

# Load config at the top as in BlazeMeter
config = load_config()
artifacts_base = config["artifacts"]["artifacts_path"]
environments_json_path = config["datadog"]["environments_json_path"]

DD_API_KEY = os.getenv("DD_API_KEY")
DD_APP_KEY = os.getenv("DD_APP_KEY")
DD_API_BASE_URL = os.getenv("DD_API_BASE_URL", "https://api.datadoghq.com")
DATADOG_API_URL = f"{DD_API_BASE_URL}/api/v1/query"
DATADOG_V2_TIMESERIES_URL = f"{DD_API_BASE_URL}/api/v2/query/timeseries"

async def load_environment_json(env_name: str, ctx: Context) -> dict:
    """
    Loads the complete environment configuration for a given environment from environments.json.
    Args:
        env_name (str): The environment name ("QA", "UAT", etc.)
        ctx: FastMCP context (for info/error reporting)
    Returns:
        dict: Complete environment configuration including env_tag, metadata, tags, services, hosts, and kubernetes sections.
    """
    with open(environments_json_path, "r", encoding="utf-8") as f:
        envdata = json.load(f)
    
    env_config = envdata["environments"].get(env_name)
    if not env_config:
        await ctx.error(f"Environment '{env_name}' not found in environments.json")
        raise ValueError(f"Environment '{env_name}' not found in environments.json")
    
    # Add the environment name to the config for reference
    env_config["environment_name"] = env_name
    
    # Store in context for later steps
    if ctx is not None:
        ctx.set_state("env_config", env_config)  # Store as dict directly
        ctx.set_state("env_name", env_name)

    # Extract key info for the log message
    env_tag = env_config.get("env_tag", "unknown")
    host_count = len(env_config.get("hosts", []))
    k8s_services = len(env_config.get("kubernetes", {}).get("services", []))
    await ctx.info(f"Environment '{env_name}' loaded with env_tag: {env_tag}, {host_count} hosts, {k8s_services} k8s services")

    return env_config

async def get_metrics_for_hosts(run_id: str, env_config: dict, start_time: str, end_time: str, ctx: Context):
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

async def get_kubernetes_metrics_for_services(run_id: str, env_config: dict, start_time: str, end_time: str, ctx: Context):
    """
    Pulls Kubernetes CPU and Memory metrics for services defined in environment config using Datadog v2 timeseries API.
    
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
    outcsv = os.path.join(outdir, "k8s_metrics.csv")

    # Convert times if needed (assume epoch or ISO str) 
    def to_epoch(ts):
        if isinstance(ts, (float, int)):
            return int(ts)
        try:
            # Handle both ISO format (2024-08-04T11:00:00) and space format (2024-08-04 11:00:00)
            if 'T' in str(ts):
                return int(datetime.fromisoformat(ts).timestamp())
            else:
                return int(datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").timestamp())
        except Exception:
            return int(ts)

    start_epoch = to_epoch(start_time) * 1000  # Datadog v2 API expects milliseconds
    end_epoch = to_epoch(end_time) * 1000

    # Extract environment info from config
    env_tag = env_config.get("env_tag", "unknown")
    env_name = env_config.get("environment_name", "unknown")
    k8s_config = env_config.get("kubernetes", {})
    services = k8s_config.get("services", [])
    
    # Debug: Log what we found
    await ctx.info(f"Environment: {env_name}, Tag: {env_tag}")
    await ctx.info(f"K8s config: {k8s_config}")
    await ctx.info(f"Services found: {len(services)} - {services}")

    if not services:
        await ctx.error("No Kubernetes services found in environment configuration")
        return f"ERROR: No Kubernetes services found in environment configuration: {k8s_config}"

    # Build queries for each service
    queries = []
    for idx, service in enumerate(services):
        service_filter = service.get("service_filter", "*")
        query_str = f"avg:kubernetes.cpu.usage.total{{env:{env_tag},service:{service_filter}}} by {{kube_container_name}}"
        queries.append({
            "data_source": "metrics", 
            "name": f"query_{idx}",
            "query": query_str
        })

    # Build POST request body matching your example
    post_data = {
        "data": {
            "type": "timeseries_request",
            "interval": 15000,
            "attributes": {
                "from": start_epoch,
                "to": end_epoch,
                "queries": queries,
                "formulas": [{"formula": q["name"]} for q in queries]  # One formula per query
            }
        }
    }

    headers = {
        "DD-API-KEY": DD_API_KEY,
        "DD-APPLICATION-KEY": DD_APP_KEY,
        "Content-Type": "application/json"
    }

    # Debug: Log the request details
    await ctx.info(f"Making Datadog API request with start_epoch: {start_epoch}, end_epoch: {end_epoch}")
    await ctx.info(f"Query: {queries[0]['query'] if queries else 'No queries'}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(DATADOG_V2_TIMESERIES_URL, json=post_data, headers=headers)
            await ctx.info(f"API response status: {resp.status_code}")
            resp.raise_for_status()
            resp_json = resp.json()
            await ctx.info(f"API response received, series count: {len(resp_json.get('data', {}).get('attributes', {}).get('series', []))}")
            
        except httpx.HTTPStatusError as e:
            await ctx.error(f"Datadog v2 API error: HTTP {e.response.status_code}")
            await ctx.error(f"Response body: {e.response.text}")
            return f"ERROR: Datadog v2 API error: HTTP {e.response.status_code} with response body: {e.response.text}"
        except Exception as e:
            await ctx.error(f"Error fetching Kubernetes metrics: {str(e)}")
            return f"ERROR: Error fetching Kubernetes metrics: {str(e)}"

    # Process response and write to CSV
    with open(outcsv, "w", newline="") as fcsv:
        writer = csv.writer(fcsv)
        writer.writerow([
            "env_name", "env_tag", "service_filter", "container_name", "timestamp", "metric", "value"
        ])

        # Extract data from response structure matching your uploaded JSON
        data_attrs = resp_json.get("data", {}).get("attributes", {})
        series_list = data_attrs.get("series", [])
        times = data_attrs.get("times", [])
        
        for series in series_list:
            # Extract container name from group_tags
            group_tags = series.get("group_tags", [])
            container_name = "unknown"
            for tag in group_tags:
                if tag.startswith("kube_container_name:"):
                    container_name = tag.split(":", 1)[1]
                    break

            # Map back to service filter using query_index
            query_index = series.get("query_index", 0)
            service_filter = services[query_index].get("service_filter", "*") if query_index < len(services) else "*"
            
            # Get values for this series
            values = series.get("values", [])
            
            # Write data points
            for i, timestamp_ms in enumerate(times):
                if i < len(values) and values[i] is not None:
                    dt = datetime.utcfromtimestamp(timestamp_ms / 1000).isoformat()
                    writer.writerow([
                        env_name, env_tag, service_filter, container_name, 
                        dt, "kubernetes.cpu.usage.total", values[i]
                    ])

    service_count = len(services)
    await ctx.info(f"Kubernetes metrics CSV created for {service_count} services: {outcsv}")
    return outcsv
