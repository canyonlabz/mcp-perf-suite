# 📚 Documentation Overview

Welcome to the **Documentation Hub** for the **MCP Performance Testing Suite**!
This folder contains all reference materials, specifications, templates, and technical guides used across the suite of MCP servers.

The goal of this directory is to help end-users, contributors, and performance engineers quickly understand:

* How each MCP server works
* How to configure them
* How to customize templates
* How to use the available tools
* How the MCP servers integrate across the ecosystem

---

## 📁 What’s Inside This Folder

This folder will grow over time. For now, here are the key documents:

### 📘 **1. Template Authoring Guidelines (`template_guidelines.md`)**

A detailed guide explaining how to create custom Markdown templates for performance reports, including:

* Supported Markdown syntax
* Placeholder reference
* Rules for Confluence-safe formatting
* Examples for API tables, summaries, and insights
* How the report generator fills in template variables

➡️ *Use this if you want to customize the look & layout of performance reports.*

---

### ⚙️ **2. MCP Configuration References (Coming Soon)**

Planned documents:

#### **`config_reference.md`**

A unified explanation of the `config.yaml` files used across all MCP servers, including:

* Common fields (`general`, `artifacts`, `logging`, etc.)
* Server-specific sections
* Examples from:

  * `blazemeter-mcp`
  * `datadog-mcp`
  * `perfreport-mcp`
  * `confluence-mcp`
  * Any future MCP servers added to the suite

➡️ *This will help users understand exactly how to configure each server consistently.*

---

### 🔧 **3. MCP Tool Index (Coming Soon)**

Planned document:

#### **`mcp_tools_index.md`**

A single reference listing *all* tools exposed by each MCP server.
For each server, we will include:

* Server name
* Tool name
* Purpose
* Input arguments
* Example usage

Example snippet:

```
blazemeter-mcp
  • get_test_runs
  • start_test_run
  • stop_test_run
  • get_aggregate_report
```

➡️ *Useful for developers integrating MCP servers into automated pipelines or toolchains.*

---

### 🧩 **4. Architecture & Flow Docs (Future Expansion)**

Potential documents coming later:

* `architecture_overview.md`
* `data_flow_across_mcp_servers.md`
* `report_generation_pipeline.md`
* `how_network_capture_integrates_with_jmeter.md`
* `performance_analysis_pipeline.md`

➡️ *These give new contributors a high-level picture of the entire ecosystem.*

---

## 🧭 Suggested Folder Structure (Growing)

```
docs/
│
├── README.md                  ← You are here
├── template_guidelines.md     ← Performance report template rules
│
├── config_reference.md        ← (Planned)
├── mcp_tools_index.md         ← (Planned)
│
├── architecture_overview.md   ← (Future)
└── examples/                  ← Example templates, configs, outputs
```

---

## 🚀 Future Improvements

As more MCP servers are added or enhanced, this docs folder will evolve to include:

* Detailed examples
* Troubleshooting guides
* Contribution guidelines
* Best practices for large-scale performance testing
* How to extend or override MCP server behavior
