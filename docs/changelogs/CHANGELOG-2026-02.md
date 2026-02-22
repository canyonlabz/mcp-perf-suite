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
  "spec_title": "PwC.NGA.DocumentFileService.WebSvc",
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

### Smoke Test Results

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

### Smoke Test Results

| Test | HAR File | Entries Total | Filtered | Captured | Steps | JMX Generated |
|------|----------|---------------|----------|----------|-------|---------------|
| har-smoke-01 | `central-acquisitionhub-uat.pwc.com.har` (2.5 MB) | 42 | 0 | 42 | 8 | Yes (270 KB) |
| har-smoke-02 | `nga-perf.pwcglb.com-WITH-MJS.har` (6.0 MB) | 61 | 41 | 20 | 1 | Yes |
| har-smoke-03 | `nga-perf.pwcglb.com-WITH-MJS.har` (after config update) | 61 | 45 | 16 | 1 | Yes |

---

*Last Updated: February 22, 2026*
