"""audit_logs_immutability_rls

Revision ID: a2f4c9b0e8d1
Revises: d4d1f5b38d89
Create Date: 2026-08-16 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a2f4c9b0e8d1'
down_revision: Union[str, None] = 'd4d1f5b38d89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop broad/unwanted policies on approval_audit_logs
    op.execute("DROP POLICY IF EXISTS approval_audit_logs_tenant_policy ON approval_audit_logs;")
    op.execute("DROP POLICY IF EXISTS approval_audit_logs_tenant_update_policy ON approval_audit_logs;")
    op.execute("DROP POLICY IF EXISTS approval_audit_logs_tenant_delete_policy ON approval_audit_logs;")

    # 2. Ensure RLS and FORCE RLS are enabled
    op.execute("ALTER TABLE approval_audit_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE approval_audit_logs FORCE ROW LEVEL SECURITY;")

    # 3. Create explicit SELECT and INSERT policies
    op.execute("""
    CREATE POLICY approval_audit_logs_tenant_select_policy ON approval_audit_logs
    FOR SELECT USING (
        organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
    );
    """)
    op.execute("""
    CREATE POLICY approval_audit_logs_tenant_insert_policy ON approval_audit_logs
    FOR INSERT WITH CHECK (
        organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
    );
    """)


def downgrade() -> None:
    """Security hardening migration downgrade is unsupported.
    
    Disabling Row-Level Security or dropping immutability policies would leave
    the approval_audit_logs table exposed and susceptible to tampering.
    For staging and production environments, any rollback or schema correction
    must be applied as a forward migration or by restoring from a verified
    database snapshot/backup.
    """
    raise RuntimeError(
        "Downgrade of security migration 'a2f4c9b0e8d1' (Audit Logs Immutability & RLS) "
        "is strictly unsupported. To revert or alter security policies, apply a forward "
        "migration or restore from an authenticated database backup."
    )

