"""Recreates clean fail-closed RLS policies on all tenant tables."""
from sqlalchemy import create_engine, text

admin_url = 'postgresql://postgres:postgres@127.0.0.1:5434/closely_db'
engine = create_engine(admin_url, isolation_level='AUTOCOMMIT')

tables = [
    'organizations', 'users', 'categories', 'products', 'conversations',
    'messages', 'customer_memories', 'orders', 'order_items',
    'recommendation_feedback', 'approval_requests', 'notifications',
    'approval_audit_logs', 'outbound_messages'
]

with engine.connect() as conn:
    print('Dropping all existing policies on tenant tables...')
    for t in tables:
        pols = conn.execute(text(f"SELECT policyname FROM pg_policies WHERE tablename = '{t}'")).fetchall()
        for p in pols:
            conn.execute(text(f'DROP POLICY IF EXISTS "{p[0]}" ON {t}'))
            print(f'  Dropped {t}.{p[0]}')

    print('\nRecreating clean fail-closed policies...')
    
    # 1. organizations
    conn.execute(text("""
        ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
        ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
        CREATE POLICY organizations_tenant_policy ON organizations
        USING (id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        WITH CHECK (id = nullif(current_setting('app.current_tenant', true), '')::uuid);
    """))

    # 2. direct org tables (excluding approval_audit_logs)
    direct_org = ['users', 'categories', 'products', 'conversations', 'customer_memories', 'orders', 'approval_requests', 'notifications', 'outbound_messages']
    for t in direct_org:
        conn.execute(text(f"""
            ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
            ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
            CREATE POLICY {t}_tenant_policy ON {t}
            USING (organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
            WITH CHECK (organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid);
        """))

    # 2.5 approval_audit_logs (only SELECT and INSERT policies)
    conn.execute(text("""
        ALTER TABLE approval_audit_logs ENABLE ROW LEVEL SECURITY;
        ALTER TABLE approval_audit_logs FORCE ROW LEVEL SECURITY;
        CREATE POLICY approval_audit_logs_tenant_select_policy ON approval_audit_logs
        FOR SELECT USING (organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid);
        CREATE POLICY approval_audit_logs_tenant_insert_policy ON approval_audit_logs
        FOR INSERT WITH CHECK (organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid);
    """))

    # 3. messages
    conn.execute(text("""
        ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
        ALTER TABLE messages FORCE ROW LEVEL SECURITY;
        CREATE POLICY messages_tenant_policy ON messages
        USING (conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid))
        WITH CHECK (conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid));
    """))

    # 4. order_items
    conn.execute(text("""
        ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
        ALTER TABLE order_items FORCE ROW LEVEL SECURITY;
        CREATE POLICY order_items_tenant_policy ON order_items
        USING (order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid))
        WITH CHECK (order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid));
    """))

    # 5. recommendation_feedback
    conn.execute(text("""
        ALTER TABLE recommendation_feedback ENABLE ROW LEVEL SECURITY;
        ALTER TABLE recommendation_feedback FORCE ROW LEVEL SECURITY;
        CREATE POLICY recommendation_feedback_tenant_policy ON recommendation_feedback
        USING (message_id IN (SELECT m.id FROM messages m JOIN conversations c ON m.conversation_id = c.id WHERE c.organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid))
        WITH CHECK (message_id IN (SELECT m.id FROM messages m JOIN conversations c ON m.conversation_id = c.id WHERE c.organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid));
    """))

    # Grant permissions to closely_app
    conn.execute(text("""
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO closely_app;
        REVOKE UPDATE, DELETE ON approval_audit_logs FROM closely_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO closely_app;
    """))

print('Done recreating policies!')
