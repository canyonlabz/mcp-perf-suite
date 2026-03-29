---
name: report-revision-workflow
description: >-
  AI-assisted HITL revision of performance test reports with iterative refinement,
  version tracking, and optional Confluence publishing. Use when the user mentions
  report revision, AI-enhanced report, revise executive summary, revise key observations,
  revise issues table, or improve a performance report.
---

# AI-Assisted Report Revision Workflow

## When to Use This Skill

- User wants to revise or enhance a performance test report with AI-generated content
- User mentions report revision, AI summary, executive summary, key observations, or issues table
- User wants to iteratively refine report sections with feedback
- User wants to publish a revised report to Confluence
- This workflow supports both `single_run` reports and `comparison` reports

---

## Reference

This section provides context for humans and capable models. For the step-by-step
execution instructions, skip to the **Execution** section below.

### What This Workflow Does

Orchestrates the AI-assisted revision of performance test reports using a Human-In-The-Loop
(HITL) approach. It enables iterative refinement of report sections through PerfReport MCP
tools that work together to discover data, save AI-generated revisions, and assemble the
final report.

The workflow phases:

1. **Discovery** — Gather all available data files and determine which sections are revisable
2. **AI Generation** — Read analysis data and generate revised content for enabled sections
3. **Save Revisions** — Save each revised section with version tracking
4. **Assembly** — Assemble the final revised report with AI content replacing placeholders
5. **User Review** — Present results and gather feedback
6. **HITL Iteration** — Refine specific sections based on user feedback (repeatable)
7. **Confluence Publishing** — Optionally publish the revised report

### Report Types and Section Differences

This workflow handles two report types with different section IDs:

**Single-Run Report Sections:**

| Section ID | Placeholder | Description |
|------------|-------------|-------------|
| `executive_summary` | `{{EXECUTIVE_SUMMARY}}` | High-level test outcome summary with key metrics and findings |
| `key_observations` | `{{KEY_OBSERVATIONS}}` | Bullet-point observations about test performance and issues |
| `issues_table` | `{{ISSUES_TABLE}}` | Table of issues and errors observed during test execution |
| `jmeter_log_analysis` | `{{JMETER_LOG_ANALYSIS}}` | JMeter/BlazeMeter log error analysis with categorization, affected APIs, and JTL correlation |
| `bottleneck_analysis` | `{{BOTTLENECK_ANALYSIS}}` | Bottleneck identification with degradation thresholds, severity breakdown, and per-endpoint findings |

**Comparison Report Sections:**

| Section ID | Placeholder | Description |
|------------|-------------|-------------|
| `executive_summary` | `{{EXECUTIVE_SUMMARY}}` | Comparison summary across multiple test runs |
| `key_findings` | `{{KEY_FINDINGS_BULLETS}}` | Key findings from comparing test runs |
| `issues_summary` | `{{ISSUES_SUMMARY}}` | Summary of issues across compared runs |
| `overall_trend_summary` | `{{OVERALL_TREND_SUMMARY}}` | Overall performance trend narrative comparing key metrics across test runs |
| `correlation_insights_section` | `{{CORRELATION_INSIGHTS_SECTION}}` | Performance-infrastructure correlation analysis across compared runs |

The `discover_revision_data` tool returns the full list of available sections dynamically.
The tables above reflect the known sections defined in `report_config.yaml`. Additional
sections may be added in the future.

**Key differences between report types:**
- Single-run uses `key_observations` and `issues_table`
- Comparison uses `key_findings` and `issues_summary`
- Comparison has additional sections: `overall_trend_summary` and `correlation_insights_section`
- Single-run has additional sections: `jmeter_log_analysis` and `bottleneck_analysis`

### Artifact Paths

**Single-Run Reports:**

