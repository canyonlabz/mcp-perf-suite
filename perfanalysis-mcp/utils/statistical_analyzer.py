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
# Correlation analysis functions
# -----------------------------------------------
def calculate_correlation_matrix(performance_data: Dict, infrastructure_data: Dict, test_run_id: str, config: Dict = None) -> Dict:
    """Calculate temporal correlation between performance and infrastructure metrics"""
    
    correlations = {
        "test_run_id": test_run_id,
        "analysis_timestamp": datetime.datetime.now().isoformat(),
        "environment_type": None,
        "correlation_matrix": {},
        "significant_correlations": [],
        "correlation_threshold": 0.3,
        "summary": {},
        "insights": [],
        "temporal_analysis": {}
    }
    
    try:
        # Get configuration
        if config is None:
            config = {}
        
        granularity_window = config.get('perf_analysis', {}).get('correlation_granularity_window', 60)
        sla_threshold = config.get('perf_analysis', {}).get('response_time_sla', 5000)
        resource_thresholds = config.get('perf_analysis', {}).get('resource_thresholds', {})
        
        # === ENVIRONMENT TYPE DETECTION ===
        infra_summary = infrastructure_data.get('infrastructure_summary', {})
        k8s_summary = infra_summary.get('kubernetes_summary', {})
        host_summary = infra_summary.get('host_summary', {})
        
        has_k8s = k8s_summary.get('total_services', 0) > 0
        has_hosts = host_summary.get('total_hosts', 0) > 0
        
        if has_k8s and not has_hosts:
            correlations["environment_type"] = "kubernetes"
            return analyze_temporal_kubernetes_correlations(correlations, performance_data, infrastructure_data, 
                                                         granularity_window, sla_threshold, resource_thresholds)
        elif has_hosts and not has_k8s:
            correlations["environment_type"] = "host"
            return analyze_temporal_host_correlations(correlations, performance_data, infrastructure_data,
                                                   granularity_window, sla_threshold, resource_thresholds)
        elif has_k8s and has_hosts:
            correlations["environment_type"] = "hybrid"
            correlations["insights"].append("Warning: Mixed K8s+Host environment detected - correlation may be complex")
            return analyze_hybrid_correlations(correlations, performance_data, infrastructure_data)
        else:
            correlations["environment_type"] = "none"
            correlations["insights"].append("No infrastructure metrics available for correlation")
            return correlations
            
    except Exception as e:
        correlations["error"] = f"Correlation analysis failed: {str(e)}"
        return correlations

def analyze_kubernetes_correlations(correlations: Dict, performance_data: Dict, infrastructure_data: Dict) -> Dict:
    """Analyze correlations for Kubernetes-based environments"""
    
    # Extract performance metrics
    perf_overall = performance_data.get('overall_stats', {})
    perf_apis = performance_data.get('api_analysis', {})
    
    # Extract K8s infrastructure metrics
    infra_detailed = infrastructure_data.get('detailed_metrics', {})
    k8s_data = infra_detailed.get('kubernetes', {})
    k8s_services = k8s_data.get('services', {})
    
    correlations["infrastructure_scope"] = "kubernetes"
    correlations["services_analyzed"] = len(k8s_services)
    
    # Correlate performance with K8s resource utilization
    service_correlations = []
    
    for service_name, service_metrics in k8s_services.items():
        cpu_analysis = service_metrics.get('cpu_analysis', {})
        memory_analysis = service_metrics.get('memory_analysis', {})
        
        # Get resource utilization metrics
        avg_cpu_util = cpu_analysis.get('avg_utilization_pct', 0)
        peak_cpu_util = cpu_analysis.get('peak_utilization_pct', 0)
        avg_memory_util = memory_analysis.get('avg_utilization_pct', 0)
        peak_memory_util = memory_analysis.get('peak_utilization_pct', 0)
        
        # Correlate with overall performance
        overall_response_time = perf_overall.get('avg_response_time', 0)
        overall_p95 = perf_overall.get('p95_response_time', 0)
        
        # Calculate correlations (simplified approach)
        cpu_rt_correlation = calculate_resource_correlation(avg_cpu_util, overall_response_time, "cpu")
        memory_rt_correlation = calculate_resource_correlation(avg_memory_util, overall_response_time, "memory")
        
        service_correlation = {
            "service": service_name,
            "cpu_correlation": cpu_rt_correlation,
            "memory_correlation": memory_rt_correlation,
            "avg_cpu_utilization": avg_cpu_util,
            "peak_cpu_utilization": peak_cpu_util,
            "avg_memory_utilization": avg_memory_util,
            "peak_memory_utilization": peak_memory_util,
            "containers": len(service_metrics.get('containers', {}))
        }
        
        service_correlations.append(service_correlation)
        
        # Check for significant correlations
        check_significant_correlation(correlations, service_correlation, "kubernetes")
    
    correlations["correlation_matrix"]["kubernetes_correlations"] = service_correlations
    correlations["correlation_matrix"]["performance_overview"] = perf_overall
    
    # Generate K8s-specific insights
    correlations["insights"] = generate_kubernetes_insights(service_correlations, perf_overall)
    
    return correlations

