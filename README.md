# MCP Perf Suite

> **⚠️ This project is under active development. Features, modules, and documentation may change frequently. Use at your own risk and please report any issues or suggestions!**

Welcome to the **MCP Perf Suite** — a modular collection of MCP servers designed to support and streamline performance testing workflows.

---

## 📖 Overview

This repository hosts multiple MCP servers, each designed for a specific role in the performance testing lifecycle:

### 🧪 Test Creation & Execution
- **JMeter MCP Server:**  
  Generate JMeter scripts from Playwright-captured traffic. Convert structured JSON into JMX files, execute JMeter tests, monitor them in real time, and analyze performance results.

- **BlazeMeter MCP Server:**  
  Interact with BlazeMeter’s API to manage workspaces, projects, tests, and fetch run results.

### 📊 Monitoring & Analysis
- **Datadog (Application Performance Monitoring) MCP Server:**  
  Pull and correlate monitoring and metrics data from Datadog to complement load test results.

- **Performance Test Analysis MCP Server:**  
  Perform deep analysis of BlazeMeter test results alongside Datadog system metrics (e.g., CPU, Memory). Includes log analysis of both JMeter and Datadog logs, followed by time-series correlation across datasets to detect anomalies and provide actionable insights.

### 🧠 AI Memory & Learning
- **PerfMemory MCP Server:**  
  Persistent memory and lessons-learned layer backed by PostgreSQL with pgvector. Stores debug sessions, attempts, and vector embeddings of symptoms so AI agents can recall past fixes and avoid repeating mistakes. Supports OpenAI, Azure OpenAI, and Ollama embedding providers.

### 📑 Reporting & Collaboration
- **Performance Reporting MCP Server:**  
  Generate formatted reports (e.g. PDF, Word, Markdown) from test data and analysis files for presentation and decision-making.

- **Confluence MCP Server:**  
  Publish Performance Test reports by converting Markdown files into Confluence XHTML format.

- **Microsoft Graph MCP Server:**  
  Integrate with Microsoft Graph API to streamline performance testing workflows. Upload artifacts to SharePoint for centralized storage, and use Teams integration to coordinate test execution and share results across the team.

---

## 🔄 Pipeline & Workflow

The MCP servers in this repository (and external integrations like Playwright MCP) form a complete performance testing pipeline. This workflow illustrates how scripts are created, validated, executed, monitored, analyzed, and finally reported and shared across teams.

### 📐 Workflow Diagram

```text
                ┌────────────────────────┐
                │   Playwright MCP       │
                │ (external, captures    │
                │  browser traffic)      │
                └───────────┬────────────┘
                            │ JSON traffic
                            ▼
                ┌────────────────────────┐       ┌─────────────────────────┐
                │   JMeter MCP Server    │◄─────►│  PerfMemory MCP Server  │
                │  - Generate JMX scripts│       │  - Recall past fixes    │
                │  - Run smoke tests to  │       │  - Store new lessons    │
                │    validate correctness│       │  - Vector similarity    │
                └───────────┬────────────┘       │    search (pgvector)    │
                            │ Validated JMX      └─────────────────────────┘
                            ▼
                ┌────────────────────────┐
                │   BlazeMeter MCP Server│
                │  - Execute full-scale  │
                │    performance tests   │
                │  - Fetch run results   │
                └───────────┬────────────┘
                            │ Results & metrics
                            ▼
        ┌────────────────────────────────┐
        │ Datadog MCP Server             │
        │ (APM metrics correlation)      │
        └───────────┬────────────────────┘
                    │
                    ▼
        ┌────────────────────────────────┐
        │ Performance Test Analysis MCP  │
        │ - Analyze BlazeMeter results   │
        │ - Analyze Datadog metrics      │
        │ - Log analysis (JMeter +       │
        │   Datadog logs)                │
        │ - Time-series correlation      │
        └───────────┬────────────────────┘
                    │
                    ▼
        ┌────────────────────────────────┐
        │ Performance Reporting MCP      │
        │ (PDF, Word, Markdown reports)  │
        └───────────┬────────────────────┘
                    │
                    ▼
        ┌────────────────────────────────┐
        │ Confluence MCP Server          │
        │ (Publish reports to Confluence)│
        └───────────┬────────────────────┘
                    │
                    ▼
        ┌─────────────────────────────────┐
        │ Microsoft Graph MCP Server      │
        │ - Upload artifacts to SharePoint│
        │ - Share results via Teams       │
        └─────────────────────────────────┘
```

