# services/datadog_api.py
import os
import re
import json
import httpx
import csv
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional, Union
from dotenv import load_dotenv
from fastmcp import FastMCP, Context    # ✅ FastMCP 2.x import
from utils.config import load_config
from utils.datadog_config_loader import load_environment_json

# -----------------------------------------------
# Bootstrap
# -----------------------------------------------
load_dotenv()   # Load environment variables from .env file such as API keys and secrets
config = load_config()
dd_config = config.get('datadog', {})
artifacts_base = config["artifacts"]["artifacts_path"]
environments_json_path = config["datadog"]["environments_json_path"]
configured_tz = config.get("datadog", {}).get("time_zone", "UTC")

DD_API_KEY = os.getenv("DD_API_KEY")
DD_APP_KEY = os.getenv("DD_APP_KEY")
DD_API_BASE_URL = os.getenv("DD_API_BASE_URL", "https://api.datadoghq.com")
V1_QUERY_URL = f"{DD_API_BASE_URL}/api/v1/query"
V2_TIMESERIES_URL = f"{DD_API_BASE_URL}/api/v2/query/timeseries"

# CA bundle path for SSL verification
CA_BUNDLE = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")

# -----------------------------------------------
# Helpers
# -----------------------------------------------

def _parse_resource_limit(resource_str: str) -> float:
    """
    Parse resource limit strings like "4.05 core", "16 GiB", "50 millicores" into numeric values.
    
    Args:
        resource_str: Resource string from environments.json
    
    Returns:
        float: Numeric value in base units (cores for CPU, bytes for memory)
    """
    if not resource_str:
        return 0.0
    
    resource_str = resource_str.strip().lower()
    
    # CPU parsing
    if 'core' in resource_str:
        value = float(re.findall(r'[\d.]+', resource_str)[0])
        if 'millicore' in resource_str:
            return value / 1000.0  # Convert millicores to cores
        return value  # cores
    
    # Memory parsing
    elif 'gib' in resource_str:
        value = float(re.findall(r'[\d.]+', resource_str)[0])
        return value * 1024**3  # Convert GiB to bytes
    elif 'gb' in resource_str:
        value = float(re.findall(r'[\d.]+', resource_str)[0])
        return value * 1000**3  # Convert GB to bytes
    elif 'mib' in resource_str:
        value = float(re.findall(r'[\d.]+', resource_str)[0])
        return value * 1024**2  # Convert MiB to bytes
    elif 'mb' in resource_str:
        value = float(re.findall(r'[\d.]+', resource_str)[0])
        return value * 1000**2  # Convert MB to bytes
    
    return 0.0

def _calculate_cpu_percentage(usage_nanocores: float, limit_cores: float) -> float:
    """Calculate CPU utilization percentage."""
    if limit_cores <= 0:
        return 0.0
    # Convert nanocores to cores: 1 core = 1,000,000,000 nanocores
    usage_cores = usage_nanocores / 1_000_000_000.0
    return (usage_cores / limit_cores) * 100.0

