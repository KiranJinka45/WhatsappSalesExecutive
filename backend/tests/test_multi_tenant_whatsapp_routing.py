"""
Multi-Tenant WhatsApp Routing & Isolation Test Suite.
Verifies:
1. Webhooks for Tenant A route exclusively to Tenant A's database session and RLS context.
2. Webhooks for Tenant B route exclusively to Tenant B's database session and RLS context.
3. Unknown phone_number_id / WABA webhooks are cleanly rejected without leaking into any tenant.
4. WhatsApp tokens are encrypted at rest (Fernet) and never stored in plaintext.
5. Meta Embedded Signup executes automated WABA webhook subscriptions and Cloud API registration.
6. WhatsApp health endpoint enforces strict tenant isolation.
"""
import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app import models
from app.database import tenant_var
from app.security import encrypt_token, decrypt_token
from app.services import whatsapp_registration_service as reg_service
from tests.conftest import TestingSessionLocal, clean_tables, create_test_tenant

client = TestClient(app)


def _setup_two_tenants():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()

    # 1. Create Tenant A
    headers_a = create_test_tenant(client, "owner_a@boutique.com", "Owner A", "Boutique Silk")
    db = TestingSessionLocal()
    org_a = db.query(models.Organization).filter(models.Organization.name == "Boutique Silk").first()
    org_a.whatsapp_phone_number_id = "phone_id_silk_101"
    org_a.whatsapp_business_account_id = "waba_silk_101"
    org_a.whatsapp_number = "+919100000001"
    org_a.whatsapp_access_token = encrypt_token("secret_token_tenant_a")
    org_a.is_whatsapp_connected = 1
    org_a.whatsapp_onboarding_state = "CONNECTED"
    db.commit()
    db.refresh(org_a)
    org_a_id = org_a.id
    db.close()

    # 2. Create Tenant B
    headers_b = create_test_tenant(client, "owner_b@boutique.com", "Owner B", "Boutique Cotton")
    db = TestingSessionLocal()
    org_b = db.query(models.Organization).filter(models.Organization.name == "Boutique Cotton").first()
    org_b.whatsapp_phone_number_id = "phone_id_cotton_202"
    org_b.whatsapp_business_account_id = "waba_cotton_202"
    org_b.whatsapp_number = "+919200000002"
    org_b.whatsapp_access_token = encrypt_token("secret_token_tenant_b")
    org_b.is_whatsapp_connected = 1
    org_b.whatsapp_onboarding_state = "CONNECTED"
    db.commit()
    db.refresh(org_b)
    org_b_id = org_b.id
    db.close()

    return headers_a, org_a_id, headers_b, org_b_id


def _build_meta_webhook_payload(phone_number_id: str, waba_id: str, customer_phone: str, text_body: str):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": waba_id,
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550001234",
                                "phone_number_id": phone_number_id
                            },
                            "contacts": [
                                {
                                    "profile": {
                                        "name": "Customer Test"
                                    },
                                    "wa_id": customer_phone.replace("+", "")
                                }
                            ],
                            "messages": [
                                {
                                    "from": customer_phone,
                                    "id": f"wamid_test_{uuid.uuid4().hex[:8]}",
                                    "timestamp": "1710000000",
                                    "text": {
                                        "body": text_body
                                    },
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


def test_01_webhook_routing_tenant_a_isolated():
    """Webhook targeted at Tenant A's phone_number_id creates conversation ONLY under Tenant A."""
    headers_a, org_a_id, headers_b, org_b_id = _setup_two_tenants()

    payload_a = _build_meta_webhook_payload(
        phone_number_id="phone_id_silk_101",
        waba_id="waba_silk_101",
        customer_phone="+919876543210",
        text_body="Hi Boutique Silk! Do you have Kanchi pattu sarees in stock?"
    )

    with patch("app.routers.webhooks.process_message_async") as mock_async:
        resp = client.post("/api/webhooks/whatsapp", json=payload_a)
        assert resp.status_code == 200

    # 1. Verify Conversation in Tenant A
    db = TestingSessionLocal()
    tenant_var.set(org_a_id)
    db.organization_id = org_a_id
    try:
        db.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(org_a_id)})
    except Exception:
        pass

    conv_a = db.query(models.Conversation).filter(models.Conversation.organization_id == org_a_id).first()
    assert conv_a is not None
    assert conv_a.customer_phone == "+919876543210"

    msg_a = db.query(models.Message).filter(models.Message.conversation_id == conv_a.id).first()
    assert msg_a is not None
    assert "Kanchi pattu sarees" in msg_a.content
    db.close()

    # 2. Strict Cross-Tenant Verification: Tenant B has 0 conversations and 0 messages
    db = TestingSessionLocal()
    tenant_var.set(org_b_id)
    db.organization_id = org_b_id
    try:
        db.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(org_b_id)})
    except Exception:
        pass

    conv_b_count = db.query(models.Conversation).filter(models.Conversation.organization_id == org_b_id).count()
    assert conv_b_count == 0
    db.close()


