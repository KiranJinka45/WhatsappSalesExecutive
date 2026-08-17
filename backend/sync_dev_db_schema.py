"""Syncs closely_db schema with current models/migrations."""
from sqlalchemy import create_engine, text
from app import models

admin_url = 'postgresql://postgres:postgres@127.0.0.1:5434/closely_db'
engine = create_engine(admin_url, isolation_level='AUTOCOMMIT')

with engine.connect() as conn:
    # Check columns on approval_requests
    cols = [r[0] for r in conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'approval_requests'")).fetchall()]
    print("Existing columns in approval_requests:", cols)
    
    needed_cols = [
        ("approved_by_user_id", "UUID REFERENCES users(id) ON DELETE SET NULL"),
        ("edited_by_user_id", "UUID REFERENCES users(id) ON DELETE SET NULL"),
        ("edited_response", "TEXT"),
        ("message_hash", "VARCHAR(64)"),
        ("version", "INTEGER DEFAULT 1"),
        ("price_snapshot", "JSONB DEFAULT '{}'::jsonb"),
        ("stock_snapshot", "JSONB DEFAULT '{}'::jsonb"),
        ("expires_at", "TIMESTAMP WITH TIME ZONE"),
        ("sent_at", "TIMESTAMP WITH TIME ZONE"),
        ("error_message", "TEXT"),
    ]
    for col_name, col_type in needed_cols:
        if col_name not in cols:
            conn.execute(text(f"ALTER TABLE approval_requests ADD COLUMN {col_name} {col_type}"))
            print(f"  Added {col_name} to approval_requests")

    # Grant permissions to closely_app on all tables
    conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO closely_app"))
    conn.execute(text("REVOKE UPDATE, DELETE ON approval_audit_logs FROM closely_app"))
    conn.execute(text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO closely_app"))
    print("Permissions granted to closely_app.")

print("Schema sync completed.")
