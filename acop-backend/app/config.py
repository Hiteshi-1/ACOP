"""
Centralized application configuration.
Reads from environment variables / .env file via pydantic-settings.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ---- App ----
    APP_NAME: str = "ACOP - Autonomous Cloud Operations Platform"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = "dev-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # ---- Database ----
    DATABASE_URL: str = "sqlite:///./acop.db"

    # ---- LLM ----
    LLM_PROVIDER: str = "gemini"  # "gemini" (free tier) or "anthropic" (paid)

    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-6"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # ---- Kubernetes ----
    K8S_MODE: str = "mock"  # incluster | kubeconfig | mock
    KUBECONFIG_PATH: str = "~/.kube/config"
    K8S_NAMESPACE: str = "default"

    # ---- RAG ----
    CHROMA_PERSIST_DIR: str = "./chroma_store"
    CHROMA_COLLECTION_NAME: str = "acop_runbooks"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # informational; actual model is fixed by ChromaDB's DefaultEmbeddingFunction

    # ---- ML ----
    MODEL_ARTIFACTS_DIR: str = "./model_artifacts"
    LSTM_SEQUENCE_LENGTH: int = 30
    ANOMALY_THRESHOLD: float = 0.85

    # ---- Agents ----
    AGENT_LOOP_INTERVAL_SECONDS: int = 60
    AUTO_REMEDIATION_ENABLED: bool = True
    AUTO_REMEDIATION_CONFIDENCE_THRESHOLD: float = 0.8

    # ---- CORS ----
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
