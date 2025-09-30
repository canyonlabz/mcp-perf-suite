"""
APM Tool Agnostic Infrastructure Analysis Module

Handles analysis of infrastructure metrics from various APM tools:
- Datadog
- Dynatrace  
- AppDynamics
- New Relic
- etc.

Centralizes all infrastructure metric calculations, unit conversions, 
and resource utilization analysis.
"""
import json
import re
from typing import Dict, List, Optional, Any, Tuple
from fastmcp import Context     # ✅ FastMCP 2.x import
from pathlib import Path
import pandas as pd
import numpy as np
import math
import datetime
from utils.file_processor import (
    write_json_output,
    write_markdown_output,
    write_infrastructure_csv,
    format_infrastructure_markdown,
)

# -----------------------------------------------
# Main Function for the APM Analyzer MCP
# -----------------------------------------------
async def perform_infrastructure_analysis(
    k8s_files: List[Path], host_files: List[Path], 
    environments_config: Dict, config: Dict, test_run_id: str, ctx: Context
) -> Dict[str, Any]:
    """Perform comprehensive infrastructure metrics analysis"""
    
    analysis_results = {
        "infrastructure_summary": {},
        "resource_utilization": {},
        "detailed_metrics": {},
        "resource_insights": {},
        "assumptions_made": [],
        "environments_analyzed": [],
        "analysis_timestamp": datetime.datetime.now().isoformat()
    }
    
    # Analyze Kubernetes metrics if present
    if k8s_files:
        await ctx.info("K8s Analysis", f"Processing {len(k8s_files)} Kubernetes metrics files")
        k8s_analysis = await analyze_kubernetes_metrics(k8s_files, environments_config, config, ctx)
        analysis_results["detailed_metrics"]["kubernetes"] = k8s_analysis
        analysis_results["environments_analyzed"].extend(k8s_analysis.get("environments", []))
        analysis_results["assumptions_made"].extend(k8s_analysis.get("assumptions", []))
    
    # Analyze Host metrics if present  
    if host_files:
        await ctx.info("Host Analysis", f"Processing {len(host_files)} host metrics files")
        host_analysis = await analyze_host_metrics(host_files, environments_config, config, ctx)
        analysis_results["detailed_metrics"]["hosts"] = host_analysis
        analysis_results["environments_analyzed"].extend(host_analysis.get("environments", []))
        analysis_results["assumptions_made"].extend(host_analysis.get("assumptions", []))
    
    # Generate overall infrastructure summary
    analysis_results["infrastructure_summary"] = generate_infrastructure_summary(analysis_results)
    
    # Generate resource utilization insights
    analysis_results["resource_insights"] = generate_resource_insights(analysis_results, config)
    
    return analysis_results

