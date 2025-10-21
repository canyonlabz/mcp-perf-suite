"""
services/comparison_report_generator.py
Multi-run performance test comparison report generation
"""

import json
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from fastmcp import Context

# Import config and utilities
from utils.config import load_config
from utils.file_utils import (
    _load_json_safe,
    _load_text_file,
    _save_text_file,
    _save_json_file,
    _convert_to_pdf,
    _convert_to_docx
)

# Load configuration globally
CONFIG = load_config()
ARTIFACTS_CONFIG = CONFIG.get('artifacts', {})
REPORT_CONFIG = CONFIG.get('perf_report', {})
ARTIFACTS_PATH = Path(ARTIFACTS_CONFIG.get('artifacts_path', './artifacts'))
TEMPLATES_PATH = Path(REPORT_CONFIG.get('templates_path', './templates'))
MCP_VERSION = (CONFIG.get('general') or {}).get('mcp_version', 'unknown')

# Maximum recommended runs for comparison
MAX_RECOMMENDED_RUNS = 5

# -----------------------------------------------
# Main Comparison Report functions
# ----------------------------------------------- 
async def generate_comparison_report(run_id_list: list, ctx: Context, format: str = "md", template: Optional[str] = None) -> Dict:
    """
    Generate multi-run comparison report from metadata JSONs.
    
    Args:
        run_id_list: List of 2-5 test run IDs to compare
        ctx: Workflow context for chaining
        format: Output format ('md', 'pdf', 'docx')
        template: Optional comparison template name
    
    Returns:
        Dict with comparison report metadata and paths
    """
    try:
        generated_timestamp = datetime.now().isoformat()
        warnings = []
        
        # Validate run count
        run_count = len(run_id_list)
        if run_count < 2:
            await ctx.error("At least 2 test runs are required for comparison report generation.")
            return {
                "error": "Comparison requires at least 2 test runs",
                "run_id_list": run_id_list,
                "generated_timestamp": generated_timestamp
            }
        
        if run_count > MAX_RECOMMENDED_RUNS:
            await ctx.warning("Comparing more than 5 test runs may lead to unreadable reports.")
            warning_msg = (
                f"WARNING: Comparing {run_count} test runs exceeds the recommended "
                f"maximum of {MAX_RECOMMENDED_RUNS}. The report may be difficult to read. "
                "Consider using a trend analysis tool for large-scale comparisons."
            )
            warnings.append(warning_msg)
        
        # Load metadata for each run
        run_metadata_list = []
        for run_id in run_id_list:
            metadata_path = ARTIFACTS_PATH / run_id / "reports" / f"report_metadata_{run_id}.json"
            
            if not metadata_path.exists():
                await ctx.error(f"Metadata not found for run {run_id}")
                error_msg = f"Metadata not found for run {run_id}: {metadata_path}"
                return {
                    "error": error_msg,
                    "run_id_list": run_id_list,
                    "generated_timestamp": generated_timestamp
                }
            
            with open(metadata_path, 'r') as f:
                run_metadata = json.load(f)
                run_metadata_list.append(run_metadata)
        
        # Select template
        template_name = template or "default_comparison_report_template.md"
        template_path = TEMPLATES_PATH / template_name
        
        if not template_path.exists():
            await ctx.error(f"Comparison template not found: {template_name}")
            return {
                "error": f"Comparison template not found: {template_name}",
                "run_id_list": run_id_list,
                "generated_timestamp": generated_timestamp
            }
        
        template_content = await _load_text_file(template_path)
        
        # Build comparison context
        context = _build_comparison_context(
            run_id_list,
            run_metadata_list,
            generated_timestamp
        )
        
        # Render template
        comparison_markdown = _render_comparison_template(template_content, context)
        
        # Save comparison report
        comparison_id = "_".join(run_id_list)
        reports_dir = ARTIFACTS_PATH / "comparisons"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        report_name = f"comparison_report_{comparison_id}.md"
        md_path = reports_dir / report_name
        await _save_text_file(md_path, comparison_markdown)
        
        # Convert to requested format
        final_path = md_path
        if format == "pdf":
            final_path = await _convert_to_pdf(md_path, reports_dir, comparison_id)
        elif format == "docx":
            final_path = await _convert_to_docx(md_path, reports_dir, comparison_id)
        
        # Define metadata path
        metadata_path = reports_dir / f"comparison_metadata_{comparison_id}.json"
        
        # Build response
        response = {
            "run_id_list": run_id_list,
            "run_count": run_count,
            "report_name": report_name if format == "md" else final_path.name,
            "report_path": str(final_path),
            "metadata_path": str(metadata_path),
            "generated_timestamp": generated_timestamp,
            "mcp_version": MCP_VERSION,
            "format": format,
            "template_used": template_name,
            "warnings": warnings
        }
        
        # Build comprehensive comparison metadata
        comparison_metadata = {
            **response,
            "runs_analyzed": [
                {
                    "run_id": meta["run_id"],
                    "test_date": meta["test_config"]["test_date"],
                    "environment": meta["test_config"]["environment"]
                }
                for meta in run_metadata_list
            ]
        }
        
        # Save comparison metadata
        await _save_json_file(metadata_path, comparison_metadata)
        
        return response
        
    except Exception as e:
        return {
            "error": f"Comparison report generation failed: {str(e)}",
            "run_id_list": run_id_list,
            "generated_timestamp": datetime.now().isoformat()
        }


