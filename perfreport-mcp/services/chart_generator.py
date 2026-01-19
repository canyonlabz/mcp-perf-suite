"""
services/chart_generator.py
Chart generation for performance reports using Matplotlib
"""

import json
import yaml
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import numpy as np
import pytz
from fastmcp import Context

# Import config at module level
from utils.config import load_config, load_chart_colors

# Import chart utilities
from utils.chart_utils import (
    load_environment_details,
    get_metric_files
)

# Import chart functions
from services.charts import single_axis_charts, dual_axis_charts, multi_line_charts, comparison_bar_charts

# Load configuration globally
CONFIG = load_config()
ARTIFACTS_CONFIG = CONFIG.get('artifacts', {})
ARTIFACTS_PATH = Path(ARTIFACTS_CONFIG.get('artifacts_path', '../artifacts'))
CHART_COLORS = load_chart_colors()

# Load chart schema
REPO_ROOT = Path(__file__).parent.parent
CHART_SCHEMA_PATH = REPO_ROOT / "chart_schema.yaml"

with open(CHART_SCHEMA_PATH, 'r') as f:
    CHART_SCHEMA = yaml.safe_load(f)

# Chart defaults
CHART_DEFAULTS = CHART_SCHEMA.get('defaults', {})
CHART_WIDTH = CHART_DEFAULTS['resolution']['width'] / CHART_DEFAULTS['resolution']['dpi']
CHART_HEIGHT = CHART_DEFAULTS['resolution']['height'] / CHART_DEFAULTS['resolution']['dpi']
DPI = CHART_DEFAULTS['resolution']['dpi']

# Chart mapping to functions and data sources
chart_module_registry = {
    "single_axis_charts": single_axis_charts,
    "dual_axis_charts": dual_axis_charts,
    "multi_line_charts": multi_line_charts,
    "comparison_bar_charts": comparison_bar_charts,
}

chart_map = {
    "CPU_UTILIZATION_LINE": {
        "function": "generate_cpu_utilization_chart",
        "module": "single_axis_charts",
        "data_source": "infrastructure",
    },
    "MEMORY_UTILIZATION_LINE": {
        "function": "generate_memory_utilization_chart",
        "module": "single_axis_charts",
        "data_source": "infrastructure",
    },
    # CPU/Memory raw usage charts (Cores/GB instead of %)
    "CPU_CORES_LINE": {
        "function": "generate_cpu_cores_chart",
        "module": "single_axis_charts",
        "data_source": "infrastructure",
    },
    "MEMORY_USAGE_LINE": {
        "function": "generate_memory_usage_chart",
        "module": "single_axis_charts",
        "data_source": "infrastructure",
    },
    "RESP_TIME_P90_VUSERS_DUALAXIS": {
        "function": "generate_p90_vusers_chart",
        "module": "dual_axis_charts",
        "data_source": "performance",
    },
    # Multi-line charts (all hosts/services on single chart)
    "CPU_UTILIZATION_MULTILINE": {
        "function": "generate_cpu_utilization_multiline_chart",
        "module": "multi_line_charts",
        "data_source": "infrastructure_multi",
    },
    "MEMORY_UTILIZATION_MULTILINE": {
        "function": "generate_memory_utilization_multiline_chart",
        "module": "multi_line_charts",
        "data_source": "infrastructure_multi",
    },
    # Infrastructure vs VUsers dual-axis charts
    "CPU_UTILIZATION_VUSERS_DUALAXIS": {
        "function": "generate_cpu_utilization_vusers_chart",
        "module": "dual_axis_charts",
        "data_source": "infrastructure_performance",
        "metric_filter": "cpu_util_pct",
    },
    "MEMORY_UTILIZATION_VUSERS_DUALAXIS": {
        "function": "generate_memory_utilization_vusers_chart",
        "module": "dual_axis_charts",
        "data_source": "infrastructure_performance",
        "metric_filter": "mem_util_pct",
    },
    # Comparison bar charts (for multi-run comparison reports)
    "CPU_CORE_COMPARISON_BAR": {
        "function": "generate_cpu_core_comparison_bar_chart",
        "module": "comparison_bar_charts",
        "data_source": "comparison_metadata",
    },
    "MEMORY_USAGE_COMPARISON_BAR": {
        "function": "generate_memory_usage_comparison_bar_chart",
        "module": "comparison_bar_charts",
        "data_source": "comparison_metadata",
    },
    # Add more chart definitions here as needed
}

