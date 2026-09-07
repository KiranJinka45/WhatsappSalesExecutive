import uuid
import pytest
from sqlalchemy import text
from tests.conftest import TestingSessionLocal, clean_tables
from app import models
from app.ai.schemas import (
    IntentExtraction, ProductSearchCriteria, GroundedProductResult, DraftGenerationResult
)
from app.ai.intent_router import route_and_extract_intent, _fallback_rule_extraction
from app.ai.sql_executor import execute_deterministic_catalog_query
from app.ai.draft_pipeline import execute_draft_generation_pipeline


@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield


def _create_sample_tenant_and_catalog(db):
    """Helper to create two isolated tenants with products for RLS and SQL query testing."""
    org1 = models.Organization(
        name="Pushpalatha Silks",
        whatsapp_number="+919876543210",
        policies={"operating_mode": "HUMAN_APPROVAL", "shadow_mode": False}
    )
    org2 = models.Organization(
        name="Kalyan Sarees",
        whatsapp_number="+919876543211",
        policies={"operating_mode": "HUMAN_APPROVAL", "shadow_mode": False}
    )
    db.add_all([org1, org2])
    db.commit()

    # Add products for Org 1
    p1 = models.Product(
        organization_id=org1.id,
        sku="SKU-MAROON-SILK-01",
        name="Maroon Pure Silk Kanjeevaram Saree",
        price=3500.0,
        stock_count=5,
        color="Maroon",
        fabric="Silk",
        sizes=["Free Size"],
        description="Handwoven pure silk saree in deep maroon shade."
    )
    p2 = models.Product(
        organization_id=org1.id,
        sku="SKU-BLUE-COTTON-02",
        name="Royal Blue Daily Wear Cotton Saree",
        price=1200.0,
        stock_count=10,
        color="Blue",
        fabric="Cotton",
        sizes=["Free Size"],
        description="Breathable cotton saree for daily wear."
    )
    p3 = models.Product(
        organization_id=org1.id,
        sku="SKU-GREEN-SILK-OUTOFSTOCK",
        name="Emerald Green Silk Saree",
        price=3800.0,
        stock_count=0,
        color="Green",
        fabric="Silk",
        sizes=["Free Size"],
        description="Emerald green festive silk saree."
    )

    # Add product for Org 2 (to test tenant isolation)
    p4 = models.Product(
        organization_id=org2.id,
        sku="SKU-ORG2-MAROON-SILK",
        name="Competitor Maroon Silk Saree",
        price=2999.0,
        stock_count=8,
        color="Maroon",
        fabric="Silk"
    )
    db.add_all([p1, p2, p3, p4])
    db.commit()

    return org1, org2, [p1, p2, p3, p4]


def test_layer1_pydantic_intent_extraction():
    """Verify Pydantic schemas enforce type safety and parse structured shopping criteria."""
    criteria = ProductSearchCriteria(
        product_type="Saree",
        color="Maroon",
        fabric="Silk",
        budget_max=4000.0,
        is_in_stock_only=True
    )
    assert criteria.product_type == "Saree"
    assert criteria.budget_max == 4000.0
    assert criteria.is_in_stock_only is True

    intent_ext = IntentExtraction(
        intent="product_search",
        confidence=0.98,
        explanation="Customer asked for maroon silk saree under 4000",
        product_search=criteria
    )
    assert intent_ext.intent == "product_search"
    assert intent_ext.product_search.color == "Maroon"

    raw_msg = "Do you have a maroon silk saree under ₹4,000?"
    fallback_ext = _fallback_rule_extraction(raw_msg)
    assert fallback_ext.intent == "product_search"
    assert fallback_ext.product_search is not None
    assert fallback_ext.product_search.color == "Maroon"
    assert fallback_ext.product_search.fabric == "Silk"
    assert fallback_ext.product_search.product_type == "Saree"
    assert fallback_ext.product_search.budget_max == 4000.0


