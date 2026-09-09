import pytest
import io
import uuid
from fastapi.testclient import TestClient
from tests.conftest import app, TestingSessionLocal, clean_tables, create_test_tenant
from app import models

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

def _get_auth(suffix=None):
    s = suffix or str(uuid.uuid4())[:8]
    return create_test_tenant(client, f"cat_rec_{s}@example.com", f"CatRec User {s}", f"CatRec Org {s}")

def test_catalog_import_csv_atomic_upsert_and_reupload():
    auth_headers = _get_auth("import_upsert")
    
    # 1. Initial CSV Upload via POST /api/catalog/import/csv
    csv_v1 = (
        "sku,name,price,category,stock_count,color,fabric\n"
        "SKU-BOUTIQUE-01,Kanchipuram Red Saree,12000,Sarees,15,Red,Silk\n"
        "SKU-BOUTIQUE-02,Banarasi Blue Saree,18000,Sarees,8,Blue,Katan Silk\n"
    )
    files = {"file": ("catalog_v1.csv", io.BytesIO(csv_v1.encode("utf-8")), "text/csv")}
    res = client.post("/api/catalog/import/csv", headers=auth_headers, files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["created"] == 2
    assert data["updated"] == 0
    assert data["invalid_rows"] == 0

    # Verify DB products
    get_res1 = client.get("/api/catalog/products", headers=auth_headers)
    assert get_res1.status_code == 200
    prods1 = get_res1.json()
    assert len(prods1) == 2

    # 2. Re-upload CSV with updated price and stock (Atomic Bulk Upsert - no duplicates!)
    csv_v2 = (
        "sku,name,price,category,stock_count,color,fabric\n"
        "SKU-BOUTIQUE-01,Kanchipuram Red Saree,12500,Sarees,20,Red,Silk\n"  # Price & stock updated
        "SKU-BOUTIQUE-02,Banarasi Blue Saree,18000,Sarees,5,Blue,Katan Silk\n"  # Stock updated
        "SKU-BOUTIQUE-03,Chanderi Green Saree,4500,Sarees,10,Green,Chanderi\n" # New SKU
    )
    files_v2 = {"file": ("catalog_v2.csv", io.BytesIO(csv_v2.encode("utf-8")), "text/csv")}
    res_v2 = client.post("/api/catalog/import/csv", headers=auth_headers, files=files_v2)
    assert res_v2.status_code == 200
    data_v2 = res_v2.json()
    assert data_v2["status"] == "success"
    assert data_v2["created"] == 1
    assert data_v2["updated"] == 2

    # Verify DB products count is 3 (2 updated, 1 created, 0 duplicates)
    get_res2 = client.get("/api/catalog/products", headers=auth_headers)
    prods2 = get_res2.json()
    assert len(prods2) == 3
    sku_map = {p["sku"]: p for p in prods2}
    assert float(sku_map["SKU-BOUTIQUE-01"]["price"]) == 12500.0
    assert sku_map["SKU-BOUTIQUE-01"]["stock_count"] == 20

def test_catalog_import_csv_validation_errors():
    auth_headers = _get_auth("val_errs")
    
    # Invalid CSV: negative price and missing SKU
    csv_bad = (
        "sku,name,price,category,stock_count\n"
        "SKU-GOOD-01,Good Saree,5000,Sarees,10\n"
        "SKU-BAD-01,Bad Saree,-1200,Sarees,5\n"
    )
    files = {"file": ("bad.csv", io.BytesIO(csv_bad.encode("utf-8")), "text/csv")}
    res = client.post("/api/catalog/import/csv?mode=atomic", headers=auth_headers, files=files)
    assert res.status_code == 400
    assert "negative" in res.json()["detail"].lower() or "price" in res.json()["detail"].lower()

def test_meta_webhook_status_update_delivered_and_read():
    db = TestingSessionLocal()
    org = models.Organization(name="Status Test Org", whatsapp_number="+15551234567")
    db.add(org)
    db.commit()
    db.refresh(org)

    conv = models.Conversation(organization_id=org.id, customer_phone="+15559876543", status="AI_ACTIVE")
    db.add(conv)
    db.commit()
    db.refresh(conv)

    wamid = "wamid.HBgLMTIzNDU2Nzg5MA=="
    outbound = models.OutboundMessage(
        organization_id=org.id,
        conversation_id=conv.id,
        provider_idempotency_key=f"outbox_test_{uuid.uuid4().hex[:6]}",
        provider_message_id=wamid,
        payload_hash="hash123",
        recipient_phone=conv.customer_phone,
        content="Hello customer!",
        status="SENT"
    )
    db.add(outbound)
    db.commit()
    db.refresh(outbound)
    outbound_id = outbound.id
    db.close()

    # 1. Post Meta status webhook update: DELIVERED
    status_payload_delivered = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WABA123",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "+15551234567"},
                    "statuses": [{
                        "id": wamid,
                        "status": "delivered",
                        "timestamp": "1678900000",
                        "recipient_id": "15559876543"
                    }]
                }
            }]
        }]
    }

    res_deliv = client.post("/api/webhooks/whatsapp", json=status_payload_delivered)
    assert res_deliv.status_code == 200
    assert res_deliv.json()["status"] == "success"

    # Verify status in database
    db2 = TestingSessionLocal()
    msg1 = db2.query(models.OutboundMessage).filter(models.OutboundMessage.id == outbound_id).first()
    assert msg1.status == "DELIVERED"
    db2.close()

    # 2. Post Meta status webhook update: READ
    status_payload_read = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WABA123",
            "changes": [{
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "+15551234567"},
                    "statuses": [{
                        "id": wamid,
                        "status": "read",
                        "timestamp": "1678900100",
                        "recipient_id": "15559876543"
                    }]
                }
            }]
        }]
    }

    res_read = client.post("/api/webhooks/whatsapp", json=status_payload_read)
    assert res_read.status_code == 200
    assert res_read.json()["status"] == "success"

    db3 = TestingSessionLocal()
    msg2 = db3.query(models.OutboundMessage).filter(models.OutboundMessage.id == outbound_id).first()
    assert msg2.status == "READ"
    db3.close()

