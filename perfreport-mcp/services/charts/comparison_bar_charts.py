"""
Horizontal bar chart generators for comparison reports.
These charts visualize resource usage across multiple test runs.
"""

import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List, Optional
from utils.chart_utils import get_chart_output_path, interpolate_placeholders
from utils.config import load_chart_colors

# Load chart colors for color name resolution
CHART_COLORS = load_chart_colors()


def resolve_color(color_name: str) -> str:
    """Resolve color name (e.g., 'primary') to actual color value (e.g., '#1f77b4')"""
    return CHART_COLORS.get(color_name, color_name)


def resolve_colors(color_names: List[str], count: int) -> List[str]:
    """
    Resolve color names to actual values, cycling if needed.
    
    Args:
        color_names: List of color names from chart spec
        count: Number of colors needed
    
    Returns:
        List of resolved color hex values
    """
    colors = [resolve_color(name) for name in color_names]
    return [colors[i % len(colors)] for i in range(count)]


# -----------------------------------------------
# Comparison Bar Chart Generators
# -----------------------------------------------

async def generate_cpu_core_comparison_bar_chart(
    run_data: List[Dict],
    resource_name: str,
    chart_spec: dict,
    comparison_id: str
) -> dict:
    """
    Generate a horizontal bar chart comparing CPU core usage across test runs.
    
    This chart shows one horizontal bar per test run, making it easy to
    visualize how CPU usage changed between runs for a specific resource.
    
    Args:
        run_data: List of dicts with keys:
                 - run_id: Test run identifier
                 - peak_cores: Peak CPU usage in cores
                 - avg_cores: Average CPU usage in cores (optional)
        resource_name: Name of the host/service being compared
        chart_spec: Chart configuration from schema (chart_schema.yaml)
        comparison_id: Unique identifier for this comparison (e.g., timestamp)
    
    Returns:
        dict: {
            "chart_id": "CPU_CORE_COMPARISON_BAR",
            "resource": resource_name,
            "path": str (full path to generated PNG)
        }
        Or dict with "error" key if generation fails.
    
    Example:
        run_data = [
            {"run_id": "80593110", "peak_cores": 1.25, "avg_cores": 0.85},
            {"run_id": "80840304", "peak_cores": 1.42, "avg_cores": 0.92}
        ]
        result = await generate_cpu_core_comparison_bar_chart(
            run_data, "api-service", spec, "20260117"
        )
    """
    chart_id = "CPU_CORE_COMPARISON_BAR"
    
    if not run_data:
        return {"chart_id": chart_id, "resource": resource_name, "error": "No run data provided"}
    
    # Get unit configuration
    unit_config = chart_spec.get("unit", {})
    unit_type = unit_config.get("type", "cores")
    
    # Determine labels and conversion based on unit type
    if unit_type == "millicores":
        conversion_factor = 1000  # cores to millicores
        x_label = chart_spec.get("x_axis", {}).get("label", "CPU Usage (mCPU)")
        value_format = "{:.0f} mCPU"
    else:  # cores (default)
        conversion_factor = 1.0
        x_label = chart_spec.get("x_axis", {}).get("label", "CPU Usage (Cores)")
        value_format = "{:.3f} Cores"
    
    # Extract and convert data
    run_labels = [f"Run {d['run_id']}" for d in run_data]
    peak_values = [d.get('peak_cores', 0) * conversion_factor for d in run_data]
    
    # Chart configuration
    raw_title = chart_spec.get("title", f"CPU Core Usage Comparison - {resource_name}")
    title = interpolate_placeholders(raw_title, resource_name=resource_name)
    y_label = chart_spec.get("y_axis", {}).get("label", "Test Run")
    color_names = chart_spec.get("colors", ["primary", "secondary", "info", "warning", "error"])
    colors = resolve_colors(color_names, len(run_data))
    
    # Figure sizing
    dpi = int(chart_spec.get("dpi", 144))
    width_px = int(chart_spec.get("width_px", 1280))
    height_px = int(chart_spec.get("height_px", 720))
    figsize = (width_px / dpi, height_px / dpi)
    
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Create horizontal bar chart
    y_pos = np.arange(len(run_labels))
    bars = ax.barh(y_pos, peak_values, color=colors, height=0.6)
    
    # Add value labels on bars if configured
    if chart_spec.get("show_value_labels", True):
        for bar, value in zip(bars, peak_values):
            width = bar.get_width()
            ax.text(
                width + max(peak_values) * 0.02,  # Slightly offset from bar end
                bar.get_y() + bar.get_height() / 2,
                value_format.format(value),
                ha='left',
                va='center',
                fontsize=9
            )
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(run_labels)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    
    if chart_spec.get("show_grid", True):
        ax.grid(True, axis='x', linewidth=0.5, alpha=0.6)
    
    # Invert y-axis so first run is at top
    ax.invert_yaxis()
    
    # Add some padding to the right for value labels
    if chart_spec.get("show_value_labels", True):
        ax.set_xlim(0, max(peak_values) * 1.2)
    
    # Save chart
    bbox = chart_spec.get("bbox_inches", "tight")
    safe_resource_name = resource_name.replace('/', '_').replace('\\', '_').replace('*', '')
    chart_path = get_chart_output_path(comparison_id, f"{chart_id}-{safe_resource_name}")
    fig.savefig(chart_path, dpi=dpi, bbox_inches=bbox, facecolor="white")
    plt.close(fig)
    
    return {
        "chart_id": chart_id,
        "resource": resource_name,
        "path": str(chart_path),
        "unit": unit_type,
        "runs": len(run_data)
    }


