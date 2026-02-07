# JMeter MCP Server

Welcome to the JMeter MCP Server!
This is a Python-based MCP server built with **FastMCP** to automate JMeter-based performance testing workflows — including Playwright trace capture, network analysis, correlation detection, JMX script generation, test execution, results aggregation, and log analysis.

---

## Features

* **Playwright Integration**: Parse network traces captured by Cursor's Playwright MCP agent for seamless browser-to-JMeter script conversion.
* **Run JMeter tests directly**: Execute JMeter test plans (`.jmx` files) locally.
* **Stop active JMeter tests**: Gracefully terminate test executions in progress.
* **Capture network traffic**: Parse Playwright network traces and map them to test steps from spec files.
* **Analyze correlations**: Identify dynamic values (IDs, tokens, correlation IDs) that flow between requests for parameterization.
* **Orphan ID detection**: Flag request-only IDs without prior response sources for manual parameterization.
* **Generate JMeter scripts**: Convert captured network traffic into executable JMX test scripts with proper structure.
* **Aggregate post-test results**: Parse JMeter JTL output to generate BlazeMeter-style summary reports and KPIs.
* **Deep log analysis**: Analyze JMeter/BlazeMeter log files — group errors by type, API, and root cause with first-occurrence request/response details and JTL correlation.
* **Configurable domain exclusions**: Filter out APM, analytics, and middleware traffic from capture and analysis.
* **Configurable and extensible**: Manage all paths and parameters through `config.yaml` and `jmeter_config.yaml` files.

Future tools under consideration:

* `validate_jmx` — Validate JMX script structure and variable references (currently disabled)
* **OAuth 2.0 / PKCE correlation support** — Authentication flow correlation (Phase 2)
* **HITL tools** — Human-in-the-loop tools to add/edit JMeter elements (e.g., samplers, extractors, assertions) as needed
* **Input adapters** — HAR file adapter and Swagger/OpenAPI adapter to convert those files into the well-structured network capture JSON for JMX generation

---

## Prerequisites

* Python 3.12 or higher
* JMeter installed and added to your system `PATH`
* Configured `config.yaml` (copy from `config.example.yaml`)
* Configured `jmeter_config.yaml` for JMeter-specific settings (copy from `jmeter_config.example.yaml`)
* **Cursor IDE** with Playwright MCP enabled (for browser automation workflows)

All configuration is managed through YAML files — no `.env` file is required.

Planned support for additional MCP hosts:

* **Claude Desktop**
* **VS Code** (via MCP extension)

---

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/canyonlabz/mcp-perf-suite.git
cd mcp-perf-suite/jmeter-mcp
```

### 2. Create Configuration Files

Copy the example configuration and customize for your environment:

```bash
# Copy the example config
cp config.example.yaml config.yaml

# Edit config.yaml with your paths:
# - artifacts_path: where test outputs are stored
# - jmeter_home: path to your JMeter installation
# - jmeter_bin_path: path to JMeter bin directory
```

### 3. Set Up Python Environment

#### Option A: Using `uv` (Recommended)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run directly with uv (handles dependencies automatically)
uv run jmeter.py
```

#### Option B: Using Virtual Environment

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e .
```

---

## Configuration Files

### `config.yaml` (Main Configuration)

Copy from `config.example.yaml` and customize. For detailed guidance on all available options, see the [JMeter MCP Configuration Guide](../docs/jmeter_mcp_configuration_guide.md).

```yaml
general:
  enable_debug: False
  enable_logging: True

logging:
  log_level: "INFO"
  verbose_mode: False
  log_path: "C:\\path\\to\\logs"

artifacts:
  artifacts_path: "C:\\path\\to\\mcp-perf-suite\\artifacts"

jmeter:
  jmeter_home: "C:\\path\\to\\apache-jmeter"
  jmeter_bin_path: "C:\\path\\to\\apache-jmeter\\bin"
  jmeter_start_exe: "jmeter.bat"      # Use "jmeter" for Linux/Mac
  jmeter_stop_exe: "stoptest.cmd"     # Use "stoptest.sh" for Linux/Mac

jmeter_log:
  max_description_length: 200        # Max characters for error description in log analysis output
  max_request_length: 500            # Max characters for captured request details
  max_response_length: 500           # Max characters for captured response details
  max_stack_trace_lines: 50          # Max lines to capture from a stack trace
  error_levels:                      # Log levels to treat as issues (WARN excluded by design)
    - "ERROR"
    - "FATAL"

