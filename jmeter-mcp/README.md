# JMeter MCP Server

Welcome to the JMeter MCP Server! 🎉
This is a Python-based MCP server built with **FastMCP** to automate JMeter-based performance testing workflows — including execution, monitoring, artifact capture, and analysis.

---

## ✨ Features

* **Run JMeter tests directly**: Execute JMeter test plans (`.jmx` files) locally or remotely.
* **Stop active JMeter tests**: Gracefully terminate test executions in progress.
* **Capture network traffic**: Record live network traffic via browser automation or proxy tools.
* **Analyze captured traffic**: Inspect requests/responses to identify potential bottlenecks or anomalies.
* **Convert traffic to HAR or JSON**: Standardize captured network traffic for analysis or JMeter script creation.
* **Generate JMeter scripts**: Convert HAR or JSON traffic into executable JMX test scripts.
* **Aggregate post-test results**: Parse JMeter JTL output to generate summary reports and KPIs.
* **Configurable and extensible**: Manage all paths and parameters through `config.yaml` and `.env` files.
* **Browser integration (Cursor 2.0)**: Utilize Cursor’s browser agent for web traffic capture and playback.

🧩 Future tools under consideration:

* `get_jmeter_logs` – Retrieve logs and errors after execution
* `validate_jmx` – Validate JMX syntax and embedded variables
* `generate_summary_report` – Produce a summarized Markdown report for quick insights
* `compare_runs` – Compare two or more JMeter test results (for regression or trend analysis)

---

## 🏁 Prerequisites

* Python 3.12.4 or higher
* JMeter installed and added to your system `PATH`
* Configured `config.yaml` for server and environment settings
* Optional `.env` for credentials and local paths

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/canyonlabz/mcp-perf-suite.git
cd jmeter-mcp
```

### 2. Create & Activate a Python Virtual Environment

#### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Windows (PowerShell)

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

### 3. Configure the MCP Server

Define key paths and parameters in `config.yaml`:

```yaml
jmeter:
  jmeter_home: "C:\\<path_to_jmeter>\\apache-jmeter"
  jmeter_bin_path: "C:\\<path_to_jmeter>\\apache-jmeter\\bin" 
  jmeter_start_exe: "jmeter.bat" 
  jmeter_stop_exe: "stoptest.cmd" 

test_specs:
  web_flows_path: "test-specs\\web-flows"   # Browser web automation flow definition files
  api_flows_path: "test-specs\\api-flows"   # API automation flow definition files

browser:
  browser_type: "chrome"               # Options: "chrome", "firefox", "edge"
  headless_mode: True                  # Run browser in headless mode
  window_size: "1920,1080"             # Browser window size
  implicit_wait: 10                    # Implicit wait time in seconds
  page_load_timeout: 60                # Page load timeout in seconds

network_capture:
  capture_api_requests: True          # Always true – critical for JMeter
  capture_static_assets: False        # CSS, JS, PNG, JPG, etc.
  capture_fonts: False                # WOFF, WOFF2, TTF, etc.
  capture_third_party: True           # Google Fonts, CDN, Ads
  capture_cookies: True               # Always true – critical for JMeter
  capture_domain: ""                  
