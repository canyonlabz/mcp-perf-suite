# services/jmeter_runner.py

import os
import subprocess
import uuid
import time
import csv
import math
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

def _percentile(values, pct):
    """Simple percentile helper used for p90, etc."""
    if not values:
        return None
    vals = sorted(values)
    idx = max(0, min(len(vals) - 1, int(math.ceil(pct / 100.0 * len(vals)) - 1)))
    return vals[idx]

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
        run_id = str(uuid.uuid4())

        # Give JMeter a moment to fail fast if something is wrong
        time.sleep(1.0)
        return_code = process.poll()

        if return_code is not None:
            # JMeter already exited – capture output and surface as error
            out, err = process.communicate(timeout=5)
            status = "FAILED_TO_START"
            ctx.set_state("run_status", status)
            ctx.set_state("error", err.decode(errors="ignore"))
            return {
                "run_id": None,
                "status": status,
                "test_run_id": test_run_id,
                "cmd": " ".join(cmd),
                "jtl_path": jtl_output,
                "log_path": log_output,
                "summary_path": summary_output,
                "stdout": out.decode(errors="ignore"),
                "stderr": err.decode(errors="ignore"),
            }

        # Otherwise we assume it is now running
        status = "RUNNING"
        ctx.set_state("last_run_id", run_id)
        ctx.set_state("run_status", status)
        ctx.set_state("jmeter_pid", process.pid)

        return {
            "run_id": run_id,
            "status": status,
            "test_run_id": test_run_id,
            "cmd": " ".join(cmd),
            "jtl_path": jtl_output,
            "log_path": log_output,
            "summary_path": summary_output,
            "pid": process.pid,
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

def get_jmeter_realtime_status(test_run_id: str, expected_samples: int | None = None) -> dict:
    """
    Compute 'live' smoke-test metrics by reading the JTL for a given test_run_id.

    This is intentionally simple and intended for:
      - Sanity checks that the generated JMX works
      - Light smoke tests before uploading to BlazeMeter

    Metrics:
      - total_samples
      - error_count, error_rate, success_rate
      - avg_response_time_ms
      - p90_response_time_ms
      - per-label summaries (count, errors, avg, p90)
      - optional percent_complete if expected_samples is provided
    """
    jtl_path = _make_jtl_path(test_run_id)

    if not os.path.exists(jtl_path):
        return {
            "test_run_id": test_run_id,
            "status": "NO_JTL",
            "message": "No JTL file exists yet for this test_run_id.",
        }

    total = 0
    error_count = 0
    elapsed_all: list[int] = []
    per_label: dict[str, dict] = {}

    with open(jtl_path, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # JMeter CSV headers match what your sample JTL uses:
            # timeStamp, elapsed, label, responseCode, ...
            try:
                elapsed = int(row.get("elapsed") or 0)
            except ValueError:
                continue

            label = row.get("label", "UNKNOWN")
            rc = (row.get("responseCode") or "").strip()

            total += 1
            elapsed_all.append(elapsed)

            if label not in per_label:
                per_label[label] = {"count": 0, "errors": 0, "elapsed": []}

            per_label[label]["count"] += 1
            per_label[label]["elapsed"].append(elapsed)

            # simple rule: non-2xx/3xx = error
            if not (rc.startswith("2") or rc.startswith("3")):
                error_count += 1
                per_label[label]["errors"] += 1

    if total == 0:
        return {
            "test_run_id": test_run_id,
            "status": "EMPTY_JTL",
            "message": "JTL file exists but has no samples yet.",
            "jtl_path": jtl_path,
        }

    avg = sum(elapsed_all) / total
    p90 = _percentile(elapsed_all, 90)
    error_rate = error_count / total if total else 0.0

    label_summaries = {}
    for label, stats in per_label.items():
        c = stats["count"]
        if c == 0:
            continue
        avg_l = sum(stats["elapsed"]) / c
        p90_l = _percentile(stats["elapsed"], 90)
        label_summaries[label] = {
            "count": c,
            "errors": stats.get("errors", 0),
            "error_rate": (stats.get("errors", 0) / c) if c else 0.0,
            "avg_ms": avg_l,
            "p90_ms": p90_l,
        }

    percent_complete = None
    if expected_samples:
        percent_complete = min(1.0, total / expected_samples)

    last_updated = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(os.path.getmtime(jtl_path)),
    )

    return {
        "test_run_id": test_run_id,
        "status": "OK",   # JTL exists and has samples; we don't distinguish running vs complete here
        "metrics": {
            "total_samples": total,
            "error_count": error_count,
            "error_rate": error_rate,
            "success_rate": 1.0 - error_rate,
            "avg_response_time_ms": avg,
            "p90_response_time_ms": p90,
            "per_label": label_summaries,
            "percent_complete": percent_complete,
        },
        "jtl_path": jtl_path,
        "last_updated_utc": last_updated,
    }

def get_artifact_paths(test_run_id):
    """Returns all artifact paths for this run."""
    return {
        "jtl_path": _make_jtl_path(test_run_id),
        "log_path": _make_log_path(test_run_id),
        "summary_path": _make_summary_path(test_run_id)
    }
