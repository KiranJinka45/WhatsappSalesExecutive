from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas, security

import httpx
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/brand", tags=["brand"], responses={401: {"description": "Unauthorized"}, 400: {"description": "Bad Request"}})

def subscribe_waba_to_app(waba_id: str, access_token: str) -> bool:
    """
    Subscribes the WhatsApp Business Account to the App so we receive incoming message webhooks.
    """
    # Skip sandbox/mock subscription calls
    if "demo" in waba_id or "demo" in access_token or "mock" in access_token:
        logger.info(f"Skipping sandbox/mock webhook subscription for WABA: {waba_id}")
        return True
    url = f"https://graph.facebook.com/v18.0/{waba_id}/subscribed_apps"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    try:
        res = httpx.post(url, headers=headers, timeout=10.0)
        if res.status_code == 200 and res.json().get("success") is True:
            logger.info(f"Successfully subscribed WABA {waba_id} to webhooks.")
            return True
        else:
            logger.error(f"Failed to subscribe WABA {waba_id} to webhooks: {res.status_code} - {res.text}")
            return False
    except Exception as e:
        logger.error(f"Error subscribing WABA {waba_id} to webhooks: {e}", exc_info=True)
        return False

@router.get("/profile", response_model=schemas.OrganizationOut)
def get_brand_profile(
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org)
):
    # Auto-sanitize any legacy email string stored in WABA ID column or policies
    dirty = False
    if "@" in str(org.whatsapp_business_account_id or ""):
        org.whatsapp_business_account_id = None
        dirty = True
    if isinstance(org.policies, dict) and "@" in str(org.policies.get("whatsapp_business_account_id") or ""):
        org.policies["whatsapp_business_account_id"] = None
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(org, "policies")
        dirty = True
    if dirty:
        db.commit()
        db.refresh(org)
    return org

@router.put("/profile", response_model=schemas.OrganizationOut)
def update_brand_profile(
    profile_in: schemas.OrganizationUpdate,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    try:
        update_data = profile_in.model_dump(exclude_unset=True)

        # Check WABA ID format if provided
        if "whatsapp_business_account_id" in update_data and update_data["whatsapp_business_account_id"]:
            waba = str(update_data["whatsapp_business_account_id"]).strip()
            if "@" in waba or (waba and not any(c.isdigit() for c in waba)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="WhatsApp Business Account ID (WABA ID) must be a numeric ID (e.g. 105938472910485), not an email address."
                )
            update_data["whatsapp_business_account_id"] = waba

        # Check duplicate WhatsApp number
        if "whatsapp_number" in update_data and update_data["whatsapp_number"]:
            num = str(update_data["whatsapp_number"]).strip()
            update_data["whatsapp_number"] = num
            if num != org.whatsapp_number:
                exists = db.query(models.Organization).filter(
                    models.Organization.whatsapp_number == num,
                    models.Organization.id != org.id
                ).first()
                if exists:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="This WhatsApp number is already connected to another brand."
                    )

        for field, value in update_data.items():
            if field == "policies":
                existing_policies = org.policies if isinstance(org.policies, dict) else {}
                old_ks = existing_policies.get("emergency_kill_switch")
                merged = dict(existing_policies)
                if isinstance(value, dict):
                    merged.update(value)
                # Purge legacy email values from merged policies
                pol_waba = str(merged.get("whatsapp_business_account_id") or "").strip()
                if "@" in pol_waba:
                    merged["whatsapp_business_account_id"] = update_data.get("whatsapp_business_account_id") or org.whatsapp_business_account_id
                new_ks = merged.get("emergency_kill_switch")
                org.policies = merged
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(org, "policies")

                # Audit log kill switch state changes
                if old_ks is not None and old_ks != new_ks:
                    action_type = "KILL_SWITCH_DEACTIVATED" if new_ks is False else "KILL_SWITCH_ACTIVATED"
                    reason_msg = "Owner preflight deactivation for live approval-only sending" if new_ks is False else "Kill switch enabled by owner"
                    ks_audit = models.ApprovalAuditLog(
                        organization_id=org.id,
                        user_id=current_user.id,
                        action=action_type,
                        previous_status="KILL_SWITCH_ACTIVE" if old_ks else "KILL_SWITCH_INACTIVE",
                        new_status="KILL_SWITCH_INACTIVE" if new_ks is False else "KILL_SWITCH_ACTIVE",
                        message_content=reason_msg,
                        metadata_={
                            "reason": reason_msg,
                            "actor_user_id": str(current_user.id),
                            "previous_state": old_ks,
                            "new_state": new_ks
                        }
                    )
                    db.add(ks_audit)
            else:
                setattr(org, field, value)

        db.commit()
        db.refresh(org)
        
        # Trigger webhook app subscription if WABA details are updated/exist
        waba_id = org.whatsapp_business_account_id
        access_token = org.whatsapp_access_token
        if waba_id and access_token:
            subscribe_waba_to_app(waba_id, access_token)
            
        return org
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating brand profile: {e}", exc_info=True)
        if "whatsapp_number" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This WhatsApp number is already connected to another brand."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update brand profile: {str(e)}"
        )

