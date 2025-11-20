# 🚦 PerfReport MCP Server

Welcome to the **PerfReport MCP Server**!
This Python-based MCP server is built using FastMCP to generate easy-to-share, stakeholder-ready performance reports from your BlazeMeter and APM (e.g. Datadog, Dynatrace, AppDynamics, etc) analysis workflows.

---

## ⭐ Features

- 📝 Generate beautiful performance test reports (Markdown, PDF, Word)
- 📊 Create PNG charts for single and dual-axis metric test visualizations
- 📑 Template-driven formatting for flexible and branded reports
- 🗂 Compare multiple runs in a single analysis
- 🛠 Revise reports based on business/AI feedback
- 🔗 Modular structure with seamless MCP suite integration

---

## ⚡ Prerequisites

- Python 3.12.4 or higher
- Access to BlazeMeter and APM MCP artifacts
- Setup your `config.yaml` and `chart_colors.yaml` file

---

## 🚀 Getting Started

### 1. Clone the repository

```
git clone https://github.com/canyonlabz/mcp-perf-suite.git
cd perfreport-mcp
```

### 2. Create/activate virtual environment

A virtual environment can be manually activated, or automatically initialized by the MCP Client (e.g. Cursor) on startup.

#### On macOS / Linux
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### On Windows (PowerShell)
```
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

#### 3. Configure your environment

- Update `config.yaml` and `chart_colors.yaml`
- Ensure `templates/` contains required .md templates

#### 4. Running the MCP server ▶️

*Option 1: Run directly with Python*
`python perfreport.py`

*Option 2: Run using `uv` (Recommended) ⚡

You can use **uv** to simplify setup and execution. It manages dependencies and environments automatically.

- Install `uv` (macOS, Linux, Windows PowerShell)
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

- Run the MCP Server with `uv`

```
uv run perfreport.py
```

---

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


---

## 🔄 Workflow Example

1. 🏃‍♂️ Generate a report after test analysis
2. 🌟 Visualize results with charts for stakeholders
3. 👥 Revise reports with feedback (business, QA, engineering)
4. 📈 Compare test runs for trends and regression
5. 📂 Download outputs from the artifacts directory

---

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
  "path": "/artifacts/RUN-20251010-01/reports/performance_report.md"
}
```

**PNG Chart**

```
/artifacts/RUN-20251010-01/charts/response-time.png
```

---

## 🏗 Project Structure

```
perfreport-mcp/
├── perfreport.py                               # MCP entrypoint   
├── services/
│   ├── report_generator.py                     # Module containing functions for report generation
│   ├── comparison_report_generator.py          # Multi-run comparisons
│   ├── chart_generator.py                      # Module containing functions for chart generation
│   └── template_manager.py                     # Module with functions for reading/writing templates
├── utils/
│   └── config.py                               # Utility for loading config.yaml
├── config.yaml                                 # Centralized, environment-agnostic config
├── chart_colors.yaml                           # Configurations for colors to be used in the visualization charts generated
├── chart_schema.yaml                           # Configurations for template chart generation
├── templates/
│   ├── default_report_template.md              # Template for a single performance test run with detailed analysis and executive summary
│   └── default_comparison_report_template.md   # Template for comparing multiple performance test runs side-by-side
├── README.md
├── pyproject.toml                              # Modern Python project metadata & dependencies
└── requirements.txt                            # Dependencies
```


***

## 🔌 Integration

Works seamlessly with BlazeMeter and Datadog MCP servers
for full-stack, end-to-end performance test reporting.

***

## 🙌 Contributing

💡 Suggestions, issues, and PRs are always welcome!
Built with FastMCP, Matplotlib, and love.