# -----------------------------------------------
# Kubernetes Analysis Functions
# -----------------------------------------------
async def analyze_kubernetes_metrics(
    k8s_files: List[Path], environments_config: Dict, config: Dict, ctx: Context
) -> Dict[str, Any]:
    """Analyze Kubernetes container metrics with correct nanocore calculations"""
    
    k8s_analysis = {
        "services": {},
        "environments": [],
        "assumptions": [],
        "total_containers": 0,
        "metrics_summary": {}
    }
    
    # Combine all K8s CSV files
    all_k8s_data = []
    for k8s_file in k8s_files:
        try:
            df = pd.read_csv(k8s_file)
            all_k8s_data.append(df)
        except Exception as e:
            await ctx.error(f"K8s File Error", f"Failed to read {k8s_file}: {str(e)}")
            continue
    
    if not all_k8s_data:
        return k8s_analysis
    
    # Combine all dataframes
    combined_df = pd.concat(all_k8s_data, ignore_index=True)
    
    # Get unique environments
    environments = combined_df['env_name'].unique().tolist()
    k8s_analysis["environments"] = environments
    
    # Process each environment
    for env_name in environments:
        env_data = combined_df[combined_df['env_name'] == env_name]
        env_config = environments_config.get("environments", {}).get(env_name, {})
        
        # Get K8s services configuration
        k8s_config = env_config.get("kubernetes", {})
        services_config = k8s_config.get("services", [])
        
        # Analyze each unique service
        unique_services = env_data['service_filter'].unique()
        
        for service_name in unique_services:
            service_data = env_data[env_data['service_filter'] == service_name]
            
            # Find matching service configuration
            service_config = next(
                (s for s in services_config if s.get('service_filter') == service_name), 
                {}
            )
            
            # Get resource allocation (with config-driven defaults)
            resource_allocation = get_kubernetes_resource_allocation(service_config, service_name, config)
            
            # Track assumptions
            if not service_config:
                k8s_analysis["assumptions"].append(
                    f"K8s Service '{service_name}' not found in environments.json - "
                    f"using defaults: {resource_allocation['cpus']} cores, {resource_allocation['memory_gb']}GB"
                )
            else:
                if 'cpus' not in service_config:
                    k8s_analysis["assumptions"].append(
                        f"K8s Service '{service_name}' missing CPU config - assumed {resource_allocation['cpus']} cores"
                    )
                if 'memory' not in service_config:
                    k8s_analysis["assumptions"].append(
                        f"K8s Service '{service_name}' missing memory config - assumed {resource_allocation['memory_gb']}GB"
                    )
            
            # Analyze service metrics
            service_analysis = analyze_k8s_service_metrics(service_data, resource_allocation, config)
            k8s_analysis["services"][f"{env_name}::{service_name}"] = service_analysis
            
            # Count containers
            container_count = service_data['container_or_pod'].nunique()
            k8s_analysis["total_containers"] += container_count
    
    return k8s_analysis

def get_kubernetes_resource_allocation(service_config: Dict, service_name: str, config: Dict) -> Dict:
    """Get K8s resource allocation with config-driven fallbacks"""
    
    defaults = config['perf_analysis']['default_resources']['kubernetes']
    
    return {
        "cpus": parse_cpu_cores(service_config.get("cpus", f"{defaults['cpus']} core")),
        "memory_gb": parse_memory_gib(service_config.get("memory", f"{defaults['memory_gb']}GiB"))
    }

