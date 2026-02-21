# MCP Performance Suite - Changelog (February 2026)

This document contains all enhancements and new features added to the MCP Performance Suite during February 2026.

---

## Table of Contents

- [1. HAR File Input Adapter (February 21, 2026)](#1-har-file-input-adapter-february-21-2026)
  - [1.1 Overview](#11-overview)
  - [1.2 New MCP Tool](#12-new-mcp-tool)
  - [1.3 Step Strategies](#13-step-strategies)
  - [1.4 Filtering](#14-filtering)
  - [1.5 Capture Manifest](#15-capture-manifest)
  - [1.6 Safeguards](#16-safeguards)
  - [1.7 Files Created/Modified](#17-files-createdmodified)

---

## 1. HAR File Input Adapter (February 21, 2026)

### 1.1 Overview

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

### 1.2 New MCP Tool

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

### 1.3 Step Strategies

The adapter groups HAR entries into logical steps that become JMeter Transaction Controllers:

| Strategy | Behavior | Best For |
|----------|----------|----------|
| `auto` (default) | Uses `page` if HAR has `pageref` fields, else `time_gap` | General use |
| `page` | Groups by HAR `pageref`, using page titles as labels | Browser DevTools exports |
| `time_gap` | Splits when gap between requests exceeds threshold | Proxy tool exports |
| `single_step` | All entries in one step | API recordings, manual reorganization |

**Page label extraction:** For the `page` strategy, the adapter extracts readable labels from page titles (which are typically full URLs) by parsing hostname + first path segment. For example, `https://app.example.com/dashboard/settings?tab=profile` becomes `app.example.com/dashboard`.

---

### 1.4 Filtering

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

### 1.5 Capture Manifest

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

### 1.6 Safeguards

Four safeguards were implemented to ensure the adapter integrates safely:

| # | Safeguard | Description |
|---|-----------|-------------|
| 1 | **Lazy import** | `har_adapter.py` is imported inside a `try/except` in `jmeter.py`. If the import fails, the MCP server starts normally and returns an informative error when the tool is called. |
| 2 | **No coupling to existing modules** | Utility functions (`_create_step_metadata`, `_write_step_network_capture`, etc.) are duplicated rather than importing from `playwright_adapter.py` private internals. Shared extraction planned for Phase 2. |
| 3 | **Schema validation** | Output is validated against the canonical network capture schema before writing to disk. Missing fields or type mismatches raise `ValueError` with descriptive messages. |
| 4 | **File size guard** | HAR files > 50 MB trigger a warning. Files > 200 MB are rejected with a clear error message. |

---

### 1.7 Files Created/Modified

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

*Last Updated: February 21, 2026*
