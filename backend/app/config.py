"""Application configuration via Pydantic BaseSettings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    DATABASE_URL: str = "postgresql://aiops:aiops_secret@localhost:5433/aiops_db"
    REDIS_URL: str = "redis://localhost:6380/0"
    CELERY_BROKER_URL: str = "redis://localhost:6380/1"
    SECRET_KEY: str = "change-me-in-production"
    DEBUG: bool = True

    # Detection engine defaults
    EWMA_ALPHA: float = 0.3
    Z_SCORE_THRESHOLD: float = 2.0

    # Suppression engine defaults
    SUPPRESSION_SIMILARITY_THRESHOLD: float = 0.85

    # Grounded Post-Mortem & LLM settings (optional; falls back to deterministic synthesizer)
    LLM_API_KEY: str | None = None
    LLM_PROVIDER: str = "openai"  # 'openai', 'groq', or 'gemini'
    LLM_MODEL: str = "gpt-4o-mini"
    REVENUE_PER_WEIGHT_MINUTE: float = 150.0

    # API & Security settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AIOps Root Cause Correlator"
    VERSION: str = "1.0.0"
    CORS_ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "https://aiops-root-cause-correlator.vercel.app",
    ]
    API_AUTH_TOKEN: str | None = None
    REQUIRE_AUTH_FOR_MUTATIONS: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