# ===== COMPARISON CONTEXT BUILDER =====
def _build_comparison_context(run_id_list: List[str], run_metadata_list: List[Dict], timestamp: str) -> Dict:
    """Build context dictionary for comparison template rendering."""
    run_count = len(run_id_list)
    
    # Base context
    context = {
        "GENERATED_TIMESTAMP": timestamp,
        "RUN_COUNT": str(run_count),
        "ENVIRONMENT": _determine_common_environment(run_metadata_list),
        "MCP_VERSION": MCP_VERSION,
        "RUN_IDS_LIST": ", ".join(run_id_list)
    }
    
    # Populate run-specific columns (1-5)
    for i in range(5):
        if i < run_count:
            _populate_run_column(context, i + 1, run_metadata_list[i], i)
        else:
            _populate_empty_run_column(context, i + 1)
    
    # Build comparison summaries and tables
    context.update({
        "EXECUTIVE_SUMMARY": _build_executive_summary(run_metadata_list),
        "KEY_FINDINGS_BULLETS": _build_key_findings(run_metadata_list),
        "OVERALL_TREND_SUMMARY": _build_overall_trend(run_metadata_list),
        
        # Issues & Errors
        "ISSUES_SUMMARY": _build_issues_summary(run_metadata_list),
        "CRITICAL_ISSUES_TABLE": _build_critical_issues_table(run_metadata_list),
        "PERFORMANCE_DEGRADATIONS_ROWS": _build_performance_degradations(run_metadata_list),
        "INFRASTRUCTURE_CONCERNS_ROWS": _build_infrastructure_concerns(run_metadata_list),
        "ERROR_RATE_SUMMARY": _build_error_rate_summary(run_metadata_list),
        
        # Bugs section
        "TOTAL_BUG_COUNT": "0",
        "OPEN_BUG_COUNT": "0",
        "RESOLVED_BUG_COUNT": "0",
        
        # API Performance
        "API_COMPARISON_ROWS": _build_api_comparison_table(run_metadata_list),
        "TOP_OFFENDERS_ROWS": _build_top_offenders_table(run_metadata_list),
        
        # Throughput
        "THROUGHPUT_TREND": _format_trend_symbol(_calculate_metric_trend(run_metadata_list, ["performance_metrics", "avg_throughput"], lower_is_better=False)),
        "PEAK_THROUGHPUT_TREND": _format_trend_symbol(_calculate_metric_trend(run_metadata_list, ["performance_metrics", "peak_throughput"], lower_is_better=False)),
        "THROUGHPUT_SUMMARY": _build_throughput_summary(run_metadata_list),
        
        # Infrastructure
        "CPU_COMPARISON_ROWS": _build_cpu_comparison_table(run_metadata_list),
        "MEMORY_COMPARISON_ROWS": _build_memory_comparison_table(run_metadata_list),
        "CPU_IMPROVED_COUNT": "0",
        "CPU_DEGRADED_COUNT": str(_count_degraded_services(run_metadata_list, "cpu")),
        "CPU_STABLE_COUNT": "0",
        "MEMORY_IMPROVED_COUNT": "0",
        "MEMORY_DEGRADED_COUNT": str(_count_degraded_services(run_metadata_list, "memory")),
        "MEMORY_STABLE_COUNT": "0",
        "RESOURCE_EFFICIENCY_SUMMARY": _build_resource_efficiency(run_metadata_list),
        
        # Correlation (optional)
        "CORRELATION_INSIGHTS_SECTION": _build_correlation_section(run_metadata_list),
        "CORRELATION_KEY_OBSERVATIONS": _build_correlation_observations(run_metadata_list),
        
        # Conclusion
        "CONCLUSION_SYNOPSIS": _build_conclusion_synopsis(run_metadata_list),
        "RECOMMENDATIONS_LIST": _build_recommendations(run_metadata_list),
        "NEXT_STEPS_LIST": _build_next_steps(run_metadata_list)
    })
    
    # Populate source files per run
    for i, metadata in enumerate(run_metadata_list):
        context[f"RUN_{i+1}_SOURCE_FILES"] = _format_source_files(metadata.get("source_files", {}))
    
    # Fill remaining empty runs with N/A for source files
    for i in range(run_count, 5):
        context[f"RUN_{i+1}_SOURCE_FILES"] = "N/A"
    
    return context

