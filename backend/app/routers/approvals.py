import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas, security
from ..approval_service import (
    get_tenant_approval_requests,
    get_approval_request_by_id,
    get_approval_audit_logs,
    transition_approval_state
)

logger = logging.getLogger(__name__)

_error_schema = {
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {"detail": {"type": "string"}},
            }
        }
    }
}

router = APIRouter(
    prefix="/api/approvals",
    tags=["approvals"],
    responses={
        400: {"description": "Bad Request", **_error_schema},
        401: {"description": "Unauthorized", **_error_schema},
        403: {"description": "Forbidden", **_error_schema},
    },
)


@router.get("", response_model=List[schemas.ApprovalRequestOut])
def list_approvals(
    status: Optional[str] = Query(None, description="Filter by approval status, e.g. WAITING_APPROVAL, APPROVED, SENT"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.get_current_user)
):
    """
    List tenant-scoped approval requests with optional status filtering.
    Enforces Row-Level Security isolation.
    """
    return get_tenant_approval_requests(
        db=db,
        org_id=org.id,
        status=status,
        limit=limit,
        offset=offset
    )


@router.get("/{approval_id}", response_model=schemas.ApprovalRequestOut)
def get_approval_detail(
    approval_id: UUID,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.get_current_user)
):
    """
    Retrieve single approval request with full explainability metadata,
    price/stock snapshots, and audit trail links.
    """
    approval = get_approval_request_by_id(db=db, org_id=org.id, approval_id=approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return approval


@router.post("/{approval_id}/respond", response_model=schemas.ApprovalRequestOut)
def respond_to_approval(
    approval_id: UUID,
    payload: schemas.ApprovalActionRequest,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner", "manager"))
):
    """
    Execute atomic state transition on an ApprovalRequest:
    - approve: Revalidates catalog facts, hashes message, locks row, creates outbox record, and dispatches via WhatsApp BSP.
    - edit_and_send: Stores edited text, updates version & SHA-256 hash, creates outbox record, and dispatches via WhatsApp BSP.
    - reject: Silences draft and transitions conversation to HUMAN_TAKEOVER.
    - takeover: Merchant assumes active control of conversation.
    - snooze / expire: Marks draft as expired.
    """
    approval, send_result = transition_approval_state(
        db=db,
        approval_id=approval_id,
        org_id=org.id,
        user=current_user,
        action=payload.action,
        edited_response=payload.edited_response,
        reason=payload.reason
    )
    return approval


@router.get("/{approval_id}/audit", response_model=List[schemas.ApprovalAuditLogOut])
def get_approval_audit_trail(
    approval_id: UUID,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.get_current_user)
):
    """
    Retrieve complete append-only audit trail for an ApprovalRequest.
    """
    # Verify approval exists and belongs to current tenant
    approval = get_approval_request_by_id(db=db, org_id=org.id, approval_id=approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
        
    return get_approval_audit_logs(db=db, org_id=org.id, approval_id=approval_id)
