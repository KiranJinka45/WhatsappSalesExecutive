import pytest
from app.ai.decision_engine import DecisionEngine, DEFAULT_POLICIES

@pytest.fixture
def engine():
    return DecisionEngine()

def test_grounding_failure(engine):
    # Rule 1: grounding_valid = False
    result = engine.evaluate(
        intent="general_query",
        policies=DEFAULT_POLICIES,
        grounding_valid=False,
        proposed_reply="some reply",
        entities={},
        catalog_context=[{"sku": "123"}]
    )
    assert result.action == "wait_for_approval"
    assert result.risk_score == 85
    assert result.rule_triggered == "GROUNDING_FAILURE"

def test_complaint_escalation(engine):
    # Rule 2: intent = complaint
    result = engine.evaluate(
        intent="complaint",
        policies=DEFAULT_POLICIES,
        grounding_valid=True,
        proposed_reply="I am sorry",
        entities={},
        catalog_context=[]
    )
    assert result.action == "wait_for_approval"
    assert result.risk_score == 90
    assert result.rule_triggered == "COMPLAINT_ESCALATION"

def test_refund_policy_requires_owner(engine):
    # Rule 3: intent = refund, policy = requires owner
    policies = DEFAULT_POLICIES.copy()
    policies["refund_requires_owner"] = True
    result = engine.evaluate(
        intent="refund",
        policies=policies,
        grounding_valid=True,
        proposed_reply="Refund initiated",
        entities={},
        catalog_context=[]
    )
    assert result.action == "wait_for_approval"
    assert result.risk_score == 90
    assert result.rule_triggered == "REFUND_POLICY"

def test_refund_policy_auto(engine):
    # Rule 3: intent = refund, policy = auto
    policies = DEFAULT_POLICIES.copy()
    policies["refund_requires_owner"] = False
    result = engine.evaluate(
        intent="refund",
        policies=policies,
        grounding_valid=True,
        proposed_reply="Refund initiated",
        entities={},
        catalog_context=[]
    )
    assert result.action == "send"
    assert result.risk_score == 30
    assert result.rule_triggered == "REFUND_POLICY"

def test_discount_inquiry_policy_exceeded(engine):
    # Rule 4: intent = discount_inquiry, discount_limit = 0
    result = engine.evaluate(
        intent="discount_inquiry",
        policies=DEFAULT_POLICIES,
        grounding_valid=True,
        proposed_reply="Here is a 5% discount",
        entities={},
        catalog_context=[]
    )
    assert result.action == "wait_for_approval"
    assert result.risk_score == 80
    assert result.rule_triggered == "DISCOUNT_POLICY"

def test_discount_inquiry_policy_allowed(engine):
    # Rule 4: intent = discount_inquiry, discount_limit > 0
    policies = DEFAULT_POLICIES.copy()
    policies["discount_limit"] = 10
    result = engine.evaluate(
        intent="discount_inquiry",
        policies=policies,
        grounding_valid=True,
        proposed_reply="Here is a 5% discount",
        entities={},
        catalog_context=[]
    )
    assert result.action == "send"
    assert result.risk_score == 15
    assert result.rule_triggered == "DISCOUNT_POLICY"

def test_human_negotiation_policy(engine):
    # Rule 4b: intent = human_negotiation
    result = engine.evaluate(
        intent="human_negotiation",
        policies=DEFAULT_POLICIES,
        grounding_valid=True,
        proposed_reply="Can you bargain?",
        entities={},
        catalog_context=[]
    )
    assert result.action == "wait_for_approval"
    assert result.risk_score == 85
    assert result.rule_triggered == "HUMAN_NEGOTIATION"

def test_bulk_order_threshold_exceeded(engine):
    # Rule 5: bulk order >= threshold
    policies = DEFAULT_POLICIES.copy()
    policies["bulk_threshold"] = 5
    result = engine.evaluate(
        intent="bulk_order",
        policies=policies,
        grounding_valid=True,
        proposed_reply="Sure",
        entities={"quantity": 10},
        catalog_context=[]
    )
    assert result.action == "wait_for_approval"
    assert result.risk_score == 60
    assert result.rule_triggered == "BULK_THRESHOLD"
    assert "meets/exceeds threshold" in result.reason

def test_bulk_order_below_threshold(engine):
    # Rule 5: bulk order < threshold
    policies = DEFAULT_POLICIES.copy()
    policies["bulk_threshold"] = 20
    result = engine.evaluate(
        intent="bulk_order",
        policies=policies,
        grounding_valid=True,
        proposed_reply="Sure",
        entities={"quantity": 10},
        catalog_context=[]
    )
    assert result.action == "wait_for_approval"
    assert result.risk_score == 45
    assert result.rule_triggered == "BULK_THRESHOLD"
    assert "below threshold" not in result.reason  # message just says detected

