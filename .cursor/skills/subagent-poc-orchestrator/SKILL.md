---
name: subagent-poc-orchestrator
description: >-
  TEMPORARY proof-of-concept orchestrator for testing BlazeMeter and Datadog subagents.
  Use when the user mentions subagent testing, subagent POC, or wants to test the
  blazemeter-extractor and datadog-extractor subagents. This skill does NOT run the
  full E2E pipeline — it only tests the BlazeMeter and Datadog extraction phases via
  subagents and writes a debug manifest with findings.
---

# Subagent Proof-of-Concept Orchestrator

> **STATUS: TEMPORARY / PROOF-OF-CONCEPT**
> This skill exists solely to test the `blazemeter-extractor` and `datadog-extractor`
> subagents. It does NOT replace the production `performance-testing-workflow` skill.
> Do NOT use this for production workflows. 

## When to Use This Skill

- User explicitly asks to test the subagent POC
- User mentions "subagent testing", "test the extractors", or "subagent proof-of-concept"
- User wants to validate that BlazeMeter and Datadog subagents work correctly

## What This Skill Does

1. Collects inputs from the user
2. Invokes the `blazemeter-extractor` subagent
3. Tests two timestamp handoff approaches (subagent return vs. file read)
4. Invokes the `datadog-extractor` subagent
5. Writes an orchestrator-level `debug_manifest.json` with all findings
6. **STOPS** — does NOT proceed to PerfAnalysis, PerfReport, or Confluence

## What This Skill Tests

| Test Area | What We're Validating |
|-----------|----------------------|
| Subagent invocation | Can the orchestrator successfully invoke custom subagents? |
| `mcpServers` YAML field | Does Cursor respect the `mcpServers` field in subagent frontmatter? |
| MCP tool execution | Can subagents call BlazeMeter/Datadog MCP tools autonomously? |
| JSON return parsing | Can the orchestrator parse structured JSON from subagent responses? |
| Timestamp handoff (primary) | Can `start_time`/`end_time` be extracted from the subagent's return JSON? |
| Timestamp handoff (fallback) | Can the orchestrator read `test_config.json` as a fallback? |
| Artifact validation | Did the subagents write the expected files to the artifacts folder? |
| Debug manifest output | Did each subagent write its own `debug_manifest.json`? |

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

Create task items to monitor POC progress:

- BlazeMeter subagent invocation
- Timestamp handoff testing (primary + fallback)
- Datadog subagent invocation
- Orchestrator debug manifest generation

---

### Step 3 — Invoke BlazeMeter Subagent

**Action:** Invoke the `blazemeter-extractor` subagent with the following prompt:

```
Extract BlazeMeter test results for test_run_id: {test_run_id}.
{Include test_name if provided: "Test name: {test_name}"}

This is a BETA test of the subagent system. Follow all instructions in your
system prompt including writing the debug_manifest.json file. Pay special
attention to documenting whether the mcpServers YAML field was respected
(i.e., were only BlazeMeter MCP tools visible to you, or could you see
all MCP tools?).
```

**After the subagent returns:**

1. Parse the JSON block from the subagent's response
2. Record the full JSON response for the debug manifest
3. Extract `status`, `start_time`, `end_time`, and `notes`
4. Record whether JSON parsing succeeded or failed

**Save:**
- `bz_status` = parsed `status` value
- `bz_start_time` = parsed `start_time` value (may be null)
- `bz_end_time` = parsed `end_time` value (may be null)
- `bz_return_json` = the full parsed JSON object

If `bz_status` is `"failed"`, warn the user but continue to Step 4 to test the
fallback mechanism. Datadog subagent may still fail, but the debug data is valuable.

---

### Step 4 — Test Timestamp Handoff (Primary + Fallback)

This step tests BOTH approaches for getting timestamps. Record results for both.

#### 4a. Primary Approach — From Subagent Return JSON

Check if `bz_start_time` and `bz_end_time` from Step 3 are non-null and valid ISO 8601.

**Record:**
- `primary_handoff_success` = true/false
- `primary_start_time` = value or null
- `primary_end_time` = value or null

#### 4b. Fallback Approach — From test_config.json File

