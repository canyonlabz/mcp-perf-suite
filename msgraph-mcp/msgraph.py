# msgraph.py
from fastmcp import FastMCP, Context  # ✅ FastMCP 2.x import
from typing import Optional, Dict, Any
from utils.config import load_config

from services.msgraph_api import (
    teams_notify_test_start,
    teams_notify_test_complete,
)

mcp = FastMCP(
    name="msgraph",
)

@mcp.tool()
async def notify_test_start(test_run_id: str, message: str, ctx: Context) -> str:
    """
    Send a Teams message announcing that a performance test has started.

    Args:
        test_run_id: The unique test run identifier.
        message: The message to send to the Teams channel.
        ctx: The FastMCP context object.

    Returns:
        A string indicating that the message was sent successfully.
    """
    return await teams_notify_test_start(test_run_id, message, ctx)
