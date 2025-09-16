# services/blazemeter_api.py
import os
import httpx
import base64
import time
import zipfile
import shutil
import json
import csv
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv
from fastmcp import FastMCP, Context  # ✅ FastMCP 2.x import
from utils.config import load_config

# Load environment variables from .env file such as API keys and secrets
load_dotenv()

# Load the config.yaml which contains path folder settings. NOTE: OS specific yaml files will override default config.yaml
config = load_config()
bz_config = config.get('blazemeter', {})
artifacts_base = config['artifacts']['artifacts_path']

BLAZEMETER_API_KEY = os.getenv("BLAZEMETER_API_KEY")
BLAZEMETER_API_SECRET = os.getenv("BLAZEMETER_API_SECRET")
BLAZEMETER_ACCOUNT_ID = os.getenv("BLAZEMETER_ACCOUNT_ID")
BLAZEMETER_WORKSPACE_ID = os.getenv("BLAZEMETER_WORKSPACE_ID")
BLAZEMETER_API_BASE = "https://a.blazemeter.com/api/v4"

# ===============================================
# Helper Functions
# ===============================================

def get_headers(extra: dict = None):
    # Basic Auth header BlazeMeter expects
    auth = base64.b64encode(f"{BLAZEMETER_API_KEY}:{BLAZEMETER_API_SECRET}".encode()).decode()
    h = {
        "Authorization": f"Basic {auth}",
    }
    if extra:
        h.update(extra)
    return h

def format_timestamp(ts: str) -> str:
    """Convert BlazeMeter ISO timestamp to readable format."""
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

def to_epoch(dt_str: str) -> int:
    fmts = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(dt_str, fmt)
            return int(time.mktime(dt.timetuple()))
        except Exception:
            continue
    raise ValueError(f"Invalid date format: {dt_str}. Expected 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD'.")

def epoch_to_timestamp(epoch: int) -> str:
    if epoch is None:
        return None
    return datetime.utcfromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S UTC")

def format_duration(seconds: int) -> str:
    if seconds is None:
        return "N/A"
    minutes, sec = divmod(seconds, 60)
    return f"{minutes}m {sec}s" if minutes else f"{sec}s"

def write_test_config_json(run_id: str, summary_fields: dict) -> str:
    """
    Writes test_config.json to the proper artifacts path for the given run.
    Returns the path to the JSON file or an error message.
    """
    dest_folder = os.path.join(artifacts_base, str(run_id), "blazemeter")
    os.makedirs(dest_folder, exist_ok=True)
    config_path = os.path.join(dest_folder, "test_config.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(summary_fields, f, indent=2)
        return config_path
    except Exception as e:
        return f"❗ Error writing test_config.json: {e}"

# ===============================================
# Main API Functions for the BlazeMeter MCP
# ===============================================

async def list_workspaces() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BLAZEMETER_API_BASE}/workspaces?accountId={BLAZEMETER_ACCOUNT_ID}", headers=get_headers())
        resp.raise_for_status()
        workspaces = resp.json()["result"]
        return "\n".join(f"{ws['id']}: {ws['name']}" for ws in workspaces)

async def list_projects(workspace_id: str | None = None, project_name: str | None = None) -> str:
    """List BlazeMeter projects for a workspace.

    Args:
        workspace_id: Optional explicit workspace ID. If omitted/None/empty, falls back to env `BLAZEMETER_WORKSPACE_ID`.
        project_name: Optional filter to match a specific project name.

    Returns:
        Newline separated string of `id: name` entries, or an informative message if none found / error.
    """
    # Fallback to globally configured workspace id if not provided explicitly
    workspace_id = workspace_id or BLAZEMETER_WORKSPACE_ID
    if not workspace_id:
        return "❗ workspace_id not provided and BLAZEMETER_WORKSPACE_ID is not set in the environment."
    
    # Get pagination limit from config or default to 100
    pagination_limit = bz_config.get('pagination_limit', 100)

    async with httpx.AsyncClient() as client:
        url = f"{BLAZEMETER_API_BASE}/projects?workspaceId={workspace_id}&limit={pagination_limit}"
        if project_name:
            url += f"&name={project_name}"
        resp = await client.get(url, headers=get_headers())
        resp.raise_for_status()
        projects = resp.json()["result"]
        
        if not projects and project_name:
            return f"No projects found matching '{project_name}'"
        
        return "\n".join(f"{p['id']}: {p['name']}" for p in projects)

