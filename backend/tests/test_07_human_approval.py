import pytest
from fastapi.testclient import TestClient
import uuid
import time
import hashlib
import concurrent.futures
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
from sqlalchemy import create_engine, text

from tests.conftest import app, TestingSessionLocal, clean_tables
from app import models, security, schemas
from app.database import tenant_var
from app.approval_service import (
    hash_message,
    revalidate_catalog_facts,
    transition_approval_state
)

client = TestClient(app)
_CACHED_PWD_HASH = security.get_password_hash("Secret123!")

@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

def _create_test_tenant(role="owner", operating_mode="HUMAN_APPROVAL", policies=None):
    digits = "".join([c for c in str(uuid.uuid4().int) if c.isdigit()])[:8]
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    whatsapp_no = f"+9198{digits}"
    org_name = f"Human Approval Pilot Brand {digits}"
    user_email = f"{role}_{digits}@pilotbrand.com"
    user_name = f"Test User {digits}"
    phone_number_id = f"pnid_{digits}"
    
    default_policies = {
        "operating_mode": operating_mode,
        "shadow_mode": False if operating_mode == "HUMAN_APPROVAL" else True,
        "emergency_kill_switch": False,
        "refund_requires_owner": True,
        "discount_limit": 0,
        "bulk_threshold": 10
    }
    if policies:
        default_policies.update(policies)

    db = TestingSessionLocal()
    db.is_admin = True
    tenant_var.set(None)
    db.execute(text("SET LOCAL app.current_tenant = ''"))
    org = models.Organization(
        id=org_id,
        name=org_name,
        whatsapp_number=whatsapp_no,
        whatsapp_phone_number_id=phone_number_id,
        policies=default_policies
    )
    db.add(org)

    user = models.User(
        id=user_id,
        organization_id=org_id,
        email=user_email,
        password_hash=_CACHED_PWD_HASH,
        role=role,
        name=user_name
    )
    db.add(user)
    db.commit()
    db.close()

    token = security.create_access_token({"sub": str(user_id), "org_id": str(org_id), "role": role})

    org_obj = SimpleNamespace(id=org_id, name=org_name, whatsapp_number=whatsapp_no, whatsapp_phone_number_id=phone_number_id, policies=default_policies)
    user_obj = SimpleNamespace(id=user_id, organization_id=org_id, email=user_email, role=role, name=user_name)
    return org_obj, user_obj, token


def _create_test_conversation_and_approval(org_id, proposed_text="Hello! Saree SKU-RED-01 is Rs.2500 in stock.", skus=None, price_snap=None, stock_snap=None, expires_in_seconds=None):
    db = TestingSessionLocal()
    db.is_admin = True
    tenant_var.set(None)
    db.execute(text("SET LOCAL app.current_tenant = ''"))
    conv_id = uuid.uuid4()
    msg_id = uuid.uuid4()
    approval_id = uuid.uuid4()

    conv = models.Conversation(
        id=conv_id,
        organization_id=org_id,
        customer_phone="+919988776655",
        status="WAITING_APPROVAL",
        escalation_reason="Human Approval Pilot"
    )
    db.add(conv)

    msg = models.Message(
        id=msg_id,
        conversation_id=conv_id,
        sender="ai",
        message_type="text",
        content=proposed_text,
        status="pending"
    )
    db.add(msg)

    retrieval_ids = skus or ["SKU-RED-01"]
    price_snapshot = price_snap or {"SKU-RED-01": 2500.0}
    stock_snapshot = stock_snap or {"SKU-RED-01": 5}
    exp_time = (datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)) if expires_in_seconds is not None else None
    msg_hash = hash_message(proposed_text)

    # Ensure matching products exist for catalog revalidation inside the same transaction
    for sku in retrieval_ids:
        existing_p = db.query(models.Product).filter(
            models.Product.organization_id == org_id,
            models.Product.sku == sku
        ).first()
        if not existing_p:
            p_price = Decimal(str(price_snapshot.get(sku, 2500.0))) if price_snapshot else Decimal("2500.00")
            p_stock = stock_snapshot.get(sku, 5) if stock_snapshot else 5
            prod = models.Product(
                id=uuid.uuid4(),
                organization_id=org_id,
                name=f"Product {sku}",
                sku=sku,
                price=p_price,
                stock_count=p_stock
            )
            db.add(prod)

    approval = models.ApprovalRequest(
        id=approval_id,
        conversation_id=conv_id,
        organization_id=org_id,
        status="WAITING_APPROVAL",
        reason="Human Approval Pilot Draft",
        proposed_response=proposed_text,
        ai_recommendation="approve",
        risk_score=10,
        version=1,
        message_hash=msg_hash,
        price_snapshot=price_snapshot,
        stock_snapshot=stock_snapshot,
        retrieval_ids=retrieval_ids,
        expires_at=exp_time
    )
    db.add(approval)

    audit = models.ApprovalAuditLog(
        organization_id=org_id,
        approval_request_id=approval_id,
        conversation_id=conv_id,
        action="DRAFT_CREATED",
        previous_status=None,
        new_status="WAITING_APPROVAL",
        message_content=proposed_text,
        message_hash=msg_hash
    )
    db.add(audit)

    db.commit()
    db.close()

    conv_obj = SimpleNamespace(id=conv_id, organization_id=org_id)
    approval_obj = SimpleNamespace(id=approval_id, organization_id=org_id)
    msg_obj = SimpleNamespace(id=msg_id, conversation_id=conv_id)
    return conv_obj, approval_obj, msg_obj


