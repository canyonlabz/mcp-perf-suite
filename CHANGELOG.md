# MCP Performance Suite - Changelog

This document summarizes the enhancements and new features added to the MCP Performance Suite.

---

## Table of Contents

- [1. Multi-Session Artifact Handling (February 2026)](#1-multi-session-artifact-handling-february-2026)
  - [1.1 Overview](#11-overview)
  - [1.2 New MCP Tool](#12-new-mcp-tool)
  - [1.3 Design](#13-design)
  - [1.4 Configuration](#14-configuration)
  - [1.5 Files Created/Modified](#15-files-createdmodified)
- [2. Bottleneck Analyzer v0.2 (February 2026)](#2-bottleneck-analyzer-v02-february-2026)
  - [2.1 Overview](#21-overview)
  - [2.2 MCP Tool](#22-mcp-tool)
  - [2.3 What It Does](#23-what-it-does)
  - [2.4 Key Capabilities (v0.2)](#24-key-capabilities-v02)
  - [2.5 Two-Phase Analysis Architecture](#25-two-phase-analysis-architecture)
  - [2.6 Finding Classifications](#26-finding-classifications)
  - [2.7 Raw Metrics Fallback (Missing K8s Limits)](#27-raw-metrics-fallback-missing-k8s-limits)
  - [2.8 Configuration](#28-configuration)
  - [2.9 Output Files](#29-output-files)
  - [2.10 Files Created/Modified](#210-files-createdmodified)
- [3. JMeter Log Analysis Tool (February 2026)](#3-jmeter-log-analysis-tool-february-2026)
  - [3.1 Overview](#31-overview)
  - [3.2 New MCP Tool](#32-new-mcp-tool)
  - [3.3 Configuration](#33-configuration)
  - [3.4 Output Files](#34-output-files)
  - [3.5 Key Capabilities](#35-key-capabilities)
  - [3.6 Files Created/Modified](#36-files-createdmodified)
- [4. AI-Assisted Report Revision (January 31, 2026)](#4-ai-assisted-report-revision-january-31-2026)
  - [4.1 Overview](#41-overview)
  - [4.2 New MCP Tools](#42-new-mcp-tools)
  - [4.3 Configuration](#43-configuration)
  - [4.4 Workflow](#44-workflow)
  - [4.5 Files Created/Modified](#45-files-createdmodified)
- [5. Datadog MCP Dynamic Limits (January 23, 2026)](#5-datadog-mcp-dynamic-limits-january-23-2026)
  - [5.1 Phase 1: Datadog MCP Changes](#51-phase-1-datadog-mcp-changes)
  - [5.2 Phase 2: PerfAnalysis MCP Changes](#52-phase-2-perfanalysis-mcp-changes)
  - [5.3 Phase 3: PerfReport MCP Changes](#53-phase-3-perfreport-mcp-changes)
- [6. Report Enhancements (PerfReport MCP)](#6-report-enhancements-perfreport-mcp)
  - [6.1 Human-Readable Test Duration](#61-human-readable-test-duration)
  - [6.2 Cleaner Infrastructure Summaries](#62-cleaner-infrastructure-summaries)
  - [6.3 Formatted Bottleneck Analysis](#63-formatted-bottleneck-analysis)
  - [6.4 BlazeMeter Report Link](#64-blazemeter-report-link)
  - [6.5 Cleaner Service/Host Names](#65-cleaner-servicehost-names)
  - [6.6 Configurable Resource Allocation Display](#66-configurable-resource-allocation-display)
- [7. New Charts Available](#7-new-charts-available)
  - [7.1 CPU Utilization vs Virtual Users (Dual-Axis)](#71-cpu-utilization-vs-virtual-users-dual-axis)
  - [7.2 Memory Utilization vs Virtual Users (Dual-Axis)](#72-memory-utilization-vs-virtual-users-dual-axis)
  - [7.3 CPU Core Usage Over Time](#73-cpu-core-usage-over-time)
  - [7.4 Memory Usage Over Time](#74-memory-usage-over-time)
  - [7.5 CPU Core Comparison Bar Chart](#75-cpu-core-comparison-bar-chart)
  - [7.6 Memory Usage Comparison Bar Chart](#76-memory-usage-comparison-bar-chart)
- [8. Future Updates](#8-future-updates)

---

## 1. Multi-Session Artifact Handling (February 2026)

### 1.1 Overview

When a BlazeMeter test run uses multiple load generators (engines), each engine produces its own `artifacts.zip` file containing a `kpi.jtl` and `jmeter.log`. Previously, the BlazeMeter MCP tools processed one session at a time, and each subsequent download/extract/process cycle **overwrote** the previous session's files. This meant only the last session's JTL and log data was retained locally, causing incomplete data for downstream analysis tools like `identify_bottlenecks` and `correlate_test_results`.

This enhancement introduces a unified session-based artifact processing model that handles both single-session and multi-session runs through a single consolidated tool.

---

### 1.2 New MCP Tool

| Tool | Purpose |
|------|---------|
| `process_session_artifacts` | Downloads, extracts, and processes artifact ZIPs for all sessions of a BlazeMeter run |

```python
process_session_artifacts(
    run_id: str,          # BlazeMeter run/master ID
    sessions_id: list,    # List of session IDs from get_run_results (sessionsId field)
    ctx: Context          # FastMCP context
) -> dict
```

**Returns:**
- `status`: `"success"` (all done), `"partial"` (some failed), `"error"` (all failed)
- `total_sessions` / `completed_sessions` / `failed_sessions`: Session counts
- `combined_csv`: Path to the combined `test-results.csv`
- `log_files`: List of JMeter log filenames produced
- `manifest_path`: Path to the session manifest JSON
- `message`: Human-readable summary with retry guidance

**Key Features:**
- **Unified handling:** Always creates `sessions/session-{i}/` subfolders, whether 1 or N sessions
- **Built-in retry:** Each session's download is retried up to 3 times (configurable) before failing
- **Idempotent / resumable:** If called again after a partial failure, skips completed sessions and retries only the failed ones, using a session manifest as the source of truth
- **JTL concatenation:** Combines all session JTL files into a single `test-results.csv` with header deduplication
- **Log numbering:** Single session produces `jmeter.log`; multi-session produces `jmeter-1.log` through `jmeter-N.log`

**Deprecated Tools:** The following tools are now deprecated in favor of `process_session_artifacts`:
- `download_artifacts_zip`
- `extract_artifact_zip`
- `process_extracted_files`

---

### 1.3 Design

**Directory Structure (all runs):**

```
artifacts/{run_id}/blazemeter/
  sessions/
    session_manifest.json       # Source of truth for session processing state
    session-1/
      artifacts.zip             # Downloaded zip for session 1
      artifacts/                # Extracted contents
        kpi.jtl
        jmeter.log
        error.jtl
    session-2/                  # Only exists if multi-session
      artifacts.zip
      artifacts/
        ...
  test-results.csv              # Combined JTL from all sessions (header deduped)
  jmeter.log                    # Single session: just the log (no numbering)
  jmeter-1.log                  # Multi-session: numbered logs
  jmeter-2.log
  aggregate_performance_report.csv  # From BlazeMeter API (unchanged)
  test_config.json                  # From BlazeMeter API (unchanged)
```

**Session Manifest:** A `session_manifest.json` file tracks per-session processing state with stage-level granularity (download, extract, process). This enables idempotent re-runs -- the tool reads the manifest on each invocation and skips completed work.

**PerfAnalysis Integration:** The `analyze_logs` function in PerfAnalysis MCP now uses a glob pattern (`jmeter*.log`) to discover all JMeter log files, supporting both single-session (`jmeter.log`) and multi-session (`jmeter-1.log`, `jmeter-2.log`, etc.) layouts.

---

### 1.4 Configuration

New settings added to `blazemeter-mcp/config.example.yaml` under the `blazemeter` section:

```yaml
blazemeter:
  artifact_download_max_retries: 3   # Max download attempts per session artifact ZIP
  artifact_download_retry_delay: 2   # Seconds to wait between download retry attempts
  cleanup_session_folders: false     # If true, remove sessions/ subfolder after combining artifacts
```

---

### 1.5 Files Created/Modified

#### Files Created

| File | Purpose |
|------|---------|
| `blazemeter-mcp/services/artifact_manager.py` | Helper module -- session manifest management, JTL concatenation with header dedup, download-with-retry logic |

#### Files Modified

| File | Changes |
|------|---------|
| `blazemeter-mcp/config.example.yaml` | Added `artifact_download_max_retries`, `artifact_download_retry_delay`, `cleanup_session_folders` settings |
| `blazemeter-mcp/utils/config.py` | Added convenience accessors for new config values with defaults |
| `blazemeter-mcp/services/blazemeter_api.py` | Added `session_artifact_processor` orchestration function; imports from `artifact_manager.py` |
| `blazemeter-mcp/blazemeter.py` | Added `process_session_artifacts` MCP tool; marked `download_artifacts_zip`, `extract_artifact_zip`, `process_extracted_files` as `[DEPRECATED]` |
| `perfanalysis-mcp/services/log_analyzer.py` | Replaced hardcoded `jmeter.log` path with `jmeter*.log` glob pattern for multi-session support |
| `blazemeter-mcp/.cursor/rules/AGENTS.md` | Updated workflow: consolidated steps 4-7 into single step using `process_session_artifacts`; added optional JMeter log analysis step |
| `.cursor/rules/performance-testing-workflow.mdc` | Updated BlazeMeter workflow section (consolidated artifact steps), PerfAnalysis log references, and task tracking counts |

---

## 2. Bottleneck Analyzer v0.2 (February 2026)

### 2.1 Overview

The `identify_bottlenecks` tool in the PerfAnalysis MCP Server has been significantly upgraded (v0.2) to deliver accurate, actionable bottleneck detection with dramatically reduced false positives. The v0.1 implementation flagged transient spikes and inherently slow endpoints as bottlenecks, lacked temporal context, and reported 0% infrastructure utilization when Kubernetes resource limits were not defined. v0.2 addresses all of these issues through 8 targeted improvements.

**The primary question this tool answers:**

> At what concurrency level does system performance begin to degrade, and what is the limiting factor?

**Core principle:** A bottleneck is a *sustained, non-recovering* degradation pattern. If the system recovers, it was a transient event, not a bottleneck.

---

### 2.2 MCP Tool

| Tool | Purpose |
|------|---------|
| `identify_bottlenecks` | Analyzes load test results (JTL) and infrastructure metrics (Datadog) to detect performance degradation thresholds, sustained bottlenecks, and capacity risks |

```python
identify_bottlenecks(
    test_run_id: str,                # Unique test run identifier
    baseline_run_id: str = None,     # Optional previous run ID for comparison
    ctx: Context = None              # FastMCP context
) -> dict
```

**Returns:**
- `status`: `"success"` or `"failed"`
- `summary`: Headline answer, threshold concurrency, bottleneck counts by type and severity
- `findings_count`: Total bottlenecks detected
- `output_files`: Paths to JSON, CSV, and Markdown reports

---

### 2.3 What It Does

The tool detects six categories of performance degradation:

| Category | What It Detects |
|----------|----------------|
| **Latency Degradation** | P90 response time increases beyond threshold from baseline |
| **Error Rate Increase** | Error rate rises above absolute threshold |
| **Throughput Plateau** | Throughput stops scaling with increasing concurrency |
| **Infrastructure Saturation** | CPU or Memory utilization exceeds configured thresholds |
| **Resource-Performance Coupling** | Latency degradation coincides with infrastructure stress |
| **Multi-Tier Bottlenecks** | Specific endpoints degrade earlier than others under load |

---

### 2.4 Key Capabilities (v0.2)

The following 8 improvements were implemented:

#### Improvement 1: Sustained Degradation Validation

Degradation must **persist** through the remainder of the test to be classified as a bottleneck. A new `persistence_ratio` parameter (default: 0.6 = 60%) defines the minimum fraction of remaining buckets that must stay degraded after onset.

- If persistence is met: confirmed **bottleneck**
- If the system recovers: reclassified as **transient spike** (severity: low)

This eliminates false positives from temporary spikes caused by garbage collection, cold caches, or transient network issues.

#### Improvement 2: Outlier Filtering

After time bucketing, a **rolling median smoothing** step filters noise from key metrics (P50, P90, P95, avg response time, error rate, throughput). Outlier buckets are detected using Median Absolute Deviation (MAD) and excluded from baseline computation and sustained-degradation scanning.

- Raw values preserved in `<metric>_raw` columns for transparency
- Configurable via `rolling_window_buckets` (default: 3)

#### Improvement 3: Timestamps in Findings

Every finding now includes precise temporal context:

- `onset_timestamp`: UTC timestamp when degradation was detected
- `onset_bucket_index`: Zero-based bucket index within the test
- `test_elapsed_seconds`: Seconds from test start to onset

Example: "**Onset**: 2025-12-16 09:35:00+00:00, bucket #9, 9m 0s into test"

#### Improvement 4: Multi-Tier Bottleneck Accuracy

Per-endpoint analysis now uses the same rigorous detection as overall metrics:

- **Per-label baseline** computed from early post-warmup buckets
- **Inherently slow vs load-induced distinction**: If an endpoint's P90 is already above SLA at baseline, it is classified as `known_slow_endpoint` (severity: info), not a bottleneck
- Per-label outlier detection and persistence checks
- Evidence recommends per-API SLA overrides for known-slow endpoints

#### Improvement 5: Multi-Factor Severity Classification

A new `_classify_severity_v2()` function computes severity from a **composite score** across four dimensions:

| Dimension | Score Range | What It Measures |
|-----------|------------|------------------|
| Delta magnitude | 0-3 | How far the metric deviates from baseline |
| Persistence | 0-3 | What fraction of the test stayed degraded |
| Scope | 0-1 | Overall (higher weight) vs single-endpoint |
| Classification | Short-circuit | Known-slow = info, transient = low |

Composite scoring (0-7): critical (>= 7), high (>= 5), medium (>= 3), low (< 3).

#### Improvement 6: Two-Phase Analysis Architecture

See [2.5 Two-Phase Analysis Architecture](#25-two-phase-analysis-architecture) below.

#### Improvement 7: Capacity Risk Detection

See [2.5 Two-Phase Analysis Architecture](#25-two-phase-analysis-architecture) (Phase 2b).

#### Improvement 8: Raw Metrics Fallback (Missing K8s Limits)

See [2.7 Raw Metrics Fallback](#27-raw-metrics-fallback-missing-k8s-limits) below.

---

### 2.5 Two-Phase Analysis Architecture

The analysis follows the same mental model a performance test engineer uses: first identify **when** degradation happened, then examine infrastructure for **that specific time window** to understand **why**.

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1 — Performance Degradation Detection (JTL only)         │
│                                                                 │
│  Detectors: Latency, Error Rate, Throughput, Multi-Tier         │
│  Output: Findings with onset timestamps + degradation windows   │
└─────────────────────┬───────────────────────────────────────────┘
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
┌────────────────────┐   ┌─────────────────────────────────────────┐
│  Phase 2a          │   │  Phase 2b                               │
│  Infrastructure    │   │  Capacity Risk Detection                │
│  Cross-Reference   │   │                                         │
│                    │   │  Scans infra across full test for       │
│  Scoped to Phase 1 │   │  sustained stress WITH healthy latency  │
│  degradation       │   │                                         │
│  windows only      │   │  - Sustained high utilization           │
│                    │   │  - Climbing trends (memory leaks, etc.) │
│  Classifies:       │   │  - Excludes Phase 2a overlaps           │
│  - infra_correlated│   │                                         │
│  - infra_independ. │   │  Classification: capacity_risk          │
│  - inconclusive    │   │  (warnings, not bottlenecks)            │
└────────────────────┘   └─────────────────────────────────────────┘
```

**Phase 2a — Infrastructure Cross-Reference:**

For each Phase 1 bottleneck finding, Phase 2a extracts infrastructure metrics for the specific degradation window and compares against the baseline window:

```json
{
  "status": "infrastructure_correlated",
  "baseline_window": { "avg_cpu": 40.0, "avg_memory": 55.0 },
  "degradation_window": { "avg_cpu": 82.0, "avg_memory": 68.0, "max_cpu": 87.0 },
  "cpu_delta_pct": 105.0,
  "root_cause_indicator": "Infrastructure stress likely contributing: CPU (baseline 40.0% -> 82.0%, +105.0%)."
}
```

**Phase 2b — Capacity Risk Detection:**

Detects infrastructure stress that has NOT yet caused performance degradation — an early warning:

- Sustained CPU/Memory above threshold while P90 remains within SLA
- Climbing trends (CPU or Memory average increases >= 30% from first-half to second-half of test)
- Reports headroom, duration, and SLA compliance during the stress window
- Findings appear in a separate "Capacity Observations" section, not mixed with bottlenecks

---

### 2.6 Finding Classifications

Every finding is assigned one of four classifications:

| Classification | Meaning | Severity |
|---------------|---------|----------|
| `bottleneck` | Sustained, non-recovering performance degradation | medium - critical |
| `transient_spike` | Brief degradation that recovered (< persistence_ratio) | low |
| `known_slow_endpoint` | Endpoint already above SLA at baseline (not load-induced) | info |
| `capacity_risk` | Infrastructure stressed but performance still healthy | low - medium |

The headline and threshold concurrency exclude transient spikes, known-slow endpoints, and capacity risks from bottleneck tallies.

**Example headlines:**
- "The system handled up to 25 concurrent users with no sustained performance degradation (1 transient spike(s), 1 known slow endpoint(s) noted)."
- "Performance degradation detected at 150 concurrent users (2 bottleneck(s), 1 capacity risk(s))."

---

### 2.7 Raw Metrics Fallback (Missing K8s Limits)

In Kubernetes environments where CPU/Memory limits are not defined, Datadog reports raw usage (nanocores, bytes) but cannot compute utilization percentages. The v0.1 tool would report 0.0% for all infrastructure metrics in this scenario.

**v0.2 detection logic:**

1. Loads `cpu_util_pct` / `mem_util_pct` from the Datadog CSV
2. If all utilization values are zero or near-zero, detects missing limits
3. Falls back to raw metrics: `kubernetes.cpu.usage.total` (nanocores -> cores) and `kubernetes.memory.usage` (bytes -> GB)
4. Uses **relative-from-baseline thresholds** instead of absolute percentage thresholds

**Reporting differences in raw mode:**

| Aspect | Percentage Mode | Raw Mode |
|--------|----------------|----------|
| Baseline display | `Avg CPU: 45.2%` | `Avg CPU: 0.096 cores` |
| Threshold | `cpu_high_pct: 80%` | `raw_metric_degrade_pct: 50% from baseline` |
| Headroom | `17% remaining` | `N/A (limits not defined)` |
| Capacity risk | Uses absolute thresholds | Uses relative-from-baseline |
| Note | - | "K8s resource limits not defined. Reporting raw usage." |

**Infrastructure metadata returned:**
```json
{
  "metric_mode": "raw",
  "limits_available": false,
  "cpu_unit": "cores",
  "memory_unit": "GB"
}
```

---

### 2.8 Configuration

All parameters are configurable under the `bottleneck_analysis` section of `config.yaml`:

```yaml
bottleneck_analysis:
  bucket_seconds: 60              # Time bucket width
  warmup_buckets: 2               # Buckets to skip at test start
  sustained_buckets: 2            # Consecutive degraded buckets to trigger detection
  persistence_ratio: 0.6          # Min fraction of remaining test that must stay degraded
  rolling_window_buckets: 3       # Window size for rolling median smoothing
  latency_degrade_pct: 25.0       # % increase from baseline to flag latency degradation
  error_rate_degrade_abs: 5.0     # Absolute error rate threshold
  throughput_plateau_pct: 5.0     # Throughput flatness threshold
  sla_p90_ms: 5000                # P90 SLA threshold (ms)
  cpu_high_pct: 80                # CPU utilization threshold (%) — used when limits available
  memory_high_pct: 85             # Memory utilization threshold (%) — used when limits available
  raw_metric_degrade_pct: 50.0    # Relative increase from baseline when utilization % unavailable
```

---

### 2.9 Output Files

All outputs are written to `artifacts/<test_run_id>/analysis/`:

| File | Description |
|------|-------------|
| `bottleneck_analysis.json` | Full analysis metadata, configuration, baseline metrics, infrastructure metadata, and findings with infrastructure context |
| `bottleneck_analysis.csv` | One row per finding with flattened fields (25+ columns including onset timestamps, persistence ratio, classification, infrastructure context) |
| `bottleneck_analysis.md` | Human-readable report with executive summary, baseline metrics, detailed findings, infrastructure context tables, capacity observations, and analysis configuration |

**Markdown Report Sections:**
1. Executive Summary (headline, metrics table, counts by type and severity)
2. Baseline Metrics (concurrency, P90, error rate, throughput, CPU/Memory with units)
3. Detailed Findings (per finding: classification, scope, onset, metric/baseline/delta, persistence, evidence, infrastructure context table)
4. Capacity Observations (Phase 2b findings, separate from bottlenecks)
5. Analysis Configuration (all parameters and infra metric mode)

**CSV Fields:**
`test_run_id`, `analysis_mode`, `bottleneck_type`, `scope`, `scope_name`, `concurrency`, `metric_name`, `metric_value`, `baseline_value`, `delta_abs`, `delta_pct`, `severity`, `confidence`, `classification`, `persistence_ratio`, `outlier_filtered`, `onset_timestamp`, `onset_bucket_index`, `test_elapsed_seconds`, `evidence`, `infra_correlated`, `infra_status`, `infra_cpu_baseline`, `infra_cpu_during`, `infra_memory_baseline`, `infra_memory_during`, `infra_metric_mode`, `infra_limits_available`

---

### 2.10 Files Created/Modified

#### Files Created
| File | Purpose |
|------|---------|
| `perfanalysis-mcp/services/bottleneck_analyzer.py` | Core bottleneck analysis engine — time bucketing, outlier filtering, 6 detection algorithms, two-phase infrastructure analysis, capacity risk detection, raw metrics fallback, severity classification, and output formatting |

#### Files Modified
| File | Changes |
|------|---------|
| `perfanalysis-mcp/perfanalysis.py` | Registered `identify_bottlenecks` MCP tool |
| `perfanalysis-mcp/config.example.yaml` | Added `bottleneck_analysis` configuration section with all v0.2 parameters |

---

## 3. JMeter Log Analysis Tool (February 2026)

### 3.1 Overview

A new `analyze_jmeter_log` tool has been added to the JMeter MCP server. This tool performs deep analysis of JMeter and BlazeMeter log files, providing granular error grouping, first-occurrence request/response details, and optional JTL correlation — designed to help performance test engineers quickly identify issues and perform root cause analysis.

This is a more thorough, JMeter-specific alternative to the existing `analyze_logs` tool in PerfAnalysis MCP, which provides a higher-level, cross-tool summary.

---

### 3.2 New MCP Tool

| Tool | Purpose |
|------|---------|
| `analyze_jmeter_log` | Deep analysis of JMeter/BlazeMeter log files with error grouping, first-occurrence details, and JTL correlation |

```python
analyze_jmeter_log(
    test_run_id: str,          # Unique test run identifier
    log_source: str = "blazemeter",  # "jmeter" or "blazemeter"
    ctx: Context               # FastMCP context
) -> dict
```

**Returns:**
- `status`: `"OK"`, `"NO_LOGS"`, or `"ERROR"`
- `log_files_analyzed`: List of log file names processed
- `jtl_file_analyzed`: JTL file name (if found)
- `total_issues`: Total unique error groups found
- `total_occurrences`: Sum of all error occurrences
- `issues_by_severity`: Breakdown by Critical / High / Medium
- `output_files`: Paths to CSV, JSON, and Markdown outputs

---

### 3.3 Configuration

A new `jmeter_log` section was added to `config.yaml` / `config.example.yaml`:

```yaml
jmeter_log:
  max_description_length: 200        # Max characters for error description excerpt
  max_request_length: 500            # Max characters for captured request details
  max_response_length: 500           # Max characters for captured response details
  max_stack_trace_lines: 50          # Max lines to capture from a stack trace
  error_levels:                      # Log levels to treat as issues
    - "ERROR"
    - "FATAL"
```

> **Note:** WARN-level messages are excluded by design. The `logging` section in config.yaml is reserved for future MCP server debugging and is separate from `jmeter_log`.

---

### 3.4 Output Files

All outputs are written to `artifacts/<test_run_id>/analysis/`:

| File | Description |
|------|-------------|
| `<source>_log_analysis.csv` | All issues in tabular form (17 columns) |
| `<source>_log_analysis.json` | Full metadata, summary statistics, and issue details |
| `<source>_log_analysis.md` | Human-readable report with 8 sections |

Where `<source>` is `jmeter` or `blazemeter` depending on the `log_source` parameter.

**Markdown Report Sections:**
1. Header (test run ID, log source, date, files analyzed)
2. Executive Summary (totals, severity breakdown, time window)
3. Issues by Severity (tables for Critical, High, Medium)
4. Top Affected APIs
5. Error Category Breakdown
6. First Occurrence Details (per issue with request/response)
7. JTL Correlation Summary
8. Log Files Analyzed

---

### 3.5 Key Capabilities

- **Multi-line block parsing**: Handles JSR223 Post-Processor verbose output, including `Request=[...]` and `Response=[...]` boundary detection
- **Granular error grouping**: Groups by composite signature (error category + response code + API endpoint + normalized message hash), so different root causes on the same API are tracked separately
- **Message normalization**: Replaces UUIDs, emails, IPs, timestamps, and numeric IDs with placeholders for consistent deduplication
- **First-occurrence capture**: Preserves the first error message, request body, and response body for each unique error group (truncated per config)
- **JTL correlation**: Enriches error groups with JTL response codes and elapsed times; identifies JTL-only failures (errors in JTL with no corresponding log entry)
- **Multi-file discovery**: Automatically discovers and analyzes all `.log` files in the source directory (e.g., `jmeter.log`, `jmeter-1.log`, `jmeter-2.log`)
- **BlazeMeter support**: Handles BlazeMeter's `test-results.csv` naming convention for JTL files

---

### 3.6 Files Created/Modified

### Files Created
| File | Purpose |
|------|---------|
| `jmeter-mcp/services/jmeter_log_analyzer.py` | Core service module — orchestration, parsing, categorization, grouping, JTL correlation, and output formatting |
| `jmeter-mcp/utils/log_utils.py` | Low-level log parsing utilities — regex patterns, field extraction, normalization, hashing, and text helpers |

### Files Modified
| File | Changes |
|------|---------|
| `jmeter-mcp/jmeter.py` | Registered `analyze_jmeter_log` MCP tool |
| `jmeter-mcp/utils/file_utils.py` | Added 6 new I/O helper functions (`get_analysis_output_dir`, `get_source_artifacts_dir`, `discover_files_by_extension`, `save_csv_file`, `save_json_file`, `save_markdown_file`) |
| `jmeter-mcp/config.example.yaml` | Added `jmeter_log` configuration section |
| `jmeter-mcp/README.md` | Updated tools, workflow, project structure, output structure, and future enhancements |

---

## 4. AI-Assisted Report Revision (January 31, 2026)

### 4.1 Overview

A new AI-assisted workflow enables intelligent revision of performance test reports using a Human-In-The-Loop (HITL) approach. This feature allows MCP clients like Cursor to analyze test data and generate improved content for specific report sections while preserving all original metrics, tables, and data.

**Key Features:**
- AI-generated Executive Summary, Key Observations, and Issues Table
- Full preservation of original report data (BlazeMeter links, API tables, infrastructure metrics)
- Version-controlled revisions with rollback capability
- Support for iterative feedback and refinement
- Configurable sections (enabled/disabled per section)

---

### 4.2 New MCP Tools

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

### 4.3 Configuration

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

### 4.4 Workflow

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

### 4.5 Files Created/Modified

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

## 5. Datadog MCP Dynamic Limits (January 23, 2026)

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

### 5.1 Phase 1: Datadog MCP Changes

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

### 5.2 Phase 2: PerfAnalysis MCP Changes

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

### 5.3 Phase 3: PerfReport MCP Changes

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

## 6. Report Enhancements (PerfReport MCP)

### 6.1 Human-Readable Test Duration

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

### 6.2 Cleaner Infrastructure Summaries

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

### 6.3 Formatted Bottleneck Analysis

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

### 6.4 BlazeMeter Report Link

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

### 6.5 Cleaner Service/Host Names

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

### 6.6 Configurable Resource Allocation Display

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

## 7. New Charts Available

### 7.1 CPU Utilization vs Virtual Users (Dual-Axis)

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

### 7.2 Memory Utilization vs Virtual Users (Dual-Axis)

**Chart ID:** `MEMORY_UTILIZATION_VUSERS_DUALAXIS`

**What It Shows:** A dual-axis line chart correlating memory utilization (%) with virtual users over time.

**Why It's Important:**
- **Detects memory leaks:** Memory that climbs continuously without stabilizing may indicate a leak
- **Identifies memory pressure:** Shows if memory becomes constrained as load increases
- **GC impact analysis:** Memory sawtooth patterns can reveal garbage collection impacts

**When to Use:** Include when memory-intensive operations are under test, or when investigating out-of-memory errors and performance degradation over long-running tests.

---

### 7.3 CPU Core Usage Over Time

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

### 7.4 Memory Usage Over Time

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

### 7.5 CPU Core Comparison Bar Chart

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

### 7.6 Memory Usage Comparison Bar Chart

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

## 8. Future Updates

*This section will be updated as new enhancements are released.*

### Planned: PerfAnalysis MCP Enhancements
- ~~Bottleneck Analyzer v0.2 — Sustained Degradation, Outlier Filtering, Two-Phase Infrastructure Analysis, Raw Metrics Fallback~~ ✅ **Completed February 8, 2026**

### Planned: Datadog MCP Enhancements
- ~~Dynamic CPU/Memory limits from Datadog~~ ✅ **Completed January 23, 2026**

---

## Files Modified

### New Files Created
| File | Description |
|------|-------------|
| `blazemeter-mcp/services/artifact_manager.py` | Helper module for session artifact processing — manifest management, JTL concatenation, download-with-retry |
| `perfanalysis-mcp/services/bottleneck_analyzer.py` | Bottleneck analysis engine — time bucketing, outlier filtering, two-phase infrastructure analysis, capacity risk detection, raw metrics fallback |
| `docs/todo/TODO-perfanalysis_identify_bottlenecks_spec.md` | Full specification for identify_bottlenecks tool with all v0.2 improvements |
| `perfreport-mcp/utils/report_utils.py` | Shared utility functions for report formatting |
| `perfreport-mcp/utils/revision_utils.py` | Path helpers, validation, version management for revisions |
| `perfreport-mcp/report_config.yaml` | Report display configuration |
| `perfreport-mcp/report_config.example.yaml` | Documented configuration template |
| `perfreport-mcp/services/charts/comparison_bar_charts.py` | Horizontal bar chart generators |
| `perfreport-mcp/services/revision_data_discovery.py` | Discovery tool for AI revision workflow |
| `perfreport-mcp/services/revision_context_manager.py` | Save/load revision content with versioning |
| `perfreport-mcp/services/report_revision_generator.py` | Report assembly with AI content |
| `.cursor/rules/report-revision-workflow.mdc` | Cursor Rules for AI-assisted revision workflow |

### Files Modified
| File | Changes |
|------|---------|
| `blazemeter-mcp/config.example.yaml` | Added `artifact_download_max_retries`, `artifact_download_retry_delay`, `cleanup_session_folders` settings |
| `blazemeter-mcp/utils/config.py` | Added convenience accessors for artifact download/retry/cleanup config values |
| `blazemeter-mcp/services/blazemeter_api.py` | Added `session_artifact_processor` orchestration function for multi-session artifact handling |
| `blazemeter-mcp/blazemeter.py` | Added `process_session_artifacts` tool; deprecated `download_artifacts_zip`, `extract_artifact_zip`, `process_extracted_files` |
| `perfanalysis-mcp/services/log_analyzer.py` | Updated JMeter log discovery to use `jmeter*.log` glob for multi-session support |
| `blazemeter-mcp/.cursor/rules/AGENTS.md` | Consolidated artifact steps into single `process_session_artifacts` step; added optional JMeter log analysis step |
| `.cursor/rules/performance-testing-workflow.mdc` | Updated BlazeMeter and PerfAnalysis workflow sections for multi-session support |
| `perfanalysis-mcp/perfanalysis.py` | Registered `identify_bottlenecks` MCP tool |
| `perfanalysis-mcp/config.example.yaml` | Added `bottleneck_analysis` configuration section with v0.2 parameters |
| `datadog-mcp/services/datadog_api.py` | Dynamic limits queries, combined usage+limits requests, utilization calculation with -1 marker, CSV consistency fix |
| `perfanalysis-mcp/services/apm_analyzer.py` | Read limits from CSV, filter -1 values, limits_status tracking, None handling for undefined limits |
| `perfreport-mcp/perfreport.py` | Registered 3 new MCP tools for AI-assisted revision |
| `perfreport-mcp/utils/config.py` | Added `load_revisable_sections_config()`, `get_section_config()` functions |
| `perfreport-mcp/services/report_generator.py` | Duration formatting, header stripping, bottleneck formatting, BlazeMeter link, service name cleanup, config-driven allocation columns, N/A* footnotes for undefined limits |
| `perfreport-mcp/services/comparison_report_generator.py` | Duration formatting integration |
| `perfreport-mcp/services/chart_generator.py` | New chart registrations and data source handlers |
| `perfreport-mcp/services/charts/dual_axis_charts.py` | CPU/Memory vs VUsers charts |
| `perfreport-mcp/services/charts/single_axis_charts.py` | CPU Cores and Memory Usage charts |
| `perfreport-mcp/chart_schema.yaml` | New chart specifications |
| `perfreport-mcp/templates/default_report_template.md` | BlazeMeter report link placeholder |

---

*Last Updated: February 10, 2026*
