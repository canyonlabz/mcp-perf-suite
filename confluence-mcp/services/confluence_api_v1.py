# Confluence v1 APIs (On-Prem)
import os
import json
import httpx
import base64
from typing import Union
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

# CA bundle path for SSL verification
CA_BUNDLE = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")

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
    url = f"{base_url}/rest/api/space"
    headers = get_headers({"Accept": "application/json"})
    verify_ssl = get_ssl_verify_setting()

    async with httpx.AsyncClient(verify=verify_ssl) as client:
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
    url = f"{base_url}/rest/api/space/{space_ref}"
    headers = get_headers({"Accept": "application/json"})
    verify_ssl = get_ssl_verify_setting()

    async with httpx.AsyncClient(verify=verify_ssl) as client:
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

async def list_pages_v1(space_ref: str, ctx: Context) -> list:
    """
    Lists all pages in a specific on-prem Confluence space.
    
    Args:
        space_ref (str): Space key for on-prem (v1).
        ctx (Context): FastMCP invocation context.
    
    Returns:
        List of pages with 'page_ref', 'title', 'status', 'url', and 'type'.
    """
    base_url = CONFLUENCE_V1_BASE_URL
    url = f"{base_url}/rest/api/content"
    params = {"spaceKey": space_ref, "type": "page"}
    headers = get_headers({"Accept": "application/json"})
    verify_ssl = get_ssl_verify_setting()
    
    async with httpx.AsyncClient(verify=verify_ssl) as client:
        response = await client.get(url, headers=headers, params=params)
        data = response.json()
    
    pages = []
    for item in data["results"]:
        pages.append({
            "page_ref": item.get("id"),
            "title": item.get("title"),
            "status": item.get("status"),
            "type": item.get("type"),
            "url": base_url + item.get("_links", {}).get("webui", ""),
        })
    
    await ctx.info(f"Fetched {len(pages)} pages from space {space_ref} (v1).")
    return pages

async def get_page_by_id_v1(page_ref: str, ctx: Context) -> dict:
    """
    Retrieves metadata for a specific page by ID in on-prem Confluence.
    
    Args:
        page_ref (str): Page ID.
        ctx (Context): FastMCP invocation context.
    
    Returns:
        dict: Page metadata including id, title, status, space info, version, history, and URLs.
    """
    base_url = CONFLUENCE_V1_BASE_URL
    url = f"{base_url}/rest/api/content/{page_ref}"
    headers = get_headers({"Accept": "application/json"})
    verify_ssl = get_ssl_verify_setting()
    
    async with httpx.AsyncClient(verify=verify_ssl) as client:
        response = await client.get(url, headers=headers)
        item = response.json()
    
    page_data = {
        "page_ref": item.get("id"),
        "title": item.get("title"),
        "type": item.get("type"),
        "status": item.get("status"),
        "space_key": item.get("space", {}).get("key"),
        "space_name": item.get("space", {}).get("name"),
        "version": item.get("version", {}).get("number"),
        "version_message": item.get("version", {}).get("message"),
        "last_modified_by": item.get("version", {}).get("by", {}).get("displayName"),
        "last_modified_at": item.get("version", {}).get("when"),
        "created_by": item.get("history", {}).get("createdBy", {}).get("displayName"),
        "created_at": item.get("history", {}).get("createdDate"),
        "url": base_url + item.get("_links", {}).get("webui", ""),
    }
    
    await ctx.info(f"Fetched metadata for page {page_ref} (v1).")
    return page_data

