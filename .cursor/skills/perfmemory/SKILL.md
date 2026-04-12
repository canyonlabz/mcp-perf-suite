---
name: perfmemory
description: >-
  Manage the PerfMemory lessons-learned layer — search for past fixes before debugging,
  store debug sessions and attempts during debugging, and ingest existing knowledge from
  debug manifests or lessons-learned documents. Use when the user mentions perfmemory,
  lessons learned, debug memory, ingesting debug manifests, or searching for past fixes.
---

# PerfMemory — Lessons Learned Memory Layer

## When to Use This Skill

- User asks to search memory for past fixes before debugging
- User asks to store a debug session or attempt in memory
- User asks to ingest a debug manifest or lessons-learned document into memory
- User asks to review, verify, or archive stored lessons
- User asks for memory statistics or session details
- The `jmeter-debugging` skill references PerfMemory integration steps

---

## Reference

### What PerfMemory Does

PerfMemory is a persistent memory layer backed by PostgreSQL + pgvector + Apache AGE.
It stores structured debug sessions, attempts, and vector embeddings of symptoms so
AI agents can recall past fixes via semantic similarity search and graph traversal.
Instead of starting every debug workflow from scratch, agents check memory first and
apply known fixes proactively.

### How It Works

1. **Symptom text** is embedded into a vector using the configured embedding provider
2. The vector is stored alongside structured metadata (diagnosis, fix, outcome, etc.)
3. **Graph nodes and edges** are created in the Apache AGE knowledge graph, linking
   attempts to projects, error patterns, and fix patterns
4. When a new symptom is encountered, it is embedded and compared against stored vectors
5. **Graph traversal** finds structurally related issues across projects — even when
   the symptom text is phrased differently
6. Matches are ranked by a combined vector + graph score and returned with their fix details

### Structured Symptom Text Template

The `symptom_text` field is the ONLY field that gets embedded as a vector. Its structure
directly affects search quality. Always use this format:

```
[Error Category] on [Sampler Name] — [Response Code].
[Error Message / Symptom Description].
[Brief Diagnosis Context].
```

**Good example:**

```
Missing Correlations (OAuth Parameters) on TC01_S02_GET /oauth2/authorize
— java.net.URISyntaxException. Illegal character in query caused by unresolved
${oauth_redirect_uri}, ${oauth_client_id}, ${oauth_response_mode}, ${oauth_nonce},
${oauth_state}. The redirect URL from GET /home contains all OAuth parameters
URL-encoded in the goto query parameter but no extractors existed.
```

**Bad example (too vague):**

```
OAuth error on login page. Variables not found.
```

### Similarity Score Interpretation

| Score Range | Recommendation | Action |
|-------------|----------------|--------|
| > 0.85 or `source: "both"` | `apply_known_fix` | Apply the fix directly, especially if `confirmed_count > 1` |
| 0.60 - 0.85 | `review_suggestions` | Present matches to user or review before applying |
| < 0.60 | `no_match` | No useful matches — proceed with normal debugging |

The default threshold is set in `perfmemory-mcp/config.yaml` under `search.similarity_threshold`.

### Match Source Field

When graph is enabled, each match includes a `source` field:

| Source | Meaning |
|--------|---------|
| `vector` | Found via pgvector cosine similarity only |
| `graph` | Found via Apache AGE graph traversal only |
| `both` | Found by both vector search and graph traversal (highest confidence) |

### Related Rules

- **`prerequisites.mdc`** — `test_run_id` is required for all workflows
- **`skill-execution-rules.mdc`** — Follow steps in order, do not skip
- **`mcp-error-handling.mdc`** — MCP tool error handling (no retry for code-based tools)

---

## Workflow A — Search Memory Before Debugging

Use this workflow when an agent encounters an error and wants to check if a similar
issue has been solved before. This is called BEFORE starting a debug loop.

### Collect Inputs

```
REQUIRED:
  symptom_text = [the current error symptom — use the structured template above]

OPTIONAL:
  system_under_test = [filter to a specific system, e.g. "Shopping Cart"]
  error_category    = [filter to a specific category, e.g. "Missing Correlations"]
```

### Step 1 — Search for Similar Attempts

