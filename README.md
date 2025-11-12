# MCP Perf Suite

> **⚠️ This project is under active development. Features, modules, and documentation may change frequently. Use at your own risk and please report any issues or suggestions!**

Welcome to the **MCP Perf Suite** — a modular collection of MCP servers designed to support and streamline performance testing workflows.

---

## 📖 Overview

This repository hosts multiple MCP servers, each designed for a specific role in the performance testing lifecycle:

- **BlazeMeter MCP Server:**  
  Interact with BlazeMeter’s API to manage workspaces, projects, tests, and fetch run results. (Available now)

- **Datadog (Application Performance Monitoring) MCP Server:**  
  Pull and correlate monitoring and metrics data from Datadog to complement load test results.

- **Performance Test Analysis MCP Server:**  
  Leverage Large Language Models (e.g., OpenAI GPT) to analyze test results, detect anomalies, and provide insights.

- **Performance Reporting MCP Server:**  
  Generate formatted reports (e.g. PDF, Word, Markdown) from test data and analysis files for presentation and decision-making.

- **Confluence MCP Server**
  Publish Performance Test reports by taking Markdown files and converting to Confluence XHTML format.

---

## 🏗️ Architecture & Structure

Each MCP server lives in its **own subdirectory** within this repo, making it easy to develop, maintain, and deploy independently:

```

mcp-perf-suite/
├── artifacts/               # Folder that contains the performance test results
├── blazemeter-mcp/          # BlazeMeter MCP server (current)
├── confluence-mcp/          # Confluence MCP server (current)
├── datadog-mcp/             # Datadog MCP server (current)
├── jmeter-mcp/              # JMeter MCP server (future)
├── msgraph-mcp/             # Microsoft Graph MCP server (future)
├── perfanalysis-mcp/        # LLM-powered test analysis MCP (current)
├── perfreport-mcp/          # Reporting and formatting MCP (current)
├── README.md                # This file: repo overview and guidance
└── LICENSE                  # Repository license (e.g., MIT)

```

---

## ▶️ Getting Started with BlazeMeter MCP Server

Navigate to the `blazemeter-mcp/` folder for detailed setup and usage instructions specific to the BlazeMeter MCP server.

The BlazeMeter MCP server uses FastMCP, Python 3.12+, and exposes actions to manage load test lifecycles and retrieve results.

---

## ▶️ Getting Started with Datadog MCP Server

Navigate to the `datadog-mcp/` folder for detailed setup and usage instructions specific to the Datadog MCP server.

The Datadog MCP server uses FastMCP, Python 3.12+, and exposes actions to pull KPI metrics for a given environment and query logs.

---

## ▶️ Getting Started with Performance Analysis MCP Server

Navigate to the `perfanalysis-mcp/` folder for detailed setup and usage instructions specific to the Performance Test Analyzer MCP server.

The Performance Analysis MCP server uses FastMCP, Python 3.12+, and exposes actions to identify bottlenecks and report findings as JSON and Markdown files.

---

## ▶️ Getting Started with Performance Report MCP Server

Navigate to the `perfreport-mcp/` folder for detailed setup and usage instructions specific to the Performance Report MCP server.

The Performance Report MCP server uses FastMCP, Python 3.12+, and exposes tools to generate performance test reports based upon analysis files. Outputs
reports as either PDF or Word format.

## ▶️ Getting Started with Confluence MCP Server

Navigate to the `confluence-mcp/` folder for detailed setup and usage instructions specific to the Confluence MCP server.

The Confluence MCP server uses FastMCP, Python 3.12+, and exposes actions to publish performance test reports to Confluence. It also supports listing and retrieving Confluence spaces and pages, searching pages, and managing available reports and charts for publication.

---

## 🛣️ Future Roadmap 

- Refactor the **Datadog MCP Server** to an **APM MCP Server** to support multiple APM (Application Performance Monitoring) tools (e.g. Dynatrace, AppDynamics, etc).  
- Enhance the **Test Analysis MCP Server** utilizing OpenAI GPT or other LLMs for enhanced test result analysis. 
- Add test results log analysis to identify potential issues or bottlenecks.
- Continue refinement of the **Reporting MCP Server** to produce executive-friendly reports and dashboards from test analysis data.  
- Enable seamless workflow orchestration across MCP servers for a comprehensive performance testing pipeline.

---

## 🤝 Contribution

Contributions, ideas, and feature requests are welcome! Please open issues or create pull requests to collaborate.

---

## 📜 License 

This project is licensed under the MIT License. See the LICENSE file for details.

---

Created with ❤️ to enable next-gen performance testing, analysis, and reporting powered by MCP and AI.

