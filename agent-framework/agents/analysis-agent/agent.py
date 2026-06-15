"""PerfPilot Analysis Agent -- AG2 ConversableAgent factory (F3.9 stub).

This module ships the four-file pattern's `agent.py` slot per V2 doc
§7.1.  In F3.9, it contains ONLY the agent factory -- no tool functions
are registered.  Tool wiring lands in F3.10 when the agent is promoted
from `in_development` to `available`.

The analysis-agent owns post-test data correlation and verdict
generation: SLA validation (P90 response times against ``slas.yaml``
thresholds), bottleneck attribution (correlating BlazeMeter results
with Datadog infrastructure metrics), and log-error analysis (mapping
failed transactions to root-cause buckets).

**MCP collaboration:**

- PerfAnalysis MCP (gateway, ``perfanalysis_*``) -- automated SLA
  validation, bottleneck detection, comparative analysis, and
  structured analysis output generation.

**Upstream dependencies:**

- Execution-agent artifacts (``artifacts/{test_run_id}/blazemeter/``):
  aggregate CSV, test-results CSV, JMeter log analysis
- Monitoring-agent artifacts (``artifacts/{test_run_id}/datadog/``):
  host metrics, K8s metrics, APM traces, application logs

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


def build_analysis_agent():
    """Construct and return the PerfPilot Analysis Agent.

    Returns a ``ConversableAgent`` with the system prompt loaded from
    ``INSTRUCTIONS.md`` and LLM configuration resolved from the
    per-agent config cascade.

    No tools are registered in F3.9 (stub).  F3.10 will wire:
    - SLA validation (P90 vs slas.yaml thresholds)
    - Bottleneck attribution (BlazeMeter + Datadog correlation)
    - Log-error analysis (root-cause bucketing)
    - Comparative analysis (multi-run trend detection)
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
        name="analysis-agent",
        system_message=system_message,
        llm_config=llm_config,
        human_input_mode="NEVER",
    )

    logger.info("analysis-agent built (F3.9 stub — no tools registered)")
    return agent
