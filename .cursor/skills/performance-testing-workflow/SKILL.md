---
name: performance-testing-workflow
description: >-
  End-to-end performance testing pipeline orchestrating BlazeMeter, Datadog, PerfAnalysis,
  PerfReport, and Confluence MCP workflows sequentially. Use when the user mentions
  performance testing workflow, E2E pipeline, BlazeMeter results, test run analysis,
  performance report generation, or end-to-end test processing.
---

# End-to-End Performance Testing Workflow

## When to Use This Skill

- User wants to run the full performance testing pipeline (BlazeMeter through Confluence)
- User mentions E2E workflow, performance testing workflow, or test run processing
- User has BlazeMeter test run IDs and wants to generate reports
- User wants to collect BlazeMeter results, Datadog metrics, analyze, and report
- User wants to run any individual sub-workflow (BlazeMeter, Datadog, PerfAnalysis, PerfReport, or Confluence) standalone

---

## Reference

This section provides context for humans and capable models. For the step-by-step
execution instructions, skip to the **Execution** section below.

### What This Workflow Does

Orchestrates the complete performance testing pipeline from retrieving BlazeMeter/JMeter
test results through publishing reports to Confluence. It coordinates multiple MCP
workflows sequentially, ensuring data flows correctly between each step.

The pipeline executes in this order:

1. **BlazeMeter MCP** — Retrieves and processes test results
2. **Datadog MCP** — Collects infrastructure metrics, logs, and APM traces
3. **PerfAnalysis MCP** — Analyzes performance data and correlates results
4. **PerfReport MCP** — Generates formatted reports and charts
5. **Confluence MCP** (Optional) — Publishes reports to Confluence

Each workflow can also be run independently if needed (e.g., running Datadog workflow
days after test completion).

### Data Flow Between Workflows

Variables that must be passed between workflows:

| Variable | Source | Destination |
|----------|--------|-------------|
| `run_id` | User input | All workflows |
| `start_time` | BlazeMeter `get_run_results` | Datadog workflow |
| `end_time` | BlazeMeter `get_run_results` | Datadog workflow |
| `environment` | User input | Datadog, PerfAnalysis, PerfReport |
| `sessionsId` | BlazeMeter `get_run_results` | BlazeMeter `process_session_artifacts` |
| `space_ref` | Confluence `list_spaces` | Confluence `create_page` |
| `parent_id` | Confluence `get_page_by_id` / `list_pages` | Confluence `create_page` |
| `page_ref` | Confluence `create_page` | Confluence `attach_images`, `update_page` |

### Tool Reference

#### BlazeMeter MCP Tools

| Tool | Purpose | Key Parameters |
|------|---------|---------------|
| `get_run_results` | Get test run results, extract start/end times and sessionsId | `test_run_id` |
| `get_artifacts_path` | Get local artifact storage path | `run_id` |
| `process_session_artifacts` | Download, extract, and process session artifacts | `run_id`, `sessions_id_list` |
| `get_public_report` | Get public BlazeMeter report URL | `test_run_id` |
| `get_aggregate_report` | Get aggregate performance report CSV | `test_run_id` |

#### Datadog MCP Tools

| Tool | Purpose | Key Parameters |
|------|---------|---------------|
| `load_environment` | Load environment config (host-based or k8s-based) | `env_name` |
| `get_host_metrics` | Get CPU/Memory metrics for host-based environments | `run_id`, `env_name`, `start_time`, `end_time` |
| `get_kubernetes_metrics` | Get CPU/Memory metrics for k8s-based environments | `run_id`, `env_name`, `start_time`, `end_time` |
| `get_logs` | Get logs from Datadog | `run_id`, `env_name`, `query_type`, `start_time`, `end_time` |
| `get_apm_traces` | Get APM traces from Datadog | `run_id`, `env_name`, `query_type`, `start_time`, `end_time` |
| `get_kpi_timeseries` | Get custom KPI metrics (optional) | `env_name`, `query_names` (list), `start_time`, `end_time`, `run_id`, `scope` (optional) |

