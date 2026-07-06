from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from ..database import get_db, engine
from .. import models, security
from ..config import settings
import redis
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/liveness")
def liveness():
    """
    Checks if the service is running and responsive.
    """
    return {"status": "alive"}

@router.get("/readiness", responses={503: {"description": "Service Unavailable"}})
def readiness():
    """
    Checks database and Redis connectivity to determine if requests can be served.
    """
    checks = {
        "database": "healthy",
        "redis": "healthy"
    }
    all_healthy = True

    # Database check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Readiness check - DB failed: {e}")
        checks["database"] = f"unhealthy: {e}"
        all_healthy = False

    # Redis check
    try:
        r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        r.ping()
    except Exception as e:
        logger.error(f"Readiness check - Redis failed: {e}")
        checks["redis"] = f"unhealthy: {e}"
        all_healthy = False

    if all_healthy:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready", "checks": checks})
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"status": "not_ready", "checks": checks})

@router.get("/dependencies", responses={503: {"description": "Service Unavailable"}})
def dependencies():
    """
    Checks third-party configuration and APIs (e.g. Gemini API setup).
    """
    checks = {
        "gemini_api_key": "configured" if settings.GEMINI_API_KEY else "not_configured"
    }
    if settings.GEMINI_API_KEY:
        return {"status": "healthy", "dependencies": checks}
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"status": "unhealthy", "dependencies": checks})

@router.get("")
def health_check():
    """
    Aggregate health check.
    """
    return {"status": "ok"}



@router.get("/metrics", responses={401: {"description": "Unauthorized"}})
def health_metrics(
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
):
    """
    Auth-protected metrics endpoint.
    Returns conversation, product, and message counts plus
    human-takeover and AI-containment rates.
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
    ai_active = by_status.get("ai_active", 0)
    human_takeover = by_status.get("human_takeover", 0)
    resolved = by_status.get("resolved", 0)

    # Total products
    total_products = (
        db.query(func.count(models.Product.id))
        .filter(models.Product.organization_id == org.id)
        .scalar()
    ) or 0

    # Total messages (join through conversations owned by org)
    total_messages = (
        db.query(func.count(models.Message.id))
        .join(models.Conversation, models.Message.conversation_id == models.Conversation.id)
        .filter(models.Conversation.organization_id == org.id)
        .scalar()
    ) or 0

    # Rates
    human_takeover_rate = (
        round((human_takeover / total_conversations) * 100, 2)
        if total_conversations > 0
        else 0.0
    )
    ai_containment_rate = (
        round(((total_conversations - human_takeover) / total_conversations) * 100, 2)
        if total_conversations > 0
        else 0.0
    )

    return {
        "total_conversations": total_conversations,
        "conversations_by_status": {
            "ai_active": ai_active,
            "human_takeover": human_takeover,
            "resolved": resolved,
        },
        "total_products": total_products,
        "total_messages": total_messages,
        "human_takeover_rate": human_takeover_rate,
        "ai_containment_rate": ai_containment_rate,
    }
