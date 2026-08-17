import pytest
import uuid
import concurrent.futures
from tests.conftest import TestingSessionLocal, setup_test_db
from app.database import tenant_var
from app import models
from sqlalchemy import text

@pytest.fixture(autouse=True)
def setup_concurrency_db():
    setup_test_db()
    yield

def create_tenant_data(org_id_str: str, org_name: str):
    db = TestingSessionLocal()
    db.is_admin = True
    org_uuid = uuid.UUID(org_id_str)
    try:
        org = models.Organization(
            id=org_uuid,
            name=org_name,
            whatsapp_number=f"+91{org_id_str.replace('-', '')[:10]}",
            whatsapp_phone_number_id=f"waba_{org_name}",
            whatsapp_access_token="secret_token_123"
        )
        db.add(org)
        
        prod = models.Product(
            id=uuid.uuid4(),
            organization_id=org_uuid,
            sku=f"SKU-{org_name}",
            name=f"Saree {org_name}",
            price=1500.0,
            stock_count=10,
            color="Red",
            fabric="Silk"
        )
        db.add(prod)
        db.commit()
    finally:
        db.close()

def worker_query_task(org_id_str: str, expected_sku: str):
    db = TestingSessionLocal()
    org_uuid = uuid.UUID(org_id_str)
    db.organization_id = org_uuid
    token = tenant_var.set(org_uuid)
    try:
        try:
            db.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(org_uuid)})
        except Exception:
            pass

        products = db.query(models.Product).all()
        for p in products:
            assert str(p.organization_id) == org_id_str, f"Cross-tenant leak detected! Found product belonging to {p.organization_id} in query for {org_id_str}"
        
        own_product = db.query(models.Product).filter(models.Product.sku == expected_sku).first()
        assert own_product is not None, f"Expected SKU {expected_sku} not found for tenant {org_id_str}"
        assert str(own_product.organization_id) == org_id_str
        return len(products)
    finally:
        db.close()
        tenant_var.reset(token)

def test_50_concurrent_requests_cross_tenant_isolation():
    tenants = [
        (str(uuid.uuid4()), "OrgAlpha"),
        (str(uuid.uuid4()), "OrgBeta"),
        (str(uuid.uuid4()), "OrgGamma"),
        (str(uuid.uuid4()), "OrgDelta"),
        (str(uuid.uuid4()), "OrgEpsilon"),
    ]
    
    for org_id, org_name in tenants:
        create_tenant_data(org_id, org_name)
        
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        for i in range(50):
            target_org_id, target_org_name = tenants[i % 5]
            expected_sku = f"SKU-{target_org_name}"
            future = executor.submit(worker_query_task, target_org_id, expected_sku)
            tasks.append(future)
            
        results = [f.result() for f in concurrent.futures.as_completed(tasks)]
        
    assert len(results) == 50
    assert all(r >= 1 for r in results)
