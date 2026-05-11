# MCP Performance Suite - Changelog (May 2026)

This document summarizes the enhancements and new features added to the MCP Performance Suite during May 2026.

---

## Table of Contents

- [1. PerfMemory Taxonomy System](#1-perfmemory-taxonomy-system)
- [2. JMeter MCP — EntraID Correlation Engine](#2-jmeter-mcp--entraid-correlation-engine)
- [3. EntraID Debugging Skill](#3-entraid-debugging-skill)
- [Previous Changelogs](#previous-changelogs)

---

## 1. PerfMemory Taxonomy System

### 1.1 Overview

Added a YAML-driven taxonomy layer to the PerfMemory MCP server that standardizes application and service naming before data enters the vector database and knowledge graph. This solves the problem of inconsistent `system_under_test` naming across teams and sessions (e.g., "OCP", "ocp-app", "Online Cart Application" all mapping to the same system), which previously degraded vector search quality and fragmented graph relationships.

### 1.2 Taxonomy Configuration

A new `taxonomy.yaml` file defines the canonical mapping of applications, services, and aliases:

- Each application entry has a canonical `system_under_test` name, optional aliases, and service hierarchy
- Aliases enable `system_alias` lookups — agents can pass any known alias and the taxonomy resolves it to the canonical name
- Services within an application inherit the parent's project context in the knowledge graph

### 1.3 Database Schema Updates

Extended both the relational and graph schemas to support taxonomy-driven fields:

| Layer | Changes |
|-------|---------|
| Relational (`debug_sessions`, `debug_attempts`) | New taxonomy columns for standardized system and service identification |
| Graph (`perf_knowledge`) | Updated vertex labels and edge properties for service-level tracking |

### 1.4 Tool Enhancements

Updated existing MCP tools to leverage the taxonomy:

| Tool | Enhancement |
|------|-------------|
| `store_debug_session` | Resolves `system_alias` to canonical `system_under_test` via taxonomy |
| `store_debug_attempt` | Applies taxonomy normalization to system and service fields |
| `find_similar_attempts` | Accepts `system_alias` input parameter for taxonomy-aware search |
| `find_cross_project_patterns` | Resolves error category and project aliases via taxonomy |
| `list_sessions` / `get_session_detail` | Enhanced filtering options using taxonomy fields |

### 1.5 Taxonomy Normalization Tool

A new `normalize_taxonomy` MCP tool that validates and normalizes existing data against the taxonomy:

- Scans existing sessions and attempts for non-compliant naming
- Backfills alias mappings for historical data
- Reports compliance status and suggested corrections

### 1.6 Files Created / Modified

| File | Purpose |
|------|---------|
| `perfmemory-mcp/taxonomy.example.yaml` | Example taxonomy configuration with application/service/alias definitions |
| `perfmemory-mcp/perfmemory.py` | Added `normalize_taxonomy` tool, taxonomy resolution in existing tools |
| `perfmemory-mcp/services/session_manager.py` | Taxonomy column support in CRUD operations and search |
| `perfmemory-mcp/services/graph_manager.py` | Graph schema updates for taxonomy-driven service tracking |
| `.cursor/skills/perfmemory/SKILL.md` | Updated with taxonomy usage guidance and `system_alias` parameter docs |

---

## 2. JMeter MCP — EntraID Correlation Engine

### 2.1 Overview

Extended the JMeter MCP correlation analysis engine to automatically detect and generate extractors and pre-processors for Microsoft Entra ID (formerly Azure AD) authentication flows. Previously, EntraID login flows required 10+ manual debugging iterations to identify missing correlations. This enhancement automates the detection of EntraID-specific dynamic values during script generation from HAR or Playwright network captures.

### 2.2 EntraID-Specific Constants

New constant sets in `constants.py` categorizing EntraID fields and patterns:

| Constant Set | Purpose |
|--------------|---------|
| `ENTRA_CONFIG_FIELDS` | Fields from `$Config` JavaScript objects (`sFT`, `sCtx`, `canary`, `sessionId`, etc.) |
| `ENTRA_CREDENTIAL_TYPE_FIELDS` | Fields from the GetCredentialType API response (`FederationRedirectUrl`, etc.) |
| `WSFED_FORM_FIELDS` | WS-Federation hidden form field names (`wresult`, `wctx`, `wa`, `wtrealm`) |
| `OPENAM_TOKEN_FIELDS` | OpenAM/ForgeRock token fields (`authId`, `nonce`, `cdssoToken`) |

### 2.3 New Extraction Functions

Four new extraction functions in `extractors.py` targeting EntraID response patterns:

| Function | What It Extracts |
|----------|-----------------|
| `extract_from_entra_config()` | `$Config` JS object fields and GetCredentialType JSON responses, including nested URL parsing for `estsrequest` from `FederationRedirectUrl` |
| `extract_from_body_redirect_urls()` | OAuth parameters from `href`, `<meta refresh>`, and `window.location` assignments in HTML |
| `extract_from_html_form_post()` (extended) | WS-Federation form fields (`wresult`, `wctx`) and tenant GUIDs from form action URLs |
| `extract_from_json_body()` (extended) | OpenAM token fields (`authId`, `nonce`, `cdssoToken`) via top-level JSON scan |

### 2.4 EntraID Flow Detection

A new `detect_entra_flow()` function in `extractors.py` that identifies EntraID authentication flows based on URL patterns, response content, and headers. When detected, the script generator attaches EntraID-specific pre-processors to the appropriate samplers.

### 2.5 New Pre-Processors

Two new JMeter pre-processor builders in `pre_processor.py`:

| Pre-Processor | Type | Purpose |
|---------------|------|---------|
| `entra_state_preprocessor` | JSR223 (Groovy) | Generates MSAL-format `oauth_state` as base64url-encoded JSON `{id:UUID, meta:{interactionType:"redirect"}}` |
| `entra_wsfed_cookie_preprocessor` | BeanShell | Injects `ESTSWCTXFLOWTOKEN` and `AADSSO` cookies into the CookieManager before WS-Fed form submission |

Both are registered in the component registry and can be added via `add_jmeter_component`.

### 2.6 Boundary Extractor Support

Added `boundary_extractor` support across the pipeline for extracting large values (e.g., WS-Federation `wresult` SAML tokens) that are too large for regex extraction:

- `naming.py` — Generates `left_boundary`/`right_boundary` configuration with WS-Fed-specific templates
- `extractor_helpers.py` — Creates `BoundaryExtractor` JMeter elements from the naming config
- `correlation_config.yaml` — New `response_wsfed_form: "boundary_extractor"` extractor type mapping

### 2.7 Script Generator Integration

Updated `script_generator.py` with EntraID-aware logic:

- Calls `detect_entra_flow()` during script generation
- Inserts `entra_state_preprocessor` on authorize samplers
- Inserts `entra_wsfed_cookie_preprocessor` on WS-Fed form submission samplers
- Works in both structured (controller-based) and flat generation modes

### 2.8 Files Modified

| File | Changes |
|------|---------|
| `jmeter-mcp/services/correlations/constants.py` | Added 4 EntraID constant sets |
| `jmeter-mcp/services/correlations/extractors.py` | Added 2 new extraction functions, extended 2 existing ones, added `detect_entra_flow()` |
| `jmeter-mcp/services/correlations/utils.py` | Extended `walk_json` to match `OAUTH_TOKEN_FIELDS` |
| `jmeter-mcp/services/correlations/naming.py` | Added boundary extractor config generation and WS-Fed boundary templates |
| `jmeter-mcp/correlation_config.example.yaml` | Added EntraID extractor type mappings and regex templates |
| `jmeter-mcp/services/helpers/extractor_helpers.py` | Added `boundary_extractor` case in extractor element creation |
| `jmeter-mcp/services/jmx/pre_processor.py` | Added 2 new pre-processor builder functions |
| `jmeter-mcp/services/jmx/component_registry.py` | Registered `entra_state_preprocessor` and `entra_wsfed_cookie_preprocessor` |
| `jmeter-mcp/services/script_generator.py` | Added EntraID flow detection and pre-processor insertion logic |

---

## 3. EntraID Debugging Skill

### 3.1 Overview

A new dedicated Cursor Skill (`.cursor/skills/jmeter-entraid-debugging/SKILL.md`) providing domain-specific knowledge for debugging JMeter scripts that interact with Microsoft Entra ID authentication flows. This skill is a companion to the general `jmeter-debugging` skill — the debugging skill defines the iterative workflow, while this skill provides the EntraID-specific diagnosis patterns, component references, and sampler sequences.

### 3.2 Why a Separate Skill

- The general debugging skill handles any JMeter failure type; EntraID knowledge is only relevant during auth/login flow debugging
- Skills should stay focused and under 500 lines (this skill is 217 lines)
- Separation of concerns: agents use `jmeter-debugging` for *how* to debug and `jmeter-entraid-debugging` for *what* to look for in EntraID flows

### 3.3 Skill Content

| Section | Purpose |
|---------|---------|
| Flow Recognition | Table of indicators that identify an EntraID flow (URL patterns, response markers) |
| Diagnosis Patterns | 8 patterns ordered by flow sequence: `response_mode=fragment`, BssoInterrupt, `$Config` extraction, GetCredentialType, OpenAM chain, WS-Fed wresult, cookie injection, MSAL state |
| Available Components | 7 JMeter MCP components relevant to EntraID with their `add_jmeter_component` types |
| Typical Sampler Sequence | 13-step reference table from authorize to application token |
| Extractor Quick Reference | 20 extractors with exact variable names, types, and expressions |
| Network Capture Limitation | Documents the known HAR/Playwright empty-response limitation for EntraID flows |

### 3.4 Cross-Reference

A one-line cross-reference was added to the `jmeter-debugging` skill's Common Diagnosis Patterns section, directing agents to the EntraID skill when they encounter EntraID patterns during triage.

### 3.5 Files Created / Modified

| File | Purpose |
|------|---------|
| `.cursor/skills/jmeter-entraid-debugging/SKILL.md` | New EntraID debugging skill with diagnosis patterns and component references |
| `.cursor/skills/jmeter-debugging/SKILL.md` | Added cross-reference to the EntraID skill |

---

## Previous Changelogs

| Month | File | Highlights |
|-------|------|------------|
| April 2026 | [CHANGELOG-2026-04.md](docs/changelogs/CHANGELOG-2026-04.md) | Skills Migration, Cursor Subagents, PerfMemory MCP + AGE Graph, MS Teams MCP, KPI Analysis, JMeter Script Validator, Structure Export & HAR-JMX Comparison |
| March 2026 | [CHANGELOG-2026-03.md](docs/changelogs/CHANGELOG-2026-03.md) | HITL Editing Tools, Correlation Analysis v0.6/v0.7, AI-Assisted Debugging, Artifact Path Alignment, BlazeMeter Shared Folders |
| February 2026 | [CHANGELOG-2026-02.md](docs/changelogs/CHANGELOG-2026-02.md) | Swagger/OpenAPI Adapter, HAR Adapter, Centralized SLA Config, JMeter Log Analysis, Bottleneck Analyzer v0.2, Multi-Session Artifacts |
| January 2026 | [CHANGELOG-2026-01.md](docs/changelogs/CHANGELOG-2026-01.md) | AI-Assisted Report Revision, Datadog Dynamic Limits, Report Enhancements, New Charts |

---

*Last Updated: May 10, 2026*
