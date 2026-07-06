import pytest
from fastapi.testclient import TestClient
from datetime import timedelta
import uuid

from app.security import create_access_token
from tests.conftest import app, TestingSessionLocal, clean_tables, create_test_tenant

client = TestClient(app)

def test_expired_jwt_rejection():
    # Generate a JWT that expired 1 hour ago
    expired_token = create_access_token(
        data={"sub": str(uuid.uuid4())},
        expires_delta=timedelta(hours=-1)
    )
    
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/catalog/products", headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"

def test_malformed_jwt_rejection():
    headers = {"Authorization": "Bearer this.is.not.a.valid.jwt"}
    response = client.get("/api/catalog/products", headers=headers)
    assert response.status_code == 401

def test_missing_auth_header():
    response = client.get("/api/catalog/products")
    assert response.status_code == 401

def test_wrong_role_rejection():
    # If there are roles like 'admin' vs 'user', test it here
    pass

def test_nonexistent_user_token_rejection():
    # Valid JWT but user ID doesn't exist in DB
    fake_user_id = str(uuid.uuid4())
    token = create_access_token(data={"sub": fake_user_id})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get("/api/catalog/products", headers=headers)
    assert response.status_code == 401