def _calculate_memory_percentage(usage_bytes: float, limit_bytes: float) -> float:
    """Calculate memory utilization percentage."""
    if limit_bytes <= 0:
        return 0.0
    return (usage_bytes / limit_bytes) * 100.0

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
    """Parse input times (epoch or ISO) and convert to epoch timestamps.
    
    Accepts multiple input formats (all assumed to be in UTC):
    - Epoch timestamp (e.g., "1761933994")
    - ISO 8601 format (e.g., "2025-10-31T14:06:34Z" or "2025-10-31 14:06:34")
    - Datetime string format (e.g., "2025-10-31 14:06:34")
    
    Note: All input timestamps are treated as UTC. No timezone conversion is performed.
    The function only formats/parses the timestamp, it does not convert between timezones.

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
        # ISO-like formats; treat as UTC (no conversion)
        # We only rely on naive parsing here to stay dependency-free
        # Handle ISO 8601 format with Z suffix (e.g., "2025-10-31T14:06:34Z")
        # Note: All inputs are guaranteed to be UTC, so no timezone offset handling needed
        val_norm = val.replace("T", " ").strip()
        # Strip Z suffix if present (all inputs are UTC)
        val_norm = val_norm.rstrip("Z")
        # Try common formats
        fmts = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]
        for fmt in fmts:
            try:
                dt_naive = datetime.strptime(val_norm, fmt)
                # Mark as UTC without conversion - input is assumed to already be UTC
                return dt_naive.replace(tzinfo=timezone.utc)
            except Exception:
                continue
        raise ValueError(f"Unrecognized time format: {val}")

    # Parse both times (already UTC, no conversion needed)
    start_dt_utc = parse_one(start_time)
    end_dt_utc = parse_one(end_time)
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
        "env_name", "env_tag", "scope", "hostname", "filter", "container_or_pod",
        "timestamp_utc", "metric", "value", "unit"
    ])

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
        run_id: Test run identifier for artifacts
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

    verify_ssl = get_ssl_verify_setting()
    async with httpx.AsyncClient(verify=verify_ssl) as client:
        for h in hosts:
            hostname = h.get("hostname")
            if not hostname:
                continue

            # Parse CPU limit for percentage calculation
            cpu_limit_cores = _parse_resource_limit(h.get("cpus", ""))

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
                warnings.append(f"Host '{hostname}': API error — {e}; Request params: {params}; Response: {json.dumps(data, indent=2) if 'data' in locals() else 'N/A'}")
                await ctx.error(f"Host '{hostname}': API error — {e}; Request params: {params}; Response: {json.dumps(data, indent=2) if 'data' in locals() else 'N/A'}")
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
                        w.writerow([env_name, env_tag, "host", hostname, "", "", dt_iso, metric_name, val, unit])

                write_series("system.cpu.user", "%")
                write_series("system.cpu.system", "%")
                write_series("system.mem.used", "bytes")
                write_series("system.mem.total", "bytes")

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
                        w.writerow([env_name, env_tag, "host", hostname, "", "", dt_iso, "mem_util_pct", pct, "%"])

                # Derived CPU percent per timestamp (if CPU limit is configured)
                if cpu_limit_cores > 0:
                    cpu_user = dict(series_map.get("system.cpu.user", []))
                    cpu_sys = dict(series_map.get("system.cpu.system", []))
                    common_ts = sorted(set(cpu_user.keys()) & set(cpu_sys.keys()))
                    
                    for ts_ms in common_ts:
                        cpu_total = (cpu_user.get(ts_ms, 0) or 0) + (cpu_sys.get(ts_ms, 0) or 0)
                        cpu_pct = (cpu_total / cpu_limit_cores) * 100.0
                        dt_iso = datetime.utcfromtimestamp(ts_ms / 1000).isoformat()
                        w.writerow([env_name, env_tag, "host", hostname, "", "", dt_iso, "cpu_util_pct", cpu_pct, "%"])

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
    Collect CPU & Memory metrics for each configured k8s service and/or pod and write one CSV per service/pod.
    - Services are read from environment["kubernetes"]["services"].
    - Pods are read from environment["kubernetes"]["pods"].
    - At least one of them must be defined (services or pods).
    - One CSV is produced per service / pod, all using the same schema.

    Args:
        env_name: Environment name to load (e.g., 'QA', 'UAT')
        start_time: Start timestamp (epoch or ISO8601)
        end_time: End timestamp (epoch or ISO8601)  
        run_id: Test run identifier for artifacts
        ctx: FastMCP context for logging

    Returns:
        dict: {
          "files": ["<path-to-k8s_metrics_[service].csv>", ...],
          "summary": {
            "env_name": str, "env_tag": str,
            "entities": int, "metrics": ["cpu","mem"],
            "date_range": {"start": str, "end": str, "tz": str},
            "aggregates": [{"filter": str, "avg_cpu": float, "avg_mem": float}],
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

    env_tag = env_config.get("env_tag", "unknown")

    kube_namespace = env_config.get("kube_namespace")

    k8s_cfg = env_config.get("kubernetes", {}) or {}
    services: List[Dict[str, Any]] = k8s_cfg.get("services", []) or []
    pods: List[Dict[str, Any]] = k8s_cfg.get("pods", []) or []

    if not services and not pods:
        msg = "No Kubernetes pods or services configured in environment. At least one must be defined."
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

    verify_ssl = get_ssl_verify_setting()

    async with httpx.AsyncClient(verify=verify_ssl) as client:
        # -------------------------------------------------------------
        # 1) Services
        # -------------------------------------------------------------
        for svc in services:
            s_filter = svc.get("service_filter")
            if not s_filter:
                continue

            # Parse CPU and Memory limits for percentage calculation
            cpu_limit_cores = _parse_resource_limit(svc.get("cpus", ""))
            memory_limit_bytes = _parse_resource_limit(svc.get("memory", ""))

            # 1a) CPU request
            body_cpu = {
                "data": {
                    "type": "timeseries_request",
                    "interval": 20000,
                    "attributes": {
                        "from": v2_from_ms,
                        "to": v2_to_ms,
                        "queries": [{
                            "data_source": "metrics",
                            "name": "a",
                            "query": svc_cpu_query(env_tag, s_filter)
                        }],
                        "formulas": [{"formula": "a"}]
                    }
                }
            }

            cpu_series: Dict[str, List[Tuple[int, float]]] = {}
            try:
                r_cpu = await client.post(V2_TIMESERIES_URL, headers=headers, json=body_cpu, timeout=60.0)
                r_cpu.raise_for_status()
                attrs = r_cpu.json().get("data", {}).get("attributes", {})
                cpu_series = _extract_series(attrs, ["kube_container_name"])
            except Exception as e:
                warnings.append(f"Service '{s_filter}': CPU query error — {e}; Request body: {body_cpu}; Response: {json.dumps(attrs, indent=2) if 'attrs' in locals() else 'N/A'}")
                await ctx.error(warnings[-1])
                continue

            # 1b) Memory request
            body_mem = {
                "data": {
                    "type": "timeseries_request",
                    "interval": 20000,
                    "attributes": {
                        "from": v2_from_ms,
                        "to": v2_to_ms,
                        "queries": [{
                            "data_source": "metrics",
                            "name": "a",
                            "query": svc_mem_query(env_tag, s_filter)
                        }],
                        "formulas": [{"formula": "a"}]
                    }
                }
            }

            mem_series: Dict[str, List[Tuple[int, float]]] = {}
            try:
                r_mem = await client.post(V2_TIMESERIES_URL, headers=headers, json=body_mem, timeout=60.0)
                r_mem.raise_for_status()
                attrs = r_mem.json().get("data", {}).get("attributes", {})
                mem_series = _extract_series(attrs, ["kube_container_name"])
            except Exception as e:
                warnings.append(f"Service '{s_filter}': Memory query error — {e}; Request body: {body_mem}; Response: {json.dumps(attrs, indent=2) if 'attrs' in locals() else 'N/A'}")
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

                def write_series(
                    metric_name: str,
                    unit: str,
                    per_container: Dict[str, List[Tuple[int, float]]],
                ):
                    for cname, pts in per_container.items():
                        for ts_ms, val in pts:
                            dt_iso = datetime.utcfromtimestamp(ts_ms / 1000).isoformat()
                            # scope = "k8s", hostname = "", service_filter = s_filter
                            w.writerow([env_name, env_tag, "k8s", "", s_filter, cname, dt_iso, metric_name, val, unit])

                # Raw CPU/Memory metrics
                write_series("kubernetes.cpu.usage.total", "nanocores", cpu_series)
                write_series("kubernetes.memory.usage", "bytes", mem_series)

                # CPU percentage based on CPU limits
                if cpu_limit_cores > 0:
                    for cname, pts in cpu_series.items():
                        for ts_ms, val in pts:
                            cpu_pct = _calculate_cpu_percentage(val, cpu_limit_cores)
                            dt_iso = datetime.utcfromtimestamp(ts_ms / 1000).isoformat()
                            w.writerow([env_name, env_tag, "k8s", "", s_filter, cname, dt_iso, "cpu_util_pct", cpu_pct, "%"])

                # Memory percentage based on Memory limits
                if memory_limit_bytes > 0:
                    for cname, pts in mem_series.items():
                        for ts_ms, val in pts:
                            mem_pct = _calculate_memory_percentage(val, memory_limit_bytes)
                            dt_iso = datetime.utcfromtimestamp(ts_ms / 1000).isoformat()
                            w.writerow([env_name, env_tag, "k8s", "", s_filter, cname, dt_iso, "mem_util_pct", mem_pct, "%"])

            # Aggregates (per service)
            def flat_vals(series: Dict[str, List[Tuple[int, float]]]) -> List[float]:
                return [v for pts in series.values() for (_, v) in pts]

            cpu_vals = flat_vals(cpu_series)
            mem_vals = flat_vals(mem_series)
            avg_cpu = (sum(cpu_vals) / len(cpu_vals)) if cpu_vals else 0.0
            avg_mem = (sum(mem_vals) / len(mem_vals)) if mem_vals else 0.0

            aggregates.append(
                {
                    "filter": s_filter,
                    "entity_type": "service",
                    "avg_cpu": round(avg_cpu, 4),
                    "avg_mem": round(avg_mem, 4),
                }
            )

            await ctx.info(f"K8s CSV written: {outcsv}")

        # -------------------------------------------------------------
        # 2) Pods
        # -------------------------------------------------------------
        for pod in pods:
            pod_filter = pod.get("pod_filter")
            if not pod_filter:
                continue

            # Parse CPU and Memory limits at the pod definition level
            cpu_limit_cores = _parse_resource_limit(pod.get("cpus", ""))
            memory_limit_bytes = _parse_resource_limit(pod.get("memory", ""))

            # 2a) CPU request
            body_cpu = {
                "data": {
                    "type": "timeseries_request",
                    "interval": 20000,
                    "attributes": {
                        "from": v2_from_ms,
                        "to": v2_to_ms,
                        "queries": [{
                            "data_source": "metrics",
                            "name": "a",
                            "query": pod_cpu_query(kube_namespace, pod_filter),
                        }],
                        "formulas": [{"formula": "a"}],
                    },
                }
            }

            pod_cpu_series: Dict[str, List[Tuple[int, float]]] = {}
            try:
                r_cpu = await client.post(
                    V2_TIMESERIES_URL,
                    headers=headers,
                    json=body_cpu,
                    timeout=60.0,
                )
                r_cpu.raise_for_status()
                attrs = r_cpu.json().get("data", {}).get("attributes", {})
                # Prefer pod name, fallback to container name
                pod_cpu_series = _extract_series(attrs, ["kube_pod_name", "kube_container_name", "kube_namespace"])
            except Exception as e:
                warnings.append(
                    f"Pod '{pod_filter}': CPU query failed with error: {e}"
                )
                await ctx.error(warnings[-1])
                continue

            # 2b) Memory request
            body_mem = {
                "data": {
                    "type": "timeseries_request",
                    "interval": 20000,
                    "attributes": {
                        "from": v2_from_ms,
                        "to": v2_to_ms,
                        "queries": [{
                            "data_source": "metrics",
                            "name": "a",
                            "query": pod_mem_query(kube_namespace, pod_filter),
                        }],
                            "formulas": [{"formula": "a"}],
                    },
                }
            }

            pod_mem_series: Dict[str, List[Tuple[int, float]]] = {}
            try:
                r_mem = await client.post(
                    V2_TIMESERIES_URL,
                    headers=headers,
                    json=body_mem,
                    timeout=60.0,
                )
                r_mem.raise_for_status()
                attrs = r_mem.json().get("data", {}).get("attributes", {})
                pod_mem_series = _extract_series(attrs, ["kube_pod_name", "kube_container_name", "kube_namespace"])
            except Exception as e:
                warnings.append(
                    f"Pod '{pod_filter}': Memory query failed with error: {e}"
                )
                await ctx.error(warnings[-1])
                continue

            # If both CPU and Memory are empty, skip file
            if not any(pod_cpu_series.values()) and not any(pod_mem_series.values()):
                warnings.append(
                    f"Pod '{pod_filter}': no datapoints in the date range; skipping file"
                )
                await ctx.info(warnings[-1])
                continue

            # Prepare per-pod CSV
            fname = f"k8s_metrics_[{_sanitize_filename(pod_filter)}].csv"
            outcsv = os.path.join(outdir, fname)
            files.append(outcsv)

            with open(outcsv, "w", newline="", encoding="utf-8") as fcsv:
                w = csv.writer(fcsv)
                _write_csv_header(w)

                def write_pod_series(
                    metric_name: str,
                    unit: str,
                    per_pod: Dict[str, List[Tuple[int, float]]],
                ):
                    for pod_id, pts in per_pod.items():
                        for ts_ms, val in pts:
                            dt_iso = datetime.utcfromtimestamp(ts_ms / 1000).isoformat()
                            # "filter" column stores pod_filter here.
                            # "container_or_pod" column stores the pod identifier.
                            w.writerow([env_name, env_tag, "k8s", "", pod_filter, pod_id, dt_iso, metric_name, val, unit])

                write_pod_series(
                    "kubernetes.cpu.usage.total",
                    "nanocores",
                    pod_cpu_series,
                )
                write_pod_series(
                    "kubernetes.memory.usage",
                    "bytes",
                    pod_mem_series,
                )

                # Percentages based on pod-level limits
                if cpu_limit_cores > 0:
                    for pod_id, pts in pod_cpu_series.items():
                        for ts_ms, val in pts:
                            cpu_pct = _calculate_cpu_percentage(val, cpu_limit_cores)
                            dt_iso = datetime.utcfromtimestamp(ts_ms / 1000).isoformat()
                            w.writerow([env_name, env_tag, "k8s", "", pod_filter, pod_id, dt_iso, "cpu_util_pct", cpu_pct, "%"])

                if memory_limit_bytes > 0:
                    for pod_id, pts in pod_mem_series.items():
                        for ts_ms, val in pts:
                            mem_pct = _calculate_memory_percentage(
                                val, memory_limit_bytes
                            )
                            dt_iso = datetime.utcfromtimestamp(ts_ms / 1000).isoformat()
                            w.writerow([env_name, env_tag, "k8s", "", pod_filter, pod_id, dt_iso, "mem_util_pct", mem_pct, "%"])

            # Aggregates (per pod_filter)
            def flat_vals(series: Dict[str, List[Tuple[int, float]]]) -> List[float]:
                return [v for pts in series.values() for (_, v) in pts]

            cpu_vals = flat_vals(pod_cpu_series)
            mem_vals = flat_vals(pod_mem_series)
            avg_cpu = (sum(cpu_vals) / len(cpu_vals)) if cpu_vals else 0.0
            avg_mem = (sum(mem_vals) / len(mem_vals)) if mem_vals else 0.0

            aggregates.append(
                {
                    "filter": pod_filter,
                    "entity_type": "pod",
                    "avg_cpu": round(avg_cpu, 4),
                    "avg_mem": round(avg_mem, 4),
                }
            )

            await ctx.info(f"K8s pod CSV written: {outcsv}")

    # Final summary
    summary = {
        "env_name": env_name,
        "env_tag": env_tag,
        "entities": len(services) + len(pods),
        "metrics": ["cpu", "mem"],
        "date_range": {"start": str(start_time), "end": str(end_time), "tz": tz_label},
        "aggregates": aggregates,
        "warnings": warnings,
    }

    return {"files": files, "summary": summary}

# -----------------------------
# Query builder functions
# -----------------------------

def svc_cpu_query(tag: str, svc_filter: str) -> str:
    return (
        f"avg:kubernetes.cpu.usage.total{{env:{tag},service:{svc_filter}}}"
        " by {kube_container_name}"
    )

def svc_mem_query(tag: str, svc_filter: str) -> str:
    return (
        f"avg:kubernetes.memory.usage{{env:{tag},service:{svc_filter}}}"
        " by {kube_container_name}"
    )

def pod_cpu_query(ns: Optional[str], pod_filter: str) -> str:
    """
    Pod queries use pod_filter as kube_service and include kube_namespace.
    We group by kube_namespace so metrics are aggregated per namespace.
    """
    if ns:
        return (
            "avg:kubernetes.cpu.usage.total"
            f"{{kube_service:{pod_filter},kube_namespace:{ns}}} by {{kube_namespace}}"
        )
    # Fallback if namespace is not configured
    return (
        "avg:kubernetes.cpu.usage.total"
        f"{{kube_service:{pod_filter}}} by {{kube_namespace}}"
    )

def pod_mem_query(ns: Optional[str], pod_filter: str) -> str:
    """
    Pod queries use pod_filter as kube_service and include kube_namespace.
    We group by kube_namespace so metrics are aggregated per namespace.
    """
    if ns:
        return (
            "avg:kubernetes.memory.usage"
            f"{{kube_service:{pod_filter},kube_namespace:{ns}}} by {{kube_namespace}}"
        )
    return (
        "avg:kubernetes.memory.usage"
        f"{{kube_service:{pod_filter}}} by {{kube_namespace}}"
    )

# Small helper to normalize v2 timeseries into: { identifier -> [(ts_ms, value), ...] }
def _extract_series(attrs: Dict[str, Any], id_tag_keys: List[str]) -> Dict[str, List[Tuple[int, float]]]:
    times = attrs.get("times", []) or []
    series_list = attrs.get("series", []) or []
    values = attrs.get("values", []) or []

    per_id: Dict[str, List[Tuple[int, float]]] = {}
    for s_idx, series in enumerate(series_list):
        gtags = series.get("group_tags", []) or []

        identifier: str = ""
        # Try each tag key in order (e.g. kube_pod_name, kube_container_name)
        for tag_key in id_tag_keys:
            identifier = next(
                (t.split(":", 1)[1] for t in gtags if t.startswith(f"{tag_key}:")),
                identifier,
            )
            if identifier:
                break

        if not identifier:
            identifier = f"series_{s_idx}"

        row_vals = values[s_idx] if s_idx < len(values) else []
        pts: List[Tuple[int, float]] = []
        for t_idx, ts_ms in enumerate(times):
            if t_idx >= len(row_vals):
                break
            val = row_vals[t_idx]
            if val is None:
                continue
            try:
                pts.append((int(ts_ms), float(val)))
            except (TypeError, ValueError):
                continue

        if pts:
            per_id[identifier] = pts

    return per_id

# -----------------------------
# Helper functions
# -----------------------------

def get_ssl_verify_setting() -> Union[str, bool]:
    """
    Determines SSL verification setting based on config.yaml.
    
    Returns:
        Union[str, bool]: 
            - Path to CA bundle (str) if ssl_verification is "ca_bundle" and certs are available
            - False if ssl_verification is "disabled"
            - True as fallback (use system certs)
    """
    ssl_verification = dd_config.get('ssl_verification', 'ca_bundle').lower()
    
    if ssl_verification == 'disabled':
        return False
    elif ssl_verification == 'ca_bundle':
        # Use CA bundle if available, otherwise default to True
        return CA_BUNDLE or True
    else:
        # Default to system cert verification
        return True