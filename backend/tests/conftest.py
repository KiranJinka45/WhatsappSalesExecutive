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
from app import ai_service
ai_service.get_embedding = unittest.mock.MagicMock(return_value=[0.0] * 768)
ai_service.classify_intent = unittest.mock.MagicMock(return_value="product_discovery")
ai_service.generate_reply = unittest.mock.MagicMock(return_value="Mocked AI reply")


import pytest

@pytest.fixture(scope="session", autouse=True)
def initialize_db():
    setup_test_db()
    yield
    # We can keep tables or drop them at end of session

def setup_test_db():
    """Create pgvector extension and all tables."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_test_db():
    """No-op during test runs to prevent dropping tables between test classes."""
    pass


def clean_tables(db):
    """Delete all rows in reverse FK order."""
    from app.database import tenant_var
    tenant_var.set(None)
    db.organization_id = None
    db.query(models.Message).delete()
    db.query(models.Conversation).delete()
    db.query(models.Product).delete()
    db.query(models.Category).delete()
    db.query(models.User).delete()
    db.query(models.Organization).delete()
    db.commit()


def create_test_tenant(client, email, name, org_name, password="securepassword123"):
    """
    Register and log in a test tenant. Returns auth headers dict.
    """
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
