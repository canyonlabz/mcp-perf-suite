import httpx
import os
from datetime import datetime

BLAZEMETER_API_KEY = os.getenv("BLAZEMETER_API_KEY")
BLAZEMETER_API_BASE = "https://a.blazemeter.com/api/v4"

def get_headers() -> dict:
    return {"Authorization": f"Bearer {BLAZEMETER_API_KEY}"}

def format_timestamp(ts: str) -> str:
    """Convert BlazeMeter ISO timestamp to readable format."""
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

async def list_workspaces() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BLAZEMETER_API_BASE}/workspaces", headers=get_headers())
        resp.raise_for_status()
        workspaces = resp.json()["result"]
        return "\n".join(f"{ws['id']}: {ws['name']}" for ws in workspaces)

async def list_projects(workspace_id: str) -> str:
    async with httpx.AsyncClient() as client:
        url = f"{BLAZEMETER_API_BASE}/workspaces/{workspace_id}/projects"
        resp = await client.get(url, headers=get_headers())
        resp.raise_for_status()
        projects = resp.json()["result"]
        return "\n".join(f"{p['id']}: {p['name']}" for p in projects)

async def list_tests(project_id: str) -> str:
    async with httpx.AsyncClient() as client:
        url = f"{BLAZEMETER_API_BASE}/projects/{project_id}/tests"
        resp = await client.get(url, headers=get_headers())
        resp.raise_for_status()
        tests = resp.json()["result"]
        return "\n".join(f"{t['id']}: {t['name']}" for t in tests)

async def run_test(test_id: str) -> str:
    async with httpx.AsyncClient() as client:
        url = f"{BLAZEMETER_API_BASE}/tests/{test_id}/start"
        resp = await client.post(url, headers=get_headers())
        resp.raise_for_status()
        result = resp.json()["result"]
        return f"Run started. Run ID: {result['id']}"

async def get_results_summary(run_id: str) -> str:
    """Fetch and format a summary report for the BlazeMeter test run."""

    async with httpx.AsyncClient() as client:
        summary_url = f"{BLAZEMETER_API_BASE}/masters/{run_id}/summary"
        resp = await client.get(summary_url, headers=get_headers(), timeout=30.0)
        resp.raise_for_status()
        summary = resp.json().get("result", {})

    if not summary:
        return f"No summary available for run ID {run_id}."

    # Extract fields safely with defaults
    test_id = summary.get("testId", "Unknown")
    test_name = summary.get("testName", "Unknown")
    max_virtual_users = summary.get("maxVirtualUsers", "N/A")
    start_time = format_timestamp(summary.get("startTime")) if summary.get("startTime") else "N/A"
    end_time = format_timestamp(summary.get("endTime")) if summary.get("endTime") else "N/A"

    duration_sec = None
    if start_time != "N/A" and end_time != "N/A":
        start_dt = datetime.fromisoformat(summary["startTime"].replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(summary["endTime"].replace("Z", "+00:00"))
        duration_sec = int((end_dt - start_dt).total_seconds())
    duration_str = f"{duration_sec}s" if duration_sec is not None else "N/A"

    samples_total = summary.get("samplesTotal", "N/A")

    error_count = summary.get("errorCount", summary.get("failCount", 0))
    pass_count = samples_total - error_count if isinstance(samples_total, int) else "N/A"
    fail_count = error_count

    # Aggregate response times
    response_times = summary.get("aggregatedResponseTimes", {})
    rt_min = response_times.get("min", "N/A")
    rt_max = response_times.get("max", "N/A")
    rt_avg = response_times.get("avg", "N/A")
    rt_p90 = response_times.get("p90", "N/A")

    # Build formatted report
    report = (
        f"BlazeMeter Test Run Summary\n"
        f"===========================\n"
        f"Test Name: {test_name}\n"
        f"Test ID: {test_id}\n"
        f"Run ID: {run_id}\n\n"
        f"Start Time: {start_time}\n"
        f"End Time: {end_time}\n"
        f"Duration: {duration_str}\n"
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
