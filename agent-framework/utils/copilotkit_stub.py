"""Stub orchestrator agent for the AG-UI / CopilotKit endpoint (PBI 3.6.3).

This module is a placeholder that exists ONLY between Feature 3.6 and
Feature 3.7. It gives the AG-UI bridge something real to mount at
`/copilotkit` so the wire (browser -> AG-UI SSE -> AG2 -> LLM) can be
smoke-tested end-to-end before the actual orchestrator is built.

Feature 3.7 will:

  1. Create `agents/orchestrator/{agent.py, tools.py, prompts.py, config.yaml}`
     following the V2 doc's 4-file specialist-agent pattern.
  2. Replace the import in `agui_server.py` from
     `utils.copilotkit_stub.build_stub_orchestrator` to
     `agents.orchestrator.agent.build_orchestrator`.
  3. **Delete this file.**

Search for the marker `STUB-F3.6.3` to find the lines that change.
"""

from __future__ import annotations

import logging
from typing import Any

from .llm_provider import LLMProvider, load_default_provider_config

log = logging.getLogger(__name__)

STUB_SYSTEM_PROMPT = (
    "You are a placeholder for the PerfPilot Orchestrator Agent. "
    "The full orchestrator is being built in Feature 3.7. "
    "When the user sends a message, briefly acknowledge it, tell them "
    "the orchestrator is on the way in F3.7, and remind them they can "
    "still use the A2A surface on port 8001 to drive specialist agents "
    "directly. Keep responses to two short sentences."
)


def build_stub_orchestrator() -> Any:
    """Construct an AG2 ConversableAgent wired to our LLMProvider.

    Returns the agent so callers (the AG-UI bridge) can wrap it with
    `AGUIStream(...)`. Importing AG2 lazily keeps `utils/` test-friendly
    when AG2 isn't installed - useful for unit tests of session_store /
    task_store / hitl_store that have no need for the agent stack.
    """
    # STUB-F3.6.3
    from autogen import ConversableAgent

    provider_config = load_default_provider_config()
    provider = LLMProvider(provider_config)
    log.info(
        "Building stub orchestrator (provider=%s, model=%s)",
        provider.provider,
        provider.get_model_name(),
    )

    return ConversableAgent(
        name="orchestrator_stub",
        system_message=STUB_SYSTEM_PROMPT,
        llm_config=provider.to_ag2_config(),
        # Don't block on stdin - this is a server.
        human_input_mode="NEVER",
        # Single reply; orchestrator stub is not supposed to multi-turn yet.
        max_consecutive_auto_reply=1,
    )
