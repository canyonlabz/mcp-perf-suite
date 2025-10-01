# services/performance_analyzer.py
import os
import json
import csv
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from scipy import stats
from scipy.stats import pearsonr, spearmanr
import httpx
from dotenv import load_dotenv
from fastmcp import Context     # ✅ FastMCP 2.x import

from utils.config import (
    load_config,
    load_environments_config
)
from utils.file_processor import (
    load_jmeter_results,
    load_datadog_metrics,
    write_json_output,
    write_csv_output,
    write_markdown_output,
    write_performance_csv,
    write_infrastructure_csv,
    write_correlation_csv,
    write_anomalies_csv,
    format_performance_markdown,
    format_infrastructure_markdown,
    format_correlation_markdown,
    format_anomalies_markdown,
    format_bottlenecks_markdown,
    format_comparison_markdown,
    format_executive_markdown
)
from utils.statistical_analyzer import (
    perform_aggregate_analysis,
    calculate_response_time_stats,
    calculate_correlation_matrix,
    detect_statistical_anomalies,
    identify_resource_bottlenecks
)
from services.apm_analyzer import (
    perform_infrastructure_analysis,
    generate_infrastructure_outputs
)
from services.ai_analyst import (
    generate_ai_insights,
    summarize_host_metrics,
    summarize_k8s_metrics
)

# Load configuration and environment
load_dotenv()
config = load_config()
pa_config = config.get('perf_analysis', {})
apm_tool = pa_config.get('apm_tool', 'datadog').lower()
artifacts_base = config['artifacts']['artifacts_path']