#### PerfAnalysis MCP Tools

| Tool | Purpose | Key Parameters |
|------|---------|---------------|
| `analyze_test_results` | Analyze BlazeMeter test results | `test_run_id` |
| `analyze_environment_metrics` | Analyze Datadog infrastructure metrics | `test_run_id`, `environment` |
| `correlate_test_results` | Cross-correlate BlazeMeter and Datadog data | `test_run_id` |
| `analyze_logs` | Analyze JMeter/BlazeMeter and Datadog logs | `test_run_id` |
| `identify_bottlenecks` | Bottleneck analysis and concurrency threshold detection | `test_run_id` |

#### PerfReport MCP Tools

| Tool | Purpose | Key Parameters |
|------|---------|---------------|
| `create_performance_test_report` | Generate performance report (MD/PDF/DOCX) | `run_id`, `template` (optional), `format` |
| `list_chart_types` | List available chart options and chart_id values | — |
| `create_chart` | Create a chart image (PNG) | `run_id`, `chart_id`, `env_name` (for infra charts) |

#### Confluence MCP Tools

| Tool | Purpose | Key Parameters |
|------|---------|---------------|
| `list_spaces` | List Confluence spaces | `mode` |
| `get_space_details` | Get space metadata | `space_ref`, `mode` |
| `get_page_by_id` | Look up page by ID | `page_id`, `mode` |
| `list_pages` | List pages in a space (search by name) | `space_ref`, `mode` |
| `get_available_reports` | List available reports for a test run | `test_run_id` |
| `create_page` | Create Confluence page from Markdown report | `space_ref`, `test_run_id`, `filename`, `mode`, `parent_id`, `report_type` |
| `attach_images` | Attach chart PNGs to a page | `page_ref`, `test_run_id`, `mode`, `report_type` |
| `update_page` | Replace chart placeholders with embedded images | `page_ref`, `test_run_id`, `mode`, `report_type` |

#### JMeter MCP Tools (Optional)

| Tool | Purpose | Key Parameters |
|------|---------|---------------|
| `analyze_jmeter_log` | Analyze JMeter log for errors and issues | `test_run_id`, `log_source` |

### report_type Parameter

The `report_type` parameter determines artifact paths for Confluence publishing:

- `"single_run"` — Individual test run reports (this workflow)
  - Reports: `artifacts/{test_run_id}/reports/`
  - Charts: `artifacts/{test_run_id}/charts/`
- `"comparison"` — Comparison reports (see `.cursor/skills/comparison-report-workflow/SKILL.md`)
  - Reports: `artifacts/comparisons/{comparison_id}/`
  - Charts: `artifacts/comparisons/{comparison_id}/charts/`

### Related Rules

- **`prerequisites.mdc`** — `test_run_id` and artifact structure validation
- **`skill-execution-rules.mdc`** — Follow steps in order, collect inputs first, do not skip
- **`mcp-error-handling.mdc`** — MCP tool error handling (retry policy, reporting format)

### Downstream Workflows

After completing this workflow, the user can proceed to:

- **AI HITL Report Revision** — `.cursor/skills/report-revision-workflow/SKILL.md`
  Iterative AI-assisted revision of report sections (executive summary, key observations,
  issues table) with version tracking.
- **Comparison Report** — `.cursor/skills/comparison-report-workflow/SKILL.md`
  Multi-run comparison report with comparison charts and Confluence publishing.
  Requires the E2E workflow to have completed for each individual test run first.

### Important Notes

- **Sequential execution:** Each workflow must complete before proceeding to the next.
- **Independence:** Each sub-workflow can run standalone if needed.
- **Multiple test runs:** Process sequentially (Run 1 complete -> Run 2 complete).
- **Context management:** Use task tracking to maintain state. If context is lost, the
  task list can be referenced to resume from the last completed step.

---

## Execution

Follow these steps exactly, in order. Each step has one or more actions.

---

### Collect Inputs

