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

# Import config at module level
from utils.config import load_config, load_chart_colors

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

# -----------------------------------------------
# Main Functions for the Chart Generation Module
# -----------------------------------------------
async def generate_single_axis_chart(run_id: str, chart_type: str) -> Dict:
    """
    Generate single axis PNG chart using chart type from schema.
    
    Args:
        run_id: Test run identifier
        chart_type: Chart type identifier from chart_schema.yaml
    
    Returns:
        Dict with run_id, path to PNG, and metadata
    """
    try:
        # Look up chart specification from schema
        chart_spec = _get_chart_spec_by_id(chart_type)
        if not chart_spec:
            return {
                "run_id": run_id,
                "error": f"Chart type not found: {chart_type}. Use list_chart_types() to see available options."
            }
        
        # Load data automatically based on chart specification
        df = await _load_chart_data_from_spec(run_id, chart_spec)
        
        # Validate data
        is_valid, validation_error = _validate_chart_data(df, chart_spec)
        if not is_valid:
            return {
                "run_id": run_id,
                "error": f"Data validation failed: {validation_error}"
            }
        
        # Check preconditions (e.g., failure > 0)
        if not _check_precondition(df, chart_spec):
            return {
                "run_id": run_id,
                "skipped": True,
                "reason": f"Precondition not met: {chart_spec.get('precondition', 'N/A')}"
            }
        
        # Generate chart
        fig, ax = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT), dpi=DPI)
        
        x_col = chart_spec['x_axis']['column']
        y_col = chart_spec['y_axis']['column']
        
        # Resample to 1-minute if timestamp
        if chart_spec['x_axis'].get('format') == 'datetime':
            df = _parse_datetime_column(df, x_col)
            df = df.set_index(x_col).resample('1min').mean().ffill().reset_index()
        
        # Plot line
        color = CHART_COLORS.get(chart_spec['colors'][0], CHART_COLORS['primary'])
        ax.plot(df[x_col], df[y_col], color=color, linewidth=2, marker='o', markersize=3)
        
        # Styling
        ax.set_xlabel(chart_spec['x_axis']['label'], fontsize=CHART_DEFAULTS['font_size']['axis_label'])
        ax.set_ylabel(chart_spec['y_axis']['label'], fontsize=CHART_DEFAULTS['font_size']['axis_label'])
        ax.set_title(chart_spec['title'], fontsize=CHART_DEFAULTS['font_size']['title'], fontweight='bold')
        
        if chart_spec.get('show_grid', True):
            ax.grid(True, alpha=0.3, color=CHART_COLORS['grid'])
        
        # Format x-axis for datetime
        if chart_spec['x_axis'].get('format') == 'datetime':
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        # Save chart
        output_path = await _save_chart(fig, run_id, chart_spec)
        plt.close(fig)
        
        return {
            "run_id": run_id,
            "chart_type": chart_type or "custom",
            "path": str(output_path),
            "title": chart_spec['title'],
            "data_points": len(df)
        }
        
    except Exception as e:
        return {
            "run_id": run_id,
            "error": f"Chart generation failed: {str(e)}"
        }


async def generate_dual_axis_chart(run_id: str, chart_type: str) -> Dict:
    """
    Generate dual axis PNG chart using chart type from schema.
    
    Args:
        run_id: Test run identifier
        chart_type: Chart type identifier from chart_schema.yaml
    
    Returns:
        Dict with run_id, path to PNG, and metadata
    """
    try:
        # Look up chart specification from schema
        chart_spec = _get_chart_spec_by_id(chart_type)
        if not chart_spec:
            return {
                "run_id": run_id,
                "error": f"Chart type not found: {chart_type}. Use list_chart_types() to see available options."
            }
        
        # Load data automatically based on chart specification
        df = await _load_chart_data_from_spec(run_id, chart_spec)
        
        # Validate data
        is_valid, validation_error = _validate_chart_data(df, chart_spec)
        if not is_valid:
            return {
                "run_id": run_id,
                "error": f"Data validation failed: {validation_error}"
            }
        
        # Generate dual-axis chart
        fig, ax1 = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT), dpi=DPI)
        
        x_col = chart_spec['x_axis']['column']
        y_left_col = chart_spec['y_axis_left']['column']
        y_right_col = chart_spec['y_axis_right']['column']
        
        # Resample to 1-minute if timestamp
        if chart_spec['x_axis'].get('format') == 'datetime':
            df = _parse_datetime_column(df, x_col)
            df = df.set_index(x_col).resample('1min').mean().ffill().reset_index()
        
        # Plot left axis
        color_left = CHART_COLORS.get(chart_spec['y_axis_left'].get('color', 'primary'))
        ax1.plot(df[x_col], df[y_left_col], color=color_left, linewidth=2, 
                 marker='o', markersize=3, label=chart_spec['y_axis_left']['label'])
        ax1.set_xlabel(chart_spec['x_axis']['label'], fontsize=CHART_DEFAULTS['font_size']['axis_label'])
        ax1.set_ylabel(chart_spec['y_axis_left']['label'], color=color_left, 
                       fontsize=CHART_DEFAULTS['font_size']['axis_label'])
        ax1.tick_params(axis='y', labelcolor=color_left)
        
        # Plot right axis
        ax2 = ax1.twinx()
        color_right = CHART_COLORS.get(chart_spec['y_axis_right'].get('color', 'secondary'))
        ax2.plot(df[x_col], df[y_right_col], color=color_right, linewidth=2, 
                 marker='s', markersize=3, label=chart_spec['y_axis_right']['label'])
        ax2.set_ylabel(chart_spec['y_axis_right']['label'], color=color_right, 
                       fontsize=CHART_DEFAULTS['font_size']['axis_label'])
        ax2.tick_params(axis='y', labelcolor=color_right)
        
        # Title and grid
        ax1.set_title(chart_spec['title'], fontsize=CHART_DEFAULTS['font_size']['title'], fontweight='bold')
        if chart_spec.get('show_grid', True):
            ax1.grid(True, alpha=0.3, color=CHART_COLORS['grid'])
        
        # Format x-axis for datetime
        if chart_spec['x_axis'].get('format') == 'datetime':
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.xticks(rotation=45)
        
        # Legend
        if chart_spec.get('include_legend', True):
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', 
                       fontsize=CHART_DEFAULTS['font_size']['legend'])
        
        plt.tight_layout()
        
        # Save chart
        output_path = await _save_chart(fig, run_id, chart_spec)
        plt.close(fig)
        
        return {
            "run_id": run_id,
            "chart_type": chart_type or "custom",
            "path": str(output_path),
            "title": chart_spec['title'],
            "data_points": len(df)
        }
        
    except Exception as e:
        return {
            "run_id": run_id,
            "error": f"Dual-axis chart generation failed: {str(e)}"
        }