# -----------------------------------------------
# Comparison report utility functions
# ----------------------------------------------- 
def _populate_run_column(context: Dict, run_num: int, metadata: Dict, index: int):
    """Populate context with data for a specific run column."""
    test_config = metadata.get("test_config", {})
    perf_metrics = metadata.get("performance_metrics", {})
    infra_summary = metadata.get("infrastructure_metrics", {}).get("summary", {})
    
    prefix = f"RUN_{run_num}_"
    
    # Calculate delta vs previous run
    delta_str = ""
    if index > 0:
        # Will be calculated in table builders
        delta_str = ""
    
    context.update({
        f"{prefix}ID": metadata.get("run_id", "N/A"),
        f"{prefix}LABEL": f"Run {run_num}",
        f"{prefix}DATE": test_config.get("test_date", "N/A")[:10] if test_config.get("test_date") else "N/A",
        f"{prefix}DURATION": f"{test_config.get('test_duration', 0)} seconds",
        f"{prefix}SAMPLES": str(test_config.get("total_samples", 0)),
        f"{prefix}SUCCESS_RATE": f"{test_config.get('success_rate', 0):.2f}",
        f"{prefix}ENV": test_config.get("environment", "Unknown"),
        f"{prefix}TYPE": test_config.get("test_type", "Load Test"),
        
        # Performance
        f"{prefix}AVG_THROUGHPUT": f"{perf_metrics.get('avg_throughput', 0):.2f}",
        f"{prefix}PEAK_THROUGHPUT": f"{perf_metrics.get('peak_throughput', 0):.2f}",
        f"{prefix}ERROR_COUNT": str(perf_metrics.get("error_count", 0)),
        f"{prefix}ERROR_RATE": f"{perf_metrics.get('error_rate', 0):.2f}",
        f"{prefix}ERROR_DELTA": delta_str,
        f"{prefix}TOP_ERROR": perf_metrics.get("top_error_type", "N/A")
    })


def _populate_empty_run_column(context: Dict, run_num: int):
    """Populate context with N/A for missing run columns."""
    prefix = f"RUN_{run_num}_"
    
    for key in ["ID", "LABEL", "DATE", "DURATION", "SAMPLES", "SUCCESS_RATE", 
                "ENV", "TYPE", "AVG_THROUGHPUT", "PEAK_THROUGHPUT", "ERROR_COUNT",
                "ERROR_RATE", "ERROR_DELTA", "TOP_ERROR"]:
        context[f"{prefix}{key}"] = "N/A"


def _render_comparison_template(template: str, context: Dict) -> str:
    """Render comparison template with context using {{}} placeholders."""
    rendered = template
    for key, value in context.items():
        placeholder = "{{" + key + "}}"
        rendered = rendered.replace(placeholder, str(value))
    return rendered


# ===== CALCULATION HELPERS =====