test_specs:
  web_flows_path: "test-specs\\web-flows"
  api_flows_path: "test-specs\\api-flows"
  examples_path: "test-specs\\examples"

browser:
  browser_type: "chrome"
  headless_mode: True
  window_size: "1920,1080"
  implicit_wait: 10
  page_load_timeout: 60
  think_time: 5000

network_capture:
  capture_api_requests: True
  capture_static_assets: False
  capture_fonts: False
  capture_video_streams: False
  capture_third_party: True
  capture_cookies: True
  capture_domain: ""
  # Domains to exclude from capture and correlation analysis
  exclude_domains:
    - "datadoghq.com"
    - "google-analytics.com"
    - "googletagmanager.com"
    - "facebook.com"
    - "doubleclick.net"
    - "newrelic.com"
    - "segment.io"
    - "hotjar.com"
    - "mixpanel.com"
    - "amplitude.com"
    - "sentry.io"
    - "bugsnag.com"
    - "fullstory.com"
    - "logrocket.com"
```

> **Note:** The `logging` section is reserved for future MCP server debugging and is not currently implemented. It is separate from the `jmeter_log` section, which controls how the `analyze_jmeter_log` tool processes JMeter/BlazeMeter log files.

### `jmeter_config.yaml` (JMeter Script Settings)

Controls how JMX scripts are generated. For detailed guidance, see the [JMeter MCP Configuration Guide](../docs/jmeter_mcp_configuration_guide.md).

```yaml
thread_group:
  num_threads: 10
  ramp_time: 100
  loops: 10

cookie_manager:
  enabled: true

user_defined_variables:
  enabled: true
  variables:
    "thinkTime": 5000
    "pacing": 10000

csv_dataset_config:
  enabled: false
  csv_file_path: "testdata_csv"
  filename: "test_data.csv"
  # ... additional CSV settings

controller_config:
  enabled: true
  controller_type: "simple"

http_sampler:
  auto_redirects: true
  post_body_raw: true

test_action_config:
  enabled: true
  action: "pause"
  duration: 5000
  test_action_name: "Think Time"

results_collector_config:
  view_results_tree: false
  aggregate_report: false
  response_time_graph: true
  summary_report: true
```

---

## Running the MCP Server

### Option 1: Run with `uv` (Recommended)

```bash
uv run jmeter.py
```

### Option 2: Run with Python

```bash
python jmeter.py
```

Runs with default `stdio` transport — ideal for local runs or Cursor integration.

---

## MCP Server Configuration (`mcp.json`)

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

## Tools

The JMeter MCP server exposes the following tools for agents, Cursor, or automation pipelines:

### Browser Automation & Network Capture

| Tool                        | Description                                                                |
| :-------------------------- | :------------------------------------------------------------------------- |
| `archive_playwright_traces` | Archives existing Playwright trace files before a new browser automation run |
| `get_test_specs`            | Discovers available Markdown browser automation specs in `test-specs/`     |
| `get_browser_steps`         | Loads a given Markdown file and parses browser automation test steps       |
| `capture_network_traffic`   | Parses Playwright network traces and maps them to test steps from a spec file |
| `analyze_network_traffic`   | Analyzes network traffic to identify correlations, dynamic values, and orphan IDs |

### JMeter Script Generation & Execution

| Tool                        | Description                                                                |
| :-------------------------- | :------------------------------------------------------------------------- |
| `generate_jmeter_script`    | Converts captured network traffic JSON into a JMeter JMX script            |
| `list_jmeter_scripts`       | Lists the current JMX scripts available for a given test run               |
| `start_jmeter_test`         | Executes a JMeter test based on configuration or provided JMX file         |
| `get_jmeter_run_status`     | Returns real-time metrics for a running JMeter test by reading JTL file    |
| `stop_jmeter_test`          | Gracefully stops an ongoing JMeter test run                                |
| `generate_aggregate_report` | Parses JMeter JTL results to produce BlazeMeter-style aggregate CSV report |

### Log Analysis

| Tool                        | Description                                                                |
| :-------------------------- | :------------------------------------------------------------------------- |
| `analyze_jmeter_log`        | Deep analysis of JMeter/BlazeMeter log files — groups errors by type, API, and root cause with first-occurrence request/response details and optional JTL correlation |

---

## Typical Workflow

### 1. **Prepare Test Specs**

Create a Markdown spec file in `test-specs/web-flows/` defining the browser steps:

```markdown
# My Application Flow

Step 1: Navigate to https://example.com/
Step 2: Click on "Login" button
Step 3: Enter username and password
Step 4: Click "Submit"
Step 5: Verify dashboard loads