def analyze_k8s_service_metrics(service_data: pd.DataFrame, resource_allocation: Dict, config: Dict) -> Dict:
    """Analyze individual K8s service metrics with CORRECT nanocore calculations"""
    
    # Separate CPU and Memory metrics
    cpu_data = service_data[service_data['metric'].str.contains('cpu', case=False, na=False)]
    memory_data = service_data[service_data['metric'].str.contains('mem', case=False, na=False)]
    
    service_metrics = {
        "resource_allocation": resource_allocation,
        "cpu_analysis": {},
        "memory_analysis": {},
        "containers": {},
        "time_range": {},
        "peak_utilization": {}
    }
    
    # Time range analysis
    if not service_data.empty:
        service_metrics["time_range"] = {
            "start_time": service_data['timestamp_utc'].min(),
            "end_time": service_data['timestamp_utc'].max(),
            "duration_minutes": calculate_duration_minutes(service_data['timestamp_utc'])
        }
    
    # CPU Analysis with CORRECT nanocore conversion
    if not cpu_data.empty:
        # CRITICAL: Use /1e3 for microcores to cores conversion
        cpu_data_converted = cpu_data.copy()
        cpu_data_converted['cpu_cores'] = cpu_data_converted['value'] / 1e3  # microcores to cores

        service_metrics["cpu_analysis"] = {
            "allocated_cores": resource_allocation['cpus'],
            "peak_usage_cores": float(cpu_data_converted['cpu_cores'].max()),
            "avg_usage_cores": float(cpu_data_converted['cpu_cores'].mean()),
            "min_usage_cores": float(cpu_data_converted['cpu_cores'].min()),
            "peak_utilization_pct": float((cpu_data_converted['cpu_cores'].max() / resource_allocation['cpus']) * 100),
            "avg_utilization_pct": float((cpu_data_converted['cpu_cores'].mean() / resource_allocation['cpus']) * 100),
            "samples_count": len(cpu_data_converted)
        }
    
    # Memory Analysis  
    if not memory_data.empty:
        memory_data_converted = memory_data.copy()
        memory_data_converted['memory_gb'] = memory_data_converted['value'] / 1e9  # bytes to GB
        
        service_metrics["memory_analysis"] = {
            "allocated_gb": resource_allocation['memory_gb'],
            "peak_usage_gb": float(memory_data_converted['memory_gb'].max()),
            "avg_usage_gb": float(memory_data_converted['memory_gb'].mean()),
            "min_usage_gb": float(memory_data_converted['memory_gb'].min()),
            "peak_utilization_pct": float((memory_data_converted['memory_gb'].max() / resource_allocation['memory_gb']) * 100),
            "avg_utilization_pct": float((memory_data_converted['memory_gb'].mean() / resource_allocation['memory_gb']) * 100),
            "samples_count": len(memory_data_converted)
        }
    
    # Container-level breakdown
    containers = service_data['container_or_pod'].unique()
    for container in containers:
        container_data = service_data[service_data['container_or_pod'] == container]
        
        container_cpu = container_data[container_data['metric'].str.contains('cpu', case=False, na=False)]
        container_memory = container_data[container_data['metric'].str.contains('mem', case=False, na=False)]
        
        service_metrics["containers"][container] = {
            "cpu_samples": len(container_cpu),
            "memory_samples": len(container_memory),
            "peak_cpu_cores": float(container_cpu['value'].max() / 1e6) if not container_cpu.empty else 0,
            "peak_memory_gb": float(container_memory['value'].max() / 1e9) if not container_memory.empty else 0
        }
    
    return service_metrics

# -----------------------------------------------
# Host Analysis Functions
# -----------------------------------------------
async def analyze_host_metrics(
    host_files: List[Path], environments_config: Dict, config: Dict, ctx: Context
) -> Dict[str, Any]:
    """Analyze host/VM metrics"""
    
    host_analysis = {
        "hosts": {},
        "environments": [],
        "assumptions": [],
        "total_hosts": 0,
        "metrics_summary": {}
    }
    
    # Combine all host CSV files
    all_host_data = []
    for host_file in host_files:
        try:
            df = pd.read_csv(host_file)
            all_host_data.append(df)
        except Exception as e:
            await ctx.error(f"Host File Error", f"Failed to read {host_file}: {str(e)}")
            continue
    
    if not all_host_data:
        return host_analysis
    
    # Combine all dataframes
    combined_df = pd.concat(all_host_data, ignore_index=True)
    
    # Get unique environments
    environments = combined_df['env_name'].unique().tolist()
    host_analysis["environments"] = environments
    
    # Process each environment
    for env_name in environments:
        env_data = combined_df[combined_df['env_name'] == env_name]
        env_config = environments_config.get("environments", {}).get(env_name, {})
        
        # Get hosts configuration
        hosts_config = env_config.get("hosts", [])
        
        # Analyze each unique host
        unique_hosts = env_data['hostname'].unique()
        
        for hostname in unique_hosts:
            host_data = env_data[env_data['hostname'] == hostname]
            
            # Find matching host configuration
            host_config = next(
                (h for h in hosts_config if h.get('hostname') == hostname),
                {}
            )
            
            # Get resource allocation (with config-driven defaults)
            resource_allocation = get_host_resource_allocation(host_config, hostname, config)
            
            # Track assumptions
            if not host_config:
                host_analysis["assumptions"].append(
                    f"Host '{hostname}' not found in environments.json - "
                    f"using defaults: {resource_allocation['cpus']} CPUs, {resource_allocation['memory_gb']}GB"
                )
            else:
                if 'cpus' not in host_config:
                    host_analysis["assumptions"].append(
                        f"Host '{hostname}' missing CPU config - assumed {resource_allocation['cpus']} CPUs"
                    )
                if 'memory' not in host_config:
                    host_analysis["assumptions"].append(
                        f"Host '{hostname}' missing memory config - assumed {resource_allocation['memory_gb']}GB"
                    )
            
            # Analyze host metrics
            host_metrics_analysis = analyze_host_system_metrics(host_data, resource_allocation, config)
            host_analysis["hosts"][f"{env_name}::{hostname}"] = host_metrics_analysis
            
            host_analysis["total_hosts"] += 1
    
    return host_analysis

