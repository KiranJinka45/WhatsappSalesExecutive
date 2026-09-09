import logging
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas, security

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/outbox",
    tags=["outbox"],
    responses={
        400: {"description": "Bad Request"},
        401: {"description": "Unauthorized"},
        404: {"description": "Outbox record not found"},
    },
)

class ReconcileRequest(BaseModel):
    action: str  # "allow_resend" (or "resend"), "close_loop" (or "mark_delivered", "mark_sent"), "mark_failed"
    notes: Optional[str] = None
    status: Optional[str] = None  # Optional explicit target status ("PENDING", "DELIVERED", "FAILED", "SENT")

class OutboundMessageItem(BaseModel):
    id: UUID
    approval_request_id: Optional[UUID] = None
    conversation_id: UUID
    recipient_phone: str
    content: str
    status: str
    attempt_count: int
    last_error: Optional[str] = None
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None

@router.get("", response_model=list[OutboundMessageItem])
def list_outbox_messages(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.get_current_user)
):
    """
    List outbound messages for the merchant's organization, with optional status filtering
    (e.g., UNKNOWN_PROVIDER_OUTCOME, FAILED, PENDING).
    """
    query = db.query(models.OutboundMessage).filter(
        models.OutboundMessage.organization_id == org.id
    )
    if status:
        query = query.filter(models.OutboundMessage.status == status)
    
    messages = query.order_by(models.OutboundMessage.created_at.desc()).offset(offset).limit(limit).all()
    return [
        OutboundMessageItem(
            id=m.id,
            approval_request_id=m.approval_request_id,
            conversation_id=m.conversation_id,
            recipient_phone=m.recipient_phone,
            content=m.content,
            status=m.status,
            attempt_count=m.attempt_count,
            last_error=m.last_error,
            created_at=m.created_at,
            sent_at=m.sent_at
        )
        for m in messages
    ]

@router.post("/{outbox_id}/reconcile")
def reconcile_outbox_message(
    outbox_id: UUID,
    req: ReconcileRequest,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.get_current_user)
):
    """
    Reconciles an outbound message state, particularly for UNKNOWN_PROVIDER_OUTCOME edge cases.
    - 'allow_resend': resets status to PENDING so outbox worker can retry dispatch.
    - 'close_loop' / 'mark_delivered': marks status as DELIVERED / SENT to acknowledge delivery.
    - 'mark_failed': marks status as FAILED.
    """
    outbound = db.query(models.OutboundMessage).filter(
        models.OutboundMessage.id == outbox_id,
        models.OutboundMessage.organization_id == org.id
    ).first()

    if not outbound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outbound message not found")

    action_lower = req.action.lower()
    previous_status = outbound.status

    if action_lower in ["allow_resend", "resend", "reset", "retry"]:
        target_status = "PENDING"
        outbound.status = target_status
        outbound.attempt_count = 0
        outbound.last_error = f"Manual reconciliation: allowed resend ({req.notes or 'merchant request'})"
        
        # Reset linked approval request if present
        if outbound.approval_request_id:
            appr = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == outbound.approval_request_id).first()
            if appr:
                appr.status = "APPROVED"

    elif action_lower in ["close_loop", "mark_delivered", "delivered", "mark_sent", "sent"]:
        target_status = req.status.upper() if req.status else "DELIVERED"
        outbound.status = target_status
        if not outbound.sent_at:
            outbound.sent_at = datetime.now(timezone.utc)
            
        if outbound.approval_request_id:
            appr = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == outbound.approval_request_id).first()
            if appr:
                appr.status = "SENT"
                if not appr.sent_at:
                    appr.sent_at = datetime.now(timezone.utc)

    elif action_lower in ["mark_failed", "failed"]:
        target_status = "FAILED"
        outbound.status = target_status
        outbound.last_error = req.notes or "Manually marked failed"
        
        if outbound.approval_request_id:
            appr = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == outbound.approval_request_id).first()
            if appr:
                appr.status = "SEND_FAILED"

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid action '{req.action}'. Allowed actions: 'allow_resend', 'close_loop', 'mark_failed'"
        )

    # Log audit trail for reconciliation
    audit_log = models.ApprovalAuditLog(
        organization_id=org.id,
        approval_request_id=outbound.approval_request_id,
        conversation_id=outbound.conversation_id,
        user_id=current_user.id,
        action=f"RECONCILE_{action_lower.upper()}",
        previous_status=previous_status,
        new_status=outbound.status,
        message_content=outbound.content,
        message_hash=outbound.payload_hash,
        revalidation_passed=True,
        metadata_={
            "reconcile_action": req.action,
            "notes": req.notes,
            "outbox_id": str(outbound.id)
        }
    )
    db.add(audit_log)
    db.commit()
    db.refresh(outbound)

    return {
        "status": "success",
        "outbox_id": str(outbound.id),
        "previous_status": previous_status,
        "new_status": outbound.status,
        "action": req.action,
        "notes": req.notes
    }
