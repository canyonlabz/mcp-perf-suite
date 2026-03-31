---
name: subagent-orchestrator
description: >-
  Orchestrates BlazeMeter and Datadog data extraction using dedicated subagents.
  Use when the user mentions subagent workflow, subagent orchestrator, or wants to
  run the BlazeMeter and Datadog extraction phases via subagents. This skill handles
  the extraction and handoff phases only — it does NOT run PerfAnalysis, PerfReport,
  or Confluence. After this skill completes, the user can continue with the
  performance-testing-workflow skill starting from Step 4 (PerfAnalysis).
---

# Subagent Orchestrator

## When to Use This Skill

- User wants to extract BlazeMeter results and Datadog metrics via subagents
- User mentions "subagent workflow", "subagent orchestrator", or "run the extractors"
- User wants to offload BlazeMeter and Datadog MCP work to subagents to save context

## What This Skill Does

1. Collects inputs from the user
2. Invokes the `blazemeter-extractor` subagent to populate `artifacts/{test_run_id}/blazemeter/`
3. Extracts timestamps via subagent return (primary) or `test_config.json` (fallback)
4. Invokes the `datadog-extractor` subagent to populate `artifacts/{test_run_id}/datadog/`
5. Writes an `orchestrator_manifest.json` with execution results
6. **STOPS** — does NOT proceed to PerfAnalysis, PerfReport, or Confluence

After this skill completes, the user can continue with the
`performance-testing-workflow` skill starting from **Step 4 (PerfAnalysis)**.

## Architecture

```
User Prompt (test_run_id, env_name, ...)
  │
  ▼
Orchestrator (this skill)
  │
  ├── blazemeter-extractor subagent
  │     └── artifacts/{test_run_id}/blazemeter/
  │           ├── test-results.csv
  │           ├── aggregate_performance_report.csv
  │           ├── test_config.json
  │           ├── jmeter.log (or jmeter-*.log)
  │           ├── public_report.json
  │           ├── sessions/session_manifest.json
  │           └── subagent_manifest.json
  │
  ├── [extract start_time / end_time]
  │
  ├── datadog-extractor subagent
  │     └── artifacts/{test_run_id}/datadog/
  │           ├── host_metrics_*.csv or k8s_metrics_*.csv
  │           ├── logs_*.csv
  │           ├── apm_traces_*.csv (if traces exist)
  │           ├── kpi_metrics_*.csv (if requested)
  │           └── subagent_manifest.json
  │
  └── orchestrator_manifest.json
        └── artifacts/{test_run_id}/orchestrator_manifest.json
```

## Platform Notes

**`mcpServers` YAML field:** Confirmed that Cursor does NOT enforce the `mcpServers`
field in subagent frontmatter. Both subagents see all configured MCP servers. Tool
isolation is enforced via prompt-level instructions in each subagent's system prompt.
The `mcpServers` field is retained in the YAML for forward compatibility and for
Claude Code users where it IS enforced.

---

## Execution

Follow these steps exactly, in order.

---

### Step 1 — Collect Inputs

Ask the user for the following values. Do not proceed until all required values are collected.

```
REQUIRED:
  test_run_id = [BlazeMeter test run ID — e.g., "12345678"]
  env_name    = [Datadog environment name — e.g., "QA", "UAT"]

OPTIONAL:
  test_name       = [informational label for the test run]
  log_query_type  = [Datadog log query type — default: "all_errors"]
  apm_query_type  = [Datadog APM query type — default: "all_errors"]
  kpi_query_names = [list of KPI query group keys — default: none]
```

---

### Step 2 — Initialize Task Tracking

Create task items to monitor progress:

- BlazeMeter subagent invocation
- Timestamp handoff (primary + fallback)
- Datadog subagent invocation
- Orchestrator manifest generation

---

### Step 3 — Invoke BlazeMeter Subagent

**Action:** Invoke the `blazemeter-extractor` subagent with the following prompt:

