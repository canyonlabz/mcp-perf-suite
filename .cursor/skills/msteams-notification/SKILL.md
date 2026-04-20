---
name: msteams-notification
description: >-
  Orchestrate MS Teams notifications for performance testing — send start-test,
  stop-test, and test-results notifications to configured channels and chats
  using templates, @mentions, and auto-populated context from test artifacts.
  Use when the user mentions Teams notification, notify the team, send Teams
  message, start/stop test notification, test results notification, or
  MS Teams alert.
---

# MS Teams Notification Skill

## When to Use This Skill

- User wants to notify a Teams channel or chat about a performance test
- User mentions "send a Teams notification", "notify the team", or "alert stakeholders"
- User wants to send a start-test, stop-test, or test-results notification
- User is in the `performance-testing-workflow` and wants to notify before/after a test
- User asks to @mention people in a Teams notification

## What This Skill Does

1. Ensures MS Teams authentication is active
2. Collects notification parameters from the user
3. Resolves the target channel/chat (config name or raw ID)
4. Populates template variables from user input and test artifacts
5. Resolves @mentions (config-driven + dynamic) to Azure AD object IDs
6. Sends the notification via `teams_send_message`

## Prerequisites

- The `msteams-mcp` server must be running and connected
- The user must have authenticated via `teams_login` (check with `teams_status` first)
- For artifact-based variables (`test_run_id`), the relevant BlazeMeter/Datadog/Report
  artifacts must already exist in `artifacts/{test_run_id}/`

### Related Rules

- **`mcp-error-handling.mdc`** — MCP tool error handling (retry policy, reporting format)
- **`skill-execution-rules.mdc`** — Follow steps in order, collect inputs first

---

## Reference

### MS Teams MCP Tools Used

| Tool | Purpose |
|------|---------|
| `teams_status` | Verify authentication is active before sending |
| `teams_login` | Authenticate if session is expired |
| `teams_send_message` | Send the notification (with template, target, mentions) |
| `teams_search_people` | Resolve person name to email when user gives a name |

### Notification Types and Templates

| Type | Template | When to Use |
|------|----------|-------------|
| Start test | `notification-start-test.md` | Before launching a load test |
| Stop test | `notification-stop-test.md` | After a test completes |
| Test results | `notification-test-results.md` | After analysis and reporting are done |

Templates fall back to `default-{name}` if no custom version exists.

### Template Placeholders

Placeholders use `{{VARIABLE_NAME}}` syntax. Unmatched placeholders are silently removed.

**Common (all templates):**

| Placeholder | Source | Required |
|-------------|--------|----------|
| `{{TEST_NAME}}` | User input | Yes |
| `{{ENVIRONMENT}}` | User input | Yes |
| `{{TEST_RUN_ID}}` | User input or `test_run_id` param | Yes |
| `{{MESSAGE}}` | The `message` param or user's free-text | No |

**Start-test specific:**

| Placeholder | Source |
|-------------|--------|
| `{{START_TIME}}` | User input or auto from artifacts |
| `{{DURATION}}` | User input (planned duration) |
| `{{VIRTUAL_USERS}}` | User input |

**Stop-test specific:**

| Placeholder | Source |
|-------------|--------|
| `{{START_TIME}}` | Auto from notification log or artifacts |
| `{{END_TIME}}` | Auto from artifacts or current time |
| `{{DURATION}}` | Auto-calculated or user input |
| `{{VIRTUAL_USERS}}` | Auto from notification log or user input |
| `{{STATUS}}` | User input (e.g., "Completed", "Aborted") |

**Test-results specific:**

| Placeholder | Source |
|-------------|--------|
| `{{AVG_RESPONSE_TIME}}` | BlazeMeter aggregate report |
| `{{P90_RESPONSE_TIME}}` | BlazeMeter aggregate report |
| `{{P95_RESPONSE_TIME}}` | BlazeMeter aggregate report |
| `{{MAX_RESPONSE_TIME}}` | BlazeMeter aggregate report |
| `{{ERROR_RATE}}` | BlazeMeter aggregate report |
| `{{THROUGHPUT}}` | BlazeMeter aggregate report |
| `{{BLAZEMETER_REPORT_LINK}}` | `artifacts/{id}/blazemeter/public_report.json` |
| `{{CONFLUENCE_REPORT_LINK}}` | `artifacts/{id}/reports/report_metadata_{id}.json` |

### Config-Driven Targets and Mentions

Targets and standing mention lists are defined in the `msteams-mcp` config file
under `teams.notification_targets`. The tool auto-resolves named targets to
conversation IDs and merges config-level mentions with any dynamic mentions.

Example config structure:

```yaml
notification_targets:
  channels:
    qa-perf-results:
      conversation_id: "19:abc@thread.tacv2"
      description: "QA Performance Testing"
      template: "notification-test-results.md"
      mentions:
        - "homer.simpson@company.com"
        - "marge.simpson@company.com"
  chats:
    default_chat:
      conversation_id: "19:def@thread.v2"
      description: "Internal Performance Team"
```

### Mention Resolution

The `mentions` parameter accepts a JSON array. Each entry needs `email` and/or `id`:

```json
[
  {"email": "john.doe@company.com"},
  {"email": "jane.doe@company.com", "displayName": "Jane Doe (US)"},
  {"id": "5769135d-...", "displayName": "Known User"}
]
```

Resolution rules:
- If `id` is provided → used directly (no search)
- If only `email` → auto-resolved via `teams_search_people`
- If search returns 0 or multiple matches → message is NOT sent, warning returned
- Config mentions + dynamic mentions are merged and deduplicated by email

### Integration with Performance Testing Workflow

This skill can be invoked at three points in the `performance-testing-workflow`:

1. **Before Step 2 (BlazeMeter)** — Send start-test notification
2. **After Step 2 (BlazeMeter)** — Send stop-test notification
3. **After Step 5 or 6 (PerfReport/Confluence)** — Send test-results notification

The `test_run_id` parameter auto-loads context from artifacts, so most
placeholders are populated automatically after the relevant workflow steps complete.

---

## Execution

Follow these steps exactly, in order.

---

### Collect Inputs

Ask the user for the following values. Do not proceed until required values are collected.

```
REQUIRED:
  notification_type = [start-test | stop-test | test-results]
  target            = [named target from config, e.g. "qa-perf-results",
                       or raw conversation ID]

REQUIRED (if no test_run_id for auto-population):
  test_name         = [e.g., "Shopping Cart 150-User Load Test (QA)"]
  environment       = [e.g., "QA", "UAT", "PROD"]

CONDITIONAL:
  test_run_id       = [e.g., "7654321" — auto-populates variables from artifacts]

OPTIONAL:
  subject           = [bold title line above message in channels]
  message           = [free-text appended to the template as {{MESSAGE}}]
  mentions          = [additional people to @mention beyond config defaults]
  variables         = [explicit key-value overrides for any placeholder]
```

**Inferring values from conversation context:**
- If the user is in a `performance-testing-workflow` conversation, the `test_run_id`,
  `test_name`, `environment`, and other values are likely already known. Use them.
- If the user says "notify the team that the test is done", infer `notification_type`
  as `stop-test` and check context for `test_run_id`.
- If the user provides a `test_run_id` but no explicit variable values, rely on
  auto-population from artifacts.

---

### Step 1 — Check Authentication

```
teams_status()
```

Inspect the response. If the session is expired or missing:

```
teams_login()
```

Do not proceed until authentication is confirmed.

---

### Step 2 — Determine Template

Based on `notification_type`:

| Type | Template filename |
|------|-------------------|
| `start-test` | `notification-start-test.md` |
| `stop-test` | `notification-stop-test.md` |
| `test-results` | `notification-test-results.md` |

The tool's layered resolution handles fallback to `default-{name}` automatically.

---

### Step 3 — Build Variables

Construct the `variables` JSON object from collected inputs.

**For start-test:**

```json
{
  "TEST_NAME": "{test_name}",
  "ENVIRONMENT": "{environment}",
  "TEST_RUN_ID": "{test_run_id}",
  "START_TIME": "{start_time or current time}",
  "DURATION": "{planned_duration}",
  "VIRTUAL_USERS": "{virtual_users}"
}
```

**For stop-test:**

If `test_run_id` is provided, check the notification log for the previous start-test:
- Read `artifacts/{test_run_id}/notifications/notification_log.json`
- Find the most recent `notification-start-test` entry
- Extract `TEST_NAME`, `ENVIRONMENT`, `START_TIME`, `VIRTUAL_USERS` from it

```json
{
  "TEST_NAME": "{from log or user}",
  "ENVIRONMENT": "{from log or user}",
  "TEST_RUN_ID": "{test_run_id}",
  "START_TIME": "{from log}",
  "END_TIME": "{end_time or current time}",
  "DURATION": "{calculated or user}",
  "VIRTUAL_USERS": "{from log or user}",
  "STATUS": "{status — e.g., Completed, Aborted}"
}
```

**For test-results:**

If `test_run_id` is provided, the tool auto-loads variables from artifacts
(`load_context_variables`). You only need to pass explicit overrides and any
values the tool cannot auto-detect:

