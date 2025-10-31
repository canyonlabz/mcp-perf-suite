# Confluence MCP Server 🗂️🚀

A Python-based MCP server built with FastMCP 2.0 to publish performance test reports and artifacts to Confluence Cloud (v2 REST API) or Server/Data Center (v1 REST API). Converts Markdown reports to Confluence storage-format XHTML and provides comprehensive Confluence management capabilities.

## 🎯 Features

- 🔄 **Dual-Mode Support**: Works with both Confluence Cloud (v2 API) and On-Prem/Data Center (v1 API)
- 📝 **Markdown Conversion**: Automatic Markdown-to-XHTML conversion compliant with Confluence storage format
- 📚 **Complete Page Management**: List, search, create, read, and update Confluence pages
- 🔍 **CQL Search**: Powerful search using Confluence Query Language (CQL) for both Cloud and On-Prem
- 📊 **Artifact Management**: List and manage performance test reports and charts from local artifacts
- 🔒 **Flexible Authentication**: Support for API tokens (Cloud), PAT (On-Prem), and corporate SSL certificates
- 🧩 **Modular Architecture**: Clean separation of API versions, services, and utilities
- 🛡️ **Error Handling**: Comprehensive error reporting and context logging via FastMCP

## 🛠️ Prerequisites

- 🐍 **Python 3.12+**
- 🚀 **FastMCP 2.0**
- 🔑 **Confluence API Credentials** (API token for Cloud, PAT for On-Prem)
- 📂 **Artifacts Directory**: Performance reports in `artifacts/<test_run_id>/reports/`
- 📦 **Python Packages**: `fastmcp`, `httpx`, `python-dotenv`, `pyyaml`

## 🚀 Getting Started

### 1. Clone the Repository
```
git clone https://github.com/canyonlabz/mcp-perf-suite.git
cd mcp-perf-suite/confluence-mcp
```

### 2. Create and Activate Python Virtual Environment
```
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# Or for Windows
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the `confluence-mcp` directory:

```
# Confluence Cloud (v2 API)
CONFLUENCE_V2_BASE_URL=https://your-domain.atlassian.net
CONFLUENCE_V2_USER=your.email@company.com
CONFLUENCE_V2_API_TOKEN=your_api_token_here

# Confluence On-Prem (v1 API)
CONFLUENCE_V1_BASE_URL=https://confluence.your-company.com
CONFLUENCE_V1_PAT=your_personal_access_token
CONFLUENCE_V1_USER=your_username

# SSL Certificate Configuration (for corporate environments)
SSL_CERT_FILE=/path/to/ca-bundle.pem
REQUESTS_CA_BUNDLE=/path/to/ca-bundle.pem
```

### 4. Configure SSL Verification (Optional)

Edit `config.yaml` to control SSL verification behavior:

```
confluence:
  # SSL verification options: "ca_bundle", "disabled", or "system"
  ssl_verification: "ca_bundle"  # Uses certs from env vars
  # ssl_verification: "disabled"  # Skip verification (dev/testing only)
```

### 5. Run the MCP Server
```
python confluence.py        # Default stdio mode for Cursor AI
uv run confluence.py        # Alternative with uv
```

## 🔧 Usage

### 📝 Available MCP Tools

| 🛠️ Tool Name | 📃 Description | Cloud | On-Prem |
|--------------|----------------|-------|---------|
| `list_spaces` | List all accessible Confluence spaces | ✅ | ✅ |
| `get_space_details` | Get detailed metadata for a specific space | ✅ | ✅ |
| `list_pages` | List all pages within a space | ✅ | ✅ |
| `get_page_by_id` | Get metadata for a specific page | ✅ | ✅ |
| `get_page_content` | Retrieve full page content (storage XHTML) | ✅ | ✅ |
| `search_pages` | Search pages using CQL queries | ✅ | ✅ |
| `create_page` | Create new page from Markdown report | ✅ | ✅ |
| `list_available_reports` | List local performance reports | ✅ | ✅ |
| `list_available_charts` | List local performance charts | ✅ | ✅ |
| `convert_markdown_to_xhtml` | Convert Markdown to Confluence XHTML | ✅ | ✅ |

**Coming Soon:**
- `update_page` - Update existing page content
- `attach_file` - Attach charts/artifacts to pages

### 📈 Typical Workflow

#### 1. List Available Reports
```
# List single-run reports for a specific test
reports = await list_available_reports(test_run_id="80014829")

