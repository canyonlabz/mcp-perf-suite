"""PerfPilot Execution Agent -- AG2 ConversableAgent factory + agent tools.

This module ships the four-file pattern's `agent.py` slot per V2 doc
§7.1: construct and return the agent on demand, with all configuration
loaded from the sibling `INSTRUCTIONS.md`, `agent_card.json`, and *one of*
`config.yaml` / `config.example.yaml`. Callers (the A2A task executor in
PBI 3.8.6, the orchestrator's `delegate_to_specialist` tool) import
`build_execution_agent()` and wrap the result.

**What this module ships (state as of PBI 3.8.3):**

- A working `ConversableAgent` factory with the real long-form system
  prompt loaded from `INSTRUCTIONS.md`.
- Per-agent `llm_provider` resolution via the framework's
  `utils.base_agent.resolve_agent_config_path()` candidate walker.
- **One agent tool wired:**
    1. `start_performance_test(test_id)`               -- PBI 3.8.3 (this commit)
- **Two tools still pending:**
    2. `wait_for_completion(run_id, ...)`              -- PBI 3.8.4
    3. `extract_test_run_artifacts(test_run_id, ...)`  -- PBI 3.8.5

`_register_tools(agent)` is now lit up and called from
`build_execution_agent()`, mirroring the orchestrator's PBI 3.7.3
cadence. Each PBI in 3.8.3-3.8.5 adds another tool there.

**Tool design conventions (apply to every agent tool in this module):**

- Module-level functions so smoke tests and PBI 3.8.6's task executor
  can import and exercise them directly without spinning up an LLM.
  The on-disk folder name is `execution-agent` (hyphenated), so callers
  load this module via `importlib.util.spec_from_file_location()` -- not
  Python's normal `from agents.execution-agent.agent import ...` (which
  would be a syntax error).
- Each tool wraps one or more MCP tools through `utils/mcp_client.py`'s
  `MCPClient` async context manager. The tool function manages the
  connection lifecycle in production; smoke tests inject a pre-built
  client via the `_*_with_client` private helper to avoid double
  setup/teardown.
- **Tools NEVER raise for tool-side failures.** They return a structured
  `{"ok": False, "error": {"type": ..., "message": ...}}` dict so the
  orchestrator (and the human ultimately) can narrate the failure
  honestly. The only exceptions a tool surfaces are programmer errors
  (PermissionError from an out-of-namespace MCP call -- which signals
  an `mcp_tools.allowed_namespaces` misconfiguration, not a runtime
  failure).
- Idempotency drives retry policy per tool:
    - `start_performance_test`        -- NOT idempotent (a retry could
      start a duplicate run). Single attempt; surface errors directly.
    - `wait_for_completion`           -- idempotent (status polling).
      Retry transparently up to 3x per `mcp-error-handling` rule.
    - `extract_test_run_artifacts`    -- idempotent per step. Each
      MCP call retries up to 3x with 5-10s back-off for API-based MCPs;
      code-based MCPs (`jmeter_analyze_jmeter_log`) never retry.

**Return-shape convention:**

  Success:  {"ok": True,  "vendor": "blazemeter", ...tool-specific fields..., "raw": <truncated MCP response>}
  Failure:  {"ok": False, "error": {"type": "<ExceptionClass>", "message": "<truncated>"}, ...echoed inputs...}

**What this module still does NOT do (deferred):**

- A2A `task_executor` dispatch (PBI 3.8.6 adds `_run_execution_agent`).
- Card flip to `available` + populated `skills[]` (PBI 3.8.7).

Heavy imports (`autogen`, `yaml`, `fastmcp` via `utils.mcp_client`) live
inside the functions that need them so this module is cheap to import
in tests / IDE indexing that do not exercise the agent.

NOTE: This module deliberately does NOT use `from __future__ import
annotations`. AG2 0.13.3 introspects tool function signatures via
pydantic's `TypeAdapter`, which cannot evaluate stringified `Annotated`
annotations. Keeping annotations as live types makes tool registration
work without per-call `.rebuild()` shenanigans (same constraint that
applies to the orchestrator's `agent.py`).
"""

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Annotated, Any, Optional

