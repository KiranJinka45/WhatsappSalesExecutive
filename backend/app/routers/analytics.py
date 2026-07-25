from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from .. import models, security

router = APIRouter(prefix="/api/analytics", tags=["analytics"], responses={401: {"description": "Unauthorized"}})


@router.get("/dashboard")
def dashboard_summary(
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
):
    """
    Auth-protected dashboard summary.
    Returns conversation counts, product/message totals, AI rates,
    and actual business metrics (revenue, orders, top products) from DB.
    """
    # Total conversations
    total_conversations = (
        db.query(func.count(models.Conversation.id))
        .filter(models.Conversation.organization_id == org.id)
        .scalar()
    ) or 0

    # Conversations by status
    status_counts = (
        db.query(models.Conversation.status, func.count(models.Conversation.id))
        .filter(models.Conversation.organization_id == org.id)
        .group_by(models.Conversation.status)
        .all()
    )
    by_status = {row[0]: row[1] for row in status_counts}
    ai_active_count = by_status.get("AI_ACTIVE", 0)
    waiting_approval_count = by_status.get("WAITING_APPROVAL", 0)
    owner_active_count = by_status.get("OWNER_ACTIVE", 0)
    closed_count = by_status.get("CLOSED", 0)

    # Total products
    total_products = (
        db.query(func.count(models.Product.id))
        .filter(models.Product.organization_id == org.id)
        .scalar()
    ) or 0

    # Total messages
    total_messages = (
        db.query(func.count(models.Message.id))
        .join(models.Conversation, models.Message.conversation_id == models.Conversation.id)
        .filter(models.Conversation.organization_id == org.id)
        .scalar()
    ) or 0

    # Conversations created in last 24h
    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    conversations_today = (
        db.query(func.count(models.Conversation.id))
        .filter(
            models.Conversation.organization_id == org.id,
            models.Conversation.created_at >= twenty_four_hours_ago,
        )
        .scalar()
    ) or 0

    # Rates
    # Takeovers are WAITING_APPROVAL + OWNER_ACTIVE
    human_takeover_count = waiting_approval_count + owner_active_count
    ai_containment_rate = (
        round(((total_conversations - human_takeover_count) / total_conversations) * 100, 2)
        if total_conversations > 0
        else 100.0
    )

    # Actual Business Metrics from Orders table
    orders_started = (
        db.query(func.count(models.Order.id))
        .filter(models.Order.organization_id == org.id)
        .scalar()
    ) or 0

    orders_completed = (
        db.query(func.count(models.Order.id))
        .filter(
            models.Order.organization_id == org.id,
            models.Order.status.in_(["paid", "shipped", "delivered"])
        )
        .scalar()
    ) or 0

    revenue_influenced = (
        db.query(func.sum(models.Order.total_amount))
        .filter(
            models.Order.organization_id == org.id,
            models.Order.status != "cancelled"
        )
        .scalar()
    ) or 0.0
    # Convert Decimal to float for JSON serialization
    revenue_influenced = float(revenue_influenced) if revenue_influenced else 0.0

    # Top products by sales
    top_products_query = (
        db.query(
            models.OrderItem.product_sku,
            models.OrderItem.product_name,
            func.sum(models.OrderItem.quantity).label("total_qty")
        )
        .join(models.Order, models.OrderItem.order_id == models.Order.id)
        .filter(models.Order.organization_id == org.id)
        .group_by(models.OrderItem.product_sku, models.OrderItem.product_name)
        .order_by(func.sum(models.OrderItem.quantity).desc())
        .limit(3)
        .all()
    )

    top_products = [
        {"sku": row[0], "name": row[1], "views": int(row[2])}
        for row in top_products_query
    ]

    # Grounding & safety metrics (mock fallbacks for now, can be computed from messages metadata)
    # Grounding checks: we look for messages where grounding check succeeded
    # For now, let's keep realistic defaults or count them if metadata is present
    total_ai_messages = (
        db.query(func.count(models.Message.id))
        .join(models.Conversation, models.Message.conversation_id == models.Conversation.id)
        .filter(
            models.Conversation.organization_id == org.id,
            models.Message.sender == "ai"
        )
        .scalar()
    ) or 0

    return {
        "total_conversations": total_conversations,
        "ai_active_count": ai_active_count,
        "human_takeover_count": human_takeover_count,
        "resolved_count": closed_count,
        "ai_containment_rate": ai_containment_rate,
        "total_products": total_products,
        "total_messages": total_messages,
        "conversations_today": conversations_today,
        "orders_started": orders_started,
        "orders_completed": orders_completed,
        "revenue_influenced": revenue_influenced,
        "top_products": top_products,
        "total_ai_messages": total_ai_messages
    }
