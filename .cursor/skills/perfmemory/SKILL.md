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

PerfMemory is a persistent memory layer backed by PostgreSQL + pgvector. It stores
structured debug sessions, attempts, and vector embeddings of symptoms so AI agents
can recall past fixes via semantic similarity search. Instead of starting every debug
workflow from scratch, agents check memory first and apply known fixes proactively.

### How It Works

1. **Symptom text** is embedded into a vector using the configured embedding provider
2. The vector is stored alongside structured metadata (diagnosis, fix, outcome, etc.)
3. When a new symptom is encountered, it is embedded and compared against stored vectors
4. Matches are ranked by cosine similarity and returned with their fix details

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
| > 0.85 | `apply_known_fix` | Apply the fix directly, especially if `confirmed_count > 1` |
| 0.60 - 0.85 | `review_suggestions` | Present matches to user or review before applying |
| < 0.60 | `no_match` | No useful matches — proceed with normal debugging |

The default threshold is set in `perfmemory-mcp/config.yaml` under `search.similarity_threshold`.

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

**If `recommendation` = `apply_known_fix` (similarity > 0.85):**
- Review the top match's `diagnosis` and `fix_description`
- If `confirmed_count > 1` and `is_verified = true`: apply the fix directly
- If `confirmed_count = 1` or `is_verified = false`: present to user for confirmation

**If `recommendation` = `review_suggestions` (similarity 0.60 - 0.85):**
- Present the top 2-3 matches to the user with their diagnosis and fix
- Let the user decide which (if any) to apply
- If the user approves a fix, apply it and pass the `attempt_id` as
  `matched_attempt_id` when storing the new attempt (Workflow B)

**If `recommendation` = `no_match`:**
- Proceed with normal debugging workflow (no prior knowledge available)

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

---

## Error Handling

- If `store_debug_session` or `store_debug_attempt` fails, report the error immediately.
  Do NOT retry — these are code-based MCP tools (per `mcp-error-handling.mdc`).
- If `find_similar_attempts` fails, proceed with normal debugging (memory is advisory).
- If the database is unreachable, skip all perfmemory operations and inform the user.
  Do not block the debugging workflow because memory is unavailable.
- Never modify the perfmemory MCP source code to work around errors.