log = logging.getLogger(__name__)

AGENT_DIR = Path(__file__).resolve().parent
AGENT_NAME = "execution-agent"
FRAMEWORK_DIR = AGENT_DIR.parent.parent  # agent-framework/

INSTRUCTIONS_PATH = AGENT_DIR / "INSTRUCTIONS.md"
AGENT_CARD_PATH = AGENT_DIR / "agent_card.json"


# =============================================================================
# Factory
# =============================================================================

def build_execution_agent() -> Any:
    """Construct the PerfPilot Execution Agent AG2 ConversableAgent.

    Resolution order for the LLM provider:
      1. Per-agent `llm_provider` block in the first existing of
         `config.yaml` (operator-side override, gitignored) or
         `config.example.yaml` (committed default).
      2. Global fallback `config/agents.yaml -> default_llm_provider`
         via `utils.llm_provider.load_default_provider_config()`.

    Returns:
        An `autogen.ConversableAgent` instance with the long-form
        `INSTRUCTIONS.md` as `system_message` and
        `human_input_mode="NEVER"` (this is a server agent).

        No tools are registered in PBI 3.8.1 -- they land in PBIs
        3.8.3 / 3.8.4 / 3.8.5 (each tool gets its own PBI per the
        F3.8 plan, mirroring the orchestrator's 3.7.3-3.7.6 cadence).

    Raises:
        FileNotFoundError: when one of the four sibling files is missing.
        Anything `LLMProvider.to_ag2_config()` raises when credentials
        are not configured.
    """
    from autogen import ConversableAgent  # type: ignore

    from utils.llm_provider import LLMProvider

    system_message = _load_system_message()
    provider_config = _resolve_provider_config()
    provider = LLMProvider(provider_config)

    log.info(
        "Building %s (provider=%s, model=%s)",
        AGENT_NAME, provider.provider, provider.get_model_name(),
    )

    agent = ConversableAgent(
        name=AGENT_NAME,
        system_message=system_message,
        llm_config=provider.to_ag2_config(),
        # Server-side: never block on stdin.
        human_input_mode="NEVER",
        # Allow chain depth for future tool-call -> tool-result ->
        # follow-up reply patterns. PBI 3.8.6's A2A executor dispatches
        # to tool functions directly (bypassing the LLM loop), but the
        # agent is also reachable via the orchestrator's
        # `delegate_to_specialist` and via direct LLM interactions where
        # chain depth matters. 5 is the headroom; deeper chains likely
        # indicate a tool error loop and should terminate.
        max_consecutive_auto_reply=5,
    )

    _register_tools(agent)
    return agent


# =============================================================================
# Internal helpers
# =============================================================================

def _load_system_message() -> str:
    """Read `INSTRUCTIONS.md` as the AG2 `system_message`."""
    if not INSTRUCTIONS_PATH.exists():
        raise FileNotFoundError(
            f"Execution-agent INSTRUCTIONS.md not found at {INSTRUCTIONS_PATH}."
        )
    return INSTRUCTIONS_PATH.read_text(encoding="utf-8-sig")


def _resolve_provider_config() -> dict:
    """Return the merged LLM-provider config for the execution-agent.

    Per-agent overrides win over the global default in
    `config/agents.yaml -> default_llm_provider:`. Env credentials are
    merged in by `utils.llm_provider.merge_env_credentials` regardless
    of which YAML block sourced the behavior keys.
    """
    from utils.llm_provider import (
        load_default_provider_config,
        merge_env_credentials,
    )

    agent_block = _load_per_agent_llm_block()
    if agent_block:
        log.debug(
            "Execution-agent using per-agent llm_provider override from %s",
            _resolved_config_filename(),
        )
        return merge_env_credentials(agent_block)

    log.debug("Execution-agent using default_llm_provider from agents.yaml")
    return load_default_provider_config()


