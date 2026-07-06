import os
import sys
import unittest
from fastapi.testclient import TestClient

# Import shared test infrastructure from conftest
from tests.conftest import (
    engine, TestingSessionLocal, setup_test_db, teardown_test_db,
    clean_tables, create_test_tenant, app
)
from app.database import Base
from app.config import settings
from app import models

class TestCloselyBackend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_test_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        teardown_test_db()

    def setUp(self):
        from unittest.mock import patch
        
        # Start mock patches for AI service to run tests offline
        self.classify_patch = patch('app.ai_service.classify_intent')
        self.mock_classify = self.classify_patch.start()
        self.mock_classify.side_effect = lambda msg, hist=None: (
            "human_negotiation" if any(w in msg.lower() for w in ["discount", "wholesale", "human"]) 
            else "product_discovery"
        )

        self.embedding_patch = patch('app.ai_service.get_embedding')
        self.mock_embedding = self.embedding_patch.start()
        self.mock_embedding.return_value = [0.0] * 768

        self.reply_patch = patch('app.ai_service.generate_reply')
        self.mock_reply = self.reply_patch.start()
        self.mock_reply.return_value = "Mocked AI Response: Here are some beautiful sarees for you!"

        # Clear out tables before each test to guarantee isolated states
        db = TestingSessionLocal()
        clean_tables(db)
        db.close()
        
        # Seed test organization and user
        self.auth_headers = self._create_test_owner()

    def tearDown(self):
        self.classify_patch.stop()
        self.embedding_patch.stop()
        self.reply_patch.stop()

    def _create_test_owner(self):
        # Sign up
        signup_data = {
            "email": "testowner@boutique.com",
            "name": "Kiran Owner",
            "password": "securepassword123",
            "organization_name": "Kiran Sarees"
        }
        response = self.client.post("/api/auth/signup", json=signup_data)
        self.assertEqual(response.status_code, 201)
        
        # Log in
        login_data = {
            "username": "testowner@boutique.com",
            "password": "securepassword123"
        }
        response = self.client.post("/api/auth/login", data=login_data)
        self.assertEqual(response.status_code, 200)
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_brand_profile_and_policies(self):
        # Get brand profile
        response = self.client.get("/api/brand/profile", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Kiran Sarees")
        
        # Update policies
        update_data = {
            "whatsapp_number": "+919876543210",
            "address": "Dharmavaram, Andhra Pradesh",
            "policies": {
                "shipping": "We offer free shipping across India. Standard delivery is 3-5 working days.",
                "cod": "Cash on Delivery (COD) is available for orders below INR 10,000.",
                "returns": "Easy returns within 7 days of delivery. Product must be in original condition."
            }
        }
        response = self.client.put("/api/brand/profile", json=update_data, headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        profile = response.json()
        self.assertEqual(profile["whatsapp_number"], "+919876543210")
        self.assertEqual(profile["policies"]["cod"], "Cash on Delivery (COD) is available for orders below INR 10,000.")

    def test_catalog_csv_upload(self):
        # Load test CSV file
        csv_path = os.path.join(os.path.dirname(__file__), "test_data.csv")
        with open(csv_path, "rb") as f:
            files = {"file": ("test_data.csv", f, "text/csv")}
            response = self.client.post("/api/catalog/upload", files=files, headers=self.auth_headers)
            
        self.assertEqual(response.status_code, 200)
        res_data = response.json()
        self.assertEqual(res_data["status"], "success")
        self.assertGreater(res_data["created"], 0)

        # Check products are in database
        response = self.client.get("/api/catalog/products", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        products = response.json()
        self.assertEqual(len(products), 5)
        
        # Check single product details (SKU001)
        banarasi_saree = next(p for p in products if p["sku"] == "SKU001")
        self.assertEqual(banarasi_saree["color"], "Black")
        self.assertEqual(float(banarasi_saree["price"]), 4500.0)
        self.assertEqual(banarasi_saree["fabric"], "Silk")
        self.assertIn("Free Size", banarasi_saree["sizes"])

    def test_product_crud(self):
        # Create single product manually
        product_data = {
            "sku": "SKU999",
            "name": "Chanderi Silk Saree",
            "category_name": "Sarees",
            "gender": "Women",
            "price": "6000.00",
            "color": "Green",
            "fabric": "Chanderi Silk",
            "description": "Premium handloom green Chanderi silk saree.",
            "sizes": ["Free Size"],
            "stock_count": 12,
            "image_urls": ["https://example.com/chanderi.jpg"]
        }
        response = self.client.post("/api/catalog/products", json=product_data, headers=self.auth_headers)
        self.assertEqual(response.status_code, 201)
        created_prod = response.json()
        prod_id = created_prod["id"]
        
        # Verify get lists
        response = self.client.get("/api/catalog/products", headers=self.auth_headers)
        self.assertEqual(len(response.json()), 1)

        # Update product
        update_data = {
            "price": "5500.00",
            "stock_count": 10
        }
        response = self.client.put(f"/api/catalog/products/{prod_id}", json=update_data, headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(float(response.json()["price"]), 5500.0)
        self.assertEqual(response.json()["stock_count"], 10)

        # Delete product
        response = self.client.delete(f"/api/catalog/products/{prod_id}", headers=self.auth_headers)
        self.assertEqual(response.status_code, 204)
        
        response = self.client.get("/api/catalog/products", headers=self.auth_headers)
        self.assertEqual(len(response.json()), 0)

    def test_simulated_whatsapp_webhook_flow(self):
        # 1. Update policies for context grounding
        update_data = {
            "whatsapp_number": "+919876543210",
            "policies": {
                "shipping": "Free delivery across India.",
                "cod": "COD is available.",
                "returns": "Easy 7 day returns."
            }
        }
        self.client.put("/api/brand/profile", json=update_data, headers=self.auth_headers)

        # 2. Upload catalog CSV
        csv_path = os.path.join(os.path.dirname(__file__), "test_data.csv")
        with open(csv_path, "rb") as f:
            self.client.post("/api/catalog/upload", files={"file": ("test_data.csv", f, "text/csv")}, headers=self.auth_headers)

        # 3. Simulate customer inbound WhatsApp message (discovery query)
        webhook_payload = {
            "customer_phone": "+919900001111",
            "brand_phone": "+919876543210",
            "message": "Hi, show me black sarees under 5000",
            "customer_name": "Sita Reddy"
        }
        response = self.client.post("/api/webhooks/whatsapp", json=webhook_payload)
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(res_json["status"], "processing")
        
        # Verify conversation and messages in the database
        db = TestingSessionLocal()
        conv = db.query(models.Conversation).filter(models.Conversation.customer_phone == "+919900001111").first()
        self.assertIsNotNone(conv)
        self.assertEqual(conv.status, "ai_active")
        
        messages = db.query(models.Message).filter(models.Message.conversation_id == conv.id).order_by(models.Message.created_at.asc()).all()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].sender, "customer")
        self.assertEqual(messages[1].sender, "ai")
        self.assertIn("Mocked AI Response", messages[1].content)
        db.close()
        
        # 4. Simulate human takeover request (escalation)
        negotiation_payload = {
            "customer_phone": "+919900001111",
            "brand_phone": "+919876543210",
            "message": "I want a discount. Can you do 2000 wholesale price?",
            "customer_name": "Sita Reddy"
        }
        response = self.client.post("/api/webhooks/whatsapp", json=negotiation_payload)
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertEqual(res_json["status"], "processing")
        
        # Verify conversation is now in human_takeover status in database
        db = TestingSessionLocal()
        conv = db.query(models.Conversation).filter(models.Conversation.customer_phone == "+919900001111").first()
        self.assertEqual(conv.status, "human_takeover")
        
        messages = db.query(models.Message).filter(models.Message.conversation_id == conv.id).all()
        # Should contain customer message, AI response, escalation message, handoff note
        self.assertTrue(any("wholesale" in m.content for m in messages))
        db.close()

if __name__ == "__main__":
    unittest.main()