# -----------------------------------------------
# Main Functions for the Chart Generation Module
# -----------------------------------------------

async def generate_chart(run_id: str, env_name: str, chart_id: str) -> dict:
    chart_spec = _get_chart_spec_by_id(chart_id)
    if not chart_spec:
        return {"error": f"Unsupported chart_id: {chart_id}"}

    mapping = chart_map.get(chart_id)
    if not mapping:
        return {"error": f"No handler mapped for chart_id: {chart_id}"}

    chart_handler = get_chart_handler(mapping)
    if not chart_handler:
        return {"error": f"Handler not found: {mapping['module']}.{mapping['function']}"}

    data_source = mapping["data_source"]
    results = []
    errors = []

    # Infrastructure (Datadog) charts
    if data_source == "infrastructure":
        env_info = await load_environment_details(run_id, env_name)
        env_type = env_info['env_type']     # Environment type can be either 'host' or 'k8s'
        if not env_info:
            return {"error": f"Missing environment info for: {env_name}"}

        resources = env_info["resources"]

        metric_files = await get_metric_files(run_id, env_type, resources)

        for resource, metric_file in zip(resources, metric_files):
            try:
                df = pd.read_csv(metric_file)
                out = await chart_handler(df, chart_spec, env_type, resource, run_id)
                results.append(out)
            except Exception as e:
                errors.append({"resource": resource, "error": str(e)})

    # Performance (BlazeMeter or JMeter) charts
    elif data_source == "performance":
        perf_path = ARTIFACTS_PATH / run_id / "blazemeter" / "test-results.csv"
        if not perf_path.exists():
            return {"error": f"Missing BlazeMeter test-results.csv for run: {run_id}"}
        try:
            df = pd.read_csv(perf_path)
            out = await chart_handler(df, chart_spec, run_id)
            results.append(out)
        except Exception as e:
            errors.append({"error": str(e)})

    # Infrastructure multi-line charts (all resources on single chart)
    elif data_source == "infrastructure_multi":
        env_info = await load_environment_details(run_id, env_name)
        if not env_info:
            return {"error": f"Missing environment info for: {env_name}"}
        
        env_type = env_info['env_type']
        resources = env_info["resources"]
        metric_files = await get_metric_files(run_id, env_type, resources)
        
        # Determine metric filter based on chart_id
        if "CPU" in chart_id:
            metric_filter = "cpu_util_pct"
        elif "MEMORY" in chart_id:
            metric_filter = "mem_util_pct"
        else:
            metric_filter = None
        
        # Build dict of DataFrames for all resources
        dataframes = {}
        resource_column = "hostname" if env_type == "host" else "container_or_pod"
        
        for resource, metric_file in zip(resources, metric_files):
            try:
                df = pd.read_csv(metric_file)
                # Filter for the specific metric type
                if metric_filter and "metric" in df.columns:
                    df = df[df["metric"] == metric_filter]
                # Filter for this specific resource
                if resource_column in df.columns:
                    df = df[df[resource_column] == resource]
                if not df.empty:
                    dataframes[resource] = df
            except Exception as e:
                errors.append({"resource": resource, "error": str(e)})
        
        if dataframes:
            try:
                out = await chart_handler(dataframes, chart_spec, run_id)
                results.append(out)
            except Exception as e:
                errors.append({"error": str(e)})
        else:
            errors.append({"error": "No valid data found for any resource"})

    # Infrastructure + Performance combined charts (dual-axis: infra metric vs vusers)
    elif data_source == "infrastructure_performance":
        # Load environment info for infrastructure data
        env_info = await load_environment_details(run_id, env_name)
        if not env_info:
            return {"error": f"Missing environment info for: {env_name}"}
        
        env_type = env_info['env_type']
        resources = env_info["resources"]
        metric_files = await get_metric_files(run_id, env_type, resources)
        
        # Get metric filter from chart mapping
        metric_filter = mapping.get("metric_filter")
        
        # Build dict of DataFrames for all resources (infrastructure data)
        infra_dataframes = {}
        resource_column = "hostname" if env_type == "host" else "container_or_pod"
        
        for resource, metric_file in zip(resources, metric_files):
            try:
                df = pd.read_csv(metric_file)
                # Filter for the specific metric type
                if metric_filter and "metric" in df.columns:
                    df = df[df["metric"] == metric_filter]
                # Filter for this specific resource
                if resource_column in df.columns:
                    df = df[df[resource_column] == resource]
                if not df.empty:
                    infra_dataframes[resource] = df
            except Exception as e:
                errors.append({"resource": resource, "error": str(e)})
        
        # Load performance data (BlazeMeter test-results.csv)
        perf_path = ARTIFACTS_PATH / run_id / "blazemeter" / "test-results.csv"
        perf_df = None
        if perf_path.exists():
            try:
                perf_df = pd.read_csv(perf_path)
            except Exception as e:
                errors.append({"error": f"Failed to load performance data: {str(e)}"})
        else:
            errors.append({"error": f"Missing BlazeMeter test-results.csv for run: {run_id}"})
        
        # Generate chart if we have both data sources
        if infra_dataframes and perf_df is not None:
            try:
                out = await chart_handler(infra_dataframes, perf_df, chart_spec, run_id)
                results.append(out)
            except Exception as e:
                errors.append({"error": str(e)})
        elif not infra_dataframes:
            errors.append({"error": "No valid infrastructure data found for any resource"})

    else:
        return {"error": f"Unknown data source: {data_source}"}

    return {
        "run_id": run_id,
        "chart_id": chart_id,
        "charts": results,
        "errors": errors,
    }

