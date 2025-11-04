# Confluence API client
from fastmcp import FastMCP, Context
from services.confluence_api_v1 import (
    list_spaces_v1, 
    get_space_details_v1,
    list_pages_v1, 
    get_page_by_id_v1,
    get_page_content_v1,
    create_page_v1, 
    search_content_v1,
    #attach_file_v1,
)
from services.confluence_api_v2 import (
    list_spaces_v2, 
    get_space_details_v2,
    list_pages_v2,
    get_page_by_id_v2,
    get_page_content_v2,
    create_page_v2,
    search_content_v2,
    #attach_file_v2,
)
from services.artifact_manager import list_available_reports, list_available_charts
from services.content_parser import markdown_to_confluence_xhtml

mcp = FastMCP(name="confluence")

@mcp.tool
async def list_spaces(mode: str, ctx: Context) -> list:
    """
    Lists available Confluence spaces accessible in the given mode (cloud/onprem).

    Args:
        mode (str): Which Confluence API to use. Options:
            - "cloud": Use Confluence Cloud v2 API (uses 'space_id').
            - "onprem": Use on-premises Confluence v1 API (uses 'space_key').
        ctx (Context): FastMCP invocation context. Stores retrieved spaces for reuse.

    Returns:
        List[dict]: Spaces with keys:
            - 'space_ref': Use as space identifier in other tools (maps to either space_id or key based on mode).
            - 'name': Human-friendly display name.
            - 'type': Space type, if available.
    """
    if mode == "cloud":
        return await list_spaces_v2(ctx)
    return await list_spaces_v1(ctx)

@mcp.tool()
async def get_space_details(space_ref: str, mode: str, ctx: Context) -> dict:
    """
    Retrieves metadata and configuration details for a specific Confluence space.

    Args:
        space_ref (str): Identifier for the Confluence space (space_id for cloud or space_key for on-prem).
        mode (str): "cloud" (Confluence v2 API) or "onprem" (Confluence v1 API).
        ctx (Context): FastMCP context for workflow chaining and error reporting.

    Returns:
        dict: Space metadata, including:
            - 'space_ref' (ID or key)
            - 'name'
            - 'type'
            - 'description'
            - 'status'
            - Additional API-provided metadata (e.g., permissions, categories, homepage)
    """
    if mode == "cloud":
        return await get_space_details_v2(space_ref, ctx)
    return await get_space_details_v1(space_ref, ctx)

@mcp.tool
async def list_pages(space_ref: str, mode: str, ctx: Context) -> list:
    """
    Lists pages in a Confluence space. Use 'space_ref' output from list_spaces.

    Args:
        space_ref (str): Unique reference for the Confluence space (either space_id or space_key).
        mode (str): "cloud" for v2 API; "onprem" for v1 API.
        ctx (Context): FastMCP invocation context. Page list will be stored for further workflow steps.

    Returns:
        List of page metadata dicts with:
            - page_ref: Unique page identifier
            - title: Page title
            - status: Page status (current, archived, etc.)
            - url: Direct link to page
            - Additional fields depending on API version
    """
    if mode == "cloud":
        return await list_pages_v2(space_ref, ctx)
    else:
        return await list_pages_v1(space_ref, ctx)

@mcp.tool()
async def get_page_by_id(page_ref: str, mode: str, ctx: Context) -> dict:
    """
    Retrieves detailed metadata for a specific Confluence page by ID.
    
    Args:
        page_ref (str): Unique page identifier (page ID).
        mode (str): "cloud" (Confluence v2 API) or "onprem" (Confluence v1 API).
        ctx (Context): FastMCP invocation context for workflow chaining and logging.
    
    Returns:
        dict: Page metadata including:
            - page_ref: Page ID
            - title: Page title
            - status: Page status (current, archived, etc.)
            - version: Current version number
            - space information (key/name for v1, id for v2)
            - timestamps (created, last modified)
            - author/owner information
            - url: Direct link to page
    """
    if mode == "cloud":
        return await get_page_by_id_v2(page_ref, ctx)
    else:
        return await get_page_by_id_v1(page_ref, ctx)

@mcp.tool()
async def get_page_content(page_ref: str, mode: str, ctx: Context) -> dict:
    """
    Retrieves the full content body of a Confluence page in storage format (XHTML).
    
    This is useful for:
    - Reading existing page content before updates
    - Extracting specific sections or data
    - Backing up page content
    - Analyzing page structure
    
    Args:
        page_ref (str): Unique page identifier (page ID).
        mode (str): "cloud" (Confluence v2 API) or "onprem" (Confluence v1 API).
        ctx (Context): FastMCP invocation context for workflow chaining and logging.
    
    Returns:
        dict: Page content including:
            - page_ref: Page ID
            - title: Page title
            - status: Page status
            - storage_xhtml: Full page body content in Confluence storage format (XHTML)
            - representation: Content representation type (typically "storage")
            - url: Direct link to page
    """
    if mode == "cloud":
        return await get_page_content_v2(page_ref, ctx)
    else:
        return await get_page_content_v1(page_ref, ctx)

