# MCP Performance Suite - Changelog (January 2026)

This document contains all enhancements and new features added to the MCP Performance Suite during January 2026.

---

## Table of Contents

- [1. AI-Assisted Report Revision (January 31, 2026)](#1-ai-assisted-report-revision-january-31-2026)
  - [1.1 Overview](#11-overview)
  - [1.2 New MCP Tools](#12-new-mcp-tools)
  - [1.3 Configuration](#13-configuration)
  - [1.4 Workflow](#14-workflow)
  - [1.5 Files Created/Modified](#15-files-createdmodified)
- [2. Datadog MCP Dynamic Limits (January 23, 2026)](#2-datadog-mcp-dynamic-limits-january-23-2026)
  - [2.1 Phase 1: Datadog MCP Changes](#21-phase-1-datadog-mcp-changes)
  - [2.2 Phase 2: PerfAnalysis MCP Changes](#22-phase-2-perfanalysis-mcp-changes)
  - [2.3 Phase 3: PerfReport MCP Changes](#23-phase-3-perfreport-mcp-changes)
- [3. Report Enhancements (PerfReport MCP)](#3-report-enhancements-perfreport-mcp)
  - [3.1 Human-Readable Test Duration](#31-human-readable-test-duration)
  - [3.2 Cleaner Infrastructure Summaries](#32-cleaner-infrastructure-summaries)
  - [3.3 Formatted Bottleneck Analysis](#33-formatted-bottleneck-analysis)
  - [3.4 BlazeMeter Report Link](#34-blazemeter-report-link)
  - [3.5 Cleaner Service/Host Names](#35-cleaner-servicehost-names)
  - [3.6 Configurable Resource Allocation Display](#36-configurable-resource-allocation-display)
- [4. New Charts Available](#4-new-charts-available)
  - [4.1 CPU Utilization vs Virtual Users (Dual-Axis)](#41-cpu-utilization-vs-virtual-users-dual-axis)
  - [4.2 Memory Utilization vs Virtual Users (Dual-Axis)](#42-memory-utilization-vs-virtual-users-dual-axis)
  - [4.3 CPU Core Usage Over Time](#43-cpu-core-usage-over-time)
  - [4.4 Memory Usage Over Time](#44-memory-usage-over-time)
  - [4.5 CPU Core Comparison Bar Chart](#45-cpu-core-comparison-bar-chart)
  - [4.6 Memory Usage Comparison Bar Chart](#46-memory-usage-comparison-bar-chart)

---

## 1. AI-Assisted Report Revision (January 31, 2026)

### 1.1 Overview

A new AI-assisted workflow enables intelligent revision of performance test reports using a Human-In-The-Loop (HITL) approach. This feature allows MCP clients like Cursor to analyze test data and generate improved content for specific report sections while preserving all original metrics, tables, and data.

**Key Features:**
- AI-generated Executive Summary, Key Observations, and Issues Table
- Full preservation of original report data (BlazeMeter links, API tables, infrastructure metrics)
- Version-controlled revisions with rollback capability
- Support for iterative feedback and refinement
- Configurable sections (enabled/disabled per section)

---

### 1.2 New MCP Tools

Three new tools were added to PerfReport MCP:

| Tool | Purpose |
|------|---------|
| `discover_revision_data` | Gathers all available data files and provides AI with context for generating revisions |
| `prepare_revision_context` | Saves AI-generated content to versioned markdown files for HITL iteration |
| `revise_performance_test_report` | Assembles the final revised report using AI content + original data |

#### discover_revision_data

```python
discover_revision_data(
    run_id: str,                    # Test run ID
    report_type: str = "single_run", # "single_run" or "comparison"
    additional_context: str = None   # Optional project context
) -> dict
```

**Returns:**
- `data_sources`: Organized file paths by MCP source (blazemeter, datadog, analysis, reports)
- `revisable_sections`: All sections with enabled/disabled status
- `existing_revisions`: Any previous revision versions per section
- `revision_guidelines`: Instructions for generating content

#### prepare_revision_context

```python
prepare_revision_context(
    run_id: str,
    section_id: str,                # "executive_summary", "key_observations", "issues_table"
    revised_content: str,           # AI-generated markdown content
    report_type: str = "single_run",
    additional_context: str = None  # For traceability
) -> dict
```

**Returns:**
- `section_full_id`: Composite ID (e.g., "single_run.executive_summary")
- `revision_number`: Auto-incremented version (1, 2, 3...)
- `revision_path`: Full path to saved file

#### revise_performance_test_report

```python
revise_performance_test_report(
    run_id: str,
    report_type: str = "single_run",
    revision_version: int = None    # Optional specific version, defaults to latest
) -> dict
```

**Returns:**
- `revised_report_path`: Path to new revised report
- `backup_report_path`: Path to original (backed up)
- `sections_revised`: List of sections updated
- `ai_template_path`: Path to AI-enhanced template created

---

### 1.3 Configuration

New `revisable_sections` block added to `report_config.yaml`:

```yaml
revisable_sections:
  single_run:
    executive_summary:
      enabled: false  # Set to true to enable revision
      placeholder: "EXECUTIVE_SUMMARY"
      ai_placeholder: "AI_EXECUTIVE_SUMMARY"
      output_file: "AI_EXECUTIVE_SUMMARY"
      description: "High-level summary of test results"
    key_observations:
      enabled: false
      placeholder: "KEY_OBSERVATIONS"
      ai_placeholder: "AI_KEY_OBSERVATIONS"
      output_file: "AI_KEY_OBSERVATIONS"
      description: "Key findings and observations"
    issues_table:
      enabled: false
      placeholder: "ISSUES_TABLE"
      ai_placeholder: "AI_ISSUES_TABLE"
      output_file: "AI_ISSUES_TABLE"
      description: "Table of issues observed during testing"
  comparison:
    # Similar structure for comparison reports
```

**Default Behavior:** All sections are disabled by default. Users must explicitly enable sections for revision.

---

### 1.4 Workflow

The AI-assisted revision follows this workflow:

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  1. Discovery       │    │  2. AI Generation   │    │  3. Save Revisions  │
│                     │    │                     │    │                     │
│ discover_revision   │──▶│ AI reads data        │──▶│ prepare_revision    │
│ _data()             │    │ & generates content │    │ _context()          │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
                                                               │
                                                               ▼
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│  6. HITL Iteration  │    │  5. User Review     │    │  4. Assembly        │
│     (Optional)      │◀──│                      │◀──│                     │
│                     │    │ Review revised      │    │ revise_performance  │
│ Repeat steps 2-4    │    │ report              │    │ _test_report()      │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

**Example Artifacts Structure:**
```
artifacts/{run_id}/
├── reports/
│   ├── performance_report_{run_id}.md          # Current report
│   ├── performance_report_{run_id}_original.md # Backed up original
│   ├── performance_report_{run_id}_revised.md  # AI-revised report
│   ├── report_metadata_{run_id}.json           # Updated metadata
│   ├── report_metadata_{run_id}_original.json  # Backed up metadata
│   └── revisions/                              # AI content versions
│       ├── AI_EXECUTIVE_SUMMARY_v1.md
│       ├── AI_EXECUTIVE_SUMMARY_v2.md          # HITL iteration
│       ├── AI_KEY_OBSERVATIONS_v1.md
│       └── AI_ISSUES_TABLE_v1.md
```

**AI Template Creation:**
- Creates `ai_<template_name>.md` in templates folder
- Replaces original placeholders with AI placeholders for enabled sections
- Reused for future revisions of reports using the same template

---

### 1.5 Files Created/Modified

#### New Files

| File | Description |
|------|-------------|
| `perfreport-mcp/services/revision_data_discovery.py` | Discovery tool implementation |
| `perfreport-mcp/services/revision_context_manager.py` | Save/load revision content with versioning |
| `perfreport-mcp/services/report_revision_generator.py` | Report assembly with AI content |
| `perfreport-mcp/utils/revision_utils.py` | Path helpers, validation, version management |
| `.cursor/rules/report-revision-workflow.mdc` | Cursor Rules for orchestrating the workflow |

#### Modified Files

| File | Changes |
|------|---------|
| `perfreport-mcp/perfreport.py` | Registered 3 new MCP tools |
| `perfreport-mcp/utils/config.py` | Added `load_revisable_sections_config()`, `get_section_config()` |
| `perfreport-mcp/report_config.example.yaml` | Added `revisable_sections` configuration block |

---

### Technical Notes

1. **Data Preservation:** The revision generator reuses `_build_report_context()` from `report_generator.py` to ensure all original data (tables, links, metrics) is populated correctly.

2. **Version Control:** Each call to `prepare_revision_context()` creates a new version file (v1, v2, v3...). Previous versions are preserved for comparison.

3. **Backup Safety:** Original report and metadata are backed up with `_original` suffix before any modifications. Backups are not overwritten.

4. **Template Reuse:** AI templates are created once and reused for future revisions of reports using the same base template.

5. **Glossary Support:** Cursor Rules include guidelines for adding technical term definitions (footnotes for 1-2 terms, glossary table for 3+).

---

## 2. Datadog MCP Dynamic Limits (January 23, 2026)

**Summary:** CPU and Memory resource limits are now queried dynamically from Datadog rather than relying on static configurations in `environments.json`. This ensures accurate % utilization calculations that reflect actual Kubernetes resource configurations.

### Problem Solved

Previously, the Datadog MCP calculated % CPU/Memory utilization by:
1. Querying **usage** from Datadog (`kubernetes.cpu.usage.total`, `kubernetes.memory.usage`)
2. Reading **limits** from static `environments.json` configuration
3. Calculating: `% = (usage / static_limit) * 100`

**Issues:**
- Static limits become stale when DevOps changes resource allocations
- Manual maintenance burden to keep configurations in sync
- Inaccurate KPIs when static config doesn't match actual K8s limits

**Solution:** Query both usage AND limits directly from Datadog, ensuring % utilization is always calculated from the actual Kubernetes configuration.

---

### 2.1 Phase 1: Datadog MCP Changes

**File:** `datadog-mcp/services/datadog_api.py`

#### New Query Functions

Added functions that return both usage and limits queries:
- `svc_cpu_with_limits_query()` - Service CPU usage + limits
- `svc_mem_with_limits_query()` - Service Memory usage + limits  
- `pod_cpu_with_limits_query()` - Pod CPU usage + limits
- `pod_mem_with_limits_query()` - Pod Memory usage + limits

#### New Helper Functions

| Function | Purpose |
|----------|---------|
| `_build_combined_metrics_request()` | Builds Datadog v2 API request with both usage and limits queries |
| `_extract_series_with_limits()` | Parses response separating usage (query_index=0) and limits (query_index=1) |
| `_calculate_utilization_with_dynamic_limits()` | Calculates % utilization; returns `-1` when limits not defined |
| `_fill_missing_limits_series()` | Fills `0.0` when Datadog returns no limits data (CSV consistency) |

#### CSV Output Changes

**New metric rows added:**
```csv
# Limits from Datadog (new rows)
env_name,env_tag,k8s,,service*,container,timestamp,kubernetes.cpu.limits,2.0,cores
env_name,env_tag,k8s,,service*,container,timestamp,kubernetes.memory.limits,4294967296.0,bytes

# Utilization calculated from dynamic limits
env_name,env_tag,k8s,,service*,container,timestamp,cpu_util_pct,5.25,%
env_name,env_tag,k8s,,service*,container,timestamp,mem_util_pct,15.17,%

# When limits = 0 (not defined in Kubernetes)
env_name,env_tag,k8s,,service*,container,timestamp,cpu_util_pct,-1,%
```

#### Aggregates Structure Updated

```json
{
  "filter": "application-svc*",
  "entity_type": "service",
  "avg_cpu_nanocores": 1821261.16,
  "avg_mem_bytes": 651773952.0,
  "cpu_limits_available": true,
  "mem_limits_available": true,
  "avg_cpu_pct": 5.25,
  "avg_mem_pct": 15.17
}
```

When limits not defined:
```json
{
  "cpu_limits_available": false,
  "avg_cpu_pct": -1
}
```

---

### 2.2 Phase 2: PerfAnalysis MCP Changes

**File:** `perfanalysis-mcp/services/apm_analyzer.py`

#### Updated `analyze_k8s_entity_metrics()`

- Reads `kubernetes.cpu.limits` and `kubernetes.memory.limits` rows from CSV
- Reads pre-calculated `cpu_util_pct` and `mem_util_pct` values
- Filters out `-1` values when calculating statistics (min/avg/max)
- Sets utilization fields to `None` when limits not defined
- Falls back to `environments.json` only when limits rows are missing entirely (backward compatibility)

#### New `limits_status` Field

JSON output now includes status flags:
```json
{
  "limits_status": {
    "cpu_limits_defined": true,
    "mem_limits_defined": false
  }
}
```

#### Updated `analyze_k8s_utilization()`

- Handles `None` utilization values gracefully
- Reports "limits_not_defined" status in resource insights

---

### 2.3 Phase 3: PerfReport MCP Changes

**File:** `perfreport-mcp/services/report_generator.py`

#### Updated Table Builders

`_build_cpu_utilization_table()` and `_build_memory_utilization_table()`:
- Shows `N/A*` when limits not defined
- Adds explanatory footnote when any service has undefined limits

**Example Output:**
```markdown
| Service Name | Peak (%) | Avg (%) | Min (%) | Allocated |
|--------------|----------|---------|---------|-----------|
| api-gateway | 45.23 | 32.15 | 12.05 | 2.00 |
| auth-service | N/A* | N/A* | N/A* | 0.00 |

*\*N/A indicates CPU limits are not defined in Kubernetes for this service. % utilization cannot be calculated.*
```

#### Updated `_extract_infra_peaks()`

- Safely handles `None` values (skips instead of treating as 0)
- Prevents errors when aggregating infrastructure metrics

---

### Data Flow Summary

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│    Datadog MCP      │    │   PerfAnalysis MCP  │    │   PerfReport MCP    │
│                     │    │                     │    │                     │
│ CSV output:         │──▶│ JSON output:        │───▶│ Report output:      │
│ - cpu_util_pct: -1  │    │ - peak_util: None   │    │ - Peak (%): N/A*    │
│ - limits: 0         │    │ - limits_defined:   │    │ - Footnote added    │
│                     │    │   false             │    │                     │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
```

---

### Backward Compatibility

- **CSV Schema:** Unchanged structure; new metrics added as rows, not columns
- **environments.json:** Not modified; static values ignored for K8s (used as fallback only)
- **Host environments:** Unchanged behavior; dynamic limits only apply to Kubernetes

---

### Files Created/Modified

| File | Changes |
|------|---------|
| `datadog-mcp/services/datadog_api.py` | Dynamic limits queries, combined usage+limits requests, utilization calculation with -1 marker, CSV consistency fix |
| `perfanalysis-mcp/services/apm_analyzer.py` | Read limits from CSV, filter -1 values, limits_status tracking, None handling for undefined limits |
| `perfreport-mcp/services/report_generator.py` | N/A* footnotes for undefined limits, safe None handling in `_extract_infra_peaks()` |

---

## 3. Report Enhancements (PerfReport MCP)

### 3.1 Human-Readable Test Duration

**What Changed:** Test duration is now displayed in a human-friendly format instead of raw seconds.

**Before:**
```
| Test Duration | 3600 |
```

**After:**
```
| Test Duration | 1h 0m 0s |
```

**Examples:**
| Raw Seconds | Human-Readable |
|-------------|----------------|
| 45 | 45s |
| 125 | 2m 5s |
| 3665 | 1h 1m 5s |
| 7200 | 2h 0m 0s |

**Why This Matters:** Performance engineers and stakeholders can immediately understand test duration without mental math. A test that ran for "1h 30m" is instantly comprehensible compared to "5400 seconds".

---

### 3.2 Cleaner Infrastructure Summaries

**What Changed:** Removed auto-generated headers and footers from infrastructure and correlation analysis sections that were redundant in the final report.

**Before:**
```markdown
## Infrastructure Summary

Infrastructure Analysis Report - Run 123456789
Generated: 2026-01-17T10:30:00

The infrastructure analysis shows...
```

**After:**
```markdown
## Infrastructure Summary

The infrastructure analysis shows...
```

**Why This Matters:** Reports are cleaner and more professional. The redundant headers were artifacts from the analysis phase that don't add value in the final report context.

---

### 3.3 Formatted Bottleneck Analysis

**What Changed:** Bottleneck insights are now displayed as properly formatted markdown bullet points instead of raw list notation.

**Before:**
```
['High CPU correlation with response time degradation', 'Memory pressure detected during peak load', 'Database connection pool exhaustion suspected']
```

**After:**
```markdown
Based on correlation and infrastructure analysis:

- High CPU correlation with response time degradation
- Memory pressure detected during peak load
- Database connection pool exhaustion suspected
```

**Why This Matters:** Stakeholders can quickly scan and understand the key bottlenecks identified during the test. The formatted output is ready for presentation and review meetings.

---

### 3.4 BlazeMeter Report Link

**What Changed:** Performance reports now include a direct link to the BlazeMeter public report for the test run.

**Example:**
```markdown
### 1.1 Test Configuration

| Configuration Item | Value |
|-------------------|-------|
| Test Run ID | 123456789 |
| Test Date | 2026-01-15 |
| ... | ... |
| BlazeMeter Report | [View Report](https://a.blazemeter.com/app/?public-token=abc123#/masters/123456789/summary) |
```

**Workflow Prerequisite:** The BlazeMeter workflow must call `get_public_report` and save the output to `artifacts/{run_id}/blazemeter/public_report.json` before generating the performance report.

**Why This Matters:** Provides one-click access to the interactive BlazeMeter dashboard with detailed drill-down capabilities, response time distributions, and real-time graphs that complement the static report.

---

### 3.5 Cleaner Service/Host Names

**What Changed:** Service and host names in infrastructure tables are now displayed without environment prefixes and Datadog query wildcards.

**Before:**
```markdown
| Service Name | Peak (%) | Avg (%) | Allocated |
|--------------|----------|---------|-----------|
| UAT::api-gateway* | 45.23 | 32.15 | 4 cores |
| UAT::app-service* | 38.91 | 25.67 | 2 cores |
```

**After:**
```markdown
| Service Name | Peak (%) | Avg (%) | Allocated |
|--------------|----------|---------|-----------|
| api-gateway | 45.23 | 32.15 | 4 cores |
| app-service | 38.91 | 25.67 | 2 cores |
```

**Why This Matters:** 
- Tables are easier to read without visual clutter
- Service names match what engineers see in their Kubernetes dashboards
- Reports can be shared with stakeholders who don't need to understand Datadog query syntax

---

### 3.6 Configurable Resource Allocation Display

**What Changed:** A new `report_config.yaml` file allows you to show or hide resource allocation columns in infrastructure tables.

**Configuration File:** `perfreport-mcp/report_config.yaml`

```yaml
version: "1.0"

infrastructure_tables:
  cpu_utilization:
    show_allocated_column: true    # Show/hide "Allocated" column
  cpu_core_usage:
    show_allocated_column: true
  memory_utilization:
    show_allocated_column: true
  memory_usage:
    show_allocated_column: true
```

**With Allocation Columns (default):**
```markdown
| Service Name | Peak (%) | Avg (%) | Min (%) | Allocated |
|--------------|----------|---------|---------|-----------|
| api-gateway | 45.23 | 32.15 | 12.05 | 4 cores |
```

**Without Allocation Columns:**
```markdown
| Service Name | Peak (%) | Avg (%) | Min (%) |
|--------------|----------|---------|---------|
| api-gateway | 45.23 | 32.15 | 12.05 |
```

**Why This Matters:**
- Resource allocation values from `environments.json` may not always be accurate
- Some cloud environments use auto-scaling without fixed limits
- Teams can focus on actual usage metrics when allocation data is unreliable

---

### Files Created/Modified

| File | Changes |
|------|---------|
| `perfreport-mcp/utils/report_utils.py` | New shared utility functions for report formatting |
| `perfreport-mcp/report_config.yaml` | New report display configuration file |
| `perfreport-mcp/report_config.example.yaml` | New documented configuration template |
| `perfreport-mcp/services/report_generator.py` | Duration formatting, header stripping, bottleneck formatting, BlazeMeter link, service name cleanup, config-driven allocation columns |
| `perfreport-mcp/services/comparison_report_generator.py` | Duration formatting integration |
| `perfreport-mcp/templates/default_report_template.md` | BlazeMeter report link placeholder |
| `.cursor/rules/performance-testing-workflow.mdc` | Workflow updates for public report saving |

---

## 4. New Charts Available

### 4.1 CPU Utilization vs Virtual Users (Dual-Axis)

**Chart ID:** `CPU_UTILIZATION_VUSERS_DUALAXIS`

**What It Shows:** A dual-axis line chart correlating CPU utilization (%) with the number of virtual users over time.

```
┌────────────────────────────────────────────────────────────┐
│  CPU Utilization vs Virtual Users                          │
│                                                            │
│  CPU %                                          VUsers     │
│  100 ┤                                              │ 500  │
│   80 ┤         ████████████                         │ 400  │
│   60 ┤    ████─            ─████                    │ 300  │
│   40 ┤ ██─                      ─██                 │ 200  │
│   20 ┤─                              ─              │ 100  │
│    0 └──────────────────────────────────────────────┘ 0    │
│       08:00   09:00   10:00   11:00   12:00                │
│                     Time (hh:mm) UTC                       │
│                                                            │
│  ── CPU Utilization (%)   ── Virtual Users                 │
└────────────────────────────────────────────────────────────┘
```

**Why It's Important:**
- **Identifies CPU bottlenecks:** If CPU rises sharply while virtual users increase, the infrastructure may be CPU-bound
- **Capacity planning:** Shows how much headroom exists before CPU becomes saturated
- **Correlation analysis:** Helps determine if high response times correlate with CPU pressure

**When to Use:** Include this chart when investigating whether infrastructure resources are keeping pace with load. Essential for capacity planning and right-sizing exercises.

---

### 4.2 Memory Utilization vs Virtual Users (Dual-Axis)

**Chart ID:** `MEMORY_UTILIZATION_VUSERS_DUALAXIS`

**What It Shows:** A dual-axis line chart correlating memory utilization (%) with virtual users over time.

**Why It's Important:**
- **Detects memory leaks:** Memory that climbs continuously without stabilizing may indicate a leak
- **Identifies memory pressure:** Shows if memory becomes constrained as load increases
- **GC impact analysis:** Memory sawtooth patterns can reveal garbage collection impacts

**When to Use:** Include when memory-intensive operations are under test, or when investigating out-of-memory errors and performance degradation over long-running tests.

---

### 4.3 CPU Core Usage Over Time

**Chart ID:** `CPU_CORES_LINE`

**What It Shows:** Actual CPU consumption in Cores or Millicores (configurable) over time for a specific service or host.

**Unit Configuration (in `chart_schema.yaml`):**
```yaml
unit:
  type: "cores"      # Options: "cores", "millicores"
```

**Example Output:**
- **Cores:** `0.85 Cores`, `1.25 Cores`
- **Millicores:** `850 mCPU`, `1250 mCPU`

**Why It's Important:**
- **Actual resource consumption:** Shows real CPU usage, not just percentages
- **Kubernetes resource requests:** Compare against pod CPU requests/limits in Kubernetes
- **Cost optimization:** Helps right-size CPU allocations to reduce cloud costs

**When to Use:** Essential for Kubernetes environments where CPU is allocated in cores/millicores. Use alongside percentage charts to understand both relative and absolute consumption.

---

### 4.4 Memory Usage Over Time

**Chart ID:** `MEMORY_USAGE_LINE`

**What It Shows:** Actual memory consumption in GB or MB (configurable) over time for a specific service or host.

**Unit Configuration (in `chart_schema.yaml`):**
```yaml
unit:
  type: "gb"        # Options: "gb", "mb"
```

**Example Output:**
- **GB:** `2.45 GB`, `4.12 GB`
- **MB:** `2508 MB`, `4218 MB`

**Why It's Important:**
- **Absolute memory tracking:** See exactly how much RAM is consumed
- **Kubernetes memory limits:** Compare against pod memory requests/limits
- **Leak detection:** Easier to spot memory leaks when viewing absolute values vs percentages

**When to Use:** Use when you need to compare memory usage against Kubernetes resource quotas or when investigating memory-related issues.

---

### 4.5 CPU Core Comparison Bar Chart

**Chart ID:** `CPU_CORE_COMPARISON_BAR`

**What It Shows:** Vertical bar chart comparing peak CPU core usage across multiple test runs for a specific service/host. Each bar represents a test run on the X-axis, with CPU usage values on the Y-axis.

```
┌────────────────────────────────────────────────────────────┐
│  CPU Core Usage Comparison - api-gateway                   │
│                                                            │
│  CPU (Cores)                                               │
│  2.0 ┤                                                     │
│      │                   1.58                              │
│  1.5 ┤       1.25        ┌───┐                             │
│      │       ┌───┐       │   │        1.12                 │
│  1.0 ┤       │   │       │   │       ┌───┐                 │
│      │       │   │       │   │       │   │                 │
│  0.5 ┤       │   │       │   │       │   │                 │
│      │       │   │       │   │       │   │                 │
│  0.0 └───────┴───┴───────┴───┴───────┴───┴─────────────    │
│              Run         Run         Run                   │
│           123456789    80840304    81012456                │
│                        Test Run                            │
└────────────────────────────────────────────────────────────┘
```

**Unit Configuration:** Supports both `cores` and `millicores` display formats.

**Why It's Important:**
- **Trend analysis:** Quickly see if CPU usage is increasing across releases
- **Regression detection:** Identify if a new deployment consumes more CPU
- **Resource planning:** Track resource consumption growth over time

**When to Use:** Include in comparison reports when analyzing multiple test runs (e.g., before/after optimization, release comparison, capacity trend analysis).

---

### 4.6 Memory Usage Comparison Bar Chart

**Chart ID:** `MEMORY_USAGE_COMPARISON_BAR`

**What It Shows:** Vertical bar chart comparing peak memory usage across multiple test runs for a specific service/host. Each bar represents a test run on the X-axis, with memory usage values on the Y-axis.

```
┌────────────────────────────────────────────────────────────┐
│  Memory Usage Comparison - api-gateway                     │
│                                                            │
│  Memory (GB)                                               │
│  4.0 ┤                                                     │
│      │                                                     │
│  3.0 ┤                   3.12        2.89                  │
│      │                   ┌───┐       ┌───┐                 │
│  2.0 ┤       2.45        │   │       │   │                 │
│      │       ┌───┐       │   │       │   │                 │
│  1.0 ┤       │   │       │   │       │   │                 │
│      │       │   │       │   │       │   │                 │
│  0.0 └───────┴───┴───────┴───┴───────┴───┴─────────────    │
│              Run         Run         Run                   │
│           123456789    80840304    81012456                │
│                        Test Run                            │
└────────────────────────────────────────────────────────────┘
```

**Unit Configuration:** Supports both `gb` and `mb` display formats.

**Why It's Important:**
- **Memory growth tracking:** Identify services with increasing memory footprints
- **Leak investigation:** Memory that grows across test runs may indicate a slow leak
- **Optimization validation:** Confirm memory optimizations are effective

**When to Use:** Include in comparison reports alongside CPU comparison charts for a complete picture of resource consumption trends.

---

### Files Created/Modified

| File | Changes |
|------|---------|
| `perfreport-mcp/services/charts/comparison_bar_charts.py` | New horizontal bar chart generators |
| `perfreport-mcp/services/charts/dual_axis_charts.py` | New CPU/Memory vs VUsers charts |
| `perfreport-mcp/services/charts/single_axis_charts.py` | New CPU Cores and Memory Usage charts |
| `perfreport-mcp/services/chart_generator.py` | New chart registrations and data source handlers |
| `perfreport-mcp/chart_schema.yaml` | New chart specifications |

---

*Last Updated: January 31, 2026*