def get_host_resource_allocation(host_config: Dict, hostname: str, config: Dict) -> Dict:
    """Get host resource allocation with config-driven fallbacks"""
    
    defaults = config['perf_analysis']['default_resources']['host']
    
    return {
        "cpus": host_config.get("cpus", defaults["cpus"]),
        "memory_gb": parse_memory_gb(host_config.get("memory", f"{defaults['memory_gb']}GB"))
    }

def analyze_host_system_metrics(host_data: pd.DataFrame, resource_allocation: Dict, config: Dict) -> Dict:
    """Analyze individual host system metrics"""
    
    # Separate CPU and Memory metrics
    cpu_data = host_data[host_data['metric'].str.contains('cpu', case=False, na=False)]
    memory_data = host_data[host_data['metric'].str.contains('mem', case=False, na=False)]
    
    host_metrics = {
        "resource_allocation": resource_allocation,
        "cpu_analysis": {},
        "memory_analysis": {},
        "time_range": {},
        "metric_types": host_data['metric'].unique().tolist()
    }
    
    # Time range analysis
    if not host_data.empty:
        host_metrics["time_range"] = {
            "start_time": host_data['timestamp_utc'].min(),
            "end_time": host_data['timestamp_utc'].max(),
            "duration_minutes": calculate_duration_minutes(host_data['timestamp_utc'])
        }
    
    # CPU Analysis (Host CPU already in percentages)
    if not cpu_data.empty:
        # Calculate total CPU utilization (sum of user + system if both present)
        cpu_user = cpu_data[cpu_data['metric'] == 'system.cpu.user']['value']
        cpu_system = cpu_data[cpu_data['metric'] == 'system.cpu.system']['value'] 
        
        if not cpu_user.empty and not cpu_system.empty:
            total_cpu_pct = cpu_user + cpu_system
        elif not cpu_user.empty:
            total_cpu_pct = cpu_user
        elif not cpu_system.empty:
            total_cpu_pct = cpu_system
        else:
            total_cpu_pct = cpu_data['value']  # Fallback to any CPU metric
        
        if not total_cpu_pct.empty:
            host_metrics["cpu_analysis"] = {
                "allocated_cpus": resource_allocation['cpus'],
                "peak_utilization_pct": float(total_cpu_pct.max()),
                "avg_utilization_pct": float(total_cpu_pct.mean()),
                "min_utilization_pct": float(total_cpu_pct.min()),
                "samples_count": len(total_cpu_pct),
                "metrics_included": cpu_data['metric'].unique().tolist()
            }
    
    # Memory Analysis
    if not memory_data.empty:
        # Look for memory usage percentage or calculate from raw values
        mem_used_pct = memory_data[memory_data['metric'] == 'mem_used_pct']['value']
        
        if not mem_used_pct.empty:
            # Direct percentage available
            host_metrics["memory_analysis"] = {
                "allocated_gb": resource_allocation['memory_gb'],
                "peak_utilization_pct": float(mem_used_pct.max()),
                "avg_utilization_pct": float(mem_used_pct.mean()),
                "min_utilization_pct": float(mem_used_pct.min()),
                "samples_count": len(mem_used_pct),
                "calculation_method": "direct_percentage"
            }
        else:
            # Calculate from raw memory values if available
            mem_used = memory_data[memory_data['metric'] == 'system.mem.used']['value']
            mem_total = memory_data[memory_data['metric'] == 'system.mem.total']['value']
            
            if not mem_used.empty and not mem_total.empty:
                # Convert to GB and calculate percentage
                mem_used_gb = mem_used / 1e9
                mem_total_gb = mem_total / 1e9
                mem_util_pct = (mem_used_gb / mem_total_gb) * 100
                
                host_metrics["memory_analysis"] = {
                    "allocated_gb": resource_allocation['memory_gb'],
                    "peak_usage_gb": float(mem_used_gb.max()),
                    "avg_usage_gb": float(mem_used_gb.mean()),
                    "detected_total_gb": float(mem_total_gb.mean()),
                    "peak_utilization_pct": float(mem_util_pct.max()),
                    "avg_utilization_pct": float(mem_util_pct.mean()),
                    "samples_count": len(mem_util_pct),
                    "calculation_method": "calculated_from_raw"
                }
    
    return host_metrics

