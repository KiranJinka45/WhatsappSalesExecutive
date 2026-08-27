"""
Acceptance Test Suite for Meta Embedded Signup Integration.
Tests OAuth code exchange, single-use session nonce validation, anti-replay protection,
authoritative resource discovery, BOLA isolation, and zero-secret leakage.
"""
import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app import models
from app.database import tenant_var
from tests.conftest import TestingSessionLocal, clean_tables, create_test_tenant
from app.services import whatsapp_registration_service as reg_service


class TestEmbeddedSignupFlow:

    @pytest.fixture(autouse=True)
    def setup_class(self):
        self.client = TestClient(app)
        db = TestingSessionLocal()
        clean_tables(db)
        db.close()

        # 1. Create Tenant A (Owner)
        self.headers_a = create_test_tenant(
            self.client, "owner_a@boutique.com", "Owner A", "Brand A"
        )
        db = TestingSessionLocal()
        self.org_a = db.query(models.Organization).filter(models.Organization.name == "Brand A").first()
        self.org_a_id = self.org_a.id
        self.user_a = db.query(models.User).filter(models.User.email == "owner_a@boutique.com").first()
        self.user_a_id = self.user_a.id

        # 2. Create Tenant B (Owner)
        self.headers_b = create_test_tenant(
            self.client, "owner_b@boutique.com", "Owner B", "Brand B"
        )
        self.org_b = db.query(models.Organization).filter(models.Organization.name == "Brand B").first()
        self.org_b_id = self.org_b.id

        # 3. Create Staff A in Tenant A
        user_staff = models.User(
            id=uuid.uuid4(),
            organization_id=self.org_a_id,
            email="staff_a@boutique.com",
            password_hash="mocked_hash_password123",
            role="staff",
            name="Staff A"
        )
        db.add(user_staff)
        db.commit()
        db.close()

        res = self.client.post("/api/auth/login", data={"username": "staff_a@boutique.com", "password": "password123"})
        token_staff = res.json()["access_token"]
        self.headers_staff_a = {"Authorization": f"Bearer {token_staff}"}

    def test_01_embedded_signup_config_and_nonce_generation(self):
        """Owner receives public config and a valid one-time session nonce. Staff is rejected with 403."""
        # Non-owner staff rejected
        res_staff = self.client.get("/api/brand/whatsapp/embedded-signup-config", headers=self.headers_staff_a)
        assert res_staff.status_code == 403

        # Owner succeeds
        res_owner = self.client.get("/api/brand/whatsapp/embedded-signup-config", headers=self.headers_a)
        assert res_owner.status_code == 200
        data = res_owner.json()
        assert "app_id" in data
        assert "config_id" in data
        assert "api_version" in data
        assert "session_nonce" in data
        assert len(data["session_nonce"]) >= 32
        # Zero secret exposure in config response
        assert "WHATSAPP_APP_SECRET" not in res_owner.text
        assert "mock_meta_app_secret" not in res_owner.text

    @patch("httpx.get")
    def test_02_embedded_signup_oauth_exchange_success(self, mock_get):
        """Valid code and nonce exchanges token, discovers WABA phones, and marks CONNECTED."""
        # 1. Get session nonce
        res_cfg = self.client.get("/api/brand/whatsapp/embedded-signup-config", headers=self.headers_a)
        nonce = res_cfg.json()["session_nonce"]

        # 2. Mock Meta API responses (OAuth token, debug token, phone discovery, phone status)
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "mock_oauth_exchanged_token_sec_123"}
        mock_token_resp.content = b'{"access_token": "mock_oauth_exchanged_token_sec_123"}'

        mock_debug_resp = MagicMock()
        mock_debug_resp.status_code = 200
        mock_debug_resp.json.return_value = {"data": {"app_id": "123456", "is_valid": True}}
        mock_debug_resp.content = b'{"data": {"is_valid": true}}'

        mock_phones_resp = MagicMock()
        mock_phones_resp.status_code = 200
        mock_phones_resp.json.return_value = {
            "data": [{
                "id": "phone_meta_live_999",
                "display_phone_number": "+91 98765 43210",
                "verified_name": "Brand A Boutique",
                "code_verification_status": "VERIFIED"
            }]
        }
        mock_phones_resp.content = b'{"data": []}'

        mock_status_resp = MagicMock()
        mock_status_resp.status_code = 200
        mock_status_resp.json.return_value = {
            "id": "phone_meta_live_999",
            "verified_name": "Brand A Boutique",
            "code_verification_status": "VERIFIED"
        }
        mock_status_resp.content = b'{"id": "phone_meta_live_999"}'

        mock_get.side_effect = [mock_token_resp, mock_debug_resp, mock_phones_resp, mock_status_resp]

        # 3. Trigger callback endpoint
        callback_payload = {
            "code": "valid_meta_auth_code_xyz",
            "session_nonce": nonce,
            "waba_id_hint": "waba_meta_hint_888",
            "phone_number_id_hint": "phone_meta_live_999"
        }
        res_cb = self.client.post(
            "/api/brand/whatsapp/embedded-signup-callback",
            json=callback_payload,
            headers=self.headers_a
        )

        assert res_cb.status_code == 200
        data = res_cb.json()
        assert data["status"] == "success"
        assert data["onboarding_state"] == "CONNECTED"
        assert data["is_whatsapp_connected"] == 1
        assert "+9198" in data["masked_display_number"]

        # Verify DB Organization state
        db = TestingSessionLocal()
        updated_org = db.query(models.Organization).filter(models.Organization.id == self.org_a_id).first()
        assert updated_org.is_whatsapp_connected == 1
        assert updated_org.whatsapp_business_account_id == "waba_meta_hint_888"
        assert updated_org.whatsapp_phone_number_id == "phone_meta_live_999"
        db.close()

    def test_03_embedded_signup_replay_nonce_rejected(self):
        """Single-use nonce cannot be re-used (anti-replay defense)."""
        # 1. Get session nonce
        res_cfg = self.client.get("/api/brand/whatsapp/embedded-signup-config", headers=self.headers_a)
        nonce = res_cfg.json()["session_nonce"]

        # 2. Manually consume the nonce
        consumed_first = reg_service.validate_and_consume_onboarding_session(self.org_a_id, nonce)
        assert consumed_first is True

        # 3. Second attempt to use the same nonce must fail
        consumed_second = reg_service.validate_and_consume_onboarding_session(self.org_a_id, nonce)
        assert consumed_second is False

        # 4. Attempting callback with already-consumed nonce returns 400
        callback_payload = {
            "code": "valid_meta_auth_code_xyz",
            "session_nonce": nonce
        }
        res_cb = self.client.post(
            "/api/brand/whatsapp/embedded-signup-callback",
            json=callback_payload,
            headers=self.headers_a
        )
        assert res_cb.status_code == 400
        assert "Invalid, expired, or previously used" in res_cb.json()["detail"]

    @patch("httpx.get")
    def test_04_embedded_signup_token_exchange_rejection(self, mock_get):
        """Meta token exchange failure returns safe error without exposing internals."""
        res_cfg = self.client.get("/api/brand/whatsapp/embedded-signup-config", headers=self.headers_a)
        nonce = res_cfg.json()["session_nonce"]

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 400
        mock_token_resp.json.return_value = {"error": {"message": "Invalid authorization code", "code": 100}}
        mock_token_resp.content = b'{"error": {"code": 100}}'
        mock_get.return_value = mock_token_resp

        res_cb = self.client.post(
            "/api/brand/whatsapp/embedded-signup-callback",
            json={"code": "expired_code_123", "session_nonce": nonce},
            headers=self.headers_a
        )
        assert res_cb.status_code == 400
        assert "authorization code exchange failed" in res_cb.json()["detail"]

    def test_05_embedded_signup_cross_tenant_nonce_isolation(self):
        """Tenant A cannot use a session nonce generated for Tenant B (BOLA protection)."""
        # Generate nonce for Tenant B
        res_cfg_b = self.client.get("/api/brand/whatsapp/embedded-signup-config", headers=self.headers_b)
        nonce_b = res_cfg_b.json()["session_nonce"]

        # Tenant A attempts to use Tenant B's nonce
        res_cb = self.client.post(
            "/api/brand/whatsapp/embedded-signup-callback",
            json={"code": "auth_code_xyz", "session_nonce": nonce_b},
            headers=self.headers_a
        )
        assert res_cb.status_code == 400
        assert "Invalid, expired, or previously used" in res_cb.json()["detail"]

    @patch("httpx.get")
    def test_06_embedded_signup_sandbox_test_number_detected(self, mock_get):
        """Meta sandbox test numbers (+1 555...) are detected and flagged safely."""
        res_cfg = self.client.get("/api/brand/whatsapp/embedded-signup-config", headers=self.headers_a)
        nonce = res_cfg.json()["session_nonce"]

        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": "mock_sandbox_token_123"}
        mock_token_resp.content = b'{"access_token": "mock_sandbox_token_123"}'

        mock_debug_resp = MagicMock()
        mock_debug_resp.status_code = 200
        mock_debug_resp.json.return_value = {"data": {"is_valid": True}}
        mock_debug_resp.content = b'{"data": {"is_valid": true}}'

        mock_phones_resp = MagicMock()
        mock_phones_resp.status_code = 200
        mock_phones_resp.json.return_value = {
            "data": [{
                "id": "1292475657271575",
                "display_phone_number": "+1 555-659-5978"
            }]
        }
        mock_phones_resp.content = b'{"data": []}'

        mock_status_resp = MagicMock()
        mock_status_resp.status_code = 200
        mock_status_resp.json.return_value = {"id": "1292475657271575"}
        mock_status_resp.content = b'{"id": "1292475657271575"}'

        mock_get.side_effect = [mock_token_resp, mock_debug_resp, mock_phones_resp, mock_status_resp]

        res_cb = self.client.post(
            "/api/brand/whatsapp/embedded-signup-callback",
            json={"code": "sandbox_auth_code_xyz", "session_nonce": nonce, "waba_id_hint": "sandbox_waba"},
            headers=self.headers_a
        )
        assert res_cb.status_code == 200
        data = res_cb.json()
        assert data["onboarding_state"] == "META_TEST_NUMBER_CONNECTED"
        assert data["is_test_number"] is True
        assert data["is_whatsapp_connected"] == 0

    @patch("httpx.get")
    def test_07_embedded_signup_zero_secret_leakage(self, mock_get):
        """API responses, metadata, and audit logs never leak access tokens, codes, or secrets."""
        res_cfg = self.client.get("/api/brand/whatsapp/embedded-signup-config", headers=self.headers_a)
        nonce = res_cfg.json()["session_nonce"]

        secret_token = "secret_access_token_super_private_999"
        mock_token_resp = MagicMock()
        mock_token_resp.status_code = 200
        mock_token_resp.json.return_value = {"access_token": secret_token}
        mock_token_resp.content = b'{"access_token": "secret_access_token_super_private_999"}'

        mock_debug_resp = MagicMock()
        mock_debug_resp.status_code = 200
        mock_debug_resp.json.return_value = {"data": {"is_valid": True}}
        mock_debug_resp.content = b'{"data": {"is_valid": true}}'

        mock_phones_resp = MagicMock()
        mock_phones_resp.status_code = 200
        mock_phones_resp.json.return_value = {"data": [{"id": "phone_123", "display_phone_number": "+919876543210"}]}
        mock_phones_resp.content = b'{"data": []}'

        mock_status_resp = MagicMock()
        mock_status_resp.status_code = 200
        mock_status_resp.json.return_value = {"id": "phone_123", "verified_name": "Brand A Boutique"}
        mock_status_resp.content = b'{"id": "phone_123"}'

        mock_get.side_effect = [mock_token_resp, mock_debug_resp, mock_phones_resp, mock_status_resp]

        res_cb = self.client.post(
            "/api/brand/whatsapp/embedded-signup-callback",
            json={"code": "secret_oauth_code_abc", "session_nonce": nonce, "waba_id_hint": "waba_sec_1"},
            headers=self.headers_a
        )
        assert res_cb.status_code == 200
        # 1. Assert secret token is not in response payload
        assert secret_token not in res_cb.text
        assert "secret_oauth_code_abc" not in res_cb.text

        # 2. Assert secret token is not in audit log metadata
        db = TestingSessionLocal()
        audit_logs = db.query(models.WhatsappOnboardingAuditLog).filter(
            models.WhatsappOnboardingAuditLog.organization_id == self.org_a_id
        ).all()
        for log in audit_logs:
            assert secret_token not in str(log.metadata_)
            assert "secret_oauth_code_abc" not in str(log.metadata_)
        db.close()