---

## 🏗️ Architecture & Structure

Each MCP server lives in its **own subdirectory** within this repo, making it easy to develop, maintain, and deploy independently:

```

mcp-perf-suite/
├── artifacts/               # Folder that contains the performance test results
├── blazemeter-mcp/          # BlazeMeter MCP server (current)
├── confluence-mcp/          # Confluence MCP server (current)
├── datadog-mcp/             # Datadog MCP server (current)
├── jmeter-mcp/              # JMeter MCP server (current)
├── msgraph-mcp/             # Microsoft Graph MCP server (future)
├── perfanalysis-mcp/        # LLM-powered test analysis MCP (current)
├── perfmemory-mcp/          # AI memory & lessons learned MCP (current)
├── perfreport-mcp/          # Reporting and formatting MCP (current)
├── README.md                # This file: repo overview and guidance
└── LICENSE                  # Repository license (e.g., MIT)

```

---

## ▶️ Getting Started with JMeter MCP Server

Navigate to the `jmeter-mcp/` folder for detailed setup and usage instructions specific to the JMeter MCP server.

The JMeter MCP server uses FastMCP, Python 3.12+, and exposes actions to generate JMX scripts from captured network traffic (via Playwright MCP). It also supports running smoke tests to validate script correctness before handing off to BlazeMeter MCP for full-scale performance execution.

## ▶️ Getting Started with BlazeMeter MCP Server

Navigate to the `blazemeter-mcp/` folder for detailed setup and usage instructions specific to the BlazeMeter MCP server.

The BlazeMeter MCP server uses FastMCP, Python 3.12+, and exposes actions to manage load test lifecycles and retrieve results.

## ▶️ Getting Started with Datadog MCP Server

Navigate to the `datadog-mcp/` folder for detailed setup and usage instructions specific to the Datadog MCP server.

The Datadog MCP server uses FastMCP, Python 3.12+, and exposes actions to pull KPI metrics for a given environment and query logs.

## ▶️ Getting Started with Performance Analysis MCP Server

Navigate to the `perfanalysis-mcp/` folder for detailed setup and usage instructions specific to the Performance Test Analyzer MCP server.

The Performance Analysis MCP server uses FastMCP, Python 3.12+, and exposes actions to identify bottlenecks and report findings as JSON and Markdown files.

## ▶️ Getting Started with Performance Report MCP Server

Navigate to the `perfreport-mcp/` folder for detailed setup and usage instructions specific to the Performance Report MCP server.

The Performance Report MCP server uses FastMCP, Python 3.12+, and exposes tools to generate performance test reports based upon analysis files. Outputs
reports as either PDF or Word format.

## ▶️ Getting Started with Confluence MCP Server

Navigate to the `confluence-mcp/` folder for detailed setup and usage instructions specific to the Confluence MCP server.

The Confluence MCP server uses FastMCP, Python 3.12+, and exposes actions to publish performance test reports to Confluence. It also supports listing and retrieving Confluence spaces and pages, searching pages, and managing available reports and charts for publication.

## ▶️ Getting Started with PerfMemory MCP Server

Navigate to the `perfmemory-mcp/` folder for detailed setup and usage instructions specific to the PerfMemory MCP server.

The PerfMemory MCP server uses FastMCP, Python 3.12+, and PostgreSQL with the pgvector extension. It provides persistent memory for JMeter script debugging — storing debug sessions, attempts, and vector embeddings so AI agents can recall past fixes via semantic similarity search. Supports OpenAI, Azure OpenAI, and Ollama embedding providers. See `docs/pgvector_installation_guide.md` for database setup instructions.

## ▶️ Getting Started with Microsoft Graph MCP Server

Navigate to the `msgraph-mcp/` folder for detailed setup and usage instructions specific to the Microsoft Graph MCP server.

The Microsoft Graph MCP server uses FastMCP, Python 3.12+, and integrates with Microsoft Graph API endpoints. It enables uploading performance test artifacts into SharePoint for centralized storage, and provides Teams integration to coordinate test execution and share results across the team.

---

## 🛣️ Future Roadmap 

### Upcoming: Schema-Driven Architecture

The MCP Perf Suite is evolving toward a **schema-driven architecture** that enables true modularity and extensibility. The core principle: **standardized data contracts between MCPs ensure that adding new data sources doesn't require changes to downstream consumers.**