def analyze_host_correlations(correlations: Dict, performance_data: Dict, infrastructure_data: Dict) -> Dict:
    """Analyze correlations for Host/VM-based environments"""
    
    # Extract performance metrics
    perf_overall = performance_data.get('overall_stats', {})
    perf_apis = performance_data.get('api_analysis', {})
    
    # Extract Host infrastructure metrics  
    infra_detailed = infrastructure_data.get('detailed_metrics', {})
    host_data = infra_detailed.get('hosts', {})
    host_systems = host_data.get('hosts', {})
    
    correlations["infrastructure_scope"] = "host"
    correlations["hosts_analyzed"] = len(host_systems)
    
    # Correlate performance with Host resource utilization
    host_correlations = []
    
    for host_name, host_metrics in host_systems.items():
        cpu_analysis = host_metrics.get('cpu_analysis', {})
        memory_analysis = host_metrics.get('memory_analysis', {})
        
        # Get resource utilization metrics
        avg_cpu_util = cpu_analysis.get('avg_utilization_pct', 0)
        peak_cpu_util = cpu_analysis.get('peak_utilization_pct', 0)
        avg_memory_util = memory_analysis.get('avg_utilization_pct', 0)
        peak_memory_util = memory_analysis.get('peak_utilization_pct', 0)
        
        # Correlate with overall performance
        overall_response_time = perf_overall.get('avg_response_time', 0)
        overall_p95 = perf_overall.get('p95_response_time', 0)
        
        # Calculate correlations
        cpu_rt_correlation = calculate_resource_correlation(avg_cpu_util, overall_response_time, "cpu")
        memory_rt_correlation = calculate_resource_correlation(avg_memory_util, overall_response_time, "memory")
        
        host_correlation = {
            "host": host_name,
            "cpu_correlation": cpu_rt_correlation,
            "memory_correlation": memory_rt_correlation,
            "avg_cpu_utilization": avg_cpu_util,
            "peak_cpu_utilization": peak_cpu_util,
            "avg_memory_utilization": avg_memory_util,
            "peak_memory_utilization": peak_memory_util,
            "allocated_cpus": cpu_analysis.get('allocated_cpus', 'unknown'),
            "allocated_memory_gb": memory_analysis.get('allocated_gb', 'unknown')
        }
        
        host_correlations.append(host_correlation)
        
        # Check for significant correlations
        check_significant_correlation(correlations, host_correlation, "host")
    
    correlations["correlation_matrix"]["host_correlations"] = host_correlations
    correlations["correlation_matrix"]["performance_overview"] = perf_overall
    
    # Generate Host-specific insights
    correlations["insights"] = generate_host_insights(host_correlations, perf_overall)
    
    return correlations

