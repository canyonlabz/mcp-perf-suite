import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from fastmcp import Context
from utils.chart_utils import (
    get_chart_output_path,
    interpolate_placeholders,
    apply_legend,
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
async def generate_cpu_utilization_chart(df, chart_spec, env_type, resource_name, run_id):
    """
    Generate and save a CPU Utilization line chart for a given resource.

    Args:
        df (pd.DataFrame): Full CSV data already loaded for this resource.
        chart_spec (dict): Chart configuration from YAML/schema.
        env_type (str): Environment type ('host' or 'k8s').
        resource_name (str): Host or k8s service being charted.
        run_id (str): Test run identifier for output paths.

    Returns:
        dict: { "resource": ..., "path": ... }
    """
    # Filter for CPU metric and container_or_pod
    resource_column = "hostname" if env_type == "host" else "container_or_pod"
    df_filtered = df[(df["metric"] == "cpu_util_pct") & (df[resource_column] == resource_name)].copy()
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

    # Figure sizing: 16:9 with YAML overrides
    # You can specify either width/height in *pixels* OR figsize directly.
    dpi = int(chart_spec.get("dpi", 144))  # crisper default for HD exports
    width_px = int(chart_spec.get("width_px", 1280))   # 16:9 default
    height_px = int(chart_spec.get("height_px", 720))  # 16:9 default
    figsize = (width_px / dpi, height_px / dpi)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    ax.plot(df_filtered["timestamp_utc"], df_filtered["value"], color=colors[0], linewidth=1.5)
    ax.fill_between(df_filtered["timestamp_utc"], df_filtered["value"], alpha=0.1, color=colors[0])
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    if chart_spec.get("show_grid", True):
        ax.grid(True, linewidth=0.5, alpha=0.6)
    apply_legend(ax, chart_spec, num_series=1)

    # Time axis formatting + label rotation
    locator = mdates.AutoDateLocator()
    formatter = mdates.DateFormatter("%H:%M")  # matches your (hh:mm) label
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)

    # Rotate ~45° (readable “clockwise” slant visually)
    for label in ax.get_xticklabels():
        label.set_rotation(45)
        label.set_horizontalalignment("right")
        label.set_rotation_mode("anchor")

    # Save with schema ID and resource name: SCHEMA_ID-<resource_name>.png
    chart_id = "CPU_UTILIZATION_LINE"
    bbox = chart_spec.get("bbox_inches", "tight")
    chart_path = get_chart_output_path(run_id, f"{chart_id}-{resource_name}")
    fig.savefig(chart_path, dpi=dpi, bbox_inches=bbox, facecolor="white")
    plt.close(fig)

    return {"chart_id": chart_id, "resource": resource_name, "path": str(chart_path)}