def _load_per_agent_llm_block() -> Optional[dict]:
    """Parse the resolved per-agent config and return its `llm_provider:` block.

    Returns None when neither candidate config file exists, the YAML is
    empty, or the `llm_provider:` key is absent / commented out.
    """
    from utils.base_agent import resolve_agent_config_path

    config_path = resolve_agent_config_path(AGENT_DIR)
    if config_path is None:
        log.warning(
            "Execution-agent config not found under %s "
            "(expected config.yaml or config.example.yaml); "
            "using default LLM provider.",
            AGENT_DIR,
        )
        return None

    import yaml

    with open(config_path, "r", encoding="utf-8-sig") as f:
        parsed = yaml.safe_load(f) or {}
    block = parsed.get("llm_provider")
    if not block or not isinstance(block, dict):
        return None
    return dict(block)


def _resolved_config_filename() -> str:
    from utils.base_agent import resolve_agent_config_path

    path = resolve_agent_config_path(AGENT_DIR)
    return path.name if path else "<none>"


# =============================================================================
# Tool registration
# =============================================================================

def _register_tools(agent: Any) -> None:
    """Wire the F3.8 agent tools onto the ConversableAgent.

    Both decorators are required for each tool:
      - `register_for_llm(...)` advertises the tool in the LLM's tool
        catalog so the model can decide to call it during a generate_reply
        loop (used for orchestrator -> execution-agent chains, future
        LLM-driven flows).
      - `register_for_execution()` tells AG2 that THIS agent is the one
        that actually runs the function (vs. a separate executor agent).

    AG2 0.13.3 uses `api_style='tool'` by default, which is what we want
    (modern OpenAI tools API, not the deprecated function-calling API).
    The same decoration pattern works for both sync and async tool
    functions; AG2 awaits the coroutine when `register_for_execution()`
    invokes it.

    PBIs 3.8.3 / 3.8.4 wire `start_performance_test` and
    `wait_for_completion`. PBI 3.8.5 will add `extract_test_run_artifacts`.
    """
    agent.register_for_llm(
        name="start_performance_test",
        description=(
            "Kick off a performance test run against a test definition that "
            "ALREADY EXISTS in the load-testing tool of record (BlazeMeter "
            "in F3.8; vendor-agnostic by name for future Gatling / Locust / "
            "k6 expansion). Takes the existing test_id and returns the "
            "freshly-minted run_id on success. Starting a test is NOT "
            "idempotent -- this tool makes a single attempt and surfaces "
            "any error directly; do NOT retry on transient failure without "
            "human or orchestrator approval. Always returns a structured "
            "dict ({ok: True, run_id, ...} on success or {ok: False, "
            "error: {...}} on failure); NEVER raises."
        ),
    )(start_performance_test)
    agent.register_for_execution()(start_performance_test)

    agent.register_for_llm(
        name="wait_for_completion",
        description=(
            "Block until the given run_id reaches a terminal state in the "
            "load-testing tool, polling the underlying MCP status endpoint at "
            "`poll_interval_seconds` (default 60s) until `timeout_seconds` "
            "(default 300s) elapses. Returns ok=True on terminal completion "
            "(status='ENDED', timed_out=False), ok=True on test-side failure "
            "(has_error=True with BlazeMeter's reported error string), ok=True "
            "on wait timeout (timed_out=True with the last observed status), "
            "and ok=False ONLY when 3 consecutive MCP polls fail (transient "
            "single-poll failures are absorbed by the natural polling cadence). "
            "Status polling is idempotent and safe to call repeatedly. NEVER "
            "raises."
        ),
    )(wait_for_completion)
    agent.register_for_execution()(wait_for_completion)


# =============================================================================
# Tool 1 (PBI 3.8.3): start_performance_test
# =============================================================================

