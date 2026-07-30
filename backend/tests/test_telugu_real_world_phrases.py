import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.ai.intent_engine import classify_intent
from app.ai.entity_extractor import extract_entities, _rule_based_extract

def test_telugu_intents():
    # 1. "e saree undha?" (Is this saree available?) -> product_search or inventory_query
    assert classify_intent("e saree undha?") in ["product_search", "inventory_query"]

    # 2. "price entha andi" (What is the price?) -> product_search
    assert classify_intent("price entha andi") in ["product_search", "general_query"]

    # 3. "e designs lo vere sarees unnaya" (Are there other sarees in this design?) -> product_search or inventory_query
    assert classify_intent("e designs lo vere sarees unnaya") in ["product_search", "inventory_query", "product_visual_search"]

    # 4. "purple lo e design undha?" (Is this design available in purple?) -> product_search or inventory_query
    assert classify_intent("purple lo e design undha?") in ["product_search", "inventory_query"]

    # 5. "pink lo e design undha?" (Is this design available in pink?) -> product_search or inventory_query
    assert classify_intent("pink lo e design undha?") in ["product_search", "inventory_query"]

    # 6. "price thakkuva leva?" (Any lower price? / discount request) -> discount_request or product_search
    assert classify_intent("price thakkuva leva?") in ["discount_request", "product_search"]

    # 7. "2000 lo sarees unnaya?" (Are there sarees under 2000?) -> product_search or inventory_query
    assert classify_intent("2000 lo sarees unnaya?") in ["product_search", "inventory_query"]

    # 8. "2000 rs lo same elanti sarees leva/unnaya?" (Are there similar sarees under 2000 rs?) -> product_search or inventory_query
    assert classify_intent("2000 rs lo same elanti sarees leva/unnaya?") in ["product_search", "inventory_query"]


def test_telugu_entities():
    # Test rule-based extraction for Telugu budget suffix
    ent1 = _rule_based_extract("2000 lo sarees unnaya?")
    assert ent1["budget_max"] == 2000.0
    assert ent1["product_type"] == "Saree"

    ent2 = _rule_based_extract("2000 rs lo same elanti sarees leva/unnaya?")
    assert ent2["budget_max"] == 2000.0
    assert ent2["product_type"] == "Saree"

    ent3 = _rule_based_extract("purple lo e design undha?")
    assert ent3["color"] == "Purple"

    ent4 = _rule_based_extract("pink lo e design undha?")
    assert ent4["color"] == "Pink"
