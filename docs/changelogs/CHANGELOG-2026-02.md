# MCP Performance Suite - Changelog (February 2026)

This document contains all enhancements and new features added to the MCP Performance Suite during February 2026.

---

## Table of Contents

- [1. Swagger/OpenAPI Input Adapter (February 21, 2026)](#1-swaggeropenapi-input-adapter-february-21-2026)
  - [1.1 Overview](#11-overview)
  - [1.2 New MCP Tool](#12-new-mcp-tool)
  - [1.3 Step Strategies](#13-step-strategies)
  - [1.4 Sample Data Generation](#14-sample-data-generation)
  - [1.5 Capture Manifest](#15-capture-manifest)
  - [1.6 Safeguards](#16-safeguards)
  - [1.7 Files Created/Modified](#17-files-createdmodified)
- [2. HAR File Input Adapter (February 21, 2026)](#2-har-file-input-adapter-february-21-2026)
  - [2.1 Overview](#21-overview)
  - [2.2 New MCP Tool](#22-new-mcp-tool)
  - [2.3 Step Strategies](#23-step-strategies)
  - [2.4 Filtering](#24-filtering)
  - [2.5 Capture Manifest](#25-capture-manifest)
  - [2.6 Safeguards](#26-safeguards)
  - [2.7 Files Created/Modified](#27-files-createdmodified)

---

## 1. Swagger/OpenAPI Input Adapter (February 21, 2026)

### 1.1 Overview

A new input adapter enables conversion of Swagger 2.x / OpenAPI 3.x specification files into the canonical, step-aware network capture JSON used by the JMeter MCP pipeline. This provides a spec-first on-ramp — ideal when you have an API specification but no recorded traffic from Playwright or HAR files.

**Key Features:**
- Parses OpenAPI 3.x and Swagger 2.x specs (JSON and YAML)
- Auto-normalizes Swagger 2.x to OpenAPI 3.x internally
- Recursive `$ref` resolution with circular reference detection (max depth: 10)
- Synthetic request/response body generation from JSON Schema definitions
- Configurable step grouping strategies (tag, path, single_step)
- Handles relative server URLs via `base_url` parameter
- Deprecated endpoint filtering (off by default, configurable)
- Optional `faker` dependency for realistic sample data (graceful fallback)
- Generates `capture_manifest.json` for provenance tracking
- Schema validation before writing output
- Lazy import safeguard — JMeter MCP server starts even if the adapter fails to load

**Pipeline Position:**

```
Swagger/OpenAPI spec (.json / .yaml)
  └─→ convert_swagger_to_capture          ← New tool
        └─→ network_capture.json
              └─→ analyze_network_traffic     (existing)
                    └─→ generate_jmeter_script  (existing)
                          └─→ .jmx file
```

The adapter is an ETL step that feeds into the existing pipeline. All downstream tools (correlation analysis, script generation) work identically regardless of whether the input came from Playwright, a HAR file, or an OpenAPI spec.

---

### 1.2 New MCP Tool

One new tool was added to the JMeter MCP server:

| Tool | Purpose |
|------|---------|
| `convert_swagger_to_capture` | Convert a Swagger/OpenAPI spec to network capture JSON for JMeter script generation |

#### convert_swagger_to_capture

```python
convert_swagger_to_capture(
    test_run_id: str,              # Unique identifier for the test run
    spec_path: str,                # Full path to the spec file (.json / .yaml)
    base_url: str = "",            # Base URL (required if spec has relative server URL)
    step_strategy: str = "tag",    # tag / path / single_step
    include_deprecated: bool = False  # Whether to include deprecated endpoints
) -> dict
```

**Returns:**
```json
{
  "status": "OK",
  "message": "OpenAPI spec converted. Network capture saved to: <path>",
  "test_run_id": "swagger-smoke-01",
  "network_capture_path": "artifacts/swagger-smoke-01/jmeter/network-capture/network_capture_20260221_190509.json",
  "error": null
}
```

**Error handling:**
- `FileNotFoundError` — Spec file does not exist
- `ValueError` — Invalid JSON/YAML, unrecognized format, no paths, relative server URL without `base_url`, no usable operations
- Generic `Exception` — Unexpected errors (logged with full message)

---

### 1.3 Step Strategies

The adapter groups API endpoints into logical steps that become JMeter Transaction Controllers:

| Strategy | Behavior | Best For |
|----------|----------|----------|
| `tag` (default) | Groups by OpenAPI `tags` array | Well-organized specs with meaningful tags |
| `path` | Groups by first meaningful path segment | Specs where path structure reflects logical grouping |
| `single_step` | All endpoints in one step | Small specs, or when manual reorganization is planned |

---

### 1.4 Sample Data Generation

The adapter generates synthetic values for path parameters, query parameters, header parameters, request bodies, and response bodies based on JSON Schema definitions.

**Priority order:**

| Priority | Source | Example |
|----------|--------|---------|
| 1 | `example` field | Use as-is |
| 2 | `enum` field | First enum value |
| 3 | `format` field | `uuid` → `"550e8400-..."`, `date-time` → `"2026-01-15T10:30:00Z"` |
| 4 | `type` fallback | `"string"` → `"sample_string"`, `"integer"` → `1` |

**Special handling:**
- `additionalProperties` maps → generates `{"key1": "value1"}`
- Arrays → single-element array with a sample item
- `readOnly` properties → skipped in request bodies, included in responses
- `allOf` → merged; `oneOf`/`anyOf` → first option used
- Circular `$ref` → stops recursion, inserts `{}`

---

### 1.5 Capture Manifest

Each conversion generates a `capture_manifest.json` alongside the network capture file:

```json
{
  "source_type": "openapi",
  "source_file": "swagger.json",
  "conversion_tool": "convert_swagger_to_capture",
  "conversion_timestamp": "2026-02-22T00:05:09.208788",
  "step_strategy": "tag",
  "operations_total": 30,
  "operations_deprecated_skipped": 1,
  "operations_captured": 29,
  "spec_version": "3.0.1",
  "spec_title": "Example.DocumentFileService.WebSvc",
  "base_url": "https://example.com/file-svc"
}
```

---

### 1.6 Safeguards

| # | Safeguard | Description |
|---|-----------|-------------|
| 1 | **Lazy import** | `swagger_adapter.py` is imported inside a `try/except` in `jmeter.py`. If the import fails, the MCP server starts normally and returns an informative error when the tool is called. |
| 2 | **No coupling to existing modules** | Utility functions (`_create_step_metadata`, `_write_step_network_capture`, etc.) are duplicated — consistent with the HAR adapter pattern. |
| 3 | **Schema validation** | Output is validated against the canonical network capture schema before writing to disk. |
| 4 | **File size guard** | Spec files > 10 MB trigger a warning. Files > 50 MB are rejected. |
| 5 | **Circular $ref detection** | Tracks visited references per-branch with a max depth of 10 to prevent infinite recursion. |

---

### 1.7 Files Created/Modified

#### New Files

| File | Description |
|------|-------------|
| `jmeter-mcp/services/swagger_adapter.py` | Swagger/OpenAPI adapter module — parsing, normalization, $ref resolution, sample generation, grouping, conversion, validation, manifest |

#### Modified Files

| File | Changes |
|------|---------|
| `jmeter-mcp/jmeter.py` | Added lazy import for `swagger_adapter`, registered `convert_swagger_to_capture` MCP tool |
| `jmeter-mcp/README.md` | Added Swagger adapter to features, tool table, project structure; moved from "future" to implemented |

#### Artifacts Output

```
artifacts/<test_run_id>/jmeter/
├── network-capture/
│   ├── network_capture_<timestamp>.json    # Converted network traffic
│   └── capture_manifest.json               # Provenance metadata (source_type: "openapi")
└── ai-generated_script_<timestamp>.jmx     # After generate_jmeter_script
```

---

### Example Smoke Test Results:

| Test | Spec File | Operations Total | Deprecated Skipped | Captured | Steps | Tags |
|------|-----------|------------------|--------------------|----------|-------|------|
| swagger-smoke-01 | `swagger.json` (OpenAPI 3.0.1, 76 KB) | 30 | 1 | 29 | 6 | Admin, Blobs, Download, Metadata, Sas, Trash |

---

## 2. HAR File Input Adapter (February 21, 2026)

### 2.1 Overview

A new input adapter enables conversion of HAR (HTTP Archive) files into the canonical, step-aware network capture JSON used by the JMeter MCP pipeline. This provides an alternative on-ramp to the existing Playwright-based capture workflow — ideal when users already have a recorded HAR file from Chrome DevTools, proxy tools (Charles, Fiddler, mitmproxy), or Postman.

**Key Features:**
- Converts HAR 1.2 files to the same network capture JSON format used by `capture_network_traffic`
- Configurable step grouping strategies (auto, page, time_gap, single_step)
- Reuses existing `config.yaml` domain filtering and exclusion rules
- Configurable HTTP/2 pseudo-header stripping
- Generates a `capture_manifest.json` for provenance tracking
- File size safeguards (warn at 50 MB, reject at 200 MB)
- Schema validation before writing output
- Lazy import safeguard — JMeter MCP server starts even if the adapter fails to load

**Pipeline Position:**

```
HAR file (.har)
  └─→ convert_har_to_capture          ← New tool
        └─→ network_capture.json
              └─→ analyze_network_traffic     (existing)
                    └─→ generate_jmeter_script  (existing)
                          └─→ .jmx file
```

The adapter is an ETL step that feeds into the existing pipeline. All downstream tools (correlation analysis, script generation) work identically regardless of whether the input came from Playwright or a HAR file.

---

### 2.2 New MCP Tool

One new tool was added to the JMeter MCP server:

| Tool | Purpose |
|------|---------|
| `convert_har_to_capture` | Convert a HAR file to network capture JSON for JMeter script generation |

#### convert_har_to_capture

```python
convert_har_to_capture(
    test_run_id: str,              # Unique identifier for the test run
    har_path: str,                 # Full path to the HAR file
    step_strategy: str = "auto",   # auto / page / time_gap / single_step
    time_gap_threshold_ms: int = 3000  # Gap threshold for time_gap strategy
) -> dict
```

**Returns:**
```json
{
  "status": "OK",
  "message": "HAR file converted. Network capture saved to: <path>",
  "test_run_id": "har-smoke-01",
  "network_capture_path": "artifacts/har-smoke-01/jmeter/network-capture/network_capture_20260221_140628.json",
  "error": null
}
```

**Error handling:**
- `FileNotFoundError` — HAR file does not exist
- `ValueError` — Invalid JSON, missing `log`/`entries` keys, file too large, no usable entries after filtering
- Generic `Exception` — Unexpected errors (logged with full message)

---

### 2.3 Step Strategies

The adapter groups HAR entries into logical steps that become JMeter Transaction Controllers:

| Strategy | Behavior | Best For |
|----------|----------|----------|
| `auto` (default) | Uses `page` if HAR has `pageref` fields, else `time_gap` | General use |
| `page` | Groups by HAR `pageref`, using page titles as labels | Browser DevTools exports |
| `time_gap` | Splits when gap between requests exceeds threshold | Proxy tool exports |
| `single_step` | All entries in one step | API recordings, manual reorganization |

**Page label extraction:** For the `page` strategy, the adapter extracts readable labels from page titles (which are typically full URLs) by parsing hostname + first path segment. For example, `https://app.example.com/dashboard/settings?tab=profile` becomes `app.example.com/dashboard`.

---

### 2.4 Filtering

The adapter applies the following filters automatically:

| Filter | What It Removes |
|--------|----------------|
| OPTIONS requests | CORS preflight requests |
| Binary content types | `image/*`, `font/*`, `video/*`, `audio/*`, `application/octet-stream` |
| Non-HTTP schemes | Data URIs, WebSocket, blob URLs |
| Failed requests | Status 0 or -1 (aborted/failed) |
| Excluded domains | Domains listed in `config.yaml` `network_capture.exclude_domains` |

URL-based filtering delegates to the existing `network_capture.should_capture_url()` function, ensuring consistent behavior with the Playwright-based capture workflow.

---

### 2.5 Capture Manifest

Each conversion generates a `capture_manifest.json` alongside the network capture file:

```json
{
  "source_type": "har",
  "source_file": "recording.har",
  "conversion_tool": "convert_har_to_capture",
  "conversion_timestamp": "2026-02-21T19:06:28.405623",
  "step_strategy": "page",
  "entries_total": 61,
  "entries_filtered": 45,
  "entries_captured": 16,
  "har_version": "1.2",
  "har_creator": "WebInspector"
}
```

This provides full provenance — source file, strategy used, and a breakdown of how many entries were captured vs. filtered.

---

### 2.6 Safeguards

Four safeguards were implemented to ensure the adapter integrates safely:

| # | Safeguard | Description |
|---|-----------|-------------|
| 1 | **Lazy import** | `har_adapter.py` is imported inside a `try/except` in `jmeter.py`. If the import fails, the MCP server starts normally and returns an informative error when the tool is called. |
| 2 | **No coupling to existing modules** | Utility functions (`_create_step_metadata`, `_write_step_network_capture`, etc.) are duplicated rather than importing from `playwright_adapter.py` private internals. Shared extraction planned for Phase 2. |
| 3 | **Schema validation** | Output is validated against the canonical network capture schema before writing to disk. Missing fields or type mismatches raise `ValueError` with descriptive messages. |
| 4 | **File size guard** | HAR files > 50 MB trigger a warning. Files > 200 MB are rejected with a clear error message. |

---

### 2.7 Files Created/Modified

#### New Files

| File | Description |
|------|-------------|
| `jmeter-mcp/services/har_adapter.py` | HAR adapter module — parsing, filtering, grouping, conversion, validation, manifest |
| `docs/har_adapter_guide.md` | User-facing guide for Performance Test Engineers |

#### Modified Files

| File | Changes |
|------|---------|
| `jmeter-mcp/jmeter.py` | Added lazy import for `har_adapter`, registered `convert_har_to_capture` MCP tool |
| `jmeter-mcp/README.md` | Added HAR adapter to features, tool table, project structure, artifacts structure; moved HAR from "future" to implemented |
| `docs/README.md` | Added HAR Adapter Guide to documentation index |

#### Artifacts Output

```
artifacts/<test_run_id>/jmeter/
├── network-capture/
│   ├── network_capture_<timestamp>.json    # Converted network traffic
│   └── capture_manifest.json               # Provenance metadata
└── ai-generated_script_<timestamp>.jmx     # After generate_jmeter_script
```

---

## 3. Centralized SLA Configuration

### 3.1 Overview

All SLA (Service Level Agreement) thresholds are now defined in a single YAML file (`slas.yaml`) instead of being scattered across `config.yaml` settings and hardcoded values in Python code. This refactoring introduces per-profile defaults, per-API overrides via pattern matching, configurable percentile metrics (P90/P95/P99), and configurable error rate thresholds at every level.

**The core problem solved:**
- SLA thresholds were defined in multiple places (`config.yaml`, hardcoded `5000` in code)
- All APIs shared a single global SLA threshold
- SLA compliance was incorrectly checked against average response time instead of percentile

**What changed:**
- New `slas.yaml` file is the single source of truth for all SLA definitions
- Per-API SLA resolution using three-level pattern matching hierarchy
- SLA compliance now correctly evaluates against the configured percentile (P90 by default)
- All hardcoded SLA values (`5000`) removed from Python code and YAML configs
- If `slas.yaml` is missing, analysis fails immediately with a clear error (no silent fallbacks)

> See the full [SLA Configuration Guide](../sla_configuration_guide.md) for detailed usage instructions.

### 3.2 SLA Configuration File (slas.yaml)

The configuration supports a file-level default and multiple named SLA profiles:

```yaml
version: "1.0"

# File-level default (used when no sla_id is provided)
default_sla:
  response_time_sla_ms: 5000
  sla_unit: "P90"
  error_rate_threshold: 1.0

# Named SLA profiles
slas:
  - id: "order_management"
    description: "Order Management Service APIs"
    default_sla:
      response_time_sla_ms: 5000
      sla_unit: "P90"
      error_rate_threshold: 1.0
    api_overrides:
      - pattern: "*/orders/export*"
        response_time_sla_ms: 10000
        reason: "Bulk export endpoint"
      - pattern: "*/oauth/token*"
        response_time_sla_ms: 500
        reason: "Critical auth path"
```

**Configuration hierarchy** (most specific wins):
1. `api_overrides` pattern match → per-API threshold
2. Profile `default_sla` → profile-level default
3. File-level `default_sla` → global fallback

### 3.3 Three-Level Pattern Matching

API overrides use glob-style patterns evaluated in most-specific-first order:

| Priority | Pattern Type | Example | Matches |
|----------|-------------|---------|---------|
| 1 (highest) | Full JMeter label | `TC01_TS02_/api/orders/export` | Exact label |
| 2 | Test Case + Test Step | `TC01_TS02_*` | All APIs under that step |
| 3 (broadest) | Test Case only | `TC01_*` | All steps and APIs under that case |

### 3.4 SLA Compliance Fix (Average → Percentile)

**Before:** SLA compliance was evaluated against *average* response time, which masks tail latency issues.

**After:** SLA compliance is evaluated against the configured percentile (P90 by default, configurable via `sla_unit`).

### 3.5 MCP Tool Changes

Three PerfAnalysis MCP tools now accept an optional `sla_id` parameter:

| Tool | New Parameter | Purpose |
|------|--------------|---------|
| `analyze_test_results` | `sla_id: Optional[str]` | Per-API SLA compliance during aggregate analysis |
| `correlate_test_results` | `sla_id: Optional[str]` | SLA threshold for temporal correlation analysis |
| `identify_bottlenecks` | `sla_id: Optional[str]` | Per-endpoint SLA in bottleneck detection |

### 3.6 Files Created/Modified

#### Files Created
| File | Purpose |
|------|---------|
| `perfanalysis-mcp/slas.example.yaml` | Annotated SLA configuration template |
| `perfanalysis-mcp/utils/sla_config.py` | SLA config loader, schema validator, three-level resolver, and pattern validator |
| `docs/sla_configuration_guide.md` | Comprehensive SLA configuration documentation |

#### Files Modified
| File | Changes |
|------|---------|
| `perfanalysis-mcp/utils/statistical_analyzer.py` | Replaced global SLA with per-API resolver; fixed avg→percentile compliance check |
| `perfanalysis-mcp/services/bottleneck_analyzer.py` | Rewrote `_get_sla_threshold()` to use SLA resolver |
| `perfanalysis-mcp/services/performance_analyzer.py` | Added `sla_id` to all analysis functions |
| `perfanalysis-mcp/perfanalysis.py` | Added `sla_id` parameter to MCP tools |
| `perfreport-mcp/services/report_generator.py` | Removed hardcoded `5000` fallbacks |
| `perfreport-mcp/services/comparison_report_generator.py` | Replaced hardcoded `"5000"` with per-API threshold |

---

## 4. JMeter Log Analysis Tool

### 4.1 Overview

A new `analyze_jmeter_log` tool performs deep analysis of JMeter and BlazeMeter log files, providing granular error grouping, first-occurrence request/response details, and optional JTL correlation.

### 4.2 New MCP Tool

| Tool | Purpose |
|------|---------|
| `analyze_jmeter_log` | Deep analysis of JMeter/BlazeMeter log files with error grouping, first-occurrence details, and JTL correlation |

### 4.3 Key Capabilities

- **Multi-line block parsing**: Handles JSR223 Post-Processor verbose output
- **Granular error grouping**: Groups by composite signature (category + response code + endpoint + normalized message hash)
- **Message normalization**: Replaces UUIDs, emails, IPs, timestamps with placeholders for deduplication
- **First-occurrence capture**: Preserves the first error message, request body, and response body for each group
- **JTL correlation**: Enriches error groups with JTL response codes and elapsed times
- **Multi-file discovery**: Discovers all `.log` files in the source directory

### 4.4 Files Created/Modified

#### Files Created
| File | Purpose |
|------|---------|
| `jmeter-mcp/services/jmeter_log_analyzer.py` | Core service module |
| `jmeter-mcp/utils/log_utils.py` | Low-level log parsing utilities |

#### Files Modified
| File | Changes |
|------|---------|
| `jmeter-mcp/jmeter.py` | Registered `analyze_jmeter_log` MCP tool |
| `jmeter-mcp/utils/file_utils.py` | Added 6 new I/O helper functions |
| `jmeter-mcp/config.example.yaml` | Added `jmeter_log` configuration section |

---

## 5. Bottleneck Analyzer v0.2

### 5.1 Overview

The `identify_bottlenecks` tool has been significantly upgraded to deliver accurate, actionable bottleneck detection with dramatically reduced false positives. Key improvements include sustained degradation validation, outlier filtering, timestamps in findings, multi-factor severity classification, two-phase analysis architecture, and raw metrics fallback for environments without Kubernetes resource limits.

**Core principle:** A bottleneck is a *sustained, non-recovering* degradation pattern. If the system recovers, it was a transient event, not a bottleneck.

### 5.2 Key Improvements

1. **Sustained Degradation Validation**: Degradation must persist (configurable `persistence_ratio`, default 60%) to be classified as a bottleneck
2. **Outlier Filtering**: Rolling median smoothing with MAD-based outlier detection
3. **Timestamps in Findings**: Every finding includes `onset_timestamp`, `onset_bucket_index`, `test_elapsed_seconds`
4. **Multi-Tier Accuracy**: Per-endpoint baseline with inherently-slow vs. load-induced distinction
5. **Multi-Factor Severity**: Composite scoring across delta magnitude, persistence, scope, and classification
6. **Two-Phase Architecture**: Phase 1 (performance degradation from JTL), Phase 2a (infrastructure cross-reference), Phase 2b (capacity risk detection)
7. **Capacity Risk Detection**: Infrastructure stress with healthy latency as early warnings
8. **Raw Metrics Fallback**: Relative-from-baseline thresholds when K8s limits are missing

### 5.3 Files Created/Modified

| File | Purpose/Changes |
|------|---------|
| `perfanalysis-mcp/services/bottleneck_analyzer.py` | Core bottleneck analysis engine (created) |
| `perfanalysis-mcp/perfanalysis.py` | Registered `identify_bottlenecks` MCP tool |
| `perfanalysis-mcp/config.example.yaml` | Added `bottleneck_analysis` configuration section |

---

## 6. Multi-Session Artifact Handling

### 6.1 Overview

When a BlazeMeter test run uses multiple load generators, each engine produces its own `artifacts.zip`. A new unified `process_session_artifacts` tool handles both single-session and multi-session runs through a single consolidated tool with built-in retry, idempotent re-runs, and JTL concatenation.

### 6.2 New MCP Tool

| Tool | Purpose |
|------|---------|
| `process_session_artifacts` | Downloads, extracts, and processes artifact ZIPs for all sessions of a BlazeMeter run |

**Deprecated Tools:** `download_artifacts_zip`, `extract_artifact_zip`, `process_extracted_files`

### 6.3 Files Created/Modified

#### Files Created
| File | Purpose |
|------|---------|
| `blazemeter-mcp/services/artifact_manager.py` | Session manifest management, JTL concatenation, download-with-retry |

#### Files Modified
| File | Changes |
|------|---------|
| `blazemeter-mcp/services/blazemeter_api.py` | Added `session_artifact_processor` orchestration |
| `blazemeter-mcp/blazemeter.py` | Added `process_session_artifacts`; deprecated old tools |
| `perfanalysis-mcp/services/log_analyzer.py` | Glob pattern for multi-session log discovery |

---

*Last Updated: February 25, 2026*
