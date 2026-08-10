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
            wasender_url = f"{settings.WASENDER_API_BASE_URL.rstrip('/')}/send-message"
            if any(ext in media_url.lower() for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                payload["imageUrl"] = media_url
            else:
                payload["videoUrl"] = media_url
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

    # 2. Check if credentials are provided for live dispatch
    if not (token and phone_id) and not is_emulator:
        logger.info(f"[MOCK/SANDBOX WHATSAPP DISPATCH] Simulated message to {clean_phone}: '{content}'")
        return {
            "status": "sent",
            "message_id": f"sandbox-msg-{clean_phone}-{org.id}",
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

def download_meta_media(media_id: str, org: models.Organization) -> bytes:
    """
    Downloads media file (audio/image) bytes from Meta Cloud API.
    """
    policies = org.policies or {}
    token = policies.get("whatsapp_access_token") or getattr(settings, "WHATSAPP_ACCESS_TOKEN", None)
    
    # Standardize sandbox/mock check
    is_sandbox = any(test_p in str(org.whatsapp_number or "") for test_p in ["990000", "555157", "123456", "000000", "555"]) or not token

    # Check if we are running in simulator mode or sandbox
    if is_sandbox:
        logger.info(f"[MOCK MEDIA DOWNLOAD] Mocking download for media ID: {media_id}")
        # Return a simple 1-pixel PNG bytes or silent wav bytes depending on context
        # We'll return a simple dummy 1x1 PNG or silent wav depending on file ID hints
        if "audio" in media_id or "voice" in media_id:
            return b'RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x80>\x00\x00\x01\x00\x08\x00data\x00\x00\x00\x00'
        return b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='

    url = f"{settings.WHATSAPP_API_BASE_URL}/{settings.META_API_VERSION}/{media_id}"
    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        # Step 1: Retrieve media metadata to get download URL
        response = httpx.get(url, headers=headers, timeout=15.0)
        if response.status_code != 200:
            logger.error(f"Meta media metadata fetch failed: {response.text}")
            raise ValueError(f"Failed to fetch media metadata from Meta. Status: {response.status_code}")
        
        meta_data = response.json()
        download_url = meta_data.get("url")
        if not download_url:
            logger.error(f"No url found in Meta media metadata response: {meta_data}")
            raise ValueError("No download URL returned from Meta media metadata.")

        # Step 2: Download the binary media content
        media_response = httpx.get(download_url, headers=headers, timeout=30.0)
        if media_response.status_code != 200:
            logger.error(f"Meta media binary download failed: {media_response.text}")
            raise ValueError(f"Failed to download media binary from Meta. Status: {media_response.status_code}")
        
        return media_response.content
    except Exception as e:
        logger.error(f"Error downloading media {media_id}: {e}", exc_info=True)
        raise

def request_pairing_code(phone_number: str, org: models.Organization) -> Dict[str, Any]:
    """
    Requests a 6/8-character WhatsApp Web pairing code (OTP) from the configured
    Evolution API / WasenderAPI gateway for instant connection.
    """
    policies = org.policies or {}
    wasender_token = policies.get("wasender_api_token") or getattr(settings, "WASENDER_API_TOKEN", None)
    wasender_session = policies.get("wasender_session_id") or getattr(settings, "WASENDER_SESSION_ID", None) or "kiran"
    
    if not wasender_token:
        logger.error("WasenderAPI token is not configured.")
        return {"status": "failed", "error": "WhatsApp Gateway API Token (WASENDER_API_TOKEN) is not configured."}

    # Clean phone number format
    clean_phone = "".join([c for c in phone_number if c.isdigit()])
    
    # Evolution API / WasenderAPI pairing code endpoint
    base_url = settings.WASENDER_API_BASE_URL.rstrip('/')
    url = f"{base_url}/instance/connection/pairingCode/{wasender_session}"
    
    headers = {
        "apikey": wasender_token,
        "Authorization": f"Bearer {wasender_token}",
        "Content-Type": "application/json"
    }
    
    params = {
        "number": clean_phone,
        "precomposed": "false"
    }

    try:
        # First, ensure instance is created / connected
        create_url = f"{base_url}/instance/create"
        create_payload = {"instanceName": wasender_session, "token": wasender_token, "qrcode": False}
        httpx.post(create_url, json=create_payload, headers=headers, timeout=10.0)

        # Retrieve pairing code
        logger.info(f"Requesting pairing code for session {wasender_session} and phone {clean_phone} via {url}")
        response = httpx.get(url, headers=headers, params=params, timeout=15.0)
        
        if response.status_code == 200:
            res_data = response.json()
            code = res_data.get("code") or res_data.get("pairingCode")
            if code:
                logger.info(f"Pairing code retrieved successfully: {code}")
                return {"status": "success", "code": code}
            else:
                logger.error(f"Pairing code response did not contain 'code': {res_data}")
                return {"status": "failed", "error": f"Failed to retrieve pairing code from gateway response: {res_data}"}
        else:
            logger.error(f"WhatsApp Gateway pairing code request failed: {response.status_code} - {response.text}")
            return {"status": "failed", "error": f"Gateway failed with status {response.status_code}: {response.text}"}
    except Exception as e:
        logger.error(f"Exception requesting pairing code: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}

def check_connection_status(org: models.Organization) -> Dict[str, Any]:
    """
    Checks the current session connection status (connected, disconnected, pairing, etc.).
    """
    policies = org.policies or {}
    wasender_token = policies.get("wasender_api_token") or getattr(settings, "WASENDER_API_TOKEN", None)
    wasender_session = policies.get("wasender_session_id") or getattr(settings, "WASENDER_SESSION_ID", None) or "kiran"
    
    if not wasender_token:
        return {"status": "disconnected", "reason": "No gateway configured."}
        
    base_url = settings.WASENDER_API_BASE_URL.rstrip('/')
    url = f"{base_url}/instance/connectionState/{wasender_session}"
    
    headers = {
        "apikey": wasender_token,
        "Authorization": f"Bearer {wasender_token}"
    }
    
    try:
        response = httpx.get(url, headers=headers, timeout=10.0)
        if response.status_code == 200:
            res_data = response.json()
            # Evolution API returns e.g. {"instance": {"state": "open"}} or {"state": "open"}
            state = res_data.get("state") or res_data.get("instance", {}).get("state", "unknown")
            return {"status": "success", "state": state}
        else:
            return {"status": "failed", "error": response.text}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

