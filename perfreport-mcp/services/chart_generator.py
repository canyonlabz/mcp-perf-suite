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


async def generate_single_axis_chart(
    run_id: str,
    chart_data: dict,
    metric_config: dict
) -> Dict:
    """
    Generate single axis PNG chart.
    
    Args:
        run_id: Test run identifier
        chart_data: Dict with data or reference to data file
        metric_config: Chart configuration (can reference schema ID or be custom)
    
    Returns:
        Dict with run_id, path to PNG, and metadata
    """
    try:
        # Determine if using schema or custom config
        schema_id = metric_config.get('schema_id')
        if schema_id:
            chart_spec = _get_chart_spec_by_id(schema_id)
            if not chart_spec:
                return {
                    "run_id": run_id,
                    "error": f"Chart schema ID not found: {schema_id}"
                }
        else:
            chart_spec = metric_config  # Use custom config directly
        
        # Load data
        df = await _load_chart_data(run_id, chart_spec, chart_data)
        if df is None or df.empty:
            return {
                "run_id": run_id,
                "error": "No data available for chart generation"
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
            df[x_col] = pd.to_datetime(df[x_col], unit='ms', errors='coerce')
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
            "chart_id": schema_id or "custom",
            "path": str(output_path),
            "title": chart_spec['title'],
            "data_points": len(df)
        }
        
    except Exception as e:
        return {
            "run_id": run_id,
            "error": f"Chart generation failed: {str(e)}"
        }


async def generate_dual_axis_chart(
    run_id: str,
    chart_data: dict,
    metric_config: dict
) -> Dict:
    """
    Generate dual axis PNG chart.
    
    Args:
        run_id: Test run identifier
        chart_data: Dict with data or reference to data file
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
        
        # Load data
        df = await _load_chart_data(run_id, chart_spec, chart_data)
        if df is None or df.empty:
            return {
                "run_id": run_id,
                "error": "No data available for chart generation"
            }
        
        # Generate dual-axis chart
        fig, ax1 = plt.subplots(figsize=(CHART_WIDTH, CHART_HEIGHT), dpi=DPI)
        
        x_col = chart_spec['x_axis']['column']
        y_left_col = chart_spec['y_axis_left']['column']
        y_right_col = chart_spec['y_axis_right']['column']
        
        # Resample to 1-minute if timestamp
        if chart_spec['x_axis'].get('format') == 'datetime':
            df[x_col] = pd.to_datetime(df[x_col], unit='ms', errors='coerce')
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
            "chart_id": schema_id or "custom",
            "path": str(output_path),
            "title": chart_spec['title'],
            "data_points": len(df)
        }
        
    except Exception as e:
        return {
            "run_id": run_id,
            "error": f"Dual-axis chart generation failed: {str(e)}"
        }


async def generate_stacked_area_chart(
    run_id: str,
    chart_data: dict,
    metric_config: dict
) -> Dict:
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


# ===== HELPER FUNCTIONS =====

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
    
    if data_source.endswith('.csv'):
        csv_path = run_path / "analysis" / data_source
        if not csv_path.exists():
            return None
        df = pd.read_csv(csv_path)
        
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
