# Performance Analysis MCP Server

Welcome to the Performance Analysis MCP Server! 🎉 This Python-based MCP server is built with **FastMCP** to provide comprehensive analysis of BlazeMeter load testing results correlated with Datadog infrastructure metrics for performance bottleneck identification and optimization insights.

***

## ✨ Features

- **BlazeMeter Results Analysis**: Process JMeter JTL files for response time aggregates, error rates, throughput, and SLA compliance validation
- **Datadog Infrastructure Analysis**: Analyze CPU and memory metrics from both traditional hosts and Kubernetes services during test execution
- **Cross-Correlation Analysis**: Identify relationships between performance degradation and infrastructure resource constraints
- **Statistical Anomaly Detection**: Detect outliers and unusual patterns in both performance and infrastructure metrics using configurable sensitivity thresholds
- **Bottleneck Identification**: Pinpoint specific performance limiting factors and resource saturation points with prioritized recommendations
- **Multi-Run Trend Analysis**: Compare up to 5 test runs to track performance improvements or regressions over time
- **AI-Powered Executive Summaries**: Generate actionable insights and optimization recommendations using OpenAI GPT models
- **Multiple Output Formats**: Export results in JSON, CSV, and Markdown formats for downstream reporting and analysis
- **Consistent Architecture**: Built using the same modular patterns as BlazeMeter and Datadog MCP Servers for seamless integration

***

## 🏁 Prerequisites

- Python 3.12.4 or higher installed
- Access to BlazeMeter and Datadog artifact folders containing test results and metrics
- OpenAI API key for AI-powered summary generation (set in `.env`)
- Completed BlazeMeter and Datadog data collection from previous test runs

***

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd perfanalysis-mcp
```


### 2. Create \& Activate a Python Virtual Environment

This ensures the MCP server dependencies do not affect your global Python environment.

#### On macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```


#### On Windows (PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```


### 3. Configure Environment Variables

Create a `.env` file in the project root with your OpenAI API credentials:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

Ensure your `config.yaml` is configured with the correct artifacts path pointing to your BlazeMeter and Datadog data.

***

## ▶️ Running the MCP Server

### Option 1: Run Directly with Python

```bash
python perfanalysis.py
```

This runs the MCP server with the default `stdio` transport — ideal for running locally or integrating with Cursor AI.

### Option 2: Run Using `uv` (Recommended) ⚡️

You can use **uv** to simplify setup and execution. It manages dependencies and environments automatically.

#### Install `uv` (macOS, Linux, Windows PowerShell)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```


#### Run the MCP Server with `uv`

```bash
uv run perfanalysis.py
```


***

## ⚙️ MCP Server Configuration (`mcp.json`)

You can configure how Cursor or other MCP hosts start the server by adding to your `mcp.json` file:

```json
{
  "mcpServers": {
    "perfanalysis": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/your/perfanalysis-mcp",
        "run",
        "perfanalysis.py"
      ]
    }
  }
}
```

Replace `/path/to/your/perfanalysis-mcp` with your local path.

***

## 🛠️ Usage

Your MCP server exposes these primary tools for Cursor, agents, or other MCP clients:


| Tool | Description |
| :-- | :-- |
| `analyze_test_results` | Analyze BlazeMeter JMeter test results (JTL CSV format) for performance statistics and SLA validation |
| `analyze_environment_metrics` | Analyze Datadog infrastructure metrics (CPU/Memory) from hosts and Kubernetes services |
| `correlate_test_results` | Cross-correlate BlazeMeter and Datadog data to identify cause-effect relationships |
| `detect_anomalies` | Detect statistical anomalies in performance and infrastructure metrics with configurable sensitivity |
| `identify_bottlenecks` | Identify performance bottlenecks and constraint points with prioritized recommendations |
| `compare_test_runs` | Compare multiple test runs for trend analysis (maximum 5 runs) |
| `summary_analysis` | Generate executive summary with AI-powered insights using OpenAI integration |
| `get_analysis_status` | Get current analysis completion status for a test run |


***

## 🔁 Typical Workflow

A standard Performance Analysis MCP workflow for comprehensive performance insights:

1. **Analyze Test Results**
    - `analyze_test_results`: Process BlazeMeter JTL files for response time statistics, error analysis, and SLA compliance
2. **Analyze Infrastructure Metrics**
    - `analyze_environment_metrics`: Process Datadog CPU/Memory metrics from hosts and Kubernetes services
3. **Cross-Correlate Data**
    - `correlate_test_results`: Identify relationships between performance degradation and infrastructure constraints
