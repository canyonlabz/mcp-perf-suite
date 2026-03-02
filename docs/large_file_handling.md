# Large File Handling in PerfAnalysis MCP

**Last Updated:** February 27, 2026

This document explains how the PerfAnalysis MCP handles large test result files (JTL/CSV), the design decisions behind the current approach, and the known limitations that performance test engineers should be aware of.

---

## Background

JMeter/BlazeMeter test runs produce JTL (JMeter Test Log) files in CSV format. For large-scale tests — high concurrency, long durations, or distributed multi-engine execution — these files can grow to hundreds of megabytes with millions of rows.

**Example from production usage:**

| Test Configuration | Value |
|---|---|
| Concurrent Users | 400 (4 engines × 100 threads) |
| Test Duration | ~60 minutes |
| JTL File Size | 450 MB |
| Total Rows | ~2,500,000 |
| JTL Columns | 16+ |

Without optimisation, loading this file with `pandas.read_csv()` consumed 2–3 GB of RAM (pandas typically uses 5–8x the raw CSV size due to object/string overhead), causing the MCP server process to crash.

---

## Current Approach: Column Selection + Type Optimisation

The PerfAnalysis MCP uses three techniques to reduce memory consumption when loading large JTL files:

### 1. Column Selection (`usecols`)

JTL files contain 16+ columns, but the analysis only requires a subset:

| Column | Used By |
|--------|---------|
| `timeStamp` | Time bucketing, temporal analysis |
| `elapsed` | Response time calculations (P50, P90, P95, avg) |
| `label` | Per-endpoint analysis, SLA resolution |
| `responseCode` | JTL format validation |
| `success` | Error rate calculations |
| `allThreads` | Concurrency tracking |
| `Hostname` | Multi-engine detection and correction |

By specifying `usecols`, pandas skips parsing the remaining ~9 columns entirely. This alone reduces memory by approximately 50–60%.

### 2. Category Dtypes for Low-Cardinality Strings

Columns like `label`, `responseCode`, and `Hostname` contain a small number of unique values repeated across millions of rows. For example:

- `label`: 15 unique API endpoint names × 2.5M rows
- `Hostname`: 4 unique engine hostnames × 2.5M rows
- `responseCode`: ~5 unique codes × 2.5M rows

Using pandas `category` dtype, each unique string is stored **once**, and every row stores a 4-byte integer code instead of a full Python string object. This is the single largest memory optimisation for JTL files.

### 3. Explicit Dtype Map

Specifying dtypes upfront eliminates pandas' type inference pass, which otherwise requires reading the entire file before deciding column types:

```python
dtype_map = {
    "timeStamp": "int64",
    "elapsed": "int64",
    "label": "category",
    "responseCode": "category",
    "success": "str",
    "allThreads": "int32",
    "Hostname": "category",  # if present
}
```

**Note on `int32` for `allThreads`:** Thread counts in performance tests are realistically in the range of 1–10,000. The `int32` max of 2,147,483,647 is more than sufficient. Values approaching this limit would indicate a misconfiguration or security incident, not a legitimate test.

### Memory Estimates

For a ~2.5M row JTL file:

| Approach | Estimated Memory |
|----------|-----------------|
| Bare `pd.read_csv()` (all columns, default dtypes) | ~2–3 GB |
| With `usecols` + `category` + explicit dtypes | ~100–150 MB |

This represents a **15–20x reduction** in memory usage.

---

## Configurable Row Limit (`max_jtl_rows`)

As an additional safety valve, the bottleneck analyser supports a configurable row limit:

```yaml
# config.yaml > perf_analysis > bottleneck_analysis
bottleneck_analysis:
  max_jtl_rows: null    # null = load all rows (default)
                         # Set to e.g. 2000000 to cap memory on very large files
```

When set, only the first N rows of the JTL file are loaded. This trades completeness for stability on memory-constrained systems. When the limit is applied, a log message indicates how many rows were loaded.

---

## Why Not Chunked Processing?

A common recommendation for large CSV files is to use `pd.read_csv(chunksize=...)` to process the file in chunks and discard each chunk after aggregation. While this approach works for simple aggregations (sums, counts, means), the PerfAnalysis MCP requires operations that need the full dataset in memory:

### 1. Exact Percentile Calculations

The bottleneck analyser computes P50, P90, and P95 latency per time bucket. Exact percentiles require access to all individual data points within each bucket — they cannot be accurately computed from chunk-level aggregates. Approximate algorithms (such as t-digest) exist but introduce complexity and precision trade-offs that are unnecessary given the memory optimisations above.

### 2. Multi-Engine Concurrency Correction

In distributed BlazeMeter tests, the `allThreads` column reports per-engine thread counts. Computing true concurrency requires grouping by `Hostname` within each time bucket and summing across engines. This cross-engine grouping within time windows requires the full dataset.

### 3. Per-Endpoint Analysis

The multi-tier bottleneck analysis filters the full dataset by `label` (endpoint name) and performs independent time-bucketing, baseline computation, and degradation detection per endpoint. Chunked processing would require maintaining state across chunks for each endpoint.

### When Chunked Processing Would Be Appropriate

If the MCP Perf Suite needed to routinely handle JTL files in the **multi-gigabyte** range (10M+ rows), the architecture would need to shift toward:

- **Streaming aggregation** with approximate percentile algorithms (t-digest, HDR Histogram)
- **DuckDB or Polars** as a pandas replacement — both handle out-of-core processing natively
- **Pre-aggregation at the source** — having BlazeMeter/JMeter produce per-bucket summaries

For the current target use case (JTL files up to ~500 MB / ~3M rows), column selection and type optimisation provide sufficient memory reduction without sacrificing analytical accuracy.

---

## Affected Modules

The optimised loading pattern is applied in:

| File | Function | Purpose |
|------|----------|---------|
| `perfanalysis-mcp/services/bottleneck_analyzer.py` | `_load_jtl()` | Bottleneck analysis — loads raw JTL for time-bucket analysis |
| `perfanalysis-mcp/utils/statistical_analyzer.py` | `load_and_process_performance_data()` | Temporal correlation analysis — loads JTL for performance/infrastructure correlation |

---

## Recommendations for Performance Test Engineers

1. **JTL files under 200 MB** — No special consideration needed. Default settings work well.

2. **JTL files 200–500 MB** — The optimised loading handles these without issues. Monitor MCP server memory if running on constrained systems (< 4 GB available RAM).

3. **JTL files over 500 MB** — Consider setting `max_jtl_rows` in `config.yaml` to cap the dataset. Alternatively, use JMeter's built-in result file splitting or BlazeMeter's session-level exports to keep individual files manageable.

4. **Distributed tests (multiple engines)** — The analyser automatically detects multi-engine JTL files via the `Hostname` column and corrects concurrency calculations. No manual configuration is needed.