# BlazeMeter MCP's `start_test` tool returns a formatted string of the form
# "Run started. Run ID: 12345" (see blazemeter-mcp/services/blazemeter_api.py
# `run_test()`). The wrapper regex-extracts the run_id. Pattern is permissive
# enough to survive minor wording tweaks ("Run id:", " ID:1234") but anchors
# on the "ID:" token so it does not false-match on test_id mentions in the
# response.
_RUN_ID_PATTERN = re.compile(r"Run\s+ID\s*:\s*([A-Za-z0-9_-]+)", re.IGNORECASE)


async def start_performance_test(
    test_id: Annotated[
        str,
        "Identifier of an EXISTING test definition in the load-testing tool "
        "(BlazeMeter test ID in F3.8, e.g. '14491287'). The test artifact "
        "(JMX / .yaml / recorded scenario) must already be uploaded; this "
        "agent does NOT upload JMX scripts.",
    ],
) -> dict:
    """Kick off a performance test run for a pre-existing test definition.

    Vendor-agnostic by name; in F3.8 wraps the BlazeMeter MCP tool
    `blazemeter_start_test(test_id)` 1:1. Future feature work will swap
    the underlying MCP tool based on a per-test vendor config (Gatling /
    Locust / k6), keeping this agent-tool name stable.

    **Idempotency contract.** Starting a test is NOT idempotent:
    re-issuing this call after a timeout could create a duplicate run
    on the load-testing side. This function therefore makes a SINGLE
    attempt against the MCP and surfaces any error directly -- no
    silent retry. The orchestrator (or human, via HITL) decides
    whether to re-prompt.

    **Connection lifecycle.** Builds and tears down its own `MCPClient`
    in the default invocation path. Smoke tests inject a pre-built
    client via the `_start_performance_test_with_client` helper to
    avoid double connection overhead.

    Args:
        test_id: Identifier of an existing test definition in the
            load-testing tool of record. Stripped of surrounding
            whitespace; empty string returns an `InvalidInput` error.

    Returns:
        Always a dict. **NEVER raises** for tool-side failures.

        On success::

            {
                "ok": True,
                "vendor": "blazemeter",
                "test_id": "<echoed>",
                "run_id": "<minted-by-vendor>",
                "raw": "<truncated MCP response>",
            }

        On failure::

            {
                "ok": False,
                "error": {
                    "type": "<exception class>",
                    "message": "<truncated>",
                },
                "test_id": "<echoed>",
            }
    """
    test_id = (test_id or "").strip()
    if not test_id:
        return _invalid_input_error(
            test_id="",
            message="test_id must be a non-empty string",
        )

    from utils.mcp_client import MCPClient, build_client_config

    config = build_client_config(["blazemeter", "jmeter"])
    try:
        async with MCPClient(config) as client:
            return await _start_performance_test_with_client(test_id, client)
    except Exception as e:
        return _make_error(test_id, e)


async def _start_performance_test_with_client(
    test_id: str,
    client: Any,
) -> dict:
    """Inner implementation: single MCP call + structured normalization.

    Exposed (with the leading underscore) so smoke tests can pass a
    pre-connected `MCPClient` and avoid the connection-management
    overhead of repeatedly opening/closing the FastMCP transport.

    A single attempt -- the function never retries, since
    `blazemeter_start_test` is not idempotent.

    Args:
        test_id: Already-validated test ID (non-empty, stripped).
        client: An open `utils.mcp_client.MCPClient`. The caller owns
            the lifecycle.

    Returns:
        The same `{ok, ...}` dict shape documented on
        `start_performance_test`.
    """
    try:
        result = await client.call_tool(
            "blazemeter_start_test", {"test_id": test_id}
        )
    except Exception as e:
        return _make_error(test_id, e)

    raw = _extract_text_or_data(result)
    run_id = _parse_run_id(raw)
    if run_id is None:
        return {
            "ok": False,
            "error": {
                "type": "MalformedResponse",
                "message": (
                    "MCP returned a response but no run_id could be parsed. "
                    "Check the blazemeter-mcp response shape."
                ),
                "raw": _truncate(raw),
            },
            "test_id": test_id,
        }
    return {
        "ok": True,
        "vendor": "blazemeter",
        "test_id": test_id,
        "run_id": str(run_id),
        "raw": _truncate(raw),
    }


