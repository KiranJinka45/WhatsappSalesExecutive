from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from .. import models, security

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/dashboard")
def dashboard_summary(
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
):
    """
    Auth-protected dashboard summary.
    Returns conversation counts (total, by status, last 24 h),
    product/message totals, and AI containment / human takeover rates.
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
    ai_active_count = by_status.get("ai_active", 0)
    human_takeover_count = by_status.get("human_takeover", 0)
    resolved_count = by_status.get("resolved", 0)

    # Total products
    total_products = (
        db.query(func.count(models.Product.id))
        .filter(models.Product.organization_id == org.id)
        .scalar()
    ) or 0

    # Total messages (via conversations owned by org)
    total_messages = (
        db.query(func.count(models.Message.id))
        .join(models.Conversation, models.Message.conversation_id == models.Conversation.id)
        .filter(models.Conversation.organization_id == org.id)
        .scalar()
    ) or 0

    # Conversations created in the last 24 hours
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
    human_takeover_rate = (
        round((human_takeover_count / total_conversations) * 100, 2)
        if total_conversations > 0
        else 0.0
    )
    ai_containment_rate = (
        round(((total_conversations - human_takeover_count) / total_conversations) * 100, 2)
        if total_conversations > 0
        else 0.0
    )

    return {
        "total_conversations": total_conversations,
        "ai_active_count": ai_active_count,
        "human_takeover_count": human_takeover_count,
        "resolved_count": resolved_count,
        "ai_containment_rate": ai_containment_rate,
        "human_takeover_rate": human_takeover_rate,
        "total_products": total_products,
        "total_messages": total_messages,
        "conversations_today": conversations_today,
    }
