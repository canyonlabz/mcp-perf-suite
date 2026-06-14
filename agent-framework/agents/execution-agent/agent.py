"""PerfPilot Execution Agent -- AG2 ConversableAgent factory.

This module ships the four-file pattern's `agent.py` slot per V2 doc
§7.1: construct and return the agent on demand, with all configuration
loaded from the sibling `INSTRUCTIONS.md`, `agent_card.json`, and *one of*
`config.yaml` / `config.example.yaml`. Callers (the A2A task executor in
PBI 3.8.6, the orchestrator's `delegate_to_specialist` tool) import
`build_execution_agent()` and wrap the result.

**What this module ships (PBI 3.8.1 -- scaffold only):**

- A working `ConversableAgent` factory with the real long-form system
  prompt loaded from `INSTRUCTIONS.md`.
- Per-agent `llm_provider` resolution via the framework's
  `utils.base_agent.resolve_agent_config_path()` candidate walker.
- **No tools registered yet.** Tools land in:
    1. `start_performance_test(test_id)`                  -- PBI 3.8.3
    2. `wait_for_completion(run_id, ...)`                 -- PBI 3.8.4
    3. `extract_test_run_artifacts(test_run_id, ...)`     -- PBI 3.8.5
  When 3.8.3 lands, this module gains module-level tool functions and
  a `_register_tools(agent)` helper called from `build_execution_agent()`
  -- mirroring the orchestrator's PBI 3.7.3 pattern.

**Tool design notes (forward-looking):**

- Tools will be defined as module-level functions so smoke tests can
  import and exercise them directly (`from agents.execution_agent.agent
  import start_performance_test`) without spinning up an LLM. Note the
  Python module path uses an underscore (`execution_agent`) because the
  on-disk folder name is `execution-agent` -- this is fine because the
  package is loaded via `Path(__file__).resolve().parent`, not Python's
  import machinery, by both `utils/task_executor.py` (PBI 3.8.6) and
  the smoke tests.
- `start_performance_test` and `wait_for_completion` will wrap MCP
  tools `blazemeter_start_test` and `blazemeter_check_test_status` via
  `utils/mcp_client.py` (PBI 3.8.2). They return structured dicts
  (success or error) rather than raising, so the orchestrator can
  narrate failures to the user instead of the agent loop crashing.
- `extract_test_run_artifacts` will implement the 6-step extractor
  recipe (see INSTRUCTIONS.md §4) over six MCP calls in sequence,
  honoring the CRITICAL-vs-IMPORTANT step severity model (§7.1):
  a failure in Steps 1-3 returns `status: "failed"` immediately; a
  failure in Steps 4-6 records the error and continues, ultimately
  returning `status: "partial"` if any IMPORTANT step failed.

**What this module still does NOT do (deferred):**

- MCP client wiring (PBI 3.8.2 fills `utils/mcp_client.py`).
- A2A `task_executor` dispatch (PBI 3.8.6 adds `_run_execution_agent`).
- Card flip to `available` + populated `skills[]` (PBI 3.8.7).

Heavy imports (`autogen`, `yaml`) live inside the functions that need
them so this module is cheap to import in tests / IDE indexing that do
not exercise the agent.

NOTE: This module deliberately does NOT use `from __future__ import
annotations`. AG2 0.13.3 introspects tool function signatures via
pydantic's `TypeAdapter`, which cannot evaluate stringified `Annotated`
annotations. Keeping annotations as live types makes tool registration
work without per-call `.rebuild()` shenanigans (same constraint that
applies to the orchestrator's `agent.py`).
"""

import logging
from pathlib import Path
from typing import Any, Optional

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

    # _register_tools(agent) -- lands in PBI 3.8.3 when the first tool
    # (`start_performance_test`) is wired. Until then this factory
    # returns a tool-less agent. The orchestrator's
    # `list_available_specialists` tool already filters specialists by
    # `agents.yaml` enable state + on-disk folder presence -- it does
    # not require the specialist to have any tools registered. External
    # A2A clients see `skills: []` on this agent's card (also populated
    # in PBI 3.8.7) and degrade gracefully when delegating work that
    # would require a not-yet-registered tool.

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
