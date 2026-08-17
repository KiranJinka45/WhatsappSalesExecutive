import pytest
from fastapi.testclient import TestClient
import uuid
import io
from unittest.mock import patch

from tests.conftest import app, TestingSessionLocal, clean_tables, create_test_tenant

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

def _get_auth(suffix=None):
    s = suffix or str(uuid.uuid4())[:8]
    return create_test_tenant(client, f"m2_catalog_{s}@example.com", f"M2 User {s}", f"M2 Org {s}")

def test_valid_csv_upload_optional_color_fabric():
    auth_headers = _get_auth("valid")
    # CSV with minimal required headers: sku, name, price, category, stock_count
    csv_data = (
        "sku,name,price,category,stock_count\n"
        "SKU-M2-001,Kanjeevaram Saree,15000,Sarees,10\n"
        "SKU-M2-002,Banarasi Saree,22000,Sarees,5\n"
    )
    files = {"file": ("catalog.csv", io.BytesIO(csv_data.encode('utf-8')), "text/csv")}
    response = client.post("/api/catalog/upload", headers=auth_headers, files=files)
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "success"
    assert res["created"] == 2

    # Verify via GET products
    get_res = client.get("/api/catalog/products", headers=auth_headers)
    assert get_res.status_code == 200
    items = get_res.json()
    assert len(items) == 2
    skus = {item["sku"] for item in items}
    assert "SKU-M2-001" in skus
    assert "SKU-M2-002" in skus

def test_csv_upload_negative_price_rejected():
    auth_headers = _get_auth("negprice")
    csv_data = (
        "sku,name,price,category,stock_count\n"
        "SKU-NEG-1,Bad Saree,-1500,Sarees,10\n"
    )
    files = {"file": ("negprice.csv", io.BytesIO(csv_data.encode('utf-8')), "text/csv")}
    response = client.post("/api/catalog/upload?mode=atomic", headers=auth_headers, files=files)
    assert response.status_code == 400
    assert "negative" in response.json()["detail"].lower()

def test_csv_upload_negative_stock_rejected():
    auth_headers = _get_auth("negstock")
    csv_data = (
        "sku,name,price,category,stock_count\n"
        "SKU-NEG-2,Bad Stock Saree,1500,Sarees,-5\n"
    )
    files = {"file": ("negstock.csv", io.BytesIO(csv_data.encode('utf-8')), "text/csv")}
    response = client.post("/api/catalog/upload?mode=atomic", headers=auth_headers, files=files)
    assert response.status_code == 400
    assert "negative" in response.json()["detail"].lower() or "validation" in response.json()["detail"].lower()

def test_csv_upload_atomic_vs_partial_mode():
    auth_headers = _get_auth("modes")
    # CSV containing 1 valid row and 1 invalid row (negative price)
    csv_data = (
        "sku,name,price,category,stock_count\n"
        "SKU-VALID-1,Good Saree,5000,Sarees,10\n"
        "SKU-INVALID-1,Bad Saree,-500,Sarees,2\n"
    )

    # 1. Test Atomic Mode (rejects entire file)
    files_atomic = {"file": ("atomic.csv", io.BytesIO(csv_data.encode('utf-8')), "text/csv")}
    res_atomic = client.post("/api/catalog/upload?mode=atomic", headers=auth_headers, files=files_atomic)
    assert res_atomic.status_code == 400

    # Ensure zero products were saved
    res_check1 = client.get("/api/catalog/products", headers=auth_headers)
    assert len(res_check1.json()) == 0

    # 2. Test Partial Mode (imports valid row, skips invalid row, reports error)
    files_partial = {"file": ("partial.csv", io.BytesIO(csv_data.encode('utf-8')), "text/csv")}
    res_partial = client.post("/api/catalog/upload?mode=partial", headers=auth_headers, files=files_partial)
    assert res_partial.status_code == 200
    data_p = res_partial.json()
    assert data_p["status"] == "partial_success"
    assert data_p["created"] == 1
    assert data_p["invalid_rows"] == 1
    assert len(data_p["errors"]) == 1

    # Ensure the 1 valid product is saved in database
    res_check2 = client.get("/api/catalog/products", headers=auth_headers)
    items_p = res_check2.json()
    assert len(items_p) == 1
    assert items_p[0]["sku"] == "SKU-VALID-1"

