# AGENTS.md - agent-framework

Development context for Cursor / Claude IDE working inside `agent-framework/`.
This file is read by AI coding assistants on session start; humans should treat
it as the table of contents for the agent layer.

## What lives here

`agent-framework/` is the AG2-based agent layer for the MCP Perf Suite. It runs
in its own Docker container (`perf-agents`) alongside `perf-gateway`,
`perfmemory-db`, and the external Microsoft `playwright-mcp` container.
Architecture and design rationale:
[../docs/plans/AG2-Framework-and-Architecture-V2.md](../docs/plans/AG2-Framework-and-Architecture-V2.md).

The folder name on disk is `agent-framework/` (with hyphen) for engineering
clarity. The user-facing brand is "PerfPilot Agents". Do not rename either.

## Folder map

| Path | Purpose | Filled by |
|---|---|---|
| `agents/` | One subfolder per agent, four-file pattern (`agent.py`, `agent_card.json`, `INSTRUCTIONS.md`, `config.yaml`) | F3.7 (orchestrator), F3.8 (execution-agent vertical slice), F3.9 (stubs), F3.10 (promotions) |
| `frontend/agui_adapter.py` | FastAPI ASGI app for the AG-UI / CopilotKit bridge (port 8002) | F3.6 |
| `frontend/ui-react/` | Next.js 14 + CopilotKit React skeleton | F3.6 |
| `workflows/` | Agent-to-agent Python pipelines (NOT Cursor Skills - both retained, neither replaces the other) | F3.11 |
| `utils/` | Shared agent-layer infrastructure: base agent factory, MCP client, LLM provider, DB pool, session/task stores, HITL helpers, auth/OTel slots | F3.2 (base + mcp_client), F3.3 (db, session_store), F3.4 (llm_provider), F3.13 (auth, otel) |
| `config/` | Runtime YAML (`agents.yaml` for global LLM fallback + agent enable/disable, `mcp.yaml` for namespace registry) | F3.4 (agents.yaml), F3.13 (extended) |
| `sql/` | DDL for the `perfagent_state` database (six JSONB-only tables) | F3.3 |
| `pyproject.toml`, `requirements.txt` | Package metadata and dependencies | F3.2 |
| `.env.example` | Environment template (no real credentials) | F3.2 |

`a2a_server.py` (port 8001) and `agui_server.py` (port 8002) entrypoints are
created at the package root in F3.5 and F3.6 respectively.

## Conventions

1. **Additions only.** New files and new modules. Do not modify existing MCP
   server code or Dockerfiles without explicit approval. See
   [../.cursor/rules/project-and-coding-guidelines.mdc](../.cursor/rules/project-and-coding-guidelines.mdc).
2. **Async everywhere.** All agent code, MCP calls, DB access, and LLM calls
   are `async`. Sync wrappers around third-party libraries belong in `utils/`.
3. **Lazy heavy imports.** `ag2`, `fastmcp`, `asyncpg`, and LLM SDKs are
   imported inside functions, not at module top, so structural smoke tests run
   without a fully populated virtualenv.
4. **Four-file pattern.** Every agent folder under `agents/` has exactly:
   `agent.py`, `agent_card.json`, `INSTRUCTIONS.md`, `config.yaml`. No exceptions.
5. **MCP-mediated I/O.** Agents reach external systems only through MCP tools
   served by `gateway-mcp`. No direct vendor SDK calls from agent code.
   Exception: the script-agent's call to the Microsoft Playwright MCP is also
   mediated, just to a different MCP server (Container 4).
6. **Vendor-agnostic events.** Notifications-agent emits a `TestRunCompleted`
   event with structured fields. Routing to Teams / SharePoint / Slack / etc.
   is an Epic 4 adapter concern, not an agent concern.
7. **Config-driven behavior.** LLM provider selection (per-agent and global
   fallback), MCP namespace allowlists, agent enable/disable, auth on/off,
   OTel on/off - all in YAML, not Python.
8. **Test scripts go in gitignored `scripts/`** at the repo root, not inside
   `agent-framework/`.
