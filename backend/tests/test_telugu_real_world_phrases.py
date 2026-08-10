import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.ai.intent_engine import classify_intent
from app.ai.entity_extractor import extract_entities, _rule_based_extract

def test_telugu_intent_inventory_saree():
    # 1. "e saree undha?" (Is this saree available?)
    assert classify_intent("e saree undha?") in ["product_search", "inventory_query"]

def test_telugu_intent_general_price():
    # 2. "price entha andi" (What is the price?)
    assert classify_intent("price entha andi") in ["product_search", "general_query"]

def test_telugu_intent_design_inventory():
    # 3. "e designs lo vere sarees unnaya" (Are there other sarees in this design?)
    assert classify_intent("e designs lo vere sarees unnaya") in ["product_search", "inventory_query", "product_visual_search"]

def test_telugu_intent_color_inventory_purple():
    # 4. "purple lo e design undha?" (Is this design available in purple?)
    assert classify_intent("purple lo e design undha?") in ["product_search", "inventory_query"]

def test_telugu_intent_color_inventory_pink():
    # 5. "pink lo e design undha?" (Is this design available in pink?)
    assert classify_intent("pink lo e design undha?") in ["product_search", "inventory_query"]

def test_telugu_intent_budget_search():
    # 7. "2000 lo sarees unnaya?" (Are there sarees under 2000?)
    assert classify_intent("2000 lo sarees unnaya?") in ["product_search", "inventory_query"]

def test_telugu_intent_budget_search_ambiguous_leva():
    # 8. "2000 rs lo same elanti sarees leva/unnaya?" (Are there similar sarees under 2000 rs?)
    assert classify_intent("2000 rs lo same elanti sarees leva/unnaya?") in ["product_search", "inventory_query"]

def test_telugu_intent_negotiation_konchem_thagginchandi():
    # 9. "konchem thagginchandi" (Reduce a little bit - soft bargaining)
    assert classify_intent("konchem thagginchandi") == "human_negotiation"

def test_telugu_intent_negotiation_maku_konchem_thagginchi_ivvandi():
    # 10. "maku konchem thagginchi ivvandi" (Give us a little reduction)
    assert classify_intent("maku konchem thagginchi ivvandi") == "human_negotiation"

def test_telugu_intent_discount_inquiry_standard():
    # 11. "discounts emaina unnaya?" (Are there any discounts available? - standard inquiry)
    assert classify_intent("discounts emaina unnaya?") == "discount_inquiry"

def test_telugu_intent_negotiation_best_price():
    # 12. "best price cheppandi" (Tell me the best price - soft negotiation)
    assert classify_intent("best price cheppandi") == "human_negotiation"

def test_telugu_intent_negotiation_held_out_phrase_1():
    # Held-out testing: "final ga entha ki istharu?" (Finally, for how much will you give it?)
    # Does not contain "discount", "thagginchandi", or "price" 
    assert classify_intent("final ga entha ki istharu?") == "human_negotiation"

def test_telugu_intent_negotiation_held_out_phrase_2():
    # Held-out testing: "malli adagakunda oka mata cheppandi" (Tell me one word/price without asking again - standard haggling phrase)
    assert classify_intent("malli adagakunda oka mata cheppandi") == "human_negotiation"

def test_telugu_intent_budget_held_out_phrase():
    # Held-out testing: "1500 lopu emaina chuppinchandi" (Show me something inside/below 1500)
    # Does not use "lo" or "leva", uses "lopu" (below/inside)
    assert classify_intent("1500 lopu emaina chuppinchandi") in ["product_search", "inventory_query"]


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
