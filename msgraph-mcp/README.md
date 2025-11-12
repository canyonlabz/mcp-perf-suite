# Microsoft Graph MCP Server (msgraph-mcp)

Welcome to the Microsoft Graph MCP Server! 🎉
This Python-based MCP server, built with **FastMCP**, integrates with **Microsoft Graph APIs** to extend your performance testing lifecycle into **Microsoft Teams** and **SharePoint**.

It automates artifact uploads, test notifications, and collaboration workflows — bringing performance test visibility directly into your organization’s Microsoft 365 ecosystem.

---

## ✨ Features

* **Automated artifact publishing to SharePoint** 🗂️
  Upload all test artifacts (reports, CSVs, charts, logs) to a SharePoint document library per test run.

* **Real-time test notifications in Microsoft Teams** 💬
  Announce when tests start, complete, or fail — with direct links to artifacts and reports.

* **Seamless integration with other MCP servers** 🔗
  Designed to work alongside BlazeMeter, JMeter, Datadog, PerfAnalysis, and PerfReport MCP servers.

* **Configurable through YAML and environment variables** ⚙️
  Centralized configuration for site, drive, and Teams channel management.

* **Extensible and secure** 🔒
  Uses Microsoft’s OAuth2 Client Credentials flow with secure secret storage in `.env`.

---

## 🏁 Prerequisites

* Python **3.12.4** or higher
* A registered **Azure AD application** with Microsoft Graph API permissions
* `.env` file containing Microsoft Graph credentials
* `config.yaml` defining SharePoint and Teams settings

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd msgraph-mcp
```

### 2. Create & Activate a Virtual Environment

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

### 3. Configure Environment Variables

Create a `.env` file in the project root with your Microsoft Graph credentials:

```env
MSGRAPH_TENANT_ID=<tenant-guid>
MSGRAPH_CLIENT_ID=<app-client-id>
MSGRAPH_CLIENT_SECRET=<app-client-secret>
```

---

### 4. Configure MCP Settings (`config.yaml`)

```yaml
graph:
  authority: "https://login.microsoftonline.com/${MSGRAPH_TENANT_ID}"
  scopes:
    - "https://graph.microsoft.com/.default"

sharepoint:
  site_id: "<site-id>"
  drive_id: "<document-library-id>"
  base_folder: "PerfArtifacts"
  include_subfolders: ["report", "analysis", "charts"]
  include_extensions: [".md", ".csv", ".png", ".json"]

teams:
  team_id: "<team-id>"
  channel_id: "<channel-id>"
  notify_on_start: true
  notify_on_complete: true
  notify_on_failure: true
```

---

## ▶️ Running the MCP Server

### Option 1: Run Directly with Python

```bash
python msgraph.py
```

### Option 2: Run Using `uv` (Recommended) ⚡️

```bash
uv run msgraph.py
```

---

## ⚙️ MCP Server Configuration (`mcp.json`)

Add the following to your MCP host configuration (e.g., Cursor):

```json
{
  "mcpServers": {
    "msgraph": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/your/msgraph-mcp",
        "run",
        "msgraph.py"
      ]
    }
  }
}
```

Replace the path with your local msgraph-mcp directory.

---

## 🛠️ Available Tools

Your MCP server exposes the following tools for integration into agents, pipelines, or other MCP workflows:

| Tool                               | Description                                                                                           | Focus          |
| :--------------------------------- | :---------------------------------------------------------------------------------------------------- | :------------- |
| `create_sp_folder_for_run`         | Create a SharePoint folder for the given `test_run_id` (e.g., `PerfArtifacts/<test_run_id>/`).        | 🗂️ SharePoint |
| `upload_sp_artifact`               | Upload a single file to SharePoint for manual or targeted use.                                        | 🗂️ SharePoint |
| `bulk_upload_sp_artifacts_for_run` | Scan `artifacts/<test_run_id>/` and upload filtered files (e.g., reports, charts, CSVs).              | 🗂️ SharePoint |
| `list_sp_artifacts_for_run`        | List all artifacts already uploaded for a test run.                                                   | 🗂️ SharePoint |
| `get_sp_artifact_links`            | Return key SharePoint links (folder + key files) for the given `test_run_id`.                         | 🗂️ SharePoint |
| `notify_test_start`                | Send a Teams message announcing that a performance test has started.                                  | 💬 Teams       |
| `notify_test_complete`             | Post a summary message in Teams when a test completes successfully, with SharePoint/Confluence links. | 💬 Teams       |
| `notify_test_failure`              | Post a Teams alert when a test fails or violates SLAs.                                                | 💬 Teams       |
| `post_custom_message`              | Send a custom Teams message (useful for one-off or ad-hoc updates).                                   | 💬 Teams       |
| `validate_graph_connection`        | Verify the Microsoft Graph API credentials and permissions.                                           | 🔧 Utility     |
| `list_teams_channels`              | List Teams channels for the configured Team to discover valid destinations.                           | 🔧 Utility     |
| `list_sharepoint_libraries`        | (Optional) List available SharePoint document libraries under the configured site.                    | 🔧 Utility     |

---

## 🔁 Typical Workflow Integration

A typical cross-MCP workflow with **msgraph-mcp** might look like this:

1. **JMeter or BlazeMeter MCP** → Executes the performance test.
2. **PerfAnalysis MCP** → Analyzes the results.
3. **PerfReport MCP** → Generates a Markdown performance report.
4. **Confluence MCP** → Publishes report to Confluence (returns report URL).
5. **msgraph-mcp**:

   * `bulk_upload_sp_artifacts_for_run(<test_run_id>)` → Uploads artifacts to SharePoint.
   * `get_sp_artifact_links(<test_run_id>)` → Retrieves folder and file URLs.
   * `notify_test_complete(<test_run_id>, summary, confluence_page_url, sharepoint_folder_url)` → Posts Teams message linking both.

📢 Example Teams message:

```
✅ Performance Test Completed: 100-User Load Test for My Project Application
Run ID: 98765 | Environment: QA
P90: 480ms | Error Rate: 0.2%

📄 Confluence Report: <link>
📁 SharePoint Artifacts: <link>
```

---

## 📁 Project Structure

```
msgraph-mcp/
├── msgraph.py                    # MCP server entrypoint (FastMCP)
├── services/
│   ├── graph_client.py           # Microsoft Graph client utilities
│   ├── teams_notifier.py         # Send messages to Teams channels
│   └── sharepoint_uploader.py    # Upload artifacts to SharePoint
├── utils/
│   └── config.py                 # Utility for loading config.yaml
├── config.yaml                   # Centralized configuration file
├── pyproject.toml                # Python project metadata
├── requirements.txt              # Dependencies (if not using pyproject.toml)
├── README.md                     # This file
└── .env                          # Local environment variables
```

---

## 🚧 Future Enhancements

* **Adaptive notification templates** (Markdown / Adaptive Cards in Teams)
* **Automated cleanup / archival** of older test runs in SharePoint
* **Direct Confluence-to-Teams embedding** for report previews
* **Multi-channel support** (send to multiple Teams channels per environment)
* **Integration with Power Automate or Logic Apps** for custom workflows

---

## 🤝 Contributing

Feel free to open issues or submit pull requests to expand the available tools or enhance functionality.

---

Created with ❤️ using FastMCP, Microsoft Graph, and the MCP Perf Suite Architecture.
