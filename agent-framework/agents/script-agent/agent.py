"""PerfPilot Script Agent -- AG2 ConversableAgent factory (F3.9 stub).

This module ships the four-file pattern's `agent.py` slot per V2 doc
§7.1.  In F3.9, it contains ONLY the agent factory -- no tool functions
are registered.  Tool wiring lands in F3.10 when the agent is promoted
from `in_development` to `available`.

The script-agent owns the JMeter-script lifecycle: capture network
traffic (Playwright MCP), convert to JMX (JMeter MCP), look up known
issues (PerfMemory MCP), iteratively debug, and deliver a clean script
for the execution-agent to run.

**Three-way MCP collaboration:**

1. JMeter MCP   (gateway, ``jmeter_*``)      -- JMX creation, editing,
   component manipulation, smoke testing, HAR/Swagger conversion,
   correlation.
2. PerfMemory MCP (gateway, ``perfmemory_*``) -- Similar-issue lookup
   (pgvector semantic search), cross-project pattern discovery (Apache
   AGE graph RAG), and automatic solution application.
3. Playwright MCP (direct, ``browser_*``)     -- Browser automation for
   live network capture against real applications.  Runs outside the
   gateway-mcp; the script-agent connects to it directly.

**Dual test_run_id lifecycle:**

- **Script-creation phase** uses a ``script_run_id`` (user-supplied or
  auto-minted) to organize input files and generated JMX artifacts under
  ``artifacts/{script_run_id}/jmeter/``.
- **Test-execution phase** uses the BlazeMeter-generated ``test_run_id``
  (owned by the execution-agent).  These are separate artifact trees by
  design: one for what the AI created, one for real-world test results.

Heavy imports (``autogen``, ``yaml``) live inside the functions that need
them so this module is cheap to import in smoke tests.

NOTE: This module deliberately does NOT use ``from __future__ import
annotations``.  AG2 0.13.3 introspects tool function signatures via
pydantic's ``TypeAdapter``, which cannot evaluate stringified
``Annotated`` annotations.
"""

import logging
import pathlib

logger = logging.getLogger(__name__)

_AGENT_DIR = pathlib.Path(__file__).resolve().parent


def build_script_agent():
    """Construct and return the PerfPilot Script Agent.

    Returns a ``ConversableAgent`` with the system prompt loaded from
    ``INSTRUCTIONS.md`` and LLM configuration resolved from the
    per-agent config cascade (``config.yaml`` > ``config.example.yaml``
    > global ``agents.yaml`` fallback).

    No tools are registered in F3.9 (stub).  F3.10 will wire:
    - JMX generation tools (HAR/Swagger/Playwright capture)
    - Script debugging / smoke-test loop
    - PerfMemory lookup + automatic fix application
    """
    import yaml

    try:
        from autogen import ConversableAgent
    except ImportError:
        from ag2 import ConversableAgent

    instructions_path = _AGENT_DIR / "INSTRUCTIONS.md"
    system_message = instructions_path.read_text(encoding="utf-8-sig")

    from utils.base_agent import resolve_agent_config_path
    from utils.llm_provider import build_llm_config

    config_path = resolve_agent_config_path(_AGENT_DIR)
    with open(config_path, encoding="utf-8-sig") as fh:
        agent_config = yaml.safe_load(fh) or {}

    llm_config = build_llm_config(agent_config.get("llm_provider"))

    agent = ConversableAgent(
        name="script-agent",
        system_message=system_message,
        llm_config=llm_config,
        human_input_mode="NEVER",
    )

    logger.info("script-agent built (F3.9 stub — no tools registered)")
    return agent
