from typing import List, Dict, Any, Tuple
import re
import logging

logger = logging.getLogger(__name__)

# Decision Engine version - bump this on every rule-set change
DECISION_ENGINE_VERSION = "v2.0"

# Default merchant policy values (used when merchant has not configured them)
DEFAULT_POLICIES = {
    "bulk_threshold": 10,
    "discount_limit": 0,        # 0 means any discount request triggers approval
    "reservation_enabled": False,
    "refund_requires_owner": True,
    "night_delivery_enabled": False,
}


class DecisionResult:
    """Structured result from the Decision Engine evaluation."""
    __slots__ = (
        "action", "reason", "risk_score", "ai_recommendation", "rule_triggered"
    )

    def __init__(
        self,
        action: str,
        reason: str,
        risk_score: int,
        ai_recommendation: str,
        rule_triggered: str,
    ):
        self.action = action
        self.reason = reason
        self.risk_score = risk_score
        self.ai_recommendation = ai_recommendation
        self.rule_triggered = rule_triggered

    def as_tuple(self) -> Tuple[str, str, int, str, str]:
        return (
            self.action,
            self.reason,
            self.risk_score,
            self.ai_recommendation,
            self.rule_triggered,
        )


def _get_policy(policies: Dict[str, Any], key: str) -> Any:
    """Read a policy value, falling back to DEFAULT_POLICIES."""
    return policies.get(key, DEFAULT_POLICIES.get(key))