async def generate_stacked_area_chart(run_id: str, chart_data: dict, metric_config: dict) -> Dict:
    """
    Generate stacked area chart showing cumulative resource usage per service.
    
    Args:
        run_id: Test run identifier
        chart_data: Dict with multi-service time-series data
        metric_config: Chart configuration
    
    Returns:
        Dict with run_id, path to PNG, and metadata
    """
    try:
        schema_id = metric_config.get('schema_id')
        if schema_id:
            chart_spec = _get_chart_spec_by_id(schema_id)
            if not chart_spec:
                return {
                    "run_id": run_id,
                    "error": f"Chart schema ID not found: {schema_id}"
                }
        else:
            chart_spec = metric_config
        
        # Load multi-service data
        service_data_dict = await _load_infrastructure_time_series(run_id, chart_spec)
        if not service_data_dict:
            return {
                "run_id": run_id,
                "error": "No infrastructure time-series data available"
            }
        
        # Generate stacked area chart
        fig, ax = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT), dpi=DPI)
        
        # Prepare data: Align all services to common timeline
        aligned_df = _align_service_timeseries(service_data_dict, chart_spec)
        if aligned_df.empty:
            return {
                "run_id": run_id,
                "error": "Failed to align service time-series data"
            }
        
        # Get service columns (exclude timestamp)
        service_cols = [col for col in aligned_df.columns if col != 'timestamp']
        
        # Stack plot (cumulative)
        colors = [CHART_COLORS.get(c, CHART_COLORS['primary']) for c in chart_spec['colors'][:len(service_cols)]]
        ax.stackplot(aligned_df['timestamp'], 
                     *[aligned_df[col] for col in service_cols],
                     labels=service_cols,
                     colors=colors,
                     alpha=0.7)
        
        # Styling
        ax.set_xlabel(chart_spec['x_axis']['label'], fontsize=CHART_DEFAULTS['font_size']['axis_label'])
        ax.set_ylabel(chart_spec['y_axis']['label'], fontsize=CHART_DEFAULTS['font_size']['axis_label'])
        ax.set_title(chart_spec['title'], fontsize=CHART_DEFAULTS['font_size']['title'], fontweight='bold')
        ax.set_ylim(0, chart_spec['y_axis'].get('max', 100))
        
        if chart_spec.get('show_grid', True):
            ax.grid(True, alpha=0.3, color=CHART_COLORS['grid'])
        
        # Format x-axis for datetime
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.xticks(rotation=45)
        
        # Legend
        if chart_spec.get('include_legend', True):
            ax.legend(loc=chart_spec.get('legend_location', 'upper left'),
                      fontsize=CHART_DEFAULTS['font_size']['legend'])
        
        plt.tight_layout()
        
        # Save chart
        output_path = await _save_chart(fig, run_id, chart_spec)
        plt.close(fig)
        
        return {
            "run_id": run_id,
            "chart_id": schema_id or "custom",
            "path": str(output_path),
            "title": chart_spec['title'],
            "services": service_cols,
            "data_points": len(aligned_df)
        }
        
    except Exception as e:
        return {
            "run_id": run_id,
            "error": f"Stacked area chart generation failed: {str(e)}"
        }


# -----------------------------------------------
# Helper Functions
# -----------------------------------------------
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
        if 'service_filter' in chart_data:
            template_vars['service_filter'] = chart_data['service_filter']
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
            pattern = data_source.replace('{scope}', r'(\w+)').replace('{service_filter}', r'([^]]+)')
            pattern = pattern.replace('[', r'\[').replace(']', r'\]')
            
            for file_path in datadog_path.glob("*.csv"):
                match = re.match(pattern, file_path.name)
                if match:
                    scope, service_filter = match.groups()
                    chart_data['scope'] = scope
                    chart_data['service_filter'] = service_filter
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
