"""create initial schema

Revision ID: 20260421_000001
Revises:
Create Date: 2026-04-21 22:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260421_000001"
down_revision = None
branch_labels = None
depends_on = None

message_direction = postgresql.ENUM("inbound", "outbound", name="message_direction")
message_direction_column = postgresql.ENUM(
    "inbound",
    "outbound",
    name="message_direction",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    message_direction.create(bind, checkfirst=True)

    op.create_table(
        "clients",
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clients_phone"), "clients", ["phone"], unique=True)

    op.create_table(
        "products",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("external_product_id", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_product_id"),
    )

    op.create_table(
        "conversations",
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversations_client_id"), "conversations", ["client_id"], unique=False)
    op.create_index(op.f("ix_conversations_product_id"), "conversations", ["product_id"], unique=False)
    op.create_index(
        "ix_conversations_client_last_message_at",
        "conversations",
        ["client_id", "last_message_at"],
        unique=False,
    )

    op.create_table(
        "conversation_reviews",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("wants_to_continue", sa.Boolean(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("stage", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("model_provider", sa.Text(), nullable=True),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "conversation_id",
            "window_started_at",
            "window_ended_at",
            name="uq_conversation_review_window",
        ),
    )
    op.create_index(
        op.f("ix_conversation_reviews_conversation_id"),
        "conversation_reviews",
        ["conversation_id"],
        unique=False,
    )

    op.create_table(
        "messages",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("external_message_id", sa.String(length=255), nullable=False),
        sa.Column("direction", message_direction_column, nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("message_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_message_id"),
    )
    op.create_index(op.f("ix_messages_client_id"), "messages", ["client_id"], unique=False)
    op.create_index(
        "ix_messages_client_conversation_timestamp",
        "messages",
        ["client_id", "conversation_id", "message_timestamp"],
        unique=False,
    )
    op.create_index(op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_messages_message_timestamp"), "messages", ["message_timestamp"], unique=False)
    op.create_index(op.f("ix_messages_product_id"), "messages", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_messages_product_id"), table_name="messages")
    op.drop_index(op.f("ix_messages_message_timestamp"), table_name="messages")
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_index("ix_messages_client_conversation_timestamp", table_name="messages")
    op.drop_index(op.f("ix_messages_client_id"), table_name="messages")
    op.drop_table("messages")

    op.drop_index(op.f("ix_conversation_reviews_conversation_id"), table_name="conversation_reviews")
    op.drop_table("conversation_reviews")

    op.drop_index("ix_conversations_client_last_message_at", table_name="conversations")
    op.drop_index(op.f("ix_conversations_product_id"), table_name="conversations")
    op.drop_index(op.f("ix_conversations_client_id"), table_name="conversations")
    op.drop_table("conversations")

    op.drop_table("products")

    op.drop_index(op.f("ix_clients_phone"), table_name="clients")
    op.drop_table("clients")

    bind = op.get_bind()
    message_direction.drop(bind, checkfirst=True)
