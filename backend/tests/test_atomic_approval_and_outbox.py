import uuid
import hashlib
import httpx
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import text
from tests.conftest import app, TestingSessionLocal, clean_tables
from app import models, security, schemas
from app.database import tenant_var
from app.approval_service import approve_draft_atomic, hash_message
from app.outbox_dispatcher import dispatch_outbound_message

client = TestClient(app)
_CACHED_PWD_HASH = security.get_password_hash("Secret123!")


@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield


from types import SimpleNamespace

def _create_test_tenant(role="owner", policies=None):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    whatsapp_no = "+919876543210"
    org_name = "Kanchipuram Silk Palace"
    user_email = f"owner_{uuid.uuid4().hex[:6]}@kanchi.com"

    default_policies = {
        "operating_mode": "HUMAN_APPROVAL",
        "shadow_mode": False,
        "emergency_kill_switch": False
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
        whatsapp_phone_number_id="phone_id_kanchi",
        whatsapp_access_token=security.encrypt_token("valid_test_token"),
        policies=default_policies
    )
    db.add(org)

    user = models.User(
        id=user_id,
        organization_id=org_id,
        email=user_email,
        password_hash=_CACHED_PWD_HASH,
        role=role,
        name="Kanchi Owner"
    )
    db.add(user)
    db.commit()
    db.close()

    token = security.create_access_token({"sub": str(user_id), "org_id": str(org_id), "role": role})
    org_ns = SimpleNamespace(id=org_id, name=org_name, whatsapp_number=whatsapp_no, policies=default_policies)
    user_ns = SimpleNamespace(id=user_id, organization_id=org_id, email=user_email, role=role)
    return org_ns, user_ns, token


def _create_catalog_and_draft(org_id, initial_price=3500.0, initial_stock=5):
    db = TestingSessionLocal()
    db.is_admin = True
    tenant_var.set(None)
    db.execute(text("SET LOCAL app.current_tenant = ''"))

    prod_id = uuid.uuid4()
    conv_id = uuid.uuid4()
    msg_id = uuid.uuid4()
    approval_id = uuid.uuid4()

    # Create Product
    prod = models.Product(
        id=prod_id,
        organization_id=org_id,
        sku="SKU-KANJI-01",
        name="Crimson Pure Zari Silk Saree",
        price=initial_price,
        stock_count=initial_stock,
        color="Crimson",
        fabric="Silk"
    )
    db.add(prod)

    # Create Conversation
    conv = models.Conversation(
        id=conv_id,
        organization_id=org_id,
        customer_phone="+919876500000",
        customer_name="Priya Raman",
        status="WAITING_APPROVAL"
    )
    db.add(conv)

    # Create Pending Draft Message
    proposed_text = "Namaste Priya! Crimson Pure Zari Silk Saree (SKU-KANJI-01) is available for Rs.3,500."
    msg = models.Message(
        id=msg_id,
        conversation_id=conv.id,
        sender="ai",
        message_type="text",
        content=proposed_text,
        status="pending"
    )
    db.add(msg)

    # Create ApprovalRequest
    approval = models.ApprovalRequest(
        id=approval_id,
        organization_id=org_id,
        conversation_id=conv.id,
        status="WAITING_APPROVAL",
        reason="Grounded Product Catalog Inquiry",
        proposed_response=proposed_text,
        version=1,
        retrieval_ids=["SKU-KANJI-01"],
        price_snapshot={"SKU-KANJI-01": initial_price},
        stock_snapshot={"SKU-KANJI-01": initial_stock},
        grounding_score=1.0
    )
    db.add(approval)
    db.commit()
    db.close()

    prod_ns = SimpleNamespace(id=prod_id, sku="SKU-KANJI-01", price=initial_price, stock_count=initial_stock)
    conv_ns = SimpleNamespace(id=conv_id, customer_phone="+919876500000", status="WAITING_APPROVAL")
    approval_ns = SimpleNamespace(id=approval_id, proposed_response=proposed_text, status="WAITING_APPROVAL")
    return prod_ns, conv_ns, approval_ns



