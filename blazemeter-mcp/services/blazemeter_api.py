# services/blazemeter_api.py
import os
import httpx
import base64
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BLAZEMETER_API_KEY = os.getenv("BLAZEMETER_API_KEY")
BLAZEMETER_API_SECRET = os.getenv("BLAZEMETER_API_SECRET")
BLAZEMETER_ACCOUNT_ID = os.getenv("BLAZEMETER_ACCOUNT_ID")
BLAZEMETER_WORKSPACE_ID = os.getenv("BLAZEMETER_WORKSPACE_ID")
BLAZEMETER_API_BASE = "https://a.blazemeter.com/api/v4"

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

async def list_workspaces() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BLAZEMETER_API_BASE}/workspaces?accountId={BLAZEMETER_ACCOUNT_ID}", headers=get_headers())
        resp.raise_for_status()
        workspaces = resp.json()["result"]
        return "\n".join(f"{ws['id']}: {ws['name']}" for ws in workspaces)

async def list_projects(workspace_id: str) -> str:
    workspace_id = BLAZEMETER_WORKSPACE_ID
    async with httpx.AsyncClient() as client:
        url = f"{BLAZEMETER_API_BASE}/projects?workspaceId={workspace_id}"
        resp = await client.get(url, headers=get_headers())
        resp.raise_for_status()
        projects = resp.json()["result"]
        return "\n".join(f"{p['id']}: {p['name']}" for p in projects)

async def list_tests(project_id: str) -> str:
    async with httpx.AsyncClient() as client:
        url = f"{BLAZEMETER_API_BASE}/tests?projectId={project_id}"
        resp = await client.get(url, headers=get_headers({"Content-Type": "application/json"}))
        resp.raise_for_status()
        tests = resp.json()["result"]
        return "\n".join(f"{t['id']}: {t['name']}" for t in tests)

async def run_test(test_id: str) -> str:
    async with httpx.AsyncClient() as client:
        url = f"{BLAZEMETER_API_BASE}/tests/{test_id}/start?delayedStart=false"
        resp = await client.post(url, headers=get_headers({"Content-Type": "application/json"}))
        resp.raise_for_status()
        result = resp.json()["result"]
        return f"Run started. Run ID: {result['id']}"

async def get_results_summary(run_id: str, include_artifacts: bool = False) -> str:
    """
    Fetch and format a summary report for the BlazeMeter test run, merging
    fields from both 'master' details and 'summary statistics' endpoints.

    Args:
        run_id: The BlazeMeter master/run ID.
        include_artifacts: If True, also download JTL/logs to an ./artifacts folder.

    Returns:
        A pretty-printed, human-friendly test summary, or error details if retrieval fails.
    """

    # Prepare results for later combination
    master = {}
    summary = {}

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
    max_virtual_users = summary.get("maxUsers", master.get("maxUsers", "N/A"))
    start_time = format_timestamp(master.get("startTime")) if master.get("startTime") else "N/A"
    end_time = format_timestamp(master.get("endTime")) if master.get("endTime") else "N/A"
    duration_sec = summary.get("duration", "N/A")

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

    report = (
        f"BlazeMeter Test Run Summary\n"
        f"===========================\n"
        f"Test Name: {test_name}\n"
        f"Test ID: {test_id}\n"
        f"Run ID: {run_id}\n\n"
        f"Start Time: {start_time}\n"
        f"End Time: {end_time}\n"
        f"Duration: {duration_sec}s\n"
        f"Max Virtual Users: {max_virtual_users}\n\n"
        f"Samples Total: {samples_total}\n"
        f"Pass Count: {pass_count}\n"
        f"Fail Count: {fail_count}\n"
        f"Error Count: {error_count}\n\n"
        f"Response Time (ms):\n"
        f"  Min: {rt_min}\n"
        f"  Max: {rt_max}\n"
        f"  Avg: {rt_avg}\n"
        f"  90th Percentile: {rt_p90}\n"
    )
    return report