def calculate_resource_correlation(resource_util: float, response_time: float, resource_type: str) -> float:
    """Calculate correlation between resource utilization and performance"""
    # Simplified correlation logic - in reality, you'd use time-series data
    
    if resource_util == 0 or response_time == 0:
        return 0.0
    
    # Basic correlation based on resource utilization levels
    if resource_type == "cpu":
        # High CPU usage typically correlates with slower response times
        if resource_util > 80:
            return 0.7 + (resource_util - 80) / 100  # Strong positive correlation
        elif resource_util > 50:
            return 0.3 + (resource_util - 50) / 100  # Moderate correlation
        else:
            return 0.1  # Weak correlation
    
    elif resource_type == "memory":
        # High memory usage may correlate with slower response times (due to GC, swapping)
        if resource_util > 85:
            return 0.6 + (resource_util - 85) / 75   # Strong positive correlation
        elif resource_util > 60:
            return 0.2 + (resource_util - 60) / 100  # Moderate correlation
        else:
            return 0.05  # Very weak correlation
    
    return 0.0

def check_significant_correlation(correlations: Dict, resource_correlation: Dict, env_type: str):
    """Check if correlations are significant and add to results"""
    threshold = correlations["correlation_threshold"]
    
    cpu_corr = resource_correlation.get("cpu_correlation", 0)
    memory_corr = resource_correlation.get("memory_correlation", 0)
    resource_name = resource_correlation.get("service" if env_type == "kubernetes" else "host", "unknown")
    
    if abs(cpu_corr) >= threshold:
        correlations["significant_correlations"].append({
            "type": "cpu_performance",
            "environment": env_type,
            "resource": resource_name,
            "correlation_coefficient": cpu_corr,
            "strength": "strong" if abs(cpu_corr) > 0.7 else "moderate",
            "direction": "positive" if cpu_corr > 0 else "negative",
            "interpretation": f"CPU utilization {'increases' if cpu_corr > 0 else 'decreases'} with response time"
        })
    
    if abs(memory_corr) >= threshold:
        correlations["significant_correlations"].append({
            "type": "memory_performance",
            "environment": env_type,
            "resource": resource_name,
            "correlation_coefficient": memory_corr,
            "strength": "strong" if abs(memory_corr) > 0.7 else "moderate",
            "direction": "positive" if memory_corr > 0 else "negative",
            "interpretation": f"Memory utilization {'increases' if memory_corr > 0 else 'decreases'} with response time"
        })

def generate_kubernetes_insights(service_correlations: List[Dict], performance_overview: Dict) -> List[str]:
    """Generate Kubernetes-specific insights"""
    insights = []
    
    total_services = len(service_correlations)
    insights.append(f"Analyzed {total_services} Kubernetes service(s) for performance correlation")
    
    # CPU insights
    high_cpu_services = [s for s in service_correlations if s["avg_cpu_utilization"] > 50]
    if high_cpu_services:
        insights.append(f"{len(high_cpu_services)} service(s) showing elevated CPU usage (>50%)")
    
    # Memory insights
    high_memory_services = [s for s in service_correlations if s["avg_memory_utilization"] > 60]
    if high_memory_services:
        insights.append(f"{len(high_memory_services)} service(s) showing elevated memory usage (>60%)")
    
    # Container density insights
    total_containers = sum(s.get("containers", 0) for s in service_correlations)
    insights.append(f"Total containers analyzed: {total_containers}")
    
    return insights

