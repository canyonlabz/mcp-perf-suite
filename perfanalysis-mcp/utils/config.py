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

def load_environments_config(config: Dict) -> Dict:
    """
    Load Datadog environments.json configuration. TODO: Pass in APM tool name instead of hardcoding (e.g. Datadog).
    """
    try:
        # Path should be relative to project root, not artifacts
        env_file = Path("../datadog-mcp/environments.json")
        if env_file.exists():
            with open(env_file, 'r') as f:
                return json.load(f)
        else:
            # Fallback - look in current directory
            env_file = Path("environments.json")
            if env_file.exists():
                with open(env_file, 'r') as f:
                    return json.load(f)
            else:
                return {"environments": {}}  # Empty config if not found
    except Exception:
        return {"environments": {}}

if __name__ == '__main__':
    # For testing purposes, print both configurations.
    config = load_config()
    print("Loaded general configuration:")
    print(config)