# -----------------------------------------------
# Utility Functions 
# -----------------------------------------------
def parse_cpu_cores(cpu_str: str) -> float:
    """Parse CPU allocation from various formats with robust handling"""
    if isinstance(cpu_str, (int, float)):
        return float(cpu_str)
    
    try:
        # Handle formats: "4.05 core", "4 cores", "4.0", "4"
        import re
        cpu_str = str(cpu_str).lower()
        matches = re.findall(r'(\d+\.?\d*)', cpu_str)
        return float(matches[0]) if matches else 2.0
    except (ValueError, AttributeError):
        return 2.0  # Safe default from config

def parse_memory_gb(memory_str: str) -> float:
    """Parse memory allocation from various formats"""
    if isinstance(memory_str, (int, float)):
        return float(memory_str)
    
    try:
        import re
        memory_str = str(memory_str).upper()
        
        # Extract numeric value
        matches = re.findall(r'(\d+\.?\d*)', memory_str)
        if not matches:
            return 8.0
        
        value = float(matches[0])
        
        # Convert based on unit
        if 'GB' in memory_str or 'GIB' in memory_str:
            return value
        elif 'MB' in memory_str or 'MIB' in memory_str:
            return value / 1024
        elif 'TB' in memory_str or 'TIB' in memory_str:
            return value * 1024
        else:
            return value  # Assume GB if no unit
    except (ValueError, AttributeError):
        return 8.0  # Safe default from config

def parse_memory_gib(memory_str: str) -> float:
    """Parse memory allocation from GiB format (same as GB for practical purposes)"""
    return parse_memory_gb(memory_str)

def calculate_duration_minutes(timestamp_series) -> float:
    """Calculate duration in minutes from timestamp series"""
    try:
        start_time = pd.to_datetime(timestamp_series.min())
        end_time = pd.to_datetime(timestamp_series.max())
        duration = (end_time - start_time).total_seconds() / 60
        return round(duration, 2)
    except:
        return 0.0

# -----------------------------------------------
# Summary & Insight Functions
# -----------------------------------------------
def generate_infrastructure_summary(analysis_results: Dict) -> Dict:
    """Generate overall infrastructure summary"""
    
    summary = {
        "total_environments": len(analysis_results.get("environments_analyzed", [])),
        "kubernetes_summary": {},
        "host_summary": {},
        "overall_health": "unknown"
    }
    
    # K8s summary
    k8s_data = analysis_results.get("detailed_metrics", {}).get("kubernetes", {})
    if k8s_data:
        summary["kubernetes_summary"] = {
            "total_services": len(k8s_data.get("services", {})),
            "total_containers": k8s_data.get("total_containers", 0),
            "environments": k8s_data.get("environments", [])
        }
    
    # Host summary
    host_data = analysis_results.get("detailed_metrics", {}).get("hosts", {})
    if host_data:
        summary["host_summary"] = {
            "total_hosts": host_data.get("total_hosts", 0),
            "environments": host_data.get("environments", [])
        }
    
    return summary

