import pytest
from unittest.mock import patch, MagicMock
from app.ai.intent_engine import classify_intent
from app.ai.entity_extractor import extract_entities

def test_visual_search_intent_classification():
    # 1. Test visual search classification with explicit keywords
    intent = classify_intent("send me pics of Kanjeevaram sarees")
    assert intent == "product_visual_search"

    intent = classify_intent("saree photos and price please")
    assert intent == "product_visual_search"

    intent = classify_intent("Dharmavaram sarees under 3000 photo pettu")
    assert intent == "product_visual_search"

def test_visual_search_entity_extraction():
    # Patch generate_content to return None response text to force local rule-based extractor fallback
    with patch("app.ai.entity_extractor.generate_content") as mock_gen:
        mock_gen.return_value = MagicMock(text=None)
        
        # Test budget range fallback entity extraction
        entities = extract_entities("sarees between 2000 and 4000")
        assert entities.get("budget_min") == 2000.0
        assert entities.get("budget_max") == 4000.0

        entities = extract_entities("Dharmavaram sarees under 3000")
        assert entities.get("budget_max") == 3000.0
        assert entities.get("budget_min") is None

        entities = extract_entities("sarees starting from 1500")
        assert entities.get("budget_min") == 1500.0
        assert entities.get("budget_max") is None