async def list_tests(project_id: str) -> str:
    async with httpx.AsyncClient() as client:
        url = f"{BLAZEMETER_API_BASE}/tests?projectId={project_id}"
        resp = await client.get(url, headers=get_headers({"Content-Type": "application/json"}))
        resp.raise_for_status()
        tests = resp.json()["result"]
        return "\n".join(f"{t['id']}: {t['name']}" for t in tests)

async def run_test(test_id: str, ctx: Context) -> str:
    """
    Starts a BlazeMeter test run and stores the run_id in context for workflow chaining.
    Args:
        test_id: The BlazeMeter test ID.
        ctx (Context, optional): FastMCP context object for state management.
    Returns:
        String with created run ID and status.
    """
    async with httpx.AsyncClient() as client:
        url = f"{BLAZEMETER_API_BASE}/tests/{test_id}/start?delayedStart=false"
        resp = await client.post(url, headers=get_headers({"Content-Type": "application/json"}))
        resp.raise_for_status()
        result = resp.json()["result"]
        run_id = result['id']
        # Optionally store run_id in context for downstream tools
        if ctx is not None:
            ctx.set_state("run_id", run_id)
        return f"Run started. Run ID: {run_id}"

async def get_test_status(run_id: str, ctx: Context) -> dict:
    """
    Retrieves the current status and status breakdown for the given BlazeMeter run.

    Args:
        run_id: The BlazeMeter master/run ID.
        ctx (Context, optional): FastMCP workflow context for state passing.

    Returns:
        Dictionary with keys:
            - run_id: Run/master ID
            - status: Main status string (e.g. 'ENDED', 'RUNNING', etc.)
            - statuses: Breakdown of session states (pending, booting, ready, ended)
            - error: Error object/string/null (if present in API response)
            - has_error: True if error or failed/aborted state detected, else False
            - context: Updated workflow context (if used)
    """
    url = f"{BLAZEMETER_API_BASE}/masters/{run_id}/status"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=get_headers())
            resp.raise_for_status()
            data = resp.json()
            result = data.get("result", {})
            status = result.get("status", "UNKNOWN")
            statuses = result.get("statuses", {})
            error = data.get("error")
            has_error = bool(error) or (status.upper() in {"FAILED", "ERROR", "ABORTED"})
            # Save to context for workflow chaining
            if ctx is not None:
                ctx.set_state("last_status", status)
                ctx.set_state("statuses", statuses)
                ctx.set_state("has_error", has_error)
                await ctx.info("Current Status", status)
            return {
                "run_id": run_id,
                "status": status,
                "statuses": statuses,
                "error": error,
                "has_error": has_error
            }
    except Exception as e:
        if ctx is not None:
            ctx.set_state("last_status", "ERROR")
            ctx.set_state("error", str(e))
            ctx.set_state("has_error", True)
            await ctx.error("Error retrieving test status", str(e))
        return {
            "run_id": run_id,
            "status": "ERROR",
            "statuses": {},
            "error": str(e),
            "has_error": True
        }

