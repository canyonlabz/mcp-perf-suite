---
name: jmeter-debugging
description: >-
  Iterative AI-driven JMeter script debugging via smoke tests, log analysis, and
  targeted fixes. Use when the user asks to debug, troubleshoot, fix errors in, or
  validate a JMeter script, or mentions JMeter smoke testing failures.
---

# JMeter Script Debugging

## When to Use This Skill

- User explicitly asks to debug, troubleshoot, or fix a JMeter script
- User reports errors from a JMeter smoke test or test execution
- User wants to validate that a JMeter script runs cleanly
- Never start this workflow unless the user explicitly requests it

---

## Reference

This section provides context for humans and capable models. For the step-by-step
execution instructions, skip to the **Execution** section below.

### How Debugging Works

This workflow mirrors how an experienced performance test engineer debugs a script:

1. Run a 1/1/1 smoke test
2. Analyze the log to find the **first** failure
3. Attach a debug post-processor to capture full request/response details
4. Re-run to capture verbose debug data
5. Diagnose root cause from the debug output
6. Apply a single targeted fix
7. Re-test — if clean, done. If not, repeat from step 1.

Maximum **5 iterations**. If not resolved after 5 cycles, stop and report.

### Common Diagnosis Patterns

**Missing or stale correlation values** (`NOT_FOUND` in request body or URL):
- A dynamic value was not extracted from a prior response
- Fix: Add a JSON, Regex, or Boundary extractor to the correct sampler

**Extractor on the wrong sampler** (common in OAuth/SSO flows):
- The extractor logic is correct but placed under the wrong HTTP sampler
- Fix: Remove from wrong sampler, add to the correct one

**Wrong request body or parameterization:**
- Hardcoded values that should be parameterized
- Fix: Use `edit_jmeter_component` with `replace_in_body`

**Auth token or session issues:**
- Bearer token, CSRF token, or session cookie not passed correctly
- Fix: Verify extractors are on the correct sampler in the auth chain

**Server-side validation errors** (application error in response body):
- Request data invalid from server's perspective (duplicate, expired)
- Fix: Report to user — may need test data adjustments, not script fixes

### Debug Manifest

A markdown file maintained throughout debugging to log all issues and fixes.

**Location:** `artifacts/{test_run_id}/analysis/debug_manifest.md`

The manifest is created at the start, appended after each iteration, and finalized
when debugging completes. See the Execution section for the exact templates.

### PerfMemory Integration

This workflow integrates with the PerfMemory lessons-learned memory layer. Before
starting a debug loop, the agent searches for similar past issues. During debugging,
each attempt is stored so future agents can learn from it. See the `perfmemory` skill
for full details on PerfMemory tools and workflows.

**Memory is advisory** — if the PerfMemory MCP server is unavailable, skip all
memory-related steps and proceed with normal debugging. Do not block debugging
because memory is down.

### Related Rules

- **`prerequisites.mdc`** — `test_run_id` and artifact structure validation
- **`skill-execution-rules.mdc`** — Follow steps in order, do not skip
- **`mcp-error-handling.mdc`** — MCP tool error handling
- **`jmeter-script-guardrails.mdc`** — Smoke test = 1/1/1, one fix at a time, max 5 iterations, stop on environment issues

---

## Execution

This is an **iterative workflow**. Steps 3-8 repeat until the script is clean or
the iteration limit (5) is reached.

---

### Collect Inputs

Ask the user for the following values. Do not proceed until all required values are collected.

```
REQUIRED:
  test_run_id = [ask user — must have an existing JMX in artifacts/{test_run_id}/jmeter/]
```

---

### Step 0.5 — Memory Check (PerfMemory)

**Input:** `test_run_id`

**Action:** Before starting the debug loop, check if this system has known issues in
memory. This is a broad check to pre-load context — specific symptom searches happen
at Step 5.

0.5a. Search for past sessions related to this system:

```
find_similar_attempts(
  symptom_text      = "JMeter script debugging for {system_under_test}",
  system_under_test = {system_under_test}
)
```

0.5b. If results are returned (any similarity), note the top matches for context.
These give the agent awareness of what types of issues have been seen before on this
system (e.g., "this system commonly has OAuth correlation issues").

0.5c. If no results or PerfMemory is unavailable, proceed normally — this step is
advisory only.

