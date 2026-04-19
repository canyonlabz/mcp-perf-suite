# MCP Performance Suite - Changelog (April 2026)

This document summarizes the enhancements and new features added to the MCP Performance Suite during April 2026.

---

## Table of Contents

- [1. Cursor Rules to Cursor Skills Migration](#1-cursor-rules-to-cursor-skills-migration)
- [2. Cursor Subagents](#2-cursor-subagents)
- [3. PerfMemory MCP Server](#3-perfmemory-mcp-server)
- [4. PerfMemory AI Skill & Debugging Integration](#4-perfmemory-ai-skill--debugging-integration)
- [5. MS Teams MCP Server](#5-ms-teams-mcp-server)
- [6. PerfMemory Apache AGE Knowledge Graph](#6-perfmemory-apache-age-knowledge-graph)
- [Previous Changelogs](#previous-changelogs)

---

## 1. Cursor Rules to Cursor Skills Migration

### 1.1 Overview

Migrated the project's primary AI workflows from Cursor Rules (`.mdc` files always loaded into context) to Cursor Skills (`.md` files loaded on-demand when relevant). This significantly reduces context window consumption — rules are always injected into every conversation, while skills are only loaded when the agent detects a matching trigger.

### 1.2 Why This Matters

With 8+ MCP servers and growing workflow complexity, the accumulated rule files consumed substantial context on every interaction, even when irrelevant. Skills are invoked selectively based on user intent, preserving context for the actual task.

### 1.3 Skills Created

12 skills now cover the full performance testing lifecycle:

| Skill | Folder | Purpose |
|-------|--------|---------|
| Performance Testing Workflow | `performance-testing-workflow/` | End-to-end pipeline: BlazeMeter, Datadog, PerfAnalysis, PerfReport, Confluence |
| Comparison Report Workflow | `comparison-report-workflow/` | Multi-run side-by-side comparison reports |
| Report Revision Workflow | `report-revision-workflow/` | AI-assisted HITL report revision with version tracking |
| Playwright Browser Automation | `playwright-browser-automation/` | Browser automation to capture traffic and generate JMeter scripts |
| JMeter HITL Editing | `jmeter-hitl-editing/` | AI-assisted script analysis, component addition, and editing |
| JMeter Debugging | `jmeter-debugging/` | Iterative smoke test, diagnose, fix cycle |
| JMeter HAR Conversion | `jmeter-har-conversion/` | HAR file to JMX script conversion |
| JMeter Swagger Conversion | `jmeter-swagger-conversion/` | Swagger/OpenAPI spec to JMX script conversion |
| JMeter Correlation Naming | `jmeter-correlation-naming/` | Correlation variable naming review and adjustment |
| ADO Test Case Conversion | `ado-test-case-conversion/` | Azure DevOps QA test cases to browser automation specs |
| Subagent Orchestrator | `subagent-orchestrator/` | Orchestrate BlazeMeter and Datadog extraction via subagents |
| PerfMemory | `perfmemory/` | Lessons-learned memory layer for debugging |

All skills live under `.cursor/skills/` with a consistent `SKILL.md` structure: frontmatter with name/description/triggers, a Reference section for context, and an Execution section with step-by-step instructions.

### 1.4 Rules Retained

Six rules remain as `.mdc` files because they apply globally across all workflows:

| Rule | Purpose |
|------|---------|
| `prerequisites.mdc` | Pre-flight checks: credentials, artifact structure, `test_run_id` |
| `skill-execution-rules.mdc` | Follow skills exactly, sequential processing, task tracking |
| `mcp-error-handling.mdc` | Retry/no-retry policies for API vs code-based MCP tools |
| `jmeter-script-guardrails.mdc` | Smoke test = 1/1/1, one fix at a time, max 5 iterations |
| `browser-automation-guardrails.mdc` | Browser automation safety and network capture rules |

---

## 2. Cursor Subagents

### 2.1 Overview

Introduced Cursor subagents to offload long-running MCP extraction tasks from the main agent context. Subagents run in isolated contexts with their own tool access, enabling parallel execution and preserving the parent agent's context window for higher-level orchestration.

### 2.2 BlazeMeter Extractor Subagent

**Type:** `blazemeter-extractor`

Extracts all BlazeMeter test artifacts for a given `test_run_id`:
- Test results CSV (aggregate performance report)
- Session data (multi-engine sessions, JMeter logs)
- Test configuration metadata
- Public report URLs

Outputs to `artifacts/{test_run_id}/blazemeter/` with a `subagent_manifest.json` tracking extraction status.

### 2.3 Datadog Extractor Subagent

**Type:** `datadog-extractor`

Extracts Datadog monitoring data for a given environment and time window:
- Host or Kubernetes metrics (CPU, memory, network, disk)
- Application logs (error queries, custom queries)
- APM traces (if available)
- KPI metrics (optional, custom query groups)

Outputs to `artifacts/{test_run_id}/datadog/` with a `subagent_manifest.json` tracking extraction status.

### 2.4 Subagent Orchestrator Skill

A dedicated skill (`.cursor/skills/subagent-orchestrator/SKILL.md`) coordinates the two subagents sequentially:

1. Invoke `blazemeter-extractor` subagent
2. Extract test timestamps from BlazeMeter output
3. Invoke `datadog-extractor` subagent with the extracted time window
4. Write `orchestrator_manifest.json` with combined results
5. Hand off to the user for PerfAnalysis (Step 4 of the E2E workflow)

### 2.5 Files Created

| File | Purpose |
|------|---------|
| `.cursor/skills/subagent-orchestrator/SKILL.md` | Orchestrator skill with step-by-step subagent invocation workflow |

---

## 3. PerfMemory MCP Server

### 3.1 Overview

A new MCP server providing persistent memory and lessons-learned storage for JMeter script debugging. Built on PostgreSQL with the pgvector extension for vector similarity search, enabling AI agents to recall past fixes and avoid repeating mistakes across debugging sessions.

### 3.2 Architecture

- **Database:** PostgreSQL 18+ with pgvector 0.8.2 extension
- **Embedding providers:** OpenAI (`text-embedding-3-small`, 1536 dims), Azure OpenAI, Ollama (`nomic-embed-text`, 768 dims)
- **Search:** Cosine similarity via HNSW index with configurable threshold (default 0.60)
- **Connection management:** `psycopg2` connection pool with TCP keepalives, health checks, and graceful shutdown

### 3.3 Database Schema

Two normalized tables with a parent-child relationship:

| Table | Purpose |
|-------|---------|
| `debug_sessions` | Top-level debugging sessions with metadata (system, environment, auth flow, outcome) |
| `debug_attempts` | Individual debug iterations within a session (symptom, diagnosis, fix, embedding) |

Key design decisions:
- `symptom_text` is the only field embedded as a vector — its structure directly affects search quality
- `confirmed_count` tracks how many times a fix has been successfully reused
- `is_verified` flags human-reviewed lessons for higher confidence
- `is_active` enables soft-archiving without data loss

### 3.4 MCP Tools (9 total)

| Tool | Purpose |
|------|---------|
| `store_debug_session` | Create a new debugging session |
| `store_debug_attempt` | Record a debug iteration with symptom embedding |
| `find_similar_attempts` | Semantic similarity search with optional metadata filters |
| `close_debug_session` | Close a session with final outcome |
| `list_sessions` | Browse sessions with filters |
| `get_session_detail` | Full session detail with all attempts |
| `archive_attempt` | Soft-archive outdated lessons |
| `verify_attempt` | Mark an attempt as human-verified |
| `get_memory_stats` | Aggregate statistics on stored knowledge |

### 3.5 Configuration

Follows the same pattern as other MCP servers:
- **`.env`** for secrets (API keys, database credentials, SSL settings)
- **`config.yaml`** for tunable settings (similarity threshold, top_k, debug flags)
- Platform-specific overrides (`config.windows.yaml`, `config.mac.yaml`)

### 3.6 Production Readiness

- TCP keepalives (`idle=30s`, `interval=10s`, `count=3`) for stale connection detection
- Connection health checks (`SELECT 1`) before returning connections from the pool
- Leak prevention for `register_vector` failures
- SSL/TLS support for cloud-hosted PostgreSQL (Azure, AWS, GCP)
- Graceful shutdown via `atexit` hook for connection pool and HTTP client cleanup
- Lazy-cached embedding clients to prevent per-call resource creation

### 3.7 Files Created

| File | Purpose |
|------|---------|
| `perfmemory-mcp/perfmemory.py` | FastMCP server entrypoint with 9 tool definitions |
| `perfmemory-mcp/services/session_manager.py` | Database CRUD, connection pool, vector search |
| `perfmemory-mcp/services/embeddings.py` | Embedding provider abstraction (OpenAI, Azure, Ollama) |
| `perfmemory-mcp/utils/config.py` | Configuration loader (YAML + .env hybrid) |
| `perfmemory-mcp/sql/schema/README.md` | Schema design document |
| `perfmemory-mcp/sql/schema/schema_openai.sql` | Schema with `vector(1536)` for OpenAI/Azure embeddings |
| `perfmemory-mcp/sql/schema/schema_ollama.sql` | Schema with `vector(768)` for Ollama embeddings |
| `perfmemory-mcp/pyproject.toml` | Project metadata and dependencies |
| `perfmemory-mcp/.env.example` | Example environment variables |
| `perfmemory-mcp/config.example.yaml` | Example tunable configuration |
| `perfmemory-mcp/README.md` | Setup guide, tool reference, and workflow documentation |
| `docs/pgvector_installation_guide.md` | PostgreSQL + pgvector Docker setup guide |
| `docker/docker-compose-mac.yaml` | Docker Compose for pgvector container (Mac) |
| `docker/docker-compose-windows.yaml` | Docker Compose for pgvector container (Windows) |

---

## 4. PerfMemory AI Skill & Debugging Integration

### 4.1 Overview

Created a new standalone AI Skill for the PerfMemory MCP server and integrated it into the existing JMeter debugging workflow. This enables AI agents to search for past fixes before debugging, store lessons learned during debugging, and ingest existing knowledge from debug manifests or curated lessons-learned documents.

### 4.2 New Standalone Skill

**File:** `.cursor/skills/perfmemory/SKILL.md`

The PerfMemory Skill defines three workflows:

| Workflow | Purpose |
|----------|---------|
| **Workflow A** — Search Memory | Search for similar past issues before starting a debug loop. Returns ranked matches with recommendations (apply, review, or no match). |
| **Workflow B** — Store Lessons | Open a debug session, store each debug attempt with structured symptom text, and close the session when done. |
| **Workflow C** — Ingest Knowledge | Bulk-load lessons from debug manifests (`artifacts/{test_run_id}/analysis/debug_manifest.md`) or curated lessons-learned documents (`.md` files). |

Additional features:
- Structured symptom text template for consistent embedding quality
- Similarity score interpretation guide (>0.85 apply, 0.60-0.85 review, <0.60 no match)
- Maintenance operations: verify, archive, stats, session browsing

### 4.3 JMeter Debugging Skill Integration

**File:** `.cursor/skills/jmeter-debugging/SKILL.md`

Five additive integration points were added to the existing 10-step debugging workflow:

| Step | Name | Purpose |
|------|------|---------|
| Step 0.5 | Memory Check | Broad search for past issues on this system before debugging begins |
| Step 1.5 | Open PerfMemory Session | Create a debug session to track this debugging effort |
| Step 5d | Memory-Assisted Triage | Targeted search for the specific error — can skip verbose debugging if a high-confidence match exists |
| Step 8e | Store Attempt | Record each debug attempt (symptom, diagnosis, fix, outcome) in PerfMemory |
| Step 10b | Close Session | Close the PerfMemory session with final outcome and resolution reference |

All PerfMemory steps are **advisory only** — if the PerfMemory MCP server is unavailable, all memory steps are skipped and debugging proceeds normally.

### 4.4 Early Stop on Errors

Updated the smoke test monitoring logic (Steps 3c, 7a, 9c) to stop tests early when errors are detected instead of waiting for the full test to complete. Uses `stop_jmeter_test` for graceful shutdown with PID kill as a fallback only.

### 4.5 Files Created

| File | Purpose |
|------|---------|
| `.cursor/skills/perfmemory/SKILL.md` | Standalone PerfMemory Skill with 3 workflows, symptom template, and maintenance operations |

### 4.6 Files Modified

| File | Changes |
|------|---------|
| `.cursor/skills/jmeter-debugging/SKILL.md` | Added PerfMemory Integration reference section, Steps 0.5/1.5/5d/8e/10b, early-stop logic in Steps 3c/7a/9c, updated error handling for PerfMemory advisory behavior |

---

## 5. MS Teams MCP Server

### 5.1 Overview

A new MCP server (`msteams-mcp`) that automates Microsoft Teams notifications for performance testing workflows. Enables pre-test alerts, post-test result sharing, channel/chat discovery, and stakeholder communication — all driven by AI agents.

The server uses browser-based authentication (via Playwright) instead of Azure AD app registration, removing the need for admin consent, client secrets, and OAuth2 flows. Authentication architecture informed by [m0nkmaster/msteams-mcp](https://github.com/nicholasgriffintn/msteams-mcp) (MIT License), reimplemented in Python for the mcp-perf-suite ecosystem.

### 5.2 Authentication Architecture

Three-layer token resolution for fast, reliable authentication:

| Layer | Strategy | Speed |
|-------|----------|-------|
| 1. In-Memory Cache | Reuse tokens already in memory | Instant |
| 2. Encrypted Session File | Decrypt `session-state.json` (AES-256-GCM, machine-bound key) | Fast |
| 3. Browser Login | SSO first (headless), then visible browser fallback | Slow |

Token types used:

| Token | Used For | TTL |
|-------|----------|-----|
| Skype Token | Messaging APIs (chatsvc), CSA channel listing | ~24 hours |
| Auth Token | General Teams API auth | ~24 hours |
| Substrate Token | Search, People, and Channel discovery APIs | ~1 hour |
| CSA Token | Teams/channels list API (CSA v3) | ~24 hours |

### 5.3 MCP Tools (10 total)

#### Authentication

| Tool | Description |
|------|-------------|
| `teams_login` | Authenticate to MS Teams (SSO → headless → visible browser fallback) |
| `teams_status` | Check session health, token validity, and user info (no network calls) |

#### Messaging & Channels

| Tool | Description |
|------|-------------|
| `teams_send_message` | Send a message to a channel, chat, or group — supports templates, named targets, and `test_run_id` context |
| `teams_list_channels` | List all teams and channels the authenticated user has access to |
| `teams_find_channel` | Search for channels by name (org-wide discovery + membership status) |

#### Chats

| Tool | Description |
|------|-------------|
| `teams_get_chat` | Get a 1:1 chat conversation ID for another user (deterministic, no API call) |
| `teams_create_group_chat` | Create a new group chat with 2+ members and optional topic |

#### Search & People

| Tool | Description |
|------|-------------|
| `teams_search` | Full-text search across Teams messages with operator support |
| `teams_search_people` | Search for people by name or email (returns job title, department, MRI) |
| `teams_get_me` | Get the current user's profile (display name, email, tenant ID, MRI) |

### 5.4 Templated Notifications

Markdown notification templates with `{{PLACEHOLDER}}` interpolation, auto-converted to Teams-compatible HTML. The enhanced `teams_send_message` tool supports:

- **Template loading** with layered fallback: channel-specific → caller-specified → `default-` prefixed
- **Variable interpolation** from explicit parameters, `test_run_id` artifact files, or the `message` parameter
- **Config-driven named targets** — map friendly names (e.g. `perf-channel`) to conversation IDs in `config.yaml`
- **Per-channel template overrides** — bind a custom template to a specific channel in config
- **Notification logging** to `artifacts/<test_run_id>/notifications/notification_log.json` for context tracking across notifications (e.g. stop-test references start-test details)

Default templates provided:

| Template | Purpose |
|----------|---------|
| `default-notification-start-test.md` | Pre-test alert with test name, environment, duration, virtual users |
| `default-notification-stop-test.md` | Post-test completion with status and end time |
| `default-notification-test-results.md` | Results summary with key metrics and report links |

Auto-populated variables from `test_run_id` artifacts:

| Source | Variables |
|--------|-----------|
| `blazemeter/public_report.json` | `BLAZEMETER_REPORT_LINK`, `REPORT_LINK` |
| `confluence/report_metadata.json` | `CONFLUENCE_REPORT_LINK`, `REPORT_LINK` |
| `notifications/notification_log.json` | `TEST_NAME`, `ENVIRONMENT`, `DURATION`, `START_TIME` (from last start notification) |

### 5.5 Markdown to Teams HTML Conversion

A Python port of the TypeScript markdown converter, supporting:

- Bold, italic, strikethrough, inline code, fenced code blocks
- Ordered and unordered lists
- Paragraph breaks and line breaks
- Auto-detection: plain text with markdown formatting is automatically converted when `content_type="text"`

### 5.6 Files Created

| File | Purpose |
|------|---------|
| `msteams-mcp/msteams.py` | FastMCP server entry point with 10 tool definitions |
| `msteams-mcp/services/auth_manager.py` | Three-layer auth orchestration |
| `msteams-mcp/services/browser_auth.py` | Teams navigation + login detection |
| `msteams-mcp/services/browser_context.py` | Playwright persistent browser context |
| `msteams-mcp/services/token_extractor.py` | JWT decode + token extraction from localStorage |
| `msteams-mcp/services/session_store.py` | Encrypted session persistence |
| `msteams-mcp/services/crypto.py` | AES-256-GCM encryption primitives |
| `msteams-mcp/services/errors.py` | ErrorCode enum, McpError, Result monad |
| `msteams-mcp/services/teams_api.py` | Chatsvc + CSA API client (messaging, chats, channels) |
| `msteams-mcp/services/substrate_api.py` | Substrate API client (search, people, channel discovery) |
| `msteams-mcp/services/parsers.py` | Parsing functions + markdown to Teams HTML converter |
| `msteams-mcp/services/template_manager.py` | Template loading, rendering, and notification logging |
| `msteams-mcp/services/target_resolver.py` | Named target resolution from config |
| `msteams-mcp/templates/default-notification-start-test.md` | Start-test notification template |
| `msteams-mcp/templates/default-notification-stop-test.md` | Stop-test notification template |
| `msteams-mcp/templates/default-notification-test-results.md` | Results summary notification template |
| `msteams-mcp/utils/config.py` | Platform-aware YAML config loader |
| `msteams-mcp/config.example.yaml` | Configuration template with notification targets |
| `msteams-mcp/pyproject.toml` | Python project metadata + dependencies |
| `msteams-mcp/README.md` | Setup guide, tool reference, and workflow documentation |

---

## 6. PerfMemory Apache AGE Knowledge Graph

### 6.1 Overview

Enhanced the PerfMemory MCP server (v0.2.0) with an Apache AGE knowledge graph layer alongside the existing pgvector vector search. This enables structural relationship traversal across projects, error patterns, and fix patterns — complementing semantic similarity search with graph-based issue discovery. The goal: give AI agents enough structural memory to recognize patterns and auto-fix JMeter scripts, breaking out of repetitive debugging loops.

### 6.2 Infrastructure

Built a custom Docker image (`perfmem-pgvector-age`) that compiles Apache AGE from source against PostgreSQL 18, layered on top of the existing `pgvector/pgvector:pg18` base image.

| Component | Details |
|-----------|---------|
| Base image | `pgvector/pgvector:pg18` |
| AGE version | `PG18/v1.7.0-rc0` (compiled from source) |
| Container name | `perfmem-pgvector-age` |
| Preloaded libraries | `shared_preload_libraries = 'age'` |

Existing pgvector data is fully preserved — the volume mount is unchanged and no migration is needed for relational/vector data.

### 6.3 Graph Schema

The `perf_knowledge` graph uses 4 vertex labels and 4 edge types:

**Vertex Labels:**

| Label | Purpose | Key Properties |
|-------|---------|----------------|
| `Attempt` | Maps 1:1 to a `debug_attempts` row | `attempt_id`, `project`, `error_category`, `fix_type`, `outcome` |
| `Project` | Groups attempts by `system_under_test` | `name` |
| `ErrorPattern` | Represents a class of error | `error_category`, `response_code` |
| `FixPattern` | Represents a class of fix | `fix_type`, `component_type` |

**Edge Types:**

| Edge | From → To | Purpose |
|------|-----------|---------|
| `BELONGS_TO` | Attempt → Project | Project membership |
| `HAS_ERROR` | Attempt → ErrorPattern | Links attempt to its error class |
| `FIXED_BY` | Attempt → FixPattern | Links resolved attempt to its fix class |
| `SIMILAR_TO` | Attempt → Attempt | Structural or embedding-based similarity |

### 6.4 New MCP Tools

Two new graph-specific tools added (11 tools total):

| Tool | Purpose |
|------|---------|
| `find_cross_project_patterns` | Graph traversal to find resolved attempts from other projects sharing the same ErrorPattern. Used as a fallback when vector search returns no matches. Supports enrichment with full relational details. |
| `get_related_issues` | Explore the graph neighborhood of a specific attempt — returns connected ErrorPatterns, FixPatterns, and neighboring attempts via SIMILAR_TO edges. Supports enrichment. |

### 6.5 Hybrid Search Enhancement

`find_similar_attempts` now performs both vector and graph searches, merging results with configurable weighted scoring:

| Setting | Default | Purpose |
|---------|---------|---------|
| `graph.vector_weight` | 0.6 | Weight for vector cosine similarity |
| `graph.graph_weight` | 0.4 | Weight for graph match presence |

Results include a `source` field (`vector`, `graph`, or `both`) and a `combined_score`. Matches found by both vector and graph (`source: "both"`) are highest confidence.

### 6.6 Graph Manager Module

A new `graph_manager.py` module encapsulates all Apache AGE/Cypher operations, keeping them isolated from the relational `session_manager.py`:

- Separate `psycopg2` connection pool with AGE-specific `search_path` and `statement_timeout` (10s)
- Custom `agtype` result parsing for Python interop
- Write operations: `create_attempt_node`, `create_cross_project_edges`, `create_embedding_edges`
- Read operations: `find_graph_related`, `find_cross_project_patterns`, `get_related_issues`

### 6.7 Automatic Graph Population

When `graph.enabled: true`, `store_debug_attempt` automatically:

1. Creates an Attempt node with BELONGS_TO → Project edge
2. MERGEs ErrorPattern and FixPattern nodes with HAS_ERROR / FIXED_BY edges
3. Creates deterministic SIMILAR_TO edges to attempts from other projects sharing the same ErrorPattern
4. Creates embedding-based SIMILAR_TO edges for attempts above the configurable similarity threshold (default 0.82)

Existing data can be backfilled using `sql/graph/002_seed_graph_from_existing_data.sql`.

### 6.8 PerfMemory Skill Updates

Updated `.cursor/skills/perfmemory/SKILL.md` with:

- New **Step 3** in Workflow A: Cross-project graph search as fallback when vector returns no matches
- New **Step 4** in Workflow A: Graph neighborhood exploration for deeper context
- `enrich` parameter documentation for both graph tools
- "When to use" guidance for `get_related_issues` (post-match exploration, pre-fix context, cross-project verification)

### 6.9 Files Created

| File | Purpose |
|------|---------|
| `docker/Dockerfile.pgvector-age` | Custom Docker image: pgvector + Apache AGE on PostgreSQL 18 |
| `perfmemory-mcp/services/graph_manager.py` | Apache AGE/Cypher operations module |
| `perfmemory-mcp/sql/graph/001_create_graph.sql` | Graph schema creation (vertex/edge labels) |
| `perfmemory-mcp/sql/graph/002_seed_graph_from_existing_data.sql` | Backfill graph from existing relational data |
| `perfmemory-mcp/sql/graph/README.md` | Graph schema documentation |

### 6.10 Files Modified

| File | Changes |
|------|---------|
| `docker/docker-compose-windows.yaml` | Custom build from `Dockerfile.pgvector-age`, renamed container to `perfmem-pgvector-age` |
| `docker/docker-compose-mac.yaml` | Same as Windows compose changes |
| `perfmemory-mcp/perfmemory.py` | Added 2 graph tools, hybrid search in `find_similar_attempts`, graph ingestion in `store_debug_attempt` |
| `perfmemory-mcp/services/session_manager.py` | Added `get_attempt_by_id()` for enriching graph results |
| `perfmemory-mcp/utils/config.py` | Added graph config loading and `ef_search` parameter |
| `perfmemory-mcp/config.example.yaml` | Added `server` version block and `graph` configuration section |
| `perfmemory-mcp/README.md` | Added graph tools, updated workflow diagram, project structure, and config reference |
| `.cursor/skills/perfmemory/SKILL.md` | Added graph workflow steps, `enrich` parameter docs, usage guidance |
| `README.md` | Updated PerfMemory description, workflow diagram, architecture tree, removed MS Graph references |
| `docs/enhancements/Enhancement_Apache AGE Graph Layer for PerfMemory.md` | Updated status to "In Progress" |

---

## Previous Changelogs

| Month | File | Highlights |
|-------|------|------------|
| March 2026 | [CHANGELOG-2026-03.md](docs/changelogs/CHANGELOG-2026-03.md) | HITL Editing Tools, Correlation Analysis v0.6/v0.7, AI-Assisted Debugging, Artifact Path Alignment, BlazeMeter Shared Folders |
| February 2026 | [CHANGELOG-2026-02.md](docs/changelogs/CHANGELOG-2026-02.md) | Swagger/OpenAPI Adapter, HAR Adapter, Centralized SLA Config, JMeter Log Analysis, Bottleneck Analyzer v0.2, Multi-Session Artifacts |
| January 2026 | [CHANGELOG-2026-01.md](docs/changelogs/CHANGELOG-2026-01.md) | AI-Assisted Report Revision, Datadog Dynamic Limits, Report Enhancements, New Charts |

---

*Last Updated: April 19, 2026*
