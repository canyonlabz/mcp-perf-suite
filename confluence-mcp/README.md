# Confluence MCP Server 🗂️🚀

A Python-based MCP server built with FastMCP 2.0 to publish performance test reports and artifacts to Confluence Cloud (REST v2) or Server/Data Center (REST v1). Converts Markdown reports from PerfReport MCP to Confluence storage-format XHTML for reliable sharing.

## 🎯 Features

- 🔄 Publish test results and analysis from the PerfSuite pipeline directly into Confluence pages.
- 🌐 Support for both Confluence Cloud (v2 API) and on-prem (v1 API) via dual-mode routing.
- 📝 Automatic Markdown-to-XHTML conversion compliant with Confluence storage format (layout macros, tables, attachments).
- 📚 List, search, create, and update pages in any accessible Confluence space.
- 📎 Attach test artifacts (charts, CSVs) to Confluence pages.
- 🔒 Flexible authentication and pagination for both API versions.
- 🧩 Extensible utility modules for configuration and pagination handling.

## 🛠️ Prerequisites

- 🐍 Python 3.12+
- 🚀 FastMCP 2.0
- 🔑 Confluence API credentials set in `.env`
- 📂 PerfReport MCP output artifacts in `repo_root/artifacts/<test_run_id>/reports/`
- 📦 Required Python packages: fastmcp, httpx, python-dotenv, markdown2, beautifulsoup4, lxml

## 🚀 Getting Started

1. **Clone the Repository**
   ```bash
   git clone https://github.com/canyonlabz/mcp-perf-suite.git
   cd confluence-mcp
   ```

2. **Create and Activate Python Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # macOS/Linux
   # Or for Windows
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**

   Create a `.env` file with your Confluence credentials:

   ```
   # For Cloud v2
   CONFLUENCE_V2_BASEURL=https://mycompany.atlassian.net/wiki
   CONFLUENCE_V2_USER=your.email@company.com
   CONFLUENCE_V2_API_TOKEN=your_cloud_api_token

   # For On-Prem v1
   CONFLUENCE_V1_BASEURL=https://onprem-host
   CONFLUENCE_V1_PAT=your_on_prem_pat
   CONFLUENCE_V1_USER=your_username
   ```

4. **Run the MCP Server**
   ```bash
   python confluence.py        # Default stdio for use with Cursor AI Desktop
   uv run confluence.py        # Alternative with uv
   ```

## 🔧 Usage

### 📝 MCP Tools Overview

| 🛠️ Tool Name           | 📃 Description                                           |
|------------------------|-----------------------------------------------------------|
| 🗂️ set_confluence_mode | Set API mode ("cloud" or "onprem") for routing            |
| 📚 list_spaces         | List available Confluence spaces                          |
| 📄 list_pages          | List pages in a specific space                            |
| 🔍 search_pages        | Search pages via CQL query                                |
| 🖊️ get_page_content    | Retrieve full Confluence page body (storage-format XHTML) |
| 🆕 create_page         | Create Confluence page with performance report            |
| 📝 update_page         | Update existing page, incrementing version                |
| 📎 attach_file         | Attach test artifact to page                              |
| 🔄 convert_markdown_to_confluence | Convert Markdown to Confluence storage-format  |

### 📈 Typical Publishing Workflow

1. 📝 Generate Performance Report using PerfReport MCP.
2. 🔄 Convert Markdown to Confluence XHTML, automatically handled by Confluence MCP.
3. 🆕 Publish the report to a new Confluence page under your preferred space.
4. 📎 Attach charts or CSVs for richer report content.

### 📦 Project Structure

```
confluence-mcp/
├── confluence.py
├── services/
│   ├── confluence_v2_api.py
│   ├── confluence_v1_api.py
│   └── content_parser.py
├── utils/
│   ├── config.py
│   └── pagination.py
├── .env
├── config.yaml
├── README.md
├── requirements.txt
└── tests/
```

## ⚙️ Configuration

- See `config.yaml` for default space IDs, parent page templates, and layout settings.
- Attachments can be versioned or overwritten (configurable).

## 🚧 Future Enhancements

- 📑 Bulk markdown publishing
- 🔄 Diff/replace updated sections only
- 🖼️ Native markdown images/macros
- 🚥 Labeling and comment support
- 🔍 Advanced search filters and auto-categorization

## 🤝 Contributing

Feel free to open issues or submit pull requests to enhance the Confluence MCP Server.