def generate_host_insights(host_correlations: List[Dict], performance_overview: Dict) -> List[str]:
    """Generate Host/VM-specific insights"""
    insights = []
    
    total_hosts = len(host_correlations)
    insights.append(f"Analyzed {total_hosts} host system(s) for performance correlation")
    
    # CPU insights
    high_cpu_hosts = [h for h in host_correlations if h["avg_cpu_utilization"] > 60]
    if high_cpu_hosts:
        insights.append(f"{len(high_cpu_hosts)} host(s) showing elevated CPU usage (>60%)")
    
    # Memory insights
    high_memory_hosts = [h for h in host_correlations if h["avg_memory_utilization"] > 70]
    if high_memory_hosts:
        insights.append(f"{len(high_memory_hosts)} host(s) showing elevated memory usage (>70%)")
    
    return insights

def analyze_hybrid_correlations(correlations: Dict, performance_data: Dict, infrastructure_data: Dict) -> Dict:
    """Analyze correlations for hybrid environments (both K8s and Host)"""
    # For simplicity, just note that hybrid analysis is complex
    correlations["insights"].append("Hybrid environment detected - detailed correlation analysis not implemented")
    return correlations

# -----------------------------------------------
# Temporal correlation analysis functions
# -----------------------------------------------
def analyze_temporal_kubernetes_correlations(correlations: Dict, performance_data: Dict, infrastructure_data: Dict,
                                           granularity_window: int, sla_threshold: float, resource_thresholds: Dict) -> Dict:
    """Analyze temporal correlations for Kubernetes environments"""
    
    try:
        # Load raw data files for temporal analysis
        test_run_id = correlations["test_run_id"]
        # Import artifacts_base from the config
        from .config import load_config
        config = load_config()
        artifacts_base = config['artifacts']['artifacts_path']
        artifacts_path = Path(artifacts_base) / test_run_id
        
        # Load BlazeMeter performance data
        blazemeter_file = artifacts_path / "blazemeter" / "test-results.csv"
        if not blazemeter_file.exists():
            # Debug: check if the directory exists
            if not artifacts_path.exists():
                correlations["error"] = f"Artifacts directory not found: {artifacts_path} (cwd: {Path.cwd()})"
            else:
                correlations["error"] = f"BlazeMeter data file not found: {blazemeter_file} (exists: {blazemeter_file.exists()})"
            return correlations
        
        # Load Datadog infrastructure data
        datadog_files = list(artifacts_path.glob("datadog/*.csv"))
        if not datadog_files:
            correlations["error"] = f"Datadog data files not found in {artifacts_path / 'datadog'}"
            return correlations
        
        # Process the data
        perf_df = load_and_process_performance_data(blazemeter_file)
        infra_df = load_and_process_infrastructure_data(datadog_files[0])
        
        if perf_df is None or infra_df is None:
            correlations["error"] = "Failed to load or process performance/infrastructure data"
            return correlations
        
        # Perform temporal correlation analysis
        temporal_results = perform_temporal_correlation_analysis(
            perf_df, infra_df, granularity_window, sla_threshold, resource_thresholds
        )
        
        # Update correlations with temporal results
        correlations["temporal_analysis"] = temporal_results
        correlations["correlation_matrix"] = temporal_results.get("correlation_matrix", {})
        correlations["significant_correlations"] = temporal_results.get("significant_correlations", [])
        correlations["insights"].extend(temporal_results.get("insights", []))
        
        # Generate summary
        correlations["summary"] = generate_temporal_correlation_summary(temporal_results)
        
        return correlations
        
    except Exception as e:
        correlations["error"] = f"Temporal correlation analysis failed: {str(e)}"
        return correlations

def analyze_temporal_host_correlations(correlations: Dict, performance_data: Dict, infrastructure_data: Dict,
                                     granularity_window: int, sla_threshold: float, resource_thresholds: Dict) -> Dict:
    """Analyze temporal correlations for Host environments"""
    # Similar to Kubernetes but for host metrics
    # For now, redirect to Kubernetes analysis with host detection
    correlations["insights"].append("Host temporal correlation analysis not yet implemented - using basic analysis")
    return analyze_kubernetes_correlations(correlations, performance_data, infrastructure_data)