async def get_results_summary(run_id: str, ctx: Context) -> str:
    """
    Fetch and format a summary report for the BlazeMeter test run, merging
    fields from both 'master' details and 'summary statistics' endpoints.
    Also writes test_config.json with key run and test config metadata.

    Args:
        run_id: The BlazeMeter master/run ID.
        ctx (Context, optional): FastMCP workflow context for caching or chaining summary.

    Returns:
        A pretty-printed, human-friendly test summary, or error details if retrieval fails.
        Writes test_config.json for downstream analysis. Updates context with summary if present.
    """

    # Prepare results for later combination
    master = {}
    summary = {}
    summary_fields = {}
    config_fields = {}

    try:
        async with httpx.AsyncClient() as client:
            # 1. Fetch main test run (master) info
            master_url = f"{BLAZEMETER_API_BASE}/masters/{run_id}"
            master_resp = await client.get(master_url, headers=get_headers(), timeout=30.0)
            master_resp.raise_for_status()
            master = master_resp.json().get("result", {})

            # 2. Fetch summary statistics (aggregated metrics per run)
            summary_url = f"{BLAZEMETER_API_BASE}/masters/{run_id}/reports/default/summary"
            summary_resp = await client.get(summary_url, headers=get_headers(), timeout=30.0)
            summary_resp.raise_for_status()
            summary_data = summary_resp.json().get("result", {})

            # There may be a "summary" array (per doc); pick the overall summary.
            summary_list = summary_data.get("summary", [])
            summary = summary_list[0] if summary_list else {}

    except httpx.HTTPStatusError as he:
        return f"❗ Error: BlazeMeter API request failed ({he.response.status_code})\nDetails: {he}"
    except Exception as e:
        return f"❗ Error: Could not fetch summary for run {run_id}.\nDetails: {e}"

    if not master or not summary:
        return f"⚠️ No results available for run ID {run_id} (master or summary empty)."

    # Safely extract key fields
    test_id = master.get("testId", "Unknown")
    test_name = master.get("name", "Unknown")
    workspace_id = BLAZEMETER_WORKSPACE_ID if BLAZEMETER_WORKSPACE_ID else "Workspace ID not found"
    project_id = master.get("projectId", None)
    sessions_id = master.get("sessionsId", [])
    max_virtual_users = summary.get("maxUsers", master.get("maxUsers", "N/A"))
    start_time = epoch_to_timestamp(master.get("created")) if master.get("created") else "N/A"
    end_time = epoch_to_timestamp(master.get("ended")) if master.get("ended") else "N/A"

    # Calculate duration in seconds if possible
    duration_seconds = None
    duration_str = "N/A"
    if start_time and end_time:
        try:
            duration_seconds = int(master.get("ended")) - int(master.get("created"))
            duration_str = format_duration(duration_seconds)
        except Exception:
            pass

    samples_total = summary.get("hits", "N/A")
    error_count = summary.get("failed", "N/A")
    try:
        # Only compute if both fields are int-able
        pass_count = int(samples_total) - int(error_count)
        fail_count = int(error_count)
    except Exception:
        pass_count = "N/A"
        fail_count = error_count

    rt_min = summary.get("min", "N/A")
    rt_max = summary.get("max", "N/A")
    rt_avg = summary.get("avg", "N/A")
    rt_p90 = summary.get("tp90", "N/A")

    # Extract relevant config from first executions[] entry, if present
    executions = master.get("executions", [])
    if executions:
        exec0 = executions[0]
        config_fields = {
            "concurrency": exec0.get("concurrency"),
            "rampUp": exec0.get("rampUp"),
            "steps": exec0.get("steps"),
            "iterations": exec0.get("iterations"),
        }

    # Fill out the test_config.json schema
    summary_fields = {
        "run_id": run_id,
        "workspace_id": workspace_id,
        "project_id": project_id,
        "test_id": test_id,
        "test_name": test_name,
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": duration_seconds,
        "max_virtual_users": max_virtual_users,
        "samples_total": samples_total,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "error_count": error_count,
        "response_time_min_ms": rt_min,
        "response_time_max_ms": rt_max,
        "response_time_avg_ms": rt_avg,
        "response_time_p90_ms": rt_p90,
        "config": config_fields,
        "labels": [lbl.get("name") for lbl in master.get("jetpackLabels", [])] if master.get("jetpackLabels") else None,
        "notes": ""
    }

    test_config_json = write_test_config_json(run_id, summary_fields)

    # Update context with summary for downstream tools
    if ctx is not None:
        await ctx.info("Test Configuration JSON Path", test_config_json)
        ctx.set_state("summary", summary_fields)
        ctx.set_state("test_config_json_path", test_config_json)

    report = (
        f"BlazeMeter Test Run Summary\n"
        f"===========================\n"
        f"Test Name: {test_name}\n"
        f"Test ID: {test_id}\n"
        f"Run ID: {run_id}\n\n"
        f"Start Time: {start_time}\n"
        f"End Time: {end_time}\n"
        f"Duration: {duration_str}s\n"
        f"Max Virtual Users: {max_virtual_users}\n\n"
        f"Samples Total: {samples_total}\n"
        f"Pass Count: {pass_count}\n"
        f"Fail Count: {fail_count}\n"
        f"Error Count: {error_count}\n\n"
        f"Response Time (ms):\n"
        f"Session ID: {sessions_id}\n"
        f"  Min: {rt_min}\n"
        f"  Max: {rt_max}\n"
        f"  Avg: {rt_avg}\n"
        f"  90th Percentile: {rt_p90}\n"
        f"Test Config: \n"
        f"  concurrency={config_fields.get('concurrency')}\n"
        f"  rampUp={config_fields.get('rampUp')}\n"
        f"  steps={config_fields.get('steps')}\n"
        f"  iterations={config_fields.get('iterations')}\n"
        f"Test Configuration JSON: {test_config_json}\n"
    )
    return report