# -----------------------------------------------
# Main Functions for the PerfAnalysis MCP
# -----------------------------------------------
async def analyze_blazemeter_results(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Analyze BlazeMeter test results using aggregate report data
    
    Args:
        test_run_id: The unique test run identifier
        ctx: FastMCP workflow context for chaining
        
    Returns:
        Dictionary containing comprehensive performance analysis
    """
    try:
        await ctx.info("BlazeMeter Analysis", f"Starting analysis for run {test_run_id}")
        
        # Check for aggregate report CSV (primary data source)
        blazemeter_path = Path(artifacts_base) / test_run_id / 'blazemeter'
        aggregate_csv = blazemeter_path / 'aggregate_performance_report.csv'
        
        if not aggregate_csv.exists():
            error_msg = "BlazeMeter aggregate report not found. Please run 'get_aggregate_report' first."
            await ctx.error("Missing Prerequisite", error_msg)
            return {
                "error": error_msg,
                "status": "prerequisite_missing",
                "required_step": "get_aggregate_report",
                "expected_file": str(aggregate_csv)
            }
        
        # Load aggregate performance data
        df = pd.read_csv(aggregate_csv)
        
        if df.empty:
            return {"error": "Aggregate report CSV is empty", "status": "failed"}
        
        # Setup analysis output folder
        analysis_path = Path(artifacts_base) / test_run_id / 'analysis'
        analysis_path.mkdir(parents=True, exist_ok=True)
        
        # Perform comprehensive analysis
        analysis_result = await perform_aggregate_analysis(df, test_run_id, config, ctx)
        
        # Extract key summaries for response
        overall_summary = analysis_result.get('overall_stats', {})
        statistical_summary = analysis_result.get('statistical_summary', {})
        sla_analysis = analysis_result.get('sla_analysis', {})

        # Generate output files
        output_files = await generate_performance_outputs(analysis_result, analysis_path, test_run_id, ctx)

        await ctx.info("BlazeMeter Analysis Complete",
                       f"Analysis completed for {len(df)} labels. "
                       f"Files saved to {analysis_path}")
        return {
            "status": "success",
            "test_run_id": test_run_id,
            "summary": {
                "overall_performance": overall_summary,
                "statistical_insights": statistical_summary,
                "sla_compliance": {
                    "compliance_rate": sla_analysis.get('compliance_rate'),
                    "total_apis": sla_analysis.get('total_apis'),
                    "compliant_apis": sla_analysis.get('compliant_apis'),
                    "violating_apis": sla_analysis.get('violating_apis'),
                    "sla_threshold_ms": sla_analysis.get('sla_threshold_ms')
                }
            },
            "output_files": output_files,
            "data_source": "blazemeter_aggregate_api"
        }
        
    except Exception as e:
        error_msg = f"BlazeMeter analysis failed: {str(e)}"
        await ctx.error("Analysis Error", error_msg)
        return {"error": error_msg, "status": "failed"}

async def analyze_apm_metrics(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Analyze infrastructure metrics from configurable APM tool (Datadog/Dynatrace/etc.)
    
    Args:
        test_run_id: The unique test run identifier  
        ctx: FastMCP workflow context for chaining
        
    Returns:
        Dictionary containing infrastructure metrics analysis
    """
    try:
        await ctx.info("Infrastructure Analysis", f"Starting metrics analysis for run {test_run_id}")
        
        # Get APM tool from config (future-proof for multiple APM tools)
        apm_tool = config['perf_analysis']['apm_tool']
        
        # Check for metrics data in APM-specific folder
        apm_path = Path(artifacts_base) / test_run_id / apm_tool
        
        if not apm_path.exists():
            error_msg = f"No {apm_tool} metrics folder found at {apm_path}"
            await ctx.error("Missing Metrics Data", error_msg)
            return {
                "error": error_msg,
                "status": "no_data_available",
                "expected_path": str(apm_path)
            }
        
        # Find metrics CSV files
        k8s_files = list(apm_path.glob("k8s_metrics_*.csv"))
        host_files = list(apm_path.glob("host_metrics_*.csv"))
        
        if not k8s_files and not host_files:
            error_msg = f"No metrics CSV files found in {apm_path}. Expected k8s_metrics_*.csv or host_metrics_*.csv"
            await ctx.error("No Metrics Files", error_msg)
            return {
                "error": error_msg,
                "status": "no_metrics_files",
                "expected_patterns": ["k8s_metrics_*.csv", "host_metrics_*.csv"]
            }
        
        # Load environments configuration 
        environments_config = load_environments_config(config)
        
        # Setup analysis output folder
        analysis_path = Path(artifacts_base) / test_run_id / 'analysis'
        analysis_path.mkdir(parents=True, exist_ok=True)
        
        # Perform comprehensive infrastructure analysis
        analysis_result = await perform_infrastructure_analysis(
            k8s_files, host_files, environments_config, config, test_run_id, ctx
        )
        
        # Generate output files
        output_files = await generate_infrastructure_outputs(
            analysis_result, analysis_path, test_run_id, ctx
        )
        
        await ctx.info("Infrastructure Analysis Complete",
                      f"Analysis completed for {len(k8s_files)} K8s + {len(host_files)} Host files. "
                      f"Files saved to {analysis_path}")
        
        # Return lightweight summary (not full analysis data)
        infrastructure_summary = analysis_result.get('infrastructure_summary', {})
        resource_insights = analysis_result.get('resource_insights', {})
        
        return {
            "status": "success",
            "test_run_id": test_run_id,
            "summary": {
                "infrastructure_overview": infrastructure_summary,
                "resource_utilization": resource_insights,
                "environments_analyzed": analysis_result.get('environments_analyzed', []),
                "assumptions_made": analysis_result.get('assumptions_made', [])
            },
            "output_files": output_files,
            "data_source": f"{apm_tool}_metrics"
        }
        
    except Exception as e:
        error_msg = f"Infrastructure analysis failed: {str(e)}"
        await ctx.error("Analysis Error", error_msg)
        return {"error": error_msg, "status": "failed"}

async def correlate_performance_data(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Cross-correlate BlazeMeter and Datadog data to identify relationships
    """
    try:
        # Load previous analysis results
        analysis_path = Path(artifacts_base) / test_run_id / "analysis"

        performance_file = analysis_path / 'performance_analysis.json'
        infrastructure_file = analysis_path / 'infrastructure_analysis.json'

        if not performance_file.exists():
            error_msg = "Performance analysis file not found. Run analyze_test_results first."
            await ctx.error("Missing Performance Analysis", error_msg)
            return {"error": error_msg, "status": "failed"}
            
        if not infrastructure_file.exists():
            error_msg = "Infrastructure analysis file not found. Run analyze_environment_metrics first."
            await ctx.error("Missing Infrastructure Analysis", error_msg)
            return {"error": error_msg, "status": "failed"}
        
        # Load analysis data
        with open(performance_file, 'r') as f:
            performance_data = json.load(f)
        with open(infrastructure_file, 'r') as f:
            infrastructure_data = json.load(f)
        
        # Perform correlation analysis
        correlation_results = calculate_correlation_matrix(performance_data, infrastructure_data, test_run_id)
        
        # Save correlation results
        output_file = analysis_path / 'correlation_analysis.json'
        write_json_output(correlation_results, output_file)
        
        # Save CSV matrix
        csv_file = analysis_path / 'correlation_matrix.csv'
        write_correlation_csv(correlation_results, csv_file)
        
        # Save markdown summary
        md_file = analysis_path / 'correlation_analysis.md'
        write_markdown_output(format_correlation_markdown(correlation_results), md_file)
        
        await ctx.info(f"Correlation analysis completed", f"Results saved to {output_file}")
        ctx.set_state("correlation_analysis", json.dumps(correlation_results))
        ctx.set_state("correlation_analysis_file", str(output_file))
        
        return {
            "status": "success",
            "test_run_id": test_run_id,
            "correlations": correlation_results,
            "output_files": {
                "json": str(output_file),
                "csv": str(csv_file),
                "markdown": str(md_file)
            }
        }
        
    except Exception as e:
        error_msg = f"Correlation analysis failed: {str(e)}"
        await ctx.error("Correlation Error", error_msg)
        return {"error": error_msg, "status": "failed"}

async def detect_performance_anomalies(test_run_id: str, sensitivity: str, ctx: Context) -> Dict[str, Any]:
    """
    Detect statistical anomalies in performance and infrastructure metrics
    """
    try:
        artifacts_path = Path(artifacts_base) / test_run_id
        
        # Load raw data for anomaly detection
        blazemeter_results = artifacts_path / 'blazemeter' / 'test-results.csv'
        datadog_metrics = list((artifacts_path / 'datadog').glob('*.csv'))
        
        if not blazemeter_results.exists():
            error_msg = "BlazeMeter results CSV not found for anomaly detection"
            await ctx.error("Missing Test Results", error_msg)
            return {"error": error_msg, "status": "failed"}
        
        anomalies = detect_statistical_anomalies(blazemeter_results, datadog_metrics, sensitivity)
        
        # Save anomaly results
        output_file = artifacts_path / 'anomaly_detection.json'
        write_json_output(anomalies, output_file)
        
        # Save CSV of detected anomalies
        csv_file = artifacts_path / 'detected_anomalies.csv'
        write_anomalies_csv(anomalies, csv_file)
        
        # Save markdown summary
        md_file = artifacts_path / 'anomaly_detection.md'
        write_markdown_output(format_anomalies_markdown(anomalies), md_file)
        
        await ctx.info(f"Anomaly detection completed", f"Found {len(anomalies.get('anomalies', []))} anomalies")
        ctx.set_state("anomaly_detection", json.dumps(anomalies))
        ctx.set_state("anomaly_detection_file", str(output_file))
        
        return {
            "status": "success",
            "test_run_id": test_run_id,
            "anomalies": anomalies,
            "sensitivity": sensitivity,
            "output_files": {
                "json": str(output_file),
                "csv": str(csv_file),
                "markdown": str(md_file)
            }
        }
        
    except Exception as e:
        error_msg = f"Anomaly detection failed: {str(e)}"
        await ctx.error("Anomaly Detection Error", error_msg)
        return {"error": error_msg, "status": "failed"}

async def identify_system_bottlenecks(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Identify performance bottlenecks and constraint points
    """
    try:
        artifacts_path = Path(artifacts_base) / test_run_id
        
        # Load correlation and anomaly data
        correlation_file = artifacts_path / 'correlation_analysis.json'
        anomaly_file = artifacts_path / 'anomaly_detection.json'
        
        if not correlation_file.exists():
            error_msg = "Correlation analysis required for bottleneck identification. Run correlate_test_results first."
            await ctx.error("Missing Correlation Analysis", error_msg)
            return {"error": error_msg, "status": "failed"}
        
        bottlenecks = identify_resource_bottlenecks(correlation_file, anomaly_file, test_run_id)
        
        # Save bottleneck analysis
        output_file = artifacts_path / 'bottleneck_analysis.json'
        write_json_output(bottlenecks, output_file)
        
        # Save markdown summary
        md_file = artifacts_path / 'bottleneck_analysis.md'
        write_markdown_output(format_bottlenecks_markdown(bottlenecks), md_file)
        
        await ctx.info(f"Bottleneck analysis completed", f"Identified {len(bottlenecks.get('bottlenecks', []))} bottlenecks")
        ctx.set_state("bottleneck_analysis", json.dumps(bottlenecks))
        ctx.set_state("bottleneck_analysis_file", str(output_file))
        
        return {
            "status": "success",
            "test_run_id": test_run_id,
            "bottlenecks": bottlenecks,
            "output_files": {
                "json": str(output_file),
                "markdown": str(md_file)
            }
        }
        
    except Exception as e:
        error_msg = f"Bottleneck identification failed: {str(e)}"
        await ctx.error("Bottleneck Analysis Error", error_msg)
        return {"error": error_msg, "status": "failed"}

async def compare_multiple_runs(test_run_ids: List[str], comparison_type: str, ctx: Context) -> Dict[str, Any]:
    """
    Compare multiple test runs for trend analysis (max 5 runs)
    """
    try:
        if len(test_run_ids) > 5:
            error_msg = "Maximum 5 test runs allowed for comparison"
            await ctx.error("Too Many Runs", error_msg)
            return {"error": error_msg, "status": "failed"}
        
        comparison_results = perform_multi_run_comparison(test_run_ids, comparison_type)
        
        # Save comparison results
        comparison_id = "_vs_".join(test_run_ids[:3])
        output_file = Path(artifacts_base) / f'comparison_{comparison_id}.json'
        write_json_output(comparison_results, output_file)
        
        # Save markdown summary
        md_file = Path(artifacts_base) / f'comparison_{comparison_id}.md'
        write_markdown_output(format_comparison_markdown(comparison_results), md_file)
        
        await ctx.info(f"Test run comparison completed", f"Compared {len(test_run_ids)} runs")
        ctx.set_state("comparison_results", json.dumps(comparison_results))
        ctx.set_state("comparison_file", str(output_file))
        
        return {
            "status": "success",
            "test_run_ids": test_run_ids,
            "comparison": comparison_results,
            "output_files": {
                "json": str(output_file),
                "markdown": str(md_file)
            }
        }
        
    except Exception as e:
        error_msg = f"Test run comparison failed: {str(e)}"
        await ctx.error("Comparison Error", error_msg)
        return {"error": error_msg, "status": "failed"}

async def generate_executive_summary(test_run_id: str, include_recommendations: bool, ctx: Context) -> Dict[str, Any]:
    """
    Generate executive summary with AI-powered insights using OpenAI
    """
    try:
        artifacts_path = Path(artifacts_base) / test_run_id
        
        # Gather all analysis results
        analysis_files = [
            ('performance_analysis', 'blazemeter/performance_analysis.json'),
            ('infrastructure_analysis', 'datadog/infrastructure_analysis.json'),
            ('correlation_analysis', 'correlation_analysis.json'),
            ('anomaly_detection', 'anomaly_detection.json'),
            ('bottleneck_analysis', 'bottleneck_analysis.json')
        ]
        
        combined_data = {"test_run_id": test_run_id}
        for key, file_path in analysis_files:
            full_path = artifacts_path / file_path
            if full_path.exists():
                with open(full_path, 'r') as f:
                    combined_data[key] = json.load(f)
        
        # Generate AI-powered summary if requested
        if include_recommendations:
            ai_summary = await generate_ai_insights(combined_data, test_run_id)
        else:
            ai_summary = {"message": "AI recommendations disabled"}
        
        # Create comprehensive summary
        summary = {
            "test_run_id": test_run_id,
            "generated_at": datetime.datetime.now().isoformat(),
            "analysis_summary": combined_data,
            "ai_insights": ai_summary,
            "executive_summary": create_executive_overview(combined_data)
        }
        
        # Save executive summary
        output_file = artifacts_path / 'executive_summary.json'
        write_json_output(summary, output_file)
        
        # Save markdown executive report
        md_file = artifacts_path / 'executive_summary.md'
        write_markdown_output(format_executive_markdown(summary), md_file)
        
        await ctx.info(f"Executive summary generated", f"Summary saved to {output_file}")
        ctx.set_state("executive_summary", json.dumps(summary))
        ctx.set_state("executive_summary_file", str(output_file))
        
        return {
            "status": "success",
            "test_run_id": test_run_id,
            "summary": summary,
            "output_files": {
                "json": str(output_file),
                "markdown": str(md_file)
            }
        }
        
    except Exception as e:
        error_msg = f"Executive summary generation failed: {str(e)}"
        await ctx.error("Summary Generation Error", error_msg)
        return {"error": error_msg, "status": "failed"}

async def get_current_analysis_status(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Get the current analysis status for a test run
    """
    try:
        artifacts_path = Path(artifacts_base) / test_run_id
        
        if not artifacts_path.exists():
            error_msg = f"Test run not found: {test_run_id}"
            await ctx.error("Test Run Not Found", error_msg)
            return {"error": error_msg, "status": "not_found"}
        
        # Check which analysis steps are completed
        status = {
            "test_run_id": test_run_id,
            "artifacts_path": str(artifacts_path),
            "completed_analyses": [],
            "available_files": []
        }
        
        analysis_files = {
            "performance_analysis": "blazemeter/performance_analysis.json",
            "infrastructure_analysis": "datadog/infrastructure_analysis.json", 
            "correlation_analysis": "correlation_analysis.json",
            "anomaly_detection": "anomaly_detection.json",
            "bottleneck_analysis": "bottleneck_analysis.json",
            "executive_summary": "executive_summary.json"
        }
        
        for analysis_name, file_path in analysis_files.items():
            full_path = artifacts_path / file_path
            if full_path.exists():
                status["completed_analyses"].append(analysis_name)
                status["available_files"].append(str(full_path))
        
        await ctx.info(f"Analysis status retrieved", f"Completed: {len(status['completed_analyses'])} analyses")
        
        return status
        
    except Exception as e:
        error_msg = f"Status check failed: {str(e)}"
        await ctx.error("Status Check Error", error_msg)
        return {"error": error_msg, "status": "failed"}

# -----------------------------------------------
# Helper Functions for data processing & analysis
# -----------------------------------------------
def validate_sla_compliance(analysis: Dict, sla_threshold: int) -> Dict:
    """Validate response times against SLA threshold"""
    sla_results = {"threshold_ms": sla_threshold, "violations": []}
    
    if 'api_analysis' in analysis:
        for api, stats in analysis['api_analysis'].items():
            if stats.get('avg_response_time', 0) > sla_threshold:
                sla_results['violations'].append({
                    "api": api,
                    "avg_response_time": stats['avg_response_time'],
                    "violation_amount": stats['avg_response_time'] - sla_threshold
                })
    
    sla_results['compliance_rate'] = 1 - (len(sla_results['violations']) / max(len(analysis.get('api_analysis', {})), 1))
    return sla_results

def process_infrastructure_metrics(host_metrics: List[Path], k8s_metrics: List[Path]) -> Dict:
    """Process and summarize infrastructure metrics"""
    analysis = {
        "host_analysis": {},
        "k8s_analysis": {},
        "summary": {
            "total_hosts": len(host_metrics),
            "total_k8s_services": len(k8s_metrics)
        }
    }
    
    # Process host metrics
    for host_file in host_metrics:
        host_data = load_datadog_metrics(host_file)
        if host_data is not None:
            hostname = extract_hostname_from_path(host_file)
            analysis["host_analysis"][hostname] = summarize_host_metrics(host_data)
    
    # Process K8s metrics  
    for k8s_file in k8s_metrics:
        k8s_data = load_datadog_metrics(k8s_file)
        if k8s_data is not None:
            service_name = extract_service_from_path(k8s_file)
            analysis["k8s_analysis"][service_name] = summarize_k8s_metrics(k8s_data)
    
    return analysis

def perform_multi_run_comparison(test_run_ids: List[str], comparison_type: str) -> Dict:
    """Compare multiple test runs for trend analysis"""
    comparison_results = {
        "comparison_type": comparison_type,
        "test_run_ids": test_run_ids,
        "trends": {},
        "summary": {}
    }
    
    # Implementation for multi-run comparison
    # This would load each run's analysis and compare key metrics
    
    return comparison_results

def create_executive_overview(combined_data: Dict) -> Dict:
    """Create executive-level overview of all analyses"""
    overview = {
        "test_performance": {},
        "infrastructure_health": {},
        "key_findings": [],
        "recommendations": []
    }
    
    # Extract key metrics from combined analysis data
    if 'performance_analysis' in combined_data:
        perf_data = combined_data['performance_analysis']
        overview["test_performance"] = {
            "overall_success_rate": perf_data.get('overall_stats', {}).get('success_rate', 0),
            "avg_response_time": perf_data.get('overall_stats', {}).get('avg_response_time', 0),
            "total_requests": perf_data.get('overall_stats', {}).get('total_samples', 0)
        }
    
    return overview

# Additional helper functions
def extract_hostname_from_path(file_path: Path) -> str:
    """Extract hostname from file path"""
    return file_path.stem.replace('host_metrics_[', '').replace(']', '')

def extract_service_from_path(file_path: Path) -> str:
    """Extract service name from file path"""
    return file_path.stem.replace('k8s_metrics_[', '').replace(']', '')

# -----------------------------------------------
# Output functions for performance analysis
# -----------------------------------------------
async def generate_performance_outputs(analysis: Dict, output_path: Path, test_run_id: str, ctx: Context) -> Dict[str, str]:
    """Generate all output files for performance analysis"""
    
    output_files = {}
    
    try:
        # JSON Output - Detailed analysis
        json_file = output_path / 'performance_analysis.json'
        await write_json_output(analysis, json_file)
        output_files['json'] = str(json_file)
        
        # CSV Output - Structured data for reporting
        csv_file = output_path / 'performance_summary.csv'
        await write_performance_csv(analysis, csv_file)
        output_files['csv'] = str(csv_file)
        
        # Markdown Output - Human-readable summary
        markdown_file = output_path / 'performance_summary.md'
        markdown_content = format_performance_markdown(analysis, test_run_id)
        await write_markdown_output(markdown_content, markdown_file)
        output_files['markdown'] = str(markdown_file)
        
        await ctx.info("Output Generation", f"Generated {len(output_files)} analysis files")
        
    except Exception as e:
        await ctx.error("Output Generation Error", f"Failed to generate outputs: {str(e)}")
    
    return output_files