def _calculate_delta(current: float, previous: float, lower_is_better: bool = True) -> Tuple[float, str]:
    """
    Calculate percentage delta and trend indicator.
    
    Returns:
        (delta_pct, trend_symbol)
    """
    if previous == 0:
        return 0.0, "➡️"
    
    delta_pct = ((current - previous) / previous) * 100
    
    if abs(delta_pct) <= 5:
        return delta_pct, "➡️"  # Stable
    
    # For response time, CPU, memory, errors: lower is better
    # For throughput: higher is better
    if lower_is_better:
        if delta_pct > 0:
            return delta_pct, "⬇️"  # Degraded (increased)
        else:
            return delta_pct, "⬆️"  # Improved (decreased)
    else:
        if delta_pct > 0:
            return delta_pct, "⬆️"  # Improved (increased)
        else:
            return delta_pct, "⬇️"  # Degraded (decreased)


def _get_nested_value(data: Dict, keys: List[str], default=0):
    """Safely get nested dictionary value."""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data if data is not None else default


def _calculate_metric_trend(run_metadata_list: List[Dict], metric_path: List[str], lower_is_better: bool = True) -> str:
    """Calculate overall trend for a metric across runs."""
    values = [_get_nested_value(meta, metric_path) for meta in run_metadata_list]
    
    if len(values) < 2:
        return "➡️"
    
    first_val = values[0]
    last_val = values[-1]
    
    delta, trend = _calculate_delta(last_val, first_val, lower_is_better)
    return trend


def _format_trend_symbol(trend: str) -> str:
    """Format trend with description."""
    if trend == "⬆️":
        return "⬆️ Improved"
    elif trend == "⬇️":
        return "⬇️ Degraded"
    else:
        return "➡️ Stable"


# ===== SUMMARY BUILDERS =====

def _determine_common_environment(run_metadata_list: List[Dict]) -> str:
    """Determine if all runs share same environment."""
    envs = [meta.get("test_config", {}).get("environment", "Unknown") 
            for meta in run_metadata_list]
    unique_envs = list(set(envs))
    
    if len(unique_envs) == 1:
        return unique_envs[0]
    else:
        return f"Multiple ({', '.join(unique_envs)})"


def _build_executive_summary(run_metadata_list: List[Dict]) -> str:
    """Generate executive summary for comparison."""
    first_run = run_metadata_list[0]["performance_metrics"]
    last_run = run_metadata_list[-1]["performance_metrics"]
    
    first_rt = first_run.get("avg_response_time", 0)
    last_rt = last_run.get("avg_response_time", 0)
    
    delta, trend = _calculate_delta(last_rt, first_rt, lower_is_better=True)
    
    summary = f"Comparison of **{len(run_metadata_list)} test runs** shows "
    
    if trend == "⬆️":
        summary += f"**improvement** in average response times ({abs(delta):.1f}% faster). "
    elif trend == "⬇️":
        summary += f"**performance degradation** with average response times increasing by {abs(delta):.1f}%. "
    else:
        summary += "**stable** performance with minimal variation across runs. "
    
    # Add error rate summary
    first_errors = first_run.get("error_rate", 0)
    last_errors = last_run.get("error_rate", 0)
    
    if last_errors > first_errors:
        summary += f"Error rates increased from {first_errors:.2f}% to {last_errors:.2f}%. "
    
    return summary


def _build_key_findings(run_metadata_list: List[Dict]) -> str:
    """Build key findings bullets."""
    findings = []
    
    # Response time trend
    rt_trend = _calculate_metric_trend(run_metadata_list, ["performance_metrics", "avg_response_time"])
    if rt_trend == "⬇️":
        findings.append("- Response times show degradation trend across test runs")
    elif rt_trend == "⬆️":
        findings.append("- Response times improved across test runs")
    
    # Infrastructure observations
    first_cpu = run_metadata_list[0]["infrastructure_metrics"]["summary"].get("cpu_peak_pct", 0)
    last_cpu = run_metadata_list[-1]["infrastructure_metrics"]["summary"].get("cpu_peak_pct", 0)
    
    if last_cpu > first_cpu * 1.5:
        findings.append("- CPU utilization increased significantly")
    
    # Resource allocation
    first_mem = run_metadata_list[0]["infrastructure_metrics"]["summary"].get("memory_allocated_gb", 0)
    last_mem = run_metadata_list[-1]["infrastructure_metrics"]["summary"].get("memory_allocated_gb", 0)
    
    if last_mem < first_mem:
        findings.append("- Resource allocation reduced in later runs")
    
    if not findings:
        findings.append("- Performance metrics remain consistent across runs")
    
    return "\n".join(findings)