def generate_resource_insights(analysis_results: Dict, config: Dict) -> Dict:
    """Generate resource utilization insights with config-driven thresholds"""
    
    cpu_thresholds = config['perf_analysis']['resource_thresholds']['cpu']
    memory_thresholds = config['perf_analysis']['resource_thresholds']['memory']
    
    insights = {
        "high_utilization": [],
        "low_utilization": [],
        "right_sized": [],
        "recommendations": []
    }
    
    # Analyze K8s resources
    k8s_data = analysis_results.get("detailed_metrics", {}).get("kubernetes", {})
    for service_name, service_metrics in k8s_data.get("services", {}).items():
        analyze_service_utilization(service_name, service_metrics, cpu_thresholds, memory_thresholds, insights)
    
    # Analyze Host resources
    host_data = analysis_results.get("detailed_metrics", {}).get("hosts", {})
    for host_name, host_metrics in host_data.get("hosts", {}).items():
        analyze_host_utilization(host_name, host_metrics, cpu_thresholds, memory_thresholds, insights)
    
    return insights

def analyze_service_utilization(service_name: str, service_metrics: Dict, cpu_thresholds: Dict, memory_thresholds: Dict, insights: Dict):
    """Analyze K8s service utilization against thresholds"""
    
    cpu_analysis = service_metrics.get("cpu_analysis", {})
    memory_analysis = service_metrics.get("memory_analysis", {})
    
    # CPU utilization analysis
    if cpu_analysis:
        peak_cpu_pct = cpu_analysis.get("peak_utilization_pct", 0)
        avg_cpu_pct = cpu_analysis.get("avg_utilization_pct", 0)
        
        if peak_cpu_pct > cpu_thresholds['high']:
            insights["high_utilization"].append({
                "resource": f"{service_name} (CPU)",
                "type": "kubernetes",
                "peak_utilization": peak_cpu_pct,
                "avg_utilization": avg_cpu_pct,
                "threshold": cpu_thresholds['high'],
                "recommendation": f"CPU usage peaked at {peak_cpu_pct:.1f}% - consider increasing CPU allocation"
            })
        elif avg_cpu_pct < cpu_thresholds['low']:
            insights["low_utilization"].append({
                "resource": f"{service_name} (CPU)",
                "type": "kubernetes", 
                "avg_utilization": avg_cpu_pct,
                "threshold": cpu_thresholds['low'],
                "recommendation": f"CPU avg usage {avg_cpu_pct:.1f}% - consider reducing allocation to save costs"
            })
        else:
            insights["right_sized"].append({
                "resource": f"{service_name} (CPU)",
                "utilization": avg_cpu_pct,
                "status": "well-utilized"
            })
    
    # Memory utilization analysis  
    if memory_analysis:
        peak_mem_pct = memory_analysis.get("peak_utilization_pct", 0)
        avg_mem_pct = memory_analysis.get("avg_utilization_pct", 0)
        
        if peak_mem_pct > memory_thresholds['high']:
            insights["high_utilization"].append({
                "resource": f"{service_name} (Memory)",
                "type": "kubernetes",
                "peak_utilization": peak_mem_pct,
                "avg_utilization": avg_mem_pct,
                "threshold": memory_thresholds['high'],
                "recommendation": f"Memory usage peaked at {peak_mem_pct:.1f}% - consider increasing memory allocation"
            })
        elif avg_mem_pct < memory_thresholds['low']:
            insights["low_utilization"].append({
                "resource": f"{service_name} (Memory)",
                "type": "kubernetes",
                "avg_utilization": avg_mem_pct,
                "threshold": memory_thresholds['low'],
                "recommendation": f"Memory avg usage {avg_mem_pct:.1f}% - consider reducing allocation to save costs"
            })
        else:
            insights["right_sized"].append({
                "resource": f"{service_name} (Memory)",
                "utilization": avg_mem_pct,
                "status": "well-utilized"
            })

