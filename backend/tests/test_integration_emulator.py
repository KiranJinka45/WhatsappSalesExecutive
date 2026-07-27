import pytest
import time
import threading
import uvicorn
import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app as backend_app
from app.emulator import app as emulator_app
from app.config import settings
from tests.conftest import TestingSessionLocal, clean_tables
from app import models

# 1. Spin up the Meta Emulator in a background thread during tests
@pytest.fixture(scope="module", autouse=True)
def run_emulator():
    # Force settings base URL to point to local emulator port
    settings.WHATSAPP_API_BASE_URL = "http://127.0.0.1:9000"
    settings.WHATSAPP_PHONE_NUMBER_ID = "mock_phone_id"
    settings.WHATSAPP_ACCESS_TOKEN = "mock_access_token"
    
    config = uvicorn.Config(emulator_app, host="127.0.0.1", port=9000, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()
    time.sleep(1.0)  # Wait for server to bind
    yield
    server.should_exit = True
    thread.join(timeout=1.0)

@pytest.fixture(autouse=True)
def clean_emulator_and_db():
    # Clear emulator logs
    httpx.post("http://127.0.0.1:9000/api/emulator/clear")
    
    # Setup test database tables cleanly
    db = TestingSessionLocal()
    clean_tables(db)
    
    # Ensure at least one test Organization exists
    org = models.Organization(
        name="Bangalore Couture Test",
        whatsapp_number="15550000000",
        policies={"return_policy": "No returns allowed."}
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    
    # Ensure a User exists linked to this organization
    user = models.User(
        organization_id=org.id,
        email="testowner@example.com",
        password_hash="mock_hash",
        role="owner",
        name="Owner Name"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    db.close()
    yield

def build_mock_webhook(phone: str, text: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "field": "messages",
                "value": {
                    "contacts": [{
                        "wa_id": phone,
                        "profile": {"name": "Integration Customer"}
                    }],
                    "messages": [{
                        "id": f"wamid.test_{int(time.time())}_{phone}",
                        "from": phone,
                        "timestamp": str(int(time.time())),
                        "type": "text",
                        "text": {"body": text}
                    }],
                    "metadata": {
                        "display_phone_number": "15550000000",
                        "phone_number_id": "mock_phone_id"
                    }
                }
            }]
        }]
    }

def test_emulator_end_to_end_loop():
    """
    Test standard success loop:
    Webhook Inbound -> Backend -> AI Orchestrator -> Emulator Outbound Received
    """
    # Override mock generate_reply return value for this integration test
    from app import ai_service
    ai_service.generate_reply.return_value = "Hello! Check out our Royal Silk Saree (SKU-SAR-999) for INR 2999."

    client = TestClient(backend_app)
    
    # Seed a simple category and product for search
    db = TestingSessionLocal()
    org = db.query(models.Organization).first()
    category = models.Category(organization_id=org.id, name="Sarees")
    db.add(category)
    db.commit()
    db.refresh(category)
    
    product = models.Product(
        organization_id=org.id,
        category_id=category.id,
        sku="SKU-SAR-999",
        name="Royal Silk Saree",
        price=2999.00,
        color="Blue",
        fabric="Silk",
        stock_count=5,
        sizes=["Free Size"],
        embedding=[0.1] * 768,  # Dummy mock embedding vector
        embedding_status="completed"
    )
    db.add(product)
    db.commit()
    db.close()

    # Send inbound webhook requesting sarees
    webhook_payload = build_mock_webhook("919876543210", "Show sarees under 4000")
    response = client.post("/api/webhooks/whatsapp", json=webhook_payload)
    
    assert response.status_code == 200
    assert response.json() == {"status": "processing"}
    
    # Wait for the background execution task to complete (poll up to 6s)
    messages = []
    for _ in range(12):
        time.sleep(0.5)
        em_res = httpx.get("http://127.0.0.1:9000/api/emulator/messages")
        if em_res.status_code == 200 and len(em_res.json()) > 0:
            messages = em_res.json()
            break
            
    assert len(messages) == 1
    sent_msg = messages[0]
    assert sent_msg["recipient"] == "919876543210"
    assert "Royal Silk Saree" in sent_msg["content"]
    assert "SKU-SAR-999" in sent_msg["content"]

    # Save outbound payload as a golden artifact for visual and regression audits
    import os
    import json
    goldens_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "goldens", "outbound"))
    os.makedirs(goldens_dir, exist_ok=True)
    golden_path = os.path.join(goldens_dir, "budget_search.json")
    with open(golden_path, "w", encoding="utf-8") as f:
        json.dump(sent_msg["payload"], f, indent=2)

