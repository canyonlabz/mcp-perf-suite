"""PerfPilot Orchestrator — AG2 ConversableAgent factory (PBI 3.7.1 scaffold).

This module ships the four-file pattern's `agent.py` slot per V2 doc §7.1:
construct and return the agent on demand, with all configuration loaded
from the sibling `INSTRUCTIONS.md`, `agent_card.json`, and *one of*
`config.yaml` / `config.example.yaml`. Callers (the AG-UI bridge in PBI
3.7.7, the A2A task executor in PBI 3.7.8) import `build_orchestrator()`
and wrap the result.

What this scaffold gives you today:

- A working `ConversableAgent` instance with a placeholder system prompt
  loaded from `INSTRUCTIONS.md`.
- Resolution of the per-agent `llm_provider` block via the same
  candidate-resolution helper every other agent will use:
  `utils.base_agent.resolve_agent_config_path()` walks
  `config.yaml` (operator-side, gitignored) -> `config.example.yaml`
  (committed default) and the factory loads whichever exists.
  Falls back to `utils.llm_provider.load_default_provider_config()` if
  neither file declares an `llm_provider:` block.
- Empty `tools=[]` — the four delegation tools land in PBIs 3.7.3-3.7.6.
- A name (`"orchestrator"`) and `system_message` that PBI 3.7.7 can
  swap in for `utils.copilotkit_stub.build_stub_orchestrator()` with a
  one-line import change in `agui_server.py`.

What this scaffold does NOT do yet:

- No MCP client wiring (deferred to F3.8 per Decision 12).
- No tools beyond AG2's built-ins (PBIs 3.7.3-3.7.6).
- No DB-loaded message history (PBI 3.7.7 plus Decision 14).
- No A2A `task_executor` dispatch (PBI 3.7.8).

Heavy imports (`autogen`, `yaml`) live inside the factory so this module
is cheap to import in tests / IDE indexing that do not exercise the agent.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

AGENT_DIR = Path(__file__).resolve().parent
AGENT_NAME = "orchestrator"

INSTRUCTIONS_PATH = AGENT_DIR / "INSTRUCTIONS.md"
AGENT_CARD_PATH = AGENT_DIR / "agent_card.json"


def build_orchestrator() -> Any:
    """Construct the PerfPilot Orchestrator AG2 ConversableAgent.

    Resolution order for the LLM provider:
      1. Per-agent `llm_provider` block in the first existing of
         `config.yaml` (operator-side override, gitignored) or
         `config.example.yaml` (committed default).
      2. Global fallback `config/agents.yaml -> default_llm_provider`
         via `utils.llm_provider.load_default_provider_config()`.

    Returns:
        An `autogen.ConversableAgent` instance with the placeholder
        `INSTRUCTIONS.md` content as `system_message`, no registered
        tools, and `human_input_mode="NEVER"` (this is a server agent).

    Raises:
        FileNotFoundError: when one of the four sibling files is missing.
        Anything `LLMProvider.to_ag2_config()` raises when credentials
        are not configured (caller is expected to surface that to the
        operator with the existing fallback messaging — see
        `agui_server._mount_copilotkit()` for the prior-art pattern).
    """
    # Local imports so this module is cheap to import for structural tests.
    from autogen import ConversableAgent  # type: ignore

    from utils.llm_provider import LLMProvider, load_default_provider_config

    system_message = _load_system_message()
    provider_config = _resolve_provider_config()
    provider = LLMProvider(provider_config)

    log.info(
        "Building %s (provider=%s, model=%s)",
        AGENT_NAME, provider.provider, provider.get_model_name(),
    )

    return ConversableAgent(
        name=AGENT_NAME,
        system_message=system_message,
        llm_config=provider.to_ag2_config(),
        # Server-side: never block on stdin.
        human_input_mode="NEVER",
        # PBI 3.7.1: no tools yet, so cap auto-reply at 1. PBIs 3.7.3-3.7.6
        # add tools; PBI 3.7.7 raises this so the orchestrator can do its
        # own multi-turn delegation cycles.
        max_consecutive_auto_reply=1,
    )


def _load_system_message() -> str:
    """Read `INSTRUCTIONS.md` as the AG2 `system_message`."""
    if not INSTRUCTIONS_PATH.exists():
        raise FileNotFoundError(
            f"Orchestrator INSTRUCTIONS.md not found at {INSTRUCTIONS_PATH}. "
            f"PBI 3.7.1 scaffold requires this file to exist; PBI 3.7.2 "
            f"replaces the placeholder content with the real long-form prompt."
        )
    # utf-8-sig transparently strips a leading BOM if any Windows editor
    # / Write tool added one (PyYAML + json.load both reject BOMs).
    return INSTRUCTIONS_PATH.read_text(encoding="utf-8-sig")


def _resolve_provider_config() -> dict:
    """Return the merged LLM-provider config for the orchestrator.

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
        log.debug("Orchestrator using per-agent llm_provider override from %s", _resolved_config_filename())
        return merge_env_credentials(agent_block)

    log.debug("Orchestrator using default_llm_provider from agents.yaml")
    return load_default_provider_config()


def _load_per_agent_llm_block() -> Optional[dict]:
    """Parse the resolved per-agent config and return its `llm_provider:` block.

    The config file is whichever of `config.yaml` (operator-side override,
    gitignored) or `config.example.yaml` (committed default) the
    framework loader finds first via
    `utils.base_agent.resolve_agent_config_path()`.

    Returns None when neither file exists, the YAML is empty, or the
    `llm_provider:` key is absent / commented out (the PBI 3.7.1 default
    in `config.example.yaml`).
    """
    from utils.base_agent import resolve_agent_config_path

    config_path = resolve_agent_config_path(AGENT_DIR)
    if config_path is None:
        log.warning(
            "Orchestrator config not found under %s "
            "(expected config.yaml or config.example.yaml); "
            "using default LLM provider.",
            AGENT_DIR,
        )
        return None

    import yaml  # deferred so structural import does not require PyYAML

    # utf-8-sig matches utils.base_agent.load_agent_definition's read path
    # so any BOM emitted by a Windows editor is transparently stripped.
    with open(config_path, "r", encoding="utf-8-sig") as f:
        parsed = yaml.safe_load(f) or {}
    block = parsed.get("llm_provider")
    if not block or not isinstance(block, dict):
        return None
    return dict(block)


def _resolved_config_filename() -> str:
    """Helper for log messages: return just the filename of the resolved config."""
    from utils.base_agent import resolve_agent_config_path

    path = resolve_agent_config_path(AGENT_DIR)
    return path.name if path else "<none>"
