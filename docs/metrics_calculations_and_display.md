# 📊 Metrics Calculations and Display Reference

### *How performance metrics are collected, calculated, and displayed across the MCP pipeline*

---

## 🎯 1. Overview

This document explains the complete data flow from metric collection to report display:

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Datadog MCP   │ --> │  PerfAnalysis    │ --> │   PerfReport    │ --> │   Confluence    │
│  (Collection)   │     │   MCP (Analysis) │     │ MCP (Reporting) │     │  (Publishing)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘     └─────────────────┘
       │                        │                        │                       │
       ▼                        ▼                        ▼                       ▼
   Raw metrics              JSON analysis           Markdown report         HTML page
   in CSV format            with insights           with tables/charts      with formatting
```

The Datadog MCP collects two types of infrastructure metrics:

| Metric Type | Description | Use Case |
|-------------|-------------|----------|
| 🖥️ **Host-based** | Traditional VM/server metrics | On-premise, EC2, bare metal |
| ☸️ **Kubernetes-based** | Container/pod metrics | K8s deployments, EKS, AKS, GKE |

---

## 🖥️ 2. Host-Based Metric Collection

### 2.1 CPU Metrics

| Metric | Description | Unit | Datadog Query |
|--------|-------------|------|---------------|
| `system.cpu.user` | User space CPU usage | % | `avg:system.cpu.user{host:<hostname>}.rollup(avg,60)` |
| `system.cpu.system` | Kernel/system CPU usage | % | `avg:system.cpu.system{host:<hostname>}.rollup(avg,60)` |

**Total CPU Utilization Formula:**
```
cpu_util_pct = system.cpu.user + system.cpu.system
```

> **Note:** The `.rollup(avg,60)` aggregates data points over 60-second intervals.

### 2.2 Memory Metrics

| Metric | Description | Unit | Datadog Query |
|--------|-------------|------|---------------|
| `system.mem.used` | Used memory | bytes | `avg:system.mem.used{host:<hostname>}.rollup(avg,60)` |
| `system.mem.total` | Total memory | bytes | `avg:system.mem.total{host:<hostname>}.rollup(avg,60)` |

**Memory Utilization Formula:**
```
mem_util_pct = (system.mem.used / system.mem.total) * 100
```

### 2.3 Host CSV Output Example

```csv
env_name,env_tag,scope,hostname,service_filter,container_or_pod,timestamp_utc,metric,value,unit
Example-UAT,example.uat.env,host,web-server-01,,,2026-01-18T07:22:00,system.cpu.user,44.06,%
Example-UAT,example.uat.env,host,web-server-01,,,2026-01-18T07:26:00,system.cpu.system,3.62,%
Example-UAT,example.uat.env,host,web-server-01,,,2026-01-18T07:26:00,cpu_util_pct,47.68,%
Example-UAT,example.uat.env,host,web-server-01,,,2026-01-18T07:48:00,system.mem.used,69941806592.0,bytes
Example-UAT,example.uat.env,host,web-server-01,,,2026-01-18T07:42:00,system.mem.total,137438482432.0,bytes
Example-UAT,example.uat.env,host,web-server-01,,,2026-01-18T07:26:00,mem_util_pct,50.86,%
```

### 2.4 environments.json Configuration (Host)

```json
{
  "environments": {
    "Example-UAT": {
      "env_tag": "example.uat.env",
      "hosts": [
        {
          "hostname": "web-server-01",
          "description": "Application Server"
        },
        {
          "hostname": "db-server-01",
          "description": "Database Server"
        }
      ]
    }
  }
}
```

> **Note:** For host-based systems, CPU utilization is calculated as `user + system` percentage directly from Datadog metrics. No resource allocation configuration is required.

---

## ☸️ 3. Kubernetes Metric Collection

Kubernetes metrics can be collected at two levels, configured in `environments.json`:

| Level | Description | Use Case |
|-------|-------------|----------|
| **Service-level** | Aggregated across all pods of a service | High-level service health |
| **Pod/Container-level** | Individual pod or container metrics | Detailed troubleshooting |

### 3.1 Service-Level Queries

Used when `services` array is defined in `environments.json`:

**CPU Usage:**
```
avg:kubernetes.cpu.usage.total{env:<env>,service:<service>} by {kube_container_name}
```

**CPU Limits:**
```
avg:kubernetes.cpu.limits{env:<env>,service:<service>} by {kube_container_name}
```

**Memory Usage:**
```
avg:kubernetes.memory.usage{env:<env>,service:<service>} by {kube_container_name}
```

**Memory Limits:**
```
avg:kubernetes.memory.limits{env:<env>,service:<service>} by {kube_container_name}
```

### 3.2 Pod/Container-Level Queries

Used when `pods` array is defined in `environments.json`:

**CPU Usage:**
```
avg:kubernetes.cpu.usage.total{kube_namespace:<namespace>,pod_name:<pod_filter>*} by {pod_name}
```

**CPU Limits:**
```
avg:kubernetes.cpu.limits{kube_namespace:<namespace>,pod_name:<pod_filter>*} by {pod_name}
```

**Memory Usage:**
```
avg:kubernetes.memory.usage{kube_namespace:<namespace>,pod_name:<pod_filter>*} by {pod_name}
```

**Memory Limits:**
```
avg:kubernetes.memory.limits{kube_namespace:<namespace>,pod_name:<pod_filter>*} by {pod_name}
```

### 3.3 Kubernetes Metric Units

| Metric | Raw Unit | Notes |
|--------|----------|-------|
| `kubernetes.cpu.usage.total` | nanocores | 1 core = 1,000,000,000 nanocores |
| `kubernetes.cpu.limits` | cores | Direct core count |
| `kubernetes.memory.usage` | bytes | Raw bytes |
| `kubernetes.memory.limits` | bytes | Raw bytes |

### 3.4 Utilization Calculation (Kubernetes)

**CPU Utilization Formula:**
```
cpu_util_pct = (cpu_usage_nanocores / 1e9) / cpu_limits_cores * 100
```

**Memory Utilization Formula:**
```
mem_util_pct = (memory_usage_bytes / memory_limits_bytes) * 100
```

### 3.5 Kubernetes CSV Output Example

```csv
env_name,env_tag,scope,hostname,filter,container_or_pod,timestamp_utc,metric,value,unit
Perf,perf,service,N/A,checkout-api,main,2026-01-18T10:30:00Z,kubernetes.cpu.usage.total,500000000.0,nanocores
Perf,perf,service,N/A,checkout-api,main,2026-01-18T10:30:00Z,kubernetes.cpu.limits,1.0,cores
Perf,perf,service,N/A,checkout-api,main,2026-01-18T10:30:00Z,cpu_util_pct,50.0,%
Perf,perf,service,N/A,checkout-api,main,2026-01-18T10:30:00Z,kubernetes.memory.usage,2147483648.0,bytes
Perf,perf,service,N/A,checkout-api,main,2026-01-18T10:30:00Z,kubernetes.memory.limits,4294967296.0,bytes
Perf,perf,service,N/A,checkout-api,main,2026-01-18T10:30:00Z,mem_util_pct,50.0,%
```

### 3.6 environments.json Configuration (Kubernetes)

**Service-level configuration:**
```json
{
  "environments": {
    "Performance": {
      "env_tag": "perf",
      "kubernetes": {
        "services": [
          {
            "service_filter": "checkout-api",
            "description": "Checkout API microservice"
          },
          {
            "service_filter": "auth-service",
            "description": "Authentication service"
          }
        ]
      }
    }
  }
}
```

**Pod-level configuration:**
```json
{
  "environments": {
    "Performance": {
      "env_tag": "perf",
      "kubernetes": {
        "pods": [
          {
            "pod_filter": "checkout-api*",
            "kube_namespace": "production",
            "description": "Checkout API pods"
          },
          {
            "pod_filter": "worker*",
            "kube_namespace": "production",
            "description": "Worker pods"
          }
        ]
      }
    }
  }
}
```

> ⚠️ **Deprecation Notice:** The `cpus` and `memory` fields in `environments.json` for Kubernetes services/pods are **deprecated** and no longer used. CPU and memory limits are now dynamically retrieved from Datadog via the `kubernetes.cpu.limits` and `kubernetes.memory.limits` metrics. This ensures utilization calculations reflect the actual Kubernetes resource configurations.

### 3.7 Special Values for Undefined Limits

| Value | Meaning |
|-------|---------|
| `-1` | Limits not defined in Kubernetes (utilization cannot be calculated) |
| `0.0` | Limits metric returned but value is zero |

---

## 🧮 4. PerfAnalysis MCP: Analysis & Aggregation

### 4.1 Unit Conversions

| Input (CSV) | Conversion | Output (JSON) |
|-------------|------------|---------------|
| CPU nanocores | `÷ 1e9` | cores |
| Memory bytes | `÷ 1e9` | GB |
| Host CPU % | no conversion | % |
| Utilization % | no conversion | % |

### 4.2 Statistical Aggregations

For each metric, PerfAnalysis calculates:

| Statistic | Description |
|-----------|-------------|
| `min` | Minimum value in time series |
| `avg` | Average (mean) value |
| `max` | Maximum value |
| `peak` | Same as max, used for threshold comparison |
| `p90` | 90th percentile (if enough samples) |
| `p95` | 95th percentile (if enough samples) |
| `p99` | 99th percentile (if enough samples) |

### 4.3 Handling Undefined Limits

When CSV contains `-1` for utilization:

```python
# PerfAnalysis converts -1 to None
if util_value == -1:
    utilization = None
    limits_defined = False
