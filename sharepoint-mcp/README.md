# 📂🏢 SharePoint MCP Server

A Python-based MCP server built with FastMCP 2.0 to upload performance test artifacts to SharePoint. Enables performance test engineers to persist test results, reports, and analysis files to SharePoint document libraries — all driven by AI agents.

> **Architecture Note**: Authentication architecture adapted from the [msteams-mcp](../msteams-mcp/) server in this suite, using the same browser-based token capture pattern for environments without Azure AD app registration access.

## ✨ Features

- 🔐 **Browser-Based Authentication**: No Azure AD app registration required — authenticates via the SharePoint web client directly
- 🔄 **Three-Layer Token Resolution**: In-memory cache, encrypted session file, browser login (fast path avoids browser launches)
- 🛡️ **Encrypted Session Storage**: AES-256-GCM encryption with machine-bound scrypt key derivation
- 📡 **SSO Support**: Automatic session reuse across server restarts — login once, reuse silently until tokens expire
- 🏢 **Tenant Auto-Detection**: Extracts tenant name from browser URL after login (no manual configuration needed)
- 📤 **Single File Upload**: Upload individual artifacts to a specified SharePoint location
- 📦 **Folder Upload**: Upload an entire artifact folder (recursive) in one operation
- 📁 **Folder Management**: Create folders and list document library contents
- 💬 **Optional Teams Notification**: Notify your team via MS Teams MCP after upload completes (config-driven)
- 🧩 **FastMCP 2.0**: Consistent architecture with the rest of the mcp-perf-suite ecosystem

## 🛠️ Prerequisites

- 🐍 **Python 3.12+**
- 🚀 **FastMCP 2.0**
- 🌐 **Microsoft Edge or Google Chrome** installed (used for Playwright browser automation)
- 🏢 **SharePoint Online Account** (business or enterprise)
- 📦 **Python Packages**: `fastmcp`, `httpx`, `playwright`, `cryptography`, `python-dotenv`, `pyyaml`

## 🚀 Getting Started

### 1. Clone the Repository
```
git clone https://github.com/canyonlabz/mcp-perf-suite.git
cd mcp-perf-suite/sharepoint-mcp
```

### 2. Register in Cursor MCP Config

Add this entry to your `~/.cursor/mcp.json` inside the `"mcpServers"` block:

```json
"sharepoint": {
  "command": "uv",
  "args": [
    "--directory",
    "C:\\Users\\<your-user>\\Repos\\_GitHub\\mcp-perf-suite\\sharepoint-mcp",
    "run",
    "sharepoint.py"
  ]
}
```

### 3. Restart Cursor

The `sharepoint` MCP server will appear in your available tools.

### 4. First-Time Login

Call `sharepoint_login` from any Cursor agent conversation. On first run:
1. A visible Edge/Chrome window opens and navigates to your SharePoint site
2. You log in manually (SSO, password, MFA — whatever your tenant requires)
3. The session and Bearer token are captured, encrypted, and saved locally
4. All subsequent calls reuse the cached session — **no browser opens again** until tokens expire

## 🔧 Available MCP Tools

### Authentication

| 🛠️ Tool Name | 📃 Description |
|-----------|-------------|
| `sharepoint_login` | Authenticate to SharePoint (SSO, headless, visible browser fallback) |
| `sharepoint_status` | Check session health, token validity, tenant info (no network calls) |

### File Operations

| 🛠️ Tool Name | 📃 Description |
|-----------|-------------|
| `sharepoint_upload_file` | Upload a single file to a specified SharePoint folder |
| `sharepoint_upload_folder` | Upload an entire local folder (recursive) to a SharePoint folder |

### Folder Operations

| 🛠️ Tool Name | 📃 Description |
|-----------|-------------|
| `sharepoint_create_folder` | Create a folder in a SharePoint document library |
| `sharepoint_list_folder` | List contents of a SharePoint folder (files and subfolders) |

### 📤 Upload Design

The upload interface is deliberately simple — two modes only:

- 📄 **Single file**: Specify one local file path and a SharePoint destination
- 📦 **Full folder**: Specify a local folder path and a SharePoint destination — everything inside gets uploaded

Both modes **require** `site_url` and `destination_folder`. There is no default upload location — the user must always specify where artifacts go.

## 🔐 Authentication Architecture

### Three-Layer Token Resolution

```
sharepoint_login() called
       |
       v
+----------------------------+
| Layer 1: In-Memory Cache   |  <-- Fastest (no I/O)
| Valid Bearer token?        |
+----------+-----------------+
           | miss
           v
+----------------------------+
| Layer 2: Encrypted File    |  <-- Fast (local file decrypt)
| session-state.json         |
| Valid token extractable?   |
+----------+-----------------+
           | miss or expired
           v
+----------------------------+
| Layer 3: Browser Login     |  <-- Slow (launches browser)
| Headless SSO first         |
| Visible login fallback     |
+----------------------------+
```

### Token Types

