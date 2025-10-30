# Confluence API client
from fastmcp import FastMCP, Context
from services.confluence_api_v1 import (
    list_spaces_v1, 
    get_space_details_v1,
    list_pages_v1, 
    create_page_v1, 
    attach_file_v1,
)
from services.confluence_api_v2 import (
    list_spaces_v2, 
    get_space_details_v2,
    list_pages_v2,
    create_page_v2,
    attach_file_v2,
)
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
        List[dict]: Page summaries with keys:
            - 'page_ref': Opaque unique value (usually page_id).
            - 'title': Page title.
            - 'url': Confluence page URL.
            - 'status': Page status (if available).
    """
    if mode == "cloud":
        return await list_pages_v2(space_ref, ctx)
    return await list_pages_v1(space_ref, ctx)

@mcp.tool()
async def get_page_by_id(page_ref: str, mode: str, ctx: Context) -> dict:
    """
    Retrieves metadata for a specific Confluence page, including its title, parent, links, and status.

    Args:
        page_ref (str): Unique page reference or ID, as returned by list_pages or create_page.
        mode (str): "cloud" (Confluence v2 API) or "onprem" (Confluence v1 API).
        ctx (Context): FastMCP context for chaining and error/status handling.

    Returns:
        dict: Page metadata, containing:
            - 'page_ref'
            - 'title'
            - 'url'
            - 'status'
            - 'parent_ref' (if available)
            - 'space_ref'
            - Additional API-provided fields
    """
    #if mode == "cloud":
    #    return await get_page_by_id_v2(page_ref, ctx)
    #return await get_page_by_id_v1(page_ref, ctx)

@mcp.tool()
async def get_page_contents(page_ref: str, mode: str, ctx: Context) -> dict:
    """
    Retrieves the full contents of a Confluence page in XHTML storage format.

    Args:
        page_ref (str): Reference/ID for the target Confluence page.
        mode (str): "cloud" for v2 API, "onprem" for v1 API.
        ctx (Context): FastMCP context for workflow sequencing or error messaging.

    Returns:
        dict: Page contents, including:
            - 'page_ref'
            - 'storage_xhtml' (XHTML markup of page body)
            - 'title'
            - 'status'
            - Additional content fields (labels, attachments if included)
    """
    #if mode == "cloud":
    #    return await get_page_contents_v2(page_ref, ctx)
    #return await get_page_contents_v1(page_ref, ctx)

@mcp.tool
async def create_page(space_ref: str, filename: str, mode: str, ctx: Context) -> dict:
    """
    Creates a new Confluence page by importing a Markdown performance report.

    Args:
        space_ref (str): Space reference to create the page under, from list_spaces.
        filename (str): Markdown report filename, as returned by list_available_reports.
        mode (str): "cloud" or "onprem".
        ctx (Context): FastMCP context for error/status reporting.

    Returns:
        Dict with:
            - 'page_ref': Created page reference.
            - 'url': New page URL.
            - 'title': Extracted or default title.
            - 'status': Result status ("created" or "error").
    """
    # Load markdown and convert
    xhtml = await markdown_to_confluence_xhtml(filename)
    if mode == "cloud":
        return await create_page_v2(space_ref, filename, xhtml, ctx)
    return await create_page_v1(space_ref, filename, xhtml, ctx)

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
    if mode == "cloud":
        return await attach_file_v2(page_ref, filename, ctx)
    return await attach_file_v1(page_ref, filename, ctx)

@mcp.tool()
async def list_available_reports(mode: str, run_id: str = None, ctx: Context = None) -> list:
    """
    Lists available Markdown report files that can be published to Confluence.

    Args:
        mode (str): "cloud" or "onprem" (for future proofing).
        run_id (str, optional): If provided, filters for single test run reports.
            - If omitted, lists comparison reports from 'comparisons/'.
        ctx (Context, optional): FastMCP context for caching or downstream use.

    Returns:
        List[dict]: Report file summaries with keys:
            - 'filename': Exact file name to use with create_page.
            - 'display_name': Suggested title (if parseable), else file name.
            - 'report_type': "single" or "comparison".
            - 'test_run_ids': List of involved test run IDs.
    """
    #from services.report_discovery import list_markdown_reports

    #return await list_markdown_reports(mode, run_id, ctx)

@mcp.tool()
async def list_available_charts(mode: str, run_id: str = None, ctx: Context = None) -> list:
    """
    Lists available PNG chart images for attachment to Confluence reports.

    Args:
        mode (str): "cloud" or "onprem".
        run_id (str, optional): If provided, limits to charts generated for single run.
            - If omitted, lists comparison/charts from "comparisons/" folder.
        ctx (Context, optional): FastMCP context for caching/chart reuse.

    Returns:
        List[dict]: Chart files with keys:
            - 'filename': PNG file name (for attach_file tool).
            - 'description': Parsed from file name or default label.
            - 'chart_type': e.g., "bar", "line", "comparison".
    """
    #from services.report_discovery import list_chart_files

    #return await list_chart_files(mode, run_id, ctx)

@mcp.tool
async def convert_markdown_to_confluence_xhtml(markdown_path: str):
    """
    Converts a Markdown report file (from PerfReport MCP output) to Confluence-compatible XHTML storage format.

    Args:
        markdown_path (str): Path to local Markdown report file.

    Returns:
        str: String containing processed XHTML, suitable for page creation or update.
    """
    return await markdown_to_confluence_xhtml(markdown_path)

# -----------------------------
# Confluence MCP entry point
# -----------------------------
if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down Confluence MCP...")