Ask the user for the following values. Do not proceed until all required values are collected.

```
REQUIRED:
  test_mode = [single test run or multiple test runs]
  run_id    = [for each test run — e.g., "7654321"]
  env_name  = [environment name — e.g., "QA", "UAT"]

OPTIONAL:
  test_name = [informational label for the test run]
  env_type  = [for validation — "Hosts-based" or "Kubernetes-based"]

CONDITIONAL (only if publishing to Confluence):
  confluence_mode  = ["cloud" or "onprem"]
  confluence_space = [space name — e.g., "Quality Engineering"]
  parent_page_name = [e.g., "AI Generated Test Reports"]
  parent_page_id   = [optional — e.g., "123456789"]
```

If the user provides Confluence information, assume they want to publish results.

---

### Step 1 — Initialize Task Tracking

**Input:** `run_id`(s), workflow list

**Action:** For each test run, create granular task items to monitor progress:

- BlazeMeter workflow steps (6 steps)
- Datadog workflow steps (5 steps)
- PerfAnalysis workflow steps (5 steps)
- PerfReport workflow steps (4 steps)
- Confluence workflow steps (7 steps, if applicable)

Update task status as each step completes. This allows resuming if context is lost.

---

### Step 2 — BlazeMeter MCP Workflow

**Prerequisites:** `run_id` collected from user.

**For each test run, process sequentially (Run 1 complete -> Run 2).**

#### 2a. Get Test Run Results

```
get_run_results(
  test_run_id = {run_id}
)
```

**Save:**
- `start_time` = extracted from the test run results
- `end_time` = extracted from the test run results
- `sessionsId` = list of session IDs from the response

If start/end times cannot be extracted, fall back to extracting from the aggregate report
in step 2e.

#### 2b. Get Artifacts Path

```
get_artifacts_path(
  run_id = {run_id}
)
```

**Save:** `artifacts_path` from the response.

#### 2c. Process Session Artifacts

```
process_session_artifacts(
  run_id          = {run_id},
  sessions_id_list = {sessionsId}
)
```

This single tool handles downloading, extracting, and processing all session artifacts:
- Single-session (1 entry in sessionsId): produces `test-results.csv` and `jmeter.log`
- Multi-session (N entries): produces combined `test-results.csv` and `jmeter-1.log` through `jmeter-N.log`
- Built-in retry: each session retried up to 3 times automatically
- **Idempotent:** If status is `"partial"` or `"error"`, re-run with the same parameters.
  It skips completed sessions and retries only failed ones.

#### 2d. Get Public Report

```
get_public_report(
  test_run_id = {run_id}
)
```

**Save:** `public_url` from the response.

**Action:** Save the returned URL to `artifacts/{run_id}/blazemeter/public_report.json`:

```json
{"run_id": "{run_id}", "public_url": "{url}", "public_token": "{token}"}
```

This enables PerfReport to include a direct link to the BlazeMeter report.

#### 2e. Get Aggregate Report

```
get_aggregate_report(
  test_run_id = {run_id}
)
```

#### 2f. Analyze JMeter Logs (Optional)

**When:** Only if the JMeter MCP server is available.

```
analyze_jmeter_log(
  test_run_id = {run_id},
  log_source  = "blazemeter"
)
```

Discovers all `.log` files in `artifacts/{run_id}/blazemeter/` automatically.
Output files are used downstream by PerfAnalysis and PerfReport.
If the JMeter MCP server is not available, skip this step.

#### 2g. Validation

Verify these files exist before proceeding:

- `artifacts/{run_id}/blazemeter/aggregate_performance_report.csv`
- `artifacts/{run_id}/blazemeter/test-results.csv`
- `artifacts/{run_id}/blazemeter/jmeter.log` (single-session) OR `artifacts/{run_id}/blazemeter/jmeter-*.log` (multi-session)
- `artifacts/{run_id}/blazemeter/sessions/session_manifest.json`