async def list_test_runs(test_id: str, start_time: str, end_time: str, ctx: Context) -> list:
    """
    Lists BlazeMeter test runs (masters) for the specified test and time range.
    Accepts dates as 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS'.

    Returns:
        List of dicts with run/master info and session IDs.
        Fields: run_id, test_name, start_time, end_time, status, session_ids, duration_seconds (optional)
    """
    start_epoch = to_epoch(start_time)
    end_epoch = to_epoch(end_time)
    url = f"{BLAZEMETER_API_BASE}/masters?testId={test_id}&from={start_epoch}&to={end_epoch}"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=get_headers())
            resp.raise_for_status()
            results = resp.json().get("result", [])
        except Exception as e:
            return [{"error": f"Failed to retrieve test runs: {e}"}]

        runs = []
        for m in results:
            created = m.get("created")
            ended = m.get("ended")
            # Calculate duration in seconds if possible
            duration_seconds = None
            duration_str = "N/A"
            if created and ended:
                try:
                    duration_seconds = int(ended) - int(created)
                    duration_str = format_duration(duration_seconds)
                except Exception:
                    pass
            runs.append({
                "run_id": m.get("id"),
                "test_name": m.get("name"),
                "start_time": epoch_to_timestamp(created),
                "end_time": epoch_to_timestamp(ended),
                "sessions_id": m.get("sessionsId", []),
                "project_id": m.get("projectId"),
                "max_users": m.get("maxUsers"),
                "duration": duration_str,                   # Human-friendly e.g. "2m 8s"
                "duration_seconds": duration_seconds,       # Raw seconds for downstream use
                "locations": m.get("locations", []),
            })
            await ctx.info(f"Found run ID {m.get('id')} with test name {m.get('name')}.",
                           extra={
                                 "start_time": epoch_to_timestamp(created),
                                 "end_time": epoch_to_timestamp(ended),
                                 "duration": duration_str,
                                 "sessions_id": m.get("sessionsId", []),
                                 "project_id": m.get("projectId"),
                                 "max_users": m.get("maxUsers"),
                                 "locations": m.get("locations", []),
                           })
        return runs if runs else [{"message": "No matching runs found."}]

