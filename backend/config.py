"""WhyGraph configuration — loads environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration from environment variables."""

    # FalkorDB
    FALKORDB_HOST: str = os.getenv("FALKORDB_HOST", "localhost")
    FALKORDB_PORT: int = int(os.getenv("FALKORDB_PORT", "6379"))
    FALKORDB_PASSWORD: str = os.getenv("FALKORDB_PASSWORD", "")
    FALKORDB_GRAPH_NAME: str = os.getenv("FALKORDB_GRAPH_NAME", "whygraph")

    # LLM Provider
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "google")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # App
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))

    # Data paths
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    ADR_DIR: str = os.path.join(DATA_DIR, "adrs")
    POSTMORTEM_DIR: str = os.path.join(DATA_DIR, "postmortems")
    ORG_FILE: str = os.path.join(DATA_DIR, "org.json")
    SERVICES_FILE: str = os.path.join(DATA_DIR, "services.json")


config = Config()
