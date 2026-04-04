import os
from pathlib import Path
from dotenv import load_dotenv


def load_config() -> dict:
    """Load PerfMemory configuration from .env file.

    Searches for .env in the perfmemory-mcp directory (one level up from utils/).
    Falls back to environment variables if .env is not found.

    Returns:
        dict with keys: embedding, database, search, debug
    """
    mcp_root = Path(__file__).resolve().parent.parent
    env_path = mcp_root / ".env"

    # Local dev: loads .env file if present.
    # Docker/cloud: .env won't exist; os.getenv() reads from container environment
    # variables injected by the platform (Azure Container Apps, etc.).
    if env_path.exists():
        load_dotenv(env_path)

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
        },
        "search": {
            "top_k": int(os.getenv("VECTOR_TOP_K", "5")),
            "threshold": float(os.getenv("SIMILARITY_THRESHOLD", "0.75")),
        },
        "debug": os.getenv("DEBUG", "false").lower() == "true",
    }