```

---

## ▶️ Running the MCP Server

### Option 1: Run with Python

```bash
python jmeter.py
```

Runs with default `stdio` transport — ideal for local runs or Cursor integration.

---

### Option 2: Run Using `uv` (Recommended) ⚡️

#### Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Run the MCP Server

```bash
uv run jmeter.py
```

---

## ⚙️ MCP Server Configuration (`mcp.json`)

Example setup for Cursor or compatible MCP hosts:

```json
{
  "mcpServers": {
    "jmeter": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/your/jmeter-mcp",
        "run",
        "jmeter.py"
      ]
    }
  }
}
```

---

## 🛠️ Tools

Your MCP server exposes the following tools for agents, Cursor, or automation pipelines:

| Tool                        | Description                                                                |
| :-------------------------- | :------------------------------------------------------------------------- |
| `get_test_specs`            | Discover available Markdown browser automation specs in `test-specs/`.     |
| `get_browser_steps`         | Loads a given Markdown file with browser automation test steps             | 
| `capture_network_traffic`   | Captures network traffic data and converts to HAR or JSON file             |
| `analyze_network_traffic`   | Analyzes network traffic to extract request metadata and statistics        |
| `generate_jmeter_script`    | Converts HAR or JSON network traffic into a JMeter JMX script              |
| `validate_jmx`              | Validates JMX script structure and variable references                     |
| `list_jmeter_scripts`       | Lists the current JMX scripts available for a given run_id                 |
| `start_jmeter_test`         | Executes a JMeter test based on configuration or provided JMX file         |
| `get_jmeter_run_status`     | Checks the current status of a running JMeter test and returns run details |
| `stop_jmeter_test`          | Gracefully stops an ongoing JMeter test run                                |
| `get_jmeter_run_summary`    | Analyzes the test run results and provides high-level summary              |
| `generate_aggregate_report` | Parses JMeter JTL results to produce KPI summaries                         |

---

## 🔁 Typical Workflow

1. **Prepare Test**

   * Load configuration and environment variables.
   * Ensure JMX test plan is ready or generate from HAR.

2. **Run Test**

   * `start_jmeter_test` executes the JMeter test.
   * Logs and results stored in artifacts directory.

3. **Monitor / Stop Test (Optional)**

   * `stop_jmeter_test` terminates the test gracefully if required.

4. **Post-Processing**

   * `get_jmeter_run_summary` generates high-level summary of test run.
   * `generate_aggregate_report` extracts KPIs from JTL.
   * `analyze_network_traffic` reviews captured HTTP data.

5. **Optional Conversion**

   * `capture_network_traffic` → `generate_jmeter_script` for iterative script refinement.

6. **Reporting**

   * Output results as CSV, JSON, or Markdown for downstream MCP analysis.

---

## 📁 Project Structure

```
jmeter-mcp/
├── jmeter.py                     # MCP server entrypoint (FastMCP)
├── services/
│   ├── browser_automation.py     # OLD jmeter-ai-studio code that uses browser-use to iterate over the "STEPS", then gradually appended network captured data to JSON output file. This file may not be requied for the JMeter MCP.
│   ├── jmeter_runner.py          # Handles JMeter execution and control, plus creating a test summary & aggregate report
│   ├── log_analyzer.py           # Analyzes the JMeter log for errors, warnings, and other potential issues
│   ├── network_capture.py        # Captures and processes network traffic
│   ├── spec_parser.py            # parse Markdown -> structured steps
│   ├── script_generator.py       # Generates JMX scripts from HAR
│   └── jmx/                          # <<< JMX builder DSL lives here
│       ├── config_elements.py        # JMeter config elements such as User Defined Variables, CSV Data Sets, etc.
│       ├── controllers.py            # JMeter Controllers (e.g. Simple, Transaction, etc.)
│       ├── listeners.py              # JMeter Listeners (e.g. View Results Tree, Aggregate Report, etc.)
│       ├── samplers.py               # JMeter Samplers (e.g. HTTP Request for GET/POST/PUT/DELETE, etc.)
│       └── plan.py                   # JMeter Test Plan and Thread Groups
├── utils/
│   ├── browser_utils.py          # Defines the output paths for browser automation from Playwright MCP (e.g. recording path, trace path, etc.)
│   ├── config.py                 # Loads configuration YAML files (e.g. config.yaml, jmeter_config.yaml)
│   └── file_utils.py             # File handling utilities
├── config.yaml                   # Centralized configuration
├── .env                          # Environment variables
├── requirements.txt              # Dependencies
├── pyproject.toml                # Project metadata
├── README.md                     # This file
└── test-specs/
    ├── web-flows/
    │   ├── blazedemo_product_purchase.md
    │   └── <other_web_flow>.md
    ├── api-flows/
    │   ├── user_login_flow.md
    │   └── <other_api_flow>.md
    └── examples/
        └── sample_template.md
```

---

## 🚧 Future Enhancements

* **Integration with BlazeMeter and Datadog MCPs** for unified execution and monitoring
* **Real-time metric streaming** to Datadog or Prometheus
* **Auto-scaling JMeter clusters** (K8s-based execution)
* **LLM-based test analysis** using PerfAnalysis MCP
* **Report generation via PerfReport MCP**

---

## 🤝 Contributing

Feel free to open issues or submit pull requests to enhance functionality, add new tools, or improve documentation!

---

Created with ❤️ using FastMCP, JMeter, and the MCP Perf Suite architecture.
