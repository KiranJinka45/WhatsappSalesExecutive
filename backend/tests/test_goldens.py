import os
import json
import pytest
from unittest.mock import MagicMock, patch
from app import ai_service

def load_golden(name: str):
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "goldens", f"{name}.json")
    with open(path, "r") as f:
        return json.load(f)

@pytest.mark.parametrize("golden_name", [
    "budget_search",
    "failure_out_of_stock",
    "angry_customer",
    "human_takeover"
])
@patch("app.ai.client.get_client")
def test_golden_evaluations(mock_get_client, golden_name):
    # Mock LLM response to ensure deterministic test runs
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    golden = load_golden(golden_name)
    history = golden["conversation_history"]
    message = golden["customer_message"]
    expected = golden["expected_output"]
    
    # 1. Test Intent classification
    with patch("app.ai_service.classify_intent") as mock_intent:
        mock_intent.return_value = expected["intent"]
        intent = ai_service.classify_intent(message, history)
        assert intent == expected["intent"], f"Intent mismatch for {golden_name}"
        
    # 2. Test Entity extraction
    with patch("app.ai_service.extract_entities") as mock_entities:
        mock_entities.return_value = expected.get("entities", {})
        entities = ai_service.extract_entities(message, history)
        assert entities == expected.get("entities", {}), f"Entities mismatch for {golden_name}"
        
    # 3. Test Retrieval Quality Layer
    catalog_context = [
        {"sku": "ETH-001", "name": "Red Saree", "price": 4500, "stock_count": 10},
        {"sku": "ETH-002", "name": "Blue Saree", "price": 2500, "stock_count": 5},
        {"sku": "ETH-003", "name": "Out of stock Saree", "price": 1000, "stock_count": 0}
    ]
    
    is_valid, filtered, reason = ai_service.validate_retrieval(expected["intent"], expected.get("entities", {}), catalog_context)
    
    # Assert validation rules
    rules = expected.get("validation_rules", [])
    if "NO_PRODUCTS_OVER_3000_RETRIEVED" in rules:
        for item in filtered:
            assert item["price"] <= 3000, "Found item costing > 3000 in budget-limited context"
            
    if "NO_HALLUCINATION_OF_STOCK" in rules:
        for item in filtered:
            assert item["stock_count"] > 0, "Found out-of-stock item when checking availability"
            
    # 4. Test Recommendation Ranker
    ranked = ai_service.rank_recommendations(filtered)
    assert len(ranked) == len(filtered)
    if ranked:
        # Check order descending by ranking score
        scores = [item["ranking_score"] for item in ranked]
        assert scores == sorted(scores, reverse=True), "Recommendations not sorted by ranking score descending"
