# Datadog MCP Server

Welcome to the Datadog MCP Server! 🎉 This is a Python-based MCP server built with **FastMCP** to seamlessly integrate with Datadog's monitoring APIs for performance testing correlation and infrastructure metrics collection.

***

## ✨ Features

- **Environment-based configuration**: Load host and Kubernetes service definitions from `environments.json` for organized metric collection.
- **Host metrics collection**: Retrieve CPU and memory metrics for traditional hosts using Datadog's v1 API.
- **Kubernetes metrics collection**: Fetch container-level CPU metrics for microservices using Datadog's v2 timeseries API.
- **Performance testing integration**: Output structured CSV files for downstream analysis and correlation with BlazeMeter test results.
- **Flexible environment schema**: Support both traditional hosts and Kubernetes clusters in a single environment configuration.
- **Robust error handling**: Comprehensive validation and context-aware error reporting throughout the workflow.
- **Consistent architecture**: Built using the same patterns as the BlazeMeter MCP Server for seamless integration.

***

## 🏁 Prerequisites

- Python 3.12.4 or higher installed
- Datadog API Key and Application Key (set in `.env`)
- Configured `environments.json` file defining your infrastructure

***

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd datadog-mcp
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

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```


### 3. Configure Environment Variables

Create a `.env` file in the project root with your Datadog API credentials:

```env
DD_API_KEY=your_datadog_api_key_here
DD_APP_KEY=your_datadog_application_key_here
```


### 4. Configure Your Infrastructure

Create an `environments.json` file defining your environments, hosts, and Kubernetes services:

```json
{
  "schema_version": "1.0",
  "environments": {
    "QA": {
      "env_tag": "qa",
      "metadata": {
        "platform": "Linux",
        "cpus": 4,
        "memory": "16GB",
        "description": "QA environment for web/app/db tier"
      },
      "tags": ["team:qa"],
      "services": [
        {"service_name": "serviceA", "type": "web"},
        {"service_name": "serviceB", "type": "app"}
      ],
      "hosts": [
        {"hostname": "qa-web-01"},
        {"hostname": "qa-app-01"}
      ],
      "kubernetes": {
        "services": [
          {
            "service_filter": "*products*",
            "description": "Products microservices"
          },
          {
            "service_filter": "*auth*", 
            "description": "Authentication services"
          }
        ]
      }
    }
  }
}
```


***

## ▶️ Running the MCP Server

### Option 1: Run Directly with Python

```bash
python datadog.py
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
uv run datadog.py
```


***

## ⚙️ MCP Server Configuration (`mcp.json`)

You can configure how Cursor or other MCP hosts start the server by adding to your `mcp.json` file:

```json
{
  "mcpServers": {
    "datadog": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/your/datadog-mcp",
        "run",
        "datadog.py"
      ]
    }
  }
}
```

Replace `/path/to/your/datadog-mcp` with your local path.

***

## 🛠️ Usage

Your MCP server exposes these primary tools for Cursor, agents, or other MCP clients:


| Tool | Description |
| :-- | :-- |
| `load_environment` | Load environment configuration from environments.json and store in context |
| `get_host_metrics` | Retrieve CPU and memory metrics for all hosts in the current environment |
| `get_kubernetes_metrics` | Fetch CPU metrics for Kubernetes containers/services in the current environment |


***

## 🔁 Typical Workflow

A standard Datadog MCP workflow for performance testing correlation:

1. **Load Environment Configuration**
    - `load_environment`: Load the desired environment (e.g., "QA", "UAT") and store configuration in context.
2. **Collect Infrastructure Metrics**
    - `get_host_metrics`: Retrieve CPU and memory metrics for traditional hosts during your performance test window.
    - **OR** `get_kubernetes_metrics`: Collect container-level CPU metrics for microservices during the test.
3. **Analyze Results**
    - CSV artifacts are automatically saved to `artifacts/{run_id}/datadog/` for downstream analysis.
    - Correlate infrastructure metrics with BlazeMeter performance test results.

***

## 📊 CSV Output Examples

### Host Metrics CSV

```csv
env_name,env_tag,hostname,timestamp,metric,value
QA,qa,qa-web-01,2025-09-03T15:30:00,system.cpu.user,25.4
QA,qa,qa-web-01,2025-09-03T15:30:00,system.mem.used,8589934592
```


### Kubernetes Metrics CSV

```csv
env_name,env_tag,service_filter,container_name,timestamp,metric,value
QA,qa,*products*,product-api,2025-09-03T15:30:00,kubernetes.cpu.usage.total,1500000000
```


***

## 📁 Project Structure

```
datadog-mcp/
├── datadog.py                     # MCP server entrypoint (FastMCP)
├── services/
│   └── datadog_api.py             # Datadog API & helper functions  
├── utils/
│   └── config.py                  # Utility for loading config.yaml
├── environments.json              # Environment/infrastructure definitions
├── config.yaml                    # Centralized, environment-agnostic config
├── pyproject.toml                 # Modern Python project metadata & dependencies
├── requirements.txt               # Dependencies
├── README.md                      # This file
└── .env                           # Local environment variables (API keys)
```


***

## 🔧 Configuration Files

### `config.yaml`

```yaml
artifacts:
  artifacts_path: "artifacts"

datadog:
  environments_json_path: "environments.json"
```


### Environment Schema

- **env_tag**: Technical Datadog environment tag for filtering
- **hosts**: List of hostnames for traditional host monitoring
- **kubernetes.services**: Service filters for container monitoring
- **metadata**: Environment descriptions and specifications

***

## 🚧 Future Enhancements

- **Memory metrics for Kubernetes**: Add memory collection alongside CPU metrics
- **Custom metric support**: Allow arbitrary Datadog metric queries
- **Dashboard integration**: Export metrics to Datadog dashboards
- **Alert correlation**: Link infrastructure alerts with performance test results
- **Multi-region support**: Handle metrics from different Datadog regions

***

## 🤝 Integration with Performance Testing

This MCP server is designed to work alongside the **BlazeMeter MCP Server** for complete performance testing workflows:

1. **Start BlazeMeter test** → Get `run_id`
2. **Load Datadog environment** → Configure infrastructure monitoring
3. **Collect metrics during test** → Host or Kubernetes metrics
4. **Analyze correlation** → Compare infrastructure load with performance results

***

## 🤝 Contributing

Feel free to open issues or submit pull requests!

***

Created with ❤️ using FastMCP and Datadog APIs