9. **Three IDs travel with every task** (Section 4.3 of the V2 doc):
   `external_session_id` (optional, propagated from upstream SDLC),
   `session_id` (required, per UI/IDE/A2A connection), and `task_id`
   (required, per A2A task).

## Per-agent `config.yaml` schema

Each agent folder under `agents/<name>/` has a `config.yaml` file (created in
F3.7+). The schema below is consumed by `utils/llm_provider.py` and the
agent loader in `utils/base_agent.py`:

```yaml
# Per-agent override for the LLM. If this entire block is omitted, the agent
# falls back to `config/agents.yaml -> default_llm_provider`. Credentials
# (api_key / endpoint) are NEVER stored here - they come from `.env` and
# are merged at runtime by `utils/llm_provider.py::merge_env_credentials`.
llm_provider:
  provider: openai          # one of: openai | azure_openai | ollama
  openai_model: gpt-4o-mini # for provider=openai
  # azure_deployment: gpt-4o      # for provider=azure_openai
  # ollama_model: llama3.1        # for provider=ollama
  temperature: 0.2          # 0.1 for analysis/reporting, 0.4+ for creative

# MCP namespace allowlist. Each entry corresponds to a namespace prefix on
# the gateway-mcp tool catalog (e.g. "blazemeter_*", "datadog_*"). The
# orchestrator and agent-loader filter the MCP tool catalog through this
# list so each agent only sees the tools it is supposed to use.
mcp_tools:
  allowed_namespaces:
    - blazemeter
    - datadog

# Optional A2A discovery metadata. If absent, sensible defaults are derived
# from the agent name and folder.
a2a:
  display_name: "Execution Agent"
  description: "Runs BlazeMeter test runs end to end."
  tags: ["execution", "blazemeter"]
```

The global fallback file `config/agents.yaml` (or `agents.example.yaml`) holds
the `default_llm_provider` block plus the per-agent enable/disable map. A
disabled agent is not instantiated at startup and returns `404` on its A2A
agent card. TLS settings (`ssl_verification: ca_bundle | system | disabled`)
also live here; the actual CA bundle path comes from `REQUESTS_CA_BUNDLE` or
`SSL_CERT_FILE` env vars - same convention as `blazemeter-mcp`,
`datadog-mcp`, and `confluence-mcp`.

## Where to look first

- **Architecture overview, sequence diagrams, port assignments:** V2 doc
  Sections 4 and 5
- **Endpoint inventories:**
  - A2A on port 8001 (protocol-standard paths, no `/api/perfpilot/*` prefix):
    V2 doc Section 9.2
  - AG-UI on port 8002 (`/api/perfpilot/*` prefix, `/api/perfpilot/chat`):
    V2 doc Section 10.2
- **Database schema (six tables):** V2 doc Section 12.3
- **LLM provider pattern to mirror:**
  [../perfmemory-mcp/services/embeddings.py](../perfmemory-mcp/services/embeddings.py)
- **Long-running task patterns (poll / SSE / webhook):** V2 doc Section 14
- **HITL multi-round revise loop pattern:** V2 doc Section 15

## Cursor rules in force

- [../.cursor/rules/project-and-coding-guidelines.mdc](../.cursor/rules/project-and-coding-guidelines.mdc):
  no refactoring, additions only, smoke-test each enhancement, scripts go in
  gitignored `scripts/`.
- [../.cursor/rules/prerequisites.mdc](../.cursor/rules/prerequisites.mdc): MCP
  credentials are gitignored, do not validate `.env` files upfront.
- [../.cursor/rules/mcp-error-handling.mdc](../.cursor/rules/mcp-error-handling.mdc):
  retry policy and error reporting format per MCP type.
- [../.cursor/rules/skill-execution-rules.mdc](../.cursor/rules/skill-execution-rules.mdc):
  do not skip or reorder steps in skill workflows.

## HITL gate

Every PBI is reviewed before the next begins. Do not push to
`ag2-agent-framework`; the user reviews and approves all changes locally.

```
draft -> HITL review -> approve / reject -> revise if needed -> approve -> next PBI
```
