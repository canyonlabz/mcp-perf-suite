# services/msgraph_api.py
import os
import httpx
import json
import base64
from typing import Dict, Any, List, Union
from dotenv import load_dotenv
from fastmcp import FastMCP, Context  # ✅ FastMCP 2.x import
from utils.config import load_config

# Load environment variables from .env file such as API keys and secrets
load_dotenv()

# Load the config.yaml which contains path folder settings. NOTE: OS specific yaml files will override default config.yaml
config = load_config()
msgraph_config = config.get('msgraph', {})
artifacts_base = config['artifacts']['artifacts_path']

MSGRAPH_TENANT_ID = os.getenv("MSGRAPH_TENANT_ID")
MSGRAPH_CLIENT_ID = os.getenv("MSGRAPH_CLIENT_ID")
MSGRAPH_CLIENT_SECRET = os.getenv("MSGRAPH_CLIENT_SECRET")
MSGRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

# Microsoft Teams specific IDs (TODO: Load these from teams.json, users can add multiple teams/channels)
MSGRAPH_TEAM_ID = os.getenv("MSGRAPH_TEAM_ID")
MSGRAPH_CHANNEL_ID = os.getenv("MSGRAPH_CHANNEL_ID")

# ===============================================
# Helper Functions
# ===============================================
def get_headers(extra: dict = None):
    # Basic Auth header Microsoft Graph expects
    auth = base64.b64encode(f"{MSGRAPH_CLIENT_ID}:{MSGRAPH_CLIENT_SECRET}".encode()).decode()
    h = {
        "Authorization": f"Basic {auth}",
    }
    if extra:
        h.update(extra)
    return h

# ===============================================
# Microsoft Graph API Functions
# ===============================================
async def teams_notify_test_start(test_run_id: str, message: str, ctx: Context) -> str:
    """
    Send a Teams message announcing that a performance test has started.
    """
    url = f"{MSGRAPH_API_BASE}/teams/{MSGRAPH_TEAM_ID}/channels/{MSGRAPH_CHANNEL_ID}/messages"
    headers = get_headers()
    data = {
        "body": {
            "content": message
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        return response.json()

async def teams_notify_test_complete(test_run_id: str, message: str, ctx: Context) -> str:
    """
    Send a Teams message announcing that a performance test has completed.
    """
    url = f"{MSGRAPH_API_BASE}/teams/{MSGRAPH_TEAM_ID}/channels/{MSGRAPH_CHANNEL_ID}/messages"
    headers = get_headers()
    data = {
        "body": {
            "content": message
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        return response.json()

async def teams_notify_test_failure(test_run_id: str, message: str, ctx: Context) -> str:
    """
    Send a Teams message announcing that a performance test has failed.
    """
    url = f"{MSGRAPH_API_BASE}/teams/{MSGRAPH_TEAM_ID}/channels/{MSGRAPH_CHANNEL_ID}/messages"
    headers = get_headers()
    data = {
        "body": {
            "content": message
        }
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        return response.json()