**On error:** If API calls fail, retry up to 3 times. If retries fail, stop and report.
Do not proceed to the next workflow if BlazeMeter fails.

**Save forward:**
- `run_id` -> all downstream workflows
- `start_time` -> Datadog workflow
- `end_time` -> Datadog workflow

**Update task tracking:** Mark all BlazeMeter steps as completed.

---

### Step 3 — Datadog MCP Workflow

**Prerequisites:**
- `env_name` provided by the user
- `run_id` from BlazeMeter workflow
- `start_time` and `end_time` from BlazeMeter workflow
- BlazeMeter workflow must have completed successfully

Do not proceed until all prerequisites are met.

#### 3a. Load Environment

```
load_environment(
  env_name = {env_name}
)
```

This automatically loads the complete environment configuration, identifies the
environment type (host-based or k8s-based), and loads all resources with CPU/Memory specs.

**Save:** `env_type` = host-based or k8s-based from the response.

#### 3b. Get Infrastructure Metrics

**Decision gate — choose based on `env_type`:**

If host-based:

```
get_host_metrics(
  run_id     = {run_id},
  env_name   = {env_name},
  start_time = {start_time},
  end_time   = {end_time}
)
```

If k8s-based:

```
get_kubernetes_metrics(
  run_id     = {run_id},
  env_name   = {env_name},
  start_time = {start_time},
  end_time   = {end_time}
)
```

Metrics pulled should be CPU and Memory only.

#### 3c. Get Logs

```
get_logs(
  run_id     = {run_id},
  env_name   = {env_name},
  query_type = {query_type},
  start_time = {start_time},
  end_time   = {end_time}
)
```

Log query types: `"warnings"`, `"all_errors"`, `"api_errors"`, `"service_errors"`,
`"host_errors"`, `"kubernetes_errors"`, or `"custom"`.
Custom log queries are defined in `datadog-mcp/custom_queries.json` using "Keys" for `query_type`.

#### 3d. Get APM Traces

```
get_apm_traces(
  run_id     = {run_id},
  env_name   = {env_name},
  query_type = {query_type},
  start_time = {start_time},
  end_time   = {end_time}
)
```

APM query types: `"all_errors"`, `"service_errors"`, `"http_500_errors"`, `"http_errors"`,
`"slow_requests"`, or `"custom"`.
Custom APM queries are defined in `datadog-mcp/custom_queries.json` using "Keys" for `query_type`.

#### 3e. Get Custom KPI Metrics (Optional)

**When:** Only if the user provides a list of custom KPI query names.

```
get_kpi_timeseries(
  env_name    = {env_name},
  query_names = {list of query group keys},
  start_time  = {start_time},
  end_time    = {end_time},
  run_id      = {run_id},
  scope       = {scope}
)
```

- `query_names` is a list of query group keys from the `"kpi_queries"` section in
  `datadog-mcp/custom_queries.json` (e.g., `["cpu_usage", "memory_pressure"]`).
- `scope` is optional (`"host"` or `"k8s"`). If omitted, it is auto-detected from the
  loaded environment configuration.
- KPI queries can be template-based using placeholders (`{{service_name}}`, `{{env_tag}}`)
  or hard-coded.

#### 3f. Validation

Verify these files exist before proceeding:

- `artifacts/{run_id}/datadog/host_metrics_*.csv` OR `artifacts/{run_id}/datadog/k8s_metrics_*.csv`
- `artifacts/{run_id}/datadog/logs_*.csv` (optional)
- `artifacts/{run_id}/datadog/kpi_metrics_*.csv` (optional)

**On error:** If API calls fail, retry up to 3 times. If retries fail, stop and report.
Do not proceed to the next workflow if Datadog fails.

**Save forward:**
- `run_id` -> all downstream workflows
- `env_name` -> PerfAnalysis and PerfReport workflows

**Update task tracking:** Mark all Datadog steps as completed.

---

### Step 4 — PerfAnalysis MCP Workflow

