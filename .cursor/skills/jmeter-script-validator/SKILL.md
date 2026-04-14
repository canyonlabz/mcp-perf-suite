---
name: jmeter-script-validator
description: >-
  Validate existing JMeter scripts via autonomous smoke testing using the
  jmeter-script-validator subagent. Use when the user mentions script validation,
  script health check, validate JMeter script, re-validate old scripts, check if
  a JMeter script still works, or smoke test validation. This skill orchestrates
  one or more validator subagents, each producing a standalone Markdown validation
  report.
---

# JMeter Script Validator

## When to Use This Skill

- User wants to validate whether an existing JMeter script still works
- User mentions "script validation", "re-validate", "script health check"
- User wants to smoke test an old script to check for broken endpoints, stale correlations, or payload changes
- User wants to validate multiple scripts using subagents
- Never start this workflow unless the user explicitly requests it

---

## Reference

This section provides context for humans and capable models. For the step-by-step
execution instructions, skip to the **Execution** section below.

### What This Skill Does

This skill orchestrates the `jmeter-script-validator` subagent to autonomously
validate JMeter scripts. Each subagent:

1. Runs an initial 1/1/1 smoke test to detect the first failure
2. Stops the test at the first error and reads the JTL to identify the failing sampler
3. Attaches a Debug Post-Processor to capture verbose request/response data
4. Runs a second smoke test to collect detailed debug output
5. Stops the second test and inspects the JTL Request URL for `NOT_FOUND` patterns
6. Analyzes the JMeter log with debug data for root cause diagnosis
7. Compiles a well-structured Markdown validation report with findings
8. Optionally generates an aggregate report for the smoke test results

The subagent does **NOT** apply fixes. It is strictly a validation and diagnosis
tool. For iterative fix-and-retest, use the `jmeter-debugging` skill instead.

### Architecture

```
User Prompt (test_run_id, jmx_filename, ...)
  │
  ▼
Orchestrator (this skill)
  │
  ├── jmeter-script-validator subagent
  │     ├── Smoke Test 1 (detect first failure via run status / JTL)
  │     ├── Attach Debug Post-Processor to failing sampler
  │     ├── Smoke Test 2 (capture verbose debug data)
  │     ├── Analyze JMeter log + inspect JTL Request URLs
  │     ├── Generate aggregate report (optional)
  │     └── Write validation report
  │           └── artifacts/{test_run_id}/analysis/Report_{Script_Name}.md
  │
  ├── [optional] additional subagents for other scripts
  │
  └── Summary to user
```

### Report Naming Convention

Each smoke test produces its own Markdown report. The report name is derived from
the JMX script filename using Snake Case with a `Report_` prefix:

| JMX Filename | Report Name |
|---|---|
| `Login_Flow.jmx` | `Report_Login_Flow.md` |
| `ai-generated-script.jmx` | `Report_Ai_Generated_Script.md` |
| `imported_checkout-api.jmx` | `Report_Imported_Checkout_Api.md` |
| `my test script.jmx` | `Report_My_Test_Script.md` |

**Conversion rules:**
1. Remove the `.jmx` extension
2. Replace hyphens (`-`), spaces, and dots with underscores (`_`)
3. Title-case each segment (capitalize the first letter of each word)
4. Prepend `Report_`

Reports are written to: `artifacts/{test_run_id}/analysis/Report_{Script_Name}.md`

### Validation vs Debugging

| Aspect | Script Validator (this skill) | Debugging Skill |
|---|---|---|
| Purpose | Diagnose and report | Diagnose and fix |
| Applies fixes? | No | Yes |
| Max smoke tests | 2 per script | Up to 5 iterations |
| Output | Markdown report only | Fixed script + debug manifest |
| Runs as | Subagent | Interactive foreground |

### Related Files

- **Subagent definition:** `.cursor/agents/jmeter-script-validator.md`
- **JMeter debugging skill:** `.cursor/skills/jmeter-debugging/SKILL.md`
- **JMeter HITL editing skill:** `.cursor/skills/jmeter-hitl-editing/SKILL.md`
- **JMeter script guardrails:** `.cursor/rules/jmeter-script-guardrails.mdc`
- **Skill execution rules:** `.cursor/rules/skill-execution-rules.mdc`
- **Prerequisites:** `.cursor/rules/prerequisites.mdc`
- **MCP error handling:** `.cursor/rules/mcp-error-handling.mdc`