**Save:** `memory_context` (list of top match summaries, or empty)

---

### Step 1 — Create Debug Manifest

**Input:** `test_run_id`

**Action:** Create the file `artifacts/{test_run_id}/analysis/debug_manifest.md` with:

```markdown
# Debug Manifest

- **Test Run ID**: {test_run_id}
- **Script**: {jmx_filename}
- **Started**: {current timestamp YYYY-MM-DD HH:MM:SS}
- **Status**: In Progress

---
```

**Save:** `iteration_count` = 0

---

### Step 1.5 — Open PerfMemory Session

**Input:** `test_run_id`, `jmx_filename`

**Action:** Open a debug session in PerfMemory to track this debugging effort.

```
store_debug_session(
  system_under_test = {system_under_test},
  test_run_id       = {test_run_id},
  script_name       = {jmx_filename},
  auth_flow_type    = {if known from script analysis, otherwise omit},
  environment       = {if known, otherwise omit},
  created_by        = "cursor"
)
```

**Save:** `pm_session_id` from the response.

If PerfMemory is unavailable, set `pm_session_id` = null and skip all subsequent
PerfMemory steps.

---

### Step 2 — Enforce 1/1/1 Thread Configuration

**Input:** `test_run_id`

**Action:** Call `analyze_jmeter_script` to find the Thread Group node. The tool
automatically exports the structure to versioned files under
`artifacts/{test_run_id}/jmeter/analysis/`.

```
analyze_jmeter_script(
  test_run_id  = {test_run_id},
  detail_level = "detailed"
)
```

**Save:** `exported_files` from the response — contains paths to the persisted
`jmx_structure_*.json` and `.md` files. For large scripts, read the JSON file for
node lookups instead of relying on the in-context response.

**Check** the Thread Group properties. If not set to 1/1/1, override:

```
edit_jmeter_component(
  test_run_id    = {test_run_id},
  target_node_id = {thread_group_node_id},
  operations     = [
    {"op": "set_prop", "name": "ThreadGroup.num_threads", "value": "1"},
    {"op": "set_prop", "name": "ThreadGroup.ramp_time", "value": "1"},
    {"op": "set_prop", "name": "LoopController.loops", "value": "1"}
  ],
  dry_run = false
)
```

---

### Step 3 — Run Smoke Test

**Input:** `test_run_id`

**Action:**

3a. List scripts to get the JMX path:

```
list_jmeter_scripts(
  test_run_id = {test_run_id}
)
```

**Save:** `jmx_path` from the response.

3b. Start the test:

```
start_jmeter_test(
  test_run_id = {test_run_id},
  jmx_path    = {jmx_path}
)
```

**Save:** `pid` from the response.

3c. Monitor and stop early on errors:

```
get_jmeter_run_status(
  test_run_id = {test_run_id},
  pid         = {pid}
)
```

Poll every few seconds. When errors appear (error rate > 0%), **verify errors in the
JTL before stopping**:

1. Read the JTL file at `artifacts/{test_run_id}/jmeter/test-results.csv`
2. Search for any row where the `success` column is `false`
3. **If `success=false` rows exist:** Errors are confirmed. Stop the test immediately.
4. **If NO `success=false` rows exist:** The error_rate was a transient JTL parsing
   artifact (race condition from reading the CSV while JMeter is mid-write). Ignore
   the error and continue polling.

The `metrics.error_rate` from `get_jmeter_run_status` can report false positives
due to this JTL read race condition. Always verify against the JTL source of truth.

Once errors are confirmed in the JTL, stop the test:

```
stop_jmeter_test(
  test_run_id = {test_run_id}
)
```

After stopping, wait a few seconds for JMeter threads to wind down before proceeding
to log analysis. Thread shutdown is not instantaneous.

If the test completes on its own with 0% errors, proceed directly to Step 4.

**Fallback:** Only kill the PID if `stop_jmeter_test` fails to stop the test.

---

### Step 4 — Analyze Log

**Input:** `test_run_id`

**Action:** Call `analyze_jmeter_log` with `log_source="jmeter"` (not the default):

```
analyze_jmeter_log(
  test_run_id = {test_run_id},
  log_source  = "jmeter"
)
```

