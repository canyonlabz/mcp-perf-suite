"""
KPI Timeseries Analysis Module

Handles analysis of application-level KPI metrics from APM-generated
kpi_metrics_*.csv files.  Produces per-service summaries with category
tagging, trend detection, and insight generation.

This module is called FROM existing PerfAnalysis tools — it does not
register any MCP tools itself.

Technology-neutral: works with any runtime/APM tool.  Metric categorization
is pattern-based via the shared CATEGORY_REGISTRY in kpi_utils.
"""
import datetime
from typing import Dict, List, Optional, Any
from fastmcp import Context
from pathlib import Path
import pandas as pd

from utils.kpi_utils import (
    load_kpi_dataframe,
    categorize_metric,
    get_display_unit,
    compute_metric_summary,
    CATEGORY_REGISTRY,
)
from utils.file_processor import (
    write_json_output,
    write_markdown_output,
)


# -----------------------------------------------
# Tool 1: analyze_environment_metrics
# -----------------------------------------------

async def analyze_kpi_metrics(
    kpi_files: List[Path],
    environments_config: Dict,
    config: Dict,
    ctx: Context,
) -> Dict[str, Any]:
    """Analyze KPI timeseries data and produce per-service, per-metric summaries.

    Reads all kpi_metrics_*.csv files, groups by service (``filter`` column),
    computes descriptive statistics and trend per metric, and tags each metric
    with its category.

    Args:
        kpi_files:            Sorted list of kpi_metrics_*.csv paths.
        environments_config:  Environment config dict (from environments.json).
        config:               PerfAnalysis config dict.
        ctx:                  FastMCP context for progress logging.

    Returns:
        Dict with keys: ``services``, ``metric_categories_found``,
        ``total_services``, ``kpi_insights``, ``analysis_timestamp``.
    """
    kpi_analysis: Dict[str, Any] = {
        "services": {},
        "metric_categories_found": [],
        "total_services": 0,
        "kpi_insights": [],
        "analysis_timestamp": datetime.datetime.now().isoformat(),
    }

    await ctx.info("KPI Analysis", f"Processing {len(kpi_files)} KPI metrics file(s)")

    raw_df = load_kpi_dataframe(kpi_files)
    if raw_df is None or raw_df.empty:
        await ctx.warning("KPI Analysis", "KPI CSV files found but contained no data")
        return kpi_analysis

    identifier_col = "filter"
    if identifier_col not in raw_df.columns:
        await ctx.warning("KPI Analysis", "KPI CSV missing 'filter' column — skipping")
        return kpi_analysis

    services = raw_df[identifier_col].unique()
    categories_seen: set = set()

    for service in services:
        svc_data = raw_df[raw_df[identifier_col] == service]
        svc_metrics = svc_data["metric"].unique()
        service_summary: Dict[str, Any] = {}

        for metric_name in svc_metrics:
            metric_rows = svc_data[svc_data["metric"] == metric_name]
            category = categorize_metric(metric_name)
            categories_seen.add(category)

            original_unit = str(metric_rows["unit"].iloc[0]) if "unit" in metric_rows.columns else "unknown"
            display_unit = get_display_unit(metric_name, original_unit)

            stats = compute_metric_summary(metric_rows["value"])

            service_summary[metric_name] = {
                "category": category,
                "unit": original_unit,
                "display_unit": display_unit,
                **stats,
            }

        kpi_analysis["services"][service] = service_summary

    kpi_analysis["total_services"] = len(services)
    kpi_analysis["metric_categories_found"] = sorted(categories_seen)

    kpi_analysis["kpi_insights"] = generate_kpi_insights(kpi_analysis)

    await ctx.info(
        "KPI Analysis Complete",
        f"Analyzed {len(services)} service(s), "
        f"{len(categories_seen)} category/categories: {', '.join(sorted(categories_seen))}",
    )

    return kpi_analysis


# -----------------------------------------------
# Insight Generation
# -----------------------------------------------

