---
name: comparison-report-workflow
description: >-
  Create comparison reports analyzing multiple test runs side-by-side with comparison
  charts and optional Confluence publishing. Use when the user mentions comparison report,
  multi-run comparison, side-by-side analysis, or comparing test runs.
---

# Comparison Report Workflow

## When to Use This Skill

- User wants to compare multiple test runs side-by-side
- User mentions comparison report, multi-run comparison, or test run comparison
- User has 2+ test runs that have completed the E2E performance testing workflow
- User wants comparison charts (CPU, Memory) across test runs

---

## Reference

This section provides context for humans and capable models. For the step-by-step
execution instructions, skip to the **Execution** section below.

### What This Workflow Does

Creates comparison reports that analyze multiple test runs side-by-side, generates
comparison bar charts, and publishes the results to Confluence. This workflow is designed
to run AFTER the end-to-end performance testing workflow
(`.cursor/skills/performance-testing-workflow/SKILL.md`) has been completed for each
individual test run.

The workflow steps:

1. **Validate Prerequisites** — Verify all test runs have completed the E2E workflow
2. **PerfReport MCP** — Generate comparison report and comparison charts
3. **Confluence MCP** (Optional) — Publish comparison report to Confluence
4. **AI Revision** (Optional) — Enhance the report with AI-generated insights

### comparison_id vs run_id

This is a critical distinction:

- `comparison_id` is a **timestamp-based unique identifier** generated when
  `create_comparison_report` runs (e.g., `"2026-01-21-14-27-42"`)
- `comparison_id` is NOT the same as any individual `run_id`
- When publishing to Confluence, use `comparison_id` as the `test_run_id` parameter
- `report_type: "comparison"` tells all tools to look in `artifacts/comparisons/{comparison_id}/`

### Artifact Path Structure

```
artifacts/comparisons/{comparison_id}/
├── comparison_report_{run_ids}.md               # Generated comparison report
├── comparison_report_{run_ids}_original.md      # Backup (after AI revision)
├── comparison_report_{run_ids}_revised.md       # AI-revised report
├── comparison_metadata_{run_ids}.json           # Metadata
├── comparison_metadata_{run_ids}_original.json  # Backup metadata
├── charts/                                      # Comparison bar charts
│   ├── CPU_PEAK_CORE_COMPARISON_BAR-{resource}.png
│   ├── CPU_AVG_CORE_COMPARISON_BAR-{resource}.png
│   ├── MEMORY_PEAK_USAGE_COMPARISON_BAR-{resource}.png
│   └── MEMORY_AVG_USAGE_COMPARISON_BAR-{resource}.png
└── revisions/                                   # AI revision files
    ├── AI_EXECUTIVE_SUMMARY_v1.md
    ├── AI_KEY_FINDINGS_BULLETS_v1.md
    └── AI_ISSUES_SUMMARY_v1.md
```

### Tool Reference

#### PerfReport MCP Tools

| Tool | Purpose | Key Parameters |
|------|---------|---------------|
| `create_comparison_report` | Generate comparison report from multiple runs | `run_id_list`, `template` (optional), `format` |
| `list_chart_types` | List available chart options | — |
| `create_comparison_chart` | Create comparison bar chart | `comparison_id`, `run_id_list`, `chart_id`, `env_name` (optional) |
| `list_templates` | List available report templates | — |

#### Confluence MCP Tools

| Tool | Purpose | Key Parameters |
|------|---------|---------------|
| `list_spaces` | List Confluence spaces | `mode` |
| `get_page_by_id` | Look up page by ID | `page_id`, `mode` |
| `list_pages` | List pages in a space (search by name) | `space_ref`, `mode` |
| `get_available_reports` | List available reports for comparison_id | `test_run_id` (use comparison_id) |
| `create_page` | Create Confluence page | `space_ref`, `test_run_id`, `filename`, `mode`, `parent_id`, `report_type` |
| `attach_images` | Attach chart PNGs to page | `page_ref`, `test_run_id`, `mode`, `report_type` |
| `update_page` | Replace chart placeholders with embedded images | `page_ref`, `test_run_id`, `mode`, `report_type` |

### Comparison Chart IDs

| Chart ID | Description |
|----------|-------------|
| `CPU_PEAK_CORE_COMPARISON_BAR` | Peak CPU core usage across runs |
| `CPU_AVG_CORE_COMPARISON_BAR` | Average CPU core usage across runs |
| `MEMORY_PEAK_USAGE_COMPARISON_BAR` | Peak memory usage across runs |
| `MEMORY_AVG_USAGE_COMPARISON_BAR` | Average memory usage across runs |

**Chart configuration:**
- CPU charts display in "millicores" or "cores" (configured in `chart_schema.yaml`)
- Memory charts display in "MB" or "GB" (configured in `chart_schema.yaml`)
- Comparison charts use the navy-blue gradient color palette from `chart_colors.yaml`
- Each test run gets a distinct color from light to dark blue

### Related Rules