@mcp.tool
async def create_page(space_ref: str, test_run_id: str, filename: str, mode: str, ctx: Context, parent_id: str) -> dict:
    """
    Creates a new Confluence page by importing a Markdown performance report.
    
    Args:
        space_ref (str): Space identifier (space_id for cloud, space_key for on-prem) from list_spaces.
        test_run_id (str): ID of the test run (used for artifact path).
        filename (str): Markdown report filename, as returned by list_available_reports.
        mode (str): "cloud" or "onprem".
        ctx (Context): FastMCP context for error/status reporting.
        parent_id (str): Parent page ID to nest the new page under.
    
    Returns:
        dict with:
            - 'page_ref': Created page reference/ID.
            - 'url': New page URL.
            - 'title': Extracted title from markdown.
            - 'status': Result status ("created" or "error").
    """
    # Convert markdown to Confluence XHTML
    xhtml_result = await markdown_to_confluence_xhtml(test_run_id, filename, ctx)
    
    # Check if conversion failed
    if isinstance(xhtml_result, dict) and "error" in xhtml_result:
        return xhtml_result
    
    storage_xhtml = xhtml_result
    
    # Extract title from markdown file
    try:
        from pathlib import Path
        with open(filename, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            title = first_line.lstrip('#').strip() if first_line.startswith('#') else Path(filename).stem
    except Exception:
        title = Path(filename).stem
    
    # Create page using appropriate API
    if mode == "cloud":
        return await create_page_v2(space_ref, title, storage_xhtml, ctx, parent_id)
    else:
        return await create_page_v1(space_ref, title, storage_xhtml, ctx, parent_id)

@mcp.tool
async def attach_file(page_ref: str, filename: str, mode: str, ctx: Context) -> dict:
    """
    Attaches a PNG chart image to an existing Confluence report page.

    Args:
        page_ref (str): Unique reference for target page (from create_page or list_pages).
        filename (str): PNG image file name, from list_available_charts.
        mode (str): "cloud" or "onprem".
        ctx (Context): FastMCP context for chaining/error handling.

    Returns:
        Dict containing:
            - 'page_ref': Target page.
            - 'filename': Attached chart file.
            - 'attachment_url': Final URL for attachment.
            - 'status': Result status.
    """
    #if mode == "cloud":
    #    return await attach_file_v2(page_ref, filename, ctx)
    #return await attach_file_v1(page_ref, filename, ctx)

@mcp.tool()
async def get_available_reports(test_run_id: str = None, ctx: Context = None) -> list:
    """
    Lists available Markdown performance reports that can be published to Confluence.
    
    Args:
        test_run_id: Optional test run ID for single-run reports. If omitted, lists comparison reports.
        ctx: FastMCP context.
    
    Returns:
        List of report metadata dicts with filename, type, and test run IDs.
    """
    return await list_available_reports(test_run_id, ctx)

@mcp.tool()
async def get_available_charts(test_run_id: str = None, ctx: Context = None) -> list:
    """
    Lists available PNG chart images that can be attached to Confluence pages.
    
    Args:
        test_run_id: Optional test run ID for single-run charts. If omitted, lists comparison charts.
        ctx: FastMCP context.
    
    Returns:
        List of chart metadata dicts with filename, type, and description.
    """
    return await list_available_charts(test_run_id, ctx)

@mcp.tool
async def convert_markdown_to_xhtml(test_run_id: str, filename: str, ctx: Context = None) -> str:
    """
    Converts a Markdown performance report to Confluence storage-format XHTML.
    
    Args:
        test_run_id: ID of the test run (used for artifact path).
        filename: Filename of the markdown report. NOTE: full path is constructed internally. Get list from get_available_reports.
        ctx: FastMCP context for error/status reporting.
    
    Returns:
        str: Confluence-compatible XHTML markup, ready for page creation or update.
             Returns error dict if conversion fails.
    """
    return await markdown_to_confluence_xhtml(test_run_id, filename, ctx)

@mcp.tool()
async def search_pages(query: str, mode: str, ctx: Context, space_ref: str = None) -> list:
    """
    Searches for Confluence pages using CQL (Confluence Query Language).
    
    Both on-prem and cloud support powerful CQL queries for searching titles and content.
    
    Args:
        query (str): Search term or phrase (e.g., "performance test", "QA Testing Process").
        mode (str): "cloud" or "onprem".
        ctx (Context): FastMCP context.
        space_ref (str, optional): Limit search to specific space (space key for both v1 and cloud).
    
    Returns:
        List of matching pages with:
            - page_ref: Page ID
            - title: Page title
            - url: Page URL
            - space_key: Space key
            - space_name: Space name
            - excerpt: Search result preview
            - last_modified: Last modification date
    
    Examples:
        - search_pages("performance test", "cloud")
        - search_pages("QA Testing Process", "onprem", space_ref="NPQA")
    """
    if mode == "cloud":
        return await search_content_v2(query, space_ref, ctx)
    else:
        return await search_content_v1(query, space_ref, ctx)

# -----------------------------
# Confluence MCP entry point
# -----------------------------
if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down Confluence MCP...")