END
```

### 2. **Capture Network Traffic**

Use Cursor's Playwright MCP agent to execute the browser automation:

1. **Archive previous traces**: `archive_playwright_traces` clears old trace data
2. **Run browser automation**: Cursor's Playwright agent executes the spec
3. **Capture traffic**: `capture_network_traffic` parses the Playwright traces and maps requests to steps

### 3. **Analyze Correlations**

* `analyze_network_traffic` identifies dynamic values (IDs, tokens, correlation IDs) that flow between requests
* Detects **orphan IDs** — values in request URLs without identifiable source responses
* Outputs `correlation_spec.json` with:
  - High-confidence correlations (source -> usage patterns)
  - Low-confidence orphan IDs (recommend CSV or User Defined Variable parameterization)
  - Parameterization hints (extractor type, strategy)

### 4. **Generate Correlation Naming (Cursor Rules)**

* Apply the `.cursor/rules/jmeter-correlations.mdc` rules to `correlation_spec.json`
* Generates `correlation_naming.json` with meaningful JMeter variable names
* Provides JMeter extractor expressions (JSON Extractor or Regex Extractor)

### 5. **Generate JMeter Script**

* `generate_jmeter_script` converts the captured network traffic JSON into a JMX test plan
* Applies settings from `jmeter_config.yaml` (thread groups, think times, listeners)

### 6. **Execute Test**

* `start_jmeter_test` runs the generated JMX file
* `get_jmeter_run_status` polls real-time metrics during execution
* `stop_jmeter_test` terminates the test gracefully if needed

### 7. **Generate Reports**

* `generate_aggregate_report` produces a BlazeMeter-style aggregate report CSV from JTL results
* Output results available for downstream analysis

### 8. **Analyze Logs**

* `analyze_jmeter_log` performs deep analysis of JMeter or BlazeMeter log files
* Identifies and groups errors by type, API endpoint, and root cause
* Captures first-occurrence request/response details for each unique error
* Correlates log errors with JTL result data when available
* Outputs CSV, JSON, and Markdown reports to `artifacts/<test_run_id>/analysis/`

---

## Project Structure

```
jmeter-mcp/
├── jmeter.py                     # MCP server entrypoint (FastMCP)
├── services/
│   ├── correlation_analyzer.py   # Backward-compatible wrapper for correlations package
│   ├── correlations/             # Modular correlation analysis package (v0.2.0)
│   │   ├── __init__.py           # Package exports (analyze_traffic)
│   │   ├── analyzer.py           # Main orchestrator (_find_correlations, analyze_traffic)
│   │   ├── classifiers.py        # Value type classification and parameterization strategy
│   │   ├── constants.py          # Regex patterns, header exclusions, configuration
│   │   ├── extractors.py         # Source extraction from responses (JSON, headers, redirects)
│   │   ├── matchers.py           # Usage detection in requests, orphan ID detection
│   │   └── utils.py              # URL normalization, JSON traversal, file loading
│   ├── jmeter_log_analyzer.py    # Deep JMeter/BlazeMeter log analysis service
│   ├── jmeter_runner.py          # Handles JMeter execution, control, and reporting
│   ├── network_capture.py        # URL filtering and capture configuration logic
│   ├── playwright_adapter.py     # Parses Playwright traces into step-aware network capture
│   ├── script_generator.py       # Generates JMX scripts from network capture JSON
│   ├── spec_parser.py            # Parses Markdown specs into structured steps
│   └── jmx/                      # JMX builder DSL
│       ├── config_elements.py    # User Defined Variables, CSV Data Sets, etc.
│       ├── controllers.py        # JMeter Controllers (Simple, Transaction, etc.)
│       ├── listeners.py          # JMeter Listeners (View Results Tree, Aggregate Report)
│       ├── oauth2.py             # OAuth 2.0 components (code_challenge, code_verifier, etc.)
│       ├── post_processor.py     # Post-Processor elements (JSON Extractors, RegEx Extractors, etc.)
│       ├── pre_processor.py      # Pre-Processor elements (JSR223 PreProcessor, etc.)
│       ├── plan.py               # JMeter Test Plan and Thread Groups
│       └── samplers.py           # JMeter Samplers (HTTP Request GET/POST/PUT/DELETE)
├── utils/
│   ├── browser_utils.py          # Domain extraction, logging setup, async utilities
│   ├── config.py                 # Loads configuration YAML files
│   ├── file_utils.py             # File handling, discovery, and output utilities
│   └── log_utils.py              # Log parsing utilities (regex, extraction, normalization)
├── config.example.yaml           # Example configuration template
├── jmeter_config.example.yaml    # Example JMeter script generation settings
├── pyproject.toml                # Project metadata and dependencies
├── uv.lock                       # uv dependency lock file
├── README.md                     # This file
└── test-specs/
    ├── web-flows/
    │   └── blazedemo_product_purchase.md
    ├── api-flows/
    │   └── (API flow specs)
    └── examples/
        └── (Example templates)