# =============================================================================
# Tool helpers (shared across PBIs 3.8.3 / 3.8.4 / 3.8.5)
# =============================================================================

def _parse_run_id(raw: Any) -> Optional[str]:
    """Extract the run_id from the MCP response, handling multiple shapes.

    Handles three shapes:
      - dict with `run_id` / `runId` / `id` key -> use directly
      - formatted string like 'Run started. Run ID: 12345' -> regex extract
      - anything else -> None
    """
    if isinstance(raw, dict):
        for key in ("run_id", "runId", "id"):
            value = raw.get(key)
            if value not in (None, ""):
                return str(value)
    if isinstance(raw, str):
        m = _RUN_ID_PATTERN.search(raw)
        if m:
            return m.group(1)
    return None


def _extract_text_or_data(result: Any) -> Any:
    """Return `.data` if present, else `.content[0].text`, else the raw object.

    FastMCP's `CallToolResult` populates `.data` when the tool returns a
    structured value (dict / dataclass / list of primitives) and
    `.content[0].text` when the tool returns a plain string. This helper
    handles both transparently.
    """
    data = getattr(result, "data", None)
    if data is not None:
        return data
    content = getattr(result, "content", None) or []
    if content:
        text = getattr(content[0], "text", None)
        if text is not None:
            return text
    return result


def _truncate(value: Any, limit: int = 500) -> str:
    """Return `str(value)` truncated to a UI-friendly length."""
    s = str(value)
    return s if len(s) <= limit else s[: limit - 3] + "..."


def _make_error(test_id: str, e: BaseException) -> dict:
    """Build the canonical `{ok: False, error: {...}}` dict from an exception."""
    return {
        "ok": False,
        "error": {
            "type": type(e).__name__,
            "message": _truncate(e),
        },
        "test_id": test_id,
    }


def _invalid_input_error(test_id: str, message: str) -> dict:
    """Build the canonical `InvalidInput` error dict (used for client-side validation)."""
    return {
        "ok": False,
        "error": {
            "type": "InvalidInput",
            "message": message,
        },
        "test_id": test_id,
    }


# =============================================================================
# Tool 2 (PBI 3.8.4): wait_for_completion
# =============================================================================

# Status-vocabulary constants. Single source of truth so the parser, the
# terminal-state classifier, and the smoke tests all agree on what
# "terminal" means. BlazeMeter's API documents `ENDED` as the natural
# completion state and `FAILED` / `ERROR` / `ABORTED` as the terminal
# failure states (see blazemeter-mcp/services/blazemeter_api.py
# `get_test_status` for the `has_error` bool's exact criteria).
TERMINAL_SUCCESS_STATUS = "ENDED"
TERMINAL_FAILURE_STATUSES = frozenset({"FAILED", "ERROR", "ABORTED"})

# Safety floor for poll interval. The user-facing default is 60s (see
# `wait_for_completion` signature) but smoke tests need to drive the
# loop at sub-second intervals; this floor prevents foot-gun zeros.
_MIN_POLL_INTERVAL_SECONDS = 0.05

# Hard error threshold: three consecutive polls failing with an exception
# (network, auth, etc.) is treated as a wait-side failure and aborts the
# loop. Transient single-poll failures are absorbed because the natural
# 60-second polling cadence provides better back-off than blind retries.
_MAX_CONSECUTIVE_POLL_FAILURES = 3