**Save:** `error_rate` and `first_failing_sampler` from the response.

---

### Step 5 — Triage

**Input:** `error_rate`, `first_failing_sampler`, log analysis output

**Decision gate — choose ONE path:**

**Path A — Script is clean (0% error rate):**
- Go to Step 9 (Cleanup).

**Path B — Environment/systemic issue (stop immediately):**
If ANY of these are true, stop debugging and go to Step 10 (Report):
- HTTP 401/403 on login/auth samplers
- HTTP 5xx on all or most samplers
- Connection refused/timeout on all samplers
- Repeated identical errors across all samplers

**Path C — Script issue (continue debugging):**
If errors are isolated to specific samplers:

5d. **Memory-assisted triage** — Before proceeding to Step 6, search PerfMemory for
this specific symptom (skip if `pm_session_id` is null):

```
find_similar_attempts(
  symptom_text      = {build structured symptom from the error — see perfmemory skill
                       for the template},
  system_under_test = {system_under_test},
  error_category    = {error category from log analysis}
)
```

**If `recommendation` = `apply_known_fix` (similarity > 0.85):**
- Skip Step 6 and Step 7 — apply the known fix directly at Step 8
- Save `matched_attempt_id` from the top match for Step 8e

**If `recommendation` = `review_suggestions` (similarity 0.60 - 0.85):**
- Present the top matches to the user for review
- If user approves a suggestion, apply it at Step 8 and save `matched_attempt_id`
- If user declines, continue to Step 6 as normal

**If `recommendation` = `no_match`:**
- Continue to Step 6 as normal.

---

### Step 6 — Attach Debug Post-Processor

**Input:** `test_run_id`, `first_failing_sampler` node_id

**Action:**

6a. Enable verbose logging:

```
edit_jmeter_component(
  test_run_id    = {test_run_id},
  target_node_id = {udv_node_id},
  operations     = [{"op": "set_prop", "name": "VERBOSE_LOGGING", "value": "true"}],
  dry_run        = false
)
```

6b. Add the built-in debug post-processor to the first failing sampler:

```
add_jmeter_component(
  test_run_id    = {test_run_id},
  component_type = "jsr223_debug_postprocessor",
  parent_node_id = {first_failing_sampler_node_id},
  component_config = {},
  dry_run        = false
)
```

**Save:** `debug_postprocessor_node_id` from the response.

---

### Step 7 — Debug Smoke Test and Diagnose

**Input:** `test_run_id`

**Action:**

7a. Re-run the smoke test (same as Step 3, including early stop on errors).

7b. Run `analyze_jmeter_log(test_run_id, log_source="jmeter")` again.

7c. Read the raw JMeter log at `artifacts/{test_run_id}/jmeter/{test_run_id}.log`.
Search for lines containing `[ERROR]:[DEBUG]:` — these contain the verbose
request/response details from the debug post-processor.

**Diagnose** the root cause using the debug output. See the Common Diagnosis Patterns
in the Reference section.

---

### Step 8 — Apply Fix and Iterate

**Input:** `test_run_id`, diagnosis from Step 7

**Action:**

8a. Apply a **single** targeted fix using `add_jmeter_component` or `edit_jmeter_component`.
Always use `dry_run=true` first, then `dry_run=false` to apply.

8b. Re-analyze the script to verify structure. This also refreshes the persisted
structure files so the latest node_ids are available on disk:

```
analyze_jmeter_script(
  test_run_id  = {test_run_id},
  detail_level = "summary"
)
```

8c. Increment `iteration_count` = `iteration_count` + 1

8d. Append to the debug manifest:

```markdown
## Iteration {iteration_count} — {current timestamp}

### Error Identified
- **Sampler**: {sampler_name}
- **Response Code**: {code}
- **Error Message**: {message}

### Diagnosis
{description of root cause}

### Fix Applied
{description of fix and which component was added/edited}

### Result After Fix
{to be filled after re-test}
Completed at {current timestamp}.
```

8e. **Store attempt in PerfMemory** (skip if `pm_session_id` is null):

