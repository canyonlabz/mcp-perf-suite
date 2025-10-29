import matplotlib.pyplot as plt
import matplotlib.dates as mdates
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

    bbox = chart_spec.get("bbox_inches", "tight")
    chart_path = get_chart_output_path(run_id, "p90_vs_vusers_dual_axis")
    fig.savefig(chart_path, dpi=dpi, bbox_inches=bbox, facecolor="white")
    plt.close(fig)

    return {"chart_type": "RESP_TIME_P90_VUSERS_DUALAXIS", "path": str(chart_path)}
