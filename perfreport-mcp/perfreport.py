from fastmcp import FastMCP, Context
from typing import Optional
from services.report_generator import (
    generate_performance_test_report,
)
from services.chart_generator import (
    generate_chart,
)
from services.template_manager import (
    list_templates as get_template_list, 
    get_template_details as get_template_info
)
from services.comparison_report_generator import generate_comparison_report


mcp = FastMCP(name="perfreport")


@mcp.tool
async def create_performance_test_report(run_id: str, ctx: Context, format: str = "md", template: str = None) -> dict:
    """
    Generate a formatted performance test report for a specific run.
    Args:
        run_id: Unique test run identifier.
        ctx: Workflow context for chaining.
        format: Output type; one of 'md', 'pdf', or 'docx'.
        template: Optional name of Markdown report template to use.
        
    Returns:
        dict with run_id and path to created report file, or error info.
    """
    return await generate_performance_test_report(run_id, ctx, format, template)

@mcp.tool
async def create_comparison_report(run_id_list: list, template: str = None, format: str = "md", ctx: Context = None) -> dict:
    """
    Generate a report comparing multiple test runs.
    
    Args:
        run_id_list: List of test run identifiers to compare (2-5 recommended).
        template: Optional name of Markdown comparison template to use.
        format: Output type; 'md', 'pdf', or 'docx'.
        ctx: Workflow chaining context.
    
    Returns:
        dict with run_id_list, report path, and metadata, or error info.
    """
    return await generate_comparison_report(run_id_list, ctx, format, template)
    
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
async def create_chart(run_id: str, chart_id: str, env_name: Optional[str] = None, ctx: Context = None) -> dict:
    """
    Unified chart generation tool for MCP.
    Args:
        run_id: Test run ID
        chart_id: Chart type specifier (must match YAML/schema)
        env_name: Optional, for infrastructure charts
        ctx: Workflow context
    Returns:
        dict containing chart metadata, path, and any errors
    """
    return await generate_chart(run_id, env_name, chart_id)

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
    Get detailed info about a report markdown template.
    Args:
        template_name: The markdown template to look up.
        ctx: Workflow chaining context.
    Returns:
        dict with template metadata and content preview, or error info.
    """
    return await get_template_info(template_name)

@mcp.tool
async def list_chart_types(ctx: Context = None) -> dict:
    """
    List available chart types from chart_schema.yaml.
    
    Args:
        ctx: Workflow chaining context.
    
    Returns:
        dict with available chart types and their descriptions.
    """
    from services.chart_generator import CHART_SCHEMA
    
    chart_types = []
    for chart in CHART_SCHEMA.get('charts', []):
        chart_types.append({
            'id': chart['id'],
            'title': chart['title'],
            'description': chart['description'],
            'chart_type': chart['chart_type'],
            'placeholder': chart.get('placeholder', '')
        })
    
    return {
        'chart_types': chart_types,
        'total_count': len(chart_types)
    }

if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down Performance Reporting MCP…")

