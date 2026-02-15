"""
Horizontal bar chart generators for performance analysis.
Shows API-level metrics ranked by severity or response time.
"""

import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List
from utils.chart_utils import get_chart_output_path
from utils.config import load_chart_colors

# Load chart colors for color name resolution
CHART_COLORS = load_chart_colors()


def resolve_color(color_name: str) -> str:
    """Resolve color name (e.g., 'primary') to actual color value (e.g., '#1f77b4')"""
    return CHART_COLORS.get(color_name, color_name)


# -----------------------------------------------
# Horizontal Bar Chart Generators
# -----------------------------------------------

async def generate_top_slowest_apis_chart(
    api_data: Dict[str, dict],
    chart_spec: dict,
    run_id: str
) -> dict:
    """
    Generate a horizontal bar chart showing top API SLA violators by P90 response time.

    Displays the slowest APIs that exceeded their SLA threshold, ranked by P90
    response time (descending). Each bar represents one API, with a dashed vertical
    line showing the per-API SLA threshold.

    Args:
        api_data: Dict from performance_analysis.json["api_analysis"].
                  Each key is an API name, value is a dict with:
                  - p90_response_time: float (ms)
                  - avg_response_time: float (ms)
                  - sla_compliant: bool
                  - sla_threshold_ms: float (ms)
                  - samples: int
        chart_spec: Chart configuration from chart_schema.yaml.
        run_id: Test run identifier for output path.

    Returns:
        dict: {
            "chart_id": "TOP_SLOWEST_APIS_BAR",
            "path": str (full path to generated PNG),
            "api_count": int (number of APIs shown)
        }
        Or dict with "error" key if generation fails.
    """
    chart_id = "TOP_SLOWEST_APIS_BAR"

    if not api_data:
        return {"chart_id": chart_id, "error": "No API analysis data provided"}

    # Filter for SLA violators only (if filter_condition is set in schema)
    filter_condition = chart_spec.get("filter_condition", "")
    if "sla_compliant == False" in filter_condition:
        filtered = {
            name: data for name, data in api_data.items()
            if not data.get("sla_compliant", True)
        }
    else:
        filtered = api_data

    if not filtered:
        return {"chart_id": chart_id, "error": "No SLA-violating APIs found"}

    # Sort by P90 response time descending and take top N
    limit = chart_spec.get("limit", 10)
    sorted_apis = sorted(
        filtered.items(),
        key=lambda x: x[1].get("p90_response_time", 0),
        reverse=True
    )[:limit]

    # Extract data for plotting (reverse for horizontal bar - top item at top)
    sorted_apis.reverse()
    api_names = []
    p90_values = []
    sla_thresholds = []

    for name, data in sorted_apis:
        # Truncate long API names for readability
        display_name = name if len(name) <= 50 else name[:47] + "..."
        api_names.append(display_name)
        p90_values.append(data.get("p90_response_time", 0))
        sla_thresholds.append(data.get("sla_threshold_ms", None))

    # Chart configuration
    title = chart_spec.get("title", "Top API SLA Violators")
    x_label = chart_spec.get("x_axis", {}).get("label", "P90 Response Time (ms)")
    y_label = chart_spec.get("y_axis", {}).get("label", "API Name")
    color_names = chart_spec.get("colors", ["error", "warning"])
    colors = [resolve_color(c) for c in color_names]
    bar_color = colors[0] if colors else "#d62728"

    # SLA threshold line configuration
    sla_config = chart_spec.get("sla_threshold", {})
    show_sla_line = sla_config.get("show_line", True)
    sla_line_style = sla_config.get("line_style", "dashed")
    sla_line_color = resolve_color(sla_config.get("line_color", "error"))

    # Figure sizing - slightly taller for horizontal bars
    dpi = int(chart_spec.get("dpi", 144))
    width_px = int(chart_spec.get("width_px", 1280))
    # Dynamic height based on number of APIs
    bar_height_px = 50
    min_height_px = 400
    height_px = max(min_height_px, len(api_names) * bar_height_px + 150)
    figsize = (width_px / dpi, height_px / dpi)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Create horizontal bar chart
    y_pos = np.arange(len(api_names))
    bars = ax.barh(y_pos, p90_values, color=bar_color, height=0.6, alpha=0.85)

    # Add SLA threshold lines per API (if configured and available)
    if show_sla_line:
        for idx, threshold in enumerate(sla_thresholds):
            if threshold is not None and threshold > 0:
                ax.plot(
                    [threshold, threshold],
                    [idx - 0.35, idx + 0.35],
                    color=sla_line_color,
                    linestyle=sla_line_style,
                    linewidth=2,
                    alpha=0.8
                )

    # Add value labels at the end of each bar
    for bar, value in zip(bars, p90_values):
        width = bar.get_width()
        ax.text(
            width + max(p90_values) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{value:.0f} ms",
            ha='left',
            va='center',
            fontsize=8,
            fontweight='bold'
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(api_names, fontsize=8)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.set_xlim(left=0, right=max(p90_values) * 1.15)

    if chart_spec.get("show_grid", True):
        ax.grid(True, axis='x', linewidth=0.5, alpha=0.6)

    plt.tight_layout()

    bbox = chart_spec.get("bbox_inches", "tight")
    chart_path = get_chart_output_path(run_id, chart_id)
    fig.savefig(chart_path, dpi=dpi, bbox_inches=bbox, facecolor="white")
    plt.close(fig)

    return {
        "chart_id": chart_id,
        "path": str(chart_path),
        "api_count": len(api_names)
    }
