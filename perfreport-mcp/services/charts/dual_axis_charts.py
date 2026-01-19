import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from typing import Dict, Optional
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
# Dual Axis Chart Generators
# -----------------------------------------------
async def generate_p90_vusers_chart(df: pd.DataFrame, chart_spec: dict, run_id: str):
    """
    Generate and save a dual-axis line chart of P90 Response Time vs Virtual Users.

    Args:
        df (pd.DataFrame): test-results.csv (JTL) loaded as DataFrame.
            Required columns: timeStamp (ms), elapsed (ms), allThreads (int).
        chart_spec (dict): Chart configuration from YAML/schema.
            Optional keys: title, x_axis.label, y_axis_left.label, y_axis_right.label,
                           colors [left, right], dpi, width_px, height_px, bbox_inches,
                           show_grid (bool), include_legend (bool)
        run_id (str): test run identifier for output path.

    Returns:
        dict: { "chart_type": "RESP_TIME_P90_VUSERS_DUALAXIS", "path": <png path> }
    """
    # ---- 1) Prepare timestamps & group by minute ----------------------------
    # timeStamp comes from JTL in milliseconds epoch
    df = df.copy()
    df["timeStamp"] = pd.to_datetime(df["timeStamp"], unit="ms", errors="coerce")
    df = df.dropna(subset=["timeStamp"]).sort_values("timeStamp")

    # Group into minute buckets for a clean, readable trend
    df["minute"] = df["timeStamp"].dt.floor("min")
    grouped = df.groupby("minute", as_index=True)

    # ---- 2) Compute metrics -------------------------------------------------
    # p90 of response time (ms) per minute, and mean virtual users per minute
    if "elapsed" not in df.columns or "allThreads" not in df.columns:
        return {"chart_type": "RESP_TIME_P90_VUSERS_DUALAXIS",
                "error": "Missing required columns: 'elapsed' and/or 'allThreads'."}

    p90_ms = grouped["elapsed"].quantile(0.90)
    vusers = grouped["allThreads"].mean()

    # ---- 3) Labels, colors, figure sizing ----------------------------------
    # Titles & axis labels (with interpolation support if you wired it in)
    raw_title = chart_spec.get("title", "P90 Response Time vs Virtual Users")
    try:
        # if you have interpolate_placeholders available
        title = interpolate_placeholders(raw_title, run_id=run_id)
    except Exception:
        title = raw_title

    x_label = chart_spec.get("x_axis", {}).get("label", "Time (hh:mm)")
    y_left_label = chart_spec.get("y_axis_left", {}).get("label", "P90 Response Time (ms)")
    y_right_label = chart_spec.get("y_axis_right", {}).get("label", "Virtual Users")

    # Resolve colors (tokens → hex; or accept hex/named directly)
    color_tokens = chart_spec.get("colors", ["primary", "secondary"])
    left_color  = resolve_color(color_tokens[0] if len(color_tokens) > 0 else "C0")
    right_color = resolve_color(color_tokens[1] if len(color_tokens) > 1 else "C1")

    # Figure sizing: 16:9 defaults, overridable via YAML
    dpi = int(chart_spec.get("dpi", 144))
    width_px = int(chart_spec.get("width_px", 1280))   # 16:9 default
    height_px = int(chart_spec.get("height_px", 720))  # 16:9 default
    figsize = (width_px / dpi, height_px / dpi)

    fig, ax_left = plt.subplots(figsize=figsize, dpi=dpi)

    # ---- 4) Plot left axis (P90 ms) ----------------------------------------
    ax_left.plot(p90_ms.index, p90_ms.values, color=left_color, linewidth=1.8, label=y_left_label)
    ax_left.set_ylabel(y_left_label, color=left_color)
    ax_left.tick_params(axis="y", labelcolor=left_color)
    ax_left.set_xlabel(x_label)
    ax_left.set_title(title)

    # ---- 5) Plot right axis (virtual users) --------------------------------
    ax_right = ax_left.twinx()
    ax_right.plot(vusers.index, vusers.values, color=right_color, linewidth=1.8, label=y_right_label)
    ax_right.set_ylabel(y_right_label, color=right_color)
    ax_right.tick_params(axis="y", labelcolor=right_color)

    # ---- 6) Time axis formatting & rotation --------------------------------
    locator = mdates.AutoDateLocator(minticks=5, maxticks=10)
    formatter = mdates.DateFormatter("%H:%M")
    ax_left.xaxis.set_major_locator(locator)
    ax_left.xaxis.set_major_formatter(formatter)

    for lbl in ax_left.get_xticklabels():
        lbl.set_rotation(45)
        lbl.set_horizontalalignment("right")
        lbl.set_rotation_mode("anchor")

    # ---- 7) Grid / legend / save -------------------------------------------
    if chart_spec.get("show_grid", True):
        ax_left.grid(True, linewidth=0.5, alpha=0.6)

    if chart_spec.get("include_legend"):
        l1, lab1 = ax_left.get_legend_handles_labels()
        l2, lab2 = ax_right.get_legend_handles_labels()
        ax_left.legend(l1 + l2, lab1 + lab2, loc="upper left")

    # Save with schema ID as filename (no hostname for performance charts)
    chart_id = "RESP_TIME_P90_VUSERS_DUALAXIS"
    bbox = chart_spec.get("bbox_inches", "tight")
    chart_path = get_chart_output_path(run_id, chart_id)
    fig.savefig(chart_path, dpi=dpi, bbox_inches=bbox, facecolor="white")
    plt.close(fig)

    return {"chart_id": chart_id, "path": str(chart_path)}