# -----------------------------------------------
# Helper Functions
# -----------------------------------------------
def get_chart_handler(mapping):
    module = chart_module_registry.get(mapping["module"])
    if module is None:
        return None
    return getattr(module, mapping["function"], None)

def _parse_datetime_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Parse datetime column handling both epoch timestamps and ISO datetime strings.
    Converts to configured timezone for human-readable display.
    
    Args:
        df: DataFrame containing the datetime column
        column: Name of the datetime column to parse
    
    Returns:
        DataFrame with parsed datetime column
    """
    if df.empty or column not in df.columns:
        return df
    
    # Get a sample value to determine format
    sample_val = df[column].iloc[0] if not df.empty else None
    
    try:
        if isinstance(sample_val, (int, float)) or (isinstance(sample_val, str) and sample_val.isdigit()):
            # Numeric timestamps - assume milliseconds
            df[column] = pd.to_datetime(df[column], unit='ms', errors='coerce')
        else:
            # ISO datetime strings
            df[column] = pd.to_datetime(df[column], errors='coerce')
        
        # Convert to configured timezone if available
        try:
            timezone_str = CONFIG.get('perf_report', {}).get('time_zone')
            if timezone_str:
                target_tz = pytz.timezone(timezone_str)
                # Ensure timezone-aware datetime
                if df[column].dt.tz is None:
                    df[column] = df[column].dt.tz_localize('UTC')
                # Convert to target timezone
                df[column] = df[column].dt.tz_convert(target_tz)
        except Exception as tz_error:
            print(f"Warning: Could not convert timezone: {str(tz_error)}")
        
        # Check for any NaT values (parsing failures)
        nat_count = df[column].isna().sum()
        if nat_count > 0:
            print(f"Warning: {nat_count} datetime values failed to parse in column '{column}'")
            
    except Exception as e:
        print(f"Error parsing datetime column '{column}': {str(e)}")
        # Try fallback parsing
        try:
            df[column] = pd.to_datetime(df[column], errors='coerce')
        except Exception as e2:
            print(f"Fallback parsing also failed for column '{column}': {str(e2)}")
    
    return df


def _validate_chart_data(df: pd.DataFrame, chart_spec: Dict) -> Tuple[bool, str]:
    """
    Validate that the data contains required columns and proper formats.
    
    Args:
        df: DataFrame to validate
        chart_spec: Chart specification from schema
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if df is None or df.empty:
        return False, "No data available for chart generation"
    
    # Check required columns
    required_columns = chart_spec.get('data_sources', {}).get('required_columns', [])
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        available_columns = list(df.columns)
        return False, f"Missing required columns: {missing_columns}. Available columns: {available_columns}"
    
    # Check for empty data after filtering
    if len(df) == 0:
        return False, "No data remaining after applying filters"
    
    # Check for numeric columns (y-axis data)
    y_columns = []
    if 'y_axis' in chart_spec:
        y_columns.append(chart_spec['y_axis']['column'])
    if 'y_axis_left' in chart_spec:
        y_columns.append(chart_spec['y_axis_left']['column'])
    if 'y_axis_right' in chart_spec:
        y_columns.append(chart_spec['y_axis_right']['column'])
    
    for y_col in y_columns:
        if y_col in df.columns:
            # Check if column contains numeric data
            if not pd.api.types.is_numeric_dtype(df[y_col]):
                try:
                    df[y_col] = pd.to_numeric(df[y_col], errors='coerce')
                    nan_count = df[y_col].isna().sum()
                    if nan_count > 0:
                        return False, f"Column '{y_col}' contains {nan_count} non-numeric values that could not be converted"
                except Exception as e:
                    return False, f"Column '{y_col}' is not numeric and could not be converted: {str(e)}"
    
    return True, ""


