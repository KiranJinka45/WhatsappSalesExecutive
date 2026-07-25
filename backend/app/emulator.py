import base64
import uuid
import asyncio
import logging
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

app = FastAPI(title="Meta Cloud API Emulator", description="Local mock server simulating Facebook Graph API for WhatsApp BSP")
logger = logging.getLogger("meta_emulator")

# In-memory stores for testing assertions
received_messages: List[Dict[str, Any]] = []
chaos_config: Dict[str, Any] = {
    "delay_seconds": 0,
    "http_status": 200,
    "error_message": None,
    "fail_count": 0
}

def generate_realistic_wamid(to_phone: str) -> str:
    """
    Generates a realistic base64-encoded Meta Cloud API wamid identifier.
    """
    raw_entropy = f"{to_phone}:{uuid.uuid4().hex[:12]}".encode('utf-8')
    b64_entropy = base64.b64encode(raw_entropy).decode('utf-8').replace('=', '')
    return f"wamid.HBgM{b64_entropy}"

class OutboundText(BaseModel):
    preview_url: Optional[bool] = True
    body: str

class OutboundMedia(BaseModel):
    link: str
    caption: Optional[str] = None

class OutboundPayload(BaseModel):
    messaging_product: str
    recipient_type: Optional[str] = "individual"
    to: str
    type: str
    text: Optional[OutboundText] = None
    image: Optional[OutboundMedia] = None
    video: Optional[OutboundMedia] = None

@app.post("/{version}/{phone_number_id}/messages")
async def send_message(
    version: str,
    phone_number_id: str,
    payload: OutboundPayload,
    authorization: str = Header(None)
):
    """
    Mimics POST graph.facebook.com/{version}/{phone_number_id}/messages
    """
    # 1. Validate Authentication
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuthException: Active Access Token must be used to query information about the current user."
        )

    token = authorization.split("Bearer ")[1]
    
    # 2. Process Chaos Configurations
    if chaos_config.get("fail_count", 0) > 0:
        chaos_config["fail_count"] -= 1
        logger.warning(f"Simulating transient API failure. Remaining fail_count: {chaos_config['fail_count']}")
        raise HTTPException(
            status_code=500,
            detail="Simulated transient server error"
        )

    if chaos_config["delay_seconds"] > 0:
        logger.info(f"Simulating API latency delay of {chaos_config['delay_seconds']}s")
        await asyncio.sleep(chaos_config["delay_seconds"])

    if chaos_config["http_status"] != 200:
        logger.warning(f"Simulating API HTTP crash state: {chaos_config['http_status']}")
        raise HTTPException(
            status_code=chaos_config["http_status"],
            detail=chaos_config["error_message"] or "Simulated error"
        )

    # 3. Log Received Payload
    message_entry = {
        "phone_number_id": phone_number_id,
        "token": token,
        "payload": payload.model_dump(),
        "recipient": payload.to,
        "type": payload.type,
        "content": payload.text.body if payload.type == "text" and payload.text else (
            payload.image.caption if payload.type == "image" and payload.image else (
                payload.video.caption if payload.type == "video" and payload.video else ""
            )
        )
    }
    received_messages.append(message_entry)
    logger.info(f"Emulator received message to {payload.to} [{payload.type}]")

    # 4. Return standard Graph API success structure
    msg_id = generate_realistic_wamid(payload.to)
    return {
        "messaging_product": "whatsapp",
        "contacts": [
            {
                "input": payload.to,
                "wa_id": payload.to
            }
        ],
        "messages": [
            {
                "id": msg_id
            }
        ]
    }

@app.get("/api/emulator/messages")
def get_received_messages():
    """
    Test helper to retrieve all logged outbound deliveries.
    """
    return received_messages

class ChaosSettings(BaseModel):
    delay_seconds: int = 0
    http_status: int = 200
    error_message: Optional[str] = None
    fail_count: int = 0

@app.post("/api/emulator/configure-chaos")
def configure_chaos(settings: ChaosSettings):
    """
    Dynamically trigger rate-limiting or latency parameters.
    """
    chaos_config["delay_seconds"] = settings.delay_seconds
    chaos_config["http_status"] = settings.http_status
    chaos_config["error_message"] = settings.error_message
    chaos_config["fail_count"] = settings.fail_count
    return {"status": "chaos_configured", "config": chaos_config}

@app.post("/api/emulator/clear")
def clear_emulator():
    """
    Resets historical logs and failure state.
    """
    received_messages.clear()
    chaos_config["delay_seconds"] = 0
    chaos_config["http_status"] = 200
    chaos_config["error_message"] = None
    chaos_config["fail_count"] = 0
    return {"status": "cleared"}
