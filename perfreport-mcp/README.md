# 🚦 PerfReport MCP Server

Welcome to the **PerfReport MCP Server**!
This Python-based MCP server is built using FastMCP to generate easy-to-share, stakeholder-ready performance reports from your BlazeMeter and Datadog analysis workflows.

***

## ⭐ Features

- 📝 Generate beautiful performance test reports (Markdown, PDF, Word)
- 📊 Create PNG charts for single and dual metric test visualizations
- 📑 Template-driven formatting for flexible and branded reports
- 🗂 Compare multiple runs in a single analysis
- 🛠 Revise reports based on business/AI feedback
- 🔗 Modular structure with seamless MCP suite integration

***

## ⚡ Prerequisites

- Python 3.12.4 or higher
- Access to BlazeMeter and Datadog MCP artifacts
- Setup your `config.yaml` and `chartcolors.yaml` file

***

## 🚀 Getting Started

1. **Clone the repository**
`git clone <your-repo-url>`
`cd perfreport-mcp`
2. **Create/activate virtual environment**
`python3 -m venv venv`
`source venv/bin/activate`
`pip install -r requirements.txt`
3. **Configure your environment**
    - Update `config.yaml` and `chartcolors.yaml`
    - Ensure `templates/` contains required .md templates
4. **Run the MCP server**
`python perfreport.py`
Or use [uv](https://github.com/astral-sh/uv) for fast, isolated runs:
`uv run perfreport.py`

***

## 🛎 MCP Tools

These are exposed for Cursor, agent, or CLI use:


| Tool | Description |
| :-- | :-- |
| `create_performance_test_report` | Generate a report (Markdown, PDF, Word) from a single test run |
| `create_single_axis_chart` | Create a PNG chart for one metric |
| `create_dual_axis_chart` | Create a PNG chart with two metrics |
| `create_comparison_report` | Compare multiple runs in one report |
| `revise_performance_test_report` | Apply feedback and revise a report |
| `list_templates` | Show available report templates |
| `get_template_details` | Show details/preview for a specific template |


***

## 🔄 Workflow Example

1. 🏃‍♂️ Generate a report after test analysis
2. 🌟 Visualize results with charts for stakeholders
3. 👥 Revise reports with feedback (business, QA, engineering)
4. 📈 Compare test runs for trends and regression
5. 📂 Download outputs from the artifacts directory

***

## 📎 Output Examples

**Markdown Report**

```
# Performance Report: RUN-20251010-01
- SLA Met: All endpoints ✅
- Peak throughput: 1200 req/sec
- Bottleneck: Database tier 🔎
```

**Returned JSON**

```json
{
  "run_id": "RUN-20251010-01",
  "path": "/artifacts/RUN-20251010-01/reports/report.md"
}
```

**PNG Chart**

```
/artifacts/RUN-20251010-01/charts/response-time.png
```


***

## 🏗 Project Structure

```
perfreport-mcp/
  perfreport.py
  services/
    report_generator.py
    chart_generator.py
    template_manager.py
  utils/
    utils.py
  config.yaml
  chartcolors.yaml
  templates/
    default_report_template.md
    multi_run_comparison_template.md
  README.md
  requirements.txt
```


***

## 🔌 Integration

Works seamlessly with BlazeMeter and Datadog MCP servers
for full-stack, end-to-end performance test reporting.

***

## 🙌 Contributing

💡 Suggestions, issues, and PRs are always welcome!
Built with FastMCP, Matplotlib, and love.