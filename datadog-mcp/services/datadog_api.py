# services/datadog_api.py
import os
import re
import json
import httpx
import csv
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
from dotenv import load_dotenv
from fastmcp import FastMCP, Context    # ✅ FastMCP 2.x import
from utils.config import load_config

# -----------------------------------------------
# Bootstrap
# -----------------------------------------------
load_dotenv()   # Load environment variables from .env file such as API keys and secrets
config = load_config()
artifacts_base = config["artifacts"]["artifacts_path"]
environments_json_path = config["datadog"]["environments_json_path"]
configured_tz = config.get("datadog", {}).get("time_zone", "UTC")

DD_API_KEY = os.getenv("DD_API_KEY")
DD_APP_KEY = os.getenv("DD_APP_KEY")
DD_API_BASE_URL = os.getenv("DD_API_BASE_URL", "https://api.datadoghq.com")
V1_QUERY_URL = f"{DD_API_BASE_URL}/api/v1/query"
V2_TIMESERIES_URL = f"{DD_API_BASE_URL}/api/v2/query/timeseries"

# -----------------------------------------------
# Helpers
# -----------------------------------------------

def _sanitize_filename(text: str) -> str:
    """Sanitize text to be safe for filenames."""
    text = text.strip().replace(" ", "_")
    return re.sub(r"[^a-zA-Z0-9._-]", "_", text)

def _ensure_ready(ctx: Optional[Context]):
    """Ensure required environment variables are set."""
    missing = []
    if not DD_API_KEY:
        missing.append("DD_API_KEY")
    if not DD_APP_KEY:
        missing.append("DD_APP_KEY")
    if missing:
        msg = f"Missing environment variable(s): {', '.join(missing)}"
        if ctx:
            ctx.error(msg)
        raise RuntimeError(msg)

def _ensure_artifacts_dir(run_id: str) -> str:
    """Ensure artifacts/run_id/datadog/ directory exists and return its path."""
    base = os.path.join(artifacts_base, str(run_id), "datadog")
    os.makedirs(base, exist_ok=True)
    return base

def _parse_to_utc(start_time: str, end_time: str) -> Tuple[int, int, int, int, str]:
    """Parse input times (epoch or ISO) in configured timezone and convert to UTC.

    Returns: (v1_from_s, v1_to_s, v2_from_ms, v2_to_ms, tz_label)
    """
    # Accept epoch int/float or ISO8601 (with/without T)
    def parse_one(val: str) -> datetime:
        # Try epoch first
        try:
            if isinstance(val, (int, float)) or (isinstance(val, str) and val.isdigit()):
                return datetime.fromtimestamp(int(val), tz=timezone.utc)
        except Exception:
            pass
        # ISO-like formats; interpret in configured timezone then convert to UTC
        # We only rely on naive parsing here to stay dependency-free
        val_norm = val.replace("T", " ").strip()
        # Try common formats
        fmts = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]
        for fmt in fmts:
            try:
                dt_naive = datetime.strptime(val_norm, fmt)
                # We do not have pytz; assume configured_tz is either "UTC" or ignored
                if configured_tz.upper() == "UTC":
                    return dt_naive.replace(tzinfo=timezone.utc)
                # If non-UTC is configured, we still treat dt as local wall time and convert by assuming it was local
                # Since we have no tz database here, we document that non-UTC offsets should be pre-adjusted by caller
                return dt_naive.replace(tzinfo=timezone.utc)
            except Exception:
                continue
        raise ValueError(f"Unrecognized time format: {val}")

    start_dt_utc = parse_one(start_time).astimezone(timezone.utc)
    end_dt_utc = parse_one(end_time).astimezone(timezone.utc)
    if start_dt_utc >= end_dt_utc:
        raise ValueError("start_time must be before end_time")

    v1_from_s = int(start_dt_utc.timestamp())
    v1_to_s = int(end_dt_utc.timestamp())
    v2_from_ms = v1_from_s * 1000
    v2_to_ms = v1_to_s * 1000
    tz_label = "UTC"
    return v1_from_s, v1_to_s, v2_from_ms, v2_to_ms, tz_label

