import pytest
from unittest.mock import patch
from tests.conftest import app, TestingSessionLocal, clean_tables
from app import models
from app.routers.webhooks import process_message_async

@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

def test_visual_search_guardrails():
    db = TestingSessionLocal()

    # 1. Create Tenant A
    org_a = models.Organization(name="Tenant A Boutique", whatsapp_number="+919900001111")
    db.add(org_a)
    db.commit()
    db.refresh(org_a)

    # 2. Create Tenant B
    org_b = models.Organization(name="Tenant B Boutique", whatsapp_number="+919900002222")
    db.add(org_b)
    db.commit()
    db.refresh(org_b)

    # 3. Create active product under Tenant B, inactive product under Tenant A
    p_active_b = models.Product(
        organization_id=org_b.id,
        sku="SKU-B",
        name="Tenant B Silk Saree",
        price=2000.0,
        color="Blue",
        fabric="Silk",
        stock_count=5,
        image_urls=["https://example.com/saree_b.jpg"],
        embedding_status="completed"
    )
    db.add(p_active_b)

    p_inactive_a = models.Product(
        organization_id=org_a.id,
        sku="SKU-A",
        name="Tenant A Inactive Saree",
        price=2000.0,
        color="Blue",
        fabric="Silk",
        stock_count=0, # Inactive/Out of stock
        image_urls=["https://example.com/saree_a.jpg"],
        embedding_status="completed"
    )
    db.add(p_inactive_a)
    db.commit()

    conv_a = models.Conversation(organization_id=org_a.id, customer_phone="+919999999999", customer_name="Sita Reddy")
    db.add(conv_a)
    db.commit()
    db.refresh(conv_a)

    mock_entities = {
        "product_type": "Silk",
        "color": None,
        "fabric": "Silk",
        "size": None,
        "budget_min": None,
        "budget_max": 3000.0,
        "gender": None
    }

    with patch("app.ai_service.classify_intent", return_value="product_visual_search"), \
         patch("app.ai_service.extract_entities", return_value=mock_entities), \
         patch("app.bsp_service.send_whatsapp_message") as mock_send:
        
        # Trigger visual search query on Tenant A
        process_message_async(str(org_a.id), str(conv_a.id), "show me silk sarees under 3000")
        
        # Verify that:
        # A) Tenant A did not send any images because Tenant A's only product is inactive (stock_count=0)
        # B) Tenant B's active product is not leaked to Tenant A
        sent_messages = db.query(models.Message).filter(models.Message.conversation_id == conv_a.id).all()
        ai_image_msgs = [m for m in sent_messages if m.sender == "ai" and m.message_type == "image"]
        assert len(ai_image_msgs) == 0

        ai_text_msgs = [m for m in sent_messages if m.sender == "ai" and m.message_type == "text"]
        assert len(ai_text_msgs) >= 1
        # Must return clean "don't have any matching products" text reply instead of leaking B's product
        assert "don't have any matching products" in ai_text_msgs[0].content or "starting from" not in ai_text_msgs[0].content

    db.close()