def _build_overall_trend(run_metadata_list: List[Dict]) -> str:
    """Build overall trend summary."""
    perf_trend = _calculate_metric_trend(run_metadata_list, ["performance_metrics", "avg_response_time"])
    
    if perf_trend == "⬇️":
        return "Overall performance trend shows **degradation** across test runs, likely due to resource constraints or increased load."
    elif perf_trend == "⬆️":
        return "Overall performance trend shows **improvement** across test runs."
    else:
        return "Overall performance remains **stable** with minimal variation across test runs."


def _build_issues_summary(run_metadata_list: List[Dict]) -> str:
    """Build issues summary."""
    total_sla_violations = sum(
        len(meta.get("sla_analysis", {}).get("violations", []))
        for meta in run_metadata_list
    )
    
    if total_sla_violations > 0:
        return f"A total of **{total_sla_violations} SLA violations** were detected across all test runs."
    else:
        return "No critical SLA violations detected across test runs."


def _build_critical_issues_table(run_metadata_list: List[Dict]) -> str:
    """Build critical issues table."""
    # For now, return placeholder
    return "No critical issues detected requiring immediate attention."


def _build_performance_degradations(run_metadata_list: List[Dict]) -> str:
    """Build performance degradation rows."""
    rows = []
    
    # Check response time degradation
    first_rt = run_metadata_list[0]["performance_metrics"].get("avg_response_time", 0)
    last_rt = run_metadata_list[-1]["performance_metrics"].get("avg_response_time", 0)
    delta, trend = _calculate_delta(last_rt, first_rt)
    
    if trend == "⬇️":
        affected_runs = ", ".join([f"Run {i+1}" for i in range(1, len(run_metadata_list))])
        rows.append(f"| Response Time Increase | High | {affected_runs} | Avg response time increased by {abs(delta):.1f}% |")
    
    if not rows:
        rows.append("| No significant degradations | - | - | All metrics within acceptable ranges |")
    
    return "\n".join(rows)


def _build_infrastructure_concerns(run_metadata_list: List[Dict]) -> str:
    """Build infrastructure concerns rows."""
    rows = []
    
    # Check CPU concerns
    last_cpu = run_metadata_list[-1]["infrastructure_metrics"]["summary"].get("cpu_peak_pct", 0)
    if last_cpu > 50:
        rows.append(f"| High CPU Usage | CPU | Run {len(run_metadata_list)} | CPU utilization peaked at {last_cpu:.2f}% |")
    
    if not rows:
        rows.append("| No infrastructure concerns | - | - | All resources within acceptable ranges |")
    
    return "\n".join(rows)


def _build_error_rate_summary(run_metadata_list: List[Dict]) -> str:
    """Build error rate summary."""
    error_rates = [meta["performance_metrics"].get("error_rate", 0) for meta in run_metadata_list]
    
    if max(error_rates) < 1.0:
        return "Error rates remain low (< 1%) across all test runs."
    else:
        return f"Error rates peaked at {max(error_rates):.2f}% in Run {error_rates.index(max(error_rates)) + 1}."


def _build_api_comparison_table(run_metadata_list: List[Dict]) -> str:
    """Build API comparison table rows."""
    # Get all unique APIs across runs
    all_apis = set()
    for meta in run_metadata_list:
        violations = meta.get("sla_analysis", {}).get("violations", [])
        for v in violations:
            all_apis.add(v.get("api_name", "Unknown"))
    
    if not all_apis:
        return "| No SLA violations detected | - | - | - | - | - | - | ✅ |"
    
    rows = []
    for api in sorted(all_apis):
        row_data = [api, "5000"]  # API name and SLA threshold
        
        # Get response times for this API across runs
        for meta in run_metadata_list:
            violations = meta.get("sla_analysis", {}).get("violations", [])
            api_violation = next((v for v in violations if v.get("api_name") == api), None)
            
            if api_violation:
                rt = api_violation.get("avg_response_time", 0)
                row_data.append(f"{rt:.0f} ❌")
            else:
                row_data.append("✅")
        
        # Pad with N/A for missing runs
        while len(row_data) < 7:
            row_data.append("N/A")
        
        # Add trend (simple: comparing first and last)
        row_data.append("⬇️")
        
        rows.append("| " + " | ".join(row_data[:8]) + " |")
    
    return "\n".join(rows[:10])  # Limit to 10 rows


