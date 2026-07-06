from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks, Header
from sqlalchemy.orm import Session
import logging
import hmac
import hashlib
from typing import Optional
from pydantic import BaseModel
from ..database import get_db, tenant_var, SessionLocal
from .. import models, ai_service
from ..config import settings

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"], responses={400: {"description": "Bad Request"}})
logger = logging.getLogger(__name__)

def verify_meta_signature(payload: bytes, signature_header: str, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected_sig = signature_header.split("sha256=")[1]
    computed_sig = hmac.new(
        app_secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_sig, computed_sig)

@router.get("/whatsapp")
def verify_whatsapp_handshake(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    Standard Meta Webhook validation handshake.
    """
    if hub_mode == "subscribe" and hub_challenge:
        if hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
            return int(hub_challenge)
        else:
            raise HTTPException(status_code=403, detail="Verification token mismatch")
    return {"status": "verification_endpoint"}

def process_message_async(org_id: str, conv_id: str, message_text: str):
    """
    Background task to process AI response asynchronously, 
    preventing Meta webhook timeouts.
    """
    import time
    max_retries = 3
    retry_delay = 1.0
    last_exception = None

    db = SessionLocal()
    db.organization_id = org_id
    token = tenant_var.set(org_id)
    
    try:
        conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
        if not conv or conv.status != "ai_active":
            db.close()
            tenant_var.reset(token)
            return
    except Exception as e:
        logger.error(f"Failed to load conversation: {e}", exc_info=True)
        last_exception = e

    if last_exception is None:
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    db.close()
                    db = SessionLocal()
                    db.organization_id = org_id
                    tenant_var.set(org_id)
                    conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
                    if not conv or conv.status != "ai_active":
                        break

                # Fetch last 10 messages for conversational context
                msg_history = db.query(models.Message).filter(
                    models.Message.conversation_id == conv.id
                ).order_by(models.Message.created_at.asc()).limit(10).all()
                
                history_list = [{"sender": m.sender, "content": m.content} for m in msg_history]
                
                # Intent Classification
                intent = ai_service.classify_intent(message_text, history_list)
                logger.info(f"Classified intent for conversation {conv_id}: {intent}")
                
                # Human Escalation Trigger
                if intent == "human_negotiation":
                    conv.status = "human_takeover"
                    db.commit()
                    
                    # Log AI Handoff notification message
                    handoff_msg = models.Message(
                        conversation_id=conv.id,
                        sender="ai",
                        message_type="text",
                        content="[System Note: Customer requested wholesale/negotiation. Silent escalation triggered.]",
                        status="sent"
                    )
                    db.add(handoff_msg)
                    db.commit()
                    db.close()
                    tenant_var.reset(token)
                    return

                # Context retrieval initialization
                catalog_context = []
                org_token = tenant_var.set(None)
                db.organization_id = None
                try:
                    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
                finally:
                    tenant_var.reset(org_token)
                    db.organization_id = org_id
                    
                if not org:
                    logger.error(f"Organization {org_id} not found in async task.")
                    break

                # Semantic Search Context Retrieval
                if intent in ["product_discovery", "similar_recommendation", "product_info", "availability"]:
                    query_embedding = ai_service.get_embedding(message_text)
                    catalog_matches = db.query(models.Product).order_by(
                        models.Product.embedding.cosine_distance(query_embedding)
                    ).limit(5).all()
                    
                    catalog_context = [{
                        "sku": p.sku,
                        "name": p.name,
                        "price": float(p.price),
                        "color": p.color,
                        "fabric": p.fabric,
                        "sizes": p.sizes,
                        "stock_count": p.stock_count,
                        "description": p.description,
                        "image_urls": p.image_urls,
                        "video_urls": p.video_urls
                    } for p in catalog_matches]

                # Generate grounded reply
                policies_context = org.policies or {}
                ai_reply = ai_service.generate_reply(message_text, history_list, catalog_context, policies_context)

                # Log AI message
                ai_msg = models.Message(
                    conversation_id=conv.id,
                    sender="ai",
                    message_type="text",
                    content=ai_reply,
                    status="sent"
                )
                db.add(ai_msg)
                
                # Update conversation metadata with preferences/budget tracking
                meta = dict(conv.metadata_ or {})
                if "under" in message_text.lower():
                     words = message_text.lower().split()
                     for i, w in enumerate(words):
                          if w == "under" and i+1 < len(words):
                               try:
                                   clean_price = "".join([c for c in words[i+1] if c.isdigit()])
                                   if clean_price:
                                       meta["budget_limit"] = int(clean_price)
                               except ValueError:
                                   pass
                conv.metadata_ = meta
                db.commit()
                db.refresh(ai_msg)
                
                # Broadcast AI response to connected merchant streams
                from ..connection_manager import manager
                manager.broadcast(org_id, "new_message", {
                    "conversation_id": str(conv.id),
                    "message": {
                        "id": str(ai_msg.id),
                        "sender": ai_msg.sender,
                        "message_type": ai_msg.message_type,
                        "content": ai_msg.content,
                        "status": ai_msg.status,
                        "error_message": ai_msg.error_message,
                        "created_at": ai_msg.created_at.isoformat()
                    }
                })
                
                # Trigger real outbound BSP API payload dispatch
                from ..bsp_service import send_whatsapp_message
                send_whatsapp_res = send_whatsapp_message(conv.customer_phone, ai_reply, org)
                
                if send_whatsapp_res.get("status") == "failed":
                    ai_msg.status = "failed"
                    ai_msg.error_message = send_whatsapp_res.get("error")
                    db.commit()
                    manager.broadcast(org_id, "new_message", {
                        "conversation_id": str(conv.id),
                        "message": {
                            "id": str(ai_msg.id),
                            "sender": ai_msg.sender,
                            "message_type": ai_msg.message_type,
                            "content": ai_msg.content,
                            "status": "failed",
                            "error_message": ai_msg.error_message,
                            "created_at": ai_msg.created_at.isoformat()
                        }
                    })
                    logger.error(f"Outbound WhatsApp send failed: {send_whatsapp_res.get('error')}")
                else:
                    logger.info(f"Generated and sent reply: '{ai_reply}' for customer: {conv.customer_phone}")
                
                db.close()
                tenant_var.reset(token)
                return

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed in process_message_async: {e}")
                last_exception = e
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2.0

    # Persistent failure handling
    logger.error(f"Persistent failure in async message processing: {last_exception}", exc_info=True)
    try:
        try:
            db.close()
        except Exception:
            pass
        db = SessionLocal()
        db.organization_id = org_id
        tenant_var.set(org_id)
        conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
        if conv:
            failed_msg = models.Message(
                conversation_id=conv.id,
                sender="ai",
                message_type="text",
                content="System Error: Failed to generate reply.",
                status="failed",
                error_message=str(last_exception)
            )
            db.add(failed_msg)
            db.commit()
            db.refresh(failed_msg)
            
            from ..connection_manager import manager
            manager.broadcast(org_id, "new_message", {
                "conversation_id": str(conv.id),
                "message": {
                    "id": str(failed_msg.id),
                    "sender": failed_msg.sender,
                    "message_type": failed_msg.message_type,
                    "content": failed_msg.content,
                    "status": "failed",
                    "error_message": failed_msg.error_message,
                    "created_at": failed_msg.created_at.isoformat()
                }
            })
    except Exception as e:
        logger.error(f"Failed to save background task error to database: {e}", exc_info=True)
    finally:
        db.close()
        tenant_var.reset(token)


@router.post("/whatsapp")
async def receive_whatsapp_message(
    request: Request, 
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Receives incoming WhatsApp message payload from BSP.
    Decoupled processing via BackgroundTasks.
    """
    payload_bytes = await request.body()
    
    # Signature Verification
    if settings.WHATSAPP_APP_SECRET:
        if not verify_meta_signature(payload_bytes, x_hub_signature_256, settings.WHATSAPP_APP_SECRET):
            logger.warning("Invalid webhook signature rejected.")
            raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        body = await request.json()
    except Exception:
        # If not JSON, try Form data (Twilio default format)
        form_data = await request.form()
        body = dict(form_data)

    logger.info(f"Incoming webhook payload: {body}")

    # Standardize incoming fields
    customer_phone = None
    brand_phone = None
    message_text = ""
    customer_name = "Customer"
    
    # 1. Twilio Format parsing
    if "From" in body:
        from_raw = body.get("From", "")
        customer_phone = from_raw.replace("whatsapp:", "").strip()
        to_raw = body.get("To", "")
        brand_phone = to_raw.replace("whatsapp:", "").strip()
        message_text = body.get("Body", "").strip()
        customer_name = body.get("ProfileName", "Customer")
    # 2. General / Gupshup / Meta Cloud API format parsing
    elif "entry" in body:
        try:
            entry = body["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            if "messages" in value:
                message = value["messages"][0]
                customer_phone = message["from"]
                message_text = message.get("text", {}).get("body", "").strip()
                contacts = value.get("contacts", [{}])[0]
                customer_name = contacts.get("profile", {}).get("name", "Customer")
                brand_phone = value.get("metadata", {}).get("display_phone_number")
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse Meta Cloud API payload: {e}")
            return {"status": "ignored", "reason": "Unparseable payload structure"}
    # 3. Direct Test sandbox payload format (JSON format for direct API calling)
    else:
        customer_phone = body.get("customer_phone")
        brand_phone = body.get("brand_phone")
        message_text = body.get("message")
        customer_name = body.get("customer_name", "Customer")

    if not customer_phone or not message_text:
        return {"status": "ignored", "reason": "No sender phone or message content parsed."}

    # Temporarily unset tenant filter to find the correct org globally
    token = tenant_var.set(None)
    db.organization_id = None
    try:
        org = None
        if brand_phone:
            org = db.query(models.Organization).filter(models.Organization.whatsapp_number == brand_phone).first()
        
        if not org:
            org = db.query(models.Organization).first()
            if not org:
                return {"status": "error", "reason": "No registered brands found in the system."}
    finally:
        tenant_var.reset(token)

    # Set tenant context for the remainder of the synchronous request
    tenant_var.set(org.id)
    db.organization_id = org.id

    # Resolve/Create conversation
    conv = db.query(models.Conversation).filter(
        models.Conversation.organization_id == org.id,
        models.Conversation.customer_phone == customer_phone
    ).first()

    if not conv:
        conv = models.Conversation(
            organization_id=org.id,
            customer_phone=customer_phone,
            customer_name=customer_name,
            status="ai_active"
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

    # Log Customer message synchronously
    cust_msg = models.Message(
        conversation_id=conv.id,
        sender="customer",
        message_type="text",
        content=message_text
    )
    db.add(cust_msg)
    db.commit()
    db.refresh(cust_msg)
    
    # Broadcast customer message to connected merchant streams
    from ..connection_manager import manager
    manager.broadcast(str(org.id), "new_message", {
        "conversation_id": str(conv.id),
        "message": {
            "id": str(cust_msg.id),
            "sender": cust_msg.sender,
            "message_type": cust_msg.message_type,
            "content": cust_msg.content,
            "created_at": cust_msg.created_at.isoformat()
        }
    })

    if conv.status == "human_takeover":
        return {"status": "forwarded_to_agent"}

    # Delegate LLM and database intensive work to background task
    background_tasks.add_task(process_message_async, org.id, conv.id, message_text)

    # Return 200 OK immediately to Meta
    return {"status": "processing"}

class PaymentPayload(BaseModel):
    event: str  # e.g. "payment.captured"
    customer_phone: str
    amount: float
    currency: str = "INR"

@router.post("/payments", responses={404: {"description": "Conversation not found"}})
def receive_payment_webhook(payload: PaymentPayload, db: Session = Depends(get_db)):
    """
    Simulates payment gateway webhook ingestion.
    Updates conversation metadata funnel_stage to 'paid' and logs order_value.
    """
    # Temporarily bypass tenant filtering to find conversation globally by customer phone
    token = tenant_var.set(None)
    db.organization_id = None
    try:
        conv = db.query(models.Conversation).filter(
            models.Conversation.customer_phone == payload.customer_phone
        ).order_by(models.Conversation.updated_at.desc()).first()
        
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found for this customer phone")
            
        org_id = str(conv.organization_id)
        
        # Apply changes
        meta = dict(conv.metadata_ or {})
        meta["funnel_stage"] = "paid"
        meta["order_value"] = payload.amount
        conv.metadata_ = meta
        db.commit()
        db.refresh(conv)
        
        # Broadcast funnel update to merchant dashboard SSE streams
        from ..connection_manager import manager
        manager.broadcast(org_id, "funnel_update", {
            "conversation_id": str(conv.id),
            "funnel_stage": "paid",
            "order_value": payload.amount
        })
        return {"status": "success", "conversation_id": str(conv.id)}
    finally:
        tenant_var.reset(token)