def load_and_process_performance_data(file_path: Path) -> Optional[pd.DataFrame]:
    """Load and process BlazeMeter performance data for temporal analysis - OPTIMIZED"""
    try:
        df = pd.read_csv(file_path)
        
        # Convert epoch timestamp to datetime with UTC
        df['timestamp'] = pd.to_datetime(df['timeStamp'], unit='ms', utc=True)
        
        # Filter required columns
        required_cols = ['timestamp', 'elapsed', 'label', 'success']
        df = df[required_cols].copy()
        
        # Add SLA compliance flag (vectorized)
        df['sla_violation'] = df['elapsed'] > 5000  # Default SLA threshold
        
        return df
        
    except Exception as e:
        print(f"Error loading performance data: {e}")
        return None

def load_and_process_infrastructure_data(file_path: Path) -> Optional[pd.DataFrame]:
    """Load and process Datadog infrastructure data for temporal analysis - OPTIMIZED"""
    try:
        df = pd.read_csv(file_path)
        
        # Convert ISO timestamp to datetime with UTC
        df['timestamp'] = pd.to_datetime(df['timestamp_utc'], utc=True)
        
        # Filter for CPU and memory metrics only
        df = df[df['metric'].isin(['kubernetes.cpu.usage.total', 'kubernetes.memory.usage'])].copy()
        
        # Convert values based on metric type (vectorized)
        df['value_pct'] = 0.0
        cpu_mask = df['metric'] == 'kubernetes.cpu.usage.total'
        memory_mask = df['metric'] == 'kubernetes.memory.usage'
        
        # CPU: nanocores to percentage
        df.loc[cpu_mask, 'value_pct'] = (df.loc[cpu_mask, 'value'] / 1e9) / 4.05 * 100
        
        # Memory: bytes to percentage  
        df.loc[memory_mask, 'value_pct'] = (df.loc[memory_mask, 'value'] / (16 * 1024**3)) * 100
        
        # Create simplified metric names for unstacking
        df['metric_type'] = df['metric'].map({
            'kubernetes.cpu.usage.total': 'cpu',
            'kubernetes.memory.usage': 'memory'
        })
        
        # Group by timestamp and metric, take mean across containers (simpler than pivot)
        infra_agg = df.groupby(['timestamp', 'metric_type'])['value_pct'].mean().unstack(fill_value=0)
        infra_agg.columns = [f'{col}_utilization_pct' for col in infra_agg.columns]
        infra_agg = infra_agg.reset_index()
        
        return infra_agg
        
    except Exception as e:
        print(f"Error loading infrastructure data: {e}")
        return None

