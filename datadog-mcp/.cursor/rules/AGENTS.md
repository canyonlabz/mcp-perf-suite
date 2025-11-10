# Datadog MCP Workflow: Collecting Infrastructure Metrics and Logs

This workflow collects infrastructure metrics (CPU and Memory) and application logs from Datadog during the performance test execution window. It automatically detects the environment type (host-based or Kubernetes-based) and retrieves metrics accordingly. The collected data is used for correlation analysis with performance test results.

0. **Prerequisites:** 
   - Environment name (env_name) should be provided by the user (e.g., 'QA', 'UAT', etc.)
   - Test run ID (run_id) should be the same as the BlazeMeter run_id from the previous workflow
   - Start and end times should be extracted from the BlazeMeter test run results
   Do not proceed until environment name is provided and BlazeMeter workflow has completed.

1. Use `load_environment` with the provided environment name from step 0. This tool automatically:
   - Loads the complete environment configuration
   - Identifies the environment type (host-based or k8s-based)
   - Loads all resources (hosts with CPU/Memory specs or k8s services with CPU/Memory specs)
2. Based on the loaded environment configuration:
   - If environment type is host-based → use `get_host_metrics`
   - If environment type is k8s-based → use `get_kubernetes_metrics`
   - Use the start and end dates from the BlazeMeter test run results to get metrics. NOTE: metrics pulled should be CPU and Memory only.
3. Get Datadog logs:
   - Always get logs for query_type "http_errors" using the same start/end times and run_id.
   - Ask the user if "http_errors" logs are sufficient or if additional log types should be captured (e.g., "warnings", "all_errors", "api_errors", "service_errors", "host_errors", "kubernetes_errors", or "custom").
   - If the user requests additional log types, use `get_logs` for each additional query_type using the same start/end times and run_id.

# Tasks:
1. Provide a high-level summary and put into a table showcasing CPU & Memory comparison.
2. After completing all the BlazeMeter and Datadog steps, continue to the PerfAnalysis MCP workflow.