```
artifacts/{run_id}/reports/
├── performance_report_{run_id}.md              # Original report
├── performance_report_{run_id}_original.md     # Backup (after revision)
├── performance_report_{run_id}_revised.md      # AI-revised report
├── report_metadata_{run_id}.json               # Metadata
├── report_metadata_{run_id}_original.json      # Backup metadata
└── revisions/                                  # AI revision files
    ├── AI_EXECUTIVE_SUMMARY_v1.md
    ├── AI_KEY_OBSERVATIONS_v1.md
    └── AI_ISSUES_TABLE_v1.md
```

**Comparison Reports:**

```
artifacts/comparisons/{comparison_id}/
├── comparison_report_*.md              # Original report
├── comparison_report_*_original.md     # Backup (after revision)
├── comparison_report_*_revised.md      # AI-revised report
├── comparison_metadata_*.json          # Metadata
├── comparison_metadata_*_original.json # Backup metadata
├── charts/                             # Comparison charts
└── revisions/                          # AI revision files
    ├── AI_EXECUTIVE_SUMMARY_v1.md
    ├── AI_KEY_FINDINGS_BULLETS_v1.md
    └── AI_ISSUES_SUMMARY_v1.md
```

### Tool Reference

| Tool | Purpose | Key Parameters |
|------|---------|---------------|
| `discover_revision_data` | Gather data files and revisable sections | `run_id`, `report_type`, `additional_context` (optional) |
| `prepare_revision_context` | Save AI-generated content for a section | `run_id`, `section_id`, `revised_content`, `report_type`, `additional_context` (optional) |
| `revise_performance_test_report` | Assemble final revised report from saved revisions | `run_id`, `report_type`, `revision_version` (optional) |
| `convert_markdown_to_xhtml` | Convert revised Markdown to Confluence XHTML | `test_run_id`, `filename`, `report_type` |
| `update_page` | Publish revised content to Confluence page | `page_ref`, `test_run_id`, `mode`, `use_revised`, `report_type` |

### AI Content Guidelines

#### Executive Summary

- High-level overview of test results
- Include key metrics: success rate, avg response time, throughput
- Highlight critical issues or SLA violations
- 3-5 sentences or bullet points
- Mention test environment and date if relevant
- Incorporate `additional_context` if provided (project name, purpose)

#### Key Observations (single_run) / Key Findings (comparison)

- 3-7 key observations or findings
- Bullet points for clarity
- Both positive findings and concerns
- Reference specific APIs or services
- Prioritize by impact
- **For comparison:** Include trends across runs, scaling behavior, pattern identification

#### Issues Table (single_run) / Issues Summary (comparison)

- Markdown table: Issue Type, Severity, Count/Impact, Affected Endpoint, Description
- Sort by severity (Critical > High > Medium > Low)
- Include error rates and specific error messages
- For HTTP errors, recommend reviewing JMeter logs
- **For comparison:** Recurring vs. one-time issues, issues resolved between runs

#### JMeter Log Analysis (single_run)

- Categorize errors found in JMeter/BlazeMeter logs
- List affected APIs and endpoints
- Correlate with JTL test results data where applicable
- Highlight patterns (e.g., recurring errors, timeouts, connection failures)

#### Bottleneck Analysis (single_run)

- Identify the concurrency threshold where performance degradation begins
- Severity breakdown by endpoint
- Per-endpoint findings with specific metrics
- Recommendations for addressing bottlenecks

#### Overall Trend Summary (comparison)

- Narrative describing how key metrics changed across test runs
- Highlight scaling behavior (e.g., linear throughput growth, stable error rates)
- Note any inflection points where performance degraded

#### Correlation Insights (comparison)

- Performance-infrastructure correlation findings across runs
- CPU/Memory scaling behavior relative to load increases
- Identify which resources correlate most strongly with response time changes

#### Writing Style

- Professional tone suitable for leadership/stakeholders
- Concise but informative with specific metrics and data points
- Use markdown formatting (headers, bullet points, tables)

#### Technical Term Definitions

When using terms non-technical stakeholders may not understand:

- **1-2 terms:** Add a footnote after Key Observations:
  `> **Terms:** *CoV* — A measure of response time consistency; values >1.0 indicate high variability.`