```

**JSON Output Example:**
```json
{
  "entity_name": "my-service",
  "cpu": {
    "usage_cores": {"min": 0.05, "avg": 0.15, "max": 0.25},
    "allocated_cores": 0.0,
    "utilization_pct": null,
    "limits_status": {
      "cpu_limits_defined": false
    }
  }
}
```

### 4.4 Threshold Analysis

Thresholds are configurable in `perfanalysis-mcp/config.yaml`:

```yaml
resource_thresholds:
  cpu:
    high: 80    # % - triggers high utilization warning
    low: 20     # % - triggers under-utilization warning
  memory:
    high: 85    # % - triggers high utilization warning
    low: 15     # % - triggers under-utilization warning
```

**Insight Generation:**

| Condition | Insight Type | Example Message |
|-----------|--------------|-----------------|
| `util > high` | Warning | "High CPU utilization (85%) on my-service" |
| `util < low` | Info | "Under-utilized CPU (10%) - consider reducing allocation" |
| `util is None` | Info | "CPU limits not defined - utilization cannot be calculated" |

---

## 📝 5. PerfReport MCP: Report Generation

### 5.1 Table Formatting

**CPU Utilization Table Example:**

| Service | Allocated (cores) | Peak Usage | Avg Usage | Peak Util % | Avg Util % |
|---------|-------------------|------------|-----------|-------------|------------|
| service-a | 2.0 | 1.50 | 0.80 | 75.0% | 40.0% |
| service-b | 1.0 | 0.25 | 0.15 | 25.0% | 15.0% |
| service-c | N/A* | 0.30 | 0.20 | N/A* | N/A* |

*\*N/A indicates CPU limits are not defined in Kubernetes for this service. % utilization cannot be calculated.*

### 5.2 Handling None Values in Display

```python
# PerfReport converts None to "N/A*"
if utilization is None:
    display_value = "N/A*"
    add_footnote = True
