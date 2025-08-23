# BlazeMeter MCP Server

Welcome to the BlazeMeter MCP Server! 🎉 This is a Python-based MCP server built with **FastMCP** to interact easily with BlazeMeter’s API for performance testing lifecycle management.

---

## ✨ Features

- List BlazeMeter workspaces, projects, and tests  
- Start BlazeMeter load tests  
- Fetch detailed run summaries with key metrics and response time aggregates  
- Modular and extensible design ready for future integrations like Datadog  

---

## 🏁 Prerequisites

- Python 3.12.4 or higher installed  
- BlazeMeter API Key (set in `.env`)  

---

## 🚀 Getting Started

### 1. Clone the Repository

```

git clone <your-repo-url>
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

Your MCP server exposes these primary actions which Cursor or other MCP clients can call:

| Action             | Description                         |
|--------------------|-----------------------------------|
| `get_workspaces`   | List all BlazeMeter workspaces     |
| `get_projects`     | List projects for a workspace      |
| `get_tests`        | List tests for a project           |
| `start_test`       | Start a load test run              |
| `get_run_results`  | Fetch summary metrics of a test run|

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

blazemeter_mcp_server/
├── blazemeter.py          # MCP server entrypoint with FastMCP
├── services/
│   └── blazemeter_api.py  # BlazeMeter API logic
├── artifacts/             # Runtime directory for results/JTL/log downloads
├── requirements.txt       # Python dependencies
├── README.md              # This file
└── .env                   # Environment variables (API keys)

```

---

## 🚧 Future Enhancements

- Support JTL/log artifact downloads and local serving  
- Integration with Datadog MCP Server for correlated analytics  
- Advanced filtering and query options in summaries  
- More robust error handling and logging  

---

## 🤝 Contributing

Feel free to open issues or submit pull requests!

---

Created with ❤️ using FastMCP and BlazeMeter APIs