def generate_kpi_insights(kpi_analysis: Dict[str, Any]) -> List[str]:
    """Generate human-readable insights from the KPI analysis results.

    Scans per-service metric summaries and produces actionable observations
    about latency health, GC behaviour, throughput consistency, error trends,
    and other KPI categories.

    Args:
        kpi_analysis: The dict produced by :func:`analyze_kpi_metrics`.

    Returns:
        List of insight strings.
    """
    insights: List[str] = []

    for service, metrics in kpi_analysis.get("services", {}).items():
        short_name = _short_service_name(service)

        for metric_name, stats in metrics.items():
            category = stats.get("category", "custom")
            trend = stats.get("trend", "stable")
            samples = stats.get("samples", 0)
            if samples == 0:
                continue

            if category == "latency":
                _add_latency_insights(insights, short_name, metric_name, stats)

            elif category in ("gc_pressure", "gc_pause"):
                _add_gc_pressure_insights(insights, short_name, metric_name, stats)

            elif category == "gc_heap":
                _add_gc_heap_insights(insights, short_name, metric_name, stats)

            elif category == "gc_activity":
                if trend == "increasing":
                    insights.append(
                        f"{short_name}: {metric_name} shows increasing GC frequency "
                        f"(trend: {trend}) — may indicate growing allocation pressure"
                    )

            elif category == "throughput":
                _add_throughput_insights(insights, short_name, metric_name, stats)

            elif category == "errors":
                _add_error_insights(insights, short_name, metric_name, stats)

            elif category == "contention":
                if trend == "increasing":
                    insights.append(
                        f"{short_name}: {metric_name} trending upward — "
                        f"investigate potential lock contention hotspots"
                    )

            elif category == "threads":
                if trend == "increasing":
                    insights.append(
                        f"{short_name}: {metric_name} growing over time — "
                        f"thread pool may be under pressure"
                    )

            elif category == "connections":
                if trend == "increasing":
                    insights.append(
                        f"{short_name}: {metric_name} trending upward — "
                        f"check for connection pool saturation"
                    )

            elif category == "process_cpu":
                p90 = stats.get("p90")
                if p90 is not None and p90 > 80:
                    insights.append(
                        f"{short_name}: {metric_name} P90 at {p90:.1f}% — "
                        f"process-level CPU near saturation"
                    )

            elif category == "process_memory":
                if trend == "increasing":
                    insights.append(
                        f"{short_name}: {metric_name} trending upward — "
                        f"possible process-level memory growth"
                    )

    return insights


def _add_latency_insights(
    insights: List[str], svc: str, metric: str, stats: Dict
) -> None:
    """Append latency-specific insights."""
    p95 = stats.get("p95")
    p90 = stats.get("p90")
    trend = stats.get("trend", "stable")
    display_unit = stats.get("display_unit", stats.get("unit", ""))

    if p95 is not None and p90 is not None:
        insights.append(
            f"{svc}: {metric} P90={p90:.4f}{display_unit}, "
            f"P95={p95:.4f}{display_unit} — "
            + ("stable" if trend == "stable" else f"trend: {trend}")
        )
    if trend == "increasing":
        insights.append(
            f"{svc}: {metric} shows increasing latency — "
            f"investigate potential degradation"
        )


def _add_gc_pressure_insights(
    insights: List[str], svc: str, metric: str, stats: Dict
) -> None:
    """Append GC pressure / pause insights."""
    p90 = stats.get("p90")
    avg = stats.get("avg")
    trend = stats.get("trend", "stable")
    display_unit = stats.get("display_unit", stats.get("unit", ""))

    if avg is not None and p90 is not None:
        if stats.get("category") == "gc_pressure" and p90 > 85:
            insights.append(
                f"{svc}: {metric} P90 at {p90:.1f}{display_unit} — "
                f"GC pressure is high, may impact responsiveness"
            )
        elif stats.get("category") == "gc_pressure":
            insights.append(
                f"{svc}: {metric} avg {avg:.1f}{display_unit}, "
                f"P90 {p90:.1f}{display_unit} — "
                f"{'no GC pressure detected' if trend == 'stable' else f'trend: {trend}'}"
            )


def _add_gc_heap_insights(
    insights: List[str], svc: str, metric: str, stats: Dict
) -> None:
    """Append GC heap size insights (focus on growth trends)."""
    trend = stats.get("trend", "stable")
    if trend == "increasing":
        min_val = stats.get("min", 0)
        max_val = stats.get("max", 0)
        display_unit = stats.get("display_unit", stats.get("unit", ""))
        insights.append(
            f"{svc}: {metric} shows gradual increase "
            f"({min_val:.1f}→{max_val:.1f}{display_unit}, trend: {trend}) — "
            f"potential slow memory growth"
        )


def _add_throughput_insights(
    insights: List[str], svc: str, metric: str, stats: Dict
) -> None:
    """Append throughput-related insights."""
    avg = stats.get("avg")
    std_dev = stats.get("std_dev", 0)
    trend = stats.get("trend", "stable")

    if avg is not None and avg > 0:
        cv = (std_dev / avg) if avg != 0 else 0
        if cv > 0.5:
            insights.append(
                f"{svc}: {metric} has high variability "
                f"(CV={cv:.2f}) — throughput is inconsistent"
            )
        if trend == "decreasing":
            insights.append(
                f"{svc}: {metric} trending downward — "
                f"server-side throughput may be declining"
            )


