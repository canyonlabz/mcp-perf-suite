# 🧠📚 PerfMemory MCP Server

Welcome to the PerfMemory MCP Server! 🚀  
This is a Python-based MCP server built with **FastMCP 2.0** that introduces a persistent "memory layer" for performance testing — enabling AI agents like Claude/Cursor to learn from past debugging sessions and apply those lessons to future JMeter script creation and troubleshooting.

Powered by a **PostgreSQL + pgvector database with HNSW indexing**, PerfMemory MCP stores structured debug sessions, failed attempts, and successful resolutions, allowing agents to query semantically similar issues before taking action. By leveraging embeddings and vector search, it transforms historical "lessons learned" into actionable intelligence — reducing trial-and-error and accelerating script fixes.

---

## ✨ Features

* **🔍 Semantic Similarity Search**: Find past debug attempts that match a current symptom using vector cosine similarity — no exact keyword match needed.
* **📝 Debug Session Tracking**: Record the full story of a debug workflow — from the first error through every attempt to the final resolution.
* **🧩 Structured Lessons Learned**: Each attempt captures the symptom, diagnosis, fix, error category, severity, and outcome — not just freeform text.
* **✅ Confidence Signals**: Track which fixes have been human-verified (`is_verified`) and how many times a fix has been reused successfully (`confirmed_count`).
* **📦 Archive & Lifecycle**: Mark outdated lessons as inactive so they stop appearing in search results, while keeping them for audit trail.
* **🔀 Flexible Embedding Providers**: Choose between OpenAI, Azure OpenAI, or Ollama for generating vector embeddings — local or cloud.
* **☁️ Cloud-Ready**: SSL/TLS support for Azure, AWS, and GCP hosted PostgreSQL. TCP keepalives and connection health checks for production reliability.

---

## 🏁 Prerequisites

* Python 3.12 or higher
* **PostgreSQL 18+** with the **pgvector** extension enabled
* An embedding provider configured (one of the following):
  * **OpenAI** — requires an API key
  * **Azure OpenAI** — requires API key, endpoint, and deployment name
  * **Ollama** — requires a running Ollama instance with an embedding model pulled (e.g., `nomic-embed-text`)
* **Cursor IDE** (or compatible MCP host)

For database setup instructions, see the [pgvector Installation Guide](../docs/pgvector_installation_guide.md).

For example prompts, workflows, and tips, see the [PerfMemory User Guide](../docs/perfmemory_user_guide.md).

---

## 🚀 Getting Started

### 1. Set Up the Database

Follow the [pgvector Installation Guide](../docs/pgvector_installation_guide.md) to:
- Start a PostgreSQL + pgvector container via Docker Compose
- Connect with `psql` and enable the vector extension

### 2. Apply the Schema

Run the appropriate schema script against your database:

```bash
# For OpenAI or Azure OpenAI embeddings (1536 dimensions)
psql -h localhost -U perfadmin -d perfmemory -f sql/schema/schema_openai.sql

# For Ollama nomic-embed-text embeddings (768 dimensions)
psql -h localhost -U perfadmin -d perfmemory -f sql/schema/schema_ollama.sql
```

This creates the `debug_sessions` and `debug_attempts` tables, the HNSW vector index, and all B-tree indexes for metadata filtering.

### 3. Configure Environment

Copy the example `.env` file and fill in your credentials:

```bash
cp .env.example .env
```

