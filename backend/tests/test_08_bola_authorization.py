"""
Milestone 4 Hardening: Broken Object-Level Authorization (BOLA) & RLS Security Acceptance Test Suite.
Verifies cross-tenant isolation, role-based authorization, and fail-closed audit log protection across API boundaries.
"""
import unittest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app import models, security
from app.database import tenant_var
from app.approval_service import hash_message
from tests.conftest import TestingSessionLocal, clean_tables, create_test_tenant


class TestBOLAAuthorization(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

        # Reset database tables cleanly
        db = TestingSessionLocal()
        clean_tables(db)
        db.close()

        # 1. Create Tenant A (Owner)
        self.headers_a = create_test_tenant(
            self.client, "owner_a@boutique.com", "Owner A", "Brand A"
        )

        # 2. Create Tenant B (Owner)
        self.headers_b = create_test_tenant(
            self.client, "owner_b@boutique.com", "Owner B", "Brand B"
        )

        # Extract IDs using fresh session
        db = TestingSessionLocal()
        db.is_admin = True
        db.execute(text("SET LOCAL app.current_tenant = ''"))

        org_a = db.query(models.Organization).filter(models.Organization.name == "Brand A").first()
        org_b = db.query(models.Organization).filter(models.Organization.name == "Brand B").first()
        self.org_a_id = org_a.id
        self.org_b_id = org_b.id

        # Create a Staff (Viewer) user for Tenant A
        staff_a = models.User(
            organization_id=self.org_a_id,
            email="staff_a@boutique.com",
            password_hash=security.get_password_hash("password123"),
            role="staff",
            name="Staff A"
        )
        db.add(staff_a)
        db.commit()
        db.refresh(staff_a)
        self.staff_a_id = staff_a.id

        # Create conversation and approval request for Tenant B
        conv_b = models.Conversation(
            organization_id=self.org_b_id,
            customer_phone="+919888888888",
            customer_name="Customer B",
            status="WAITING_APPROVAL"
        )
        db.add(conv_b)
        db.commit()
        db.refresh(conv_b)
        self.conv_b_id = conv_b.id

        draft_text_b = "Namaste Customer B! Here is silk saree SKU-B for Rs.2,500."
        approval_b = models.ApprovalRequest(
            organization_id=self.org_b_id,
            conversation_id=self.conv_b_id,
            status="WAITING_APPROVAL",
            reason="High-value item query",
            proposed_response=draft_text_b,
            message_hash=hash_message(draft_text_b),
            version=1,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
        )
        db.add(approval_b)
        db.commit()
        db.refresh(approval_b)
        self.approval_b_id = approval_b.id

        db.close()

        # Login Staff A to get staff_a auth headers
        res = self.client.post("/api/auth/login", data={"username": "staff_a@boutique.com", "password": "password123"})
        self.assertEqual(res.status_code, 200)
        token_staff = res.json()["access_token"]
        self.headers_staff_a = {"Authorization": f"Bearer {token_staff}"}

    def test_01_bola_get_approval_detail_cross_tenant_denied(self):
        """Verify Tenant A cannot access Tenant B's approval request by ID (returns 404)."""
        res = self.client.get(f"/api/approvals/{self.approval_b_id}", headers=self.headers_a)
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found", res.json()["detail"].lower())

    def test_02_bola_respond_approval_cross_tenant_denied(self):
        """Verify Tenant A cannot approve, edit, or reject Tenant B's approval request (returns 404)."""
        res = self.client.post(
            f"/api/approvals/{self.approval_b_id}/respond",
            json={"action": "approve"},
            headers=self.headers_a
        )
        self.assertEqual(res.status_code, 404)

        # Confirm Tenant B's approval remains WAITING_APPROVAL in DB
        db = TestingSessionLocal()
        db.is_admin = True
        db.execute(text("SET LOCAL app.current_tenant = ''"))
        refreshed = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == self.approval_b_id).first()
        self.assertEqual(refreshed.status, "WAITING_APPROVAL")
        db.close()

    def test_03_bola_get_audit_trail_cross_tenant_denied(self):
        """Verify Tenant A cannot read Tenant B's approval audit logs (returns 404)."""
        res = self.client.get(f"/api/approvals/{self.approval_b_id}/audit", headers=self.headers_a)
        self.assertEqual(res.status_code, 404)
        self.assertIn("not found", res.json()["detail"].lower())

    def test_04_bola_unauthorized_role_approval_respond_forbidden(self):
        """Verify staff/viewer role cannot respond to approval requests (returns 403 Forbidden)."""
        # Create an approval for Tenant A first
        db = TestingSessionLocal()
        db.is_admin = True
        db.execute(text("SET LOCAL app.current_tenant = ''"))

        conv_a = models.Conversation(
            organization_id=self.org_a_id,
            customer_phone="+919777777777",
            customer_name="Customer A",
            status="WAITING_APPROVAL"
        )
        db.add(conv_a)
        db.commit()
        db.refresh(conv_a)

        approval_a = models.ApprovalRequest(
            organization_id=self.org_a_id,
            conversation_id=conv_a.id,
            status="WAITING_APPROVAL",
            reason="Discount request",
            proposed_response="Draft A",
            message_hash=hash_message("Draft A")
        )
        db.add(approval_a)
        db.commit()
        db.refresh(approval_a)
        approval_a_id = approval_a.id
        db.close()

        # Attempt response with Staff A headers
        res = self.client.post(
            f"/api/approvals/{approval_a_id}/respond",
            json={"action": "approve"},
            headers=self.headers_staff_a
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("not permitted", res.json()["detail"].lower())

    def test_05_bola_unauthenticated_requests_unauthorized(self):
        """Verify unauthenticated calls return 401 Unauthorized across all approval routes."""
        routes = [
            ("GET", f"/api/approvals"),
            ("GET", f"/api/approvals/{self.approval_b_id}"),
            ("POST", f"/api/approvals/{self.approval_b_id}/respond"),
            ("GET", f"/api/approvals/{self.approval_b_id}/audit"),
            ("GET", f"/api/brand/kill-switch"),
            ("POST", f"/api/brand/kill-switch")
        ]
        for method, endpoint in routes:
            if method == "GET":
                res = self.client.get(endpoint)
            else:
                res = self.client.post(endpoint, json={"active": True})
            self.assertEqual(res.status_code, 401, f"Failed on {method} {endpoint}")

    def test_06_kill_switch_role_security(self):
        """Verify staff/viewer user cannot toggle emergency kill-switch (403 Forbidden)."""
        res = self.client.post(
            "/api/brand/kill-switch",
            json={"active": True, "reason": "Unauthorized attempt"},
            headers=self.headers_staff_a
        )
        self.assertEqual(res.status_code, 403)

    def test_07_outbound_messages_rls_isolation(self):
        """Verify outbound_messages table isolates records per tenant at database RLS level."""
        db = TestingSessionLocal()
        db.is_admin = True
        db.execute(text("SET LOCAL app.current_tenant = ''"))

        outbound_b = models.OutboundMessage(
            approval_request_id=self.approval_b_id,
            organization_id=self.org_b_id,
            conversation_id=self.conv_b_id,
            message_version=1,
            provider_idempotency_key=f"outbound_{self.approval_b_id}_v1",
            payload_hash="303f6db0ce0daf92f04458fc8da566fd1f951f18c0631e3c3f0cd79abd08d8b3",
            recipient_phone="+919888888888",
            content="Test content B",
            status="PENDING"
        )
        db.add(outbound_b)
        db.commit()
        db.close()

        # Query as Tenant A in a clean session under RLS context
        db_a = TestingSessionLocal()
        db_a.is_admin = False
        db_a.organization_id = self.org_a_id
        tenant_var.set(self.org_a_id)
        db_a.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(self.org_a_id)})
        results = db_a.query(models.OutboundMessage).all()
        self.assertEqual(len(results), 0)
        db_a.close()

    def test_08_onboarding_connection_status_tenant_isolation(self):
        """Verify Tenant A cannot see Tenant B's onboarding status or masked number."""
        res_a = self.client.get("/api/brand/whatsapp/connection-status", headers=self.headers_a)
        self.assertEqual(res_a.status_code, 200)
        data_a = res_a.json()
        self.assertIn("onboarding_state", data_a)
        # Ensure Tenant B data is not returned
        self.assertNotEqual(data_a.get("masked_display_number"), "+9198 ***** 88")

    def test_09_onboarding_mutation_endpoints_role_security(self):
        """Verify non-owner roles (staff/viewer) cannot execute onboarding mutations (403 Forbidden)."""
        endpoints = [
            ("POST", "/api/brand/whatsapp/request-verification-code", {"method": "SMS"}),
            ("POST", "/api/brand/whatsapp/verify-registration-code", {"code": "123456"}),
            ("POST", "/api/brand/whatsapp/activate-live-number", {})
        ]
        for method, endpoint, payload in endpoints:
            res = self.client.post(endpoint, json=payload, headers=self.headers_staff_a)
            self.assertEqual(res.status_code, 403, f"Expected 403 for staff on {endpoint}, got {res.status_code}")

    def test_10_onboarding_audit_logs_rls_isolation(self):
        """Verify whatsapp_onboarding_audit_logs isolates records per tenant at database RLS level."""
        db = TestingSessionLocal()
        db.is_admin = True
        db.execute(text("SET LOCAL app.current_tenant = ''"))

        audit_b = models.WhatsappOnboardingAuditLog(
            id=uuid.uuid4(),
            organization_id=self.org_b_id,
            action="REQUEST_CODE_SUCCESS",
            previous_state="NOT_CONNECTED",
            new_state="VERIFICATION_CODE_REQUESTED",
            error_category=None,
            metadata_={"method": "SMS"},
            correlation_id=str(uuid.uuid4())
        )
        db.add(audit_b)
        db.commit()
        db.close()

        # Query as Tenant A in clean session under RLS context
        db_a = TestingSessionLocal()
        db_a.is_admin = False
        db_a.organization_id = self.org_a_id
        tenant_var.set(self.org_a_id)
        db_a.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(self.org_a_id)})
        results = db_a.query(models.WhatsappOnboardingAuditLog).filter(
            models.WhatsappOnboardingAuditLog.organization_id == self.org_b_id
        ).all()
        self.assertEqual(len(results), 0)
        db_a.close()

    def test_11_onboarding_api_response_zero_secret_leakage(self):
        """Verify onboarding API responses never expose tokens, WABA IDs, phone IDs, codes, or PINs."""
        res = self.client.get("/api/brand/whatsapp/connection-status", headers=self.headers_a)
        self.assertEqual(res.status_code, 200)
        raw_text = res.text
        self.assertNotIn("whatsapp_access_token", raw_text)
        self.assertNotIn("whatsapp_business_account_id", raw_text)
        self.assertNotIn("whatsapp_phone_number_id", raw_text)
        self.assertNotIn("pin", raw_text)
        self.assertNotIn("code", raw_text)


if __name__ == "__main__":
    unittest.main()

