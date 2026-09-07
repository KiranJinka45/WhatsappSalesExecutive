import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.database import SessionLocal
from app import models

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_org():
    db = SessionLocal()
    org = db.query(models.Organization).filter(models.Organization.whatsapp_phone_number_id == "100987654321").first()
    if not org:
        org = models.Organization(
            name="Test Apparel Brand",
            whatsapp_number="+15551234567",
            whatsapp_phone_number_id="100987654321",
            whatsapp_business_account_id="123456789012345",
            policies={}
        )
        db.add(org)
        db.commit()
    yield org
    db.close()

def test_meta_webhook_valid_signature():
    old_testing = settings.TESTING
    old_secret = settings.WHATSAPP_APP_SECRET
    try:
        secret = "test_meta_app_secret_12345"
        settings.WHATSAPP_APP_SECRET = secret
        settings.TESTING = False
        
        body = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789012345",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "15551234567",
                            "phone_number_id": "100987654321"
                        },
                        "contacts": [{
                            "profile": {"name": "Jane Customer"},
                            "wa_id": "15559876543"
                        }],
                        "messages": [{
                            "from": "15559876543",
                            "id": "wamid.HBgLMTU1NTk4NzY1NDMVAgASGBQzQTZEMkQ1QjczMTQ5RDI1QUUxOAA=",
                            "timestamp": "1695213600",
                            "text": {"body": "Do you have a maroon silk saree under ₹4,000?"},
                            "type": "text"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }
        raw_bytes = json.dumps(body).encode("utf-8")
        sig = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
        
        response = client.post(
            "/api/webhooks/whatsapp",
            content=raw_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={sig}"
            }
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processing"
    finally:
        settings.TESTING = old_testing
        settings.WHATSAPP_APP_SECRET = old_secret


def test_meta_webhook_invalid_signature_rejected():
    old_testing = settings.TESTING
    old_secret = settings.WHATSAPP_APP_SECRET
    try:
        secret = "test_meta_app_secret_12345"
        settings.WHATSAPP_APP_SECRET = secret
        settings.TESTING = False
        
        body = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789012345",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {"display_phone_number": "15551234567", "phone_number_id": "100987654321"},
                        "messages": [{"from": "15559876543", "id": "wamid.test", "text": {"body": "hello"}, "type": "text"}]
                    },
                    "field": "messages"
                }]
            }]
        }
        raw_bytes = json.dumps(body).encode("utf-8")
        tampered_sig = "sha256=invalidhash00000000000000000000000000000000000000000000000000000000"
        
        response = client.post(
            "/api/webhooks/whatsapp",
            content=raw_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": tampered_sig
            }
        )
        assert response.status_code == 403
        assert "Invalid or missing signature" in response.json()["detail"]
    finally:
        settings.TESTING = old_testing
        settings.WHATSAPP_APP_SECRET = old_secret


def test_meta_webhook_rejects_wasender_or_arbitrary_post():
    old_testing = settings.TESTING
    old_secret = settings.WHATSAPP_APP_SECRET
    try:
        secret = "test_meta_app_secret_12345"
        settings.WHATSAPP_APP_SECRET = secret
        settings.TESTING = False
        
        body = {
            "event": "messages.upsert",
            "data": {
                "key": {"remoteJid": "919999999999@s.whatsapp.net", "fromMe": False, "id": "wasender_msg_123"},
                "message": {"conversation": "Hi"}
            }
        }
        raw_bytes = json.dumps(body).encode("utf-8")
        sig = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
        
        response = client.post(
            "/api/webhooks/whatsapp",
            content=raw_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={sig}"
            }
        )
        assert response.status_code == 422
        assert "Unprocessable Entity: Unrecognized payload structure" in response.json()["detail"]
    finally:
        settings.TESTING = old_testing
        settings.WHATSAPP_APP_SECRET = old_secret
