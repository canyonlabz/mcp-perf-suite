# End-to-End Performance Testing Workflow

This workflow orchestrates the complete performance testing pipeline from retrieving BlazeMeter/JMeter test results through publishing reports to Confluence. It coordinates multiple MCP workflows sequentially, ensuring data flows correctly between each step and handles both single and multiple test run scenarios.

## Workflow Overview

The end-to-end workflow executes the following MCP workflows in sequence:
1. **BlazeMeter MCP** - Retrieves and processes test results
2. **Datadog MCP** - Collects infrastructure metrics and logs
3. **PerfAnalysis MCP** - Analyzes performance data and correlates results
4. **PerfReport MCP** - Generates formatted reports and charts
5. **Confluence MCP** (Optional) - Publishes reports to Confluence

Each workflow can also be run independently if needed (e.g., running Datadog workflow days after test completion).

---

## 0. Prerequisites Collection

**Before starting, collect ALL required information from the user:**

### Performance Test Details

Ask the user if this is for:
- **Single test run** (most common)
- **Multiple test runs** (sequential processing)

For each test run, collect:
- **Test run ID** (run_id) - e.g., "7654321"
- **Environment name** - e.g., "QA"
- **Environment type** (optional, for validation) - "Hosts-based" or "Kubernetes-based"
- **BlazeMeter Workspace Name** - e.g., "Quality Engineering"

### Confluence Details (Optional - only if publishing to Confluence)

If the user provides Confluence information, assume they want to publish results:
- **Confluence mode** - "cloud" or "onprem"
- **Confluence Space name** - e.g., "Quality Engineering"
- **Parent Page name** - e.g., "AI Generated Test Reports"
- **Parent Page ID** (optional, if provided) - e.g., "123456789"

**Do not proceed until all required information is collected.**

---

## 1. Initialize Task Tracking

For each test run, create granular task items using task tracking to monitor progress:
- BlazeMeter workflow steps (9 steps)
- Datadog workflow steps (3 steps)
- PerfAnalysis workflow steps (4 steps)
- PerfReport workflow steps (4 steps)
- Confluence workflow steps (5 steps, if applicable)

This allows tracking progress and resuming if context is lost. Update task status as each step completes.

---

## 2. Process Each Test Run Sequentially

**Important:** Process test runs sequentially (Run 1 complete → Run 2 complete) to maintain context and avoid confusion.

For each test run:

### 2.1 BlazeMeter MCP Workflow

**Reference:** `blazemeter-mcp/.cursor/rules/AGENTS.md`

1. Execute the BlazeMeter workflow with the provided workspace name and run_id.
2. **Extract start_time and end_time** from the BlazeMeter test run results:
   - Primary: Extract from `get_run_results` response
   - Fallback: Extract from `get_aggregate_report` if not available in run results
   - Store these timestamps for use in Datadog workflow
3. **Error Handling:**
   - If API calls fail, retry up to 3 times
   - If retries fail, stop workflow and report error
   - Do not proceed to next workflow if BlazeMeter workflow fails
4. **Validation:** Verify required files exist:
   - `artifacts/{run_id}/blazemeter/aggregate_performance_report.csv`
   - `artifacts/{run_id}/blazemeter/test-results.csv`
   - `artifacts/{run_id}/blazemeter/jmeter.log`
5. Update task tracking: Mark all BlazeMeter steps as completed.

**Data to pass forward:**
- `run_id` → to all downstream workflows
- `start_time` → to Datadog workflow
- `end_time` → to Datadog workflow

---

### 2.2 Datadog MCP Workflow

**Reference:** `datadog-mcp/.cursor/rules/AGENTS.md`

1. Execute the Datadog workflow with:
   - Environment name from prerequisites
   - Test run ID from BlazeMeter workflow
   - Start and end times extracted from BlazeMeter results
2. **Error Handling:**
   - If API calls fail, retry up to 3 times
   - If retries fail, stop workflow and report error
   - Do not proceed to next workflow if Datadog workflow fails
3. **Validation:** Verify required files exist:
   - `artifacts/{run_id}/datadog/host_metrics_*.csv` OR
   - `artifacts/{run_id}/datadog/k8s_metrics_*.csv`
   - `artifacts/{run_id}/datadog/logs_*.csv`
4. Update task tracking: Mark all Datadog steps as completed.

**Data to pass forward:**
- `run_id` → to all downstream workflows
- `environment name` → to PerfAnalysis and PerfReport workflows

---

### 2.3 PerfAnalysis MCP Workflow

**Reference:** `perfanalysis-mcp/.cursor/rules/AGENTS.md`

1. Execute the PerfAnalysis workflow with:
   - Test run ID from previous workflows
   - Environment name from Datadog workflow
2. **Error Handling:**
   - These are Python code executions (not API calls)
   - Do NOT retry on failure
   - Analyze the error and report back to user:
     - Error message from MCP tool
     - Missing file paths (if any)
     - Expected vs. actual file structure
     - Root cause analysis
   - Do NOT attempt to fix code or modify files
   - Stop workflow and report issue to user
