# JMeter MCP Server Script Generator
# This module generates JMeter JMX files based on network capture JSON files.
from fastmcp import FastMCP, Context  # ✅ FastMCP 2.x import
from typing import Optional, Dict, Any

mcp = FastMCP(
    name="jmeter",
)

#from services.spec_parser import list_test_specs, load_browser_steps
#from services.network_capture import capture_traffic, analyze_traffic
from services.script_generator import generate_jmeter_jmx #validate_jmeter_script
from services.spec_parser import list_test_specs, load_browser_steps  # Load spec files and parse steps
from services.jmeter_runner import (
    run_jmeter_test, 
    stop_running_test,
    list_jmeter_scripts_for_run,
    get_jmeter_realtime_status, 
    generate_aggregate_report_csv,
    #summarize_test_run
)

from services.playwright_adapter import run_playwright_capture_pipeline
from services.playwright_adapter import archive_existing_traces
from services.correlations import analyze_traffic  # New modular package (v0.2.0)
from services.jmeter_log_analyzer import analyze_logs as run_jmeter_log_analysis

# Lazy import: HAR adapter is optional — server must start even if it fails to load (safeguard #1)
try:
    from services.har_adapter import convert_har_to_capture as _har_convert, validate_har_file as _har_validate
    _HAR_ADAPTER_AVAILABLE = True
except Exception:
    _HAR_ADAPTER_AVAILABLE = False

# ----------------------------------------------------------
# Browser Automation Helper Tools
# ----------------------------------------------------------

@mcp.tool()
async def archive_playwright_traces(ctx: Context, test_run_id: Optional[str] = None) -> dict:
    """
    Archives existing Playwright trace files before a new browser automation run.
    Moves the entire traces directory to a timestamped backup location.
    
    Args:
        ctx (Context): FastMCP context for state/error details.
        test_run_id (Optional[str]): Optional identifier for logging/context purposes.
    
    Returns:
        dict: {
            "status": "OK" | "NO_ACTION" | "ERROR",
            "message": str,
            "archived_path": str | None,
            "test_run_id": str | None
        }
    """
    _ = ctx  # reserved for future context usage
    try:
        archived_path = archive_existing_traces()
        
        if archived_path:
            return {
                "status": "OK",
                "message": f"Traces archived to: {archived_path}",
                "archived_path": archived_path,
                "test_run_id": test_run_id
            }
        else:
            return {
                "status": "NO_ACTION",
                "message": "No traces to archive (directory empty or doesn't exist)",
                "archived_path": None,
                "test_run_id": test_run_id
            }
    
    except PermissionError as e:
        return {
            "status": "ERROR",
            "message": f"Permission denied when archiving traces: {e}",
            "archived_path": None,
            "test_run_id": test_run_id
        }
    except OSError as e:
        return {
            "status": "ERROR",
            "message": f"OS error when archiving traces: {e}",
            "archived_path": None,
            "test_run_id": test_run_id
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "message": f"Unexpected error archiving traces: {e}",
            "archived_path": None,
            "test_run_id": test_run_id
        }

@mcp.tool()
async def get_test_specs(ctx: Context, test_run_id: Optional[str] = None) -> dict:
    """
    Discovers available Markdown browser automation specs in the 'test-specs/' directory.
    Args:
        test_run_id (Optional[str]): Unique identifier for the test run. If provided, also searches artifacts/<test_run_id>/test-specs/.
        ctx (Context, optional): FastMCP context for state/error details.

    Returns: dict of spec file names and metadata.
    """
    _ = ctx  # reserved for future context usage
    try:
        result = list_test_specs(test_run_id)
        return result
    except Exception as exc:
        return {
            "status": "ERROR",
            "message": str(exc),
            "count": 0,
            "specs": [],
            "roots_scanned": [],
        }

@mcp.tool()
async def get_browser_steps(test_run_id: str, filename: str, ctx: Context) -> list:
    """
    Loads a given Markdown file containing browser automation test steps (supports 'Steps' and 'Test Cases / Test Steps').
    Args:
        test_run_id (str): Unique identifier for the test run.
        filename (str): Relative path to a test-specs Markdown file.
        ctx (Context, optional): FastMCP context for state/error details.
    
    Returns: List of browser automation steps parsed from the spec file.
    """
    return load_browser_steps(test_run_id, filename, ctx)

