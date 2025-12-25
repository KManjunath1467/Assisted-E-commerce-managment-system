from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "E-Commerce Operations Assistant"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database
    DATABASE_URL: str

    # Vector store
    QDRANT_URL: str = "http://localhost:6333"

    # LLM API settings (OpenAI-compatible)
    DIAL_API_KEY: str
    DIAL_ENDPOINT: str
    DIAL_API_VERSION: str
    DIAL_DEPLOYMENT: str

    # MCP tool routing — "none" | "sales" | "sales,inventory" | "all"
    USE_MCP_TOOLS: str = "all"

    # Unified MCP server URL
    MCP_URL: str = "http://localhost:8001"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
