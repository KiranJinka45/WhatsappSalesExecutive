import logging
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text
from . import models
from .config import settings
from .connection_manager import manager

logger = logging.getLogger(__name__)


def dispatch_outbound_message(
    db: Session,
    outbox_id: UUID,
    redis_client: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Transactional Outbox Dispatcher Worker.
    Operates asynchronously to dispatch queued PENDING outbound messages to Meta Cloud API.
    
    Safety Gates:
    1. Redis & Database Tenant Kill Switch check (halts and marks CANCELLED if active)
    2. Meta Cloud API Dispatch with 5.0s timeout
    3. Outcome Handling:
       - 200 OK -> SENT
       - Provider rejection -> FAILED
       - ReadTimeout -> UNKNOWN_PROVIDER_OUTCOME & HUMAN_TAKEOVER (halts retries to prevent double sending)
    """
    outbound_msg = db.query(models.OutboundMessage).filter(
        models.OutboundMessage.id == outbox_id,
        models.OutboundMessage.status == "PENDING"
    ).first()

    if not outbound_msg:
        logger.info(f"Outbox message {outbox_id} not found or not in PENDING state.")
        return {"status": "skipped", "reason": "Not in PENDING state"}

    tenant_id = outbound_msg.organization_id
    org = db.query(models.Organization).filter(models.Organization.id == tenant_id).first()
    approval_req = db.query(models.ApprovalRequest).filter(
        models.ApprovalRequest.id == outbound_msg.approval_request_id
    ).first() if outbound_msg.approval_request_id else None

    # 1. Kill Switch Check (Redis & Policy)
    kill_switch_active = False
    if redis_client:
        try:
            kill_switch_key = f"tenant:{tenant_id}:kill_switch:active"
            val = redis_client.get(kill_switch_key)
            if val and (val == b"true" or val == "true" or val == b"1" or val == "1"):
                kill_switch_active = True
        except Exception as r_err:
            logger.warning(f"Failed to query Redis kill switch: {r_err}")

    if not kill_switch_active and org:
        policies = org.policies or {}
        if policies.get("emergency_kill_switch") is True:
            kill_switch_active = True

    if kill_switch_active:
        logger.warning(f"Kill switch active for tenant {tenant_id}. Cancelling outbox {outbox_id}.")
        outbound_msg.status = "CANCELLED"
        if approval_req:
            approval_req.status = "CANCELLED"
        db.commit()
        return {"status": "cancelled", "reason": "Kill switch active"}

    # 2. Advance outbox state to DISPATCHING to claim the job
    outbound_msg.status = "DISPATCHING"
    outbound_msg.attempt_count = (outbound_msg.attempt_count or 0) + 1
    if approval_req:
        approval_req.status = "DISPATCHING"
    db.commit()

    # 3. Construct Meta Cloud API Payload
    clean_phone = "".join([c for c in outbound_msg.recipient_phone if c.isdigit()])
    if clean_phone and not outbound_msg.recipient_phone.startswith("+"):
        clean_phone = f"{clean_phone}"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": outbound_msg.content
        }
    }

    from .security import decrypt_token
    raw_token = getattr(org, "whatsapp_access_token", None) or getattr(settings, "WHATSAPP_ACCESS_TOKEN", None) or "mock_token"
    token = decrypt_token(raw_token)
    phone_id = getattr(org, "whatsapp_phone_number_id", None) or getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None) or "mock_phone_id"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    url = f"{settings.WHATSAPP_API_BASE_URL}/{settings.META_API_VERSION}/{phone_id}/messages"

    is_emulator = "localhost" in settings.WHATSAPP_API_BASE_URL or "127.0.0.1" in settings.WHATSAPP_API_BASE_URL
    is_mock = (token == "mock_token" and phone_id == "mock_phone_id" and not is_emulator)

    if is_mock:
        # Mock / Sandbox testing fallback when no provider credentials configured
        mock_msg_id = f"wamid.mock.{outbox_id}"
        outbound_msg.status = "SENT"
        outbound_msg.provider_message_id = mock_msg_id
        outbound_msg.sent_at = datetime.now(timezone.utc)
        if approval_req:
            approval_req.status = "SENT"
            approval_req.sent_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": "sent", "message_id": mock_msg_id, "mock": True}

    # 4. Meta API Dispatch & Outcome Handling
    try:
        with httpx.Client() as client:
            response = client.post(url, json=payload, headers=headers, timeout=5.0)
            
            if response.status_code == 200:
                res_data = response.json()
                msg_id = res_data.get("messages", [{}])[0].get("id") or f"wamid.{outbox_id}"
                outbound_msg.status = "SENT"
                outbound_msg.provider_message_id = msg_id
                outbound_msg.sent_at = datetime.now(timezone.utc)
                if approval_req:
                    approval_req.status = "SENT"
                    approval_req.sent_at = datetime.now(timezone.utc)
                db.commit()
                return {"status": "sent", "message_id": msg_id, "mock": False}
            else:
                err_text = response.text
                logger.error(f"Meta API Error for outbox {outbox_id}: {err_text}")
                outbound_msg.status = "FAILED"
                outbound_msg.last_error = err_text
                if approval_req:
                    approval_req.status = "SEND_FAILED"
                    approval_req.error_message = err_text
                db.commit()
                return {"status": "failed", "error": err_text}

    except httpx.TimeoutException as timeout_err:
        # CRITICAL: Unknown Provider Outcome Handling
        # Halts automatic retries to prevent double-messaging
        err_msg = f"Provider Network Timeout: {timeout_err}"
        logger.error(f"Provider Timeout for outbox {outbox_id}. Marking UNKNOWN_PROVIDER_OUTCOME.")
        outbound_msg.status = "UNKNOWN_PROVIDER_OUTCOME"
        outbound_msg.last_error = err_msg
        if approval_req:
            approval_req.status = "SEND_FAILED"
            approval_req.error_message = err_msg
            conv = db.query(models.Conversation).filter(models.Conversation.id == approval_req.conversation_id).first()
            if conv:
                conv.status = "HUMAN_TAKEOVER"
        db.commit()
        return {"status": "unknown_timeout", "error": err_msg}

    except Exception as ex:
        err_msg = str(ex)
        logger.error(f"Failed to dispatch message to Meta: {err_msg}", exc_info=True)
        outbound_msg.status = "FAILED"
        outbound_msg.last_error = err_msg
        if approval_req:
            approval_req.status = "SEND_FAILED"
            approval_req.error_message = err_msg
        db.commit()
        return {"status": "failed", "error": err_msg}
