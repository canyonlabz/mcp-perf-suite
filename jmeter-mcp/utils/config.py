import yaml
import os
import platform

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

def load_jmeter_config():
    """
    Loads the JMeter-specific configuration from 'jmeter_config.yaml'.
    """
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    config_path = os.path.join(repo_root, 'jmeter_config.yaml')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError("JMeter configuration file 'jmeter_config.yaml' not found.")
    
    with open(config_path, 'r') as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as e:
            raise Exception(f"Error parsing 'jmeter_config.yaml': {e}")

if __name__ == '__main__':
    # For testing purposes, print both configurations.
    config = load_config()
    print("Loaded general configuration:")
    print(config)
