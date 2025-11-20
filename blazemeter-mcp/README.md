# BlazeMeter MCP Server

Welcome to the BlazeMeter MCP Server! 🎉 This is a Python-based MCP server built with **FastMCP** to interact easily with BlazeMeter’s API for performance testing lifecycle management.

---

## ✨ Features

- **List workspaces, projects, and tests**: Discover all available test suites organized by workspace and project.
- **Start BlazeMeter load tests**: Trigger test runs for any configured test, directly via MCP actions.
- **Fetch detailed run summaries**: Retrieve key metrics—including response time aggregates—after each test run.
- **Download and manage test artifacts**: Fully automate retrieval, extraction, and processing of test result artifacts (`artifacts.zip`, JMeter logs, KPIs).
- **Flexible configuration loading**: Centralized `config.yaml` management for all paths and parameters.
- **Extensible utilities**: Modular codebase supporting new MCP server integrations (e.g. Datadog, test analysis/reporting).
- **Defensive error handling**: Robust input validation and artifact management for reliable automation.

---

## 🏁 Prerequisites

- Python 3.12.4 or higher installed  
- BlazeMeter API Key (set in `.env`)  

---

## 🚀 Getting Started

### 1. Clone the Repository

```
git clone https://github.com/canyonlabz/mcp-perf-suite.git
cd blazemeter_mcp_server
```

### 2. Create & Activate a Python Virtual Environment

This ensures the MCP server dependencies do not affect your global Python environment.

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

### 3. Configure Environment Variables

Create a `.env` file in the project root with your BlazeMeter API key:

```
BLAZEMETER_API_KEY=your_blazemeter_api_key_here
BLAZEMETER_API_SECRET=your_blazemeter_api_secret_here
BLAZEMETER_ACCOUNT_ID=your_blazemeter_account_id_here
BLAZEMETER_WORKSPACE_ID=your_blazemeter_workspace_id_here
```

---

## ▶️ Running the MCP Server

### Option 1: Run Directly with Python

```
python blazemeter.py
```

This runs the MCP server with the default `stdio` transport — ideal for running locally or integrating with Cursor AI.

---

### Option 2: Run Using `uv` (Recommended) ⚡️

You can use **uv** to simplify setup and execution. It manages dependencies and environments automatically.

#### Install `uv` (macOS, Linux, Windows PowerShell)

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Run the MCP Server with `uv`

```
uv run blazemeter.py
```

---

## ⚙️ MCP Server Configuration (`mcp.json`)

You can create an `mcp.json` file to configure how Cursor or other MCP hosts start the server:

```
{
    "mcpServers": {
        "blazemeter": {
            "command": "uv",
            "args": [
                "--directory",
                "/path/to/your/blazemeter_mcp_server",
                "run",
                "blazemeter.py"
            ]
        }
    }
}
```

Replace `/path/to/your/blazemeter_mcp_server` with your local path.

---

## 🛠️ Usage

Your MCP server exposes these primary tools for Cursor, agents, or other MCP clients (with a short description of each):

| Tool | Description |
| :-- | :-- |
| `get_workspaces` | List all workspaces in your BlazeMeter account |
| `get_projects` | List projects for a specified workspace |
| `get_tests` | List all tests in a given project |
| `start_test` | Initiate a new BlazeMeter test run |
| `check_test_status` | Check the status breakdown of a BlazeMeter test run (running, completed, or error states) |
| `get_public_report_url` | Generate a shareable public BlazeMeter report URL for a completed test run |
| `list_test_runs` | List past runs (masters) for a test within a time range, with session IDs |
| `get_artifacts_path` | Return the configured local path for storing all test artifacts |
| `get_artifact_file_list` | Get downloadable artifact/log files for a specific session |
| `download_artifacts_zip` | Download `artifacts.zip` for a run and store in correct folder |
| `extract_artifact_zip` | Unpack the ZIP file and list all extracted files for analysis |
| `process_extracted_files` | Move/rename key files (especially `kpi.jtl` to `test-results.csv`) |
| `get_run_results` | Fetch summary metrics and key performance indicators for a test run |

---

## 🔁 Typical Workflow

A standard BlazeMeter MCP workflow uses these tools in sequence for automated, robust performance testing:

1. **Start a Test**
    - `start_test`: Initiate a new BlazeMeter load test run.
2. **Poll for Status**
    - `check_test_status`: Monitor the test status until it completes or ends.
3. **Get Public Report URL (optional)**
    - `get_public_report_url`: Generate a shareable report link for stakeholders once the test finishes.
4. **List Past Runs (optional for analytics/history)**
    - `list_test_runs`: View previous completed runs for a given test within a time range.
5. **Retrieve and Process Test Artifacts**
    - `get_artifact_file_list`: Get artifact and log download URLs for the completed test session.
    - `download_artifacts_zip`: Download the results archive for the run.
    - `extract_artifact_zip`: Unpack and list extracted files (CSV, logs, config, etc.).
    - `process_extracted_files`: Move/rename essential files (e.g. convert `kpi.jtl` to `test-results.csv`).
6. **Analyze Results**
    - `get_run_results`: Return key performance metrics, errors, response time statistics, and summary fields for the run.

---

## 📊 Result Summary Example

When you call `get_run_results(run_id)`, the server returns a user-friendly summary including:

- Test name, test and run IDs  
- Start and end times, duration  
- Max virtual users  
- Sample counts (total, passed, failed, errors)  
- Aggregate response times (min, max, avg, 90th percentile)  

Example summary snippet:

```

BlazeMeter Test Run Summary
===========================
Test Name: My Load Test
Test ID: 98765
Run ID: 1234567

Start Time: 2025-08-21 19:08:00 UTC
End Time: 2025-08-21 19:38:00 UTC
Duration: 1800s
Max Virtual Users: 1000

Samples Total: 256000
Pass Count: 254788
Fail Count: 1212
Error Count: 1212

Response Time (ms):
Min: 88
Max: 8500
Avg: 340
90th Percentile: 560

```

---

## 📁 Project Structure

```
blazemeter-mcp/
├── blazemeter.py                  # MCP server entrypoint (FastMCP)
├── services/
│   └── blazemeter_api.py          # BlazeMeter API & helper functions
├── utils/
│   └── config.py                  # Utility for loading config.yaml
├── config.yaml                    # Centralized, environment-agnostic config
├── pyproject.toml                 # Modern Python project metadata & dependencies
├── requirements.txt*              # (if present) for legacy dependency management
├── README.md                      # This file
└── .env                           # Local environment variables (API keys, secrets)
```

\*If you're exclusively using modern tools like `uv` with `pyproject.toml`, you may omit `requirements.txt`.

---

## 🚧 Future Enhancements

- Expanded artifact processing \& analytics workflows
- Integration with Datadog and other monitoring MCP servers
- Automated test result analysis via LLMs
- Enhanced error reporting and system diagnostics

---

## 🤝 Contributing

Feel free to open issues or submit pull requests!

---

Created with ❤️ using FastMCP and BlazeMeter APIs

