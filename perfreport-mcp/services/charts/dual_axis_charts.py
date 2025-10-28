import matplotlib.pyplot as plt
import pandas as pd
from fastmcp import Context
from utils.chart_utils import get_chart_output_path

# -----------------------------------------------
# Dual Axis Chart Generators
# -----------------------------------------------
async def generate_p90_vusers_chart(df, chart_spec, ctx):
    """
    Generate and save a dual-axis line chart of P90 Response Time vs Virtual Users.

    Args:
        df (pd.DataFrame): BlazeMeter/test-results.csv loaded as dataframe.
        chart_spec (dict): Chart configuration from YAML/schema.
        ctx (Context): MCP context object.

    Returns:
        dict: { "chart_type": ..., "path": ... }
    """
    # Convert timestamp column to datetime
    df["timeStamp"] = pd.to_datetime(df["timeStamp"], unit="ms", errors="coerce")
    df = df.dropna(subset=["timeStamp"])
    df = df.sort_values("timeStamp")

    # Resample or group by minute as needed for clarity (example: by minute)
    df["minute"] = df["timeStamp"].dt.floor("min")
    grouped = df.groupby("minute")

    # Calculate P90 response time per window and average virtual user count
    p90 = grouped["90_percentile"].quantile(0.9) if "90_percentile" in df.columns else grouped["Elapsed"].quantile(0.9)
    vusers = grouped["allThreads"].mean()

    # Prepare axis labels and colors
    title = chart_spec.get("title", "P90 Response Time vs Virtual Users")
    x_label = chart_spec.get("x_axis", {}).get("label", "Time (hh:mm)")
    y_left_label = chart_spec.get("y_axis_left", {}).get("label", "P90 Response Time (ms)")
    y_right_label = chart_spec.get("y_axis_right", {}).get("label", "Virtual Users")
    colors = chart_spec.get("colors", ["#1f77b4", "#ff7f0e"])

    # Plot
    fig, ax1 = plt.subplots()
    ax1.plot(p90.index, p90.values, color=colors[0], label=y_left_label)
    ax1.set_ylabel(y_left_label, color=colors[0])
    ax1.set_xlabel(x_label)
    ax1.tick_params(axis="y", labelcolor=colors[0])

    ax2 = ax1.twinx()
    ax2.plot(vusers.index, vusers.values, color=colors[1], label=y_right_label)
    ax2.set_ylabel(y_right_label, color=colors[1])
    ax2.tick_params(axis="y", labelcolor=colors[1])

    ax1.set_title(title)
    if chart_spec.get("show_grid"):
        ax1.grid(True)

    # Legend: show both lines
    if chart_spec.get("include_legend"):
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    chart_path = get_chart_output_path(ctx.run_id, "p90_vs_vusers_dual_axis")
    fig.savefig(chart_path, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return {"chart_type": "RESP_TIME_P90_VUSERS_DUALAXIS", "path": str(chart_path)}
