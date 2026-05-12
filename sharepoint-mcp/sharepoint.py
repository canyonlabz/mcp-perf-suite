"""
SharePoint MCP Server

Tools:
  sharepoint_login         — authenticate to SharePoint via browser-based SSO/manual login
  sharepoint_status        — check authentication state and token health
  sharepoint_upload_file   — upload a single file to a SharePoint document library
  sharepoint_upload_folder — upload an entire local folder (recursive) to SharePoint
  sharepoint_create_folder — create a folder in a SharePoint document library
  sharepoint_list_folder   — list contents of a SharePoint folder
"""

import json
import logging
import sys
from fastmcp import FastMCP
from utils.config import load_config
from services import (
    auth_manager,
    sharepoint_api,
    token_extractor,
)

config = load_config()
server_cfg = config.get("server", {})
general_cfg = config.get("general", {})

log_level = logging.DEBUG if general_cfg.get("enable_debug") else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("sharepoint-mcp")

mcp = FastMCP(name=server_cfg.get("name", "sharepoint-mcp"))


@mcp.tool()
async def sharepoint_login(force: bool = False) -> str:
    """
    Authenticate to SharePoint.

    Attempts SSO first (cached session), then headless browser refresh,
    then interactive browser login as a last resort. The tenant is
    auto-detected from the browser URL after login.

    Args:
        force: Skip cached tokens and force a fresh browser login.

    Returns:
        JSON status with authentication result, user info, and tenant.
    """
    result = await auth_manager.login(force=force)

    if result.ok:
        return json.dumps(result.value, indent=2)

    return json.dumps({
        "status": "error",
        "code": result.error.code.value,
        "message": result.error.message,
        "suggestions": result.error.suggestions,
    }, indent=2)


@mcp.tool()
async def sharepoint_status() -> str:
    """
    Check the current authentication and session health.

    Returns token validity, session age, tenant info, user info,
    and diagnostics. No network calls — reads from local cache only.

    Returns:
        JSON diagnostic snapshot of auth state.
    """
    status = auth_manager.get_status()
    return json.dumps(status, indent=2, default=str)


@mcp.tool()
async def sharepoint_upload_file(
    site_url: str,
    destination_folder: str,
    local_file_path: str,
) -> str:
    """
    Upload a single file to a SharePoint document library folder.

    Both site_url and destination_folder are required — there is no
    default upload location.

    Args:
        site_url: Full SharePoint site URL.
                  Example: "https://contoso.sharepoint.com/sites/PerfTesting"
        destination_folder: Server-relative folder path in the document library.
                           Example: "/sites/PerfTesting/Shared Documents/Results/2026-05-11"
        local_file_path: Absolute path to the local file to upload.
                        Example: "C:/artifacts/run-01/report.pdf"

    Returns:
        JSON with upload result (file name, SharePoint URL, size).
    """
    if not site_url or not site_url.strip():
        return json.dumps({
            "status": "warning",
            "message": "site_url is required. Provide the full SharePoint site URL "
                       "(e.g. https://contoso.sharepoint.com/sites/PerfTesting).",
            "suggestions": [
                "Call sharepoint_status to check if tenant is auto-detected",
                "Ask the user for their SharePoint site URL",
            ],
        }, indent=2)

    if not destination_folder or not destination_folder.strip():
        return json.dumps({
            "status": "warning",
            "message": "destination_folder is required. Provide the server-relative folder path "
                       "(e.g. /sites/PerfTesting/Shared Documents/Results).",
            "suggestions": [
                "Call sharepoint_list_folder to browse available folders",
                "Ask the user where they want to upload the file",
            ],
        }, indent=2)

    if not local_file_path or not local_file_path.strip():
        return json.dumps({
            "status": "warning",
            "message": "local_file_path is required. Provide the full path to the local file.",
        }, indent=2)

    result = await sharepoint_api.upload_file(
        site_url=site_url.strip(),
        destination_folder=destination_folder.strip(),
        local_file_path=local_file_path.strip(),
    )

    if result.ok:
        return json.dumps({
            "status": "uploaded",
            "message": f"File '{result.value['name']}' uploaded successfully",
            "details": result.value,
        }, indent=2)

    return json.dumps({
        "status": "error",
        "code": result.error.code.value,
        "message": result.error.message,
        "suggestions": result.error.suggestions,
    }, indent=2)


