# 🛣️ MCP Perf Suite — Roadmap

> This document captures the evolution plan for the MCP Perf Suite, from near-term infrastructure upgrades to the long-term vision of a fully autonomous, model-agnostic performance testing platform.

---

## 📍 Current State

- 🔧 **7 MCP servers** (JMeter, BlazeMeter, Datadog, PerfAnalysis, PerfReport, Confluence, MS Graph), each standalone and FastMCP 2.0-based
- 🔌 Each server runs as a separate process with its own connection
- 🤖 AI orchestration is handled by the client model (e.g., Cursor + Claude), which manages tool sequencing, state, and error recovery
- 📂 Artifacts flow between MCPs via the filesystem (`artifacts/<run_id>/`)
- ⚠️ No formal data contracts between MCPs — the agent is the glue

---

## 🚀 Phase 1: FastMCP 3.0 Migration

**Goal:** Upgrade each MCP server from FastMCP 2.0 to 3.0 for access to providers, transforms, and modern transport options.

**Why first:** Everything downstream (orchestrator, dockerization, composition) depends on the 3.0 provider/mount model. Migrating on a stable baseline avoids a moving target.

**Approach:**
- 🔄 Migrate one MCP at a time, starting with the simplest (e.g., Confluence MCP)
- 📦 Update FastMCP dependency and imports to 3.0 patterns
- ✅ Validate each server end-to-end after migration (tool calls, artifact output, error handling)
- 🔁 Repeat for all 7 servers

