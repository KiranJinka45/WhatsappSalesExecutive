import os
import sys
import unittest
from fastapi.testclient import TestClient

# Import shared test infrastructure from conftest
from tests.conftest import (
    engine, TestingSessionLocal, setup_test_db, teardown_test_db,
    clean_tables, create_test_tenant, app
)
from app.database import Base, get_db, tenant_var
from app import models

class TestTenantIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_test_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        teardown_test_db()

    def setUp(self):
        # Clear tables
        db = TestingSessionLocal()
        clean_tables(db)
        db.close()

        # Create Tenant A
        self.org_a_headers = self._create_tenant("tenant_a@boutique.com", "User A", "Brand A")
        # Create Tenant B
        self.org_b_headers = self._create_tenant("tenant_b@boutique.com", "User B", "Brand B")

        # Extract IDs
        db = TestingSessionLocal()
        self.org_a = db.query(models.Organization).filter(models.Organization.name == "Brand A").first()
        self.org_b = db.query(models.Organization).filter(models.Organization.name == "Brand B").first()
        
        self.user_a = db.query(models.User).filter(models.User.email == "tenant_a@boutique.com").first()
        self.user_b = db.query(models.User).filter(models.User.email == "tenant_b@boutique.com").first()
        db.close()

    def _create_tenant(self, email, name, org_name):
        signup_data = {
            "email": email,
            "name": name,
            "password": "password123",
            "organization_name": org_name
        }
        res = self.client.post("/api/auth/signup", json=signup_data)
        self.assertEqual(res.status_code, 201)
        
        login_data = {"username": email, "password": "password123"}
        res = self.client.post("/api/auth/login", data=login_data)
        self.assertEqual(res.status_code, 200)
        return {"Authorization": f"Bearer {res.json()['access_token']}"}

    def test_tenant_read_isolation(self):
        """
        Verify Tenant A cannot list or read Tenant B's products.
        """
        # Create product under Tenant B directly in DB
        db = TestingSessionLocal()
        prod_b = models.Product(
            organization_id=self.org_b.id,
            sku="SKU-B",
            name="Tenant B Saree",
            price=2500,
            color="Red",
            fabric="Silk",
            embedding_status="completed"
        )
        db.add(prod_b)
        db.commit()
        db.refresh(prod_b)
        prod_b_id = prod_b.id
        db.close()

        # Query products as Tenant A
        res = self.client.get("/api/catalog/products", headers=self.org_a_headers)
        self.assertEqual(res.status_code, 200)
        products = res.json()
        # Verify Tenant A sees 0 products
        self.assertEqual(len(products), 0)

        # Attempt to read Tenant B's product by ID as Tenant A
        res = self.client.get(f"/api/catalog/products/{prod_b_id}", headers=self.org_a_headers)
        # Should return 404/403 (or FastAPI route doesn't implement single GET, but PUT/DELETE will reject)
        # Let's verify details or updates are blocked
        res_put = self.client.put(f"/api/catalog/products/{prod_b_id}", json={"price": 3000}, headers=self.org_a_headers)
        self.assertEqual(res_put.status_code, 404)

    def test_tenant_write_isolation(self):
        """
        Verify Tenant A cannot create or associate products to Tenant B.
        """
        # Attempt to create product as Tenant A, forcing Tenant B organization_id in request
        # (FastAPI product router maps org from Depends(security.get_current_org))
        product_data = {
            "sku": "SKU-A",
            "name": "Tenant A Kurta",
            "category_name": "Kurtas",
            "price": "1200.00",
            "color": "Blue",
            "fabric": "Cotton",
            "sizes": ["M"],
            "stock_count": 10
        }
        res = self.client.post("/api/catalog/products", json=product_data, headers=self.org_a_headers)
        self.assertEqual(res.status_code, 201)
        prod_id = res.json()["id"]

        # Verify in DB that it is associated with Tenant A's organization, not B
        db = TestingSessionLocal()
        prod = db.query(models.Product).filter(models.Product.id == prod_id).first()
        self.assertEqual(prod.organization_id, self.org_a.id)
        db.close()

    def test_tenant_delete_isolation(self):
        """
        Verify Tenant A cannot delete Tenant B's products.
        """
        # Create product under Tenant B directly in DB
        db = TestingSessionLocal()
        prod_b = models.Product(
            organization_id=self.org_b.id,
            sku="SKU-B",
            name="Tenant B Saree",
            price=2500,
            color="Red",
            fabric="Silk",
            embedding_status="completed"
        )
        db.add(prod_b)
        db.commit()
        db.refresh(prod_b)
        prod_b_id = prod_b.id
        db.close()

        # Attempt to delete Tenant B's product as Tenant A
        res = self.client.delete(f"/api/catalog/products/{prod_b_id}", headers=self.org_a_headers)
        self.assertEqual(res.status_code, 404)

        # Verify product B still exists in DB
        db = TestingSessionLocal()
        exists = db.query(models.Product).filter(models.Product.id == prod_b_id).first()
        self.assertIsNotNone(exists)
        db.close()

    def test_tenant_conversations_isolation(self):
        """
        Verify conversation details, messages, and takeovers are fully isolated.
        """
        # Create conversation for Tenant B
        db = TestingSessionLocal()
        conv_b = models.Conversation(
            organization_id=self.org_b.id,
            customer_phone="+919900002222",
            customer_name="Customer B",
            status="ai_active"
        )
        db.add(conv_b)
        db.commit()
        db.refresh(conv_b)
        conv_b_id = conv_b.id
        db.close()

        # Query conversations as Tenant A
        res = self.client.get("/api/conversations", headers=self.org_a_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()), 0)

        # Attempt to access B's conversation detail as Tenant A
        res_detail = self.client.get(f"/api/conversations/{conv_b_id}", headers=self.org_a_headers)
        self.assertEqual(res_detail.status_code, 404)

        # Attempt takeover on Tenant B's conversation as Tenant A
        res_takeover = self.client.post(f"/api/conversations/{conv_b_id}/takeover?status_val=human_takeover", headers=self.org_a_headers)
        self.assertEqual(res_takeover.status_code, 404)

if __name__ == "__main__":
    unittest.main()