# List comparison reports
comparison_reports = await list_available_reports()
```

#### 2. Search for Target Space
```
# Search for spaces containing "QA"
spaces = await search_pages(query="QA", mode="cloud")
```

#### 3. Create Page from Report
```
# Create page in specific space
result = await create_page(
    space_ref="7537021",  # Space ID (cloud) or key (on-prem)
    filename="/path/to/performance_report_80014829.md",
    mode="cloud"
)
```

#### 4. Search for Published Reports
```
# Find all performance test reports
results = await search_pages(
    query="performance test",
    mode="cloud",
    space_ref="XYZ"
)
```

### 📦 Project Structure

```
confluence-mcp/
├── confluence.py                    # Main MCP server entry point
├── services/
│   ├── confluence_api_v1.py        # On-Prem API functions (v1)
│   ├── confluence_api_v2.py        # Cloud API functions (v2)
│   ├── artifact_manager.py         # Local artifact management
│   └── content_parser.py           # Markdown-to-XHTML conversion
├── utils/
│   └── config.py                   # Configuration loader
├── .env                            # Environment variables (not in git)
├── config.yaml                     # Application configuration
├── config.windows.yaml             # Windows-specific overrides
├── config.mac.yaml                 # macOS-specific overrides
├── README.md
├── requirements.txt
└── tests/                          # Test files (future)
```

### 🔍 CQL Search Examples

Both Cloud and On-Prem support powerful CQL queries:

```
# Search by title
search_pages(query="performance test", mode="cloud")

# Search in specific space
search_pages(query="QA Testing", mode="onprem", space_ref="MYQA")

# The tool automatically builds CQL:
# type=page AND (title~"query" OR text~"query") AND space=KEY
```

**Supported CQL Operators:**
- `~` (contains/fuzzy match)
- `=` (exact match)
- `AND`, `OR`, `NOT`
- `>`, `<`, `>=`, `<=` (dates/numbers)

## ⚙️ Configuration

### config.yaml

```
artifacts:
  artifacts_path: "./artifacts"  # Base path for reports and charts

confluence:
  ssl_verification: "ca_bundle"  # Options: ca_bundle, disabled, system
```

### OS-Specific Overrides

Create `config.windows.yaml` or `config.mac.yaml` for platform-specific paths:

```
artifacts:
  artifacts_path: "C:\\Users\\YourName\\mcp-perf-suite\\artifacts"  # Windows
  # artifacts_path: "/Users/yourname/mcp-perf-suite/artifacts"      # macOS
```

## 🔐 Authentication

### Cloud (v2 API)
- Uses **Basic Auth** with base64-encoded `username:api_token`
- API token generated from Atlassian account settings
- User email required

### On-Prem (v1 API)
- Uses **Bearer token** with Personal Access Token (PAT)
- PAT generated from Confluence profile settings
- Optional username field

### SSL Certificates
For corporate environments with custom CA certificates:
1. Set `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` in `.env`
2. Configure `ssl_verification` in `config.yaml`

## 🚧 Future Enhancements

- 🔄 Update page content (preserve version history)
- 📎 Attach files to pages
- 📑 Bulk page operations
- 🖼️ Enhanced image/macro handling
- 🏷️ Label and comment management
- 📊 Advanced reporting templates

## 🐛 Troubleshooting

### SSL Certificate Issues
```
# Option 1: Use CA bundle
export SSL_CERT_FILE=/path/to/ca-bundle.pem
export REQUESTS_CA_BUNDLE=/path/to/ca-bundle.pem

# Option 2: Disable verification (not recommended for production)
# Set in config.yaml:
# ssl_verification: "disabled"
```

### Authentication Errors
- **Cloud**: Verify API token is valid and user email is correct
- **On-Prem**: Ensure PAT has appropriate permissions
- Check base URLs don't have trailing slashes

### Page Creation Failures
- Verify space exists and you have create permissions
- Check Markdown file exists and is readable
- Ensure title doesn't conflict with existing pages

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## 📄 License

This project is part of the MCP Performance Suite. See repository root for license information.

## 🔗 Related Projects

- **MCP Performance Suite**: Parent project containing BlazeMeter, Datadog, Performance Analysis, and Performance Reporting MCPs
- **FastMCP**: Framework powering this MCP server

---

**Built with ❤️ using FastMCP 2.0**