async def wait_for_completion(
    run_id: Annotated[
        str,
        "BlazeMeter run_id minted by `start_performance_test` (also called "
        "`master_id` in some BlazeMeter API endpoints). Same value carried "
        "through the rest of the F3.8 pipeline as `test_run_id`.",
    ],
    *,
    poll_interval_seconds: Annotated[
        float,
        "Seconds between status polls. Default 60.0 to stay well under "
        "BlazeMeter's API rate limits; status updates are not granular "
        "enough to benefit from tighter polling.",
    ] = 60.0,
    timeout_seconds: Annotated[
        float,
        "Maximum seconds to wait for terminal state. Default 300.0 (5 "
        "minutes) -- appropriate for short smoke tests; production "
        "callers should raise this for longer real workloads.",
    ] = 300.0,
) -> dict:
    """Block until `run_id` reaches a terminal state, polling at intervals.

    In F3.8 wraps the BlazeMeter MCP tool `blazemeter_check_test_status(run_id)`
    in an `asyncio.sleep` loop. The status polling is idempotent, so transient
    per-poll MCP failures are absorbed silently (counted, but not raised) and
    only escalate to a hard error after 3 consecutive failures -- the natural
    60-second polling cadence acts as the back-off.

    **Return-shape contract** (matches `INSTRUCTIONS.md` §3.2):

    Terminal success (BlazeMeter reported `status: 'ENDED'`)::

        {"ok": True, "run_id": ..., "status": "ENDED", "has_error": False,
         "error": None, "timed_out": False, "polls": <int>, "elapsed_seconds": <float>,
         "last_response": "<truncated>"}

    Terminal failure (BlazeMeter reported `has_error: True` or one of
    FAILED / ERROR / ABORTED). The wait OPERATION succeeded (we got a
    deterministic verdict), but the test itself failed -- `ok: True`
    reflects the wait's success; `has_error: True` reflects the test's
    failure. The orchestrator decides whether to still attempt extraction::

        {"ok": True, "run_id": ..., "status": "FAILED" | "ERROR" | "ABORTED" | ...,
         "has_error": True, "error": "<BlazeMeter's error string or object>",
         "timed_out": False, "polls": <int>, "elapsed_seconds": <float>,
         "last_response": "<truncated>"}

    Timeout (deadline reached before BlazeMeter reached terminal)::

        {"ok": True, "run_id": ..., "status": "<last observed, e.g. RUNNING>",
         "has_error": False, "error": None, "timed_out": True, "polls": <int>,
         "elapsed_seconds": <float>, "last_response": "<truncated>",
         "notes": "Reached timeout_seconds=... before terminal state."}

    Hard error (3 consecutive MCP polls raised; or invalid input). Only
    case where `ok: False`::

        {"ok": False, "run_id": ..., "error": {"type": ..., "message": ...,
         "phase": "mcp-call" | "client-setup" | "invalid-input",
         "consecutive_failures": <int, when applicable>}, "polls": <int>}

    **Never raises** for tool-side failures.

    Args:
        run_id: BlazeMeter run identifier. Stripped of surrounding
            whitespace; empty string returns an `InvalidInput` error.
        poll_interval_seconds: Seconds between status polls (default 60).
            Clamped to a floor of 0.05s for smoke-test ergonomics.
        timeout_seconds: Maximum total wait window (default 300). Clamped
            to non-negative values; zero means "single-shot status check".

    Returns:
        A dict as documented above. The shape varies by branch; callers
        should switch on `ok` first, then `timed_out` / `has_error`.
    """
    run_id = (run_id or "").strip()
    if not run_id:
        return {
            "ok": False,
            "run_id": "",
            "error": {
                "type": "InvalidInput",
                "message": "run_id must be a non-empty string",
                "phase": "invalid-input",
            },
            "polls": 0,
        }

    poll = max(_MIN_POLL_INTERVAL_SECONDS, float(poll_interval_seconds))
    timeout = max(0.0, float(timeout_seconds))

    from utils.mcp_client import MCPClient, build_client_config

    config = build_client_config(["blazemeter", "jmeter"])
    try:
        async with MCPClient(config) as client:
            return await _wait_for_completion_with_client(
                run_id,
                client,
                poll_interval_seconds=poll,
                timeout_seconds=timeout,
            )
    except Exception as e:
        return {
            "ok": False,
            "run_id": run_id,
            "error": {
                "type": type(e).__name__,
                "message": _truncate(e),
                "phase": "client-setup",
            },
            "polls": 0,
        }