#### Future Architecture Vision

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES                                   │
├─────────────────────────────────┬───────────────────────────────────────────┤
│          APM MCP                │           Load Test MCP                   │
│   (replaces Datadog MCP)        │      (replaces BlazeMeter MCP)            │
│                                 │                                           │
│  ┌─────────────────────────┐    │    ┌─────────────────────────┐            │
│  │   Datadog Adapter       │    │    │   BlazeMeter Adapter    │            │
│  │   New Relic Adapter     │    │    │   LoadRunner Adapter    │            │
│  │   AppDynamics Adapter   │    │    │   Gatling Adapter       │            │
│  │   Dynatrace Adapter     │    │    │   k6 Adapter            │            │
│  │   Splunk APM Adapter    │    │    │   Locust Adapter        │            │
│  └──────────┬──────────────┘    │    └──────────┬──────────────┘            │
│             │                   │               │                           │
│             ▼                   │               ▼                           │
│  ┌─────────────────────────┐    │    ┌─────────────────────────┐            │
│  │  Standardized APM       │    │    │  Standardized Load Test │            │
│  │  Output Schema          │    │    │  Output Schema          │            │
│  │  (metrics, logs, traces)│    │    │  (results, aggregates)  │            │
│  └──────────┬──────────────┘    │    └──────────┬──────────────┘            │
├─────────────┴───────────────────┴───────────────┴───────────────────────────┤
│                                                                             │
│                    STANDARDIZED SCHEMA LAYER                                │
│           (Source-agnostic data contracts / JSON & CSV schemas)             │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                         ┌─────────────────────────┐                         │
│                         │  Performance Analysis   │                         │
│                         │        MCP              │                         │
│                         │ (source-agnostic)       │                         │
│                         └───────────┬─────────────┘                         │
│                                     │                                       │
│                                     ▼                                       │
│                         ┌─────────────────────────┐                         │
│                         │  Performance Report     │                         │
│                         │        MCP              │                         │
│                         │ (source-agnostic)       │                         │
│                         └───────────┬─────────────┘                         │
│                                     │                                       │
│                    ┌────────────────┼────────────────┐                      │
│                    ▼                ▼                ▼                      │
│              ┌──────────┐    ┌──────────┐    ┌──────────────┐               │
│              │Confluence│    │ MS Graph │    │ Other Output │               │
│              │   MCP    │    │   MCP    │    │   Adapters   │               │
│              └──────────┘    └──────────┘    └──────────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Key Benefits

| Benefit | Description |
|---------|-------------|
| **Extensibility** | Add new APM tools or load test platforms by implementing an adapter that outputs the standard schema |
| **Loose Coupling** | PerfAnalysis and PerfReport MCPs remain unchanged when new data sources are added |
| **Community Contributions** | Clear schema contracts make it easy for contributors to add support for their preferred tools |
| **Maintainability** | Changes to source APIs (e.g., Datadog v3) only affect their respective adapter, not the entire pipeline |

#### Planned Milestones

- [ ] **APM MCP Server**: Unified entry point supporting multiple APM tools via adapter modules
  - Datadog (current implementation migrated as adapter)
  - New Relic adapter
  - Dynatrace adapter  
  - AppDynamics adapter
  - Splunk APM adapter

- [ ] **Load Test MCP Server**: Unified entry point supporting multiple load testing tools
  - BlazeMeter (current implementation migrated as adapter)
  - LoadRunner adapter
  - Gatling adapter
  - k6 adapter
  - Locust adapter

- [ ] **Schema Documentation**: Formal JSON/CSV schema specifications for data interchange

### Other Planned Enhancements

- Enhance the **Test Analysis MCP Server** utilizing OpenAI GPT or other LLMs for enhanced test result analysis
- Add test results log analysis to identify potential issues or bottlenecks
- Continue refinement of the **Reporting MCP Server** to produce executive-friendly reports and dashboards from test analysis data
- Enable seamless workflow orchestration across MCP servers for a comprehensive performance testing pipeline

---

## 🤝 Contribution

Contributions, ideas, and feature requests are welcome! Please open issues or create pull requests to collaborate.

---

## 📜 License 

This project is licensed under the MIT License. See the LICENSE file for details.

---

Created with ❤️ to enable next-gen performance testing, analysis, and reporting powered by FastMCP and AI.

