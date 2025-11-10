# PerfReport MCP Workflow: Generating Performance Test Reports

This workflow generates formatted performance test reports (Markdown, PDF, or Word) and creates visualization charts from the analysis data produced by the PerfAnalysis MCP. Reports include performance statistics, infrastructure metrics, correlation analysis, and visual charts for CPU/Memory utilization and response time trends.

0. **Prerequisites:**
   - Test run ID (run_id) should be the same as the test_run_id from the PerfAnalysis workflow
   - Environment name (env_name) should be the same as the environment name used in the Datadog and PerfAnalysis workflows (required for infrastructure charts)
   - PerfAnalysis workflow must be completed first (required files: `artifacts/{run_id}/analysis/performance_analysis.json`, `infrastructure_analysis.json`, `correlation_analysis.json`)
   Do not proceed until the PerfAnalysis workflow has completed successfully.

1. **Create performance test report** using `create_performance_test_report` with the run_id.
   - Default format is Markdown ("md"), but can also generate PDF ("pdf") or Word ("docx") formats.
   - Optional: Specify a template name if a custom template should be used.
   - Requires: `artifacts/{run_id}/analysis/performance_analysis.json` and other analysis JSON files from PerfAnalysis workflow.

2. **List available chart types** using `list_chart_types` to see all available chart options.
   - This helps identify the correct chart_id values for chart creation.

3. **Create CPU and Memory Utilization charts** using `create_chart` with the run_id:
   - Create chart with chart_id "CPU_UTILIZATION_LINE" (requires env_name parameter for infrastructure charts).
   - Create chart with chart_id "MEMORY_UTILIZATION_LINE" (requires env_name parameter for infrastructure charts).
   - These charts visualize CPU and Memory utilization over time for the test run.

4. **Create P90 vs. Virtual Users chart** using `create_chart` with the run_id:
   - Create chart with chart_id "RESP_TIME_P90_VUSERS_DUALAXIS".
   - This dual-axis chart shows the correlation between 90th percentile response time and virtual users over time.
