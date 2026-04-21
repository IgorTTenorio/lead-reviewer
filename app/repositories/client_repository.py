from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Client


class ClientRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_phone(self, phone: str) -> Client | None:
        stmt = select(Client).where(Client.phone == phone)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_or_create(self, phone: str, display_name: str | None = None) -> Client:
        client = self.get_by_phone(phone)
        if client:
            if display_name and client.display_name != display_name:
                client.display_name = display_name
            return client

        client = Client(phone=phone, display_name=display_name)
        self.db.add(client)
        self.db.flush()
        return client
