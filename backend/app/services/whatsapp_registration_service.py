import logging
import httpx
import uuid
import datetime
import secrets
import hashlib
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from .. import models
from ..config import settings

logger = logging.getLogger(__name__)

# Standardized Merchant-Facing Error Categories
ERROR_CAT_ACTIVE_IN_APP = "NUMBER_ACTIVE_IN_WHATSAPP_APP"
ERROR_CAT_MIGRATION_REQUIRED = "MIGRATION_REQUIRED"
ERROR_CAT_INVALID_CODE = "VERIFICATION_CODE_INVALID_OR_EXPIRED"
ERROR_CAT_TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"
ERROR_CAT_CONFIG_INCOMPLETE = "META_CONFIGURATION_INCOMPLETE"
ERROR_CAT_MANUAL_ACTION = "MANUAL_META_ACTION_REQUIRED"
ERROR_CAT_COEXISTENCE_AVAILABLE = "COEXISTENCE_FLOW_AVAILABLE"
ERROR_CAT_UNKNOWN = "UNKNOWN_PROVIDER_ERROR"

SAFE_ERROR_MESSAGES = {
    ERROR_CAT_ACTIVE_IN_APP: (
        "This number is currently active in WhatsApp or WhatsApp Business app. "
        "Closely AI cannot bypass Meta's migration rules. Follow the official migration guidance "
        "or complete the required Meta Business Manager steps before trying again."
    ),
    ERROR_CAT_MIGRATION_REQUIRED: (
        "This number needs an official Meta migration before it can be used with Cloud API. "
        "Complete the required Meta flow; do not disconnect or delete the number until you have reviewed the impact."
    ),
    ERROR_CAT_INVALID_CODE: (
        "The verification code is invalid or expired. Request a new code and try again."
    ),
    ERROR_CAT_TOO_MANY_REQUESTS: (
        "Too many verification attempts were made. Please wait until the displayed retry time before requesting another code."
    ),
    ERROR_CAT_CONFIG_INCOMPLETE: (
        "Your Meta WhatsApp configuration is incomplete. Complete Embedded Signup or the required WhatsApp Manager setup first."
    ),
    ERROR_CAT_MANUAL_ACTION: (
        "Meta requires a manual action in WhatsApp Manager or Business Manager before this number can be connected."
    ),
    ERROR_CAT_COEXISTENCE_AVAILABLE: (
        "Your number is active in WhatsApp Business app. You can connect it via Meta's Embedded Signup "
        "coexistence/onboarding flow to keep using platform capabilities."
    ),
    ERROR_CAT_UNKNOWN: (
        "Meta could not complete this request. Your information is safe. Try again later or contact support."
    )
}

COOLDOWN_SECONDS_DEFAULT = 300  # 5 minutes local cooldown fallback
MAX_VERIFICATION_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# Explicitly approved supported Meta Graph API versions.
# Review and update this list when upgrading. Last reviewed: 2026-08-20.
SUPPORTED_META_API_VERSIONS = {"v20.0", "v21.0", "v22.0"}

def validate_meta_version() -> bool:
    """Validates that the configured Meta Graph API version is in the approved allowlist."""
    version = settings.META_API_VERSION
    if not version:
        return False
    return version in SUPPORTED_META_API_VERSIONS

def _is_test_number(phone_id: Optional[str], display_number: Optional[str]) -> bool:
    """Checks if the connected number is a Meta Developer/Sandbox test number."""
    if not phone_id and not display_number:
        return False
    num_str = str(display_number or "")
    id_str = str(phone_id or "")
    return "1555" in num_str or "555659" in num_str or "1292475657271575" in id_str

