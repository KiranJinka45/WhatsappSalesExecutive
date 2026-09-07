import pytest
import uuid
import time
from unittest.mock import patch, MagicMock
from fastapi import Request, HTTPException
from fastapi.testclient import TestClient

from tests.conftest import app, TestingSessionLocal, clean_tables
from app import models
from app.config import settings
from app.rate_limiter import RedisRateLimiter
from app.routers.webhooks import process_message_async

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

def test_total_llm_outage_generates_graceful_fallback():
    db = TestingSessionLocal()
    try:
        org = models.Organization(
            name="Resilience Test Boutique", 
            whatsapp_number="+919876543210",
            whatsapp_phone_number_id="1292475657271575"
        )
        db.add(org)
        db.commit()
        db.refresh(org)

        conv = models.Conversation(
            organization_id=org.id,
            customer_phone="+919999988888",
            customer_name="Test Customer",
            status="AI_ACTIVE"
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

        cust_msg = models.Message(
            conversation_id=conv.id,
            sender="customer",
            message_type="text",
            content="Hi, do you have banarasi silk sarees under 5000?"
        )
        db.add(cust_msg)
        db.commit()

        with patch("app.ai.client.get_gemini_client", side_effect=Exception("Gemini 503 Unavailable")), \
             patch("app.ai.client.get_groq_client", side_effect=Exception("Groq 429 Rate Limit")), \
             patch("app.ai.client.get_openai_client", return_value=None), \
             patch("app.ai.client.get_openrouter_client", return_value=None), \
             patch("app.ai.client.get_nvidia_client", return_value=None), \
             patch("app.bsp_service.send_whatsapp_message", return_value=True):

            process_message_async(
                org_id=str(org.id),
                conv_id=str(conv.id),
                message_text="Hi, do you have banarasi silk sarees under 5000?"
            )

        db.expire_all()
        ai_messages = db_session = db.query(models.Message).filter(
            models.Message.conversation_id == conv.id,
            models.Message.sender == "ai"
        ).all()

        assert len(ai_messages) >= 1
        fallback_message = ai_messages[-1]
        assert fallback_message.content is not None
        assert len(fallback_message.content.strip()) > 0
        # In shadow/guardrail mode without catalog items, fallback status is 'pending' or 'sent'
        assert fallback_message.status in ("pending", "sent")

        updated_conv = db.query(models.Conversation).filter(models.Conversation.id == conv.id).first()
        assert updated_conv.status in ("AI_ACTIVE", "WAITING_APPROVAL")
    finally:
        db.close()

def test_redis_down_rate_limiter_in_memory_degradation():
    limiter = RedisRateLimiter(name="test_resilience", requests_limit=3, window_seconds=60)

    req = MagicMock(spec=Request)
    req.headers = {"x-forwarded-for": "198.51.100.99"}
    req.client = MagicMock()
    req.client.host = "10.0.0.1"

    original_testing = settings.TESTING
    try:
        settings.TESTING = False

        with patch("redis.from_url", side_effect=Exception("Redis connection refused on port 6379")):
            limiter(req)
            limiter(req)
            limiter(req)

            with pytest.raises(HTTPException) as exc_info:
                limiter(req)

            assert exc_info.value.status_code == 429
            assert "Too many requests" in exc_info.value.detail
    finally:
        settings.TESTING = original_testing

def test_webhook_deduplication_and_replay_protection():
    db = TestingSessionLocal()
    try:
        org = models.Organization(
            name="Dedup Store", 
            whatsapp_number="+919876500000",
            whatsapp_phone_number_id="1292475657271575"
        )
        db.add(org)
        db.commit()
        db.refresh(org)

        dedup_msg_id = f"wamid_test_dedup_{uuid.uuid4().hex[:8]}"
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "1292475657271575",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "+919876500000",
                            "phone_number_id": "1292475657271575"
                        },
                        "contacts": [{
                            "profile": {"name": "Replay Tester"},
                            "wa_id": "919111122222"
                        }],
                        "messages": [{
                            "from": "919111122222",
                            "id": dedup_msg_id,
                            "timestamp": str(int(time.time())),
                            "text": {"body": "Checking pricing for silk saree"},
                            "type": "text"
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

        res1 = client.post("/api/webhooks/whatsapp", json=payload)
        assert res1.status_code == 200
        assert res1.json().get("status") == "processing"

        res2 = client.post("/api/webhooks/whatsapp", json=payload)
        assert res2.status_code == 200
        assert res2.json().get("status") == "ignored"
        assert "Duplicate message" in res2.json().get("reason", "")
    finally:
        db.close()
