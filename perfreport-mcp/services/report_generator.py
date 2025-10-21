"""
services/report_generator.py
Performance report generation from PerfAnalysis MCP outputs
"""
import json
import asyncio
import pypandoc
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from fastmcp import Context

# Import config at module level (global)
from utils.config import load_config
from utils.file_utils import (
    _load_json_safe,
    _load_text_safe,
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

# -----------------------------------------------
# Main Performance Report functions
# ----------------------------------------------- 
async def generate_performance_test_report(run_id: str, ctx: Context, format: str = "md", template: Optional[str] = None) -> Dict:
    """
    Generate performance test report from PerfAnalysis outputs.
    
    Args:
        run_id: Test run identifier
        ctx: Workflow context for chaining
        format: Output format ('md', 'pdf', 'docx')
        template: Optional template name
        
    Returns:
        Dict with metadata and paths
    """
    try:
        generated_timestamp = datetime.now().isoformat()
        warnings = []
        missing_sections = []
        
        # Validate run_id path
        run_path = ARTIFACTS_PATH / run_id
        analysis_path = run_path / "analysis"
        
        if not run_path.exists():
            await ctx.error(f"Run path not found: {run_path}")
            return {
                "run_id": run_id,
                "error": f"Run path not found: {run_path}",
                "generated_timestamp": generated_timestamp
            }
        
        if not analysis_path.exists():
            await ctx.error(f"Analysis path not found: {analysis_path}")
            return {
                "run_id": run_id,
                "error": f"Analysis path not found: {analysis_path}",
                "generated_timestamp": generated_timestamp
            }
        
        # Load analysis files
        source_files = {}
        perf_data = await _load_json_safe(
            analysis_path / "performance_analysis.json",
            "performance_analysis",
            source_files,
            warnings,
            missing_sections
        )
        
        infra_data = await _load_json_safe(
            analysis_path / "infrastructure_analysis.json",
            "infrastructure_analysis",
            source_files,
            warnings,
            missing_sections
        )
        
        corr_data = await _load_json_safe(
            analysis_path / "correlation_analysis.json",
            "correlation_analysis",
            source_files,
            warnings,
            missing_sections
        )
        
        # Load markdown summaries (optional)
        perf_summary_md = await _load_text_safe(
            analysis_path / "performance_summary.md",
            "performance_summary_md",
            source_files,
            warnings
        )
        
        infra_summary_md = await _load_text_safe(
            analysis_path / "infrastructure_summary.md",
            "infrastructure_summary_md",
            source_files,
            warnings
        )
        
        corr_summary_md = await _load_text_safe(
            analysis_path / "correlation_analysis.md",
            "correlation_analysis_md",
            source_files,
            warnings
        )
        
        # Select template
        template_name = template or "default_report_template.md"
        template_path = TEMPLATES_PATH / template_name
        
        if not template_path.exists():
            await ctx.error(f"Template not found: {template_name}")
            return {
                "run_id": run_id,
                "error": f"Template not found: {template_name}",
                "generated_timestamp": generated_timestamp
            }
        
        template_content = await _load_text_file(template_path)
        
        # Build context for template
        context = _build_report_context(
            run_id,
            generated_timestamp,
            perf_data,
            infra_data,
            corr_data,
            perf_summary_md,
            infra_summary_md,
            corr_summary_md
        )
        
        # Extract key metrics for metadata (needed for comparison reports)
        overall_stats = {}
        sla_analysis = {}
        api_violations = []

        if perf_data:
            overall_stats = perf_data.get("overall_stats", {})
            sla_analysis = perf_data.get("sla_analysis", {})
            
            # Extract SLA violators
            api_analysis = perf_data.get("api_analysis", {})
            for api_name, stats in api_analysis.items():
                if not stats.get("sla_compliant", True):
                    api_violations.append({
                        "api_name": api_name,
                        "avg_response_time": stats.get("avg_response_time", 0),
                        "sla_threshold": stats.get("sla_threshold_ms", 5000),
                        "error_rate": stats.get("error_rate", 0)
                    })

        # Extract infrastructure service-level details
        infra_services = []
        if infra_data:
            detailed = infra_data.get("detailed_metrics", {})
            k8s = detailed.get("kubernetes", {})
            services = k8s.get("services", {})
            
            for service_name, service_data in services.items():
                cpu_analysis = service_data.get("cpu_analysis", {})
                mem_analysis = service_data.get("memory_analysis", {})
                res_alloc = service_data.get("resource_allocation", {})
                
                infra_services.append({
                    "service_name": service_name,
                    "cpu_peak_pct": cpu_analysis.get("peak_utilization_pct", 0),
                    "cpu_avg_pct": cpu_analysis.get("avg_utilization_pct", 0),
                    "memory_peak_pct": mem_analysis.get("peak_utilization_pct", 0),
                    "memory_avg_pct": mem_analysis.get("avg_utilization_pct", 0),
                    "cpu_cores": res_alloc.get("cpus", 0),
                    "memory_gb": res_alloc.get("memory_gb", 0)
                })

        # Extract correlation insights
        correlation_insights = []
        if corr_data:
            significant_corr = corr_data.get("significant_correlations", [])
            for corr in significant_corr:
                correlation_insights.append({
                    "type": corr.get("type", "Unknown"),
                    "interpretation": corr.get("interpretation", "N/A"),
                    "strength": corr.get("strength", "N/A")
                })

        # Render template
        report_markdown = _render_template(template_content, context)
        
        # Count chart placeholders
        chart_placeholder_count = report_markdown.count("[CHART_PLACEHOLDER")
        
        # Save markdown report
        reports_dir = run_path / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        report_name = f"performance_report_{run_id}.md"
        md_path = reports_dir / report_name
        await _save_text_file(md_path, report_markdown)
        
        # Convert to requested format
        final_path = md_path
        if format == "pdf":
            final_path = await _convert_to_pdf(md_path, reports_dir, run_id)
        elif format == "docx":
            final_path = await _convert_to_docx(md_path, reports_dir, run_id)

        # Define metadata path
        metadata_path = reports_dir / f"report_metadata_{run_id}.json"

        # Build response
        response = {
            "run_id": run_id,
            "report_name": report_name if format == "md" else final_path.name,
            "report_path": str(final_path),
            "metadata_path": str(metadata_path),
            "generated_timestamp": generated_timestamp,
            "mcp_version": MCP_VERSION,
            "format": format,
            "template_used": template_name,
            "source_files": source_files,
            "missing_sections": missing_sections,
            "warnings": warnings,
            "chart_placeholders": chart_placeholder_count,
        }
        
        # Build comprehensive metadata for programmatic use
        metadata = {
            # Include basic response info
            **response,
            
            # Add detailed metrics for comparison report generator
            "test_config": {
                "test_date": generated_timestamp,
                "test_duration": overall_stats.get("test_duration", 0),
                "total_samples": overall_stats.get("total_samples", 0),
                "success_rate": overall_stats.get("success_rate", 0),
                "environment": context.get("ENVIRONMENT", "Unknown"),
                "test_type": context.get("TEST_TYPE", "Load Test")
            },
            
            "performance_metrics": {
                "avg_response_time": overall_stats.get("avg_response_time", 0),
                "min_response_time": overall_stats.get("min_response_time", 0),
                "max_response_time": overall_stats.get("max_response_time", 0),
                "median_response_time": overall_stats.get("median_response_time", 0),
                "p90_response_time": overall_stats.get("p90_response_time", 0),
                "p95_response_time": overall_stats.get("p95_response_time", 0),
                "p99_response_time": overall_stats.get("p99_response_time", 0),
                "avg_throughput": overall_stats.get("avg_throughput", 0),
                "peak_throughput": overall_stats.get("peak_throughput", overall_stats.get("avg_throughput", 0)),
                "error_count": overall_stats.get("error_count", 0),
                "error_rate": overall_stats.get("error_rate", 0),
                "top_error_type": overall_stats.get("top_error_type", "N/A")
            },
            
            "infrastructure_metrics": {
                "services": infra_services,
                "summary": {
                    "cpu_peak_pct": _safe_float(context.get("PEAK_CPU_USAGE")),
                    "cpu_avg_pct": _safe_float(context.get("AVG_CPU_USAGE")),
                    "memory_peak_pct": _safe_float(context.get("PEAK_MEMORY_USAGE")),
                    "memory_avg_pct": _safe_float(context.get("AVG_MEMORY_USAGE")),
                    "cpu_cores_allocated": _safe_float(context.get("CPU_CORES_ALLOCATED")),
                    "memory_allocated_gb": _safe_float(context.get("MEMORY_ALLOCATED"))
                }
            },
            
            "sla_analysis": {
                "sla_threshold_ms": sla_analysis.get("sla_threshold_ms", 5000),
                "compliant_apis": sla_analysis.get("compliant_apis", 0),
                "non_compliant_apis": sla_analysis.get("non_compliant_apis", 0),
                "compliance_rate": sla_analysis.get("compliance_rate", 100.0),
                "violations": api_violations
            },
            
            "correlation_insights": {
                "significant_correlations": correlation_insights,
                "correlation_summary": corr_data.get("insights", "") if corr_data else ""
            },
            
            "bugs_created": []  # Placeholder for future enhancement
        }

        # Save metadata JSON
        await _save_json_file(metadata_path, metadata)

        return response
        
    except Exception as e:
        return {
            "run_id": run_id,
            "error": f"Report generation failed: {str(e)}",
            "generated_timestamp": datetime.now().isoformat()
        }

# -----------------------------------------------
# Report generation functions
# ----------------------------------------------- 
def _build_report_context(
    run_id: str,
    timestamp: str,
    perf_data: Optional[Dict],
    infra_data: Optional[Dict],
    corr_data: Optional[Dict],
    perf_md: Optional[str],
    infra_md: Optional[str],
    corr_md: Optional[str]
) -> Dict:
    """Build context dictionary for template rendering"""
    
    context = {
        "RUN_ID": run_id,
        "GENERATED_TIMESTAMP": timestamp,
        "MCP_VERSION": MCP_VERSION,
        "ENVIRONMENT": "Unknown",
        "TEST_TYPE": "Load Test"
    }
    
    # Extract performance data
    if perf_data:
        overall = perf_data.get("overall_stats", {})
        context.update({
            "TOTAL_SAMPLES": overall.get("total_samples", "N/A"),
            "SUCCESS_RATE": f"{overall.get('success_rate', 0):.2f}",
            "AVG_RESPONSE_TIME": f"{overall.get('avg_response_time', 0):.2f}",
            "MIN_RESPONSE_TIME": f"{overall.get('min_response_time', 0):.2f}",
            "MAX_RESPONSE_TIME": f"{overall.get('max_response_time', 0):.2f}",
            "MEDIAN_RESPONSE_TIME": f"{overall.get('median_response_time', 0):.2f}",
            "P90_RESPONSE_TIME": f"{overall.get('p90_response_time', 0):.2f}",
            "P95_RESPONSE_TIME": f"{overall.get('p95_response_time', 0):.2f}",
            "P99_RESPONSE_TIME": f"{overall.get('p99_response_time', 0):.2f}",
            "AVG_THROUGHPUT": f"{overall.get('avg_throughput', 0):.2f}",
            "TEST_DURATION": f"{overall.get('test_duration', 0)} seconds",
            "PEAK_THROUGHPUT": f"{overall.get('avg_throughput', 0):.2f}"
        })
        
        # Build API performance table
        context["API_PERFORMANCE_TABLE"] = _build_api_table(perf_data.get("api_analysis", {}))
        
        # SLA summary
        context["SLA_SUMMARY"] = _build_sla_summary(perf_data.get("sla_analysis", {}))
    else:
        _set_na_values(context, [
            "TOTAL_SAMPLES", "SUCCESS_RATE", "AVG_RESPONSE_TIME",
            "MIN_RESPONSE_TIME", "MAX_RESPONSE_TIME", "MEDIAN_RESPONSE_TIME",
            "P90_RESPONSE_TIME", "P95_RESPONSE_TIME", "P99_RESPONSE_TIME",
            "AVG_THROUGHPUT", "TEST_DURATION", "PEAK_THROUGHPUT"
        ])
        context["API_PERFORMANCE_TABLE"] = "No performance data available"
        context["SLA_SUMMARY"] = "No SLA data available"
    
    # Extract infrastructure data
    if infra_data:
        summary = infra_data.get("infrastructure_summary", {})
        environments_analyzed = infra_data.get("environments_analyzed", [])
        # Flatten and deduplicate environments, then stringify
        flat_envs: List[str] = []
        for item in environments_analyzed:
            if isinstance(item, list):
                flat_envs.extend([str(x) for x in item])
            else:
                flat_envs.append(str(item))
        seen = set()
        unique_envs: List[str] = []
        for e in flat_envs:
            if e and e not in seen:
                unique_envs.append(e)
                seen.add(e)
        env_str = ", ".join(unique_envs) if unique_envs else "Unknown"
        
        # Find peak CPU/Memory from detailed metrics
        cpu_peak, cpu_avg, mem_peak, mem_avg, cpu_cores, mem_gb = _extract_infra_peaks(infra_data)
        
        context.update({
            "ENVIRONMENT": env_str,
            "PEAK_CPU_USAGE": f"{cpu_peak:.2f}",
            "AVG_CPU_USAGE": f"{cpu_avg:.2f}",
            "CPU_CORES_ALLOCATED": f"{cpu_cores:.2f}",
            "PEAK_MEMORY_USAGE": f"{mem_peak:.2f}",
            "AVG_MEMORY_USAGE": f"{mem_avg:.2f}",
            "MEMORY_ALLOCATED": f"{mem_gb:.2f}",
            "INFRASTRUCTURE_SUMMARY": infra_md or "No infrastructure summary available"
        })
    else:
        _set_na_values(context, [
            "PEAK_CPU_USAGE", "AVG_CPU_USAGE", "CPU_CORES_ALLOCATED",
            "PEAK_MEMORY_USAGE", "AVG_MEMORY_USAGE", "MEMORY_ALLOCATED"
        ])
        context["INFRASTRUCTURE_SUMMARY"] = "No infrastructure data available"
    
    # Extract correlation data
    if corr_data:
        context.update({
            "CORRELATION_SUMMARY": corr_md or _build_correlation_summary(corr_data),
            "CORRELATION_DETAILS": _build_correlation_details(corr_data)
        })
    else:
        context["CORRELATION_SUMMARY"] = "No correlation analysis available"
        context["CORRELATION_DETAILS"] = ""
    
    # Executive summary and other sections
    context["EXECUTIVE_SUMMARY"] = _build_executive_summary(perf_data, infra_data, corr_data)
    context["KEY_OBSERVATIONS"] = _build_key_observations(perf_data, infra_data)
    context["ISSUES_TABLE"] = _build_issues_table(perf_data)
    context["BOTTLENECK_ANALYSIS"] = _build_bottleneck_analysis(corr_data, infra_data)
    context["RECOMMENDATIONS"] = _build_recommendations(perf_data, infra_data, corr_data)
    context["SOURCE_FILES_LIST"] = "See metadata JSON for complete source file list"
    
    return context

def _render_template(template: str, context: Dict) -> str:
    """Render template with context using {{}} placeholders"""
    rendered = template
    for key, value in context.items():
        placeholder = "{{" + key + "}}"
        rendered = rendered.replace(placeholder, str(value))
    return rendered

def _build_api_table(api_analysis: Dict) -> str:
    """Build Markdown table for API performance"""
    if not api_analysis:
        return "No API data available"
    
    lines = [
        "| API Name | Samples | Avg (ms) | Min (ms) | Max (ms) | 95th (ms) | Error Rate | SLA Met |",
        "|----------|---------|----------|----------|----------|-----------|------------|---------|"
    ]
    
    for api_name, stats in api_analysis.items():
        line = (
            f"| {api_name} | "
            f"{stats.get('samples', 0)} | "
            f"{stats.get('avg_response_time', 0):.2f} | "
            f"{stats.get('min_response_time', 0):.2f} | "
            f"{stats.get('max_response_time', 0):.2f} | "
            f"{stats.get('p95_response_time', 0):.2f} | "
            f"{stats.get('error_rate', 0):.2f}% | "
            f"{'✅' if stats.get('sla_compliant', False) else '❌'} |"
        )
        lines.append(line)
    
    return "\n".join(lines)

def _build_sla_summary(sla_analysis: Dict) -> str:
    """Build SLA compliance summary"""
    if not sla_analysis:
        return "No SLA analysis available"
    
    total = sla_analysis.get("total_apis", 0)
    compliant = sla_analysis.get("compliant_apis", 0)
    compliance_rate = sla_analysis.get("compliance_rate", 0)
    
    return f"**SLA Compliance:** {compliant}/{total} APIs met SLA ({compliance_rate:.1f}%)"

def _build_executive_summary(perf_data: Optional[Dict], infra_data: Optional[Dict], corr_data: Optional[Dict]) -> str:
    """Generate executive summary"""
    if not perf_data:
        return "Performance test completed. Detailed analysis data not available."
    
    overall = perf_data.get("overall_stats", {})
    success_rate = overall.get("success_rate", 0)
    avg_rt = overall.get("avg_response_time", 0)
    
    summary = f"Performance test completed with {success_rate:.1f}% success rate and average response time of {avg_rt:.2f}ms. "
    
    if success_rate >= 99.5:
        summary += "Test performed exceptionally well with minimal errors. "
    elif success_rate >= 95:
        summary += "Test performed well with acceptable error rates. "
    else:
        summary += "Test experienced elevated error rates requiring investigation. "
    
    return summary

def _build_key_observations(perf_data: Optional[Dict], infra_data: Optional[Dict]) -> str:
    """Build key observations bullets"""
    observations = []
    
    if perf_data:
        overall = perf_data.get("overall_stats", {})
        if overall.get("success_rate", 0) >= 99:
            observations.append("- Excellent success rate observed")
        if overall.get("error_count", 0) > 0:
            observations.append(f"- {overall.get('error_count', 0)} errors detected during test execution")
    
    if infra_data:
        observations.append("- Infrastructure metrics captured and analyzed")
    
    return "\n".join(observations) if observations else "- Test completed successfully"

def _build_issues_table(perf_data: Optional[Dict]) -> str:
    """Build issues table from error data"""
    if not perf_data:
        return "No issues data available"
    
    overall = perf_data.get("overall_stats", {})
    error_count = overall.get("error_count", 0)
    
    if error_count == 0:
        return "**No issues detected during test execution**"
    
    return f"| Issue Type | Count |\n|------------|-------|\n| Errors | {error_count} |"

def _build_correlation_summary(corr_data: Dict) -> str:
    """Build correlation summary text"""
    correlations = corr_data.get("significant_correlations", [])
    if not correlations:
        return "No significant correlations found between performance and infrastructure metrics."
    
    summary = f"Found {len(correlations)} significant correlation(s):\n"
    for corr in correlations:
        summary += f"- {corr.get('type', 'Unknown')}: {corr.get('interpretation', 'N/A')}\n"
    
    return summary

def _build_correlation_details(corr_data: Dict) -> str:
    """Build detailed correlation information"""
    matrix = corr_data.get("correlation_matrix", {})
    if not matrix:
        return "No correlation matrix data available"
    
    lines = ["| Metric Pair | Correlation Coefficient |", "|-------------|------------------------|"]
    
    for key, value in matrix.items():
        lines.append(f"| {key} | {value:.4f} |")
    
    return "\n".join(lines)

def _build_bottleneck_analysis(corr_data: Optional[Dict], infra_data: Optional[Dict]) -> str:
    """Build bottleneck identification section"""
    if not corr_data and not infra_data:
        return "Insufficient data for bottleneck analysis"
    
    analysis = "Based on correlation and infrastructure analysis:\n"
    
    if corr_data:
        insights = corr_data.get("insights", "")
        if insights:
            analysis += f"\n{insights}\n"
    
    return analysis

def _build_recommendations(perf_data: Optional[Dict], infra_data: Optional[Dict], corr_data: Optional[Dict]) -> str:
    """Generate recommendations based on analysis"""
    recommendations = []
    
    if perf_data:
        overall = perf_data.get("overall_stats", {})
        if overall.get("error_rate", 0) > 1:
            recommendations.append("- Investigate and resolve error causes to improve reliability")
        
        avg_rt = overall.get("avg_response_time", 0)
        if avg_rt > 5000:
            recommendations.append("- Optimize response times to meet SLA requirements")
    
    if not recommendations:
        recommendations.append("- Continue monitoring performance trends")
        recommendations.append("- Maintain current system configuration")
    
    return "\n".join(recommendations)

def _extract_infra_peaks(infra_data: Dict) -> tuple:
    """Extract peak CPU/Memory values from infrastructure data"""
    cpu_peak = 0.0
    cpu_avg = 0.0
    mem_peak = 0.0
    mem_avg = 0.0
    cpu_cores = 0.0
    mem_gb = 0.0
    
    detailed = infra_data.get("detailed_metrics", {})
    k8s = detailed.get("kubernetes", {})
    services = k8s.get("services", {})
    
    for service_data in services.values():
        cpu_analysis = service_data.get("cpu_analysis", {})
        mem_analysis = service_data.get("memory_analysis", {})
        
        cpu_peak = max(cpu_peak, cpu_analysis.get("peak_utilization_pct", 0))
        cpu_avg = max(cpu_avg, cpu_analysis.get("avg_utilization_pct", 0))
        mem_peak = max(mem_peak, mem_analysis.get("peak_utilization_pct", 0))
        mem_avg = max(mem_avg, mem_analysis.get("avg_utilization_pct", 0))
        
        res_alloc = service_data.get("resource_allocation", {})
        cpu_cores = max(cpu_cores, res_alloc.get("cpus", 0))
        mem_gb = max(mem_gb, res_alloc.get("memory_gb", 0))
    
    return cpu_peak, cpu_avg, mem_peak, mem_avg, cpu_cores, mem_gb

def _set_na_values(context: Dict, keys: List[str]):
    """Set N/A for missing keys"""
    for key in keys:
        context[key] = "N/A"

def _safe_float(value, default=0.0):
    """Safely convert value to float, handling 'N/A' strings"""
    if value == "N/A" or value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default
