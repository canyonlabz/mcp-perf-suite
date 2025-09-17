# utils/file_processor.py
import json
import csv
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
import aiofiles

# -----------------------------------------------
# File loading functions
# -----------------------------------------------
def load_jmeter_results(file_path: Path) -> Optional[pd.DataFrame]:
    """Load JMeter results from CSV file"""
    try:
        df = pd.read_csv(file_path)
        # Basic validation of required columns
        required_cols = ['timeStamp', 'elapsed', 'label', 'responseCode', 'success']
        if not all(col in df.columns for col in required_cols):
            return None
        return df
    except Exception:
        return None

def load_datadog_metrics(file_path: Path) -> Optional[pd.DataFrame]:
    """Load Datadog metrics from CSV file"""
    try:
        return pd.read_csv(file_path)
    except Exception:
        return None

# -----------------------------------------------
# File writing functions
# -----------------------------------------------
async def write_json_output(data: Dict[str, Any], file_path: Path) -> None:
    """Write data to JSON file asynchronously"""
    try:
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        raise Exception(f"Failed to write JSON file {file_path}: {str(e)}")

async def write_csv_output(data: List[Dict[str, Any]], file_path: Path, 
                          headers: Optional[List[str]] = None) -> None:
    """Write data to CSV file asynchronously"""
    try:
        if not data:
            return
        
        if headers is None:
            headers = list(data[0].keys()) if data else []
        
        async with aiofiles.open(file_path, 'w', newline='', encoding='utf-8') as f:
            # Use pandas for easier async CSV writing
            df = pd.DataFrame(data)
            csv_content = df.to_csv(index=False)
            await f.write(csv_content)
            
    except Exception as e:
        raise Exception(f"Failed to write CSV file {file_path}: {str(e)}")

async def write_markdown_output(content: str, file_path: Path) -> None:
    """Write markdown content to file asynchronously"""
    try:
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(content)
    except Exception as e:
        raise Exception(f"Failed to write Markdown file {file_path}: {str(e)}")

# -----------------------------------------------
# Analysis CSV writing functions
# -----------------------------------------------
async def write_performance_csv(analysis: Dict, csv_file: Path):
    """Write performance analysis to CSV format"""
    
    csv_data = []
    
    # Overall summary row
    overall = analysis.get('overall_stats', {})
    if overall and 'error' not in overall:
        csv_data.append({
            'metric_type': 'overall',
            'api_name': 'ALL',
            'samples': overall.get('total_samples', 0),
            'avg_response_time': overall.get('avg_response_time', 0),
            'min_response_time': overall.get('min_response_time', 0),
            'max_response_time': overall.get('max_response_time', 0),
            'p95_response_time': overall.get('p95_response_time', 0),
            'p99_response_time': overall.get('p99_response_time', 0),
            'success_rate': overall.get('success_rate', 0),
            'error_count': overall.get('error_count', 0),
            'avg_throughput': overall.get('avg_throughput', 0),
            'sla_compliant': None
        })
    
    # Individual API rows
    for api_name, api_stats in analysis.get('api_analysis', {}).items():
        csv_data.append({
            'metric_type': 'per_api',
            'api_name': api_name,
            'samples': api_stats.get('samples', 0),
            'avg_response_time': api_stats.get('avg_response_time', 0),
            'min_response_time': api_stats.get('min_response_time', 0),
            'max_response_time': api_stats.get('max_response_time', 0),
            'p95_response_time': api_stats.get('p95_response_time', 0),
            'p99_response_time': api_stats.get('p99_response_time', 0),
            'success_rate': api_stats.get('success_rate', 0),
            'error_count': api_stats.get('error_count', 0),
            'avg_throughput': api_stats.get('throughput', 0),
            'sla_compliant': api_stats.get('sla_compliant', None)
        })
    
    # Write to CSV
    df = pd.DataFrame(csv_data)
    df.to_csv(csv_file, index=False)

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

