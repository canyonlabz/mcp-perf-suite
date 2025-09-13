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
from fastmcp import Context

from utils.config import load_config
from utils.file_processor import (
    load_jmeter_results,
    load_datadog_metrics,
    write_json_output,
    write_csv_output,
    write_markdown_output
)
from utils.statistical_analyzer import (
    calculate_response_time_stats,
    calculate_correlation_matrix,
    detect_statistical_anomalies,
    identify_resource_bottlenecks
)
from utils.openai_client import generate_ai_insights

# Load configuration and environment
load_dotenv()
config = load_config()
artifacts_base = config['artifacts']['artifacts_path']

async def analyze_blazemeter_results(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Analyze BlazeMeter JMeter test results focusing on response time aggregates
    """
    try:
        # Locate BlazeMeter results
        blazemeter_path = Path(artifacts_base) / test_run_id / 'blazemeter'
        results_file = blazemeter_path / 'test-results.csv'
        
        if not results_file.exists():
            error_msg = f"BlazeMeter results file not found: {results_file}"
            await ctx.error("Missing BlazeMeter Results", error_msg)
            return {"error": error_msg, "status": "failed"}
        
        # Load and process JMeter results
        df = load_jmeter_results(results_file)
        if df is None:
            error_msg = "Failed to load JMeter results CSV"
            await ctx.error("CSV Load Error", error_msg)
            return {"error": error_msg, "status": "failed"}
        
        # Calculate performance statistics
        analysis = calculate_response_time_stats(df)
        
        # Add SLA validation
        sla_threshold = config.get('perf_analysis', {}).get('response_time_sla', 5000)
        analysis['sla_analysis'] = validate_sla_compliance(analysis, sla_threshold)
        
        # Save analysis results
        output_file = blazemeter_path / 'performance_analysis.json'
        write_json_output(analysis, output_file)
        
        # Save CSV summary for reporting
        csv_file = blazemeter_path / 'performance_summary.csv'
        write_performance_csv(analysis, csv_file)
        
        # Save markdown summary
        md_file = blazemeter_path / 'performance_analysis.md'
        write_markdown_output(format_performance_markdown(analysis), md_file)
        
        await ctx.info(f"BlazeMeter analysis completed", f"Results saved to {output_file}")
        ctx.set_state("performance_analysis", json.dumps(analysis))
        ctx.set_state("performance_analysis_file", str(output_file))
        
        return {
            "status": "success",
            "test_run_id": test_run_id,
            "analysis": analysis,
            "output_files": {
                "json": str(output_file),
                "csv": str(csv_file),
                "markdown": str(md_file)
            }
        }
        
    except Exception as e:
        error_msg = f"BlazeMeter analysis failed: {str(e)}"
        await ctx.error("Analysis Error", error_msg)
        return {"error": error_msg, "status": "failed"}

async def analyze_datadog_metrics(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Analyze Datadog infrastructure metrics (CPU/Memory for Hosts and K8s)
    """
    try:
        # Locate Datadog metrics
        datadog_path = Path(artifacts_base) / test_run_id / 'datadog'
        
        if not datadog_path.exists():
            error_msg = f"Datadog metrics directory not found: {datadog_path}"
            await ctx.error("Missing Datadog Metrics", error_msg)
            return {"error": error_msg, "status": "failed"}
        
        # Find all metric files
        host_metrics = list(datadog_path.glob('host_metrics_*.csv'))
        k8s_metrics = list(datadog_path.glob('k8s_metrics_*.csv'))
        
        if not host_metrics and not k8s_metrics:
            error_msg = "No Datadog metric files found"
            await ctx.error("No Metrics Found", error_msg)
            return {"error": error_msg, "status": "failed"}
        
        # Process metrics
        infrastructure_analysis = process_infrastructure_metrics(host_metrics, k8s_metrics)
        
        # Save results
        output_file = datadog_path / 'infrastructure_analysis.json'
        write_json_output(infrastructure_analysis, output_file)
        
        # Save CSV summary
        csv_file = datadog_path / 'infrastructure_summary.csv'
        write_infrastructure_csv(infrastructure_analysis, csv_file)
        
        # Save markdown summary
        md_file = datadog_path / 'infrastructure_analysis.md'
        write_markdown_output(format_infrastructure_markdown(infrastructure_analysis), md_file)
        
        await ctx.info(f"Infrastructure analysis completed", f"Results saved to {output_file}")
        ctx.set_state("infrastructure_analysis", json.dumps(infrastructure_analysis))
        ctx.set_state("infrastructure_analysis_file", str(output_file))
        
        return {
            "status": "success",
            "test_run_id": test_run_id,
            "analysis": infrastructure_analysis,
            "output_files": {
                "json": str(output_file),
                "csv": str(csv_file),
                "markdown": str(md_file)
            }
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
        blazemeter_path = Path(artifacts_base) / test_run_id / 'blazemeter'
        datadog_path = Path(artifacts_base) / test_run_id / 'datadog'
        
        performance_file = blazemeter_path / 'performance_analysis.json'
        infrastructure_file = datadog_path / 'infrastructure_analysis.json'
        
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
        output_file = Path(artifacts_base) / test_run_id / 'correlation_analysis.json'
        write_json_output(correlation_results, output_file)
        
        # Save CSV matrix
        csv_file = Path(artifacts_base) / test_run_id / 'correlation_matrix.csv'
        write_correlation_csv(correlation_results, csv_file)
        
        # Save markdown summary
        md_file = Path(artifacts_base) / test_run_id / 'correlation_analysis.md'
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
            "generated_at": datetime.now().isoformat(),
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

# Helper functions for data processing
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

# Additional helper functions would go here...
def extract_hostname_from_path(file_path: Path) -> str:
    """Extract hostname from file path"""
    return file_path.stem.replace('host_metrics_[', '').replace(']', '')

def extract_service_from_path(file_path: Path) -> str:
    """Extract service name from file path"""
    return file_path.stem.replace('k8s_metrics_[', '').replace(']', '')

def summarize_host_metrics(host_data: pd.DataFrame) -> Dict:
    """Summarize host metrics data"""
    # Implementation for host metrics summarization
    return {}

def summarize_k8s_metrics(k8s_data: pd.DataFrame) -> Dict:
    """Summarize K8s metrics data"""
    # Implementation for K8s metrics summarization
    return {}

def write_performance_csv(analysis: Dict, csv_file: Path):
    """Write performance analysis to CSV"""
    # Implementation for CSV writing
    pass

def write_infrastructure_csv(analysis: Dict, csv_file: Path):
    """Write infrastructure analysis to CSV"""
    # Implementation for CSV writing
    pass

def write_correlation_csv(correlation_results: Dict, csv_file: Path):
    """Write correlation matrix to CSV"""
    # Implementation for correlation CSV
    pass

def write_anomalies_csv(anomalies: Dict, csv_file: Path):
    """Write detected anomalies to CSV"""
    # Implementation for anomalies CSV
    pass

def format_performance_markdown(analysis: Dict) -> str:
    """Format performance analysis as markdown"""
    # Implementation for markdown formatting
    return "# Performance Analysis\n\n"

def format_infrastructure_markdown(analysis: Dict) -> str:
    """Format infrastructure analysis as markdown"""
    return "# Infrastructure Analysis\n\n"

def format_correlation_markdown(correlation_results: Dict) -> str:
    """Format correlation analysis as markdown"""
    return "# Correlation Analysis\n\n"

def format_anomalies_markdown(anomalies: Dict) -> str:
    """Format anomaly detection as markdown"""
    return "# Anomaly Detection\n\n"

def format_bottlenecks_markdown(bottlenecks: Dict) -> str:
    """Format bottleneck analysis as markdown"""
    return "# Bottleneck Analysis\n\n"

def format_comparison_markdown(comparison_results: Dict) -> str:
    """Format test run comparison as markdown"""
    return "# Test Run Comparison\n\n"

def format_executive_markdown(summary: Dict) -> str:
    """Format executive summary as markdown"""
    return "# Executive Summary\n\n"