- **3+ terms:** Add a "Glossary" section before "Report Generation Details" with a definition table.

**Common terms requiring definition:** CoV, P90/P95/P99, SLA, Throughput, Latency vs
Response Time, Error Rate, mCPU, Connection Pool.

### AI Content Guidelines for Comparison Reports

When generating content for comparison reports, consider:

1. **Trends Analysis** — How performance changed across runs, improvements or degradations, pattern identification
2. **Multi-Run Context** — User load scaling (e.g., 25 -> 500 VUs), throughput changes, success rate consistency
3. **Infrastructure Insights** — CPU/Memory scaling behavior, resource utilization patterns, correlation between load and usage
4. **Aggregated Issues** — Recurring vs. one-time issues, issues resolved between runs, critical patterns

**Example comparison executive summary:**
> "Analysis of 5 test runs (25-750 VUs) shows stable system performance under increasing
> load. Throughput scaled linearly from 1.76 to 161.54 req/sec while maintaining 99.98%+
> success rate. CPU utilization increased proportionally (220 -> 1040 mCPU) indicating
> healthy resource scaling."

### Priority Data Files

**For single_run reports (read in this order):**

1. `artifacts/{run_id}/analysis/performance_analysis.json` — Core metrics
2. `artifacts/{run_id}/analysis/performance_summary.md` — Human-readable summary
3. `artifacts/{run_id}/analysis/infrastructure_analysis.json` — Infrastructure metrics
4. `artifacts/{run_id}/analysis/correlation_analysis.json` — Correlations
5. `artifacts/{run_id}/analysis/bottleneck_analysis.json` — Bottleneck analysis
6. `artifacts/{run_id}/analysis/<source>_log_analysis.json` — Source: "jmeter" or "blazemeter"
7. `artifacts/{run_id}/analysis/log_analysis.json` — High-level log analysis incl. Datadog
8. `artifacts/{run_id}/blazemeter/test_config.json` — Test configuration
9. `artifacts/{run_id}/reports/performance_report_{run_id}.md` — Current report

**For comparison reports (read in this order):**

1. `artifacts/comparisons/{comparison_id}/comparison_metadata_*.json` — Run IDs and config
2. `artifacts/comparisons/{comparison_id}/comparison_report_*.md` — Current comparison report
3. For each run in `run_id_list`:
   - `artifacts/{run_id}/reports/report_metadata_{run_id}.json` — Individual run metrics
   - `artifacts/{run_id}/analysis/performance_analysis.json` — Detailed metrics per run

### Related Rules

- **`prerequisites.mdc`** — `test_run_id` and artifact structure validation
- **`skill-execution-rules.mdc`** — Follow steps in order, collect inputs first, do not skip
- **`mcp-error-handling.mdc`** — MCP tool error handling (retry policy, reporting format)

### Important Notes

- The original report must exist before running the revision workflow.
- Sections must be enabled in `report_config.yaml` before they can be revised. All sections
  are disabled by default.
- Each call to `prepare_revision_context` creates a new version. Previous versions are
  preserved for comparison.
- The original report and metadata are backed up before any modifications. Backups are not
  overwritten if they already exist.
- When iterating, provide specific feedback to improve subsequent versions.

---

## Execution

This is an **interactive HITL workflow**. Steps 6-7 repeat as many times as needed
based on user feedback.

---

### Collect Inputs

Ask the user for the following values. Do not proceed until all required values are collected.

```
REQUIRED:
  run_id      = [test run ID for single_run, or comparison_id for comparison reports]
  report_type = ["single_run" (default) or "comparison"]

OPTIONAL:
  additional_context = [project name, purpose, feature/PBI details from ADO/JIRA]
  sections_to_revise = [user preferences on which sections to revise]
```

### Prerequisites Check

**For single_run reports, verify:**
- Report exists at `artifacts/{run_id}/reports/performance_report_{run_id}.md`
- Analysis data exists at `artifacts/{run_id}/analysis/`
- Sections are enabled in `report_config.yaml` under `revisable_sections.single_run`