async def generate_memory_utilization_chart(df, chart_spec, env_type, resource_name, run_id):
    """
    Generate and save a Memory Utilization line chart for a given resource.

    Args:
        df (pd.DataFrame): Full CSV data already loaded for this resource.
        chart_spec (dict): Chart configuration from YAML/schema.
        env_type (str): Environment type ('host' or 'k8s').
        resource_name (str): Host or k8s service being charted.
        run_id (str): Test run identifier for output paths.

    Returns:
        dict: { "resource": ..., "path": ... }
    """
    # Filter for memory metric and container_or_pod
    resource_column = "hostname" if env_type == "host" else "container_or_pod"
    df_filtered = df[(df["metric"] == "mem_util_pct") & (df[resource_column] == resource_name)].copy()
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

    # Figure sizing: 16:9 with YAML overrides
    # You can specify either width/height in *pixels* OR figsize directly.
    dpi = int(chart_spec.get("dpi", 144))  # crisper default for HD exports
    width_px = int(chart_spec.get("width_px", 1280))   # 16:9 default
    height_px = int(chart_spec.get("height_px", 720))  # 16:9 default
    figsize = (width_px / dpi, height_px / dpi)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    ax.plot(df_filtered["timestamp_utc"], df_filtered["value"], color=colors[0], linewidth=1.5)
    ax.fill_between(df_filtered["timestamp_utc"], df_filtered["value"], alpha=0.1, color=colors[0])
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    if chart_spec.get("show_grid", True):
        ax.grid(True, linewidth=0.5, alpha=0.6)
    apply_legend(ax, chart_spec, num_series=1)

    # Time axis formatting + label rotation
    locator = mdates.AutoDateLocator()
    formatter = mdates.DateFormatter("%H:%M")  # matches your (hh:mm) label
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)

    # Rotate ~45° (readable “clockwise” slant visually)
    for label in ax.get_xticklabels():
        label.set_rotation(45)
        label.set_horizontalalignment("right")
        label.set_rotation_mode("anchor")

    # Save with schema ID and resource name: SCHEMA_ID-<resource_name>.png
    chart_id = "MEMORY_UTILIZATION_LINE"
    bbox = chart_spec.get("bbox_inches", "tight")
    chart_path = get_chart_output_path(run_id, f"{chart_id}-{resource_name}")
    fig.savefig(chart_path, dpi=dpi, bbox_inches=bbox, facecolor="white")
    plt.close(fig)

    return {"chart_id": chart_id, "resource": resource_name, "path": str(chart_path)}

async def generate_cpu_cores_chart(df, chart_spec, env_type, resource_name, run_id):
    """
    Generate and save a CPU Core Usage line chart for a given resource.
    
    This chart shows actual CPU usage in Cores or Millicores (configurable),
    rather than percentage utilization. Useful for capacity planning and
    comparing against allocated resources.

    Args:
        df (pd.DataFrame): Full CSV data already loaded for this resource.
                          Expected to have 'cpu_cores' metric with nanocores values.
        chart_spec (dict): Chart configuration from YAML/schema including unit config.
        env_type (str): Environment type ('host' or 'k8s').
        resource_name (str): Host or k8s service being charted.
        run_id (str): Test run identifier for output paths.

    Returns:
        dict: { "chart_id": ..., "resource": ..., "path": ... }
    """
    # Filter for CPU core metric
    resource_column = "hostname" if env_type == "host" else "container_or_pod"
    
    # Try to find CPU core metric - could be 'cpu_cores' or 'cpu_nanocores'
    cpu_metrics = ["cpu_cores", "cpu_nanocores", "kubernetes.cpu.usage.total"]
    df_filtered = None
    
    for metric_name in cpu_metrics:
        df_try = df[(df["metric"] == metric_name) & (df[resource_column] == resource_name)].copy()
        if not df_try.empty:
            df_filtered = df_try
            break
    
    if df_filtered is None or df_filtered.empty:
        return {"resource": resource_name, "error": "No CPU core usage data for resource."}

    df_filtered["timestamp_utc"] = pd.to_datetime(df_filtered["timestamp_utc"])
    df_filtered = df_filtered.sort_values(by="timestamp_utc")
    
    # Get unit configuration
    unit_config = chart_spec.get("unit", {})
    unit_type = unit_config.get("type", "cores")
    
    # Determine conversion factor based on unit type
    # Datadog kubernetes.cpu.usage.total is in nanocores
    if unit_type == "millicores":
        conversion_factor = 1.0e-6  # nanocores to millicores
        y_label = chart_spec.get("y_axis", {}).get("label", "CPU Usage (mCPU)")
    else:  # cores (default)
        conversion_factor = 1.0e-9  # nanocores to cores
        y_label = chart_spec.get("y_axis", {}).get("label", "CPU Usage (Cores)")
    
    # Apply conversion
    df_filtered["converted_value"] = df_filtered["value"] * conversion_factor

    raw_title = chart_spec.get("title", f"CPU Core Usage - {resource_name}")
    title = interpolate_placeholders(raw_title, resource_name=resource_name)
    x_label = chart_spec.get("x_axis", {}).get("label", "Time (UTC)")
    color_names = chart_spec.get("colors", ["primary"])
    colors = [resolve_color(c) for c in color_names]

    # Figure sizing: 16:9 with YAML overrides
    dpi = int(chart_spec.get("dpi", 144))
    width_px = int(chart_spec.get("width_px", 1280))
    height_px = int(chart_spec.get("height_px", 720))
    figsize = (width_px / dpi, height_px / dpi)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    ax.plot(df_filtered["timestamp_utc"], df_filtered["converted_value"], color=colors[0], linewidth=1.5)
    ax.fill_between(df_filtered["timestamp_utc"], df_filtered["converted_value"], alpha=0.1, color=colors[0])
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    if chart_spec.get("show_grid", True):
        ax.grid(True, linewidth=0.5, alpha=0.6)
    apply_legend(ax, chart_spec, num_series=1)

    # Time axis formatting + label rotation
    locator = mdates.AutoDateLocator()
    formatter = mdates.DateFormatter("%H:%M")
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)

    for label in ax.get_xticklabels():
        label.set_rotation(45)
        label.set_horizontalalignment("right")
        label.set_rotation_mode("anchor")

    # Save with schema ID and resource name
    chart_id = "CPU_CORES_LINE"
    bbox = chart_spec.get("bbox_inches", "tight")
    chart_path = get_chart_output_path(run_id, f"{chart_id}-{resource_name}")
    fig.savefig(chart_path, dpi=dpi, bbox_inches=bbox, facecolor="white")
    plt.close(fig)

    return {"chart_id": chart_id, "resource": resource_name, "path": str(chart_path), "unit": unit_type}


