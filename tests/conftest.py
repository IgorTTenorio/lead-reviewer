from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import reset_settings_cache
from app.db import session as session_module
from app.db.base import Base
from app.models import Client, Conversation, ConversationReview, Message, Product


@pytest.fixture
def db_session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    database_path = tmp_path / "test.db"
    database_url = f"sqlite:///{database_path}"

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", database_url)
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("CELERY_BROKER_URL", "memory://")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "cache+memory://")
    monkeypatch.setenv("CELERY_TASK_ALWAYS_EAGER", "true")
    monkeypatch.setenv("CELERY_TASK_EAGER_PROPAGATES", "true")

    reset_settings_cache()
    session_module.get_engine.cache_clear()
    session_module.get_session_factory.cache_clear()

    engine = session_module.get_engine()
    Base.metadata.create_all(bind=engine)
    SessionLocal = session_module.get_session_factory()

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        session_module.get_engine.cache_clear()
        session_module.get_session_factory.cache_clear()
        reset_settings_cache()