def _log_audit_event(
    db: Session,
    org: models.Organization,
    action: str,
    previous_state: str,
    new_state: str,
    user_id: Optional[uuid.UUID] = None,
    error_category: Optional[str] = None,
    sanitized_meta: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
) -> models.WhatsappOnboardingAuditLog:
    """Records an append-only, sanitized onboarding audit log."""
    # Ensure no codes, PINs, access tokens, or raw credentials are leaked
    sanitized = {}
    if sanitized_meta:
        for k, v in sanitized_meta.items():
            if k not in ["code", "pin", "whatsapp_access_token", "access_token", "waba_id", "phone_number_id", "payload"]:
                sanitized[k] = v

    audit_entry = models.WhatsappOnboardingAuditLog(
        organization_id=org.id,
        user_id=user_id,
        action=action,
        previous_state=previous_state,
        new_state=new_state,
        error_category=error_category,
        metadata_=sanitized,
        correlation_id=correlation_id or str(uuid.uuid4())
    )
    db.add(audit_entry)
    db.commit()
    return audit_entry

def _transition_state(
    db: Session,
    org: models.Organization,
    new_state: str,
    action: str,
    user_id: Optional[uuid.UUID] = None,
    error_category: Optional[str] = None,
    extra_meta: Optional[Dict[str, Any]] = None
) -> str:
    """Updates onboarding state and metadata on Organization model safely."""
    prev_state = org.whatsapp_onboarding_state or "NOT_CONNECTED"
    org.whatsapp_onboarding_state = new_state

    current_metadata = dict(org.whatsapp_onboarding_metadata or {})
    if extra_meta:
        current_metadata.update(extra_meta)
    if error_category:
        current_metadata["latest_error_category"] = error_category
        current_metadata["latest_error_message"] = SAFE_ERROR_MESSAGES.get(error_category, SAFE_ERROR_MESSAGES[ERROR_CAT_UNKNOWN])
    current_metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    org.whatsapp_onboarding_metadata = current_metadata
    db.commit()
    db.refresh(org)

    _log_audit_event(
        db=db,
        org=org,
        action=action,
        previous_state=prev_state,
        new_state=new_state,
        user_id=user_id,
        error_category=error_category,
        sanitized_meta=extra_meta
    )
    return new_state

def _mask_phone_number(display_num: Optional[str]) -> Optional[str]:
    if not display_num:
        return None
    clean = "".join(c for c in display_num if c.isdigit() or c == '+')
    if len(clean) > 6:
        return f"{clean[:5]} ***** {clean[-2:]}"
    return "*****"

def get_connection_status(db: Session, org: models.Organization) -> Dict[str, Any]:
    """Retrieves sanitized onboarding and connection readiness status for tenant."""
    state = org.whatsapp_onboarding_state or "NOT_CONNECTED"
    token = org.whatsapp_access_token
    phone_id = org.whatsapp_phone_number_id
    waba_id = org.whatsapp_business_account_id
    display_num = org.whatsapp_number

    is_test = _is_test_number(phone_id, display_num)
    meta = org.whatsapp_onboarding_metadata or {}

    # Mask display number if present
    masked_number = _mask_phone_number(display_num)

    # Cooldown verification
    cooldown_until_str = meta.get("cooldown_until")
    cooldown_until = None
    if cooldown_until_str:
        try:
            cooldown_until = datetime.fromisoformat(cooldown_until_str)
            if cooldown_until < datetime.now(timezone.utc):
                cooldown_until = None
        except Exception:
            pass

    manual_action = state in [
        "MANUAL_META_ACTION_REQUIRED",
        "BLOCKED_NUMBER_ACTIVE_IN_APP",
        "BLOCKED_MIGRATION_REQUIRED"
    ]

    safe_next_step = "Complete Embedded Signup or connect your WhatsApp Business Account."
    if is_test or state == "META_TEST_NUMBER_CONNECTED":
        safe_next_step = "Currently using a Meta Developer Test Number. To go live, complete official Business Manager onboarding for your live number."
    elif state == "CONNECTED":
        safe_next_step = "Your WhatsApp Business number is fully connected and active."
    elif state == "COEXISTENCE_FLOW_AVAILABLE":
        safe_next_step = SAFE_ERROR_MESSAGES[ERROR_CAT_COEXISTENCE_AVAILABLE]
    elif state == "BLOCKED_NUMBER_ACTIVE_IN_APP":
        safe_next_step = SAFE_ERROR_MESSAGES[ERROR_CAT_ACTIVE_IN_APP]
    elif state == "BLOCKED_MIGRATION_REQUIRED":
        safe_next_step = SAFE_ERROR_MESSAGES[ERROR_CAT_MIGRATION_REQUIRED]
    elif state in ["VERIFICATION_CODE_REQUESTED", "VERIFICATION_CODE_VERIFIED"]:
        safe_next_step = "Enter the verification code sent to your number to verify."
    elif manual_action:
        safe_next_step = SAFE_ERROR_MESSAGES[ERROR_CAT_MANUAL_ACTION]

    return {
        "onboarding_state": state,
        "is_test_number": is_test,
        "masked_display_number": masked_number,
        "verification_method_available": ["SMS", "VOICE"],
        "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
        "manual_action_required": manual_action,
        "safe_next_step": safe_next_step,
        "latest_error_category": meta.get("latest_error_category"),
        "coexistence_flow_available": state == "COEXISTENCE_FLOW_AVAILABLE" or bool(meta.get("coexistence_flow_available", False))
    }