# -----------------------------------------------
# Infrastructure vs VUsers Dual-Axis Charts
# -----------------------------------------------

async def generate_cpu_utilization_vusers_chart(
    infra_dataframes: Dict[str, pd.DataFrame],
    perf_df: pd.DataFrame,
    chart_spec: dict,
    run_id: str
) -> dict:
    """
    Generate a dual-axis chart showing CPU Utilization (%) vs Virtual Users over time.
    
    This chart correlates infrastructure CPU usage with the load applied during
    performance testing, helping identify whether CPU becomes a bottleneck
    as virtual users increase.
    
    Args:
        infra_dataframes: Dict mapping resource_name to DataFrame with columns:
                         - timestamp_utc: datetime
                         - value: CPU utilization percentage
        perf_df: DataFrame from test-results.csv with columns:
                - timeStamp: epoch milliseconds
                - allThreads: virtual user count
        chart_spec: Chart configuration from schema (chart_schema.yaml)
        run_id: Test run identifier for output path
    
    Returns:
        dict: {
            "chart_id": "CPU_UTILIZATION_VUSERS_DUALAXIS",
            "path": str (full path to generated PNG),
            "resources": list (names of resources used for averaging)
        }
        Or dict with "error" key if generation fails.
    """
    chart_id = "CPU_UTILIZATION_VUSERS_DUALAXIS"
    
    if not infra_dataframes:
        return {"chart_id": chart_id, "error": "No infrastructure data provided"}
    
    if perf_df is None or perf_df.empty:
        return {"chart_id": chart_id, "error": "No performance data provided"}
    
    # ---- 1) Process performance data (VUsers) --------------------------------
    perf_df = perf_df.copy()
    perf_df["timeStamp"] = pd.to_datetime(perf_df["timeStamp"], unit="ms", errors="coerce")
    perf_df = perf_df.dropna(subset=["timeStamp"]).sort_values("timeStamp")
    perf_df["minute"] = perf_df["timeStamp"].dt.floor("min")
    vusers = perf_df.groupby("minute")["allThreads"].mean()
    
    # ---- 2) Process infrastructure data (CPU %) ------------------------------
    # Aggregate CPU utilization across all resources by computing the mean
    all_cpu_dfs = []
    resource_names = []
    
    for resource_name, df in infra_dataframes.items():
        if df is None or df.empty:
            continue
        
        df = df.copy()
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"])
        df = df.sort_values(by="timestamp_utc")
        df["minute"] = df["timestamp_utc"].dt.floor("min")
        
        # Group by minute and get mean CPU for this resource
        resource_cpu = df.groupby("minute")["value"].mean()
        all_cpu_dfs.append(resource_cpu)
        resource_names.append(resource_name)
    
    if not all_cpu_dfs:
        return {"chart_id": chart_id, "error": "No valid CPU data to aggregate"}
    
    # Average CPU across all resources
    cpu_combined = pd.concat(all_cpu_dfs, axis=1)
    cpu_avg = cpu_combined.mean(axis=1)
    
    # ---- 3) Align time ranges ------------------------------------------------
    # Find common time range
    common_start = max(cpu_avg.index.min(), vusers.index.min())
    common_end = min(cpu_avg.index.max(), vusers.index.max())
    
    cpu_avg = cpu_avg[(cpu_avg.index >= common_start) & (cpu_avg.index <= common_end)]
    vusers = vusers[(vusers.index >= common_start) & (vusers.index <= common_end)]
    
    if cpu_avg.empty or vusers.empty:
        return {"chart_id": chart_id, "error": "No overlapping time range between infrastructure and performance data"}
    
    # ---- 4) Chart configuration ----------------------------------------------
    title = chart_spec.get("title", "CPU Utilization vs Virtual Users")
    x_label = chart_spec.get("x_axis", {}).get("label", "Time (hh:mm) UTC")
    y_left_label = chart_spec.get("y_axis_left", {}).get("label", "CPU Utilization (%)")
    y_right_label = chart_spec.get("y_axis_right", {}).get("label", "Virtual Users")
    
    color_tokens = chart_spec.get("colors", ["primary", "secondary"])
    left_color = resolve_color(color_tokens[0] if len(color_tokens) > 0 else "primary")
    right_color = resolve_color(color_tokens[1] if len(color_tokens) > 1 else "secondary")
    
    dpi = int(chart_spec.get("dpi", 144))
    width_px = int(chart_spec.get("width_px", 1280))
    height_px = int(chart_spec.get("height_px", 720))
    figsize = (width_px / dpi, height_px / dpi)
    
    # ---- 5) Create dual-axis plot --------------------------------------------
    fig, ax_left = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Plot CPU utilization on left axis
    ax_left.plot(cpu_avg.index, cpu_avg.values, color=left_color, linewidth=1.8, label=y_left_label)
    ax_left.set_ylabel(y_left_label, color=left_color)
    ax_left.tick_params(axis="y", labelcolor=left_color)
    ax_left.set_xlabel(x_label)
    ax_left.set_title(title)
    
    # Plot virtual users on right axis
    ax_right = ax_left.twinx()
    ax_right.plot(vusers.index, vusers.values, color=right_color, linewidth=1.8, label=y_right_label)
    ax_right.set_ylabel(y_right_label, color=right_color)
    ax_right.tick_params(axis="y", labelcolor=right_color)
    
    # ---- 6) Time axis formatting ---------------------------------------------
    locator = mdates.AutoDateLocator(minticks=5, maxticks=10)
    formatter = mdates.DateFormatter("%H:%M")
    ax_left.xaxis.set_major_locator(locator)
    ax_left.xaxis.set_major_formatter(formatter)
    
    for lbl in ax_left.get_xticklabels():
        lbl.set_rotation(45)
        lbl.set_horizontalalignment("right")
        lbl.set_rotation_mode("anchor")
    
    # ---- 7) Grid / legend / save ---------------------------------------------
    if chart_spec.get("show_grid", True):
        ax_left.grid(True, linewidth=0.5, alpha=0.6)
    
    if chart_spec.get("include_legend", True):
        l1, lab1 = ax_left.get_legend_handles_labels()
        l2, lab2 = ax_right.get_legend_handles_labels()
        legend_loc = chart_spec.get("legend_location", "upper left")
        ax_left.legend(l1 + l2, lab1 + lab2, loc=legend_loc, fontsize=8)
    
    bbox = chart_spec.get("bbox_inches", "tight")
    chart_path = get_chart_output_path(run_id, chart_id)
    fig.savefig(chart_path, dpi=dpi, bbox_inches=bbox, facecolor="white")
    plt.close(fig)
    
    return {
        "chart_id": chart_id,
        "path": str(chart_path),
        "resources": resource_names
    }


