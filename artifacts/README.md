# 📦 Artifacts Directory

Welcome to the `artifacts/` folder! This is the central hub for storing and organizing output files from various MCP servers used in performance testing workflows.

## 🧠 Purpose

This directory holds test run artifacts from:
- 🧪 **BlazeMeter MCP** – Load test configurations, results, and logs
- 📊 **Datadog MCP** – KPI metrics like CPU and memory usage
- 🔍 **Future Analysis MCP** – Will consume these artifacts for deeper insights

Each test run is stored in its own subfolder for modularity and traceability.

## 📁 Structure

```plaintext
artifacts/
├── <test_run_id>/
│   ├── blazemeter/
│   │   ├── test_config.json
│   │   ├── results.jtl
│   │   └── results.log
│   ├── datadog/
│   │   ├── metrics_cpu.json
│   │   ├── metrics_memory.json
│   │   └── summary.yaml
│   └── metadata.json
