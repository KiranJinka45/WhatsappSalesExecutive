"""add_outbound_messages_table_and_rls

Revision ID: e7f8a9b0c1d2
Revises: f6fce6b78e4f
Create Date: 2026-08-14 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'f6fce6b78e4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create outbound_messages table
    op.create_table(
        'outbound_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('approval_request_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('approval_requests.id', ondelete='SET NULL'), nullable=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('message_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('provider_idempotency_key', sa.String(length=100), nullable=False, unique=True, index=True),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('recipient_phone', sa.String(length=30), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDING', index=True),
        sa.Column('provider_message_id', sa.String(length=100), nullable=True, index=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('approval_request_id', 'message_version', name='uq_outbound_approval_version'),
        sa.UniqueConstraint('provider_idempotency_key', name='uq_outbound_provider_idempotency')
    )
    op.create_index('idx_outbound_org_status', 'outbound_messages', ['organization_id', 'status'])

    # 2. Enable & Force Row-Level Security on outbound_messages
    op.execute("ALTER TABLE outbound_messages ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE outbound_messages FORCE ROW LEVEL SECURITY;")

    # 3. Apply fail-closed tenant RLS policies for outbound_messages
    op.execute("""
    CREATE POLICY outbound_messages_tenant_insert_policy ON outbound_messages
    FOR INSERT WITH CHECK (
        organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
    );
    """)
    op.execute("""
    CREATE POLICY outbound_messages_tenant_update_policy ON outbound_messages
    FOR UPDATE USING (
        organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
    ) WITH CHECK (
        organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
    );
    """)
    op.execute("""
    CREATE POLICY outbound_messages_tenant_select_policy ON outbound_messages
    FOR SELECT USING (
        organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
    );
    """)
    op.execute("""
    CREATE POLICY outbound_messages_tenant_delete_policy ON outbound_messages
    FOR DELETE USING (
        organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
    );
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS outbound_messages_tenant_delete_policy ON outbound_messages;")
    op.execute("DROP POLICY IF EXISTS outbound_messages_tenant_select_policy ON outbound_messages;")
    op.execute("DROP POLICY IF EXISTS outbound_messages_tenant_update_policy ON outbound_messages;")
    op.execute("DROP POLICY IF EXISTS outbound_messages_tenant_insert_policy ON outbound_messages;")
    op.drop_index('idx_outbound_org_status', table_name='outbound_messages')
    op.drop_table('outbound_messages')
