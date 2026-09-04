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
    media_url: Optional[str] = None,
    from_approval: bool = False,
    ignore_guardrails: bool = False
) -> Dict[str, Any]:
    """
    Dispatches outbound message to customer via WhatsApp BSP.
    - If emergency_kill_switch is True: 100% suppressed and returns kill_switch_active.
    - In SHADOW_MODE: outbound delivery is 100% suppressed and logged internally.
    - In HUMAN_APPROVAL mode: outbound delivery is permitted ONLY if from_approval=True.
    - If ignore_guardrails=True: bypasses kill_switch and shadow mode (used for test connections).
    """
    policies = org.policies or {}
    clean_phone = "".join([c for c in to_phone if c.isdigit()])

    if not ignore_guardrails:
        # 0a. Emergency Kill Switch Guardrail
        if policies.get("emergency_kill_switch") is True:
            logger.warning(f"[KILL SWITCH ACTIVE] Outbound WhatsApp message to {clean_phone} for org {org.id} halted.")
            return {
                "status": "kill_switch_active",
                "error": "Emergency kill switch is currently active for this organization",
                "mock": False
            }

        # 0b. Pilot Operating Mode & Shadow Mode Guardrails
        operating_mode = policies.get("operating_mode", "SHADOW")
        is_shadow = getattr(settings, "SHADOW_MODE", True) or policies.get("shadow_mode", True)

        if not from_approval:
            # Autonomous pipeline sending is suppressed in shadow mode OR human approval mode
            if is_shadow or operating_mode == "HUMAN_APPROVAL":
                logger.info(f"[GUARDRAIL] Autonomous message to {clean_phone} suppressed (mode={operating_mode}, shadow={is_shadow}). Draft logged internally.")
                return {
                    "status": "shadow_mode_suppressed",
                    "message_id": f"shadow-draft-{clean_phone}-{org.id}",
                    "mock": True
                }
        else:
            # Outbound initiated via verified Human Approval
            if is_shadow and operating_mode != "HUMAN_APPROVAL" and policies.get("shadow_mode", True):
                logger.info(f"[SHADOW MODE GUARDRAIL] Approved draft to {clean_phone} suppressed in pure shadow mode.")
                return {
                    "status": "shadow_mode_suppressed",
                    "message_id": f"shadow-draft-{clean_phone}-{org.id}",
                    "mock": True
                }

    token = getattr(org, "whatsapp_access_token", None) or policies.get("whatsapp_access_token") or getattr(settings, "WHATSAPP_ACCESS_TOKEN", None)
    phone_id = getattr(org, "whatsapp_phone_number_id", None) or policies.get("whatsapp_phone_number_id") or getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None)
    
    # Clean destination phone number format (remove non-digits)
    clean_phone = "".join([c for c in to_phone if c.isdigit()])

    # Check if we are targeting the local emulator
    is_emulator = "localhost" in settings.WHATSAPP_API_BASE_URL or "127.0.0.1" in settings.WHATSAPP_API_BASE_URL

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
            err_text = response.text
            logger.warning(f"WhatsApp Cloud API dispatch error status {response.status_code}: {err_text}")
            
            # Format clean, human-readable error messages for known Meta API codes
            formatted_error = err_text
            try:
                err_json = response.json()
                err_obj = err_json.get("error", {})
                err_code = err_obj.get("code")
                err_type = str(err_obj.get("type", ""))
                err_msg = str(err_obj.get("message", ""))
                
                if err_code == 190 or "OAuthException" in err_type or "190" in err_text or "Authentication Error" in err_msg:
                    formatted_error = "Meta System User Access Token has expired or is invalid (OAuth Error 190). Please generate a Permanent System User Access Token in Meta Business Manager (System Users -> Expiration: Never) and paste it into Settings."
                elif err_code == 131030 or "131030" in err_text:
                    formatted_error = f"Recipient phone number {clean_phone} is not added to your Meta Development App allowed test numbers list."
                elif err_code == 131009 or "131009" in err_text or "phone_number_id" in err_msg.lower():
                    formatted_error = f"Invalid Meta Phone Number ID '{phone_id}'. Please check your Phone Number ID in Meta Developer Dashboard."
                elif err_msg:
                    formatted_error = f"{err_msg} (Meta Code: {err_code})"
            except Exception:
                if "190" in err_text or "OAuthException" in err_text:
                    formatted_error = "Meta System User Access Token has expired or is invalid (OAuth Error 190). Please generate a Permanent System User Access Token in Meta Business Manager (System Users -> Expiration: Never) and paste it into Settings."

            # Fallback to hello_world template if outside 24h conversation window
            if ("131047" in err_text or "24 hours" in err_text.lower() or "re-engagement" in err_text.lower()) and not media_url:
                logger.info(f"Attempting template 'hello_world' fallback for 24h window restriction to {clean_phone}...")
                template_payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": clean_phone,
                    "type": "template",
                    "template": {
                        "name": "hello_world",
                        "language": {"code": "en_US"}
                    }
                }
                tpl_resp = httpx.post(url, json=template_payload, headers=headers, timeout=10.0)
                if tpl_resp.status_code == 200:
                    tpl_data = tpl_resp.json()
                    msg_id = tpl_data.get("messages", [{}])[0].get("id")
                    logger.info(f"WhatsApp template 'hello_world' sent successfully to {clean_phone}. Message ID: {msg_id}")
                    return {"status": "sent", "message_id": msg_id, "mock": False}
                else:
                    err_text = tpl_resp.text
                    try:
                        t_json = tpl_resp.json()
                        t_err = t_json.get("error", {})
                        if t_err.get("code") == 190 or t_err.get("type") == "OAuthException":
                            formatted_error = "Meta System User Access Token has expired or is invalid (OAuth Error 190). Please generate a new System User Access Token in Meta Business Manager and update it in Settings."
                    except Exception:
                        pass
            return {
                "status": "failed",
                "error": formatted_error,
                "raw_error": err_text,
                "mock": False
            }
    except httpx.TimeoutException as e:
        logger.error(f"Network timeout during WhatsApp API call to {clean_phone}: {e}")
        return {
            "status": "unknown_timeout",
            "error": f"Network timeout during provider dispatch: {e}",
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

