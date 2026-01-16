# Confluence API client
import re
from fastmcp import FastMCP, Context
from services.confluence_api_v1 import (
    list_spaces_v1, 
    get_space_details_v1,
    list_pages_v1, 
    get_page_by_id_v1,
    get_page_content_v1,
    create_page_v1, 
    search_content_v1,
    attach_file_v1,
)
from services.confluence_api_v2 import (
    list_spaces_v2, 
    get_space_details_v2,
    list_pages_v2,
    get_page_by_id_v2,
    get_page_content_v2,
    create_page_v2,
    search_content_v2,
    attach_file_v2,
)
from services.artifact_manager import list_available_reports, list_available_charts
from services.content_parser import markdown_to_confluence_xhtml

mcp = FastMCP(name="confluence")

# -----------------------------
# Validation Helper Functions
# -----------------------------

# Maximum title length for Confluence pages
MAX_TITLE_LENGTH = 255

# Allowed characters pattern for page titles:
# - Alphanumeric (a-z, A-Z, 0-9)
# - Whitespace
# - Underscores, dashes
# - Parentheses, square brackets
# - Commas, periods, colons, semi-colons
# - Hash (#), forward slash (/), percent (%), ampersand (&), apostrophe (')
ALLOWED_TITLE_PATTERN = re.compile(r"^[a-zA-Z0-9\s_\-\(\)\[\],.:;#/%&']+$")

def validate_page_title(title: str) -> dict:
    """
    Validates a Confluence page title for acceptable characters and length.
    
    Args:
        title (str): The title to validate.
    
    Returns:
        dict: Validation result with:
            - 'valid': True if title passes validation, False otherwise
            - 'error': Error message if validation failed, None otherwise
    """
    if not title or not title.strip():
        return {"valid": False, "error": "Title cannot be empty or whitespace only."}
    
    title = title.strip()
    
    # Check length
    if len(title) > MAX_TITLE_LENGTH:
        return {
            "valid": False,
            "error": f"Title exceeds maximum length of {MAX_TITLE_LENGTH} characters. "
                     f"Provided title is {len(title)} characters."
        }
    
    # Check for allowed characters
    if not ALLOWED_TITLE_PATTERN.match(title):
        # Find the invalid characters to provide helpful feedback
        invalid_chars = set()
        for char in title:
            if not re.match(r"[a-zA-Z0-9\s_\-\(\)\[\],.:;#/%&']", char):
                invalid_chars.add(repr(char))
        
        return {
            "valid": False,
            "error": f"Title contains invalid characters: {', '.join(sorted(invalid_chars))}. "
                     f"Allowed characters are: alphanumeric, whitespace, underscores, dashes, "
                     f"parentheses (), square brackets [], commas, periods, colons, semi-colons, "
                     f"hash (#), forward slash (/), percent (%), ampersand (&), and apostrophe (')."
        }
    
    return {"valid": True, "error": None}

