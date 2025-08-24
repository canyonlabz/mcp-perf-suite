import yaml
import os
import platform

def load_config():
    # Compute the repository root directory.
    # Assuming this file is at 'repo/src/utils/config.py', we go up two levels.
    # Compute the repository root directory.
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    
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

if __name__ == '__main__':
    # For testing purposes, print both configurations.
    config = load_config()
    print("Loaded general configuration:")
    print(config)
