import matplotlib.pyplot as plt
import pandas as pd
from fastmcp import Context
from utils.chart_utils import (
    get_chart_output_path,
    interpolate_placeholders
)
from utils.config import load_chart_colors

# Load chart colors for color name resolution
CHART_COLORS = load_chart_colors()

def resolve_color(color_name: str) -> str:
    """Resolve color name (e.g., 'primary') to actual color value (e.g., '#1f77b4')"""
    return CHART_COLORS.get(color_name, color_name)

# -----------------------------------------------
# Single Axis Chart Generators
# -----------------------------------------------
async def generate_cpu_utilization_chart(df, chart_spec, resource_name, run_id):
    """
    Generate and save a CPU Utilization line chart for a given resource.

    Args:
        df (pd.DataFrame): Full CSV data already loaded for this resource.
        chart_spec (dict): Chart configuration from YAML/schema.
        resource_name (str): Host or k8s service being charted.
        run_id (str): Test run identifier for output paths.

    Returns:
        dict: { "resource": ..., "path": ... }
    """
    # Filter for CPU metric and container_or_pod
    df_filtered = df[(df["metric"] == "cpu_util_pct") & (df["container_or_pod"] == resource_name)].copy()
    if df_filtered.empty:
        return {"resource": resource_name, "error": "No CPU utilization data for resource."}

    df_filtered["timestamp_utc"] = pd.to_datetime(df_filtered["timestamp_utc"])
    df_filtered = df_filtered.sort_values(by="timestamp_utc")

    raw_title = chart_spec.get("title", f"CPU Utilization - {resource_name}")
    title = interpolate_placeholders(raw_title, resource_name=resource_name)
    y_label = chart_spec.get("y_axis", {}).get("label", "CPU Util (%)")
    x_label = chart_spec.get("x_axis", {}).get("label", "Time (UTC)")
    color_names = chart_spec.get("colors", ["primary"])
    colors = [resolve_color(c) for c in color_names]

    fig, ax = plt.subplots()
    ax.plot(df_filtered["timestamp_utc"], df_filtered["value"], color=colors[0])
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    if chart_spec.get("show_grid"):
        ax.grid(True)
    if chart_spec.get("include_legend"):
        ax.legend([resource_name])

    chart_path = get_chart_output_path(run_id, f"cpu_metric_{resource_name}")
    fig.savefig(chart_path, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return {"resource": resource_name, "path": str(chart_path)}

async def generate_memory_utilization_chart(df, chart_spec, resource_name, run_id):
    """
    Generate and save a Memory Utilization line chart for a given resource.

    Args:
        df (pd.DataFrame): Full CSV data already loaded for this resource.
        chart_spec (dict): Chart configuration from YAML/schema.
        resource_name (str): Host or k8s service being charted.
        run_id (str): Test run identifier for output paths.

    Returns:
        dict: { "resource": ..., "path": ... }
    """
    # Filter for memory metric and container_or_pod
    df_filtered = df[(df["metric"] == "mem_util_pct") & (df["container_or_pod"] == resource_name)].copy()
    if df_filtered.empty:
        return {"resource": resource_name, "error": "No Memory utilization data for resource."}

    df_filtered["timestamp_utc"] = pd.to_datetime(df_filtered["timestamp_utc"])
    df_filtered = df_filtered.sort_values(by="timestamp_utc")

    raw_title = chart_spec.get("title", f"Memory Utilization - {resource_name}")
    title = interpolate_placeholders(raw_title, resource_name=resource_name)
    y_label = chart_spec.get("y_axis", {}).get("label", "Memory Util (%)")
    x_label = chart_spec.get("x_axis", {}).get("label", "Time (UTC)")
    color_names = chart_spec.get("colors", ["secondary"])
    colors = [resolve_color(c) for c in color_names]

    fig, ax = plt.subplots()
    ax.plot(df_filtered["timestamp_utc"], df_filtered["value"], color=colors[0])
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    if chart_spec.get("show_grid"):
        ax.grid(True)
    if chart_spec.get("include_legend"):
        ax.legend([resource_name])

    chart_path = get_chart_output_path(run_id, f"memory_metric_{resource_name}")
    fig.savefig(chart_path, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return {"resource": resource_name, "path": str(chart_path)}

async def generate_error_rate_chart(df, chart_spec, ctx):
    """
    Generate and save an Error Rate line chart for a given resource.

    Args:
        df (pd.DataFrame): Full CSV data for the resource (already loaded)
        chart_spec (dict): Chart configuration from YAML/schema
        ctx (Context): MCP context object

    Returns:
        dict: { "resource": ..., "path": ... }
    """
    """Generate error rate chart from BlazeMeter data"""

async def generate_throughput_chart(run_id, chart_spec, ctx):
    """Generate throughput chart from BlazeMeter data"""
