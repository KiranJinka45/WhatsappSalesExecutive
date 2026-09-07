from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
import logging
from sqlalchemy.orm import Session

from .schemas import IntentExtraction, DraftGenerationResult, GroundedProductResult
from .intent_router import route_and_extract_intent
from .sql_executor import execute_deterministic_catalog_query
from .orchestrator import generate_reply
from .decision_engine import DecisionEngine
from .. import models
from ..connection_manager import manager

logger = logging.getLogger(__name__)

decision_engine_instance = DecisionEngine()


def execute_draft_generation_pipeline(
    db: Session,
    org: models.Organization,
    conversation: models.Conversation,
    customer_message_text: str,
    history: Optional[List[Dict[str, str]]] = None,
    detected_language: str = "en",
    detected_script: str = "latin"
) -> DraftGenerationResult:
    """
    Core 3-Layer Draft Generation Worker Pipeline:
    1. Layer 1: LLM Intent Router & Pydantic Extraction
    2. Layer 2: Deterministic SQL Catalog Querying (Tenant-Scoped via RLS)
    3. Layer 3: Grounded Draft Generation with Exact SQL Facts
    4. State Machine: Creates/Updates ApprovalRequest in WAITING_APPROVAL state.
    """
    history_list = history or []

    # ── Layer 1: LLM Intent Router ──────────────────────────────────────
    intent_extraction: IntentExtraction = route_and_extract_intent(
        customer_message_text,
        history=history_list
    )
    logger.info(f"Layer 1 Extraction: intent={intent_extraction.intent}, criteria={intent_extraction.product_search}")

    # ── Layer 2: Deterministic SQL Execution ────────────────────────────
    retrieved_products: List[GroundedProductResult] = []
    price_snapshot: Dict[str, float] = {}
    stock_snapshot: Dict[str, int] = {}

    if intent_extraction.intent in ["product_search", "stock_inquiry", "product_visual_search", "bargaining"]:
        retrieved_products, price_snapshot, stock_snapshot = execute_deterministic_catalog_query(
            db=db,
            org_id=org.id,
            criteria=intent_extraction.product_search,
            limit=5
        )
        logger.info(f"Layer 2 SQL Query retrieved {len(retrieved_products)} products for org {org.id}")

    # Format catalog context for generation
    catalog_context_dicts = [
        {
            "sku": p.sku,
            "name": p.name,
            "price": p.price,
            "color": p.color,
            "fabric": p.fabric,
            "stock_count": p.stock_count,
            "sizes": p.sizes,
            "image_urls": p.image_urls,
            "description": p.description
        }
        for p in retrieved_products
    ]

    # ── Layer 3: Grounded Draft Generation ──────────────────────────────
    policies_context = org.policies or {}
    proposed_response = generate_reply(
        customer_msg=customer_message_text,
        history=history_list,
        catalog_context=catalog_context_dicts,
        policies_context=policies_context,
        detected_language=detected_language,
        detected_script=detected_script,
        customer_name=conversation.customer_name or "Customer",
        brand_name=org.name
    )

    # Deterministic Decision Engine Evaluation
    decision = decision_engine_instance.evaluate(
        intent=intent_extraction.intent,
        policies=policies_context,
        grounding_valid=True,
        proposed_reply=proposed_response,
        entities=intent_extraction.product_search.model_dump() if intent_extraction.product_search else {},
        catalog_context=catalog_context_dicts
    )

    # ── State Machine Advancement: WAITING_APPROVAL ─────────────────────
    # Check if there is an existing pending approval request for this conversation
    approval = db.query(models.ApprovalRequest).filter(
        models.ApprovalRequest.conversation_id == conversation.id,
        models.ApprovalRequest.organization_id == org.id,
        models.ApprovalRequest.status.in_(["WAITING_APPROVAL", "DRAFT_READY"])
    ).first()

    retrieval_sku_list = [p.sku for p in retrieved_products]

    if not approval:
        approval = models.ApprovalRequest(
            conversation_id=conversation.id,
            organization_id=org.id,
            status="WAITING_APPROVAL",
            reason=decision.reason or f"Customer Inquiry: {intent_extraction.intent}",
            proposed_response=proposed_response,
            ai_recommendation=decision.ai_recommendation or "approve",
            risk_score=decision.risk_score,
            price_snapshot=price_snapshot,
            stock_snapshot=stock_snapshot,
            retrieval_ids=retrieval_sku_list,
            grounding_score=1.0,
            decision_engine_version="v2.0",
            rule_triggered=decision.rule_triggered,
            metadata_={
                "intent": intent_extraction.intent,
                "confidence": intent_extraction.confidence,
                "extraction_explanation": intent_extraction.explanation,
                "criteria": intent_extraction.product_search.model_dump() if intent_extraction.product_search else None
            }
        )
        db.add(approval)
    else:
        # Update existing draft
        approval.proposed_response = proposed_response
        approval.reason = decision.reason or f"Customer Inquiry: {intent_extraction.intent}"
        approval.ai_recommendation = decision.ai_recommendation or "approve"
        approval.risk_score = decision.risk_score
        approval.price_snapshot = price_snapshot
        approval.stock_snapshot = stock_snapshot
        approval.retrieval_ids = retrieval_sku_list
        approval.rule_triggered = decision.rule_triggered
        approval.status = "WAITING_APPROVAL"
        approval.metadata_ = {
            "intent": intent_extraction.intent,
            "confidence": intent_extraction.confidence,
            "extraction_explanation": intent_extraction.explanation,
            "criteria": intent_extraction.product_search.model_dump() if intent_extraction.product_search else None
        }

    # Update conversation status to WAITING_APPROVAL
    conversation.status = "WAITING_APPROVAL"
    conversation.escalation_reason = decision.reason
    db.commit()
    db.refresh(approval)

    # Broadcast real-time event to merchant dashboard
    try:
        manager.broadcast(str(org.id), "new_approval", {
            "approval_id": str(approval.id),
            "conversation_id": str(conversation.id),
            "status": approval.status,
            "reason": approval.reason,
            "risk_score": approval.risk_score,
            "proposed_response": approval.proposed_response,
            "retrieval_ids": approval.retrieval_ids
        })
    except Exception as broadcast_err:
        logger.warning(f"Failed to broadcast new_approval SSE event: {broadcast_err}")

    return DraftGenerationResult(
        intent_extraction=intent_extraction,
        retrieved_products=retrieved_products,
        price_snapshot=price_snapshot,
        stock_snapshot=stock_snapshot,
        proposed_response=proposed_response,
        grounding_score=1.0,
        action=decision.action,
        escalation_reason=decision.reason,
        risk_score=decision.risk_score,
        ai_recommendation=decision.ai_recommendation,
        rule_triggered=decision.rule_triggered,
        detected_language=detected_language,
        detected_script=detected_script
    )