@mcp.tool()
async def capture_network_traffic(test_run_id: str, spec_file: str, ctx: Context) -> dict:
    """
    Parses Playwright network traces and maps them to test steps from a spec file.
    
    This tool reads the latest Playwright trace from .playwright-mcp/traces/,
    correlates network requests with steps defined in the spec file, and outputs
    a structured JSON file for JMeter script generation.
    
    Args:
        test_run_id (str): Unique identifier for the test run (used for output path).
        spec_file (str): Full path to the spec file.
        ctx (Context, optional): FastMCP context for state/error details.
    
    Returns: dict with artifact path(s), status, and any errors.
    """
    try:
        output_path = run_playwright_capture_pipeline(spec_file, test_run_id)
        return {
            "status": "OK",
            "message": f"Network capture saved to: {output_path}",
            "test_run_id": test_run_id,
            "spec_file": spec_file,
            "output_path": output_path,
            "error": None
        }
    except FileNotFoundError as e:
        return {
            "status": "ERROR",
            "message": str(e),
            "test_run_id": test_run_id,
            "spec_file": spec_file,
            "output_path": None,
            "error": str(e)
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "message": f"Error during network capture: {e}",
            "test_run_id": test_run_id,
            "spec_file": spec_file,
            "output_path": None,
            "error": str(e)
        }

@mcp.tool()
async def convert_har_to_capture(
    test_run_id: str,
    har_path: str,
    ctx: Context,
    step_strategy: str = "auto",
    time_gap_threshold_ms: int = 3000,
) -> dict:
    """
    Convert a HAR (HTTP Archive) file to network capture JSON format.

    Use this instead of capture_network_traffic when you have a HAR file
    from Chrome DevTools, a proxy tool (Charles, Fiddler, mitmproxy),
    or Postman. The output JSON feeds directly into analyze_network_traffic
    and generate_jmeter_script.

    Args:
        test_run_id (str): Unique identifier for the test run.
        har_path (str): Full path to the HAR file.
        ctx (Context): FastMCP context for logging.
        step_strategy (str): How to group entries into steps
            (auto/page/time_gap/single_step). Default: auto.
        time_gap_threshold_ms (int): Gap threshold for time_gap strategy.
            Default: 3000ms.

    Returns:
        dict: {
            "status": "OK" | "ERROR",
            "message": str,
            "test_run_id": str,
            "network_capture_path": str | None,
            "error": str | None
        }
    """
    _ = ctx  # reserved for future context usage
    if not _HAR_ADAPTER_AVAILABLE:
        return {
            "status": "ERROR",
            "message": "HAR adapter is not available. Check server logs for import errors.",
            "test_run_id": test_run_id,
            "network_capture_path": None,
            "error": "HAR adapter failed to load",
        }
    try:
        output_path = _har_convert(
            har_path=har_path,
            test_run_id=test_run_id,
            step_strategy=step_strategy,
            time_gap_threshold_ms=time_gap_threshold_ms,
        )
        return {
            "status": "OK",
            "message": f"HAR file converted. Network capture saved to: {output_path}",
            "test_run_id": test_run_id,
            "network_capture_path": output_path,
            "error": None,
        }
    except FileNotFoundError as e:
        return {
            "status": "ERROR",
            "message": str(e),
            "test_run_id": test_run_id,
            "network_capture_path": None,
            "error": str(e),
        }
    except ValueError as e:
        return {
            "status": "ERROR",
            "message": str(e),
            "test_run_id": test_run_id,
            "network_capture_path": None,
            "error": str(e),
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "message": f"Unexpected error converting HAR file: {e}",
            "test_run_id": test_run_id,
            "network_capture_path": None,
            "error": str(e),
        }

@mcp.tool()
async def analyze_network_traffic(test_run_id: str, ctx: Context) -> dict:
    """
    Analyzes network traffic data, extracting test request metadata/stats
    and potential correlations, and writes correlation_spec.json.

    Args:
        test_run_id (str): Unique identifier for the test run.
        ctx (Context, optional): FastMCP context for state/error details.
        
    Returns: dict with extracted stats, request/response mappings, discovered correlations.
    """
    return await analyze_traffic(test_run_id, ctx)

# ----------------------------------------------------------
# JMeter JMX Generation
# ----------------------------------------------------------