```
find_similar_attempts(
  symptom_text      = {symptom_text},
  system_under_test = {system_under_test},      # optional
  error_category    = {error_category}          # optional
)
```

### Step 2 — Interpret Results

**If `recommendation` = `apply_known_fix` (similarity > 0.85 or source = "both"):**
- Review the top match's `diagnosis` and `fix_description`
- If `confirmed_count > 1` and `is_verified = true`: apply the fix directly
- If `confirmed_count = 1` or `is_verified = false`: present to user for confirmation
- Check the `source` field: matches found by "both" vector and graph are highest confidence

**If `recommendation` = `review_suggestions` (similarity 0.60 - 0.85):**
- Present the top 2-3 matches to the user with their diagnosis and fix
- Let the user decide which (if any) to apply
- If the user approves a fix, apply it and pass the `attempt_id` as
  `matched_attempt_id` when storing the new attempt (Workflow B)

**If `recommendation` = `no_match`:**
- Try `find_cross_project_patterns` if `error_category` is known (Step 3)
- If still no results, proceed with normal debugging workflow

### Step 3 — Cross-Project Pattern Search (Graph)

If vector search returned `no_match` but you have an `error_category`, check the
knowledge graph for cross-project patterns:

```
find_cross_project_patterns(
  error_category    = {error_category},
  current_project   = {system_under_test},     # optional — excludes own project
  response_code     = {response_code},         # optional — omit to match all response codes
  enrich            = true                     # optional — fetches full attempt details
)
```

If matches are returned:
- Review the `graph_path` field to understand how the match was found
  (e.g., `ErrorPattern(Missing Correlations/*)` or `SIMILAR_TO(hops<=2)`)
- When `enrich = true` (default), each match includes `symptom_text`, `diagnosis`,
  `fix_description`, `sampler_name`, `api_endpoint`, `confirmed_count`, and `is_verified`
  from the relational store — enough context to decide whether to apply the fix
- If a match looks promising, use `get_related_issues` (Step 4) to explore its
  neighborhood for additional related fixes

### Step 4 — Explore Graph Neighborhood (Optional)

When a match from Step 2 or Step 3 looks relevant, explore its graph neighborhood
to discover additional related fixes that may not have surfaced in the initial search:

```
get_related_issues(
  attempt_id           = {matched_attempt_id},
  include_same_project = true,                 # set false for cross-project only
  enrich               = true                  # optional — fetches full neighbor details
)
```

This returns:
- **error_patterns**: The error categories and response codes linked to this attempt
- **fix_patterns**: The fix types and component types that resolved it
- **neighbors**: Other attempts connected via SIMILAR_TO edges, with full details
  when `enrich = true` (symptom, diagnosis, fix, confidence signals)

Use this when:
- A match was found but you want to see if there are related fixes for the same class of issue
- You want to understand the full context of an error pattern before applying a fix
- You want to check if the same fix type has been applied successfully in other projects

---

## Workflow B — Store Lessons During Debugging

Use this workflow during an active debug session to record what was tried and what
worked. This is integrated into the `jmeter-debugging` skill at specific steps.

### Step 1 — Open a Debug Session

Called once at the start of debugging.

```
REQUIRED:
  system_under_test = [what is being tested, e.g. "Shopping Cart"]
  test_run_id       = [the artifact test run ID]

OPTIONAL:
  script_name    = [the JMX filename]
  auth_flow_type = [none, oauth_pkce, oauth_auth_code, saml, token_chain,
                    custom_sso, entra_id, other]
  environment    = [dev, qa, uat, staging, prod]
  created_by     = [PTE name or "cursor"]
  notes          = [freeform session notes]
```

```
store_debug_session(
  system_under_test = {system_under_test},
  test_run_id       = {test_run_id},
  script_name       = {script_name},
  auth_flow_type    = {auth_flow_type},
  environment       = {environment},
  created_by        = {created_by},
  notes             = {notes}
)
```

**Save:** `session_id` from the response.

### Step 2 — Store Each Debug Attempt

Called after each debug iteration (after applying a fix and observing the result).

