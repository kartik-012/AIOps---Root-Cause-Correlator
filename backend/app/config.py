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

    # API settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AIOps Root Cause Correlator"
    VERSION: str = "1.0.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
