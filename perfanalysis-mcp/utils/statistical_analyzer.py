# utils/statistical_analyzer.py
import pandas as pd
import numpy as np
import json
import datetime
import math
from fastmcp import Context     # ✅ FastMCP 2.x import
from pathlib import Path
from typing import Dict, List, Any, Optional
from scipy.stats import pearsonr, spearmanr

# -----------------------------------------------
# BlazeMeter/JMeter statistical analysis functions
# -----------------------------------------------
async def perform_aggregate_analysis(df: pd.DataFrame, test_run_id: str, config: Dict, ctx: Context) -> Dict[str, Any]:
    """Perform comprehensive analysis on aggregate report data"""
    
    # Convert numpy types to Python native types for JSON serialization
    def to_native_type(value):
        if pd.isna(value) or (isinstance(value, float) and math.isnan(value)):
            return None
        elif isinstance(value, np.integer):
            return int(value)
        elif isinstance(value, np.floating):
            return float(value)
        else:
            return value
    
    # Get overall summary from "ALL" row
    all_summary = df[df['labelName'] == 'ALL']
    if all_summary.empty:
        await ctx.warning("No 'ALL' summary row found in aggregate data")
        overall_stats = {"error": "No 'ALL' summary found in aggregate data"}
    else:
        all_row = all_summary.iloc[0]
        overall_stats = {
            "total_samples": to_native_type(all_row['samples']),
            "avg_response_time": to_native_type(all_row['avgResponseTime']),
            "min_response_time": to_native_type(all_row['minResponseTime']),
            "max_response_time": to_native_type(all_row['maxResponseTime']),
            "median_response_time": to_native_type(all_row['medianResponseTime']),
            "p90_response_time": to_native_type(all_row['90line']),
            "p95_response_time": to_native_type(all_row['95line']),
            "p99_response_time": to_native_type(all_row['99line']),
            "std_deviation": to_native_type(all_row['stDev']),
            "avg_latency": to_native_type(all_row['avgLatency']),
            "error_count": to_native_type(all_row['errorsCount']),
            "error_rate": to_native_type(all_row['errorsRate']),
            "avg_throughput": to_native_type(all_row['avgThroughput']),
            "test_duration": to_native_type(all_row['duration']),
            "success_rate": to_native_type(100.0 - all_row['errorsRate']) if pd.notna(all_row['errorsRate']) else 100.0
        }
    
    # Analyze individual APIs (exclude "ALL" row)
    individual_apis = df[df['labelName'] != 'ALL']
    api_analysis = {}
    
    # Get SLA threshold from config
    sla_threshold = config.get('perf_analysis', {}).get('response_time_sla', 5000)
    
    for _, row in individual_apis.iterrows():
        api_name = row['labelName']
        avg_rt = to_native_type(row['avgResponseTime'])
        
        api_analysis[api_name] = {
            "samples": to_native_type(row['samples']),
            "avg_response_time": avg_rt,
            "min_response_time": to_native_type(row['minResponseTime']),
            "max_response_time": to_native_type(row['maxResponseTime']),
            "median_response_time": to_native_type(row['medianResponseTime']),
            "p90_response_time": to_native_type(row['90line']),
            "p95_response_time": to_native_type(row['95line']),
            "p99_response_time": to_native_type(row['99line']),
            "std_deviation": to_native_type(row['stDev']),
            "error_count": to_native_type(row['errorsCount']),
            "error_rate": to_native_type(row['errorsRate']),
            "success_rate": to_native_type(100.0 - row['errorsRate']) if pd.notna(row['errorsRate']) else 100.0,
            "throughput": to_native_type(row['avgThroughput']),
            "sla_compliant": bool(avg_rt <= sla_threshold) if avg_rt is not None else None,
            "sla_threshold_ms": sla_threshold
        }
    
    # SLA Analysis
    sla_analysis = analyze_sla_compliance(individual_apis, sla_threshold)
    
    # Statistical Analysis
    statistical_summary = {
        "total_apis_analyzed": len(individual_apis),
        "apis_with_errors": int(len(individual_apis[individual_apis['errorsCount'] > 0])),
        "slowest_api": get_slowest_api(individual_apis),
        "fastest_api": get_fastest_api(individual_apis),
        "high_variability_apis": get_high_variability_apis(individual_apis)
    }
    
    await ctx.info(f"Aggregate analysis completed for test run {test_run_id}")

    return {
        "test_run_id": test_run_id,
        "overall_stats": overall_stats,
        "api_analysis": api_analysis,
        "sla_analysis": sla_analysis,
        "statistical_summary": statistical_summary,
        "analysis_timestamp": datetime.datetime.now().isoformat(),
        "data_quality": {
            "total_labels": len(df),
            "individual_apis": len(individual_apis),
            "has_overall_summary": not all_summary.empty
        }
    }

