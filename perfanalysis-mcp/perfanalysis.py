# perfanalysis.py
from fastmcp import FastMCP, Context    # ✅ FastMCP 2.x import
from typing import Optional, List, Dict, Any
import json

from services.performance_analyzer import (
    analyze_blazemeter_results,
    analyze_apm_metrics,
    correlate_performance_data,
    detect_performance_anomalies,
    identify_system_bottlenecks,
    compare_multiple_runs,
    generate_executive_summary,
    get_current_analysis_status
)

mcp = FastMCP(name="perfanalysis")

@mcp.tool()
async def analyze_test_results(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Analyze BlazeMeter JMeter test results (JTL CSV format)
    
    Args:
        test_run_id: The unique test run identifier
        ctx: FastMCP workflow context for chaining
        
    Returns:
        Dictionary containing statistical analysis of test results
    """
    return await analyze_blazemeter_results(test_run_id, ctx)

@mcp.tool()
async def analyze_environment_metrics(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Analyze Datadog infrastructure metrics and logs
    
    Args:
        test_run_id: The unique test run identifier
        ctx: FastMCP workflow context for chaining
        
    Returns:
        Dictionary containing infrastructure metrics analysis
    """
    return await analyze_apm_metrics(test_run_id, ctx)

@mcp.tool()
async def correlate_test_results(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Cross-correlate BlazeMeter and APM data to identify relationships
    
    Args:
        test_run_id: The unique test run identifier
        ctx: FastMCP workflow context for chaining
        
    Returns:
        Dictionary containing correlation analysis results
    """
    return await correlate_performance_data(test_run_id, ctx)

@mcp.tool()
async def detect_anomalies(test_run_id: str, sensitivity: str = "medium", ctx: Context = None) -> Dict[str, Any]:
    """
    Detect statistical anomalies in performance and infrastructure metrics
    
    Args:
        test_run_id: The unique test run identifier
        sensitivity: Detection sensitivity (low/medium/high)
        ctx: FastMCP workflow context for chaining
        
    Returns:
        Dictionary containing detected anomalies
    """
    return await detect_performance_anomalies(test_run_id, sensitivity, ctx)

@mcp.tool()
async def identify_bottlenecks(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Identify performance bottlenecks and constraint points
    
    Args:
        test_run_id: The unique test run identifier
        ctx: FastMCP workflow context for chaining
        
    Returns:
        Dictionary containing identified bottlenecks and recommendations
    """
    return await identify_system_bottlenecks(test_run_id, ctx)

@mcp.tool()
async def compare_test_runs(test_run_ids: List[str], comparison_type: str = "performance", ctx: Context = None) -> Dict[str, Any]:
    """
    Compare multiple test runs for trend analysis (max 5 runs)
    
    Args:
        test_run_ids: List of test run identifiers to compare (max 5)
        comparison_type: Type of comparison (performance/infrastructure/both)
        ctx: FastMCP workflow context for chaining
        
    Returns:
        Dictionary containing comparative analysis
    """
    return await compare_multiple_runs(test_run_ids, comparison_type, ctx)

@mcp.tool()
async def summary_analysis(test_run_id: str, include_recommendations: bool = True, ctx: Context = None) -> Dict[str, Any]:
    """
    Generate executive summary with AI-powered insights using OpenAI
    
    Args:
        test_run_id: The unique test run identifier
        include_recommendations: Include AI-generated recommendations
        ctx: FastMCP workflow context for chaining
        
    Returns:
        Dictionary containing executive summary and insights
    """
    return await generate_executive_summary(test_run_id, include_recommendations, ctx)

@mcp.tool()
async def get_analysis_status(test_run_id: str, ctx: Context) -> Dict[str, Any]:
    """
    Get the current analysis status for a test run
    
    Args:
        test_run_id: The unique test run identifier
        ctx: FastMCP workflow context for chaining
        
    Returns:
        Dictionary containing analysis completion status
    """
    return await get_current_analysis_status(test_run_id, ctx)

if __name__ == "__main__":
    try:
        mcp.run("stdio")
    except KeyboardInterrupt:
        print("Shutting down Performance Analysis MCP…")