async def get_page_content_v1(page_ref: str, ctx: Context) -> dict:
    """
    Retrieves the full content body of a Confluence page in storage format (XHTML).
    
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
    base_url = CONFLUENCE_V1_BASE_URL
    url = f"{base_url}/rest/api/content/{page_ref}"
    params = {"expand": "body.storage"}
    headers = get_headers({"Accept": "application/json"})
    verify_ssl = get_ssl_verify_setting()
    
    async with httpx.AsyncClient(verify=verify_ssl) as client:
        response = await client.get(url, headers=headers, params=params)
        item = response.json()
    
    content_data = {
        "page_ref": item.get("id"),
        "title": item.get("title"),
        "status": item.get("status"),
        "storage_xhtml": item.get("body", {}).get("storage", {}).get("value", ""),
        "representation": item.get("body", {}).get("storage", {}).get("representation"),
        "url": base_url + item.get("_links", {}).get("webui", ""),
    }
    
    await ctx.info(f"Fetched content for page {page_ref} (v1). Content size: {len(content_data['storage_xhtml'])} chars.")
    return content_data

async def create_page_v1(space_ref: str, title: str, storage_xhtml: str, ctx: Context, parent_id: str = None) -> dict:
    """
    Creates a new Confluence page in on-prem instance.
    
    Args:
        space_ref (str): Space key for on-prem (v1).
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
    base_url = CONFLUENCE_V1_BASE_URL
    url = f"{base_url}/rest/api/content"
    headers = get_headers({"Content-Type": "application/json", "Accept": "application/json"})
    verify_ssl = get_ssl_verify_setting()
    
    # Build request payload
    payload = {
        "type": "page",
        "title": title,
        "space": {
            "key": space_ref
        },
        "body": {
            "storage": {
                "value": storage_xhtml,
                "representation": "storage"
            }
        }
    }
    
    # Add parent if specified
    if parent_id:
        payload["ancestors"] = [{"id": parent_id}]
    
    try:
        async with httpx.AsyncClient(verify=verify_ssl) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
        
        page_data = {
            "page_ref": result.get("id"),
            "title": result.get("title"),
            "url": base_url + result.get("_links", {}).get("webui", ""),
            "status": "created"
        }
        
        await ctx.info(f"Successfully created page '{title}' in space {space_ref} (v1).")
        return page_data
        
    except httpx.HTTPStatusError as e:
        error_msg = f"Failed to create page: {e.response.status_code} - {e.response.text}"
        await ctx.error(error_msg)
        return {"error": error_msg, "status": "error"}
    except Exception as e:
        error_msg = f"Failed to create page: {str(e)}"
        await ctx.error(error_msg)
        return {"error": error_msg, "status": "error"}

async def search_content_v1(query: str, space_key: str = None, ctx: Context = None) -> list:
    """
    Search Confluence content using CQL (v1 API for on-prem).
    
    Args:
        query (str): Search query (will be used in title and text search).
        space_key (str, optional): Limit search to specific space.
        ctx (Context): FastMCP context.
    
    Returns:
        List of matching pages with title, id, url, space, and excerpt.
    """
    base_url = CONFLUENCE_V1_BASE_URL
    
    # Build CQL query
    cql_parts = [f'type=page AND (title~"{query}" OR text~"{query}")']
    if space_key:
        cql_parts.append(f'space={space_key}')
    
    cql = " AND ".join(cql_parts)
    
    url = f"{base_url}/rest/api/content/search"
    params = {"cql": cql, "limit": 50}
    headers = get_headers({"Accept": "application/json"})
    verify_ssl = get_ssl_verify_setting()
    
    async with httpx.AsyncClient(verify=verify_ssl) as client:
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
            "url": item.get("url") or (base_url + item.get("content", {}).get("_links", {}).get("webui", "")),
            "excerpt": item.get("excerpt", ""),
            "last_modified": item.get("lastModified", ""),
        })
    
    if ctx:
        await ctx.info(f"Found {len(results)} results for query: {query}")
    
    return results


# -----------------------------
# Helper functions
# -----------------------------

def get_ssl_verify_setting() -> Union[str, bool]:
    """
    Determines SSL verification setting based on config.yaml.
    
    Returns:
        Union[str, bool]: 
            - Path to CA bundle (str) if ssl_verification is "ca_bundle" and certs are available
            - False if ssl_verification is "disabled"
            - True as fallback (use system certs)
    """
    ssl_verification = cnf_config.get('ssl_verification', 'ca_bundle').lower()
    
    if ssl_verification == 'disabled':
        return False
    elif ssl_verification == 'ca_bundle':
        # Use CA bundle if available, otherwise default to True
        return CA_BUNDLE or True
    else:
        # Default to system cert verification
        return True


def get_headers(extra: dict = None):
    """
    Generates authorization headers for Confluence on-prem (v1) API.
    Uses Bearer token authentication.
    
    Args:
        extra (dict, optional): Additional headers to include.
    
    Returns:
        dict: Headers dictionary with Authorization and any extra headers.
    """
    h = {
        "Authorization": f"Bearer {CONFLUENCE_V1_PAT}",
    }
    if extra:
        h.update(extra)
    return h