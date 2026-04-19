"""
Microsoft Teams MCP Server

Tools:
  teams_login          — authenticate to MS Teams via browser-based SSO/manual login
  teams_status         — check authentication state and token health
  teams_list_channels  — list joined teams and their channels
  teams_send_message   — send a message to a Teams conversation
"""

import json
import logging
import sys
from fastmcp import FastMCP
from utils.config import load_config
from services import auth_manager, teams_api

config = load_config()
server_cfg = config.get("server", {})
general_cfg = config.get("general", {})

log_level = logging.DEBUG if general_cfg.get("enable_debug") else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("msteams-mcp")

mcp = FastMCP(name=server_cfg.get("name", "msteams-mcp"))


@mcp.tool()
async def teams_login(force: bool = False) -> str:
    """
    Authenticate to Microsoft Teams.

    Attempts SSO first (cached session), then headless browser refresh,
    then interactive browser login as a last resort.

    Args:
        force: Skip cached tokens and force a fresh browser login.

    Returns:
        JSON status with authentication result and user info.
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
async def teams_status() -> str:
    """
    Check the current authentication and session health.

    Returns token validity, session age, user info, and diagnostics.
    No network calls — reads from local cache only.

    Returns:
        JSON diagnostic snapshot of auth state.
    """
    status = auth_manager.get_status()
    return json.dumps(status, indent=2, default=str)


@mcp.tool()
async def teams_list_channels() -> str:
    """
    List all Teams and channels the authenticated user has access to.

    Returns a JSON array of teams, each containing their channels with IDs.
    Use the channel ID as conversation_id in teams_send_message.
    Call teams_login first if not yet authenticated.

    Returns:
        JSON array of teams with nested channel lists.
    """
    result = await teams_api.get_my_teams_and_channels()
    if not result.ok:
        return json.dumps({
            "status": "error",
            "code": result.error.code.value,
            "message": result.error.message,
            "suggestions": result.error.suggestions,
        }, indent=2)

    return json.dumps(result.value, indent=2)


@mcp.tool()
async def teams_send_message(
    conversation_id: str,
    message: str,
    content_type: str = "text",
    reply_to_message_id: str = "",
) -> str:
    """
    Send a message to a Microsoft Teams conversation (channel, chat, or group).

    Args:
        conversation_id: The conversation/channel ID (from teams_list_channels).
                         Channels look like "19:xxx@thread.tacv2".
        message: The message content to send.
        content_type: "text" for plain text, "html" for rich HTML content.
        reply_to_message_id: Optional. For channel thread replies, the root message ID.

    Returns:
        JSON result with send status and message ID.
    """
    result = await teams_api.send_message(
        conversation_id=conversation_id,
        content=message,
        content_type=content_type,
        reply_to_message_id=reply_to_message_id or None,
    )

    if result.ok:
        return json.dumps({
            "status": "sent",
            "message": "Message delivered successfully",
            "details": result.value,
        }, indent=2)

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
        print("Shutting down MS Teams MCP…")
