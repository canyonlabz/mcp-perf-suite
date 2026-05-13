---
name: sharepoint-upload
description: >-
  Upload performance test artifacts to SharePoint document libraries.
  Use when the user mentions uploading artifacts to SharePoint, saving
  test results to SharePoint, persisting files to SharePoint, or
  archiving performance test output.
---

# SharePoint Upload Skill

## When to Use This Skill

- User wants to upload performance test artifacts to SharePoint
- User mentions "upload to SharePoint", "save to SharePoint", or "archive artifacts"
- User wants to persist `artifacts/{test_run_id}/` files to a SharePoint document library
- User is at the end of a `performance-testing-workflow` and wants to archive results
- User wants to upload a specific file or folder to SharePoint

## What This Skill Does

1. Ensures SharePoint authentication is active
2. Collects the upload destination from the user (site URL + folder path)
3. Creates the destination folder in SharePoint if it doesn't exist
4. Uploads the specified file or folder
5. Optionally sends a Teams notification about the upload (if configured)

## Prerequisites

- The `sharepoint-mcp` server must be running and connected
- The user must have authenticated via `sharepoint_login` (check with `sharepoint_status` first)
- The local file(s) to upload must exist on disk
- For `test_run_id`-based uploads, the relevant artifacts must exist in `artifacts/{test_run_id}/`

### Related Rules

- **`mcp-error-handling.mdc`** — MCP tool error handling (retry policy, reporting format)
- **`skill-execution-rules.mdc`** — Follow steps in order, collect inputs first

---

## Reference

### SharePoint MCP Tools Used

| Tool | Purpose |
|------|---------|
| `sharepoint_status` | Verify authentication is active before uploading |
| `sharepoint_login` | Authenticate if session is expired |
| `sharepoint_upload_file` | Upload a single file |
| `sharepoint_upload_folder` | Upload an entire folder (recursive) |
| `sharepoint_create_folder` | Create the destination folder if it doesn't exist |
| `sharepoint_list_folder` | Browse folder contents (to verify upload or find destination) |
| `sharepoint_list_libraries` | Discover available document libraries in a site |

### Optional MS Teams Integration

If `notification_on_upload.enabled` is `true` in `sharepoint-mcp/config.yaml`, a
Teams notification is sent after successful upload using the configured target and
template. This requires `msteams-mcp` to be connected.

| Tool | Purpose |
|------|---------|
| `teams_status` | Check Teams auth before sending notification |
| `teams_login` | Authenticate to Teams if needed |
| `teams_send_message` | Send upload completion notification |

---

## Execution

Follow these steps exactly, in order.

---

### Collect Inputs

Ask the user for the following values. Do not proceed until required values are collected.

```
REQUIRED:
  site_url           = Full SharePoint site URL
                       Example: "https://contoso.sharepoint.com/sites/PerfTesting"
  destination_folder = Server-relative folder path in the document library
                       Example: "/sites/PerfTesting/Shared Documents/Results/2026-05-11"

REQUIRED (one of the two):
  local_file_path    = Absolute path to a single file to upload
  local_folder_path  = Absolute path to a folder to upload (all contents, recursive)

OPTIONAL:
  test_run_id        = If uploading artifacts for a test run, the run ID.
                       When provided, local_folder_path defaults to artifacts/{test_run_id}/
                       and destination_folder can be auto-suggested.
```

**Inferring values from conversation context:**
- If the user is in a `performance-testing-workflow` conversation, the `test_run_id`
  is likely already known. Use `artifacts/{test_run_id}/` as the default local path.
- If the user says "upload the test results to SharePoint", check the conversation
  context for a `test_run_id` and ask for the SharePoint destination.
- If the user provides a `test_run_id` but no `destination_folder`, suggest a folder
  structure like `/sites/{SiteName}/Shared Documents/{test_run_id}` and ask for confirmation.
- If the user doesn't know their `site_url`, use `sharepoint_list_libraries` after
  login to help them discover available sites and libraries.

---

### Step 1 — Check Authentication

```
sharepoint_status()
```

Inspect the response:
- `authMode` should be `"bearer"` or `"cookie"` — either is valid
- If `authMode` is `"none"`, or `isSessionExpired` is `true`, authenticate:

```
sharepoint_login()
```

Do not proceed until `authMode` is confirmed as `"bearer"` or `"cookie"`.

If the tenant was auto-detected, note it — it can help construct the `site_url`
if the user only provides a site name.

---

### Step 2 — Validate Destination

Verify the destination exists or create it:

```
sharepoint_create_folder(
  site_url      = "{site_url}",
  folder_path   = "{destination_folder}"
)
```

This creates the full folder path including parents. If the folder already exists,
the tool returns success without error.

---

### Step 3 — Upload

**For a single file:**

```
sharepoint_upload_file(
  site_url           = "{site_url}",
  destination_folder = "{destination_folder}",
  local_file_path    = "{local_file_path}"
)
```

**For a folder (all contents):**

```
sharepoint_upload_folder(
  site_url           = "{site_url}",
  destination_folder = "{destination_folder}",
  local_folder_path  = "{local_folder_path}"
)
```

If `test_run_id` is provided and no explicit local path was given:

```
sharepoint_upload_folder(
  site_url           = "{site_url}",
  destination_folder = "{destination_folder}",
  local_folder_path  = "artifacts/{test_run_id}"
)
```

---

### Step 4 — Verify Upload

Check the response:

- **Success** (`"status": "uploaded"` or `"status": "completed"`) — Report the
  uploaded file count, total size, and SharePoint destination to the user.
- **Completed with errors** (`"status": "completed_with_errors"`) — Report
  which files succeeded and which failed. Ask the user if they want to retry
  the failed files individually.
- **Auth failure** — Run `sharepoint_login()` and retry once.
- **Other errors** — Report the full error and ask the user for next steps.

---

### Step 5 — Optional Teams Notification

Check if Teams notification is configured:

1. Read the `notification_on_upload` section from `sharepoint-mcp` config
2. If `enabled: true` and a `target` is set:

```
teams_status()
```

If Teams auth is active:

```
teams_send_message(
  target    = "{notification target from config}",
  template  = "{template from config or 'default-notification-sharepoint-upload.md'}",
  variables = '{"TEST_RUN_ID": "{test_run_id}", "SHAREPOINT_URL": "{site_url}{destination_folder}", "UPLOAD_FILE_COUNT": "{count}", "UPLOAD_TOTAL_SIZE": "{size}", "UPLOADED_BY": "{user}"}'
)
```

If Teams auth is not active, skip the notification and inform the user that
the Teams notification was not sent because `msteams-mcp` is not authenticated.

---

## Error Handling

- **Auth expired mid-upload:** The API layer automatically retries 401 errors once
  with cookie auth if Bearer auth fails. If the retry also fails, run
  `sharepoint_login()`, then retry the upload once.
- **File too large:** Files over the `max_upload_size_mb` threshold (default 250 MB)
  are automatically uploaded using chunked upload. If a file exceeds SharePoint's
  absolute limit (~10 GB), report the error and suggest splitting the file.
- **Folder not found (404):** The `site_url` or `destination_folder` is incorrect.
  Ask the user to verify the path. Suggest using `sharepoint_list_libraries` and
  `sharepoint_list_folder` to discover the correct path.
- **Permission denied (403):** The user doesn't have write access to the destination.
  Ask the user to verify they have Contribute or Edit permissions on the library.
- **Partial upload failure:** Some files uploaded, some failed. Report the failures
  with specific file names and error messages. Ask if the user wants to retry just
  the failed files.

---

## Examples

### Upload Test Run Artifacts

User: "Upload the artifacts from run 2026-05-11-14-30 to SharePoint"

```
sharepoint_status()
# Authenticated, tenant: contoso

sharepoint_create_folder(
  site_url    = "https://contoso.sharepoint.com/sites/PerfTesting",
  folder_path = "/sites/PerfTesting/Shared Documents/Results/2026-05-11-14-30"
)

sharepoint_upload_folder(
  site_url           = "https://contoso.sharepoint.com/sites/PerfTesting",
  destination_folder = "/sites/PerfTesting/Shared Documents/Results/2026-05-11-14-30",
  local_folder_path  = "artifacts/2026-05-11-14-30"
)
```

### Upload a Single Report

User: "Upload the performance report PDF to the QA SharePoint site"

```
sharepoint_upload_file(
  site_url           = "https://contoso.sharepoint.com/sites/QA",
  destination_folder = "/sites/QA/Shared Documents/Reports",
  local_file_path    = "artifacts/2026-05-11-14-30/reports/performance_report.pdf"
)
```

### Discover Available Libraries

User: "Where can I upload files on SharePoint?"

```
sharepoint_list_libraries(
  site_url = "https://contoso.sharepoint.com/sites/PerfTesting"
)
# Returns: [{"title": "Shared Documents", ...}, {"title": "Test Results", ...}]
```