@patch("app.routers.catalog.generate_product_embedding_task")
@patch("app.ai.entity_extractor.extract_entities")
def test_deterministic_search_filters(mock_extract, mock_emb_task):
    mock_extract.return_value = {
        "color": "maroon",
        "fabric": "silk",
        "product_type": "saree",
        "budget_max": 15000
    }
    auth_headers = _get_auth("search")
    
    # Create test catalog items
    p1 = {
        "sku": "SKU-SR-01",
        "name": "Maroon Kanjeevaram Silk Saree",
        "price": 12000.0,
        "color": "Maroon",
        "fabric": "Silk",
        "category_name": "Sarees",
        "stock_count": 5
    }
    p2 = {
        "sku": "SKU-SR-02",
        "name": "Red Daily Cotton Saree",
        "price": 3000.0,
        "color": "Red",
        "fabric": "Cotton",
        "category_name": "Sarees",
        "stock_count": 0  # Out of stock
    }
    p3 = {
        "sku": "SKU-KT-01",
        "name": "Blue Designer Kurti",
        "price": 2500.0,
        "color": "Blue",
        "fabric": "Georgette",
        "category_name": "Kurtis",
        "stock_count": 12
    }
    assert client.post("/api/catalog/products", headers=auth_headers, json=p1).status_code == 201
    assert client.post("/api/catalog/products", headers=auth_headers, json=p2).status_code == 201
    assert client.post("/api/catalog/products", headers=auth_headers, json=p3).status_code == 201

    # Test 1: Search query with entity extraction (maroon silk saree under 15000)
    r1 = client.get("/api/catalog/products?q=maroon+silk+saree+under+15000", headers=auth_headers)
    assert r1.status_code == 200
    res1 = r1.json()
    assert len(res1) >= 1
    assert res1[0]["sku"] == "SKU-SR-01"

    # Test 2: In-stock filter strictly excludes out of stock items
    r2 = client.get("/api/catalog/products?in_stock=true", headers=auth_headers)
    assert r2.status_code == 200
    skus_instock = [x["sku"] for x in r2.json()]
    assert "SKU-SR-01" in skus_instock
    assert "SKU-KT-01" in skus_instock
    assert "SKU-SR-02" not in skus_instock

    # Test 3: Structured price range filter (max_price=5000)
    r3 = client.get("/api/catalog/products?max_price=5000", headers=auth_headers)
    assert r3.status_code == 200
    skus_cheap = [x["sku"] for x in r3.json()]
    assert "SKU-SR-02" in skus_cheap
    assert "SKU-KT-01" in skus_cheap
    assert "SKU-SR-01" not in skus_cheap

def test_tenant_isolation_same_sku_different_orgs():
    auth_org1 = _get_auth("iso1")
    auth_org2 = _get_auth("iso2")

    same_sku = "SKU-COMMON-99"
    prod_data = {
        "sku": same_sku,
        "name": "Shared SKU Product Name",
        "price": 1999.0,
        "color": "Green",
        "stock_count": 8
    }

    # Both org 1 and org 2 should create the same SKU without constraint violation
    res1 = client.post("/api/catalog/products", headers=auth_org1, json=prod_data)
    assert res1.status_code == 201
    
    res2 = client.post("/api/catalog/products", headers=auth_org2, json=prod_data)
    assert res2.status_code == 201

    # Query org1: gets 1 item
    get1 = client.get("/api/catalog/products", headers=auth_org1)
    assert len(get1.json()) == 1
    assert get1.json()[0]["id"] == res1.json()["id"]

    # Query org2: gets 1 item
    get2 = client.get("/api/catalog/products", headers=auth_org2)
    assert len(get2.json()) == 1
    assert get2.json()[0]["id"] == res2.json()["id"]