**For comparison reports, verify:**
- Report exists at `artifacts/comparisons/{comparison_id}/comparison_report_*.md`
- Comparison metadata exists at `artifacts/comparisons/{comparison_id}/comparison_metadata_*.json`
- Individual run reports exist for each run in `run_id_list`
- Sections are enabled in `report_config.yaml` under `revisable_sections.comparison`

Do not proceed until the original report has been generated.

---

### Step 1 — Initialize Task Tracking

**Action:** Create task items to monitor progress:

- Discovery: Run `discover_revision_data`
- AI Generation: Read data files and generate content
- Save Revisions: Run `prepare_revision_context` (per section)
- Assembly: Run `revise_performance_test_report`
- Review: User reviews revised report
- HITL Iteration (if needed)
- Confluence Publishing (if needed)

---

### Step 2 — Discovery

**Input:** `run_id`, `report_type`, `additional_context` (optional)

**Action:** Call MCP tool `discover_revision_data`

```
discover_revision_data(
  run_id             = {run_id},
  report_type        = {report_type},
  additional_context = {additional_context}
)
```

**Expected response:**

```json
{
  "data_sources": { "blazemeter": [...], "datadog": [...], "analysis": [...], "reports": [...] },
  "revisable_sections": [ { "section_id": "...", "enabled": true/false, ... } ],
  "enabled_section_count": 3,
  "revision_output_path": "artifacts/{run_id}/reports/revisions/",
  "existing_revisions": { ... },
  "revision_guidelines": "..."
}
```

**Save:**
- `data_sources` = file paths organized by MCP source
- `revisable_sections` = list of sections with enabled/disabled status
- `enabled_section_count` = number of sections ready for revision

**Validation:** Verify `enabled_section_count > 0`. If no sections are enabled, inform
the user to update `report_config.yaml`:

```
Location: perfreport-mcp/report_config.yaml
Section: revisable_sections.single_run (or .comparison)
Set enabled: true for desired sections
```

**On error:** If the tool fails, check `run_id`, verify the artifacts folder exists,
and ensure the original report was generated first. Stop and report to user.

---

### Step 3 — AI Generation

**Input:** `data_sources` (from Step 2), `report_type`, `additional_context`

**Action:** Read the priority data files listed in the Reference section to build context.

For each **enabled** section, generate revised content following the AI Content Guidelines
in the Reference section:

**Single-run sections:**
- `executive_summary` — 3-5 sentences, key metrics, critical issues
- `key_observations` — 3-7 bullet points prioritized by impact
- `issues_table` — Markdown table sorted by severity
- `jmeter_log_analysis` — Error categorization, affected APIs, JTL correlation findings
- `bottleneck_analysis` — Degradation thresholds, severity breakdown, per-endpoint findings

**Comparison sections:**
- `executive_summary` — Overall comparison findings across runs
- `key_findings` — Trends and insights, 3-7 bullet points
- `issues_summary` — Aggregated issues, recurring vs. one-time
- `overall_trend_summary` — Performance trend narrative across runs
- `correlation_insights_section` — Performance-infrastructure correlation analysis

Use the data from the analysis files to produce specific, data-driven content.

**Save:** `generated_content` = dict mapping section_id to generated markdown content.

---

### Step 4 — Save Revisions

**Input:** `run_id`, `report_type`, `generated_content` (from Step 3), `additional_context`

**Action:** For each enabled section, call MCP tool `prepare_revision_context`:

```
prepare_revision_context(
  run_id             = {run_id},
  section_id         = {section_id},
  revised_content    = {content for this section},
  report_type        = {report_type},
  additional_context = {additional_context}
)
```

**Expected response:**

```json
{
  "section_full_id": "single_run.executive_summary",
  "revision_number": 1,
  "revision_path": "artifacts/{run_id}/reports/revisions/AI_EXECUTIVE_SUMMARY_v1.md",
  "previous_versions": []
}
```

