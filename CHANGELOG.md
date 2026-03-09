# MCP Performance Suite - Changelog (March 2026)

This document summarizes the enhancements and new features added to the MCP Performance Suite during March 2026.

---

## Table of Contents

- [1. Documentation & Cursor Rules](#1-documentation--cursor-rules)
- [2. Artifact Output Path Alignment](#2-artifact-output-path-alignment)
  - [2.1 Overview](#21-overview)
  - [2.2 JMeter MCP Output Changes](#22-jmeter-mcp-output-changes)
  - [2.3 Consumer-Side Fallback Pattern](#23-consumer-side-fallback-pattern)
  - [2.4 Listener Output Paths](#24-listener-output-paths)
  - [2.5 Files Modified](#25-files-modified)
- [3. JMeter HITL (Human-in-the-Loop) Editing Tools](#3-jmeter-hitl-human-in-the-loop-editing-tools)
  - [3.1 Overview](#31-overview)
  - [3.2 New MCP Tools](#32-new-mcp-tools)
  - [3.3 Component Registry](#33-component-registry)
  - [3.4 Script Source Agnostic](#34-script-source-agnostic)
  - [3.5 Safety Features](#35-safety-features)
  - [3.6 Files Created/Modified](#36-files-createdmodified)
- [4. Correlation Analysis Enhancements (v0.6.0)](#4-correlation-analysis-enhancements-v060)
  - [4.1 Overview](#41-overview)
  - [4.2 Multi-Phase Correlation Detection](#42-multi-phase-correlation-detection)
  - [4.3 OAuth and PKCE Support](#43-oauth-and-pkce-support)
  - [4.4 Static Header Parameterization](#44-static-header-parameterization)
  - [4.5 Enhanced Classification](#45-enhanced-classification)
  - [4.6 AI HITL Correlation Naming](#46-ai-hitl-correlation-naming)
  - [4.7 Orphan Variable Handling](#47-orphan-variable-handling)
  - [4.8 Script Generator Refactoring](#48-script-generator-refactoring)
  - [4.9 Files Created](#49-files-created)
  - [4.10 Files Modified](#410-files-modified)
- [5. AI-Assisted Script Debugging Workflow](#5-ai-assisted-script-debugging-workflow)
  - [5.1 Overview](#51-overview)
  - [5.2 Debug Workflow](#52-debug-workflow)
  - [5.3 New Component Type](#53-new-component-type)
  - [5.4 Debug Manifest](#54-debug-manifest)
  - [5.5 Safety Guardrails](#55-safety-guardrails)
  - [5.6 Files Created/Modified](#56-files-createdmodified)
- [Previous Changelogs](#previous-changelogs)

---

## 1. Documentation & Cursor Rules

### New Files

| File | Purpose |
|------|---------|
| `.cursor/rules/jmeter-hitl-editing.mdc` | Cursor Rule defining the full HITL workflow: script sources, core add/edit steps, headless execution, and downstream analysis |
| `docs/artifacts_guide.md` | Comprehensive guide to the artifacts folder: local-first architecture, directory structure, vendor conventions, consumer fallback pattern, and HITL state management |
| `docs/jmeter_hitl_user_guide.md` | User-facing guide for the HITL tools with requirements, getting started steps, best practices, and V2 roadmap |

### Updated Files

| File | Changes |
|------|---------|
| `.cursor/rules/jmeter-hitl-editing.mdc` | Restructured to support external JMX scripts; added 4 script sources; clarified test_run_id requirements; added dynamic test_run_id fallback; added import workflow with `imported_` prefix |
| `docs/changelogs/CHANGELOG-2026-02.md` | Archived full February changelog content (SLA Config, Log Analysis, Bottleneck v0.2, Multi-Session Artifacts) |
| `docs/README.md` | Added HITL user guide entry; updated numbering and folder structure tree |

---

## 2. Artifact Output Path Alignment

### 2.1 Overview

Aligned artifact output paths across the JMeter MCP, PerfAnalysis MCP, and Streamlit UI to ensure the full pipeline works end-to-end. Previously, test results from the JMeter MCP's headless execution landed in `jmeter/` but downstream consumers only looked in `blazemeter/`.

### 2.2 JMeter MCP Output Changes

The JMeter MCP now writes test outputs to `artifacts/<test_run_id>/jmeter/` with standardized filenames:

| File | Path |
|------|------|
| JTL (raw sample data) | `jmeter/test-results.csv` |
| Aggregate report | `jmeter/aggregate_performance_report.csv` |
| View Results Tree listener | `jmeter/results_tree.csv` |
| Aggregate Report listener | `jmeter/aggregate_report.csv` |

### 2.3 Consumer-Side Fallback Pattern

All consumers now check `blazemeter/` first, then fall back to `jmeter/`:

| Consumer | File |
|----------|------|
| Streamlit UI | `streamlit-ui/src/services/artifact_loader.py` |
| PerfAnalysis - performance analyzer | `perfanalysis-mcp/services/performance_analyzer.py` |
| PerfAnalysis - statistical analyzer | `perfanalysis-mcp/utils/statistical_analyzer.py` |
| PerfAnalysis - bottleneck analyzer | `perfanalysis-mcp/services/bottleneck_analyzer.py` |

### 2.4 Listener Output Paths

JMeter script listeners (View Results Tree, Aggregate Report) now write to the artifacts folder instead of the `jmeter-mcp/` root directory. This is configured at script generation time using absolute paths.

### 2.5 Files Modified

| File | Changes |
|------|---------|
| `jmeter-mcp/services/jmeter_runner.py` | Updated `_make_jtl_path` to output `test-results.csv`; updated `_make_aggregate_report_path` for consistent naming |
| `jmeter-mcp/services/script_generator.py` | Inject artifact-folder-relative paths into listener `filename` properties at generation time |
| `streamlit-ui/src/services/artifact_loader.py` | Added `_resolve_path_with_jmeter_fallback()` helper; updated `load_csv()`, `load_json()`, `check_data_availability()` |
| `perfanalysis-mcp/services/performance_analyzer.py` | Added `jmeter/` fallback for anomaly detection JTL lookup |
| `perfanalysis-mcp/utils/statistical_analyzer.py` | Added `jmeter/` fallback in both correlation functions |
| `perfanalysis-mcp/services/bottleneck_analyzer.py` | Added `jmeter/` fallback for JTL path resolution |

---

## 3. JMeter HITL (Human-in-the-Loop) Editing Tools

### 3.1 Overview

Three new MCP tools enable AI-assisted analysis, addition, and modification of JMeter JMX scripts. These tools implement a Human-in-the-Loop pattern where the AI agent proposes changes and the user reviews/approves them. The tools work on **any valid JMX script**, whether created manually in JMeter GUI, exported from BlazeMeter, generated by third-party tools, or produced by the JMeter MCP pipelines (Playwright, HAR, Swagger).

### 3.2 New MCP Tools

| Tool | Purpose |
|------|---------|
| `analyze_jmeter_script` | Analyze a JMX script's structure, hierarchy, node IDs, and variables. Returns a tree view with stable `node_id` identifiers for targeting specific elements. |
| `add_jmeter_component` | Add new JMeter components (controllers, samplers, config elements, extractors, assertions, timers, pre/post processors) to an existing script. Supports `dry_run` preview mode. |
| `edit_jmeter_component` | Edit existing components via operations: `rename`, `set_prop`, `replace_in_body`, `toggle_enabled`. Supports `dry_run` preview mode. |
| `list_jmeter_component_types` | Browse all supported component types with metadata, required/optional fields, and validation rules. |

**Key Design Decisions:**

- **`node_id` targeting**: Each JMX element receives a stable SHA1-hash identifier based on its type, name, and position, enabling reliable targeting across operations
- **Dry run mode**: All mutating operations support `dry_run=true` for previewing changes without modifying the file
- **Automatic backups**: Every non-dry-run mutation creates a numbered backup (e.g., `script-000001.jmx`, `script-000002.jmx`) following JMeter's own backup convention
- **Auto-discovery**: The `analyze_jmeter_script` tool auto-discovers `ai-generated_script_*` files; for external scripts, pass `jmx_filename` explicitly

### 3.3 Component Registry

A central `COMPONENT_REGISTRY` dictionary maps ~36 JMeter component types to builder functions, metadata, and validation schemas. Categories include:

| Category | Components |
|----------|-----------|
| Controllers | Loop, If, While, Once Only, Switch, ForEach, Transaction |
| Samplers | HTTP Request, JSR223 Sampler |
| Config Elements | CSV Data Set, User Defined Variables, HTTP Request Defaults, Cookie Manager, Header Manager, Auth Manager, Keystore Config |
| Extractors | JSON, Regex, CSS Selector, Boundary, XPath2 |
| Assertions | Response Assertion, Duration Assertion |
| Timers | Constant Timer, Constant Throughput Timer, Random Timer |
| Pre/Post Processors | JSR223 Pre-Processor, JSR223 Post-Processor |

### 3.4 Script Source Agnostic

The HITL tools do not require the script to have been created by `mcp-perf-suite`. Four script sources are supported:

1. **External / Pre-existing**: User copies their JMX into the artifacts folder
2. **Playwright + JMeter MCP**: Browser automation capture → script generation
3. **HAR Adapter**: HAR file import → script generation
4. **Swagger/OpenAPI Adapter**: API spec import → script generation

All sources converge on the same HITL workflow: analyze → add/edit → verify.

### 3.5 Safety Features

- **Backups**: Numbered `.jmx` backups in `artifacts/<test_run_id>/jmeter/backups/`
- **Dry run**: Preview any change before applying
- **Validation**: Component configs are validated against the registry schema before modification
- **Re-analysis**: Users are encouraged to re-analyze after each edit to confirm structural integrity

### 3.6 Files Created/Modified

#### Files Created

| File | Purpose |
|------|---------|
| `jmeter-mcp/services/jmx_editor.py` | Core HITL service: JMX discovery, parsing, saving, backup management, node indexing, variable scanning, and the add/edit/analyze logic |
| `jmeter-mcp/services/jmx/component_registry.py` | Central registry of ~36 JMeter component types with builders, metadata, and validation |
| `jmeter-mcp/services/jmx/assertions.py` | Builder functions for Response Assertion and Duration Assertion |
| `jmeter-mcp/services/jmx/timers.py` | Builder functions for Constant Timer, Constant Throughput Timer, and Random Timer |
| `docs/jmeter_hitl_user_guide.md` | User-facing guide with requirements, best practices, and workflow documentation |

#### Files Modified

| File | Changes |
|------|---------|
| `jmeter-mcp/jmeter.py` | Registered `analyze_jmeter_script`, `add_jmeter_component`, `edit_jmeter_component`, `list_jmeter_component_types` MCP tools |
| `jmeter-mcp/services/jmx/controllers.py` | Added 6 controller builders (Loop, If, While, Once Only, Switch, ForEach) |
| `jmeter-mcp/services/jmx/samplers.py` | Added JSR223 Sampler builder |
| `jmeter-mcp/services/jmx/config_elements.py` | Added HTTP Request Defaults, Auth Manager, Keystore Config builders |
| `jmeter-mcp/services/jmx/post_processor.py` | Added JSR223 Post-Processor builder |
| `jmeter-mcp/services/jmx/__init__.py` | Updated exports for all new builder functions |
| `jmeter-mcp/config.example.yaml` | Added `jmx_editing` section for backup configuration |

---

## 4. Correlation Analysis Enhancements (v0.6.0)

### 4.1 Overview

Major overhaul of the correlation analysis engine to support multi-phase detection, OAuth/PKCE flow recognition, static header parameterization, and an AI Human-in-the-Loop (HITL) naming workflow. The correlation analyzer now detects dynamic values across both responses and requests, classifies them by type, and feeds them into the JMX script generator for automatic parameterization.

### 4.2 Multi-Phase Correlation Detection

The analyzer now runs four detection phases in sequence:

| Phase | Name | Description |
|-------|------|-------------|
| 1a | Response-side extraction | Scan response bodies, headers, redirects, and cookies for dynamic values reused in later requests |
| 1b | Request-side OAuth/PKCE | Extract OAuth parameters from request URLs, POST bodies, and headers when response bodies are missing (common with browser-captured HAR traffic) |
| 1c | Token chain analysis | Detect sequential OAuth token exchanges (authorization_code, token-exchange, refresh_token) |
| 1d | Static header detection | Identify static API key headers using a generic pattern (`-key$` regex) for UDV parameterization |

### 4.3 OAuth and PKCE Support

- **Request-side OAuth detection**: Extracts `client_id`, `redirect_uri`, `state`, `nonce`, `scope`, `response_type`, `response_mode`, and SSO tokens from request URLs, POST bodies, and headers
- **PKCE flow detection**: Identifies `code_challenge` and `code_verifier` values across authorize and token exchange requests
- **PKCE Pre-Processor**: Inserts a JSR223 PreProcessor that generates fresh `code_verifier` and `code_challenge` values per iteration using SHA-256 and Base64URL encoding
- **PKCE substitution**: Replaces hardcoded PKCE values in URLs, POST bodies, and headers with `${code_challenge}` and `${code_verifier}`

### 4.4 Static Header Parameterization

- Detects static API key headers matching the generic `-key$` pattern across all requests
- Adds detected values to User Defined Variables automatically
- Replaces hardcoded header values with `${variable_name}` references in all HTTP Header Managers

### 4.5 Enhanced Classification

| Value Type | Detection Method |
|------------|-----------------|
| `oauth_state`, `oauth_nonce`, `oauth_code` | OAuth parameter name matching |
| `oauth_redirect_uri`, `oauth_client_id` | OAuth URL/body parameter extraction |
| `oauth_scope`, `oauth_response_type` | Request-side parameter detection |
| `sso_token` | SSO cookie/header detection |
| `api_key` | Generic header pattern matching (`-key$`) |
| `timestamp` | 13-digit Unix epoch millisecond detection |
| `business_id_numeric`, `business_id_guid` | Existing response-side extraction |

### 4.6 AI HITL Correlation Naming

A new workflow step between correlation analysis and JMX generation:

1. `analyze_network_traffic` produces `correlation_spec.json` with raw correlations
2. The AI generates `correlation_naming.json` assigning unique variable names, extractor types, and expressions per the naming rules (`.cursor/rules/jmeter-correlations.mdc`)
3. `generate_jmeter_script` consumes both files to produce the parameterized JMX

### 4.7 Orphan Variable Handling

- Orphan IDs (values in requests with no identifiable source response) are extracted and added to User Defined Variables
- SignalR timestamps detected by `source_key: "_"` are assigned `${__time()}` for dynamic generation
- Orphan values are substituted in URLs and POST bodies (both raw and URL-encoded forms)

### 4.8 Script Generator Refactoring

The `script_generator.py` was refactored into modular helper files under `services/helpers/`:

| Module | Responsibility |
|--------|---------------|
| `extractor_helpers.py` | Correlation naming/spec loading, extractor map building, extractor element creation |
| `substitution_helpers.py` | Variable name maps, substitution maps, URL/body/header replacement, PKCE substitution, static header substitution |
| `orphan_helpers.py` | Orphan value extraction, UDV variable building, orphan substitution maps, static header config extraction |
| `hostname_helpers.py` | Hostname extraction, categorization, variable mapping, hostname substitution |

### 4.9 Files Created

| File | Purpose |
|------|---------|
| `jmeter-mcp/services/helpers/__init__.py` | Package init for helper modules |
| `jmeter-mcp/services/helpers/extractor_helpers.py` | Correlation extractor support functions |
| `jmeter-mcp/services/helpers/substitution_helpers.py` | Variable substitution functions including PKCE and static headers |
| `jmeter-mcp/services/helpers/orphan_helpers.py` | Orphan variable and static header UDV handling |
| `jmeter-mcp/services/helpers/hostname_helpers.py` | Hostname parameterization functions |
| `.cursor/rules/jmeter-correlations.mdc` | Cursor Rule defining correlation naming conventions and output schema |

### 4.10 Files Modified

| File | Changes |
|------|---------|
| `jmeter-mcp/services/correlations/analyzer.py` | Added Phase 1b (request-side OAuth), Phase 1c (token chains), Phase 1d (static headers); updated summary statistics |
| `jmeter-mcp/services/correlations/extractors.py` | Added `extract_oauth_params_from_request_urls`, `extract_oauth_params_from_request_body`, `extract_oauth_from_request_headers`, `detect_pkce_flow`, `detect_token_exchanges`, `detect_static_api_key_headers` |
| `jmeter-mcp/services/correlations/classifiers.py` | Added 13-digit Unix epoch timestamp reclassification to `timestamp` value type |
| `jmeter-mcp/services/correlations/constants.py` | Expanded OAuth parameter lists; added generic `API_KEY_HEADER_RE` pattern (`-key$`) |
| `jmeter-mcp/services/jmx/oauth2.py` | Implemented `create_oauth_token_extractor`; scaffolded `create_oauth_refresh_flow` |
| `jmeter-mcp/services/jmx/pre_processor.py` | Added `create_pkce_preprocessor` and `append_preprocessor` |
| `jmeter-mcp/services/script_generator.py` | Refactored to import helper modules; added PKCE detection/substitution, orphan UDV merging, static header extraction/substitution; wired all phases into both controller and flat mode |
| `jmeter-mcp/config.example.yaml` | Updated version to `0.6.0-dev` |

---

## 5. AI-Assisted Script Debugging Workflow

### 5.1 Overview

A new iterative debugging workflow enables Cursor (or any AI agent) to autonomously validate and fix JMeter scripts after generation. This closes the loop on the script creation pipeline — scripts created via Playwright, HAR, or Swagger adapters can now be smoke-tested, diagnosed, and repaired without manual intervention.

The workflow mirrors how an experienced performance test engineer debugs a script: run a 1-user smoke test, identify the first failure, diagnose it using verbose logging, apply a fix, and re-test. This cycle repeats until the script is clean or human intervention is needed.

```
                        ┌─────────────────────────┐
                        │   User Requests Debug   │
                        └────────────┬────────────┘
                                     │
                                     ▼
                        ┌─────────────────────────┐
                        │  Create Debug Manifest  │
                        └────────────┬────────────┘
                                     │
                ┌────────────────────┼────────────────────┐
                │            ITERATIVE CYCLE              │
                │                    ▼                    │
                │   ┌─────────────────────────────────┐   │
                │   │  Phase 1: Smoke Test (1/1/1)    │   │
                │   │  start_jmeter_test              │   │
                │   │  get_jmeter_run_status          │   │
                │   │  analyze_jmeter_log             │   │
                │   └───────────────┬─────────────────┘   │
                │                   │                     │
                │                   ▼                     │
                │   ┌─────────────────────────────────┐   │
                │   │  Phase 2: Triage                │   │
                │   │  0% errors ──────► Done         │   │
                │   │  401/403 ────────► STOP (creds) │   │
                │   │  5xx all ────────► STOP (env)   │   │
                │   │  Isolated errors ► Continue     │   │
                │   └───────────────┬─────────────────┘   │
                │                   │                     │
                │                   ▼                     │
                │   ┌─────────────────────────────────┐   │
                │   │  Phase 3: Apply Debug           │   │
                │   │  PostProcessor                  │   │
                │   │  Enable VERBOSE_LOGGING         │   │
                │   │  Attach to first failing        │   │
                │   │  sampler                        │   │
                │   └───────────────┬─────────────────┘   │
                │                   │                     │
                │                   ▼                     │
                │   ┌─────────────────────────────────┐   │
                │   │  Phase 4: Debug Smoke Test      │   │
                │   │  Re-run 1/1/1                   │   │
                │   │  analyze_jmeter_log             │   │
                │   │  Read [ERROR]:[DEBUG]: lines    │   │
                │   │  from raw log                   │   │
                │   └───────────────┬─────────────────┘   │
                │                   │                     │
                │                   ▼                     │
                │   ┌─────────────────────────────────┐   │
                │   │  Phase 5: Diagnose & Fix        │   │
                │   │  (one issue at a time)          │   │
                │   │  - Correlation issues           │   │
                │   │  - Extractor placement          │   │
                │   │  - Parameterization             │   │
                │   │  - Auth/session tokens          │   │
                │   └───────────────┬─────────────────┘   │
                │                   │                     │
                │                   ▼                     │
                │   ┌─────────────────────────────────┐   │
                │   │  Phase 6: Iterate               │   │
                │   │  Append to debug manifest       │   │
                │   │  Max 5 iterations               │   │
                │   └───────────────┬─────────────────┘   │
                │                   │                     │
                │            ┌──────┴───────┐             │
                │            │ Errors left? │             │
                │            └──────┬───────┘             │
                │             Yes   │   No                │
                │              │    │    │                │
                │              ▼    │    ▼                │
                │          Loop ◄───┘  Continue           │
                │                                         │
                └─────────────────────────────────────────┘
                                     │
                                     ▼
                        ┌──────────────────────────┐
                        │  Phase 7: Cleanup        │
                        │  Disable debug post-     │
                        │  processors              │
                        │  VERBOSE_LOGGING=false   │
                        │  Final validation run    │
                        │  Finalize debug manifest │
                        └──────────────────────────┘
```

**Key Principles:**
- **User-initiated only** — Cursor never starts debugging unless explicitly asked
- **First-failure-first** — fix one sampler at a time; cascading errors often resolve themselves
- **Dual-channel analysis** — `analyze_jmeter_log` for structured error triage + raw log reading for verbose `[ERROR]:[DEBUG]:` request/response details
- **Automatic bailout** — stops on server-side, credential, or infrastructure issues that require human intervention

---

### 5.2 Debug Workflow

The workflow is defined in a new Cursor Rule (`jmeter-script-debugging.mdc`) with 7 phases:

| Phase | Purpose | Key Tools |
|-------|---------|-----------|
| Phase 1 | Run initial 1/1/1 smoke test | `start_jmeter_test`, `get_jmeter_run_status`, `analyze_jmeter_log` |
| Phase 2 | Triage errors — continue, stop, or done | Decision tree based on error patterns |
| Phase 3 | Attach debug post-processor to first failing sampler, enable `VERBOSE_LOGGING` | `add_jmeter_component`, `edit_jmeter_component` |
| Phase 4 | Re-run smoke test with verbose logging | `start_jmeter_test`, raw log reading |
| Phase 5 | Diagnose root cause and apply a single fix | `add_jmeter_component`, `edit_jmeter_component` |
| Phase 6 | Iterate (loop back to Phase 1, max 5 cycles) | Append iteration to debug manifest |
| Phase 7 | Cleanup — disable debug artifacts, final validation run | `edit_jmeter_component`, finalize debug manifest |

---

### 5.3 New Component Type

A new `jsr223_debug_postprocessor` component type was added to the JMX builder pipeline and component registry. This is a JSR223 PostProcessor pre-loaded with a Groovy debug script that logs verbose request/response details for failed samplers.

**Behavior:**
- Gated by the `VERBOSE_LOGGING` User Defined Variable (must be `"true"` to produce output)
- Only fires when the sampler **fails** (`prev.isSuccessful() == false`)
- Uses `log.error()` so the `analyze_jmeter_log` tool picks up the output as a heads-up
- Log output uses `[ERROR]:[DEBUG]:` prefix followed by Response Code, Response Message, Request, and Response body

**Usage via HITL tools:**

```
add_jmeter_component(
  test_run_id="<test_run_id>",
  component_type="jsr223_debug_postprocessor",
  parent_node_id="<failing_sampler_node_id>",
  component_config={}
)
```

No required fields — the Groovy script is built-in. Only an optional `name` override is supported.

---

### 5.4 Debug Manifest

Each debugging session produces a debug manifest at `artifacts/<test_run_id>/analysis/debug_manifest.md`. This markdown file is created at the start of the workflow and appended after each iteration.

**Contents:**
- Test run ID, script name, start timestamp, and status
- Per-iteration entries with timestamps, error details, diagnosis, fix applied, and result
- Final summary with total duration, iteration count, and list of all fixes applied

**Status values:** `In Progress`, `Resolved`, `Needs Human Intervention`, `Iteration Limit Reached`

The manifest serves as a historical record for identifying recurring patterns, reporting AI debugging efficiency to leadership, and informing future MCP tool improvements.

---

### 5.5 Safety Guardrails

| Guardrail | Description |
|-----------|-------------|
| User-initiated only | Workflow only activates when the user explicitly requests debugging |
| One fix at a time | Fix the first failing sampler, re-test, then assess remaining errors |
| 1/1/1 smoke tests only | All debug runs use 1 thread, 1 second ramp-up, 1 loop |
| Max 5 iterations | Prevents infinite loops on systemic issues |
| Environment bailout | Stops on HTTP 401/403, widespread 5xx, or connection failures |
| Automatic backups | HITL tools create numbered backups before every edit |
| `log_source="jmeter"` | Always uses local JMeter log source, not the default BlazeMeter source |

---

### 5.6 Files Created/Modified

#### New Files

| File | Purpose |
|------|---------|
| `.cursor/rules/jmeter-script-debugging.mdc` | Cursor Rule defining the full iterative debugging workflow (7 phases, safety guidelines, debug manifest) |

#### Modified Files

| File | Changes |
|------|---------|
| `jmeter-mcp/services/jmx/post_processor.py` | Added `create_jsr223_debug_postprocessor` function with built-in Groovy debug script |
| `jmeter-mcp/services/jmx/component_registry.py` | Added `_build_jsr223_debug_postprocessor` adapter and `jsr223_debug_postprocessor` registry entry |
| `jmeter-mcp/services/jmx/__init__.py` | Exported `create_jsr223_debug_postprocessor` |
| `jmeter-mcp/jmeter_config.example.yaml` | Added `VERBOSE_LOGGING` to default User Defined Variables |

---

## Previous Changelogs

| Month | File | Highlights |
|-------|------|------------|
| February 2026 | [CHANGELOG-2026-02.md](docs/changelogs/CHANGELOG-2026-02.md) | Swagger/OpenAPI Adapter, HAR Adapter, Centralized SLA Config, JMeter Log Analysis, Bottleneck Analyzer v0.2, Multi-Session Artifacts |
| January 2026 | [CHANGELOG-2026-01.md](docs/changelogs/CHANGELOG-2026-01.md) | AI-Assisted Report Revision, Datadog Dynamic Limits, Report Enhancements, New Charts |

---

*Last Updated: March 8, 2026*
