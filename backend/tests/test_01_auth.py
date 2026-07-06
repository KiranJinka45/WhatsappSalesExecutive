import pytest
from fastapi.testclient import TestClient
import uuid
import json

from tests.conftest import app, TestingSessionLocal, clean_tables

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

def test_signup_valid_user():
    signup_data = {
        "email": f"test_signup_{uuid.uuid4()}@example.com",
        "name": "Test User",
        "password": "securepassword123",
        "organization_name": "Test Org"
    }
    res = client.post("/api/auth/signup", json=signup_data)
    assert res.status_code == 201
    data = res.json()
    assert "id" in data
    assert data["email"] == signup_data["email"]

def test_signup_duplicate_email():
    email = f"test_dup_{uuid.uuid4()}@example.com"
    signup_data = {
        "email": email,
        "name": "Test User",
        "password": "securepassword123",
        "organization_name": "Test Org"
    }
    # First signup
    client.post("/api/auth/signup", json=signup_data)
    
    # Second signup should fail
    res = client.post("/api/auth/signup", json=signup_data)
    assert res.status_code == 409
    assert "already exists" in res.json()["detail"].lower()

def test_login_invalid_password():
    email = f"test_invalid_{uuid.uuid4()}@example.com"
    signup_data = {
        "email": email,
        "name": "Test User",
        "password": "securepassword123",
        "organization_name": "Test Org"
    }
    client.post("/api/auth/signup", json=signup_data)
    
    login_data = {
        "username": email,
        "password": "wrongpassword"
    }
    res = client.post("/api/auth/login", data=login_data)
    assert res.status_code == 401

def test_login_invalid_email():
    login_data = {
        "username": "doesnotexist@example.com",
        "password": "securepassword123"
    }
    res = client.post("/api/auth/login", data=login_data)
    assert res.status_code == 401

def test_get_current_user_profile():
    # Setup user
    email = f"test_me_{uuid.uuid4()}@example.com"
    signup_data = {
        "email": email,
        "name": "Profile User",
        "password": "securepassword123",
        "organization_name": "Profile Org"
    }
    client.post("/api/auth/signup", json=signup_data)
    
    login_res = client.post("/api/auth/login", data={"username": email, "password": "securepassword123"})
    token = login_res.json()["access_token"]
    
    # Fetch profile
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == email
    assert data["name"] == "Profile User"
    assert "organization_id" in data
