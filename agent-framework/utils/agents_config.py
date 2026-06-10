"""Loader for `config/agents.yaml` (or its committed `.example` fallback).

Provides three small helpers used by the A2A server, the AG-UI bridge, and
the orchestrator:

    load_agents_config()  -> the full parsed dict
    is_agent_enabled()    -> per-agent on/off bool
    list_enabled_agents() -> list of agent names that are enabled

The first call caches the parsed YAML in-process. Hot-reload during dev is
left for future Features; for Epic 3, restarting the server picks up edits.

Heavy import (`yaml`) is deferred into `load_agents_config()` so this module
can be imported in environments without PyYAML installed.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

KNOWN_AGENTS = (
    "orchestrator",
    "execution-agent",
    "script-agent",
    "monitoring-agent",
    "analysis-agent",
    "reporting-agent",
    "notifications-agent",
)

_cache_lock = threading.Lock()
_cached: Optional[dict] = None
_cached_for: Optional[Path] = None


def load_agents_config(framework_dir: Optional[Path] = None, *, force_reload: bool = False) -> dict:
    """Return the parsed `agents.yaml` (or `agents.example.yaml`) as a dict.

    Mirrors `utils.llm_provider.load_agents_yaml` but caches the result so
    repeated lookups are O(1). The cache key is the resolved framework dir;
    set `force_reload=True` to re-read from disk (useful in tests).

    Returns:
        Parsed YAML dict. Empty dict (with warning) if neither file exists.
    """
    global _cached, _cached_for
    import yaml  # deferred so module imports without PyYAML installed

    if framework_dir is None:
        framework_dir = Path(__file__).resolve().parent.parent

    with _cache_lock:
        if not force_reload and _cached is not None and _cached_for == framework_dir:
            return _cached

        candidates = (
            framework_dir / "config" / "agents.yaml",
            framework_dir / "config" / "agents.example.yaml",
        )
        for candidate in candidates:
            if candidate.exists():
                with open(candidate, "r", encoding="utf-8") as f:
                    _cached = yaml.safe_load(f) or {}
                _cached_for = framework_dir
                log.info("Loaded agents config from %s", candidate)
                return _cached

        log.warning(
            "Neither agents.yaml nor agents.example.yaml found under %s/config/. "
            "All agents will be treated as disabled.",
            framework_dir,
        )
        _cached = {}
        _cached_for = framework_dir
        return _cached


def is_agent_enabled(agent_name: str, framework_dir: Optional[Path] = None) -> bool:
    """Return True if `agent_name` is enabled in `agents.yaml`.

    Unknown agents (not in `KNOWN_AGENTS`) are always disabled. An agent
    listed in the config without an explicit `enabled` key defaults to True.
    """
    if agent_name not in KNOWN_AGENTS:
        return False

    config = load_agents_config(framework_dir)
    agents_block = config.get("agents") or {}
    entry = agents_block.get(agent_name)
    if entry is None:
        return False
    if isinstance(entry, dict):
        return bool(entry.get("enabled", True))
    return bool(entry)


def list_enabled_agents(framework_dir: Optional[Path] = None) -> list[str]:
    """Return the list of agent names that are currently enabled."""
    return [name for name in KNOWN_AGENTS if is_agent_enabled(name, framework_dir)]