- **`prerequisites.mdc`** — `test_run_id` and artifact structure validation
- **`skill-execution-rules.mdc`** — Follow steps in order, collect inputs first, do not skip
- **`mcp-error-handling.mdc`** — MCP tool error handling (retry policy, reporting format)

### Downstream Workflows

After completing this workflow, the user can proceed to:

- **AI HITL Report Revision** — `.cursor/skills/report-revision-workflow/SKILL.md`
  with `report_type: "comparison"` and `comparison_id` as the `run_id`.

### Important Notes

- **Prerequisites are critical:** Each test run must have completed the full E2E workflow
  before it can be included in a comparison.
- **Recommended:** 2-5 test runs for optimal readability. Maximum 10 supported.
- **Custom templates:** Available via `list_templates`. Custom templates should include
  comparison-specific placeholders (see `docs/report_template_guidelines.md`).
- **Unit configuration:** CPU in "cores" or "millicores", Memory in "GB" or "MB"
  (configured in `report_config.yaml` and `chart_schema.yaml`).

---

## Execution

Follow these steps exactly, in order. Each step has one or more actions.

---

### Collect Inputs

Ask the user for the following values. Do not proceed until all required values are collected.

```
REQUIRED:
  run_id_list = [list of 2-5 test run IDs — e.g., ["80593110", "80603131", "80612241"]]

OPTIONAL:
  env_name  = [environment name for chart filtering]
  template  = [custom comparison template name — default: "default_comparison_report_template.md"]

CONDITIONAL (only if publishing to Confluence):
  confluence_mode  = ["cloud" or "onprem"]
  confluence_space = [space name — e.g., "Quality Engineering"]
  parent_page_name = [e.g., "AI Generated Test Reports"]
  parent_page_id   = [optional — e.g., "123456789"]
```

If the user provides Confluence information, assume they want to publish results.

---

### Step 1 — Validate Prerequisites

**Input:** `run_id_list`

**Action:** For each `run_id` in the list, verify these files exist:

- `artifacts/{run_id}/reports/report_metadata_{run_id}.json`
- `artifacts/{run_id}/analysis/infrastructure_analysis.json`

If any files are missing:
- Report which `run_id`(s) are missing prerequisites
- Advise the user to run the E2E performance testing workflow for those runs first
  (`.cursor/skills/performance-testing-workflow/SKILL.md`)
- Do NOT proceed until all prerequisites are met

---

### Step 2 — Create Comparison Report

**Input:** `run_id_list`, `template` (optional)

**Action:** Call MCP tool `create_comparison_report`

```
create_comparison_report(
  run_id_list = {run_id_list},
  template    = {template},
  format      = "md"
)
```

**Expected response:**

```json
{
  "comparison_id": "2026-01-21-14-27-42",
  "report_path": "artifacts/comparisons/{comparison_id}/comparison_report_{run_ids}.md",
  "metadata_path": "artifacts/comparisons/{comparison_id}/comparison_metadata_{run_ids}.json"
}
```

**Save:**
- `comparison_id` = the generated comparison identifier (used as `test_run_id` in all subsequent steps)
- `report_path` = path to the generated report

**On error:** These are Python code executions. Do NOT retry. Report error to user.

---

### Step 3 — Create Comparison Charts

**Input:** `comparison_id` (from Step 2), `run_id_list`, `env_name` (optional)

**Action:** First, list available chart types:

```
list_chart_types()
```

Look for chart IDs containing "COMPARISON".

Then create all 4 comparison charts:

```
create_comparison_chart(
  comparison_id = {comparison_id},
  run_id_list   = {run_id_list},
  chart_id      = "CPU_PEAK_CORE_COMPARISON_BAR",
  env_name      = {env_name}
)
```

```
create_comparison_chart(
  comparison_id = {comparison_id},
  run_id_list   = {run_id_list},
  chart_id      = "CPU_AVG_CORE_COMPARISON_BAR",
  env_name      = {env_name}
)
```

```
create_comparison_chart(
  comparison_id = {comparison_id},
  run_id_list   = {run_id_list},
  chart_id      = "MEMORY_PEAK_USAGE_COMPARISON_BAR",
  env_name      = {env_name}
)
```

```
create_comparison_chart(
  comparison_id = {comparison_id},
  run_id_list   = {run_id_list},
  chart_id      = "MEMORY_AVG_USAGE_COMPARISON_BAR",
  env_name      = {env_name}
)
```

Charts are saved to: `artifacts/comparisons/{comparison_id}/charts/`

**On error:** These are Python code executions. Do NOT retry. Report error to user.

#### Validation

Verify these files exist:

- `artifacts/comparisons/{comparison_id}/comparison_report_{run_ids}.md`
- `artifacts/comparisons/{comparison_id}/comparison_metadata_{run_ids}.json`
- `artifacts/comparisons/{comparison_id}/charts/CPU_PEAK_CORE_COMPARISON_BAR-*.png`
- `artifacts/comparisons/{comparison_id}/charts/CPU_AVG_CORE_COMPARISON_BAR-*.png`
- `artifacts/comparisons/{comparison_id}/charts/MEMORY_PEAK_USAGE_COMPARISON_BAR-*.png`
- `artifacts/comparisons/{comparison_id}/charts/MEMORY_AVG_USAGE_COMPARISON_BAR-*.png`

