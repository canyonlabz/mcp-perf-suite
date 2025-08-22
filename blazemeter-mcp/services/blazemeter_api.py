import httpx
import os

BLAZEMETER_API_KEY = os.getenv("BLAZEMETER_API_KEY")
BLAZEMETER_API_BASE = "https://a.blazemeter.com/api/v4"

def get_headers() -> dict:
    return {"Authorization": f"Bearer {BLAZEMETER_API_KEY}"}

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
    async with httpx.AsyncClient() as client:
        summary_url = f"{BLAZEMETER_API_BASE}/masters/{run_id}/summary"
        summary_resp = await client.get(summary_url, headers=get_headers())
        summary_resp.raise_for_status()
        summary = summary_resp.json().get("result", {})
        # Parse out needed metrics, format them simply
        return f"Test Run {run_id} Summary: {summary}"