**Prerequisites:**
- `test_run_id` = same as BlazeMeter `run_id`
- `environment` = same as Datadog `env_name`
- BlazeMeter workflow completed (required: `artifacts/{test_run_id}/blazemeter/aggregate_performance_report.csv`)
- Datadog workflow completed (required: `artifacts/{test_run_id}/datadog/host_metrics_*.csv` or `k8s_metrics_*.csv`)

Do not proceed until both BlazeMeter and Datadog workflows have completed successfully.

#### 4a. Analyze Test Results

```
analyze_test_results(
  test_run_id = {test_run_id}
)
```

This must run BEFORE steps 4b and 4c.
Requires: `artifacts/{test_run_id}/blazemeter/aggregate_performance_report.csv`

#### 4b. Analyze Environment Metrics

```
analyze_environment_metrics(
  test_run_id = {test_run_id},
  environment = {environment}
)
```

Requires: `artifacts/{test_run_id}/datadog/host_metrics_*.csv` or `k8s_metrics_*.csv`

#### 4c. Correlate Test Results

```
correlate_test_results(
  test_run_id = {test_run_id}
)
```

Requires: Outputs from steps 4a and 4b must be completed first.

#### 4d. Analyze Logs

```
analyze_logs(
  test_run_id = {test_run_id}
)
```

Requires:
- `artifacts/{test_run_id}/blazemeter/jmeter.log` (single-session) OR `jmeter-*.log` (multi-session)
- `artifacts/{test_run_id}/datadog/logs_*.csv`

#### 4e. Identify Bottlenecks

```
identify_bottlenecks(
  test_run_id = {test_run_id}
)
```

Performs bottleneck analysis and identifies the concurrency threshold where degradation begins.
Requires: `artifacts/{test_run_id}/blazemeter/test-results.csv`
Optional: `artifacts/{test_run_id}/datadog/k8s_metrics_*.csv`, `host_metrics_*.csv`, or `kpi_metrics_*.csv`

#### 4f. Validation

Verify these files exist before proceeding:

- `artifacts/{run_id}/analysis/performance_analysis.json`
- `artifacts/{run_id}/analysis/infrastructure_analysis.json`
- `artifacts/{run_id}/analysis/correlation_analysis.json`
- `artifacts/{run_id}/analysis/log_analysis.json`
- `artifacts/{run_id}/analysis/blazemeter_log_analysis.json`
- `artifacts/{run_id}/analysis/bottleneck_analysis.json`
- `artifacts/{run_id}/analysis/kpi_analysis.json`

**On error:** These are Python code executions (not API calls). Do NOT retry.
Report the error with: error message, missing file paths, expected vs. actual structure.
Do NOT attempt to fix code or modify files. Stop and report to user.

**Save forward:**
- `run_id` -> PerfReport workflow
- `env_name` -> PerfReport workflow

**Update task tracking:** Mark all PerfAnalysis steps as completed.

---

### Step 5 — PerfReport MCP Workflow

**Prerequisites:**
- `run_id` = same as PerfAnalysis `test_run_id`
- `env_name` = same as used in Datadog and PerfAnalysis (required for infrastructure charts)
- PerfAnalysis completed (required: `artifacts/{run_id}/analysis/performance_analysis.json`,
  `infrastructure_analysis.json`, `correlation_analysis.json`)

Do not proceed until PerfAnalysis has completed successfully.

#### 5a. Create Performance Test Report

```
create_performance_test_report(
  run_id   = {run_id},
  template = {template},
  format   = "md"
)
```

- Default format is Markdown (`"md"`), but can also generate PDF (`"pdf"`) or Word (`"docx"`).
- **Template selection:**
  - If regenerating an existing report, check `artifacts/{run_id}/reports/report_metadata_{run_id}.json`
    for the `template_used` field and pass that value as `template` to maintain consistency.
  - For new reports, optionally specify a template name for a custom template.
  - If no template is specified, defaults to `default_report_template.md`.

#### 5b. List Chart Types

```
list_chart_types()
```

This identifies the correct `chart_id` values for chart creation.