# ============================================================================
# 1. ATOMIC APPROVAL UNIT & INTEGRATION TESTS
# ============================================================================

def test_atomic_approval_success_creates_outbox_pending():
    """Verify approve_draft_atomic transitions status, hashes text, and creates PENDING OutboundMessage."""
    org, user, _ = _create_test_tenant()
    _, conv, approval = _create_catalog_and_draft(org.id)

    db = TestingSessionLocal()
    try:
        appr, outbox = approve_draft_atomic(
            db=db,
            tenant_id=org.id,
            approval_id=approval.id,
            user_id=user.id,
            reason="Approved by merchant"
        )

        # 1. Verify Approval State
        assert appr.status == "APPROVED"
        assert appr.approved_by_user_id == user.id
        assert appr.version == 2
        expected_hash = hashlib.sha256(approval.proposed_response.strip().encode("utf-8")).hexdigest()
        assert appr.message_hash == expected_hash

        # 2. Verify Outbound Message in PENDING
        assert outbox is not None
        assert outbox.status == "PENDING"
        assert outbox.message_version == 2
        assert outbox.provider_idempotency_key == f"outbox_{approval.id}_v2"
        assert outbox.payload_hash == expected_hash
        assert outbox.recipient_phone == conv.customer_phone
        assert outbox.content == approval.proposed_response

        # 3. Verify Immutable Audit Log
        audit = db.query(models.ApprovalAuditLog).filter(
            models.ApprovalAuditLog.approval_request_id == approval.id,
            models.ApprovalAuditLog.action == "APPROVED"
        ).first()
        assert audit is not None
        assert audit.revalidation_passed is True
        assert audit.message_hash == expected_hash
        assert audit.new_status == "APPROVED"
    finally:
        db.close()


def test_atomic_approval_with_merchant_edit():
    """Verify approving with merchant edited text computes updated SHA-256 and records DRAFT_EDITED."""
    org, user, _ = _create_test_tenant()
    _, conv, approval = _create_catalog_and_draft(org.id)

    edited_text = "Namaste Priya! Crimson Silk Saree is Rs.3,500. We can also provide free matching fall/pico!"
    expected_hash = hashlib.sha256(edited_text.strip().encode("utf-8")).hexdigest()

    db = TestingSessionLocal()
    try:
        appr, outbox = approve_draft_atomic(
            db=db,
            tenant_id=org.id,
            approval_id=approval.id,
            merchant_edited_text=edited_text,
            user_id=user.id
        )

        assert appr.status == "APPROVED"
        assert appr.edited_by_user_id == user.id
        assert appr.edited_response == edited_text
        assert appr.message_hash == expected_hash

        assert outbox.content == edited_text
        assert outbox.payload_hash == expected_hash

        audit = db.query(models.ApprovalAuditLog).filter(
            models.ApprovalAuditLog.approval_request_id == approval.id,
            models.ApprovalAuditLog.action == "DRAFT_EDITED"
        ).first()
        assert audit is not None
        assert audit.revalidation_passed is True
        assert audit.message_content == edited_text
    finally:
        db.close()


def test_catalog_drift_revalidation_failure_price_change():
    """Verify live catalog price drift blocks approval with 409 Conflict."""
    from fastapi import HTTPException
    org, user, _ = _create_test_tenant()
    prod, _, approval = _create_catalog_and_draft(org.id, initial_price=3500.0, initial_stock=5)

    # Merchant updates live price in DB to Rs. 4000
    db = TestingSessionLocal()
    db.is_admin = True
    tenant_var.set(None)
    db.execute(text("SET LOCAL app.current_tenant = ''"))
    db.query(models.Product).filter(models.Product.id == prod.id).update({"price": 4000.0})
    db.commit()

    # Attempting to approve must fail with 409 Conflict
    with pytest.raises(HTTPException) as exc_info:
        approve_draft_atomic(
            db=db,
            tenant_id=org.id,
            approval_id=approval.id,
            user_id=user.id
        )

    assert exc_info.value.status_code == 409
    assert "Price changed" in exc_info.value.detail

    # Verify audit log was recorded with revalidation_passed = False
    audit = db.query(models.ApprovalAuditLog).filter(
        models.ApprovalAuditLog.approval_request_id == approval.id,
        models.ApprovalAuditLog.action == "REVALIDATION_FAILED"
    ).first()
    assert audit is not None
    assert audit.revalidation_passed is False

    # Approval request must remain WAITING_APPROVAL
    approval_row = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == approval.id).first()
    assert approval_row.status == "WAITING_APPROVAL"
    db.close()


