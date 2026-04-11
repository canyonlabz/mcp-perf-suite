import os
import platform
import yaml
from pathlib import Path
from dotenv import load_dotenv


def _get_mcp_root() -> Path:
    """Resolve the perfmemory-mcp directory from this file's location."""
    return Path(__file__).resolve().parent.parent


def _load_yaml_config() -> dict:
    """Load YAML config with platform-specific override support.

    Resolution order (first match wins):
      1. config.windows.yaml / config.mac.yaml  (platform-specific)
      2. config.yaml                             (default)

    Returns:
        Parsed YAML dict, or empty dict if no config file found.
    """
    mcp_root = _get_mcp_root()

    config_map = {
        "Darwin": "config.mac.yaml",
        "Windows": "config.windows.yaml",
    }

    system = platform.system()
    platform_config = config_map.get(system)

    candidates = [platform_config, "config.yaml"] if platform_config else ["config.yaml"]

    for filename in candidates:
        config_path = mcp_root / filename
        if config_path.exists():
            with open(config_path, "r") as f:
                try:
                    return yaml.safe_load(f) or {}
                except yaml.YAMLError as e:
                    raise Exception(f"Error parsing '{filename}': {e}")

    return {}


def load_config() -> dict:
    """Load PerfMemory configuration from YAML config and .env file.

    Tunable settings (search thresholds, top_k, debug flags) come from
    config.yaml (or platform-specific overrides). Secrets and environment-
    specific values (API keys, database credentials, SSL) come from .env
    or system environment variables.

    Returns:
        dict with keys: embedding, database, search, debug
    """
    mcp_root = _get_mcp_root()
    env_path = mcp_root / ".env"

    # Local dev: loads .env file if present.
    # Docker/cloud: .env won't exist; os.getenv() reads from container
    # environment variables injected by the platform.
    if env_path.exists():
        load_dotenv(env_path)

    yaml_cfg = _load_yaml_config()
    search_cfg = yaml_cfg.get("search", {})
    graph_cfg = yaml_cfg.get("graph", {})
    general_cfg = yaml_cfg.get("general", {})

    return {
        "embedding": {
            "provider": os.getenv("EMBEDDING_PROVIDER", "openai"),
            "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
            "openai_model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            "azure_api_key": os.getenv("AZURE_OPENAI_API_KEY", ""),
            "azure_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            "azure_deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT", "text-embedding-3-small"),
            "azure_api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            "ollama_model": os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        },
        "database": {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("POSTGRES_PORT", "5432")),
            "dbname": os.getenv("POSTGRES_DB", "perfmemory"),
            "user": os.getenv("POSTGRES_USER", "perfadmin"),
            "password": os.getenv("POSTGRES_PASSWORD", ""),
            "sslmode": os.getenv("POSTGRES_SSLMODE", "prefer"),
            "sslrootcert": os.getenv("POSTGRES_SSLROOTCERT", ""),
        },
        "search": {
            "top_k": search_cfg.get("top_k", 5),
            "threshold": search_cfg.get("similarity_threshold", 0.60),
            "ef_search": search_cfg.get("ef_search", 40),
        },
        "graph": {
            "enabled": graph_cfg.get("enabled", False),
            "graph_name": graph_cfg.get("graph_name", "perf_knowledge"),
            "vector_weight": graph_cfg.get("vector_weight", 0.6),
            "graph_weight": graph_cfg.get("graph_weight", 0.4),
            "embedding_edge_threshold": graph_cfg.get("embedding_edge_threshold", 0.82),
            "max_embedding_edges": graph_cfg.get("max_embedding_edges", 3),
        },
        "debug": general_cfg.get("enable_debug", False),
    }
