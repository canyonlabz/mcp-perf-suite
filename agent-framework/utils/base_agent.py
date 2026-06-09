"""Factory for constructing AG2 ConversableAgent instances from agent folders.

This module provides the framework-level convention for how an agent's
four-file pattern (`agent.py`, `agent_card.json`, `INSTRUCTIONS.md`,
`config.yaml`) is loaded from disk. Each specialist agent's `agent.py` calls
into `create_agent()` and supplies agent-specific behavior on top of the
shared factory.

Status:
    F3.2 (this commit) - public API skeleton, four-file loading, name
        validation. The actual `ConversableAgent` construction is a placeholder.
    F3.4 - LLM provider wiring once `utils/llm_provider.py` lands.
    F3.7 - real `ConversableAgent` creation, starting with the orchestrator.
    F3.13 - auth middleware and OpenTelemetry span hooks lit up.

Heavy imports (`ag2` / `autogen`) are deferred into the function that needs
them so this module can be imported in environments without AG2 installed
(structural smoke test, IDE indexing, etc.).
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

REQUIRED_AGENT_FILES = ("agent.py", "agent_card.json", "INSTRUCTIONS.md", "config.yaml")


@dataclass
class AgentDefinition:
    """Materialized view of an agent's four-file pattern.

    Loaded from disk by `load_agent_definition()` and consumed by
    `create_agent()`. The fields capture the entire static description of
    an agent before its runtime LLM provider and MCP client are wired in.
    """

    name: str
    folder: Path
    config: dict
    instructions: str
    agent_card: dict
    enabled: bool = True
    extras: dict = field(default_factory=dict)


def load_agent_definition(agent_folder: Path) -> AgentDefinition:
    """Load an agent's four-file pattern from disk.

    Args:
        agent_folder: Path to `agents/<agent-name>/`.

    Returns:
        `AgentDefinition` with config, instructions, and agent card loaded.

    Raises:
        FileNotFoundError: If the folder or any required file is missing.
        ValueError: If `config.yaml` or `agent_card.json` are malformed.
    """
    if not agent_folder.is_dir():
        raise FileNotFoundError(f"Agent folder not found: {agent_folder}")

    name = agent_folder.name

    for required in REQUIRED_AGENT_FILES:
        candidate = agent_folder / required
        if not candidate.exists():
            raise FileNotFoundError(
                f"Required file missing for agent '{name}': {candidate}"
            )

    config_path = agent_folder / "config.yaml"
    instructions_path = agent_folder / "INSTRUCTIONS.md"
    agent_card_path = agent_folder / "agent_card.json"

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Agent '{name}' config.yaml must be a YAML mapping")

    with open(instructions_path, "r", encoding="utf-8") as f:
        instructions = f.read()

    with open(agent_card_path, "r", encoding="utf-8") as f:
        try:
            agent_card = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Agent '{name}' agent_card.json is not valid JSON") from exc

    enabled = bool(config.get("enabled", True))

    return AgentDefinition(
        name=name,
        folder=agent_folder,
        config=config,
        instructions=instructions,
        agent_card=agent_card,
        enabled=enabled,
    )


def discover_agents(agents_root: Path) -> list[AgentDefinition]:
    """Walk `agents/` and load every agent that has the full four-file pattern.

    Subfolders that do not yet have all four files (for example, freshly
    scaffolded folders containing only `.gitkeep`) are skipped silently and
    logged at DEBUG level. This lets the scaffolding coexist with the eventual
    real agents in F3.7+.

    Args:
        agents_root: Path to `agent-framework/agents/`.

    Returns:
        List of fully loaded `AgentDefinition` instances, sorted by name.
    """
    if not agents_root.is_dir():
        log.warning("agents/ folder not found at %s", agents_root)
        return []

    definitions: list[AgentDefinition] = []
    for child in sorted(agents_root.iterdir()):
        if not child.is_dir():
            continue
        if not all((child / required).exists() for required in REQUIRED_AGENT_FILES):
            log.debug("Skipping incomplete agent folder: %s", child)
            continue
        try:
            definitions.append(load_agent_definition(child))
        except Exception:
            log.exception("Failed to load agent definition from %s", child)
    return definitions


def create_agent(definition: AgentDefinition, **overrides: Any) -> Any:
    """Construct an AG2 `ConversableAgent` from a loaded `AgentDefinition`.

    F3.2 status: this is a structural skeleton. Until F3.7 lands the real
    ConversableAgent factory (with LLM provider wiring from F3.4 and MCP
    namespace filtering via `mcp_client.py`), this returns a placeholder
    dictionary describing what *would* be created. Callers in F3.2 are not
    expected to interact with the return value.

    Args:
        definition: `AgentDefinition` from `load_agent_definition()`.
        **overrides: Optional keyword overrides applied on top of
            `definition.config`. Useful for tests and orchestrator-driven
            instantiation.

    Returns:
        AG2 `ConversableAgent` instance (in F3.7+); a placeholder dict in F3.2.
    """
    if not definition.enabled:
        log.info(
            "Agent '%s' is disabled in config; create_agent() returning disabled marker",
            definition.name,
        )
        return {
            "agent_name": definition.name,
            "status": "disabled",
            "reason": "config.yaml has enabled: false",
        }

    log.warning(
        "create_agent('%s') is a F3.2 skeleton; real ConversableAgent wiring lights up in F3.7",
        definition.name,
    )
    return {
        "agent_name": definition.name,
        "status": "skeleton",
        "config": dict(definition.config),
        "overrides": dict(overrides),
        "instructions_preview": definition.instructions[:200],
    }