class DecisionEngine:
    """
    Fully deterministic decision engine.
    No LLM calls. No model inference. Pure rules.

    Consumes:
        - intent (str): structured intent from the Intent Classifier
        - policies (dict): merchant-configurable policy thresholds
        - grounding_valid (bool): whether the Grounding Validator passed
        - proposed_reply (str): the LLM-generated reply (for inspection only)
        - entities (dict): extracted entities (e.g. quantity parsed from message)
        - catalog_context (list): retrieved catalog items

    Returns:
        DecisionResult with action, reason, risk_score, ai_recommendation,
        and rule_triggered.
    """

    def evaluate(
        self,
        intent: str,
        policies: Dict[str, Any],
        grounding_valid: bool,
        proposed_reply: str,
        entities: Dict[str, Any],
        catalog_context: List[Dict[str, Any]],
    ) -> DecisionResult:
        """
        Deterministic decision routing.
        Evaluates rules in priority order and returns the first match.
        """

        # ── 1. Grounding failure (highest priority) ──────────────────────
        if not grounding_valid:
            return DecisionResult(
                action="wait_for_approval",
                reason="Grounding validation failed – potential hallucination detected",
                risk_score=85,
                ai_recommendation="reject",
                rule_triggered="GROUNDING_FAILURE",
            )

        # ── 2. Complaint ─────────────────────────────────────────────────
        if intent == "complaint":
            return DecisionResult(
                action="wait_for_approval",
                reason="Customer complaint or defect report detected",
                risk_score=90,
                ai_recommendation="reject",
                rule_triggered="COMPLAINT_ESCALATION",
            )

        # ── 3. Refund ────────────────────────────────────────────────────
        if intent == "refund":
            if _get_policy(policies, "refund_requires_owner"):
                return DecisionResult(
                    action="wait_for_approval",
                    reason="Refund request requires owner approval (policy: refund_requires_owner=True)",
                    risk_score=90,
                    ai_recommendation="reject",
                    rule_triggered="REFUND_POLICY",
                )
            # Policy allows AI to handle refunds autonomously
            return DecisionResult(
                action="send",
                reason="Refund handled autonomously (policy: refund_requires_owner=False)",
                risk_score=30,
                ai_recommendation="approve",
                rule_triggered="REFUND_POLICY",
            )

        # ── 4. Discount inquiry ──────────────────────────────────────────
        if intent == "discount_inquiry":
            discount_limit = _get_policy(policies, "discount_limit")
            if discount_limit > 0:
                return DecisionResult(
                    action="send",
                    reason=f"Discount inquiry handled autonomously (policy: discount_limit={discount_limit}%)",
                    risk_score=15,
                    ai_recommendation="approve",
                    rule_triggered="DISCOUNT_POLICY",
                )
            return DecisionResult(
                action="wait_for_approval",
                reason=f"Discount inquiry detected – exceeds policy limit of {discount_limit}%",
                risk_score=80,
                ai_recommendation="reject",
                rule_triggered="DISCOUNT_POLICY",
            )

        # ── 4b. Human negotiation ────────────────────────────────────────
        if intent == "human_negotiation":
            return DecisionResult(
                action="wait_for_approval",
                reason="Custom discount negotiation or bargaining detected – requires human intervention",
                risk_score=85,
                ai_recommendation="reject",
                rule_triggered="HUMAN_NEGOTIATION",
            )

        # ── 5. Bulk order ────────────────────────────────────────────────
        if intent == "bulk_order":
            threshold = _get_policy(policies, "bulk_threshold")
            # Try to parse a quantity from entities
            qty = entities.get("quantity")
            if qty is None:
                # Fall back to scanning the proposed reply / entities for numbers
                qty = 0
            try:
                qty = int(qty)
            except (TypeError, ValueError):
                qty = 0

            if qty >= threshold:
                return DecisionResult(
                    action="wait_for_approval",
                    reason=f"Bulk order quantity ({qty}) meets/exceeds threshold ({threshold})",
                    risk_score=60,
                    ai_recommendation="approve",
                    rule_triggered="BULK_THRESHOLD",
                )
            # Even below threshold, bulk intent still gets flagged
            return DecisionResult(
                action="wait_for_approval",
                reason=f"Bulk/wholesale inquiry detected (quantity: {qty}, threshold: {threshold})",
                risk_score=45,
                ai_recommendation="approve",
                rule_triggered="BULK_THRESHOLD",
            )

        # ── 6. Shipping exception ────────────────────────────────────────
        if intent == "shipping_exception":
            if not _get_policy(policies, "night_delivery_enabled"):
                return DecisionResult(
                    action="wait_for_approval",
                    reason="Urgent/express shipping request – night delivery is disabled",
                    risk_score=50,
                    ai_recommendation="reject",
                    rule_triggered="SHIPPING_EXCEPTION",
                )
            return DecisionResult(
                action="send",
                reason="Shipping query handled autonomously (night_delivery_enabled=True)",
                risk_score=15,
                ai_recommendation="approve",
                rule_triggered="SHIPPING_EXCEPTION",
            )

        # ── 7. Inventory reservation ─────────────────────────────────────
        if intent == "inventory_query":
            if not _get_policy(policies, "reservation_enabled"):
                return DecisionResult(
                    action="wait_for_approval",
                    reason="Inventory hold/reservation requested – reservations are disabled",
                    risk_score=40,
                    ai_recommendation="reject",
                    rule_triggered="INVENTORY_RESERVATION",
                )
            # Reservations enabled – allow AI to handle
            return DecisionResult(
                action="send",
                reason="Inventory query handled autonomously (reservation_enabled=True)",
                risk_score=10,
                ai_recommendation="approve",
                rule_triggered="INVENTORY_RESERVATION",
            )

        # ── 8. Product search with no catalog results ────────────────────
        if intent == "product_search" and not catalog_context:
            return DecisionResult(
                action="wait_for_approval",
                reason="No matching products found in catalog for customer query",
                risk_score=35,
                ai_recommendation="reject",
                rule_triggered="OUT_OF_CATALOG",
            )

        # ── 9. Default: autonomously handle ──────────────────────────────
        return DecisionResult(
            action="send",
            reason="Autonomously handled – no policy rules triggered",
            risk_score=10,
            ai_recommendation="approve",
            rule_triggered="NONE",
        )


# Global engine instance
decision_engine = DecisionEngine()