async def get_session_artifacts(session_id: str, ctx: Context) -> dict:
    """
    Calls BlazeMeter API to get artifact and log file URLs for a given session.

    Args:
        session_id: BlazeMeter session ID
        ctx (Context, optional): FastMCP workflow context for passing file URLs downstream.

    Returns:
        Dict mapping each filename to its downloadable URL (dataUrl). Updates context with file list if present.
    """
    url = f"{BLAZEMETER_API_BASE}/sessions/{session_id}/reports/logs"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=get_headers())
        resp.raise_for_status()
        result = resp.json().get("result", {})
        files = {}
        for item in result.get("data", []):
            filename = item.get("filename")
            data_url = item.get("dataUrl")
            if filename and data_url:
                files[filename] = data_url
            if filename and filename.lower() == "artifacts.zip":
                ctx.set_state("artifact_zip_url", data_url)
                ctx.set_state("artifact_zip_filename", filename)
                await ctx.info("Artifact ZIP URL", data_url)
                await ctx.info("Artifact ZIP Filename", filename)
        if ctx is not None:
            ctx.set_state("artifact_file_list", files)
            ctx.set_state("artifact_file_session_id", session_id)
        return files if files else {"message": "No files found in this session's logs report."}

async def download_artifact_zip_file(artifact_zip_url: str, run_id: str, ctx: Context) -> str:
    """
    Downloads the artifact ZIP file for a test run to the correct artifacts folder.

    Args:
        artifact_zip_url: Signed S3 URL for artifacts.zip.
        run_id: The BlazeMeter run ID (master ID).
        ctx (Context, optional): FastMCP workflow context to save downloaded file path.

    Returns:
        Full local path to the downloaded ZIP file, or error message.
        Updates context with file path.
    """
    dest_folder = os.path.join(artifacts_base, str(run_id), "blazemeter")
    os.makedirs(dest_folder, exist_ok=True)
    local_zip_path = os.path.join(dest_folder, "artifacts.zip")
    try:
        async with httpx.AsyncClient() as client:
            # Try with minimal headers first (like Postman might send)
            minimal_headers = {"Accept": "*/*", "User-Agent": "Mozilla/5.0 (compatible; BlazeMeter-MCP/1.0)"}
            try:
                response = await client.get(artifact_zip_url, headers=minimal_headers)
                response.raise_for_status()
            except Exception as e1:
                # If minimal headers fail, try with BlazeMeter auth headers
                try:
                    response = await client.get(artifact_zip_url, headers=get_headers({"Accept": "*/*"}))
                    response.raise_for_status()
                except Exception as e2:
                    if ctx is not None:
                        ctx.set_state("download_error", str(e2))
                    return f"❗ Error downloading artifacts.zip: Minimal headers failed: {e1}, Auth headers failed: {e2}"
            
            with open(local_zip_path, "wb") as f:
                f.write(response.content)
        if ctx is not None:
            ctx.set_state("local_zip_path", local_zip_path)
            await ctx.info("Downloaded artifacts.zip to", local_zip_path)
        return local_zip_path
    except Exception as e:
        if ctx is not None:
            ctx.set_state("download_error", str(e))
            await ctx.error("Error downloading artifacts.zip", str(e))
        return f"❗ Error downloading artifacts.zip: {e}"

