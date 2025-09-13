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

- **Reporting MCP Server (planned):**  
  Generate formatted reports from test data and analysis for presentation and decision-making.

---

## 🏗️ Architecture & Structure

Each MCP server lives in its **own subdirectory** within this repo, making it easy to develop, maintain, and deploy independently:

```

mcp-perf-suite/
├── artifacts/               # Folder that contains the performance test results
├── blazemeter-mcp/          # BlazeMeter MCP server (current)
├── datadog-mcp/             # Datadog MCP server (current)
├── perfanalysis-mcp/        # LLM-powered test analysis MCP (current)
├── reporting-mcp/           # Reporting and formatting MCP (planned)
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

## 🛣️ Future Roadmap 

- Refine the **Datadog MCP Server** to enable log ingestion and correlation.  
- Refine the **Test Analysis MCP Server** utilizing OpenAI GPT and other LLMs for automated test result analytics.  
- Create the **Reporting MCP Server** to produce executive-friendly reports and dashboards from test and analysis data.  
- Enable seamless orchestration across MCP servers for comprehensive performance testing workflows.

---

## 🤝 Contribution

Contributions, ideas, and feature requests are welcome! Please open issues or create pull requests to collaborate.

---

## 📜 License 

This project is licensed under the MIT License. See the LICENSE file for details.

---

Created with ❤️ to enable next-gen performance testing and analysis powered by MCP and AI.

