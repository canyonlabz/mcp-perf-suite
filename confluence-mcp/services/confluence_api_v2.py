# Confluence v2 APIs (Cloud)
import os
import json
import httpx
import base64
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
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=get_headers({"Accept": "application/json"}))
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
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=get_headers({"Accept": "application/json"}))
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

async def list_pages_v2(space_ref: str, ctx: Context) -> list:
    """
    Lists all pages in a specific Confluence Cloud space.
    
    Args:
        space_ref (str): Space ID for Cloud (v2).
        ctx (Context): FastMCP invocation context.
    
    Returns:
        List of pages with 'page_ref', 'title', 'status', 'url', 'parent_id', and version info.
    """
    base_url = CONFLUENCE_V2_BASE_URL
    url = f"{base_url}/wiki/api/v2/spaces/{space_ref}/pages"
    headers = get_headers({"Accept": "application/json"})
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        data = response.json()
    
    pages = []
    for item in data["results"]:
        pages.append({
            "page_ref": item.get("id"),
            "title": item.get("title"),
            "status": item.get("status"),
            "parent_id": item.get("parentId"),
            "space_id": item.get("spaceId"),
            "version": item.get("version", {}).get("number"),
            "created_at": item.get("createdAt"),
            "url": base_url + item.get("_links", {}).get("webui", ""),
        })
    
    await ctx.info(f"Fetched {len(pages)} pages from space {space_ref} (v2).")
    return pages

async def get_page_by_id_v2(page_ref: str, ctx: Context) -> dict:
    """
    Retrieves metadata for a specific page by ID in Confluence Cloud.
    
    Args:
        page_ref (str): Page ID.
        ctx (Context): FastMCP invocation context.
    
    Returns:
        dict: Page metadata including id, title, status, parent info, space info, version, timestamps, and URLs.
    """
    base_url = CONFLUENCE_V2_BASE_URL
    url = f"{base_url}/wiki/api/v2/pages/{page_ref}"
    headers = get_headers({"Accept": "application/json"})
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        item = response.json()
    
    page_data = {
        "page_ref": item.get("id"),
        "title": item.get("title"),
        "status": item.get("status"),
        "parent_type": item.get("parentType"),
        "parent_id": item.get("parentId"),
        "space_id": item.get("spaceId"),
        "owner_id": item.get("ownerId"),
        "author_id": item.get("authorId"),
        "version": item.get("version", {}).get("number"),
        "version_message": item.get("version", {}).get("message"),
        "version_created_at": item.get("version", {}).get("createdAt"),
        "created_at": item.get("createdAt"),
        "position": item.get("position"),
        "url": item.get("_links", {}).get("base", "") + item.get("_links", {}).get("webui", ""),
    }
    
    await ctx.info(f"Fetched metadata for page {page_ref} (v2).")
    return page_data

async def get_page_content_v2(page_ref: str, ctx: Context) -> dict:
    """
    Retrieves the full content body of a Confluence Cloud page in storage format (XHTML).
    
    Args:
        page_ref (str): Page ID.
        ctx (Context): FastMCP invocation context.
    
    Returns:
        dict: Page content including:
            - page_ref: Page ID
            - title: Page title
            - storage_xhtml: Full XHTML content in Confluence storage format
            - status: Page status
            - url: Page URL
    """
    base_url = CONFLUENCE_V2_BASE_URL
    url = f"{base_url}/wiki/api/v2/pages/{page_ref}"
    params = {"body-format": "storage"}
    headers = get_headers({"Accept": "application/json"})
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        item = response.json()
    
    content_data = {
        "page_ref": item.get("id"),
        "title": item.get("title"),
        "status": item.get("status"),
        "storage_xhtml": item.get("body", {}).get("storage", {}).get("value", ""),
        "representation": item.get("body", {}).get("storage", {}).get("representation"),
        "url": item.get("_links", {}).get("base", "") + item.get("_links", {}).get("webui", ""),
    }
    
    await ctx.info(f"Fetched content for page {page_ref} (v2). Content size: {len(content_data['storage_xhtml'])} chars.")
    return content_data