---

## Execution

Follow these steps exactly, in order.

---

### Step 1 — Collect Inputs

Ask the user for the following values. Do not proceed until all required values are collected.

```
REQUIRED:
  test_run_id  = [ask user — must have an existing JMX in artifacts/{test_run_id}/jmeter/]

OPTIONAL:
  jmx_filename     = [specific JMX file to validate — if not provided, auto-discovers]
  validate_all     = [true/false — validate all JMX scripts found for this test_run_id.
                      Default: false. If true, one subagent is launched per script.]
  generate_report  = [true/false — generate aggregate report after smoke tests.
                      Default: true]
```

---

### Step 2 — Initialize Task Tracking

Create task items to monitor progress:

- Script discovery
- Subagent invocation (one per script)
- Report validation
- Summary to user

---

### Step 3 — Discover Scripts

**Action:** List the JMX scripts available for this test run.

The orchestrator (you) should call the JMeter MCP tool directly to discover scripts:

```
list_jmeter_scripts(
  test_run_id = {test_run_id}
)
```

**Save:** `scripts_list` — the list of JMX script paths and filenames.

**Decision gate:**

- If `jmx_filename` was provided, verify it exists in `scripts_list`. If not found, report
  the error to the user and stop.
- If `validate_all=true`, all scripts in `scripts_list` will be validated.
- If neither was provided and multiple scripts exist, ask the user which script(s)
  to validate.
- If only one script exists, use it automatically.

**Save:** `target_scripts` — the list of scripts to validate (one or more).

---

### Step 4 — Derive Report Names

For each script in `target_scripts`, derive the report filename:

1. Take the JMX filename (e.g., `Login_Flow.jmx`)
2. Remove the `.jmx` extension → `Login_Flow`
3. Replace hyphens, spaces, dots with underscores → `Login_Flow`
4. Title-case each segment → `Login_Flow`
5. Prepend `Report_` → `Report_Login_Flow`
6. Append `.md` → `Report_Login_Flow.md`

**Save:** Mapping of `{jmx_filename} → {report_filename}` for each target script.

---

### Step 5 — Invoke Subagent(s)

For each script in `target_scripts`, invoke a `jmeter-script-validator` subagent
with the following prompt:

```
Validate the JMeter script for test_run_id: {test_run_id}

  jmx_filename:    {jmx_filename}
  report_filename: {report_filename}
  generate_report: {generate_report}

Follow all instructions in your system prompt. Write the validation report to:
  artifacts/{test_run_id}/analysis/{report_filename}
```

**Important:**
- If `validate_all=true` and multiple scripts exist, invoke subagents
  **sequentially** — one at a time, waiting for each to complete before
  starting the next
- Save the return JSON from each subagent for the summary

---

### Step 6 — Validate Reports

After all subagents complete, verify that each expected report file exists:

```
artifacts/{test_run_id}/analysis/{report_filename}
```

**For each report:**
- If the file exists, record it as successful
- If the file does not exist, record the failure and check the subagent return
  for error details

---

### Step 7 — Report Results to User

Present a clear summary to the user:

1. **Scripts Validated**
   - List each script, its validation outcome (pass/fail), and report location

2. **Validation Results**
   - For each script: whether it passed (0% errors) or failed (with first error details)
   - If failed: the failing sampler name, HTTP response code, and brief diagnosis

3. **Report Locations**
   - Full path to each validation report in `artifacts/{test_run_id}/analysis/`
   - Path to aggregate reports if generated

4. **Next Steps**
   - If scripts failed validation: recommend running the `jmeter-debugging` skill
     to iteratively fix the issues
   - If scripts passed: the scripts are ready for load testing or BlazeMeter upload

---

## Error Handling

- If `list_jmeter_scripts` returns no scripts, stop and inform the user that no JMX
  files were found for the given `test_run_id`.
- If a subagent fails to invoke, record it in the summary and continue with remaining
  subagents.
- Do NOT retry subagent invocations. Each subagent handles its own MCP tool retries
  internally.
- Do NOT modify any existing Rules, Skills, or MCP source code.
- If the orchestrator itself encounters an error, report directly to the user with the
  full error message.
- JMeter MCP tools are code-based — do NOT retry on failure. Report the error as-is.