@mcp.tool()
async def sharepoint_upload_folder(
    site_url: str,
    destination_folder: str,
    local_folder_path: str,
) -> str:
    """
    Upload an entire local folder (recursive) to a SharePoint document library.

    All files in the local folder and its subfolders are uploaded,
    preserving the directory structure. Both site_url and
    destination_folder are required.

    Args:
        site_url: Full SharePoint site URL.
                  Example: "https://contoso.sharepoint.com/sites/PerfTesting"
        destination_folder: Server-relative folder path for the upload root.
                           Example: "/sites/PerfTesting/Shared Documents/Results/run-01"
        local_folder_path: Absolute path to the local folder to upload.
                          Example: "C:/artifacts/run-01"

    Returns:
        JSON with upload summary (files uploaded, total size, errors).
    """
    if not site_url or not site_url.strip():
        return json.dumps({
            "status": "warning",
            "message": "site_url is required. Provide the full SharePoint site URL "
                       "(e.g. https://contoso.sharepoint.com/sites/PerfTesting).",
            "suggestions": [
                "Call sharepoint_status to check if tenant is auto-detected",
                "Ask the user for their SharePoint site URL",
            ],
        }, indent=2)

    if not destination_folder or not destination_folder.strip():
        return json.dumps({
            "status": "warning",
            "message": "destination_folder is required. Provide the server-relative folder path "
                       "(e.g. /sites/PerfTesting/Shared Documents/Results/run-01).",
            "suggestions": [
                "Call sharepoint_list_folder to browse available folders",
                "Ask the user where they want to upload the folder",
            ],
        }, indent=2)

    if not local_folder_path or not local_folder_path.strip():
        return json.dumps({
            "status": "warning",
            "message": "local_folder_path is required. Provide the full path to the local folder.",
        }, indent=2)

    result = await sharepoint_api.upload_folder(
        site_url=site_url.strip(),
        destination_folder=destination_folder.strip(),
        local_folder_path=local_folder_path.strip(),
    )

    if result.ok:
        value = result.value
        msg = (
            f"Uploaded {value['filesUploaded']}/{value['filesTotal']} files "
            f"({value['totalSizeBytes'] / (1024*1024):.1f} MB) "
            f"to {value['destinationFolder']}"
        )
        if value.get("errors"):
            msg += f" ({len(value['errors'])} errors)"

        return json.dumps({
            "status": "completed" if not value.get("errors") else "completed_with_errors",
            "message": msg,
            "details": value,
        }, indent=2)

    return json.dumps({
        "status": "error",
        "code": result.error.code.value,
        "message": result.error.message,
        "suggestions": result.error.suggestions,
    }, indent=2)


@mcp.tool()
async def sharepoint_create_folder(
    site_url: str,
    folder_path: str,
) -> str:
    """
    Create a folder in a SharePoint document library.

    Creates the full folder path (including parent folders if needed).
    If the folder already exists, returns success without error.

    Args:
        site_url: Full SharePoint site URL.
                  Example: "https://contoso.sharepoint.com/sites/PerfTesting"
        folder_path: Server-relative folder path to create.
                    Example: "/sites/PerfTesting/Shared Documents/Results/2026-05-11"

    Returns:
        JSON with folder creation result.
    """
    if not site_url or not site_url.strip():
        return json.dumps({
            "status": "warning",
            "message": "site_url is required.",
        }, indent=2)

    if not folder_path or not folder_path.strip():
        return json.dumps({
            "status": "warning",
            "message": "folder_path is required.",
        }, indent=2)

    result = await sharepoint_api.create_folder(
        site_url=site_url.strip(),
        folder_path=folder_path.strip(),
    )

    if result.ok:
        value = result.value
        status = "already_exists" if value.get("alreadyExisted") else "created"
        return json.dumps({
            "status": status,
            "message": f"Folder '{value['name']}' {'already exists' if value.get('alreadyExisted') else 'created successfully'}",
            "details": value,
        }, indent=2)

    return json.dumps({
        "status": "error",
        "code": result.error.code.value,
        "message": result.error.message,
        "suggestions": result.error.suggestions,
    }, indent=2)


@mcp.tool()
async def sharepoint_list_folder(
    site_url: str,
    folder_path: str,
) -> str:
    """
    List contents of a SharePoint folder (files and subfolders).

    Returns files with name, URL, size, and last modified date.
    Returns subfolders with name, URL, and item count.

    Args:
        site_url: Full SharePoint site URL.
                  Example: "https://contoso.sharepoint.com/sites/PerfTesting"
        folder_path: Server-relative folder path to list.
                    Example: "/sites/PerfTesting/Shared Documents"

    Returns:
        JSON with files and folders arrays.
    """
    if not site_url or not site_url.strip():
        return json.dumps({
            "status": "warning",
            "message": "site_url is required.",
        }, indent=2)

    if not folder_path or not folder_path.strip():
        return json.dumps({
            "status": "warning",
            "message": "folder_path is required.",
        }, indent=2)

    result = await sharepoint_api.list_folder(
        site_url=site_url.strip(),
        folder_path=folder_path.strip(),
    )

    if result.ok:
        return json.dumps(result.value, indent=2)

    return json.dumps({
        "status": "error",
        "code": result.error.code.value,
        "message": result.error.message,
        "suggestions": result.error.suggestions,
    }, indent=2)


if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down SharePoint MCP…")
