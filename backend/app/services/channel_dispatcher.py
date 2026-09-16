"""
Unified multi-channel outbound dispatcher for Closely AI.
Routes outbound messages to WhatsApp BSP or Instagram Graph API based on conversation channel.
Supports both synchronous worker threads and asynchronous endpoints.
"""
import logging
from typing import Optional, List, Dict, Any

from .. import models
from ..bsp_service import send_whatsapp_message
from .instagram_service import (
    send_instagram_text,
    send_instagram_image,
    send_instagram_product_carousel,
    send_instagram_text_async,
    send_instagram_image_async,
    send_instagram_product_carousel_async,
)

logger = logging.getLogger("channel_dispatcher")


def dispatch_channel_message(
    org: models.Organization,
    channel: str,
    recipient_id: str,
    text: str,
    media_url: Optional[str] = None,
    products: Optional[List[Dict[str, Any]]] = None,
    from_approval: bool = False,
    ignore_guardrails: bool = False,
) -> Dict[str, Any]:
    """
    Synchronous multi-channel message dispatcher (used in process_message_async worker).
    """
    channel = (channel or "whatsapp").lower()

    if channel == "instagram":
        token = getattr(org, "instagram_access_token", None)
        if not token or not org.is_instagram_connected:
            logger.warning(
                "Instagram not connected for Org %s. Message to %s skipped.",
                org.id, recipient_id,
            )
            return {"status": "skipped", "error": "Instagram not connected", "mock": True}

        try:
            if products and len(products) > 0:
                res = send_instagram_product_carousel(
                    page_access_token_encrypted=token,
                    recipient_igsid=recipient_id,
                    products=products,
                )
                return {"status": "sent", "channel": "instagram", "details": res}
            elif media_url:
                res = send_instagram_image(
                    page_access_token_encrypted=token,
                    recipient_igsid=recipient_id,
                    image_url=media_url,
                )
                return {"status": "sent", "channel": "instagram", "details": res}
            else:
                res = send_instagram_text(
                    page_access_token_encrypted=token,
                    recipient_igsid=recipient_id,
                    text=text,
                )
                return {"status": "sent", "channel": "instagram", "details": res}
        except Exception as e:
            logger.error("Instagram dispatch error to %s: %s", recipient_id, e, exc_info=True)
            return {"status": "failed", "error": str(e), "mock": False}

    # Default: WhatsApp Cloud API
    return send_whatsapp_message(
        to_phone=recipient_id,
        content=text,
        org=org,
        media_url=media_url,
        from_approval=from_approval,
        ignore_guardrails=ignore_guardrails,
    )


async def dispatch_channel_message_async(
    org: models.Organization,
    channel: str,
    recipient_id: str,
    text: str,
    media_url: Optional[str] = None,
    products: Optional[List[Dict[str, Any]]] = None,
    from_approval: bool = False,
    ignore_guardrails: bool = False,
) -> Dict[str, Any]:
    """
    Asynchronous multi-channel message dispatcher (used in async API endpoints).
    """
    channel = (channel or "whatsapp").lower()

    if channel == "instagram":
        token = getattr(org, "instagram_access_token", None)
        if not token or not org.is_instagram_connected:
            logger.warning(
                "Instagram not connected for Org %s. Message to %s skipped.",
                org.id, recipient_id,
            )
            return {"status": "skipped", "error": "Instagram not connected", "mock": True}

        try:
            if products and len(products) > 0:
                res = await send_instagram_product_carousel_async(
                    page_access_token_encrypted=token,
                    recipient_igsid=recipient_id,
                    products=products,
                )
                return {"status": "sent", "channel": "instagram", "details": res}
            elif media_url:
                res = await send_instagram_image_async(
                    page_access_token_encrypted=token,
                    recipient_igsid=recipient_id,
                    image_url=media_url,
                )
                return {"status": "sent", "channel": "instagram", "details": res}
            else:
                res = await send_instagram_text_async(
                    page_access_token_encrypted=token,
                    recipient_igsid=recipient_id,
                    text=text,
                )
                return {"status": "sent", "channel": "instagram", "details": res}
        except Exception as e:
            logger.error("Instagram dispatch error to %s: %s", recipient_id, e, exc_info=True)
            return {"status": "failed", "error": str(e), "mock": False}

    # Default: WhatsApp Cloud API
    return send_whatsapp_message(
        to_phone=recipient_id,
        content=text,
        org=org,
        media_url=media_url,
        from_approval=from_approval,
        ignore_guardrails=ignore_guardrails,
    )