def perform_temporal_correlation_analysis(perf_df: pd.DataFrame, infra_df: pd.DataFrame, 
                                        granularity_window: int, sla_threshold: float, 
                                        resource_thresholds: Dict) -> Dict:
    """Perform temporal correlation analysis - OPTIMIZED with pandas vectorization"""
    
    results = {
        "analysis_periods": [],
        "correlation_matrix": {},
        "significant_correlations": [],
        "insights": []
    }
    
    try:
        # Get resource thresholds
        cpu_high_threshold = resource_thresholds.get('cpu', {}).get('high', 80)
        memory_high_threshold = resource_thresholds.get('memory', {}).get('high', 85)
        
        # Align time boundaries
        start_time = max(perf_df['timestamp'].min(), infra_df['timestamp'].min())
        end_time = min(perf_df['timestamp'].max(), infra_df['timestamp'].max())
        
        # Filter to common time range
        perf_df = perf_df[(perf_df['timestamp'] >= start_time) & (perf_df['timestamp'] <= end_time)].copy()
        infra_df = infra_df[(infra_df['timestamp'] >= start_time) & (infra_df['timestamp'] <= end_time)].copy()
        
        if perf_df.empty or infra_df.empty:
            results["error"] = "No overlapping time range between performance and infrastructure data"
            return results
        
        # === FAST PANDAS APPROACH: Resample both to same granularity ===
        # Set timestamp as index for resampling
        perf_indexed = perf_df.set_index('timestamp')
        infra_indexed = infra_df.set_index('timestamp')
        
        # Resample performance data to time windows (vectorized aggregation)
        perf_resampled = perf_indexed.resample(f'{granularity_window}S').agg({
            'elapsed': ['mean', 'max', 'count'],
            'sla_violation': 'sum'
        })
        perf_resampled.columns = ['avg_response_time', 'max_response_time', 'request_count', 'sla_violations']
        
        # Resample infrastructure data to same windows (vectorized aggregation)
        infra_resampled = infra_indexed.resample(f'{granularity_window}S').mean()
        
        # Merge on timestamp index (single operation)
        merged = pd.merge(
            perf_resampled, 
            infra_resampled, 
            left_index=True, 
            right_index=True, 
            how='inner'
        )
        
        # Drop windows with no data
        merged = merged[merged['request_count'] > 0].copy()
        
        if merged.empty:
            results["error"] = "No data after resampling and merging"
            return results
        
        # Add flags for constraints (vectorized boolean operations)
        merged['cpu_constraint'] = merged['cpu_utilization_pct'] > cpu_high_threshold
        merged['memory_constraint'] = merged['memory_utilization_pct'] > memory_high_threshold
        merged['performance_degradation'] = merged['avg_response_time'] > sla_threshold
        
        # Filter to interesting periods (performance issues OR high resource usage)
        interesting = merged[
            (merged['sla_violations'] > 0) | 
            (merged['cpu_constraint']) | 
            (merged['memory_constraint']) |
            (merged['performance_degradation'])
        ].copy()
        
        # Build analysis periods from interesting windows with API breakdown
        for timestamp, row in interesting.iterrows():
            # Get API breakdown for this time window
            window_start = timestamp
            window_end = timestamp + pd.Timedelta(seconds=granularity_window)
            
            window_apis = perf_indexed[
                (perf_indexed.index >= window_start) & 
                (perf_indexed.index < window_end)
            ].copy()
            
            # Calculate per-API stats for this window
            api_breakdown = []
            if not window_apis.empty and 'label' in window_apis.columns:
                api_stats = window_apis.groupby('label').agg({
                    'elapsed': ['mean', 'max', 'count'],
                    'sla_violation': 'sum'
                }).reset_index()
                
                api_stats.columns = ['api_name', 'avg_response_time', 'max_response_time', 'request_count', 'sla_violations']
                
                # Sort by average response time descending
                api_stats = api_stats.sort_values('avg_response_time', ascending=False)
                
                # Convert to list of dicts
                for _, api_row in api_stats.iterrows():
                    api_breakdown.append({
                        "api_name": str(api_row['api_name']),
                        "avg_response_time": float(api_row['avg_response_time']),
                        "max_response_time": float(api_row['max_response_time']),
                        "request_count": int(api_row['request_count']),
                        "sla_violations": int(api_row['sla_violations'])
                    })
            
            results["analysis_periods"].append({
                "time_window": timestamp.isoformat(),
                "performance_issues": {
                    "avg_response_time": float(row['avg_response_time']),
                    "max_response_time": float(row['max_response_time']),
                    "sla_violations": int(row['sla_violations']),
                    "total_requests": int(row['request_count']),
                    "sla_violation_rate": float((row['sla_violations'] / row['request_count']) * 100) if row['request_count'] > 0 else 0
                },
                "infrastructure_metrics": {
                    "avg_cpu": float(row['cpu_utilization_pct']),
                    "avg_memory": float(row['memory_utilization_pct'])
                },
                "correlation_analysis": {
                    "cpu_constraint": bool(row['cpu_constraint']),
                    "memory_constraint": bool(row['memory_constraint']),
                    "performance_degradation": bool(row['performance_degradation'])
                },
                "api_breakdown": api_breakdown
            })
        
        # === CALCULATE CORRELATIONS (vectorized) ===
        # Use all windows (not just interesting ones) for correlation
        cpu_rt_corr = merged['cpu_utilization_pct'].corr(merged['avg_response_time'])
        memory_rt_corr = merged['memory_utilization_pct'].corr(merged['avg_response_time'])
        cpu_sla_corr = merged['cpu_utilization_pct'].corr(merged['sla_violations'])
        memory_sla_corr = merged['memory_utilization_pct'].corr(merged['sla_violations'])
        
        # Handle NaN correlations (happens when all values are constant)
        cpu_rt_corr = 0.0 if pd.isna(cpu_rt_corr) else float(cpu_rt_corr)
        memory_rt_corr = 0.0 if pd.isna(memory_rt_corr) else float(memory_rt_corr)
        cpu_sla_corr = 0.0 if pd.isna(cpu_sla_corr) else float(cpu_sla_corr)
        memory_sla_corr = 0.0 if pd.isna(memory_sla_corr) else float(memory_sla_corr)
        
        results["correlation_matrix"] = {
            "cpu_response_time_correlation": cpu_rt_corr,
            "memory_response_time_correlation": memory_rt_corr,
            "cpu_sla_violations_correlation": cpu_sla_corr,
            "memory_sla_violations_correlation": memory_sla_corr,
            "analysis_windows": len(merged),
            "interesting_periods": len(interesting),
            "total_correlation_samples": len(merged)
        }
        
        # Identify significant correlations
        threshold = 0.3
        if abs(cpu_rt_corr) >= threshold:
            results["significant_correlations"].append({
                "type": "cpu_response_time",
                "correlation_coefficient": cpu_rt_corr,
                "strength": "strong" if abs(cpu_rt_corr) > 0.7 else "moderate",
                "direction": "positive" if cpu_rt_corr > 0 else "negative",
                "interpretation": f"CPU utilization {'increases' if cpu_rt_corr > 0 else 'decreases'} with response time"
            })
        
        if abs(memory_rt_corr) >= threshold:
            results["significant_correlations"].append({
                "type": "memory_response_time", 
                "correlation_coefficient": memory_rt_corr,
                "strength": "strong" if abs(memory_rt_corr) > 0.7 else "moderate",
                "direction": "positive" if memory_rt_corr > 0 else "negative",
                "interpretation": f"Memory utilization {'increases' if memory_rt_corr > 0 else 'decreases'} with response time"
            })
        
        # Generate insights
        results["insights"].extend(generate_temporal_insights(results))
        
        return results
        
    except Exception as e:
        results["error"] = f"Temporal correlation analysis failed: {str(e)}"
        import traceback
        results["error_details"] = traceback.format_exc()
        return results