async def generate_memory_usage_chart(df, chart_spec, env_type, resource_name, run_id):
    """
    Generate and save a Memory Usage line chart for a given resource.
    
    This chart shows actual memory usage in GB or MB (configurable),
    rather than percentage utilization. Useful for capacity planning and
    comparing against allocated resources.

    Args:
        df (pd.DataFrame): Full CSV data already loaded for this resource.
                          Expected to have 'mem_bytes' metric with byte values.
        chart_spec (dict): Chart configuration from YAML/schema including unit config.
        env_type (str): Environment type ('host' or 'k8s').
        resource_name (str): Host or k8s service being charted.
        run_id (str): Test run identifier for output paths.

    Returns:
        dict: { "chart_id": ..., "resource": ..., "path": ... }
    """
    # Filter for memory usage metric
    resource_column = "hostname" if env_type == "host" else "container_or_pod"
    
    # Try to find memory usage metric - could be various names
    mem_metrics = ["mem_bytes", "memory_bytes", "kubernetes.memory.usage", "system.mem.used"]
    df_filtered = None
    
    for metric_name in mem_metrics:
        df_try = df[(df["metric"] == metric_name) & (df[resource_column] == resource_name)].copy()
        if not df_try.empty:
            df_filtered = df_try
            break
    
    if df_filtered is None or df_filtered.empty:
        return {"resource": resource_name, "error": "No memory usage data for resource."}

    df_filtered["timestamp_utc"] = pd.to_datetime(df_filtered["timestamp_utc"])
    df_filtered = df_filtered.sort_values(by="timestamp_utc")
    
    # Get unit configuration
    unit_config = chart_spec.get("unit", {})
    unit_type = unit_config.get("type", "gb")
    
    # Determine conversion factor based on unit type
    # Datadog kubernetes.memory.usage is in bytes
    if unit_type == "mb":
        conversion_factor = 1.0 / (1024 * 1024)  # bytes to MB
        y_label = chart_spec.get("y_axis", {}).get("label", "Memory Usage (MB)")
    else:  # gb (default)
        conversion_factor = 1.0 / (1024 * 1024 * 1024)  # bytes to GB
        y_label = chart_spec.get("y_axis", {}).get("label", "Memory Usage (GB)")
    
    # Apply conversion
    df_filtered["converted_value"] = df_filtered["value"] * conversion_factor

    raw_title = chart_spec.get("title", f"Memory Usage - {resource_name}")
    title = interpolate_placeholders(raw_title, resource_name=resource_name)
    x_label = chart_spec.get("x_axis", {}).get("label", "Time (UTC)")
    color_names = chart_spec.get("colors", ["warning"])
    colors = [resolve_color(c) for c in color_names]

    # Figure sizing: 16:9 with YAML overrides
    dpi = int(chart_spec.get("dpi", 144))
    width_px = int(chart_spec.get("width_px", 1280))
    height_px = int(chart_spec.get("height_px", 720))
    figsize = (width_px / dpi, height_px / dpi)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    ax.plot(df_filtered["timestamp_utc"], df_filtered["converted_value"], color=colors[0], linewidth=1.5)
    ax.fill_between(df_filtered["timestamp_utc"], df_filtered["converted_value"], alpha=0.1, color=colors[0])
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    if chart_spec.get("show_grid", True):
        ax.grid(True, linewidth=0.5, alpha=0.6)
    apply_legend(ax, chart_spec, num_series=1)

    # Time axis formatting + label rotation
    locator = mdates.AutoDateLocator()
    formatter = mdates.DateFormatter("%H:%M")
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)

    for label in ax.get_xticklabels():
        label.set_rotation(45)
        label.set_horizontalalignment("right")
        label.set_rotation_mode("anchor")

    # Save with schema ID and resource name
    chart_id = "MEMORY_USAGE_LINE"
    bbox = chart_spec.get("bbox_inches", "tight")
    chart_path = get_chart_output_path(run_id, f"{chart_id}-{resource_name}")
    fig.savefig(chart_path, dpi=dpi, bbox_inches=bbox, facecolor="white")
    plt.close(fig)

    return {"chart_id": chart_id, "resource": resource_name, "path": str(chart_path), "unit": unit_type}


