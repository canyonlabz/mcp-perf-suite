"""
utils/chart_utils.py
File I/O helper functions for chart generation in PerfAnalysis MCP
"""
import json
import asyncio
import pypandoc
import re
from pathlib import Path
from typing import Dict, Optional, List

# Import config at module level
from utils.config import load_config

# Load configuration
CONFIG = load_config()
REPORT_CONFIG = CONFIG.get("perf_report", {})
ARTIFACTS_CONFIG = CONFIG.get('artifacts', {})
ARTIFACTS_PATH = Path(ARTIFACTS_CONFIG.get('artifacts_path', '../artifacts'))
APM_TOOL = REPORT_CONFIG.get("apm_tool", "datadog").lower()
# -----------------------------------------------
# Utility functions
# -----------------------------------------------
async def load_environment_details(run_id: str, env_name: str) -> Optional[Dict]:
    """
    Load environment information and identify its infrastructure resources.

    This unified helper loads the environments.json file from the repo
    root (datadog-mcp/environments.json) and determines whether the target
    environment is infrastructure-based (hosts) or platform-based (Kubernetes).
    It also extracts the associated resource names.

    Args:
        run_id (str):
            The performance test run identifier. Used to resolve chart paths.
        env_name (str):
            The environment key (e.g. 'UAT-Central', 'Perf-West') specified in
            the environments.json file.

    Returns:
        dict | None:
            Returns a dictionary containing:
            {
                "env_name": <environment name>,
                "env_type": "host" | "k8s" | "unknown",
                "resources": [<list of hostnames or filters>],
                "config": <entire environment definition>
            }
            Returns None if the JSON file is missing or the environment is undefined.

    Example:
        >>> result = await load_environment_details("run_12345", "UAT-Central")
        >>> print(result["env_type"])
        'k8s'
        >>> print(result["resources"])
        ['nga-ai-autogen-app-api', 'nga-ai-plan-service']
    """
    env_path = Path("../datadog-mcp") / "environments.json"
    if not env_path.exists():
        return None

    loop = asyncio.get_event_loop()
    raw_json = await loop.run_in_executor(None, env_path.read_text)
    env_data = json.loads(raw_json)
    environments = env_data.get("environments", {})

    if env_name not in environments:
        return None

    env_entry = environments[env_name]

    # Identify environment type
    env_type = "unknown"
    resources: List[str] = []
    if env_entry.get("hosts"):
        env_type = "host"
        resources = [h["hostname"] for h in env_entry["hosts"]]
    elif env_entry.get("kubernetes", {}).get("services"):
        env_type = "k8s"
        resources = [
            s["service_filter"].replace("*", "") for s in env_entry["kubernetes"]["services"]
        ]
    elif env_entry.get("kubernetes", {}).get("pods"):
        env_type = "k8s"
        resources = [
            p["pod_filter"].replace("*", "") for p in env_entry["kubernetes"]["pods"]
        ]

    return {
        "env_name": env_name,
        "env_type": env_type,
        "resources": resources,
        "config": env_entry,
    }

async def get_metric_files(run_id: str, env_type: str, resources: List[str]) -> List[Path]:
    """
    Discover APM metric files corresponding to environment resources.

    Args:
        run_id (str):
            Unique test run identifier (used in artifacts folder resolution).
        env_type (str):
            Environment type. One of ['host', 'k8s'].
        resources (List[str]):
            List of discovered resource identifiers (hostnames or K8s services).

    Returns:
        List[Path]:
            List of valid CSV paths under artifacts/<run_id>/<APM_TOOL>/.

    Example:
        >>> await get_metric_files("run_12345", "k8s", ["nga-ai-autogen-app-api"])
        [Path("artifacts/run_12345/datadog/k8s_metrics_[nga-ai-autogen-app-api_].csv")]
        >>> await get_metric_files("run_12345", "host", ["u2zqtwbpwdwv037"])
        [Path("artifacts/run_12345/datadog/host_metrics_[u2zqtwbpwdwv037].csv")]
    """
    base_dir = ARTIFACTS_PATH / run_id / APM_TOOL
    print(f"DEBUG: base_dir={base_dir}, exists={base_dir.exists()}, APM_TOOL={APM_TOOL}")
    if not base_dir.exists():
        print(f"DEBUG: base_dir does not exist!")
        return []

    discovered_files = []
    for resource in resources:
        # Build expected filename with brackets
        # Note: Host files use format: host_metrics_[hostname].csv (no trailing underscore)
        #       K8s files use format: k8s_metrics_[service_name_].csv (with trailing underscore)
        if env_type == "host":
            expected_name = f"{env_type}_metrics_[{resource}].csv"
        else:  # k8s
            expected_name = f"{env_type}_metrics_[{resource}_].csv"
        print(f"DEBUG: Looking for {expected_name} in {base_dir}")
        # Check all CSV files and match by expected filename prefix
        csv_files = list(base_dir.glob("*.csv"))
        print(f"DEBUG: Found {len(csv_files)} CSV files")
        for csv_file in csv_files:
            # Check if the filename matches our expected pattern
            if csv_file.name == expected_name:
                print(f"DEBUG: Matched {csv_file.name}")
                discovered_files.append(csv_file)
                break  # Found the matching file, move to next resource
        else:
            print(f"DEBUG: No match found for {expected_name}")

    return discovered_files

def get_chart_output_path(run_id: str, chart_name: str) -> Path:
    """
    Return the output path for saving a generated chart,
    ensuring the output directory exists.

    Args:
        run_id (str): The test run's unique identifier.
        chart_name (str): The base filename (no extension) for the chart.

    Returns:
        Path: The absolute path to where the PNG file should be written.
    """
    charts_dir = ARTIFACTS_PATH / run_id / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    return charts_dir / f"{chart_name}.png"

def interpolate_placeholders(template: str, **kwargs) -> str:
    """
    Replace placeholder tokens (e.g., {resource_name}) in a template string
    with the provided keyword arguments.

    Args:
        template (str):
            The input string containing one or more placeholders enclosed
            in curly braces. Example: "CPU Utilization - {resource_name}".
        **kwargs:
            Key-value pairs corresponding to placeholders and their values.
            For example:
                interpolate_placeholders(
                    "CPU Utilization - {resource_name}",
                    resource_name="api-service"
                )

    Returns:
        str: A string with all matching placeholders substituted. If a
        placeholder in the template does not have a corresponding key
        in `kwargs`, it will remain unchanged or be replaced with a
        `{MISSING:key}` token as a fallback.

    Example:
        >>> interpolate_placeholders(
        ...     "Run {run_id} - Resource: {resource_name}",
        ...     run_id="80014829",
        ...     resource_name="api-service"
        ... )
        'Run 80014829 - Resource: api-service'
    """
    if not template or "{" not in template:
        return template
    try:
        return template.format(**kwargs)
    except KeyError as e:
        # gracefully handle missing placeholders
        missing_key = str(e).strip("'")
        return re.sub(rf"{{{missing_key}}}", f"{{MISSING:{missing_key}}}", template)