async def _wait_for_completion_with_client(
    run_id: str,
    client: Any,
    *,
    poll_interval_seconds: float = 60.0,
    timeout_seconds: float = 300.0,
) -> dict:
    """Inner implementation: status polling loop over a caller-provided client.

    Exposed (underscored) so smoke tests can inject a `_FakeMCPClient`
    or pre-connected real `MCPClient` and exercise the loop without
    re-opening the FastMCP transport per call.

    Args:
        run_id: Pre-validated (non-empty, stripped) run identifier.
        client: An object exposing the async `call_tool(name, args)`
            method -- either `utils.mcp_client.MCPClient` in production
            or a test fake. The caller owns the lifecycle.
        poll_interval_seconds: Already clamped to >= 0.05s.
        timeout_seconds: Already clamped to >= 0.0s.

    Returns:
        The same `{ok, ...}` dict shape documented on `wait_for_completion`.
    """
    deadline = time.monotonic() + timeout_seconds
    start = time.monotonic()

    polls = 0
    consecutive_failures = 0
    last_status: Optional[str] = None
    last_response: Any = None

    while True:
        polls += 1
        try:
            result = await client.call_tool(
                "blazemeter_check_test_status", {"run_id": run_id}
            )
            payload = _extract_text_or_data(result)
            consecutive_failures = 0
            last_response = payload
        except Exception as e:
            consecutive_failures += 1
            if consecutive_failures >= _MAX_CONSECUTIVE_POLL_FAILURES:
                return {
                    "ok": False,
                    "run_id": run_id,
                    "error": {
                        "type": type(e).__name__,
                        "message": _truncate(e),
                        "phase": "mcp-call",
                        "consecutive_failures": consecutive_failures,
                    },
                    "polls": polls,
                    "elapsed_seconds": round(time.monotonic() - start, 2),
                    "last_response": _truncate(last_response) if last_response is not None else None,
                }
            payload = None  # absorbed transient failure; fall through to sleep

        # Classify a successful poll's payload as terminal-success,
        # terminal-failure, or still-running.
        if isinstance(payload, dict):
            status_raw = payload.get("status")
            status_str = str(status_raw) if status_raw is not None else None
            status_upper = status_str.upper() if status_str else None
            if status_str:
                last_status = status_str
            has_error = bool(payload.get("has_error"))
            err_field = payload.get("error")

            if (
                status_upper == TERMINAL_SUCCESS_STATUS
                and not has_error
            ):
                return {
                    "ok": True,
                    "run_id": run_id,
                    "status": last_status,
                    "has_error": False,
                    "error": None,
                    "timed_out": False,
                    "polls": polls,
                    "elapsed_seconds": round(time.monotonic() - start, 2),
                    "last_response": _truncate(payload),
                }

            if has_error or (
                status_upper is not None
                and status_upper in TERMINAL_FAILURE_STATUSES
            ):
                return {
                    "ok": True,
                    "run_id": run_id,
                    "status": last_status,
                    "has_error": True,
                    "error": err_field,
                    "timed_out": False,
                    "polls": polls,
                    "elapsed_seconds": round(time.monotonic() - start, 2),
                    "last_response": _truncate(payload),
                }

        # Not terminal yet. Check timeout before sleeping so we never
        # over-sleep the deadline. A single-shot mode (timeout_seconds=0)
        # falls through here on the first iteration and returns timed_out.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {
                "ok": True,
                "run_id": run_id,
                "status": last_status,
                "has_error": False,
                "error": None,
                "timed_out": True,
                "polls": polls,
                "elapsed_seconds": round(time.monotonic() - start, 2),
                "last_response": _truncate(last_response) if last_response is not None else None,
                "notes": (
                    f"Reached timeout_seconds={timeout_seconds} before "
                    f"terminal state. Last status: {last_status!r}."
                ),
            }

        await asyncio.sleep(min(poll_interval_seconds, remaining))
