import pytest
from decimal import Decimal
from unittest.mock import MagicMock
from app.catalog_service import parse_and_sync_catalog, CatalogRow
from app.ai.policy_validator import validate_reply
from app.ai.entity_extractor import extract_entities
from pydantic import ValidationError

def test_catalog_row_validation_valid():
    row_data = {
        "sku": "SKU001",
        "name": "Silk Kurtis",
        "price": Decimal("1299.00"),
        "color": "Blue",
        "category_name": "Ethnic",
        "gender": "Women",
        "fabric": "Silk",
        "description": "Lovely kurti",
        "stock_count": 10,
        "sizes": ["S", "M", "L"],
        "image_urls": ["https://example.com/img1.jpg"],
        "video_urls": ["https://example.com/vid1.mp4"]
    }
    row = CatalogRow(**row_data)
    assert row.sku == "SKU001"
    assert row.price == Decimal("1299.00")
    assert row.stock_count == 10

def test_catalog_row_validation_invalid():
    # Price is negative
    row_data = {
        "sku": "SKU001",
        "name": "Silk Kurtis",
        "price": Decimal("-5.00"),
        "color": "Blue",
        "category_name": "Ethnic",
        "gender": "Women",
        "fabric": "Silk",
        "stock_count": 10,
    }
    with pytest.raises(ValidationError):
        CatalogRow(**row_data)

def test_policy_validator():
    catalog_context = [
        {"sku": "SKU001", "name": "Silk Kurtis", "price": Decimal("1200.00"), "stock_count": 0}
    ]
    policies_context = {}
    
    # Test price mismatch
    is_valid, corrected, violations = validate_reply("This kurti costs INR 1500.", catalog_context, policies_context)
    assert is_valid is False
    assert len(violations) > 0
    assert "Price 1500 does not match catalog" in violations[0]
    
    # Test stock mismatch
    is_valid, corrected, violations = validate_reply("The Silk Kurtis is available.", catalog_context, policies_context)
    assert is_valid is False
    assert len(violations) > 0
    assert "out of stock" in violations[0]