```

**Footnote Text:**
> *N/A indicates [CPU/Memory] limits are not defined in Kubernetes for this service. % utilization cannot be calculated.*

### 5.3 Number Formatting

| Metric Type | Format | Example |
|-------------|--------|---------|
| CPU cores | 2 decimal places | `1.25` |
| Memory GB | 2 decimal places | `4.50` |
| Percentage | 1 decimal place + % | `75.5%` |
| Response time (ms) | integer | `250` |
| Throughput | 2 decimal places | `150.25` |

### 5.4 Report Metadata

Each report includes metadata in the header:

```markdown
**Generated:** 2026-01-18 15:30:00 EST  
**PerfReport Version:** 0.9.0-beta.1  
**Build Date:** 2026-01-23
```

---

## 📤 6. Confluence MCP: Publishing

### 6.1 Markdown to Confluence Conversion

- Markdown tables → Confluence tables (HTML)
- Code blocks → Confluence code macros
- Images (charts) → Confluence attachments with inline display

### 6.2 Chart Embedding

Charts generated by PerfReport are:
1. Saved as PNG files in artifacts folder
2. Uploaded as Confluence attachments
3. Referenced inline in the page content

---

## 💡 7. Common Scenarios & Examples

### Scenario A: Host with CPU and Memory Metrics

**Data Flow:**
1. Datadog returns: `system.cpu.user = 44.06%`, `system.cpu.system = 3.62%`, `system.mem.used = 69.9GB`, `system.mem.total = 137.4GB`
2. CSV contains raw values with units
3. Datadog MCP calculates: `cpu_util_pct = 47.68%`, `mem_util_pct = 50.86%`
4. PerfAnalysis outputs: `{"cpu_utilization_pct": 47.68, "mem_utilization_pct": 50.86}`
5. PerfReport displays: `47.7%` and `50.9%`

### Scenario B: Kubernetes Service with Limits Defined

**Data Flow:**
1. Datadog returns: `cpu.usage = 500000000 nanocores`, `cpu.limits = 1.0 cores`
2. CSV contains: `kubernetes.cpu.usage.total = 500000000`, `kubernetes.cpu.limits = 1.0`
3. Datadog MCP calculates: `cpu_util_pct = (0.5 / 1.0) * 100 = 50.0%`
4. PerfAnalysis outputs: `{"utilization_pct": 50.0, "limits_defined": true}`
5. PerfReport displays: `50.0%`

### Scenario C: Kubernetes Service without Limits Defined

**Data Flow:**
1. Datadog returns: `cpu.usage = 500000000 nanocores`, NO limits series
2. CSV contains: `kubernetes.cpu.usage.total = 500000000`, `kubernetes.cpu.limits = 0.0`
3. Datadog MCP calculates: `cpu_util_pct = -1` (marker for undefined)
4. PerfAnalysis outputs: `{"utilization_pct": null, "limits_defined": false}`
5. PerfReport displays: `N/A*` with footnote

### Scenario D: Pod-Level Kubernetes Metrics

**Data Flow:**
1. Query uses `pod_name` filter instead of `service` tag
2. Datadog returns metrics per pod replica
3. CSV contains one row per pod per timestamp
4. PerfAnalysis aggregates across pods if needed
5. PerfReport shows per-pod breakdown or aggregated view

---

## 📐 8. Unit Reference Quick Guide

### CPU Units

| Context | Raw Unit | Display Unit | Conversion |
|---------|----------|--------------|------------|
| K8s Usage | nanocores | cores | ÷ 1,000,000,000 |
| K8s Limits | cores | cores | none |
| Host | percent | percent | none |

### Memory Units

| Context | Raw Unit | Display Unit | Conversion |
|---------|----------|--------------|------------|
| K8s Usage | bytes | GB | ÷ 1,000,000,000 |
| K8s Limits | bytes | GB | ÷ 1,000,000,000 |
| Host | bytes | GB | ÷ 1,073,741,824 (1024³) |

### Time Units

| Context | Raw Unit | Display Unit |
|---------|----------|--------------|
| Response time | milliseconds | ms |
| Duration | seconds | sec or min:sec |
| Timestamps | ISO 8601 UTC | Local timezone |

---

## 🔧 9. Troubleshooting

### Issue: Utilization shows N/A*
**Cause:** Kubernetes CPU/Memory limits not configured for the pod/service  
**Solution:** Configure resource limits in Kubernetes deployment, or document as expected

### Issue: Utilization shows 0%
**Cause:** Either no usage or limits returned as 0  
**Check:** Verify Datadog is receiving metrics for the service

### Issue: Very high utilization (>100%)
**Cause:** Usage exceeds limits (can happen with burstable resources)  
**Note:** This is valid - Kubernetes allows bursting above limits if node has capacity

### Issue: Host CPU appears high
**Cause:** CPU utilization is calculated as `system.cpu.user + system.cpu.system`  
**Note:** Values represent percentage of total CPU capacity used across all cores

### Issue: Missing host metrics
**Cause:** Datadog agent not installed or not reporting  
**Check:** Verify agent status on the host

---

## ⚙️ 10. Configuration Reference

### Datadog MCP
```yaml
# datadog-mcp/config.yaml
datadog:
  environments_json_path: "path/to/environments.json"  # Host/service/pod definitions
  time_zone: "America/New_York"
```

> **Note:** The `environments.json` file defines which hosts, services, and pods to collect metrics for. For Kubernetes, resource limits are retrieved dynamically from Datadog metrics (not from this file).

### PerfAnalysis MCP
```yaml
# perfanalysis-mcp/config.yaml
perf_analysis:
  resource_thresholds:
    cpu:
      high: 80
      low: 20
    memory:
      high: 85
      low: 15
```

### PerfReport MCP
```yaml
# perfreport-mcp/config.yaml
server:
  version: "0.9.0-beta.1"
  build:
    date: "2026-01-23"
```

---

## 📚 Appendix: Related Documentation

- [Datadog Query Guide](./datadog_query_guide.md)
- [Report Template Guidelines](./report_template_guidelines.md)
- [JMeter MCP Configuration Guide](./jmeter_mcp_configuration_guide.md)