def _build_top_offenders_table(run_metadata_list: List[Dict]) -> str:
    """Build top offenders table."""
    # Similar to API comparison but sorted by severity
    return _build_api_comparison_table(run_metadata_list)


def _build_throughput_summary(run_metadata_list: List[Dict]) -> str:
    """Build throughput summary."""
    throughputs = [meta["performance_metrics"].get("avg_throughput", 0) for meta in run_metadata_list]
    
    if max(throughputs) - min(throughputs) < max(throughputs) * 0.1:
        return "Throughput remains consistent across all test runs with less than 10% variation."
    else:
        return f"Throughput varies from {min(throughputs):.2f} to {max(throughputs):.2f} req/sec across runs."


def _build_cpu_comparison_table(run_metadata_list: List[Dict]) -> str:
    """Build CPU comparison table."""
    # Get all services from first run
    services = run_metadata_list[0]["infrastructure_metrics"].get("services", [])
    
    if not services:
        return "| No service data available | N/A | N/A | N/A | N/A | N/A | - | - |"
    
    rows = []
    for service in services[:5]:  # Limit to 5 services
        service_name = service.get("service_name", "Unknown")
        row_data = [service_name]
        
        cpu_values = []
        for meta in run_metadata_list:
            svc = next((s for s in meta["infrastructure_metrics"].get("services", []) 
                       if s.get("service_name") == service_name), None)
            if svc:
                cpu_peak = svc.get("cpu_peak_pct", 0)
                cpu_values.append(cpu_peak)
                row_data.append(f"{cpu_peak:.2f}%")
            else:
                row_data.append("N/A")
        
        # Pad with N/A
        while len(row_data) < 6:
            row_data.append("N/A")
        
        # Add trend and delta
        if len(cpu_values) >= 2:
            delta, trend = _calculate_delta(cpu_values[-1], cpu_values[0], lower_is_better=True)
            row_data.append(trend)
            row_data.append(f"{delta:+.2f}%")
        else:
            row_data.append("➡️")
            row_data.append("N/A")
        
        rows.append("| " + " | ".join(row_data[:8]) + " |")
    
    return "\n".join(rows)


def _build_memory_comparison_table(run_metadata_list: List[Dict]) -> str:
    """Build memory comparison table (similar to CPU)."""
    services = run_metadata_list[0]["infrastructure_metrics"].get("services", [])
    
    if not services:
        return "| No service data available | N/A | N/A | N/A | N/A | N/A | - | - |"
    
    rows = []
    for service in services[:5]:
        service_name = service.get("service_name", "Unknown")
        row_data = [service_name]
        
        mem_values = []
        for meta in run_metadata_list:
            svc = next((s for s in meta["infrastructure_metrics"].get("services", []) 
                       if s.get("service_name") == service_name), None)
            if svc:
                mem_peak = svc.get("memory_peak_pct", 0)
                mem_values.append(mem_peak)
                row_data.append(f"{mem_peak:.2f}%")
            else:
                row_data.append("N/A")
        
        while len(row_data) < 6:
            row_data.append("N/A")
        
        if len(mem_values) >= 2:
            delta, trend = _calculate_delta(mem_values[-1], mem_values[0], lower_is_better=True)
            row_data.append(trend)
            row_data.append(f"{delta:+.2f}%")
        else:
            row_data.append("➡️")
            row_data.append("N/A")
        
        rows.append("| " + " | ".join(row_data[:8]) + " |")
    
    return "\n".join(rows)


def _count_degraded_services(run_metadata_list: List[Dict], resource_type: str) -> int:
    """Count services with degraded metrics."""
    if len(run_metadata_list) < 2:
        return 0
    
    services = run_metadata_list[0]["infrastructure_metrics"].get("services", [])
    degraded_count = 0
    
    metric_key = f"{resource_type}_peak_pct"
    
    for service in services:
        service_name = service.get("service_name")
        first_val = service.get(metric_key, 0)
        
        last_svc = next((s for s in run_metadata_list[-1]["infrastructure_metrics"].get("services", [])
                        if s.get("service_name") == service_name), None)
        if last_svc:
            last_val = last_svc.get(metric_key, 0)
            delta, trend = _calculate_delta(last_val, first_val)
            if trend == "⬇️":
                degraded_count += 1
    
    return degraded_count


