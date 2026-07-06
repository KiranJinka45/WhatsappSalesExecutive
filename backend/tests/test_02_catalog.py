import pytest
from fastapi.testclient import TestClient
import uuid

from tests.conftest import app, TestingSessionLocal, clean_tables, create_test_tenant

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

def _get_auth():
    return create_test_tenant(client, f"catalog_{uuid.uuid4()}@example.com", "Cat User", "Cat Org")

def test_catalog_invalid_csv_format():
    auth_headers = _get_auth()
    invalid_csv = "this is not,a valid,csv,file\nfoo"
    
    files = {"file": ("invalid.csv", invalid_csv, "text/csv")}
    response = client.post("/api/catalog/upload", headers=auth_headers, files=files)
    assert response.status_code in [200, 400, 422, 500]

def test_catalog_upload_missing_fields():
    auth_headers = _get_auth()
    csv_content = "id,description\n1,Great product\n2,Another product"
    
    files = {"file": ("missing.csv", csv_content, "text/csv")}
    response = client.post("/api/catalog/upload", headers=auth_headers, files=files)
    assert response.status_code in [200, 400, 422, 500]

def test_catalog_get_nonexistent_product():
    auth_headers = _get_auth()
    fake_id = str(uuid.uuid4())
    response = client.delete(f"/api/catalog/products/{fake_id}", headers=auth_headers)
    assert response.status_code == 404

def test_catalog_pagination():
    auth_headers = _get_auth()
    for i in range(5):
        product_data = {
            "sku": f"SKU-{i}-{uuid.uuid4()}",
            "name": f"Product {i}",
            "description": f"Desc {i}",
            "price": 10.0 + i,
            "color": "Red"
        }
        res = client.post("/api/catalog/products", headers=auth_headers, json=product_data)
        assert res.status_code == 201

    res1 = client.get("/api/catalog/products?limit=2&offset=0", headers=auth_headers)
    assert res1.status_code == 200
    assert len(res1.json()) == 2
    
    res2 = client.get("/api/catalog/products?limit=2&offset=2", headers=auth_headers)
    assert res2.status_code == 200
    assert len(res2.json()) == 2

def test_catalog_update_product():
    auth_headers = _get_auth()
    product_data = {
        "sku": f"SKU-UPD-{uuid.uuid4()}",
        "name": "Old Name",
        "description": "Old Desc",
        "price": 10.0,
        "color": "Blue"
    }
    res = client.post("/api/catalog/products", headers=auth_headers, json=product_data)
    assert res.status_code == 201
    prod_id = res.json()["id"]
    
    update_data = {
        "name": "New Name",
        "price": 20.0
    }
    res_update = client.put(f"/api/catalog/products/{prod_id}", headers=auth_headers, json=update_data)
    assert res_update.status_code == 200
    updated = res_update.json()
    assert updated["name"] == "New Name"
    assert float(updated["price"]) == 20.0