async def extract_artifact_zip_file(local_zip_path: str, run_id: str, ctx: Context) -> list:
    """
    Extracts the specified artifacts.zip file to the appropriate folder for a run.

    Args:
        local_zip_path: Full path to the downloaded artifacts.zip file.
        run_id: BlazeMeter run ID.
        ctx (Context, optional): Workflow context to store extracted file list.

    Returns:
        List of full paths to the extracted files (within the run's 'artifacts' directory). Updates context for downstream use.
    """
    dest_folder = os.path.join(artifacts_base, str(run_id), "blazemeter", "artifacts")
    os.makedirs(dest_folder, exist_ok=True)
    try:
        with zipfile.ZipFile(local_zip_path, "r") as zip_ref:
            zip_ref.extractall(dest_folder)
            extracted_files = [os.path.join(dest_folder, name) for name in zip_ref.namelist()]
        if ctx is not None:
            ctx.set_state("extracted_files", extracted_files)
            await ctx.info(f"Extracted {len(extracted_files)} artifact files.")
        return extracted_files
    except Exception as e:
        if ctx is not None:
            ctx.set_state("extraction_error", str(e))
            await ctx.error("Error extracting artifacts.zip", str(e))
        return [f"❗ Error extracting ZIP: {e}"]

def process_extracted_artifact_files(run_id: str, extracted_files: list, ctx: Context) -> dict:
    """
    Processes BlazeMeter artifact files for a run:
      - Moves/renames kpi.jtl to test-results.csv
      - Moves jmeter.log
      - Ignores error.jtl and other .jtl files

    Args:
        run_id: BlazeMeter run ID.
        extracted_files: List of full paths to extracted files.
        ctx (Context, optional): Workflow context to store result file paths and errors.

    Returns:
        Dict with processed file paths, errors. Updates context for downstream steps.
    """
    result = {"errors": []}
    dest_folder = os.path.join(artifacts_base, str(run_id), "blazemeter")
    os.makedirs(dest_folder, exist_ok=True)

    # Only use kpi.jtl for CSV conversion
    kpi_file = next((f for f in extracted_files if os.path.basename(f).lower() == 'kpi.jtl'), None)
    log_file = next((f for f in extracted_files if os.path.basename(f).lower() == 'jmeter.log'), None)

    # Rename and move kpi.jtl
    if kpi_file and os.path.exists(kpi_file):
        csv_path = os.path.join(dest_folder, "test-results.csv")
        shutil.move(kpi_file, csv_path)
        result["csv_path"] = csv_path
    else:
        result["errors"].append("kpi.jtl (metrics) not found.")

    # Move jmeter.log
    if log_file and os.path.exists(log_file):
        log_dest = os.path.join(dest_folder, "jmeter.log")
        shutil.move(log_file, log_dest)
        result["log_path"] = log_dest
    else:
        result["errors"].append("jmeter.log not found.")

    if ctx is not None:
        ctx.set_state("processed_csv_path", result.get("csv_path"))
        ctx.set_state("processed_log_path", result.get("log_path"))
        ctx.set_state("process_errors", result.get("errors"))

    return result

async def get_public_report_url(run_id: str, ctx: Context) -> dict:
    """
    Requests a public token for the provided run_id and returns a shareable BlazeMeter report URL.

    Args:
        run_id: The BlazeMeter master/run ID.
        ctx (Context, optional): FastMCP context to pass/share report URL and token.

    Returns:
        Dictionary with:
            - run_id: The provided run ID.
            - public_url: The public report URL for sharing.
            - public_token: The raw public token.
            - is_new: True if the token was newly created, False if already existed.
            - error: Error message or None.
        Updates context with public_url and public_token for workflow chaining.
    """
    url = f"{BLAZEMETER_API_BASE}/masters/{run_id}/public-token"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=get_headers({"Content-Type": "application/json"}))
            resp.raise_for_status()
            data = resp.json()
            result = data.get("result", {})
            token = result.get("publicToken")
            is_new = result.get("new", False)
            if token:
                public_url = f"https://a.blazemeter.com/app/?public-token={token}#/masters/{run_id}/summary"
                if ctx is not None:
                    ctx.set_state("public_url", public_url)
                    ctx.set_state("public_token", token)
                    ctx.set_state("is_new_token", is_new)
                return {
                    "run_id": run_id,
                    "public_url": public_url,
                    "public_token": token,
                    "is_new": is_new,
                    "error": None
                }
            else:
                if ctx is not None:
                    ctx.set_state("public_url", None)
                    ctx.set_state("public_token", None)
                    ctx.set_state("is_new_token", False)
                    ctx.set_state("public_report_error", "Public token not returned by API.")
                return {
                    "run_id": run_id,
                    "public_url": None,
                    "public_token": None,
                    "is_new": False,
                    "error": "Public token not returned by API."
                }
    except Exception as e:
        if ctx is not None:
            ctx.set_state("public_url", None)
            ctx.set_state("public_report_error", str(e))
        return {
            "run_id": run_id,
            "public_url": None,
            "public_token": None,
            "is_new": False,
            "error": str(e)
        }

