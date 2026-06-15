"""PerfPilot Monitoring Agent -- AG2 ConversableAgent factory (F3.9 stub).

This module ships the four-file pattern's `agent.py` slot per V2 doc
§7.1.  In F3.9, it contains ONLY the agent factory -- no tool functions
are registered.  Tool wiring lands in F3.10 when the agent is promoted
from `in_development` to `available`.

The monitoring-agent owns per-test-run observability data extraction:
pulling host metrics, Kubernetes metrics, APM traces, and application
logs from Datadog during and after a performance test run.  The
extracted data feeds the analysis-agent's SLA validation and bottleneck
attribution pipeline.

**MCP collaboration:**

- Datadog MCP (gateway, ``datadog_*``) -- host metrics (CPU, memory,
  disk, network), Kubernetes pod/node metrics, APM service traces, and
  application log queries scoped to a test run's time window.

**Timing contract:**

The monitoring-agent needs the test run's start_time and end_time
(provided by the execution-agent's artifact extraction) to scope its
Datadog queries.  It also uses environment-specific host/service
definitions from ``datadog-mcp/environments.json`` and optional custom
queries from ``datadog-mcp/custom_queries.json``.

Heavy imports (``autogen``, ``yaml``) live inside the functions that
need them so this module is cheap to import in smoke tests.

NOTE: This module deliberately does NOT use ``from __future__ import
annotations``.  AG2 0.13.3 introspects tool function signatures via
pydantic's ``TypeAdapter``, which cannot evaluate stringified
``Annotated`` annotations.
"""

import logging
import pathlib

logger = logging.getLogger(__name__)

_AGENT_DIR = pathlib.Path(__file__).resolve().parent


def build_monitoring_agent():
    """Construct and return the PerfPilot Monitoring Agent.

    Returns a ``ConversableAgent`` with the system prompt loaded from
    ``INSTRUCTIONS.md`` and LLM configuration resolved from the
    per-agent config cascade (``config.yaml`` > ``config.example.yaml``
    > global ``agents.yaml`` fallback).

    No tools are registered in F3.9 (stub).  F3.10 will wire:
    - Host metric extraction (CPU, memory, disk, network)
    - Kubernetes metric extraction (pod, node, container)
    - APM trace extraction (service latency, error rates)
    - Log query extraction (application error logs)
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
        name="monitoring-agent",
        system_message=system_message,
        llm_config=llm_config,
        human_input_mode="NEVER",
    )

    logger.info("monitoring-agent built (F3.9 stub — no tools registered)")
    return agent