def _get_chart_spec_by_id(chart_id: str) -> Optional[Dict]:
    """Retrieve chart specification from schema by ID"""
    for chart in CHART_SCHEMA.get('charts', []):
        if chart['id'] == chart_id:
            return chart
    return None


async def _load_chart_data(run_id: str, chart_spec: Dict, chart_data: dict) -> Optional[pd.DataFrame]:
    """
    Load data for chart generation from CSV or JSON.
    Supports both inline data (chart_data dict) or file references.
    """
    # If data is provided inline
    if 'data' in chart_data and isinstance(chart_data['data'], list):
        return pd.DataFrame(chart_data['data'])
    
    # Otherwise, load from file system
    run_path = ARTIFACTS_PATH / run_id
    data_source = chart_spec['data_sources']['primary']
    
    # Handle template variables in data source path
    if '{' in data_source and '}' in data_source:
        # Extract template variables from chart_data or metric_config
        template_vars = {}
        if 'scope' in chart_data:
            template_vars['scope'] = chart_data['scope']
        if 'filter' in chart_data:
            template_vars['filter'] = chart_data['filter']
        if 'pod_or_container' in chart_data:
            template_vars['pod_or_container'] = chart_data['pod_or_container']
        
        # Check for unresolved template variables
        unresolved_vars = []
        for key, value in template_vars.items():
            if value:  # Only replace if value is not None/empty
                data_source = data_source.replace(f'{{{key}}}', value)
            else:
                unresolved_vars.append(key)
        
        # Check if any template variables remain unresolved
        import re
        remaining_vars = re.findall(r'\{(\w+)\}', data_source)
        if remaining_vars:
            print(f"Warning: Unresolved template variables in data source '{data_source}': {remaining_vars}")
            print(f"Available template variables: {list(template_vars.keys())}")
            return None
    
    if data_source.endswith('.csv'):
        # Determine the correct subdirectory based on data source
        if 'blazemeter' in str(run_path) or data_source == 'test-results.csv':
            csv_path = run_path / "blazemeter" / data_source
        elif 'datadog' in str(run_path) or '_metrics_' in data_source:
            csv_path = run_path / "datadog" / data_source
        else:
            csv_path = run_path / "analysis" / data_source
            
        if not csv_path.exists():
            print(f"Warning: CSV file not found: {csv_path}")
            return None
        
        try:
            df = pd.read_csv(csv_path)
            if df.empty:
                print(f"Warning: CSV file is empty: {csv_path}")
                return None
        except Exception as e:
            print(f"Error reading CSV file {csv_path}: {str(e)}")
            return None
        
    elif data_source.endswith('.json'):
        json_path = run_path / "analysis" / data_source
        if not json_path.exists():
            return None
        
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Navigate JSON path if specified
        json_path_str = chart_spec['data_sources'].get('json_path', '')
        if json_path_str:
            for key in json_path_str.split('.'):
                if key and key in data:
                    data = data[key]
        
        # Convert to DataFrame
        if isinstance(data, dict):
            # For api_analysis: dict of dicts
            df = pd.DataFrame.from_dict(data, orient='index').reset_index()
            df.rename(columns={'index': 'api_name'}, inplace=True)
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            return None
    else:
        return None
    
    # Apply metric filter if specified (e.g., only cpu_util_pct rows)
    metric_filter = chart_spec.get('data_sources', {}).get('metric_filter')
    if metric_filter and 'metric' in df.columns:
        original_count = len(df)
        df = df[df['metric'] == metric_filter]
        filtered_count = len(df)
        if df.empty:
            print(f"Warning: No data found for metric filter '{metric_filter}'")
            return None
        print(f"Applied metric filter '{metric_filter}': {original_count} -> {filtered_count} rows")
    
    # Apply filter condition if specified (e.g., only SLA violators)
    filter_cond = chart_spec.get('filter_condition')
    if filter_cond:
        try:
            df = df.query(filter_cond)
        except:
            pass
    
    # Apply limit and sort
    if 'limit' in chart_spec:
        sort_col = chart_spec['x_axis']['column']
        ascending = chart_spec.get('sort', 'descending') == 'ascending'
        df = df.nlargest(chart_spec['limit'], sort_col) if not ascending else df.nsmallest(chart_spec['limit'], sort_col)
    
    return df


