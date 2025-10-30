# Confluence v1 APIs (On-Prem)
import os
import json
import httpx
from fastmcp import Context
from dotenv import load_dotenv
from utils.config import load_config

# Load environment variables from .env file such as API keys and secrets
load_dotenv()

# Load the config.yaml which contains path folder settings. NOTE: OS specific yaml files will override default config.yaml
config = load_config()
cnf_config = config.get('confluence', {})
artifacts_base = config['artifacts']['artifacts_path']

# --- On‑Prem (v1) ---
CONFLUENCE_V1_BASE_URL = os.getenv("CONFLUENCE_V1_BASE_URL")
CONFLUENCE_V1_PAT = os.getenv("CONFLUENCE_V1_PAT")
CONFLUENCE_V1_USER = os.getenv("CONFLUENCE_V1_USER")

# -----------------------------
# Confluence v1 API functions
# -----------------------------
async def list_spaces_v1(ctx: Context) -> list:
    """
    Lists all spaces in the on-prem Confluence instance.
    Args:
        ctx (Context): FastMCP invocation context.
    Returns:
        List of spaces with 'space_ref', 'name', 'type', 'status', and 'url'.
    """
    # Load environment/config as needed
    base_url = CONFLUENCE_V1_BASE_URL
    api_token = CONFLUENCE_V1_PAT
    url = f"{base_url}/rest/api/space"
    headers = {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        data = response.json()
    spaces = []
    for item in data["results"]:
        spaces.append({
            "space_ref": item.get("key"),
            "name": item.get("name"),
            "type": item.get("type", "global"),
            "status": item.get("status"),
            "url": f"{base_url}/spaces/{item.get('key')}/overview",
        })
    await ctx.info(f"Fetched {len(spaces)} spaces from on-prem Confluence.")
    return spaces

async def get_space_details_v1(space_ref: str, ctx: Context) -> dict:
    """
    Retrieves metadata and configuration details for a specific on-prem Confluence space.
    Args:
        space_ref (str): The space key identifier.
        ctx (Context): FastMCP context for workflow chaining and error reporting.
    Returns:
        dict: Space metadata including 'space_ref', 'name', 'type', 'description', 'status', and additional metadata.
    """
    base_url = CONFLUENCE_V1_BASE_URL
    api_token = CONFLUENCE_V1_PAT
    url = f"{base_url}/rest/api/space/{space_ref}"
    headers = {"Authorization": f"Bearer {api_token}", "Accept": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        item = response.json()
    details = {
        "space_ref": item.get("key"),
        "id": item.get("id"),
        "name": item.get("name"),
        "type": item.get("type"),
        "status": item.get("status"),
        "description": item.get("_expandable", {}).get("description", ""),
        "creator": item.get("creator", {}).get("displayName"),
        "created_at": item.get("creationDate"),
        "last_modified_by": item.get("lastModifier", {}).get("displayName"),
        "last_modified_at": item.get("lastModificationDate"),
        "web_url": base_url + item.get("_links", {}).get("webui", ""),
        "homepage_id": item.get("_expandable", {}).get("homepage"),
    }
    await ctx.info(f"Fetched details for space {space_ref} (v1).")
    return details