---

### Step 4 — Confluence Publishing (Optional)

**When:** Only execute if Confluence details were provided in Collect Inputs.

**Prerequisites:**
- `comparison_id` from Step 2
- `run_id_list`
- `confluence_mode`, `confluence_space`, `parent_page_name` or `parent_page_id`

#### 4a. Locate Space and Parent Page

```
list_spaces(
  mode = {confluence_mode}
)
```

Search for the space matching `confluence_space`. Extract `space_ref`.

**Locate parent page:**

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

Search for the page matching `parent_page_name`.

**Save:** `parent_id` = the parent page ID.

#### 4b. Get Available Reports

```
get_available_reports(
  test_run_id = {comparison_id}
)
```

Select the report filename (e.g., `comparison_report_{run_ids}.md`).

**Save:** `report_filename`.

#### 4c. Create Confluence Page

```
create_page(
  space_ref   = {space_ref},
  test_run_id = {comparison_id},
  filename    = {report_filename},
  mode        = {confluence_mode},
  parent_id   = {parent_id},
  report_type = "comparison",
  title       = {optional custom title}
)
```

**Important:** Use `comparison_id` as `test_run_id` and `report_type: "comparison"`.

**Save:** `page_ref` = returned page ID.

#### 4d. Attach Chart Images

```
attach_images(
  page_ref    = {page_ref},
  test_run_id = {comparison_id},
  mode        = {confluence_mode},
  report_type = "comparison"
)
```

Uploads ALL PNG chart images from `artifacts/comparisons/{comparison_id}/charts/`.
Check response for attached/failed counts. Continue even if some fail.

#### 4e. Update Page with Embedded Images

```
update_page(
  page_ref    = {page_ref},
  test_run_id = {comparison_id},
  mode        = {confluence_mode},
  report_type = "comparison"
)
```

Replaces `{{CHART_PLACEHOLDER: ID}}` markers with embedded `<ac:image>` markup.
Check response for `placeholders_replaced` and `placeholders_remaining`.

Expected placeholders: `CPU_PEAK_CORE_COMPARISON_BAR`, `CPU_AVG_CORE_COMPARISON_BAR`,
`MEMORY_PEAK_USAGE_COMPARISON_BAR`, `MEMORY_AVG_USAGE_COMPARISON_BAR`.

#### 4f. Validation

Verify:
- Page created successfully (check for `page_ref` and URL)
- Images attached (check status: `"success"` or `"partial"`)
- Placeholders replaced (check `placeholders_replaced` list)

**On error:** If API calls fail, retry up to 3 times. Wait 5-10 seconds between retries.

---

### Step 5 — Generate Summary

**Action:** Present a summary to the user.

#### Comparison Report Details

- **Comparison ID:** `{comparison_id}`
- **Test Runs Compared:** `{run_id_list}`
- **Template Used:** `{template_name}`
- **Report Path:** `artifacts/comparisons/{comparison_id}/comparison_report_{run_ids}.md`

#### Charts Generated

| Chart ID | Description | Output Path |
|----------|-------------|-------------|
| CPU_PEAK_CORE_COMPARISON_BAR | Peak CPU core usage across runs | `charts/CPU_PEAK_CORE_COMPARISON_BAR-{resource}.png` |
| CPU_AVG_CORE_COMPARISON_BAR | Average CPU core usage across runs | `charts/CPU_AVG_CORE_COMPARISON_BAR-{resource}.png` |
| MEMORY_PEAK_USAGE_COMPARISON_BAR | Peak memory usage across runs | `charts/MEMORY_PEAK_USAGE_COMPARISON_BAR-{resource}.png` |
| MEMORY_AVG_USAGE_COMPARISON_BAR | Average memory usage across runs | `charts/MEMORY_AVG_USAGE_COMPARISON_BAR-{resource}.png` |

#### Confluence Publishing (if applicable)

- **Page Title:** `{page_title}`
- **Page URL:** `{confluence_url}`
- **Images Attached:** `{count}`
- **Placeholders Replaced:** `{list}`

#### Next Steps

Ask the user:
- "Would you like to enhance the comparison report with AI-generated insights?" — If yes,
  follow the skill at `.cursor/skills/report-revision-workflow/SKILL.md` with
  `report_type: "comparison"` and `comparison_id` as the `run_id`.

---

## Error Handling

These rules apply to every step:

- **PerfReport MCP tools** (create_comparison_report, create_comparison_chart):
  These are Python code executions. Do NOT retry on failure.
  Report the error with: error message, missing file paths, expected vs. actual structure.
  Do NOT attempt to fix code or modify files.

- **Confluence MCP tools** (list_spaces, create_page, attach_images, update_page):
  These are API calls. Retry up to 3 times. Wait 5-10 seconds between retries.

- Do not proceed to the next step if the current step failed.
- Do NOT write code to fix MCP tool issues.
- Ask the user for next steps on any error.