At minimum, configure:
- **Embedding provider** — set `EMBEDDING_PROVIDER` and the corresponding API key/endpoint
- **Database connection** — set `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- **SSL** (cloud only) — set `POSTGRES_SSLMODE` and optionally `POSTGRES_SSLROOTCERT`

### 4. Set Up Python Environment

#### Option A: Using `uv` (Recommended)

```bash
uv run perfmemory.py
```

#### Option B: Using Virtual Environment

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e .
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

---

## ⚙️ MCP Server Configuration (`mcp.json`)

Example setup for Cursor or compatible MCP hosts:

```json
{
  "mcpServers": {
    "perfmemory": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/your/perfmemory-mcp",
        "run",
        "perfmemory.py"
      ]
    }
  }
}
```

---

## 🛠️ Tools

The PerfMemory MCP server exposes 9 tools organized into three groups:

### Core Tools

| Tool | Description |
| :--- | :---------- |
| `store_debug_session` | Create a new debug session to track a debugging workflow. Returns a `session_id` for linking attempts. |
| `store_debug_attempt` | Embed a symptom and store a debug attempt linked to a session. Records the symptom, diagnosis, fix, and outcome. If `matched_attempt_id` is provided, increments the matched attempt's `confirmed_count`. |
| `find_similar_attempts` | Search the memory store for past attempts that match a symptom. Returns matches ranked by cosine similarity with a recommendation (`apply_known_fix`, `review_suggestions`, or `no_match`). |

### Session Management Tools

| Tool | Description |
| :--- | :---------- |
| `close_debug_session` | Finalize a session with its outcome (`resolved`, `unresolved`, etc.) and optionally link the resolving attempt. |
| `list_sessions` | Browse stored debug sessions with optional filters (system, environment, outcome). |
| `get_session_detail` | Retrieve a full session with all its attempts ordered by iteration number. |

### Maintenance Tools

| Tool | Description |
| :--- | :---------- |
| `archive_attempt` | Mark an attempt as inactive — excludes it from future searches while preserving it for audit. |
| `verify_attempt` | Mark an attempt as human-verified — signals high confidence in the lesson. |
| `get_memory_stats` | Get overview statistics: total sessions, attempts, breakdowns by system and outcome, verified and active counts. |

---

## 🔁 Typical Workflow

### During JMeter Script Debugging

```
1. Encounter an error in a JMeter script
         │
         ▼
2. Call find_similar_attempts with the symptom
         │
    ┌────┴────┐
    │ Match?  │
    └────┬────┘
    Yes  │  No
    │    │
    ▼    ▼
3a. Apply   3b. Start a new
known fix   debug session
    │            │
    ▼            ▼
4a. Store    4b. Debug iteratively,
attempt      storing each attempt
(with           │
matched_id)     ▼
             4c. Close session
                 with outcome