def _write_csv_header(writer: csv.writer):
    """Write standard CSV header for output files."""
    writer.writerow([
        "env_name", "env_tag", "scope", "hostname", "service_filter", "container_or_pod",
        "timestamp_utc", "metric", "value", "unit", "derived_pct",
    ])

# -----------------------------------------------
# Environment loader
# -----------------------------------------------

async def load_environment_json(env_name: str, ctx: Context) -> Dict[str, Any]:
    """
    Loads the complete environment configuration for a given environment from environments.json and stores it in the context.
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
    ctx.set_state("env_config", json.dumps(env_config))  # Store as JSON string
    ctx.set_state("env_name", env_name)

    # Extract key info for the log message
    env_tag = env_config.get("env_tag", "unknown")
    host_count = len(env_config.get("hosts", []))
    k8s_services = len(env_config.get("kubernetes", {}).get("services", []))
    await ctx.info(f"Environment '{env_name}' loaded with env_tag: {env_tag}, {host_count} hosts, {k8s_services} k8s services")

    return env_config

# -----------------------------------------------
# Hosts (v1) — per-host CSV + aggregates
# -----------------------------------------------
async def collect_host_metrics(env_name: str, start_time: str, end_time: str, run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Collect CPU & Memory metrics for each host and write one CSV per host.

    Args:
        env_name: Environment name to load (e.g., 'QA', 'UAT')
        start_time: Start timestamp (epoch or ISO8601)
        end_time: End timestamp (epoch or ISO8601)  
        run_id: Optional test run identifier for artifacts
        ctx: FastMCP context for logging

    Returns:
        dict: {
          "files": ["<path-to-host_metrics_[hostname].csv>", ...],
          "summary": {
            "env_name": str, "env_tag": str,
            "entities": int, "metrics": ["cpu","mem"],
            "date_range": {"start": str, "end": str, "tz": str},
            "aggregates": [{"hostname": str, "avg_cpu_util": float, "avg_mem_pct": float}],
            "warnings": [str, ...]
          }
        }
    """
    _ensure_ready(ctx)

    # Load environment config internally.
    env_config = await load_environment_json(env_name, ctx)
    if not env_config:
        msg = "No infrastructure configuration available. Load environment JSON file first."
        await ctx.error(msg)
        return {"files": [], "summary": {"warnings": [msg]}}

    env_name = env_config.get("environment_name", "unknown")
    env_tag = env_config.get("env_tag", "unknown")
    hosts = env_config.get("hosts", [])
    if not hosts:
        msg = "No hosts configured in environment."
        await ctx.error(msg)
        return {"files": [], "summary": {"warnings": [msg]}}

    run = str(run_id) if run_id else "mock_run_id"
    outdir = _ensure_artifacts_dir(run)

    v1_from_s, v1_to_s, v2_from_ms, v2_to_ms, tz_label = _parse_to_utc(start_time, end_time)

    files: List[str] = []
    aggregates: List[Dict[str, Any]] = []
    warnings: List[str] = []

    # Build queries (include cpu.system so we can compute total busy ≈ user+system)
    # Keeping scope to CPU+Memory only.
    q_tpl = (
        "avg:system.cpu.user{host:%(h)s}.rollup(avg,60),"
        "avg:system.cpu.system{host:%(h)s}.rollup(avg,60),"
        "avg:system.mem.used{host:%(h)s}.rollup(avg,60),"
        "avg:system.mem.total{host:%(h)s}.rollup(avg,60)"
    )

    headers = {"DD-API-KEY": DD_API_KEY, "DD-APPLICATION-KEY": DD_APP_KEY}

    async with httpx.AsyncClient() as client:
        for h in hosts:
            hostname = h.get("hostname")
            if not hostname:
                continue

            query = q_tpl % {"h": hostname}
            params = {"from": v1_from_s, "to": v1_to_s, "query": query}

            # Collect series values keyed by metric name
            series_map: Dict[str, List[Tuple[int, float]]] = {}
            try:
                resp = await client.get(V1_QUERY_URL, params=params, headers=headers, timeout=60.0)
                resp.raise_for_status()
                data = resp.json()
                for series in data.get("series", []):
                    metric = series.get("metric") or series.get("display_name")
                    pts = series.get("pointlist", [])
                    # each point is [ms, value]
                    series_map[metric] = [(int(ts), val if val is not None else float("nan")) for ts, val in pts]
            except Exception as e:
                warnings.append(f"Host '{hostname}': API error — {e}")
                await ctx.error(f"Host '{hostname}': API error — {e}")
                continue

            # If no datapoints at all, skip file
            if not any(series_map.values()):
                warnings.append(f"Host '{hostname}': no datapoints in the date range; skipping file")
                await ctx.info(warnings[-1])
                continue

            # Prepare per-host CSV
            outcsv = os.path.join(outdir, f"host_metrics_[{_sanitize_filename(hostname)}].csv")
            files.append(outcsv)
            with open(outcsv, "w", newline="", encoding="utf-8") as fcsv:
                w = csv.writer(fcsv)
                _write_csv_header(w)

                # Write rows for each metric series
                def write_series(metric_name: str, unit: str = ""):
                    for ts_ms, val in series_map.get(metric_name, []):
                        dt_iso = datetime.utcfromtimestamp(ts_ms / 1000).isoformat()
                        w.writerow([env_name, env_tag, "host", hostname, "", "", dt_iso, metric_name, val, unit, ""])  # derived_pct empty here

                write_series("system.cpu.user", "%")
                write_series("system.cpu.system", "%")
                write_series("system.mem.used", "B")
                write_series("system.mem.total", "B")

                # Derived memory percent per timestamp (if both available)
                mem_used = dict(series_map.get("system.mem.used", []))
                mem_tot = dict(series_map.get("system.mem.total", []))
                mem_pct_vals: List[float] = []
                for ts_ms, used in mem_used.items():
                    tot = mem_tot.get(ts_ms)
                    if tot and tot > 0:
                        pct = (used / tot) * 100.0
                        mem_pct_vals.append(pct)
                        dt_iso = datetime.utcfromtimestamp(ts_ms / 1000).isoformat()
                        w.writerow([env_name, env_tag, "host", hostname, "", "", dt_iso, "mem_used_pct", pct, "%", pct])

            # Aggregates
            # CPU utilization ≈ avg(user + system) over overlapping timestamps
            cpu_user = dict(series_map.get("system.cpu.user", []))
            cpu_sys = dict(series_map.get("system.cpu.system", []))
            common_ts = sorted(set(cpu_user.keys()) & set(cpu_sys.keys()))
            cpu_util_vals = [(cpu_user[t] or 0) + (cpu_sys[t] or 0) for t in common_ts]
            avg_cpu_util = sum(cpu_util_vals) / len(cpu_util_vals) if cpu_util_vals else 0.0

            avg_mem_pct = 0.0
            # reuse mem_pct_vals collected above
            avg_mem_pct = sum(mem_pct_vals) / len(mem_pct_vals) if 'mem_pct_vals' in locals() and mem_pct_vals else 0.0

            aggregates.append({
                "hostname": hostname,
                "avg_cpu_util": round(avg_cpu_util, 4),
                "avg_mem_pct": round(avg_mem_pct, 4),
            })

            await ctx.info(f"Host CSV written: {outcsv}")

    summary = {
        "env_name": env_name,
        "env_tag": env_tag,
        "entities": len(hosts),
        "metrics": ["cpu", "mem"],
        "date_range": {"start": str(start_time), "end": str(end_time), "tz": tz_label},
        "aggregates": aggregates,
        "warnings": warnings,
    }

    return {"files": files, "summary": summary}