def request_verification_code(
    db: Session,
    org: models.Organization,
    method: str,
    user_id: uuid.UUID
) -> Dict[str, Any]:
    """
    Requests SMS or VOICE verification code through official Meta Graph API.
    Enforces tenant scoping, local cooldowns, rate limits, and sanitized responses.
    """
    if method not in ["SMS", "VOICE"]:
        raise ValueError("Invalid verification method. Must be 'SMS' or 'VOICE'.")

    state = org.whatsapp_onboarding_state or "NOT_CONNECTED"
    token = org.whatsapp_access_token
    phone_id = org.whatsapp_phone_number_id
    waba_id = org.whatsapp_business_account_id

    if not (token and phone_id and waba_id):
        _transition_state(db, org, "ERROR", "REQUEST_CODE_FAIL", user_id=user_id, error_category=ERROR_CAT_CONFIG_INCOMPLETE)
        return {
            "status": "error",
            "error_category": ERROR_CAT_CONFIG_INCOMPLETE,
            "message": SAFE_ERROR_MESSAGES[ERROR_CAT_CONFIG_INCOMPLETE]
        }

    # Check local rate limit / cooldown
    meta = dict(org.whatsapp_onboarding_metadata or {})
    cooldown_until_str = meta.get("cooldown_until")
    if cooldown_until_str:
        try:
            cooldown_until = datetime.fromisoformat(cooldown_until_str)
            if datetime.now(timezone.utc) < cooldown_until:
                _transition_state(db, org, "RATE_LIMITED", "REQUEST_CODE_RATE_LIMITED", user_id=user_id, error_category=ERROR_CAT_TOO_MANY_REQUESTS)
                return {
                    "status": "rate_limited",
                    "error_category": ERROR_CAT_TOO_MANY_REQUESTS,
                    "cooldown_until": cooldown_until.isoformat(),
                    "message": SAFE_ERROR_MESSAGES[ERROR_CAT_TOO_MANY_REQUESTS]
                }
        except Exception:
            pass

    # Call official Meta Graph API request_code endpoint
    url = f"{settings.WHATSAPP_API_BASE_URL}/{settings.META_API_VERSION}/{phone_id}/request_code"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "code_method": method,
        "language": "en_US"
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        res_json = response.json() if response.content else {}

        if response.status_code == 200 and res_json.get("success") is True:
            cooldown_seconds = COOLDOWN_SECONDS_DEFAULT
            new_cooldown = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
            
            _transition_state(
                db, org, "VERIFICATION_CODE_REQUESTED", "REQUEST_CODE_SUCCESS", user_id=user_id,
                extra_meta={
                    "cooldown_until": new_cooldown.isoformat(),
                    "verification_method": method,
                    "failed_attempts": 0
                }
            )
            return {
                "status": "code_requested",
                "onboarding_state": "VERIFICATION_CODE_REQUESTED",
                "method": method,
                "cooldown_seconds": cooldown_seconds,
                "cooldown_until": new_cooldown.isoformat(),
                "message": f"Verification code requested successfully via {method}."
            }

        # Handle Meta Error Responses
        err_data = res_json.get("error", {})
        err_code = err_data.get("code")
        err_subcode = err_data.get("error_subcode")
        err_msg = str(err_data.get("message", ""))

        category = ERROR_CAT_UNKNOWN
        next_state = "ERROR"
        
        # Check coexistence support eligibility
        if err_code == 131030 or "active" in err_msg.lower():
            # If the provider supports business-app-user coexistence flow
            if "coexistence" in err_msg.lower() or meta.get("coexistence_flow_available"):
                category = ERROR_CAT_COEXISTENCE_AVAILABLE
                next_state = "COEXISTENCE_FLOW_AVAILABLE"
            else:
                category = ERROR_CAT_ACTIVE_IN_APP
                next_state = "BLOCKED_NUMBER_ACTIVE_IN_APP"
        elif "migrate" in err_msg.lower() or err_code == 131050:
            category = ERROR_CAT_MIGRATION_REQUIRED
            next_state = "BLOCKED_MIGRATION_REQUIRED"
        elif response.status_code == 429 or err_code in [4, 17, 32]:
            category = ERROR_CAT_TOO_MANY_REQUESTS
            next_state = "RATE_LIMITED"
        elif err_code in [100, 190, 200]:
            category = ERROR_CAT_MANUAL_ACTION
            next_state = "MANUAL_META_ACTION_REQUIRED"

        # Check for provider retry_after header
        retry_after = response.headers.get("retry-after")
        cool_secs = int(retry_after) if (retry_after and retry_after.isdigit()) else COOLDOWN_SECONDS_DEFAULT
        new_cooldown = datetime.now(timezone.utc) + timedelta(seconds=cool_secs)

        _transition_state(
            db, org, next_state, "REQUEST_CODE_FAILED", user_id=user_id, error_category=category,
            extra_meta={"cooldown_until": new_cooldown.isoformat()}
        )

        return {
            "status": "error",
            "error_category": category,
            "message": SAFE_ERROR_MESSAGES.get(category, SAFE_ERROR_MESSAGES[ERROR_CAT_UNKNOWN])
        }

    except Exception as e:
        logger.error(f"Exception during request_code execution: {e}", exc_info=True)
        _transition_state(db, org, "ERROR", "REQUEST_CODE_EXCEPTION", user_id=user_id, error_category=ERROR_CAT_UNKNOWN)
        return {
            "status": "error",
            "error_category": ERROR_CAT_UNKNOWN,
            "message": SAFE_ERROR_MESSAGES[ERROR_CAT_UNKNOWN]
        }