4. **Detect Anomalies**
    - `detect_anomalies`: Find statistical outliers and unusual patterns in both performance and infrastructure data
5. **Identify Bottlenecks**
    - `identify_bottlenecks`: Pinpoint specific performance limiting factors and optimization opportunities
6. **Generate Executive Summary**
    - `summary_analysis`: Create AI-powered comprehensive summary with actionable recommendations

***

## 📊 Output Examples

### Performance Analysis JSON

```json
{
  "overall_stats": {
    "total_samples": 256000,
    "success_rate": 99.53,
    "avg_response_time": 340,
    "p90_response_time": 560,
    "error_count": 1212
  },
  "sla_analysis": {
    "threshold_ms": 5000,
    "compliance_rate": 0.98,
    "violations": []
  }
}
```


### Correlation Analysis CSV

```csv
metric_1,metric_2,correlation_coefficient,p_value,significance
avg_response_time,cpu_utilization,0.72,0.001,high
error_rate,memory_usage,0.45,0.02,medium
```


### Executive Summary Markdown

```markdown
# Executive Summary - Test Run 1234567

## Key Findings
- Overall performance meets SLA requirements with 99.5% success rate
- Strong correlation (0.72) between CPU utilization and response times
- Memory bottleneck identified on qa-app-01 during peak load

## Recommendations
1. Scale CPU resources for application tier
2. Optimize database connection pooling
3. Implement caching for frequently accessed endpoints
```


***

## 📁 Project Structure

```
perfanalysis-mcp/
├── perfanalysis.py                # MCP server entrypoint (FastMCP)
├── services/
│   └── performance_analyzer.py    # Core analysis logic and workflows
├── utils/
│   ├── config.py                  # Config loader utility
│   ├── file_processor.py          # CSV/file processing utilities
│   ├── statistical_analyzer.py    # Statistical analysis functions
│   └── openai_client.py           # OpenAI API integration
├── config.yaml                    # Server configuration with SLA thresholds
├── pyproject.toml                 # Modern Python project metadata & dependencies
├── requirements.txt               # Dependencies
├── README.md                      # This file
└── .env                           # Local environment variables (OpenAI API key)
```


***

## 🔧 Configuration Files

### `config.yaml`

```yaml
# Performance Analysis Settings
perf_analysis:
  response_time_sla: 5000  # milliseconds
  statistical_confidence: 0.95
  anomaly_sensitivity:
    low: 3.0      # Standard deviations
    medium: 2.5
    high: 2.0

# OpenAI Integration
openai:
  model: "gpt-4o-mini"  # Cost-effective option
  max_tokens: 2000
  temperature: 0.3
```


***

## 🧪 Analysis Capabilities

### Statistical Methods

- **Correlation Analysis**: Pearson and Spearman correlation for linear and non-linear relationships
- **Anomaly Detection**: Z-score analysis with configurable standard deviation thresholds
- **Trend Analysis**: Time-series analysis with moving averages for multi-run comparison
- **SLA Validation**: Response time compliance checking against configurable thresholds


### AI-Powered Insights

- **Executive Summaries**: Business-friendly analysis using OpenAI GPT models
- **Optimization Recommendations**: Actionable insights based on correlation patterns
- **Risk Assessment**: Identification of performance risks and constraint points

***

## 🚧 Future Enhancements

- **Temporal Correlation**: Per-identifier correlation (service/host) to preserve hot spot visibility
- **Insight Enrichment**: Highlight top APIs per “interesting” window, summarize constraints, and surface actionable findings
- **Custom Metrics**: Support for additional performance and infrastructure metrics
- **Predictive Analysis**: Machine learning models for performance forecasting
- **Dashboard Integration**: Export data optimized for reporting dashboards
- **Multi-Environment Comparison**: Cross-environment performance analysis

***

## 🤝 Integration with Performance Testing Suite

This MCP server is designed to work seamlessly with the **BlazeMeter MCP Server** and **Datadog MCP Server** for complete end-to-end performance testing workflows:

1. **BlazeMeter MCP** → Execute load tests and collect performance artifacts
2. **Datadog MCP** → Gather infrastructure metrics during test execution
3. **Performance Analysis MCP** → Correlate data and generate insights
4. **Future Reporting MCP** → Create formatted reports and visualizations

***

## 🤝 Contributing

Feel free to open issues or submit pull requests to enhance the analysis capabilities!

***

Created with ❤️ using FastMCP, Pandas, SciPy, and OpenAI APIs