async def _load_chart_data_from_spec(run_id: str, chart_spec: Dict) -> Optional[pd.DataFrame]:
    """
    Load data for chart generation based on chart specification.
    This is the template-driven approach that automatically determines data source.
    
    Args:
        run_id: Test run identifier
        chart_spec: Chart specification from schema
    
    Returns:
        DataFrame with chart data
    """
    # Create empty chart_data dict for template-driven approach
    chart_data = {}
    
    # For infrastructure charts, we need to determine scope and service from the data source path
    data_source = chart_spec['data_sources']['primary']
    
    # Handle template variables in data source path
    if '{' in data_source and '}' in data_source:
        # For infrastructure charts, we need to find the actual files and extract template variables
        run_path = ARTIFACTS_PATH / run_id
        
        # Look for matching files in datadog directory
        datadog_path = run_path / "datadog"
        if datadog_path.exists():
            # Find files matching the pattern
            import re
            pattern = data_source.replace('{scope}', r'(\w+)').replace('{filter}', r'([^]]+)')
            pattern = pattern.replace('[', r'\[').replace(']', r'\]')
            
            for file_path in datadog_path.glob("*.csv"):
                match = re.match(pattern, file_path.name)
                if match:
                    scope, filter_value = match.groups()
                    chart_data['scope'] = scope
                    chart_data['filter'] = filter_value
                    break
        
        # If no template variables found, try to load from blazemeter
        if not chart_data and data_source == 'test-results.csv':
            chart_data = {}  # Empty for blazemeter data
    
    # Use the existing _load_chart_data function
    return await _load_chart_data(run_id, chart_spec, chart_data)


async def _load_infrastructure_time_series(run_id: str, chart_spec: Dict) -> Optional[Dict]:
    """
    Load infrastructure time-series data for multiple services.
    Returns dict: {service_name: DataFrame(timestamp, metric_value)}
    """
    run_path = ARTIFACTS_PATH / run_id
    json_path = run_path / "analysis" / chart_spec['data_sources']['primary']
    
    if not json_path.exists():
        return None
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Navigate to detailed_metrics
    json_path_str = chart_spec['data_sources'].get('json_path', '')
    for key in json_path_str.split('.'):
        if key and key in data:
            data = data[key]
    
    service_data = {}
    metric_extraction = chart_spec['data_sources'].get('metric_extraction', 'cpu_samples')
    
    # Check both kubernetes and hosts
    for service_type in chart_spec['data_sources'].get('service_types', []):
        if service_type in data:
            for service_name, service_info in data[service_type].items():
                if metric_extraction in service_info:
                    samples = service_info[metric_extraction]
                    if samples:
                        service_data[service_name] = samples
    
    return service_data if service_data else None


def _align_service_timeseries(service_data_dict: Dict, chart_spec: Dict) -> pd.DataFrame:
    """
    Align multiple service time-series to common timeline with 1-minute granularity.
    Returns DataFrame with columns: timestamp, service1, service2, ...
    """
    all_dfs = []
    
    for service_name, samples in service_data_dict.items():
        df = pd.DataFrame(samples)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp').resample('1min').mean().ffill()
        df.rename(columns={'value': service_name}, inplace=True)
        all_dfs.append(df[[service_name]])
    
    if not all_dfs:
        return pd.DataFrame()
    
    # Merge all service DataFrames on timestamp
    merged_df = all_dfs[0]
    for df in all_dfs[1:]:
        merged_df = merged_df.join(df, how='outer')
    
    merged_df = merged_df.ffill().fillna(0).reset_index()
    return merged_df


def _check_precondition(df: pd.DataFrame, chart_spec: Dict) -> bool:
    """
    Check if chart should be generated based on preconditions.
    Example: precondition: "failure > 0"
    """
    precondition = chart_spec.get('precondition')
    if not precondition:
        return True
    
    try:
        # Check if any row meets condition
        return df.eval(precondition).any()
    except:
        return True  # If check fails, generate anyway


async def _save_chart(fig, run_id: str, chart_spec: Dict) -> Path:
    """Save matplotlib figure to PNG file"""
    charts_dir = ARTIFACTS_PATH / run_id / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    
    filename = chart_spec['output_filename'].format(run_id=run_id)
    output_path = charts_dir / filename
    
    fig.savefig(output_path, dpi=DPI, bbox_inches='tight', facecolor='white')
    
    return output_path
