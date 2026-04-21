from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.webhook import WebhookProcessResult
from app.services.webhook_ingestion import WebhookIngestionService

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/evolution", response_model=WebhookProcessResult, status_code=status.HTTP_202_ACCEPTED)
def evolution_webhook(payload: dict[str, Any], db: Session = Depends(get_db)) -> WebhookProcessResult:
    service = WebhookIngestionService(db)
    return service.process_evolution_payload(payload)