def test_bulk_order_invalid_quantity(engine):
    result = engine.evaluate(
        intent="bulk_order",
        policies=DEFAULT_POLICIES,
        grounding_valid=True,
        proposed_reply="Sure",
        entities={"quantity": "many"},
        catalog_context=[]
    )
    assert result.action == "wait_for_approval"
    assert result.risk_score == 45
    assert result.rule_triggered == "BULK_THRESHOLD"

def test_shipping_exception_no_night_delivery(engine):
    policies = DEFAULT_POLICIES.copy()
    policies["night_delivery_enabled"] = False
    result = engine.evaluate(
        intent="shipping_exception",
        policies=policies,
        grounding_valid=True,
        proposed_reply="Okay",
        entities={},
        catalog_context=[]
    )
    assert result.action == "wait_for_approval"
    assert result.risk_score == 50
    assert result.rule_triggered == "SHIPPING_EXCEPTION"

def test_shipping_exception_night_delivery(engine):
    policies = DEFAULT_POLICIES.copy()
    policies["night_delivery_enabled"] = True
    result = engine.evaluate(
        intent="shipping_exception",
        policies=policies,
        grounding_valid=True,
        proposed_reply="Okay",
        entities={},
        catalog_context=[]
    )
    assert result.action == "send"
    assert result.risk_score == 15
    assert result.rule_triggered == "SHIPPING_EXCEPTION"

def test_inventory_query_no_reservation(engine):
    policies = DEFAULT_POLICIES.copy()
    policies["reservation_enabled"] = False
    result = engine.evaluate(
        intent="inventory_query",
        policies=policies,
        grounding_valid=True,
        proposed_reply="I will hold it",
        entities={},
        catalog_context=[]
    )
    assert result.action == "wait_for_approval"
    assert result.risk_score == 40
    assert result.rule_triggered == "INVENTORY_RESERVATION"

def test_inventory_query_reservation(engine):
    policies = DEFAULT_POLICIES.copy()
    policies["reservation_enabled"] = True
    result = engine.evaluate(
        intent="inventory_query",
        policies=policies,
        grounding_valid=True,
        proposed_reply="I will hold it",
        entities={},
        catalog_context=[]
    )
    assert result.action == "send"
    assert result.risk_score == 10
    assert result.rule_triggered == "INVENTORY_RESERVATION"

def test_out_of_catalog(engine):
    result = engine.evaluate(
        intent="product_search",
        policies=DEFAULT_POLICIES,
        grounding_valid=True,
        proposed_reply="I couldn't find it",
        entities={},
        catalog_context=[]
    )
    assert result.action == "wait_for_approval"
    assert result.risk_score == 35
    assert result.rule_triggered == "OUT_OF_CATALOG"

def test_default_send(engine):
    result = engine.evaluate(
        intent="product_search",
        policies=DEFAULT_POLICIES,
        grounding_valid=True,
        proposed_reply="Here is the item",
        entities={},
        catalog_context=[{"sku": "999"}]
    )
    assert result.action == "send"
    assert result.risk_score == 10
    assert result.rule_triggered == "NONE"

def test_default_send_general(engine):
    result = engine.evaluate(
        intent="general_query",
        policies=DEFAULT_POLICIES,
        grounding_valid=True,
        proposed_reply="We are open 9 to 5",
        entities={},
        catalog_context=[]
    )
    assert result.action == "send"
    assert result.risk_score == 10
    assert result.rule_triggered == "NONE"

# Additional edge cases

def test_grounding_failure_overrides_everything(engine):
    # Even if intent is general_query which normally sends, grounding failure overrides
    result = engine.evaluate(
        intent="general_query",
        policies=DEFAULT_POLICIES,
        grounding_valid=False,
        proposed_reply="Hallucinated open hours",
        entities={},
        catalog_context=[]
    )
    assert result.action == "wait_for_approval"
    assert result.rule_triggered == "GROUNDING_FAILURE"

def test_complaint_overrides_bulk(engine):
    # A complaint about a bulk order should trigger COMPLAINT (higher priority)
    result = engine.evaluate(
        intent="complaint",
        policies=DEFAULT_POLICIES,
        grounding_valid=True,
        proposed_reply="Sorry about that",
        entities={"quantity": 100},
        catalog_context=[]
    )
    assert result.action == "wait_for_approval"
    assert result.rule_triggered == "COMPLAINT_ESCALATION"

def test_bulk_order_with_none_quantity(engine):
    result = engine.evaluate(
        intent="bulk_order",
        policies=DEFAULT_POLICIES,
        grounding_valid=True,
        proposed_reply="Sure",
        entities={"quantity": None},
        catalog_context=[]
    )
    assert result.rule_triggered == "BULK_THRESHOLD"
    assert result.risk_score == 45
