# utils/sla_config.py
"""
SLA Configuration Loader, Resolver, and Validator.

Loads SLA definitions from slas.yaml, resolves per-API SLA thresholds
based on a three-level pattern matching hierarchy, and validates that
configured patterns match actual test result labels.

This module is the single point of access for all SLA-related configuration.
No hardcoded SLA values exist in this module or should exist anywhere in the
codebase. If slas.yaml is missing, a clear error is raised immediately.
"""

import yaml
import os
import re
import fnmatch
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VALID_SLA_UNITS = {"P90", "P95", "P99"}
SLA_CONFIG_FILENAME = "slas.yaml"

# Module-level cache for loaded SLA config
_SLA_CONFIG_CACHE: Optional[Dict[str, Any]] = None


# ===========================================================================
# SLA Config Loader (Task 1.2)
# ===========================================================================

def load_sla_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Load and validate the SLA configuration from slas.yaml.

    The file is expected at the root of the perfanalysis-mcp directory
    (same level as config.yaml).

    Args:
        force_reload: If True, bypass the cache and reload from disk.

    Returns:
        Validated SLA configuration dict.

    Raises:
        FileNotFoundError: If slas.yaml does not exist.
        ValueError: If the configuration schema is invalid.
    """
    global _SLA_CONFIG_CACHE

    if _SLA_CONFIG_CACHE is not None and not force_reload:
        return _SLA_CONFIG_CACHE

    # slas.yaml lives at the MCP root (one level up from utils/)
    mcp_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sla_config_path = os.path.join(mcp_root, SLA_CONFIG_FILENAME)

    if not os.path.exists(sla_config_path):
        raise FileNotFoundError(
            f"SLA configuration file not found: {sla_config_path}\n"
            f"This file is required for SLA evaluation. "
            f"Copy 'slas.example.yaml' to 'slas.yaml' and configure your SLA profiles.\n"
            f"See docs/sla-configuration-guide.md for details."
        )

    with open(sla_config_path, 'r', encoding='utf-8') as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing '{SLA_CONFIG_FILENAME}': {e}")

    _validate_sla_config(config)

    _SLA_CONFIG_CACHE = config
    logger.info("SLA configuration loaded successfully from '%s'.", sla_config_path)
    return config


# ===========================================================================
# Schema Validation
# ===========================================================================

def _validate_sla_config(config: Dict[str, Any]) -> None:
    """
    Validate the top-level structure and all nested objects in slas.yaml.

    Raises:
        ValueError: If any required field is missing or has an invalid value.
    """
    if not isinstance(config, dict):
        raise ValueError(
            f"{SLA_CONFIG_FILENAME} must contain a YAML mapping (dict) at the root level."
        )

    # -- version (required) --------------------------------------------------
    if "version" not in config:
        raise ValueError(f"{SLA_CONFIG_FILENAME} must include a 'version' field.")

    # -- default_sla (required, all fields mandatory at file level) ----------
    if "default_sla" not in config:
        raise ValueError(f"{SLA_CONFIG_FILENAME} must include a 'default_sla' section.")

    _validate_file_level_default_sla(config["default_sla"])

    # -- slas (optional list of profiles) ------------------------------------
    slas = config.get("slas", [])
    if not isinstance(slas, list):
        raise ValueError("'slas' must be a list of SLA profile objects.")

    seen_ids: set = set()
    for i, profile in enumerate(slas):
        _validate_sla_profile(profile, i, seen_ids)


def _validate_file_level_default_sla(block: Dict[str, Any]) -> None:
    """
    Validate the file-level default_sla block.

    At the file level ALL fields are required because this is the ultimate
    fallback -- there are no hardcoded defaults anywhere in the codebase.
    """
    context = "default_sla"

    if not isinstance(block, dict):
        raise ValueError(f"'{context}' must be a mapping (dict).")

    required_fields = ["response_time_sla_ms", "sla_unit", "error_rate_threshold"]
    for field in required_fields:
        if field not in block:
            raise ValueError(
                f"'{context}' must include '{field}'. "
                f"All fields are required at the file level because there are no "
                f"hardcoded fallback values."
            )

    _validate_response_time(block["response_time_sla_ms"], context)
    _validate_sla_unit(block["sla_unit"], context)
    _validate_error_rate(block["error_rate_threshold"], context)


def _validate_sla_profile(profile: Dict[str, Any], index: int, seen_ids: set) -> None:
    """Validate a single SLA profile entry in the slas list."""
    if not isinstance(profile, dict):
        raise ValueError(f"SLA profile at index {index} must be a mapping (dict).")

    # -- id (required, unique) -----------------------------------------------
    profile_id = profile.get("id")
    if not profile_id or not isinstance(profile_id, str):
        raise ValueError(
            f"SLA profile at index {index} must have a non-empty string 'id' field."
        )

    if profile_id in seen_ids:
        raise ValueError(f"Duplicate SLA profile id: '{profile_id}'.")
    seen_ids.add(profile_id)

    context_prefix = f"slas['{profile_id}']"

    # -- default_sla (required at profile level, response_time_sla_ms mandatory) --
    if "default_sla" not in profile:
        raise ValueError(
            f"{context_prefix} must include a 'default_sla' section with at least "
            f"'response_time_sla_ms'."
        )

    profile_default = profile["default_sla"]
    if not isinstance(profile_default, dict):
        raise ValueError(f"{context_prefix}.default_sla must be a mapping (dict).")

    if "response_time_sla_ms" not in profile_default:
        raise ValueError(
            f"{context_prefix}.default_sla must include 'response_time_sla_ms'."
        )

    _validate_response_time(
        profile_default["response_time_sla_ms"],
        f"{context_prefix}.default_sla"
    )

    # sla_unit and error_rate_threshold are optional (inherit from file default)
    if "sla_unit" in profile_default:
        _validate_sla_unit(profile_default["sla_unit"], f"{context_prefix}.default_sla")

    if "error_rate_threshold" in profile_default:
        _validate_error_rate(
            profile_default["error_rate_threshold"],
            f"{context_prefix}.default_sla"
        )

    # -- api_overrides (optional list) ----------------------------------------
    overrides = profile.get("api_overrides", [])
    if not isinstance(overrides, list):
        raise ValueError(f"{context_prefix}.api_overrides must be a list.")

    for j, override in enumerate(overrides):
        _validate_api_override(override, j, context_prefix)


def _validate_api_override(
    override: Dict[str, Any], index: int, context_prefix: str
) -> None:
    """Validate a single api_override entry."""
    ctx = f"{context_prefix}.api_overrides[{index}]"

    if not isinstance(override, dict):
        raise ValueError(f"{ctx} must be a mapping (dict).")

    if "pattern" not in override:
        raise ValueError(f"{ctx} must include a 'pattern' field.")

    if not isinstance(override["pattern"], str) or not override["pattern"].strip():
        raise ValueError(f"{ctx}.pattern must be a non-empty string.")

    if "response_time_sla_ms" not in override:
        raise ValueError(f"{ctx} must include a 'response_time_sla_ms' field.")

    _validate_response_time(override["response_time_sla_ms"], ctx)

    # sla_unit and error_rate_threshold are optional (inherit from profile/file default)
    if "sla_unit" in override:
        _validate_sla_unit(override["sla_unit"], ctx)

    if "error_rate_threshold" in override:
        _validate_error_rate(override["error_rate_threshold"], ctx)


# ===========================================================================
# Field-Level Validators
# ===========================================================================

def _validate_response_time(value: Any, context: str) -> None:
    """Validate that response_time_sla_ms is a positive number."""
    if not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(
            f"'{context}.response_time_sla_ms' must be a positive number, got: {value}"
        )


def _validate_sla_unit(value: Any, context: str) -> None:
    """Validate that sla_unit is one of the supported percentile options."""
    if value not in VALID_SLA_UNITS:
        raise ValueError(
            f"'{context}.sla_unit' must be one of {sorted(VALID_SLA_UNITS)}, got: '{value}'"
        )


def _validate_error_rate(value: Any, context: str) -> None:
    """Validate that error_rate_threshold is a non-negative number."""
    if not isinstance(value, (int, float)) or value < 0:
        raise ValueError(
            f"'{context}.error_rate_threshold' must be a non-negative number, got: {value}"
        )