def test_signature_verification_rejection():
    """
    Test that invalid hub signatures are rejected with HTTP 403, and missing secrets with 401.
    """
    client = TestClient(backend_app)
    original_secret = settings.WHATSAPP_APP_SECRET
    original_testing = settings.TESTING
    original_env = settings.APP_ENV
    
    try:
        # Enable app secret checks and verify signature rejection
        settings.WHATSAPP_APP_SECRET = "secure_test_secret_key"
        settings.TESTING = False
        settings.APP_ENV = "production"
        
        webhook_payload = build_mock_webhook("919876543210", "Hi")
        
        # 1. Invalid signature
        headers = {"X-Hub-Signature-256": "sha256=invalid_hash_signature_value"}
        response = client.post("/api/webhooks/whatsapp", json=webhook_payload, headers=headers)
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid or missing signature"
        
        # 2. Missing signature
        response_missing = client.post("/api/webhooks/whatsapp", json=webhook_payload)
        assert response_missing.status_code == 403
        assert response_missing.json()["detail"] == "Invalid or missing signature"
        
        # 3. Missing WHATSAPP_APP_SECRET should return 401
        settings.WHATSAPP_APP_SECRET = None
        response_no_secret = client.post("/api/webhooks/whatsapp", json=webhook_payload, headers=headers)
        assert response_no_secret.status_code == 401
        assert response_no_secret.json()["detail"] == "Authentication credentials not provided"
        
    finally:
        settings.WHATSAPP_APP_SECRET = original_secret
        settings.TESTING = original_testing
        settings.APP_ENV = original_env

def test_chaos_server_error_takeover():
    """
    Test that if Meta Emulator fails with HTTP 500, the backend
    gracefully transitions conversation status to 'human_takeover'.
    """
    client = TestClient(backend_app)

    # Seed a simple category and product for search
    db = TestingSessionLocal()
    org = db.query(models.Organization).first()
    category = models.Category(organization_id=org.id, name="Sarees")
    db.add(category)
    db.commit()
    db.refresh(category)
    
    product = models.Product(
        organization_id=org.id,
        category_id=category.id,
        sku="SKU-SAR-999",
        name="Royal Silk Saree",
        price=2999.00,
        color="Blue",
        fabric="Silk",
        stock_count=5,
        sizes=["Free Size"],
        embedding=[0.1] * 768,
        embedding_status="completed"
    )
    db.add(product)
    db.commit()
    db.close()
    
    # Configure emulator to crash
    httpx.post("http://127.0.0.1:9000/api/emulator/configure-chaos", json={
        "delay_seconds": 0,
        "http_status": 500,
        "error_message": "Meta Internal Server Error simulation"
    })
    
    webhook_payload = build_mock_webhook("919876543210", "Do you have blue sarees?")
    response = client.post("/api/webhooks/whatsapp", json=webhook_payload)
    assert response.status_code == 200
    
    time.sleep(3.0)
    
    # Verify database status transitions to human takeover
    db = TestingSessionLocal()
    conv = db.query(models.Conversation).filter(models.Conversation.customer_phone == "919876543210").first()
    assert conv is not None
    
    # Since the outbound dispatch crashed, the system fallback should toggle to takeover
    assert conv.status == "OWNER_ACTIVE"
    
    # Confirm fallback note or error was appended
    messages = db.query(models.Message).filter(models.Message.conversation_id == conv.id).all()
    failed_msg = [m for m in messages if m.status == "failed"]
    assert len(failed_msg) > 0
    db.close()

def test_csv_line_endings_normalization():
    """
    Test that CSV catalog uploads normalize Classic Mac carriage returns (\r)
    line-endings correctly.
    """
    client = TestClient(backend_app)
    
    # Retrieve user from DB to sign JWT correctly
    db = TestingSessionLocal()
    user = db.query(models.User).first()
    db.close()
    
    # Generate CSV content using Classic Mac \r line separator
    csv_mac_content = (
        "sku,name,price,color,category,fabric,stock_count,description,sizes,gender\r"
        "SKU-MAC-101,Mac Silk Kurta,2499.00,Pink,Kurtas,Silk,10,Mac Classic Format,S,Unisex"
    ).encode("utf-8")
    
    # Authorize client session
    from app.security import create_access_token
    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post(
        "/api/catalog/upload",
        files={"file": ("mac_catalog.csv", csv_mac_content, "text/csv")},
        headers=headers
    )
    
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["created"] == 1
    assert res_data["status"] == "success"
    
    # Verify in DB
    db = TestingSessionLocal()
    prod = db.query(models.Product).filter(models.Product.sku == "SKU-MAC-101").first()
    assert prod is not None
    assert prod.name == "Mac Silk Kurta"
    assert float(prod.price) == 2499.00
    db.close()