3. **Validation:** Verify required analysis files exist:
   - `artifacts/{run_id}/analysis/performance_analysis.json`
   - `artifacts/{run_id}/analysis/infrastructure_analysis.json`
   - `artifacts/{run_id}/analysis/correlation_analysis.json`
   - `artifacts/{run_id}/analysis/log_analysis.json`
4. Update task tracking: Mark all PerfAnalysis steps as completed.

**Data to pass forward:**
- `run_id` → to PerfReport workflow
- `environment name` → to PerfReport workflow

---

### 2.4 PerfReport MCP Workflow

**Reference:** `perfreport-mcp/.cursor/rules/AGENTS.md`

1. Execute the PerfReport workflow with:
   - Test run ID from previous workflows
   - Environment name from previous workflows (for infrastructure charts)
2. **Error Handling:**
   - These are Python code executions (not API calls)
   - Do NOT retry on failure
   - Analyze the error and report back to user:
     - Error message from MCP tool
     - Missing file paths (if any)
     - Expected vs. actual file structure
     - Root cause analysis
   - Do NOT attempt to fix code or modify files
   - Stop workflow and report issue to user
3. **Validation:** Verify required report files exist:
   - `artifacts/{run_id}/reports/performance_report_{run_id}.md`
   - `artifacts/{run_id}/charts/*.png` (at least CPU, Memory, and P90 charts)
4. Update task tracking: Mark all PerfReport steps as completed.

**Data to pass forward:**
- `run_id` → to Confluence workflow (if applicable)
- Report file paths → to Confluence workflow (if applicable)

---

### 2.5 Confluence MCP Workflow (Optional)

**Reference:** `confluence-mcp/.cursor/rules/AGENTS.md`

**Only execute if Confluence details were provided in prerequisites.**

1. Execute the Confluence workflow for each test run:
   - Use the same Confluence Space and Parent Page for all test runs
   - Each test run will create a separate page under the same parent
2. **Error Handling:**
   - If API calls fail, retry up to 3 times
   - If retries fail, report error but continue (don't block other runs)
3. **Validation:** Verify page was created successfully (check for page_ref and URL in response)
4. Update task tracking: Mark all Confluence steps as completed.

---

## 3. Generate End-to-End Summary

After all test runs are processed, generate a comprehensive summary:

### 3.1 File Locations Summary

For each test run, list all generated artifacts:
- BlazeMeter artifacts location: `artifacts/{run_id}/blazemeter/`
- Datadog artifacts location: `artifacts/{run_id}/datadog/`
- Analysis artifacts location: `artifacts/{run_id}/analysis/`
- Report artifacts location: `artifacts/{run_id}/reports/`
- Chart artifacts location: `artifacts/{run_id}/charts/`
- Confluence page URLs (if published)

### 3.2 Aggregate Metrics Summary

For each test run, provide aggregate metrics in a table format:

**BlazeMeter Metrics:**
- Total samples
- Success rate (%)
- Average response time (ms)
- P90 response time (ms)
- P95 response time (ms)
- Peak throughput (req/sec)
- Error rate (%)

**Datadog Infrastructure Metrics:**
- Peak CPU utilization (%) - aggregate per Host or k8s service
- Average CPU utilization (%) - aggregate per Host or k8s service
- Peak Memory utilization (%) - aggregate per Host or k8s service
- Average Memory utilization (%) - aggregate per Host or k8s service

**Note:** Do not include per-API breakdowns, only aggregate metrics.

### 3.3 Multiple Test Runs Comparison (if applicable)

If multiple test runs were processed, provide a side-by-side comparison table showing:
- Test run IDs
- Key performance metrics (response times, throughput, error rates)
- Infrastructure metrics (CPU/Memory utilization)
- Any notable differences or trends

---

## 4. Final Task Status

Display final task tracking status:
- Total test runs processed
- Completed workflows per test run
- Any failed steps (with error details)
- Overall workflow status (Success/Partial Success/Failed)

---

## Important Notes

1. **Sequential Execution:** Each workflow must complete successfully before proceeding to the next. If any workflow fails, stop and report the error.

2. **Data Flow:** Ensure these values are passed correctly through all workflows:
   - `run_id` → All workflows
   - `environment name` → Datadog → PerfAnalysis → PerfReport
   - `start_time` / `end_time` → BlazeMeter → Datadog
   - `workspace_id` → BlazeMeter only (looked up from workspace name)

3. **Error Recovery:** 
   - API-based workflows (BlazeMeter, Datadog, Confluence): Retry up to 3 times
   - Code-based workflows (PerfAnalysis, PerfReport): Report errors, do not retry

4. **Independence:** Each individual workflow can be run standalone if needed. The E2E workflow is for convenience and automation.

5. **Context Management:** Use task tracking to maintain state. If context is lost, the task list can be referenced to resume from the last completed step.