```

---

## Artifacts Output Structure

When you run tests and analyses, artifacts are organized under `artifacts/<test_run_id>/`:

```
artifacts/
└── <test_run_id>/
    ├── jmeter/
    │   ├── network-capture/
    │   │   └── network_capture_<timestamp>.json
    │   ├── correlation_spec.json        # Correlation analysis output
    │   ├── correlation_naming.json      # Variable naming (via Cursor Rules)
    │   ├── <test_run_id>.jmx            # Generated JMeter script
    │   ├── <test_run_id>.jtl            # JMeter results log
    │   ├── <test_run_id>_aggregate_report.csv
    │   └── jmeter.log                   # JMeter execution log
    ├── blazemeter/
    │   ├── jmeter.log                   # BlazeMeter JMeter log(s)
    │   └── test-results.csv             # BlazeMeter JTL (renamed)
    ├── analysis/
    │   ├── <source>_log_analysis.csv    # Log analysis issues (tabular)
    │   ├── <source>_log_analysis.json   # Log analysis metadata + full issues
    │   └── <source>_log_analysis.md     # Log analysis report (human-readable)
    └── test-specs/
        └── (run-specific spec overrides)
```

---

## Correlation Analysis Details

The correlation analyzer (v0.2.0) performs the following:

### Phase 1: Source Extraction
- **Response JSON bodies**: Walks JSON up to 5 levels deep, extracting ID-like values
- **Response headers**: Extracts correlation headers (x-request-id, x-correlation-id, etc.)
- **Redirect URLs**: Parses `Location` headers for OAuth params (client_id, state, nonce, etc.)

### Phase 2: Usage Detection
- **Request URLs**: Path segments and query parameters
- **Request headers**: Custom headers (excluding HTTP plumbing like content-length)
- **Request bodies**: JSON fields and form data

### Phase 3: Orphan ID Detection
- Identifies ID-like values in requests without prior response sources
- Suggests parameterization strategy:
  - `csv_dataset` for high-frequency IDs (3+ occurrences)
  - `user_defined_variable` for low-frequency IDs (1-2 occurrences)

### Output Schema
```json
{
  "correlations": [
    {
      "correlation_id": "corr_1",
      "type": "business_id",
      "value_type": "business_id_numeric",
      "confidence": "high",
      "source": { ... },
      "usages": [ ... ],
      "parameterization_hint": {
        "strategy": "extract_and_reuse",
        "extractor_type": "json"
      }
    }
  ],
  "summary": {
    "total_correlations": 27,
    "business_ids": 12,
    "correlation_ids": 0,
    "oauth_params": 4,
    "orphan_ids": 11
  }
}
```

---

## Future Enhancements

### Input Adapters
* **HAR file adapter** — Convert browser-recorded or proxy-captured HAR files into network capture JSON for JMX generation (Phase 1)
* **Swagger/OpenAPI adapter** — Convert API specifications into synthetic network capture JSON for JMX generation (Phase 2)
* Both adapters reuse the existing correlation analysis and JMX generation pipeline

### Script Generation & Editing
* **OAuth 2.0 / PKCE correlation support** for authentication flows
* **Automatic JMX correlation insertion** based on `correlation_naming.json`
* **HITL tools** — Human-in-the-loop tools for adding/editing JMeter elements (samplers, extractors, assertions, pre/post-processors) directly through the MCP

### Integration & Infrastructure
* **Integration with BlazeMeter and Datadog MCPs** for unified execution and monitoring
* **Real-time metric streaming** to Datadog or Prometheus
* **Auto-scaling JMeter clusters** (K8s-based execution)
* **LLM-based test analysis** using PerfAnalysis MCP
* **Report generation via PerfReport MCP**

### MCP Host Support
* **Claude Desktop** support
* **VS Code** support (via MCP extension)

---

## Contributing

Feel free to open issues or submit pull requests to enhance functionality, add new tools, or improve documentation!

---

Created with FastMCP, JMeter, and the MCP Perf Suite architecture.