def _add_error_insights(
    insights: List[str], svc: str, metric: str, stats: Dict
) -> None:
    """Append error/exception insights."""
    max_val = stats.get("max", 0)
    avg = stats.get("avg", 0)
    trend = stats.get("trend", "stable")

    if max_val is not None and max_val > 0:
        insights.append(
            f"{svc}: {metric} detected — peak {max_val:.0f}, "
            f"avg {avg:.1f} ({'stable' if trend == 'stable' else f'trend: {trend}'})"
        )
        if trend == "increasing":
            insights.append(
                f"{svc}: {metric} trending upward — investigate error source"
            )


def _short_service_name(full_service: str) -> str:
    """Shorten a dotted service name to its last two segments for readability."""
    parts = full_service.rsplit(".", 2)
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return full_service


# -----------------------------------------------
# Output Generation
# -----------------------------------------------

async def generate_kpi_outputs(
    kpi_analysis: Dict[str, Any],
    output_path: Path,
    test_run_id: str,
    ctx: Context,
) -> Dict[str, str]:
    """Write KPI analysis results to standalone output files.

    Produces:
      - ``kpi_analysis.json``  — full structured analysis
      - ``kpi_summary.md``     — human-readable markdown summary

    Args:
        kpi_analysis:  Dict returned by :func:`analyze_kpi_metrics`.
        output_path:   Analysis output directory (artifacts/{run}/analysis/).
        test_run_id:   Current test run ID.
        ctx:           FastMCP context.

    Returns:
        Dict mapping output type to file path string.
    """
    output_files: Dict[str, str] = {}

    try:
        json_file = output_path / "kpi_analysis.json"
        await write_json_output(kpi_analysis, json_file)
        output_files["json"] = str(json_file)

        md_file = output_path / "kpi_summary.md"
        md_content = _format_kpi_markdown(kpi_analysis, test_run_id)
        await write_markdown_output(md_content, md_file)
        output_files["markdown"] = str(md_file)

        await ctx.info(
            "KPI Output Generation",
            f"Generated {len(output_files)} KPI analysis file(s)",
        )

    except Exception as e:
        await ctx.error(
            "KPI Output Generation Error",
            f"Failed to generate KPI outputs: {str(e)}",
        )

    return output_files


def _format_kpi_markdown(kpi_analysis: Dict[str, Any], test_run_id: str) -> str:
    """Format KPI analysis as a Markdown summary."""
    lines: List[str] = []
    lines.append(f"# KPI Analysis Summary — {test_run_id}")
    lines.append("")
    lines.append(f"**Services analyzed:** {kpi_analysis.get('total_services', 0)}")
    categories = kpi_analysis.get("metric_categories_found", [])
    lines.append(f"**Metric categories:** {', '.join(categories) if categories else 'none'}")
    lines.append(f"**Generated:** {kpi_analysis.get('analysis_timestamp', 'N/A')}")
    lines.append("")

    for service, metrics in kpi_analysis.get("services", {}).items():
        lines.append(f"## {service}")
        lines.append("")

        if not metrics:
            lines.append("_No KPI metrics found for this service._")
            lines.append("")
            continue

        lines.append("| Metric | Category | Avg | P90 | P95 | Min | Max | Trend | Samples |")
        lines.append("|--------|----------|-----|-----|-----|-----|-----|-------|---------|")

        for metric_name, stats in metrics.items():
            cat = stats.get("category", "custom")
            du = stats.get("display_unit", "")
            suffix = f" {du}" if du else ""

            def _fmt(val: Any) -> str:
                if val is None:
                    return "N/A"
                if isinstance(val, float):
                    return f"{val:.4f}{suffix}" if abs(val) < 10 else f"{val:.1f}{suffix}"
                return str(val)

            lines.append(
                f"| {metric_name} | {cat} "
                f"| {_fmt(stats.get('avg'))} "
                f"| {_fmt(stats.get('p90'))} "
                f"| {_fmt(stats.get('p95'))} "
                f"| {_fmt(stats.get('min'))} "
                f"| {_fmt(stats.get('max'))} "
                f"| {stats.get('trend', 'N/A')} "
                f"| {stats.get('samples', 0)} |"
            )
        lines.append("")

    kpi_insights = kpi_analysis.get("kpi_insights", [])
    if kpi_insights:
        lines.append("## Insights")
        lines.append("")
        for insight in kpi_insights:
            lines.append(f"- {insight}")
        lines.append("")

    return "\n".join(lines)
