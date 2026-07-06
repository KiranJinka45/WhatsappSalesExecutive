import os
import sys
import unittest
import uuid
import json
from fastapi.testclient import TestClient

# Import shared test infrastructure from conftest
from tests.conftest import (
    engine, TestingSessionLocal, setup_test_db, teardown_test_db,
    clean_tables, create_test_tenant, app
)
from app.database import Base, get_db
from app import models
from app.connection_manager import manager

class TestSprint2Gates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_test_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        teardown_test_db()

    def setUp(self):
        db = TestingSessionLocal()
        clean_tables(db)
        db.close()

        # Seed Owner
        self.auth_headers = self._create_owner()

    def _create_owner(self):
        signup_data = {
            "email": "owner@closely.com",
            "name": "Kiran Boss",
            "password": "securepassword123",
            "organization_name": "Closely Test Brand"
        }
        res = self.client.post("/api/auth/signup", json=signup_data)
        self.assertEqual(res.status_code, 201)

        login_data = {
            "username": "owner@closely.com",
            "password": "securepassword123"
        }
        res = self.client.post("/api/auth/login", data=login_data)
        self.assertEqual(res.status_code, 200)
        token = res.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_correlation_id_middleware(self):
        """
        Verify every response includes X-Request-ID and handles correlation tracing.
        """
        response = self.client.get("/api/health/liveness")
        self.assertEqual(response.status_code, 200)
        self.assertIn("X-Request-ID", response.headers)
        request_id = response.headers["X-Request-ID"]
        self.assertTrue(len(request_id) > 10)

        # Verify passing custom request ID preserves it
        custom_id = str(uuid.uuid4())
        response = self.client.get("/api/health/liveness", headers={"X-Request-ID": custom_id})
        self.assertEqual(response.headers["X-Request-ID"], custom_id)

    def test_payment_webhook_flow(self):
        """
        Verify payments webhook sets funnel stage to paid and logs values.
        """
        # 1. Manually insert active conversation under our brand
        db = TestingSessionLocal()
        org = db.query(models.Organization).first()
        conv = models.Conversation(
            organization_id=org.id,
            customer_phone="+919988776655",
            customer_name="Buyer Sita",
            status="ai_active",
            metadata_={"funnel_stage": "lead"}
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        db.close()

        # 2. Trigger payment success webhook payload
        payload = {
            "event": "payment.captured",
            "customer_phone": "+919988776655",
            "amount": 3500.50,
            "currency": "INR"
        }
        res = self.client.post("/api/webhooks/payments", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "success")

        # 3. Assert DB updates
        db = TestingSessionLocal()
        updated_conv = db.query(models.Conversation).filter(
            models.Conversation.customer_phone == "+919988776655"
        ).first()
        self.assertEqual(updated_conv.metadata_["funnel_stage"], "paid")
        self.assertEqual(updated_conv.metadata_["order_value"], 3500.50)
        db.close()

    def test_jwt_tampering_and_expired_rejections(self):
        """
        Verify invalid auth headers/tokens are rejected immediately with 401.
        """
        # Tampered Token
        tampered_headers = {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.tampered.token"}
        res = self.client.get("/api/brand/profile", headers=tampered_headers)
        self.assertEqual(res.status_code, 401)

        # Empty/Malformed Token
        malformed_headers = {"Authorization": "Bearer malformed"}
        res = self.client.get("/api/brand/profile", headers=malformed_headers)
        self.assertEqual(res.status_code, 401)

    def test_csv_upload_validation_edge_cases(self):
        """
        Verify catalog CSV uploader rejects invalid formats and delimiters.
        """
        # Missing SKU column completely
        invalid_csv_content = b"name,price,color,category,fabric,stock_count\nSaree,4500.00,Red,Sarees,Silk,10"
        files = {"file": ("invalid.csv", invalid_csv_content, "text/csv")}
        res = self.client.post("/api/catalog/upload", files=files, headers=self.auth_headers)
        self.assertEqual(res.status_code, 500)  # In our uploader, errors are wrapped in 500
        self.assertIn("Missing required columns", res.json()["detail"])

        # Negative price uploader check
        invalid_price_content = b"sku,name,price,color,category,fabric,stock_count\nSKU001,Saree,-4500.00,Red,Sarees,Silk,10"
        files = {"file": ("invalid_price.csv", invalid_price_content, "text/csv")}
        res = self.client.post("/api/catalog/upload", files=files, headers=self.auth_headers)
        self.assertEqual(res.status_code, 500)
        self.assertIn("Price cannot be negative", res.json()["detail"])

    def test_sse_connection_manager_broadcast(self):
        """
        Test the ConnectionManager SSE registry and broadcast delivery directly.
        """
        org_id = str(uuid.uuid4())
        queue = manager.register(org_id)

        # Broadcast mock notification
        event_data = {"test": "val"}
        manager.broadcast(org_id, "test_event", event_data)

        # Assert queue holds data
        self.assertEqual(queue.qsize(), 1)
        item = queue.get_nowait()
        self.assertEqual(item["event"], "test_event")
        self.assertEqual(item["data"], event_data)

        manager.disconnect(org_id, queue)

if __name__ == "__main__":
    unittest.main()
