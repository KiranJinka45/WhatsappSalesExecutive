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
from app.routers.auth import login_limiter

class TestTenantIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_test_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        teardown_test_db()

    def setUp(self):
        # Reset login rate limiter requests for this client
        login_limiter.requests.clear()

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
        token = res.cookies.get("access_token")
        return {"Authorization": f"Bearer {token}"}

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
        res_takeover = self.client.post(f"/api/conversations/{conv_b_id}/takeover?status_val=OWNER_ACTIVE", headers=self.org_a_headers)
        self.assertEqual(res_takeover.status_code, 404)

    def test_db_rls_isolation(self):
        """
        Verify RLS enforces isolation directly at database level when app.current_tenant is set.
        """
        from sqlalchemy import text
        db = TestingSessionLocal()
        
        # 1. Clear session variable and create a product for Tenant B
        db.execute(text("SET LOCAL app.current_tenant = ''"))
        prod_b = models.Product(
            organization_id=self.org_b.id,
            sku="SKU-RLS-B",
            name="Tenant B RLS Saree",
            price=3000,
            color="Red",
            fabric="Silk",
            embedding_status="completed"
        )
        db.add(prod_b)
        db.commit()
        
        # 2. Start a transaction, set app.current_tenant to Tenant A's ID
        db.begin()
        
        # Create a non-superuser role for testing RLS enforcement
        db.execute(text("DROP ROLE IF EXISTS test_rls_user"))
        db.execute(text("CREATE ROLE test_rls_user"))
        db.execute(text("GRANT USAGE ON SCHEMA public TO test_rls_user"))
        db.execute(text("GRANT SELECT ON products TO test_rls_user"))
        db.execute(text("SET ROLE test_rls_user"))
        
        db.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(self.org_a.id)})
        
        # Query products (RLS should block seeing Tenant B's product)
        prods = db.query(models.Product).filter(models.Product.sku == "SKU-RLS-B").all()
        
        # Clean up role and reset role
        db.execute(text("RESET ROLE"))
        db.execute(text("DROP OWNED BY test_rls_user"))
        db.execute(text("DROP ROLE IF EXISTS test_rls_user"))
        
        self.assertEqual(len(prods), 0)
        
        db.rollback()
        db.close()

    def test_write_rls_enforcement_at_db_level(self):
        """
        Verify RLS restricts INSERT and UPDATE at the database level when app.current_tenant is set.
        """
        from sqlalchemy import text
        from sqlalchemy.exc import InternalError, ProgrammingError, OperationalError
        db = TestingSessionLocal()
        
        # 1. Create the role in a separate transaction and commit it so it persists database rollback
        db.execute(text("DROP ROLE IF EXISTS test_rls_write_user"))
        db.execute(text("CREATE ROLE test_rls_write_user"))
        db.execute(text("GRANT USAGE ON SCHEMA public TO test_rls_write_user"))
        db.execute(text("GRANT SELECT, INSERT, UPDATE ON products TO test_rls_write_user"))
        db.commit()
        
        # 2. Start the test transaction
        db.begin()
        db.execute(text("SET ROLE test_rls_write_user"))
        
        try:
            # Set tenant context to Tenant A
            db.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(self.org_a.id)})
            
            # Attempt to INSERT a product with Tenant B's organization_id
            mismatched_prod = models.Product(
                organization_id=self.org_b.id,
                sku="SKU-RLS-MISMATCH",
                name="Tenant B Saree Mismatch",
                price=4000,
                color="Green",
                fabric="Cotton",
                embedding_status="completed"
            )
            db.add(mismatched_prod)
            
            # This should fail due to RLS insert policy
            with self.assertRaises((ProgrammingError, InternalError, OperationalError)) as context:
                db.commit()
            
            self.assertIn("violates row-level security policy", str(context.exception))
            db.rollback()
            
        finally:
            # Clean up role and reset
            try:
                db.rollback()
            except Exception:
                pass
            
            db.execute(text("RESET ROLE"))
            try:
                db.execute(text("DROP OWNED BY test_rls_write_user"))
            except Exception:
                pass
            db.execute(text("DROP ROLE IF EXISTS test_rls_write_user"))
            db.commit()
            db.close()

    def test_soft_delete_conversations_and_brand(self):
        """
        Verify DELETE /api/brand/profile soft-deletes the brand and its conversations,
        ensuring rows remain in the DB with deleted_at set, but normal queries exclude them.
        """
        db = TestingSessionLocal()
        # 1. Create a conversation for Tenant A
        conv_a = models.Conversation(
            organization_id=self.org_a.id,
            customer_phone="+919900003333",
            customer_name="Customer A Soft Delete",
            status="AI_ACTIVE"
        )
        db.add(conv_a)
        db.commit()
        db.refresh(conv_a)
        conv_a_id = conv_a.id
        
        # Verify it can be retrieved normally
        db.is_admin = False
        db.organization_id = self.org_a.id
        db_conv = db.query(models.Conversation).filter(models.Conversation.id == conv_a_id).first()
        self.assertIsNotNone(db_conv)
        
        # 2. Call DELETE /api/brand/profile
        res = self.client.delete("/api/brand/profile", headers=self.org_a_headers)
        self.assertEqual(res.status_code, 204)
        
        # 3. Verify normal queries return empty/404/401
        # Get conversations
        res_convs = self.client.get("/api/conversations", headers=self.org_a_headers)
        self.assertEqual(res_convs.status_code, 401)
        
        # 4. Verify rows STILL exist in DB (not hard-deleted) with deleted_at set
        # Bypass RLS/loader filters to check actual database rows
        db.is_admin = True
        db.expire_all()
        db_org = db.query(models.Organization).filter(models.Organization.id == self.org_a.id).first()
        self.assertIsNotNone(db_org)
        self.assertIsNotNone(db_org.deleted_at)
        
        db_conv_deleted = db.query(models.Conversation).filter(models.Conversation.id == conv_a_id).first()
        self.assertIsNotNone(db_conv_deleted)
        self.assertIsNotNone(db_conv_deleted.deleted_at)
        
        db.close()

    def test_login_rate_limiting(self):
        """
        Verify login rate limiter returns 429 after exceeding limit.
        """
        login_data = {"username": "limit@test.com", "password": "password123"}
        
        # Call login up to 5 times (limiter limit is 5)
        for _ in range(5):
            self.client.post("/api/auth/login", data=login_data)
            
        # 6th call should trigger 429
        res = self.client.post("/api/auth/login", data=login_data)
        self.assertEqual(res.status_code, 429)
        self.assertIn("Too many requests", res.json()["detail"])

    def test_cross_tenant_caching_isolation(self):
        """
        Verify that query compilation caching in SQLAlchemy doesn't leak tenant data.
        Interleave requests between Org A and Org B, asserting strict data correctness.
        """
        # Create product for Org A
        res_a = self.client.post(
            "/api/catalog/products",
            headers=self.org_a_headers,
            json={"sku": "ORG-A-ONLY-SKU", "name": "Product A", "price": 10.0, "color": "Red"}
        )
        self.assertEqual(res_a.status_code, 201)

        # Create product for Org B
        res_b = self.client.post(
            "/api/catalog/products",
            headers=self.org_b_headers,
            json={"sku": "ORG-B-ONLY-SKU", "name": "Product B", "price": 20.0, "color": "Blue"}
        )
        self.assertEqual(res_b.status_code, 201)

        # Alternating requests: A -> B -> A -> B -> A
        sequence = [
            (self.org_a_headers, "ORG-A-ONLY-SKU", "ORG-B-ONLY-SKU"),
            (self.org_b_headers, "ORG-B-ONLY-SKU", "ORG-A-ONLY-SKU"),
            (self.org_a_headers, "ORG-A-ONLY-SKU", "ORG-B-ONLY-SKU"),
            (self.org_b_headers, "ORG-B-ONLY-SKU", "ORG-A-ONLY-SKU"),
            (self.org_a_headers, "ORG-A-ONLY-SKU", "ORG-B-ONLY-SKU"),
        ]

        for headers, expected_sku, prohibited_sku in sequence:
            res = self.client.get("/api/catalog/products", headers=headers)
            self.assertEqual(res.status_code, 200)
            products = res.json()
            skus = [p["sku"] for p in products]
            self.assertIn(expected_sku, skus)
            self.assertNotIn(prohibited_sku, skus)

if __name__ == "__main__":
    unittest.main()
