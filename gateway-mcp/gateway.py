"""
PerfPilot Hub — MCP Gateway for Performance Testing

The central MCP gateway for the MCP Perf Suite. Gives AI agents a single
endpoint into the performance testing lifecycle, routing them to specialized
MCP servers via FastMCP v3's create_proxy() with subprocess isolation.

Each server runs in its own process with its own venv — no shared
dependencies, no import collisions.

Supports stdio (local Cursor) and http (future Docker/A2A) transports.
"""
import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server import create_proxy

from utils.config import load_config

REPO_ROOT = Path(__file__).resolve().parent.parent

config = load_config()
server_cfg = config.get("server", {})
servers_cfg = config.get("servers", {})

gateway = FastMCP(server_cfg.get("name", "perfpilot-hub"))


def _server_config(server_dir: str, script: str) -> dict:
    """Build an MCP server config dict that uses the server's own venv Python."""
    server_path = REPO_ROOT / server_dir
    venv_python = server_path / ".venv" / "Scripts" / "python.exe"

    if not venv_python.exists():
        venv_python = server_path / ".venv" / "bin" / "python"

    return {
        "mcpServers": {
            "default": {
                "command": str(venv_python),
                "args": [script],
                "cwd": str(server_path),
            }
        }
    }


# --- Core servers ---
if servers_cfg.get("jmeter", True):
    gateway.mount(
        create_proxy(_server_config("jmeter-mcp", "jmeter.py")),
        namespace="jmeter",
    )

if servers_cfg.get("blazemeter", True):
    gateway.mount(
        create_proxy(_server_config("blazemeter-mcp", "blazemeter.py")),
        namespace="blazemeter",
    )

if servers_cfg.get("datadog", True):
    gateway.mount(
        create_proxy(_server_config("datadog-mcp", "datadog.py")),
        namespace="datadog",
    )

if servers_cfg.get("perfanalysis", True):
    gateway.mount(
        create_proxy(_server_config("perfanalysis-mcp", "perfanalysis.py")),
        namespace="perfanalysis",
    )

if servers_cfg.get("perfreport", True):
    gateway.mount(
        create_proxy(_server_config("perfreport-mcp", "perfreport.py")),
        namespace="perfreport",
    )

if servers_cfg.get("confluence", True):
    gateway.mount(
        create_proxy(_server_config("confluence-mcp", "confluence.py")),
        namespace="confluence",
    )

if servers_cfg.get("perfmemory", True):
    gateway.mount(
        create_proxy(_server_config("perfmemory-mcp", "perfmemory.py")),
        namespace="perfmemory",
    )

# --- Local-only servers ---
if servers_cfg.get("msteams", True):
    gateway.mount(
        create_proxy(_server_config("msteams-mcp", "msteams.py")),
        namespace="msteams",
    )

if servers_cfg.get("sharepoint", True):
    gateway.mount(
        create_proxy(_server_config("sharepoint-mcp", "sharepoint.py")),
        namespace="sharepoint",
    )


if __name__ == "__main__":
    transport = os.environ.get(
        "GATEWAY_TRANSPORT", server_cfg.get("transport", "stdio")
    )

    if transport == "http":
        host = os.environ.get("GATEWAY_HOST", server_cfg.get("host", "0.0.0.0"))
        port = int(os.environ.get("GATEWAY_PORT", server_cfg.get("port", 8000)))
        gateway.run(transport="http", host=host, port=port)
    else:
        gateway.run(transport="stdio")
