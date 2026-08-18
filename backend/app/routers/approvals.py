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
    try:
        reqs = get_tenant_approval_requests(
            db=db,
            org_id=org.id,
            status=status,
            limit=limit,
            offset=offset
        )
        validated_reqs = []
        for r in reqs:
            try:
                validated_reqs.append(schemas.ApprovalRequestOut.model_validate(r))
            except Exception as val_err:
                logger.warning(f"Strict validation failed for ApprovalRequest {r.id}, attempting safe attribute mapping: {val_err}")
                try:
                    # Manually sanitize fields to ensure Pydantic parsing succeeds
                    raw_data = {
                        "id": r.id,
                        "conversation_id": r.conversation_id,
                        "organization_id": r.organization_id,
                        "status": r.status or "WAITING_APPROVAL",
                        "reason": r.reason or "Needs verification",
                        "proposed_response": r.proposed_response or "",
                        "ai_recommendation": r.ai_recommendation,
                        "risk_score": getattr(r, "risk_score", 0) or 0,
                        "approved_by_user_id": r.approved_by_user_id,
                        "edited_by_user_id": r.edited_by_user_id,
                        "edited_response": r.edited_response,
                        "message_hash": r.message_hash,
                        "version": r.version or 1,
                        "price_snapshot": r.price_snapshot or {},
                        "stock_snapshot": r.stock_snapshot or {},
                        "expires_at": r.expires_at,
                        "sent_at": r.sent_at,
                        "error_message": r.error_message,
                        "llm_model": r.llm_model,
                        "prompt_version": r.prompt_version,
                        "retrieval_ids": r.retrieval_ids or [],
                        "grounding_score": r.grounding_score or 0.0,
                        "decision_engine_version": r.decision_engine_version,
                        "rule_triggered": r.rule_triggered,
                        "metadata": r.metadata_ or {},
                        "created_at": r.created_at,
                        "updated_at": r.updated_at
                    }
                    validated_reqs.append(schemas.ApprovalRequestOut(**raw_data))
                except Exception as map_err:
                    logger.error(f"Fallback attribute mapping failed for ApprovalRequest {r.id}: {map_err}", exc_info=True)
        return validated_reqs
    except Exception as e:
        logger.error(f"Failed listing approval requests: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve approval list: {str(e)}"
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
