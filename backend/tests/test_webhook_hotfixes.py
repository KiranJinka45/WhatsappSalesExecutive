import pytest
from fastapi.testclient import TestClient
from tests.conftest import app, TestingSessionLocal, clean_tables
from app import models

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

def test_webhook_fallback_rejection():
    """Verify that inbound webhooks for unknown phone_number_id fail safely without matching arbitrary tenants."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15555555555",
                                "phone_number_id": "9999999999" # Unknown ID
                            },
                            "messages": [
                                {
                                    "from": "919999999999",
                                    "id": "ABGGxx123",
                                    "timestamp": "1672531199",
                                    "text": {"body": "Hello!"},
                                    "type": "text"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    response = client.post("/api/webhooks/whatsapp", json=payload)
    assert response.status_code == 200
    res_json = response.json()
    assert res_json.get("status") == "error"
    assert "Tenant matching failed" in res_json.get("reason", "")