def analyze_time_window(window_perf: pd.DataFrame, window_infra: pd.DataFrame, 
                       window_start: pd.Timestamp, window_end: pd.Timestamp,
                       sla_threshold: float, cpu_high_threshold: float, 
                       memory_high_threshold: float) -> Optional[Dict]:
    """Analyze a single time window for performance and infrastructure correlation"""
    
    try:
        # Performance analysis
        perf_issues = {
            "avg_response_time": window_perf['elapsed'].mean(),
            "max_response_time": window_perf['elapsed'].max(),
            "sla_violations": window_perf['sla_violation'].sum(),
            "total_requests": len(window_perf),
            "sla_violation_rate": window_perf['sla_violation'].mean() * 100
        }
        
        # Infrastructure analysis
        infra_metrics = {
            "avg_cpu": window_infra['cpu_utilization_pct'].mean(),
            "peak_cpu": window_infra['cpu_utilization_pct'].max(),
            "avg_memory": window_infra['memory_utilization_pct'].mean(),
            "peak_memory": window_infra['memory_utilization_pct'].max()
        }
        
        # Only include windows with performance issues or high resource usage
        has_performance_issues = (perf_issues["sla_violation_rate"] > 10 or 
                                 perf_issues["avg_response_time"] > sla_threshold)
        has_high_resource_usage = (infra_metrics["avg_cpu"] > cpu_high_threshold or 
                                  infra_metrics["avg_memory"] > memory_high_threshold)
        
        if has_performance_issues or has_high_resource_usage:
            return {
                "time_window": f"{window_start.isoformat()} to {window_end.isoformat()}",
                "performance_issues": perf_issues,
                "infrastructure_metrics": infra_metrics,
                "correlation_analysis": {
                    "cpu_constraint": infra_metrics["avg_cpu"] > cpu_high_threshold,
                    "memory_constraint": infra_metrics["avg_memory"] > memory_high_threshold,
                    "performance_degradation": has_performance_issues
                }
            }
        
        return None
        
    except Exception as e:
        print(f"Error analyzing time window: {e}")
        return None

