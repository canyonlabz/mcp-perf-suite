"""PerfPilot Reporting Agent -- AG2 ConversableAgent factory (F3.9 stub).

This module ships the four-file pattern's `agent.py` slot per V2 doc
§7.1.  In F3.9, it contains ONLY the agent factory -- no tool functions
are registered.  Tool wiring lands in F3.10 when the agent is promoted
from `in_development` to `available`.

The reporting-agent owns the final-mile delivery of performance test
results: chart generation from analysis data, Markdown report assembly,
multi-round Human-in-the-Loop revision (the only specialist that drives
HITL revision loops), and Confluence publishing.

**MCP collaboration:**

- PerfReport MCP (gateway, ``perfreport_*``) -- chart generation (PNG),
  Markdown report creation, AI-driven report revision, template
  management.
- Confluence MCP (gateway, ``confluence_*``) -- page creation, content
  update, image attachment, space/page navigation.

**Upstream dependencies:**

- Analysis-agent artifacts (``artifacts/{test_run_id}/analysis/``):
  SLA results, bottleneck analysis, error analysis, summary.
- Execution-agent artifacts (``artifacts/{test_run_id}/blazemeter/``):
  aggregate CSV (for embedding in report tables), public report URL.
- Monitoring-agent artifacts (``artifacts/{test_run_id}/datadog/``):
  infrastructure metrics (for infrastructure sections in the report).

Heavy imports (``autogen``, ``yaml``) live inside the functions that
need them so this module is cheap to import in smoke tests.

NOTE: This module deliberately does NOT use ``from __future__ import
annotations``.
"""

import logging
import pathlib

logger = logging.getLogger(__name__)

_AGENT_DIR = pathlib.Path(__file__).resolve().parent


def build_reporting_agent():
    """Construct and return the PerfPilot Reporting Agent.

    No tools are registered in F3.9 (stub).  F3.10 will wire:
    - Chart generation (response-time, throughput, error-rate charts)
    - Markdown report assembly (template-driven)
    - AI-driven report revision (multi-round HITL loop)
    - Confluence publishing (page creation + image attachment)
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
        name="reporting-agent",
        system_message=system_message,
        llm_config=llm_config,
        human_input_mode="NEVER",
    )

    logger.info("reporting-agent built (F3.9 stub — no tools registered)")
    return agent
