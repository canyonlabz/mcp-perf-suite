# services/jmeter_runner.py

import os
import subprocess
import uuid
import time
from dotenv import load_dotenv
from utils.config import load_config, load_jmeter_config

# Load environment variables (API keys, secrets, etc.)
load_dotenv()

# Load configuration
CONFIG = load_config()
JMETER_CONFIG = CONFIG.get('jmeter', {})
ARTIFACTS_PATH = CONFIG['artifacts']['artifacts_path']
JMX_CONFIG = load_jmeter_config()

# ----------------------------------------------------------
# Helper Functions
# ----------------------------------------------------------

def _get_jmeter_bin():
    return JMETER_CONFIG.get('jmeter_bin_path', '')

def _get_start_exe():
    return JMETER_CONFIG.get('jmeter_start_exe', 'jmeter.bat')

def _get_stop_exe():
    return JMETER_CONFIG.get('jmeter_stop_exe', 'stoptest.cmd')

def _get_jmeter_home():
    return JMETER_CONFIG.get('jmeter_home', '')

def _get_artifact_dir(test_run_id):
    path = os.path.join(ARTIFACTS_PATH, str(test_run_id), 'jmeter')
    os.makedirs(path, exist_ok=True)
    return path

def _make_jtl_path(test_run_id):
    return os.path.join(_get_artifact_dir(test_run_id), f'{test_run_id}.jtl')

def _make_log_path(test_run_id):
    return os.path.join(_get_artifact_dir(test_run_id), f'{test_run_id}.log')

def _make_summary_path(test_run_id):
    return os.path.join(_get_artifact_dir(test_run_id), f'{test_run_id}_summary.json')

# ----------------------------------------------------------
# Main JMeter Runner Functions
# ----------------------------------------------------------

async def run_jmeter_test(test_run_id, jmx_path, ctx):
    """
    Starts a new JMeter test execution.
    Args:
        test_run_id (str): Unique test run identifier.
        jmx_path (str): Path to the JMeter JMX test plan.
        ctx (Context, optional): Workflow context.
    Returns:
        dict: Run status, artifact locations, and error (if any).
    """
    bin_dir = _get_jmeter_bin()
    start_exe = _get_start_exe()
    jtl_output = _make_jtl_path(test_run_id)
    log_output = _make_log_path(test_run_id)
    summary_output = _make_summary_path(test_run_id)

    cmd = [
        os.path.join(bin_dir, start_exe),
        f'-n',
        f'-t', jmx_path,
        f'-l', jtl_output,
        f'-j', log_output
    ]

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        status = "STARTED"
        run_id = str(uuid.uuid4())
        ctx.set_state("last_run_id", run_id)
        ctx.set_state("run_status", status)
        return {
            "run_id": run_id,
            "status": status,
            "test_run_id": test_run_id,
            "cmd": " ".join(cmd),
            "jtl_path": jtl_output,
            "log_path": log_output,
            "summary_path": summary_output,
            "start_time": time.time()
        }
    except Exception as e:
        ctx.set_state("run_status", "ERROR")
        ctx.set_state("error", str(e))
        return {
            "run_id": None,
            "status": "ERROR",
            "error": str(e)
        }

async def stop_running_test(test_run_id, ctx):
    """
    Stops a running JMeter test execution.
    Args:
        test_run_id (str): Unique test run identifier.
        ctx (Context): Workflow context.
    Returns:
        dict: Stop status and error info.
    """
    bin_dir = _get_jmeter_bin()
    stop_exe = _get_stop_exe()
    stop_cmd = [os.path.join(bin_dir, stop_exe)]

    try:
        proc = subprocess.Popen(stop_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(timeout=10)
        status = "STOPPED" if proc.returncode == 0 else "ERROR"
        ctx.set_state("run_status", status)
        return {
            "test_run_id": test_run_id,
            "cmd": " ".join(stop_cmd),
            "output": out.decode(),
            "error": err.decode() if proc.returncode != 0 else None,
            "status": status,
            "stop_time": time.time()
        }
    except Exception as e:
        ctx.set_state("run_status", "ERROR")
        ctx.set_state("error", str(e))
        return {
            "test_run_id": test_run_id,
            "status": "ERROR",
            "error": str(e)
        }

# Additional helpers (if you want run status, artifact validation, etc.)
def list_jmeter_scripts_for_run(test_run_id: str) -> dict:
    """
    Lists existing JMeter .jmx scripts for a given test_run_id under:
        <ARTIFACTS_PATH>/<test_run_id>/jmeter

    Does NOT create the directory if it doesn't exist.
    Returns:
        dict: {
            "test_run_id": str,
            "artifact_dir": str,
            "scripts": [
                {
                    "filename": str,
                    "full_path": str,
                    "size_bytes": int,
                    "modified_time_utc": str
                },
                ...
            ],
            "count": int,
            "status": "OK" | "NOT_FOUND" | "EMPTY",
            "message": str
        }
    """
    artifact_dir = os.path.join(ARTIFACTS_PATH, str(test_run_id), "jmeter")

    if not os.path.isdir(artifact_dir):
        return {
            "test_run_id": str(test_run_id),
            "artifact_dir": artifact_dir,
            "scripts": [],
            "count": 0,
            "status": "NOT_FOUND",
            "message": "No JMeter artifact directory found for this test_run_id."
        }

    scripts = []
    for name in os.listdir(artifact_dir):
        if not name.lower().endswith(".jmx"):
            continue

        full_path = os.path.join(artifact_dir, name)
        try:
            size_bytes = os.path.getsize(full_path)
            mtime = os.path.getmtime(full_path)
            modified_time_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime))
        except OSError:
            size_bytes = None
            modified_time_utc = None

        scripts.append(
            {
                "filename": name,
                "full_path": full_path,
                "size_bytes": size_bytes,
                "modified_time_utc": modified_time_utc,
            }
        )

    status = "OK" if scripts else "EMPTY"
    message = (
        "JMeter scripts found."
        if scripts
        else "Artifact directory exists but contains no .jmx files."
    )

    return {
        "test_run_id": str(test_run_id),
        "artifact_dir": artifact_dir,
        "scripts": scripts,
        "count": len(scripts),
        "status": status,
        "message": message,
    }

def get_artifact_paths(test_run_id):
    """Returns all artifact paths for this run."""
    return {
        "jtl_path": _make_jtl_path(test_run_id),
        "log_path": _make_log_path(test_run_id),
        "summary_path": _make_summary_path(test_run_id)
    }
