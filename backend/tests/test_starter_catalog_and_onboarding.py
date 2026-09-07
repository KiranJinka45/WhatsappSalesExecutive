import pytest
import uuid
from decimal import Decimal
from fastapi.testclient import TestClient

from tests.conftest import app, TestingSessionLocal, clean_tables
from app import models
from app import security

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

def create_authenticated_merchant():
    db = TestingSessionLocal()
    try:
        org = models.Organization(name="Boutique Silk Store", whatsapp_number="+919876500111")
        db.add(org)
        db.commit()
        db.refresh(org)
        org_id = org.id

        user = models.User(
            organization_id=org.id,
            email=f"merchant_{uuid.uuid4().hex[:6]}@example.com",
            name="Silk Merchant",
            password_hash=security.get_password_hash("testpass123"),
            role="owner"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id

        token = security.create_access_token(data={"sub": str(user_id)})
        return org_id, user_id, token
    finally:
        db.close()

def test_seed_starter_pack_silk_sarees():
    org_id, user_id, token = create_authenticated_merchant()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/catalog/seed-starter-pack?pack_type=silk_sarees", headers=headers)
    assert res.status_code == 201
    data = res.json()

    assert data["status"] == "success"
    assert data["pack_type"] == "silk_sarees"
    assert data["seeded_count"] == 5
    assert len(data["products"]) == 5

    # Verify Products in DB
    db = TestingSessionLocal()
    try:
        products = db.query(models.Product).filter(models.Product.organization_id == org_id).all()
        assert len(products) == 5
        sku_list = [p.sku for p in products]
        assert any("SAREE-KAN-001" in s for s in sku_list)
        assert any("SAREE-BAN-002" in s for s in sku_list)

        # Verify Category created
        category = db.query(models.Category).filter(models.Category.organization_id == org_id).first()
        assert category is not None
        assert category.name == "Silk Sarees"
    finally:
        db.close()

def test_seed_starter_pack_invalid_type():
    org_id, user_id, token = create_authenticated_merchant()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/catalog/seed-starter-pack?pack_type=invalid_pack", headers=headers)
    assert res.status_code == 400
    assert "Invalid pack_type" in res.json()["detail"]

def test_seed_starter_pack_idempotent_update():
    org_id, user_id, token = create_authenticated_merchant()
    headers = {"Authorization": f"Bearer {token}"}

    # First seeding
    res1 = client.post("/api/catalog/seed-starter-pack?pack_type=ethnic_wear", headers=headers)
    assert res1.status_code == 201
    assert res1.json()["seeded_count"] == 3

    # Re-seeding same pack updates rather than creating duplicate SKUs
    res2 = client.post("/api/catalog/seed-starter-pack?pack_type=ethnic_wear", headers=headers)
    assert res2.status_code == 201
    assert res2.json()["seeded_count"] == 3

    db = TestingSessionLocal()
    try:
        products = db.query(models.Product).filter(models.Product.organization_id == org_id).all()
        assert len(products) == 3
    finally:
        db.close()
