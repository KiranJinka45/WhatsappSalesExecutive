import pytest
from fastapi.testclient import TestClient
from tests.conftest import app, TestingSessionLocal, clean_tables
from app import models, database

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

def test_rls_fail_closed():
    db = TestingSessionLocal()
    # 1. Create a dummy organization and a product
    org = models.Organization(name="Test Shop", whatsapp_number="+15550100010")
    db.add(org)
    db.commit()
    db.refresh(org)
    
    prod = models.Product(
        organization_id=org.id,
        sku="TEST-SKU",
        name="Test product",
        price=10.0,
        color="Red",
        description="A nice product"
    )
    db.add(prod)
    db.commit()
    db.close()
    
    # 2. Query without any organization_id set on the session and tenant_var unset
    db2 = TestingSessionLocal()
    db2.is_admin = False
    
    # Check that query filters out all products because of dummy UUID fallback
    products = db2.query(models.Product).all()
    assert len(products) == 0
    db2.close()

def test_webhook_fallback_rejection():
    # 1. Register a valid organization
    db = TestingSessionLocal()
    org = models.Organization(name="Active Shop", whatsapp_number="+917989888858", whatsapp_phone_number_id="7989888858")
    db.add(org)
    db.commit()
    db.close()
    
    # 2. Dispatch a webhook payload for an UNKNOWN organization (different phone_number_id)
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
