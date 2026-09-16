"""add instagram support

Revision ID: e8a1f2b3c4d5
Revises: 1d644d678b5e
Create Date: 2026-09-16

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e8a1f2b3c4d5'
down_revision: Union[str, None] = '1d644d678b5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. channel column on conversations & expand customer_phone length
    op.add_column(
        "conversations",
        sa.Column(
            "channel",
            sa.String(length=20),
            nullable=False,
            server_default="whatsapp",
        ),
    )
    op.create_index(
        "ix_conversations_channel", "conversations", ["channel"], unique=False
    )
    op.alter_column(
        "conversations",
        "customer_phone",
        existing_type=sa.String(length=20),
        type_=sa.String(length=64),
        existing_nullable=False,
    )

    # 2. channel column on messages
    op.add_column(
        "messages",
        sa.Column(
            "channel",
            sa.String(length=20),
            nullable=False,
            server_default="whatsapp",
        ),
    )

    # 3. instagram fields on organizations
    op.add_column(
        "organizations",
        sa.Column("instagram_business_account_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("instagram_page_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("instagram_access_token", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "is_instagram_connected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 4. unique constraint for instagram_business_account_id lookup
    op.create_index(
        "ix_organizations_instagram_business_account_id",
        "organizations",
        ["instagram_business_account_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_organizations_instagram_business_account_id", table_name="organizations")
    op.drop_column("organizations", "is_instagram_connected")
    op.drop_column("organizations", "instagram_access_token")
    op.drop_column("organizations", "instagram_page_id")
    op.drop_column("organizations", "instagram_business_account_id")
    op.drop_column("messages", "channel")
    op.drop_index("ix_conversations_channel", table_name="conversations")
    op.alter_column(
        "conversations",
        "customer_phone",
        existing_type=sa.String(length=64),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.drop_column("conversations", "channel")