async def generate_error_rate_chart(df: pd.DataFrame, chart_spec: dict, run_id: str):
    """
    Generate and save an Error Rate line chart from BlazeMeter/JMeter test results.

    Shows the number of failed requests per minute over the duration of the test,
    providing a clear view of when errors occurred and whether they were transient
    or sustained.

    Args:
        df (pd.DataFrame): test-results.csv (JTL) loaded as DataFrame.
            Required columns: timeStamp (ms epoch), success (boolean string).
        chart_spec (dict): Chart configuration from chart_schema.yaml.
        run_id (str): Test run identifier for output path.

    Returns:
        dict: { "chart_id": "ERROR_RATE_LINE", "path": <png path> }
    """
    chart_id = "ERROR_RATE_LINE"

    # Validate required columns
    if "timeStamp" not in df.columns or "success" not in df.columns:
        return {"chart_id": chart_id, "error": "Missing required columns: 'timeStamp' and/or 'success'."}

    df = df.copy()
    df["timeStamp"] = pd.to_datetime(df["timeStamp"], unit="ms", errors="coerce")
    df = df.dropna(subset=["timeStamp"]).sort_values("timeStamp")

    # Count errors per minute bucket
    df["minute"] = df["timeStamp"].dt.floor("min")
    # success column can be boolean or string "true"/"false"
    df["is_error"] = df["success"].astype(str).str.lower() != "true"
    error_counts = df.groupby("minute")["is_error"].sum()

    if error_counts.empty:
        return {"chart_id": chart_id, "error": "No data to plot after grouping."}

    # Chart configuration
    title = chart_spec.get("title", "Error Rate Over Time")
    y_label = chart_spec.get("y_axis", {}).get("label", "Error Count")
    x_label = chart_spec.get("x_axis", {}).get("label", "Time (hh:mm)")
    color_names = chart_spec.get("colors", ["error"])
    colors = [resolve_color(c) for c in color_names]

    # Figure sizing
    dpi = int(chart_spec.get("dpi", 144))
    width_px = int(chart_spec.get("width_px", 1280))
    height_px = int(chart_spec.get("height_px", 720))
    figsize = (width_px / dpi, height_px / dpi)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    ax.plot(error_counts.index, error_counts.values, color=colors[0], linewidth=1.5)
    ax.fill_between(error_counts.index, error_counts.values, alpha=0.15, color=colors[0])
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_ylim(bottom=0)

    if chart_spec.get("show_grid", True):
        ax.grid(True, linewidth=0.5, alpha=0.6)

    # Time axis formatting + label rotation
    locator = mdates.AutoDateLocator()
    formatter = mdates.DateFormatter("%H:%M")
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)

    for label in ax.get_xticklabels():
        label.set_rotation(45)
        label.set_horizontalalignment("right")
        label.set_rotation_mode("anchor")

    bbox = chart_spec.get("bbox_inches", "tight")
    chart_path = get_chart_output_path(run_id, chart_id)
    fig.savefig(chart_path, dpi=dpi, bbox_inches=bbox, facecolor="white")
    plt.close(fig)

    return {"chart_id": chart_id, "path": str(chart_path)}


