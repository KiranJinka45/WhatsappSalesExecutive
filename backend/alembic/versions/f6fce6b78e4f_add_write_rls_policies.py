"""add_write_rls_policies

Revision ID: f6fce6b78e4f
Revises: b2fbe48c9249
Create Date: 2026-07-11 22:14:40.028314

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6fce6b78e4f'
down_revision: Union[str, None] = 'b2fbe48c9249'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Direct organization_id mapping tables
    direct_tables = [
        ('products', 'organization_id'),
        ('conversations', 'organization_id'),
        ('orders', 'organization_id'),
        ('categories', 'organization_id'),
        ('users', 'organization_id'),
        ('approval_requests', 'organization_id'),
        ('notifications', 'organization_id'),
        ('customer_memories', 'organization_id'),
        ('organizations', 'id')
    ]
    
    for table_name, org_col in direct_tables:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;")
        
        # INSERT
        op.execute(f"""
        CREATE POLICY {table_name}_tenant_insert_policy ON {table_name}
        FOR INSERT WITH CHECK (
            {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
        );
        """)
        # UPDATE
        op.execute(f"""
        CREATE POLICY {table_name}_tenant_update_policy ON {table_name}
        FOR UPDATE USING (
            {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
        ) WITH CHECK (
            {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
        );
        """)
        # SELECT
        op.execute(f"""
        CREATE POLICY {table_name}_tenant_select_policy ON {table_name}
        FOR SELECT USING (
            {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
        );
        """)
        # DELETE
        op.execute(f"""
        CREATE POLICY {table_name}_tenant_delete_policy ON {table_name}
        FOR DELETE USING (
            {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
        );
        """)

    # messages table (linked via conversation_id)
    op.execute("ALTER TABLE messages ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE messages FORCE ROW LEVEL SECURITY;")
    op.execute("""
    CREATE POLICY messages_tenant_insert_policy ON messages FOR INSERT WITH CHECK (
        conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
    );
    """)
    op.execute("""
    CREATE POLICY messages_tenant_update_policy ON messages FOR UPDATE USING (
        conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
    ) WITH CHECK (
        conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
    );
    """)
    op.execute("""
    CREATE POLICY messages_tenant_select_policy ON messages FOR SELECT USING (
        conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
    );
    """)
    op.execute("""
    CREATE POLICY messages_tenant_delete_policy ON messages FOR DELETE USING (
        conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
    );
    """)

    # order_items table (linked via order_id)
    op.execute("ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE order_items FORCE ROW LEVEL SECURITY;")
    op.execute("""
    CREATE POLICY order_items_tenant_insert_policy ON order_items FOR INSERT WITH CHECK (
        order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
    );
    """)
    op.execute("""
    CREATE POLICY order_items_tenant_update_policy ON order_items FOR UPDATE USING (
        order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
    ) WITH CHECK (
        order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
    );
    """)
    op.execute("""
    CREATE POLICY order_items_tenant_select_policy ON order_items FOR SELECT USING (
        order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
    );
    """)
    op.execute("""
    CREATE POLICY order_items_tenant_delete_policy ON order_items FOR DELETE USING (
        order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
    );
    """)

    # recommendation_feedback table (linked via message_id)
    op.execute("ALTER TABLE recommendation_feedback ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE recommendation_feedback FORCE ROW LEVEL SECURITY;")
    op.execute("""
    CREATE POLICY recommendation_feedback_tenant_insert_policy ON recommendation_feedback FOR INSERT WITH CHECK (
        message_id IN (
            SELECT m.id FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
        )
    );
    """)
    op.execute("""
    CREATE POLICY recommendation_feedback_tenant_update_policy ON recommendation_feedback FOR UPDATE USING (
        message_id IN (
            SELECT m.id FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
        )
    ) WITH CHECK (
        message_id IN (
            SELECT m.id FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
        )
    );
    """)
    op.execute("""
    CREATE POLICY recommendation_feedback_tenant_select_policy ON recommendation_feedback FOR SELECT USING (
        message_id IN (
            SELECT m.id FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
        )
    );
    """)
    op.execute("""
    CREATE POLICY recommendation_feedback_tenant_delete_policy ON recommendation_feedback FOR DELETE USING (
        message_id IN (
            SELECT m.id FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
        )
    );
    """)

def downgrade() -> None:
    tables = [
        'products', 'conversations', 'messages', 'orders', 'order_items',
        'categories', 'users', 'approval_requests', 'notifications',
        'recommendation_feedback', 'customer_memories', 'organizations'
    ]
    for table_name in tables:
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_insert_policy ON {table_name};")
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_update_policy ON {table_name};")
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_select_policy ON {table_name};")
        op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_delete_policy ON {table_name};")
        op.execute(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;")