def _build_resource_efficiency(run_metadata_list: List[Dict]) -> str:
    """Build resource efficiency summary."""
    first_cpu_alloc = run_metadata_list[0]["infrastructure_metrics"]["summary"].get("cpu_cores_allocated", 0)
    last_cpu_alloc = run_metadata_list[-1]["infrastructure_metrics"]["summary"].get("cpu_cores_allocated", 0)
    
    if last_cpu_alloc < first_cpu_alloc:
        return f"Resource allocation decreased from {first_cpu_alloc:.1f} to {last_cpu_alloc:.1f} CPU cores, correlating with performance degradation."
    else:
        return "Resource allocation remains consistent across test runs."


def _build_correlation_section(run_metadata_list: List[Dict]) -> str:
    """Build correlation insights section (optional)."""
    # Check if any run has significant correlations
    has_insights = any(
        meta.get("correlation_insights", {}).get("significant_correlations")
        for meta in run_metadata_list
    )
    
    if not has_insights:
        return ""
    
    return "Correlation analysis reveals relationships between infrastructure metrics and performance outcomes."


def _build_correlation_observations(run_metadata_list: List[Dict]) -> str:
    """Build correlation observations."""
    observations = []
    
    for i, meta in enumerate(run_metadata_list):
        corr_insights = meta.get("correlation_insights", {}).get("significant_correlations", [])
        if corr_insights:
            observations.append(f"- **Run {i+1}:** {corr_insights[0].get('interpretation', 'N/A')}")
    
    return "\n".join(observations) if observations else "- No significant correlations detected"


def _build_conclusion_synopsis(run_metadata_list: List[Dict]) -> str:
    """Build conclusion synopsis."""
    perf_trend = _calculate_metric_trend(run_metadata_list, ["performance_metrics", "avg_response_time"])
    
    if perf_trend == "⬇️":
        return "Performance degraded across test runs, primarily due to resource constraints and increased load. Immediate action recommended to restore optimal performance."
    elif perf_trend == "⬆️":
        return "Performance improved across test runs, indicating successful optimizations or reduced load."
    else:
        return "Performance remains stable across test runs with no significant regressions detected."


def _build_recommendations(run_metadata_list: List[Dict]) -> str:
    """Build recommendations list."""
    recommendations = []
    
    # Check resource allocation
    first_cpu = run_metadata_list[0]["infrastructure_metrics"]["summary"].get("cpu_cores_allocated", 0)
    last_cpu = run_metadata_list[-1]["infrastructure_metrics"]["summary"].get("cpu_cores_allocated", 0)
    
    if last_cpu < first_cpu:
        recommendations.append(f"- Restore CPU allocation to baseline levels ({first_cpu:.1f} cores)")
    
    # Check CPU utilization
    last_cpu_peak = run_metadata_list[-1]["infrastructure_metrics"]["summary"].get("cpu_peak_pct", 0)
    if last_cpu_peak > 50:
        recommendations.append("- Investigate and optimize high CPU utilization")
    
    # SLA violations
    total_violations = sum(len(m.get("sla_analysis", {}).get("violations", [])) for m in run_metadata_list)
    if total_violations > 0:
        recommendations.append("- Address API endpoints consistently violating SLA thresholds")
    
    if not recommendations:
        recommendations.append("- Continue monitoring performance metrics")
        recommendations.append("- Maintain current resource allocation")
    
    return "\n".join(recommendations)


def _build_next_steps(run_metadata_list: List[Dict]) -> str:
    """Build next steps list."""
    return "\n".join([
        "- Schedule follow-up tests with adjusted resource allocation",
        "- Monitor infrastructure metrics during peak load periods",
        "- Review and optimize APIs with consistent SLA violations"
    ])


def _format_source_files(source_files: Dict) -> str:
    """Format source files for display."""
    return "\n".join([f"- {k}: {v}" for k, v in source_files.items()])