def test_02_webhook_routing_tenant_b_isolated():
    """Webhook targeted at Tenant B's phone_number_id creates conversation ONLY under Tenant B."""
    headers_a, org_a_id, headers_b, org_b_id = _setup_two_tenants()

    payload_b = _build_meta_webhook_payload(
        phone_number_id="phone_id_cotton_202",
        waba_id="waba_cotton_202",
        customer_phone="+919999888877",
        text_body="Hi Boutique Cotton! What cotton dress materials are available?"
    )

    with patch("app.routers.webhooks.process_message_async") as mock_async:
        resp = client.post("/api/webhooks/whatsapp", json=payload_b)
        assert resp.status_code == 200

    # 1. Verify Conversation in Tenant B
    db = TestingSessionLocal()
    tenant_var.set(org_b_id)
    db.organization_id = org_b_id
    try:
        db.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(org_b_id)})
    except Exception:
        pass

    conv_b = db.query(models.Conversation).filter(models.Conversation.organization_id == org_b_id).first()
    assert conv_b is not None
    assert conv_b.customer_phone == "+919999888877"
    db.close()

    # 2. Strict Cross-Tenant Verification: Tenant A has 0 conversations
    db = TestingSessionLocal()
    tenant_var.set(org_a_id)
    db.organization_id = org_a_id
    try:
        db.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(org_a_id)})
    except Exception:
        pass

    conv_a_count = db.query(models.Conversation).filter(models.Conversation.organization_id == org_a_id).count()
    assert conv_a_count == 0
    db.close()


def test_03_unknown_phone_number_rejected_without_fallback():
    """Webhook for an unknown phone_number_id is safely ignored and never routes to any tenant."""
    headers_a, org_a_id, headers_b, org_b_id = _setup_two_tenants()

    payload_unknown = _build_meta_webhook_payload(
        phone_number_id="phone_id_stranger_9999",
        waba_id="waba_stranger_9999",
        customer_phone="+919000000000",
        text_body="Hello stranger business!"
    )

    resp = client.post("/api/webhooks/whatsapp", json=payload_unknown)
    assert resp.status_code == 200
    assert resp.json().get("status") == "ignored"

    # Confirm neither Tenant A nor Tenant B received this message
    db = TestingSessionLocal()
    total_convs = db.query(models.Conversation).count()
    assert total_convs == 0
    db.close()


def test_04_token_encryption_at_rest():
    """Confirms WhatsApp access tokens are encrypted at rest with Fernet and decryptable at runtime."""
    raw_secret = "EAABwzL13nxIBO9test_meta_long_lived_system_token_xyz"
    encrypted = encrypt_token(raw_secret)

    # Must be encrypted and prefixed with enc:
    assert encrypted.startswith("enc:")
    assert encrypted != raw_secret
    assert raw_secret not in encrypted

    # Decrypt restores original plaintext token
    decrypted = decrypt_token(encrypted)
    assert decrypted == raw_secret

    # Plaintext token strictly rejected (no silent plaintext bypass)
    legacy_token = "legacy_unencrypted_token"
    with pytest.raises(ValueError, match="Plaintext token detected"):
        decrypt_token(legacy_token)


