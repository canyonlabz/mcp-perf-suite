# Artifacts Guide - How MCP Performance Suite Manages Test Data

## Why Artifacts Matter

The MCP Performance Suite is a **local-first** tool suite. There is no central database, no cloud storage backend, and no remote API for state management. All test data -- scripts, results, logs, analysis outputs, reports, and charts -- lives on your local filesystem in a single directory tree called the **artifacts folder**.

The artifacts folder is the shared contract between every MCP server in the suite. When one tool writes a file (e.g., JMeter MCP generates a JTL), another tool knows exactly where to find it (e.g., PerfAnalysis MCP reads the JTL for analysis). This works because every MCP server follows the same folder structure and naming conventions documented here.

If you delete the artifacts folder, you lose all test history. If you back it up, you preserve everything needed to reproduce analysis, regenerate reports, or compare test runs.

---

## Local-First Architecture

### No Database

The suite intentionally avoids databases. Test state is represented as files on disk:

- **JTL CSV files** hold raw sample-level performance data
- **JSON files** hold analysis results, correlation specs, and session manifests
- **Markdown and PNG files** hold reports and charts
- **JMX files** hold JMeter test scripts (with numbered backups for revision history)
- **YAML files** hold configuration (not stored in artifacts -- these live alongside each MCP server)

This means:

- **Nothing to install** beyond the MCP servers themselves and their Python dependencies
- **Nothing to migrate** when upgrading -- the file format is the API
- **Easy to share** -- zip an artifacts folder and hand it to a colleague
- **Easy to version control** -- commit an artifacts folder to Git for audit trails (though large JTLs are best kept in `.gitignore`)

### Local Execution

All MCP servers run on your local machine. JMeter runs headless locally. Playwright automates your local browser. The Streamlit UI reads from local files. The only external calls are to third-party APIs when you explicitly use them (BlazeMeter API, Datadog API, Confluence API).

This makes the suite well-suited for:

- Individual performance engineers running tests on their workstation
- CI/CD pipelines where the artifacts folder is a build artifact
- Air-gapped environments with no internet access (excluding the cloud-dependent MCPs)

---

## The `test_run_id`

Every test run in the suite is identified by a `test_run_id`. This is a user-provided string that becomes the folder name under `artifacts/`. It is the primary key for all operations.

**Examples of good test_run_ids:**

| Style | Example | When to use |
|-------|---------|-------------|
| Descriptive | `login_flow_baseline` | Manual exploratory testing |
| Sprint-based | `sprint_42_regression` | CI/CD or scheduled test cycles |
| Date-based | `2026-03-01-smoke` | Daily smoke tests |
| BlazeMeter run ID | `r-ext-65abc123` | Tests originated from BlazeMeter |

**Rules:**

- Every MCP tool that reads or writes artifacts requires a `test_run_id`
- If you don't provide one when using the AI HITL tools, the AI agent will ask for one (or generate a fallback in `YYYY-MM-DD-HH-MM-SS` format)
- The `test_run_id` must be filesystem-safe (no slashes, colons, or special characters)
- Reusing a `test_run_id` will overwrite previous results in that folder

---

## The `artifacts_path` Configuration

Every MCP server in the suite has an `artifacts_path` setting in its `config.yaml`:

```yaml
general:
  artifacts_path: ""
```

**Default behavior:** When left empty (the default), each MCP server resolves the artifacts path relative to the `mcp-perf-suite` root directory:

```
<mcp-perf-suite-root>/artifacts/
```

**Custom path:** Set an absolute path to store artifacts elsewhere:

```yaml
general:
  artifacts_path: "D:/perf-test-data/artifacts"
```

**Important:** If you override `artifacts_path`, you must set the same value in **every** MCP server's `config.yaml`. All servers must agree on where artifacts live, otherwise one server won't find another server's output.

The MCP servers that use `artifacts_path`:

| MCP Server | Reads From | Writes To |
|------------|-----------|-----------|
| **blazemeter-mcp** | - | `blazemeter/` subfolder |
| **jmeter-mcp** | `jmeter/` subfolder | `jmeter/` subfolder |
| **datadog-mcp** | - | `datadog/` subfolder |
| **perfanalysis-mcp** | `blazemeter/`, `jmeter/`, `datadog/` | `analysis/` subfolder |
| **perfreport-mcp** | `analysis/` | `reports/`, `charts/` subfolders |
| **confluence-mcp** | `reports/` | - (publishes to Confluence) |
| **streamlit-ui** | All subfolders | - (read-only display) |

---

## Directory Structure

Each `test_run_id` gets its own folder under `artifacts/`. The subfolders are organized by the MCP server or function that produces them:

