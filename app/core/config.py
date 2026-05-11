from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    app_name: str = Field(default_factory=lambda: os.getenv("APP_NAME", "lead-reviewer"))
    app_env: str = Field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@localhost:5432/lead_reviewer",
        )
    )
    alembic_database_url: str | None = Field(
        default_factory=lambda: os.getenv("ALEMBIC_DATABASE_URL")
    )
    celery_broker_url: str = Field(
        default_factory=lambda: os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    )
    celery_result_backend: str = Field(
        default_factory=lambda: os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
    )
    celery_task_always_eager: bool = Field(
        default_factory=lambda: os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    celery_task_eager_propagates: bool = Field(
        default_factory=lambda: os.getenv("CELERY_TASK_EAGER_PROPAGATES", "true").strip().lower()
        in {"1", "true", "yes", "on"}
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        return self.database_url

    @property
    def alembic_url(self) -> str:
        return self.alembic_database_url or self.database_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