```json
{
  "TEST_NAME": "{test_name}",
  "ENVIRONMENT": "{environment}",
  "VIRTUAL_USERS": "{virtual_users}",
  "AVG_RESPONSE_TIME": "{from aggregate report}",
  "P90_RESPONSE_TIME": "{from aggregate report}",
  "P95_RESPONSE_TIME": "{from aggregate report}",
  "MAX_RESPONSE_TIME": "{from aggregate report}",
  "ERROR_RATE": "{from aggregate report}",
  "THROUGHPUT": "{from aggregate report}"
}
```

For metrics from the BlazeMeter aggregate report, read
`artifacts/{test_run_id}/blazemeter/aggregate_performance_report.csv` and extract
the `TOTAL` row values. The tool auto-loads `BLAZEMETER_REPORT_LINK` and
`CONFLUENCE_REPORT_LINK` from their respective JSON files when `test_run_id` is set.

---

### Step 4 — Build Mentions List

If the user specified additional people to @mention:

1. If user gave **emails** → add directly to the mentions array
2. If user gave **names** → search first:

```
teams_search_people(query="{person_name}")
```

Review the results. If exactly one match, use their email. If multiple matches,
present the options to the user and ask them to confirm which person to tag.

Combine with any config-level mentions (handled automatically by the tool).

Format the final mentions parameter:

```json
[
  {"email": "person1@company.com"},
  {"email": "person2@company.com", "displayName": "Person Two (US)"}
]
```

If no dynamic mentions are needed and the config already has the correct list,
leave the `mentions` parameter empty — the tool merges config mentions automatically.

---

### Step 5 — Send Notification

```
teams_send_message(
  target      = "{target}",
  template    = "{template_filename}",
  variables   = '{...JSON string...}',
  test_run_id = "{test_run_id}",
  subject     = "{subject}",
  message     = "{message}",
  mentions    = '[...JSON string...]'
)
```

**Important:** Only pass parameters that have values. Omit empty optional parameters.

---

### Step 6 — Verify and Report

Check the response:

- **Success** (`"status": "sent"`) — Report the message ID and target to the user.
  If `test_run_id` was provided, confirm that the notification was logged to
  `artifacts/{test_run_id}/notifications/notification_log.json`.
- **Mention resolution failure** (`"INVALID_INPUT"` with mention warnings) —
  Report which emails failed. Ask the user to verify the email addresses or
  provide object IDs directly. Do NOT retry automatically.
- **Auth failure** — Run `teams_login()` and retry once.
- **Other errors** — Report the full error and ask the user for next steps.

---

## Error Handling

- **Auth expired mid-send:** Run `teams_login()`, then retry the send once.
- **Mention not found:** Report the warning. Do NOT send the message without the mention.
  Ask the user to verify the email or provide an alternative.
- **Ambiguous mention:** Present the multiple matches to the user. Ask them to pick the
  correct person or provide the specific `id`.
- **Template not found:** Report the missing template name. Suggest checking the
  `templates/` directory or using a default template.
- **No conversation_id resolved:** The target name doesn't match any config entry and
  isn't a valid raw ID. Ask the user to verify the target name or provide a conversation ID.
  Suggest using `teams_list_channels` or `teams_find_channel` to discover the correct ID.

---

## Examples

### Start-Test Notification (Simple)

User: "Notify the perf channel that we're starting the 50-user load test on QA"

```
teams_send_message(
  target    = "perf-channel",
  template  = "notification-start-test.md",
  variables = '{"TEST_NAME": "50-User Load Test", "ENVIRONMENT": "QA", "VIRTUAL_USERS": "50"}',
  subject   = "50-User Load Test — Starting"
)
```

### Test-Results Notification (With test_run_id)

User: "Send the test results to the QA channel for run 7654321"

```
teams_send_message(
  target      = "qa-perf-results",
  template    = "notification-test-results.md",
  test_run_id = "7654321",
  variables   = '{"TEST_NAME": "Shopping Cart 150-User Load Test (QA)", "ENVIRONMENT": "QA", "VIRTUAL_USERS": "150"}',
  subject     = "Shopping Cart 150-User Load Test — Results"
)
```

The tool auto-loads `BLAZEMETER_REPORT_LINK`, `CONFLUENCE_REPORT_LINK`, and other
context variables from `artifacts/7654321/`.

### Dynamic @mention

User: "Send the results to the default chat and tag lisa.simpson@company.com"

```
teams_send_message(
  target      = "default_chat",
  template    = "notification-test-results.md",
  test_run_id = "7654321",
  mentions    = '[{"email": "lisa.simpson@company.com"}]'
)
```

Config mentions for `default_chat` are merged automatically.