# -----------------------------------------------
# Kubernetes (v2) — per-service CSV (merged CPU+Mem) + aggregates
# -----------------------------------------------
async def collect_kubernetes_metrics(env_name: str, start_time: str, end_time: str, run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Collect CPU & Memory metrics for each configured k8s service and write one CSV per service.
    CPU and Memory are queried separately (to avoid ambiguous multi-metric responses) and merged by timestamp & container.

    Args:
        env_name: Environment name to load (e.g., 'QA', 'UAT')
        start_time: Start timestamp (epoch or ISO8601)
        end_time: End timestamp (epoch or ISO8601)  
        run_id: Optional test run identifier for artifacts
        ctx: FastMCP context for logging

    Returns:
        dict: {
          "files": ["<path-to-k8s_metrics_[service].csv>", ...],
          "summary": {
            "env_name": str, "env_tag": str,
            "entities": int, "metrics": ["cpu","mem"],
            "date_range": {"start": str, "end": str, "tz": str},
            "aggregates": [{"service_filter": str, "avg_cpu": float, "avg_mem": float}],
            "warnings": [str, ...]
          }
        }
    """
    _ensure_ready(ctx)

    # Load environment config internally.
    env_config = await load_environment_json(env_name, ctx)
    if not env_config:
        msg = "No infrastructure configuration available. Load environment JSON file first."
        await ctx.error(msg)
        return {"files": [], "summary": {"warnings": [msg]}}

    env_name = env_config.get("environment_name", "unknown")
    env_tag = env_config.get("env_tag", "unknown")
    services = env_config.get("kubernetes", {}).get("services", [])
    if not services:
        msg = "No Kubernetes services configured in environment."
        await ctx.error(msg)
        return {"files": [], "summary": {"warnings": [msg]}}

    run = str(run_id) if run_id else "mock_run_id"
    outdir = _ensure_artifacts_dir(run)

    v1_from_s, v1_to_s, v2_from_ms, v2_to_ms, tz_label = _parse_to_utc(start_time, end_time)

    files: List[str] = []
    aggregates: List[Dict[str, Any]] = []
    warnings: List[str] = []

    headers = {
        "DD-API-KEY": DD_API_KEY,
        "DD-APPLICATION-KEY": DD_APP_KEY,
        "Content-Type": "application/json",
    }

    # Metric queries (by container)
    def cpu_query(env_tag: str, svc_filter: str) -> str:
        return f"avg:kubernetes.cpu.usage.total{{env:{env_tag},service:{svc_filter}}} by {{kube_container_name}}"

    def mem_query(env_tag: str, svc_filter: str) -> str:
        # Choose a common memory usage metric; adjust if your Datadog tenant uses a different one
        return f"avg:kubernetes.memory.usage{{env:{env_tag},service:{svc_filter}}} by {{kube_container_name}}"

    async with httpx.AsyncClient() as client:
        for svc in services:
            s_filter = svc.get("service_filter")
            if not s_filter:
                continue

            # 1) CPU request
            body_cpu = {
                "data": {
                    "type": "timeseries_request",
                    "interval": 15000,
                    "attributes": {
                        "from": v2_from_ms,
                        "to": v2_to_ms,
                        "queries": [{
                            "data_source": "metrics",
                            "name": "a",
                            "query": cpu_query(env_tag, s_filter)
                        }],
                        "formulas": [{"formula": "a"}]
                    }
                }
            }

            cpu_series: Dict[str, List[Tuple[int, float]]] = {}
            try:
                r_cpu = await client.post(V2_TIMESERIES_URL, headers=headers, json=body_cpu, timeout=60.0)
                r_cpu.raise_for_status()
                j = r_cpu.json()
                ##attrs = (j.get("data") or [{}])[0].get("attributes", {})
                attrs = j.get("data", {}).get("attributes", {})
                times = attrs.get("times", [])  # ms timestamps
                series_list = attrs.get("series", [])
                for idx, s in enumerate(series_list):
                    # group_tags like ["kube_container_name:xyz"]
                    gtags = s.get("group_tags", [])
                    cname = next((t.split(":",1)[1] for t in gtags if t.startswith("kube_container_name:")), "")
                    # values provided in a separate top-level "values" array aligned with times
                values = attrs.get("values", [])
                # The v2 payload places all series’ values in a single matrix parallel to `series`
                # values[series_index][time_index]
                for s_idx, s in enumerate(series_list):
                    gtags = s.get("group_tags", [])
                    cname = next((t.split(":",1)[1] for t in gtags if t.startswith("kube_container_name:")), "")
                    if not cname:
                        cname = f"series_{s_idx}"
                    cpu_series[cname] = [(int(times[t_idx]), float(values[s_idx][t_idx])) for t_idx in range(len(times)) if values[s_idx][t_idx] is not None]
            except Exception as e:
                warnings.append(f"Service '{s_filter}': CPU query error — {e}; Request body: {body_cpu}; Response: {json.dumps(j, indent=2) if 'j' in locals() else 'N/A'}")
                await ctx.error(warnings[-1])
                continue

            # 2) Memory request
            body_mem = {
                "data": {
                    "type": "timeseries_request",
                    "interval": 15000,
                    "attributes": {
                        "from": v2_from_ms,
                        "to": v2_to_ms,
                        "queries": [{
                            "data_source": "metrics",
                            "name": "a",
                            "query": mem_query(env_tag, s_filter)
                        }],
                        "formulas": [{"formula": "a"}]
                    }
                }
            }

            mem_series: Dict[str, List[Tuple[int, float]]] = {}
            try:
                r_mem = await client.post(V2_TIMESERIES_URL, headers=headers, json=body_mem, timeout=60.0)
                r_mem.raise_for_status()
                j = r_mem.json()
                ##attrs = (j.get("data") or [{}])[0].get("attributes", {})
                attrs = j.get("data", {}).get("attributes", {})
                times = attrs.get("times", [])
                series_list = attrs.get("series", [])
                values = attrs.get("values", [])
                for s_idx, s in enumerate(series_list):
                    gtags = s.get("group_tags", [])
                    cname = next((t.split(":",1)[1] for t in gtags if t.startswith("kube_container_name:")), "")
                    if not cname:
                        cname = f"series_{s_idx}"
                    mem_series[cname] = [(int(times[t_idx]), float(values[s_idx][t_idx])) for t_idx in range(len(times)) if values[s_idx][t_idx] is not None]
            except Exception as e:
                warnings.append(f"Service '{s_filter}': Memory query error — {e}; Request body: {body_mem}; Response: {json.dumps(j, indent=2) if 'j' in locals() else 'N/A'}")
                await ctx.error(warnings[-1])
                continue

            # If both CPU and Memory are empty, skip file
            if not any(cpu_series.values()) and not any(mem_series.values()):
                warnings.append(f"Service '{s_filter}': no datapoints in the date range; skipping file")
                await ctx.info(warnings[-1])
                continue

            # Prepare per-service CSV
            fname = f"k8s_metrics_[{_sanitize_filename(s_filter)}].csv"
            outcsv = os.path.join(outdir, fname)
            files.append(outcsv)

            # Merge by container + timestamp
            with open(outcsv, "w", newline="", encoding="utf-8") as fcsv:
                w = csv.writer(fcsv)
                _write_csv_header(w)

                def write_series(scope_metric: str, unit: str, per_container: Dict[str, List[Tuple[int, float]]]):
                    for cname, pts in per_container.items():
                        for ts_ms, val in pts:
                            dt_iso = datetime.utcfromtimestamp(ts_ms / 1000).isoformat()
                            w.writerow([env_name, env_tag, "k8s", "", s_filter, cname, dt_iso, scope_metric, val, unit, ""])  # derived_pct empty for k8s

                write_series("kubernetes.cpu.usage.total", "nanocores", cpu_series)
                write_series("kubernetes.memory.usage", "bytes", mem_series)

            # Aggregates (service-level): simple mean across all container values within window
            def flat_vals(d: Dict[str, List[Tuple[int, float]]]) -> List[float]:
                arr: List[float] = []
                for _, pts in d.items():
                    arr.extend([v for _, v in pts])
                return arr

            cpu_vals = flat_vals(cpu_series)
            mem_vals = flat_vals(mem_series)
            avg_cpu = (sum(cpu_vals) / len(cpu_vals)) if cpu_vals else 0.0
            avg_mem = (sum(mem_vals) / len(mem_vals)) if mem_vals else 0.0

            aggregates.append({
                "service_filter": s_filter,
                "avg_cpu": round(avg_cpu, 4),
                "avg_mem": round(avg_mem, 4),
            })

            await ctx.info(f"K8s CSV written: {outcsv}")

    summary = {
        "env_name": env_name,
        "env_tag": env_tag,
        "entities": len(services),
        "metrics": ["cpu", "mem"],
        "date_range": {"start": str(start_time), "end": str(end_time), "tz": tz_label},
        "aggregates": aggregates,
        "warnings": warnings,
    }

    return {"files": files, "summary": summary}
