import logging
import httpx
from typing import Optional, Dict, Any
from .config import settings
from . import models

logger = logging.getLogger(__name__)

def send_whatsapp_message(
    to_phone: str,
    content: str,
    org: models.Organization,
    media_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Dispatches outbound message to customer via WhatsApp BSP.
    Uses organization-specific token/id if stored in policies,
    otherwise falls back to global settings or mock delivery for sandbox tests.
    """
    # 1. Fetch credentials (tenant-specific or global fallback)
    policies = org.policies or {}
    token = policies.get("whatsapp_access_token") or getattr(settings, "WHATSAPP_ACCESS_TOKEN", None)
    phone_id = policies.get("whatsapp_phone_number_id") or getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None)
    
    # WasenderAPI Credentials
    wasender_token = policies.get("wasender_api_token") or getattr(settings, "WASENDER_API_TOKEN", None)
    wasender_session = policies.get("wasender_session_id") or getattr(settings, "WASENDER_SESSION_ID", None) or "kiran"

    # Clean destination phone number format (remove non-digits)
    clean_phone = "".join([c for c in to_phone if c.isdigit()])

    # Check if we are targeting the local emulator
    is_emulator = "localhost" in settings.WHATSAPP_API_BASE_URL or "127.0.0.1" in settings.WHATSAPP_API_BASE_URL

    # 1b. If WasenderAPI token is configured, use WasenderAPI gateway
    if wasender_token:
        wasender_url = f"{settings.WASENDER_API_BASE_URL.rstrip('/')}/send-text"
        headers = {
            "Authorization": f"Bearer {wasender_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "session": wasender_session,
            "to": clean_phone,
            "text": content
        }
        if media_url:
            payload["media_url"] = media_url
        try:
            response = httpx.post(wasender_url, json=payload, headers=headers, timeout=10.0)
            if response.status_code in (200, 201):
                res_data = response.json()
                msg_id = res_data.get("id") or res_data.get("message_id") or f"wasender-{clean_phone}"
                logger.info(f"WasenderAPI message sent successfully to {clean_phone}. ID: {msg_id}")
                return {"status": "sent", "message_id": msg_id, "mock": False}
            else:
                logger.error(f"WasenderAPI dispatch failed with status {response.status_code}: {response.text}")
                return {"status": "failed", "error": response.text, "mock": False}
        except Exception as e:
            logger.error(f"Exception during WasenderAPI request: {e}", exc_info=True)
            return {"status": "failed", "error": str(e), "mock": False}

    # 2. Check if Meta credentials are present - if not, run mock delivery for local sandbox testing
    if not (token and phone_id) and not is_emulator:
        logger.info(f"[MOCK WHATSAPP DISPATCH] Send message to {clean_phone}: '{content}'")
        return {
            "status": "sent",
            "message_id": f"mock-msg-{clean_phone}-{org.id}",
            "mock": True
        }

    # Fallback default mock credentials if testing emulator
    token = token or "mock_access_token"
    phone_id = phone_id or "mock_phone_id"

    # 3. Trigger actual WhatsApp Cloud API POST request
    url = f"{settings.WHATSAPP_API_BASE_URL}/{settings.META_API_VERSION}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_phone,
        "type": "text",
        "text": {
            "preview_url": True,
            "body": content
        }
    }

    if media_url:
        # If media URL is provided, format it as an image/video message
        if any(ext in media_url.lower() for ext in [".png", ".jpg", ".jpeg", ".webp"]):
            payload["type"] = "image"
            payload["image"] = {"link": media_url, "caption": content}
        else:
            payload["type"] = "video"
            payload["video"] = {"link": media_url, "caption": content}
        payload.pop("text", None)

    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
        if response.status_code == 200:
            res_data = response.json()
            msg_id = res_data.get("messages", [{}])[0].get("id")
            logger.info(f"WhatsApp message sent successfully to {clean_phone}. Message ID: {msg_id}")
            return {
                "status": "sent",
                "message_id": msg_id,
                "mock": False
            }
        else:
            logger.error(f"WhatsApp Cloud API failed with status {response.status_code}: {response.text}")
            return {
                "status": "failed",
                "error": response.text,
                "mock": False
            }
    except Exception as e:
        logger.error(f"Exception during WhatsApp API request: {e}", exc_info=True)
        return {
            "status": "failed",
            "error": str(e),
            "mock": False
        }
