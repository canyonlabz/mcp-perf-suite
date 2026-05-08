# PerfMemory Tools

Standalone CLI utilities for PerfMemory database maintenance and data quality.

These tools are designed to be run manually by a PTE or kicked off by Cursor/AI agents.
They operate directly on the PostgreSQL database and use the same `.env` configuration
as the PerfMemory MCP server.

---

## Available Tools

### `normalize_taxonomy.py`

Normalizes existing `system_under_test` values to canonical taxonomy names and backfills
empty `system_alias` fields. Optionally fixes `error_category` and `environment` drift.

**Prerequisites:**

- Python 3.10+
- `perfmemory-mcp/taxonomy.yaml` must exist (copy from `taxonomy.example.yaml` and customize)
- `perfmemory-mcp/.env` must exist with valid PostgreSQL credentials
- Database must be running and accessible

**Quick Start:**

```bash
# Navigate to the tools directory
cd perfmemory-mcp/tools

# Dry-run (default) — preview what would change, no modifications
python normalize_taxonomy.py

# Apply changes after reviewing dry-run output
python normalize_taxonomy.py --apply

# Also fix error_category and environment columns
python normalize_taxonomy.py --apply --fix-error-category --fix-environment

# Include Apache AGE graph normalization
python normalize_taxonomy.py --apply --include-graph

# Override database connection (defaults to ../.env)
python normalize_taxonomy.py --host localhost --port 5433 --db perfmemory
```

**CLI Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--apply` | Execute normalization (without this flag, runs in dry-run mode) | `false` |
| `--fix-error-category` | Also normalize `error_category` in `debug_attempts` | `false` |
| `--fix-environment` | Also normalize `environment` in `debug_sessions` | `false` |
| `--include-graph` | Also update Apache AGE graph (`Project.name`, `Attempt.project`) | `false` |
| `--taxonomy` | Path to taxonomy YAML file | `../taxonomy.yaml` |
| `--env-file` | Path to .env file for DB credentials | `../.env` |
| `--host` | PostgreSQL host (overrides .env) | — |
| `--port` | PostgreSQL port (overrides .env) | — |
| `--db` | PostgreSQL database name (overrides .env) | — |
| `--user` | PostgreSQL user (overrides .env) | — |
| `--password` | PostgreSQL password (overrides .env) | — |

**How Matching Works (3-Tier):**

1. **Exact match** — `system_under_test` matches a taxonomy application `name` or `alias` (case-insensitive)
2. **Contains match** — A taxonomy `name` or `alias` appears as a substring in the `system_under_test` value (e.g., "Shopping Portal (OSP) - Login Flow" matches alias "OSP")
3. **Unmatched** — Value doesn't match any taxonomy application; reported but not modified

**Logging:**

All output is printed to stdout and also written to a timestamped log file in `tools/logs/`:

```
tools/logs/normalize_20260507_223000.log
```

**Adaptability:**

This tool is designed to be modified for your team's needs. The matching logic is
clearly structured so you can add custom matching rules, adjust substring matching
thresholds, or add support for additional columns.

---

## Logs

Runtime log files are stored in the `logs/` subfolder. These files are gitignored
and will not be committed to the repository. Each tool generates timestamped log files
so you can review past runs.

---

## Dependencies

All dependencies are already part of the PerfMemory MCP requirements:

- `psycopg2-binary` — PostgreSQL driver
- `python-dotenv` — .env file loading
- `PyYAML` — Taxonomy YAML parsing

No additional `pip install` is needed if you already have the PerfMemory MCP environment set up.