| Token | Source | Used For | Typical TTL |
|-------|--------|----------|-------------|
| **SharePoint Bearer** | Network request intercept | All `_api/` REST calls | ~1 hour |
| **FedAuth Cookie** | Browser cookies | Session continuity | Session-based |
| **rtFa Cookie** | Browser cookies | Root federation auth | Session-based |
| **Form Digest** | `_api/contextinfo` | Write operations (CSRF) | ~30 minutes |

### Why Browser-Based Auth?

Traditional approaches require registering an Azure AD app with Graph API permissions, admin consent, client secrets, and OAuth2 flows. This is often inaccessible for performance testing teams.

Instead, we authenticate the same way a human does — through the SharePoint web client. Playwright captures the resulting Bearer token from network requests, which is then reused for `_api/` REST calls. No app registration, no client secrets, no admin consent needed.

## 🛡️ Security Model

### What Is Stored

| File | Location | Contents |
|------|----------|----------|
| `session-state.json` | `%APPDATA%\sharepoint-mcp-server\` | Encrypted cookies + localStorage from SharePoint session |
| `token-cache.json` | `%APPDATA%\sharepoint-mcp-server\` | Encrypted Bearer token + expiry |
| `browser-profile\` | `%APPDATA%\sharepoint-mcp-server\` | Chromium persistent profile |

### Encryption Details

- **Algorithm**: AES-256-GCM (authenticated encryption)
- **Key Derivation**: scrypt (N=16384, r=8, p=1) from `hostname:username`
- **Key Material**: Machine-bound — derived from `socket.gethostname():os.getlogin()`
- **IV**: 16 bytes, randomly generated per encryption
- **Implication**: Encrypted files are useless on another machine or user account

## ⚙️ Configuration

### config.yaml

```yaml
server:
  name: "sharepoint-mcp"
  version: "0.1.0"

general:
  enable_debug: false
  enable_logging: true

sharepoint:
  tenant: ""                    # Auto-detected from browser URL; set manually only if needed
  browser_channel: "chrome"     # "chrome", "msedge", or "chromium"
  session_expiry_hours: 12
  token_refresh_threshold_sec: 600
  http_request_timeout_sec: 60
  retry_max_attempts: 3
  retry_base_delay_sec: 1
  retry_max_delay_sec: 10
  max_upload_size_mb: 250       # Chunked upload threshold
  chunk_size_mb: 10             # Chunk size for large files

  # Optional Teams notification after upload
  notification_on_upload:
    enabled: false
    target: ""                  # Named target from msteams-mcp config
    template: ""                # Falls back to "default-notification-sharepoint-upload.md"
```

### OS-Specific Overrides

Create `config.windows.yaml` or `config.mac.yaml` for platform-specific settings. Platform-specific files take priority over `config.yaml`.

## 📦 Project Structure

```
sharepoint-mcp/
├── sharepoint.py                  # FastMCP server entry point
├── services/
│   ├── auth_manager.py            # Three-layer auth orchestration
│   ├── browser_auth.py            # SharePoint navigation + token intercept
│   ├── browser_context.py         # Playwright persistent browser context
│   ├── token_extractor.py         # Bearer JWT extraction + user profile
│   ├── session_store.py           # Encrypted session persistence
│   ├── crypto.py                  # AES-256-GCM encryption primitives
│   ├── errors.py                  # ErrorCode enum, McpError, Result type
│   └── sharepoint_api.py          # SharePoint _api REST client
├── utils/
│   └── config.py                  # Platform-aware YAML config loader
├── config.yaml                    # Application configuration
├── config.example.yaml            # Configuration template
├── pyproject.toml                 # Python project metadata + dependencies
└── README.md
```

## 🧠 High-Level Workflow

```text
AI Agent
    ↓
SharePoint MCP
    ↓
Browser Authentication
    ↓
SharePoint REST API
    ↓
Upload Artifacts / Reports / Logs
    ↓
(Optional) MS Teams Notification
```

## 🐛 Troubleshooting

### Server Won't Start
- Ensure `mcp.json` entry points to the correct `sharepoint-mcp` directory
- Verify Python 3.12+ is available: `python --version`
- Check `uv` is installed: `uv --version`

### Browser Doesn't Open
- Ensure Microsoft Edge or Google Chrome is installed
- Check for stale browser profile locks: delete `%APPDATA%\sharepoint-mcp-server\browser-profile\SingletonLock` if it exists

### Tenant Not Detected
- If auto-detection fails, set `sharepoint.tenant` in your `config.yaml`
- The tenant is the subdomain in your SharePoint URL: `https://<tenant>.sharepoint.com`

### Upload Fails with 401
- Your Bearer token has likely expired (~1 hour lifetime)
- Call `sharepoint_login()` to refresh authentication, then retry
- Check `sharepoint_status()` for token health

### Session Expired
- Call `sharepoint_login(force=True)` to force a fresh browser login
- Sessions expire after 12 hours by default (configurable)
- Quick fix: delete `%APPDATA%\sharepoint-mcp-server\*`, restart Cursor, then call `sharepoint_login()`

## License

This project is part of the MCP Performance Suite. See repository root for license information.

Authentication architecture adapted from [msteams-mcp](../msteams-mcp/) (browser-based token capture pattern).

---

**Built with ❤️ using FastMCP 2.0**