def test_outbox_reconciliation_api():
    auth_headers = _get_auth("reconcile")
    db = TestingSessionLocal()
    
    # Resolve org and user from auth token
    user = db.query(models.User).filter(models.User.email == "cat_rec_reconcile@example.com").first()
    org_id = user.organization_id

    conv = models.Conversation(organization_id=org_id, customer_phone="+15551112222", status="HUMAN_TAKEOVER")
    db.add(conv)
    db.commit()
    db.refresh(conv)

    # Create outbound message in UNKNOWN_PROVIDER_OUTCOME state
    outbound = models.OutboundMessage(
        organization_id=org_id,
        conversation_id=conv.id,
        provider_idempotency_key=f"outbox_rec_{uuid.uuid4().hex[:6]}",
        payload_hash="hash999",
        recipient_phone=conv.customer_phone,
        content="Is this available?",
        status="UNKNOWN_PROVIDER_OUTCOME",
        last_error="Provider Network Timeout"
    )
    db.add(outbound)
    db.commit()
    db.refresh(outbound)
    outbound_id = str(outbound.id)
    db.close()

    # 1. Reconcile with "allow_resend"
    res_resend = client.post(
        f"/api/outbox/{outbound_id}/reconcile",
        headers=auth_headers,
        json={"action": "allow_resend", "notes": "Merchant retrying manually"}
    )
    assert res_resend.status_code == 200
    res_data1 = res_resend.json()
    assert res_data1["status"] == "success"
    assert res_data1["previous_status"] == "UNKNOWN_PROVIDER_OUTCOME"
    assert res_data1["new_status"] == "PENDING"

    # 2. Reconcile with "close_loop"
    res_close = client.post(
        f"/api/outbox/{outbound_id}/reconcile",
        headers=auth_headers,
        json={"action": "close_loop", "notes": "Verified on merchant phone"}
    )
    assert res_close.status_code == 200
    res_data2 = res_close.json()
    assert res_data2["status"] == "success"
    assert res_data2["previous_status"] == "PENDING"
    assert res_data2["new_status"] == "DELIVERED"

    # Check database audit logs
    db4 = TestingSessionLocal()
    audits = db4.query(models.ApprovalAuditLog).filter(models.ApprovalAuditLog.organization_id == org_id).all()
    assert len(audits) >= 2
    actions = {a.action for a in audits}
    assert "RECONCILE_ALLOW_RESEND" in actions
    assert "RECONCILE_CLOSE_LOOP" in actions
    db4.close()

def test_outbox_list_api():
    auth_headers = _get_auth("list_queue")
    db = TestingSessionLocal()
    user = db.query(models.User).filter(models.User.email == "cat_rec_list_queue@example.com").first()
    org_id = user.organization_id

    conv = models.Conversation(organization_id=org_id, customer_phone="+15553334444", status="HUMAN_TAKEOVER")
    db.add(conv)
    db.commit()
    db.refresh(conv)

    msg_unknown = models.OutboundMessage(
        organization_id=org_id,
        conversation_id=conv.id,
        message_version=1,
        provider_idempotency_key=f"idem_list_unk_{uuid.uuid4()}",
        payload_hash="hash_list_unk",
        recipient_phone="+15553334444",
        content="Testing unknown list",
        status="UNKNOWN_PROVIDER_OUTCOME",
        attempt_count=3,
        last_error="Network timeout on provider"
    )
    msg_delivered = models.OutboundMessage(
        organization_id=org_id,
        conversation_id=conv.id,
        message_version=1,
        provider_idempotency_key=f"idem_list_del_{uuid.uuid4()}",
        payload_hash="hash_list_del",
        recipient_phone="+15553334444",
        content="Testing delivered list",
        status="DELIVERED",
        attempt_count=1
    )
    db.add_all([msg_unknown, msg_delivered])
    db.commit()
    db.close()

    # Query with status filter
    res_filtered = client.get("/api/outbox?status=UNKNOWN_PROVIDER_OUTCOME", headers=auth_headers)
    assert res_filtered.status_code == 200
    items_filtered = res_filtered.json()
    assert len(items_filtered) >= 1
    assert all(i["status"] == "UNKNOWN_PROVIDER_OUTCOME" for i in items_filtered)

    # Query all
    res_all = client.get("/api/outbox", headers=auth_headers)
    assert res_all.status_code == 200
    items_all = res_all.json()
    assert len(items_all) >= 2