```
artifacts/<test_run_id>/
│
├── blazemeter/                          # BlazeMeter MCP outputs
│   ├── test-results.csv                 # JTL (raw sample data) from BlazeMeter
│   ├── aggregate_performance_report.csv # Aggregate stats from BlazeMeter API
│   ├── jmeter.log                       # Single-session JMeter log
│   ├── jmeter-*.log                     # Multi-session JMeter logs (jmeter-1.log, etc.)
│   ├── public_report.json               # Public BlazeMeter report URL
│   └── sessions/
│       └── session_manifest.json        # Session download/processing state
│
├── jmeter/                              # JMeter MCP outputs
│   ├── ai-generated_script_*.jmx       # Generated JMeter script
│   ├── imported_*.jmx                   # Imported external JMX (if applicable)
│   ├── test-results.csv                 # JTL from headless execution
│   ├── aggregate_performance_report.csv # Aggregate stats from generate_aggregate_report
│   ├── results_tree.csv                 # View Results Tree listener output
│   ├── aggregate_report.csv             # Aggregate Report listener output
│   ├── <test_run_id>.log               # JMeter execution log
│   ├── <test_run_id>_summary.json      # Run summary metadata
│   ├── correlation_spec.json            # Correlation analysis output
│   ├── correlation_naming.json          # Variable naming for correlations
│   ├── backups/                         # Numbered JMX backups from HITL edits
│   │   ├── script-000001.jmx           # State before first edit
│   │   └── script-000002.jmx           # State before second edit
│   ├── network-capture/                 # Playwright/HAR/Swagger capture data
│   │   ├── network_capture_*.json       # Network traffic in canonical format
│   │   └── capture_manifest.json        # Provenance metadata (source, timestamp)
│   └── testdata_csv/                    # CSV test data files
│       └── environment.csv              # Environment-specific variables
│
├── datadog/                             # Datadog MCP outputs
│   ├── host_metrics_*.csv               # Host-based infrastructure metrics
│   ├── k8s_metrics_*.csv                # Kubernetes-based infrastructure metrics
│   └── logs_*.csv                       # Application/infrastructure logs
│
├── analysis/                            # PerfAnalysis MCP outputs
│   ├── performance_analysis.json        # Core performance analysis results
│   ├── infrastructure_analysis.json     # Infrastructure utilization analysis
│   ├── correlation_analysis.json        # Cross-correlation (perf + infra)
│   ├── bottleneck_analysis.json         # Bottleneck detection results
│   ├── bottleneck_analysis.csv          # Bottleneck data in tabular form
│   ├── bottleneck_analysis.md           # Bottleneck report (human-readable)
│   ├── *_log_analysis.json              # JMeter/BlazeMeter log analysis
│   ├── *_log_analysis.csv              # Log analysis in tabular form
│   └── *_log_analysis.md               # Log analysis report
│
├── reports/                             # PerfReport MCP outputs
│   ├── performance_report_<id>.md       # Markdown performance report
│   └── report_metadata_<id>.json        # Report metadata (template, revision)
│
└── charts/                              # PerfReport MCP chart images
    ├── CPU_UTILIZATION_MULTILINE.png
    ├── MEMORY_UTILIZATION_MULTILINE.png
    └── RESP_TIME_P90_VUSERS_DUALAXIS.png
```

---

## Vendor Folders: `blazemeter/` vs `jmeter/`

Test results can originate from two different sources:

- **`blazemeter/`** -- Tests run in the cloud via BlazeMeter. The BlazeMeter MCP downloads session artifacts (JTLs, logs) from the BlazeMeter API and places them here.
- **`jmeter/`** -- Tests created and run locally via the JMeter MCP. This includes AI-generated scripts (from Playwright, HAR, or Swagger pipelines), imported external scripts, and headless execution results.

These folders are intentionally separate. They represent different sources of truth and should never be mixed. A single `test_run_id` may have both folders if the same test scenario was run both in BlazeMeter and locally.

### Consumer-Side Fallback

Since downstream tools (PerfAnalysis, Streamlit UI) need to read test results regardless of their source, they implement a fallback pattern:

1. Check `blazemeter/test-results.csv` first
2. If not found, check `jmeter/test-results.csv`

This fallback is implemented in:

| Consumer | File |
|----------|------|
| Streamlit UI | `streamlit-ui/src/services/artifact_loader.py` |
| PerfAnalysis - performance analyzer | `perfanalysis-mcp/services/performance_analyzer.py` |
| PerfAnalysis - statistical analyzer | `perfanalysis-mcp/utils/statistical_analyzer.py` |
| PerfAnalysis - bottleneck analyzer | `perfanalysis-mcp/services/bottleneck_analyzer.py` |

If you build a new tool or MCP server that reads `test-results.csv` or `aggregate_performance_report.csv`, follow this same fallback pattern.

---

## How the AI HITL Tools Use Artifacts

The JMeter HITL (Human-in-the-Loop) tools -- `analyze_jmeter_script`, `add_jmeter_component`, `edit_jmeter_component` -- use the `jmeter/` subfolder as their working directory. Everything they need is in `artifacts/<test_run_id>/jmeter/`.

### What the HITL tools read

