"""
Chart Builder Service - Prepares data and creates Altair charts.

Transforms raw artifact data (JTL CSVs, analysis JSON, Datadog CSVs)
into the format expected by the chart component factories.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional

from src.ui.components.charts import (
    create_dual_axis_time_series,
    create_single_axis_time_series,
    create_multi_line_time_series,
    create_horizontal_bar,
    create_donut_chart,
    create_severity_bar,
)


# ---------------------------------------------------------------------------
# JTL helpers
# ---------------------------------------------------------------------------

def _calculate_bucket_seconds(jtl_df: pd.DataFrame) -> int:
    """Dynamically choose bucket size based on test duration."""
    if jtl_df is None or jtl_df.empty or "timeStamp" not in jtl_df.columns:
        return 30

    duration_ms = jtl_df["timeStamp"].max() - jtl_df["timeStamp"].min()
    duration_min = duration_ms / 60000

    if duration_min <= 5:
        return 5
    elif duration_min <= 15:
        return 10
    elif duration_min <= 30:
        return 30
    elif duration_min <= 60:
        return 60
    else:
        return 120


# ---------------------------------------------------------------------------
# Performance Tab Charts
# ---------------------------------------------------------------------------

def build_response_time_chart(jtl_df: pd.DataFrame):
    """
    Dual-axis chart: P90 Response Time vs Virtual Users over time.
    """
    if jtl_df is None or jtl_df.empty:
        return None
    required_cols = {"timeStamp", "elapsed", "allThreads"}
    if not required_cols.issubset(jtl_df.columns):
        return None

    bucket_sec = _calculate_bucket_seconds(jtl_df)
    df = jtl_df.copy()
    df["timestamp"] = pd.to_datetime(df["timeStamp"], unit="ms")
    df["bucket"] = df["timestamp"].dt.floor(f"{bucket_sec}s")

    agg = df.groupby("bucket").agg(
        p90_response_time=("elapsed", lambda x: np.percentile(x, 90)),
        max_vusers=("allThreads", "max"),
    ).reset_index()

    return create_dual_axis_time_series(
        df=agg, x_col="bucket",
        y1_col="p90_response_time", y2_col="max_vusers",
        y1_title="P90 Response Time (ms)", y2_title="Virtual Users",
        title="Response Time (P90) vs Virtual Users",
    )


def build_throughput_chart(jtl_df: pd.DataFrame):
    """Single-axis chart: Throughput (req/s) over time."""
    if jtl_df is None or jtl_df.empty or "timeStamp" not in jtl_df.columns:
        return None

    bucket_sec = _calculate_bucket_seconds(jtl_df)
    df = jtl_df.copy()
    df["timestamp"] = pd.to_datetime(df["timeStamp"], unit="ms")
    df["bucket"] = df["timestamp"].dt.floor(f"{bucket_sec}s")

    agg = df.groupby("bucket").agg(request_count=("timeStamp", "count")).reset_index()
    agg["throughput_rps"] = agg["request_count"] / bucket_sec

    return create_single_axis_time_series(
        df=agg, x_col="bucket", y_col="throughput_rps",
        y_title="Requests/sec", color="#2ecc40",
        title="Throughput Over Time",
    )


def build_error_rate_chart(jtl_df: pd.DataFrame):
    """Single-axis chart: Error rate (%) over time."""
    if jtl_df is None or jtl_df.empty:
        return None
    required_cols = {"timeStamp", "success"}
    if not required_cols.issubset(jtl_df.columns):
        return None

    bucket_sec = _calculate_bucket_seconds(jtl_df)
    df = jtl_df.copy()
    df["timestamp"] = pd.to_datetime(df["timeStamp"], unit="ms")
    df["bucket"] = df["timestamp"].dt.floor(f"{bucket_sec}s")

    # Handle 'success' column (could be boolean or string)
    if df["success"].dtype == object:
        df["is_error"] = df["success"].str.lower() != "true"
    else:
        df["is_error"] = ~df["success"].astype(bool)

    agg = df.groupby("bucket").agg(
        total=("timeStamp", "count"),
        errors=("is_error", "sum"),
    ).reset_index()
    agg["error_rate_pct"] = (agg["errors"] / agg["total"]) * 100

    return create_single_axis_time_series(
        df=agg, x_col="bucket", y_col="error_rate_pct",
        y_title="Error Rate (%)", color="#ff4136",
        title="Error Rate Over Time",
    )


def build_top_slowest_apis_chart(perf_analysis: dict, top_n: int = 15):
    """Horizontal bar chart of the slowest APIs by P90."""
    api_analysis = perf_analysis.get("api_analysis", {})
    if not api_analysis:
        return None

    rows = [
        {"api": name, "p90_response_time": stats.get("p90_response_time", 0)}
        for name, stats in api_analysis.items()
    ]
    df = pd.DataFrame(rows).nlargest(top_n, "p90_response_time")

    return create_horizontal_bar(
        df=df, x_col="p90_response_time", y_col="api",
        x_title="P90 Response Time (ms)", color="#ff851b",
        title=f"Top {min(top_n, len(df))} Slowest APIs (P90)",
    )


def build_pass_fail_donut(perf_analysis: dict):
    """Donut chart from SLA compliance data."""
    sla = perf_analysis.get("sla_analysis", {})
    if not sla:
        # Derive from api_analysis if sla_analysis not present
        api_analysis = perf_analysis.get("api_analysis", {})
        if api_analysis:
            compliant = sum(1 for s in api_analysis.values() if s.get("sla_compliant", True))
            violating = len(api_analysis) - compliant
        else:
            return None
    else:
        compliant = sla.get("compliant_apis", 0)
        violating = sla.get("violating_apis", 0)

    if compliant + violating == 0:
        return None

    df = pd.DataFrame({"Result": ["Pass", "Fail"], "Count": [compliant, violating]})
    return create_donut_chart(
        df=df, theta_col="Count", color_col="Result",
        color_scale=["#2ecc40", "#ff4136"], title="SLA Compliance",
    )


# ---------------------------------------------------------------------------
# Infrastructure Tab Charts
# ---------------------------------------------------------------------------

def build_infra_cpu_chart(datadog_dir: Path):
    """Multi-line chart: CPU utilization over time per service/host."""
    csv_files = _find_metric_csvs(datadog_dir)
    if not csv_files:
        return None

    frames = []
    for f in csv_files:
        df = pd.read_csv(f)
        cpu_df = df[df["metric"].str.contains("cpu", case=False)].copy()
        if cpu_df.empty:
            continue
        cpu_df["timestamp"] = pd.to_datetime(cpu_df["timestamp_utc"])
        service = cpu_df["container_or_pod"].iloc[0] if "container_or_pod" in cpu_df.columns else f.stem
        cpu_df["service"] = service
        frames.append(cpu_df[["timestamp", "value", "service"]])

    if not frames:
        return None

    combined = pd.concat(frames, ignore_index=True)
    return create_multi_line_time_series(
        df=combined, x_col="timestamp", y_col="value", color_col="service",
        y_title="CPU Usage", title="CPU Utilization Over Time",
    )


def build_infra_memory_chart(datadog_dir: Path):
    """Multi-line chart: Memory utilization over time per service/host."""
    csv_files = _find_metric_csvs(datadog_dir)
    if not csv_files:
        return None

    frames = []
    for f in csv_files:
        df = pd.read_csv(f)
        mem_df = df[df["metric"].str.contains("memory", case=False)].copy()
        if mem_df.empty:
            continue
        mem_df["timestamp"] = pd.to_datetime(mem_df["timestamp_utc"])
        service = mem_df["container_or_pod"].iloc[0] if "container_or_pod" in mem_df.columns else f.stem
        mem_df["service"] = service
        frames.append(mem_df[["timestamp", "value", "service"]])

    if not frames:
        return None

    combined = pd.concat(frames, ignore_index=True)
    return create_multi_line_time_series(
        df=combined, x_col="timestamp", y_col="value", color_col="service",
        y_title="Memory Usage", title="Memory Utilization Over Time",
    )


def _find_metric_csvs(datadog_dir: Path) -> list[Path]:
    """Find all metric CSV files in the Datadog directory."""
    if not datadog_dir.exists():
        return []
    return list(datadog_dir.glob("*.csv"))


# ---------------------------------------------------------------------------
# Bottleneck Tab Charts
# ---------------------------------------------------------------------------

def build_bottleneck_severity_chart(bottleneck_data: dict):
    """Vertical bar chart: Bottleneck findings by severity."""
    summary = bottleneck_data.get("summary", {})
    by_severity = summary.get("bottlenecks_by_severity", {})
    if not by_severity:
        return None

    rows = [{"severity": sev, "count": cnt} for sev, cnt in by_severity.items() if cnt > 0]
    if not rows:
        return None

    return create_severity_bar(pd.DataFrame(rows), title="Bottleneck Findings by Severity")


def build_bottleneck_type_chart(bottleneck_data: dict):
    """Horizontal bar chart: Bottleneck findings by type."""
    summary = bottleneck_data.get("summary", {})
    by_type = summary.get("bottlenecks_by_type", {})
    if not by_type:
        return None

    rows = [{"type": t.replace("_", " ").title(), "count": c} for t, c in by_type.items() if c > 0]
    if not rows:
        return None

    df = pd.DataFrame(rows)
    return create_horizontal_bar(
        df=df, x_col="count", y_col="type",
        x_title="Count", color="#5276A7",
        title="Bottleneck Findings by Type",
    )


# ---------------------------------------------------------------------------
# Log Analysis Tab Charts
# ---------------------------------------------------------------------------

def build_log_severity_chart(log_data: dict):
    """Vertical bar chart: Log issues by severity."""
    summary = log_data.get("summary", {})
    by_severity = summary.get("issues_by_severity", {})
    if not by_severity:
        return None

    rows = [{"severity": sev, "count": cnt} for sev, cnt in by_severity.items() if cnt > 0]
    if not rows:
        return None

    return create_severity_bar(pd.DataFrame(rows), title="Log Issues by Severity")


def build_log_category_chart(log_data: dict):
    """Horizontal bar chart: Log issues by error category."""
    summary = log_data.get("summary", {})
    by_category = summary.get("issues_by_category", {})
    if not by_category:
        return None

    rows = [{"category": cat, "count": cnt} for cat, cnt in by_category.items() if cnt > 0]
    if not rows:
        return None

    df = pd.DataFrame(rows).nlargest(15, "count")
    return create_horizontal_bar(
        df=df, x_col="count", y_col="category",
        x_title="Occurrences", color="#ff4136",
        title="Error Categories",
    )