def analyze_host_utilization(host_name: str, host_metrics: Dict, cpu_thresholds: Dict, memory_thresholds: Dict, insights: Dict):
    """Analyze host utilization against thresholds"""
    
    cpu_analysis = host_metrics.get("cpu_analysis", {})
    memory_analysis = host_metrics.get("memory_analysis", {})
    
    # CPU utilization analysis
    if cpu_analysis:
        peak_cpu_pct = cpu_analysis.get("peak_utilization_pct", 0)
        avg_cpu_pct = cpu_analysis.get("avg_utilization_pct", 0)
        
        if peak_cpu_pct > cpu_thresholds['high']:
            insights["high_utilization"].append({
                "resource": f"{host_name} (CPU)",
                "type": "host",
                "peak_utilization": peak_cpu_pct,
                "avg_utilization": avg_cpu_pct,
                "threshold": cpu_thresholds['high'],
                "recommendation": f"CPU usage peaked at {peak_cpu_pct:.1f}% - monitor for potential scaling needs"
            })
        elif avg_cpu_pct < cpu_thresholds['low']:
            insights["low_utilization"].append({
                "resource": f"{host_name} (CPU)",
                "type": "host",
                "avg_utilization": avg_cpu_pct,
                "threshold": cpu_thresholds['low'],
                "recommendation": f"CPU avg usage {avg_cpu_pct:.1f}% - host may be over-provisioned"
            })
        else:
            insights["right_sized"].append({
                "resource": f"{host_name} (CPU)",
                "utilization": avg_cpu_pct,
                "status": "well-utilized"
            })
    
    # Memory utilization analysis
    if memory_analysis:
        peak_mem_pct = memory_analysis.get("peak_utilization_pct", 0)
        avg_mem_pct = memory_analysis.get("avg_utilization_pct", 0)
        
        if peak_mem_pct > memory_thresholds['high']:
            insights["high_utilization"].append({
                "resource": f"{host_name} (Memory)",
                "type": "host",
                "peak_utilization": peak_mem_pct,
                "avg_utilization": avg_mem_pct,
                "threshold": memory_thresholds['high'],
                "recommendation": f"Memory usage peaked at {peak_mem_pct:.1f}% - monitor for potential memory pressure"
            })
        elif avg_mem_pct < memory_thresholds['low']:
            insights["low_utilization"].append({
                "resource": f"{host_name} (Memory)",
                "type": "host",
                "avg_utilization": avg_mem_pct,
                "threshold": memory_thresholds['low'],
                "recommendation": f"Memory avg usage {avg_mem_pct:.1f}% - host may be over-provisioned"
            })
        else:
            insights["right_sized"].append({
                "resource": f"{host_name} (Memory)",
                "utilization": avg_mem_pct,
                "status": "well-utilized"
            })

async def generate_infrastructure_outputs(analysis: Dict, output_path: Path, test_run_id: str, ctx: Context) -> Dict[str, str]:
    """Generate all output files for infrastructure analysis"""
    
    output_files = {}
    
    try:
        # JSON Output - Detailed analysis
        json_file = output_path / 'infrastructure_analysis.json'
        await write_json_output(analysis, json_file)
        output_files['json'] = str(json_file)
        
        # CSV Output - Structured data for reporting
        csv_file = output_path / 'infrastructure_summary.csv'
        await write_infrastructure_csv(analysis, csv_file)
        output_files['csv'] = str(csv_file)
        
        # Markdown Output - Human-readable summary
        markdown_file = output_path / 'infrastructure_summary.md'
        markdown_content = format_infrastructure_markdown(analysis, test_run_id)
        await write_markdown_output(markdown_content, markdown_file)
        output_files['markdown'] = str(markdown_file)
        
        await ctx.info("Infrastructure Output Generation", f"Generated {len(output_files)} analysis files")
        
    except Exception as e:
        await ctx.error("Infrastructure Output Generation Error", f"Failed to generate outputs: {str(e)}")
    
    return output_files

