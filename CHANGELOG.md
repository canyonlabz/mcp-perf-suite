# MCP Performance Suite - January 2026 Updates

This document summarizes the enhancements and new features added to the MCP Performance Suite. These updates improve report readability, add new visualization capabilities, and provide more flexibility in how performance data is displayed.

---

## Table of Contents

- [0. Datadog MCP Dynamic Limits (January 23, 2026)](#0-datadog-mcp-dynamic-limits-january-23-2026)
  - [0.1 Phase 1: Datadog MCP Changes](#01-phase-1-datadog-mcp-changes)
  - [0.2 Phase 2: PerfAnalysis MCP Changes](#02-phase-2-perfanalysis-mcp-changes)
  - [0.3 Phase 3: PerfReport MCP Changes](#03-phase-3-perfreport-mcp-changes)
- [1. Report Enhancements (PerfReport MCP)](#1-report-enhancements-perfreport-mcp)
  - [1.1 Human-Readable Test Duration](#11-human-readable-test-duration)
  - [1.2 Cleaner Infrastructure Summaries](#12-cleaner-infrastructure-summaries)
  - [1.3 Formatted Bottleneck Analysis](#13-formatted-bottleneck-analysis)
  - [1.4 BlazeMeter Report Link](#14-blazemeter-report-link)
  - [1.5 Cleaner Service/Host Names](#15-cleaner-servicehost-names)
  - [1.6 Configurable Resource Allocation Display](#16-configurable-resource-allocation-display)
- [2. New Charts Available](#2-new-charts-available)
  - [2.1 CPU Utilization vs Virtual Users (Dual-Axis)](#21-cpu-utilization-vs-virtual-users-dual-axis)
  - [2.2 Memory Utilization vs Virtual Users (Dual-Axis)](#22-memory-utilization-vs-virtual-users-dual-axis)
  - [2.3 CPU Core Usage Over Time](#23-cpu-core-usage-over-time)
  - [2.4 Memory Usage Over Time](#24-memory-usage-over-time)
  - [2.5 CPU Core Comparison Bar Chart](#25-cpu-core-comparison-bar-chart)
  - [2.6 Memory Usage Comparison Bar Chart](#26-memory-usage-comparison-bar-chart)
- [3. Future Updates](#3-future-updates)

---

## 0. Datadog MCP Dynamic Limits (January 23, 2026)

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

### 0.1 Phase 1: Datadog MCP Changes

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

### 0.2 Phase 2: PerfAnalysis MCP Changes

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

### 0.3 Phase 3: PerfReport MCP Changes

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

## 1. Report Enhancements (PerfReport MCP)

### 1.1 Human-Readable Test Duration

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

### 1.2 Cleaner Infrastructure Summaries

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

### 1.3 Formatted Bottleneck Analysis

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

### 1.4 BlazeMeter Report Link

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

### 1.5 Cleaner Service/Host Names

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

### 1.6 Configurable Resource Allocation Display

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

## 2. New Charts Available

### 2.1 CPU Utilization vs Virtual Users (Dual-Axis)

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

### 2.2 Memory Utilization vs Virtual Users (Dual-Axis)

**Chart ID:** `MEMORY_UTILIZATION_VUSERS_DUALAXIS`

**What It Shows:** A dual-axis line chart correlating memory utilization (%) with virtual users over time.

**Why It's Important:**
- **Detects memory leaks:** Memory that climbs continuously without stabilizing may indicate a leak
- **Identifies memory pressure:** Shows if memory becomes constrained as load increases
- **GC impact analysis:** Memory sawtooth patterns can reveal garbage collection impacts

**When to Use:** Include when memory-intensive operations are under test, or when investigating out-of-memory errors and performance degradation over long-running tests.

---

### 2.3 CPU Core Usage Over Time

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

### 2.4 Memory Usage Over Time

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

### 2.5 CPU Core Comparison Bar Chart

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
│           123456789    80840304    81012456                 │
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

### 2.6 Memory Usage Comparison Bar Chart

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
│           123456789    80840304    81012456                 │
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

## 3. Future Updates

*This section will be updated as new enhancements are released.*

### Planned: Datadog MCP Enhancements
- ~~Dynamic CPU/Memory limits from Datadog~~ ✅ **Completed January 23, 2026**

---

## Files Modified

### New Files Created
| File | Description |
|------|-------------|
| `perfreport-mcp/utils/report_utils.py` | Shared utility functions for report formatting |
| `perfreport-mcp/report_config.yaml` | Report display configuration |
| `perfreport-mcp/report_config.example.yaml` | Documented configuration template |
| `perfreport-mcp/services/charts/comparison_bar_charts.py` | Horizontal bar chart generators |

### Files Modified
| File | Changes |
|------|---------|
| `datadog-mcp/services/datadog_api.py` | Dynamic limits queries, combined usage+limits requests, utilization calculation with -1 marker, CSV consistency fix |
| `perfanalysis-mcp/services/apm_analyzer.py` | Read limits from CSV, filter -1 values, limits_status tracking, None handling for undefined limits |
| `perfreport-mcp/services/report_generator.py` | Duration formatting, header stripping, bottleneck formatting, BlazeMeter link, service name cleanup, config-driven allocation columns, N/A* footnotes for undefined limits |
| `perfreport-mcp/services/comparison_report_generator.py` | Duration formatting integration |
| `perfreport-mcp/services/chart_generator.py` | New chart registrations and data source handlers |
| `perfreport-mcp/services/charts/dual_axis_charts.py` | CPU/Memory vs VUsers charts |
| `perfreport-mcp/services/charts/single_axis_charts.py` | CPU Cores and Memory Usage charts |
| `perfreport-mcp/chart_schema.yaml` | New chart specifications |
| `perfreport-mcp/templates/default_report_template.md` | BlazeMeter report link placeholder |
| `.cursor/rules/performance-testing-workflow.mdc` | Workflow updates for public report saving |

---

*Last Updated: January 23, 2026*
