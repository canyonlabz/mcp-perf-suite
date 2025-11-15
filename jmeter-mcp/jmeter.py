# JMeter MCP Server Script Generator
# This module generates JMeter JMX files based on network capture JSON files.
from fastmcp import FastMCP, Context  # ✅ FastMCP 2.x import
from typing import Optional, Dict, Any
from utils.config import load_config, load_jmeter_config
from services.script_generator import generate_jmeter_jmx

mcp = FastMCP(
    name="jmeter-mcp",
)

@mcp.tool()
async def generate_jmeter_script(context: Context, json_file: str, log_callback: Optional[callable] = None) -> str:
    """
    Generate a JMeter JMX file from a network capture JSON file.

    Args:
        context (Context): The FastMCP context object.
        json_file (str): Path to the network capture JSON file.
        log_callback (Optional[callable]): Optional logging callback function.

    Returns:
        str: Path to the generated JMeter JMX file.
    """
    if log_callback is None:
        log_callback = print

    jmx_file_path = generate_jmeter_jmx(json_file, log_callback)
    return jmx_file_path