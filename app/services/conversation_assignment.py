from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Client, Conversation, Product
from app.schemas.webhook import NormalizedMessage
from app.repositories.client_repository import ClientRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.product_repository import ProductRepository


@dataclass(slots=True)
class ConversationAssignment:
    client: Client
    conversation: Conversation
    product: Product | None


class ConversationAssignmentService:
    def __init__(self, db: Session):
        self.db = db
        self.clients = ClientRepository(db)
        self.products = ProductRepository(db)
        self.conversations = ConversationRepository(db)

    def assign(self, normalized_message: NormalizedMessage) -> ConversationAssignment:
        client = self.clients.get_or_create(
            phone=normalized_message.phone,
            display_name=normalized_message.display_name,
        )
        product = self.products.get_or_create(
            normalized_message.product_external_id,
            fallback_name=normalized_message.product_external_id,
        )
        conversation = self.conversations.get_or_create(
            client_id=client.id,
            product_id=product.id if product else None,
            message_timestamp=normalized_message.message_timestamp,
        )
        return ConversationAssignment(
            client=client,
            conversation=conversation,
            product=product,
        )