# -----------------------------
# MCP Tool Definitions
# -----------------------------

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
async def create_page(space_ref: str, test_run_id: str, filename: str, mode: str, ctx: Context, parent_id: str, title: str = None) -> dict:
    """
    Creates a new Confluence page by importing a Markdown performance report.
    
    Args:
        space_ref (str): Space identifier (space_id for cloud, space_key for on-prem) from list_spaces.
        test_run_id (str): ID of the test run (used for artifact path).
                           Use "comparisons" for comparison reports stored in artifacts/comparisons/.
        filename (str): Markdown report filename, as returned by get_available_reports.
        mode (str): "cloud" or "onprem".
        ctx (Context): FastMCP context for error/status reporting.
        parent_id (str): Parent page ID to nest the new page under.
        title (str, optional): Custom page title. If not provided, title is extracted from 
            the markdown H1 heading, or falls back to the filename. Allowed characters:
            alphanumeric, whitespace, underscores, dashes, parentheses, square brackets,
            commas, periods, colons, semi-colons, hash, forward slash, percent, ampersand,
            and apostrophe. Maximum length: 255 characters.
    
    Returns:
        dict with:
            - 'page_ref': Created page reference/ID.
            - 'url': New page URL.
            - 'title': The title used for the page (user-provided or auto-extracted).
            - 'title_source': Indicates where the title came from ("user_provided", "markdown_h1", or "filename").
            - 'status': Result status ("created" or "error").
    
    Examples:
        # Single-run report
        create_page(space_ref="MYQA", test_run_id="80247571", 
                    filename="performance_report_80247571.md", mode="onprem", ...)
        
        # Comparison report
        create_page(space_ref="MYQA", test_run_id="comparisons", 
                    filename="comparison_report_run1_run2.md", mode="onprem", ...)
    """
    from pathlib import Path
    from utils.config import load_config
    
    # Load artifacts path from config
    config = load_config()
    artifacts_path = config['artifacts']['artifacts_path']
    
    # Construct full path to markdown file based on test_run_id
    if test_run_id == "comparisons":
        # Comparison reports are stored directly in comparisons folder
        markdown_file_path = Path(artifacts_path) / "comparisons" / filename
    else:
        # Single-run reports are in test_run_id/reports/ folder
        markdown_file_path = Path(artifacts_path) / test_run_id / "reports" / filename
    
    title_source = None
    
    # Determine title: user-provided or fallback to extraction
    if title and title.strip():
        # User provided a custom title - validate it
        validation = validate_page_title(title)
        if not validation["valid"]:
            await ctx.error(f"Title validation failed: {validation['error']}")
            return {
                "error": validation["error"],
                "status": "error",
                "title_provided": title
            }
        title = title.strip()
        title_source = "user_provided"
        await ctx.info(f"Using user-provided title: '{title}'")
    else:
        # Fall back to extracting title from markdown or filename
        try:
            with open(markdown_file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line.startswith('#'):
                    title = first_line.lstrip('#').strip()
                    title_source = "markdown_h1"
                else:
                    title = Path(filename).stem
                    title_source = "filename"
        except Exception:
            title = Path(filename).stem
            title_source = "filename"
        
        await ctx.info(f"Using auto-extracted title from {title_source}: '{title}'")
    
    # Convert markdown to Confluence XHTML
    xhtml_result = await markdown_to_confluence_xhtml(test_run_id, filename, ctx)
    
    # Check if conversion failed
    if isinstance(xhtml_result, dict) and "error" in xhtml_result:
        return xhtml_result
    
    storage_xhtml = xhtml_result
    
    # Create page using appropriate API
    if mode == "cloud":
        result = await create_page_v2(space_ref, title, storage_xhtml, ctx, parent_id)
    else:
        result = await create_page_v1(space_ref, title, storage_xhtml, ctx, parent_id)
    
    # Add title_source to the result for transparency
    if result.get("status") == "created":
        result["title_source"] = title_source
    
    return result

@mcp.tool
async def attach_images(page_ref: str, test_run_id: str, mode: str, ctx: Context) -> dict:
    """
    Attaches all PNG chart images from a test run to an existing Confluence page.
    
    Uploads all PNG files from artifacts/<test_run_id>/charts/ to the specified page.
    Continues on partial failures and reports which images succeeded/failed.
    
    Args:
        page_ref (str): Page ID to attach images to (from create_page or list_pages).
        test_run_id (str): Test run ID whose charts to upload.
        mode (str): "cloud" or "onprem".
        ctx (Context): FastMCP context for chaining/error handling.
    
    Returns:
        dict containing:
            - 'page_ref': Target page ID
            - 'test_run_id': Test run ID
            - 'attached': List of successfully attached images with details
            - 'failed': List of failed attachments with error details
            - 'total_attempted': Total number of files attempted
            - 'total_attached': Number of files successfully attached
            - 'status': "success" (all attached), "partial" (some failed), or "error" (all failed)
    
    Example:
        result = await attach_images(
            page_ref="123456789",
            test_run_id="80593110",
            mode="onprem",
            ctx=ctx
        )
        # Returns: {
        #     "page_ref": "123456789",
        #     "test_run_id": "80593110",
        #     "attached": [
        #         {"filename": "CPU_UTILIZATION_MULTILINE.png", "attachment_id": "...", ...},
        #         {"filename": "RESP_TIME_P90_VUSERS_DUALAXIS.png", "attachment_id": "...", ...}
        #     ],
        #     "failed": [],
        #     "total_attempted": 2,
        #     "total_attached": 2,
        #     "status": "success"
        # }
    """
    from pathlib import Path
    from utils.config import load_config
    
    # Load artifacts path from config
    config = load_config()
    artifacts_path = Path(config['artifacts']['artifacts_path'])
    
    # Construct path to charts folder
    charts_folder = artifacts_path / test_run_id / "charts"
    
    if not charts_folder.exists():
        error_msg = f"Charts folder not found: {charts_folder}"
        await ctx.error(error_msg)
        return {
            "error": error_msg,
            "page_ref": page_ref,
            "test_run_id": test_run_id,
            "status": "error"
        }
    
    # Find all PNG files in the charts folder
    png_files = list(charts_folder.glob("*.png"))
    
    if not png_files:
        error_msg = f"No PNG files found in: {charts_folder}"
        await ctx.warning(error_msg)
        return {
            "page_ref": page_ref,
            "test_run_id": test_run_id,
            "attached": [],
            "failed": [],
            "total_attempted": 0,
            "total_attached": 0,
            "status": "error",
            "message": error_msg
        }
    
    await ctx.info(f"Found {len(png_files)} PNG files to attach in {charts_folder}")
    
    # Select the appropriate attach function based on mode
    attach_func = attach_file_v2 if mode == "cloud" else attach_file_v1
    
    attached = []
    failed = []
    
    # Attach each file, continuing on errors
    for png_file in png_files:
        try:
            result = await attach_func(page_ref, str(png_file), ctx)
            
            if result.get("status") == "attached":
                attached.append(result)
            else:
                failed.append(result)
                
        except Exception as e:
            error_msg = f"Unexpected error attaching {png_file.name}: {str(e)}"
            await ctx.error(error_msg)
            failed.append({
                "filename": png_file.name,
                "error": error_msg,
                "status": "error"
            })
    
    # Determine overall status
    total_attempted = len(png_files)
    total_attached = len(attached)
    
    if total_attached == total_attempted:
        status = "success"
    elif total_attached > 0:
        status = "partial"
    else:
        status = "error"
    
    await ctx.info(f"Attachment complete: {total_attached}/{total_attempted} images attached to page {page_ref}")
    
    return {
        "page_ref": page_ref,
        "test_run_id": test_run_id,
        "attached": attached,
        "failed": failed,
        "total_attempted": total_attempted,
        "total_attached": total_attached,
        "status": status
    }

@mcp.tool()
async def get_available_reports(test_run_id: str = None, ctx: Context = None) -> list:
    """
    Lists available Markdown performance reports that can be published to Confluence.
    
    Args:
        test_run_id: Test run ID for single-run reports.
                     Use None or "comparisons" to list comparison reports.
        ctx: FastMCP context.
    
    Returns:
        List of report metadata dicts with filename, type, and test run IDs.
    
    Examples:
        # List single-run reports for a specific test
        get_available_reports(test_run_id="80247571")
        
        # List comparison reports (either approach works)
        get_available_reports()
        get_available_reports(test_run_id="comparisons")
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