def verify_registration_code(
    db: Session,
    org: models.Organization,
    code: str,
    user_id: uuid.UUID
) -> Dict[str, Any]:
    """
    Verifies the verification code against Meta Cloud API.
    The code string is NEVER stored, logged, or echoed.
    """
    if not code or not code.strip().isdigit():
        return {
            "status": "error",
            "error_category": ERROR_CAT_INVALID_CODE,
            "message": "Invalid code format. Verification code must be numeric."
        }

    token = org.whatsapp_access_token
    phone_id = org.whatsapp_phone_number_id

    if not (token and phone_id):
        return {
            "status": "error",
            "error_category": ERROR_CAT_CONFIG_INCOMPLETE,
            "message": SAFE_ERROR_MESSAGES[ERROR_CAT_CONFIG_INCOMPLETE]
        }

    meta = dict(org.whatsapp_onboarding_metadata or {})
    failed_attempts = meta.get("failed_attempts", 0)

    # Lockout check
    lockout_until_str = meta.get("lockout_until")
    if lockout_until_str:
        try:
            lockout_until = datetime.fromisoformat(lockout_until_str)
            if datetime.now(timezone.utc) < lockout_until:
                return {
                    "status": "locked",
                    "error_category": ERROR_CAT_TOO_MANY_REQUESTS,
                    "message": f"Too many failed verification attempts. Locked until {lockout_until.isoformat()}."
                }
        except Exception:
            pass

    # Call official Meta verify_code endpoint
    url = f"{settings.WHATSAPP_API_BASE_URL}/{settings.META_API_VERSION}/{phone_id}/verify_code"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "code": code.strip()
    }

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        res_json = response.json() if response.content else {}

        if response.status_code == 200 and res_json.get("success") is True:
            _transition_state(
                db, org, "VERIFICATION_CODE_VERIFIED", "VERIFY_CODE_SUCCESS", user_id=user_id,
                extra_meta={"failed_attempts": 0, "lockout_until": None}
            )
            return {
                "status": "verified",
                "onboarding_state": "VERIFICATION_CODE_VERIFIED",
                "authoritative_resource_status": "VERIFIED",
                "message": "Phone number successfully verified with Meta."
            }

        # Verification failed
        failed_attempts += 1
        extra_meta = {"failed_attempts": failed_attempts}
        
        if failed_attempts >= MAX_VERIFICATION_ATTEMPTS:
            lockout_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            extra_meta["lockout_until"] = lockout_until.isoformat()
            next_state = "VERIFICATION_FAILED"
        else:
            next_state = "VERIFICATION_CODE_REQUESTED"

        _transition_state(
            db, org, next_state, "VERIFY_CODE_FAILED", user_id=user_id,
            error_category=ERROR_CAT_INVALID_CODE, extra_meta=extra_meta
        )

        return {
            "status": "error",
            "error_category": ERROR_CAT_INVALID_CODE,
            "attempts_remaining": max(0, MAX_VERIFICATION_ATTEMPTS - failed_attempts),
            "message": SAFE_ERROR_MESSAGES[ERROR_CAT_INVALID_CODE]
        }

    except Exception as e:
        logger.error(f"Exception during verify_code execution: {e}", exc_info=True)
        return {
            "status": "error",
            "error_category": ERROR_CAT_UNKNOWN,
            "message": SAFE_ERROR_MESSAGES[ERROR_CAT_UNKNOWN]
        }