def analyze_sla_compliance(df: pd.DataFrame, sla_threshold: float) -> Dict[str, Any]:
    """Analyze SLA compliance across APIs"""
    
    if df.empty:
        return {"error": "No API data to analyze"}
    
    compliant_apis = df[df['avgResponseTime'] <= sla_threshold]
    violating_apis = df[df['avgResponseTime'] > sla_threshold]
    
    violations = []
    for _, row in violating_apis.iterrows():
        violations.append({
            "api_name": row['labelName'],
            "avg_response_time": float(row['avgResponseTime']),
            "sla_threshold": sla_threshold,
            "violation_amount": float(row['avgResponseTime'] - sla_threshold),
            "violation_percentage": float((row['avgResponseTime'] - sla_threshold) / sla_threshold * 100)
        })
    
    return {
        "sla_threshold_ms": sla_threshold,
        "total_apis": len(df),
        "compliant_apis": len(compliant_apis),
        "violating_apis": len(violating_apis),
        "compliance_rate": float(len(compliant_apis) / len(df) * 100),
        "violations": violations
    }

def get_slowest_api(df: pd.DataFrame) -> Optional[Dict]:
    """Get the slowest API by average response time"""
    if df.empty:
        return None
    
    slowest = df.loc[df['avgResponseTime'].idxmax()]
    return {
        "api_name": slowest['labelName'],
        "avg_response_time": float(slowest['avgResponseTime']),
        "samples": int(slowest['samples'])
    }

def get_fastest_api(df: pd.DataFrame) -> Optional[Dict]:
    """Get the fastest API by average response time"""
    if df.empty:
        return None
    
    fastest = df.loc[df['avgResponseTime'].idxmin()]
    return {
        "api_name": fastest['labelName'],
        "avg_response_time": float(fastest['avgResponseTime']),
        "samples": int(fastest['samples'])
    }

def get_high_variability_apis(df: pd.DataFrame, threshold: float = 50.0) -> List[Dict]:
    """Get APIs with high response time variability (high std deviation)"""
    if df.empty:
        return []
    
    high_var_apis = df[df['stDev'] > threshold]
    
    return [
        {
            "api_name": row['labelName'],
            "std_deviation": float(row['stDev']),
            "avg_response_time": float(row['avgResponseTime']),
            "coefficient_of_variation": float(row['stDev'] / row['avgResponseTime']) if row['avgResponseTime'] > 0 else 0
        }
        for _, row in high_var_apis.iterrows()
    ]

