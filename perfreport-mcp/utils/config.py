import yaml
import os
import platform
import json
from typing import Dict
from pathlib import Path

def load_config():
    # Assuming this file is at 'repo/<mcp-server>/utils/config.py', we go up one level.
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # Platform-specific config mapping
    config_map = {
        'Darwin': 'config.mac.yaml',
        'Windows': 'config.windows.yaml'
    }

    system = platform.system()
    platform_config = config_map.get(system)
    
    # Use platform-specific config if it exists, otherwise fall back to config.yaml
    candidate_files = [platform_config, 'config.yaml'] if platform_config else ['config.yaml']
    
    for filename in candidate_files:
        config_path = os.path.join(repo_root, filename)
        if os.path.exists(config_path):
            with open(config_path, 'r') as file:
                try:
                    return yaml.safe_load(file)
                except yaml.YAMLError as e:
                    raise Exception(f"Error parsing '{filename}': {e}")
    
    raise FileNotFoundError("No valid configuration file found (checked platform-specific and default).")

def load_chart_colors() -> Dict:
    """Load chart color configuration"""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    colors_path = os.path.join(repo_root, "chart_colors.yaml")
    
    if not os.path.exists(colors_path):
        # Return default colors if file missing
        return {
            "primary": "#1f77b4",
            "secondary": "#ff7f0e",
            "success": "#2ca02c",
            "error": "#d62728",
            "warning": "#ff9800"
        }
    
    with open(colors_path, 'r') as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as e:
            raise Exception(f"Error parsing chart_colors.yaml: {e}")


def load_report_config() -> Dict:
    """
    Load report display configuration from report_config.yaml.
    
    This configuration controls the look and feel of generated reports,
    such as which columns to display in infrastructure tables.
    
    Returns:
        Dict containing report configuration options. Returns sensible
        defaults if the config file doesn't exist.
        
    Example:
        >>> config = load_report_config()
        >>> show_allocated = config["infrastructure_tables"]["cpu_utilization"]["show_allocated_column"]
        >>> print(show_allocated)
        True
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(repo_root, "report_config.yaml")
    
    # Default configuration - used if file doesn't exist
    defaults = {
        "version": "1.0",
        "infrastructure_tables": {
            "cpu_utilization": {"show_allocated_column": True},
            "cpu_core_usage": {"show_allocated_column": True},
            "memory_utilization": {"show_allocated_column": True},
            "memory_usage": {"show_allocated_column": True}
        }
    }
    
    if not os.path.exists(config_path):
        return defaults
    
    with open(config_path, 'r') as file:
        try:
            config = yaml.safe_load(file) or {}
            # Merge with defaults to ensure all keys exist
            merged = defaults.copy()
            if "infrastructure_tables" in config:
                for table_name, table_config in config["infrastructure_tables"].items():
                    if table_name in merged["infrastructure_tables"]:
                        merged["infrastructure_tables"][table_name].update(table_config)
                    else:
                        merged["infrastructure_tables"][table_name] = table_config
            return merged
        except yaml.YAMLError as e:
            raise Exception(f"Error parsing report_config.yaml: {e}")

if __name__ == '__main__':
    # For testing purposes, print both configurations.
    config = load_config()
    print("Loaded general configuration:")
    print(config)
