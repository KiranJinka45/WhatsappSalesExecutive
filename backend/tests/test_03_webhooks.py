import pytest
from fastapi.testclient import TestClient

from tests.conftest import app, TestingSessionLocal, clean_tables
from app.config import settings

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

def test_whatsapp_webhook_verification():
    hub_mode = "subscribe"
    hub_verify_token = settings.WHATSAPP_VERIFY_TOKEN
    hub_challenge = "123456789"
    
    response = client.get(
        f"/api/webhooks/whatsapp?hub.mode={hub_mode}&hub.verify_token={hub_verify_token}&hub.challenge={hub_challenge}"
    )
    assert response.status_code == 200
    assert response.text == hub_challenge

def test_whatsapp_webhook_verification_invalid_token():
    response = client.get(
        "/api/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=wrong_token&hub.challenge=123"
    )
    assert response.status_code == 403

def test_whatsapp_webhook_empty_payload():
    response = client.post("/api/webhooks/whatsapp", json={})
    assert response.status_code in [200, 422]

def test_whatsapp_webhook_missing_messages():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "123", "phone_number_id": "123"}
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    response = client.post("/api/webhooks/whatsapp", json=payload)
    assert response.status_code == 200