# -----------------------------------------------
# Statistical analysis functions
# -----------------------------------------------
def calculate_response_time_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate comprehensive response time statistics"""
    
    # Overall statistics
    overall_stats = {
        "total_samples": len(df),
        "success_rate": (df['success'].sum() / len(df)) * 100 if 'success' in df.columns else 0,
        "avg_response_time": df['elapsed'].mean(),
        "min_response_time": df['elapsed'].min(),
        "max_response_time": df['elapsed'].max(),
        "p90_response_time": df['elapsed'].quantile(0.9),
        "p95_response_time": df['elapsed'].quantile(0.95),
        "p99_response_time": df['elapsed'].quantile(0.99),
        "std_dev": df['elapsed'].std(),
        "error_count": len(df[df['success'] == False]) if 'success' in df.columns else 0
    }
    
    # Per-API statistics
    api_analysis = {}
    if 'label' in df.columns:
        for label in df['label'].unique():
            label_df = df[df['label'] == label]
            api_analysis[label] = {
                "samples": len(label_df),
                "avg_response_time": label_df['elapsed'].mean(),
                "min_response_time": label_df['elapsed'].min(),
                "max_response_time": label_df['elapsed'].max(),
                "p90_response_time": label_df['elapsed'].quantile(0.9),
                "success_rate": (label_df['success'].sum() / len(label_df)) * 100 if 'success' in label_df.columns else 0,
                "error_count": len(label_df[label_df['success'] == False]) if 'success' in label_df.columns else 0
            }
    
    return {
        "overall_stats": overall_stats,
        "api_analysis": api_analysis,
        "analysis_timestamp": pd.Timestamp.now().isoformat()
    }

def calculate_correlation_matrix(performance_data: Dict, infrastructure_data: Dict, test_run_id: str) -> Dict:
    """Calculate correlation between performance and infrastructure metrics"""
    
    correlations = {
        "test_run_id": test_run_id,
        "correlation_matrix": {},
        "significant_correlations": [],
        "correlation_threshold": 0.3
    }
    
    # Extract key metrics for correlation
    perf_metrics = performance_data.get('overall_stats', {})
    infra_metrics = infrastructure_data.get('host_analysis', {})
    
    # Implementation would calculate correlations between response times and resource utilization
    # This is a simplified placeholder
    
    return correlations

def detect_statistical_anomalies(blazemeter_file: Path, datadog_files: List[Path], sensitivity: str) -> Dict:
    """Detect anomalies using statistical methods"""
    
    # Map sensitivity to standard deviations
    sensitivity_map = {"low": 3.0, "medium": 2.5, "high": 2.0}
    threshold = sensitivity_map.get(sensitivity, 2.5)
    
    anomalies = {
        "sensitivity": sensitivity,
        "threshold_std_dev": threshold,
        "anomalies": [],
        "summary": {
            "total_anomalies": 0,
            "response_time_anomalies": 0,
            "resource_anomalies": 0
        }
    }
    
    # Load and analyze BlazeMeter data for response time anomalies
    if blazemeter_file.exists():
        df = pd.read_csv(blazemeter_file)
        mean_rt = df['elapsed'].mean()
        std_rt = df['elapsed'].std()
        
        # Detect response time anomalies
        rt_anomalies = df[(np.abs(df['elapsed'] - mean_rt) > threshold * std_rt)]
        
        for _, row in rt_anomalies.iterrows():
            anomalies["anomalies"].append({
                "type": "response_time",
                "timestamp": row['timeStamp'],
                "api": row.get('label', 'unknown'),
                "value": row['elapsed'],
                "z_score": (row['elapsed'] - mean_rt) / std_rt,
                "severity": "high" if abs((row['elapsed'] - mean_rt) / std_rt) > threshold + 1 else "medium"
            })
    
    anomalies["summary"]["total_anomalies"] = len(anomalies["anomalies"])
    return anomalies

def identify_resource_bottlenecks(correlation_file: Path, anomaly_file: Path, test_run_id: str) -> Dict:
    """Identify system bottlenecks based on correlation and anomaly analysis"""
    
    bottlenecks = {
        "test_run_id": test_run_id,
        "bottlenecks": [],
        "recommendations": [],
        "priority_ranking": []
    }
    
    # Load correlation and anomaly data
    if correlation_file.exists():
        with open(correlation_file, 'r') as f:
            correlation_data = json.load(f)
    
    if anomaly_file and anomaly_file.exists():
        with open(anomaly_file, 'r') as f:
            anomaly_data = json.load(f)
    
    # Analyze patterns and identify bottlenecks
    # This would involve more complex logic to identify resource constraints
    
    return bottlenecks