async def generate_throughput_chart(df: pd.DataFrame, chart_spec: dict, run_id: str):
    """
    Generate and save a Throughput (requests/sec) line chart from BlazeMeter/JMeter results.

    Shows the transaction throughput over the duration of the test, calculated as
    the number of requests per minute divided by 60 to get requests per second.

    Args:
        df (pd.DataFrame): test-results.csv (JTL) loaded as DataFrame.
            Required columns: timeStamp (ms epoch).
        chart_spec (dict): Chart configuration from chart_schema.yaml.
        run_id (str): Test run identifier for output path.

    Returns:
        dict: { "chart_id": "THROUGHPUT_HITS_LINE", "path": <png path> }
    """
    chart_id = "THROUGHPUT_HITS_LINE"

    # Validate required columns
    if "timeStamp" not in df.columns:
        return {"chart_id": chart_id, "error": "Missing required column: 'timeStamp'."}

    df = df.copy()
    df["timeStamp"] = pd.to_datetime(df["timeStamp"], unit="ms", errors="coerce")
    df = df.dropna(subset=["timeStamp"]).sort_values("timeStamp")

    # Count requests per minute, convert to req/sec
    df["minute"] = df["timeStamp"].dt.floor("min")
    requests_per_min = df.groupby("minute").size()
    throughput = requests_per_min / 60.0  # Convert to requests per second

    if throughput.empty:
        return {"chart_id": chart_id, "error": "No data to plot after grouping."}

    # Chart configuration
    title = chart_spec.get("title", "Throughput Over Time")
    y_label = chart_spec.get("y_axis", {}).get("label", "Throughput (req/sec)")
    x_label = chart_spec.get("x_axis", {}).get("label", "Time (hh:mm)")
    color_names = chart_spec.get("colors", ["primary"])
    colors = [resolve_color(c) for c in color_names]

    # Figure sizing
    dpi = int(chart_spec.get("dpi", 144))
    width_px = int(chart_spec.get("width_px", 1280))
    height_px = int(chart_spec.get("height_px", 720))
    figsize = (width_px / dpi, height_px / dpi)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    ax.plot(throughput.index, throughput.values, color=colors[0], linewidth=1.5)
    ax.fill_between(throughput.index, throughput.values, alpha=0.1, color=colors[0])
    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_ylim(bottom=0)

    if chart_spec.get("show_grid", True):
        ax.grid(True, linewidth=0.5, alpha=0.6)

    # Time axis formatting + label rotation
    locator = mdates.AutoDateLocator()
    formatter = mdates.DateFormatter("%H:%M")
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)

    for label in ax.get_xticklabels():
        label.set_rotation(45)
        label.set_horizontalalignment("right")
        label.set_rotation_mode("anchor")

    bbox = chart_spec.get("bbox_inches", "tight")
    chart_path = get_chart_output_path(run_id, chart_id)
    fig.savefig(chart_path, dpi=dpi, bbox_inches=bbox, facecolor="white")
    plt.close(fig)

    return {"chart_id": chart_id, "path": str(chart_path)}
