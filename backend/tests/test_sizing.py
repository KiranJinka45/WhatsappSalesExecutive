import pytest
from app.ai.retrieval_validator import validate_retrieval, normalize_size

def test_normalize_size():
    assert normalize_size("38") == "m"
    assert normalize_size("36") == "s"
    assert normalize_size("40") == "l"
    assert normalize_size("42") == "xl"
    assert normalize_size("44") == "xxl"
    assert normalize_size("Medium") == "m"
    assert normalize_size("small") == "s"
    assert normalize_size("Free Size") == "free size"
    assert normalize_size("") == ""

def test_validate_retrieval_size_free_size():
    # Free size matches any requested size (sarees fit all sizes)
    catalog = [
        {"sku": "SKU001", "price": 1000, "sizes": ["Free Size"], "stock_count": 5}
    ]
    
    # 1. Asking for size M
    is_valid, filtered, msg = validate_retrieval("product_search", {"size": "M"}, catalog)
    assert is_valid is True
    assert len(filtered) == 1

    # 2. Asking for size 38
    is_valid, filtered, msg = validate_retrieval("product_search", {"size": "38"}, catalog)
    assert is_valid is True
    assert len(filtered) == 1

def test_validate_retrieval_size_strict():
    catalog = [
        {"sku": "SKU_S", "price": 1000, "sizes": ["S"], "stock_count": 5},
        {"sku": "SKU_M_L", "price": 1200, "sizes": ["M", "L"], "stock_count": 5}
    ]

    # 1. Ask for size M -> should return SKU_M_L
    is_valid, filtered, msg = validate_retrieval("product_search", {"size": "M"}, catalog)
    assert is_valid is True
    assert len(filtered) == 1
    assert filtered[0]["sku"] == "SKU_M_L"

    # 2. Ask for size 38 (maps to M) -> should return SKU_M_L
    is_valid, filtered, msg = validate_retrieval("product_search", {"size": "38"}, catalog)
    assert is_valid is True
    assert len(filtered) == 1
    assert filtered[0]["sku"] == "SKU_M_L"

    # 3. Ask for size 36 (maps to S) -> should return SKU_S
    is_valid, filtered, msg = validate_retrieval("product_search", {"size": "36"}, catalog)
    assert is_valid is True
    assert len(filtered) == 1
    assert filtered[0]["sku"] == "SKU_S"

    # 4. Ask for size XL -> should return nothing and fail validation
    is_valid, filtered, msg = validate_retrieval("product_search", {"size": "XL"}, catalog)
    assert is_valid is False
    assert len(filtered) == 0
    assert "size" in msg