async def generate_memory_usage_comparison_bar_chart(
    run_data: List[Dict],
    resource_name: str,
    chart_spec: dict,
    comparison_id: str
) -> dict:
    """
    Generate a horizontal bar chart comparing memory usage across test runs.
    
    This chart shows one horizontal bar per test run, making it easy to
    visualize how memory usage changed between runs for a specific resource.
    
    Args:
        run_data: List of dicts with keys:
                 - run_id: Test run identifier
                 - peak_gb: Peak memory usage in GB
                 - avg_gb: Average memory usage in GB (optional)
        resource_name: Name of the host/service being compared
        chart_spec: Chart configuration from schema (chart_schema.yaml)
        comparison_id: Unique identifier for this comparison (e.g., timestamp)
    
    Returns:
        dict: {
            "chart_id": "MEMORY_USAGE_COMPARISON_BAR",
            "resource": resource_name,
            "path": str (full path to generated PNG)
        }
        Or dict with "error" key if generation fails.
    
    Example:
        run_data = [
            {"run_id": "80593110", "peak_gb": 2.5, "avg_gb": 1.8},
            {"run_id": "80840304", "peak_gb": 2.8, "avg_gb": 2.1}
        ]
        result = await generate_memory_usage_comparison_bar_chart(
            run_data, "api-service", spec, "20260117"
        )
    """
    chart_id = "MEMORY_USAGE_COMPARISON_BAR"
    
    if not run_data:
        return {"chart_id": chart_id, "resource": resource_name, "error": "No run data provided"}
    
    # Get unit configuration
    unit_config = chart_spec.get("unit", {})
    unit_type = unit_config.get("type", "gb")
    
    # Determine labels and conversion based on unit type
    if unit_type == "mb":
        conversion_factor = 1024  # GB to MB
        x_label = chart_spec.get("x_axis", {}).get("label", "Memory Usage (MB)")
        value_format = "{:.0f} MB"
    else:  # gb (default)
        conversion_factor = 1.0
        x_label = chart_spec.get("x_axis", {}).get("label", "Memory Usage (GB)")
        value_format = "{:.2f} GB"
    
    # Extract and convert data
    run_labels = [f"Run {d['run_id']}" for d in run_data]
    peak_values = [d.get('peak_gb', 0) * conversion_factor for d in run_data]
    
    # Chart configuration
    raw_title = chart_spec.get("title", f"Memory Usage Comparison - {resource_name}")
    title = interpolate_placeholders(raw_title, resource_name=resource_name)
    y_label = chart_spec.get("y_axis", {}).get("label", "Test Run")
    color_names = chart_spec.get("colors", ["warning", "info", "primary", "secondary", "error"])
    colors = resolve_colors(color_names, len(run_data))
    
    # Figure sizing
    dpi = int(chart_spec.get("dpi", 144))
    width_px = int(chart_spec.get("width_px", 1280))
    height_px = int(chart_spec.get("height_px", 720))
    figsize = (width_px / dpi, height_px / dpi)
    
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
    
    # Create horizontal bar chart
    y_pos = np.arange(len(run_labels))
    bars = ax.barh(y_pos, peak_values, color=colors, height=0.6)
    
    # Add value labels on bars if configured
    if chart_spec.get("show_value_labels", True):
        for bar, value in zip(bars, peak_values):
            width = bar.get_width()
            ax.text(
                width + max(peak_values) * 0.02,  # Slightly offset from bar end
                bar.get_y() + bar.get_height() / 2,
                value_format.format(value),
                ha='left',
                va='center',
                fontsize=9
            )
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(run_labels)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    
    if chart_spec.get("show_grid", True):
        ax.grid(True, axis='x', linewidth=0.5, alpha=0.6)
    
    # Invert y-axis so first run is at top
    ax.invert_yaxis()
    
    # Add some padding to the right for value labels
    if chart_spec.get("show_value_labels", True):
        ax.set_xlim(0, max(peak_values) * 1.2)
    
    # Save chart
    bbox = chart_spec.get("bbox_inches", "tight")
    safe_resource_name = resource_name.replace('/', '_').replace('\\', '_').replace('*', '')
    chart_path = get_chart_output_path(comparison_id, f"{chart_id}-{safe_resource_name}")
    fig.savefig(chart_path, dpi=dpi, bbox_inches=bbox, facecolor="white")
    plt.close(fig)
    
    return {
        "chart_id": chart_id,
        "resource": resource_name,
        "path": str(chart_path),
        "unit": unit_type,
        "runs": len(run_data)
    }
