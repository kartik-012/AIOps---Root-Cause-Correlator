"""Pytest configuration and session fixtures for AIOps backend tests."""

import os
import pytest
from sqlalchemy import create_engine
from alembic import command
from alembic.config import Config


@pytest.fixture(scope="session", autouse=True)
def setup_database_schema():
    """Ensure database schema is up-to-date via Alembic when testing against a database."""
    from app.config import get_settings

    settings = get_settings()
    db_url = os.getenv("DATABASE_URL", settings.DATABASE_URL)
    try:
        engine = create_engine(db_url, connect_args={"connect_timeout": 2})
        with engine.connect():
            pass
    except Exception:
        # PostgreSQL is not running/available in this test environment
        return

    try:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ini_path = os.path.join(backend_dir, "alembic.ini")
        alembic_cfg = Config(ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        with engine.begin() as connection:
            alembic_cfg.attributes["connection"] = connection
            command.upgrade(alembic_cfg, "head")
    except Exception as e:
        print(f"[pytest conftest] Note: Alembic migration encountered: {e}")
    finally:
        engine.dispose()