#### 5c. Create Infrastructure Charts

```
create_chart(
  run_id   = {run_id},
  chart_id = "CPU_CORES_LINE",
  env_name = {env_name}
)
```

```
create_chart(
  run_id   = {run_id},
  chart_id = "MEMORY_USAGE_LINE",
  env_name = {env_name}
)
```

These line charts show CPU and Memory utilization for all hosts/services.
Output: `CPU_CORES_LINE-{resource-name}.png`, `MEMORY_USAGE_LINE-{resource-name}.png`

#### 5d. Create Performance Charts

```
create_chart(
  run_id   = {run_id},
  chart_id = "RESP_TIME_P90_VUSERS_DUALAXIS"
)
```

This dual-axis chart shows correlation between P90 response time and virtual users over time.
Output: `RESP_TIME_P90_VUSERS_DUALAXIS.png`

#### 5e. Validation

Verify these files exist before proceeding:

- `artifacts/{run_id}/reports/performance_report_{run_id}.md`
- `artifacts/{run_id}/charts/*.png` (at least CPU, Memory, and P90 charts)

**On error:** These are Python code executions (not API calls). Do NOT retry.
Report the error with: error message, missing file paths, expected vs. actual structure.
Do NOT attempt to fix code or modify files. Stop and report to user.

**Save forward:**
- `run_id` -> Confluence workflow (if applicable)
- Report file paths -> Confluence workflow (if applicable)

**Update task tracking:** Mark all PerfReport steps as completed.

---

### Step 6 — Confluence MCP Workflow (Optional)

**When:** Only execute if Confluence details were provided in Collect Inputs.

**Prerequisites:**
- `test_run_id` = same as PerfReport `run_id`
- `confluence_mode` = `"cloud"` or `"onprem"`
- `confluence_space` = space name from user
- `parent_page_name` or `parent_page_id` from user
- PerfReport completed (required: `artifacts/{test_run_id}/reports/*.md`)

Do not proceed until all prerequisites are met and PerfReport has completed.

#### 6a. List Spaces (Optional)

```
list_spaces(
  mode = {confluence_mode}
)
```

Search for the space matching `confluence_space`. Extract `space_ref` (space_id for cloud,
space_key for onprem).

#### 6b. Get Space Details (Optional)

```
get_space_details(
  space_ref = {space_ref},
  mode      = {confluence_mode}
)
```

#### 6c. Locate Parent Page

**Decision gate:**

If `parent_page_id` is provided:

```
get_page_by_id(
  page_id = {parent_page_id},
  mode    = {confluence_mode}
)
```

If `parent_page_name` is provided:

```
list_pages(
  space_ref = {space_ref},
  mode      = {confluence_mode}
)
```

Search results for the page matching `parent_page_name`.

**Save:** `parent_id` = the parent page ID for use in step 6e.

#### 6d. Get Available Reports

```
get_available_reports(
  test_run_id = {test_run_id}
)
```

Select the report filename to publish (typically `performance_report_{test_run_id}.md`).

**Save:** `report_filename` from the selected report.

#### 6e. Create Confluence Page

```
create_page(
  space_ref   = {space_ref},
  test_run_id = {test_run_id},
  filename    = {report_filename},
  mode        = {confluence_mode},
  parent_id   = {parent_id},
  report_type = "single_run",
  title       = {optional custom title}
)
```

The tool converts Markdown to Confluence XHTML and creates the page nested under the parent.
If no title is provided, the title is extracted from the Markdown H1 heading.

**Save:** `page_ref` = returned page ID for use in steps 6f and 6g.

#### 6f. Attach Chart Images

```
attach_images(
  page_ref    = {page_ref},
  test_run_id = {test_run_id},
  mode        = {confluence_mode},
  report_type = "single_run"
)
```

Uploads ALL PNG chart images from `artifacts/{test_run_id}/charts/` to the page.
Check response for attached/failed counts. Continue even if some fail.

#### 6g. Update Page with Embedded Images