```
Extract BlazeMeter test results for test_run_id: {test_run_id}.
{Include test_name if provided: "Test name: {test_name}"}

Follow all instructions in your system prompt including writing the
subagent_manifest.json file.
```

**After the subagent returns:**

1. Parse the JSON block from the subagent's response
2. Record the full JSON response for the orchestrator manifest
3. Extract `status`, `start_time`, `end_time`, and `notes`
4. Record whether JSON parsing succeeded or failed

**Save:**
- `bz_status` = parsed `status` value
- `bz_start_time` = parsed `start_time` value (may be null)
- `bz_end_time` = parsed `end_time` value (may be null)
- `bz_return_json` = the full parsed JSON object

If `bz_status` is `"failed"`, warn the user but continue to Step 4 to attempt the
fallback timestamp mechanism.

---

### Step 4 — Timestamp Handoff (Primary + Fallback)

This step uses two approaches for getting timestamps. Record results for both.

#### 4a. Primary Approach — From Subagent Return JSON

Check if `bz_start_time` and `bz_end_time` from Step 3 are non-null and valid ISO 8601.

**Record:**
- `primary_handoff_success` = true/false
- `primary_start_time` = value or null
- `primary_end_time` = value or null

#### 4b. Fallback Approach — From test_config.json File

Attempt to read `artifacts/{test_run_id}/blazemeter/test_config.json`.

If the file exists, extract `start_time` and `end_time` from it.

**Note:** The `test_config.json` format may differ from ISO 8601 (e.g.,
`"2026-02-26 07:42:33 UTC"` instead of `"2026-02-26T07:42:33Z"`). Normalize to
ISO 8601 before passing to Datadog if using the fallback.

**Record:**
- `fallback_file_exists` = true/false
- `fallback_start_time` = value or null
- `fallback_end_time` = value or null

#### 4c. Determine Effective Timestamps

Use the primary approach values if available. Fall back to the file-based values
if the primary approach returned null. If both are null, record the failure.

**Record:**
- `effective_start_time` = the value that will be passed to Datadog
- `effective_end_time` = the value that will be passed to Datadog
- `timestamp_source` = `"subagent_return"` or `"test_config_file"` or `"none"`

If `timestamp_source` is `"none"`, warn the user that Datadog extraction cannot
proceed without timestamps. Stop and report the failure.

---

### Step 5 — Invoke Datadog Subagent

**Action:** Invoke the `datadog-extractor` subagent with the following prompt:

```
Extract Datadog metrics for the following test run:

  test_run_id: {test_run_id}
  env_name:    {env_name}
  start_time:  {effective_start_time}
  end_time:    {effective_end_time}
  {Include if provided: "log_query_type: {log_query_type}"}
  {Include if provided: "apm_query_type: {apm_query_type}"}
  {Include if provided: "kpi_query_names: {kpi_query_names}"}

Follow all instructions in your system prompt including writing the
subagent_manifest.json file.
```

**After the subagent returns:**

1. Parse the JSON block from the subagent's response
2. Record the full JSON response for the orchestrator manifest
3. Extract `status`, `env_type`, and `notes`
4. Record whether JSON parsing succeeded or failed

**Save:**
- `dd_status` = parsed `status` value
- `dd_return_json` = the full parsed JSON object

---

### Step 6 — Write Orchestrator Manifest

Write `artifacts/{test_run_id}/orchestrator_manifest.json` with the following structure:

```json
{
  "orchestrator": "subagent-orchestrator",
  "orchestrator_version": "1.0.0",
  "test_run_id": "<test_run_id>",
  "env_name": "<env_name>",
  "execution_timestamp": "<ISO 8601 UTC>",
  "subagents": {
    "blazemeter": {
      "invocation_success": "<true | false>",
      "return_json_parsed": "<true | false>",
      "return_json": "<full bz_return_json or null>",
      "subagent_manifest_exists": "<true | false — check artifacts/{test_run_id}/blazemeter/subagent_manifest.json>"
    },
    "timestamp_handoff": {
      "primary_approach": {
        "source": "subagent_return",
        "success": "<true | false>",
        "start_time": "<value or null>",
        "end_time": "<value or null>"
      },
      "fallback_approach": {
        "source": "test_config_file",
        "file_exists": "<true | false>",
        "success": "<true | false>",
        "start_time": "<value or null>",
        "end_time": "<value or null>"
      },
      "effective_source": "<subagent_return | test_config_file | none>",
      "effective_start_time": "<value or null>",
      "effective_end_time": "<value or null>"
    },
    "datadog": {
      "invocation_success": "<true | false>",
      "return_json_parsed": "<true | false>",
      "return_json": "<full dd_return_json or null>",
      "subagent_manifest_exists": "<true | false — check artifacts/{test_run_id}/datadog/subagent_manifest.json>"
    }
  },
  "artifact_validation": {
    "blazemeter_folder_exists": "<true | false>",
    "blazemeter_files": {
      "test_results_csv": "<true | false>",
      "aggregate_performance_report_csv": "<true | false>",
      "test_config_json": "<true | false>",
      "jmeter_log": "<true | false>",
      "session_manifest_json": "<true | false>",
      "public_report_json": "<true | false>"
    },
    "datadog_folder_exists": "<true | false>",
    "datadog_files": {
      "infrastructure_metrics_csv": "<true | false>",
      "logs_csv": "<true | false>",
      "apm_traces_csv": "<true | false>",
      "kpi_metrics_csv": "<true | false | not_applicable>"
    }
  },
  "overall_assessment": {
    "blazemeter_extraction": "success | partial | failed | not_attempted",
    "datadog_extraction": "success | partial | failed | not_attempted",
    "ready_for_perfanalysis": "<true | false>"
  }
}
```

---

### Step 7 — Report Results to User

Present a clear summary to the user:

1. **BlazeMeter Subagent Results**
   - Status (success/partial/failed)
   - Files written to `artifacts/{test_run_id}/blazemeter/`
   - Any errors or warnings

2. **Timestamp Handoff Results**
   - Which approach worked (primary, fallback, both, neither)
   - Effective timestamps used

3. **Datadog Subagent Results**
   - Status (success/partial/failed)
   - Files written to `artifacts/{test_run_id}/datadog/`
   - Any errors or warnings

4. **Overall Assessment**
   - Are artifacts ready for PerfAnalysis?

5. **Manifest Locations**
   - `artifacts/{test_run_id}/orchestrator_manifest.json`
   - `artifacts/{test_run_id}/blazemeter/subagent_manifest.json`
   - `artifacts/{test_run_id}/datadog/subagent_manifest.json`

6. **Next Steps**
   - If artifacts are ready, the user can continue with the `performance-testing-workflow`
     skill starting from **Step 4 (PerfAnalysis)** to complete the pipeline.

---

## Error Handling

- If a subagent fails to invoke entirely, record it in the orchestrator manifest and
  continue to the next step.
- If JSON parsing of a subagent return fails, record the raw text response in the
  manifest under a `raw_response` field.
- Do NOT retry subagent invocations. Each subagent handles its own retries internally.
- Do NOT modify any existing Rules, Skills, or MCP source code.
- If the orchestrator itself encounters an error writing the manifest, report the
  error directly to the user with the full error message.

---

## Related Files

- **Production E2E orchestration skill:** `.cursor/skills/performance-testing-workflow/SKILL.md`
- **BlazeMeter subagent:** `.cursor/agents/blazemeter-extractor.md`
- **Datadog subagent:** `.cursor/agents/datadog-extractor.md`
- **MCP error handling rules:** `.cursor/rules/mcp-error-handling.mdc`
- **Skill execution rules:** `.cursor/rules/skill-execution-rules.mdc`
- **Prerequisites:** `.cursor/rules/prerequisites.mdc`
