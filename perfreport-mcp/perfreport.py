from fastmcp import FastMCP, Context
from services.report_generator import (
    create_performance_test_report as generate_report
)
from services.chart_generator import (
    create_single_axis_chart as generate_single_axis_chart,
    create_dual_axis_chart as generate_dual_axis_chart,
)
from services.template_manager import (
    list_templates as get_template_list, 
    get_template_details as get_template_info
)

mcp = FastMCP(name="perfreport")

@mcp.tool
async def create_performance_test_report(run_id: str, template: str = None, format: str = "md", ctx: Context = None) -> dict:
    """
    Generate a formatted performance test report for a specific run.
    Args:
        run_id: Unique test run identifier.
        template: Optional name of Markdown report template to use.
        format: Output type; one of 'md', 'pdf', or 'docx'.
        ctx: Workflow context for chaining.
    Returns:
        dict with run_id and path to created report file, or error info.
    """
    return await generate_report(run_id, template, format)

@mcp.tool
async def create_single_axis_chart(run_id: str, chart_data: dict, metric_config: dict, ctx: Context = None) -> dict:
    """
    Create a single axis (PNG) chart for a test run's reported metric(s).
    Args:
        run_id: Unique test run identifier.
        chart_data: Data to plot on the chart.
        metric_config: Chart configuration metadata.
        ctx: Workflow chaining context.
    Returns:
        dict with run_id and path to chart image, or error info.
    """
    return await generate_single_axis_chart(run_id, chart_data, metric_config)

@mcp.tool
async def create_dual_axis_chart(run_id: str, chart_data: dict, metric_config: dict, ctx: Context = None) -> dict:
    """
    Create a dual axis (PNG) chart for a test run's reported metrics.
    Args:
        run_id: Unique test run identifier.
        chart_data: Data to plot across two Y axes.
        metric_config: Chart configuration metadata.
        ctx: Workflow chaining context.
    Returns:
        dict with run_id and path to chart image, or error info.
    """
    return await generate_dual_axis_chart(run_id, chart_data, metric_config)
    
@mcp.tool
async def create_comparison_report(run_id_list: list, template: str = None, format: str = "md", ctx: Context = None) -> dict:
    """
    Generate a report comparing multiple test runs.
    Args:
        run_id_list: List of test run identifiers to compare.
        template: Optional name of Markdown report template to use.
        format: Output type; 'md', 'pdf', or 'docx'.
        ctx: Workflow chaining context.
    Returns:
        dict with run_id_list and report path, or error info.
    """
    return {
        "error": "Comparison report feature not yet implemented",
        "run_id_list": run_id_list
    }
    
@mcp.tool
async def revise_performance_test_report(run_id: str, feedback: str, ctx: Context = None) -> dict:
    """
    Revise a performance test report based on human or AI-agent feedback.
    Args:
        run_id: Unique test run identifier.
        feedback: Free text with revisions or questions.
        ctx: Workflow chaining context.
    Returns:
        dict with run_id, synopsis of changes, and path to the revised report, or error info.
    """
    return {
        "error": "Report revision feature not yet implemented",
        "run_id": run_id
    }

@mcp.tool
async def list_templates(ctx: Context = None) -> dict:
    """
    List available Markdown templates for report generation.
    Args:
        ctx: Workflow chaining context.
    Returns:
        dict listing template names and description metadata.
    """
    return await get_template_list()
    
@mcp.tool
async def get_template_details(template_name: str, ctx: Context = None) -> dict:
    """
    Get detailed info about a report template.
    Args:
        template_name: The template to look up.
        ctx: Workflow chaining context.
    Returns:
        dict with template metadata and content preview, or error info.
    """
    return await get_template_info(template_name)

if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down Performance Reporting MCP…")

