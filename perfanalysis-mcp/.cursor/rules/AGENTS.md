# PerfAnalysis MCP Workflow: Analyzing Performance Test Data

This workflow performs comprehensive analysis of performance test results and infrastructure metrics. It analyzes BlazeMeter test results, Datadog infrastructure metrics, correlates performance data with infrastructure constraints, and analyzes logs for errors and performance issues. The analysis outputs are used to generate performance reports.

0. **Prerequisites:**
   - Test run ID (test_run_id) should be the same as the BlazeMeter run_id from the BlazeMeter workflow
   - Environment name (environment) should be the same as the environment name used in the Datadog workflow
   - BlazeMeter workflow must be completed first (required files: `artifacts/{test_run_id}/blazemeter/aggregate_performance_report.csv`)
   - Datadog workflow must be completed first (required files: `artifacts/{test_run_id}/datadog/host_metrics_*.csv` or `k8s_metrics_*.csv`)
   Do not proceed until both BlazeMeter and Datadog workflows have completed successfully.

1. **Analyze test results** using `analyze_test_results` with the test_run_id.
   - This analyzes BlazeMeter JMeter test results and must be run BEFORE steps 2 and 3.
   - Requires: `artifacts/{test_run_id}/blazemeter/aggregate_performance_report.csv`

2. **Analyze environment metrics** using `analyze_environment_metrics` with the test_run_id and environment name.
   - This analyzes Datadog infrastructure metrics (CPU/Memory) from hosts or Kubernetes services.
   - Requires: `artifacts/{test_run_id}/datadog/host_metrics_*.csv` or `k8s_metrics_*.csv`

3. **Correlate test results** using `correlate_test_results` with the test_run_id.
   - This cross-correlates BlazeMeter and Datadog data to identify relationships.
   - Requires: Outputs from steps 1 and 2 must be completed first.

4. **Analyze logs** using `analyze_logs` with the test_run_id.
   - This analyzes JMeter/BlazeMeter logs and Datadog APM logs for errors and performance issues.
   - Requires: `artifacts/{test_run_id}/blazemeter/jmeter.log` and `artifacts/{test_run_id}/datadog/logs_*.csv`

5. **Identify bottlenecks** using `identify_bottlenecks` with the test_run_id.
   - This identifies the concurrency threshold where performance begins to degrade and the limiting factor.
   - Detects: latency degradation, error rate increases, throughput plateaus, infrastructure saturation, resource-performance coupling, and per-endpoint bottlenecks.
   - Requires: `artifacts/{test_run_id}/blazemeter/test-results.csv` (JTL data with allThreads column)
   - Optional: `artifacts/{test_run_id}/datadog/k8s_metrics_*.csv` or `host_metrics_*.csv` for infrastructure saturation analysis
   - Optional: Pass `baseline_run_id` for comparison against a previous test run
   - Outputs: `artifacts/{test_run_id}/analysis/bottleneck_analysis.json`, `bottleneck_analysis.csv`, `bottleneck_analysis.md`