def test_layer2_deterministic_sql_execution_and_tenant_isolation():
    """Verify SQL executor strictly queries the DB under tenant isolation and enforces filters."""
    db = TestingSessionLocal()
    try:
        org1, org2, _ = _create_sample_tenant_and_catalog(db)

        # 1. Search for Maroon Silk Saree under 4000 in Org 1
        criteria = ProductSearchCriteria(
            product_type="Saree",
            color="Maroon",
            fabric="Silk",
            budget_max=4000.0,
            is_in_stock_only=True
        )
        results, price_snap, stock_snap = execute_deterministic_catalog_query(
            db=db,
            org_id=org1.id,
            criteria=criteria
        )

        assert len(results) == 1
        assert results[0].sku == "SKU-MAROON-SILK-01"
        assert results[0].price == 3500.0
        assert results[0].stock_count == 5
        assert price_snap == {"SKU-MAROON-SILK-01": 3500.0}
        assert stock_snap == {"SKU-MAROON-SILK-01": 5}

        # Verify out-of-stock items (SKU-GREEN-SILK-OUTOFSTOCK) are excluded when is_in_stock_only=True
        green_criteria = ProductSearchCriteria(color="Green", is_in_stock_only=True)
        green_results, _, _ = execute_deterministic_catalog_query(db, org1.id, green_criteria)
        assert not any(p.sku == "SKU-GREEN-SILK-OUTOFSTOCK" for p in green_results)

        # 2. Strict Tenant Isolation Check: Org 1 search MUST NEVER return Org 2 products
        all_org1_results, _, _ = execute_deterministic_catalog_query(db, org1.id, ProductSearchCriteria())
        assert not any(p.sku == "SKU-ORG2-MAROON-SILK" for p in all_org1_results)

        # Querying Org 2 should only return Org 2's products
        all_org2_results, _, _ = execute_deterministic_catalog_query(db, org2.id, ProductSearchCriteria())
        assert len(all_org2_results) == 1
        assert all_org2_results[0].sku == "SKU-ORG2-MAROON-SILK"
    finally:
        db.close()


def test_layer3_draft_generation_and_state_machine_advancement():
    """Verify full end-to-end Draft Generation Worker creates WAITING_APPROVAL ApprovalRequest."""
    db = TestingSessionLocal()
    try:
        org1, _, _ = _create_sample_tenant_and_catalog(db)
        conv = models.Conversation(
            organization_id=org1.id,
            customer_phone="+919876500000",
            customer_name="Ananya Sharma",
            status="AI_ACTIVE"
        )
        db.add(conv)
        db.commit()

        user_msg = "Namaste! Do you have a maroon silk saree under 4000 rupees?"

        result: DraftGenerationResult = execute_draft_generation_pipeline(
            db=db,
            org=org1,
            conversation=conv,
            customer_message_text=user_msg,
            history=[],
            detected_language="en",
            detected_script="latin"
        )

        # Assert Pipeline Output
        assert result.intent_extraction.intent == "product_search"
        assert len(result.retrieved_products) > 0
        assert "SKU-MAROON-SILK-01" in result.price_snapshot
        assert result.price_snapshot["SKU-MAROON-SILK-01"] == 3500.0
        assert result.stock_snapshot["SKU-MAROON-SILK-01"] == 5
        assert result.proposed_response != ""

        # Assert State Machine advancement in Database
        db.refresh(conv)
        assert conv.status == "WAITING_APPROVAL"

        approval = db.query(models.ApprovalRequest).filter(
            models.ApprovalRequest.conversation_id == conv.id,
            models.ApprovalRequest.organization_id == org1.id
        ).first()

        assert approval is not None
        assert approval.status == "WAITING_APPROVAL"
        assert approval.proposed_response == result.proposed_response
        assert approval.retrieval_ids == ["SKU-MAROON-SILK-01"]
        assert approval.price_snapshot == {"SKU-MAROON-SILK-01": 3500.0}
        assert approval.stock_snapshot == {"SKU-MAROON-SILK-01": 5}
        assert approval.grounding_score == 1.0
    finally:
        db.close()
