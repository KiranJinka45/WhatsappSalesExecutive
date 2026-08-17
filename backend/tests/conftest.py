"""
Shared test configuration and fixtures for Closely AI backend tests.
Centralizes database setup, dependency overrides, and common helpers.
"""
import os
import sys

# Always force DATABASE_URL to closely_db_test for test suite runs
db_user = os.environ.get("POSTGRES_USER", "postgres")
db_password = os.environ.get("POSTGRES_PASSWORD", "postgres")
db_host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
db_port = os.environ.get("POSTGRES_PORT", "5434")
db_name = os.environ.get("POSTGRES_DB", "closely_db_test")
os.environ["DATABASE_URL"] = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["TESTING"] = "true"

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.database import Base, get_db
from app import models

SQLALCHEMY_DATABASE_URL = os.environ["DATABASE_URL"]
from sqlalchemy.pool import NullPool
engine = create_engine(SQLALCHEMY_DATABASE_URL, poolclass=NullPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Use sys.modules to patch database variables without shadowing the local 'app' name
import sys
sys.modules['app.database'].SessionLocal = TestingSessionLocal
sys.modules['app.database'].engine = engine

sys.modules['app.main'].engine = engine
sys.modules['app.main'].SessionLocal = TestingSessionLocal

sys.modules['app.catalog_service'].SessionLocal = TestingSessionLocal

# Also ensure router modules are patched
from app.routers import catalog, health, webhooks
sys.modules['app.routers.catalog'].SessionLocal = TestingSessionLocal
sys.modules['app.routers.health'].engine = engine
sys.modules['app.routers.webhooks'].SessionLocal = TestingSessionLocal

# Define app at the end of setup to ensure it exports the actual FastAPI instance
app = fastapi_app

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Apply dependency override globally
fastapi_app.dependency_overrides[get_db] = override_get_db

from app.routers.auth import login_limiter
from app.routers.webhooks import webhook_limiter
fastapi_app.dependency_overrides[login_limiter] = lambda: None
fastapi_app.dependency_overrides[webhook_limiter] = lambda: None

import unittest.mock
import redis

class MockRedis:
    def __init__(self):
        self._data = {}
    def ping(self):
        return True
    def get(self, key):
        return self._data.get(str(key))
    def set(self, key, value, ex=None, nx=False):
        skey = str(key)
        if nx and skey in self._data:
            return False
        self._data[skey] = str(value)
        return True
    def incr(self, key):
        skey = str(key)
        val = int(self._data.get(skey, 0)) + 1
        self._data[skey] = str(val)
        return val
    def expire(self, key, time):
        return True
    def delete(self, *keys):
        deleted_count = 0
        for k in keys:
            skey = str(k)
            if skey in self._data:
                del self._data[skey]
                deleted_count += 1
        return deleted_count
    def llen(self, key):
        skey = str(key)
        val = self._data.get(skey)
        if isinstance(val, list):
            return len(val)
        return 0
    def lindex(self, key, index):
        skey = str(key)
        val = self._data.get(skey)
        if isinstance(val, list) and 0 <= index < len(val):
            return val[index]
        return None
    def lpush(self, key, *values):
        skey = str(key)
        if skey not in self._data or not isinstance(self._data[skey], list):
            self._data[skey] = []
        for val in values:
            self._data[skey].insert(0, str(val))
        return len(self._data[skey])
    def rpoplpush(self, src, dst):
        ssrc = str(src)
        sdst = str(dst)
        src_list = self._data.get(ssrc)
        if not isinstance(src_list, list) or not src_list:
            return None
        val = src_list.pop()
        if sdst not in self._data or not isinstance(self._data[sdst], list):
            self._data[sdst] = []
        self._data[sdst].insert(0, val)
        return val
    def brpoplpush(self, src, dst, timeout=0):
        return self.rpoplpush(src, dst)
    def lrem(self, key, count, value):
        skey = str(key)
        val_list = self._data.get(skey)
        if not isinstance(val_list, list):
            return 0
        sval = str(value)
        removed_count = 0
        if count >= 0:
            idx = 0
            while idx < len(val_list) and (count == 0 or removed_count < count):
                if val_list[idx] == sval:
                    val_list.pop(idx)
                    removed_count += 1
                else:
                    idx += 1
        else:
            count = abs(count)
            idx = len(val_list) - 1
            while idx >= 0 and (count == 0 or removed_count < count):
                if val_list[idx] == sval:
                    val_list.pop(idx)
                    removed_count += 1
                idx -= 1
        return removed_count

_mock_redis_instance = MockRedis()
redis.from_url = lambda *args, **kwargs: _mock_redis_instance
redis.Redis.from_url = lambda *args, **kwargs: _mock_redis_instance

# Mock AI Service for all tests to prevent slow/hanging network calls
from app import ai_service, security
ai_service.get_embedding = unittest.mock.MagicMock(return_value=[0.0] * 768)
ai_service.get_image_embedding = unittest.mock.MagicMock(return_value=[0.0] * 3072)
ai_service.classify_intent = unittest.mock.MagicMock(return_value="product_discovery")
ai_service.generate_reply = unittest.mock.MagicMock(return_value="Mocked AI reply")

from app.routers import catalog, webhooks
catalog.get_embedding = unittest.mock.MagicMock(return_value=[0.0] * 768)
catalog.get_image_embedding = unittest.mock.MagicMock(return_value=[0.0] * 3072)

# Mock bcrypt to avoid CPU bottlenecks in tests
from app.routers import auth
security.get_password_hash = lambda password: f"mocked_hash_{password}"
security.verify_password = lambda plain, hashed: hashed == f"mocked_hash_{plain}"
auth.get_password_hash = lambda password: f"mocked_hash_{password}"
auth.verify_password = lambda plain, hashed: hashed == f"mocked_hash_{plain}"


import pytest

@pytest.fixture(scope="session", autouse=True)
def initialize_db():
    setup_test_db()
    yield

def setup_test_db():
    """Create pgvector extension, all tables, and RLS policies."""
    # Force-terminate all other sessions on closely_db_test to avoid locks during drop_all
    try:
        # Use a short connect timeout so it never hangs
        kill_engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"connect_timeout": 3})
        with kill_engine.connect() as kill_conn:
            kill_conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'closely_db_test' AND pid != pg_backend_pid();"))
            kill_conn.commit()
        kill_engine.dispose()
    except Exception:
        pass

    print(f"Base.metadata.tables: {list(Base.metadata.tables.keys())}")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    with engine.connect() as conn:
        conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO closely_app;"))
        conn.execute(text("REVOKE UPDATE, DELETE ON approval_audit_logs FROM closely_app;"))
        conn.execute(text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO closely_app;"))
        conn.commit()
    
    # Apply RLS policies for testing
    direct_tables = [
        ('products', 'organization_id'),
        ('conversations', 'organization_id'),
        ('orders', 'organization_id'),
        ('categories', 'organization_id'),
        ('users', 'organization_id'),
        ('approval_requests', 'organization_id'),
        ('outbound_messages', 'organization_id'),
        ('notifications', 'organization_id'),
        ('customer_memories', 'organization_id'),
        ('organizations', 'id')
    ]
    with engine.connect() as conn:
        for table_name, org_col in direct_tables:
            conn.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;"))
            conn.execute(text(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;"))
            
            conn.execute(text(f"""
            CREATE POLICY {table_name}_tenant_insert_policy ON {table_name}
            FOR INSERT WITH CHECK (
                {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
            );
            """))
            if table_name != 'approval_audit_logs':
                conn.execute(text(f"""
                CREATE POLICY {table_name}_tenant_update_policy ON {table_name}
                FOR UPDATE USING (
                    {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
                ) WITH CHECK (
                    {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
                );
                """))
            conn.execute(text(f"""
            CREATE POLICY {table_name}_tenant_select_policy ON {table_name}
            FOR SELECT USING (
                {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
            );
            """))
            if table_name != 'approval_audit_logs':
                conn.execute(text(f"""
                CREATE POLICY {table_name}_tenant_delete_policy ON {table_name}
                FOR DELETE USING (
                    {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
                );
                """))

        # messages table
        conn.execute(text("ALTER TABLE messages ENABLE ROW LEVEL SECURITY;"))
        conn.execute(text("ALTER TABLE messages FORCE ROW LEVEL SECURITY;"))
        conn.execute(text("""
        CREATE POLICY messages_tenant_insert_policy ON messages FOR INSERT WITH CHECK (
            conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        );
        """))
        conn.execute(text("""
        CREATE POLICY messages_tenant_update_policy ON messages FOR UPDATE USING (
            conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        ) WITH CHECK (
            conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        );
        """))
        conn.execute(text("""
        CREATE POLICY messages_tenant_select_policy ON messages FOR SELECT USING (
            conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        );
        """))
        conn.execute(text("""
        CREATE POLICY messages_tenant_delete_policy ON messages FOR DELETE USING (
            conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        );
        """))

        # order_items table
        conn.execute(text("ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;"))
        conn.execute(text("ALTER TABLE order_items FORCE ROW LEVEL SECURITY;"))
        conn.execute(text("""
        CREATE POLICY order_items_tenant_insert_policy ON order_items FOR INSERT WITH CHECK (
            order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        );
        """))
        conn.execute(text("""
        CREATE POLICY order_items_tenant_update_policy ON order_items FOR UPDATE USING (
            order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        ) WITH CHECK (
            order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        );
        """))
        conn.execute(text("""
        CREATE POLICY order_items_tenant_select_policy ON order_items FOR SELECT USING (
            current_setting('app.current_tenant', true) = '' OR
            order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        );
        """))
        conn.execute(text("""
        CREATE POLICY order_items_tenant_delete_policy ON order_items FOR DELETE USING (
            current_setting('app.current_tenant', true) = '' OR
            order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        );
        """))

        # recommendation_feedback table
        conn.execute(text("ALTER TABLE recommendation_feedback ENABLE ROW LEVEL SECURITY;"))
        conn.execute(text("ALTER TABLE recommendation_feedback FORCE ROW LEVEL SECURITY;"))
        conn.execute(text("""
        CREATE POLICY recommendation_feedback_tenant_insert_policy ON recommendation_feedback FOR INSERT WITH CHECK (
            current_setting('app.current_tenant', true) = '' OR
            message_id IN (
                SELECT m.id FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
            )
        );
        """))
        conn.execute(text("""
        CREATE POLICY recommendation_feedback_tenant_update_policy ON recommendation_feedback FOR UPDATE USING (
            current_setting('app.current_tenant', true) = '' OR
            message_id IN (
                SELECT m.id FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
            )
        ) WITH CHECK (
            current_setting('app.current_tenant', true) = '' OR
            message_id IN (
                SELECT m.id FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
            )
        );
        """))
        conn.execute(text("""
        CREATE POLICY recommendation_feedback_tenant_select_policy ON recommendation_feedback FOR SELECT USING (
            current_setting('app.current_tenant', true) = '' OR
            message_id IN (
                SELECT m.id FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
            )
        );
        """))
        conn.execute(text("""
        CREATE POLICY recommendation_feedback_tenant_delete_policy ON recommendation_feedback FOR DELETE USING (
            current_setting('app.current_tenant', true) = '' OR
            message_id IN (
                SELECT m.id FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid
            )
        );
        """))
        conn.commit()


def teardown_test_db():
    """No-op during test runs to prevent dropping tables between test classes."""
    pass


def clean_tables(db):
    """Delete all rows across all tables atomically using DELETE in reverse order."""
    from app.database import tenant_var
    tenant_var.set(None)
    db.is_admin = True
    db.organization_id = None
    try:
        table_names = [
            "outbound_messages",
            "approval_audit_logs",
            "recommendation_feedback",
            "order_items",
            "orders",
            "notifications",
            "approval_requests",
            "customer_memories",
            "messages",
            "conversations",
            "products",
            "categories",
            "users",
            "organizations"
        ]
        with engine.connect() as conn:
            for tbl in table_names:
                conn.execute(text(f"DELETE FROM {tbl};"))
            conn.commit()
    except Exception:
        db.rollback()
    finally:
        db.is_admin = False


def create_test_tenant(client, email, name, org_name, password="securepassword123"):
    """
    Register and log in a test tenant. Returns auth headers dict.
    """
    from app.routers.auth import login_limiter
    login_limiter.requests.clear()
    
    signup_data = {
        "email": email,
        "name": name,
        "password": password,
        "organization_name": org_name,
    }
    res = client.post("/api/auth/signup", json=signup_data)
    assert res.status_code == 201, f"Signup failed: {res.text}"

    login_data = {"username": email, "password": password}
    res = client.post("/api/auth/login", data=login_data)
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