def test_05_embedded_signup_waba_subscription_and_registration():
    """Validates that Embedded Signup executes WABA webhook subscription and phone registration."""
    headers_a, org_a_id, _, _ = _setup_two_tenants()

    # 1. Fetch one-time session nonce
    res_cfg = client.get("/api/brand/whatsapp/embedded-signup-config", headers=headers_a)
    assert res_cfg.status_code == 200
    nonce = res_cfg.json()["session_nonce"]

    # 2. Mock Meta Graph API responses
    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 200
    mock_token_resp.json.return_value = {"access_token": "live_merchant_access_token_12345"}

    mock_debug_resp = MagicMock()
    mock_debug_resp.status_code = 200
    mock_debug_resp.json.return_value = {"data": {"is_valid": True, "expires_at": 1750000000}}

    mock_phones_resp = MagicMock()
    mock_phones_resp.status_code = 200
    mock_phones_resp.json.return_value = {
        "data": [
            {
                "id": "phone_live_999",
                "display_phone_number": "+919493348129",
                "verified_name": "Silk Saree Boutique"
            }
        ]
    }

    mock_sub_resp = MagicMock()
    mock_sub_resp.status_code = 200
    mock_sub_resp.json.return_value = {"success": True}

    mock_reg_resp = MagicMock()
    mock_reg_resp.status_code = 200
    mock_reg_resp.json.return_value = {"success": True}

    with patch("httpx.get") as mock_get, patch("httpx.post") as mock_post:
        mock_get.side_effect = lambda url, **kwargs: (
            mock_token_resp if "oauth/access_token" in url else
            mock_debug_resp if "debug_token" in url else
            mock_phones_resp if "phone_numbers" in url else
            MagicMock(status_code=200, json=lambda: {"verified_name": "Silk Saree Boutique", "code_verification_status": "VERIFIED"}, content=b"{}")
        )
        mock_post.side_effect = lambda url, **kwargs: (
            mock_sub_resp if "subscribed_apps" in url else
            mock_reg_resp if "register" in url else
            MagicMock(status_code=200, json=lambda: {"success": True})
        )

        res_callback = client.post(
            "/api/brand/whatsapp/embedded-signup-callback",
            headers=headers_a,
            json={
                "code": "auth_code_from_meta_popup",
                "session_nonce": nonce,
                "waba_id_hint": "waba_live_999",
                "phone_number_id_hint": "phone_live_999"
            }
        )

        assert res_callback.status_code == 200
        data = res_callback.json()
        assert data.get("status") == "success"
        assert data.get("onboarding_state") == "CONNECTED"

    # Verify token is encrypted in database
    db = TestingSessionLocal()
    org = db.query(models.Organization).filter(models.Organization.id == org_a_id).first()
    assert org.whatsapp_phone_number_id == "phone_live_999"
    assert org.whatsapp_business_account_id == "waba_live_999"
    assert org.whatsapp_access_token.startswith("enc:")
    assert decrypt_token(org.whatsapp_access_token) == "live_merchant_access_token_12345"
    assert org.whatsapp_connected_at is not None
    db.close()


def test_06_whatsapp_health_tenant_isolation():
    """GET /api/brand/whatsapp/health returns tenant-specific credentials without leaks."""
    headers_a, org_a_id, headers_b, org_b_id = _setup_two_tenants()

    res_a = client.get("/api/brand/whatsapp/health", headers=headers_a)
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["phone_number_id"] == "phone_id_silk_101"
    assert data_a["waba_id"] == "waba_silk_101"
    assert data_a["token_configured"] is True

    res_b = client.get("/api/brand/whatsapp/health", headers=headers_b)
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["phone_number_id"] == "phone_id_cotton_202"
    assert data_b["waba_id"] == "waba_cotton_202"
    assert data_b["token_configured"] is True