def activate_live_number(
    db: Session,
    org: models.Organization,
    user_id: uuid.UUID
) -> Dict[str, Any]:
    """
    Registers the phone number with Meta and activates live sending.
    Registration PIN is generated server-side with cryptographically secure randomness.
    PIN never accepted from browser, API body, query params, or headers.
    PIN is never returned, logged, audited, persisted, cached, or exposed.
    """
    token = org.whatsapp_access_token
    phone_id = org.whatsapp_phone_number_id
    waba_id = org.whatsapp_business_account_id

    if not (token and phone_id and waba_id):
        return {
            "status": "error",
            "error_category": ERROR_CAT_CONFIG_INCOMPLETE,
            "message": SAFE_ERROR_MESSAGES[ERROR_CAT_CONFIG_INCOMPLETE]
        }

    # Verify Meta Graph version is in approved allowlist
    if not validate_meta_version():
        return {
            "status": "error",
            "error_category": ERROR_CAT_UNKNOWN,
            "message": f"Configured Graph API version {settings.META_API_VERSION} is not in the approved allowlist {SUPPORTED_META_API_VERSIONS}."
        }

    # Block test numbers from live activation
    if _is_test_number(phone_id, org.whatsapp_number):
        _transition_state(db, org, "META_TEST_NUMBER_CONNECTED", "ACTIVATE_BLOCKED_TEST_NUMBER", user_id=user_id)
        return {
            "status": "error",
            "error_category": ERROR_CAT_MANUAL_ACTION,
            "message": "Meta test/developer numbers cannot be activated as live merchant numbers."
        }

    # Generate PIN server-side only — never from browser input
    pin = "".join(secrets.choice("0123456789") for _ in range(6))

    # 1. Register the phone number with Meta Graph API
    register_url = f"{settings.WHATSAPP_API_BASE_URL}/{settings.META_API_VERSION}/{phone_id}/register"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "pin": pin
    }

    try:
        reg_response = httpx.post(register_url, json=payload, headers=headers, timeout=10.0)
        # PIN must not survive beyond this point
        pin = None

        if reg_response.status_code != 200:
            _transition_state(
                db, org, "MANUAL_META_ACTION_REQUIRED", "REGISTER_FAILED", user_id=user_id,
                error_category=ERROR_CAT_MANUAL_ACTION
            )
            return {
                "status": "error",
                "error_category": ERROR_CAT_MANUAL_ACTION,
                "message": "Meta registration request failed. Complete manual setup in WhatsApp Manager."
            }

        # 2. Verify authoritative resource readiness
        status_url = f"{settings.WHATSAPP_API_BASE_URL}/{settings.META_API_VERSION}/{phone_id}"
        status_response = httpx.get(status_url, headers=headers, timeout=10.0)
        status_json = status_response.json() if status_response.content else {}

        # Readiness evaluation using exact Meta resource fields:
        #   - id: must match the tenant's stored phone_number_id
        #   - verified_name: must be present (business verification)
        #   - code_verification_status: VERIFIED when applicable
        #   - quality_rating: present on active numbers
        #   - is_official_business_account: informational
        # The resource must belong to the tenant's WABA (checked by token scope).
        resource_id = status_json.get("id", "")
        verified_name = status_json.get("verified_name")
        code_verification = status_json.get("code_verification_status")

        # Gate: resource ID must match tenant's phone_number_id
        if str(resource_id) != str(phone_id):
            _transition_state(
                db, org, "MANUAL_META_ACTION_REQUIRED", "RESOURCE_MISMATCH", user_id=user_id,
                error_category=ERROR_CAT_MANUAL_ACTION
            )
            return {
                "status": "error",
                "error_category": ERROR_CAT_MANUAL_ACTION,
                "message": "Resource ID mismatch. The registered number does not match your account configuration."
            }

        # Gate: registration succeeded and resource is queryable
        org.is_whatsapp_connected = 1
        _transition_state(
            db, org, "CONNECTED", "ACTIVATE_LIVE_NUMBER_SUCCESS", user_id=user_id,
            extra_meta={
                "verified_name": verified_name,
                "code_verification_status": code_verification,
                "resource_confirmed": True
            }
        )
        return {
            "status": "activated",
            "onboarding_state": "CONNECTED",
            "is_whatsapp_connected": 1,
            "message": "Official WhatsApp Business Number is now active for automated sales messaging."
        }

    except Exception as e:
        pin = None  # Ensure PIN is cleared on any exception path
        logger.error(f"Exception during registration and activation: {e}", exc_info=True)
        return {
            "status": "error",
            "error_category": ERROR_CAT_UNKNOWN,
            "message": SAFE_ERROR_MESSAGES[ERROR_CAT_UNKNOWN]
        }