```
store_debug_attempt(
  session_id        = {session_id},
  iteration_number  = {iteration_count},
  symptom_text      = {structured symptom — use the template},
  outcome           = {resolved | failed | environment_issue | test_data_issue |
                       authentication_issue | needs_investigation},
  error_category    = {from log analysis},
  severity          = {Critical | High | Medium},
  response_code     = {HTTP status code or exception name},
  hostname          = {host where the error occurred},
  sampler_name      = {the failing JMeter sampler},
  api_endpoint      = {the failing URL/endpoint},
  diagnosis         = {root cause determination — plain language},
  fix_description   = {what fix was applied — plain language},
  fix_type          = {add_extractor | move_extractor | edit_request_body |
                       edit_header | edit_correlation | other},
  component_type    = {json_extractor | regex_extractor | jsr223_postprocessor |
                       jsr223_preprocessor | http_sampler | test_plan | other},
  manifest_excerpt  = {optional — raw manifest iteration text},
  matched_attempt_id = {optional — UUID of a memory match that was applied}
)
```

**Save:** `attempt_id` from the response.

If `matched_attempt_id` was provided, the response will also include
`confirmed_match_id` and `new_confirmed_count` showing the updated confidence.

### Step 3 — Close the Debug Session

Called once when debugging completes (resolved or not).

```
close_debug_session(
  session_id            = {session_id},
  final_outcome         = {resolved | unresolved | environment_issue |
                           test_data_issue | authentication_issue |
                           iteration_limit_reached | needs_investigation},
  resolution_attempt_id = {attempt_id of the fix that resolved the issue},
  notes                 = {summary of remaining issues if unresolved}
)
```

---

## Workflow C — Ingest Existing Knowledge

Use this workflow to bulk-load lessons from existing documents into perfmemory.
Supports two source formats.

### Source 1: Debug Manifests

Debug manifests are markdown files at `artifacts/{test_run_id}/analysis/debug_manifest.md`
generated by the `jmeter-debugging` skill. Each iteration maps to one attempt.

**Ingestion Steps:**

1. Read the manifest file
2. Parse the header for session metadata:
   - `Test Run ID` → `test_run_id`
   - `Script` → `script_name`
   - `Status` → infer `final_outcome`
3. Call `store_debug_session` with the parsed metadata
   - `system_under_test`: ask the user if not obvious from the manifest
   - `auth_flow_type`: infer from the content (OAuth, SAML, CDSSO references)
   - `environment`: infer from hostnames (e.g., `-stg.` = staging)
