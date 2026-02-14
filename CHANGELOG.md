# MCP Performance Suite - Changelog (February 2026)

This document summarizes the enhancements and new features added to the MCP Performance Suite during February 2026.

---

## Table of Contents

- [1. Centralized SLA Configuration](#1-centralized-sla-configuration)
  - [1.1 Overview](#11-overview)
  - [1.2 SLA Configuration File (slas.yaml)](#12-sla-configuration-file-slasyaml)
  - [1.3 Three-Level Pattern Matching](#13-three-level-pattern-matching)
  - [1.4 SLA Compliance Fix (Average → Percentile)](#14-sla-compliance-fix-average--percentile)
  - [1.5 MCP Tool Changes](#15-mcp-tool-changes)
  - [1.6 SLA Pattern Validator](#16-sla-pattern-validator)
  - [1.7 Legacy Config Deprecation](#17-legacy-config-deprecation)
  - [1.8 Files Created/Modified](#18-files-createdmodified)
- [2. JMeter Log Analysis Tool](#2-jmeter-log-analysis-tool)
  - [2.1 Overview](#21-overview)
  - [2.2 New MCP Tool](#22-new-mcp-tool)
  - [2.3 Configuration](#23-configuration)
  - [2.4 Output Files](#24-output-files)
  - [2.5 Key Capabilities](#25-key-capabilities)
  - [2.6 Files Created/Modified](#26-files-createdmodified)
- [3. Bottleneck Analyzer v0.2](#3-bottleneck-analyzer-v02)
  - [3.1 Overview](#31-overview)
  - [3.2 MCP Tool](#32-mcp-tool)
  - [3.3 What It Does](#33-what-it-does)
  - [3.4 Key Capabilities (v0.2)](#34-key-capabilities-v02)
  - [3.5 Two-Phase Analysis Architecture](#35-two-phase-analysis-architecture)
  - [3.6 Finding Classifications](#36-finding-classifications)
  - [3.7 Raw Metrics Fallback (Missing K8s Limits)](#37-raw-metrics-fallback-missing-k8s-limits)
  - [3.8 Configuration](#38-configuration)
  - [3.9 Output Files](#39-output-files)
  - [3.10 Files Created/Modified](#310-files-createdmodified)
- [4. Multi-Session Artifact Handling](#4-multi-session-artifact-handling)
  - [4.1 Overview](#41-overview)
  - [4.2 New MCP Tool](#42-new-mcp-tool)
  - [4.3 Design](#43-design)
  - [4.4 Configuration](#44-configuration)
  - [4.5 Files Created/Modified](#45-files-createdmodified)
- [Previous Changelogs](#previous-changelogs)

---

## 1. Centralized SLA Configuration

### 1.1 Overview

All SLA (Service Level Agreement) thresholds are now defined in a single YAML file (`slas.yaml`) instead of being scattered across `config.yaml` settings and hardcoded values in Python code. This refactoring introduces per-profile defaults, per-API overrides via pattern matching, configurable percentile metrics (P90/P95/P99), and configurable error rate thresholds at every level.

**The core problem solved:**
- SLA thresholds were defined in multiple places (`config.yaml`, hardcoded `5000` in code)
- All APIs shared a single global SLA threshold
- SLA compliance was incorrectly checked against average response time instead of percentile

**What changed:**
- New `slas.yaml` file is the single source of truth for all SLA definitions
- Per-API SLA resolution using three-level pattern matching hierarchy
- SLA compliance now correctly evaluates against the configured percentile (P90 by default)
- All hardcoded SLA values (`5000`) removed from Python code and YAML configs
- If `slas.yaml` is missing, analysis fails immediately with a clear error (no silent fallbacks)

> See the full [SLA Configuration Guide](docs/sla-configuration-guide.md) for detailed usage instructions.

---

### 1.2 SLA Configuration File (slas.yaml)

The configuration supports a file-level default and multiple named SLA profiles:

```yaml
version: "1.0"

# File-level default (used when no sla_id is provided)
default_sla:
  response_time_sla_ms: 5000
  sla_unit: "P90"
  error_rate_threshold: 1.0

# Named SLA profiles
slas:
  - id: "order_management"
    description: "Order Management Service APIs"
    default_sla:
      response_time_sla_ms: 5000
      sla_unit: "P90"
      error_rate_threshold: 1.0
    api_overrides:
      - pattern: "*/orders/export*"
        response_time_sla_ms: 10000
        reason: "Bulk export endpoint"
      - pattern: "*/oauth/token*"
        response_time_sla_ms: 500
        reason: "Critical auth path"
```

**Configuration hierarchy** (most specific wins):
1. `api_overrides` pattern match → per-API threshold
2. Profile `default_sla` → profile-level default
3. File-level `default_sla` → global fallback

---

### 1.3 Three-Level Pattern Matching

API overrides use glob-style patterns evaluated in most-specific-first order:

| Priority | Pattern Type | Example | Matches |
|----------|-------------|---------|---------|
| 1 (highest) | Full JMeter label | `TC01_TS02_/api/orders/export` | Exact label |
| 2 | Test Case + Test Step | `TC01_TS02_*` | All APIs under that step |
| 3 (broadest) | Test Case only | `TC01_*` | All steps and APIs under that case |

Within the same specificity level, the first match in file order wins.

---

### 1.4 SLA Compliance Fix (Average → Percentile)

**Before:** SLA compliance was evaluated against *average* response time, which masks tail latency issues. An API could have P90 = 8000ms but average = 3000ms, passing a 5000ms SLA check incorrectly.

**After:** SLA compliance is evaluated against the configured percentile (P90 by default, configurable via `sla_unit`). The percentile column is dynamically selected from the aggregate report data (`90line`, `95line`, or `99line`).

This fix applies to:
- `perform_aggregate_analysis()` — per-API compliance check
- `analyze_sla_compliance()` — violation detection
- `_get_sla_threshold()` — bottleneck analysis per-endpoint evaluation
- `load_and_process_performance_data()` — temporal SLA violation flagging

---

### 1.5 MCP Tool Changes

Three PerfAnalysis MCP tools now accept an optional `sla_id` parameter:

| Tool | New Parameter | Purpose |
|------|--------------|---------|
| `analyze_test_results` | `sla_id: Optional[str]` | Per-API SLA compliance during aggregate analysis |
| `correlate_test_results` | `sla_id: Optional[str]` | SLA threshold for temporal correlation analysis |
| `identify_bottlenecks` | `sla_id: Optional[str]` | Per-endpoint SLA in bottleneck detection |

All are backward compatible — omitting `sla_id` uses the file-level `default_sla`.

---

### 1.6 SLA Pattern Validator

When `sla_id` is provided, the system automatically validates that all `api_override` patterns match at least one label in the test results. Unmatched patterns are reported via `ctx.info` messages with actionable guidance:

```
[INFO] SLA Validator: 1 of 4 api_override pattern(s) did not match any test result labels.
       Unmatched: '*/oauth/token*' (SLA: 500ms)
       Action: Review patterns in slas.yaml.
```

This is informational only — it does not block analysis.

---

### 1.7 Legacy Config Deprecation

The following settings in `config.yaml` are **deprecated** and no longer used:

| Deprecated Setting | Replacement |
|-------------------|-------------|
| `perf_analysis.response_time_sla` | `slas.yaml > default_sla.response_time_sla_ms` |
| `bottleneck_analysis.sla_p90_ms` | Resolved dynamically from `slas.yaml` |
| Hardcoded `5000` in Python code | Removed — all values from `slas.yaml` |

---

### 1.8 Files Created/Modified

#### Files Created

| File | Purpose |
|------|---------|
| `perfanalysis-mcp/slas.example.yaml` | Annotated SLA configuration template with mock examples |
| `perfanalysis-mcp/utils/sla_config.py` | SLA config loader, schema validator, three-level resolver, and pattern validator |
| `docs/sla-configuration-guide.md` | Comprehensive SLA configuration documentation |

#### Files Modified

| File | Changes |
|------|---------|
| `perfanalysis-mcp/utils/statistical_analyzer.py` | Replaced global SLA with per-API resolver; fixed avg→percentile compliance check; added SLA validator call; added `sla_id` param to `perform_aggregate_analysis`, `analyze_sla_compliance`, `calculate_correlation_matrix`; removed hardcoded `5000` in `load_and_process_performance_data` |
| `perfanalysis-mcp/services/bottleneck_analyzer.py` | Rewrote `_get_sla_threshold()` to use SLA resolver; added `sla_id` to `analyze_bottlenecks`, `_detect_latency_degradation`, `_detect_capacity_risks`, `_detect_multi_tier_bottlenecks`; updated `_get_bn_config()` to remove legacy fallback; updated markdown output |
| `perfanalysis-mcp/services/performance_analyzer.py` | Added `sla_id` to `analyze_blazemeter_results`, `correlate_performance_data`, `identify_system_bottlenecks`; rewrote `validate_sla_compliance` to use resolver |
| `perfanalysis-mcp/perfanalysis.py` | Added `sla_id` parameter to `analyze_test_results`, `correlate_test_results`, `identify_bottlenecks` MCP tools |
| `perfreport-mcp/services/report_generator.py` | Removed hardcoded `5000` fallbacks; enriched SLA violation data with `sla_unit` and `sla_source`; replaced hardcoded threshold check in recommendations with SLA compliance data |
| `perfreport-mcp/services/comparison_report_generator.py` | Replaced hardcoded `"5000"` in API comparison table with per-API threshold from analysis data |
| `perfreport-mcp/chart_schema.yaml` | Removed hardcoded `value: 5000` from SLA threshold block |
| `perfreport-mcp/chart_schema.example.yaml` | Removed hardcoded `value: 5000` from SLA threshold block |
| `perfanalysis-mcp/config.example.yaml` | Marked `response_time_sla` and `sla_p90_ms` as deprecated |
| `perfanalysis-mcp/README.md` | Updated config example to reference `slas.yaml` |

---

## 2. JMeter Log Analysis Tool

### 2.1 Overview

A new `analyze_jmeter_log` tool has been added to the JMeter MCP server. This tool performs deep analysis of JMeter and BlazeMeter log files, providing granular error grouping, first-occurrence request/response details, and optional JTL correlation — designed to help performance test engineers quickly identify issues and perform root cause analysis.

This is a more thorough, JMeter-specific alternative to the existing `analyze_logs` tool in PerfAnalysis MCP, which provides a higher-level, cross-tool summary.

---

### 2.2 New MCP Tool

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

### 2.3 Configuration

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

### 2.4 Output Files

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

### 2.5 Key Capabilities

- **Multi-line block parsing**: Handles JSR223 Post-Processor verbose output, including `Request=[...]` and `Response=[...]` boundary detection
- **Granular error grouping**: Groups by composite signature (error category + response code + API endpoint + normalized message hash), so different root causes on the same API are tracked separately
- **Message normalization**: Replaces UUIDs, emails, IPs, timestamps, and numeric IDs with placeholders for consistent deduplication
- **First-occurrence capture**: Preserves the first error message, request body, and response body for each unique error group (truncated per config)
- **JTL correlation**: Enriches error groups with JTL response codes and elapsed times; identifies JTL-only failures (errors in JTL with no corresponding log entry)
- **Multi-file discovery**: Automatically discovers and analyzes all `.log` files in the source directory (e.g., `jmeter.log`, `jmeter-1.log`, `jmeter-2.log`)
- **BlazeMeter support**: Handles BlazeMeter's `test-results.csv` naming convention for JTL files

---

### 2.6 Files Created/Modified

#### Files Created
| File | Purpose |
|------|---------|
| `jmeter-mcp/services/jmeter_log_analyzer.py` | Core service module — orchestration, parsing, categorization, grouping, JTL correlation, and output formatting |
| `jmeter-mcp/utils/log_utils.py` | Low-level log parsing utilities — regex patterns, field extraction, normalization, hashing, and text helpers |

#### Files Modified
| File | Changes |
|------|---------|
| `jmeter-mcp/jmeter.py` | Registered `analyze_jmeter_log` MCP tool |
| `jmeter-mcp/utils/file_utils.py` | Added 6 new I/O helper functions (`get_analysis_output_dir`, `get_source_artifacts_dir`, `discover_files_by_extension`, `save_csv_file`, `save_json_file`, `save_markdown_file`) |
| `jmeter-mcp/config.example.yaml` | Added `jmeter_log` configuration section |
| `jmeter-mcp/README.md` | Updated tools, workflow, project structure, output structure, and future enhancements |

---

## 3. Bottleneck Analyzer v0.2

### 3.1 Overview

The `identify_bottlenecks` tool in the PerfAnalysis MCP Server has been significantly upgraded (v0.2) to deliver accurate, actionable bottleneck detection with dramatically reduced false positives. The v0.1 implementation flagged transient spikes and inherently slow endpoints as bottlenecks, lacked temporal context, and reported 0% infrastructure utilization when Kubernetes resource limits were not defined. v0.2 addresses all of these issues through 8 targeted improvements.

**The primary question this tool answers:**

> At what concurrency level does system performance begin to degrade, and what is the limiting factor?

**Core principle:** A bottleneck is a *sustained, non-recovering* degradation pattern. If the system recovers, it was a transient event, not a bottleneck.

---

### 3.2 MCP Tool

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

### 3.3 What It Does

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

### 3.4 Key Capabilities (v0.2)

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

See [3.5 Two-Phase Analysis Architecture](#35-two-phase-analysis-architecture) below.

#### Improvement 7: Capacity Risk Detection

See [3.5 Two-Phase Analysis Architecture](#35-two-phase-analysis-architecture) (Phase 2b).

#### Improvement 8: Raw Metrics Fallback (Missing K8s Limits)

See [3.7 Raw Metrics Fallback](#37-raw-metrics-fallback-missing-k8s-limits) below.

---

### 3.5 Two-Phase Analysis Architecture

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

### 3.6 Finding Classifications

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

### 3.7 Raw Metrics Fallback (Missing K8s Limits)

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

### 3.8 Configuration

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
  # sla_p90_ms: DEPRECATED — SLA thresholds are now resolved from slas.yaml
  cpu_high_pct: 80                # CPU utilization threshold (%) — used when limits available
  memory_high_pct: 85             # Memory utilization threshold (%) — used when limits available
  raw_metric_degrade_pct: 50.0    # Relative increase from baseline when utilization % unavailable
```

---

### 3.9 Output Files

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

### 3.10 Files Created/Modified

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

## 4. Multi-Session Artifact Handling

### 4.1 Overview

When a BlazeMeter test run uses multiple load generators (engines), each engine produces its own `artifacts.zip` file containing a `kpi.jtl` and `jmeter.log`. Previously, the BlazeMeter MCP tools processed one session at a time, and each subsequent download/extract/process cycle **overwrote** the previous session's files. This meant only the last session's JTL and log data was retained locally, causing incomplete data for downstream analysis tools like `identify_bottlenecks` and `correlate_test_results`.

This enhancement introduces a unified session-based artifact processing model that handles both single-session and multi-session runs through a single consolidated tool.

---

### 4.2 New MCP Tool

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

### 4.3 Design

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

### 4.4 Configuration

New settings added to `blazemeter-mcp/config.example.yaml` under the `blazemeter` section:

```yaml
blazemeter:
  artifact_download_max_retries: 3   # Max download attempts per session artifact ZIP
  artifact_download_retry_delay: 2   # Seconds to wait between download retry attempts
  cleanup_session_folders: false     # If true, remove sessions/ subfolder after combining artifacts
```

---

### 4.5 Files Created/Modified

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

## Previous Changelogs

| Month | File | Highlights |
|-------|------|------------|
| January 2026 | [CHANGELOG-2026-01.md](docs/changelogs/CHANGELOG-2026-01.md) | AI-Assisted Report Revision, Datadog Dynamic Limits, Report Enhancements, New Charts |

---

*Last Updated: February 12, 2026*
