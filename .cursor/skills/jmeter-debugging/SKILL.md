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

### Step 2 — Enforce 1/1/1 Thread Configuration

**Input:** `test_run_id`

**Action:** Call `analyze_jmeter_script` to find the Thread Group node:

```
analyze_jmeter_script(
  test_run_id  = {test_run_id},
  detail_level = "detailed"
)
```

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

3c. Monitor until complete:

```
get_jmeter_run_status(
  test_run_id = {test_run_id},
  pid         = {pid}
)
```

Poll every few seconds until the test finishes.

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
If errors are isolated to specific samplers, continue to Step 6.

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

7a. Re-run the smoke test (same as Step 3).

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

8b. Re-analyze the script to verify structure:

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

8e. **Decision gate:**

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
with debug artifacts disabled.

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

10b. Tell the user:
- Total debug iterations and elapsed time
- Fixes applied (sampler name, issue, resolution)
- Final smoke test result
- If resolved: the script is ready for load testing or BlazeMeter upload
- If not resolved: remaining errors and recommendation for manual investigation
- Debug manifest location: `artifacts/{test_run_id}/analysis/debug_manifest.md`

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