def test_webhook_idempotency():
    """
    Test idempotency: Replay the exact same webhook payload 10 times.
    Verify that the backend only creates one conversation, one message,
    and dispatches exactly one outbound message to the emulator.
    """
    client = TestClient(backend_app)

    # Seed a simple category and product for search
    db = TestingSessionLocal()
    org = db.query(models.Organization).first()
    category = models.Category(organization_id=org.id, name="Sarees")
    db.add(category)
    db.commit()
    db.refresh(category)
    
    product = models.Product(
        organization_id=org.id,
        category_id=category.id,
        sku="SKU-SAR-999",
        name="Royal Silk Saree",
        price=2999.00,
        color="Blue",
        fabric="Silk",
        stock_count=5,
        sizes=["Free Size"],
        embedding=[0.1] * 768,
        embedding_status="completed"
    )
    db.add(product)
    db.commit()
    db.close()

    webhook_payload = build_mock_webhook("917777777777", "Is there any silk saree?")
    
    # Send 10 identical webhook calls sequentially
    for _ in range(10):
        response = client.post("/api/webhooks/whatsapp", json=webhook_payload)
        assert response.status_code == 200
        # If it's a duplicate, it will return status: ignored
        # (For the first one, it is status: processing)
        
    time.sleep(3.0)
    
    # Assert database structures: exactly 1 conversation and 1 customer message + 1 AI reply
    db = TestingSessionLocal()
    conversations = db.query(models.Conversation).filter(models.Conversation.customer_phone == "917777777777").all()
    assert len(conversations) == 1
    
    messages = db.query(models.Message).filter(models.Message.conversation_id == conversations[0].id).all()
    assert len(messages) == 2  # 1 customer + 1 AI
    db.close()
    
    # Assert emulator received exactly 1 outbound message
    em_res = httpx.get("http://127.0.0.1:9000/api/emulator/messages")
    messages_received = [m for m in em_res.json() if m["recipient"] == "917777777777"]
    assert len(messages_received) == 1

def test_retry_verification():
    """
    Test transient retry: Configure emulator to return 500 two times,
    then succeed on the third attempt.
    Verify that only one message is persisted in the database.
    """
    client = TestClient(backend_app)

    # Seed a simple category and product for search
    db = TestingSessionLocal()
    org = db.query(models.Organization).first()
    category = models.Category(organization_id=org.id, name="Sarees")
    db.add(category)
    db.commit()
    db.refresh(category)
    
    product = models.Product(
        organization_id=org.id,
        category_id=category.id,
        sku="SKU-SAR-999",
        name="Royal Silk Saree",
        price=2999.00,
        color="Blue",
        fabric="Silk",
        stock_count=5,
        sizes=["Free Size"],
        embedding=[0.1] * 768,
        embedding_status="completed"
    )
    db.add(product)
    db.commit()
    db.close()
    
    # Configure emulator to return 500 for the next 2 requests
    httpx.post("http://127.0.0.1:9000/api/emulator/configure-chaos", json={
        "delay_seconds": 0,
        "http_status": 200,
        "error_message": None,
        "fail_count": 2
    })
    
    # Send inbound webhook requesting sarees
    webhook_payload = build_mock_webhook("919999999999", "Do you have sarees?")
    response = client.post("/api/webhooks/whatsapp", json=webhook_payload)
    assert response.status_code == 200
    
    # Wait for processing and retry logic to run
    # Outbound attempts: 1st send (fails) -> sleep 0.5s -> 2nd send (fails) -> sleep 1.0s -> 3rd send (succeeds)
    time.sleep(4.0)
    
    # Assert database structures: exactly 1 conversation and 1 outbound AI message
    db = TestingSessionLocal()
    conv = db.query(models.Conversation).filter(models.Conversation.customer_phone == "919999999999").first()
    assert conv is not None
    # Since it recovered and succeeded, status should be AI_ACTIVE
    assert conv.status == "AI_ACTIVE"
    
    messages = db.query(models.Message).filter(models.Message.conversation_id == conv.id).all()
    # 1 customer message + 1 AI response message (not duplicated!)
    ai_msgs = [m for m in messages if m.sender == "ai"]
    assert len(ai_msgs) == 1
    assert ai_msgs[0].status == "sent"  # Successfully marked as sent after recovery!
    db.close()
    
    # Assert emulator received exactly 1 message
    em_res = httpx.get("http://127.0.0.1:9000/api/emulator/messages")
    messages_received = [m for m in em_res.json() if m["recipient"] == "919999999999"]
    assert len(messages_received) == 1