```
update_page(
  page_ref    = {page_ref},
  test_run_id = {test_run_id},
  mode        = {confluence_mode},
  report_type = "single_run"
)
```

Replaces `{{CHART_PLACEHOLDER: ID}}` markers with embedded `<ac:image>` markup.
Check response for `placeholders_replaced` and `placeholders_remaining`.

**Note on report_type:**
- This workflow uses `report_type: "single_run"` for individual test run reports.
- Comparison reports use `report_type: "comparison"` with `comparison_id` as the
  `test_run_id`. See `.cursor/skills/comparison-report-workflow/SKILL.md` for the
  comparison Confluence flow.

#### 6h. Validation

Verify:
- Page was created successfully (check for `page_ref` and URL in `create_page` response)
- Images were attached (check `attach_images` status: `"success"` or `"partial"`)
- Placeholders were replaced (check `update_page` `placeholders_replaced` list)

**On error:** If API calls fail, retry up to 3 times. If retries fail, report error but
continue (do not block other runs).

**Update task tracking:** Mark all Confluence steps as completed.

---

### Step 7 — Generate End-to-End Summary

**Input:** All data collected throughout the workflow.

**Action:** After all test runs are processed, generate a comprehensive summary.

#### 7a. File Locations Summary

For each test run, list all generated artifacts:

- BlazeMeter: `artifacts/{run_id}/blazemeter/`
- Datadog: `artifacts/{run_id}/datadog/`
- Analysis: `artifacts/{run_id}/analysis/`
- Reports: `artifacts/{run_id}/reports/`
- Charts: `artifacts/{run_id}/charts/`
- Confluence page URLs (if published)

#### 7b. Aggregate Metrics Summary

For each test run, provide aggregate metrics in a table:

**BlazeMeter Metrics:**
- Total samples
- Success rate (%)
- Average response time (ms)
- P90 response time (ms)
- P95 response time (ms)
- Peak throughput (req/sec)
- Error rate (%)

**Datadog Infrastructure Metrics:**
- Peak CPU Cores/mCPU Usage — per host or per k8s service
- Average CPU Cores/mCPU Usage — per host or per k8s service
- Peak Memory Usage MB/GB — per host or per k8s service
- Average Memory Usage MB/GB — per host or per k8s service

Do not include per-API breakdowns, only aggregate metrics.

#### 7c. Multiple Test Runs Comparison (if applicable)

If multiple test runs were processed, provide a side-by-side comparison table:
- Test run IDs
- Key performance metrics (response times, throughput, error rates)
- Infrastructure metrics (CPU/Memory KPIs)
- Notable differences or trends

---

### Step 8 — Final Task Status and Next Steps

**Action:** Display final task tracking status:

- Total test runs processed
- Completed workflows per test run
- Any failed steps (with error details)
- Overall workflow status (Success / Partial Success / Failed)

**Ask the user:**
- "Would you like to proceed with AI HITL report revision?" — If yes, follow the skill
  at `.cursor/skills/report-revision-workflow/SKILL.md`.
- "Would you like to create a comparison report across multiple test runs?" — If yes,
  follow the skill at `.cursor/skills/comparison-report-workflow/SKILL.md`.

---

## Error Handling

These rules apply to every step:

- **API-based workflows** (BlazeMeter, Datadog, Confluence):
  - Retry up to 3 times on transient failures
  - Wait 5-10 seconds between retries to prevent HTTP 429
  - If retries fail, stop and report to user

- **Code-based workflows** (PerfAnalysis, PerfReport):
  - Do NOT retry on failure
  - Report the error with: full error message, missing file paths, expected vs. actual structure
  - Do NOT attempt to fix code or modify MCP source files
  - Stop and report to user

- **Sequential execution:** Do not proceed to the next workflow if the current one fails.
- **Multiple test runs:** Process sequentially. Complete Run 1 fully before starting Run 2.
- Do NOT write code to fix MCP tool issues.
- Ask the user for next steps on any unrecoverable failure.