def test_catalog_drift_revalidation_failure_stock_depleted():
    """Verify out-of-stock drift blocks approval with 409 Conflict."""
    from fastapi import HTTPException
    org, user, _ = _create_test_tenant()
    prod, _, approval = _create_catalog_and_draft(org.id, initial_price=3500.0, initial_stock=5)

    # Stock sells out in store
    db = TestingSessionLocal()
    db.is_admin = True
    tenant_var.set(None)
    db.execute(text("SET LOCAL app.current_tenant = ''"))
    db.query(models.Product).filter(models.Product.id == prod.id).update({"stock_count": 0})
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        approve_draft_atomic(
            db=db,
            tenant_id=org.id,
            approval_id=approval.id,
            user_id=user.id
        )

    assert exc_info.value.status_code == 409
    assert "out of stock" in exc_info.value.detail.lower()
    db.close()


def test_kill_switch_blocks_atomic_approval():
    """Verify active emergency kill switch rejects approval and records BLOCKED_BY_KILL_SWITCH."""
    from fastapi import HTTPException
    org, user, _ = _create_test_tenant(policies={"emergency_kill_switch": True})
    _, _, approval = _create_catalog_and_draft(org.id)

    db = TestingSessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            approve_draft_atomic(
                db=db,
                tenant_id=org.id,
                approval_id=approval.id,
                user_id=user.id
            )

        assert exc_info.value.status_code == 400
        assert "kill switch" in exc_info.value.detail.lower()

        audit = db.query(models.ApprovalAuditLog).filter(
            models.ApprovalAuditLog.approval_request_id == approval.id,
            models.ApprovalAuditLog.action == "BLOCKED_BY_KILL_SWITCH"
        ).first()
        assert audit is not None
    finally:
        db.close()


# ============================================================================
# 2. TRANSACTIONAL OUTBOX DISPATCHER TESTS
# ============================================================================

def test_outbox_dispatcher_success():
    """Verify outbox worker posts to Meta API, updates status to SENT, and sets sent_at timestamp."""
    org, user, _ = _create_test_tenant()
    _, conv, approval = _create_catalog_and_draft(org.id)

    db = TestingSessionLocal()
    try:
        _, outbox = approve_draft_atomic(
            db=db,
            tenant_id=org.id,
            approval_id=approval.id,
            user_id=user.id
        )

        # Mock Meta API 200 Response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"messages": [{"id": "wamid.HBgLMTIzNDU2Nzg5MA=="}]}

        with patch("httpx.Client.post", return_value=mock_resp):
            res = dispatch_outbound_message(db=db, outbox_id=outbox.id)

        assert res["status"] == "sent"
        assert res["message_id"] == "wamid.HBgLMTIzNDU2Nzg5MA=="

        db.refresh(outbox)
        assert outbox.status == "SENT"
        assert outbox.provider_message_id == "wamid.HBgLMTIzNDU2Nzg5MA=="
        assert outbox.sent_at is not None

        approval_row = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == approval.id).first()
        assert approval_row.status == "SENT"
        assert approval_row.sent_at is not None
    finally:
        db.close()


