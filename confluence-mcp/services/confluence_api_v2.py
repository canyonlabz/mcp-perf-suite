# Confluence v2 APIs (Cloud)
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

# --- Cloud (v2) ---
CONFLUENCE_V2_BASE_URL = os.getenv("CONFLUENCE_V2_BASE_URL")
CONFLUENCE_V2_USER = os.getenv("CONFLUENCE_V2_USER")
CONFLUENCE_V2_API_TOKEN = os.getenv("CONFLUENCE_V2_API_TOKEN")

# -----------------------------
# Confluence v2 API functions
# -----------------------------
async def list_spaces_v2(ctx: Context) -> list:
    """
    Lists all spaces in the Confluence Cloud instance.
    Args:
        ctx (Context): FastMCP invocation context.
    Returns:
        List of spaces with 'space_ref', 'key', 'name', 'type', 'status', and 'url'.
    """
    base_url = CONFLUENCE_V2_BASE_URL
    api_key = CONFLUENCE_V2_API_TOKEN
    url = f"{base_url}/wiki/api/v2/spaces"
    headers = {"Authorization": f"Basic {api_key}", "Accept": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        data = response.json()
    spaces = []
    for item in data["results"]:
        spaces.append({
            "space_ref": item.get("id"),
            "key": item.get("key"),
            "name": item.get("name"),
            "type": item.get("type", "global"),
            "status": item.get("status"),
            "url": f"{base_url}/spaces/{item.get('key')}",
        })
    await ctx.info(f"Fetched {len(spaces)} spaces from Confluence cloud.")
    return spaces

async def get_space_details_v2(space_ref: str, ctx: Context) -> dict:
    """
    Retrieves metadata and configuration details for a specific Confluence Cloud space.
    Args:
        space_ref (str): The space ID identifier.
        ctx (Context): FastMCP context for workflow chaining and error reporting.
    Returns:
        dict: Space metadata including 'space_ref', 'key', 'name', 'type', 'description', 'status', and additional metadata.
    """
    base_url = CONFLUENCE_V2_BASE_URL
    api_token = CONFLUENCE_V2_API_TOKEN
    url = f"{base_url}/wiki/api/v2/spaces/{space_ref}"
    headers = {"Authorization": f"Basic {api_token}", "Accept": "application/json"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        item = response.json()
    details = {
        "space_ref": item.get("id"),
        "key": item.get("key"),
        "name": item.get("name"),
        "type": item.get("type"),
        "status": item.get("status"),
        "description": item.get("description", {}).get("plain", ""),  # sometimes empty dict
        "owner_id": item.get("spaceOwnerId"),
        "created_at": item.get("createdAt"),
        "homepage_id": item.get("homepageId"),
        "web_url": item.get("_links", {}).get("base", "") + item.get("_links", {}).get("webui", ""),
    }
    await ctx.info(f"Fetched details for space {space_ref} (v2).")
    return details