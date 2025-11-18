# JMeter MCP Server Script Generator
# This module generates JMeter JMX files based on network capture JSON files.
from fastmcp import FastMCP, Context  # ✅ FastMCP 2.x import
from typing import Optional, Dict, Any

mcp = FastMCP(
    name="jmeter-mcp",
)

from services.spec_parser import list_test_specs, load_browser_steps
from services.network_capture import capture_traffic, analyze_traffic
from services.script_generator import generate_jmeter_jmx, validate_jmeter_script
from services.jmeter_runner import run_jmeter_test, stop_running_test, summarize_test_run
from services.report_aggregator import aggregate_kpi_report

# ----------------------------------------------------------
# Browser Automation Helper Tools
# ----------------------------------------------------------

@mcp.tool(enabled=False)
async def get_test_specs(test_run_id: str, ctx: Context) -> dict:
    """
    Discovers available Markdown browser automation specs in the 'test-specs/' directory.
    Args:
        test_run_id (str): Unique identifier for the test run.
        ctx (Context, optional): FastMCP context for state/error details.

    Returns: dict of spec file names and metadata.
    """
    return await list_test_specs(test_run_id, ctx)

@mcp.tool(enabled=False)
async def get_browser_steps(test_run_id: str, filename: str, ctx: Context) -> dict:
    """
    Loads a given Markdown file containing browser automation test steps (supports 'Steps' and 'Test Cases / Test Steps').
    Args:
        test_run_id (str): Unique identifier for the test run.
        filename (str): Relative path to a test-specs Markdown file.
        ctx (Context, optional): FastMCP context for state/error details.
    
    Returns: dict of loaded steps, structure format, and validation info.
    """
    return await load_browser_steps(test_run_id, filename, ctx)

@mcp.tool(enabled=False)
async def capture_network_traffic(test_run_id: str, output_format: str, ctx: Context) -> dict:
    """
    Runs and captures backend network traffic. Outputs to HAR or extended JSON format.
    Args:
        test_run_id (str): Unique identifier for the test run.
        output_format (str): 'har' or 'json'
        ctx (Context, optional): FastMCP context for state/error details.
    
    Returns: dict with artifact path(s), status, and any errors.
    """
    return await capture_traffic(test_run_id, output_format, ctx)

@mcp.tool(enabled=False)
async def analyze_network_traffic(test_run_id: str, ctx: Context) -> dict:
    """
    Analyzes network traffic data, extracting test request metadata/stats.
    Args:
        test_run_id (str): Unique identifier for the test run.
        ctx (Context, optional): FastMCP context for state/error details.
        
    Returns: dict with extracted stats, request/response mappings, discovered correlations.
    """
    return await analyze_traffic(test_run_id, ctx)

# ----------------------------------------------------------
# JMeter JMX Generation and Test Execution Tools
# ----------------------------------------------------------

@mcp.tool(enabled=False)
async def generate_jmeter_script(test_run_id: str, json_path: str, ctx: Context) -> dict:
    """
    Generate a JMeter JMX script from the structured JSON or HAR output.
    Args:
        test_run_id (str): Unique identifier for the test run.
        json_path (str): Path to the JSON (network capture, steps, etc.)
        ctx (Context, optional): Optional FastMCP workflow context for state/error details.
    
    Returns:
        dict: Includes output JMX path, mapping info, warnings, and errors (if any).
    """
    return await generate_jmeter_jmx(test_run_id, json_path, ctx)

@mcp.tool(enabled=False)
async def validate_jmx(test_run_id: str, jmx_path: str, ctx: Context) -> dict:
    """
    Validates JMX script structure and variable references.
    Args:
        test_run_id (str): Unique identifier for the test run.
        jmx_path (str): Path to the JMX script that should be validated.
        ctx (Context, optional): FastMCP context for tracking state, status, or error reporting.
    
    Returns:
        dict: Validation results, including errors, warnings, and status.
    """
    return await validate_jmeter_script(test_run_id, jmx_path, ctx)

@mcp.tool()
async def start_jmeter_test(test_run_id: str, jmx_path: str, ctx: Context) -> dict:
    """
    Execute the JMeter test plan using the given JMX and config, returning summary info and artifacts.
    Args:
        test_run_id (str): Unique identifier for the test run.
        jmx_path (str): Path to the JMX script that should be executed.
        ctx (Context, optional): FastMCP context for tracking state, status, or error reporting.
    
    Returns:
        dict: Test results, artifact paths, timings, and status.
    """
    return await run_jmeter_test(test_run_id, jmx_path, ctx)

@mcp.tool()
async def stop_jmeter_test(test_run_id: str, ctx: Context) -> dict:
    """
    Gracefully stops a running JMeter test session identified by run_id.
    Args:
        test_run_id (str): JMeter/runner session identifier.
        ctx (Context, optional): FastMCP context object.
    
    Returns:
        dict: Stop status, error (if any), and timestamps.
    """
    return await stop_running_test(test_run_id, ctx)

@mcp.tool(enabled=False)
async def get_jmeter_run_summary(test_run_id: str, ctx: Context) -> dict:
    """
    Analyzes the test run results and provides high-level summary.
    Args:
        test_run_id (str): Unique identifier for the test run.
        ctx (Context, optional): FastMCP context for tracking state, status, or error reporting.
    Returns:
        dict: Summary of test run results, KPIs, and any errors/warnings.
    """
    return await summarize_test_run(test_run_id, ctx)

@mcp.tool(enabled=False)
async def generate_aggregate_report(test_run_id: str, ctx: Context) -> dict:
    """
    Parses JMeter JTL results to produce KPI summaries.
    Args:
        test_run_id (str): Unique identifier for the test run.
        ctx (Context, optional): FastMCP context for tracking state, status, or error reporting.
    Returns:
        dict: Aggregate KPI report data, charts, and any errors/warnings.
    """
    return await aggregate_kpi_report(test_run_id, ctx)