"""add_whatsapp_onboarding_and_audit_logs

Revision ID: 1d644d678b5e
Revises: a2f4c9b0e8d1
Create Date: 2026-08-20 10:08:01.239342

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d644d678b5e'
down_revision: Union[str, None] = 'a2f4c9b0e8d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns to organizations
    op.add_column('organizations', sa.Column('whatsapp_onboarding_state', sa.String(length=50), nullable=True, server_default='NOT_CONNECTED'))
    op.add_column('organizations', sa.Column('whatsapp_onboarding_metadata', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'))

    # 2. Create whatsapp_onboarding_audit_logs table
    op.create_table(
        'whatsapp_onboarding_audit_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('previous_state', sa.String(length=50), nullable=True),
        sa.Column('new_state', sa.String(length=50), nullable=False),
        sa.Column('error_category', sa.String(length=100), nullable=True),
        sa.Column('metadata', sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('correlation_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Enable and FORCE RLS
    op.execute("ALTER TABLE whatsapp_onboarding_audit_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE whatsapp_onboarding_audit_logs FORCE ROW LEVEL SECURITY;")

    # 4. Create tenant-scoped SELECT and INSERT policies
    op.execute("""
    CREATE POLICY onboarding_audit_logs_tenant_select_policy ON whatsapp_onboarding_audit_logs
    FOR SELECT USING (
        organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
    );
    """)
    op.execute("""
    CREATE POLICY onboarding_audit_logs_tenant_insert_policy ON whatsapp_onboarding_audit_logs
    FOR INSERT WITH CHECK (
        organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
    );
    """)

    # 5. DB privileges configuration: Allow SELECT and INSERT to closely_app, revoke UPDATE and DELETE
    op.execute("GRANT SELECT, INSERT ON whatsapp_onboarding_audit_logs TO closely_app;")
    op.execute("REVOKE UPDATE, DELETE ON whatsapp_onboarding_audit_logs FROM closely_app;")


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade of security migration '1d644d678b5e' (WhatsApp Onboarding Audit Logs & RLS) "
        "is strictly unsupported. To revert or alter security policies, apply a forward "
        "migration or restore from an authenticated database backup."
    )