```

### Step by Step

1. **Check memory first** — Before starting a debug loop, call `find_similar_attempts` with the current error symptom.
2. **If a match is found** — Review the diagnosis and fix from the matched attempt. Apply it and store the new attempt with `matched_attempt_id` to increment the original's confidence.
3. **If no match** — Call `store_debug_session` to start tracking. After each debug iteration, call `store_debug_attempt` to record the symptom, what was tried, and the outcome.
4. **Close the session** — When debugging is complete, call `close_debug_session` with the final outcome and the ID of the resolving attempt.

---

## 📁 Project Structure

```
perfmemory-mcp/
├── perfmemory.py              # MCP server entrypoint (FastMCP)
├── services/
│   ├── embeddings.py          # Embedding provider abstraction (OpenAI, Azure, Ollama)
│   └── session_manager.py     # Connection pool, CRUD operations, vector search
├── utils/
│   └── config.py              # Environment variable loader (.env or system env)
├── sql/
│   └── schema/
│       ├── schema_openai.sql  # Tables + indexes for 1536-dim embeddings
│       └── schema_ollama.sql  # Tables + indexes for 768-dim embeddings
├── .env.example               # Example environment configuration
├── pyproject.toml             # Project metadata and dependencies
└── README.md                  # This file
```

---

## 🗄️ Database Schema

PerfMemory uses two tables with a parent-child relationship:

### `debug_sessions` — The debugging story

Tracks the overall debugging workflow for a JMeter script issue.

| Column | Purpose |
| :----- | :------ |
| `system_under_test` | What is being tested (portal, API, workflow) |
| `test_run_id` | Links to the artifact structure |
| `script_name` | The JMX file being debugged |
| `auth_flow_type` | Authentication flow (none, oauth_pkce, saml, etc.) |
| `environment` | Test environment (dev, qa, uat, staging, prod) |
| `final_outcome` | How the session ended (resolved, unresolved, etc.) |
| `resolution_attempt_id` | FK to the attempt that fixed the issue |

### `debug_attempts` — Individual iterations

Each row is one debug iteration within a session.

| Column | Purpose |
| :----- | :------ |
| `symptom_text` | Structured error description (embedded as vector) |
| `diagnosis` | Root cause determination |
| `fix_description` | What fix was applied |
| `fix_type` | Categorized fix (add_extractor, edit_header, etc.) |
| `outcome` | Result of this attempt (resolved, failed, etc.) |
| `embedding` | Vector embedding for similarity search |
| `is_verified` | Human-reviewed and confirmed |
| `is_active` | Included in search results (FALSE = archived) |
| `confirmed_count` | Number of times this fix was successfully reused |

### Indexing

| Index | Type | Purpose |
| :---- | :--- | :------ |
| `idx_attempts_embedding` | HNSW (cosine) | Fast approximate nearest-neighbor vector search |
| `idx_attempts_error_category` | B-tree | Filter by error category |
| `idx_attempts_outcome` | B-tree | Filter by attempt outcome |
| `idx_attempts_session_id` | B-tree | Join attempts to sessions |
| `idx_attempts_hostname` | B-tree | Filter by hostname |
| `idx_sessions_system` | B-tree | Filter by system under test |
| `idx_sessions_environment` | B-tree | Filter by environment |
| `idx_sessions_outcome` | B-tree | Filter by session outcome |

---

## 🔧 Configuration Reference

All configuration is managed through environment variables (via `.env` file locally or platform-injected in cloud).

### Embedding Provider

| Variable | Default | Description |
| :------- | :------ | :---------- |
| `EMBEDDING_PROVIDER` | `openai` | Provider to use: `openai`, `azure_openai`, or `ollama` |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `AZURE_OPENAI_API_KEY` | — | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | — | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | `text-embedding-3-small` | Azure deployment name |
| `AZURE_OPENAI_API_VERSION` | `2024-02-15-preview` | Azure API version |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama instance URL |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Ollama embedding model |

### Database

| Variable | Default | Description |
| :------- | :------ | :---------- |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `perfmemory` | Database name |
| `POSTGRES_USER` | `perfadmin` | Database user |
| `POSTGRES_PASSWORD` | — | Database password |
| `POSTGRES_SSLMODE` | `prefer` | SSL mode (`disable`, `prefer`, `require`, `verify-full`) |
| `POSTGRES_SSLROOTCERT` | — | Path to CA certificate (for `verify-ca` / `verify-full`) |

### Search

| Variable | Default | Description |
| :------- | :------ | :---------- |
| `VECTOR_TOP_K` | `5` | Max results from similarity search |
| `SIMILARITY_THRESHOLD` | `0.75` | Minimum cosine similarity score to return a match |

### General

| Variable | Default | Description |
| :------- | :------ | :---------- |
| `DEBUG` | `false` | Enable debug logging |

---

## 🚧 Future Enhancements

* **Skill Integration** — Wire `find_similar_attempts` into the `jmeter-debugging` and `jmeter-hitl-editing` skills so agents check memory automatically.
* **Structured Symptom Templates** — Standardize how symptoms are formatted before embedding to improve similarity scores.
* **Correlation Patterns Table** — Store common correlation patterns (separate from debug attempts) for reuse across scripts.
* **Data Retention Policies** — Auto-archive old attempts and configurable TTL.
* **Backup & Migration** — Database dump/restore tooling for moving data between environments.
* **Multi-Tenancy** — Team-level data isolation for shared deployments.

---

## 🤝 Contributing

Feel free to open issues or submit pull requests to enhance functionality, add new tools, or improve documentation!

---

Created with ❤️ using FastMCP, PostgreSQL, pgvector, and the MCP Perf Suite architecture.
