from __future__ import annotations

import logging

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.webhooks import router as webhooks_router
from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


configure_logging()
settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(health_router)
app.include_router(webhooks_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"app": settings.app_name, "status": "running"}