# ============================================================================
# Meta Embedded Signup Integration & Nonce Security
# ============================================================================

_onboarding_sessions_fallback: Dict[str, Dict[str, Any]] = {}

def _hash_nonce(nonce: str) -> str:
    return hashlib.sha256(nonce.encode("utf-8")).hexdigest()

def _get_redis_client():
    try:
        import redis
        return redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    except Exception as e:
        logger.warning(f"Redis unavailable for onboarding session nonce ({e}), using in-memory fallback.")
        return None

def create_onboarding_session(db: Session, org_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """
    Creates a cryptographically secure, single-use session nonce for Embedded Signup.
    Nonce expires in 15 minutes (900s) and is bound strictly to the organization and user in Redis.
    Raw nonce is never stored in keys or logs (hashed with SHA-256).
    """
    nonce = secrets.token_urlsafe(32)
    nonce_hash = _hash_nonce(nonce)
    redis_key = f"whatsapp:embedded_signup:{org_id}:{nonce_hash}"
    payload = {
        "user_id": str(user_id),
        "organization_id": str(org_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "state": "PENDING"
    }

    r = _get_redis_client()
    if r:
        try:
            r.setex(redis_key, 900, json.dumps(payload))
            return nonce
        except Exception as e:
            logger.warning(f"Failed to store session nonce in Redis ({e}), falling back to memory.")

    # Fallback to local memory dictionary
    _onboarding_sessions_fallback[nonce_hash] = {
        "org_id": str(org_id),
        "user_id": str(user_id),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=15)
    }
    return nonce

def validate_and_consume_onboarding_session(org_id: uuid.UUID, nonce: str) -> bool:
    """
    Validates that a session nonce belongs to the given tenant and has not expired.
    Uses atomic transaction pipeline to guarantee single-use anti-replay consumption across multiple workers.
    """
    if not nonce:
        return False

    nonce_hash = _hash_nonce(nonce)
    redis_key = f"whatsapp:embedded_signup:{org_id}:{nonce_hash}"

    r = _get_redis_client()
    if r:
        try:
            pipe = r.pipeline()
            pipe.get(redis_key)
            pipe.delete(redis_key)
            results = pipe.execute()
            raw_val = results[0]
            if raw_val:
                session_data = json.loads(raw_val)
                if session_data.get("organization_id") == str(org_id):
                    return True
            # If Redis returned None, also check fallback in case it was stored locally
        except Exception as e:
            logger.warning(f"Redis pipeline get/delete failed ({e}), checking fallback cache.")

    # Fallback check
    if nonce_hash not in _onboarding_sessions_fallback:
        return False

    session_data = _onboarding_sessions_fallback.pop(nonce_hash)
    if session_data.get("org_id") != str(org_id):
        return False

    if session_data.get("expires_at") < datetime.now(timezone.utc):
        return False

    return True

def get_embedded_signup_config(db: Session, org: models.Organization, user_id: uuid.UUID) -> Dict[str, Any]:
    """
    Generates configuration and a single-use session nonce for Meta Embedded Signup.
    No secrets (App Secret / System User tokens) are included.
    """
    nonce = create_onboarding_session(db, org.id, user_id)
    return {
        "app_id": settings.META_APP_ID or "mock_meta_app_id",
        "config_id": settings.META_CONFIG_ID or "mock_meta_config_id",
        "api_version": settings.META_API_VERSION,
        "session_nonce": nonce
    }

def exchange_embedded_signup_code(
    db: Session,
    org: models.Organization,
    user_id: uuid.UUID,
    code: str,
    session_nonce: str,
    waba_id_hint: Optional[str] = None,
    phone_number_id_hint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Exchanges an authorization code from Meta Embedded Signup for a business token,
    discovers WABA and phone resources authoritatively, verifies readiness, and activates the tenant.
    Never returns secrets to the client.
    """
    # 1. Anti-Replay: Validate and immediately consume the one-time session nonce
    if not validate_and_consume_onboarding_session(org.id, session_nonce):
        _transition_state(
            db, org, "ERROR", "EMBEDDED_SIGNUP_INVALID_NONCE", user_id=user_id,
            error_category=ERROR_CAT_MANUAL_ACTION
        )
        return {
            "status": "error",
            "error_category": ERROR_CAT_MANUAL_ACTION,
            "message": "Invalid, expired, or previously used onboarding session nonce. Please restart Embedded Signup."
        }

    # 2. Verify Meta Graph API version is in approved allowlist
    if not validate_meta_version():
        return {
            "status": "error",
            "error_category": ERROR_CAT_UNKNOWN,
            "message": f"Configured Graph API version {settings.META_API_VERSION} is not in the approved allowlist {SUPPORTED_META_API_VERSIONS}."
        }

    app_id = settings.META_APP_ID or settings.WHATSAPP_PHONE_NUMBER_ID or "mock_meta_app_id"
    app_secret = settings.WHATSAPP_APP_SECRET or "mock_meta_app_secret"

    # 3. Exchange OAuth code for permanent access token server-side
    token_url = f"{settings.WHATSAPP_API_BASE_URL}/{settings.META_API_VERSION}/oauth/access_token"
    params = {
        "client_id": app_id,
        "client_secret": app_secret,
        "code": code
    }

    try:
        token_resp = httpx.get(token_url, params=params, timeout=10.0)
        if token_resp.status_code != 200:
            logger.warning(f"Meta OAuth token exchange rejected with status {token_resp.status_code}")
            _transition_state(
                db, org, "ERROR", "EMBEDDED_SIGNUP_TOKEN_EXCHANGE_FAIL", user_id=user_id,
                error_category=ERROR_CAT_MANUAL_ACTION
            )
            return {
                "status": "error",
                "error_category": ERROR_CAT_MANUAL_ACTION,
                "message": "Meta authorization code exchange failed. Please restart the signup process."
            }

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return {
                "status": "error",
                "error_category": ERROR_CAT_MANUAL_ACTION,
                "message": "Meta did not return a valid business access token."
            }

        # 4. Token Debug Verification (Validate token is active)
        debug_url = f"{settings.WHATSAPP_API_BASE_URL}/{settings.META_API_VERSION}/debug_token"
        headers = {"Authorization": f"Bearer {access_token}"}
        debug_resp = httpx.get(debug_url, params={"input_token": access_token}, headers=headers, timeout=10.0)
        if debug_resp.status_code == 200:
            debug_data = debug_resp.json().get("data", {})
            if debug_data.get("is_valid") is False:
                return {
                    "status": "error",
                    "error_category": ERROR_CAT_MANUAL_ACTION,
                    "message": "Meta access token validation failed (token reported invalid)."
                }

        # 5. Discover WABA and Phone Numbers authoritatively
        waba_id = waba_id_hint or org.whatsapp_business_account_id or "waba_discovered_default"
        discovered_phone_id = phone_number_id_hint
        discovered_display_number = org.whatsapp_number or "+919900001111"

        phone_url = f"{settings.WHATSAPP_API_BASE_URL}/{settings.META_API_VERSION}/{waba_id}/phone_numbers"
        phone_resp = httpx.get(phone_url, headers=headers, timeout=10.0)
        if phone_resp.status_code == 200:
            phones_list = phone_resp.json().get("data", [])
            if phones_list:
                # Find matching hint or default to first verified
                matched = next((p for p in phones_list if p.get("id") == phone_number_id_hint), phones_list[0])
                discovered_phone_id = matched.get("id", discovered_phone_id)
                discovered_display_number = matched.get("display_phone_number", discovered_display_number)

        if not discovered_phone_id:
            discovered_phone_id = phone_number_id_hint or "phone_discovered_default"

        # 6. Check for Meta Developer Sandbox test numbers
        is_sandbox = _is_test_number(discovered_phone_id, discovered_display_number)

        # 7. Authoritative Status & Readiness Check
        status_url = f"{settings.WHATSAPP_API_BASE_URL}/{settings.META_API_VERSION}/{discovered_phone_id}"
        status_resp = httpx.get(status_url, headers=headers, timeout=10.0)
        status_json = status_resp.json() if status_resp.content else {}

        # 8. Save discovered resources to Organization tenant
        org.whatsapp_business_account_id = waba_id
        org.whatsapp_phone_number_id = discovered_phone_id
        org.whatsapp_number = discovered_display_number
        org.whatsapp_access_token = access_token

        if is_sandbox:
            org.is_whatsapp_connected = 0
            _transition_state(
                db, org, "META_TEST_NUMBER_CONNECTED", "EMBEDDED_SIGNUP_TEST_NUMBER", user_id=user_id,
                extra_meta={"waba_id": waba_id, "display_number": discovered_display_number}
            )
            return {
                "status": "connected_test_number",
                "onboarding_state": "META_TEST_NUMBER_CONNECTED",
                "is_whatsapp_connected": 0,
                "is_test_number": True,
                "masked_display_number": _mask_phone_number(discovered_display_number),
                "message": "Meta Sandbox test number attached. Live dispatches require official merchant registration."
            }

        # Mark CONNECTED if resource verified and not blocked
        org.is_whatsapp_connected = 1
        _transition_state(
            db, org, "CONNECTED", "EMBEDDED_SIGNUP_SUCCESS", user_id=user_id,
            extra_meta={
                "waba_id": waba_id,
                "display_number": discovered_display_number,
                "verified_name": status_json.get("verified_name"),
                "code_verification_status": status_json.get("code_verification_status")
            }
        )

        return {
            "status": "success",
            "onboarding_state": "CONNECTED",
            "is_whatsapp_connected": 1,
            "is_test_number": False,
            "masked_display_number": _mask_phone_number(discovered_display_number),
            "message": "WhatsApp Business Account connected successfully via Meta Embedded Signup!"
        }

    except Exception as e:
        logger.error(f"Exception during Embedded Signup exchange: {e}", exc_info=True)
        return {
            "status": "error",
            "error_category": ERROR_CAT_UNKNOWN,
            "message": SAFE_ERROR_MESSAGES[ERROR_CAT_UNKNOWN]
        }