```
store_debug_attempt(
  session_id         = {pm_session_id},
  iteration_number   = {iteration_count},
  symptom_text       = {structured symptom — see perfmemory skill for template},
  outcome            = {resolved | failed | environment_issue | test_data_issue |
                        authentication_issue | needs_investigation},
  error_category     = {from log analysis},
  severity           = {Critical | High | Medium},
  response_code      = {HTTP status code or exception},
  hostname           = {hostname where error occurred},
  sampler_name       = {failing sampler name},
  api_endpoint       = {failing URL},
  diagnosis          = {root cause from Step 7},
  fix_description    = {what was applied in Step 8a},
  fix_type           = {add_extractor | move_extractor | edit_request_body |
                        edit_header | edit_correlation | other},
  component_type     = {json_extractor | regex_extractor | jsr223_postprocessor |
                        jsr223_preprocessor | http_sampler | test_plan | other},
  matched_attempt_id = {if a memory match was applied, its attempt_id — otherwise omit}
)
```

**Save:** `last_attempt_id` from the response.

8f. **Decision gate:**

- If `iteration_count` >= 5: Go to Step 10 (Report) with status "Iteration Limit Reached".
- If `iteration_count` < 5: Go back to **Step 3** (run a fresh smoke test).

---

### Step 9 — Cleanup (script is clean)

**Input:** `test_run_id`, `debug_postprocessor_node_id`(s)

**Action:**

9a. Disable each debug post-processor (do NOT delete):

```
edit_jmeter_component(
  test_run_id    = {test_run_id},
  target_node_id = {debug_postprocessor_node_id},
  operations     = [{"op": "toggle_enabled"}],
  dry_run        = false
)
```

9b. Set verbose logging back to false:

```
edit_jmeter_component(
  test_run_id    = {test_run_id},
  target_node_id = {udv_node_id},
  operations     = [{"op": "set_prop", "name": "VERBOSE_LOGGING", "value": "false"}],
  dry_run        = false
)
```

9c. Run one final 1/1/1 smoke test (same as Step 3) to confirm the script is clean
with debug artifacts disabled. This validation run should complete fully since we
expect 0% errors. If errors still appear, stop the test early and return to Step 5.

9d. Go to Step 10 (Report) with status "Resolved".

---

### Step 10 — Finalize and Report

**Input:** `test_run_id`, `iteration_count`, final status

**Action:**

10a. Update the debug manifest header Status and append:

```markdown
## Final Summary
- **Started**: {start timestamp}
- **Completed**: {current timestamp}
- **Total Duration**: {elapsed time}
- **Total Iterations**: {iteration_count}
- **Final Status**: {Resolved | Needs Human Intervention | Iteration Limit Reached}
- **Fixes Applied**:
  1. {fix description}
  2. {fix description}
```

10b. **Close PerfMemory session** (skip if `pm_session_id` is null):

```
close_debug_session(
  session_id            = {pm_session_id},
  final_outcome         = {resolved | unresolved | environment_issue |
                           test_data_issue | authentication_issue |
                           iteration_limit_reached | needs_investigation},
  resolution_attempt_id = {last_attempt_id if resolved, otherwise omit},
  notes                 = {brief summary of outcome}
)
```

10c. Tell the user:
- Total debug iterations and elapsed time
- Fixes applied (sampler name, issue, resolution)
- Final smoke test result
- If resolved: the script is ready for load testing or BlazeMeter upload
- If not resolved: remaining errors and recommendation for manual investigation
- Debug manifest location: `artifacts/{test_run_id}/analysis/debug_manifest.md`
- Whether lessons were stored in PerfMemory (and session_id for reference)

---

## Error Handling

These rules apply to every step:

- Smoke tests MUST use **1 thread, 1 second ramp-up, 1 loop**. No exceptions.
- Fix only the **first** failing sampler per iteration. Do not batch-fix.
- Always use `dry_run=true` before applying any edit.
- Maximum **5 debug iterations**. Stop and report if not resolved.
- If errors indicate environment/infrastructure issues, **stop immediately** and report.
- Always use `log_source="jmeter"` for local smoke tests (not the default `"blazemeter"`).
- Do NOT write code to fix MCP tool issues.
- Always maintain the debug manifest throughout the workflow.
- PerfMemory is **advisory only** — if any PerfMemory tool call fails, log the error
  and continue debugging. Never block the debug loop because memory is unavailable.
- If `pm_session_id` is null, skip all PerfMemory steps (0.5, 1.5, 5d, 8e, 10b).