async def fetch_aggregate_report(run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Fetch aggregate performance report from BlazeMeter API and save to CSV.
    Returns only the 'ALL' aggregate summary to keep response lightweight.
    """
    try:
        url = f"{BLAZEMETER_API_BASE}/masters/{run_id}/reports/aggregatereport/data"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=get_headers(), timeout=30.0)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("error"):
                return {"error": f"BlazeMeter API error: {data['error']}", "status": "failed"}
            
            results = data.get("result", [])
            if not results:
                return {"error": "No aggregate data available", "status": "failed"}
            
            # Save to CSV for PerfAnalysis consumption
            csv_file = write_aggregate_report_csv(run_id, results)
            
            # Extract only the 'ALL' aggregate for response
            all_aggregate = None
            for item in results:
                if item.get("labelName") == "ALL":
                    all_aggregate = clean_aggregate_data(item)
                    break
            
            if not all_aggregate:
                return {"error": "No 'ALL' aggregate found in BlazeMeter response", "status": "failed"}

            # Update context with aggregate data and CSV path
            ctx.set_state("aggregate_report_data", json.dumps(all_aggregate))
            ctx.set_state("aggregate_report_csv", csv_file)
            
            await ctx.info(f"Aggregate report retrieved", 
                          f"ALL stats: {all_aggregate['samples']} samples, "
                          f"{all_aggregate['avgResponseTime']:.1f}ms avg")
            
            return {
                "status": "success",
                "run_id": run_id,
                "total_labels": len(results),
                "aggregate_summary": all_aggregate,
                "csv_file": csv_file
            }
            
    except Exception as e:
        error_msg = f"Failed to fetch aggregate report: {str(e)}"
        await ctx.error("Aggregate Report Error", error_msg)
        return {"error": error_msg, "status": "failed"}

def write_aggregate_report_csv(run_id: str, results: List[Dict]) -> str:
    """Write aggregate report data to CSV file"""
    
    dest_folder = os.path.join(artifacts_base, str(run_id), "blazemeter")
    os.makedirs(dest_folder, exist_ok=True)
    
    csv_file = os.path.join(dest_folder, "aggregate_performance_report.csv")
    
    # Define CSV headers matching the JSON structure
    headers = [
        "labelName", "samples", "avgResponseTime", "minResponseTime", "maxResponseTime",
        "medianResponseTime", "90line", "95line", "99line", "stDev",
        "avgLatency", "errorsCount", "errorsRate", "avgThroughput",
        "avgBytes", "duration", "concurrency", "hasLabelPassedThresholds"
    ]
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        
        for item in results:
            # Clean the data and write row
            row = {header: item.get(header, '') for header in headers}
            writer.writerow(row)
    
    return csv_file

def clean_aggregate_data(item: Dict) -> Dict:
    """Clean aggregate data for JSON serialization"""
    import math
    
    cleaned = {}
    for key, value in item.items():
        # Skip labelId as it's not needed
        if key == "labelId":
            continue
            
        # Handle NaN values
        if isinstance(value, float) and math.isnan(value):
            cleaned[key] = None
        # Ensure proper types for JSON serialization
        elif isinstance(value, (int, float)):
            cleaned[key] = float(value) if isinstance(value, float) else int(value)
        else:
            cleaned[key] = value
    
    return cleaned