@mcp.tool()
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
    ##return await validate_jmeter_script(test_run_id, jmx_path, ctx)

# ----------------------------------------------------------
# JMeter Test Execution Tools
# ----------------------------------------------------------

@mcp.tool()
async def list_jmeter_scripts(test_run_id: str, ctx: Context) -> dict:
    """
    List existing JMeter .jmx scripts for the given test_run_id.

    Looks under:
        <artifacts_root>/<test_run_id>/jmeter

    Args:
        test_run_id (str): Unique identifier for the test run.
        ctx (Context, optional): FastMCP context (currently unused, but reserved).

    Returns:
        dict: {
            "test_run_id": str,
            "artifact_dir": str,
            "scripts": [...],
            "count": int,
            "status": "OK" | "NOT_FOUND" | "EMPTY",
            "message": str
        }
    """
    # Currently no need to use ctx, but we accept it for consistency
    return list_jmeter_scripts_for_run(test_run_id)

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

@mcp.tool()
async def get_jmeter_run_status(test_run_id: str, pid: int, ctx: Context) -> dict:
    """
    Return current smoke-test metrics for the given test_run_id by reading its JTL file.

    Intended usage:
      1. Call start_jmeter_test(...)
      2. Poll this tool every few seconds while the smoke test runs
      3. Inspect total samples, error rate, avg, p90, etc.

    Args:
        test_run_id (str): Unique identifier for the test run.
        pid (int): Process ID of the running JMeter test.
        ctx (Context, optional): FastMCP context for tracking state, status, or error reporting.
    Returns:
        dict: Real-time test run metrics and status.
    """
    return get_jmeter_realtime_status(test_run_id, pid)

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
    ##return await summarize_test_run(test_run_id, ctx)

@mcp.tool()
async def generate_aggregate_report(test_run_id: str, ctx: Context) -> dict:
    """
    Generate a BlazeMeter-style Aggregate Performance Report CSV
    for the given test_run_id.

    This reads the JTL located under:
        <artifacts_root>/<test_run_id>/jmeter/<test_run_id>.jtl
    and writes:
        <artifacts_root>/<test_run_id>/jmeter/<test_run_id>_aggregate_report.csv

    Returns:
        dict with:
          - test_run_id
          - status: "OK" | "NO_JTL"
          - aggregate_report_path
          - label_count
    """
    _ = ctx  # currently unused, reserved for future context/state
    return generate_aggregate_report_csv(test_run_id)

# ----------------------------------------------------------
# JMeter Log Analysis Tools
# ----------------------------------------------------------

@mcp.tool()
async def analyze_jmeter_log(test_run_id: str, ctx: Context, log_source: str = "blazemeter") -> dict:
    """
    Analyze JMeter or BlazeMeter log files for a given test run.

    Performs deep analysis of all .log files under the specified source folder,
    identifying errors, grouping them by type/API/root cause, capturing first-
    occurrence request/response details, and optionally correlating with JTL data.

    Outputs three files to artifacts/<test_run_id>/analysis/:
      - <log_source>_log_analysis.csv  (all issues in tabular form)
      - <log_source>_log_analysis.json (metadata + summary + full issue list)
      - <log_source>_log_analysis.md   (human-readable report)

    Args:
        test_run_id (str): Unique identifier for the test run.
        ctx (Context): FastMCP context for state/error details.
        log_source (str): Which log folder to analyze — "jmeter" or "blazemeter".
            Defaults to "blazemeter".

    Returns:
        dict: {
            "test_run_id": str,
            "log_source": str,
            "status": "OK" | "NO_LOGS" | "ERROR",
            "log_files_analyzed": list[str],
            "jtl_file_analyzed": str | None,
            "total_issues": int,
            "total_occurrences": int,
            "issues_by_severity": dict,
            "output_files": {"csv": str, "json": str, "markdown": str},
            "message": str
        }
    """
    _ = ctx  # reserved for future context usage
    try:
        return run_jmeter_log_analysis(test_run_id, log_source)
    except Exception as e:
        return {
            "test_run_id": test_run_id,
            "log_source": log_source,
            "status": "ERROR",
            "message": f"Unexpected error during log analysis: {e}",
        }

# -----------------------------
# JMeter MCP entry point
# -----------------------------
if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down JMeter MCP…")