async def create_page_v2(space_ref: str, title: str, storage_xhtml: str, ctx: Context, parent_id: str = None) -> dict:
    """
    Creates a new Confluence page in Cloud instance.
    
    Args:
        space_ref (str): Space ID for Cloud (v2).
        title (str): Page title.
        storage_xhtml (str): Page content in Confluence storage format (XHTML).
        ctx (Context): FastMCP invocation context.
        parent_id (str, optional): Parent page ID to nest this page under.
    
    Returns:
        dict: Created page details including:
            - page_ref: Created page ID
            - title: Page title
            - url: Page URL
            - status: Result status ("created" or "error")
    """
    base_url = CONFLUENCE_V2_BASE_URL
    url = f"{base_url}/wiki/api/v2/pages"
    headers = get_headers({"Content-Type": "application/json", "Accept": "application/json"})
    
    # Build request payload
    payload = {
        "spaceId": space_ref,
        "status": "current",
        "title": title,
        "body": {
            "representation": "storage",
            "value": storage_xhtml
        }
    }
    
    # Add parent if specified
    if parent_id:
        payload["parentId"] = parent_id
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
        
        page_data = {
            "page_ref": result.get("id"),
            "title": result.get("title"),
            "url": result.get("_links", {}).get("base", "") + result.get("_links", {}).get("webui", ""),
            "status": "created"
        }
        
        await ctx.info(f"Successfully created page '{title}' in space {space_ref} (v2).")
        return page_data
        
    except httpx.HTTPStatusError as e:
        error_msg = f"Failed to create page: {e.response.status_code} - {e.response.text}"
        await ctx.error(error_msg)
        return {"error": error_msg, "status": "error"}
    except Exception as e:
        error_msg = f"Failed to create page: {str(e)}"
        await ctx.error(error_msg)
        return {"error": error_msg, "status": "error"}

async def search_content_v2(query: str, space_key: str = None, ctx: Context = None) -> list:
    """
    Search Confluence Cloud content using CQL (v1 API endpoint).
    Note: Cloud uses the v1 /wiki/rest/api/search endpoint for CQL queries.
    
    Args:
        query (str): Search query (will be used in title and text search).
        space_key (str, optional): Limit search to specific space key.
        ctx (Context): FastMCP context.
    
    Returns:
        List of matching pages with title, id, url, space, and excerpt.
    """
    base_url = CONFLUENCE_V2_BASE_URL
    
    # Build CQL query
    cql_parts = [f'type=page AND (title~"{query}" OR text~"{query}")']
    if space_key:
        cql_parts.append(f'space={space_key}')
    
    cql = " AND ".join(cql_parts)
    
    # Use v1 search endpoint (CQL not available in v2)
    url = f"{base_url}/wiki/rest/api/search"
    params = {"cql": cql, "limit": 50}
    headers = get_headers({"Accept": "application/json"})
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        data = response.json()
    
    results = []
    for item in data.get("results", []):
        results.append({
            "page_ref": item.get("content", {}).get("id") or item.get("id"),
            "title": item.get("title"),
            "type": item.get("content", {}).get("type") or item.get("type"),
            "space_key": item.get("space", {}).get("key"),
            "space_name": item.get("space", {}).get("name"),
            "url": item.get("url", ""),
            "excerpt": item.get("excerpt", ""),
            "last_modified": item.get("lastModified", ""),
        })
    
    if ctx:
        await ctx.info(f"Found {len(results)} results for query: {query}")
    
    return results


# -----------------------------
# Helper functions
# -----------------------------

def get_headers(extra: dict = None):
    # Basic Auth header Confluence expects
    auth = base64.b64encode(f"{CONFLUENCE_V2_USER}:{CONFLUENCE_V2_API_TOKEN}".encode()).decode()
    h = {
        "Authorization": f"Basic {auth}",
    }
    if extra:
        h.update(extra)
    return h