**Key references:**
- [FastMCP 3.0 What's New](https://www.jlowin.dev/blog/fastmcp-3-whats-new)
- [FastMCP Migration Guide](https://gofastmcp.com)

---

## 📐 Phase 2: Inter-MCP Data Contracts (I/O Schemas)

**Goal:** Define formal input/output schemas for data flowing between MCPs, so each server's expectations are explicit and validated.

**Why:** Today the agent carries state and implicitly knows what each MCP produces and what the next one expects. Formalizing these contracts:
- 🔗 Enables the Super MCP to pipe outputs between sub-MCPs without agent intervention
- 🛡️ Makes any agent (local or cloud) more reliable — it can validate tool outputs against a schema
- 🧩 Unblocks the schema-driven adapter architecture (Phase 5)
- 👥 Makes contributor onboarding easier — clear contracts instead of tribal knowledge

**Key contracts to define:**
| From | To | Data |
|------|----|------|
| BlazeMeter MCP | PerfAnalysis MCP | Run results, session artifacts, aggregate report, JMeter log analysis |
| Datadog MCP | PerfAnalysis MCP | K8s metrics, logs, APM traces |
| PerfAnalysis MCP | PerfReport MCP | Analysis results, correlation data, bottleneck findings |
| PerfReport MCP | Confluence MCP | Markdown report, generated charts, metadata |
| PerfReport MCP | MS Graph MCP | Report artifacts, chart images |

**Format:** JSON Schema, Pydantic models, or TypedDict definitions — whichever fits the codebase style. Document each contract alongside the producing MCP.

---

## 🏗️ Phase 3: Super MCP / Orchestrator

**Goal:** Introduce a single orchestrator MCP that composes all sub-MCPs via FastMCP 3.0's `mount()` / provider system.

**Architecture:**
```text
Client (Cursor, Claude Desktop, Local Agent, etc.)
  │
  ▼
perf-suite-mcp (Orchestrator) 🎛️
  ├── mount(jmeter_mcp,       namespace="jmeter")
  ├── mount(blazemeter_mcp,   namespace="blazemeter")
  ├── mount(datadog_mcp,      namespace="datadog")
  ├── mount(perfanalysis_mcp, namespace="analysis")
  ├── mount(perfreport_mcp,   namespace="report")
  ├── mount(confluence_mcp,   namespace="confluence")
  └── mount(msgraph_mcp,      namespace="msgraph")
```

**Key decisions:**
- 🏷️ **Namespacing:** Use namespaces for agent discoverability even though tool names don't currently collide. A flat list of 55+ tools is harder for models to reason about than a namespaced catalog.
- ⚡ **In-process first:** All MCPs mounted in the same Python process via `FastMCPProvider`. No separate processes, no network overhead.
- 🔀 **Proxy later:** Individual MCPs can be peeled off into separate containers and switched to `ProxyProvider` when independent scaling or fault isolation is needed (see Phase 4).
- 🧰 **Workflow-level tools (optional):** The orchestrator can expose higher-order tools (e.g., `run_e2e_workflow(run_id, env)`) that internally call the sub-MCP tools in sequence, reducing the agent's orchestration burden.

**Shared state concept — `PerfTestSession`:**
A first-class context object (run ID, environment config, session IDs, artifact paths, comparison ID) that tools read from and write to. This eliminates the need for the agent to thread state through every tool call.

---

## 🐳 Phase 4: Dockerization

**Goal:** Package the Super MCP as a single Docker container exposed over SSE (or Streamable HTTP).

**Architecture:**
```text
┌──────────────────────────────────────┐
│  🐳 Docker Container                │
│                                      │
│  perf-suite-mcp (Orchestrator)       │
│    ├── jmeter-mcp (in-process)       │
│    ├── blazemeter-mcp (in-process)   │
│    ├── datadog-mcp (in-process)      │
│    ├── perfanalysis-mcp (in-process) │
│    ├── perfreport-mcp (in-process)   │
│    ├── confluence-mcp (in-process)   │
│    └── msgraph-mcp (in-process)      │
│                                      │
│  🌐 Transport: SSE / Streamable HTTP│
│  🔌 Port: 8000                      │
└──────────────────────────────────────┘
```

**Why a single container:**
- ⚡ FastMCP 3.0 in-process mounting means one Python process handles everything
- 🚫 Avoids distributed systems overhead (service discovery, health checks, inter-container networking)
- 🔑 Runtime config via environment variables (API keys, auth tokens, transport mode)
- ☁️ Simple to deploy anywhere: local, cloud VM, Kubernetes

**When to split into multiple containers:**
- 📈 A specific MCP needs independent scaling (e.g., PerfAnalysis is CPU-heavy)
- 🔧 Different MCPs depend on different runtimes or system-level tools (e.g., JMeter CLI)
- 🛡️ Fault isolation is needed — a crash in one MCP shouldn't affect others
- 👥 Different teams deploy different MCPs on their own cadence

In the multi-container model, the orchestrator switches from `mount()` to `ProxyProvider` for the extracted MCPs.

---

## 🔌 Phase 5: Schema-Driven Adapter Architecture

**Goal:** Replace single-vendor MCPs (BlazeMeter, Datadog) with adapter-based MCPs that support multiple tools behind a standardized schema.

This phase builds on the I/O schema contracts from Phase 2.

### 📊 APM MCP Server (replaces Datadog MCP)
Unified entry point supporting multiple APM tools via adapter modules:
- Datadog (current implementation migrated as adapter)
- New Relic adapter
- Dynatrace adapter
- AppDynamics adapter
- Splunk APM adapter

All adapters output the **Standardized APM Output Schema** (metrics, logs, traces).

### 🧪 Load Test MCP Server (replaces BlazeMeter MCP)
Unified entry point supporting multiple load testing tools:
- BlazeMeter (current implementation migrated as adapter)
- LoadRunner adapter
- Gatling adapter
- k6 adapter
- Locust adapter

All adapters output the **Standardized Load Test Output Schema** (results, aggregates).

### ✏️ Test Design MCP (evolution of JMeter MCP)
Evolve from "generate JMX from Playwright JSON" toward a tool-agnostic test definition:
- `design_load_test_from_traffic(test_definition + captured_traffic)` → JMX (today), Gatling/k6/Locust (later)
- `design_load_test_from_schema(test_definition)` → vendor-specific script

A single, declarative way to describe a test — agents choose which adapter to target.

---

## 🤖 Phase 6: AI Agent Orchestration

**Goal:** Introduce a hierarchy of AI agents and sub-agents that orchestrate the performance testing workflow, with the Super MCP as their shared toolkit.

### 🏛️ Agent Hierarchy
```text
🧠 Performance Test Manager (top-level agent)
  ├── ✏️ Test Design Agent      → jmeter/* tools
  ├── 🚀 Execution Agent        → blazemeter/* tools
  ├── 👁️ Observability Agent    → datadog/* tools
  ├── 🔬 Analysis Agent         → analysis/* tools
  └── 📑 Reporting Agent        → report/*, confluence/*, msgraph/* tools
```

### 💡 Design Considerations
- 🎯 All agents connect to the **same orchestrator MCP** (single endpoint)
- 🏷️ Agents select tools based on namespaces, tags, or curated tool lists
- 📄 Structured intermediate artifacts (JSON, CSV, Markdown) serve as contracts between stages
- 🔄 The `PerfTestSession` context object (from Phase 3) carries state across agent handoffs
- 📜 Workflow rules (`.mdc` files) can be embedded into agent prompts for deterministic sequencing

### ❓ Open Questions
- How should agents represent state across tool calls? (Session object vs. conversation context vs. vector DB retrieval)
- Should the orchestrator MCP tag tools for role-based selection (e.g., `role:test_design`, `role:analysis`)?
- Single generalist agent vs. hierarchy of domain agents — where's the sweet spot?

---

## 🔬 Future Research: Agent-to-Agent (A2A) Protocol

**Goal:** Explore using A2A patterns to enable a hybrid local/cloud agent architecture for cost efficiency, latency, and privacy.

### 💡 The Idea
```text
👤 User
  │
  ▼
🏠 Local Agent (Ollama + Vector DB + Super MCP)
  │                                    │
  ▼                                    ▼
[Deterministic work]            [A2A handoff ☁️]
- BlazeMeter fetch               - "Analyze these 5 runs"
- Datadog metrics                - "Write executive summary"
- PerfAnalysis tools             - "Debug this tool failure"
- Chart generation               - "Interpret log findings"
- Confluence publish
  │                                    │
  ▼                                    ▼
Local results               ☁️ Cloud Agent (Frontier Model)
  │                                    │
  └──────────── merged ────────────────┘
                  │
                  ▼
            ✅ Final output
```

### 🎯 Why A2A
| Benefit | Description |
|---------|-------------|
| 💰 **Cost** | Only pay for frontier model tokens when frontier-level reasoning is needed |
| ⚡ **Latency** | Local tool calls are instant — no cloud round-trips for procedural work |
| 🔒 **Privacy** | API keys, test data, and credentials stay local; only synthesized analysis goes to the cloud |
| 🎓 **Specialization** | Local agent becomes an expert at *your* workflow; cloud agent brings general intelligence on demand |

### ❓ Open Research Questions
1. 🚦 **Handoff triggers:** What determines when the local agent escalates to the cloud? Confidence-based, error-based, task-type-based, or hybrid?
2. 📨 **Message format:** MCP defines tool schemas, but A2A needs a way to package context, intent, and constraints for the receiving agent. How does this bridge to MCP tool results?
3. 🔄 **State reintegration:** When the cloud agent returns a result (e.g., revised executive summary), how does the local agent weave it back into the workflow and continue?
4. 🌱 **Google A2A protocol maturity:** The protocol is still evolving. Monitor adoption and tooling before committing to an implementation.

### 📋 Prerequisites
- ✅ Phases 1–4 complete (Super MCP, Docker, I/O schemas)
- 🧠 Local model ecosystem mature enough for reliable multi-tool orchestration (estimated 6–12 months)
- 📦 A2A protocol stabilized with production-ready client/server libraries

---

## 📈 Evolution Summary

```text
Today       →  6 separate MCPs + cloud model + manual orchestration
Phase 1     →  🚀 6 MCPs on FastMCP 3.0
Phase 2     →  📐 Formal I/O schemas between MCPs
Phase 3     →  🏗️ 1 Super MCP composing all sub-MCPs
Phase 4     →  🐳 1 Docker container, SSE transport
Phase 5     →  🔌 Adapter-based MCPs (multi-vendor)
Phase 6     →  🤖 AI agent hierarchy orchestrating the pipeline
Future      →  🔬 Hybrid local/cloud agents via A2A
```

Each phase pushes intelligence into the infrastructure layer and reduces dependence on any single model or client. The MCP servers are the durable asset — the model layer is the part that keeps getting cheaper and more capable. 💪

---

## 📚 Related Documents

- 🧠 [Brainstorming: FastMCP 3.0 Roadmap Session](docs/todo/BRAINSTORM_mcp-perf-suite-roadmap-brainstorming-session.md)
- 🤝 [Brainstorming: A2A Protocol & Workflow Demo](docs/todo/BRAINSTORM_using_A2A_protocol.md)
