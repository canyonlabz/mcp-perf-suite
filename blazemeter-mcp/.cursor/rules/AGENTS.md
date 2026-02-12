# BlazeMeter MCP Workflow: Retrieving and Processing Test Results

This workflow retrieves performance test results from BlazeMeter, downloads test artifacts (JTL files, logs, etc.), processes the data, and generates aggregate performance reports. The processed results are stored locally and used as input for downstream workflows (Datadog and PerfAnalysis).

0. **Prerequisites:** Ask the user to provide:
   - BlazeMeter workspace name (e.g., "Quality Engineering", "Copilot Integration", etc.)
   - Test run ID (run_id)
   Do not proceed until both are provided.

1. **Get BlazeMeter workspaces** using `get_workspaces` to list all available workspaces.
   - Search for the workspace that matches the provided workspace name.
   - Extract the workspace_id from the matching workspace result.
   - If no matching workspace is found, report an error and ask the user to verify the workspace name.

2. **Get test run results** for the given performance test using run_id.
   - Extract and store the start_time and end_time from the test run results (required for downstream Datadog workflow).
   - Extract the `sessionsId` list from the response (contains one entry per load generator/engine).
   - If start/end times cannot be extracted from this step, fallback to extracting from the aggregate report in step 6.

3. **Get artifacts path**. This is the location of where test results will be stored locally.

4. **Process session artifacts** using `process_session_artifacts(run_id, sessions_id)`.
   - Pass the `sessionsId` list from step 2 directly.
   - This tool handles downloading, extracting, and processing all session artifacts.
   - For single-session runs (1 entry in sessionsId): produces `test-results.csv` and `jmeter.log`.
   - For multi-session runs (N entries): produces combined `test-results.csv` and `jmeter-1.log` through `jmeter-N.log`.
   - If the tool returns `status: "partial"` or `status: "error"`, re-run the tool with the same parameters.
     The tool is idempotent and will skip completed sessions, retrying only the failed ones.

5. **Get public report** for given run_id.

6. **Get aggregate report** for given run_id.

7. **(Optional) Analyze JMeter logs** using JMeter MCP tool `analyze_jmeter_log` with the test_run_id and `log_source: "blazemeter"`.
   - This step requires the JMeter MCP server to be enabled and running.
   - Analyzes the JMeter log file(s) produced in step 4 for errors, exceptions, and performance issues.
   - Discovers all `.log` files in `artifacts/{run_id}/blazemeter/` automatically (handles both single and multi-session logs).
   - Output files are used downstream by PerfAnalysis and PerfReport MCP workflows.
   - If the JMeter MCP server is not available, skip this step.

**NOTE:** If any of the above steps fail, please try again. The BlazeMeter test results are used downstream.

# Tasks:
1. Provide high-level summary and put into a table, including start/end times.
2. Next, proceed with Datadog MCP workflow.