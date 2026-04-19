"""
Target resolver for MS Teams notification destinations.

Resolves named targets (from config.yaml) to conversation IDs,
or passes raw IDs through unchanged.
"""

import logging
from typing import Any

from utils.config import load_config

logger = logging.getLogger("msteams-mcp.target-resolver")

_config = load_config()
_teams_cfg = _config.get("teams", {})
_targets_cfg = _teams_cfg.get("notification_targets", {})


def _get_channels() -> dict[str, dict[str, Any]]:
    return _targets_cfg.get("channels", {})


def _get_default_chat() -> dict[str, Any]:
    return _targets_cfg.get("default_chat", {})


def resolve_target(target: str) -> dict[str, Any]:
    """
    Resolve a target string to a conversation ID and metadata.

    Resolution logic:
        1. If target matches a named channel in config → use its conversation_id.
        2. If target == "default_chat" → use the default_chat entry.
        3. Otherwise, treat target as a raw conversation ID.

    Returns:
        Dict with keys: conversation_id, target_name, target_type,
        and optional template (per-channel template override).
    """
    channels = _get_channels()

    if target in channels:
        entry = channels[target]
        conversation_id = entry.get("conversation_id", "")
        if not conversation_id:
            logger.warning("Named channel '%s' has no conversation_id in config", target)
        return {
            "conversation_id": conversation_id,
            "target_name": target,
            "target_type": "channel",
            "template": entry.get("template"),
        }

    if target == "default_chat":
        chat = _get_default_chat()
        conversation_id = chat.get("conversation_id", "")
        return {
            "conversation_id": conversation_id,
            "target_name": "default_chat",
            "target_type": "chat",
            "template": chat.get("template"),
        }

    return {
        "conversation_id": target,
        "target_name": None,
        "target_type": "raw",
        "template": None,
    }


def list_configured_targets() -> dict[str, Any]:
    """
    List all configured notification targets from config.yaml.

    Returns channels and default_chat entries with their metadata.
    """
    channels = _get_channels()
    chat = _get_default_chat()

    channel_list = []
    for name, entry in channels.items():
        channel_list.append({
            "name": name,
            "conversation_id": entry.get("conversation_id", ""),
            "description": entry.get("description", ""),
            "template": entry.get("template"),
        })

    result: dict[str, Any] = {
        "channels": channel_list,
        "channel_count": len(channel_list),
    }

    if chat:
        result["default_chat"] = {
            "conversation_id": chat.get("conversation_id", ""),
            "description": chat.get("description", ""),
            "template": chat.get("template"),
        }

    return result
