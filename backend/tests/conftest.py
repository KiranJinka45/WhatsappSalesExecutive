"""
Shared test configuration and fixtures for Closely AI backend tests.
Centralizes database setup, dependency overrides, and common helpers.
"""
import os
import sys

# Resolve DATABASE_URL: prefer env var, fall back to docker-compose port 5434
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5434/closely_db_test"

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["TESTING"] = "true"

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app import models

# Shared test engine and session factory
SQLALCHEMY_DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(SQLALCHEMY_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Apply dependency override globally
app.dependency_overrides[get_db] = override_get_db

# Mock AI Service for all tests to prevent slow/hanging network calls
import unittest.mock
from app import ai_service, security
ai_service.get_embedding = unittest.mock.MagicMock(return_value=[0.0] * 768)
ai_service.classify_intent = unittest.mock.MagicMock(return_value="product_discovery")
ai_service.generate_reply = unittest.mock.MagicMock(return_value="Mocked AI reply")

# Mock bcrypt to avoid CPU bottlenecks in tests
security.get_password_hash = lambda password: f"mocked_hash_{password}"
security.verify_password = lambda plain, hashed: hashed == f"mocked_hash_{plain}"


import pytest

@pytest.fixture(scope="session", autouse=True)
def initialize_db():
    setup_test_db()
    yield
    # We can keep tables or drop them at end of session

def setup_test_db():
    """Create pgvector extension, all tables, and RLS policies."""
    engine.dispose()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
        try:
            conn.execute(text("""
                SELECT pg_terminate_backend(pid) 
                FROM pg_stat_activity 
                WHERE datname = current_database() AND pid <> pg_backend_pid();
            """))
            conn.commit()
        except Exception:
            pass
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # Apply RLS policies for testing
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
    with engine.connect() as conn:
        for table_name, org_col in direct_tables:
            conn.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;"))
            conn.execute(text(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;"))
            
            conn.execute(text(f"""
            CREATE POLICY {table_name}_tenant_insert_policy ON {table_name}
            FOR INSERT WITH CHECK (
                current_setting('app.current_tenant', true) = '' OR
                {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
            );
            """))
            conn.execute(text(f"""
            CREATE POLICY {table_name}_tenant_update_policy ON {table_name}
            FOR UPDATE USING (
                current_setting('app.current_tenant', true) = '' OR
                {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
            ) WITH CHECK (
                current_setting('app.current_tenant', true) = '' OR
                {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
            );
            """))
            conn.execute(text(f"""
            CREATE POLICY {table_name}_tenant_select_policy ON {table_name}
            FOR SELECT USING (
                current_setting('app.current_tenant', true) = '' OR
                {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
            );
            """))
            conn.execute(text(f"""
            CREATE POLICY {table_name}_tenant_delete_policy ON {table_name}
            FOR DELETE USING (
                current_setting('app.current_tenant', true) = '' OR
                {org_col} = nullif(current_setting('app.current_tenant', true), '')::uuid
            );
            """))

        # messages table
        conn.execute(text("ALTER TABLE messages ENABLE ROW LEVEL SECURITY;"))
        conn.execute(text("ALTER TABLE messages FORCE ROW LEVEL SECURITY;"))
        conn.execute(text("""
        CREATE POLICY messages_tenant_insert_policy ON messages FOR INSERT WITH CHECK (
            current_setting('app.current_tenant', true) = '' OR
            conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        );
        """))
        conn.execute(text("""
        CREATE POLICY messages_tenant_update_policy ON messages FOR UPDATE USING (
            current_setting('app.current_tenant', true) = '' OR
            conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        ) WITH CHECK (
            current_setting('app.current_tenant', true) = '' OR
            conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        );
        """))
        conn.execute(text("""
        CREATE POLICY messages_tenant_select_policy ON messages FOR SELECT USING (
            current_setting('app.current_tenant', true) = '' OR
            conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        );
        """))
        conn.execute(text("""
        CREATE POLICY messages_tenant_delete_policy ON messages FOR DELETE USING (
            current_setting('app.current_tenant', true) = '' OR
            conversation_id IN (SELECT id FROM conversations WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        );
        """))

        # order_items table
        conn.execute(text("ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;"))
        conn.execute(text("ALTER TABLE order_items FORCE ROW LEVEL SECURITY;"))
        conn.execute(text("""
        CREATE POLICY order_items_tenant_insert_policy ON order_items FOR INSERT WITH CHECK (
            current_setting('app.current_tenant', true) = '' OR
            order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        );
        """))
        conn.execute(text("""
        CREATE POLICY order_items_tenant_update_policy ON order_items FOR UPDATE USING (
            current_setting('app.current_tenant', true) = '' OR
            order_id IN (SELECT id FROM orders WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid)
        ) WITH CHECK (
            current_setting('app.current_tenant', true) = '' OR
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
    """Delete all rows across all tables atomically using TRUNCATE CASCADE."""
    from app.database import tenant_var
    tenant_var.set(None)
    db.is_admin = True
    db.organization_id = None
    try:
        db.execute(text("TRUNCATE TABLE organizations, users, categories, products, conversations, messages, customer_memories, orders, order_items, recommendation_feedback, approval_requests, notifications CASCADE;"))
        db.commit()
    except Exception:
        db.rollback()
        # Fallback to model deletes with rollback on error
        for model in [
            models.RecommendationFeedback,
            models.OrderItem,
            models.Order,
            models.Notification,
            models.ApprovalRequest,
            models.CustomerMemory,
            models.Message,
            models.Conversation,
            models.Product,
            models.Category,
            models.User,
            models.Organization
        ]:
            try:
                db.query(model).delete()
                db.commit()
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