def generate_temporal_insights(results: Dict) -> List[str]:
    """Generate insights from temporal correlation analysis"""
    insights = []
    
    analysis_periods = results.get("analysis_periods", [])
    correlation_matrix = results.get("correlation_matrix", {})
    
    if not analysis_periods:
        insights.append("No significant performance issues or resource constraints detected during test")
        return insights
    
    # Count periods with different types of issues
    cpu_constrained_periods = sum(1 for period in analysis_periods 
                                if period["correlation_analysis"]["cpu_constraint"])
    memory_constrained_periods = sum(1 for period in analysis_periods 
                                   if period["correlation_analysis"]["memory_constraint"])
    performance_degraded_periods = sum(1 for period in analysis_periods 
                                     if period["correlation_analysis"]["performance_degradation"])
    
    insights.append(f"Analyzed {len(analysis_periods)} time periods with performance or resource issues")
    
    if cpu_constrained_periods > 0:
        insights.append(f"{cpu_constrained_periods} periods showed CPU constraints (>80% utilization)")
    
    if memory_constrained_periods > 0:
        insights.append(f"{memory_constrained_periods} periods showed memory constraints (>85% utilization)")
    
    if performance_degraded_periods > 0:
        insights.append(f"{performance_degraded_periods} periods showed performance degradation")
    
    # Correlation insights
    cpu_corr = correlation_matrix.get("cpu_response_time_correlation", 0)
    memory_corr = correlation_matrix.get("memory_response_time_correlation", 0)
    
    if abs(cpu_corr) > 0.3:
        insights.append(f"CPU utilization shows {'strong' if abs(cpu_corr) > 0.7 else 'moderate'} correlation with response time (r={cpu_corr:.3f})")
    
    if abs(memory_corr) > 0.3:
        insights.append(f"Memory utilization shows {'strong' if abs(memory_corr) > 0.7 else 'moderate'} correlation with response time (r={memory_corr:.3f})")
    
    return insights

def generate_temporal_correlation_summary(results: Dict) -> Dict:
    """Generate summary statistics for temporal correlation analysis"""
    
    analysis_periods = results.get("analysis_periods", [])
    correlation_matrix = results.get("correlation_matrix", {})
    significant_correlations = results.get("significant_correlations", [])
    
    return {
        "total_analysis_periods": len(analysis_periods),
        "total_correlations_found": len(significant_correlations),
        "strong_correlations": len([c for c in significant_correlations if c.get("strength") == "strong"]),
        "moderate_correlations": len([c for c in significant_correlations if c.get("strength") == "moderate"]),
        "cpu_related_correlations": len([c for c in significant_correlations if "cpu" in c.get("type", "")]),
        "memory_related_correlations": len([c for c in significant_correlations if "memory" in c.get("type", "")]),
        "positive_correlations": len([c for c in significant_correlations if c.get("direction") == "positive"]),
        "negative_correlations": len([c for c in significant_correlations if c.get("direction") == "negative"]),
        "correlation_samples": correlation_matrix.get("total_correlation_samples", 0)
    }

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