# -----------------------------------------------
# Formatting functions
# -----------------------------------------------
def format_performance_markdown(analysis: Dict, test_run_id: str) -> str:
    """Format performance analysis as markdown report"""
    
    overall = analysis.get('overall_stats', {})
    sla_analysis = analysis.get('sla_analysis', {})
    
    # Handle case where overall stats might have an error
    if 'error' in overall:
        total_samples = 'N/A'
        success_rate = 'N/A' 
        avg_rt = 'N/A'
    else:
        total_samples = f"{overall.get('total_samples', 'N/A'):,}"
        success_rate = f"{overall.get('success_rate', 'N/A'):.2f}%"
        avg_rt = f"{overall.get('avg_response_time', 'N/A'):.0f} ms"
    
    md_content = f"""# Performance Analysis Report - Run {test_run_id}

## Test Summary
- **Total Samples**: {total_samples}
- **Success Rate**: {success_rate}
- **Average Response Time**: {avg_rt}
- **Test Duration**: {overall.get('test_duration', 'N/A')} seconds

## Response Time Statistics
| Metric | Value (ms) |
|--------|------------|
| Minimum | {overall.get('min_response_time', 'N/A')} |
| Average | {overall.get('avg_response_time', 'N/A'):.0f} |
| Median | {overall.get('median_response_time', 'N/A'):.0f} |
| 95th Percentile | {overall.get('p95_response_time', 'N/A'):.0f} |
| 99th Percentile | {overall.get('p99_response_time', 'N/A'):.0f} |
| Maximum | {overall.get('max_response_time', 'N/A'):,} |

## SLA Analysis
- **SLA Threshold**: {sla_analysis.get('sla_threshold_ms', 'N/A')} ms
- **Compliance Rate**: {sla_analysis.get('compliance_rate', 'N/A'):.1f}%
- **APIs Meeting SLA**: {sla_analysis.get('compliant_apis', 'N/A')} / {sla_analysis.get('total_apis', 'N/A')}

"""
    
    # SLA Violations
    violations = sla_analysis.get('violations', [])
    if violations:
        md_content += "## SLA Violations\n\n"
        md_content += "| API Name | Avg Response Time | Violation Amount | Violation % |\n"
        md_content += "|----------|-------------------|------------------|-------------|\n"
        
        for violation in violations:
            md_content += f"| {violation['api_name']} | {violation['avg_response_time']:.0f} ms | {violation['violation_amount']:.0f} ms "
            md_content += f"| {violation['violation_percentage']:.1f}% |\n"
        md_content += "\n"
    
    # Top APIs by Response Time
    api_analysis = analysis.get('api_analysis', {})
    if api_analysis:
        sorted_apis = sorted(api_analysis.items(), 
                           key=lambda x: x[1].get('avg_response_time', 0), 
                           reverse=True)[:10]
        
        md_content += "## Top 10 Slowest APIs\n\n"
        md_content += "| API Name | Avg Response (ms) | Samples | Success Rate | SLA Status |\n"
        md_content += "|----------|-------------------|---------|--------------|------------|\n"
        
        for api_name, stats in sorted_apis:
            sla_status = "✅ Pass" if stats.get('sla_compliant') else "❌ Fail"
            md_content += f"| {api_name[:50]}{'...' if len(api_name) > 50 else ''} | {stats.get('avg_response_time', 'N/A'):.0f} "
            md_content += f"| {stats.get('samples', 'N/A')} | {stats.get('success_rate', 'N/A'):.2f}% | {sla_status} |\n"
    
    md_content += f"\n---\n*Generated: {analysis.get('analysis_timestamp', 'N/A')}*"
    
    return md_content

def format_infrastructure_markdown(analysis: Dict) -> str:
    """Format infrastructure analysis as markdown"""
    # Implementation for markdown formatting
    return "# Infrastructure Analysis\n\n"

def format_correlation_markdown(correlation_results: Dict) -> str:
    """Format correlation analysis as markdown"""
    # Implementation for markdown formatting
    return "# Correlation Analysis\n\n"

def format_anomalies_markdown(anomalies: Dict) -> str:
    """Format anomaly detection as markdown"""
    # Implementation for markdown formatting
    return "# Anomaly Detection\n\n"

def format_bottlenecks_markdown(bottlenecks: Dict) -> str:
    """Format bottleneck analysis as markdown"""
    # Implementation for markdown formatting
    return "# Bottleneck Analysis\n\n"

def format_comparison_markdown(comparison_results: Dict) -> str:
    """Format test run comparison as markdown"""
    # Implementation for markdown formatting
    return "# Test Run Comparison\n\n"

def format_executive_markdown(summary: Dict) -> str:
    """Format executive summary as markdown"""
    # Implementation for markdown formatting
    return "# Executive Summary\n\n"