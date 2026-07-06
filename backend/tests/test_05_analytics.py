import pytest
from fastapi.testclient import TestClient
import uuid

from tests.conftest import app, TestingSessionLocal, clean_tables, create_test_tenant
from app.database import tenant_var
from app import models

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

def _get_auth():
    return create_test_tenant(client, f"analytics_{uuid.uuid4()}@example.com", "Analytics User", "Analytics Org")

def test_analytics_dashboard_empty():
    auth_headers = _get_auth()
    response = client.get("/api/analytics/dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_conversations" in data
    assert data["total_conversations"] == 0
    assert data["total_messages"] == 0

def test_analytics_dashboard_with_data():
    auth_headers = _get_auth()
    
    res_me = client.get("/api/auth/me", headers=auth_headers)
    org_id = res_me.json()["organization_id"]
    
    db = TestingSessionLocal()
    tenant_var.set(org_id)
    db.organization_id = org_id
    
    conv = models.Conversation(
        id=str(uuid.uuid4()),
        customer_phone="1234567890",
        organization_id=org_id,
        status="active"
    )
    db.add(conv)
    db.commit()
    
    msg = models.Message(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        sender="customer",
        content="Hello"
    )
    db.add(msg)
    db.commit()
    db.close()
    
    response = client.get("/api/analytics/dashboard", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_conversations"] == 1
    assert data["total_messages"] == 1