4. For each `## Iteration N` section, parse:
   - **Error Identified** → `error_category`, `sampler_name`, `response_code`, `error_message`
   - **Diagnosis** → `diagnosis`
   - **Fix Applied** → `fix_description`, `fix_type`, `component_type`
   - **Result After Fix** → `outcome` (resolved if it improved, failed if it didn't)
5. Build `symptom_text` using the structured template from the parsed fields
6. Call `store_debug_attempt` for each iteration
7. Call `close_debug_session` with the final outcome

**Field Mapping Reference:**

| Manifest Field | PerfMemory Field |
|----------------|------------------|
| Iteration number | `iteration_number` |
| Sampler name from "Error Identified" | `sampler_name` |
| Response Code from "Error Identified" | `response_code` |
| Error Category from "Error Identified" | `error_category` |
| "Diagnosis" section | `diagnosis` |
| "Fix Applied" section | `fix_description` |
| Fix component type (JSR223, JSON Extractor, etc.) | `component_type` |
| Fix action (add extractor, edit body, etc.) | `fix_type` |
| "Result After Fix" section | `outcome` |

### Source 2: Lessons-Learned Documents

Lessons-learned documents are curated pattern files (e.g. `.md` files)
that contain numbered lessons with symptoms, causes, and fixes. These represent
human-reviewed knowledge and are stored as verified attempts.

**Ingestion Steps:**

1. Read the lessons-learned document
2. Create a single debug session to group all lessons:
   ```
   store_debug_session(
     system_under_test = {inferred or ask user},
     test_run_id       = {document filename or ask user},
     notes             = "Ingested from lessons-learned document: {filename}"
   )
   ```
3. For each numbered lesson (e.g., `## 1. Always Use follow_redirects...`):
   - Parse the lesson title as the `error_category`
   - Parse the description for `symptom_text` (the problem pattern)
   - Parse the **Fix** section for `fix_description`
   - Infer `fix_type` and `component_type` from the fix content
   - Set `outcome = "resolved"` (these are known-good patterns)
   - Call `store_debug_attempt`
4. For pre-debug checklist items (e.g., "Prerequisites: Pre-Debug Validation"):
   - Each checklist item becomes a separate attempt
   - Set `error_category = "Pre-Debug Validation"`
   - Set `outcome = "resolved"`
5. Call `close_debug_session` with `final_outcome = "resolved"`
6. Mark all attempts as human-verified:
   ```
   verify_attempt(attempt_id = {each_attempt_id})
   ```

**Symptom text for lessons-learned entries should capture the general pattern,
not a specific sampler or test case:**

```
JMeter Cookie/Redirect Handling — auto_redirects=true delegates redirect handling
to Java's HttpURLConnection which does not use JMeter's CookieManager. SSO cookies
are lost during redirect chains, causing authentication to fail silently.
```

---

## Maintenance Operations

### Verify an Attempt (Human Review)

When a human confirms that a stored lesson is correct and reliable:

```
verify_attempt(attempt_id = {attempt_id})
```

### Archive an Attempt (Outdated Lesson)

When a lesson becomes outdated (API changed, issue no longer occurs):

```
archive_attempt(
  attempt_id = {attempt_id},
  reason     = {why this lesson is no longer valid}
)
```

Archived attempts remain in the database for audit but are excluded from search results.

### View Memory Stats

```
get_memory_stats(
  system_under_test = {optional — filter to a specific system}
)
```

### Review a Session

```
get_session_detail(session_id = {session_id})
```

### Browse Sessions

```
list_sessions(
  system_under_test = {optional},
  environment       = {optional},
  final_outcome     = {optional},
  limit             = 20
)
```

### Explore Graph Neighborhood

View the graph connections for a specific attempt (requires `graph.enabled: true`).
Use this after finding a match to discover additional related fixes, or to understand
the structural context of a known issue before applying a fix.

```
get_related_issues(
  attempt_id           = {attempt_id},
  max_hops             = 2,                    # optional — graph traversal depth
  include_same_project = true,                 # optional — include same-project neighbors
  enrich               = true                  # optional — fetches full neighbor details
)
```

Returns:
- **error_patterns**: list of `{error_category, response_code}` linked to this attempt
- **fix_patterns**: list of `{fix_type, component_type}` that resolved it
- **neighbors**: other attempts connected via SIMILAR_TO edges

When `enrich = true`, each neighbor includes `symptom_text`, `diagnosis`,
`fix_description`, `sampler_name`, `api_endpoint`, `confirmed_count`, and `is_verified`.

### Cross-Project Pattern Search

Find if an error class has been resolved in other projects (requires `graph.enabled: true`).
Use this as a fallback when vector search returns no matches, or proactively when
starting work on a new project to check for known patterns.

```
find_cross_project_patterns(
  error_category  = {error_category},
  current_project = {system_under_test},       # optional — excludes own project
  response_code   = {response_code},           # optional — omit to match all response codes
  fix_type        = {fix_type},                # optional
  max_hops        = 2,                         # optional
  limit           = 5,                         # optional
  enrich          = true                       # optional — fetches full attempt details
)
```

When `enrich = true`, each match includes `symptom_text`, `diagnosis`,
`fix_description`, `sampler_name`, `api_endpoint`, `confirmed_count`, and `is_verified`.

---

## Error Handling

- If `store_debug_session` or `store_debug_attempt` fails, report the error immediately.
  Do NOT retry — these are code-based MCP tools (per `mcp-error-handling.mdc`).
- If `find_similar_attempts` fails, proceed with normal debugging (memory is advisory).
- If graph tools (`find_cross_project_patterns`, `get_related_issues`) fail or return
  "Graph layer is not enabled", fall back to vector-only results. Graph is supplementary.
- If the database is unreachable, skip all perfmemory operations and inform the user.
  Do not block the debugging workflow because memory is unavailable.
- Never modify the perfmemory MCP source code to work around errors.
