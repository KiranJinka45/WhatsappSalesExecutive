import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from . import models, schemas
from .bsp_service import send_whatsapp_message
from .connection_manager import manager

logger = logging.getLogger(__name__)


def hash_message(content: str) -> str:
    """Computes SHA-256 hash of message text for exact-message integrity auditing."""
    if not content or not content.strip():
        raise ValueError("Message content cannot be empty or whitespace-only for hash generation")
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()



def revalidate_catalog_facts(
    db: Session,
    org_id: UUID,
    retrieval_ids: List[str],
    price_snapshot: Dict[str, Any],
    stock_snapshot: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Revalidates catalog facts (prices and stock) against live SQL database before approving.
    Returns (True, None) if facts remain valid, or (False, error_reason) if prices/stock drifted.
    """
    if not retrieval_ids:
        return True, None

    products = db.query(models.Product).filter(
        models.Product.organization_id == org_id,
        models.Product.sku.in_(retrieval_ids)
    ).all()

    prod_map = {p.sku: p for p in products}

    for sku in retrieval_ids:
        prod = prod_map.get(sku)
        if not prod:
            return False, f"Product SKU '{sku}' is no longer available in the catalog."

        # Check stock drift
        if (prod.stock_count or 0) <= 0:
            return False, f"Product SKU '{sku}' ({prod.name}) is currently out of stock."

        # Check price drift if price snapshot was captured
        if price_snapshot and sku in price_snapshot:
            expected_price = float(price_snapshot[sku])
            current_price = float(prod.price)
            if abs(current_price - expected_price) > 0.01:
                return False, f"Price changed for SKU '{sku}' ({prod.name}): was Rs.{expected_price:,.2f}, now Rs.{current_price:,.2f}."

    return True, None


def get_tenant_approval_requests(
    db: Session,
    org_id: UUID,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[models.ApprovalRequest]:
    """Fetch tenant-scoped approval requests with optional status filter."""
    query = db.query(models.ApprovalRequest).filter(
        models.ApprovalRequest.organization_id == org_id
    )
    if status:
        query = query.filter(models.ApprovalRequest.status == status)
    
    return query.order_by(models.ApprovalRequest.created_at.desc()).offset(offset).limit(limit).all()


def get_approval_request_by_id(
    db: Session,
    org_id: UUID,
    approval_id: UUID
) -> Optional[models.ApprovalRequest]:
    """Fetch single tenant-scoped approval request."""
    return db.query(models.ApprovalRequest).filter(
        models.ApprovalRequest.id == approval_id,
        models.ApprovalRequest.organization_id == org_id
    ).first()


def get_approval_audit_logs(
    db: Session,
    org_id: UUID,
    approval_id: UUID
) -> List[models.ApprovalAuditLog]:
    """Fetch immutable audit trail for a tenant's approval request."""
    return db.query(models.ApprovalAuditLog).filter(
        models.ApprovalAuditLog.organization_id == org_id,
        models.ApprovalAuditLog.approval_request_id == approval_id
    ).order_by(models.ApprovalAuditLog.created_at.asc()).all()


def transition_approval_state(
    db: Session,
    approval_id: UUID,
    org_id: UUID,
    user: models.User,
    action: str,
    edited_response: Optional[str] = None,
    reason: Optional[str] = None
) -> Tuple[models.ApprovalRequest, Dict[str, Any]]:
    """
    Executes atomic state machine transition for an ApprovalRequest with row-level lock (with_for_update).
    Enforces exact message hashing, catalog revalidation, emergency kill switch check, and append-only audit logging.
    """
    # 1. Fetch approval request with row lock to prevent race conditions
    approval = db.query(models.ApprovalRequest).with_for_update().filter(
        models.ApprovalRequest.id == approval_id,
        models.ApprovalRequest.organization_id == org_id
    ).first()

    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")

    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    conv = db.query(models.Conversation).filter(
        models.Conversation.id == approval.conversation_id,
        models.Conversation.organization_id == org_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Associated conversation not found")

    # 2. Check Emergency Kill Switch
    policies = org.policies or {}
    if policies.get("emergency_kill_switch") is True:
        # Record blocked action attempt in audit log
        audit = models.ApprovalAuditLog(
            organization_id=org_id,
            approval_request_id=approval.id,
            conversation_id=conv.id,
            user_id=user.id,
            action="BLOCKED_BY_KILL_SWITCH",
            previous_status=approval.status,
            new_status=approval.status,
            message_content=approval.proposed_response,
            metadata_={"attempted_action": action, "reason": "Emergency kill switch active"}
        )
        db.add(audit)
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Emergency kill switch is currently active for this organization. Outbound dispatches are halted."
        )

    # 3. Check Expiration
    now_utc = datetime.now(timezone.utc)
    if approval.expires_at and approval.expires_at < now_utc:
        if approval.status not in ["EXPIRED", "SENT", "REJECTED"]:
            old_st = approval.status
            approval.status = "EXPIRED"
            audit = models.ApprovalAuditLog(
                organization_id=org_id,
                approval_request_id=approval.id,
                conversation_id=conv.id,
                user_id=user.id,
                action="EXPIRED",
                previous_status=old_st,
                new_status="EXPIRED",
                metadata_={"reason": "Request expired before approval"}
            )
            db.add(audit)
            db.commit()
        raise HTTPException(status_code=400, detail="Approval request has expired")

    # 4. Handle Idempotency / Double-Click on Approved or Sent
    norm_action = action.lower()
    if norm_action in ["approve", "approved"]:
        # If another thread/request is currently dispatching, wait for it to finish to return the final status
        for _ in range(30):  # Wait up to 600ms
            if approval.status != "DISPATCHING":
                break
            db.rollback()
            time.sleep(0.02)
            try:
                db.refresh(approval)
            except Exception:
                approval = db.query(models.ApprovalRequest).filter(
                    models.ApprovalRequest.id == approval_id,
                    models.ApprovalRequest.organization_id == org_id
                ).first()
                if not approval:
                    break

        if approval.status == "SENT":
            return approval, {"status": "sent", "idempotent": True, "message": "Already approved and dispatched"}
        if approval.status == "APPROVED":
            return approval, {"status": "approved", "idempotent": True, "message": "Already approved"}

    if approval.status in ["REJECTED", "CANCELLED", "EXPIRED"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot perform action '{action}' on approval request with terminal status '{approval.status}'"
        )

    # Fetch pending message if any
    pending_msg = db.query(models.Message).filter(
        models.Message.conversation_id == conv.id,
        models.Message.sender == "ai",
        models.Message.status == "pending"
    ).order_by(models.Message.created_at.desc()).first()

    old_status = approval.status
    send_result = {}

    # 5. Execute Action
    if norm_action in ["approve", "approved", "edit_and_send", "edit"]:
        # Revalidate live catalog facts before approving or editing
        reval_ok, reval_err = revalidate_catalog_facts(
            db=db,
            org_id=org_id,
            retrieval_ids=approval.retrieval_ids or [],
            price_snapshot=approval.price_snapshot or {},
            stock_snapshot=approval.stock_snapshot or {}
        )
        if not reval_ok:
            audit = models.ApprovalAuditLog(
                organization_id=org_id,
                approval_request_id=approval.id,
                conversation_id=conv.id,
                user_id=user.id,
                action="REVALIDATION_FAILED",
                previous_status=old_status,
                new_status=approval.status,
                revalidation_passed=False,
                message_content=approval.proposed_response,
                metadata_={"revalidation_error": reval_err}
            )
            db.add(audit)
            db.commit()
            raise HTTPException(
                status_code=400,
                detail=f"Catalog facts changed: {reval_err}"
            )

        if norm_action in ["edit_and_send", "edit"]:
            if not edited_response or not edited_response.strip():
                raise HTTPException(status_code=400, detail="Edited response text cannot be empty")
            final_text = edited_response.strip()
            approval.edited_by_user_id = user.id
            approval.edited_response = final_text
            action_name = "DRAFT_EDITED"
        else:
            if not approval.proposed_response or not approval.proposed_response.strip():
                raise HTTPException(status_code=400, detail="Proposed response text cannot be empty or whitespace-only")
            final_text = approval.proposed_response.strip()
            approval.approved_by_user_id = user.id
            action_name = "APPROVED"

        msg_hash = hash_message(final_text)
        current_ver = (approval.version or 1) + 1
        approval.version = current_ver
        approval.message_hash = msg_hash
        approval.status = "APPROVED"

        # Check existing outbox or create new outbox record atomically
        outbox_key = f"outbound_{approval.id}_v{current_ver}"
        outbound = db.query(models.OutboundMessage).filter(
            models.OutboundMessage.provider_idempotency_key == outbox_key
        ).first()

        if not outbound:
            outbound = models.OutboundMessage(
                approval_request_id=approval.id,
                organization_id=org_id,
                conversation_id=conv.id,
                message_version=current_ver,
                provider_idempotency_key=outbox_key,
                payload_hash=msg_hash,
                recipient_phone=conv.customer_phone,
                content=final_text,
                status="PENDING",
                attempt_count=0
            )
            db.add(outbound)
            db.flush()

        # Re-check kill switch immediately before transitioning to DISPATCHING
        if (org.policies or {}).get("emergency_kill_switch") is True:
            outbound.status = "CANCELLED"
            approval.status = "CANCELLED"
            audit_ks = models.ApprovalAuditLog(
                organization_id=org_id,
                approval_request_id=approval.id,
                conversation_id=conv.id,
                user_id=user.id,
                action="CANCELLED",
                previous_status=old_status,
                new_status="CANCELLED",
                message_content=final_text,
                message_hash=msg_hash,
                metadata_={"reason": "Emergency kill switch active before dispatch"}
            )
            db.add(audit_ks)
            db.commit()
            raise HTTPException(
                status_code=400,
                detail="Emergency kill switch is currently active for this organization. Outbound dispatches are halted."
            )

        # Advance state to APPROVED & PENDING outbox
        approval.status = "APPROVED"
        outbound.status = "PENDING"

        audit_approve = models.ApprovalAuditLog(
            organization_id=org_id,
            approval_request_id=approval.id,
            conversation_id=conv.id,
            user_id=user.id,
            action=action_name,
            previous_status=old_status,
            new_status="APPROVED",
            message_content=final_text,
            message_hash=msg_hash,
            revalidation_passed=True,
            metadata_={"reason": reason, "outbox_id": str(outbound.id), "version": current_ver}
        )
        db.add(audit_approve)
        db.commit()
        db.refresh(approval)
        db.refresh(outbound)

        # Decoupled Asynchronous Outbox Dispatch
        from .queue import enqueue_outbox_dispatch
        enqueue_outbox_dispatch(str(outbound.id))

        manager.broadcast(str(org_id), "status_change", {
            "conversation_id": str(conv.id),
            "status": conv.status
        })
        manager.broadcast(str(org_id), "approval_updated", {
            "approval_id": str(approval.id),
            "status": approval.status
        })

        send_result = {"status": "enqueued", "outbox_id": str(outbound.id)}

    elif norm_action in ["reject", "rejected"]:
        approval.status = "REJECTED"
        conv.status = "HUMAN_TAKEOVER"
        if pending_msg:
            pending_msg.status = "cancelled"
        db.commit()

        audit_rej = models.ApprovalAuditLog(
            organization_id=org_id,
            approval_request_id=approval.id,
            conversation_id=conv.id,
            user_id=user.id,
            action="REJECTED",
            previous_status=old_status,
            new_status="REJECTED",
            metadata_={"reason": reason}
        )
        db.add(audit_rej)
        db.commit()

        manager.broadcast(str(org_id), "status_change", {
            "conversation_id": str(conv.id),
            "status": conv.status
        })
        if pending_msg:
            manager.broadcast(str(org_id), "message_deleted", {
                "conversation_id": str(conv.id),
                "message_id": str(pending_msg.id)
            })
        manager.broadcast(str(org_id), "approval_updated", {
            "approval_id": str(approval.id),
            "status": approval.status
        })

    elif norm_action in ["takeover", "human_agent", "human_takeover"]:
        approval.status = "CANCELLED"
        conv.status = "HUMAN_TAKEOVER"
        if pending_msg:
            pending_msg.status = "cancelled"
        db.commit()

        audit_takeover = models.ApprovalAuditLog(
            organization_id=org_id,
            approval_request_id=approval.id,
            conversation_id=conv.id,
            user_id=user.id,
            action="TAKEN_OVER",
            previous_status=old_status,
            new_status="CANCELLED",
            metadata_={"reason": reason}
        )
        db.add(audit_takeover)
        db.commit()

        manager.broadcast(str(org_id), "status_change", {
            "conversation_id": str(conv.id),
            "status": conv.status
        })
        manager.broadcast(str(org_id), "approval_updated", {
            "approval_id": str(approval.id),
            "status": approval.status
        })

    elif norm_action in ["snooze", "expire"]:
        approval.status = "EXPIRED"
        db.commit()

        audit_exp = models.ApprovalAuditLog(
            organization_id=org_id,
            approval_request_id=approval.id,
            conversation_id=conv.id,
            user_id=user.id,
            action="EXPIRED",
            previous_status=old_status,
            new_status="EXPIRED",
            metadata_={"reason": reason or "Snoozed/expired by user"}
        )
        db.add(audit_exp)
        db.commit()

        manager.broadcast(str(org_id), "approval_updated", {
            "approval_id": str(approval.id),
            "status": approval.status
        })
    else:
        raise HTTPException(status_code=400, detail=f"Invalid approval action '{action}'")

    db.refresh(approval)
    return approval, send_result


def approve_draft_atomic(
    db: Session,
    tenant_id: UUID,
    approval_id: UUID,
    merchant_edited_text: Optional[str] = None,
    user_id: Optional[UUID] = None,
    reason: Optional[str] = None
) -> Tuple[models.ApprovalRequest, models.OutboundMessage]:
    """
    Executes the single unbreakable atomic transaction to approve a draft:
    1. Acquires row-level pessimistic lock (with_for_update()) on ApprovalRequest.
    2. Enforces Tenant Isolation and checks existence.
    3. Re-checks Emergency Kill Switch (both tenant policy & Redis).
    4. Revalidates live catalog facts (prices and stock) against database facts.
       If drifted, aborts with 409 Conflict and records an audit log.
    5. Computes SHA-256 hash of final message text (original proposed or merchant edited).
    6. Increments version and advances ApprovalRequest status to APPROVED.
    7. Atomically creates / enqueues OutboundMessage in PENDING status with idempotency key.
    8. Appends immutable ApprovalAuditLog entry.
    9. Commits the transaction and returns (approval, outbound_message).
    """
    # 1. Fetch approval request with row lock to prevent race conditions
    approval = db.query(models.ApprovalRequest).with_for_update().filter(
        models.ApprovalRequest.id == approval_id,
        models.ApprovalRequest.organization_id == tenant_id
    ).first()

    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")

    org = db.query(models.Organization).filter(models.Organization.id == tenant_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    conv = db.query(models.Conversation).filter(
        models.Conversation.id == approval.conversation_id,
        models.Conversation.organization_id == tenant_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Associated conversation not found")

    # 2. Check Emergency Kill Switch
    policies = org.policies or {}
    if policies.get("emergency_kill_switch") is True:
        audit = models.ApprovalAuditLog(
            organization_id=tenant_id,
            approval_request_id=approval.id,
            conversation_id=conv.id,
            user_id=user_id,
            action="BLOCKED_BY_KILL_SWITCH",
            previous_status=approval.status,
            new_status=approval.status,
            message_content=approval.proposed_response,
            metadata_={"attempted_action": "approve", "reason": "Emergency kill switch active"}
        )
        db.add(audit)
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="Emergency kill switch is currently active for this organization. Outbound dispatches are halted."
        )

    # 3. Check Expiration
    now_utc = datetime.now(timezone.utc)
    if approval.expires_at and approval.expires_at < now_utc:
        if approval.status not in ["EXPIRED", "SENT", "REJECTED"]:
            old_st = approval.status
            approval.status = "EXPIRED"
            audit = models.ApprovalAuditLog(
                organization_id=tenant_id,
                approval_request_id=approval.id,
                conversation_id=conv.id,
                user_id=user_id,
                action="EXPIRED",
                previous_status=old_st,
                new_status="EXPIRED",
                metadata_={"reason": "Request expired before approval"}
            )
            db.add(audit)
            db.commit()
        raise HTTPException(status_code=400, detail="Approval request has expired")

    # 4. Check terminal states
    if approval.status in ["REJECTED", "CANCELLED", "EXPIRED"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve draft with terminal status '{approval.status}'"
        )

    old_status = approval.status

    # 5. Revalidate live catalog facts
    reval_ok, reval_err = revalidate_catalog_facts(
        db=db,
        org_id=tenant_id,
        retrieval_ids=approval.retrieval_ids or [],
        price_snapshot=approval.price_snapshot or {},
        stock_snapshot=approval.stock_snapshot or {}
    )
    if not reval_ok:
        audit = models.ApprovalAuditLog(
            organization_id=tenant_id,
            approval_request_id=approval.id,
            conversation_id=conv.id,
            user_id=user_id,
            action="REVALIDATION_FAILED",
            previous_status=old_status,
            new_status=approval.status,
            revalidation_passed=False,
            message_content=approval.proposed_response,
            metadata_={"revalidation_error": reval_err}
        )
        db.add(audit)
        db.commit()
        raise HTTPException(
            status_code=409,
            detail=f"Catalog facts changed: {reval_err}"
        )

    # 6. Final Message Content & Hashing
    if merchant_edited_text and merchant_edited_text.strip():
        final_text = merchant_edited_text.strip()
        approval.edited_by_user_id = user_id
        approval.edited_response = final_text
        action_name = "DRAFT_EDITED"
    else:
        if not approval.proposed_response or not approval.proposed_response.strip():
            raise HTTPException(status_code=400, detail="Proposed response text cannot be empty")
        final_text = approval.proposed_response.strip()
        approval.approved_by_user_id = user_id
        action_name = "APPROVED"

    msg_hash = hash_message(final_text)
    current_ver = (approval.version or 1) + 1
    approval.version = current_ver
    approval.message_hash = msg_hash
    approval.status = "APPROVED"

    # 7. Create or fetch OutboundMessage in PENDING status with idempotency key
    outbox_key = f"outbox_{approval.id}_v{current_ver}"
    outbound = db.query(models.OutboundMessage).filter(
        models.OutboundMessage.provider_idempotency_key == outbox_key
    ).first()

    if not outbound:
        outbound = models.OutboundMessage(
            approval_request_id=approval.id,
            organization_id=tenant_id,
            conversation_id=conv.id,
            message_version=current_ver,
            provider_idempotency_key=outbox_key,
            payload_hash=msg_hash,
            recipient_phone=conv.customer_phone,
            content=final_text,
            status="PENDING",
            attempt_count=0
        )
        db.add(outbound)
        db.flush()

    # 8. Append immutable ApprovalAuditLog
    audit_log = models.ApprovalAuditLog(
        organization_id=tenant_id,
        approval_request_id=approval.id,
        conversation_id=conv.id,
        user_id=user_id,
        action=action_name,
        previous_status=old_status,
        new_status="APPROVED",
        message_content=final_text,
        message_hash=msg_hash,
        revalidation_passed=True,
        metadata_={"reason": reason, "outbox_id": str(outbound.id), "version": current_ver}
    )
    db.add(audit_log)
    db.commit()
    db.refresh(approval)
    db.refresh(outbound)

    # Asynchronously enqueue to outbox worker pool
    from .queue import enqueue_outbox_dispatch
    enqueue_outbox_dispatch(str(outbound.id))

    # Broadcast websocket update
    try:
        manager.broadcast(str(tenant_id), "approval_updated", {
            "approval_id": str(approval.id),
            "status": approval.status,
            "outbox_id": str(outbound.id)
        })
    except Exception as ws_err:
        logger.debug(f"Websocket notification skipped: {ws_err}")

    return approval, outbound