Attempt to read `artifacts/{test_run_id}/blazemeter/test_config.json`.

If the file exists, extract `start_time` and `end_time` from it.

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
proceed without timestamps. Still attempt to invoke the Datadog subagent to test
subagent invocation itself, but expect it to fail.

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

This is a BETA test of the subagent system. Follow all instructions in your
system prompt including writing the debug_manifest.json file. Pay special
attention to documenting whether the mcpServers YAML field was respected
(i.e., were only Datadog MCP tools visible to you, or could you see
all MCP tools?).
```

**After the subagent returns:**

1. Parse the JSON block from the subagent's response
2. Record the full JSON response for the debug manifest
3. Extract `status`, `env_type`, and `notes`
4. Record whether JSON parsing succeeded or failed

**Save:**
- `dd_status` = parsed `status` value
- `dd_return_json` = the full parsed JSON object

---

### Step 6 — Write Orchestrator Debug Manifest

Write `artifacts/{test_run_id}/debug_manifest.json` with the following structure:

```json
{
  "orchestrator": "subagent-poc-orchestrator",
  "orchestrator_version": "0.1.0-beta",
  "test_run_id": "<test_run_id>",
  "env_name": "<env_name>",
  "execution_timestamp": "<ISO 8601 UTC>",
  "poc_tests": {
    "blazemeter_subagent": {
      "invocation_success": "<true | false>",
      "return_json_parsed": "<true | false>",
      "return_json": "<full bz_return_json or null>",
      "subagent_debug_manifest_exists": "<true | false — check artifacts/{test_run_id}/blazemeter/debug_manifest.json>"
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
    "datadog_subagent": {
      "invocation_success": "<true | false>",
      "return_json_parsed": "<true | false>",
      "return_json": "<full dd_return_json or null>",
      "subagent_debug_manifest_exists": "<true | false — check artifacts/{test_run_id}/datadog/debug_manifest.json>"
    },
    "mcpServers_field": {
      "tested": true,
      "blazemeter_respected": "<value from bz debug manifest or unknown>",
      "datadog_respected": "<value from dd debug manifest or unknown>"
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
    "subagent_system_works": "<true | false | inconclusive>",
    "ready_for_perfanalysis": "<true | false — are artifacts in place for PerfAnalysis?>",
    "recommendations": "<free text — what worked, what needs refinement>"
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

4. **`mcpServers` Field Test Results**
   - Whether each subagent reported the field was respected

5. **Overall Assessment**
   - Are artifacts ready for PerfAnalysis?
   - Recommendations for next steps

6. **Debug Manifest Locations**
   - `artifacts/{test_run_id}/debug_manifest.json` (orchestrator)
   - `artifacts/{test_run_id}/blazemeter/debug_manifest.json` (BlazeMeter subagent)
   - `artifacts/{test_run_id}/datadog/debug_manifest.json` (Datadog subagent)

**Remind the user:** This is a POC test. If the artifacts look correct, the user can
manually invoke the `performance-testing-workflow` skill starting from Step 4
(PerfAnalysis) to continue the pipeline and validate end-to-end compatibility.

---

## Error Handling

- If a subagent fails to invoke entirely, record it in the debug manifest and continue
  to the next step. The goal is to capture maximum diagnostic information.
- If JSON parsing of a subagent return fails, record the raw text response in the debug
  manifest under a `raw_response` field.
- Do NOT retry subagent invocations. Each subagent handles its own retries internally.
- Do NOT modify any existing Rules, Skills, or MCP source code.
- If the orchestrator itself encounters an error writing the debug manifest, report the
  error directly to the user with the full error message.

---

## Related Files

These are reference files only. Do NOT modify them as part of this POC.

- **Production orchestration skill:** `.cursor/skills/performance-testing-workflow/SKILL.md`
- **BlazeMeter subagent:** `.cursor/agents/blazemeter-extractor.md`
- **Datadog subagent:** `.cursor/agents/datadog-extractor.md`
- **MCP error handling rules:** `.cursor/rules/mcp-error-handling.mdc`
- **Skill execution rules:** `.cursor/rules/skill-execution-rules.mdc`
- **Prerequisites:** `.cursor/rules/prerequisites.mdc`