**Repeat** for each enabled section returned by `discover_revision_data`.

**Single-run sections:**
1. `executive_summary` -> save executive summary content
2. `key_observations` -> save key observations content
3. `issues_table` -> save issues table content
4. `jmeter_log_analysis` -> save JMeter log analysis content
5. `bottleneck_analysis` -> save bottleneck analysis content

**Comparison sections:**
1. `executive_summary` -> save executive summary content
2. `key_findings` -> save key findings content
3. `issues_summary` -> save issues summary content
4. `overall_trend_summary` -> save overall trend summary content
5. `correlation_insights_section` -> save correlation insights content

Only process sections where `enabled: true` in the discovery response.

**Save:** Track which sections were saved and their version numbers.

**On error:** If the tool fails, check `section_id` is valid, content is not empty,
and `report_type` matches the `run_id`. Stop and report to user.

---

### Step 5 — Assembly

**Input:** `run_id`, `report_type`

**Action:** Call MCP tool `revise_performance_test_report`

```
revise_performance_test_report(
  run_id           = {run_id},
  report_type      = {report_type},
  revision_version = {optional — defaults to latest}
)
```

The tool:
1. Backs up original report to `*_original.md`
2. Backs up metadata to `*_original.json`
3. Replaces placeholders with AI-revised content
4. Saves revised report to `*_revised.md`
5. Updates metadata with revision info

**Expected response:**

```json
{
  "status": "success",
  "revised_report_path": "artifacts/{run_id}/reports/performance_report_{run_id}_revised.md",
  "backup_report_path": "artifacts/{run_id}/reports/performance_report_{run_id}_original.md",
  "sections_revised": ["executive_summary", "key_observations", "issues_table"],
  "revision_versions_used": { "executive_summary": 1, "key_observations": 1, "issues_table": 1 },
  "warnings": []
}
```

**Save:** `revised_report_path`, `sections_revised`, `revision_versions_used`.

**Validation:** Verify `status` is `"success"`, `sections_revised` contains all expected
sections, `revised_report_path` exists. Review any warnings.

**On error:** Verify revision files exist in the revisions folder and at least one section
is enabled. Stop and report to user.

---

### Step 6 — User Review

**Input:** `revised_report_path`, `sections_revised`, `revision_versions_used`

**Action:** Present the results to the user:

1. Display the path to the revised report
2. Summarize which sections were revised
3. Show the version numbers used
4. Note any warnings from the assembly

**Ask the user:**
- "Would you like to review the revised report?"
- "Are there any sections that need further refinement?"
- "Should I make any adjustments to the content?"

If the user is satisfied, go to Step 8.
If the user wants changes, go to Step 7.

---

### Step 7 — HITL Iteration (repeatable)

**When:** The user requests changes to specific sections.

#### 7a. Gather Feedback

Collect from the user:
- Which section needs revision?
- What changes are needed?
- Any additional context to incorporate?

#### 7b. Re-generate Content

Generate new content for the specified section incorporating the user's feedback.

#### 7c. Save New Version

```
prepare_revision_context(
  run_id             = {run_id},
  section_id         = {section_id},
  revised_content    = {new content},
  report_type        = {report_type},
  additional_context = {feedback context}
)
```

The tool automatically increments the version number (e.g., `AI_EXECUTIVE_SUMMARY_v2.md`).

#### 7d. Re-assemble Report

```
revise_performance_test_report(
  run_id           = {run_id},
  report_type      = {report_type},
  revision_version = {optional — specify version or omit for latest}
)
```

#### 7e. Present Updated Results

Go back to **Step 6** to present the updated report and ask for feedback.

Continue the HITL loop until the user approves the revised report.

---

### Step 8 — Final Output Summary

**Action:** Present a final summary to the user.

#### File Locations