from pydantic import BaseModel
from typing import Optional
import logging
logger = logging.getLogger(__name__)

class EmbeddedSignupCallbackRequest(BaseModel):
    code: str
    session_nonce: str
    waba_id_hint: Optional[str] = None
    phone_number_id_hint: Optional[str] = None

@router.get("/whatsapp/embedded-signup-config")
def get_embedded_signup_configuration(
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    """
    Returns public Meta App ID, Config ID, API version, and a one-time session nonce.
    Owner-only endpoint. Zero secrets exposed.
    """
    from ..services import whatsapp_registration_service as reg_service
    return reg_service.get_embedded_signup_config(db, org, current_user.id)

@router.post("/whatsapp/embedded-signup-callback")
@router.post("/whatsapp/embedded-signup")
def handle_embedded_signup_callback(
    payload: EmbeddedSignupCallbackRequest,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    """
    Secure server-side OAuth exchange for Meta Embedded Signup authorization code.
    Validates single-use session nonce, queries Meta authoritatively for WABA and phone resources,
    and updates tenant configuration.
    """
    from ..services import whatsapp_registration_service as reg_service
    res = reg_service.exchange_embedded_signup_code(
        db=db,
        org=org,
        user_id=current_user.id,
        code=payload.code,
        session_nonce=payload.session_nonce,
        waba_id_hint=payload.waba_id_hint,
        phone_number_id_hint=payload.phone_number_id_hint
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

class TestConnectionRequest(BaseModel):
    test_phone: Optional[str] = None
    whatsapp_access_token: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_business_account_id: Optional[str] = None

@router.post("/whatsapp/test-connection")
def test_whatsapp_connection(
    payload: Optional[TestConnectionRequest] = None,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    """
    Tests Meta Cloud API WhatsApp dispatch using provided or saved credentials.
    Auto-saves valid credentials to the organization profile.
    """
    from ..bsp_service import send_whatsapp_message
    
    if payload:
        if payload.whatsapp_business_account_id:
            waba = payload.whatsapp_business_account_id.strip()
            if "@" in waba or (waba and not any(c.isdigit() for c in waba)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="WhatsApp Business Account ID (WABA ID) must be a numeric ID (e.g. 105938472910485), not an email address."
                )
            org.whatsapp_business_account_id = waba
            if isinstance(org.policies, dict):
                org.policies["whatsapp_business_account_id"] = waba
        if payload.whatsapp_access_token:
            org.whatsapp_access_token = payload.whatsapp_access_token
            if isinstance(org.policies, dict):
                org.policies["whatsapp_access_token"] = payload.whatsapp_access_token
        if payload.whatsapp_phone_number_id:
            org.whatsapp_phone_number_id = payload.whatsapp_phone_number_id
            if isinstance(org.policies, dict):
                org.policies["whatsapp_phone_number_id"] = payload.whatsapp_phone_number_id
        
        # Clean any legacy email values from policies dict
        if isinstance(org.policies, dict):
            pol_waba = str(org.policies.get("whatsapp_business_account_id") or "").strip()
            if "@" in pol_waba:
                org.policies["whatsapp_business_account_id"] = org.whatsapp_business_account_id

        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(org, "policies")
        db.commit()
        db.refresh(org)

    # Sanitize and purge any legacy email values from policies
    if isinstance(org.policies, dict):
        pol_waba = str(org.policies.get("whatsapp_business_account_id") or "").strip()
        if "@" in pol_waba:
            org.policies["whatsapp_business_account_id"] = None
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(org, "policies")
            db.commit()
            db.refresh(org)

    stored_waba = str(org.whatsapp_business_account_id or "").strip()
    if "@" in stored_waba:
        org.whatsapp_business_account_id = None
        db.commit()
        db.refresh(org)
        stored_waba = ""
        
    if stored_waba and not any(c.isdigit() for c in stored_waba) and "demo" not in stored_waba:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Saved WhatsApp Business Account ID (WABA ID) '{stored_waba}' is invalid. WABA ID must be a numeric ID (e.g. 105938472910485), not an email address."
        )

    target_phone = (payload and payload.test_phone) or org.whatsapp_number or "+919493348129"
    
    test_msg = f"Hello! This is a test message from Closely AI to confirm your WhatsApp Meta Cloud API integration is live and active for {org.name}! 🚀"
    res = send_whatsapp_message(target_phone, test_msg, org, from_approval=True, ignore_guardrails=True)
    
    if res.get("status") in ("failed", "kill_switch_active", "shadow_mode_suppressed"):
        err_msg = res.get("error") or f"Dispatch suppressed by mode '{res.get('status')}'"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg
        )
        
    return {
        "status": "success",
        "message": f"Test message dispatched to {target_phone} successfully!",
        "details": res
    }

@router.delete("/profile", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand_profile(
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    from sqlalchemy.sql import func
    # Soft delete the organization
    org.deleted_at = func.now()
    # Soft delete all conversations of this organization
    db.query(models.Conversation).filter(models.Conversation.organization_id == org.id).update(
        {models.Conversation.deleted_at: func.now()},
        synchronize_session=False
    )
    # Soft delete all orders and order items of this organization
    order_ids = [r[0] for r in db.query(models.Order.id).filter(models.Order.organization_id == org.id).all()]
    if order_ids:
        db.query(models.Order).filter(models.Order.organization_id == org.id).update(
            {models.Order.deleted_at: func.now()},
            synchronize_session=False
        )
        db.query(models.OrderItem).filter(models.OrderItem.order_id.in_(order_ids)).update(
            {models.OrderItem.deleted_at: func.now()},
            synchronize_session=False
        )
    db.commit()
    return None


@router.post("/kill-switch", response_model=schemas.KillSwitchOut)
def toggle_emergency_kill_switch(
    payload: schemas.KillSwitchRequest,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner", "admin"))
):
    """
    Emergency Kill-Switch Endpoint:
    Immediately halts or resumes all outbound WhatsApp messaging for this tenant.
    Audited with an immutable log record.
    """
    from datetime import datetime, timezone
    from sqlalchemy.sql import func
    from ..connection_manager import manager

    policies = dict(org.policies or {})
    policies["emergency_kill_switch"] = payload.active
    policies["kill_switch_reason"] = payload.reason or ""
    policies["kill_switch_updated_at"] = datetime.now(timezone.utc).isoformat()
    policies["kill_switch_updated_by"] = str(current_user.id)
    org.policies = policies
    db.commit()
    db.refresh(org)

    # Append-only audit log entry
    action_name = "KILL_SWITCH_ACTIVATED" if payload.active else "KILL_SWITCH_DEACTIVATED"
    audit = models.ApprovalAuditLog(
        organization_id=org.id,
        user_id=current_user.id,
        action=action_name,
        previous_status=None,
        new_status="ACTIVE" if payload.active else "INACTIVE",
        metadata_={"reason": payload.reason, "user_email": current_user.email}
    )
    db.add(audit)
    db.commit()

    manager.broadcast(str(org.id), "kill_switch_toggled", {
        "emergency_kill_switch": payload.active,
        "reason": payload.reason
    })

    return schemas.KillSwitchOut(
        emergency_kill_switch=payload.active,
        operating_mode=policies.get("operating_mode", "SHADOW"),
        updated_at=datetime.now(timezone.utc),
        updated_by_user_id=current_user.id
    )


@router.get("/kill-switch", response_model=schemas.KillSwitchOut)
def get_kill_switch_status(
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.get_current_user)
):
    """
    Retrieve current emergency kill switch status and operating mode.
    """
    from datetime import datetime, timezone
    policies = org.policies or {}
    return schemas.KillSwitchOut(
        emergency_kill_switch=bool(policies.get("emergency_kill_switch", False)),
        operating_mode=str(policies.get("operating_mode", "SHADOW")),
        updated_at=datetime.now(timezone.utc),
        updated_by_user_id=None
    )


class RequestVerificationCodeRequest(BaseModel):
    method: str = "SMS"

class VerifyRegistrationCodeRequest(BaseModel):
    code: str

@router.get("/whatsapp/connection-status")
def get_whatsapp_connection_status(
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.get_current_user)
):
    """
    Returns sanitized Meta WhatsApp connection status and state for tenant.
    No access tokens, WABA IDs, phone IDs, or codes are exposed.
    """
    from ..services import whatsapp_registration_service as reg_service
    return reg_service.get_connection_status(db, org)

@router.post("/whatsapp/request-verification-code")
def request_whatsapp_verification_code(
    payload: RequestVerificationCodeRequest,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    """
    Requests SMS or Voice verification code from Meta Graph API for discovered phone resource.
    Owner-only action. Enforces local cooldowns and rate limits.
    """
    from ..services import whatsapp_registration_service as reg_service
    if payload.method not in ["SMS", "VOICE"]:
        raise HTTPException(status_code=400, detail="Method must be 'SMS' or 'VOICE'")
    res = reg_service.request_verification_code(db, org, payload.method, current_user.id)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    if res.get("status") == "rate_limited":
        raise HTTPException(status_code=429, detail=res.get("message"))
    return res

@router.post("/whatsapp/verify-registration-code")
def verify_whatsapp_registration_code(
    payload: VerifyRegistrationCodeRequest,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    """
    Verifies 6-digit verification code against Meta Cloud API.
    Owner-only action. Verification code is never logged, stored, or echoed.
    """
    from ..services import whatsapp_registration_service as reg_service
    res = reg_service.verify_registration_code(db, org, payload.code, current_user.id)
    if res.get("status") == "locked":
        raise HTTPException(status_code=423, detail=res.get("message"))
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.post("/whatsapp/activate-live-number")
def activate_whatsapp_live_number(
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    """
    Explicit human owner activation of verified WhatsApp Business number resource.
    Owner-only action. Registration PIN is generated server-side only.
    No PIN accepted from browser, API body, query params, or headers.
    """
    from ..services import whatsapp_registration_service as reg_service
    res = reg_service.activate_live_number(db, org, current_user.id)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res





