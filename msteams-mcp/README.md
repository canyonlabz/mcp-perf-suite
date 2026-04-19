# MS Teams MCP Server 💬🚀

A Python-based MCP server built with FastMCP 2.0 to automate Microsoft Teams notifications for performance testing workflows. Enables pre-test alerts, post-test result sharing, channel discovery, and team communication — all driven by AI agents.

> **Attribution**: Authentication architecture informed by [m0nkmaster/msteams-mcp](https://github.com/nicholasgriffintn/msteams-mcp) (MIT License, v0.23.1). Reimplemented in Python with improvements for the mcp-perf-suite ecosystem.

## 🎯 Features

- 🔐 **Browser-Based Authentication**: No Azure AD app registration required — authenticates via the Teams web client directly
- 🔄 **Three-Layer Token Resolution**: In-memory cache → encrypted session file → browser login (fast path avoids browser launches)
- 🛡️ **Encrypted Session Storage**: AES-256-GCM encryption with machine-bound scrypt key derivation
- 📡 **SSO Support**: Automatic session reuse across server restarts — login once, reuse silently until tokens expire
- 🧩 **FastMCP 2.0**: Consistent architecture with the rest of the mcp-perf-suite ecosystem

## 🛠️ Prerequisites

- 🐍 **Python 3.12+**
- 🚀 **FastMCP 2.0**
- 🌐 **Microsoft Edge or Google Chrome** installed (used for Playwright browser automation)
- 🏢 **Microsoft Teams Account** (personal, business, or enterprise)
- 📦 **Python Packages**: `fastmcp`, `httpx`, `playwright`, `cryptography`, `python-dotenv`, `pyyaml`

## 🚀 Getting Started

### 1. Clone the Repository
```
git clone https://github.com/canyonlabz/mcp-perf-suite.git
cd mcp-perf-suite/msteams-mcp
```

### 2. Register in Cursor MCP Config

Add this entry to your `~/.cursor/mcp.json` inside the `"mcpServers"` block:

```json
"msteams": {
  "command": "uv",
  "args": [
    "--directory",
    "C:\\Users\\<your-user>\\Repos\\_GitHub\\mcp-perf-suite\\msteams-mcp",
    "run",
    "msteams.py"
  ]
}
```

### 3. Restart Cursor

The `msteams` MCP server will appear in your available tools.

### 4. First-Time Login

Call `teams_login` from any Cursor agent conversation. On first run:
1. A visible Edge/Chrome window opens and navigates to `teams.microsoft.com`
2. You log in manually (SSO, password, MFA — whatever your Tenant requires)
3. The session is captured, encrypted, and saved locally
4. All subsequent calls reuse the cached session — **no browser opens again** until tokens expire

## 🔧 Usage

### 📝 Available MCP Tools

#### Authentication

| 🛠️ Tool Name | 📃 Description |
|--------------|----------------|
| `teams_login` | Authenticate to MS Teams (SSO → headless → visible browser fallback) |
| `teams_status` | Check session health, token validity, and user info (no network calls) |

#### Messaging & Channels

| 🛠️ Tool Name | 📃 Description |
|--------------|----------------|
| `teams_send_message` | Send a message to a channel, chat, or group conversation |
| `teams_list_channels` | List all teams and channels the authenticated user has access to |
| `teams_find_channel` | Search for channels by name (org-wide discovery + membership status) |

#### Search & People

| 🛠️ Tool Name | 📃 Description |
|--------------|----------------|
| `teams_search` | Full-text search across Teams messages with operator support |
| `teams_search_people` | Search for people by name or email (returns job title, department, MRI) |
| `teams_get_me` | Get the current user's profile (display name, email, tenant ID, MRI) |

### Example: Login Flow
```
# First call — opens browser for manual login
teams_login()
# → {"status": "authenticated", "method": "manual", "user": "you@company.com"}

# Subsequent calls — instant, from encrypted cache
teams_login()
# → {"status": "authenticated", "method": "sso", "user": "you@company.com"}

# Force fresh login (wipes and rebuilds session)
teams_login(force=True)
```

### Example: Status Check
```
teams_status()
# → {
#   "hasSession": true,
#   "sessionAgeHours": 2.3,
#   "isSessionExpired": false,
#   "substrateToken": {"hasToken": true, "remainingMinutes": 45.2},
#   "messageAuth": {"hasSkypeToken": true, "hasAuthToken": true, "skypeTokenRemainingMinutes": 110.5},
#   "user": "you@company.com"
# }
```

### Example: Send a Notification
```
# List available channels first
teams_list_channels()
# → [{"displayName": "Performance Engineering", "channels": [{"id": "19:abc@thread.tacv2", ...}]}]

# Send a message to the channel
teams_send_message(conversation_id="19:abc@thread.tacv2", message="Load test starting in 5 minutes")
# → {"status": "sent", "message": "Message delivered successfully"}
```

### Example: Search Messages
```
# Search for recent test notifications
teams_search(query="load test results sent:>=2026-04-01")
# → {"resultCount": 5, "pagination": {"total": 12, "hasMore": true}, "results": [...]}

# Search with operators
teams_search(query="from:homer.simpson@company.com is:Channels hasattachment:true")
```

### Example: Find a Channel
```
# Search when you know part of the name
teams_find_channel(query="performance")
# → {"count": 3, "channels": [
#     {"channelName": "Performance Engineering", "teamName": "QA", "isMember": true},
#     {"channelName": "Performance Results", "teamName": "DevOps", "isMember": false}
# ]}
```

### Example: People Search
```
# Find someone for @mentions
teams_search_people(query="Homer")
# → {"returned": 2, "results": [
#     {"displayName": "Homer Simpson", "email": "homer.simpson@company.com", "jobTitle": "Power Plant Operator", ...}
# ]}

# Get your own profile
teams_get_me()
# → {"displayName": "Your Name", "email": "you@company.com", "mri": "8:orgid:abc-123-..."}
```

## 🔐 Authentication Architecture

### Three-Layer Token Resolution

```
teams_login() called
       │
       ▼
┌──────────────────────────┐
│ Layer 1: In-Memory Cache │  ← Fastest (no I/O)
│ Valid token in memory?   │
└────────┬─────────────────┘
         │ miss
         ▼
┌──────────────────────────┐
│ Layer 2: Encrypted File  │  ← Fast (local file decrypt)
│ session-state.json       │
│ Valid tokens extractable?│
└────────┬─────────────────┘
         │ miss or expired
         ▼
┌──────────────────────────┐
│ Layer 3: Browser Login   │  ← Slow (launches browser)
│ Headless SSO first       │
│ Visible login fallback   │
└──────────────────────────┘
```

### Why Browser-Based Auth?

Traditional approaches require registering an Azure AD app with Graph API permissions, admin consent, client secrets, and OAuth2 flows. This is complex for performance testing teams who just need to post results to a channel.

Instead, we authenticate the same way a human does — through the Teams web client. Playwright captures the resulting session cookies and MSAL tokens, which are then reused for API calls.

### Token Types

| Token | Source | Used For | Typical TTL |
|-------|--------|----------|-------------|
| **Skype Token** | `skypetoken_asm` cookie | Messaging APIs (chatsvc), CSA channel listing | ~24 hours |
| **Auth Token** | `authtoken` cookie | General Teams API auth | ~24 hours |
| **Substrate Token** | MSAL localStorage | Search, People, and Channel discovery APIs | ~1 hour |
| **CSA Token** | `chatsvcagg` localStorage | Teams/channels list API (CSA v3) | ~24 hours |

### Login Detection

After the user logs in, the system detects success by checking for **tokens in localStorage** (primary) and known UI selectors (fallback). Token-based detection is preferred because the Teams UI changes across versions, but localStorage token patterns are stable.

## 🛡️ Security Model

### What Is Stored

| File | Location | Contents |
|------|----------|----------|
| `session-state.json` | `%APPDATA%\teams-mcp-server\` | Encrypted cookies + localStorage from Teams web session |
| `token-cache.json` | `%APPDATA%\teams-mcp-server\` | Encrypted extracted tokens (Substrate, Skype) |
| `browser-profile\` | `%APPDATA%\teams-mcp-server\` | Chromium persistent profile (same as normal Edge usage) |

### Encryption Details

- **Algorithm**: AES-256-GCM (authenticated encryption)
- **Key Derivation**: scrypt (N=16384, r=8, p=1) from `hostname:username`
- **Key Material**: Machine-bound — derived from `socket.gethostname():os.getlogin()`
- **IV**: 16 bytes, randomly generated per encryption
- **Implication**: Encrypted files are **useless on another machine or user account**. If you copy `session-state.json` to another computer, decryption will fail.

### Session Lifecycle

- Sessions expire after **12 hours** (configurable in `config.yaml`)
- Token refresh threshold: **10 minutes** before expiry, tokens are proactively refreshed
- `teams_login(force=True)` wipes all cached state and starts fresh
- On first read, plaintext files are automatically migrated to encrypted format

## 📦 Project Structure

```
msteams-mcp/
├── msteams.py                      # FastMCP server entry point
├── services/
│   ├── auth_manager.py             # Three-layer auth orchestration
│   ├── browser_auth.py             # Teams navigation + login detection
│   ├── browser_context.py          # Playwright persistent browser context
│   ├── token_extractor.py          # JWT decode + token extraction from localStorage
│   ├── session_store.py            # Encrypted session persistence
│   ├── crypto.py                   # AES-256-GCM encryption primitives
│   ├── errors.py                   # ErrorCode enum, McpError, Result monad
│   ├── teams_api.py                # Chatsvc + CSA API client (messaging, channel listing)
│   ├── substrate_api.py            # Substrate API client (search, people, channel discovery)
│   └── parsers.py                  # Pure parsing functions for API responses
├── utils/
│   └── config.py                   # Platform-aware YAML config loader
├── config.yaml                     # Application configuration
├── config.example.yaml             # Configuration template
├── pyproject.toml                  # Python project metadata + dependencies
└── README.md
```

## ⚙️ Configuration

### config.yaml

```yaml
server:
  name: "msteams-mcp"
  version: "0.1.0"

general:
  enable_debug: false       # Set true for verbose logging
  enable_logging: true

teams:
  browser_channel: "chrome"         # Browser for login: "chrome", "msedge", or "chromium"
  session_expiry_hours: 12          # Max session age before re-login
  token_refresh_threshold_sec: 600  # Refresh tokens 10 min before expiry
  http_request_timeout_sec: 30      # HTTP request timeout
  retry_max_attempts: 3             # Max retry attempts
  retry_base_delay_sec: 1           # Initial retry backoff
  retry_max_delay_sec: 10           # Max retry backoff
  default_page_size: 25             # Default search results page size
  max_page_size: 100                # Max search results page size
  default_people_limit: 10          # Default people search results
  default_channel_limit: 10         # Default channel search results
```

### OS-Specific Overrides

Create `config.windows.yaml` or `config.mac.yaml` for platform-specific settings. Platform-specific files take priority over `config.yaml`.

## 🗺️ Roadmap

### Phase 1 — Authentication ✅
- `teams_login` — Browser-based auth with three-layer token resolution
- `teams_status` — Diagnostic session health check

### Phase 2 — Channel Discovery & Messaging ✅
- `teams_list_channels` — List all joined teams and channels
- `teams_send_message` — Send messages/notifications to channels and chats
- `teams_find_channel` — Search for channels by name (org-wide + membership)

### Phase 3 — Search & People ✅
- `teams_search` — Full-text message search with operator support
- `teams_search_people` — People search by name or email
- `teams_get_me` — Current user profile extraction

### Phase 4 — Performance Testing Integration (Planned)
- Pre-test notification templates
- Post-test result summaries with links to reports
- Adaptive Card formatting for rich messages
- `teams_logout` tool for explicit session cleanup

## 🐛 Troubleshooting

### Server Won't Start
- Ensure `mcp.json` entry points to the correct `msteams-mcp` directory
- Verify Python 3.12+ is available: `python --version`
- Check `uv` is installed: `uv --version`

### Browser Doesn't Open
- Ensure Microsoft Edge or Google Chrome is installed
- Check for stale browser profile locks: delete `%APPDATA%\teams-mcp-server\browser-profile\SingletonLock` if it exists

### Login Detected But Tokens Missing
- Some Tenant configurations may not populate all token types (e.g., personal accounts may lack Substrate search tokens)
- Call `teams_status` to see which tokens are available
- Core messaging uses Skype tokens (from cookies), not Substrate tokens

### Search/People Tools Return AUTH_EXPIRED
- Substrate tokens have a short TTL (~1 hour). The server proactively refreshes via headless browser when within 10 minutes of expiry.
- If refresh fails, call `teams_login()` to re-authenticate
- Check `teams_status()` → `substrateToken.remainingMinutes` to see current token health

### Session Expired
- Call `teams_login(force=True)` to force a fresh browser login
- Check `teams_status` for `sessionAgeHours` — sessions expire after 12 hours by default

## 📄 License

This project is part of the MCP Performance Suite. See repository root for license information.

Authentication architecture informed by [m0nkmaster/msteams-mcp](https://github.com/nicholasgriffintn/msteams-mcp) (MIT License).

---

**Built with ❤️ using FastMCP 2.0**