**For single_run reports:**
- Original (backed up): `artifacts/{run_id}/reports/performance_report_{run_id}_original.md`
- Revised: `artifacts/{run_id}/reports/performance_report_{run_id}_revised.md`
- Revision files: `artifacts/{run_id}/reports/revisions/`
- Metadata: `artifacts/{run_id}/reports/report_metadata_{run_id}.json`

**For comparison reports:**
- Original (backed up): `artifacts/comparisons/{comparison_id}/comparison_report_*_original.md`
- Revised: `artifacts/comparisons/{comparison_id}/comparison_report_*_revised.md`
- Revision files: `artifacts/comparisons/{comparison_id}/revisions/`
- Metadata: `artifacts/comparisons/{comparison_id}/comparison_metadata_*.json`

#### Revision Summary Table (example for single_run)

| Section | Versions Created | Final Version Used |
|---------|------------------|-------------------|
| executive_summary | v1, v2 | v2 |
| key_observations | v1 | v1 |
| issues_table | v1 | v1 |
| jmeter_log_analysis | v1 | v1 |
| bottleneck_analysis | v1 | v1 |

#### Next Steps

Ask the user:
- "Would you like to publish the revised report to Confluence?" — If yes, go to Step 9.
- "Would you like to generate additional charts?" — Use `create_chart` from PerfReport MCP.
- "Would you like to create a comparison report?" — Follow the skill at
  `.cursor/skills/comparison-report-workflow/SKILL.md`.

---

### Step 9 — Publish Revised Report to Confluence (Optional)

**When:** The user wants to publish the revised report to an existing Confluence page.

**Prerequisites:**
- Revised report exists (`*_revised.md`)
- `page_ref` (page ID) from the initial publish is available
- Images have already been attached during the initial publish (no re-attach needed)
- `confluence_mode` = `"cloud"` or `"onprem"`

#### 9a. Convert Revised Markdown to XHTML

**For single_run reports:**

```
convert_markdown_to_xhtml(
  test_run_id = {run_id},
  filename    = "performance_report_{run_id}_revised.md",
  report_type = "single_run"
)
```

**For comparison reports:**

```
convert_markdown_to_xhtml(
  test_run_id = {comparison_id},
  filename    = "comparison_report_{ids}_revised.md",
  report_type = "comparison"
)
```

This creates a `*_revised.xhtml` file in the reports folder.

#### 9b. Update Confluence Page with Revised Content

**For single_run reports:**

```
update_page(
  page_ref    = {page_ref},
  test_run_id = {run_id},
  mode        = {confluence_mode},
  use_revised = true,
  report_type = "single_run"
)
```

**For comparison reports:**

```
update_page(
  page_ref    = {page_ref},
  test_run_id = {comparison_id},
  mode        = {confluence_mode},
  use_revised = true,
  report_type = "comparison"
)
```

The `update_page` tool with `use_revised=true`:
1. Selects the `*_revised.xhtml` file (not the main XHTML)
2. Substitutes chart placeholders with embedded `<ac:image>` markup
3. Creates a `*_revised_with_images.xhtml` file for reference
4. Updates the Confluence page with the revised content

Images are already attached from the initial publish. Only placeholder substitution
and page content update are needed.

#### 9c. Verification

Verify:
- Response shows `"used_revised": true`
- `xhtml_source` field shows the `*_revised.xhtml` filename
- Chart placeholders were replaced (check `placeholders_replaced`)
- Page URL is accessible and shows the revised content

**On error:** If API calls fail, retry up to 3 times. Report error to user.

---

## Error Handling

These rules apply to every step:

- **PerfReport MCP tools** (discover, prepare, revise): These are Python code executions.
  Do NOT retry on failure. Report the error with full details. Do NOT attempt to fix code.
- **Confluence MCP tools** (convert, update_page): These are API calls. Retry up to 3 times.
  Wait 5-10 seconds between retries.
- If any step fails, stop and report to the user with:
  - Which tool failed
  - Full error message
  - What was expected vs. what happened
- Do NOT proceed to the next step if the current step failed.
- Ask the user for next steps on any error.