- The JMX script to analyze or edit (auto-discovers `ai-generated_script_*` or uses an explicit `jmx_filename`)
- The existing backup history (to determine the next backup number)

### What the HITL tools write

- **Backups**: Before every mutation, a numbered copy is saved to `backups/`. This is the revision history -- no database needed, just files.
- **Modified JMX**: The edited script is saved in-place (same filename, same location)

### The artifacts folder as state

Since there is no database, the artifacts folder **is** the state. When the AI agent runs `analyze_jmeter_script`, it reads the current JMX from the artifacts folder. When it runs `add_jmeter_component`, it reads the latest version, creates a backup, applies the change, and writes the new version back. The numbered backup files in `backups/` serve as the commit log.

This means:

- **Current state** = the JMX file at `artifacts/<test_run_id>/jmeter/<script>.jmx`
- **History** = the numbered backups in `artifacts/<test_run_id>/jmeter/backups/`
- **Rollback** = copy any backup file back over the working JMX

### External JMX scripts

When working with a JMX that was not created by the suite (e.g., an existing script from JMeter GUI), the script must be copied into the artifacts folder before the HITL tools can operate on it. The convention is to prefix the filename with `imported_` to distinguish it from AI-generated scripts.

See the [JMeter HITL User Guide](jmeter_hitl_user_guide.md) for the full workflow, including requirements and best practices.

---

## Key Files and Their Roles

| File | Producer | Purpose | Consumed By |
|------|----------|---------|-------------|
| `test-results.csv` | BlazeMeter MCP or JMeter MCP | Raw JTL sample data (timestamps, response times, errors) | PerfAnalysis, Bottleneck Analyzer, Streamlit UI |
| `aggregate_performance_report.csv` | BlazeMeter MCP or JMeter MCP | Per-label aggregate stats (avg, P90, P95, error %) | PerfAnalysis, Streamlit UI |
| `performance_analysis.json` | PerfAnalysis MCP | Full analysis results with SLA compliance | PerfReport, Streamlit KPI Dashboard |
| `bottleneck_analysis.json` | PerfAnalysis MCP | Bottleneck detection findings | PerfReport |
| `correlation_analysis.json` | PerfAnalysis MCP | Cross-correlation of perf + infra metrics | PerfReport |
| `results_tree.csv` | JMeter listener (built-in) | Detailed per-sample data from View Results Tree | Manual inspection |
| `aggregate_report.csv` | JMeter listener (built-in) | Summary stats from Aggregate Report listener | Manual inspection |
| `performance_report_*.md` | PerfReport MCP | Final Markdown report | Confluence MCP, manual review |

**Note on listener files vs tool outputs:** JMeter has built-in listeners (View Results Tree, Aggregate Report) that write their own CSV files during execution. These are separate from the JTL (`test-results.csv`) and aggregate report (`aggregate_performance_report.csv`) produced by the MCP tools. The MCP tool outputs are the canonical source for downstream analysis. The listener files are useful for manual inspection and debugging.

---

## JMX Backup Naming

When the HITL tools modify a JMX script, they create numbered backups before each change:

```
backups/<script_name>-000001.jmx    # Original before first edit
backups/<script_name>-000002.jmx    # State before second edit
backups/<script_name>-000003.jmx    # State before third edit
```

This mirrors the backup convention used by Apache JMeter itself. The backup count is configurable via `jmx_editing.max_backup_count` in `config.yaml`.

---

## Tips for Managing Artifacts

1. **Use meaningful `test_run_id` values.** You'll be searching through these folders months from now. `sprint_42_login_flow` is infinitely better than `test1`.

2. **Don't modify artifacts manually** (except for importing external JMX files). Let the tools manage their own output. Manual edits can break assumptions downstream.

3. **Back up the artifacts folder** if you need to preserve results long-term. A simple zip or tar is sufficient. Git works for small runs; use `.gitignore` for large JTLs.

4. **Keep `artifacts_path` consistent** across all MCP server configs. If one server writes to `/data/artifacts` and another reads from `./artifacts`, they won't find each other's files.

5. **Deleting a `test_run_id` folder** removes all data for that run -- scripts, results, analysis, reports, and charts. There is no undo (unless you have a backup).

6. **The Streamlit UI discovers test runs** by scanning subfolders under `artifacts/`. Each subfolder name becomes a selectable `test_run_id` in the KPI Dashboard dropdown.

---

## Future Considerations

The local-first architecture works well for individual engineers and small teams. As the suite evolves, potential enhancements include:

- **Cloud storage adapter**: Option to sync artifacts to S3, Azure Blob, or GCS for team sharing
- **Auto-import for HITL tools**: The MCP tools will accept external JMX paths directly and handle the copy into artifacts automatically (V2 enhancement)
- **Artifact retention policies**: Auto-cleanup of old test runs based on age or count
- **Artifact index**: A lightweight manifest at the `artifacts/` root level listing all test runs with metadata (dates, sources, status)

---

*Last Updated: March 1, 2026*