def test_outbox_dispatcher_rejection_marks_failed():
    """Verify Meta Cloud API 400 error marks outbox as FAILED without throwing unhandled exceptions."""
    org, user, _ = _create_test_tenant()
    _, _, approval = _create_catalog_and_draft(org.id)

    db = TestingSessionLocal()
    try:
        _, outbox = approve_draft_atomic(
            db=db,
            tenant_id=org.id,
            approval_id=approval.id,
            user_id=user.id
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = '{"error": {"message": "Invalid recipient phone format", "code": 100}}'

        with patch("httpx.Client.post", return_value=mock_resp):
            res = dispatch_outbound_message(db=db, outbox_id=outbox.id)

        assert res["status"] == "failed"

        db.refresh(outbox)
        assert outbox.status == "FAILED"
        assert "Invalid recipient" in outbox.last_error

        approval_row = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == approval.id).first()
        assert approval_row.status == "SEND_FAILED"
    finally:
        db.close()


def test_outbox_dispatcher_timeout_unknown_provider_outcome():
    """Verify network timeout marks UNKNOWN_PROVIDER_OUTCOME and halts automatic retries to prevent double-messaging."""
    org, user, _ = _create_test_tenant()
    _, conv, approval = _create_catalog_and_draft(org.id)

    db = TestingSessionLocal()
    try:
        _, outbox = approve_draft_atomic(
            db=db,
            tenant_id=org.id,
            approval_id=approval.id,
            user_id=user.id
        )

        with patch("httpx.Client.post", side_effect=httpx.ReadTimeout("Meta API read timeout")):
            res = dispatch_outbound_message(db=db, outbox_id=outbox.id)

        assert res["status"] == "unknown_timeout"

        db.refresh(outbox)
        assert outbox.status == "UNKNOWN_PROVIDER_OUTCOME"
        assert "Timeout" in outbox.last_error

        approval_row = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == approval.id).first()
        assert approval_row.status == "SEND_FAILED"

        conv_row = db.query(models.Conversation).filter(models.Conversation.id == conv.id).first()
        assert conv_row.status == "HUMAN_TAKEOVER"
    finally:
        db.close()


def test_outbox_dispatcher_kill_switch_cancels():
    """Verify dispatcher halts and cancels pending message when emergency kill switch is active."""
    org, user, _ = _create_test_tenant()
    _, _, approval = _create_catalog_and_draft(org.id)

    db = TestingSessionLocal()
    try:
        _, outbox = approve_draft_atomic(
            db=db,
            tenant_id=org.id,
            approval_id=approval.id,
            user_id=user.id
        )

        # Activate kill switch before worker picks up outbox message
        db.query(models.Organization).filter(models.Organization.id == org.id).update({
            "policies": {"emergency_kill_switch": True}
        })
        db.commit()

        res = dispatch_outbound_message(db=db, outbox_id=outbox.id)
        assert res["status"] == "cancelled"

        db.refresh(outbox)
        assert outbox.status == "CANCELLED"

        approval_row = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == approval.id).first()
        assert approval_row.status == "CANCELLED"
    finally:
        db.close()


# ============================================================================
# 3. FASTAPI ROUTER ENDPOINTS (/api/approvals/{id}/approve & /api/inbox/{id}/approve)
# ============================================================================

def test_api_post_approvals_approve_endpoint():
    """Verify HTTP POST /api/approvals/{id}/approve executes atomic approval via REST API."""
    org, user, token = _create_test_tenant()
    _, _, approval = _create_catalog_and_draft(org.id)

    headers = {"Authorization": f"Bearer {token}"}
    resp = client.post(f"/api/approvals/{approval.id}/approve", json={}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(approval.id)
    assert data["status"] == "APPROVED"
    assert data["version"] == 2
    assert data["message_hash"] is not None


def test_api_post_inbox_approve_endpoint_alias():
    """Verify HTTP POST /api/inbox/{id}/approve alias executes atomic approval via REST API."""
    org, user, token = _create_test_tenant()
    _, _, approval = _create_catalog_and_draft(org.id)

    headers = {"Authorization": f"Bearer {token}"}
    edited_text = "Namaste! Special boutique discount applied: Rs.3,500 with express shipping."
    resp = client.post(
        f"/api/inbox/{approval.id}/approve",
        json={"edited_response": edited_text, "reason": "Boutique promotion"},
        headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(approval.id)
    assert data["status"] == "APPROVED"
    assert data["edited_response"] == edited_text
    assert data["version"] == 2
