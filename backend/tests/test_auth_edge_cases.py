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
    # 1. Test Staff User (Should get 403)
    db = TestingSessionLocal()
    db.is_admin = True
    try:
        from app.models import User, Organization
        import uuid
        from app.security import get_password_hash
        
        org = Organization(name="Staff Org")
        db.add(org)
        db.commit()
        
        staff_user = User(
            id=uuid.uuid4(),
            organization_id=org.id,
            email="staff@example.com",
            name="Staff",
            password_hash=get_password_hash("pass"),
            role="staff"
        )
        db.add(staff_user)
        db.commit()
        
        staff_token = create_access_token(data={"sub": str(staff_user.id)})
        staff_headers = {"Authorization": f"Bearer {staff_token}"}
        
        update_data = {"whatsapp_number": "123456789"}
        response = client.put("/api/brand/profile", json=update_data, headers=staff_headers)
        assert response.status_code == 403
        assert response.json()["detail"] == "Operation not permitted"
        
        # 2. Test Owner User (Should get 200)
        owner_user = User(
            id=uuid.uuid4(),
            organization_id=org.id,
            email="owner@example.com",
            name="Owner",
            password_hash=get_password_hash("pass"),
            role="owner"
        )
        db.add(owner_user)
        db.commit()
        
        owner_token = create_access_token(data={"sub": str(owner_user.id)})
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        
        response = client.put("/api/brand/profile", json=update_data, headers=owner_headers)
        assert response.status_code == 200
    finally:
        db.is_admin = False
        db.close()

def test_nonexistent_user_token_rejection():
    # Valid JWT but user ID doesn't exist in DB
    fake_user_id = str(uuid.uuid4())
    token = create_access_token(data={"sub": fake_user_id})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.get("/api/catalog/products", headers=headers)
    assert response.status_code == 401
