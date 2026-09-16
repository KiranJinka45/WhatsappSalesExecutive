"""
Instagram dispatcher service — sends outbound messages via the Meta Graph API.

Counterpart to bsp_service. Supports plain text DMs, single images, and
generic template product carousels.
Provides both sync and async dispatch functions.
"""
import logging
from typing import Optional, List, Dict, Any
import httpx
from ..config import settings
from ..security import decrypt_token

logger = logging.getLogger("instagram_service")

GRAPH_API_VERSION = getattr(settings, "META_API_VERSION", "v21.0")
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def _get_plain_token(page_access_token_encrypted: str) -> str:
    if not page_access_token_encrypted:
        raise ValueError("Instagram Page Access Token is missing.")
    if str(page_access_token_encrypted).startswith("enc:"):
        return decrypt_token(page_access_token_encrypted)
    return str(page_access_token_encrypted).strip()


def build_carousel_elements(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    elements = []
    for p in products[:10]:
        title = str(p.get("title") or p.get("name") or "Product")[:80]
        image_url = p.get("image_url") or (
            p.get("image_urls")[0] if isinstance(p.get("image_urls"), list) and p.get("image_urls") else None
        )
        
        element: Dict[str, Any] = {"title": title}
        if image_url:
            element["image_url"] = image_url

        subtitle = p.get("subtitle") or p.get("description")
        if subtitle:
            element["subtitle"] = str(subtitle)[:80]

        buttons = p.get("buttons") or []
        formatted_buttons = []
        for btn in buttons[:3]:
            btn_type = btn.get("type", "web_url")
            btn_dict: Dict[str, Any] = {"title": str(btn.get("title", "View"))[:20]}
            if btn_type == "web_url" and btn.get("url"):
                btn_dict["type"] = "web_url"
                btn_dict["url"] = btn["url"]
                formatted_buttons.append(btn_dict)
            elif btn_type == "postback" and btn.get("payload"):
                btn_dict["type"] = "postback"
                btn_dict["payload"] = btn["payload"]
                formatted_buttons.append(btn_dict)

        if formatted_buttons:
            if formatted_buttons[0].get("type") == "web_url":
                element["default_action"] = {
                    "type": "web_url",
                    "url": formatted_buttons[0]["url"],
                }
            element["buttons"] = formatted_buttons

        elements.append(element)
    return elements


# ============================================================================
# Synchronous Dispatchers (Used in background worker threads)
# ============================================================================

def send_instagram_text(page_access_token_encrypted: str, recipient_igsid: str, text: str) -> dict:
    token = _get_plain_token(page_access_token_encrypted)
    url = f"{GRAPH_BASE_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_igsid},
        "message": {"text": text},
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(url, params={"access_token": token}, json=payload)
    if resp.status_code >= 400:
        logger.error("Instagram text send failed: %s %s", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()


def send_instagram_product_carousel(
    page_access_token_encrypted: str,
    recipient_igsid: str,
    products: List[Dict[str, Any]],
) -> dict:
    token = _get_plain_token(page_access_token_encrypted)
    url = f"{GRAPH_BASE_URL}/me/messages"
    elements = build_carousel_elements(products)

    payload = {
        "recipient": {"id": recipient_igsid},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {"template_type": "generic", "elements": elements},
            }
        },
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(url, params={"access_token": token}, json=payload)
    if resp.status_code >= 400:
        logger.error("Instagram carousel send failed: %s %s", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()


def send_instagram_image(
    page_access_token_encrypted: str, recipient_igsid: str, image_url: str
) -> dict:
    token = _get_plain_token(page_access_token_encrypted)
    url = f"{GRAPH_BASE_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_igsid},
        "message": {
            "attachment": {"type": "image", "payload": {"url": image_url, "is_reusable": True}}
        },
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(url, params={"access_token": token}, json=payload)
    if resp.status_code >= 400:
        logger.error("Instagram image send failed: %s %s", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()


# ============================================================================
# Asynchronous Dispatchers (Used in async endpoints)
# ============================================================================

async def send_instagram_text_async(page_access_token_encrypted: str, recipient_igsid: str, text: str) -> dict:
    token = _get_plain_token(page_access_token_encrypted)
    url = f"{GRAPH_BASE_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_igsid},
        "message": {"text": text},
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, params={"access_token": token}, json=payload)
    if resp.status_code >= 400:
        logger.error("Instagram text send failed: %s %s", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()


async def send_instagram_product_carousel_async(
    page_access_token_encrypted: str,
    recipient_igsid: str,
    products: List[Dict[str, Any]],
) -> dict:
    token = _get_plain_token(page_access_token_encrypted)
    url = f"{GRAPH_BASE_URL}/me/messages"
    elements = build_carousel_elements(products)

    payload = {
        "recipient": {"id": recipient_igsid},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {"template_type": "generic", "elements": elements},
            }
        },
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, params={"access_token": token}, json=payload)
    if resp.status_code >= 400:
        logger.error("Instagram carousel send failed: %s %s", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()


async def send_instagram_image_async(
    page_access_token_encrypted: str, recipient_igsid: str, image_url: str
) -> dict:
    token = _get_plain_token(page_access_token_encrypted)
    url = f"{GRAPH_BASE_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_igsid},
        "message": {
            "attachment": {"type": "image", "payload": {"url": image_url, "is_reusable": True}}
        },
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(url, params={"access_token": token}, json=payload)
    if resp.status_code >= 400:
        logger.error("Instagram image send failed: %s %s", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()