async def generate_memory_utilization_vusers_chart(
    infra_dataframes: Dict[str, pd.DataFrame],
    perf_df: pd.DataFrame,
    chart_spec: dict,
    run_id: str
) -> dict:
    """
    Generate a dual-axis chart showing Memory Utilization (%) vs Virtual Users over time.
    
    This chart correlates infrastructure memory usage with the load applied during
    performance testing, helping identify whether memory becomes a bottleneck
    as virtual users increase.
    
    Args:
        infra_dataframes: Dict mapping resource_name to DataFrame with columns:
                         - timestamp_utc: datetime
                         - value: Memory utilization percentage
        perf_df: DataFrame from test-results.csv with columns:
                - timeStamp: epoch milliseconds
                - allThreads: virtual user count
        chart_spec: Chart configuration from schema (chart_schema.yaml)
        run_id: Test run identifier for output path
    
    Returns:
        dict: {
            "chart_id": "MEMORY_UTILIZATION_VUSERS_DUALAXIS",
            "path": str (full path to generated PNG),
            "resources": list (names of resources used for averaging)
        }
        Or dict with "error" key if generation fails.
    """
    chart_id = "MEMORY_UTILIZATION_VUSERS_DUALAXIS"
    
    if not infra_dataframes:
        return {"chart_id": chart_id, "error": "No infrastructure data provided"}
    
    if perf_df is None or perf_df.empty:
        return {"chart_id": chart_id, "error": "No performance data provided"}
    
    # ---- 1) Process performance data (VUsers) --------------------------------
    perf_df = perf_df.copy()
    perf_df["timeStamp"] = pd.to_datetime(perf_df["timeStamp"], unit="ms", errors="coerce")
    perf_df = perf_df.dropna(subset=["timeStamp"]).sort_values("timeStamp")
    perf_df["minute"] = perf_df["timeStamp"].dt.floor("min")
    vusers = perf_df.groupby("minute")["allThreads"].mean()
    
    # ---- 2) Process infrastructure data (Memory %) ---------------------------
    # Aggregate Memory utilization across all resources by computing the mean
    all_mem_dfs = []
    resource_names = []
    
    for resource_name, df in infra_dataframes.items():
        if df is None or df.empty:
            continue
        
        df = df.copy()
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"])
        df = df.sort_values(by="timestamp_utc")
        df["minute"] = df["timestamp_utc"].dt.floor("min")
        
        # Group by minute and get mean memory for this resource
        resource_mem = df.groupby("minute")["value"].mean()
        all_mem_dfs.append(resource_mem)
        resource_names.append(resource_name)
    
    if not all_mem_dfs:
        return {"chart_id": chart_id, "error": "No valid memory data to aggregate"}
    
    # Average memory across all resources
    mem_combined = pd.concat(all_mem_dfs, axis=1)
    mem_avg = mem_combined.mean(axis=1)
    
    # ---- 3) Align time ranges ------------------------------------------------
    # Find common time range
    common_start = max(mem_avg.index.min(), vusers.index.min())
    common_end = min(mem_avg.index.max(), vusers.index.max())
    
    mem_avg = mem_avg[(mem_avg.index >= common_start) & (mem_avg.index <= common_end)]
    vusers = vusers[(vusers.index >= common_start) & (vusers.index <= common_end)]
    
    if mem_avg.empty or vusers.empty:
        return {"chart_id": chart_id, "error": "No overlapping time range between infrastructure and performance data"}
    
    # ---- 4) Chart configuration ----------------------------------------------
    title = chart_spec.get("title", "Memory Utilization vs Virtual Users")
    x_label = chart_spec.get("x_axis", {}).get("label", "Time (hh:mm) UTC")
    y_left_label = chart_spec.get("y_axis_left", {}).get("label", "Memory Utilization (%)")
    y_right_label = chart_spec.get("y_axis_right", {}).get("label", "Virtual Users")
    
    color_tokens = chart_spec.get("colors", ["warning", "secondary"])
    left_color = resolve_color(color_tokens[0] if len(color_tokens) > 0 else "warning")
    right_color = resolve_color(color_tokens[1] if len(color_tokens) > 1 else "secondary")
    
    dpi = int(chart_spec.get("dpi", 144))
    width_px = int(chart_spec.get("width_px", 1280))
    height_px = int(chart_spec.get("height_px", 720))
    figsize = (width_px / dpi, height_px / dpi)
    
    # ---- 5) Create dual-axis plot --------------------------------------------
    fig, ax_left = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Plot memory utilization on left axis
    ax_left.plot(mem_avg.index, mem_avg.values, color=left_color, linewidth=1.8, label=y_left_label)
    ax_left.set_ylabel(y_left_label, color=left_color)
    ax_left.tick_params(axis="y", labelcolor=left_color)
    ax_left.set_xlabel(x_label)
    ax_left.set_title(title)
    
    # Plot virtual users on right axis
    ax_right = ax_left.twinx()
    ax_right.plot(vusers.index, vusers.values, color=right_color, linewidth=1.8, label=y_right_label)
    ax_right.set_ylabel(y_right_label, color=right_color)
    ax_right.tick_params(axis="y", labelcolor=right_color)
    
    # ---- 6) Time axis formatting ---------------------------------------------
    locator = mdates.AutoDateLocator(minticks=5, maxticks=10)
    formatter = mdates.DateFormatter("%H:%M")
    ax_left.xaxis.set_major_locator(locator)
    ax_left.xaxis.set_major_formatter(formatter)
    
    for lbl in ax_left.get_xticklabels():
        lbl.set_rotation(45)
        lbl.set_horizontalalignment("right")
        lbl.set_rotation_mode("anchor")
    
    # ---- 7) Grid / legend / save ---------------------------------------------
    if chart_spec.get("show_grid", True):
        ax_left.grid(True, linewidth=0.5, alpha=0.6)
    
    if chart_spec.get("include_legend", True):
        l1, lab1 = ax_left.get_legend_handles_labels()
        l2, lab2 = ax_right.get_legend_handles_labels()
        legend_loc = chart_spec.get("legend_location", "upper left")
        ax_left.legend(l1 + l2, lab1 + lab2, loc=legend_loc, fontsize=8)
    
    bbox = chart_spec.get("bbox_inches", "tight")
    chart_path = get_chart_output_path(run_id, chart_id)
    fig.savefig(chart_path, dpi=dpi, bbox_inches=bbox, facecolor="white")
    plt.close(fig)
    
    return {
        "chart_id": chart_id,
        "path": str(chart_path),
        "resources": resource_names
    }