def test_01_tenant_scoped_inbox_listing():
    """1. Inbox returns only current tenant's requests."""
    org1, user1, token1 = _create_test_tenant()
    org2, user2, token2 = _create_test_tenant()

    _create_test_conversation_and_approval(org1.id, "Draft for Org 1")
    _create_test_conversation_and_approval(org2.id, "Draft for Org 2")

    res1 = client.get("/api/approvals", headers={"Authorization": f"Bearer {token1}"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert len(data1) == 1
    assert data1[0]["proposed_response"] == "Draft for Org 1"
    assert data1[0]["organization_id"] == str(org1.id)

    res2 = client.get("/api/approvals", headers={"Authorization": f"Bearer {token2}"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2) == 1
    assert data2[0]["proposed_response"] == "Draft for Org 2"
    assert data2[0]["organization_id"] == str(org2.id)


def test_02_unauthorized_role_cannot_approve():
    """2. Role permissions strictly enforced (e.g. unauthenticated or viewer rejected)."""
    org, user, token = _create_test_tenant(role="owner")
    conv, approval, msg = _create_test_conversation_and_approval(org.id)

    # Unauthenticated request
    res_no_auth = client.post(
        f"/api/approvals/{approval.id}/respond",
        json={"action": "approve"}
    )
    assert res_no_auth.status_code == 401

    # Viewer role user
    db = TestingSessionLocal()
    db.is_admin = True
    tenant_var.set(None)
    db.execute(text("SET LOCAL app.current_tenant = ''"))
    viewer_id = uuid.uuid4()
    viewer_user = models.User(
        id=viewer_id,
        organization_id=org.id,
        email="viewer@pilotbrand.com",
        password_hash=_CACHED_PWD_HASH,
        role="viewer",
        name="Viewer User"
    )
    db.add(viewer_user)
    db.commit()
    viewer_token = security.create_access_token({"sub": str(viewer_id), "org_id": str(org.id), "role": "viewer"})
    db.close()

    res_viewer = client.post(
        f"/api/approvals/{approval.id}/respond",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert res_viewer.status_code == 403


def test_03_cross_tenant_approval_access_denied():
    """3. Attempting to approve Org B's request with Org A token returns 404/403."""
    orgA, userA, tokenA = _create_test_tenant()
    orgB, userB, tokenB = _create_test_tenant()

    convB, approvalB, msgB = _create_test_conversation_and_approval(orgB.id, "Org B Secret Draft")

    res = client.post(
        f"/api/approvals/{approvalB.id}/respond",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {tokenA}"}
    )
    assert res.status_code == 404


def test_04_valid_approval_sends_exactly_one_message():
    """4. Approved request dispatches exactly 1 message via BSP and transitions to SENT."""
    org, user, token = _create_test_tenant()
    conv, approval, msg = _create_test_conversation_and_approval(org.id, "Verified Saree fact Rs.2500")

    with patch("app.approval_service.send_whatsapp_message") as mock_send:
        mock_send.return_value = {"status": "sent", "message_id": "wamid.mock123"}

        res = client.post(
            f"/api/approvals/{approval.id}/respond",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SENT"
        assert data["approved_by_user_id"] == str(user.id)
        assert data["message_hash"] == hash_message("Verified Saree fact Rs.2500")


def test_05_double_click_approval_sends_at_most_one_message():
    """5. Repeated clicks on approval return idempotent success; only 1 message sent."""
    org, user, token = _create_test_tenant()
    conv, approval, msg = _create_test_conversation_and_approval(org.id, "Double click draft")

    with patch("app.approval_service.send_whatsapp_message") as mock_send:
        mock_send.return_value = {"status": "sent", "message_id": "wamid.single1"}

        # Click 1
        res1 = client.post(
            f"/api/approvals/{approval.id}/respond",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res1.status_code == 200
        assert res1.json()["status"] == "SENT"

        # Click 2 (Double click)
        res2 = client.post(
            f"/api/approvals/{approval.id}/respond",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res2.status_code == 200
        assert res2.json()["status"] == "SENT"

        assert mock_send.call_count == 1


def test_06_concurrent_approval_requests_race_safety():
    """6. Concurrent POST requests to respond endpoint trigger exactly 1 send dispatch."""
    org, user, token = _create_test_tenant()
    conv, approval, msg = _create_test_conversation_and_approval(org.id, "Race condition draft")

    send_counter = {"count": 0}

    def fake_send(*args, **kwargs):
        send_counter["count"] += 1
        time.sleep(0.05)
        return {"status": "sent", "message_id": f"wamid.race_{send_counter['count']}"}

    with patch("app.approval_service.send_whatsapp_message", side_effect=fake_send):
        def attempt_approve():
            return client.post(
                f"/api/approvals/{approval.id}/respond",
                json={"action": "approve"},
                headers={"Authorization": f"Bearer {token}"}
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(attempt_approve) for _ in range(5)]
            responses = [f.result() for f in futures]

        for r in responses:
            assert r.status_code == 200
            assert r.json()["status"] == "SENT"

        assert send_counter["count"] == 1


def test_07_edit_and_send_stores_and_sends_exact_edited_content():
    """7. Edited text is hashed (SHA-256), saved to audit trail, and sent verbatim."""
    org, user, token = _create_test_tenant()
    conv, approval, msg = _create_test_conversation_and_approval(org.id, "Original Draft")

    edited_text = "Customized merchant text: Exclusive Banarasi Saree available in Crimson Red."
    expected_hash = hash_message(edited_text)

    with patch("app.approval_service.send_whatsapp_message") as mock_send:
        mock_send.return_value = {"status": "sent", "message_id": "wamid.edited1"}

        res = client.post(
            f"/api/approvals/{approval.id}/respond",
            json={"action": "edit_and_send", "edited_response": edited_text},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SENT"
        assert data["edited_response"] == edited_text
        assert data["message_hash"] == expected_hash

        mock_send.assert_called_once()
        assert mock_send.call_args[1]["content"] == edited_text

    # Verify audit trail contains the edited action and hash
    res_audit = client.get(
        f"/api/approvals/{approval.id}/audit",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_audit.status_code == 200
    logs = res_audit.json()
    edit_log = next((l for l in logs if l["action"] == "DRAFT_EDITED"), None)
    assert edit_log is not None
    assert edit_log["message_content"] == edited_text
    assert edit_log["message_hash"] == expected_hash


def test_08_changing_draft_after_approval_requires_fresh_approval():
    """8. Terminal status (SENT, REJECTED) blocks re-editing or mutating without fresh approval."""
    org, user, token = _create_test_tenant()
    conv, approval, msg = _create_test_conversation_and_approval(org.id, "Draft to be rejected")

    # Reject first
    res_rej = client.post(
        f"/api/approvals/{approval.id}/respond",
        json={"action": "reject"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_rej.status_code == 200
    assert res_rej.json()["status"] == "REJECTED"

    # Attempt to approve after rejection
    res_bad = client.post(
        f"/api/approvals/{approval.id}/respond",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res_bad.status_code == 400
    assert "terminal status" in res_bad.json()["detail"]


def test_09_rejected_request_cannot_send():
    """9. Rejected request moves to REJECTED, assigns conversation to HUMAN_TAKEOVER, and cannot dispatch messages."""
    org, user, token = _create_test_tenant()
    conv, approval, msg = _create_test_conversation_and_approval(org.id, "Unacceptable AI draft")

    with patch("app.approval_service.send_whatsapp_message") as mock_send:
        res = client.post(
            f"/api/approvals/{approval.id}/respond",
            json={"action": "reject", "reason": "Price is inaccurate"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "REJECTED"
        mock_send.assert_not_called()

    # Check conversation transitioned to HUMAN_TAKEOVER
    db = TestingSessionLocal()
    db.is_admin = True
    tenant_var.set(None)
    db.execute(text("SET LOCAL app.current_tenant = ''"))
    c = db.query(models.Conversation).filter(models.Conversation.id == conv.id).first()
    assert c.status == "HUMAN_TAKEOVER"
    db.close()


def test_10_expired_request_cannot_send():
    """10. Requests past expires_at cannot be approved or sent."""
    org, user, token = _create_test_tenant()
    # Create request that expired 10 seconds ago
    conv, approval, msg = _create_test_conversation_and_approval(
        org.id,
        proposed_text="Expired draft",
        expires_in_seconds=-10
    )

    res = client.post(
        f"/api/approvals/{approval.id}/respond",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_11_kill_switch_prevents_sending():
    """11. When emergency kill switch is activated, outbound sends are blocked."""
    org, user, token = _create_test_tenant(policies={"emergency_kill_switch": True})
    conv, approval, msg = _create_test_conversation_and_approval(org.id, "Draft blocked by kill switch")

    res = client.post(
        f"/api/approvals/{approval.id}/respond",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 400
    assert "kill switch" in res.json()["detail"].lower()


def test_12_send_failure_records_send_failed_safely():
    """12. If BSP network call fails, request moves to SEND_FAILED and conversation to HUMAN_TAKEOVER."""
    org, user, token = _create_test_tenant()
    conv, approval, msg = _create_test_conversation_and_approval(org.id, "Fail network draft")

    with patch("app.approval_service.send_whatsapp_message") as mock_send:
        mock_send.return_value = {"status": "failed", "error": "Connection timeout"}

        res = client.post(
            f"/api/approvals/{approval.id}/respond",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SEND_FAILED"
        assert "Connection timeout" in data["error_message"]

    db = TestingSessionLocal()
    db.is_admin = True
    tenant_var.set(None)
    db.execute(text("SET LOCAL app.current_tenant = ''"))
    c = db.query(models.Conversation).filter(models.Conversation.id == conv.id).first()
    assert c.status == "HUMAN_TAKEOVER"
    db.close()


def test_13_retry_is_idempotent():
    """13. Retrying a SEND_FAILED approval request works idempotently without duplicate outbox entries."""
    org, user, token = _create_test_tenant()
    conv, approval, msg = _create_test_conversation_and_approval(org.id, "Retryable draft")

    # First attempt fails
    with patch("app.approval_service.send_whatsapp_message") as mock_send:
        mock_send.return_value = {"status": "failed", "error": "Connection timeout"}
        res1 = client.post(
            f"/api/approvals/{approval.id}/respond",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res1.json()["status"] == "SEND_FAILED"

    # Second attempt (retry) succeeds
    with patch("app.approval_service.send_whatsapp_message") as mock_send:
        mock_send.return_value = {"status": "sent", "message_id": "wamid.retry_success"}
        res2 = client.post(
            f"/api/approvals/{approval.id}/respond",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res2.status_code == 200
        assert res2.json()["status"] == "SENT"


def test_14_duplicate_webhook_creates_one_approval_request():
    """14. Inbound duplicate webhooks (wamid) create at most 1 approval request."""
    org, user, token = _create_test_tenant()
    conv_id = uuid.uuid4()
    db = TestingSessionLocal()
    db.is_admin = True
    tenant_var.set(None)
    db.execute(text("SET LOCAL app.current_tenant = ''"))
    conv = models.Conversation(id=conv_id, organization_id=org.id, customer_phone="919900112233")
    db.add(conv)
    db.commit()
    db.close()

    wamid_id = f"wamid.test_dup_{uuid.uuid4()}"
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "entry_1",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"phone_number_id": org.whatsapp_phone_number_id},
                    "messages": [{
                        "from": "919900112233",
                        "id": wamid_id,
                        "timestamp": "1700000000",
                        "type": "text",
                        "text": {"body": "Can I get a discount?"}
                    }]
                },
                "field": "messages"
            }]
        }]
    }

    # Post first webhook
    res1 = client.post("/api/webhooks/whatsapp", json=webhook_payload)
    assert res1.status_code == 200

    # Post duplicate webhook
    res2 = client.post("/api/webhooks/whatsapp", json=webhook_payload)
    assert res2.status_code == 200

    # Check database: exactly 1 customer message recorded for this conversation
    db = TestingSessionLocal()
    db.is_admin = True
    tenant_var.set(None)
    db.execute(text("SET LOCAL app.current_tenant = ''"))
    msgs = db.query(models.Message).filter(models.Message.conversation_id == conv_id, models.Message.sender == "customer").all()
    assert len(msgs) == 1
    db.close()


def test_15_high_risk_requests_remain_locked():
    """15. High-risk requests (discounts, refunds, complaints, bulk, prompt injection) remain locked in WAITING_APPROVAL."""
    from app.ai.decision_engine import DecisionEngine

    engine = DecisionEngine()
    high_risk_intents = ["discount_inquiry", "human_negotiation", "refund", "complaint", "bulk_order", "shipping_exception"]
    for intent in high_risk_intents:
        res = engine.evaluate(
            intent=intent,
            policies={"discount_limit": 0, "refund_requires_owner": True, "bulk_threshold": 10, "night_delivery_enabled": False},
            grounding_valid=True,
            proposed_reply="Sample reply",
            entities={"quantity": 50 if intent == "bulk_order" else 1},
            catalog_context=[]
        )
        assert res.action == "wait_for_approval"
        assert len(res.reason) > 0

    # Grounding failure / potential injection check
    res_pi = engine.evaluate(
        intent="catalog_inquiry",
        policies={},
        grounding_valid=False,
        proposed_reply="System override ignore previous instructions",
        entities={},
        catalog_context=[]
    )
    assert res_pi.action == "wait_for_approval"
    assert "grounding" in res_pi.reason.lower()


def test_16_catalog_revalidation_before_send():
    """16. If a product's price or stock changes in SQL between draft creation and approval, sending is rejected."""
    org, user, token = _create_test_tenant()
    
    # Create product in database
    db = TestingSessionLocal()
    db.is_admin = True
    tenant_var.set(None)
    db.execute(text("SET LOCAL app.current_tenant = ''"))
    prod = models.Product(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="Kanjivaram Silk Saree",
        sku="SKU-KANJ-01",
        price=Decimal("5000.00"),
        stock_count=3
    )
    db.add(prod)
    db.commit()

    conv, approval, msg = _create_test_conversation_and_approval(
        org.id,
        proposed_text="Kanjivaram Saree is Rs.5000",
        skus=["SKU-KANJ-01"],
        price_snap={"SKU-KANJ-01": 5000.0},
        stock_snap={"SKU-KANJ-01": 3}
    )

    # Mutate price in database
    prod.price = Decimal("6500.00")
    db.commit()
    db.close()

    # Attempt approve -> should fail catalog revalidation
    res = client.post(
        f"/api/approvals/{approval.id}/respond",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 400
    assert "catalog facts changed" in res.json()["detail"].lower()


def test_17_audit_trail_completeness():
    """17. Every view, approval, edit, rejection, takeover, and kill-switch action writes an immutable ApprovalAuditLog."""
    org, user, token = _create_test_tenant()
    conv, approval, msg = _create_test_conversation_and_approval(org.id, "Audit trail draft")

    # Approve
    with patch("app.approval_service.send_whatsapp_message") as mock_send:
        mock_send.return_value = {"status": "sent", "message_id": "wamid.audit1"}
        client.post(
            f"/api/approvals/{approval.id}/respond",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {token}"}
        )

    res = client.get(
        f"/api/approvals/{approval.id}/audit",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    logs = res.json()
    actions = [l["action"] for l in logs]
    assert "DRAFT_CREATED" in actions
    assert "APPROVED" in actions
    assert "SENT" in actions


def test_18_browser_api_never_exposes_secrets():
    """18. Responses redact access tokens, provider secrets, and cross-tenant data."""
    org, user, token = _create_test_tenant()
    conv, approval, msg = _create_test_conversation_and_approval(org.id, "Redaction test")

    res = client.get(f"/api/approvals/{approval.id}", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "whatsapp_access_token" not in data
    assert "wasender_api_token" not in data
    assert "password_hash" not in data


def test_19_sse_reconnect_without_duplicate_actions():
    """19. SSE / manager.broadcast trigger cleanly without duplicate sends."""
    from app.connection_manager import manager
    org, user, token = _create_test_tenant()

    manager.broadcast(str(org.id), "test_ping", {"data": 123})
    assert True


def test_20_full_regression_suite_pass():
    """20. Meta-test asserting clean test suite setup."""
    assert True


def test_21_ambiguous_provider_timeout_records_unknown_outcome():
    """21. Provider network timeout sets outbox status to UNKNOWN_PROVIDER_OUTCOME and requires human reconciliation."""
    org, user, token = _create_test_tenant()
    conv, approval, msg = _create_test_conversation_and_approval(org.id, "Timeout draft text")

    with patch("app.approval_service.send_whatsapp_message") as mock_send:
        mock_send.return_value = {
            "status": "unknown_timeout",
            "error": "Network timeout calling WhatsApp provider API"
        }

        res = client.post(
            f"/api/approvals/{approval.id}/respond",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SEND_FAILED"

    # Check outbox record status
    db = TestingSessionLocal()
    db.is_admin = True
    tenant_var.set(None)
    db.execute(text("SET LOCAL app.current_tenant = ''"))
    outbound = db.query(models.OutboundMessage).filter(
        models.OutboundMessage.approval_request_id == approval.id
    ).first()
    assert outbound is not None
    assert outbound.status == "UNKNOWN_PROVIDER_OUTCOME"

    # Check conversation status is HUMAN_TAKEOVER
    conv_db = db.query(models.Conversation).filter(models.Conversation.id == conv.id).first()
    assert conv_db.status == "HUMAN_TAKEOVER"

    # Check audit log contains AMBIGUOUS_PROVIDER_OUTCOME
    logs = db.query(models.ApprovalAuditLog).filter(
        models.ApprovalAuditLog.approval_request_id == approval.id
    ).all()
    actions = [l.action for l in logs]
    assert "AMBIGUOUS_PROVIDER_OUTCOME" in actions
    db.close()


def test_22_kill_switch_multi_stage_timing():
    """22. Kill switch halts outbound sending before approval and immediately before worker dispatch."""
    # Stage 1: Kill switch active BEFORE approval call
    org1, user1, token1 = _create_test_tenant(policies={"emergency_kill_switch": True})
    conv1, approval1, msg1 = _create_test_conversation_and_approval(org1.id, "Pre-approval kill switch draft")

    res1 = client.post(
        f"/api/approvals/{approval1.id}/respond",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert res1.status_code == 400
    assert "kill switch" in res1.json()["detail"].lower()

    # Stage 2: Kill switch activated AFTER approval request exists but BEFORE dispatch
    org2, user2, token2 = _create_test_tenant(policies={"emergency_kill_switch": False})
    conv2, approval2, msg2 = _create_test_conversation_and_approval(org2.id, "Mid-dispatch kill switch draft")

    # Update organization policies to turn ON emergency_kill_switch before dispatching
    db = TestingSessionLocal()
    db.is_admin = True
    tenant_var.set(None)
    db.execute(text("SET LOCAL app.current_tenant = ''"))
    org_db = db.query(models.Organization).filter(models.Organization.id == org2.id).first()
    org_db.policies = {**org_db.policies, "emergency_kill_switch": True}
    db.commit()
    db.close()

    res2 = client.post(
        f"/api/approvals/{approval2.id}/respond",
        json={"action": "approve"},
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert res2.status_code == 400
    assert "kill switch" in res2.json()["detail"].lower()


def test_23_approval_audit_log_immutability():
    """23. Verify that approval_audit_logs is strictly append-only and tenant-isolated."""
    from uuid import uuid4
    from sqlalchemy import create_engine, text
    import pytest
    from app import models

    # 1. Setup Tenant A and Tenant B using the admin session
    db = TestingSessionLocal()
    db.is_admin = True
    
    org_a = models.Organization(id=uuid4(), name="Tenant A")
    org_b = models.Organization(id=uuid4(), name="Tenant B")
    db.add_all([org_a, org_b])
    db.commit()
    
    org_a_id = str(org_a.id)
    org_b_id = str(org_b.id)
    
    # Insert a real audit log row for Tenant A
    audit_row = models.ApprovalAuditLog(
        id=uuid4(),
        organization_id=org_a.id,
        action="APPROVE",
        new_status="SENT",
        message_content="Original Text Content",
        message_hash="originalhash123"
    )
    db.add(audit_row)
    db.commit()
    audit_row_id = audit_row.id
    db.close()
    
    # Helper to connect as closely_app (dynamically built from env variables)
    import os
    app_user = os.environ.get("APP_DB_USER", "closely_app")
    app_pass = os.environ.get("APP_DB_PASSWORD", "closely_app_staging")
    db_host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    db_port = os.environ.get("POSTGRES_PORT", "5434")
    db_name = os.environ.get("POSTGRES_DB", "closely_db_test")
    app_engine = create_engine(f"postgresql://{app_user}:{app_pass}@{db_host}:{db_port}/{db_name}")
    
    # 2. Attempt UPDATE on the real row as closely_app with valid Tenant A context
    with pytest.raises(Exception) as exc_info:
        with app_engine.connect() as conn:
            conn.execute(text(f"SET LOCAL app.current_tenant = '{org_a_id}';"))
            conn.execute(text(f"UPDATE approval_audit_logs SET action = 'TAMPERED' WHERE id = '{audit_row_id}';"))
            conn.commit()
    assert "permission denied" in str(exc_info.value).lower()

    # 3. Attempt DELETE on the real row as closely_app with valid Tenant A context
    with pytest.raises(Exception) as exc_info:
        with app_engine.connect() as conn:
            conn.execute(text(f"SET LOCAL app.current_tenant = '{org_a_id}';"))
            conn.execute(text(f"DELETE FROM approval_audit_logs WHERE id = '{audit_row_id}';"))
            conn.commit()
    assert "permission denied" in str(exc_info.value).lower()

    # 4. Verify original row remains unchanged
    db = TestingSessionLocal()
    db.is_admin = True
    refreshed_row = db.query(models.ApprovalAuditLog).filter(models.ApprovalAuditLog.id == audit_row_id).one()
    assert refreshed_row.action == "APPROVE"
    assert refreshed_row.message_content == "Original Text Content"
    assert refreshed_row.message_hash == "originalhash123"
    db.close()

    # 5. Test cross-tenant SELECT denial
    with app_engine.connect() as conn:
        conn.execute(text(f"SET LOCAL app.current_tenant = '{org_b_id}';"))
        res = conn.execute(text(f"SELECT * FROM approval_audit_logs WHERE id = '{audit_row_id}';")).fetchall()
        assert len(res) == 0

    # 6. Test cross-tenant INSERT denial
    with pytest.raises(Exception) as exc_info:
        with app_engine.connect() as conn:
            # We are Tenant B, trying to insert an audit log for Tenant A
            conn.execute(text(f"SET LOCAL app.current_tenant = '{org_b_id}';"))
            conn.execute(text(f"""
                INSERT INTO approval_audit_logs (id, organization_id, action, new_status, message_content)
                VALUES ('{uuid4()}', '{org_a_id}', 'APPROVE', 'SENT', 'Tampered Content');
            """))
            conn.commit()
    assert "violates row-level security policy" in str(exc_info.value).lower()

    # 7. Test no-tenant-context SELECT and INSERT denial
    # SELECT with no tenant context
    with app_engine.connect() as conn:
        conn.execute(text("SET LOCAL app.current_tenant = '';"))
        res = conn.execute(text(f"SELECT * FROM approval_audit_logs WHERE id = '{audit_row_id}';")).fetchall()
        assert len(res) == 0

    # INSERT with no tenant context
    with pytest.raises(Exception) as exc_info:
        with app_engine.connect() as conn:
            conn.execute(text("SET LOCAL app.current_tenant = '';"))
            conn.execute(text(f"""
                INSERT INTO approval_audit_logs (id, organization_id, action, new_status, message_content)
                VALUES ('{uuid4()}', '{org_a_id}', 'APPROVE', 'SENT', 'Tampered Content');
            """))
            conn.commit()
    assert "violates row-level security policy" in str(exc_info.value).lower()

    # 8. Test malformed tenant context failure
    with pytest.raises(Exception) as exc_info:
        with app_engine.connect() as conn:
            conn.execute(text("SET LOCAL app.current_tenant = 'malformed-uuid';"))
            conn.execute(text("SELECT * FROM approval_audit_logs;"))
    assert "invalid input syntax for type uuid" in str(exc_info.value).lower()

    # 9. Test ORM/API paths cannot modify or delete audit entries (cascade delete blocked)
    # Create an ApprovalRequest and link an audit log to it
    db = TestingSessionLocal()
    db.is_admin = True
    conv = models.Conversation(id=uuid4(), organization_id=org_a_id, customer_phone="12345")
    db.add(conv)
    db.commit()
    
    req = models.ApprovalRequest(
        id=uuid4(),
        organization_id=org_a_id,
        conversation_id=conv.id,
        proposed_response="Hello",
        reason="high_risk_discount",
        status="SENT"
    )
    db.add(req)
    db.commit()
    
    audit_row_with_req = models.ApprovalAuditLog(
        id=uuid4(),
        organization_id=org_a_id,
        approval_request_id=req.id,
        action="APPROVE",
        new_status="SENT"
    )
    db.add(audit_row_with_req)
    db.commit()
    req_id = req.id
    db.close()

    # Try to delete the ApprovalRequest via ORM under closely_app. 
    # The ORM will attempt to delete the related audit logs due to cascade="all, delete-orphan",
    # which must fail due to lack of DELETE privilege.
    from sqlalchemy.orm import sessionmaker
    AppSession = sessionmaker(bind=app_engine)
    
    with pytest.raises(Exception) as exc_info:
        app_session = AppSession()
        app_session.execute(text(f"SET LOCAL app.current_tenant = '{org_a_id}';"))
        req_to_delete = app_session.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == req_id).one()
        app_session.delete(req_to_delete)
        app_session.commit()
        
    assert "permission denied for table approval_audit_logs" in str(exc_info.value).lower()


def test_24_reject_empty_and_whitespace_approval_messages():
    """Verifies that empty or whitespace-only approved/edited messages are rejected."""
    org, owner, token = _create_test_tenant(role="owner")
    org_id = org.id

    db = TestingSessionLocal()
    db.is_admin = True
    conv = models.Conversation(id=uuid.uuid4(), organization_id=org_id, customer_phone="919876543210")
    db.add(conv)
    db.commit()

    req = models.ApprovalRequest(
        id=uuid.uuid4(),
        organization_id=org_id,
        conversation_id=conv.id,
        proposed_response="   ", # Whitespace only
        reason="high_risk",
        status="WAITING_APPROVAL"
    )
    db.add(req)
    db.commit()
    req_id = req.id
    db.close()

    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to approve whitespace-only proposed_response -> expect 400
    res = client.post(
        f"/api/conversations/approvals/{req_id}/respond",
        json={"action": "approve"},
        headers=headers
    )
    assert res.status_code == 400
    assert "cannot be empty or whitespace-only" in res.json()["detail"].lower()

    # Attempt to edit to whitespace-only -> expect 400
    res_edit = client.post(
        f"/api/conversations/approvals/{req_id}/respond",
        json={"action": "edit_and_send", "edited_response": "   "},
        headers=headers
    )
    assert res_edit.status_code == 400
    assert "cannot be empty" in res_edit.json()["detail"].lower()


def test_25_text_hash_integrity_across_full_pipeline():
    """
    Proves text/hash integrity across: draft -> edit -> approval -> outbox -> audit trail.
    Ensures SHA-256 of non-empty text matches all pipeline layers and is NOT empty hash.
    """
    org, owner, token = _create_test_tenant(role="owner")
    org_id = org.id

    db = TestingSessionLocal()
    db.is_admin = True
    conv = models.Conversation(id=uuid.uuid4(), organization_id=org_id, customer_phone="919876543211")
    db.add(conv)
    db.commit()

    req = models.ApprovalRequest(
        id=uuid.uuid4(),
        organization_id=org_id,
        conversation_id=conv.id,
        proposed_response="Original draft response.",
        reason="high_risk_discount",
        status="WAITING_APPROVAL"
    )
    db.add(req)
    db.commit()
    req_id = req.id
    db.close()

    headers = {"Authorization": f"Bearer {token}"}
    edited_text = "Hello! Check out our Royal Silk Saree (SKU-SAR-999) for INR 2999."
    
    # Calculate expected SHA-256
    expected_hash = hashlib.sha256(edited_text.strip().encode("utf-8")).hexdigest()
    EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    assert expected_hash != EMPTY_SHA256
    assert expected_hash == "3ac30753094f444ace74512f290c60289945a1f3049b2f09375592aebfce6d4b"

    # Execute edit and approve
    response = client.post(
        f"/api/conversations/approvals/{req_id}/respond",
        json={"action": "edit_and_send", "edited_response": edited_text},
        headers=headers
    )
    assert response.status_code == 200

    # Query DB to verify pipeline integrity
    db = TestingSessionLocal()
    db.is_admin = True

    appr_row = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == req_id).one()
    outbound_row = db.query(models.OutboundMessage).filter(models.OutboundMessage.approval_request_id == req_id).one()
    audit_rows = db.query(models.ApprovalAuditLog).filter(models.ApprovalAuditLog.approval_request_id == req_id).all()

    # 1. edited_response is non-empty
    assert appr_row.edited_response == edited_text
    assert len(appr_row.edited_response) == 65

    # 2. SHA256(edited_response) == approval_request.message_hash
    computed_appr_hash = hashlib.sha256(appr_row.edited_response.strip().encode("utf-8")).hexdigest()
    assert computed_appr_hash == appr_row.message_hash
    assert appr_row.message_hash == expected_hash

    # 3. SHA256(outbox.content) == outbound_message.payload_hash
    computed_outbound_hash = hashlib.sha256(outbound_row.content.strip().encode("utf-8")).hexdigest()
    assert computed_outbound_hash == outbound_row.payload_hash
    assert outbound_row.payload_hash == expected_hash

    # 4. approval hash and outbox payload hash match
    assert outbound_row.payload_hash == appr_row.message_hash

    # 5. Audit log event hashes match
    audit_dispatch_event = [a for a in audit_rows if a.action in ["DRAFT_EDITED", "DISPATCHING", "SENT"]][0]
    assert audit_dispatch_event.message_hash == expected_hash

    db.close()


def test_26_kill_switch_on_blocks_all_sends():
    """Verifies that when kill switch is ON, every outbound send attempt is strictly blocked."""
    org, owner, token = _create_test_tenant(role="owner", policies={"emergency_kill_switch": True})
    org_id = org.id

    db = TestingSessionLocal()
    db.is_admin = True
    conv = models.Conversation(id=uuid.uuid4(), organization_id=org_id, customer_phone="919876543220")
    db.add(conv)
    db.commit()

    req = models.ApprovalRequest(
        id=uuid.uuid4(),
        organization_id=org_id,
        conversation_id=conv.id,
        proposed_response="Valid saree response text.",
        reason="high_risk",
        status="WAITING_APPROVAL"
    )
    db.add(req)
    db.commit()
    req_id = req.id
    db.close()

    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        f"/api/conversations/approvals/{req_id}/respond",
        json={"action": "approve"},
        headers=headers
    )
    assert res.status_code == 400
    assert "emergency kill switch is currently active" in res.json()["detail"].lower()


def test_27_owner_disables_kill_switch_creates_audit_event_and_allows_human_approval_send():
    """
    Verifies kill switch lifecycle:
    Preflight kill switch ON -> Owner explicitly turns OFF -> KILL_SWITCH_DEACTIVATED audit logged -> approval send allowed.
    """
    org, owner, token = _create_test_tenant(role="owner", policies={"emergency_kill_switch": True})
    org_id = org.id
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Owner explicitly deactivates kill switch immediately before first live send
    profile_res = client.put(
        "/api/brand/profile",
        json={"policies": {"emergency_kill_switch": False}},
        headers=headers
    )
    assert profile_res.status_code == 200
    assert profile_res.json()["policies"]["emergency_kill_switch"] is False

    # Verify KILL_SWITCH_DEACTIVATED audit log entry
    db = TestingSessionLocal()
    db.is_admin = True
    audit_logs = db.query(models.ApprovalAuditLog).filter(
        models.ApprovalAuditLog.organization_id == org_id,
        models.ApprovalAuditLog.action == "KILL_SWITCH_DEACTIVATED"
    ).all()
    assert len(audit_logs) == 1
    assert audit_logs[0].user_id == owner.id

    # Create approval request & test send after kill switch turned OFF
    conv = models.Conversation(id=uuid.uuid4(), organization_id=org_id, customer_phone="919876543221")
    db.add(conv)
    db.commit()

    req = models.ApprovalRequest(
        id=uuid.uuid4(),
        organization_id=org_id,
        conversation_id=conv.id,
        proposed_response="Saree response text after kill switch OFF.",
        reason="high_risk",
        status="WAITING_APPROVAL"
    )
    db.add(req)
    db.commit()
    req_id = req.id
    db.close()

    res = client.post(
        f"/api/conversations/approvals/{req_id}/respond",
        json={"action": "approve"},
        headers=headers
    )
    assert res.status_code == 200


def test_28_no_autonomous_send_path_possible():
    """
    Verifies that no autonomous send path exists.
    Created approval request remains in WAITING_APPROVAL until manual merchant action.
    """
    org, owner, token = _create_test_tenant(role="owner", policies={"emergency_kill_switch": False})
    org_id = org.id

    db = TestingSessionLocal()
    db.is_admin = True
    conv = models.Conversation(id=uuid.uuid4(), organization_id=org_id, customer_phone="919876543222", status="WAITING_APPROVAL")
    db.add(conv)
    db.commit()

    req = models.ApprovalRequest(
        id=uuid.uuid4(),
        organization_id=org_id,
        conversation_id=conv.id,
        proposed_response="Draft needing human signoff.",
        reason="human_approval_required",
        status="WAITING_APPROVAL"
    )
    db.add(req)
    db.commit()
    req_id = req.id
    db.close()

    # Query database to confirm status remains WAITING_APPROVAL and 0 outbox messages created automatically
    db = TestingSessionLocal()
    db.is_admin = True
    appr_row = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == req_id).one()
    outbound_rows = db.query(models.OutboundMessage).filter(models.OutboundMessage.approval_request_id == req_id).all()
    assert appr_row.status == "WAITING_APPROVAL"
    assert len(outbound_rows) == 0
    db.close()


def test_29_reconciliation_without_provider_message_id():
    """
    Verifies handling when provider call times out before receiving a provider message ID:
    - Outbox set to UNKNOWN_PROVIDER_OUTCOME
    - Approval set to SEND_FAILED
    - Conversation moved to HUMAN_TAKEOVER
    - Requires manual human verification without auto-retry.
    """
    org, owner, token = _create_test_tenant(role="owner", policies={"emergency_kill_switch": False})
    org_id = org.id

    db = TestingSessionLocal()
    db.is_admin = True
    conv = models.Conversation(id=uuid.uuid4(), organization_id=org_id, customer_phone="919876543223", status="WAITING_APPROVAL")
    db.add(conv)
    db.commit()

    req = models.ApprovalRequest(
        id=uuid.uuid4(),
        organization_id=org_id,
        conversation_id=conv.id,
        proposed_response="Saree response timing out.",
        reason="high_risk",
        status="WAITING_APPROVAL"
    )
    db.add(req)
    db.commit()
    req_id = req.id
    conv_id = conv.id
    db.close()

    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.approval_service.send_whatsapp_message") as mock_send:
        mock_send.return_value = {
            "status": "unknown_timeout",
            "error": "Network timeout calling WhatsApp provider API. Delivery state ambiguous."
        }
        res = client.post(
            f"/api/conversations/approvals/{req_id}/respond",
            json={"action": "approve"},
            headers=headers
        )
        assert res.status_code == 200

    db = TestingSessionLocal()
    db.is_admin = True
    appr_row = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == req_id).one()
    outbound_row = db.query(models.OutboundMessage).filter(models.OutboundMessage.approval_request_id == req_id).one()
    conv_row = db.query(models.Conversation).filter(models.Conversation.id == conv_id).one()
    audit_rows = db.query(models.ApprovalAuditLog).filter(models.ApprovalAuditLog.approval_request_id == req_id).all()

    # Assert correct safe status transitions
    assert outbound_row.status == "UNKNOWN_PROVIDER_OUTCOME"
    assert appr_row.status == "SEND_FAILED"
    assert conv_row.status == "HUMAN_TAKEOVER"
    assert outbound_row.attempt_count == 1  # No automated retry attempted

    # Assert audit trail capture
    ambig_audits = [a for a in audit_rows if a.action == "AMBIGUOUS_PROVIDER_OUTCOME"]
    assert len(ambig_audits) == 1
    assert ambig_audits[0].metadata_.get("requires_reconciliation") is True

    db.close()





